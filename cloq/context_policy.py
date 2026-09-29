"""Frozen context policy (plan section 8).

The agent's model input at a decision point is
    [system (instructions + policy)] + [tools] + [greeting] + [first user request] + history
rendered by the frozen chat template. When the rendered prompt exceeds
MAX_PROMPT_TOKENS we drop the oldest *units* of history after the first user
request until it fits. A unit is one user message, one assistant text message,
or one assistant tool-call message together with all of its tool results.

The same function is applied to every precision arm.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from transformers import AutoTokenizer

from cloq.config import CHAT_TEMPLATE_KWARGS, MAX_PROMPT_TOKENS, MODEL_ID, MODEL_REVISION

_TOK = None
_TOK_LOCK = threading.Lock()


def get_tokenizer():
    global _TOK
    if _TOK is None:
        with _TOK_LOCK:
            if _TOK is None:
                _TOK = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    return _TOK


def template_view(messages: list[dict]) -> list[dict]:
    """The message list as the vLLM server hands it to the chat template.

    vLLM's chat preprocessing (entrypoints/chat_utils.py) drops an assistant message's `tool_calls` when it is
    None or empty and parses JSON-string tool-call `arguments` into dicts before rendering; tau2's
    to_litellm_messages emits `tool_calls: None` on text turns and JSON-string arguments. Templates that test
    key presence (Llama-3.1: `'tool_calls' in message` then `tool_calls|length`) crash on the raw form and
    render arguments double-encoded, so local rendering (context policy token counts, logged prompt ids) must
    see the same view as the server. For templates that test truthiness and accept string or dict arguments
    (Qwen3/hermes) the rendered prompt is unchanged. Returns new dicts; the input is never modified.
    """
    out = []
    for m in messages:
        if m.get("role") != "assistant" or "tool_calls" not in m:
            out.append(m)
            continue
        tcs = m.get("tool_calls")
        if not tcs:
            out.append({k: v for k, v in m.items() if k != "tool_calls"})
            continue
        if not isinstance(tcs, list):
            out.append(m)
            continue
        new_tcs = []
        for tc in tcs:
            fn = tc.get("function") if isinstance(tc, dict) else None
            if isinstance(fn, dict) and not isinstance(fn.get("arguments"), dict):
                args = fn.get("arguments")
                parsed = {}
                if isinstance(args, str) and args:
                    try:
                        parsed = json.loads(args)
                    except json.JSONDecodeError:
                        parsed = {}
                elif args:
                    parsed = args
                tc = {**tc, "function": {**fn, "arguments": parsed if isinstance(parsed, dict) else {}}}
            new_tcs.append(tc)
        out.append({**m, "tool_calls": new_tcs})
    return out


def render_prompt(messages: list[dict], tools: Optional[list[dict]]) -> str:
    """Render exactly what the chat template produces for a generation request."""
    tok = get_tokenizer()
    return tok.apply_chat_template(
        template_view(messages), tools=tools or None, add_generation_prompt=True, tokenize=False, **CHAT_TEMPLATE_KWARGS
    )


def render_prompt_ids(messages: list[dict], tools: Optional[list[dict]]) -> list[int]:
    tok = get_tokenizer()
    out = tok.apply_chat_template(
        template_view(messages), tools=tools or None, add_generation_prompt=True, tokenize=True, **CHAT_TEMPLATE_KWARGS
    )
    if isinstance(out, dict) or hasattr(out, "input_ids"):
        out = out["input_ids"]
    return list(out)


def count_prompt_tokens(messages: list[dict], tools: Optional[list[dict]]) -> int:
    return len(render_prompt_ids(messages, tools))


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _is_tool_call_msg(m: dict) -> bool:
    return m.get("role") == "assistant" and bool(m.get("tool_calls"))


def split_units(history: list[dict]) -> list[list[dict]]:
    """Group a litellm-format message list into indivisible units."""
    units: list[list[dict]] = []
    i = 0
    n = len(history)
    while i < n:
        m = history[i]
        if _is_tool_call_msg(m):
            unit = [m]
            j = i + 1
            while j < n and history[j].get("role") == "tool":
                unit.append(history[j])
                j += 1
            units.append(unit)
            i = j
        elif m.get("role") == "tool":
            # orphan tool result (should not happen); keep as its own unit
            units.append([m])
            i += 1
        else:
            units.append([m])
            i += 1
    return units


@dataclass
class ContextInfo:
    pre_truncation_tokens: int
    post_truncation_tokens: int
    n_units_total: int
    n_units_dropped: int
    n_messages_in: int
    n_messages_out: int
    truncated: bool
    extra: dict = field(default_factory=dict)


def apply_context_policy(
    messages: list[dict],
    tools: Optional[list[dict]],
    max_prompt_tokens: int = MAX_PROMPT_TOKENS,
) -> tuple[list[dict], ContextInfo]:
    """Return (kept_messages, info).

    `messages` is the full litellm-format list: system first, then the
    fixed greeting (assistant), the first user request, then history.
    """
    assert messages and messages[0]["role"] == "system", "first message must be system"
    pre = count_prompt_tokens(messages, tools)
    # Locate the prefix that is always kept: system, greeting, first user message.
    head_end = 1
    # greeting(s): leading assistant text messages before the first user message
    while head_end < len(messages) and messages[head_end]["role"] == "assistant" and not messages[head_end].get("tool_calls"):
        head_end += 1
    if head_end < len(messages) and messages[head_end]["role"] == "user":
        head_end += 1
    head = messages[:head_end]
    tail = messages[head_end:]
    units = split_units(tail)
    n_units = len(units)
    if pre <= max_prompt_tokens:
        return list(messages), ContextInfo(pre, pre, n_units, 0, len(messages), len(messages), False)

    dropped = 0
    kept_units = units
    post = pre
    while kept_units:
        kept_units = kept_units[1:]
        dropped += 1
        cand = head + [m for u in kept_units for m in u]
        post = count_prompt_tokens(cand, tools)
        if post <= max_prompt_tokens:
            return cand, ContextInfo(pre, post, n_units, dropped, len(messages), len(cand), True)
    # Even the head alone is too long: return head (cannot do better; recorded).
    cand = head
    post = count_prompt_tokens(cand, tools)
    return cand, ContextInfo(pre, post, n_units, dropped, len(messages), len(cand), True, {"head_only": True})


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
