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
import re
import socket
import sys
import threading
import uuid
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

DEFAULT_KEY_FILE = "~/.config/anthropic/api_key"
RELAY_PREFIX = "relay/"
RELAY_DIR_DEFAULT = "/data/ziyangs/cloq_work/simrelay"
RELAY_TIMEOUT_S_DEFAULT = 2700.0  # 45 min per user turn; then the branch errors out as infra
RELAY_POLL_S = 3.0
STOP_TOKEN_CONVENTION = (
    "tau2 UserSimulator rules (tau2/user/user_simulator_base.py, simulation_guidelines.md): the reply is the customer's next "
    "message as plain text. When the task goal is satisfied, end the conversation by generating '###STOP###' (alone or at the "
    "end of the final message). If you are transferred to another agent, generate '###TRANSFER###'. If the scenario does not "
    "give enough information to continue, generate '###OUT-OF-SCOPE###'. Any of the three in the reply ends the conversation "
    "(tau2 UserSimulator.is_stop), so never write them otherwise.")
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
    if spec.get("provider") == "relay":
        return RELAY_PREFIX + spec["model"]
    if spec.get("provider") != "anthropic":
        raise ValueError(f"user_llm: unsupported provider {spec.get('provider')!r}")
    return f"anthropic/{spec['model']}"


def user_args(spec: dict) -> dict:
    """llm_args_user for the override. No api_key (env only), no sampling params (rejected by the model)."""
    if spec.get("provider") == "relay":  # nothing reaches litellm; the relay reads max_tokens / its own settings
        for k in ("temperature", "top_p", "top_k", "seed", "api_base", "thinking"):
            if k in spec:
                raise ValueError(f"user_llm relay: {k} is not settable (a Claude Code subagent answers)")
        return {"max_tokens": int(spec.get("max_tokens", 512))}
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


def set_context(ctx: Optional[dict]) -> None:
    """Relay request metadata for the calling thread's branch (state_id, unit_id, arm, replicate)."""
    _TL.ctx = dict(ctx) if ctx else None


def relay_dir() -> Path:
    return Path(os.environ.get("CLOQ_SIMRELAY_DIR", RELAY_DIR_DEFAULT))


def relay_dirs(root: Optional[Path] = None) -> dict:
    root = root or relay_dir()
    d = {k: root / k for k in ("pending", "claimed", "done", "expired", "replies")}
    for p in d.values():
        p.mkdir(parents=True, exist_ok=True)
    return d


def atomic_write_json(path: Path, obj: Any) -> None:
    """tmp file in the SAME directory (dot-prefixed, ignored by readers), fsync, then rename: atomic on NFS for readers."""
    tmp = path.parent / f".tmp-{path.name}-{socket.gethostname()}-{os.getpid()}-{threading.get_ident()}"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp, path)


class RelayTimeout(RuntimeError):
    """No answer in done/ within the timeout: infrastructure failure of the branch (never a user turn)."""


def _relog(msg: str) -> None:
    print(f"[simrelay {time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------- simrelay-v2 (W97)
# Used only when the branch context sets {"protocol": "simrelay-v2"} (fork_driver mode simctrl_p); v1 is unchanged.
# Differences from v1: (1) the request the responder reads holds ONLY req_id, protocol, system_prompt, messages,
# max_tokens, msg_sha256 and the stop-token convention; bookkeeping (state, unit, arm, replicate, branch tag) goes to a
# sidecar <v2 root>/meta/<req_id>.json that responders never read; req_id is random (no identifiers). (2) Integrity:
# msg_sha256 = sha256 of the canonical JSON of the exact litellm message list (system first); the answer must echo
# req_id, protocol and msg_sha256, and relay_call raises RelayIntegrityError (infra) on any mismatch. (3) v2 lives in its
# own root <relay_dir()>/v2 ($CLOQ_SIMRELAY_DIR/v2), so v1 claimers never see v2 requests and vice versa.
RELAY_V2 = "simrelay-v2"
RELAY_V2_KEYS = ("req_id", "protocol", "system_prompt", "messages", "max_tokens", "msg_sha256", "stop_token_convention")


class RelayIntegrityError(RuntimeError):
    """A v2 answer does not echo the request's req_id / protocol / msg_sha256: infrastructure failure of the branch."""


def canon_sha(obj: Any) -> str:
    """sha256 of the canonical JSON (sorted keys, no whitespace, UTF-8) of obj; the v2 msg_sha256."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def v2_messages(system_prompt: str, messages: list) -> list:
    """The litellm message list a v2 request stands for (what msg_sha256 hashes)."""
    return [{"role": "system", "content": system_prompt}] + list(messages)


def relay_v2_dirs(root: Optional[Path] = None) -> dict:
    root = Path(root) if root else relay_dir() / "v2"
    d = {k: root / k for k in ("pending", "claimed", "done", "expired", "meta")}
    for p in d.values():
        p.mkdir(parents=True, exist_ok=True)
    return d


def _relay_call_v2(model: str, msgs: list, max_tokens: int, tag: Optional[str], n_prev: int, ctx: dict) -> tuple[str, dict]:
    d = relay_v2_dirs()
    sys_msgs = [m for m in msgs if m.get("role") == "system"]
    rest = [m for m in msgs if m.get("role") != "system"]
    if len(sys_msgs) != 1 or msgs[0] is not sys_msgs[0]:
        raise RuntimeError(f"simrelay-v2 infra: expected exactly one leading system message, got {len(sys_msgs)}")
    sp = sys_msgs[0].get("content") or ""
    msg_sha = canon_sha(msgs)
    if canon_sha(v2_messages(sp, rest)) != msg_sha:  # the responder must be able to rebuild the hashed list exactly
        raise RuntimeError("simrelay-v2 infra: system message carries fields beyond role/content; request not reconstructible")
    req_id = "v2-" + uuid.uuid4().hex
    req = {"req_id": req_id, "protocol": RELAY_V2, "system_prompt": sp, "messages": rest, "max_tokens": int(max_tokens),
           "msg_sha256": msg_sha, "stop_token_convention": STOP_TOKEN_CONVENTION}
    meta_side = {"req_id": req_id, "protocol": RELAY_V2, "state_id": ctx.get("state_id"), "unit_id": ctx.get("unit_id"),
                 "arm": ctx.get("arm"), "replicate": ctx.get("replicate"), "branch_tag": tag, "user_turn_index": n_prev,
                 "model_label": model[len(RELAY_PREFIX):], "msg_sha256": msg_sha,
                 "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": socket.gethostname(), "pid": os.getpid()}
    timeout = float(os.environ.get("CLOQ_SIMRELAY_TIMEOUT_S", RELAY_TIMEOUT_S_DEFAULT))
    pend, done = d["pending"] / f"{req_id}.json", d["done"] / f"{req_id}.json"
    atomic_write_json(d["meta"] / f"{req_id}.json", meta_side)  # sidecar first: never read by responders
    t0 = time.time()
    atomic_write_json(pend, req)
    _relog(f"v2 request {req_id} written ({len(rest)} messages, tag {tag}); waiting up to {timeout / 60:.0f} min")
    next_log = t0 + 300
    while True:
        if done.exists():
            try:
                ans = json.loads(done.read_text())
            except (OSError, ValueError) as e:
                time.sleep(RELAY_POLL_S)
                ans = json.loads(done.read_text()) if done.exists() else {"error": repr(e)}
            bad = {k: (ans.get(k), want) for k, want in (("req_id", req_id), ("protocol", RELAY_V2), ("msg_sha256", msg_sha))
                   if ans.get(k) != want}
            if bad or not isinstance(ans.get("content"), str) or not ans["content"].strip():
                _relog(f"INTEGRITY FAILURE {req_id}: {bad or 'no content'}")
                raise RelayIntegrityError(f"simrelay-v2 infra: answer {done} fails integrity: "
                                          f"{ {k: v[0] for k, v in bad.items()} if bad else 'empty or non-string content'}")
            wall = time.time() - t0
            _relog(f"v2 answer {req_id} from {ans.get('responder')} after {wall:.0f} s (integrity ok)")
            return ans["content"], {"req_id": req_id, "protocol": RELAY_V2, "responder": ans.get("responder"), "wall_s": wall,
                                    "answered_utc": ans.get("answered_utc"), "claimed_utc": ans.get("claimed_utc"),
                                    "model": ans.get("model"), "cost_usd": ans.get("cost_usd"), "duration_s": ans.get("duration_s"),
                                    "template_sha256": ans.get("template_sha256"), "n_attempts": ans.get("n_attempts"),
                                    "msg_sha256": msg_sha, "integrity_ok": True, "request_path": str(pend), "done_path": str(done),
                                    "meta_path": str(d["meta"] / f"{req_id}.json")}
        now = time.time()
        if now - t0 > timeout:
            moved = None
            for src in [pend, *d["claimed"].glob(f"*/{req_id}.json")]:
                try:
                    os.rename(src, d["expired"] / f"{req_id}.json")
                    moved = str(src)
                    break
                except OSError:
                    pass
            atomic_write_json(d["expired"] / f"{req_id}.reason.json", {"req_id": req_id, "timeout_s": timeout, "moved_from": moved,
                                                                         "expired_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            _relog(f"TIMEOUT v2 {req_id} after {timeout:.0f} s (moved {moved} to expired/); branch fails as infra")
            raise RelayTimeout(f"simrelay-v2 infra: no answer for {req_id} within {timeout:.0f} s")
        if now >= next_log:
            _relog(f"still waiting for v2 {req_id} ({(now - t0) / 60:.0f} min)")
            next_log = now + 300
        time.sleep(RELAY_POLL_S)


def relay_call(model: str, msgs: list, max_tokens: int, tag: Optional[str], n_prev: int) -> tuple[str, dict]:
    """One user turn through the file relay: write pending/<req_id>.json, poll done/<req_id>.json. Returns (content, meta).
    With context protocol "simrelay-v2" (W97) the v2 path is used instead (see _relay_call_v2)."""
    ctx = getattr(_TL, "ctx", None) or {}
    if ctx.get("protocol") == RELAY_V2:
        return _relay_call_v2(model, msgs, max_tokens, tag, n_prev, ctx)
    d = relay_dirs()
    base = "-".join(str(x) for x in (ctx.get("unit_id") or tag or "x", ctx.get("arm"), f"r{ctx['replicate']}" if "replicate" in ctx else None)
                    if x is not None)
    req_id = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{base}-t{n_prev:02d}-{uuid.uuid4().hex[:8]}")
    sys_msgs = [m for m in msgs if m.get("role") == "system"]
    req = {"req_id": req_id, "protocol": "simrelay-v1", "state_id": ctx.get("state_id"), "unit_id": ctx.get("unit_id"),
           "arm": ctx.get("arm"), "replicate": ctx.get("replicate"), "branch_tag": tag, "user_turn_index": n_prev,
           "model_label": model[len(RELAY_PREFIX):],
           "system_prompt": "\n".join(m.get("content") or "" for m in sys_msgs),
           "messages": [m for m in msgs if m.get("role") != "system"],
           "messages_role_note": ("Roles are FLIPPED as tau2 sends them to the user LLM: role 'user' = the customer-service agent "
                                  "speaking to you; role 'assistant' = your own earlier messages as the customer. Your reply is the "
                                  "next 'assistant' message."),
           "litellm_messages": msgs, "litellm_messages_sha256": _sha(msgs), "max_tokens": int(max_tokens),
           "stop_token_convention": STOP_TOKEN_CONVENTION, "reply_format": {"content": "the customer's next message text only"},
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "host": socket.gethostname(), "pid": os.getpid()}
    timeout = float(os.environ.get("CLOQ_SIMRELAY_TIMEOUT_S", RELAY_TIMEOUT_S_DEFAULT))
    pend, done = d["pending"] / f"{req_id}.json", d["done"] / f"{req_id}.json"
    t0 = time.time()
    atomic_write_json(pend, req)
    _relog(f"request {req_id} written ({len(req['messages'])} messages); waiting up to {timeout / 60:.0f} min for {done}")
    next_log = t0 + 300
    while True:
        if done.exists():
            try:
                ans = json.loads(done.read_text())
            except (OSError, ValueError) as e:  # rename-based writers never expose partial files; retry once on NFS hiccups
                time.sleep(RELAY_POLL_S)
                ans = json.loads(done.read_text()) if done.exists() else {"error": repr(e)}
            if not isinstance(ans.get("content"), str):
                raise RuntimeError(f"simrelay infra: {done} has no string 'content' ({str(ans)[:200]})")
            wall = time.time() - t0
            _relog(f"answer {req_id} from {ans.get('responder')} after {wall:.0f} s")
            return ans["content"], {"req_id": req_id, "responder": ans.get("responder"), "wall_s": wall,
                                    "answered_utc": ans.get("answered_utc"), "claimed_utc": ans.get("claimed_utc"),
                                    "request_path": str(pend), "done_path": str(done)}
        now = time.time()
        if now - t0 > timeout:
            moved = None
            for src in [pend, *d["claimed"].glob(f"*/{req_id}.json")]:
                try:
                    os.rename(src, d["expired"] / f"{req_id}.json")
                    moved = str(src)
                    break
                except OSError:
                    pass
            atomic_write_json(d["expired"] / f"{req_id}.reason.json", {"req_id": req_id, "timeout_s": timeout, "moved_from": moved,
                                                                         "expired_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            _relog(f"TIMEOUT {req_id} after {timeout:.0f} s (moved {moved} to expired/); branch fails as infra")
            raise RelayTimeout(f"simrelay infra: no answer for {req_id} within {timeout:.0f} s")
        if now >= next_log:
            where = "pending" if pend.exists() else "claimed" if any(d["claimed"].glob(f"*/{req_id}.json")) else "?"
            _relog(f"still waiting for {req_id} ({where}, {(now - t0) / 60:.0f} min)")
            next_log = now + 300
        time.sleep(RELAY_POLL_S)


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
    """Wrap tau2's litellm `completion` for anthropic/* models (drop `seed`, record the call) and route relay/* models to
    the file relay (no litellm call). Idempotent."""
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
    orig_cost = LU.get_response_cost

    def get_response_cost(response):  # relay responses have no price (litellm would log an unknown-provider error)
        if str(getattr(response, "model", "")).startswith(RELAY_PREFIX):
            return 0.0
        return orig_cost(response)

    def relay_completion(model: str, kw: dict):
        msgs = kw.get("messages") or []
        if kw.get("tools"):
            raise RuntimeError("simrelay: the relay user simulator has no tools (retail/airline only)")
        tag = getattr(_TL, "tag", None)
        with _LOCK:
            n_prev = len(_RECS.get(tag, []))
        sys_txt = "\n".join(m.get("content") or "" for m in msgs if m.get("role") == "system")
        rec = {"tag": tag, "model": model, "t_start": time.time(), "dropped_params": {k: kw[k] for k in ("seed",) if k in kw},
               "params": {k: v for k, v in kw.items() if k not in ("messages", "api_key", "tools")}, "n_messages": len(msgs),
               "system_sha256": hashlib.sha256(sys_txt.encode()).hexdigest(), "messages_sha256": _sha(msgs), "tools": [],
               "request_messages": msgs}
        t0 = time.perf_counter()
        try:
            text, meta = relay_call(model, msgs, int(kw.get("max_tokens") or 512), tag, n_prev)
        except Exception as e:
            rec.update({"error": repr(e)[:500], "latency_s": time.perf_counter() - t0})
            with _LOCK:
                _RECS[rec["tag"]].append(rec)
            raise
        import litellm

        resp = litellm.ModelResponse(id=meta["req_id"], model=model,
                                     choices=[{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
                                     usage=litellm.Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0))
        rec.update({"latency_s": time.perf_counter() - t0, "litellm_response_id": meta["req_id"], "request_id": meta["req_id"],
                    "relay": meta, "response_model": model, "finish_reason": "stop",
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "note": "relay: no token counts"}, "cost_usd": meta.get("cost_usd"),
                    "content": text, "tool_calls": []})
        with _LOCK:
            _RECS[rec["tag"]].append(rec)
        return resp

    def completion(*args, **kw):
        model = kw.get("model") or (args[0] if args else "")
        if str(model).startswith(RELAY_PREFIX):
            return relay_completion(str(model), kw)
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
    LU.get_response_cost = get_response_cost
    _INSTALLED = True
