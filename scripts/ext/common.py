"""Shared pieces of the simulator-free external-environment adapters (BFCL multi-turn, ALFWorld text).

Both adapters drive the same served agent as tau2 (the vLLM OpenAI server started by scripts/a6000/worker.py, with
the model's chat template and tool parser from scripts/a6000/models.json) through /v1/chat/completions with native
tool calling, using the frozen agent decoding of configs/frozen_v0.json (greedy, seed 0, max_tokens 1024) and the
same request extras as cloq.config.agent_llm_args (return_token_ids, chat_template_kwargs, top-5 logprobs).

Run directory (same style as cloq.run_arm): runs/<run_id>/<domain>/{config,environment,model,task_manifest,
status,metrics}.json, decisions.jsonl (one record per agent decision: the exact messages and tools sent, prompt
token ids from the server, completion token ids, raw content, tool calls, parsed actions, legality flags and the
environment observations they produced), trajectory.jsonl (one record per item: full message list, official
evaluator output, termination reason, wall time). Items are written when finished, so an interrupted run resumes
by skipping items already in trajectory.jsonl.

Only the standard library is imported here (the adapters run in isolated venvs under cloq_work/envs/).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("CLOQ_ROOT", "/data/ziyangs/cloq"))
FROZEN = json.load(open(ROOT / "configs/frozen_v0.json"))
ADAPTER_VERSION = "ext-v1"


class ChatError(Exception):
    def __init__(self, kind: str, msg: str):
        super().__init__(f"{kind}: {msg}")
        self.kind = kind  # "context_overflow" | "agent_parse_error" (the agent's doing: a task failure) | "outage" (infrastructure)


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def canonical_json(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _ext_request_opts() -> dict:
    """Per-model extra chat-request fields for the ext adapters (scripts/a6000/models.json "ext_request", keyed by
    CLOQ_MODEL_ID). Empty for every Qwen model, so their requests are unchanged. W99f: l8 sets
    {"parallel_tool_calls": false}: vLLM then keeps only the first tool call of a response, because the official
    Llama-3.1 template cannot render an assistant turn with several calls (BFCL items otherwise end at decision 1)."""
    try:
        ms = json.load(open(ROOT / "scripts/a6000/models.json"))
    except OSError:
        return {}
    mid = os.environ.get("CLOQ_MODEL_ID")
    return next((dict(m.get("ext_request") or {}) for m in ms.values() if isinstance(m, dict) and m.get("hf_id") == mid), {})


def gen_params() -> dict:
    g = FROZEN["generation_agent"]
    ctk = json.loads(os.environ.get("CLOQ_CHAT_TEMPLATE_KWARGS") or "{}")
    topl = int(os.environ.get("CLOQ_TOP_LOGPROBS", "0"))
    p = {"temperature": float(os.environ.get("CLOQ_AGENT_TEMPERATURE", g["temperature"])), "top_p": g["top_p"],
         "max_tokens": g["max_tokens"], "seed": int(os.environ.get("CLOQ_AGENT_SEED", g["seed"])),
         "presence_penalty": g["presence_penalty"], "frequency_penalty": g["frequency_penalty"],
         "top_k": g["top_k"], "repetition_penalty": g["repetition_penalty"], "return_token_ids": True}
    if ctk:
        p["chat_template_kwargs"] = ctk
    if topl:
        p.update(logprobs=True, top_logprobs=topl)
    p.update(_ext_request_opts())
    return p


def chat(base: str, messages: list[dict], tools: list[dict] | None, timeout: float = 600) -> tuple[dict, float]:
    """One agent decision. Connection failures are retried (transient); a 400 about the context length is the
    agent's own failure (context_overflow); anything else that persists is an outage."""
    body = {"model": "agent", "messages": messages, **gen_params()}
    if tools:
        body["tools"] = tools
    data = json.dumps(body).encode()
    last = None
    for attempt in range(4):
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=data, headers={"Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r), time.time() - t0
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="replace")[:2000]
            if e.code == 400 and ("context length" in txt or "maximum context" in txt or "max_model_len" in txt
                                  or "too long" in txt or "exceeds" in txt):
                raise ChatError("context_overflow", txt)
            if "only supports single tool-calls" in txt:
                # W99f: the Llama-3.1 chat template refuses to render an assistant turn with several tool calls (the agent's
                # own earlier output); an agent failure like W27 in tau2, never an outage. Never raised for Qwen.
                raise ChatError("agent_parse_error", txt)
            last = f"HTTP {e.code}: {txt}"
            if e.code < 500:
                raise ChatError("outage", last)
        except Exception as e:  # connection refused/reset, timeout
            last = repr(e)
        time.sleep(5 * (attempt + 1))
    raise ChatError("outage", str(last))


def token_margins(lp) -> dict:
    """Same definition as cloq.agent._token_margins (top-1 minus best returned alternative per generated token)."""
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
    return {"token_logprobs": chosen, "token_margins": margin, "first_token_margin": margin[0] if margin else None,
            "min_margin": min(valid) if valid else None}


def decision_record(meta: dict, task_id: str, trajectory_id: str, idx: int, messages: list[dict], tools, raw: dict,
                    dt: float) -> dict:
    """Decision record with the keys of cloq.agent decision records (prompt ids come from the server)."""
    ch = (raw.get("choices") or [{}])[0]
    msg = ch.get("message") or {}
    pids = raw.get("prompt_token_ids")
    content = msg.get("content")
    tcs = msg.get("tool_calls")
    sysm = next((m.get("content") for m in messages if m.get("role") == "system"), None)
    return {
        **meta, "task_id": task_id, "trajectory_id": trajectory_id, "decision_idx": idx,
        "n_state_messages": len(messages), "messages": messages,
        "tools_sha256": sha256_text(canonical_json(tools or [])), "system_sha256": sha256_text(sysm) if sysm else None,
        "prompt_sha256": sha256_text(canonical_json(pids)) if pids is not None else None,
        "prompt_token_ids": pids, "prompt_ids_from_server": pids is not None, "n_prompt_tokens": len(pids) if pids else None,
        "completion_token_ids": ch.get("token_ids"), "n_completion_tokens": (raw.get("usage") or {}).get("completion_tokens"),
        "finish_reason": ch.get("finish_reason"), "raw_content": content, "content": content, "tool_calls": tcs or None,
        "parser_error": bool(content) and ("<tool_call>" in content or "[TOOL_CALLS]" in content) and not tcs, "generation_seconds": dt,
        **token_margins(ch.get("logprobs")),
    }


def det_tool_call_ids(raw: dict, decision_idx: int) -> dict:
    """W99p (m24 only, CLOQ_TOKENIZER_MODE=mistral): the Mistral template renders tool-call ids and vLLM's mistral parser
    draws them at random; replace them in place by d<idx:05d>c<k:02d> (9 alphanumerics, as cloq.agent.det_tool_call_id)
    so that identical decisions give identical later prompts. Idempotent; a no-op for every other model."""
    if os.environ.get("CLOQ_TOKENIZER_MODE") != "mistral":
        return raw
    for ch in raw.get("choices") or []:
        for k, tc in enumerate((ch.get("message") or {}).get("tool_calls") or []):
            tc["id"] = f"d{decision_idx % 100000:05d}c{k % 100:02d}"
    return raw


def assistant_history_message(raw: dict) -> dict:
    """The assistant turn as it goes back into the history: role, content and tool calls only (the server's extra
    fields such as token_ids or reasoning_content are not echoed back)."""
    msg = ((raw.get("choices") or [{}])[0]).get("message") or {}
    out = {"role": "assistant", "content": msg.get("content")}
    if msg.get("tool_calls"):
        out["tool_calls"] = [{"id": tc.get("id"), "type": tc.get("type", "function"),
                              "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}}
                             for tc in msg["tool_calls"]]
    return out


def git_rev(path: Path) -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def pkg_versions(names: list[str]) -> dict:
    import importlib.metadata as md
    out = {}
    for p in names:
        try:
            out[p] = md.version(p)
        except Exception:
            out[p] = None
    return out


def served_models(base: str) -> dict:
    try:
        with urllib.request.urlopen(base.rstrip("/") + "/models", timeout=10) as r:
            return json.load(r)
    except Exception as e:
        return {"error": repr(e)}


class RunDir:
    """runs/<run_id>/<domain>/ with the cloq.run_arm file set; thread-safe item writes; resume by item id."""

    def __init__(self, run_id: str, domain: str):
        self.dir = ROOT / "runs" / run_id / domain
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def completed(self) -> bool:
        p = self.dir / "status.json"
        return p.exists() and json.load(open(p)).get("status") == "completed"

    def done_items(self) -> set[str]:
        p = self.dir / "trajectory.jsonl"
        if not p.exists():
            return set()
        return {json.loads(l)["task_id"] for l in p.read_text().splitlines() if l.strip()}

    def prune_partial(self) -> None:
        """Drop decision records of items that never finished (an interrupted attempt)."""
        done = self.done_items()
        p = self.dir / "decisions.jsonl"
        if p.exists():
            keep = [l for l in p.read_text().splitlines() if l.strip() and json.loads(l)["task_id"] in done]
            tmp = p.with_suffix(".tmp")
            tmp.write_text("".join(l + "\n" for l in keep))
            os.replace(tmp, p)
        if not done and (self.dir / "trajectory.jsonl").exists():
            (self.dir / "trajectory.jsonl").unlink()

    def write_item(self, traj: dict, decisions: list[dict]) -> None:
        dec_txt = "".join(json.dumps(d, ensure_ascii=False, default=str) + "\n" for d in decisions)  # serialize first:
        traj_txt = json.dumps(traj, ensure_ascii=False, default=str) + "\n"  # a failure must not leave half an item
        with self.lock:
            with open(self.dir / "decisions.jsonl", "a", encoding="utf-8") as f:
                f.write(dec_txt)
            with open(self.dir / "trajectory.jsonl", "a", encoding="utf-8") as f:
                f.write(traj_txt)

    def write_json(self, name: str, obj) -> None:
        (self.dir / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False))

    def trajectories(self) -> list[dict]:
        return [json.loads(l) for l in (self.dir / "trajectory.jsonl").read_text().splitlines() if l.strip()]


def write_headers(rd: RunDir, args, bench: dict, task_ids: list[str], packages: list[str], manifest_path: Path) -> None:
    msha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    rd.write_json("config.json", {
        "run_id": args.run_id, "arm": args.arm, "domain": args.domain, "checkpoint": args.checkpoint,
        "adapter": ADAPTER_VERSION, "env": bench["env"], "benchmark": bench,
        "generation_agent": gen_params(), "frozen_generation_source": "configs/frozen_v0.json generation_agent",
        "manifest": str(manifest_path.relative_to(ROOT)), "manifest_sha256": msha, "subset": args.subset,
        "max_concurrency": args.max_concurrency,
    })
    rd.write_json("environment.json", {
        "hostname": platform.node(), "platform": platform.platform(), "python": sys.version, "executable": sys.executable,
        "packages": pkg_versions(packages), "cloq_commit": git_rev(ROOT), "agent_api_base": args.agent_base,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"), "prompt_nonce": os.environ.get("CLOQ_PROMPT_NONCE"),
        "model_id": os.environ.get("CLOQ_MODEL_ID"), "model_revision": os.environ.get("CLOQ_MODEL_REVISION"),
        "chat_template_kwargs": json.loads(os.environ.get("CLOQ_CHAT_TEMPLATE_KWARGS") or "{}"),
        "tool_parser": os.environ.get("CLOQ_TOOL_PARSER"), "top_logprobs": int(os.environ.get("CLOQ_TOP_LOGPROBS", "0")),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    rd.write_json("model.json", {
        "hf_id": os.environ.get("CLOQ_MODEL_ID"), "revision": os.environ.get("CLOQ_MODEL_REVISION"), "arm": args.arm,
        "checkpoint": args.checkpoint, "agent_server_models": served_models(args.agent_base),
    })
    rd.write_json("task_manifest.json", {"domain": args.domain, "task_ids": task_ids, "n_tasks": len(task_ids),
                                         "manifest": str(manifest_path.relative_to(ROOT)), "manifest_sha256": msha,
                                         "subset": args.subset})


def summarize(rd: RunDir, extra: dict | None = None) -> dict:
    trs = rd.trajectories()
    n = len(trs)
    decs = [json.loads(l) for l in (rd.dir / "decisions.jsonl").read_text().splitlines() if l.strip()] \
        if (rd.dir / "decisions.jsonl").exists() else []
    reasons: dict[str, int] = {}
    for t in trs:
        reasons[t["termination_reason"]] = reasons.get(t["termination_reason"], 0) + 1
    m = {
        "n_tasks": n, "success_rate": (sum(bool(t["success"]) for t in trs) / n) if n else None,
        "reward_mean": (sum(float(t["reward"]) for t in trs) / n) if n else None,
        "official_reward_mean": (sum(float(t["reward"]) for t in trs) / n) if n else None,
        "mean_decisions": (sum(t["n_decisions"] for t in trs) / n) if n else None,
        "mean_seconds_per_item": (sum(t["duration"] for t in trs) / n) if n else None,
        "max_seconds_per_item": max((t["duration"] for t in trs), default=None),
        "parser_error_rate": (sum(d["parser_error"] for d in decs) / len(decs)) if decs else None,
        "n_decisions_total": len(decs),
        "mean_prompt_tokens": (sum(d["n_prompt_tokens"] or 0 for d in decs) / len(decs)) if decs else None,
        "max_prompt_tokens": max((d["n_prompt_tokens"] or 0 for d in decs), default=None),
        "termination_reasons": reasons,
        "per_item": {t["task_id"]: t["success"] for t in trs},
    }
    m.update(extra or {})
    return m


def common_args(ap) -> None:
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--subset", default="smoke", help="manifest subset: dev | smoke | eval, or ids:<a,b,...>")
    ap.add_argument("--agent-base", default="http://127.0.0.1:8001/v1")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--max-concurrency", type=int, default=int(FROZEN["serving"]["max_concurrency"]))
    ap.add_argument("--limit", type=int, default=0, help="first N items of the subset (dev checks only)")


def host() -> str:
    return socket.gethostname()
