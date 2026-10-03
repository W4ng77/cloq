"""NEWMETHOD_PANEL_PROTOCOL A7 (W100ab): queue one `bank_u_arms` re-run task per (cell, block) for the failed q8 τ² arms
classified in analysis/fork/kivi_recovery/failed_arms.json (A7.2). Re-run: service_failure_verified and
timeout_cause_not_established (the concurrency-1 diagnosis); class "other" stays missing. Each task copies the original
nmp_tau2 task's B and Q roles verbatim (checkpoint, serve_env, hook flags) and records the original servers' provenance
(canary, ckpt sha, effective config sha, hook version) in `a7_expect` for the post-run identity check. Never overwrites a
task id; never re-queued by the infra retry (one re-run only).

usage: python scripts/a6000/make_tasks_a7.py [--write]
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

ROOT, WORK = Path("/data/ziyangs/cloq"), Path("/data/ziyangs/cloq_work")
Q = WORK / "queue"
RERUN = ("service_failure_verified", "timeout_cause_not_established")
SKIP = {"id", "priority", "deps", "fork", "note", "result", "finished", "seconds", "host", "error_history", "requeue_note",
        "requeue_notes", "autopilot_retry", "node", "priority_note"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--priority", type=int, default=-29)
    a = ap.parse_args()
    arms = json.loads((ROOT / "analysis/fork/kivi_recovery/failed_arms.json").read_text())
    by: dict = {}
    for x in arms:
        if x["class"] in RERUN:
            by.setdefault((x["cell"], x["block"]), []).append([x["state_key"], x["arm"]])
        else:
            print(f"stays missing (class {x['class']}): {x['cell']} {x['block']} {x['state_key']} {x['arm']}")
    for (cell, blk), sel in sorted(by.items()):
        oid = f"nmp_tau2_q8_{cell}_{blk}"
        orig = json.loads((Q / "done" / f"{oid}.json").read_text())
        srv = json.loads((WORK / "logs/tasks" / f"{oid}.servers.json").read_text())
        tid = f"a7_rr1_q8_{cell}_{blk}"
        if any((Q / d / f"{tid}.json").exists() for d in ("todo", "running", "done", "failed", "deferred")):
            print(f"exists, skipped: {tid}")
            continue
        f = orig["fork"]
        t = {**{k: v for k, v in orig.items() if k not in SKIP}, "id": tid, "priority": a.priority, "deps": [],
             "fork": {"mode": "bank_u_arms", "manifest": f["manifest"], "manifest_sha256": f["manifest_sha256"], "model": "q8",
                      "cell": cell, "block": blk, "src_out": f["out"], "out": f"analysis/fork/newmethod/tau2_recovery/q8_{cell}/{blk}/rr1",
                      "arms": sorted(sel), "concurrency": 1, "tag_suffix": "rr1"},
             "a7_expect": {r: {k: srv[r].get(k) for k in ("canary", "ckpt_sha256", "effective_config_sha")} | {"hook_version": (srv[r].get("effective_config") or {}).get("hook_version")}
                           for r in ("B", "Q")},
             "autopilot_retry": "no (A7: one re-run per arm; a failed re-run is left for a human)",
             "note": f"NEWMETHOD A7 (W100ab): one re-run of {len(sel)} failed arm(s) of {oid}, concurrency 1, recorded actions; originals read only",
             "created": time.strftime("%Y-%m-%d %H:%M:%S")}
        print(tid, len(sel), "arms", t["gpus"], t["fork"]["out"])
        if a.write:
            p = Q / "todo" / f"{tid}.json"
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(t, indent=1))
            tmp.rename(p)


if __name__ == "__main__":
    sys.exit(main())
