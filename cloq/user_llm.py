"""Per-branch user-simulator override (W90; GPT-6.1 review 5, option A: simulator robustness control).

A fork branch normally sends its user turns to the run's local simulator (Qwen3-4B-Instruct-2507 behind USER_BASE,
`hosted_vllm/user`). With a `user_llm` spec, e.g.

    {"provider": "anthropic", "model": "claude-sonnet-5-5", "max_tokens": 512, "thinking": {"type": "between_tools"}}

only the user simulator of that branch is replaced: tau2's own UserSimulator class, system prompt, task instructions,
history handling and stop-token logic are unchanged; only `llm_user` / `llm_args_user` of the run config change, so
tau2's `generate()` calls litellm with `anthropic/<model>`. The agent controller (B or Q) stays on the local vLLM server.

Secrets: the API key is read only from $CLOQ_ANTHROPIC_KEY_FILE (default ~/.config/anthropic/api_key) into the
process environment (ANTHROPIC_API_KEY, which litellm reads). It is never put into llm_args (tau2 logs llm_args), never
printed, and never written to any record.

Sampling: claude-sonnet-5-5 rejects non-default temperature/top_p/top_k (400) and has no seed, so the old simulator's
temperature 0 / seed cannot be reproduced. The orchestrator's `seed` is dropped from the request and the drop is recorded.
Thinking is turned off with {"type": "between_tools"} (thinking "disabled" is a 400 on this model).

Every anthropic user call is recorded (thread-local branch tag): the Anthropic request-id header (litellm replaces the
msg_ id by its own chatcmpl id, also kept), usage (incl. cache
tokens), finish/stop reason, latency, the request's system-prompt sha and message-list sha, and the response text.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

DEFAULT_KEY_FILE = "~/.config/anthropic/api_key"
PRICES = {"claude-sonnet-5-5": {"input": 2.0e-6, "output": 10.0e-6}}  # USD per token (cached 2026-09-25 price table)
_TL = threading.local()
_LOCK = threading.Lock()
_RECS: dict[str, list[dict]] = defaultdict(list)
_INSTALLED = False


def key_file() -> Path:
    return Path(os.path.expanduser(os.environ.get("CLOQ_ANTHROPIC_KEY_FILE", DEFAULT_KEY_FILE)))


def key_available() -> bool:
    p = key_file()
    try:
        return p.is_file() and len(p.read_text().strip()) > 0
    except OSError:
        return False


def load_key() -> None:
    """Put the key into this process's environment (never returned, never printed)."""
    p = key_file()
    if not key_available():
        raise RuntimeError(f"user_llm: no API key file at {p} (set CLOQ_ANTHROPIC_KEY_FILE)")
    os.environ["ANTHROPIC_API_KEY"] = p.read_text().strip()


def litellm_model(spec: dict) -> str:
    if spec.get("provider") != "anthropic":
        raise ValueError(f"user_llm: unsupported provider {spec.get('provider')!r}")
    return f"anthropic/{spec['model']}"


def user_args(spec: dict) -> dict:
    """llm_args_user for the override. No api_key (env only), no sampling params (rejected by the model)."""
    a = {"max_tokens": int(spec.get("max_tokens", 512)), "timeout": float(spec.get("timeout", 600))}
    if spec.get("thinking") is not None:
        a["thinking"] = copy.deepcopy(spec["thinking"])
    if spec.get("api_base"):  # dry runs only: a local mock of the Messages API
        a["api_base"] = spec["api_base"]
    if spec.get("num_retries") is not None:
        a["num_retries"] = int(spec["num_retries"])
    for k in ("temperature", "top_p", "top_k", "seed"):
        if k in spec:
            raise ValueError(f"user_llm: {k} is not settable on {spec['model']} (non-default sampling is a 400; no seed)")
    return a


def apply(rc: dict, spec: Optional[dict]) -> dict:
    """Run-config dict with the user simulator routed to `spec` (unchanged copy when spec is None)."""
    d = copy.deepcopy(rc)
    if not spec:
        return d
    d["llm_user"] = litellm_model(spec)
    d["llm_args_user"] = user_args(spec)
    return d


def set_tag(tag: Optional[str]) -> None:
    _TL.tag = tag


def pop(tag: str) -> list[dict]:
    with _LOCK:
        return _RECS.pop(tag, [])


def _sha(o: Any) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _cost(model: str, usage: dict) -> Optional[float]:
    p = PRICES.get(model.split("/", 1)[-1])
    if not p or not usage:
        return None
    return usage.get("prompt_tokens", 0) * p["input"] + usage.get("completion_tokens", 0) * p["output"]


def install() -> None:
    """Wrap tau2's litellm `completion` for anthropic/* models: drop `seed`, record the call. Idempotent."""
    global _INSTALLED
    if _INSTALLED:
        return
    import litellm
    import tau2.utils.llm_utils as LU

    for name, p in PRICES.items():  # so tau2's completion_cost() does not error on a model litellm may not list yet
        litellm.register_model({f"anthropic/{name}": {"input_cost_per_token": p["input"], "output_cost_per_token": p["output"],
                                                      "litellm_provider": "anthropic", "mode": "chat", "max_tokens": 128000,
                                                      "max_input_tokens": 1000000, "max_output_tokens": 128000}})
    orig = LU.completion

    def completion(*args, **kw):
        model = kw.get("model") or (args[0] if args else "")
        if not str(model).startswith("anthropic/"):
            return orig(*args, **kw)
        dropped = {k: kw.pop(k) for k in ("seed",) if k in kw}
        msgs = kw.get("messages") or []
        sys_txt = "\n".join(m.get("content") or "" for m in msgs if m.get("role") == "system")
        rec = {"tag": getattr(_TL, "tag", None), "model": model, "t_start": time.time(),
               "dropped_params": dropped, "params": {k: v for k, v in kw.items() if k not in ("messages", "api_key", "tools")},
               "n_messages": len(msgs), "system_sha256": hashlib.sha256(sys_txt.encode()).hexdigest(),
               "messages_sha256": _sha(msgs), "tools": [t["function"]["name"] for t in (kw.get("tools") or [])],
               "request_messages": msgs}
        t0 = time.perf_counter()
        try:
            resp = orig(*args, **kw)
        except Exception as e:
            rec.update({"error": repr(e)[:500], "latency_s": time.perf_counter() - t0})
            with _LOCK:
                _RECS[rec["tag"]].append(rec)
            raise
        hp = getattr(resp, "_hidden_params", {}) or {}
        hdr = hp.get("additional_headers") or {}
        u = resp.get("usage")
        usage = u.model_dump() if hasattr(u, "model_dump") else (dict(u) if u else {})
        ch = resp.choices[0]
        rec.update({"latency_s": time.perf_counter() - t0, "litellm_response_id": resp.get("id"),
                    "request_id": hdr.get("llm_provider-request-id") or hdr.get("request-id"),
                    "response_model": resp.get("model"), "finish_reason": ch.finish_reason,
                    "usage": usage, "cost_usd": _cost(model, {"prompt_tokens": usage.get("prompt_tokens", 0),
                                                              "completion_tokens": usage.get("completion_tokens", 0)}),
                    "content": ch.message.content,
                    "tool_calls": [{"name": tc.function.name, "arguments": tc.function.arguments} for tc in (ch.message.tool_calls or [])]})
        with _LOCK:
            _RECS[rec["tag"]].append(rec)
        return resp

    LU.completion = completion
    _INSTALLED = True
