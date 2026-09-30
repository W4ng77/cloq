"""Queue same-state fork tasks on the simulator-free environments (worker kind "fork" + "env"; scripts/ext/fork_ext.py).

  gate : engineering gate (a)(c)(d)(e) + (b) same-checkpoint on q4 GPTQ-W4 d1 (c1) vs BF16, per environment, on the
         W36-ext smoke blocks (development blocks only: never the reported eval runs). 1 GPU (q4 B+Q, GPU_UTIL 0.44).
  dev  : development forks on the W37/W38 eval blocks (only after the gate passes). Pairs (B = BF16 always):
           ALFWorld q8: GPTQ-W4 d1, AWQ-W4 d1, stress GPTQ-W3, KV4        (q4 ALFWorld is at the floor, W37)
           BFCL q4, q8: GPTQ-W4 d1, AWQ-W4 d1, stress GPTQ-W3, KV4        (one task per category)
         q8 tasks are strictly 2-GPU (B+Q on one card does not fit at max_len 33792); q4 tasks 1 GPU.
         Each task depends on its Q eval task (the block) and the BF16 eval task (canary/BB reference).

usage: python3 scripts/ext/make_tasks_extfork.py {gate|dev} [--write] [--priority P]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

Q = Path("/data/ziyangs/cloq_work/queue")
BFCL_DOMS = ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"]


def role(model: str, arm: str) -> dict:
    calib = f"manifests/a6k2/{model}/calib_fp_traj_c1.json"
    return {"bf16": {"ckpt": {"kind": "bf16"}},
            "gptq_w4_d1": {"ckpt": {"kind": "gptq", "wbits": 4, "calib": calib}},
            "awq_w4_d1": {"ckpt": {"kind": "awq", "wbits": 4, "calib": calib}},
            "gptq_w3": {"ckpt": {"kind": "gptq", "wbits": 3, "calib": calib}},
            "kvq_int4": {"ckpt": {"kind": "bf16"}, "serve_env": {"CLOQ_PYHOOKS": "1", "CLOQ_KVQ_BITS": "4"}}}[arm]


def fork_task(tid, env, model, q_arm, b_arm, spec, priority, deps, note) -> dict:
    return {"id": tid, "kind": "fork", "env": env, "model": model, "gpus": 1 if model == "q4" else 2,
            **({"gpu_util": 0.44} if model == "q4" else {}), "priority": priority, "deps": deps,
            "B": role(model, b_arm), "Q": role(model, q_arm), "fork": spec, "note": note}


def gate_tasks(priority: float) -> list[dict]:
    ts = []
    for env, doms in (("bfcl", BFCL_DOMS), ("alfworld", ["alfworld"])):
        qb = [f"ext_q4_gptq_w4_d1_{env}_smoke:{d}" for d in doms]
        bb = [f"ext_q4_bf16_{env}_smoke:{d}" for d in doms]
        ts.append(fork_task(f"fork_ext_gate_q4_gptq_w4_d1_{env}", env, "q4", "gptq_w4_d1", "bf16",
                            {"mode": "gate", "q_blocks": qb, "b_blocks": bb, "n_bb": 4, "max_states": 12, "n_iso": 4,
                             "concurrency": 8, "out": f"analysis/fork/ext/gate/{env}_q4_gptq_w4_d1"}, priority, [],
                            "fork-ext-v1 engineering gate (a,c,d,e) on the W36-ext smoke blocks (development only)"))
        ts.append(fork_task(f"fork_ext_gate_same_q4_gptq_w4_d1_{env}", env, "q4", "gptq_w4_d1", "gptq_w4_d1",
                            {"mode": "gate_same", "q_blocks": qb, "n_items": 3 if env == "bfcl" else 6, "n_same": 4,
                             "concurrency": 8, "out": f"analysis/fork/ext/gate/{env}_q4_same_ckpt"}, priority, [],
                            "fork-ext-v1 gate (b): B and Q handles on two servers of the same checkpoint"))
    return ts


def dev_tasks(priority: float) -> list[dict]:
    ts = []
    plan = [("alfworld", "q8", a, ["alfworld"]) for a in ("gptq_w4_d1", "awq_w4_d1", "gptq_w3", "kvq_int4")] + \
           [("bfcl", m, a, BFCL_DOMS) for m in ("q4", "q8") for a in ("gptq_w4_d1", "awq_w4_d1", "gptq_w3", "kvq_int4")]
    for env, m, arm, doms in plan:
        qrun, brun = f"ext_{m}_{arm}_{env}_eval", f"ext_{m}_bf16_{env}_eval"
        for d in doms:
            tag = d.replace("bfcl_", "") if env == "bfcl" else "all"
            ts.append(fork_task(f"fork_ext_dev_{m}_{arm}_{env}_{tag}", env, m, arm, "bf16",
                                {"mode": "dev", "q_blocks": [f"{qrun}:{d}"], "noop_frac": 0.1, "concurrency": 8,
                                 "out": f"analysis/fork/ext/dev/{env}_{m}_{arm}_{tag}"}, priority, [qrun, brun],
                                "fork-ext-v1 development forks (search over every item; BB/BQ/QB + 10% QQ no-op)"))
    return ts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["gate", "dev"])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--priority", type=float, default=-8)
    a = ap.parse_args()
    ts = gate_tasks(a.priority) if a.mode == "gate" else dev_tasks(a.priority)
    for t in ts:
        p = Q / "todo" / f"{t['id']}.json"
        if any((Q / d / p.name).exists() for d in ("todo", "running", "done")):
            print(f"exists: {t['id']}")
            continue
        print(("queued " if a.write else "would queue ") + t["id"] + f"  gpus={t['gpus']} deps={t['deps']}")
        if a.write:
            p.write_text(json.dumps(t, indent=1))


if __name__ == "__main__":
    main()
