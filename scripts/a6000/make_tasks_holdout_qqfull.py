"""Holdout full QQ no-op replay (W100av; docs/insights/HOLDOUT_QQFULL_PROTOCOL.md). DRY RUN by default; --write queues.
For each of the 18 telecom HOLDOUT fork dirs (make_tasks_holdout.py FORK_CELLS x g01-g06) one fork task in mode "branches"
with branches [] and noop_frac 1.0: a QQ re-run of EVERY frozen state (the 1067 unsampled ones and, as a repeat, the 135
sampled ones). The B/Q checkpoints, GPU count, gpu_util and concurrency are copied from the done fork_hold_* task; only the
mode, the branch list, noop_frac and the output root change. Holdout states are read by the driver only; nothing under
analysis/fork/holdout/ is written. Output: analysis/fork/holdout_qqfull/<model>_<cell>/gNN/branches/<state_id>.json.
usage: python scripts/a6000/make_tasks_holdout_qqfull.py [--write] [--priority P]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT, Q = Path("/data/ziyangs/cloq"), Path("/data/ziyangs/cloq_work/queue")
CELLS, GROUPS, QDIRS = (("q4", "gptq_w4_d1"), ("q8", "gptq_w4_d1"), ("q8", "awq_w4")), [f"g{k:02d}" for k in range(1, 7)], ("todo", "running", "done", "failed", "deferred")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--priority", type=int, default=-20)
    a = ap.parse_args()
    T = []
    for m, cell in CELLS:
        for g in GROUPS:
            src = json.load(open(Q / "done" / f"fork_hold_{m}_{cell}_{g}.json"))
            f0 = src["fork"]
            assert f0["out"] == f"analysis/fork/holdout/{m}_{cell}/{g}" and f0["mode"] == "dev", src["id"]
            T.append({"id": f"qqfull_hold_{m}_{cell}_{g}", "kind": "fork", "model": m, "gpus": src["gpus"],
                      **({"gpu_util": src["gpu_util"]} if "gpu_util" in src else {}), "priority": a.priority, "deps": [],
                      "B": src["B"], "Q": src["Q"],
                      "fork": {"mode": "branches", "states_dir": f"{f0['out']}/states", "branches": [], "noop_frac": 1.0,
                               "concurrency": f0.get("concurrency", 8), "out": f"analysis/fork/holdout_qqfull/{m}_{cell}/{g}"},
                      "note": "W100av holdout full QQ no-op replay (make_tasks_holdout_qqfull.py; HOLDOUT_QQFULL_PROTOCOL.md)"})
    ex = lambda tid: any((Q / d / f"{tid}.json").exists() for d in QDIRS)  # noqa: E731
    for t in T:
        print(f"{t['id']:36s} gpus {t['gpus']}  {t['fork']['states_dir']} -> {t['fork']['out']}{'  (EXISTS)' if ex(t['id']) else ''}")
    if not a.write:
        return print(f"{len(T)} tasks; DRY RUN: nothing written")
    n = 0
    for t in T:
        if not ex(t["id"]):
            json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
            n += 1
    print("queued", n)


if __name__ == "__main__":
    sys.exit(main())
