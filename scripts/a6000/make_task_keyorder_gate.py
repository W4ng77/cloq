"""ko-v1 gate task (docs/insights/KEYORDER_PERTURB_PROTOCOL.md, amendment 2026-10-05 gate). Writes nothing without --write.

One small fork task, mode keyorder, on 8 eligible states of one block (f01, Bank P group g1) of the frozen manifest
manifests/fork/keyorder_v1.json. States are chosen before any key-order suffix exists and without any outcome: within
f01, per domain, the lowest sha256("ko-v1-gate|<state_id>") (4 airline + 4 retail). Gate checks (all outcome-blind,
keyorder_arm.py writes them to keyorder_rows.jsonl / keyorder_summary.json):
  - every state rebuilds identically and a_K matches the manifest raw sha;
  - the untransformed Q -> Q re-run reproduces the original episode on all 8 states (noop_frac = 1.0, fork_driver.noop_check);
  - KQ executes with the scanner's tool messages, budget, prefix and initial env hash (identical env effects);
  - KQ's next prompt ids come from the server, match local rendering, equal the scanner prediction (and so differ from Q's);
  - Q's shadow regeneration of a_Q is identical; throughput (suffixes per hour) is recorded.
Gate outcomes live only in the gate directory, are not read before the protocol commit, and are never pooled with the
panel (the panel re-runs these states in its own directory).
Simulator: depends on the six tw-v1 panel tasks and runs at priority -15 (tw-v1: -21), so it never shares a GPU slot or
a simulator replica with tw-v1; --user-base can name another live replica outside node005/node006 instead.
usage: python scripts/a6000/make_task_keyorder_gate.py [--write] [--user-base URL]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_tasks_keyorder as MK  # noqa: E402

GROUP, BLOCK, PER_DOMAIN, GATE_ID = "g1", "f01", 4, "ko_gate_q8_gptq_w4_d1_f01"
FROZEN_MANIFEST_SHA = "cbf12188ca485c03ae600f484af43f0bd22c29dcc19d8fda4436a1a1870d28ce"  # protocol table


def pick(rows: list) -> list:
    key = lambda r: hashlib.sha256(f"ko-v1-gate|{r['state_id']}".encode()).hexdigest()
    out = []
    for dom in ("airline", "retail"):
        cand = sorted((r for r in rows if r["domain"] == dom), key=key)
        assert len(cand) >= PER_DOMAIN, (dom, len(cand))
        out += cand[:PER_DOMAIN]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--user-base", default="", help="live replica outside tw-v1's node005/node006 (then no tw-v1 deps)")
    a = ap.parse_args()
    mp = MK.ROOT / MK.MAN
    m_sha = hashlib.sha256(mp.read_bytes()).hexdigest()
    if m_sha != FROZEN_MANIFEST_SHA:
        raise SystemExit(f"manifest sha {m_sha} != protocol table {FROZEN_MANIFEST_SHA}")
    man = json.loads(mp.read_text())
    group = f"analysis/fork/dev/q8_gptq_w4_d1/{GROUP}"
    rows = [r for r in man["rows"] if r["eligible"] and r["group"] == group and r["block"] == BLOCK]
    sel = pick(rows)
    if a.user_base:
        import simreg
        r = simreg.by_url(a.user_base)
        if a.user_base in MK.TW_REPLICAS or r is None or not simreg.is_live(r):
            raise SystemExit(f"{a.user_base}: not a live replica outside tw-v1's {MK.TW_REPLICAS}")
        deps = []
    else:
        deps = list(MK.TW_TASKS)
    t = MK.task(GROUP, m_sha, deps, None, MK.PRIORITY, a.user_base)
    t["id"] = GATE_ID
    t["fork"].update({"state_ids": [r["state_id"] for r in sel], "noop_frac": 1.0, "resume": False, "concurrency": 4,
                      "out": f"analysis/fork/keyorder/gate/q8_gptq_w4_d1_{BLOCK}"})
    t["note"] = ("ko-v1 GATE (8 eligible f01 states, KQ + QQ no-op on all 8; outcome-blind checks and throughput only; "
                 "not pooled with the panel; KEYORDER_PERTURB_PROTOCOL.md amendment 2026-10-05)")
    t["autopilot_retry"] = "no (ko-v1 gate: a failed task is left for a human)"
    for r in sel:
        print(r["state_id"], r["domain"], r["task_id"], r["t"], r["n_keys"], r["n_next_q"])
    MK.put(t, a.write)
    if not a.write:
        print(json.dumps(t["fork"], indent=1)[:1500])


if __name__ == "__main__":
    main()
