"""W100q: classify the 'infrastructure_error episodes (outage)' behind failed/ and running/ eval tasks (read-only).

For every eval task in queue/failed and queue/running, and every run-domain with a tau2_results.json, each
infrastructure_error episode is classified like worker.py (context overflow / parse / empty output are agent failures,
the rest is 'outage'), and outages are split by side from the traceback (agent: tau2 llm_agent.py; user: user
simulator). The run-domain status.json is reported because worker.py re-raises on a 'completed' run-domain that holds
outages, so a plain retry re-fails without re-running them. Agent vLLM queue stats come from the task's .vllm.log
(30 s / 10 s engine log lines: running, waiting, KV usage).

usage: python analysis/status/gpu_fill_20261003/triage_outages.py > analysis/status/gpu_fill_20261003/triage_outages.json
"""
from __future__ import annotations

import collections, glob, json, os, re, statistics, sys

ROOT, WORK = "/data/ziyangs/cloq", "/data/ziyangs/cloq_work"
LINE = re.compile(r"Running: (\d+) reqs, Waiting: (\d+) reqs, GPU KV cache usage: ([\d.]+)%")


def cause(info: dict) -> str:
    e, tb = str(info.get("error", "")), str(info.get("error_traceback", ""))
    if "ContextWindowExceeded" in e:
        return "context_overflow"
    if "only supports single tool-calls" in e or ("Function name was" in e and "must be a-z" in e):
        return "agent_parse_error"
    if "AssistantMessage must have either content or tool_calls" in e:
        return "agent_empty_output"
    if "validation error for ToolCall" in e:
        return "toolcall_validation"
    side = "agent" if "llm_agent.py" in tb else ("user" if "user" in tb else "unknown")
    kind = "timeout600" if "Timeout" in e else ("conn_refused" if "refused" in e else e[:60])
    return f"outage:{side}:{kind}"


def vllm_stats(task_id: str) -> dict | None:
    p = f"{WORK}/logs/tasks/{task_id}.vllm.log"
    if not os.path.exists(p):
        return None
    r, w, kv = [], [], []
    for ln in open(p, errors="ignore"):
        m = LINE.search(ln)
        if m:
            r.append(int(m[1])); w.append(int(m[2])); kv.append(float(m[3]))
    if not w:
        return None
    return {"n_lines": len(w), "running_median": statistics.median(r), "waiting_median": statistics.median(w),
            "waiting_max": max(w), "kv_median_pct": statistics.median(kv),
            "frac_waiting_gt0": round(sum(x > 0 for x in w) / len(w), 2)}


def main() -> None:
    out = {}
    for state in ("failed", "running"):
        for f in sorted(glob.glob(f"{WORK}/queue/{state}/*.json")):
            try:
                t = json.load(open(f))
            except Exception:
                continue
            if t.get("kind") != "eval":
                continue
            rd = {}
            for r in t.get("runs", []):
                for d in t.get("domains", ("retail", "airline")):
                    base = f"{ROOT}/runs/{r['run_id']}/{d}"
                    res = f"{base}/tau2_results.json"
                    if not os.path.exists(res) or os.path.getsize(res) > 1.5e9:
                        continue
                    try:  # a running task may be rewriting the file
                        sims = json.load(open(res)).get("simulations", [])
                    except ValueError:
                        continue
                    c = collections.Counter(cause(s.get("info") or {}) for s in sims
                                            if str(s.get("termination_reason")) == "infrastructure_error")
                    st = json.load(open(f"{base}/status.json")).get("status") if os.path.exists(f"{base}/status.json") else None
                    if c:
                        rd[f"{r['run_id']}/{d}"] = {"status": st, "n_sims": len(sims), "infra": dict(c)}
            n_out = sum(v for x in rd.values() for k, v in x["infra"].items() if k.startswith("outage"))
            if n_out or state == "failed":
                out[t["id"]] = {"queue": state, "host": t.get("host"), "autopilot_retry": t.get("autopilot_retry"),
                                "error": str(t.get("error", ""))[:160], "n_outage": n_out, "run_domains": rd,
                                "agent_vllm": vllm_stats(t["id"])}
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
