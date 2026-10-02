"""CLOQ agent: tau2 LLMAgent + frozen context policy + decision-state logging.

This is the *only* scaffold difference from tau2's canonical `llm_agent`:
  1. the frozen context policy (plan section 8) is applied to the message list
     before every LLM call (identically for every precision arm);
  2. every decision point is logged with the exact serialized model input.
No planning / reflection / retry heuristics are added.
"""

from __future__ import annotations

import json
import threading
import time
import os
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

from tau2.agent.llm_agent import LLMAgent, LLMAgentState
from tau2.data_model.message import AssistantMessage, MultiToolMessage, UserMessage
from tau2.registry import registry
from tau2.utils.llm_utils import generate, to_litellm_messages, to_tau2_messages

from cloq.context_policy import (
    apply_context_policy,
    canonical_json,
    render_prompt,
    render_prompt_ids,
    sha256_text,
)

# ----------------------------------------------------------------------------
# Decision-state writer (one JSONL per run, thread-safe)
# ----------------------------------------------------------------------------


class DecisionWriter:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._f = open(self.path, "a", encoding="utf-8")

    def write(self, rec: dict) -> None:
        line = json.dumps(rec, ensure_ascii=False)
        with self._lock:
            self._f.write(line + "\n")
            self._f.flush()

    def close(self) -> None:
        with self._lock:
            self._f.close()


_WRITER: Optional[DecisionWriter] = None
_RUN_META: dict = {}


def set_decision_writer(path: Path, run_meta: dict) -> DecisionWriter:
    global _WRITER, _RUN_META
    _WRITER = DecisionWriter(path)
    _RUN_META = dict(run_meta)
    return _WRITER


def close_decision_writer() -> None:
    global _WRITER
    if _WRITER is not None:
        _WRITER.close()
        _WRITER = None


# ----------------------------------------------------------------------------
# Agent
# ----------------------------------------------------------------------------


class CLOQAgent(LLMAgent[LLMAgentState]):
    def __init__(self, tools, domain_policy, llm, llm_args=None, task=None, **_):
        super().__init__(tools=tools, domain_policy=domain_policy, llm=llm, llm_args=llm_args)
        self.task_id = task.id if task is not None else None
        self.trajectory_id = str(uuid.uuid4())
        self.decision_idx = 0
        self.tools_schema = [t.openai_schema for t in self.tools]
        self.tools_sha = sha256_text(canonical_json(self.tools_schema))
        self.system_sha = sha256_text(self.system_prompt)
        self._lg = None
        if os.environ.get("CLOQ_LOOP_GUARD"):  # W69: opt-in loop early-stop guard, new stress panels only (cloq/loop_guard.py)
            from cloq.loop_guard import LiveGuard
            self._lg = LiveGuard(tools, task)

    @classmethod
    def is_stop(cls, message) -> bool:
        # tau2's LLMAgent never stops by itself; only the opt-in loop guard's marker ends an episode from the agent side
        return getattr(message, "content", None) == "###CLOQ_LOOP_EARLY_STOP###"

    @property
    def system_prompt(self) -> str:
        # CLOQ_PROMPT_NONCE appends a neutral session-id line: the perturbation null (re-roll without weight change).
        base = super().system_prompt
        nonce = os.environ.get("CLOQ_PROMPT_NONCE")
        return f"{base}\nSession ID: {nonce}\n" if nonce else base

    def _generate_next_message(self, message, state: LLMAgentState) -> AssistantMessage:
        if isinstance(message, UserMessage) and message.is_audio:
            raise ValueError("User message cannot be audio.")
        if isinstance(message, MultiToolMessage):
            state.messages.extend(message.tool_messages)
        else:
            state.messages.append(message)
        if self._lg is not None:  # W69 loop guard: evaluated before generating, on completed decisions only
            stop = self._lg.before_decision(state.messages, self.task_id, self.trajectory_id, self.decision_idx)
            if stop is not None:
                return stop

        full_msgs = state.system_messages + state.messages
        full_lm = to_litellm_messages(full_msgs)
        kept_lm, cinfo = apply_context_policy(full_lm, self.tools_schema)
        # Rebuild tau2 messages for the kept subset so that tau2.generate does the
        # canonical conversion (identical to what an untruncated call would send).
        kept_msgs = _select_tau2_messages(full_msgs, full_lm, kept_lm)

        t0 = time.time()
        assistant_message = generate(
            model=self.llm,
            tools=self.tools,
            messages=kept_msgs,
            call_name="agent_response",
            **self.llm_args,
        )
        dt = time.time() - t0
        if _DET_TOOL_IDS and assistant_message.is_tool_call():
            # W99p (m24, Mistral tokenizer mode only): the template renders tool-call ids ([CALL_ID]) and vLLM's mistral
            # parser draws them at random, so identical decisions would give different later prompts. Replace them by
            # a function of the decision index (9 alphanumerics, the Mistral id format); a no-op replay then matches.
            assistant_message.tool_calls = [tc.model_copy(update={"id": det_tool_call_id(self.decision_idx, k)})
                                            for k, tc in enumerate(assistant_message.tool_calls)]

        raw = assistant_message.raw_data or {}
        prompt_ids = raw.get("prompt_token_ids")
        choice0 = (raw.get("choices") or [{}])[0]
        completion_ids = choice0.get("token_ids") or (choice0.get("provider_specific_fields") or {}).get("token_ids")
        finish_reason = choice0.get("finish_reason")
        raw_message = choice0.get("message") or {}
        local_ids = render_prompt_ids(kept_lm, self.tools_schema)
        prompt_text = render_prompt(kept_lm, self.tools_schema)

        content = assistant_message.content
        # "[TOOL_CALLS]": Mistral's tool-call control token left in the text by an unparsed call (W99p; m24 only)
        parser_error = bool(content) and ("<tool_call>" in content or "[TOOL_CALLS]" in content) and not assistant_message.is_tool_call()

        margins = _token_margins(choice0.get("logprobs"))

        rec = {
            **_RUN_META,
            "task_id": self.task_id,
            "trajectory_id": self.trajectory_id,
            "decision_idx": self.decision_idx,
            "n_state_messages": len(state.messages),
            "messages": kept_lm,
            "tools_sha256": self.tools_sha,
            "system_sha256": self.system_sha,
            "context": cinfo.__dict__,
            "prompt_sha256": sha256_text(prompt_text),
            "prompt_token_ids": prompt_ids if prompt_ids is not None else local_ids,
            "prompt_ids_from_server": prompt_ids is not None,
            "prompt_ids_match_local": (prompt_ids == local_ids) if prompt_ids is not None else None,
            "n_prompt_tokens": len(prompt_ids) if prompt_ids is not None else len(local_ids),
            "completion_token_ids": completion_ids,
            "n_completion_tokens": (raw.get("usage") or {}).get("completion_tokens"),
            "finish_reason": finish_reason,
            "raw_content": raw_message.get("content"),
            "content": content,
            "tool_calls": [tc.model_dump() for tc in assistant_message.tool_calls] if assistant_message.is_tool_call() else None,
            "parser_error": parser_error,
            "generation_seconds": dt,
            **margins,
        }
        if self._lg is not None:
            self._lg.after_decision(rec)
        if _WRITER is not None:
            _WRITER.write(rec)
        else:
            logger.warning("CLOQAgent: no decision writer set; decision not logged")
        self.decision_idx += 1
        return assistant_message


_DET_TOOL_IDS = os.environ.get("CLOQ_TOKENIZER_MODE") == "mistral"  # W99p; False for every HF-template model


def det_tool_call_id(decision_idx: int, k: int) -> str:
    """Deterministic Mistral tool-call id (exactly 9 alphanumerics): decision index and call position."""
    return f"d{decision_idx % 100000:05d}c{k % 100:02d}"


def _token_margins(lp) -> dict:
    """Per-token decision margins from the server's top-k logprobs (CLOQ_TOP_LOGPROBS > 0).

    margin_t = logprob(chosen token) - logprob(best alternative among the returned top-k); for greedy
    decoding this is the top-1 minus top-2 logit gap at step t. Stored rounded to 1e-4 so the record stays
    small; tokens whose top-k holds no alternative get None.
    """
    content = (lp or {}).get("content") if isinstance(lp, dict) else None
    if not content:
        return {}
    chosen, margin = [], []
    for t in content:
        c = t.get("logprob")
        alts = [a.get("logprob") for a in (t.get("top_logprobs") or []) if a.get("token") != t.get("token")]
        chosen.append(round(c, 4) if c is not None else None)
        margin.append(round(c - max(alts), 4) if (c is not None and alts) else None)
    valid = [m for m in margin if m is not None]
    return {
        "token_logprobs": chosen,
        "token_margins": margin,
        "first_token_margin": margin[0] if margin else None,
        "min_margin": min(valid) if valid else None,
    }


def _select_tau2_messages(full_msgs, full_lm, kept_lm):
    """Map the kept litellm dicts back to the original tau2 message objects.

    apply_context_policy only drops whole messages (never edits them), and
    the litellm list is positionally aligned with the tau2 list, so we keep
    the tau2 objects whose litellm rendering survives, in order.
    """
    assert len(full_msgs) == len(full_lm)
    kept = []
    j = 0
    for m, lm in zip(full_msgs, full_lm):
        if j < len(kept_lm) and lm is kept_lm[j]:
            kept.append(m)
            j += 1
    assert j == len(kept_lm), "context policy mapping failed"
    return kept


def create_cloq_agent(tools, domain_policy, **kwargs):
    return CLOQAgent(
        tools=tools,
        domain_policy=domain_policy,
        llm=kwargs.get("llm"),
        llm_args=kwargs.get("llm_args"),
        task=kwargs.get("task"),
    )


def register_cloq_agent() -> None:
    if registry.get_agent_factory("cloq_agent") is None:
        registry.register_agent_factory(create_cloq_agent, "cloq_agent")
