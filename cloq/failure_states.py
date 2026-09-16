"""Where do the Q0 states in the CLOQ buffer come from? (plan section 19)

For every Q0-sourced context in the CLOQ calibration buffer, classify the decision it was
taken from:

  before_divergence    the quantized agent still matched the BF16 tool behaviour at that point
  after_divergence     at or past the first tool-behaviour divergence on that calibration task
  parser_error         the model emitted tool-call syntax the parser could not use
  tool_error           the decision's tool call returned an error
  repeated_tool_call   the same normalised tool call had already been made in that trajectory
  near_failed_end      in the last quarter of a trajectory that ended without success
  truncated_context    the frozen context policy had to drop history for this decision

Categories overlap by construction; each is reported as a share of the Q0 token budget.

usage: python -m cloq.failure_states --calib manifests/calib_cloq.json --q-run q0_fp_traj --bf16-run bf16
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from cloq import config as C
from cloq.metrics import load_decisions, normalize_action, normalize_tool_call, read_jsonl


def _tool_divergence_index(fp: list[dict], q: list[dict]) -> int | None:
    """First decision whose tool-call behaviour differs (same rule as cloq.divergence)."""
    for i in range(min(len(fp), len(q))):
        fk = "tool" if fp[i]["tool_calls"] else "text"
        qk = "tool" if q[i]["tool_calls"] else "text"
        if fk != qk:
            return i
        if fk == "tool" and normalize_action(fp[i]["content"], fp[i]["tool_calls"]) != normalize_action(q[i]["content"], q[i]["tool_calls"]):
            return i
    if len(fp) != len(q):
        return min(len(fp), len(q))
    return None


def analyze(calib_path: Path, q_run: str, bf16_run: str) -> dict:
    man = json.load(open(calib_path))
    q_ctx = [c for c in man["contexts"] if c["source"] == "q0"]
    if not q_ctx:
        return {"note": "no Q0 contexts in this buffer"}
    domains = sorted({c["domain"] for c in q_ctx})

    dec, traj, tstar = {}, {}, {}
    for dom in domains:
        qd = defaultdict(list)
        for d in load_decisions(C.RUNS_DIR / q_run / dom):
            qd[d["task_id"]].append(d)
        fd = defaultdict(list)
        for d in load_decisions(C.RUNS_DIR / bf16_run / dom):
            fd[d["task_id"]].append(d)
        for v in list(qd.values()) + list(fd.values()):
            v.sort(key=lambda d: d["decision_idx"])
        dec[dom] = qd
        traj[dom] = {t["task_id"]: t for t in read_jsonl(C.RUNS_DIR / q_run / dom / "trajectory.jsonl")}
        tstar[dom] = {tid: _tool_divergence_index(fd[tid], qd[tid]) for tid in qd if tid in fd}

    cats = ["before_divergence", "after_divergence", "parser_error", "tool_error",
            "repeated_tool_call", "near_failed_end", "truncated_context"]
    tok = {c: 0 for c in cats}
    cnt = {c: 0 for c in cats}
    total_tokens = sum(c["n_tokens"] for c in q_ctx)
    rows = []
    for c in q_ctx:
        dom, tid, idx = c["domain"], c["task_id"], c["decision_idx"]
        ds = dec[dom][tid]
        d = next((x for x in ds if x["decision_idx"] == idx), None)
        if d is None:
            continue
        t = traj[dom].get(tid, {})
        ts = tstar[dom].get(tid)
        # did this decision's tool call return an error?
        tool_err = False
        if d["tool_calls"]:
            ids = {tc.get("id") for tc in d["tool_calls"]}
            for m in t.get("messages", []):
                if m.get("role") == "tool" and m.get("id") in ids and m.get("error"):
                    tool_err = True
        earlier = [normalize_tool_call(tc["name"], tc.get("arguments"))
                   for x in ds if x["decision_idx"] < idx for tc in (x["tool_calls"] or [])]
        repeated = bool(d["tool_calls"]) and any(
            normalize_tool_call(tc["name"], tc.get("arguments")) in earlier for tc in d["tool_calls"])
        n_dec = len(ds)
        failed = not bool(t.get("db_match")) or t.get("termination_reason") not in ("user_stop", "agent_stop")
        flags = {
            "before_divergence": ts is not None and idx < ts,
            "after_divergence": ts is not None and idx >= ts,
            "parser_error": bool(d.get("parser_error")),
            "tool_error": tool_err,
            "repeated_tool_call": repeated,
            "near_failed_end": failed and n_dec > 0 and idx >= 0.75 * (n_dec - 1),
            "truncated_context": bool((d.get("context") or {}).get("truncated")),
        }
        for k, v in flags.items():
            if v:
                tok[k] += c["n_tokens"]
                cnt[k] += 1
        rows.append({"domain": dom, "task_id": tid, "decision_idx": idx, "n_tokens": c["n_tokens"],
                     "t_star": ts, "n_decisions": n_dec, "trajectory_failed": failed, **flags})
    return {
        "calib": str(calib_path), "q_run": q_run, "bf16_run": bf16_run,
        "n_q_contexts": len(q_ctx), "q_tokens": total_tokens,
        "share_of_q_tokens": {k: (tok[k] / total_tokens if total_tokens else None) for k in cats},
        "n_contexts": cnt,
        "per_context": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calib", default=str(C.MANIFEST_DIR / "calib_cloq.json"))
    ap.add_argument("--q-run", default="q0_fp_traj")
    ap.add_argument("--bf16-run", default="bf16")
    ap.add_argument("--out", default=str(C.PROJECT_ROOT / "analysis" / "failure_states.json"))
    a = ap.parse_args()
    res = analyze(Path(a.calib), a.q_run, a.bf16_run)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "per_context"}, indent=2))


if __name__ == "__main__":
    main()
