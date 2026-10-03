"""Bank U tasks (FORK_PROTOCOL §15 + amendment 1, W70): fork_driver mode bank_u, manifest manifests/fork/bank_u_v1.json.

  --gate        replay gate: q4 GPTQ-W4 d1, q4 KV8 (hooked serving), q8 AWQ-W4; 10 states per sub-bank (U1, U2B, U2Q) on f01,
                no-op run on every state (U1: Q->Q, U2B: B->B, U2Q with this cell = source: Q->Q)
  --blocks f01  bank tasks: one per model x cell x block (U1 + U2B + U2Q of that block), 10% no-op sample
  --q0          with --blocks: Q0 controller tasks (fork_driver mode bank_u_q0) for AWQ-W4 and KV8, each depending on its
                native bank_u task; B = BF16, Q = Q0 = <model> GPTQ-W4 d1 (for the GPTQ-W4 d1 cell the native arms are Q0)
B = BF16, Q = the cell's exact serving config (kvq_int8: KV INT8 hook). q4 on 1 GPU (B+Q, GPU_UTIL 0.44); q8 on 2 GPUs pinned
to node004/005/007. Priority -17.
  --nmp-phase2 CELL ..  W100r: the q8 reference cells (gptq_w4_d1 awq_w4 kvq_int8) on the new-method panel's phase 2
                (NEWMETHOD_PANEL_PROTOCOL §2.5, §5.5: "the reference cells run f04-f06 with the panel manifest like any other
                cell"; all or none): f04-f06 bank_u U2B + token scores, specs verbatim from
                `make_newmethod_panel.py spec --model q8 --cell <c> --phase 2`, Q = qrole (the Bank U serving config).
                No gate dependency (W100r-b): §5.5 is unconditional, the §5.3 cost has no gate time, and the reference
                cells' f01-f03 Bank U rows were admitted without nmp gates. --ref-gates adds both §2.4 gates as recorded
                checks only (gate_same fail_loud, autopilot_retry "no"; no task depends on them; needs a main-session ruling).
                Refused unless analysis/fork/newmethod/expansion_q8.json has expand = true and lists the cells in phase2_cells.
usage: python scripts/a6000/make_tasks_bank_u.py (--gate | --blocks f01 [f02 ...] | --nmp-phase2 CELL .. [--ref-gates])
       [--priority P] [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
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


def nmp_phase2(cells: list[str], prio: int, gates: bool = False) -> list[dict]:
    rp = ROOT / "analysis/fork/newmethod/expansion_q8.json"
    rec = json.load(open(rp)) if rp.exists() else {}
    if rec.get("expand") is not True or not set(cells) <= set(rec.get("phase2_cells", [])):
        raise SystemExit(f"phase 2 refused: expand={rec.get('expand')}, phase2_cells={rec.get('phase2_cells')}")
    note = "W100r q8 reference cell, nmp phase 2 (make_tasks_bank_u.py --nmp-phase2; NEWMETHOD_PANEL_PROTOCOL §2.5, §5.5)"
    B, T, i = {"ckpt": {"kind": "bf16"}}, [], 0
    for c in cells:
        sp = json.loads(subprocess.check_output([sys.executable, str(ROOT / "scripts/a6000/make_newmethod_panel.py"), "spec",
                                                 "--model", "q8", "--cell", c, "--phase", "2"], cwd=ROOT, text=True))
        get = lambda pre: next(v for k, v in sp.items() if k.startswith(pre))  # noqa: E731
        clean = lambda d: {k: v for k, v in d.items() if not k.startswith("_")}  # noqa: E731
        Qr = qrole("q8", c)
        g1, g2 = f"nmp_gate_same_q8_{c}", f"nmp_gate_bank_q8_{c}"
        mk = lambda tid, b, f, deps, k: {"id": tid, "kind": "fork", "model": "q8", "gpus": 2, "node": NODES[k % 3],  # noqa: E731
                                         "priority": prio, "deps": deps, "B": b, "Q": Qr, "fork": f, "note": note}
        if gates:  # recorded checks only: nothing depends on them, and a failure is never retried by the autopilot
            ng = {"autopilot_retry": "no: recorded fail_loud check, not a dependency (W100r-b)"}
            T += [dict(mk(g1, Qr, {**clean(get("gate_same")), "fail_loud": True}, [], i), **ng),
                  dict(mk(g2, B, clean(get("bank gate")), [], i + 1), **ng)]
        for j, (f, s) in enumerate(zip(get("panel tasks"), get("token scores"))):
            tid = f"nmp_tau2_q8_{c}_{f['blocks'][0]}"
            T += [mk(tid, B, clean(f), [], i + j), mk(tid.replace("nmp_tau2_", "nmp_score_", 1), B, clean(s), [tid], i + j)]
        i += 1
    return T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--blocks", nargs="*", default=[])
    ap.add_argument("--q0", action="store_true")
    ap.add_argument("--nmp-phase2", nargs="+", default=None, metavar="CELL")
    ap.add_argument("--ref-gates", action="store_true", help="--nmp-phase2: add the §2.4 gates as non-blocking recorded checks")
    ap.add_argument("--priority", type=int, default=-17, help="--nmp-phase2 tasks")
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
    if a.q0:
        T, i = [], 0
        for blk in a.blocks:
            for m in ("q4", "q8"):
                for c in ("awq_w4", "kvq_int8"):
                    spec = {"mode": "bank_u_q0", "manifest": MAN, "manifest_sha256": sha, "model": m, "cell": c, "blocks": [blk],
                            "native_out": f"analysis/fork/bank_u/{m}_{c}/{blk}", "concurrency": 8,
                            "out": f"analysis/fork/bank_u/q0/{m}_{c}/{blk}"}
                    T.append({"id": f"bank_u_q0_{m}_{c}_{blk}", "kind": "fork", "model": m, "gpus": 1 if m == "q4" else 2,
                              **({"gpu_util": 0.44} if m == "q4" else {"node": NODES[i % 3]}), "priority": -17,
                              "deps": [f"bank_u_{m}_{c}_{blk}"], "B": {"ckpt": {"kind": "bf16"}}, "Q": qrole(m, "gptq_w4_d1"),
                              "fork": spec, "note": "W70 Bank U Q0 controller (make_tasks_bank_u.py --q0; FORK_PROTOCOL §15 amendment 1)"})
                    i += 1
    if a.nmp_phase2:
        T = nmp_phase2(a.nmp_phase2, a.priority, a.ref_gates)
    for t in T:
        print(t["id"], t["gpus"], t.get("node", ""), t["fork"].get("blocks"), t["deps"])
    if a.write:
        n = 0
        for t in T:
            if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed", "deferred")):
                tmp = Q / "todo" / f".tmp_{t['id']}"  # atomic: never a partial *.json in todo
                tmp.write_text(json.dumps(t, indent=1))
                os.replace(tmp, Q / "todo" / f"{t['id']}.json")
                n += 1
        print("wrote", n)


if __name__ == "__main__":
    main()
