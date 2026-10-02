"""W99p/W99q: Mistral-Small-3.2-24B (m24) second-family gate and formal panel (frozen manifests + queue tasks).

Manifests (written once, refuse to overwrite; ids only, no model outcome or divergence information):
  manifests/a6k2/m24/gate_tau2_v1.json   tau2 acceptance sample: per domain, the retail/airline tasks NOT in the 85-task
                                         panel (manifests/eval_tasks_v0.json), sorted by sha256('cloq-m24-gate-v1:' +
                                         domain + ':' + id); first 10 per domain (20 tasks).
  manifests/bfcl/bfcl_mt_m24_v1.json     BFCL acceptance sample: per category, bfcl_mt_v1 ids minus its dev ids minus the
                                         200 nmp_v1 panel ids, sorted by sha256('cloq-ext-m24-v1:' + id); gate_m24 = first 5.
Gate nonce: sha256('cloq-m24-gate-v1|nonce')[:8].

gate    BF16 and RTN-W4 evals on both gate samples (2 GPUs each, TP=2), four fork gates on 4 GPUs (B and Q each TP=2 on
        one NVLink pair, gpus_per_role 2; noderunner W99p): tau2 gate (BB/QQ no-op, replay, isolation), tau2 gate_same
        (same-checkpoint negative control), BFCL gate, BFCL gate_same; plus the BF16 calibration-split run and
        calib_fp_traj c1 for GPTQ-W4 (as l8/q14).
bfpair  formal stage 1, only after the gate passes (docs/insights/NEWMETHOD_PANEL_PROTOCOL.md §10): BF16 a6k2_m24_bfpair_f01..f06
        and the BF16 / RTN-W4 BFCL runs on the 200 nmp_v1 items.
panel   formal stage 2, after `make_newmethod_panel.py build --model m24` + the dated sha amendment: one cell's (rtn_w4
        first, then gptq_w4_d1) gates, f01-f03 bank_u panel tasks and token scores; --bfcl adds the BFCL forks (only if
        BF16 >= 10% on nmp_v1).
Priority -26 (ascending queue order). Never overwrites an existing id.

usage: python3 scripts/a6000/make_tasks_m24.py {manifests|gate|bfpair|panel} [--cell rtn_w4] [--bfcl] [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
TAU_GATE = "manifests/a6k2/m24/gate_tau2_v1.json"
BFCL = "manifests/bfcl/bfcl_mt_m24_v1.json"
CAL = "manifests/a6k2/m24/calib_fp_traj_c1.json"
DOMS = ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"]
NG = hashlib.sha256(b"cloq-m24-gate-v1|nonce").hexdigest()[:8]
CK = {"bf16": {"kind": "bf16"}, "rtn_w4": {"kind": "rtn", "wbits": 4}, "gptq_w4_d1": {"kind": "gptq", "wbits": 4, "calib": CAL}}
ARM = {"bf16": "bf16", "rtn_w4": "rtn", "gptq_w4_d1": "gptq"}
NOTE = "W99p m24 (Mistral-Small-3.2-24B, text-only, mistral tokenizer/parser) second-family check"


def write_once(path: Path, obj: dict) -> None:
    if path.exists():
        print(f"{path} exists (frozen); kept")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1) + "\n")
    print("wrote", path)


def manifests() -> None:
    split = json.load(open(ROOT / "manifests/task_split_v0.json"))["domains"]
    panel = json.load(open(ROOT / "manifests/eval_tasks_v0.json"))
    salt = "cloq-m24-gate-v1"
    tau = {"manifest": "gate_tau2_v1", "model": "m24", "created": time.strftime("%FT%TZ", time.gmtime()),
           "rule": f"per domain: all task ids (task_split_v0 characterization) minus the 85-task panel (eval_tasks_v0), "
                   f"sorted by sha256('{salt}:' + domain + ':' + id); first 10. No model outcome used.",
           "salt": salt, "panel_sha256": hashlib.sha256((ROOT / "manifests/eval_tasks_v0.json").read_bytes()).hexdigest()}
    for d in ("retail", "airline"):
        ids = [c["task_id"] for c in split[d]["characterization"]]
        pool = [i for i in ids if i not in set(panel[d])]
        order = sorted(pool, key=lambda i: hashlib.sha256(f"{salt}:{d}:{i}".encode()).hexdigest())
        tau[d] = order[:10]
        tau.setdefault("pool_size", {})[d] = len(pool)
        assert not set(tau[d]) & set(panel[d])
    write_once(ROOT / TAU_GATE, tau)
    src = ROOT / "manifests/bfcl/bfcl_mt_v1.json"
    s = json.load(open(src))
    nmp_p = ROOT / "manifests/fork/newmethod_panel_v1.json"
    nmp = json.load(open(nmp_p))["categories"]
    bsalt = "cloq-ext-m24-v1"
    man = {k: v for k, v in s.items() if k not in ("manifest", "selection", "categories", "frozen_before_model_runs")}
    man.update(manifest="bfcl_mt_m24_v1", parent_manifest="bfcl_mt_v1", parent_manifest_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
               excluded_panel="manifests/fork/newmethod_panel_v1.json (nmp_v1, the formal 200-item BFCL panel)",
               excluded_panel_sha256=hashlib.sha256(nmp_p.read_bytes()).hexdigest(),
               selection={"rule": f"per category, bfcl_mt_v1 ids minus its dev ids minus the nmp_v1 panel ids, sorted by "
                                  f"sha256('{bsalt}:' + id); gate_m24 = first 5 (disjoint from the formal panel). "
                                  "No model outcome or divergence used.", "salt": bsalt},
               created=time.strftime("%FT%TZ", time.gmtime()), categories={})
    for cat, c in s["categories"].items():
        panel = set(nmp[cat]["nmp_v1"])
        pool = [i for i in sorted(set(c["eval"]) | set(c["dev"])) if i not in set(c["dev"]) and i not in panel]
        order = sorted(pool, key=lambda i: hashlib.sha256(f"{bsalt}:{i}".encode()).hexdigest())
        man["categories"][cat] = {"test_category": c["test_category"], "n_total": c["n_total"], "n_pool": len(pool), "gate_m24": order[:5]}
        assert not set(order[:5]) & panel and len(order[:5]) == 5
    man["frozen_before_model_runs"] = True
    write_once(ROOT / BFCL, man)


def ev_tau(arm: str, runs: list[dict], prio: float, deps: list[str], tid: str) -> dict:
    return {"id": tid, "kind": "eval", "model": "m24", "arm": ARM[arm], "ckpt": CK[arm], "gpus": 2, "runs": runs,
            "priority": prio, "deps": deps, "note": NOTE}


def ev_bfcl(arm: str, subset: str, prio: float, deps: list[str]) -> dict:
    rid = f"ext_m24_{arm}_bfcl_{subset}"
    return {"id": rid, "kind": "eval", "env": "bfcl", "model": "m24", "arm": ARM[arm], "ckpt": CK[arm], "domains": DOMS,
            "gpus": 2, "priority": prio, "deps": deps, "runs": [{"run_id": rid, "task_file": BFCL, "subset": subset}], "note": NOTE}


def fork(tid: str, b: str, q: str, spec: dict, prio: float, deps: list[str], env: str | None = None) -> dict:
    t = {"id": tid, "kind": "fork", "model": "m24", "gpus": 4, "gpus_per_role": 2, "priority": prio, "deps": deps,
         "B": {"ckpt": CK[b]}, "Q": {"ckpt": CK[q]}, "fork": spec, "note": NOTE}
    if b != q:
        t["expect_distinct_numerics"] = True
    return {**({"env": env} if env else {}), **t}


def gate(prio: float) -> list[dict]:
    blk = {a: f"a6k2_m24_{a}_g1" for a in ("bf16", "rtn_w4")}
    ts = [ev_tau(a, [{"run_id": blk[a], "task_file": TAU_GATE, "nonce": NG}], prio, [], f"a6k2_m24_{a}_gate") for a in ("bf16", "rtn_w4")]
    ts += [ev_bfcl(a, "gate_m24", prio, []) for a in ("bf16", "rtn_w4")]
    tb, tq, bb, bq = ts[0]["id"], ts[1]["id"], ts[2]["id"], ts[3]["id"]
    ts.append(fork("fork_gate_m24_rtn_w4", "bf16", "rtn_w4", {
        "mode": "gate", "q_blocks": [[blk["rtn_w4"], d] for d in ("retail", "airline")],
        "b_blocks": [[blk["bf16"], d] for d in ("retail", "airline")], "search_tasks_per_block": 10, "n_states": 8, "n_iso": 4,
        "n_bb_noop": 4, "idcheck_n": 16, "concurrency": 8, "out": "analysis/fork/m24_gate/tau2_rtn_w4"}, prio, [tb, tq]))
    ts.append(fork("fork_gate_same_m24_rtn_w4", "rtn_w4", "rtn_w4", {
        "mode": "gate_same", "q_blocks": [[blk["rtn_w4"], d] for d in ("retail", "airline")], "n_per_block": 3, "idcheck_n": 8,
        "concurrency": 8, "out": "analysis/fork/m24_gate/tau2_same_rtn_w4"}, prio, [tq]))
    ts.append(fork("fork_ext_gate_m24_rtn_w4_bfcl", "bf16", "rtn_w4", {
        "mode": "gate", "q_blocks": [f"{bq}:{d}" for d in DOMS], "b_blocks": [f"{bb}:{d}" for d in DOMS], "n_items": 3, "n_bb": 4,
        "max_states": 12, "n_iso": 4, "concurrency": 8, "out": "analysis/fork/m24_gate/bfcl_rtn_w4"}, prio, [bb, bq], env="bfcl"))
    ts.append(fork("fork_ext_gate_same_m24_rtn_w4_bfcl", "rtn_w4", "rtn_w4", {
        "mode": "gate_same", "q_blocks": [f"{bq}:{d}" for d in DOMS], "n_items": 3, "n_same": 4, "concurrency": 8,
        "out": "analysis/fork/m24_gate/bfcl_same_rtn_w4"}, prio, [bq], env="bfcl"))
    # GPTQ-W4 d1 readiness (as l8/q14): BF16 calibration-split run -> calib_fp_traj c1; claimed after the gate evals
    ts.append({"id": "a6k2_m24_bf16_cal", "kind": "eval", "model": "m24", "arm": "bf16", "ckpt": CK["bf16"], "gpus": 2,
               "runs": [{"run_id": "a6k2_m24_bf16_cal", "task_file": "manifests/cal_tasks_v0.json", "nonce": None}],
               "priority": prio + 1, "deps": [], "note": NOTE + ": BF16 calibration-split run for GPTQ d1 (as a6k2_q14_bf16_cal)"})
    ts.append({"id": "a6k2_m24_calib_c1", "kind": "calib", "model": "m24", "arm": "fp_traj", "draw": "c1", "fp_run": "a6k2_m24_bf16_cal",
               "out": CAL, "priority": prio + 1, "deps": ["a6k2_m24_bf16_cal"], "note": NOTE})
    return ts


def bfpair(prio: float) -> list[dict]:
    """Formal stage 1 (after the gate; NEWMETHOD_PANEL_PROTOCOL §10): BF16 closed-loop runs a6k2_m24_bfpair_f01..f06 on
    the 85-task panel (eval_tasks_v0) with the main nonce blocks, 2 blocks per task; the BF16 BFCL run on the 200 nmp_v1
    items (floor check: forks only if BF16 >= 10%); the RTN-W4 Q closed-loop BFCL run."""
    blocks = json.load(open(ROOT / "manifests/fork/dev_blocks_v1.json"))["new_blocks"]
    fb = [(k, blocks[k]) for k in ("f01", "f02", "f03", "f04", "f05", "f06")]
    ts = [ev_tau("bf16", [{"run_id": f"a6k2_m24_bfpair_{k}", "task_file": "manifests/eval_tasks_v0.json", "nonce": n} for k, n in fb[i:i + 2]],
                 prio, [], f"a6k2_m24_bfpair_{fb[i][0]}_{fb[i + 1][0]}") for i in range(0, 6, 2)]
    for a in ("bf16", "rtn_w4"):
        rid = f"ext_m24_{a}_bfcl_nmp1"
        ts.append({"id": rid, "kind": "eval", "env": "bfcl", "model": "m24", "arm": ARM[a], "ckpt": CK[a], "domains": DOMS, "gpus": 2,
                   "priority": prio, "deps": [], "runs": [{"run_id": rid, "task_file": "manifests/fork/newmethod_panel_v1.json", "subset": "nmp_v1"}],
                   "note": NOTE + ": NEWMETHOD_PANEL_PROTOCOL panel B closed-loop run (same 200 ids as newmethod_panel_v1_m24)"})
    return ts


def panel(prio: float, cell: str, bfcl: bool) -> list[dict]:
    """Formal stage 2 (after `make_newmethod_panel.py build --model m24` and the dated sha amendment): one cell's gates,
    phase-1 panel tasks f01-f03, token scores, and (bfcl=True, only if BF16 >= 10% on nmp_v1) the BFCL forks. Specs come
    verbatim from `make_newmethod_panel.py spec --model m24 --cell <cell>`; B = BF16, Q = the cell, 4 GPUs (TP=2 per role)."""
    import subprocess
    import sys
    sp = json.loads(subprocess.check_output([sys.executable, str(ROOT / "scripts/a6000/make_newmethod_panel.py"), "spec", "--model", "m24",
                                             "--cell", cell], cwd=ROOT, text=True))
    if "<sha256" in json.dumps(sp):
        raise SystemExit("manifests/fork/newmethod_panel_v1_m24.json not built yet")
    strip = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}  # noqa: E731
    gs = fork(f"nmp_gate_same_m24_{cell}", cell, cell, strip(sp["gate_same (Q determinism, foreign states)"]), prio, ["a6k2_m24_bfpair_f01_f02"])
    gb = fork(f"nmp_gate_bank_m24_{cell}", "bf16", cell, strip(sp["bank gate (BB no-op on every state)"]), prio, ["a6k2_m24_bfpair_f01_f02"])
    ts = [gs, gb]
    deps_blk = {"f01": "a6k2_m24_bfpair_f01_f02", "f02": "a6k2_m24_bfpair_f01_f02", "f03": "a6k2_m24_bfpair_f03_f04"}
    for spec_t, spec_s in zip(sp["panel tasks (one per block; task id nmp_tau2_<model>_<cell>_<blk>)"],
                              sp["token scores (KLu), driver score, after each panel task"]):
        blk = spec_t["blocks"][0]
        pt = fork(f"nmp_tau2_m24_{cell}_{blk}", "bf16", cell, spec_t, prio, [gs["id"], gb["id"], deps_blk[blk]])
        st = fork(f"nmp_score_m24_{cell}_{blk}", "bf16", cell, spec_s, prio, [pt["id"]])
        ts += [pt, st]
    if bfcl:
        for k, spec_f in zip(("base", "miss_param", "miss_func", "long_context"), sp["BFCL fork tasks (fork_ext dev, one per category)"]):
            ts.append(fork(f"nmp_bfcl_m24_{cell}_{k}", "bf16", cell, spec_f, prio, [f"ext_m24_{cell}_bfcl_nmp1", "ext_m24_bf16_bfcl_nmp1"], env="bfcl"))
    return ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["manifests", "gate", "bfpair", "panel"])
    ap.add_argument("--cell", default="rtn_w4", choices=["rtn_w4", "gptq_w4_d1"], help="panel: the configuration (Q role)")
    ap.add_argument("--bfcl", action="store_true", help="panel: also the BFCL forks (only if BF16 >= 10%% on nmp_v1)")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--priority", type=float, default=-26)
    a = ap.parse_args()
    if a.mode == "manifests":
        manifests()
        return
    ts = gate(a.priority) if a.mode == "gate" else bfpair(a.priority) if a.mode == "bfpair" else panel(a.priority, a.cell, a.bfcl)
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
