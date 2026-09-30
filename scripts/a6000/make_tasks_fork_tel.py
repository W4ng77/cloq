"""Telecom development forks (W52): q8 AWQ-W4 d1 and q8 GPTQ-W4 d1 (calibration c1) on the telecom dev blocks f01-f06.

Q runs a6k2_q8_tel_<cell>_f0k and BF16 pairs a6k2_q8_tel_bfpair_f0k are all admitted in snapshot 20260930T1319Z with equal
nonces; their task sets are the 80 dev tasks of manifests/telecom/dev_v1.json and contain none of the 34 holdout tasks
(checked again by fork_driver's inputs: the fork only ever touches tasks present in the Q run). Mode "dev" (all states
frozen before branches; BB/BQ/QB + 10% QQ no-op quarantine). q8 on 2 GPUs pinned to node004/005/007; priority -12.
Two blocks per task (telecom branches are long: median 209 s, p90 425 s at the gate). Output: analysis/fork/telecom/.

usage: python scripts/a6000/make_tasks_fork_tel.py [--write]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

Q = Path("/data/ziyangs/cloq_work/queue")
NODES = ("node004", "node005", "node007")
CELLS = {"awq_w4": {"kind": "awq", "wbits": 4, "calib": "manifests/a6k2/q8/calib_fp_traj_c1.json"},
         "gptq_w4_d1": {"kind": "gptq", "wbits": 4, "calib": "manifests/a6k2/q8/calib_fp_traj_c1.json"}}
HOLDOUT = set(json.load(open("/data/ziyangs/cloq/manifests/telecom/dev_v1.json"))["holdout"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    T, i = [], 0
    for cell, ck in CELLS.items():
        for g, blocks in enumerate((["f01", "f02"], ["f03", "f04"], ["f05", "f06"]), 1):
            for b in blocks:  # never the holdout
                ids = set(json.load(open(f"/data/ziyangs/cloq/runs/a6k2_q8_tel_{cell}_{b}/telecom/task_manifest.json"))["task_ids"])
                assert not ids & HOLDOUT, (cell, b)
            T.append({"id": f"fork_tel_q8_{cell}_g{g}", "kind": "fork", "model": "q8", "gpus": 2, "node": NODES[i % 3],
                      "priority": -12, "deps": [], "B": {"ckpt": {"kind": "bf16"}}, "Q": {"ckpt": ck},
                      "fork": {"mode": "dev", "q_blocks": [[f"a6k2_q8_tel_{cell}_{b}", "telecom"] for b in blocks],
                               "branches": ["BB", "BQ", "QB"], "noop_frac": 0.1, "q_check": True, "concurrency": 8,
                               "out": f"analysis/fork/telecom/q8_{cell}/g{g}"},
                      "note": "W52 telecom dev forks (make_tasks_fork_tel.py); never the 34 holdout tasks"})
            i += 1
    for t in T:
        print(t["id"], t["node"], [q[0] for q in t["fork"]["q_blocks"]])
    if a.write:
        n = 0
        for t in T:
            if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
                json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
                n += 1
        print("wrote", n)


if __name__ == "__main__":
    main()
