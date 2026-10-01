"""Bank U tasks (FORK_PROTOCOL §15 + amendment 1, W70): fork_driver mode bank_u, manifest manifests/fork/bank_u_v1.json.

  --gate        replay gate: q4 GPTQ-W4 d1, q4 KV8 (hooked serving), q8 AWQ-W4; 10 states per sub-bank (U1, U2B, U2Q) on f01,
                no-op run on every state (U1: Q->Q, U2B: B->B, U2Q with this cell = source: Q->Q)
  --blocks f01  bank tasks: one per model x cell x block (U1 + U2B + U2Q of that block), 10% no-op sample
B = BF16, Q = the cell's exact serving config (kvq_int8: KV INT8 hook). q4 on 1 GPU (B+Q, GPU_UTIL 0.44); q8 on 2 GPUs pinned
to node004/005/007. Priority -17.
usage: python scripts/a6000/make_tasks_bank_u.py (--gate | --blocks f01 [f02 ...]) [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
NODES = ("node004", "node005", "node007")
MAN = "manifests/fork/bank_u_v1.json"


def qrole(m, cell):
    if cell == "kvq_int8":
        return {"ckpt": {"kind": "bf16"}, "serve_env": {"CLOQ_PYHOOKS": "1", "CLOQ_KVQ_BITS": "8"}}
    ck = {"kind": "gptq" if cell.startswith("gptq") else "awq", "wbits": 4, "calib": f"manifests/a6k2/{m}/calib_fp_traj_c1.json"}
    return {"ckpt": ck}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--blocks", nargs="*", default=[])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    sha = hashlib.sha256((ROOT / MAN).read_bytes()).hexdigest()
    T, i = [], 0
    pairs = [("q4", "gptq_w4_d1"), ("q4", "kvq_int8"), ("q8", "awq_w4")] if a.gate else \
        [(m, c) for m in ("q4", "q8") for c in ("gptq_w4_d1", "awq_w4", "kvq_int8")]
    for blk in (["f01"] if a.gate else a.blocks):
        for m, c in pairs:
            tid = f"bank_u_gate_{m}_{c}" if a.gate else f"bank_u_{m}_{c}_{blk}"
            spec = {"mode": "bank_u", "manifest": MAN, "manifest_sha256": sha, "model": m, "cell": c, "blocks": [blk],
                    "subs": ["U1", "U2B", "U2Q"], "noop_frac": 1.0 if a.gate else 0.1, "concurrency": 8,
                    "out": f"analysis/fork/bank_u/{'gate/' if a.gate else ''}{m}_{c}/{blk}"}
            if a.gate:
                spec["limit_per_sub"] = 10
            T.append({"id": tid, "kind": "fork", "model": m, "gpus": 1 if m == "q4" else 2,
                      **({"gpu_util": 0.44} if m == "q4" else {"node": NODES[i % 3]}), "priority": -17, "deps": [],
                      "B": {"ckpt": {"kind": "bf16"}}, "Q": qrole(m, c), "fork": spec,
                      "note": "W70 Bank U (make_tasks_bank_u.py; FORK_PROTOCOL §15 amendment 1)"})
            i += 1
    for t in T:
        print(t["id"], t["gpus"], t.get("node", ""), t["fork"]["blocks"])
    if a.write:
        n = 0
        for t in T:
            if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
                json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
                n += 1
        print("wrote", n)


if __name__ == "__main__":
    main()
