"""Where do consequential divergences come from? (W67, exploratory, dev split only)

Uses the same admitted units as analyze_dev.py (same snapshot gate, quarantine, complete-block rule) and asks:

  1. Task concentration: is the share of units whose pivot action flips the outcome (M = rescue + damage) a property of
     the task (fragile tasks), or spread evenly? Per-task M across blocks vs a binomial null with the pooled rate.
  2. Within-task direction: do the same tasks produce both rescues and damages across blocks (cancellation within a
     task), or are tasks one-directional (cancellation between tasks)?
  3. Cross-quantizer agreement: on the same task x block (same nonce, same BF16 run), do GPTQ-W4 and AWQ-W4 produce a
     consequential divergence on the same units? And KV8 vs W4. Agreement means consequence belongs to the state, not
     to the quantizer.
  4. Consequence by divergence type, position (decision index t*) and domain.

Inference: permutation null within block for (1)-(3) (task labels shuffled within each block x cell), B = 2000.

usage: python analysis/fork/analyze_consequence.py [--snapshot PATH]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis" / "fork"))
import analyze_dev as AD  # noqa: E402

OUT = ROOT / "analysis" / "fork" / "out"
RNG = np.random.default_rng(20261001)
B = 2000


def latest_snapshot() -> Path:
    return Path(sorted(glob.glob(str(ROOT / "analysis/insights/iter_3/out/snapshot_auto_*.json")))[-1])


def load_units(snap_path: Path) -> list[dict]:
    snap = json.load(open(snap_path))
    cache, units = {}, []
    for d in AD.discover(False):
        r = AD.load_dir(d, snap, cache)
        if r["quarantined"]:
            continue
        units += r["units"]
    AD.split_guard(units, "dev", "analyze_consequence")
    AD.mark_incomplete_blocks(units, "dev")
    seen, out = set(), []
    for u in units:
        if "excluded" in u:
            continue
        k = (u["model"], u["cell"], u["block"], u["task"])
        if k in seen:
            continue
        seen.add(k)
        e = AD.effects(u["Y"])
        out.append({**u, **e})
    return out


def concentration(us: list[dict]) -> dict:
    """Per-task M across blocks vs binomial null: dispersion index and share of consequences in the top 20% tasks."""
    by_task = collections.defaultdict(list)
    for u in us:
        by_task[u["task"]].append(u["M"])
    tasks = sorted(by_task)
    n = np.array([len(by_task[t]) for t in tasks])
    k = np.array([sum(by_task[t]) for t in tasks])
    p = k.sum() / n.sum()
    # dispersion: observed variance of per-task rates vs binomial expectation
    obs = float(np.sum((k - n * p) ** 2 / np.maximum(n * p * (1 - p), 1e-9)) / len(tasks))
    sims = []
    for _ in range(B):
        ks = RNG.binomial(n, p)
        sims.append(np.sum((ks - n * p) ** 2 / np.maximum(n * p * (1 - p), 1e-9)) / len(tasks))
    sims = np.array(sims)
    order = np.argsort(-k)
    top = order[: max(1, int(round(0.2 * len(tasks))))]
    zero = int(np.sum(k == 0))
    return {"n_tasks": len(tasks), "units": int(n.sum()), "M_rate": round(float(p), 4),
            "dispersion_index": round(obs, 3), "null_dispersion_mean": round(float(sims.mean()), 3),
            "p_overdispersion": round(float(np.mean(sims >= obs)), 4),
            "share_of_consequences_in_top20pct_tasks": round(float(k[top].sum() / max(k.sum(), 1)), 3),
            "tasks_never_consequential": zero, "tasks_with_any": int(np.sum(k > 0))}


def direction(us: list[dict]) -> dict:
    """Do tasks with consequences show both directions? Compare to a null that keeps each unit's M but redistributes
    r/d labels at the pooled r:(r+d) ratio."""
    by_task = collections.defaultdict(lambda: [0, 0])
    for u in us:
        by_task[u["task"]][0] += u["rescue"]
        by_task[u["task"]][1] += u["damage"]
    rows = [(r, d) for r, d in by_task.values() if r + d >= 2]
    if not rows:
        return {"tasks_with_2plus": 0}
    R = sum(r for r, _ in rows); D = sum(d for _, d in rows)
    q = R / max(R + D, 1)
    both = sum(1 for r, d in rows if r and d)
    sims = []
    for _ in range(B):
        c = 0
        for r, d in rows:
            x = RNG.binomial(r + d, q)
            c += int(0 < x < r + d)
        sims.append(c)
    sims = np.array(sims)
    # net direction purity: |r-d|/(r+d) per task
    purity = float(np.mean([abs(r - d) / (r + d) for r, d in rows]))
    return {"tasks_with_2plus_consequences": len(rows), "tasks_both_directions": both,
            "null_both_mean": round(float(sims.mean()), 1), "p_fewer_mixed_than_null": round(float(np.mean(sims <= both)), 4),
            "mean_direction_purity": round(purity, 3),
            "share_of_rescues_in_tasks_with_net_rescue": round(sum(r for r, d in rows if r > d) / max(R, 1), 3),
            "share_of_damages_in_tasks_with_net_damage": round(sum(d for r, d in rows if d > r) / max(D, 1), 3)}


def agreement(a: list[dict], b: list[dict]) -> dict:
    """Same task x block in two cells (same model, same nonce): P(M_b=1 | M_a=1) vs P(M_b=1), and phi; permutation null
    shuffles tasks within block."""
    ka = {(u["block"], u["task"]): u for u in a}
    kb = {(u["block"], u["task"]): u for u in b}
    common = sorted(set(ka) & set(kb))
    if len(common) < 30:
        return {"n_common": len(common)}
    x = np.array([ka[k]["M"] for k in common]); y = np.array([kb[k]["M"] for k in common])
    blocks = np.array([k[0] for k in common])

    def phi(x, y):
        if x.std() == 0 or y.std() == 0:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])

    obs = phi(x, y)
    # also same-direction: among units consequential in both, fraction with same sign of G
    both = [(ka[k]["G"], kb[k]["G"]) for k in common if ka[k]["M"] and kb[k]["M"]]
    same_sign = float(np.mean([ga == gb for ga, gb in both])) if both else None
    sims = []
    idx_by_block = collections.defaultdict(list)
    for i, bl in enumerate(blocks):
        idx_by_block[bl].append(i)
    for _ in range(B):
        yp = y.copy()
        for ii in idx_by_block.values():
            ii = np.array(ii); yp[ii] = y[RNG.permutation(ii)]
        sims.append(phi(x, yp))
    sims = np.array(sims)
    pa = float(y[x == 1].mean()) if (x == 1).any() else None
    return {"n_common": len(common), "P_b_given_a": round(pa, 3) if pa is not None else None,
            "P_b": round(float(y.mean()), 3), "lift": round(pa / max(y.mean(), 1e-9), 2) if pa is not None else None,
            "phi": round(obs, 3), "null_phi_95": round(float(np.quantile(sims, 0.95)), 3),
            "p_perm": round(float(np.mean(sims >= obs)), 4), "both_consequential": len(both),
            "same_direction_given_both": round(same_sign, 3) if same_sign is not None else None}


def by_field(us: list[dict], f) -> dict:
    g = collections.defaultdict(list)
    for u in us:
        if u.get("div"):
            g[f(u)].append(u)
    out = {}
    for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
        n = len(v); r = sum(u["rescue"] for u in v); d = sum(u["damage"] for u in v)
        out[str(k)] = {"n": n, "M_given_div": round((r + d) / n, 3), "r": r, "d": d, "net_G_pp": round(100 * (r - d) / n, 1)}
    return out


def tbin(u):
    t = int(u["t"])
    return "t=0" if t == 0 else "t=1-2" if t <= 2 else "t=3-6" if t <= 6 else "t>=7"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=None)
    a = ap.parse_args()
    sp = Path(a.snapshot) if a.snapshot else latest_snapshot()
    t0 = time.time()
    units = load_units(sp)
    cells = collections.defaultdict(list)
    for u in units:
        cells[f"{u['model']}:{u['cell']}"].append(u)
    res = {"analysis": "analysis/fork/analyze_consequence.py", "EXPLORATORY": True, "snapshot": str(sp),
           "script_sha256": AD.sha256(Path(__file__)), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "B": B, "cells": {}, "agreement": {}}
    for c, us in sorted(cells.items()):
        if len(us) < 100:
            continue
        res["cells"][c] = {"n_units": len(us), "concentration": concentration(us), "direction": direction(us),
                           "by_type": by_field(us, lambda u: u.get("type")), "by_position": by_field(us, tbin),
                           "by_domain": by_field(us, lambda u: u["domain"])}
    for m in ("q4", "q8"):
        pairs = [("gptq_w4_d1", "awq_w4"), ("gptq_w4_d1", "kvq_int8"), ("awq_w4", "kvq_int8")]
        for x, y in pairs:
            A = cells.get(f"{m}:{x}", []); Bc = cells.get(f"{m}:{y}", [])
            if A and Bc:
                res["agreement"][f"{m}:{x}~{y}"] = agreement(A, Bc)
    for x in ("gptq_w4_d1", "awq_w4", "kvq_int8"):
        A = cells.get(f"q4:{x}", []); Bc = cells.get(f"q8:{x}", [])
        if A and Bc:  # q4 vs q8 share task ids and nonces but not BF16 runs; agreement = task-level fragility
            res["agreement"][f"q4~q8:{x}"] = agreement(A, Bc)
    res["seconds"] = round(time.time() - t0, 1)
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"consequence_{utc}.json"
    jp.write_text(json.dumps(res, indent=1))
    print(jp)


if __name__ == "__main__":
    main()
