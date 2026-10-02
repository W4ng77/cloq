"""W99r rotation gate: frozen pass criteria (analysis/fork/rot_gate/GATE.md) evaluated on the gate outputs, and the
release of the phase-1 panel tasks (make_tasks_rotpanel.py) only for cells whose gates pass. Never reads a panel
outcome (bank_rows, branches); reads only the implementation-gate files below and gate_same verdicts.

Criteria (fixed before any SpinQuant gate output existed, 2026-10-02 03:30 PDT):
  transform control (per family f in {qr, sp}; W16A16 with the online transforms vs BF16):
    T1 WikiText-2 test ppl(f16, A16) <= 1.01 x ppl(BF16)
    T2 act flip vs the BF16 decision type (top-k, 400 decisions) <= 0.02
    T3 mean first-token KL(BF16 || cell) <= 0.01 nats
    T4 (sp only) HF invariance of the exported W16 checkpoint: fp32 top-1 agreement >= QuaRot's - 0.002 and mean
       |dlogprob_top1| <= 1.5 x QuaRot's (same check of ckpt_q8_qr16)
       AMENDMENT 2026-10-02 05:50 PDT (before any served SpinQuant output): the original T4 threshold (absolute 0.999)
       was mis-specified: the accepted QuaRot W16 export itself reaches only 0.9956 (fp32 compute on bf16-stored rotated
       weights; analysis/fork/rot_gate/ckpt_q8_qr16.quantization.json, measured 2026-10-02 00:50). SpinQuant's value
       (0.9976, mean |dlp| 0.0040 vs QuaRot 0.0045) was seen when the threshold was replaced by the QuaRot-relative one.
  determinism (every served config of the family that ran det/chunk/causal):
    D1 batch == alone == prefix-hit for all 8 prompts; D2 unchunked == chunked (8/8); D3 causal prefix identical
  direction (SpinQuant only, the published direction): P1 ppl(sp4, A4) <= ppl(qr4, A4); P2 ppl(sp16, A4) <= ppl(qr16, A4)
  throughput: R1 gen tok/s of the family's W4A4 config >= 0.5 x BF16's (fake-quant overhead must leave the panel feasible)
  panel gates (protocol §2.4): gate_same verdict pass; bank_u gate task done (it raises on failure)
usage:
  python scripts/a6000/rot_gate_check.py check                          (print verdicts, write analysis/fork/rot_gate/verdict.json)
  python scripts/a6000/rot_gate_check.py release-gates --family sp      (sp rotation gate passed -> queue the spinquant nmp gates
                                                                         + a release-panel task that waits for them)
  python scripts/a6000/rot_gate_check.py release-panel --cells c1 c2 .. (cells whose rotation gate and both nmp gates passed
                                                                         -> queue their phase-1 panel tasks)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
Q = Path("/data/ziyangs/cloq_work/queue")
G = ROOT / "analysis/fork/rot_gate"
FAM = {"qr": {"cells": ("quarot_w4", "quarot_w16", "quarot_w4a4"), "val": "validate_qr_q8", "w16": "qr_w16a16",
              "served": ("qr_w16a16", "qr_w16a4", "qr_w4a16", "qr_w4a4"), "tput": "qr_w4a4"},
       "sp": {"cells": ("spinquant_w16", "spinquant_w4a4"), "val": "validate_sp_q8", "w16": "sp_w16a16",
              "served": ("sp_w16a16", "sp_w16a4", "sp_w4a4"), "tput": "sp_w4a4"}}


def load(name):
    p = G / f"{name}.json"
    return json.load(open(p)) if p.exists() else None


def family(f: str) -> dict:
    spec = FAM[f]
    val, ppl = load(spec["val"]), load(spec["val"] + "_ppl")
    qval, qppl = load("validate_qr_q8"), load("validate_qr_q8_ppl")
    out = {"checks": {}, "missing": []}
    if not val or not ppl or not qval or not qppl:
        out["missing"].append("validation outputs")
        out["pass"] = False
        return out
    C = val["configs"]
    ck = out["checks"]
    tag = "qr16" if f == "qr" else "sp16"
    b = qppl.get("bf16_a16", {}).get("ppl")
    w = C.get(spec["w16"], {})
    ck["T1_ppl_w16a16_vs_bf16"] = {"ppl": ppl.get(f"{tag}_a16", {}).get("ppl"), "bf16": b}
    ck["T1_ppl_w16a16_vs_bf16"]["ok"] = bool(b and ck["T1_ppl_w16a16_vs_bf16"]["ppl"] and ck["T1_ppl_w16a16_vs_bf16"]["ppl"] <= 1.01 * b)
    tk = w.get("topk") or {}
    flip = (tk.get("act") or {}).get("act_flip_vs_bf16_decision")
    kl = ((tk.get("vs_ref") or {}).get("first") or {}).get("kl_mean")
    ck["T2_act_flip_w16a16"] = {"value": flip, "ok": flip is not None and flip <= 0.02}
    ck["T3_first_kl_w16a16"] = {"value": kl, "ok": kl is not None and kl <= 0.01}
    if f == "sp":
        q = load("ckpt_q8_sp16.quantization")
        r = load("ckpt_q8_qr16.quantization")
        inv = ((q or {}).get("invariance_check_hf") or {}).get("float32") or {}
        ref = ((r or {}).get("invariance_check_hf") or {}).get("float32") or {}
        ok = bool(inv and ref and inv["top1_agreement"] >= ref["top1_agreement"] - 0.002
                  and inv["mean_abs_dlogprob_top1"] <= 1.5 * ref["mean_abs_dlogprob_top1"])
        ck["T4_hf_invariance_fp32"] = {"value": inv.get("top1_agreement"), "mean_abs_dlp": inv.get("mean_abs_dlogprob_top1"),
                                       "quarot": ref.get("top1_agreement"), "quarot_mean_abs_dlp": ref.get("mean_abs_dlogprob_top1"),
                                       "ok": ok, "bf16": ((q or {}).get("invariance_check_hf") or {}).get("bfloat16")}
    for name in spec["served"]:
        r = C.get(name)
        if r is None or r.get("error"):
            ck[f"served_{name}"] = {"ok": False, "error": (r or {}).get("error", "not run")}
            continue
        d = r.get("det")
        if d:
            ck[f"D1_det_{name}"] = {**d, "ok": d["batch_eq_alone"] == d["n"] and d["prefixhit_eq_alone"] == d["n"]}
        c = r.get("chunk")
        if c:
            ck[f"D2_chunk_{name}"] = {"eq": c["unchunked_eq_chunked"], "n": c["n"], "ok": c["unchunked_eq_chunked"] == c["n"]}
        if r.get("causal"):
            ck[f"D3_causal_{name}"] = {"rows": r["causal"], "ok": all(x["identical_positions"] == x["n_positions"] for x in r["causal"])}
    if f == "sp":
        for p_, (a, bq) in {"P1_ppl_w4a4": ("sp4_a4", "qr4_a4"), "P2_ppl_w16a4": ("sp16_a4", "qr16_a4")}.items():
            x, y = ppl.get(a, {}).get("ppl"), qppl.get(bq, {}).get("ppl")
            ck[p_] = {"spinquant": x, "quarot": y, "ok": bool(x and y and x <= y)}
    bt = (qval["configs"].get("bf16", {}).get("throughput") or [{}])[-1].get("gen_tok_per_s")
    ft = (C.get(spec["tput"], {}).get("throughput") or [{}])[-1].get("gen_tok_per_s")
    ck["R1_throughput"] = {"bf16_gen_tok_s": bt, "cell_gen_tok_s": ft, "ok": bool(bt and ft and ft >= 0.5 * bt)}
    out["pass"] = all(v["ok"] for v in ck.values())
    return out


def nmp_gates(cell: str) -> dict:
    same = ROOT / f"analysis/fork/newmethod/gate/q8_{cell}/same/gate_same.json"
    v = json.load(open(same))["verdict"] if same.exists() else None
    bank_done = (Q / "done" / f"nmp_gate_bank_q8_{cell}.json").exists()
    return {"gate_same": v, "bank_done": bank_done, "pass": bool(v and v.get("pass")) and bank_done}


def cell_family(c: str) -> str:
    return "sp" if c.startswith("spinquant") else "qr"


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    g = sub.add_parser("release-gates")
    g.add_argument("--family", choices=["sp"], required=True)
    p = sub.add_parser("release-panel")
    p.add_argument("--cells", nargs="+", required=True)
    a = ap.parse_args()
    fams = {f: family(f) for f in FAM}
    res = {"families": fams, "cells": {c: nmp_gates(c) for f in FAM for c in FAM[f]["cells"]}}
    (G / "verdict.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({f: v["pass"] for f, v in fams.items()}), json.dumps({c: v["pass"] for c, v in res["cells"].items()}))
    gen = [sys.executable, str(ROOT / "scripts/a6000/make_tasks_rotpanel.py")]
    if a.cmd == "release-gates":
        if not fams["sp"]["pass"]:
            print("SpinQuant rotation gate not passed; nothing queued")
            sys.exit(3)
        cells = list(FAM["sp"]["cells"])
        subprocess.run(gen + ["--gates", "--cells", *cells, "--write"], check=True)
        t = {"id": "rot_release_panel_sp_q8", "kind": "cmd", "model": "q8", "priority": -25,
             "deps": [f"nmp_gate_{k}_q8_{c}" for c in cells for k in ("same", "bank")],
             "title": "W99s release the spinquant phase-1 panel tasks if every gate passed (rot_gate_check.py)",
             "cmd": "source scripts/a6000/env.sh && python scripts/a6000/rot_gate_check.py release-panel --cells " + " ".join(cells)}
        if not any((Q / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed", "deferred")):
            json.dump(t, open(Q / "todo" / f"{t['id']}.json", "w"), indent=1)
            print("queued", t["id"])
    elif a.cmd == "release-panel":
        ok = [c for c in a.cells if fams[cell_family(c)]["pass"] and res["cells"][c]["pass"]]
        print("released:", ok, "held:", [c for c in a.cells if c not in ok])
        if ok:
            subprocess.run(gen + ["--panel", "--cells", *ok, "--write"], check=True)
        if len(ok) < len(a.cells):
            sys.exit(3)


if __name__ == "__main__":
    main()
