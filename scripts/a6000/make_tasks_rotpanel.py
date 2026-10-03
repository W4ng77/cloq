"""Rotation cells (QuaRot / SpinQuant, W99r/W99s) on the frozen new-method panel (docs/insights/NEWMETHOD_PANEL_PROTOCOL.md,
manifests/fork/newmethod_panel_v1.json). Wraps the specs of `make_newmethod_panel.py spec` in queue tasks with this
agent's Q roles; B = BF16. Never overwrites an existing task id; priority -25; q8 forks 2 GPUs pinned round-robin to
node004/005/007 (as every q8 fork).

Cells (Q role = checkpoint + serve_env; KV16 with the online Q/K rotation on = 'kv16r', as a6k2_q8_quarot_w4a16kv16r_*):
  quarot_w4       QuaRot-W4A16-KV16   (protocol cell)          random Hadamard R1, GPTQ-W4
  quarot_w16      QuaRot transform-path control (protocol cell), W16 A16
  quarot_w4a4     QuaRot-W4A4-KV16    (advisor config; A4 = per-token sym INT4, clip 0.9)
  spinquant_w16   SpinQuant transform-path control (protocol cell): learned R1/R2, W16 A16
  spinquant_w4a4  SpinQuant-W4A4-KV16 (advisor config): learned R1/R2 (cloq.spinquant learn, W16A4), GPTQ-W4, A4
The protocol's `spinquant_w4` (learned rotation at W4A16) is not built here: rotations learned at W16A16 are a
stationary point (the loss is rotation invariant), and the advisor's SpinQuant configuration is W4A4 (GATE.md).

  --gates   gate_same (foreign states, [run, domain] pairs) + bank_u gate per cell (protocol §2.4)
  --panel   phase-1 bank_u tasks f01-f03 (deps: both gates of the cell) + score tasks + BFCL nmp1 run + 4 fork_ext dev
  --panel --phase 2   W100r: f04-f06 bank_u + score tasks only (no gates, no BFCL; protocol §5), refused unless the
            written record analysis/fork/newmethod/expansion_q8.json has expand = true and lists the cell in phase2_cells
usage: python scripts/a6000/make_tasks_rotpanel.py (--gates | --panel [--phase 2]) --cells quarot_w4 ... [--priority P] [--write]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
MAN = "manifests/fork/newmethod_panel_v1.json"
MAN_SHA = "7534c6907fa68bc8dab48061d7a2944a719e6e2fa123b639e7a0674c5a6ca201"
OUT = "analysis/fork/newmethod"
NODES = ("node004", "node005", "node007")
PRIO = -25
SPIN_DIR = Path("/data/ziyangs/cloq_work/rot/spinquant_q8_a4_s0")
H = {"CLOQ_PYHOOKS": "1"}
KV16R = {"CLOQ_KVQ_BITS": "16", "CLOQ_KVQ_ROT": "qk", "CLOQ_KVQ_FMT": "quarot", "CLOQ_KVQ_KCLIP": "0.95", "CLOQ_KVQ_VCLIP": "0.95"}
A16 = {"CLOQ_AQ_BITS": "16", "CLOQ_AQ_HAD": "quarot"}
A4 = {"CLOQ_AQ_BITS": "4", "CLOQ_AQ_FMT": "sym_quarot", "CLOQ_AQ_CLIP": "0.9", "CLOQ_AQ_HAD": "quarot"}


def spin_ck(wbits: int) -> dict:
    learn = json.load(open(SPIN_DIR / "learn.json"))
    sha = hashlib.sha256((SPIN_DIR / "R.pt").read_bytes()).hexdigest()
    assert sha == learn["R_sha256"], "R.pt changed after learning"
    ck = {"kind": "spinquant", "wbits": wbits, "seed": 0, "rotations": str(SPIN_DIR / "R.pt"), "rotations_sha256": sha}
    return {**ck, "wmethod": "gptq"} if wbits < 16 else ck


def cells() -> dict:
    qr4 = {"kind": "quarot", "wbits": 4, "wmethod": "gptq", "seed": 0}
    qr16 = {"kind": "quarot", "wbits": 16, "seed": 0}
    out = {"quarot_w4": (qr4, {**H, **A16, **KV16R}), "quarot_w16": (qr16, {**H, **A16, **KV16R}),
           "quarot_w4a4": (qr4, {**H, **A4, **KV16R})}
    if (SPIN_DIR / "learn.json").exists() and (SPIN_DIR / "R.pt").exists():
        out["spinquant_w16"] = (spin_ck(16), {**H, **A16, **KV16R})
        out["spinquant_w4a4"] = (spin_ck(4), {**H, **A4, **KV16R})
    return out


def fork_task(tid, cell, i, B, Qr, spec, deps, note, env=None):
    t = {"id": tid, "kind": "fork", "model": "q8", "gpus": 2, "node": NODES[i % len(NODES)], "priority": PRIO, "deps": deps,
         "B": B, "Q": Qr, "fork": spec, "note": note}
    if env:
        t["env"] = env
        t.pop("node")
    return t


def gate_tasks(c: str, ck: dict, senv: dict, i: int) -> list[dict]:
    role = {"ckpt": ck, "serve_env": senv}
    src = "a6k2_q8_bfpair_f01"
    same = {"mode": "gate_same", "foreign_states": True, "q_blocks": [[src, "retail"], [src, "airline"]], "n_per_block": 3,
            "idcheck_n": 8, "concurrency": 8, "out": f"{OUT}/gate/q8_{c}/same"}
    bank = {"mode": "bank_u", "manifest": MAN, "manifest_sha256": MAN_SHA, "model": "q8", "cell": c, "blocks": ["f01"],
            "subs": ["U2B"], "limit_per_sub": 10, "noop_frac": 1.0, "concurrency": 8, "out": f"{OUT}/gate/q8_{c}/bank"}
    n = "W99r rotation cell on the new-method panel (make_tasks_rotpanel.py; NEWMETHOD_PANEL_PROTOCOL §2.4)"
    return [fork_task(f"nmp_gate_same_q8_{c}", c, i, role, role, same, [], n),
            fork_task(f"nmp_gate_bank_q8_{c}", c, i + 1, {"ckpt": {"kind": "bf16"}}, role, bank, [], n)]


def panel_tasks(c: str, ck: dict, senv: dict, i: int, phase: int = 1) -> list[dict]:
    role = {"ckpt": ck, "serve_env": senv}
    B = {"ckpt": {"kind": "bf16"}}
    gates = [f"nmp_gate_same_q8_{c}", f"nmp_gate_bank_q8_{c}"]
    n = f"W99s rotation cell, phase {phase} (make_tasks_rotpanel.py; NEWMETHOD_PANEL_PROTOCOL §2, §5, §6)"
    out = []
    for j, b in enumerate(("f01", "f02", "f03") if phase == 1 else ("f04", "f05", "f06")):
        spec = {"mode": "bank_u", "manifest": MAN, "manifest_sha256": MAN_SHA, "model": "q8", "cell": c, "blocks": [b],
                "subs": ["U2B"], "noop_frac": 0.1, "concurrency": 8, "out": f"{OUT}/tau2/q8_{c}/{b}"}
        out.append(fork_task(f"nmp_tau2_q8_{c}_{b}", c, i + j, B, role, spec, gates, n))
        sc = {"driver": "score", "mode": "score_states", "model": "q8", "cell": c, "blocks": [b],
              "bank_out": f"{OUT}/tau2/q8_{c}/{b}", "out": f"{OUT}/token_scores/q8_{c}/{b}", "concurrency": 4}
        out.append(fork_task(f"nmp_score_q8_{c}_{b}", c, i + j, B, role, sc, [f"nmp_tau2_q8_{c}_{b}"], n))
    if phase == 2:  # the BFCL panel has no expansion (protocol §5)
        return out
    rid = f"ext_q8_{c}_bfcl_nmp1"
    out.append({"id": rid, "kind": "eval", "env": "bfcl", "model": "q8", "arm": "rot", "ckpt": ck, "serve_env": senv,
                "domains": ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"], "priority": PRIO,
                "deps": gates, "runs": [{"run_id": rid, "task_file": MAN, "subset": "nmp_v1"}], "note": n})
    for k in ("base", "miss_param", "miss_func", "long_context"):
        spec = {"mode": "dev", "q_blocks": [f"{rid}:bfcl_{k}"], "noop_frac": 0.1, "concurrency": 12,
                "out": f"{OUT}/bfcl/bfcl_q8_{c}_{k}"}
        out.append(fork_task(f"nmp_bfcl_q8_{c}_{k}", c, i, B, role, spec, [rid, "ext_q8_bf16_bfcl_eval"], n, env="bfcl"))
    return out


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--gates", action="store_true")
    g.add_argument("--panel", action="store_true")
    ap.add_argument("--cells", nargs="+", required=True)
    ap.add_argument("--phase", type=int, default=1, choices=(1, 2), help="--panel: 2 = f04-f06 after the expansion record")
    ap.add_argument("--priority", type=int, default=PRIO)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    globals()["PRIO"] = a.priority  # read by fork_task at call time
    got = hashlib.sha256((ROOT / MAN).read_bytes()).hexdigest()
    assert got == MAN_SHA, f"panel manifest sha {got} != frozen {MAN_SHA}"
    if a.phase == 2:
        rp = ROOT / OUT / "expansion_q8.json"
        rec = json.load(open(rp)) if rp.exists() else {}
        if a.gates or rec.get("expand") is not True or not set(a.cells) <= set(rec.get("phase2_cells", [])):
            raise SystemExit(f"phase 2 refused: expand={rec.get('expand')}, phase2_cells={rec.get('phase2_cells')}")
    C = cells()
    tasks = []
    for i, c in enumerate(a.cells):
        ck, senv = C[c]
        tasks += gate_tasks(c, ck, senv, i) if a.gates else panel_tasks(c, ck, senv, i, a.phase)
    for t in tasks:
        print(t["id"], t["kind"], t.get("node", "-"), t["deps"])
    if not a.write:
        print(f"{len(tasks)} tasks (dry run)")
        return
    n = 0
    for t in tasks:
        if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed", "deferred")):
            tmp = Q / "todo" / f".tmp_{t['id']}"  # atomic: never a partial *.json in todo
            tmp.write_text(json.dumps(t, indent=1))
            os.replace(tmp, Q / "todo" / f"{t['id']}.json")
            n += 1
    print(f"wrote {n} tasks")


if __name__ == "__main__":
    main()
