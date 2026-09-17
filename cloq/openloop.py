"""Open-loop fidelity on held-out BF16 states (plan section 15).

For every decision state of the BF16 held-out trajectories, replay the exact
stored prompt token ids through a quantized arm's server WITHOUT executing the
result, and measure:
  * tool-name agreement, full normalised tool-call agreement, argument accuracy / field F1
  * teacher-forced NLL of the BF16 action tokens under the quantized model
    (prompt_logprobs on prompt = context + BF16 completion tokens)

Both use the raw /v1/completions endpoint with token-id prompts so the input is
bit-identical to the stored context.

usage:
  python -m cloq.openloop --bf16-run bf16 --arm-run static_eval --arm static --domain airline \
      --eval-file manifests/eval_tasks_v0.json --agent-base http://127.0.0.1:8001/v1
"""

from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from loguru import logger

from cloq import config as C
from cloq.context_policy import get_tokenizer
from cloq.metrics import load_decisions, normalize_action, normalize_tool_call, read_jsonl


def _complete(api_base: str, prompt_ids: list[int], max_tokens: int, model: str = C.AGENT_SERVED_NAME) -> dict:
    g = C.FROZEN["generation_agent"]
    body = {
        "model": model, "prompt": prompt_ids, "max_tokens": max_tokens,
        "temperature": 0.0, "top_p": 1.0, "top_k": -1, "seed": 0,
        "repetition_penalty": 1.0, "presence_penalty": 0.0, "frequency_penalty": 0.0,
        "return_token_ids": True, "skip_special_tokens": True,
    }
    r = requests.post(api_base + "/completions", json=body, timeout=900)
    r.raise_for_status()
    return r.json()


def _prompt_logprobs(api_base: str, ids: list[int], model: str = C.AGENT_SERVED_NAME) -> list:
    body = {"model": model, "prompt": ids, "max_tokens": 1, "temperature": 0.0, "prompt_logprobs": 0, "return_token_ids": True}
    r = requests.post(api_base + "/completions", json=body, timeout=900)
    r.raise_for_status()
    return r.json()["choices"][0]["prompt_logprobs"]


def parse_action(text: str) -> tuple[str | None, list[dict] | None]:
    """Parse Qwen3/hermes style output into (content, tool_calls) like vLLM's hermes parser."""
    import re

    calls = []
    content = text
    for m in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, flags=re.S):
        try:
            obj = json.loads(m.group(1))
            calls.append({"name": obj.get("name"), "arguments": obj.get("arguments") or {}})
        except Exception:
            calls.append({"name": None, "arguments": {}, "parse_error": True})
    if calls:
        content = re.sub(r"<tool_call>.*?</tool_call>", "", text, flags=re.S).strip() or None
    return content, (calls or None)


def action_token_ids(d: dict, tok) -> list[int]:
    """Canonical action tokens of a stored decision: the chat-template rendering of the
    assistant message (content + tool calls) followed by <|im_end|>, i.e. exactly the tokens
    that the next prompt will contain. Independent of how litellm reports generated ids."""
    msgs = list(d["messages"])
    tool_calls = None
    if d.get("tool_calls"):
        tool_calls = [{"id": tc.get("id", ""), "name": tc["name"], "type": "function",
                       "function": {"name": tc["name"], "arguments": json.dumps(tc.get("arguments") or {})}} for tc in d["tool_calls"]]
    assistant = {"role": "assistant", "content": d.get("content"), "tool_calls": tool_calls}
    tools = _TOOLS_CACHE.get(d.get("tools_sha256"))
    full = tok.apply_chat_template(msgs + [assistant], tools=tools, add_generation_prompt=False, tokenize=True)
    if isinstance(full, dict) or hasattr(full, "input_ids"):
        full = full["input_ids"]
    full = list(full)
    prompt = d["prompt_token_ids"]
    if full[: len(prompt)] == prompt:
        ids = full[len(prompt):]
    else:  # boundary tokenisation differs: fall back to tokenising the rendered suffix text
        text = tok.apply_chat_template(msgs + [assistant], tools=tools, add_generation_prompt=False, tokenize=False)
        ptext = tok.apply_chat_template(msgs, tools=tools, add_generation_prompt=True, tokenize=False)
        assert text.startswith(ptext), "template rendering mismatch"
        ids = tok(text[len(ptext):], add_special_tokens=False)["input_ids"]
    nl = tok("\n", add_special_tokens=False)["input_ids"]
    if len(nl) == 1 and ids and ids[-1] == nl[0]:
        ids = ids[:-1]  # template appends '\n' after <|im_end|>
    return ids


_TOOLS_CACHE: dict = {}


def register_tools_for_domain(domain: str) -> None:
    """Load the tau2 tool schemas so the template renders the same <tools> block as at run time."""
    from tau2.registry import registry
    from cloq.context_policy import canonical_json, sha256_text

    env = registry.get_env_constructor(domain)()
    schema = [t.openai_schema for t in env.get_tools()]
    _TOOLS_CACHE[sha256_text(canonical_json(schema))] = schema


def _as_arg_dict(x) -> tuple[dict, bool]:
    """Tool-call arguments as a dict. Returns (dict, well_formed).

    An already-a-dict input is returned unchanged, so this is behaviour-identical on every
    input that did not previously crash.
    """
    if isinstance(x, dict):
        return x, True
    if x is None:
        return {}, True
    if isinstance(x, str):
        try:
            d = json.loads(x)
            if isinstance(d, dict):
                return d, True
        except Exception:
            pass
    return {}, False


def arg_metrics(fp_calls: list[dict] | None, q_calls: list[dict] | None) -> dict:
    """Argument-level accuracy for the first tool call when names match."""
    if not fp_calls or not q_calls:
        return {"name_match": False, "exact_args": None, "field_f1": None}
    f, q = fp_calls[0], q_calls[0]
    name_match = f["name"] == q["name"]
    if not name_match:
        return {"name_match": False, "exact_args": None, "field_f1": None}
    fa, ok_f = _as_arg_dict(f.get("arguments"))
    qa, ok_q = _as_arg_dict(q.get("arguments"))
    if not (ok_f and ok_q):
        # A quantized model sometimes emits the argument blob as a bare string instead of an
        # object. That is a failure to reproduce the BF16 action, not a reason to lose the whole
        # domain's summary, so it scores as a mismatch and is flagged.
        return {"name_match": True, "exact_args": False, "field_f1": 0.0, "malformed_arguments": True}
    exact = normalize_tool_call(f["name"], fa) == normalize_tool_call(q["name"], qa)
    fk = {(k, json.dumps(v, sort_keys=True)) for k, v in fa.items()}
    qk = {(k, json.dumps(v, sort_keys=True)) for k, v in qa.items()}
    tp = len(fk & qk)
    p = tp / len(qk) if qk else (1.0 if not fk else 0.0)
    r = tp / len(fk) if fk else (1.0 if not qk else 0.0)
    f1 = (2 * p * r / (p + r)) if (p + r) else 0.0
    return {"name_match": True, "exact_args": exact, "field_f1": f1}


def replay_state(d: dict, api_base: str, tok, max_tokens: int) -> dict:
    prompt_ids = d["prompt_token_ids"]
    fp_content, fp_calls = d["content"], d["tool_calls"]
    fp_kind = "tool" if fp_calls else "text"
    fp_norm = normalize_action(fp_content, fp_calls)
    # 1) greedy open-loop generation
    out = _complete(api_base, prompt_ids, max_tokens)
    ch = out["choices"][0]
    q_text = ch["text"]
    q_ids = ch.get("token_ids")
    q_content, q_calls = parse_action(q_text)
    q_kind = "tool" if q_calls else "text"
    q_norm = normalize_action(q_content, q_calls)
    # 2) teacher-forced NLL of the BF16 action (canonical rendering; exact generated ids kept for reference)
    fp_ids = action_token_ids(d, tok)
    gen_ids = list(d.get("completion_token_ids") or [])
    nll = None; n_action_tokens = len(fp_ids)
    if fp_ids:
        full = prompt_ids + fp_ids
        plp = _prompt_logprobs(api_base, full)
        # plp[i] is dict {token_id: {logprob,...}} for position i (None for first token)
        lps = []
        for i in range(len(prompt_ids), len(full)):
            e = plp[i]
            tid = str(full[i])
            if e is None or tid not in e:
                lps.append(float("nan")); continue
            lps.append(float(e[tid]["logprob"]))
        arr = np.array(lps, dtype=float)
        nll = float(np.nansum(-arr))
    am = arg_metrics(fp_calls, q_calls)
    return {
        "task_id": d["task_id"], "decision_idx": d["decision_idx"], "n_prompt_tokens": len(prompt_ids),
        "fp_kind": fp_kind, "q_kind": q_kind, "kind_match": fp_kind == q_kind,
        "tool_name_match": (fp_calls[0]["name"] == q_calls[0]["name"]) if (fp_calls and q_calls) else (fp_kind == q_kind == "text"),
        "full_action_match": fp_norm == q_norm,
        "tool_exact_match": (fp_norm == q_norm) if fp_kind == "tool" else None,
        "text_exact_match": (fp_norm == q_norm) if fp_kind == "text" else None,
        "exact_args": am["exact_args"], "field_f1": am["field_f1"],
        "nll": nll, "n_action_tokens": n_action_tokens, "nll_per_token": (nll / n_action_tokens) if (nll is not None and n_action_tokens) else None,
        "rendered_equals_generated": (fp_ids == gen_ids) if gen_ids else None,
        "q_text": q_text[:2000], "q_finish_reason": ch.get("finish_reason"),
        "fp_norm": fp_norm[:500], "q_norm": q_norm[:500],
    }


def run(bf16_run: str, arm: str, arm_run: str, domain: str, eval_ids: list[str], api_base: str, out_path: Path, concurrency: int = 8) -> dict:
    tok = get_tokenizer()
    register_tools_for_domain(domain)
    decs = [d for d in load_decisions(C.RUNS_DIR / bf16_run / domain) if d["task_id"] in set(eval_ids)]
    logger.info(f"{domain}: replaying {len(decs)} BF16 states through arm={arm}")
    max_tokens = C.AGENT_MAX_TOKENS
    t0 = time.time()
    with ThreadPoolExecutor(concurrency) as ex:
        rows = list(ex.map(lambda d: replay_state(d, api_base, tok, max_tokens), decs))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tool_rows = [r for r in rows if r["fp_kind"] == "tool"]
    summ = {
        "arm": arm, "arm_run": arm_run, "domain": domain, "n_states": len(rows), "n_tool_states": len(tool_rows),
        "kind_match_rate": float(np.mean([r["kind_match"] for r in rows])) if rows else None,
        "tool_name_agreement": float(np.mean([r["tool_name_match"] for r in tool_rows])) if tool_rows else None,
        "full_tool_call_agreement": float(np.mean([r["tool_exact_match"] for r in tool_rows])) if tool_rows else None,
        "full_action_agreement": float(np.mean([r["full_action_match"] for r in rows])) if rows else None,
        "exact_args_given_name": float(np.mean([r["exact_args"] for r in tool_rows if r["exact_args"] is not None])) if any(r["exact_args"] is not None for r in tool_rows) else None,
        "field_f1_given_name": float(np.mean([r["field_f1"] for r in tool_rows if r["field_f1"] is not None])) if any(r["field_f1"] is not None for r in tool_rows) else None,
        "nll_mean": float(np.mean([r["nll"] for r in rows if r["nll"] is not None])) if rows else None,
        "nll_per_token_mean": float(np.mean([r["nll_per_token"] for r in rows if r["nll_per_token"] is not None])) if rows else None,
        "seconds": time.time() - t0,
    }
    (out_path.with_suffix(".summary.json")).write_text(json.dumps(summ, indent=2))
    logger.info(json.dumps(summ))
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bf16-run", default="bf16")
    ap.add_argument("--arm", required=True)
    ap.add_argument("--arm-run", required=True, help="run id of the arm's closed-loop eval (output goes there)")
    ap.add_argument("--domain", required=True)
    ap.add_argument("--eval-file", default=str(C.MANIFEST_DIR / "eval_tasks_v0.json"))
    ap.add_argument("--agent-base", default=C.AGENT_API_BASE)
    ap.add_argument("--concurrency", type=int, default=8)
    a = ap.parse_args()
    eval_ids = json.load(open(a.eval_file))[a.domain]
    out = C.RUNS_DIR / a.arm_run / a.domain / "openloop.jsonl"
    if out.with_suffix(".summary.json").exists():
        print("exists; skipping", out); return
    run(a.bf16_run, a.arm, a.arm_run, a.domain, eval_ids, a.agent_base, out, a.concurrency)


if __name__ == "__main__":
    main()
