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

formal1 formal stage 1, only after the gate PASS and after the dated protocol (docs/insights/G12_PANEL_PROTOCOL_*.md,
        --protocol) is frozen: BF16 closed-loop runs a6k2_g12_bfpair_f01..f0K on the 85-task panel (eval_tasks_v0, main
        nonce blocks; K from the protocol, 1 block per task), and the BF16 + GPTQ-W4 d1 BFCL runs on the 200 nmp_v1 items.
formal2 formal stage 2, after `make_newmethod_panel.py build --model g12` and the dated manifest-sha amendment: the
        gptq_w4_d1 cell's gates, its bank_u panel tasks f01..f0K and token scores, and (--bfcl, only if BF16 >= 10% on
        nmp_v1, §10) the four BFCL fork tasks. Specs verbatim from `make_newmethod_panel.py spec --model g12`.

usage: python3 scripts/a6000/make_tasks_g12.py {manifests|gate|formal1|formal2} [--protocol P] [--bfcl] [--write]
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
WORK_OLD = Path("/data/ziyangs/cloq_work/staged/w100n_superseded")  # superseded definitions of requeued g12 tasks (kept, renamed)
# W100n r1: with combo_kernels on (serve.sh default), Inductor fuses Gemma 4's per-head q/k/v norms of the 512-dim
# full-attention layers into one combo reduction kernel whose only deterministic config needs 256 KiB of shared memory
# (A6000 limit 99 KiB): "No valid triton configs" at startup (queue/failed/a6k2_g12_bf16_cal.json). g12 servers run with
# combo_kernels off (no benchmarking either way, so still TORCHINDUCTOR_DETERMINISTIC-compatible); every other serve.sh
# flag unchanged. Applied to every g12 server (eval, B and Q roles) so all g12 numerics share one flavour.
SERVE_EXTRA = ["--compilation-config", json.dumps({"inductor_compile_config": {"combo_kernels": False, "benchmark_combo_kernel": False}})]


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
            "priority": prio, "deps": deps, "serve_extra": SERVE_EXTRA, "note": NOTE}


def ev_bfcl(arm: str, subset: str, prio: float, deps: list[str]) -> dict:
    rid = f"ext_g12_{arm}_bfcl_{subset}"
    return {"id": rid, "kind": "eval", "env": "bfcl", "model": "g12", "arm": ARM[arm], "ckpt": CK[arm], "domains": DOMS,
            "gpus": 1, "priority": prio, "deps": deps, "runs": [{"run_id": rid, "task_file": BFCL, "subset": subset}],
            "serve_extra": SERVE_EXTRA, "note": NOTE}


def fork(tid: str, b: str, q: str, spec: dict, prio: float, deps: list[str], env: str | None = None) -> dict:
    if spec.get("mode") == "gate_same":  # W100e-c / 9ddb588: a failing same-checkpoint control fails the task (deps never release)
        spec = {**spec, "fail_loud": True}
    t = {"id": tid, "kind": "fork", "model": "g12", "gpus": 2, "priority": prio, "deps": deps,
         "B": {"ckpt": CK[b], "serve_extra": SERVE_EXTRA}, "Q": {"ckpt": CK[q], "serve_extra": SERVE_EXTRA}, "fork": spec, "note": NOTE}
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
    ts.append({"id": "a6k2_g12_bf16_cal", "kind": "eval", "model": "g12", "arm": "bf16", "ckpt": CK["bf16"], "gpus": 1, "serve_extra": SERVE_EXTRA,
               "runs": [{"run_id": "a6k2_g12_bf16_cal", "task_file": "manifests/cal_tasks_v0.json", "nonce": None}],
               "priority": prio, "deps": [], "note": NOTE + ": BF16 calibration-split run for GPTQ d1 (as a6k2_q14_bf16_cal)"})
    ts.append({"id": "a6k2_g12_calib_c1", "kind": "calib", "model": "g12", "arm": "fp_traj", "draw": "c1", "fp_run": "a6k2_g12_bf16_cal",
               "out": CAL, "priority": prio, "deps": ["a6k2_g12_bf16_cal"], "note": NOTE})
    ts.append(ev_tau("gptq_w4_d1", [{"run_id": blk["gptq_w4_d1"], "task_file": TAU_GATE, "nonce": NG}], prio, ["a6k2_g12_calib_c1"],
                     "a6k2_g12_gptq_w4_d1_gate"))
    ts[-1]["note"] = NOTE + ": GPTQ-W4 d1 build + serve readiness on the tau2 gate sample (descriptive; not an admission criterion)"
    return ts


BLOCK_NAMES = ("f01", "f02", "f03", "f04", "f05", "f06")
CELL = "gptq_w4_d1"


def frozen_k(protocol: str) -> tuple[int, str]:
    """K (number of blocks) from the dated protocol's machine-readable line `G12_FROZEN {json}`; returns (K, sha256)."""
    p = ROOT / protocol
    txt = p.read_text()
    line = next(l for l in txt.splitlines() if l.startswith("G12_FROZEN "))
    k = int(json.loads(line[len("G12_FROZEN "):])["K"])
    assert 1 <= k <= 6
    return k, hashlib.sha256(p.read_bytes()).hexdigest()


def formal1(prio: float, protocol: str) -> list[dict]:
    k, psha = frozen_k(protocol)
    blocks = json.load(open(ROOT / "manifests/fork/dev_blocks_v1.json"))["new_blocks"]
    note = NOTE + f": formal stage 1 (protocol {protocol} sha {psha[:12]})"
    ts = []
    for b in BLOCK_NAMES[:k]:
        t = ev_tau("bf16", [{"run_id": f"a6k2_g12_bfpair_{b}", "task_file": "manifests/eval_tasks_v0.json", "nonce": blocks[b]}],
                   prio, [], f"a6k2_g12_bfpair_{b}")
        t["note"] = note
        ts.append(t)
    for arm in ("bf16", CELL):
        rid = f"ext_g12_{arm}_bfcl_nmp1"
        ts.append({"id": rid, "kind": "eval", "env": "bfcl", "model": "g12", "arm": ARM[arm], "ckpt": CK[arm], "domains": DOMS, "gpus": 1,
                   "priority": prio, "deps": [], "runs": [{"run_id": rid, "task_file": "manifests/fork/newmethod_panel_v1.json", "subset": "nmp_v1"}],
                   "serve_extra": SERVE_EXTRA, "note": note + ": NEWMETHOD_PANEL_PROTOCOL panel B closed-loop run (same 200 ids as nmp_v1)"})
    return ts


def formal2(prio: float, protocol: str, bfcl: bool) -> list[dict]:
    import subprocess
    import sys
    k, psha = frozen_k(protocol)
    sp = json.loads(subprocess.check_output([sys.executable, str(ROOT / "scripts/a6000/make_newmethod_panel.py"), "spec", "--model", "g12",
                                             "--cell", CELL], cwd=ROOT, text=True))
    if "<sha256" in json.dumps(sp):
        raise SystemExit("manifests/fork/newmethod_panel_v1_g12.json not built yet")
    strip = lambda d: {kk: v for kk, v in d.items() if not kk.startswith("_")}  # noqa: E731
    note = NOTE + f": formal stage 2 (protocol {protocol} sha {psha[:12]})"
    gs = fork(f"nmp_gate_same_g12_{CELL}", CELL, CELL, strip(sp["gate_same (Q determinism, foreign states)"]), prio, ["a6k2_g12_bfpair_f01"])
    gb = fork(f"nmp_gate_bank_g12_{CELL}", "bf16", CELL, strip(sp["bank gate (BB no-op on every state)"]), prio, ["a6k2_g12_bfpair_f01"])
    ts = [gs, gb]
    tmpl_t = sp["panel tasks (one per block; task id nmp_tau2_<model>_<cell>_<blk>)"][0]
    tmpl_s = sp["token scores (KLu), driver score, after each panel task"][0]
    for b in BLOCK_NAMES[:k]:
        spec_t = {**tmpl_t, "blocks": [b], "out": tmpl_t["out"].rsplit("/", 1)[0] + "/" + b}
        spec_s = {**tmpl_s, "blocks": [b], "bank_out": spec_t["out"], "out": tmpl_s["out"].rsplit("/", 1)[0] + "/" + b}
        pt = fork(f"nmp_tau2_g12_{CELL}_{b}", "bf16", CELL, spec_t, prio, [gs["id"], gb["id"], f"a6k2_g12_bfpair_{b}"])
        st = fork(f"nmp_score_g12_{CELL}_{b}", "bf16", CELL, spec_s, prio, [pt["id"]])
        ts += [pt, st]
    if bfcl:
        for kk, spec_f in zip(("base", "miss_param", "miss_func", "long_context"), sp["BFCL fork tasks (fork_ext dev, one per category)"]):
            ts.append(fork(f"nmp_bfcl_g12_{CELL}_{kk}", "bf16", CELL, spec_f, prio, [f"ext_g12_{CELL}_bfcl_nmp1", "ext_g12_bf16_bfcl_nmp1"], env="bfcl"))
    for t in ts:
        t["note"] = note
    return ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["manifests", "gate", "formal1", "formal2"])
    ap.add_argument("--protocol", default=None, help="formal1/formal2: the dated g12 panel protocol (docs/insights/...)")
    ap.add_argument("--bfcl", action="store_true", help="formal2: also the BFCL forks (only if BF16 >= 10%% on nmp_v1)")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--requeue", nargs="*", default=[], help="ids in failed/ or deferred/ to replace by the current definition (todo)")
    ap.add_argument("--priority", type=float, default=-24)
    a = ap.parse_args()
    if a.mode == "manifests":
        manifests()
        return
    ts = gate(a.priority) if a.mode == "gate" else formal1(a.priority, a.protocol) if a.mode == "formal1" else formal2(a.priority, a.protocol, a.bfcl)
    for t in ts:
        clash = [s for s in ("todo", "running", "done", "failed", "deferred") if (Q / s / f"{t['id']}.json").exists()]
        if t["id"] in a.requeue and clash and set(clash) <= {"failed", "deferred"}:
            if a.write:
                for s_ in clash:
                    (Q / s_ / f"{t['id']}.json").rename(WORK_OLD / f"{t['id']}.{s_}.{int(time.time())}.json")
            clash = []
        print(t["id"], t.get("gpus"), t["priority"], t["deps"], "EXISTS " + str(clash) if clash else "")
        if a.write and not clash:
            tmp = Q / "todo" / f".{t['id']}.json.tmp"
            tmp.write_text(json.dumps(t, indent=1))
            tmp.replace(Q / "todo" / f"{t['id']}.json")
    print(f"{len(ts)} tasks" + ("" if a.write else " (dry run)"))


if __name__ == "__main__":
    main()
