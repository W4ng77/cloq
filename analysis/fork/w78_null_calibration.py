"""W78: size check of the beyond-baseline tests under an opportunity-only null (exploratory calibration, CPU only).

Null world (no task-specific fragility): for each compared cell, on the panel85 population (85 tasks x the complete
85-task blocks common to all compared cells), task i's QQ success propensity p_i is its observed QQ rate over all blocks (shrunk 10% towards the domain mean
so that no task is deterministic); QQ_ib ~ Bernoulli(p_i); given QQ = 0 a rescue occurs with the domain's pooled rate
rho_d, given QQ = 1 a damage occurs with the domain's pooled rate delta_d (both from the real cell). Then M_ib = r + d,
G_ib = r - d. Every task's B rate depends on the task only through p_i (its difficulty/opportunity), so the null of the
beyond-baseline test is true. Each simulated data set is split with the same frozen A/B blocks and tested with:
  FL-AB  Freedman-Lane (nuisance-model residuals permuted within domain, HC3 t; the W78 primary test)
  wild-AB  restricted Rademacher wild bootstrap of the same residuals
  v1     raw split-B rates permuted within domain with fixed covariates (v1's test; q_A-only covariates + intercept)
Reported: rejection rate at one-sided alpha = 0.05 over n_sim data sets (should be about 0.05 for a valid test).

usage: python analysis/fork/w78_null_calibration.py --snapshot <snapshot.json> [--n-sim 400] [--B 499]
-> analysis/fork/out/w78_null_calibration_<sid>_<utc>.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402
import audit_w67 as AW  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--n-sim", type=int, default=400)
    ap.add_argument("--B", type=int, default=499)
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
    except Exception:
        pass
    rng = np.random.default_rng(AD.SEED + 78)
    snap = json.load(open(a.snapshot))
    loaded = [AD.load_dir(d, snap, {}) for d in AD.discover(False)]
    allu = [u for L in loaded for u in L["units"]]
    files = {k: v for L in loaded for k, v in L["files"].items()}
    AD.split_guard(allu, "dev", "w78_null_calibration")
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined")
    units, _ = AD.dedupe_units(allu)
    AD.mark_incomplete_blocks(units, "dev", strict=True)
    AD.mark_partial_panel_blocks(units, "dev")
    units = [u for u in units if "excluded" not in u and u["domain"] in AD.PANEL_DOMAINS]
    by = defaultdict(dict)
    for u in units:
        e = AD.effects(u["Y"], u["div"])
        by[(u["model"], u["cell"])][(u["task"], u["block"])] = (u["Y"]["QQ"], e["rescue"], e["damage"])
    present = [mc for mc in AW.CELLS if by.get(mc)]
    man = json.load(open(AD.SPLITS))["splits"]["dev"]["tasks"]
    tasks = [f"{d}:{t}" for d in AD.PANEL_DOMAINS for t in sorted(man[d])]
    blocks = sorted(set.intersection(*[{b for _, b in by[mc]} for mc in present]))
    assert all((t, b) in by[mc] for mc in present for t in tasks for b in blocks), "panel85 not fully observed"
    T, K = len(tasks), len(blocks)
    doms = sorted({t.split(":")[0] for t in tasks})
    dom_of = np.array([doms.index(t.split(":")[0]) for t in tasks])
    dom_idx = {d: list(np.where(dom_of == k)[0]) for k, d in enumerate(doms)}
    A0, B0 = AW.hsplit(blocks, AW.SALT)
    ca, cb = [blocks.index(b) for b in A0], [blocks.index(b) for b in B0]
    import analyze_difficulty as ADF
    bfst = ADF.bf16_task_stats(snap)
    out = {"snapshot": {"id": snap["snapshot_id"], "sha256": AD.sha256(a.snapshot)}, "n_tasks": T, "n_blocks": K,
           "split": {"A": A0, "B": B0}, "n_sim": a.n_sim, "B": a.B, "alpha_one_sided": 0.05, "cells": {},
           "script_sha256": AD.sha256(__file__), "audit_w67_sha256": AD.sha256(AW.__file__),
           "n_input_files": len(files), "input_files_digest_sha256": __import__("hashlib").sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
    out["units_digest_sha256_by_cell"] = {f"{mc[0]}:{mc[1]}": AD.units_digest([u for u in units if (u["model"], u["cell"]) == mc and u["block"] in blocks])
                                          for mc in present}
    for mc in present:
        QQ = np.array([[by[mc][(t, b)][0] for b in blocks] for t in tasks], float)
        R = np.array([[by[mc][(t, b)][1] for b in blocks] for t in tasks], float)
        Dm = np.array([[by[mc][(t, b)][2] for b in blocks] for t in tasks], float)
        p = QQ.mean(1)
        dm = np.array([p[dom_of == k].mean() for k in range(len(doms))])[dom_of]
        p = 0.9 * p + 0.1 * dm
        rho = np.array([R[dom_of == k][QQ[dom_of == k] == 0].mean() for k in range(len(doms))])[dom_of]
        dlt = np.array([Dm[dom_of == k][QQ[dom_of == k] == 1].mean() for k in range(len(doms))])[dom_of]
        bf = np.array([(bfst.get((mc[0], t.split(":")[0], t)) or {}).get("succ", np.nan) for t in tasks])
        for k in range(len(doms)):
            sel = dom_of == k
            bf[sel & np.isnan(bf)] = np.nanmean(bf[sel])
        rej = defaultdict(int)
        for _ in range(a.n_sim):
            qq = (rng.random((T, K)) < p[:, None]).astype(float)
            u = rng.random((T, K))
            r = ((qq == 0) & (u < rho[:, None])).astype(float)
            d = ((qq == 1) & (u < dlt[:, None])).astype(float)
            for key, Y in (("M", r + d), ("G", r - d)):
                yA, yB = Y[:, ca].mean(1), Y[:, cb].mean(1)
                qA, qB = qq[:, ca].mean(1), qq[:, cb].mean(1)
                Z = np.column_stack([(dom_of == k).astype(float) for k in range(len(doms))] + [qA, qA * (1 - qA), qB, qB * (1 - qB), bf])
                ols = AW.OLS(np.column_stack([Z, yA]))
                _, t0_, _ = ols.fit(yB)
                fit0 = Z @ (np.linalg.pinv(Z) @ yB)
                e0 = yB - fit0
                perms = np.stack([AW.perm_within_domain(rng, dom_idx) for _ in range(a.B)], axis=1)
                _, tfl, _ = ols.fit(fit0[:, None] + e0[perms])
                _, twd, _ = ols.fit(fit0[:, None] + e0[:, None] * rng.choice([-1.0, 1.0], size=(T, a.B)))
                rej[f"{key}|FL-AB"] += AW.pval(t0_, tfl[np.isfinite(tfl)]) < 0.05
                rej[f"{key}|wild-AB"] += AW.pval(t0_, twd[np.isfinite(twd)]) < 0.05
                # v1: intercept + q_A + q_A(1-q_A) + bf, raw B permutation, statistic beta
                Z1 = np.column_stack([np.ones(T), qA, qA * (1 - qA), bf])
                P1 = np.linalg.pinv(np.column_stack([Z1, yA]))
                b1 = float((P1 @ yB)[-1])
                nb = (P1 @ yB[perms])[-1]
                rej[f"{key}|v1"] += AW.pval(b1, nb) < 0.05
        out["cells"][f"{mc[0]}:{mc[1]}"] = {k: round(v / a.n_sim, 4) for k, v in sorted(rej.items())}
        print(mc, out["cells"][f"{mc[0]}:{mc[1]}"], flush=True)
    se = float(np.sqrt(0.05 * 0.95 / a.n_sim))
    out["mc_se_at_0.05"] = round(se, 4)
    out["seconds"] = round(time.time() - t0, 1)
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = AD.OUT / f"w78_null_calibration_{snap['snapshot_id']}_{utc}.json"
    jp.write_text(json.dumps(out, indent=1))
    print(f"wrote {jp.relative_to(AD.ROOT)} ({out['seconds']} s)")


if __name__ == "__main__":
    main()
