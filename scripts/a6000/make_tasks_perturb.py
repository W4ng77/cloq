"""Checkpoint specs for P2 line 3 (restoration arms, residual dose) and the smoke tasks that prove the kinds build and serve.

specs(model, cell) returns {name: ckpt dict} for every arm of one primary checkpoint (manifests/fork/dev_blocks_v1.json:
gptq_w4_d1 / awq_w4 = calibration c1, on q4 / q8): 14 restoration arms + 2 controls + 5 residual doses. Fork tasks use
them as q_ckpt (or b_ckpt); the fork scheduling itself belongs to the main session (make_tasks_fork_dev.py).

--smoke --write queues only the smoke set (priority -7): q4 gptq_w4_d1 resid a0 / a1 build+serve+canary (no episodes),
q4 restore late and resid a0.5 one BF16-harness run on the 20 determinism tasks, q8 awq_w4 restore rand_attn_s1
build+serve+canary. Everything else prints only.

usage: python scripts/a6000/make_tasks_perturb.py [--smoke] [--write]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
CK = {"gptq_w4_d1": "gptq", "awq_w4": "awq"}
DET = "manifests/a6000/det_tasks.json"
ALPHAS = (0.0, 0.25, 0.5, 1.0, 2.0)


def base(model: str, cell: str) -> dict:
    return {"kind": CK[cell], "wbits": 4, "calib": f"manifests/a6k2/{model}/calib_fp_traj_c1.json"}


def specs(model: str, cell: str) -> dict[str, dict]:
    b = base(model, cell)
    out = {}
    for p in sorted((ROOT / "manifests/perturb/restore_v1" / model).glob("*.json")):
        out[f"restore_{p.stem}"] = {"kind": "restore", "base": b, "arm": p.stem,
                                    "manifest": str(p.relative_to(ROOT))}
    for a in ALPHAS:
        out[f"resid_a{a:g}"] = {"kind": "resid", "base": b, "alpha": a}
    return out


def smoke() -> list[dict]:
    q4 = specs("q4", "gptq_w4_d1")
    q8 = specs("q8", "awq_w4")
    t = []

    def task(tid, model, name, ck, runs, deps=()):
        return {"id": tid, "kind": "eval", "model": model, "arm": name, "ckpt": ck, "runs": runs, "priority": -7,
                "deps": list(deps), "note": "P2 line 3 smoke (make_tasks_perturb.py): derived ckpt kind builds, serves, "
                                            "passes the numerics canary rules; docs/insights/PERTURBATION_PROTOCOL.md"}
    t.append(task("pert_smoke_q4_gptq_resid_a0", "q4", "resid_a0", q4["resid_a0"], []))
    first = [t[0]["id"]]  # builds and caches the q4 GPTQ base; the others reuse it
    t.append(task("pert_smoke_q4_gptq_resid_a1", "q4", "resid_a1", q4["resid_a1"], [], first))
    t.append(task("pert_smoke_q4_gptq_restore_late", "q4", "restore_late", q4["restore_late"],
                  [{"run_id": "a6k2_pert_smoke_q4_gptq_restore_late", "task_file": DET, "nonce": None}], first))
    t.append(task("pert_smoke_q4_gptq_resid_a0.5", "q4", "resid_a0.5", q4["resid_a0.5"],
                  [{"run_id": "a6k2_pert_smoke_q4_gptq_resid_a0.5", "task_file": DET, "nonce": None}], first))
    t.append(task("pert_smoke_q8_awq_restore_rand_attn_s1", "q8", "restore_rand_attn_s1", q8["restore_rand_attn_s1"], []))
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if not a.smoke:
        for m, cells in json.load(open(ROOT / "manifests/fork/dev_blocks_v1.json"))["cells"].items():
            for c in cells:
                s = specs(m, c)
                print(m, c, len(s), "ckpt specs:", " ".join(s))
        print("(specs only; fork tasks are scheduled by the main session)")
        return
    ts = smoke()
    for t in ts:
        print(t["id"], t["ckpt"]["kind"], len(t["runs"]), "runs", "deps:", ",".join(t["deps"]))
    if not a.write:
        print(f"{len(ts)} smoke tasks (dry run)")
        return
    for t in ts:
        if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
            json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
            print("queued", t["id"])


if __name__ == "__main__":
    main()
