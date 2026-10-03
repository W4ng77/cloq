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

--phase 2 (W100r): only nmp_tau2 / nmp_score for f04-f06 (deps: both gates, --gate-suffix _fx for the A4.2 gates), refused
unless the written record analysis/fork/newmethod/expansion_q8.json has expand = true and lists the cell in phase2_cells.

usage: python scripts/a6000/make_tasks_kivi.py --cells kivi_k4v4,kivi_k2v2 [--write] [--priority -24] [--phase 2 --score-priority P]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
QUEUE = Path("/data/ziyangs/cloq_work/queue")
BITS = {"kivi_k4v4": 4, "kivi_k2v2": 2, "kivi_k16v16": 16}  # k16v16: kernel-path control (protocol A4.1)
NOTE = "W99u KIVI on the nmp-v1 panel (make_tasks_kivi.py; NEWMETHOD_PANEL_PROTOCOL.md)"


def role(cell):
    b = str(BITS[cell])
    return {"ckpt": {"kind": "bf16"}, "serve_env": {"CLOQ_PYHOOKS": "1", "CLOQ_KIVI_KBITS": b, "CLOQ_KIVI_VBITS": b,
                                                    "CLOQ_KIVI_GROUP": "32", "CLOQ_KIVI_RESID": "128"}}


def spec(cell, phase=1):
    out = subprocess.run([sys.executable, str(ROOT / "scripts/a6000/make_newmethod_panel.py"), "spec", "--model", "q8",
                          "--cell", cell, "--phase", str(phase)], capture_output=True, text=True, check=True, cwd=ROOT).stdout
    return json.loads(out)


def tasks(cell, prio, gate_suffix="", gate_prio=None, phase=1, score_prio=None):
    s = spec(cell, phase)
    get = lambda pre: next(v for k, v in s.items() if k.startswith(pre))  # noqa: E731
    Q, B = role(cell), {"ckpt": {"kind": "bf16"}}
    clean = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}  # noqa: E731
    g1, g2 = f"nmp_gate_same_q8_{cell}{gate_suffix}", f"nmp_gate_bank_q8_{cell}{gate_suffix}"
    gp = prio if gate_prio is None else gate_prio
    gout = lambda f: dict(f, out=f["out"].replace(f"/q8_{cell}/", f"/q8_{cell}{gate_suffix}/"))  # noqa: E731  (A4.2)
    T = [
        {"id": g1, "kind": "fork", "model": "q8", "gpus": 2, "priority": gp, "deps": [], "B": Q, "Q": Q,
         "fork": gout(clean(get("gate_same"))), "note": NOTE},
        {"id": g2, "kind": "fork", "model": "q8", "gpus": 2, "priority": gp, "deps": [], "B": B, "Q": Q,
         "fork": gout(clean(get("bank gate"))), "note": NOTE},
    ]
    for f in get("panel tasks"):
        blk = f["blocks"][0]
        T.append({"id": f"nmp_tau2_q8_{cell}_{blk}", "kind": "fork", "model": "q8", "gpus": 2, "priority": prio,
                  "deps": [g1, g2], "B": B, "Q": Q, "fork": clean(f), "note": NOTE})
    for f in get("token scores"):
        blk = f["blocks"][0]
        T.append({"id": f"nmp_score_q8_{cell}_{blk}", "kind": "fork", "model": "q8", "gpus": 2,
                  "priority": prio if score_prio is None else score_prio,
                  "deps": [f"nmp_tau2_q8_{cell}_{blk}"], "B": B, "Q": Q, "fork": clean(f), "note": NOTE})
    if phase == 2:  # f04-f06 panel + scores only: gates already ran, the BFCL panel has no expansion (protocol §5)
        return [t for t in T if t["id"].startswith(("nmp_tau2_", "nmp_score_"))]
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
    ap.add_argument("--gate-suffix", default="", help="gate task-id / output-dir suffix, e.g. _fx (protocol A4.2)")
    ap.add_argument("--gate-priority", type=int, default=None)
    ap.add_argument("--no-bfcl", action="store_true", help="tau2 panel only (A4.1: kivi_k16v16)")
    ap.add_argument("--phase", type=int, default=1, choices=(1, 2), help="2 = f04-f06 panel + scores after the expansion record")
    ap.add_argument("--score-priority", type=int, default=None, help="token-score tasks (default --priority)")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if a.phase == 2:
        rp = ROOT / "analysis/fork/newmethod/expansion_q8.json"
        rec = json.load(open(rp)) if rp.exists() else {}
        if rec.get("expand") is not True or not set(a.cells.split(",")) <= set(rec.get("phase2_cells", [])):
            raise SystemExit(f"phase 2 refused: expand={rec.get('expand')}, phase2_cells={rec.get('phase2_cells')}")
    for cell in a.cells.split(","):
        for t in tasks(cell, a.priority, a.gate_suffix, a.gate_priority, a.phase, a.score_priority):
            if a.no_bfcl and "bfcl" in t["id"]:
                continue
            if a.only and not any(t["id"].startswith(p) for p in a.only.split(",")):
                continue
            exists = [d for d in ("todo", "running", "done", "failed", "deferred") if (QUEUE / d / f"{t['id']}.json").exists()]
            print(("SKIP (exists in %s) " % exists if exists else "") + t["id"], t.get("deps"))
            if a.write and not exists:
                tmp = QUEUE / "todo" / f".tmp_{t['id']}"  # atomic: never a partial *.json in todo
                tmp.write_text(json.dumps(t, indent=1))
                tmp.replace(QUEUE / "todo" / f"{t['id']}.json")


if __name__ == "__main__":
    main()
