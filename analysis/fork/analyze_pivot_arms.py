"""W55 step 2 analysis: action reversion at the pivot per restoration arm, and the pre-declared arm selection for step 3
(docs/insights/FORK_PROTOCOL.md §13, fixed in commit 6c926c2 before any pivot-arm outcome).

Input: analysis/fork/pivot_arms/<model>_<cell>/<arm>.jsonl (fork_driver mode pivot_arms). Unit = frozen state (task x
block). Per cell x arm:
  - r_B   P(arm's action semantically equals a_B);
  - r_Q   P(it equals a_Q);
  - other P(it equals neither);
  - exact rates.
Pipeline controls: `none` must reproduce a_Q exactly and `all` must reproduce a_B exactly.
Selection (only the GPTQ-W3 cells, q4 and q8, equal weight):
  delta   = r_B(arm) - r_B(byte-matched random seed 1), paired on the same states;
  interval hierarchical bootstrap (tasks, then blocks within task; B = 2000; seed 20261001), with draws shared across the
          two cells (same task ids and nonces);
  eligible if the one-sided 95% LB > 0 and delta >= 5 pp;
  choose  the largest delta, plus a second arm if also eligible (max 2); ties go to fewer restored bytes.

usage: python analysis/fork/analyze_pivot_arms.py [--B 2000]
-> analysis/fork/out/pivot_arms_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
IN = ROOT / "analysis/fork/pivot_arms"
CTRL = {"early": "rand_third_s1", "middle": "rand_third_s1", "late": "rand_third_s1", "attn": "rand_attn_s1", "mlp": "rand_mlp_s1"}
CANDIDATES = {**CTRL, **{f"recal_{k}": f"recal_{v}" for k, v in CTRL.items()}}
SEL_CELLS = ("q4:gptq_w3", "q8:gptq_w3")
BLOCK_RE = re.compile(r"_(q\d+|f\d\d)$")


def budget_bytes(model: str, arm: str) -> float | None:
    name = arm[len("recal_"):] if arm.startswith("recal_") else arm
    p = ROOT / f"manifests/perturb/restore_v1/{model}/{name}.json"
    try:
        m = json.load(open(p))
        return float(m.get("budget_w3") or m.get("budget") or m.get("bytes") or 0) or None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    a = ap.parse_args()
    data = defaultdict(dict)  # cell -> arm -> {state_id: row}
    for d in sorted(IN.glob("*_*")):
        if not d.is_dir():
            continue
        m, cell = d.name.split("_", 1)
        for p in sorted(d.glob("*.jsonl")):
            rows = [json.loads(x) for x in open(p) if x.strip()]
            data[f"{m}:{cell}"][p.stem] = {r["state_id"]: r for r in rows if "error" not in r}
    if not data:
        print("analyze_pivot_arms: no pivot-arm outputs yet; nothing to do.")
        return
    res = {"label": "W55 step 2; selection rule FORK_PROTOCOL.md §13 (fixed before outcomes)", "analysis": "analysis/fork/analyze_pivot_arms.py",
           "script": {"sha256": AD.sha256(__file__), "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cells": {}}
    # shared draws over the union of states' tasks/blocks
    bo = defaultdict(set)
    for arms in data.values():
        for rows in arms.values():
            for r in rows.values():
                bo[r["task"]].add(BLOCK_RE.search(r["run_id"]).group(1))
    boot = AD.Boot(sorted(bo), {k: sorted(v) for k, v in bo.items()}, B=a.B)

    def rate(units, key):
        for u in units:
            u["E"] = {"x": u[key]}
        X, M = boot.arrays(units, "x")
        return boot.task_mean(X, M)

    draws_delta = defaultdict(dict)
    for cell, arms in sorted(data.items()):
        rc = {}
        for arm, rows in sorted(arms.items()):
            us = [{"task": r["task"], "block": BLOCK_RE.search(r["run_id"]).group(1), "eq_B": int(r["eq_B"]), "eq_Q": int(r["eq_Q"]),
                   "other": int(not r["eq_B"] and not r["eq_Q"]), "exact_B": int(r["exact_B"]), "exact_Q": int(r["exact_Q"])} for r in rows.values()]
            rc[arm] = {"n": len(us), "prompt_ok": sum(r["prompt_ok"] for r in rows.values()),
                       **{k: AD.summarise(*rate(us, k)) for k in ("eq_B", "eq_Q", "other", "exact_B", "exact_Q")}}
        deltas = {}
        for arm, ctrl in CANDIDATES.items():
            if arm in arms and ctrl in arms:
                common = sorted(set(arms[arm]) & set(arms[ctrl]))
                us = [{"task": arms[arm][s]["task"], "block": BLOCK_RE.search(arms[arm][s]["run_id"]).group(1),
                       "d": int(arms[arm][s]["eq_B"]) - int(arms[ctrl][s]["eq_B"])} for s in common]
                pt, dr = rate(us, "d")
                deltas[arm] = {"control": ctrl, "n_paired": len(us), **AD.summarise(pt, dr)}
                draws_delta[cell][arm] = (pt, dr)
        res["cells"][cell] = {"arms": rc, "delta_vs_matched_random_pp": deltas,
                              "controls": {"none_exact_Q": rc.get("none", {}).get("exact_Q"), "all_exact_B": rc.get("all", {}).get("exact_B")}}
    # selection on the pooled W3 cells
    sel = {"cells": list(SEL_CELLS), "available": all(c in draws_delta for c in SEL_CELLS)}
    if sel["available"]:
        pooled = {}
        for arm in CANDIDATES:
            if all(arm in draws_delta[c] for c in SEL_CELLS):
                pt = float(np.mean([draws_delta[c][arm][0] for c in SEL_CELLS]))
                dr = np.mean([draws_delta[c][arm][1] for c in SEL_CELLS], axis=0)
                pooled[arm] = AD.summarise(pt, dr)
        elig = {k: v for k, v in pooled.items() if v["lb95_one_sided"] > 0 and v["est"] >= 5.0}
        order = sorted(elig, key=lambda k: (-elig[k]["est"], budget_bytes("q4", k) or 0))
        chosen = order[:2]
        sel.update({"pooled_delta_pp": pooled, "eligible": sorted(elig), "chosen": chosen,
                    "controls_for_step3": {k: CANDIDATES[k] for k in chosen},
                    "verdict": ("queue step 3 with " + ", ".join(chosen)) if chosen else
                    "no module set flips the pivot action above its byte-matched control: step 3 not queued"})
    else:
        sel["verdict"] = "waiting for both GPTQ-W3 cells"
    res["selection"] = sel
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / f"pivot_arms_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    def fd(dl):
        return "" if not dl else f"{dl['est']:+.1f} [{dl['ci95'][0]:+.1f}, {dl['ci95'][1]:+.1f}]"

    L = [f"**TL;DR** Pivot-time action reversion per restoration arm; selection: {sel['verdict']}.", "",
         f"# Pivot arms ({res['utc']})", "", f"Full numbers `{jp.relative_to(ROOT) if jp.is_relative_to(ROOT) else jp}`; pp; 95% hierarchical bootstrap.", ""]
    for cell, v in res["cells"].items():
        L += [f"## {cell}", "| arm | n | = a_B | = a_Q | other | exact a_B | exact a_Q | Δ vs matched random |", "|---|---|---|---|---|---|---|---|"]
        for arm, r in v["arms"].items():
            dl = v["delta_vs_matched_random_pp"].get(arm)
            L.append(f"| {arm} | {r['n']} | {r['eq_B']['est']:.1f} | {r['eq_Q']['est']:.1f} | {r['other']['est']:.1f} | {r['exact_B']['est']:.1f} | "
                     f"{r['exact_Q']['est']:.1f} | {fd(dl)} |")
        L.append("")
    (OUT / f"pivot_arms_{utc}.md").write_text("\n".join(L) + "\n")
    print(f"analyze_pivot_arms: wrote {jp.relative_to(ROOT) if jp.is_relative_to(ROOT) else jp}; {sel['verdict']}")


if __name__ == "__main__":
    main()
