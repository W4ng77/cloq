"""W100u-r (COMMONSTATE_SOURCES_PROTOCOL.md deviation D2.5): compare the checkpoint sha256 and numerics canary that each
amendment-A1 task's servers recorded (logs/tasks/<id>.servers.json, written at server start, or the done record) with the
design manifests, before the dependent GPU-hours are spent. Reads no outcome.

usage: python scripts/a6000/commonstate_ckpt_check.py [--hold]
  --hold  on a mismatch, move the design's tasks still in queue/todo/ to queue/deferred/ (atomic rename; a task a worker
          already claimed is left alone) and append the reason to logs/commonstate_ckpt_check.log. Exit 2 on any mismatch.
This is a hold, not an admission rule: admission stays with analyze_commonstate.py (A1.1).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path("/data/ziyangs/cloq_work")
Q = WORK / "queue"
TYPES = {"d2_bf16": {"B": "bf16", "Q": "gptq_w4_d2"}, "d2_d1": {"B": "gptq_w4_d2", "Q": "gptq_w4_d1"}}
DESIGNS = {"q8ext": "manifests/fork/commonstate_q8ext_v1.json", "q4": "manifests/fork/commonstate_q4_v1.json"}


def tasks(dm: dict) -> dict[str, dict]:
    m, out = dm["model"], {}
    if "ref_task" in dm:
        for b in dm["blocks"]:
            out[dm["ref_task"]["id"].format(blk=b)] = {"B": "bf16", "Q": dm["ref_task"]["cell"]}
    if "gate_dir" in dm:
        for t, roles in TYPES.items():
            out[f"cs_gate_{m}_{t}"] = roles
    for b in dm["blocks"]:
        for t, roles in TYPES.items():
            out[f"cs_{m}_{t}_{b}"] = roles
    return out


def recorded(tid: str) -> dict | None:
    p = WORK / "logs" / "tasks" / f"{tid}.servers.json"
    if p.exists():
        return json.loads(p.read_text())
    d = Q / "done" / f"{tid}.json"
    return ((json.loads(d.read_text()).get("result") or {}).get("servers")) if d.exists() else None


def check(dm: dict) -> tuple[list[dict], list[str]]:
    rows, bad = [], []
    for tid, roles in tasks(dm).items():
        srv = recorded(tid)
        if srv is None:
            rows.append({"task": tid, "status": "no server record yet"})
            continue
        r = {"task": tid, "host": srv.get("host"), "status": "ok"}
        for role, src in roles.items():
            got_c, got_k = (srv.get(role) or {}).get("canary"), (srv.get(role) or {}).get("ckpt_sha256")
            want_c, want_k = dm["canaries"][src], dm["ckpt_sha256"].get(src)
            r[role] = {"src": src, "canary_ok": got_c == want_c, "ckpt_ok": None if want_k is None else got_k == want_k,
                       "canary": got_c, "ckpt_sha256": (got_k or "")[:12]}
            if got_c != want_c or (want_k is not None and got_k != want_k):
                r["status"] = "MISMATCH"
        if r["status"] != "ok":
            bad.append(tid)
        rows.append(r)
    return rows, bad


def hold(design: str, dm: dict, bad: list[str]) -> list[str]:
    moved = []
    for tid in tasks(dm):
        src, dst = Q / "todo" / f"{tid}.json", Q / "deferred" / f"{tid}.json"
        try:
            os.rename(src, dst)  # atomic; FileNotFoundError if a worker claimed it first
        except FileNotFoundError:
            continue
        moved.append(tid)
    with open(WORK / "logs" / "commonstate_ckpt_check.log", "a") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "design": design, "mismatch": bad, "moved_to_deferred": moved,
                            "note": "D2.5 hold: checkpoint sha256 / canary differs from the design manifest; main session decides"}) + "\n")
    return moved


def main() -> int:
    rc = 0
    for design, path in DESIGNS.items():
        dm = json.loads((ROOT / path).read_text())
        rows, bad = check(dm)
        print(f"== {design}: {len(rows) - sum(r['status'] == 'no server record yet' for r in rows)} recorded, {len(bad)} mismatch")
        for r in rows:
            print("  " + json.dumps(r))
        if bad:
            rc = 2
            if "--hold" in sys.argv[1:]:
                print(f"  held (moved to deferred/): {hold(design, dm, bad)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
