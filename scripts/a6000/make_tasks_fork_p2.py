"""P2 fork tasks (docs/EXECUTION_PLAN_20260930.md §2 P2): KV axis and stress cells, protocol fork-v1 mode "dev".

  KV8 core   q4, q8 x kvq_int8 (BF16 weights + KV INT8 hook, serve_env as the closed-loop runs) on every block with an
             admitted Q run and an admitted nonce-paired BF16 run: q1-q5 + f01-f17 = 22 blocks per model.
  stress     q4, q8 x gptq_w3 (GPTQ-W3, calibration c1) on q3-q5, and x kvq_int4_rot (KV INT4 + Hadamard; the plain
             INT4 cell has no closed-loop runs) on q1-q3: all 85 tasks x 3 blocks.
Every Q block and its BF16 pair were checked in snapshot 20260930T0911Z (admitted, same nonce, one checkpoint spec per
cell), so no new closed-loop Q runs are needed. B is always plain BF16; Q is the cell's exact serving config
(fork_serve per-role config: a KV role shares B's weights but runs its own server and config hash).
Mode "dev": divergence search over all tasks of each block, all states frozen, then BB/BQ/QB + the QQ no-op on a 10%
hash sample (a mismatch quarantines the task's output, protocol A). Priority -15 (after the W forks at -20).
q8 tasks use 2 GPUs (one per server) and are pinned to node004/005/007 (node006's runner ignores task gpus).
Outputs: analysis/fork/kv/<model>_kvq_int8/g<k>, analysis/fork/stress/<model>_<cell>/ (read by analyze_dev.py).

usage: python scripts/a6000/make_tasks_fork_p2.py [--write]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

Q = Path("/data/ziyangs/cloq_work/queue")
Q8_NODES = ("node004", "node005", "node007")
KV8 = {"ckpt": {"kind": "bf16"}, "serve_env": {"CLOQ_PYHOOKS": "1", "CLOQ_KVQ_BITS": "8"}}
KV4R = {"ckpt": {"kind": "bf16"}, "serve_env": {"CLOQ_PYHOOKS": "1", "CLOQ_KVQ_BITS": "4", "CLOQ_KVQ_ROT": "1"}}
BLOCKS_KV8 = ["q1", "q2", "q3", "q4", "q5"] + [f"f{i:02d}" for i in range(1, 18)]


def w3(m):
    return {"ckpt": {"kind": "gptq", "wbits": 3, "calib": f"manifests/a6k2/{m}/calib_fp_traj_c1.json"}}


def task(tid, m, qrole, blocks, cell, out, i):
    pin = {} if m == "q4" else {"node": Q8_NODES[i % len(Q8_NODES)]}
    return {"id": tid, "kind": "fork", "model": m, "gpus": 1 if m == "q4" else 2, **({"gpu_util": 0.44} if m == "q4" else {}),
            **pin, "priority": -15, "deps": [], "B": {"ckpt": {"kind": "bf16"}}, "Q": qrole,
            "fork": {"mode": "dev", "q_blocks": [[f"a6k2_{m}_{cell}_{b}", d] for b in blocks for d in ("retail", "airline")],
                     "branches": ["BB", "BQ", "QB"], "noop_frac": 0.1, "q_check": True, "concurrency": 8, "out": out},
            "note": "P2 fork (W49): make_tasks_fork_p2.py"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    T, i = [], 0
    for m in ("q4", "q8"):
        for g in range(0, len(BLOCKS_KV8), 5):
            T.append(task(f"fork_kv_{m}_kvq_int8_g{g // 5 + 1}", m, KV8, BLOCKS_KV8[g:g + 5], "kvq_int8",
                          f"analysis/fork/kv/{m}_kvq_int8/g{g // 5 + 1}", i))
            i += 1
        T.append(task(f"fork_stress_{m}_gptq_w3", m, w3(m), ["q3", "q4", "q5"], "gptq_w3", f"analysis/fork/stress/{m}_gptq_w3", i))
        i += 1
        T.append(task(f"fork_stress_{m}_kvq_int4_rot", m, KV4R, ["q1", "q2", "q3"], "kvq_int4_rot",
                      f"analysis/fork/stress/{m}_kvq_int4_rot", i))
        i += 1
    for t in T:
        print(t["id"], t["gpus"], "GPU", t.get("node", ""), len(t["fork"]["q_blocks"]) // 2, "blocks")
    if not a.write:
        print(f"{len(T)} tasks (dry run)")
        return
    n = 0
    for t in T:
        if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
            json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
            n += 1
    print(f"wrote {n} tasks")


if __name__ == "__main__":
    main()
