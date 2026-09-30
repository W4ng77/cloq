"""W x A x KV 2^3 closed-loop matrix on the QuaRot-rotated model (W47; docs/insights/METHOD_FIDELITY.md): paired success and
turnover vs BF16 per cell, factorial main effects and interactions of W, A, KV.

Runs (all must be admitted in the integrity-gated snapshot, same prompt nonce per block):
  cell     a6k2_<model>_quarot_w{16,4}a{16,4}kv{16,4}_<block>     (8 cells, all with QuaRot online Hadamards)
  anchors  a6k2_<model>_aq_a8_<block>, a6k2_<model>_sq_w8a8_<block>, a6k2_<model>_gptq_w4_d1_<block>
  BF16     a6k2_<model>_bfpair_<block>                              (plain, unrotated BF16 on the same nonce)
Unit = task x block (task = domain:task_id); infrastructure episodes excluded (snapshot infra_missing). Y = DB success for
retail/airline, official task-basis success for telecom (analysis/fork/analyze_dev.success).
Per cell (and anchor), over units where the cell and BF16 both exist: success, cell - BF16, turnover P(Y != Y_BF16) with
fix (cell 1, BF16 0) and break (cell 0, BF16 1).
Factorial (units where all 8 cells exist; codes s = +1 for 4-bit, -1 for 16-bit): effect_X = (1/4) sum_i s_X(i) Y_i
(= mean Y at X=4 minus mean Y at X=16), two-way XY = (1/4) sum s_X s_Y Y_i (= half the difference of the X effect at
Y=4 and at Y=16), three-way WAKV = (1/4) sum s_W s_A s_KV Y_i. Also the additivity gap for the full cell:
Y(W4A4KV4) - Y(W16A16KV16) minus the sum of the three single-factor effects taken from the W16A16KV16 corner.
Intervals: hierarchical bootstrap of analysis/fork/analyze_dev.py (tasks, then blocks within task; B = 2000; seed
20261001; one set of draws shared by all statistics, so contrasts are paired).
Idempotent: an output with the same input fingerprint (script, snapshot, every run file sha) is not rewritten.

usage: python analysis/ahook/analyze_wakv.py --snapshot <snapshot.json> [--models q4]
-> analysis/ahook/out/wakv_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis/fork"))
from analyze_dev import B_BOOT, SEED, Boot, sha256, summarise  # noqa: E402
from analyze_restore_eval import episodes  # noqa: E402

OUT = ROOT / "analysis/ahook/out"
CELL_RE = re.compile(r"^a6k2_(q\d+)_(quarot_w(16|4)a(16|4)kv(16|4)|aq_a8|sq_w8a8|gptq_w4_d1)_(f\d\d)$")
FACT = [f"quarot_w{w}a{a}kv{k}" for w in (16, 4) for a in (16, 4) for k in (16, 4)]
SIGN = {c: {"W": 1 if "_w4" in c else -1, "A": 1 if "a4kv" in c else -1, "KV": 1 if c.endswith("kv4") else -1} for c in FACT}
TERMS = ["W", "A", "KV", "W:A", "W:KV", "A:KV", "W:A:KV"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--B", type=int, default=B_BOOT)
    a = ap.parse_args()
    t0 = time.time()
    snap = json.load(open(a.snapshot))
    fz, det = snap["frozen"], snap.get("detail", {})
    runs = defaultdict(dict)  # model -> {(cell, block): run id}
    for rid in fz:
        m = CELL_RE.match(rid)
        if m and (not a.models or m.group(1) in a.models):
            runs[m.group(1)][(m.group(2), m.group(6))] = rid
    if not any(any(c.startswith("quarot_") for c, _ in v) for v in runs.values()):
        print("analyze_wakv: no admitted QuaRot W x A x KV runs (a6k2_<model>_quarot_w*a*kv*_<block>) in the snapshot yet; nothing to do.")
        return
    files, skipped, Y = {}, [], defaultdict(dict)  # Y[(model, task, block)][cell or 'B'] = 0/1
    for model, rr in sorted(runs.items()):
        for (cell, blk), rid in sorted(rr.items()):
            if cell == "gptq_w4_d1" and not any(c.startswith("quarot_") and b == blk for c, b in rr):
                continue  # anchor only on blocks where the matrix ran
            bid = f"a6k2_{model}_bfpair_{blk}"
            for dom in sorted(fz[rid]):
                if dom not in (fz.get(bid) or {}):
                    skipped.append({"run": rid, "domain": dom, "reason": "BF16 run not admitted"})
                    continue
                nn = {fz[rid][dom].get("prompt_nonce"), fz[bid][dom].get("prompt_nonce")}
                if len(nn) != 1:
                    skipped.append({"run": rid, "domain": dom, "reason": f"nonce mismatch {sorted(map(str, nn))}"})
                    continue
                e = episodes(rid, dom, fz[rid][dom], (det.get(rid) or {}).get(dom))
                eb = episodes(bid, dom, fz[bid][dom], (det.get(bid) or {}).get(dom))
                if e is None or eb is None:
                    skipped.append({"run": rid, "domain": dom, "reason": "trajectory differs from the snapshot"})
                    continue
                for r in (rid, bid):
                    files[f"runs/{r}/{dom}/trajectory.jsonl"] = fz[r][dom]["files"]["trajectory.jsonl"]["sha256"]
                for task in set(e) & set(eb):
                    Y[(model, task, blk)][cell] = e[task]
                    Y[(model, task, blk)]["B"] = eb[task]
    script_sha = sha256(__file__)
    fp = hashlib.sha256(json.dumps({"script": script_sha, "dev": sha256(ROOT / "analysis/fork/analyze_dev.py"),
                                    "restore": sha256(ROOT / "analysis/fork/analyze_restore_eval.py"),
                                    "snapshot": sha256(a.snapshot), "files": files, "models": a.models, "B": a.B},
                                   sort_keys=True).encode()).hexdigest()[:16]
    OUT.mkdir(parents=True, exist_ok=True)
    for p in sorted(OUT.glob("wakv_*.json")):
        try:
            if json.load(open(p)).get("input_fingerprint") == fp:
                print(f"analyze_wakv: unchanged inputs (fingerprint {fp}); existing output {p.relative_to(ROOT)}")
                return
        except Exception:
            continue
    res_models = {}
    for model in sorted({k[0] for k in Y}):
        units = [{"task": t, "block": b, "Y": y} for (m, t, b), y in Y.items() if m == model]
        bo = defaultdict(set)
        for u in units:
            bo[u["task"]].add(u["block"])
        boot = Boot(sorted(bo), {k: sorted(v) for k, v in bo.items()}, B=a.B)

        def stat(us, fn):
            for u in us:
                u["E"] = {"x": fn(u["Y"])}
            X, M = boot.arrays(us, "x")
            return boot.task_mean(X, M)

        cells = {}
        for cell in FACT + ["aq_a8", "sq_w8a8", "gptq_w4_d1"]:
            us = [u for u in units if cell in u["Y"]]
            if not us:
                continue
            fns = {"success_cell": lambda y: y[cell], "success_B": lambda y: y["B"], "cell_minus_B": lambda y: y[cell] - y["B"],
                   "turnover_vs_B": lambda y: int(y[cell] != y["B"]), "fix_vs_B": lambda y: int(y[cell] == 1 and y["B"] == 0),
                   "break_vs_B": lambda y: int(y[cell] == 0 and y["B"] == 1)}
            cells[cell] = {"n_units": len(us), "n_tasks": len({u["task"] for u in us}), "blocks": sorted({u["block"] for u in us}),
                           "pp": {k: summarise(*stat(us, f)) for k, f in fns.items()}}
        full = [u for u in units if all(c in u["Y"] for c in FACT)]
        fact = None
        if full:
            def contrast(term):
                fs = term.split(":")
                return lambda y: sum(y[c] * math.prod(SIGN[c][f] for f in fs) for c in FACT) / 4
            fact = {"n_units": len(full), "n_tasks": len({u["task"] for u in full}),
                    "effects_pp": {t: summarise(*stat(full, contrast(t))) for t in TERMS}}
            base = "quarot_w16a16kv16"
            single = {"W": "quarot_w4a16kv16", "A": "quarot_w16a4kv16", "KV": "quarot_w16a16kv4"}
            fact["additivity_gap_pp"] = summarise(*stat(full, lambda y: (y["quarot_w4a4kv4"] - y[base])
                                                         - sum(y[c] - y[base] for c in single.values())))
            fact["rotated_control_minus_B_pp"] = summarise(*stat(full, lambda y: y[base] - y["B"]))
        res_models[model] = {"n_units": len(units), "cells": cells, "factorial": fact}
    res = {"analysis": "analysis/ahook/analyze_wakv.py", "input_fingerprint": fp,
           "snapshot": {"id": snap.get("snapshot_id"), "path": str(Path(a.snapshot).resolve()), "sha256": sha256(a.snapshot)},
           "script": {"path": str(Path(__file__).resolve()), "sha256": script_sha,
                      "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "bootstrap": {"B": a.B, "seed": SEED, "scheme": "tasks, then blocks within task; draws shared by all statistics"},
           "coding": "s = +1 at 4 bits, -1 at 16 bits; effect = (1/4) sum s Y over the 8 cells",
           "models": res_models, "skipped": skipped, "input_files": files, "seconds": round(time.time() - t0, 1)}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"wakv_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))

    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"
    L = [f"**TL;DR** W x A x KV matrix (QuaRot-rotated) vs BF16 on shared nonces; snapshot {res['snapshot']['id']}; "
         f"{len(skipped)} run-domains skipped.", "", f"# W x A x KV closed-loop matrix ({res['utc']})", "",
         f"Full numbers: `{jp.relative_to(ROOT)}`. pp; 95% hierarchical bootstrap.", ""]
    for model, r in res_models.items():
        L += [f"## {model}", "", "| cell | units | success | BF16 | cell - BF16 | turnover vs BF16 (fix/break) |", "|---|---|---|---|---|---|"]
        for c, v in r["cells"].items():
            p = v["pp"]
            L.append(f"| {c} | {v['n_units']} | {p['success_cell']['est']:.1f} | {p['success_B']['est']:.1f} | {f(p['cell_minus_B'])} | "
                     f"{p['turnover_vs_B']['est']:.1f} ({p['fix_vs_B']['est']:.1f}/{p['break_vs_B']['est']:.1f}) |")
        if r["factorial"]:
            fa = r["factorial"]
            L += ["", f"Factorial ({fa['n_units']} units with all 8 cells):", "", "| term | effect (pp) |", "|---|---|"]
            L += [f"| {t} | {f(fa['effects_pp'][t])} |" for t in TERMS]
            L += [f"| additivity gap (W4A4KV4) | {f(fa['additivity_gap_pp'])} |",
                  f"| rotated control - BF16 | {f(fa['rotated_control_minus_B_pp'])} |"]
        L.append("")
    (OUT / f"wakv_{utc}.md").write_text("\n".join(L) + "\n")
    print(f"analyze_wakv: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


if __name__ == "__main__":
    main()
