"""Checkpoint specs for P2 line 3 (restoration arms, residual dose) and the smoke tasks that prove the kinds build and serve.

specs(model, cell) returns {name: ckpt dict} for every arm of one primary checkpoint (manifests/fork/dev_blocks_v1.json:
gptq_w4_d1 / awq_w4 = calibration c1, on q4 / q8): 14 restoration arms + 2 controls + 5 residual doses. Fork tasks use
them as q_ckpt (or b_ckpt); the fork scheduling itself belongs to the main session (make_tasks_fork_dev.py).

--smoke --write queues only the smoke set (priority -7): q4 gptq_w4_d1 resid a0 / a1 build+serve+canary (no episodes),
q4 restore late and resid a0.5 one BF16-harness run on the 20 determinism tasks, q8 awq_w4 restore rand_attn_s1
build+serve+canary. Everything else prints only.

--w3 [--write]: W50 damage-regime set, 17 arms x q4/q8 on GPTQ-W3 c1, blocks q3-q5 (priority -8).

--tel [f123 f456] [--write]: W53 telecom set, 9 arms on q8 AWQ-W4 c1, telecom dev blocks (priority -9).

--rtn3 [--write]: W60 primary damage regime, 17 arms x q4/q8 on RTN-W3, blocks q3-q5 (priority -16).
--awq3 [--write]: W64 AWQ-W3 d1 closed-loop baselines, q4/q8 on q3-q5 (priority -12).
--recal [--write]: W54 restore_recal arms (8 per model) on the W3 cell, blocks q3-q5 (priority -14).

usage: python scripts/a6000/make_tasks_perturb.py [--smoke | --w3 | --rtn3 | --tel [groups] | --recal] [--write]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
CK = {"gptq_w4_d1": ("gptq", 4), "awq_w4": ("awq", 4), "gptq_w3": ("gptq", 3),  # calibration draw c1
      "rtn_w3": ("rtn", 3)}  # W60: primary damage regime; RTN has no calibration and no sequential compensation
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
    if kind == "rtn":  # same spec as the a6k2_<m>_rtn_w3 Q runs (cloq.compress rtn)
        return {"kind": "rtn", "wbits": wbits}
    return {"kind": kind, "wbits": wbits, "calib": f"manifests/a6k2/{model}/calib_fp_traj_c1.json"}


def specs(model: str, cell: str) -> dict[str, dict]:
    b = base(model, cell)
    out = {}
    for p in sorted((ROOT / "manifests/perturb/restore_v1" / model).glob("*.json")):
        out[f"restore_{p.stem}"] = {"kind": "restore", "base": b, "arm": p.stem,
                                    "manifest": str(p.relative_to(ROOT))}
    for a in ALPHAS:
        out[f"resid_a{a:g}"] = {"kind": "resid", "base": b, "alpha": a}
    if b["kind"] in ("gptq", "awq"):  # W54: rebuilt mixed precision (kept modules BF16, the rest re-calibrated)
        for p in sorted((ROOT / "manifests/perturb/restore_v1" / model).glob("*.json")):
            out[f"restore_recal_{p.stem}"] = {"kind": "restore_recal", "base": b, "arm": p.stem,
                                              "manifest": str(p.relative_to(ROOT))}
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


def w3_tasks(cell: str = "gptq_w3", priority: float = -8) -> tuple[list[dict], list[str]]:
    """17 arms x {q4, q8} on the GPTQ-W3 c1 base, runs on q3-q5; problems = blocks lacking a finished Q or BF16 run."""
    tasks, problems = [], []
    for m in ("q4", "q8"):
        blocks = []
        for b, nonce in W3_BLOCKS.items():
            ok = True
            for rid in (f"a6k2_{m}_{cell}_{b}", f"a6k2_{m}_bfpair_{b}"):
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
        sp = specs(m, cell)
        for arm in W3_ARMS:
            if not blocks:
                continue
            tasks.append({"id": f"pert_{m}_{cell}_{arm}_q345", "kind": "eval", "model": m, "arm": arm, "ckpt": sp[arm],
                          "runs": [{"run_id": f"a6k2_pert_{m}_{cell}_{arm}_{b}", "task_file": "manifests/eval_tasks_v0.json",
                                    "nonce": n} for b, n in blocks],
                          "priority": priority, "deps": [] if CK[cell][0] == "rtn" else [f"a6k2_{m}_calib_c1"],
                          "note": f"W50/W60: damage-regime ({cell}) restoration / residual-dose arms on stress blocks q3-q5, "
                                  f"paired with a6k2_<m>_{cell}_<blk> and a6k2_<m>_bfpair_<blk>; PERTURBATION_PROTOCOL.md"})
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


def awq3_baseline_tasks() -> list[dict]:
    """W64: AWQ-W3 d1 (calibration c1) closed-loop baselines on q3-q5 (method coverage; paired with bfpair_q3..q5). No
    restoration matrix. Same spec style as the existing awq cells, wbits 3; same layout as a6k2_<m>_gptq_w3_qx."""
    return [{"id": f"a6k2_{m}_awq_w3_qx", "kind": "eval", "model": m, "arm": "awq",
             "ckpt": {"kind": "awq", "wbits": 3, "calib": f"manifests/a6k2/{m}/calib_fp_traj_c1.json"},
             "runs": [{"run_id": f"a6k2_{m}_awq_w3_{b}", "task_file": "manifests/eval_tasks_v0.json", "nonce": n}
                      for b, n in W3_BLOCKS.items()],
             "priority": -12, "deps": [f"a6k2_{m}_calib_c1"],
             "note": "W64: AWQ-W3 d1 closed-loop baseline (method coverage, storage-matched comparison for restoration)"}
            for m in ("q4", "q8")]


RECAL_ARMS = ["restore_recal_" + a for a in ("early", "middle", "late", "attn", "mlp", "rand_third_s1", "rand_attn_s1",
                                             "rand_mlp_s1")]


def recal_tasks() -> tuple[list[dict], list[str]]:
    """W54: restore_recal arms on the W3 damage cell (same blocks/pairing as w3_tasks), priority -14."""
    base_tasks, problems = w3_tasks()
    blocks = {t["model"]: [(r["run_id"].rsplit("_", 1)[1], r["nonce"]) for r in t["runs"]] for t in base_tasks}
    tasks = []
    for m, bl in sorted(blocks.items()):
        sp = specs(m, "gptq_w3")
        for arm in RECAL_ARMS:
            tasks.append({"id": f"pert_{m}_gptq_w3_{arm}_q345", "kind": "eval", "model": m, "arm": arm, "ckpt": sp[arm],
                          "runs": [{"run_id": f"a6k2_pert_{m}_gptq_w3_{arm}_{b}", "task_file": "manifests/eval_tasks_v0.json",
                                    "nonce": n} for b, n in bl],
                          "priority": -14, "deps": [f"a6k2_{m}_calib_c1"],
                          "note": "W54: restore_recal (kept modules BF16, remaining modules re-calibrated sequentially, "
                                  "GPTQ-W3 c1) on q3-q5; compare with the plain restore arm of the same name"})
    return tasks, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--w3", action="store_true", help="W50 damage-regime arms (GPTQ-W3 base, blocks q3-q5)")
    ap.add_argument("--rtn3", action="store_true", help="W60 primary damage regime: RTN-W3 base, blocks q3-q5, priority -16")
    ap.add_argument("--tel", nargs="*", default=None, help="W53 telecom arms; groups f123 / f456 (default both)")
    ap.add_argument("--recal", action="store_true", help="W54 restore_recal arms on the W3 cell")
    ap.add_argument("--awq3", action="store_true", help="W64 AWQ-W3 d1 baselines on q3-q5 (priority -12)")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if a.awq3:
        for t in awq3_baseline_tasks():
            print(t["id"], [r["run_id"] for r in t["runs"]])
            if a.write and not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
                json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
                print("queued", t["id"])
        return
    if a.recal:
        ts, problems = recal_tasks()
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
            print(f"{len(ts)} restore_recal tasks (dry run)")
        return
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
    if a.w3 or a.rtn3:
        ts, problems = w3_tasks("rtn_w3", -16) if a.rtn3 else w3_tasks()
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
