"""W100n: google/gemma-4-12B-it (g12) second-family gate (frozen manifests + queue tasks). Precedent: make_tasks_m24.py.

Manifests (written once, refuse to overwrite; ids only, no model outcome or divergence information; written before any
g12 run):
  manifests/a6k2/g12/gate_tau2_v1.json   tau2 acceptance sample: per domain, the retail/airline tasks NOT in the 85-task
                                         panel (manifests/eval_tasks_v0.json), sorted by sha256('cloq-g12-gate-v1:' +
                                         domain + ':' + id); first 10 per domain (20 tasks).
  manifests/bfcl/bfcl_mt_g12_v1.json     BFCL acceptance sample: per category, bfcl_mt_v1 ids minus its dev ids minus the
                                         200 nmp_v1 panel ids, sorted by sha256('cloq-ext-g12-v1:' + id); gate_g12 = first 5.
Gate nonce: sha256('cloq-g12-gate-v1|nonce')[:8].

gate    BF16 and RTN-W4 evals on both gate samples (1 GPU each; 12B BF16 fits one A6000), four fork gates on 2 GPUs (B and
        Q one GPU each, as q8/q14): tau2 gate (BB/QQ no-op, replay, isolation, budget), tau2 gate_same (same-checkpoint
        negative control), BFCL gate, BFCL gate_same; plus GPTQ-W4 d1 readiness: the BF16 calibration-split run,
        calib_fp_traj c1, and a GPTQ-W4 d1 eval on the tau2 gate sample (build + serve check; not an admission criterion).
Priority -21 (ascending queue order: behind pert -22 / pivot -23, ahead of -19 backfill). Never overwrites an existing id.

usage: python3 scripts/a6000/make_tasks_g12.py {manifests|gate} [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
TAU_GATE = "manifests/a6k2/g12/gate_tau2_v1.json"
BFCL = "manifests/bfcl/bfcl_mt_g12_v1.json"
CAL = "manifests/a6k2/g12/calib_fp_traj_c1.json"
DOMS = ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"]
NG = hashlib.sha256(b"cloq-g12-gate-v1|nonce").hexdigest()[:8]
CK = {"bf16": {"kind": "bf16"}, "rtn_w4": {"kind": "rtn", "wbits": 4}, "gptq_w4_d1": {"kind": "gptq", "wbits": 4, "calib": CAL}}
ARM = {"bf16": "bf16", "rtn_w4": "rtn", "gptq_w4_d1": "gptq"}
NOTE = "W100n g12 (gemma-4-12B-it, text-only, gemma4 parser, thinking off) second-family gate"
OUT = "analysis/fork/g12_gate"


def write_once(path: Path, obj: dict) -> None:
    if path.exists():
        print(f"{path} exists (frozen); kept")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1) + "\n")
    tmp.replace(path)
    print("wrote", path)


def manifests() -> None:
    split = json.load(open(ROOT / "manifests/task_split_v0.json"))["domains"]
    panel = json.load(open(ROOT / "manifests/eval_tasks_v0.json"))
    salt = "cloq-g12-gate-v1"
    tau = {"manifest": "gate_tau2_v1", "model": "g12", "created": time.strftime("%FT%TZ", time.gmtime()),
           "rule": f"per domain: all task ids (task_split_v0 characterization) minus the 85-task panel (eval_tasks_v0), "
                   f"sorted by sha256('{salt}:' + domain + ':' + id); first 10. No model outcome used.",
           "salt": salt, "panel_sha256": hashlib.sha256((ROOT / "manifests/eval_tasks_v0.json").read_bytes()).hexdigest(),
           "frozen_before_model_runs": True}
    for d in ("retail", "airline"):
        ids = [c["task_id"] for c in split[d]["characterization"]]
        pool = [i for i in ids if i not in set(panel[d])]
        order = sorted(pool, key=lambda i: hashlib.sha256(f"{salt}:{d}:{i}".encode()).hexdigest())
        tau[d] = order[:10]
        tau.setdefault("pool_size", {})[d] = len(pool)
        assert not set(tau[d]) & set(panel[d]) and len(tau[d]) == 10
    write_once(ROOT / TAU_GATE, tau)
    src = ROOT / "manifests/bfcl/bfcl_mt_v1.json"
    s = json.load(open(src))
    nmp_p = ROOT / "manifests/fork/newmethod_panel_v1.json"
    nmp = json.load(open(nmp_p))["categories"]
    bsalt = "cloq-ext-g12-v1"
    man = {k: v for k, v in s.items() if k not in ("manifest", "selection", "categories", "frozen_before_model_runs")}
    man.update(manifest="bfcl_mt_g12_v1", parent_manifest="bfcl_mt_v1", parent_manifest_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
               excluded_panel="manifests/fork/newmethod_panel_v1.json (nmp_v1, the formal 200-item BFCL panel)",
               excluded_panel_sha256=hashlib.sha256(nmp_p.read_bytes()).hexdigest(),
               selection={"rule": f"per category, bfcl_mt_v1 ids minus its dev ids minus the nmp_v1 panel ids, sorted by "
                                  f"sha256('{bsalt}:' + id); gate_g12 = first 5 (disjoint from the formal panel). "
                                  "No model outcome or divergence used.", "salt": bsalt},
               created=time.strftime("%FT%TZ", time.gmtime()), categories={})
    for cat, c in s["categories"].items():
        panel_ids = set(nmp[cat]["nmp_v1"])
        pool = [i for i in sorted(set(c["eval"]) | set(c["dev"])) if i not in set(c["dev"]) and i not in panel_ids]
        order = sorted(pool, key=lambda i: hashlib.sha256(f"{bsalt}:{i}".encode()).hexdigest())
        man["categories"][cat] = {"test_category": c["test_category"], "n_total": c["n_total"], "n_pool": len(pool), "gate_g12": order[:5]}
        assert not set(order[:5]) & panel_ids and len(order[:5]) == 5
    man["frozen_before_model_runs"] = True
    write_once(ROOT / BFCL, man)


def ev_tau(arm: str, runs: list[dict], prio: float, deps: list[str], tid: str) -> dict:
    return {"id": tid, "kind": "eval", "model": "g12", "arm": ARM[arm], "ckpt": CK[arm], "gpus": 1, "runs": runs,
            "priority": prio, "deps": deps, "note": NOTE}


def ev_bfcl(arm: str, subset: str, prio: float, deps: list[str]) -> dict:
    rid = f"ext_g12_{arm}_bfcl_{subset}"
    return {"id": rid, "kind": "eval", "env": "bfcl", "model": "g12", "arm": ARM[arm], "ckpt": CK[arm], "domains": DOMS,
            "gpus": 1, "priority": prio, "deps": deps, "runs": [{"run_id": rid, "task_file": BFCL, "subset": subset}], "note": NOTE}


def fork(tid: str, b: str, q: str, spec: dict, prio: float, deps: list[str], env: str | None = None) -> dict:
    t = {"id": tid, "kind": "fork", "model": "g12", "gpus": 2, "priority": prio, "deps": deps,
         "B": {"ckpt": CK[b]}, "Q": {"ckpt": CK[q]}, "fork": spec, "note": NOTE}
    if b != q:
        t["expect_distinct_numerics"] = True
    return {**({"env": env} if env else {}), **t}


def gate(prio: float) -> list[dict]:
    blk = {a: f"a6k2_g12_{a}_g1" for a in ("bf16", "rtn_w4", "gptq_w4_d1")}
    ts = [ev_tau(a, [{"run_id": blk[a], "task_file": TAU_GATE, "nonce": NG}], prio, [], f"a6k2_g12_{a}_gate") for a in ("bf16", "rtn_w4")]
    ts += [ev_bfcl(a, "gate_g12", prio, []) for a in ("bf16", "rtn_w4")]
    tb, tq, bb, bq = ts[0]["id"], ts[1]["id"], ts[2]["id"], ts[3]["id"]
    ts.append(fork("fork_gate_g12_rtn_w4", "bf16", "rtn_w4", {
        "mode": "gate", "q_blocks": [[blk["rtn_w4"], d] for d in ("retail", "airline")],
        "b_blocks": [[blk["bf16"], d] for d in ("retail", "airline")], "search_tasks_per_block": 10, "n_states": 8, "n_iso": 4,
        "n_bb_noop": 4, "idcheck_n": 16, "concurrency": 8, "out": f"{OUT}/tau2_rtn_w4"}, prio, [tb, tq]))
    ts.append(fork("fork_gate_same_g12_rtn_w4", "rtn_w4", "rtn_w4", {
        "mode": "gate_same", "q_blocks": [[blk["rtn_w4"], d] for d in ("retail", "airline")], "n_per_block": 3, "idcheck_n": 8,
        "concurrency": 8, "out": f"{OUT}/tau2_same_rtn_w4"}, prio, [tq]))
    ts.append(fork("fork_ext_gate_g12_rtn_w4_bfcl", "bf16", "rtn_w4", {
        "mode": "gate", "q_blocks": [f"{bq}:{d}" for d in DOMS], "b_blocks": [f"{bb}:{d}" for d in DOMS], "n_items": 3, "n_bb": 4,
        "max_states": 12, "n_iso": 4, "concurrency": 8, "out": f"{OUT}/bfcl_rtn_w4"}, prio, [bb, bq], env="bfcl"))
    ts.append(fork("fork_ext_gate_same_g12_rtn_w4_bfcl", "rtn_w4", "rtn_w4", {
        "mode": "gate_same", "q_blocks": [f"{bq}:{d}" for d in DOMS], "n_items": 3, "n_same": 4, "concurrency": 8,
        "out": f"{OUT}/bfcl_same_rtn_w4"}, prio, [bq], env="bfcl"))
    # GPTQ-W4 d1 readiness (as l8/q14/m24): BF16 calibration-split run -> calib_fp_traj c1 -> one GPTQ-W4 d1 eval
    ts.append({"id": "a6k2_g12_bf16_cal", "kind": "eval", "model": "g12", "arm": "bf16", "ckpt": CK["bf16"], "gpus": 1,
               "runs": [{"run_id": "a6k2_g12_bf16_cal", "task_file": "manifests/cal_tasks_v0.json", "nonce": None}],
               "priority": prio, "deps": [], "note": NOTE + ": BF16 calibration-split run for GPTQ d1 (as a6k2_q14_bf16_cal)"})
    ts.append({"id": "a6k2_g12_calib_c1", "kind": "calib", "model": "g12", "arm": "fp_traj", "draw": "c1", "fp_run": "a6k2_g12_bf16_cal",
               "out": CAL, "priority": prio, "deps": ["a6k2_g12_bf16_cal"], "note": NOTE})
    ts.append(ev_tau("gptq_w4_d1", [{"run_id": blk["gptq_w4_d1"], "task_file": TAU_GATE, "nonce": NG}], prio, ["a6k2_g12_calib_c1"],
                     "a6k2_g12_gptq_w4_d1_gate"))
    ts[-1]["note"] = NOTE + ": GPTQ-W4 d1 build + serve readiness on the tau2 gate sample (descriptive; not an admission criterion)"
    return ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["manifests", "gate"])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--priority", type=float, default=-21)
    a = ap.parse_args()
    if a.mode == "manifests":
        manifests()
        return
    ts = gate(a.priority)
    for t in ts:
        clash = [s for s in ("todo", "running", "done", "failed", "deferred") if (Q / s / f"{t['id']}.json").exists()]
        print(t["id"], t.get("gpus"), t["priority"], t["deps"], "EXISTS " + str(clash) if clash else "")
        if a.write and not clash:
            tmp = Q / "todo" / f".{t['id']}.json.tmp"
            tmp.write_text(json.dumps(t, indent=1))
            tmp.replace(Q / "todo" / f"{t['id']}.json")
    print(f"{len(ts)} tasks" + ("" if a.write else " (dry run)"))


if __name__ == "__main__":
    main()
