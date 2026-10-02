"""Queue the KIVI cells on the new-method common panel (docs/insights/NEWMETHOD_PANEL_PROTOCOL.md, nmp-v1; W99u).

Cells kivi_k4v4 / kivi_k2v2 = BF16 weights + activations, KIVI KV cache (scripts/a6000/pyhooks/cloq_kivi.py) with the
paper's settings: group 32, residual 128 (W99t gate: analysis/fork/kivi_gate/GATE.md). Specs come verbatim from
`make_newmethod_panel.py spec` (phase 1 = f01-f03 only; expansion is decided centrally). Per cell:
  nmp_gate_same_q8_<cell>      gate_same, foreign states (B = Q = this cell)
  nmp_gate_bank_q8_<cell>      bank_u gate (10 U2B rows of f01, noop_frac 1.0)
  nmp_tau2_q8_<cell>_<blk>     panel A, deps both gates
  nmp_score_q8_<cell>_<blk>    token scores (KLu), dep the panel task
  ext_q8_<cell>_bfcl_nmp1      BFCL closed-loop Q run on the 200 panel items, deps both gates
  nmp_bfcl_q8_<cell>_<cat>     fork_ext dev per category, deps the BFCL run + ext_q8_bf16_bfcl_eval

usage: python scripts/a6000/make_tasks_kivi.py --cells kivi_k4v4,kivi_k2v2 [--write] [--priority -24]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
QUEUE = Path("/data/ziyangs/cloq_work/queue")
BITS = {"kivi_k4v4": 4, "kivi_k2v2": 2}
NOTE = "W99u KIVI on the nmp-v1 panel (make_tasks_kivi.py; NEWMETHOD_PANEL_PROTOCOL.md)"


def role(cell):
    b = str(BITS[cell])
    return {"ckpt": {"kind": "bf16"}, "serve_env": {"CLOQ_PYHOOKS": "1", "CLOQ_KIVI_KBITS": b, "CLOQ_KIVI_VBITS": b,
                                                    "CLOQ_KIVI_GROUP": "32", "CLOQ_KIVI_RESID": "128"}}


def spec(cell):
    out = subprocess.run([sys.executable, str(ROOT / "scripts/a6000/make_newmethod_panel.py"), "spec", "--model", "q8",
                          "--cell", cell], capture_output=True, text=True, check=True, cwd=ROOT).stdout
    return json.loads(out)


def tasks(cell, prio):
    s = spec(cell)
    get = lambda pre: next(v for k, v in s.items() if k.startswith(pre))  # noqa: E731
    Q, B = role(cell), {"ckpt": {"kind": "bf16"}}
    clean = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}  # noqa: E731
    g1, g2 = f"nmp_gate_same_q8_{cell}", f"nmp_gate_bank_q8_{cell}"
    T = [
        {"id": g1, "kind": "fork", "model": "q8", "gpus": 2, "priority": prio, "deps": [], "B": Q, "Q": Q,
         "fork": clean(get("gate_same")), "note": NOTE},
        {"id": g2, "kind": "fork", "model": "q8", "gpus": 2, "priority": prio, "deps": [], "B": B, "Q": Q,
         "fork": clean(get("bank gate")), "note": NOTE},
    ]
    for f in get("panel tasks"):
        blk = f["blocks"][0]
        T.append({"id": f"nmp_tau2_q8_{cell}_{blk}", "kind": "fork", "model": "q8", "gpus": 2, "priority": prio,
                  "deps": [g1, g2], "B": B, "Q": Q, "fork": clean(f), "note": NOTE})
    for f in get("token scores"):
        blk = f["blocks"][0]
        T.append({"id": f"nmp_score_q8_{cell}_{blk}", "kind": "fork", "model": "q8", "gpus": 2, "priority": prio,
                  "deps": [f"nmp_tau2_q8_{cell}_{blk}"], "B": B, "Q": Q, "fork": clean(f), "note": NOTE})
    r = get("BFCL closed-loop")
    T.append({"id": r["run_id"], "kind": "eval", "env": "bfcl", "model": "q8", "arm": cell, "priority": prio,
              "deps": [g1, g2], "serve_env": Q["serve_env"], "ckpt": Q["ckpt"], "domains": r["domains"],
              "runs": [{"run_id": r["run_id"], "task_file": r["task_file"], "subset": r["subset"]}], "note": NOTE})
    for f in get("BFCL fork tasks"):
        cat = f["out"].rsplit(f"bfcl_q8_{cell}_", 1)[1]
        T.append({"id": f"nmp_bfcl_q8_{cell}_{cat}", "kind": "fork", "env": "bfcl", "model": "q8", "gpus": 2,
                  "priority": prio, "deps": [r["run_id"], "ext_q8_bf16_bfcl_eval"], "B": B, "Q": Q, "fork": clean(f),
                  "note": NOTE})
    return T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="kivi_k4v4,kivi_k2v2")
    ap.add_argument("--priority", type=int, default=-24)
    ap.add_argument("--only", default=None, help="comma list of task-id prefixes to write (default: all)")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    for cell in a.cells.split(","):
        for t in tasks(cell, a.priority):
            if a.only and not any(t["id"].startswith(p) for p in a.only.split(",")):
                continue
            exists = [d for d in ("todo", "running", "done", "failed", "deferred") if (QUEUE / d / f"{t['id']}.json").exists()]
            print(("SKIP (exists in %s) " % exists if exists else "") + t["id"], t.get("deps"))
            if a.write and not exists:
                (QUEUE / "todo" / f"{t['id']}.json").write_text(json.dumps(t, indent=1))


if __name__ == "__main__":
    main()
