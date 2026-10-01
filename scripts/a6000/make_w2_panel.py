"""W2 stress panel (W69; QUANT_BENCHMARK_COVERAGE.md §4.4, EXECUTION_PLAN §4.1/§8.4): frozen task subset, gates, tasks.

freeze   Select ~24 of the canonical 85 retail/airline tasks (manifests/eval_tasks_v0.json) by task identity and
         prespecified task metadata only: strata = domain x tercile (within domain) of the number of gold actions in the
         task's evaluation criteria; domain allocation proportional (16 retail / 8 airline), stratum allocation by
         largest remainder; within a stratum the tasks with the smallest sha256("cloq-w2-panel-v1|domain|task_id").
         Block: q3 (nonce 4c8e1a7f), the first registered stress block with BF16, GPTQ-W4/AWQ-W4 d1, GPTQ-W3 and RTN-W3
         runs for both q4 and q8 (rule fixed here, before any W2 outcome). Writes manifests/stress/w2_panel_v1.json
         (refuses to overwrite).
tasks    Print (or --write) the gate tasks (build + two-bit grid check + serve + finite-output canary; cmd tasks running
         scripts/a6000/w2_gate.py) and the guarded panel eval tasks (deps on the gates):
           q4 RTN-W2, q8 RTN-W2, q8 GPTQ-W2 (c1, same solver settings as W3/W4) on the panel tasks x block q3;
           q4 BF16 under the same guard on the same tasks x block: live-vs-offline guard equivalence check.
         Every guarded run carries env CLOQ_LOOP_GUARD=lg-v2 and the pinned CLOQ_LOOP_GUARD_SHA (manifests/stress/loop_guard_v2.json);
         each W2 task also runs the original-cap sensitivity sample (manifests/stress/w2_panel_v1_capsample.json, no guard).
         BF16 / W4 / W3 references on the same tasks x q3 are existing unguarded runs, scored with the identical guard
         offline (analysis/loop_guard/guard_validation.py replay): under deterministic serving a guarded run equals the
         unguarded episode truncated where the guard fires; the q4 BF16 guarded run checks that.

usage: python scripts/a6000/make_w2_panel.py freeze | tasks [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
PANEL = ROOT / "manifests/stress/w2_panel_v1.json"
GUARD = ROOT / "manifests/stress/loop_guard_v2.json"  # W73: lg-v2 (lg-v1 failed its premature-stop check)
CAP = ROOT / "manifests/stress/w2_panel_v1_capsample.json"  # W73: original-cap sensitivity sample (6 tasks, no guard)
BLOCK, NONCE = "q3", "4c8e1a7f"
N_TOTAL, ALLOC = 24, {"retail": 16, "airline": 8}
CELLS = [("q4", "rtn_w2", {"kind": "rtn", "wbits": 2}), ("q8", "rtn_w2", {"kind": "rtn", "wbits": 2}),
         ("q8", "gptq_w2", {"kind": "gptq", "wbits": 2, "calib": "manifests/a6k2/q8/calib_fp_traj_c1.json"})]


def n_gold_actions(domain: str, tid: str) -> int:
    sys.path.insert(0, str(ROOT))
    from tau2.runner.helpers import get_tasks
    t = get_tasks(domain, task_split_name="base", task_ids=[tid])[0]
    ec = t.evaluation_criteria
    return len((ec.actions if ec is not None else None) or [])


def freeze():
    if PANEL.exists():
        raise SystemExit(f"{PANEL} exists: the panel is frozen")
    canon = json.load(open(ROOT / "manifests/eval_tasks_v0.json"))
    out, strata = {}, {}
    for dom, k in ALLOC.items():
        ids = [str(t) for t in canon[dom]]
        meta = {t: n_gold_actions(dom, t) for t in ids}
        order = sorted(ids, key=lambda t: (meta[t], t))  # tercile by gold-action count (ties by id)
        terc = {t: min(2, 3 * i // len(order)) for i, t in enumerate(order)}
        sizes = [sum(1 for t in ids if terc[t] == s) for s in range(3)]
        quota = [k * n / len(ids) for n in sizes]
        alloc = [int(q) for q in quota]
        for s in sorted(range(3), key=lambda s: -(quota[s] - alloc[s]))[: k - sum(alloc)]:
            alloc[s] += 1
        pick = []
        for s in range(3):
            cand = sorted((t for t in ids if terc[t] == s),
                          key=lambda t: hashlib.sha256(f"cloq-w2-panel-v1|{dom}|{t}".encode()).hexdigest())
            pick += cand[: alloc[s]]
        out[dom] = sorted(pick, key=lambda t: int(t) if t.isdigit() else t)
        strata[dom] = {"tercile_sizes": sizes, "allocation": alloc, "gold_actions": {t: meta[t] for t in out[dom]},
                       "tercile_of_pick": {t: terc[t] for t in out[dom]}}
    rec = {"panel": "w2-stress-v1", **out, "block": BLOCK, "nonce": NONCE, "n_tasks": sum(len(v) for v in out.values()),
           "selection": "domain x gold-action-count tercile; proportional allocation (16/8, largest remainder); "
                        "lowest sha256('cloq-w2-panel-v1|domain|task_id') within stratum; no outcome used",
           "strata": strata, "source": "manifests/eval_tasks_v0.json (canonical 85)",
           "block_rule": "q3 = first registered stress block with BF16, GPTQ-W4/AWQ-W4 d1, GPTQ-W3, RTN-W3 runs for q4 and q8",
           "stop_policy": "loop guard lg-v1 (manifests/stress/loop_guard_v1.json) on every compared arm incl. BF16"}
    rec["selection_sha256"] = hashlib.sha256(json.dumps({d: out[d] for d in ALLOC}, sort_keys=True).encode()).hexdigest()
    PANEL.parent.mkdir(parents=True, exist_ok=True)
    PANEL.write_text(json.dumps(rec, indent=1))
    print(json.dumps({d: out[d] for d in ALLOC}), rec["selection_sha256"][:16])


def tasks(write: bool, gates_only: bool = False):
    panel, guard = json.load(open(PANEL)), json.load(open(GUARD))
    if not gates_only and guard.get("validation", {}).get("passed") is not True:
        raise SystemExit("loop guard validation has not passed: no panel task is queued (gates: --gates-only)")
    env = {"CLOQ_LOOP_GUARD": guard["policy"], "CLOQ_LOOP_GUARD_SHA": guard["code_sha256"]}
    ts = []
    for m, cell, ck in CELLS:
        gid = f"w2gate_{m}_{cell}"
        ts.append({"id": gid, "kind": "cmd", "model": m, "gpus": 1, "priority": -10, "deps": [],
                   "title": f"W2 gate {m} {cell}",
                   "cmd": f"source scripts/a6000/env.sh && python scripts/a6000/w2_gate.py --model {m} --cell {cell} "
                          f"--ckpt '{json.dumps(ck)}'",
                   "note": "W69: W2 build / two-bit grid / serve / finite-output gate; a failure is a support result"})
        ts.append({"id": f"a6k2_w2p_{m}_{cell}_{BLOCK}", "kind": "eval", "model": m, "arm": ck["kind"], "ckpt": ck,
                   "runs": [{"run_id": f"a6k2_w2p_{m}_{cell}_{BLOCK}", "task_file": str(PANEL.relative_to(ROOT)),
                             "nonce": NONCE, "env": env},
                            # original-cap sensitivity (W73): same server, declared 6-task sample, registered caps only
                            {"run_id": f"a6k2_w2p_{m}_{cell}_cap_{BLOCK}", "task_file": str(CAP.relative_to(ROOT)),
                             "nonce": NONCE}],
                   "priority": -10, "deps": [gid] + ([f"a6k2_{m}_calib_c1"] if "calib" in ck else []),
                   "note": "W69/W73: W2 stress panel (frozen 24-task subset x block q3, loop guard lg-v2) + original-cap sample"})
    ts.append({"id": f"a6k2_w2p_q4_bf16_{BLOCK}", "kind": "eval", "model": "q4", "arm": "bf16", "ckpt": {"kind": "bf16"},
               "runs": [{"run_id": f"a6k2_w2p_q4_bf16_{BLOCK}", "task_file": str(PANEL.relative_to(ROOT)), "nonce": NONCE, "env": env}],
               "priority": -10, "deps": [],
               "note": "W69: guarded BF16 on the W2 panel: live guard == offline guard on the existing unguarded bfpair_q3"})
    if gates_only:  # build / grid / serve / finite-output gates do not depend on the stop policy
        ts = [t for t in ts if t["kind"] == "cmd"]
    for t in ts:
        print(t["id"], t["kind"], t.get("deps"))
    if write:
        for t in ts:
            if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
                json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
                print("queued", t["id"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["freeze", "tasks"])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--gates-only", action="store_true")
    a = ap.parse_args()
    freeze() if a.cmd == "freeze" else tasks(a.write, a.gates_only)


if __name__ == "__main__":
    main()
