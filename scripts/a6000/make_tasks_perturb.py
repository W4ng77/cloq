"""Checkpoint specs for P2 line 3 (restoration arms, residual dose) and the smoke tasks that prove the kinds build and serve.

specs(model, cell) returns {name: ckpt dict} for every arm of one primary checkpoint (manifests/fork/dev_blocks_v1.json:
gptq_w4_d1 / awq_w4 = calibration c1, on q4 / q8): 14 restoration arms + 2 controls + 5 residual doses. Fork tasks use
them as q_ckpt (or b_ckpt); the fork scheduling itself belongs to the main session (make_tasks_fork_dev.py).

--smoke --write queues only the smoke set (priority -7): q4 gptq_w4_d1 resid a0 / a1 build+serve+canary (no episodes),
q4 restore late and resid a0.5 one BF16-harness run on the 20 determinism tasks, q8 awq_w4 restore rand_attn_s1
build+serve+canary. Everything else prints only.

--w3 [--write]: W50 damage-regime set, 17 arms x q4/q8 on GPTQ-W3 c1, blocks q3-q5 (priority -8).

--tel [f123 f456] [--write]: W53 telecom set, 9 arms on q8 AWQ-W4 c1, telecom dev blocks (priority -9).

usage: python scripts/a6000/make_tasks_perturb.py [--smoke | --w3 | --tel [groups]] [--write]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
CK = {"gptq_w4_d1": ("gptq", 4), "awq_w4": ("awq", 4), "gptq_w3": ("gptq", 3)}  # all calibration draw c1
# W50 damage regime: GPTQ-W3 (c1) on the stress blocks q3-q5, which have both W3 Q runs (a6k2_<m>_gptq_w3_<blk>) and
# BF16 pairs (a6k2_<m>_bfpair_<blk>) on the same nonces for q4 and q8.
W3_BLOCKS = {"q3": "4c8e1a7f", "q4": "b9d2e605", "q5": "e1a47c3d"}
W3_ARMS = (["restore_" + a for a in ("early", "middle", "late", "attn", "mlp")]
           + [f"restore_rand_{b}_s{s}" for b in ("third", "attn", "mlp") for s in (1, 2, 3)]
           + [f"resid_a{a:g}" for a in (0.25, 0.5, 2.0)])
DET = "manifests/a6000/det_tasks.json"
ALPHAS = (0.0, 0.25, 0.5, 1.0, 2.0)


def base(model: str, cell: str) -> dict:
    kind, wbits = CK[cell]
    return {"kind": kind, "wbits": wbits, "calib": f"manifests/a6k2/{model}/calib_fp_traj_c1.json"}


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


def w3_tasks() -> tuple[list[dict], list[str]]:
    """17 arms x {q4, q8} on the GPTQ-W3 c1 base, runs on q3-q5; problems = blocks lacking a finished Q or BF16 run."""
    tasks, problems = [], []
    for m in ("q4", "q8"):
        blocks = []
        for b, nonce in W3_BLOCKS.items():
            ok = True
            for rid in (f"a6k2_{m}_gptq_w3_{b}", f"a6k2_{m}_bfpair_{b}"):
                for d in ("retail", "airline"):
                    st = ROOT / "runs" / rid / d / "status.json"
                    env = ROOT / "runs" / rid / d / "environment.json"
                    if not st.exists() or json.load(open(st)).get("status") != "completed":
                        problems.append(f"{rid}/{d} not completed")
                        ok = False
                    elif json.load(open(env)).get("prompt_nonce") != nonce:
                        problems.append(f"{rid}/{d} nonce != {nonce}")
                        ok = False
            if ok:
                blocks.append((b, nonce))
        sp = specs(m, "gptq_w3")
        for arm in W3_ARMS:
            if not blocks:
                continue
            tasks.append({"id": f"pert_{m}_gptq_w3_{arm}_q345", "kind": "eval", "model": m, "arm": arm, "ckpt": sp[arm],
                          "runs": [{"run_id": f"a6k2_pert_{m}_gptq_w3_{arm}_{b}", "task_file": "manifests/eval_tasks_v0.json",
                                    "nonce": n} for b, n in blocks],
                          "priority": -8, "deps": [f"a6k2_{m}_calib_c1"],
                          "note": "W50: damage-regime (GPTQ-W3 c1) restoration / residual-dose arms on stress blocks q3-q5, "
                                  "paired with a6k2_<m>_gptq_w3_<blk> and a6k2_<m>_bfpair_<blk>; PERTURBATION_PROTOCOL.md"})
    return tasks, problems


TEL_ARMS = (["restore_" + a for a in ("early", "middle", "late", "attn", "mlp")]
            + [f"restore_rand_{b}_s1" for b in ("third", "attn", "mlp")] + ["resid_a0.5"])
TEL_GROUPS = {"f123": ("f01", "f02", "f03"), "f456": ("f04", "f05", "f06")}


def tel_tasks(groups=("f123", "f456")) -> tuple[list[dict], list[str]]:
    """W53: q8 AWQ-W4 (c1, cached base) restoration arms on telecom dev blocks, paired with a6k2_q8_tel_awq_w4_<blk> and
    a6k2_q8_tel_bfpair_<blk>; same task_file / domain / naming as the *_tel_* dev tasks (make_tasks_fork_dev2.py)."""
    nonce = json.load(open(ROOT / "manifests/fork/dev_blocks_v1.json"))["new_blocks"]
    tasks, problems = [], []
    sp = specs("q8", "awq_w4")
    for gname in groups:
        blocks = []
        for b in TEL_GROUPS[gname]:
            ok = True
            for rid in (f"a6k2_q8_tel_awq_w4_{b}", f"a6k2_q8_tel_bfpair_{b}"):
                st, env = ROOT / "runs" / rid / "telecom/status.json", ROOT / "runs" / rid / "telecom/environment.json"
                if not st.exists() or json.load(open(st)).get("status") != "completed":
                    problems.append(f"{rid}/telecom not completed")
                    ok = False
                elif json.load(open(env)).get("prompt_nonce") != nonce[b]:
                    problems.append(f"{rid}/telecom nonce != {nonce[b]}")
                    ok = False
            if ok:
                blocks.append(b)
        if not blocks:
            continue
        for arm in TEL_ARMS:
            tasks.append({"id": f"pert_q8_tel_awq_w4_{arm}_{gname}", "kind": "eval", "model": "q8", "domains": ["telecom"],
                          "arm": arm, "ckpt": sp[arm],
                          "runs": [{"run_id": f"a6k2_pert_q8_tel_awq_w4_{arm}_{b}", "task_file": "manifests/telecom/dev_v1.json",
                                    "nonce": nonce[b]} for b in blocks],
                          "priority": -9, "deps": ["a6k2_q8_calib_c1"],
                          "note": "W53: telecom W4-damage restoration arms (q8 AWQ-W4 c1) on telecom dev blocks (holdout untouched); "
                                  "PERTURBATION_PROTOCOL.md"})
    return tasks, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--w3", action="store_true", help="W50 damage-regime arms (GPTQ-W3 base, blocks q3-q5)")
    ap.add_argument("--tel", nargs="*", default=None, help="W53 telecom arms; groups f123 / f456 (default both)")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if a.tel is not None:
        ts, problems = tel_tasks(tuple(a.tel) or ("f123", "f456"))
        for p in problems:
            print("MISSING", p)
        for t in ts:
            print(t["id"], [r["run_id"] for r in t["runs"]])
        if a.write:
            for t in ts:
                if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
                    json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
                    print("queued", t["id"])
        else:
            print(f"{len(ts)} telecom tasks (dry run)")
        return
    if a.w3:
        ts, problems = w3_tasks()
        for p in problems:
            print("MISSING", p)
        for t in ts:
            print(t["id"], len(t["runs"]), "runs", t["ckpt"].get("arm", t["ckpt"].get("alpha")))
        if a.write:
            for t in ts:
                if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
                    json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
                    print("queued", t["id"])
        else:
            print(f"{len(ts)} W3 tasks (dry run)")
        return
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
