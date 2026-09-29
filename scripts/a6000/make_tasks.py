"""Write the A6000 matrix (docs/A6000_PLAN.md section 3) into the file queue. Idempotent: a task whose id
is already in todo/, running/ or done/ is left alone (failed/ tasks are re-queued only with --retry).

usage: python scripts/a6000/make_tasks.py q4 q8 ...  [--retry] [--only det]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

WORK = Path("/data/ziyangs/cloq_work")
Q = WORK / "queue"
EVAL = "manifests/eval_tasks_v0.json"
CAL = "manifests/cal_tasks_v0.json"
DET = "manifests/a6000/det_tasks.json"
NONCES = ["3f9a1c07", "b84e2d91", "5c0d7e3a", "e21f6b48", "9a7c4f15"]
GAUSS_K = ["0.03", "0.1", "0.3", "1", "3"]
MODEL_PRIORITY = {"q4": 10, "q8": 20, "m24": 30, "l8": 30, "q14": 40, "q30a3": 50, "q32": 60}


def eval_task(tid, model, arm, ckpt, runs, priority, deps=()):
    return {"id": tid, "kind": "eval", "model": model, "arm": arm, "ckpt": ckpt, "runs": runs,
            "priority": priority, "deps": list(deps)}


def run(rid, task_file=EVAL, nonce=None):
    return {"run_id": rid, "task_file": task_file, "nonce": nonce}


def matrix(m: str, prefix: str = "a6000", tid: str = "") -> list[dict]:
    p = MODEL_PRIORITY[m]
    R = f"{prefix}_{m}"
    t = [eval_task(f"{m}_bf16_cal", m, "bf16", {"kind": "bf16"}, [run(f"{R}_bf16_cal", CAL)], 0),
         eval_task(f"{m}_bf16", m, "bf16", {"kind": "bf16"},
                   [run(f"{R}_bf16")] + [run(f"{R}_null_n{i + 1}", nonce=n) for i, n in enumerate(NONCES)], p)]
    for k in GAUSS_K:
        for s in (1, 2):
            t.append(eval_task(f"{m}_gauss{k}_s{s}", m, "gauss", {"kind": "gauss", "k": float(k), "seed": s},
                               [run(f"{R}_gauss{k}_s{s}")], p + 1))
    for b in (8, 4, 3):
        t.append(eval_task(f"{m}_rtn_w{b}", m, "rtn", {"kind": "rtn", "wbits": b},
                           [run(f"{R}_rtn_w{b}_n{i + 1}", nonce=NONCES[i]) for i in range(2)], p + 1))
    for d in ("c1", "c2"):
        t.append({"id": f"{m}_calib_{d}", "kind": "calib", "model": m, "arm": "fp_traj", "draw": d,
                  "fp_run": f"{R}_bf16_cal", "out": f"manifests/{prefix}/{m}/calib_fp_traj_{d}.json",
                  "priority": 0, "deps": [f"{m}_bf16_cal"]})
    for name, kind, bits, d in (("gptq_w4_d1", "gptq", 4, "c1"), ("gptq_w4_d2", "gptq", 4, "c2"),
                                ("awq_w4", "awq", 4, "c1"), ("gptq_w3", "gptq", 3, "c1")):
        t.append(eval_task(f"{m}_{name}", m, kind, {"kind": kind, "wbits": bits,
                                                    "calib": f"manifests/{prefix}/{m}/calib_fp_traj_{d}.json"},
                           [run(f"{R}_{name}_n{i + 1}", nonce=NONCES[i]) for i in range(2)], p - 1,
                           deps=[f"{m}_calib_{d}"]))
    return t


def e5(m: str, prefix: str = "a6000") -> list[dict]:
    """E5 (docs/insights/EXPERIMENTS.md): numerics-flavour null (eager BF16) + weight-only null (gauss k=0.03 s3-s5)."""
    p = MODEL_PRIORITY[m] + 2
    R = f"{prefix}_{m}"
    t = [dict(eval_task(f"{m}_bf16_eager", m, "bf16", {"kind": "bf16"}, [run(f"{R}_bf16_eager")], p),
              serve_extra=["--enforce-eager"])]
    for s in (3, 4, 5):
        t.append(eval_task(f"{m}_gauss0.03_s{s}", m, "gauss", {"kind": "gauss", "k": 0.03, "seed": s},
                           [run(f"{R}_gauss0.03_s{s}")], p))
    return t


def e3(m: str, prefix: str = "a6000", n: int = 400) -> list[dict]:
    """E3 (docs/insights/EXPERIMENTS.md): open-loop D of every matrix cell on the model's BF16 reference contexts."""
    R, tid = f"{prefix}_{m}", ""
    ref = f"{prefix}_{m}_bf16"
    out = []
    for t in matrix(m, prefix) + e5(m, prefix):
        if t["kind"] != "eval" or t["id"].endswith("_cal"):
            continue
        cell = t["id"][len(m) + 1:]
        out.append(dict(t, id=f"{m}_ol_{cell}", runs=[], priority=MODEL_PRIORITY[m] + 100,
                        deps=list(t.get("deps", [])) + [f"{m}_bf16"],
                        openloop={"ref_runs": [ref], "n": n, "out": f"analysis/openloop/{prefix}/{m}/{cell}"}))
    return out


def determinism(m: str, rep: str, node: str, prefix: str = "a6000", tid: str = "") -> dict:
    """Same BF16 config, 20 tasks; two copies on different nodes must produce byte-identical decisions."""
    t = eval_task(f"{tid}det_{m}_{rep}", m, "bf16", {"kind": "bf16"}, [run(f"{prefix}_det_{m}_{rep}", DET)], -10)
    t["node"] = node
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--retry", action="store_true")
    ap.add_argument("--only", choices=["det", "matrix", "e5", "e3"], default=None)
    ap.add_argument("--prefix", default="a6000", help="run-id prefix; a6k2 = deterministic-Inductor rerun (W3)")
    a = ap.parse_args()
    for d in ("todo", "running", "done", "failed"):
        (Q / d).mkdir(parents=True, exist_ok=True)
    n = 0
    for m in a.models:
        tasks = []
        if a.only in (None, "det"):
            tid = "" if a.prefix == "a6000" else a.prefix + "_"
            tasks += [determinism(m, "a", "node005", a.prefix, tid), determinism(m, "b", "node004", a.prefix, tid)]
        if a.only in (None, "matrix"):
            tid = "" if a.prefix == "a6000" else a.prefix + "_"
            tasks += [dict(t, id=tid + t["id"], deps=[tid + d for d in t.get("deps", [])]) for t in matrix(m, a.prefix)]
        if a.only == "e3":
            tid = "" if a.prefix == "a6000" else a.prefix + "_"
            tasks += [dict(t, id=tid + t["id"], deps=[tid + d for d in t["deps"]]) for t in e3(m, a.prefix)]
        if a.only == "e5":
            tid = "" if a.prefix == "a6000" else a.prefix + "_"
            tasks += [dict(t, id=tid + t["id"]) for t in e5(m, a.prefix)]
        for t in tasks:
            name = f"{t['id']}.json"
            if any((Q / d / name).exists() for d in ("todo", "running", "done")):
                continue
            if (Q / "failed" / name).exists():
                if not a.retry:
                    continue
                (Q / "failed" / name).unlink()
            (Q / "todo" / name).write_text(json.dumps(t, indent=1))
            n += 1
    print(f"queued {n} tasks")


if __name__ == "__main__":
    main()
