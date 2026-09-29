"""Verifier: pooled (retail+airline) outcome tests on legacy q4/q8 + damage-cell audit (live snapshot).

For each model: nulls = bf16 + null_n* with outcomes; per domain, T_dom = tasks all nulls finished; ybar_null(t).
  * P2a statistic per cell, pooled over domains: Δ = mean_t [y_cell(t) − ybar_null(t)] over tasks the cell finished,
    task-cluster bootstrap CI; plus the count of nominal CI-excludes-0 among free-zone cells (multiplicity check).
  * P4d-style: exact McNemar of every cell against canonical bf16 alone (pooled) — how many nominal p<0.05?
  * canonical rank among nulls (P4c pilot) with 4 airline nulls now available.
  * damage-cell audit (ABC / E4c): termination reasons and n_decisions for gauss3 / rtn_w3 finished tasks vs nulls.
Outcome per task: metrics.json per_task if present, else tau2_results.json simulations (identical on completed runs,
v01 check `metrics_json_mismatches` = 0). premature (non user/agent stop) -> failure, as cloq.metrics.
Usage: python v03_outcomes_pooled.py [a6000|a6k2]
Writes analysis/insights/iter_1/verify/out/v03_outcomes_pooled[_a6k2].json
"""
import json
import sys
import re
from collections import Counter

import numpy as np
from scipy.stats import binomtest

from v01_legacy_recompute import OUT, RUNS

rng = np.random.default_rng(3)
B = 4000
PFX = sys.argv[1] if len(sys.argv) > 1 else "a6000"
TAG = "" if PFX == "a6000" else "_" + PFX
FREE = re.compile(r"_(gauss0\.(03|1)_s\d|rtn_w8_n\d|null_n\d)$")


def outcomes(run, dom):
    mp = RUNS / run / dom / "metrics.json"
    if mp.exists():
        return {str(t["task_id"]): int(bool(t["db_match"]) and not t.get("premature")) for t in json.load(open(mp))["per_task"]}
    p = RUNS / run / dom / "tau2_results.json"
    if not p.exists():
        return {}
    y = {}
    for s in json.load(open(p)).get("simulations", []):
        db = ((s.get("reward_info") or {}).get("db_check") or {}).get("db_match")
        y[str(s["task_id"])] = int(bool(db) and s.get("termination_reason") in ("user_stop", "agent_stop"))
    return y


def terminations(run, dom):
    p = RUNS / run / dom / "tau2_results.json"
    if not p.exists():
        return {}
    return dict(Counter(s.get("termination_reason") for s in json.load(open(p)).get("simulations", [])))


def main():
    res = {}
    for model in ("q4", "q8"):
        runs = sorted(p.name for p in RUNS.iterdir() if p.name.startswith(f"{PFX}_{model}_") and not p.name.endswith("_cal"))
        Y = {(r, d): outcomes(r, d) for r in runs for d in ("retail", "airline")}
        nulls = [r for r in runs if re.search(r"_(bf16|null_n\d)$", r)]
        pbar, used_nulls = {}, {}
        for d in ("retail", "airline"):
            # keep nulls that cover >= 75% of the largest null; T_dom = their common tasks
            sizes = {r: len(Y[(r, d)]) for r in nulls}
            mx = max(sizes.values()) if sizes else 0
            nu = [r for r in nulls if mx and sizes[r] >= 0.75 * mx]
            if len(nu) < 2:
                continue
            T = set.intersection(*[set(Y[(r, d)]) for r in nu])
            used_nulls[d] = {"nulls": nu, "n_tasks": len(T), "rates": {r: round(np.mean([Y[(r, d)][t] for t in T]), 3) for r in nu}}
            for t in T:
                pbar[(d, t)] = np.mean([Y[(r, d)][t] for r in nu])
        m = {"nulls_by_domain": used_nulls, "cells": {}}
        free_flags = []
        bf = {(d, t): v for d in ("retail", "airline") for t, v in Y[(f"{PFX}_{model}_bf16", d)].items()}
        for r in runs:
            keys = [(d, t) for d in ("retail", "airline") for t in Y[(r, d)] if (d, t) in pbar]
            if len(keys) < 5:
                continue
            nm = [x for x in nulls if x in sum([v["nulls"] for v in used_nulls.values()], [])]
            is_null = r in nm
            # leave-one-out null mean for null members (otherwise Δ is shrunk toward 0 by construction)
            def nullmean(k):
                d, t = k
                mem = [x for x in used_nulls[d]["nulls"] if x != r] if is_null else used_nulls[d]["nulls"]
                return np.mean([Y[(x, d)][t] for x in mem])
            diff = np.array([Y[(r, k[0])][k[1]] - nullmean(k) for k in keys])
            bs = np.array([diff[rng.choice(len(diff), len(diff))].mean() for _ in range(B)])
            lo, hi = np.quantile(bs, [0.025, 0.975])
            kb = [k for k in keys if k in bf]
            a_only = sum(1 for k in kb if Y[(r, k[0])][k[1]] and not bf[k])
            b_only = sum(1 for k in kb if bf[k] and not Y[(r, k[0])][k[1]])
            mc = binomtest(a_only, a_only + b_only, 0.5).pvalue if a_only + b_only else 1.0
            c = {"n_tasks": len(keys), "db": round(float(np.mean([Y[(r, k[0])][k[1]] for k in keys])), 3),
                 "delta_vs_null": round(float(diff.mean()), 3), "ci95": [round(float(lo), 3), round(float(hi), 3)],
                 "loo_null": is_null, "mcnemar_vs_bf16": {"cell_only": a_only, "bf16_only": b_only, "p": round(mc, 3)},
                 "terminations": {d: terminations(r, d) for d in ("retail", "airline")}}
            m["cells"][r] = c
            if FREE.search(r):
                free_flags.append((r, lo > 0 or hi < 0))
            print(model, r, {k: v for k, v in c.items() if k != "terminations"}, c["terminations"])
        m["free_zone_cells_ci_excluding_0"] = [r for r, f in free_flags if f]
        m["free_zone_cells_tested"] = len(free_flags)
        # pooled free-zone delta (non-null free cells, all tasks stacked; cluster bootstrap by (cell,task) rows)
        fz = [r for r in m["cells"] if FREE.search(r) and "_null_" not in r and m["cells"][r]["n_tasks"] >= 40]
        if fz:
            # task-cluster bootstrap: resample (domain, task) clusters, keeping every cell's row for that task
            clusters = {}
            for r in fz:
                for d in ("retail", "airline"):
                    for t in Y[(r, d)]:
                        if (d, t) in pbar:
                            clusters.setdefault((d, t), []).append(Y[(r, d)][t] - pbar[(d, t)])
            keys = list(clusters)
            sums = np.array([sum(clusters[k]) for k in keys]); cnts = np.array([len(clusters[k]) for k in keys])
            bs = []
            for _ in range(B):
                j = rng.choice(len(keys), len(keys))
                bs.append(sums[j].sum() / cnts[j].sum())
            m["pooled_free_zone"] = {"cells": fz, "n_task_clusters": len(keys), "n_rows": int(cnts.sum()),
                                     "delta": round(float(sums.sum() / cnts.sum()), 4),
                                     "ci95_task_cluster": [round(float(np.quantile(bs, .025)), 4), round(float(np.quantile(bs, .975)), 4)]}
        res[model] = m
        print(model, "free-zone CI excl 0:", m["free_zone_cells_ci_excluding_0"], "of", m["free_zone_cells_tested"], m.get("pooled_free_zone"))
    json.dump(res, open(OUT / f"v03_outcomes_pooled{TAG}.json", "w"), indent=1, default=float)
    print("wrote", OUT / f"v03_outcomes_pooled{TAG}.json")


if __name__ == "__main__":
    main()
