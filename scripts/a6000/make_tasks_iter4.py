"""Iteration-4 tasks (user go-ahead 2026-09-29): is a quantized checkpoint a reproducible behavioural variant, unlike
random perturbations and sampling? Plan: docs/insights/iter_4_disposition.md (E4-1..E4-5), RESEARCH_LOG W19.

  E4-1 open-loop probes for existing checkpoints on q8/q14/q30a3/q32 (no simulator): reprioritise queued ones, add
       the missing awq_w4_d2 / gshape_w4 / rtnsign_w4 cells.
  E4-3 checkpoint replication: calibration draws c3, c4 -> GPTQ-W4 and AWQ-W4 d3, d4 on q4/q8, 2 fresh nonces each
       (+ their open-loop probes).
  E4-4 fixed Gaussian k=1 checkpoints, seeds s2/s4/s5 on q4/q8, 2 fresh nonces each (nonce noise separated from
       checkpoint identity, same design as churnctl_k1 = seed 1).
  S    sampling baseline on q4: BF16 agent at T in {0.2, 0.5, 0.8}, seeds 1-3 paired with fresh nonces q1-q3.
  D    deprioritise KV-cache quant, q8/q14 new-method cells and telecom (+30 priority; nothing is deleted).

usage: python scripts/a6000/make_tasks_iter4.py [--dry]
Lower priority = runs sooner. Existing task files are never overwritten (skip if the id exists anywhere in the queue).
"""
import argparse
import json
from pathlib import Path

Q = Path("/data/ziyangs/cloq_work/queue")
DIRS = ("todo", "running", "done", "failed", "deferred")
NONCE = {"q1": "6d1f0b3e", "q2": "f07a5c21", "q3": "4c8e1a7f"}
TASKS = "manifests/eval_tasks_v0.json"


def where(tid):
    for d in DIRS:
        if (Q / d / f"{tid}.json").exists():
            return d
    return None


def load(tid):
    d = where(tid)
    return json.load(open(Q / d / f"{tid}.json")) if d else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    new, bumped = [], []

    def add(t):
        if where(t["id"]) is None:
            new.append(t)

    def ol(m, cell, ckpt, arm, deps, prio):
        add({"id": f"a6k2_{m}_ol_{cell}", "kind": "eval", "model": m, "arm": arm, "ckpt": ckpt, "runs": [],
             "priority": prio, "deps": deps + [f"a6k2_{m}_bf16"],
             "openloop": {"ref_runs": [f"a6k2_{m}_bf16"], "n": 400, "out": f"analysis/openloop/a6k2/{m}/{cell}"}})

    # E4-1: reprioritise existing open-loop tasks, add missing cells whose checkpoint spec exists in a closed-loop task
    for m in ("q8", "q14", "q30a3", "q32"):
        for cell in ("rtn_w4", "gptq_w4_d1", "gptq_w4_d2", "awq_w4", "awq_w4_d2", "rtn_w3", "gptq_w3",
                     "gshape_w4", "rtnsign_w4", "nf4"):
            tid = f"a6k2_{m}_ol_{cell}"
            if where(tid) == "todo":
                bumped.append((tid, -8))
            elif where(tid) is None:
                src = load(f"a6k2_{m}_{cell}")
                if src is not None:
                    ol(m, cell, src["ckpt"], src["arm"], [x for x in src.get("deps", []) if "calib" in x], -8)

    # E4-3: extra calibration draws and checkpoints
    for m in ("q4", "q8"):
        for d in ("c3", "c4"):
            add({"id": f"a6k2_{m}_calib_{d}", "kind": "calib", "model": m, "arm": "fp_traj", "draw": d,
                 "fp_run": f"a6k2_{m}_bf16_cal", "out": f"manifests/a6k2/{m}/calib_fp_traj_{d}.json",
                 "priority": -9, "deps": [f"a6k2_{m}_bf16_cal"]})
            for meth in ("gptq", "awq"):
                cell = f"{meth}_w4_d{d[1]}"
                ck = {"kind": meth, "wbits": 4, "calib": f"manifests/a6k2/{m}/calib_fp_traj_{d}.json"}
                add({"id": f"a6k2_{m}_{cell}", "kind": "eval", "model": m, "arm": meth, "ckpt": ck,
                     "runs": [{"run_id": f"a6k2_{m}_{cell}_{q}", "task_file": TASKS, "nonce": NONCE[q]} for q in ("q1", "q2")],
                     "priority": -7, "deps": [f"a6k2_{m}_calib_{d}"]})
                ol(m, cell, ck, meth, [f"a6k2_{m}_calib_{d}"], -8)

    # E4-4: fixed Gaussian k=1 checkpoints under fresh nonces
    for m in ("q4", "q8"):
        for s in (2, 4, 5):
            add({"id": f"a6k2_{m}_churnctl_k1_s{s}", "kind": "eval", "model": m, "arm": "gauss",
                 "ckpt": {"kind": "gauss", "k": 1.0, "seed": s},
                 "runs": [{"run_id": f"a6k2_{m}_gauss1_s{s}_{q}", "task_file": TASKS, "nonce": NONCE[q]} for q in ("q1", "q2")],
                 "priority": -7, "deps": []})

    # S: sampling baseline (BF16, fresh nonces, per-run temperature and seed)
    for T in ("0.2", "0.5", "0.8"):
        add({"id": f"a6k2_q4_samp_T{T}", "kind": "eval", "model": "q4", "arm": "bf16", "ckpt": {"kind": "bf16"},
             "runs": [{"run_id": f"a6k2_q4_samp_T{T}_s{i}_{q}", "task_file": TASKS, "nonce": NONCE[q],
                       "env": {"CLOQ_AGENT_TEMPERATURE": T, "CLOQ_AGENT_SEED": str(i)}}
                      for i, q in ((1, "q1"), (2, "q2"), (3, "q3"))],
             "priority": -6, "deps": []})

    # D: deprioritise
    for f in sorted((Q / "todo").glob("*.json")):
        t = json.load(open(f))
        tid = t["id"]
        if any(tid == b[0] for b in bumped) or t in new:
            continue
        low = ("_kvq_" in tid or "telecom" in tid or "_tc_" in tid
               or (any(f"_{m}_" in tid for m in ("q8", "q14"))
                   and any(c in tid for c in ("_nf4", "_mxfp4", "_rot_", "_rtnsr_"))))
        if low and "_ol_" not in tid and t.get("priority", 0) < 30:
            bumped.append((tid, t.get("priority", 0) + 30))

    for t in new:
        print("NEW ", t["id"], t["priority"], len(t.get("runs", [])), "runs")
    for tid, p in bumped:
        print("PRIO", tid, "->", p)
    if a.dry:
        return
    for t in new:
        json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
    for tid, p in bumped:
        f = Q / "todo" / f"{tid}.json"
        t = json.load(open(f))
        t["priority"] = p
        json.dump(t, open(f, "w"), indent=1)


if __name__ == "__main__":
    main()
