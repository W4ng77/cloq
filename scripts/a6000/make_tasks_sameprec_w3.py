"""W3 same-precision tasks (docs/insights/SAMEPREC_W3_PROTOCOL_20261002.md; manifests/fork/sameprec_w3_v1.json).
Q = GPTQ-W3 d1 (calib c1), driver B role = Q' = GPTQ-W3 d2 (calib c2). SAMEPREC design otherwise.

  --build   one eval run of Q' per cell (a6k2_<m>_gptq_w3_d2_n1) = the build gate
  --gate    one replay-gate task per cell (mode gate; Q blocks a6k2_<m>_gptq_w3_n1; Q' own blocks ..._d2_n1), dep on build
  --formal  dev-mode tasks, one per cell x block (q3, q4, q5). Queue ONLY after both gates pass (protocol §3).
Priority -27; q4 1 GPU (gpu_util 0.44), q8 2 GPUs pinned to node004/005/007 in rotation. Never overwrites an existing id.
usage: python scripts/a6000/make_tasks_sameprec_w3.py (--build | --gate | --formal) [--write]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
MAN = ROOT / "manifests/fork/sameprec_w3_v1.json"
Q8_NODES = ("node004", "node005", "node007")
PRIO = -27


def ck(m: str, c: str) -> dict:
    return {"kind": "gptq", "wbits": 3, "calib": f"manifests/a6k2/{m}/calib_fp_traj_{c}.json"}


def fork_base(m: str, i: int, tid: str) -> dict:
    pin = {} if m == "q4" else {"node": Q8_NODES[i % len(Q8_NODES)]}
    return {**pin, "id": tid, "kind": "fork", "model": m, "gpus": 1 if m == "q4" else 2,
            **({"gpu_util": 0.44} if m == "q4" else {}), "priority": PRIO, "deps": [],
            "q_ckpt": ck(m, "c1"), "b_ckpt": ck(m, "c2"), "expect_distinct_numerics": True}


def build_tasks(man: dict) -> list[dict]:
    return [{"id": f"a6k2_{m}_gptq_w3_d2", "kind": "eval", "model": m, "arm": "gptq", "ckpt": ck(m, "c2"),
             "runs": [{"run_id": f"a6k2_{m}_gptq_w3_d2_n1", "task_file": "manifests/eval_tasks_v0.json", "nonce": "3f9a1c07"}],
             "priority": PRIO, "deps": [], "note": "W3 same-precision build gate (SAMEPREC_W3_PROTOCOL_20261002.md §3.1)"}
            for m in man["cells"]]


def gate_tasks(man: dict) -> list[dict]:
    out = []
    for i, m in enumerate(man["cells"]):
        t = fork_base(m, 0, f"fork_sameprec_w3_gate_{m}")
        t["deps"] = [f"a6k2_{m}_gptq_w3_d2"]
        t["fork"] = {"mode": "gate", "q_blocks": [[f"a6k2_{m}_gptq_w3_n1", d] for d in ("retail", "airline")],
                     "b_blocks": [[f"a6k2_{m}_gptq_w3_d2_n1", d] for d in ("retail", "airline")],
                     "search_tasks_per_block": 6, "n_states": 6, "n_iso": 2, "n_bb_noop": 4, "idcheck_n": 16,
                     "concurrency": 8, "out": f"analysis/fork/sameprec_w3/gate/{m}"}
        t["note"] = "W3 same-precision replay gate: driver B role = Q' (GPTQ-W3 d2); SAMEPREC_W3_PROTOCOL_20261002.md §3.2"
        out.append(t)
    return out


def formal_tasks(man: dict) -> list[dict]:
    out = []
    for m in man["cells"]:
        for b in man["blocks"]:
            t = fork_base(m, len(out), f"fork_sameprec_w3_{m}_{b}")
            t["fork"] = {"mode": "dev", "q_blocks": [[f"a6k2_{m}_gptq_w3_{b}", d] for d in ("retail", "airline")],
                         "branches": ["BB", "BQ", "QB"], "noop_frac": 0.1, "q_check": True, "concurrency": 8, "resume": True,
                         "out": f"analysis/fork/sameprec_w3/{m}_gptq_w3_d1_vs_d2/{b}"}
            t["note"] = f"W3 same-precision 2x2 (Q = GPTQ-W3 d1, B role = Q' = GPTQ-W3 d2), block {b}; SAMEPREC_W3_PROTOCOL_20261002.md"
            out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true")
    g.add_argument("--gate", action="store_true")
    g.add_argument("--formal", action="store_true")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    man = json.load(open(MAN))
    tasks = build_tasks(man) if a.build else gate_tasks(man) if a.gate else formal_tasks(man)
    for t in tasks:
        print(t["id"], t["kind"], t.get("gpus", 1), "GPU", t.get("node", "-"), (t.get("fork") or {}).get("out") or t["runs"][0]["run_id"])
    if not a.write:
        print(f"{len(tasks)} tasks (dry run)")
        return
    n = 0
    for t in tasks:
        if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed", "deferred")):
            json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
            n += 1
    print(f"wrote {n} tasks")


if __name__ == "__main__":
    main()
