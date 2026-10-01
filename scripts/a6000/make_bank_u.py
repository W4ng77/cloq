"""Bank U manifest (FORK_PROTOCOL §15 + amendment 1, W70). CPU only; writes manifests/fork/bank_u_v1.json.

Rows (one per sampled state):
  U1    source = a6k2_<m>_<cell>_<blk> (the configuration's own trajectory), cells q4/q8 x {gptq_w4_d1, awq_w4, kvq_int8}
  U2B   source = a6k2_<m>_bfpair_<blk> (BF16-sourced shared state), queried by every cell of model m
  U2Q   source = a6k2_<m>_gptq_w4_d1_<blk> for the first 20 tasks by sha256("bank-u2q-v1|" + task) (Q-sourced shared state)
Decision index (uniform within trajectory, no stratification): t = floor(u * n_decisions),
u = int(sha256("bank-u-v1|run|domain|task")[:12], 16) / 16**12; selection_probability = 1 / n_decisions.
Q0 subsample (U2 rows): sha256("bank-u-q0-v1|" + state_key) / 16**12 < 0.25.
Blocks f01, f02, f03; retail/airline split tasks (manifests/fork/splits_v1.json). A row whose source episode is missing,
not admitted in the snapshot or has a decision/trajectory count mismatch is kept with a missing_reason (never replaced).

usage: python scripts/a6000/make_bank_u.py --snapshot <snapshot.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT))
from cloq import fork as F  # noqa: E402

MODELS = ("q4", "q8")
CELLS = ("gptq_w4_d1", "awq_w4", "kvq_int8")
BLOCKS = ("f01", "f02", "f03")
DOMS = ("retail", "airline")


def u01(s: str) -> float:
    return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16) / 16 ** 12


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    a = ap.parse_args()
    snap = json.load(open(a.snapshot))
    split = json.load(open(ROOT / "manifests/fork/splits_v1.json"))
    tasks = {d: [str(t) for t in split["splits"]["dev"]["tasks"][d]] for d in DOMS}
    rows = []
    blocks_cache: dict = {}

    def add(sub, m, cell, run, blk, dom, tid):
        key = f"{sub}|{run}|{dom}|{tid}"
        row = {"state_key": hashlib.sha256(key.encode()).hexdigest()[:16], "sub": sub, "model": m, "cell": cell,
               "source_run": run, "block": blk, "domain": dom, "task_id": tid, "t": None, "n_decisions": None,
               "selection_probability": None, "q0": sub != "U1" and u01("bank-u-q0-v1|" + hashlib.sha256(key.encode()).hexdigest()[:16]) < 0.25,
               "missing_reason": None}
        fr = (snap["frozen"].get(run) or {}).get(dom)
        if fr is None:
            row["missing_reason"] = "source run not admitted in snapshot"
            rows.append(row)
            return
        if (run, dom) not in blocks_cache:
            blocks_cache[(run, dom)] = F.Block(ROOT, run, dom)
        b = blocks_cache[(run, dom)]
        tr = b.traj.get(tid)
        if tr is None:
            row["missing_reason"] = "task not in source trajectory"
        elif tr["termination_reason"] not in ("user_stop", "agent_stop", "max_steps", "too_many_errors"):
            row["missing_reason"] = f"source episode termination {tr['termination_reason']}"
        else:
            n0 = F.prefix_len(tr["task"])
            pos = F.agent_positions(tr["messages"], n0)
            if len(pos) != len(b.dec.get(tid, [])) or not pos:
                row["missing_reason"] = "decision/trajectory count mismatch"
            else:
                n = len(pos)
                row.update({"n_decisions": n, "t": int(u01(f"bank-u-v1|{run}|{dom}|{tid}") * n), "selection_probability": 1.0 / n})
        rows.append(row)

    for m in MODELS:
        for blk in BLOCKS:
            for dom in DOMS:
                for tid in tasks[dom]:
                    for cell in CELLS:
                        add("U1", m, cell, f"a6k2_{m}_{cell}_{blk}", blk, dom, tid)
                    add("U2B", m, None, f"a6k2_{m}_bfpair_{blk}", blk, dom, tid)
            ranked = sorted(((dom, tid) for dom in DOMS for tid in tasks[dom]), key=lambda x: hashlib.sha256(f"bank-u2q-v1|{x[0]}:{x[1]}".encode()).hexdigest())
            for dom, tid in ranked[:20]:
                add("U2Q", m, None, f"a6k2_{m}_gptq_w4_d1_{blk}", blk, dom, tid)
    man = {"version": "bank_u_v1", "protocol": "docs/insights/FORK_PROTOCOL.md §15 + amendment 1 (W70)",
           "snapshot": {"id": snap.get("snapshot_id"), "sha256": hashlib.sha256(Path(a.snapshot).read_bytes()).hexdigest()},
           "sampling": "uniform within trajectory: t = floor(u * n_decisions), u = sha256('bank-u-v1|run|domain|task')[:12]/16^12; no stratification",
           "q0_rule": "U2 rows with sha256('bank-u-q0-v1|' + state_key)[:12]/16^12 < 0.25; Q0 = <model> gptq_w4_d1",
           "cells": list(CELLS), "models": list(MODELS), "blocks": list(BLOCKS), "domains": list(DOMS),
           "n_rows": len(rows), "n_missing": sum(1 for r in rows if r["missing_reason"]), "rows": rows}
    out = ROOT / "manifests/fork/bank_u_v1.json"
    out.write_text(json.dumps(man, indent=1))
    by = {}
    for r in rows:
        k = (r["sub"], r["model"], r["block"])
        by.setdefault(k, [0, 0])
        by[k][0] += 1
        by[k][1] += bool(r["missing_reason"])
    for k, v in sorted(by.items(), key=str):
        print(k, "rows", v[0], "missing", v[1])
    print("wrote", out, "rows", len(rows), "missing", man["n_missing"], "q0", sum(1 for r in rows if r["q0"]))


if __name__ == "__main__":
    main()
