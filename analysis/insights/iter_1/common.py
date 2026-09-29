"""Shared loaders for insight iteration 1 (read-only over runs/).

A decision record is keyed by (domain, task_id, decision_idx). We keep only the fields the
insight scripts need; `ctx_key` is a hash of the conversation *excluding the system prompt*, so a
nonce run (which only appends a session-id line to the system prompt) can be paired with BF16 on
identical conversational context. For weight perturbations (Gaussian / RTN / GPTQ / AWQ) the
full `prompt_sha256` is used instead.

Runs are read as they are on disk; A6000 runs may still be in progress, so every script reports
how many tasks / decisions it actually used.
"""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
RUNS = ROOT / "runs"
OUT = ROOT / "analysis" / "insights" / "iter_1" / "out"
OUT.mkdir(parents=True, exist_ok=True)
DOMAINS = ("retail", "airline")
TEXT, TOOL = "text", "tool"


def _strip_ids(x):
    if isinstance(x, dict):
        return {k: _strip_ids(v) for k, v in x.items() if k not in ("id", "tool_call_id")}
    if isinstance(x, list):
        return [_strip_ids(v) for v in x]
    return x


def _ctx_key(messages):
    body = [_strip_ids(m) for m in messages if m.get("role") != "system"]
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def action_key(rec):
    """Normalised action: text content, or tool names + arguments (random call ids removed)."""
    if rec.get("tool_calls"):
        calls = []
        for tc in rec["tool_calls"]:
            fn = tc.get("function") or {}
            args = fn.get("arguments")
            try:
                args = json.dumps(json.loads(args), sort_keys=True) if isinstance(args, str) else json.dumps(args, sort_keys=True)
            except Exception:
                pass
            calls.append((fn.get("name"), args))
        return ("tool", tuple(calls))
    return ("text", (rec.get("content") or "").strip())


def load_run(run, domain):
    p = RUNS / run / domain / "decisions.jsonl"
    if not p.exists():
        return {}
    out = {}
    with open(p) as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:  # partially written last line of a live run
                continue
            key = (domain, str(r["task_id"]), int(r["decision_idx"]))
            out[key] = {
                "prompt_sha": r.get("prompt_sha256"),
                "ctx_key": _ctx_key(r.get("messages") or []),
                "ids": r.get("completion_token_ids") or [],
                "margins": r.get("token_margins") or [],
                "min_margin": r.get("min_margin"),
                "first_margin": r.get("first_token_margin"),
                "kind": TOOL if r.get("tool_calls") else TEXT,
                "action": action_key(r),
                "truncated": (r.get("context") or {}).get("truncated"),
            }
    return out


def load_both(run):
    d = {}
    for dom in DOMAINS:
        d.update(load_run(run, dom))
    return d


def status(run, domain):
    p = RUNS / run / domain / "status.json"
    return json.load(open(p)).get("status") if p.exists() else None


def a6000_runs(prefix="a6000_"):
    return sorted(p.name for p in RUNS.iterdir() if p.is_dir() and p.name.startswith(prefix))


def dump(name, obj):
    with open(OUT / name, "w") as f:
        json.dump(obj, f, indent=1, default=str)
    print(f"wrote {OUT / name}")
