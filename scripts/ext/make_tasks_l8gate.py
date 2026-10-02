"""W99f: queue tasks for the Llama-3.1-8B (l8) BFCL four-arm fork gate, and stage (never queue) the formal panel.

gate  : a6k2_l8_bf16_cal (tau2 calibration-split BF16 run, as a6k2_<m>_bf16_cal) -> a6k2_l8_calib_c1 (fp_traj c1, as
        every Qwen d1 checkpoint) -> ext_l8_{bf16,gptq_w4_d1}_bfcl_smokeg (manifests/bfcl/bfcl_mt_l8gate_v1.json,
        subset smoke_l8g, 5 per category) -> fork_ext_gate_l8_gptq_w4_d1_bfcl (fork-ext-v1 gate mode: 4 arms on every
        smoke state, QQ no-op on every state, BB no-op on 4 BF16 mid states, isolation, re-prefill) and
        fork_ext_dev_l8_gptq_w4_d1_bfcl_smokeg_<cat> (dev mode, one per category: effects.jsonl for analyze_ext, QQ no-op on
        every state). Outputs stay outside analysis/fork/ext/dev so the Qwen pools of analyze_ext/ext_r2 are untouched.
formal: the same pair on subset formal_l8 (50 per category) as the q4/q8 dev forks, one fork task per category (out analysis/fork/ext_l8/dev/, outside the Qwen pools); written to
        --stage DIR only (the main session decides whether to queue them).
B = BF16, Q = GPTQ-W4 d1 (calib_fp_traj_c1). l8 forks are 2-GPU (8B B+Q do not fit one card at max_len 33792).

usage: python3 scripts/ext/make_tasks_l8gate.py {gate|formal} [--write] [--node node008] [--priority -14] [--stage DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

Q = Path("/data/ziyangs/cloq_work/queue")
MAN = "manifests/bfcl/bfcl_mt_l8gate_v1.json"
DOMS = ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"]
CAL = "manifests/a6k2/l8/calib_fp_traj_c1.json"
CK = {"bf16": {"kind": "bf16"}, "gptq_w4_d1": {"kind": "gptq", "wbits": 4, "calib": CAL}}
TAG = "_sc"  # single tool call per response (models.json l8 ext_request parallel_tool_calls=false; r0 without it ended at decision 1)
NOTE = "W99f l8 second-family BFCL four-arm fork (exploratory external replication)"


def ev(arm, subset, prio, node, deps):
    rid = f"ext_l8_{arm}_bfcl_{subset}{TAG}"
    t = {"id": rid, "kind": "eval", "env": "bfcl", "model": "l8", "arm": "bf16" if arm == "bf16" else "gptq", "ckpt": CK[arm],
         "domains": DOMS, "gpus": 1, "priority": prio, "deps": deps,
         "runs": [{"run_id": rid, "task_file": MAN, "subset": subset}], "note": NOTE}
    return {**t, **({"node": node} if node else {})}


def fork(tid, spec, prio, node, deps):
    t = {"id": tid, "kind": "fork", "env": "bfcl", "model": "l8", "gpus": 2, "priority": prio, "deps": deps,
         "B": {"ckpt": CK["bf16"]}, "Q": {"ckpt": CK["gptq_w4_d1"]}, "fork": spec, "note": NOTE}
    return {**t, **({"node": node} if node else {})}


DEV_NODE = {"bfcl_base": "node006", "bfcl_miss_param": "node006"}  # spread the 2-GPU dev forks over two idle runners


def gate(prio, node):
    pre = [{"id": "a6k2_l8_bf16_cal", "kind": "eval", "model": "l8", "arm": "bf16", "ckpt": {"kind": "bf16"}, "gpus": 1,
            "runs": [{"run_id": "a6k2_l8_bf16_cal", "task_file": "manifests/cal_tasks_v0.json", "nonce": None}],
            "priority": prio, "deps": [], "node": node, "note": NOTE + ": BF16 calibration-split run for GPTQ d1 (as a6k2_q14_bf16_cal)"},
           {"id": "a6k2_l8_calib_c1", "kind": "calib", "model": "l8", "arm": "fp_traj", "draw": "c1", "fp_run": "a6k2_l8_bf16_cal",
            "out": CAL, "priority": prio, "deps": ["a6k2_l8_bf16_cal"], "node": node, "note": NOTE}]
    b, q = ev("bf16", "smoke_l8g", prio, node, []), ev("gptq_w4_d1", "smoke_l8g", prio, node, ["a6k2_l8_calib_c1"])
    deps = [b["id"], q["id"]]
    g = fork(f"fork_ext_gate_l8_gptq_w4_d1_bfcl{TAG}", {"mode": "gate", "q_blocks": [f"{q['id']}:{d}" for d in DOMS],
             "b_blocks": [f"{b['id']}:{d}" for d in DOMS], "n_bb": 4, "max_states": 20, "n_iso": 4, "concurrency": 8,
             "out": f"analysis/fork/ext_l8_gate/gate_bfcl_l8_gptq_w4_d1{TAG}"}, prio, node, deps)
    ds = [fork(f"fork_ext_dev_l8_gptq_w4_d1_bfcl_smokeg{TAG}_{x.replace('bfcl_', '')}", {"mode": "dev", "q_blocks": [f"{q['id']}:{x}"],
               "noop_frac": 1.0, "concurrency": 8, "out": f"analysis/fork/ext_l8_gate/dev/bfcl_l8_gptq_w4_d1_{x.replace('bfcl_', '')}"},
               prio, DEV_NODE.get(x, node), deps) for x in DOMS]  # one dir per category: analyze_ext.parse_dir takes the stratum from the dir name
    return pre + [b, q, g] + ds


def formal(prio):
    b, q = ev("bf16", "formal_l8", prio, None, []), ev("gptq_w4_d1", "formal_l8", prio, None, ["a6k2_l8_calib_c1"])
    ts = [b, q]
    for dom in DOMS:
        tag = dom.replace("bfcl_", "")
        ts.append(fork(f"fork_ext_dev_l8_gptq_w4_d1_bfcl{TAG}_{tag}", {"mode": "dev", "q_blocks": [f"{q['id']}:{dom}"], "noop_frac": 0.1,
                       "concurrency": 12, "out": f"analysis/fork/ext_l8/dev/bfcl_l8_gptq_w4_d1_{tag}"}, prio, None, [b["id"], q["id"]]))
    return ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["gate", "formal"])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--node", default="node008")
    ap.add_argument("--priority", type=float, default=-14)
    ap.add_argument("--stage", default=None, help="formal: directory to write the task files to (never queue/todo)")
    a = ap.parse_args()
    ts = gate(a.priority, a.node) if a.mode == "gate" else formal(a.priority)
    if a.mode == "formal":
        assert a.stage and Path(a.stage).resolve() != (Q / "todo").resolve(), "formal tasks are staged only"
        dst = Path(a.stage)
    else:
        dst = Q / "todo"
    for t in ts:
        clash = [p for s in ("todo", "running", "done", "failed") for p in [Q / s / f"{t['id']}.json"] if p.exists()]
        print(t["id"], "EXISTS " + str(clash) if clash else "")
        if a.write and not clash:
            dst.mkdir(parents=True, exist_ok=True)
            tmp = dst / f".{t['id']}.json.tmp"
            tmp.write_text(json.dumps(t, indent=1))
            tmp.replace(dst / f"{t['id']}.json")


if __name__ == "__main__":
    main()
