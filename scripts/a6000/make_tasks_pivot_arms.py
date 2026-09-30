"""W55 step 2: pivot-arm tasks (fork_driver mode "pivot_arms"; selection rule in docs/insights/FORK_PROTOCOL.md §13).

Each task serves two restoration arms, one per handle (B and Q). Each arm makes one decision at 150 hash-sampled
frozen fork states of its cell. There are no rollouts and no simulator calls.
Cells: q4 GPTQ-W4 c1 (dev fork states), q8 AWQ-W4 c1 (dev fork states), q4/q8 GPTQ-W3 c1 (stress fork states).
Arm checkpoints are the W39/W50/W54 derived specs (scripts/a6000/derived.py; the cached base keeps all arms of a cell
on bit-identical Q weights).
Priority -14. q8 runs on 2 GPUs, pinned to node004/005/007.

usage: python scripts/a6000/make_tasks_pivot_arms.py [--write]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

Q = Path("/data/ziyangs/cloq_work/queue")
NODES = ("node004", "node005", "node007")
PLAIN = ["none", "all", "early", "middle", "late", "attn", "mlp", "rand_third_s1", "rand_attn_s1", "rand_mlp_s1", "resid_a0.5"]
RECAL = ["recal_early", "recal_middle", "recal_late", "recal_attn", "recal_mlp", "recal_rand_third_s1", "recal_rand_attn_s1",
         "recal_rand_mlp_s1"]
CELLS = {  # (model, cell): (base spec, states globs, deps, arms)
    ("q4", "gptq_w4_d1"): ({"kind": "gptq", "wbits": 4, "calib": "manifests/a6k2/q4/calib_fp_traj_c1.json"},
                           ["analysis/fork/dev/q4_gptq_w4_d1/g*/states/*.json"], [], PLAIN),
    ("q8", "awq_w4"): ({"kind": "awq", "wbits": 4, "calib": "manifests/a6k2/q8/calib_fp_traj_c1.json"},
                       ["analysis/fork/dev/q8_awq_w4/g*/states/*.json"], [], PLAIN),
    ("q4", "gptq_w3"): ({"kind": "gptq", "wbits": 3, "calib": "manifests/a6k2/q4/calib_fp_traj_c1.json"},
                        ["analysis/fork/stress/q4_gptq_w3/states/*.json"], [], PLAIN + RECAL),
    ("q8", "gptq_w3"): ({"kind": "gptq", "wbits": 3, "calib": "manifests/a6k2/q8/calib_fp_traj_c1.json"},
                        ["analysis/fork/stress/q8_gptq_w3/states/*.json"], ["fork_stress_q8_gptq_w3"], PLAIN + RECAL),
}


def spec(m: str, base: dict, arm: str) -> dict:
    if arm.startswith("resid_a"):
        return {"kind": "resid", "base": base, "alpha": float(arm[len("resid_a"):])}
    kind, name = ("restore_recal", arm[len("recal_"):]) if arm.startswith("recal_") else ("restore", arm)
    return {"kind": kind, "base": base, "arm": name, "manifest": f"manifests/perturb/restore_v1/{m}/{name}.json"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    T, i = [], 0
    for (m, cell), (base, globs, deps, arms) in CELLS.items():
        for k in range(0, len(arms), 2):
            pair = arms[k:k + 2]
            b_arm, q_arm = pair[0], pair[-1]
            t = {"id": f"pivot_{m}_{cell}_{'__'.join(pair)}", "kind": "fork", "model": m, "gpus": 1 if m == "q4" else 2,
                 **({"gpu_util": 0.44} if m == "q4" else {"node": NODES[i % 3]}), "priority": -14, "deps": deps,
                 "B": {"ckpt": spec(m, base, b_arm)}, "Q": {"ckpt": spec(m, base, q_arm)},
                 "fork": {"mode": "pivot_arms", "states_globs": globs, "n_states": 150, "salt": "pivot-arms-v1",
                          "arms": {"B": b_arm, "Q": q_arm}, "concurrency": 8, "out": f"analysis/fork/pivot_arms/{m}_{cell}"},
                 "note": "W55 step 2 (make_tasks_pivot_arms.py; FORK_PROTOCOL §13)"}
            T.append(t)
            i += 1
    for t in T:
        print(t["id"], t["gpus"], t.get("node", ""), t["deps"])
    print(len(T), "tasks")
    if a.write:
        n = 0
        for t in T:
            if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
                json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
                n += 1
        print("wrote", n)


if __name__ == "__main__":
    main()
