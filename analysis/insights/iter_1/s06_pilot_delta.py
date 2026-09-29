"""Round-2 pilot of the revised P2a test (legacy numerics flavour, live snapshot).

Replaces "inside the range of the nulls" (≈1/3 false-flag rate per run) with a task-cluster bootstrap of
    Δ(config) = mean_t [ y_config(t) − ȳ_null(t) ],
where the null set is canonical bf16 + every completed nonce null of the same model and domain, and t runs over
tasks common to all of them. Also reports process-error channels (Flat Score / survey P2e):
tool_error_rate, repeated_tool_call_rate, premature_rate, mean_decisions (a proxy for token inflation),
and the count of empty/terminated episodes (ABC audit) in each cell.

Usage: python s06_pilot_delta.py [model] [domain]
"""
import json
import re
import sys

import numpy as np

from common import RUNS, a6000_runs, dump, status

MODEL = sys.argv[1] if len(sys.argv) > 1 else "q4"
DOM = sys.argv[2] if len(sys.argv) > 2 else "airline"
B = 5000
STRICT = 2
rng = np.random.default_rng(0)


def per_task(run):
    m = json.load(open(RUNS / run / DOM / "metrics.json"))
    y = {str(t["task_id"]): int(bool(t["db_match"]) and not t.get("premature", False)) for t in m["per_task"]}
    # strict error budget (Flat Score): an episode with more than STRICT tool errors counts as a failure. Post hoc
    # this is exact if a run terminated at the budget would have failed anyway (the budget only ends episodes).
    ys = {str(t["task_id"]): int(y[str(t["task_id"])] and (t.get("n_tool_errors") or 0) <= STRICT) for t in m["per_task"]}
    empty = sum(1 for t in m["per_task"] if t.get("premature") or (t.get("n_decisions") or 0) <= 1)
    proc = {k: m.get(k) for k in ("tool_error_rate", "repeated_tool_call_rate", "premature_rate", "mean_decisions",
                                  "mean_tool_calls", "db_match_rate")}
    proc["n_empty_or_premature"] = empty
    return y, ys, proc


runs = [r for r in a6000_runs(f"a6000_{MODEL}_") if not r.endswith("_cal") and status(r, DOM) == "completed"]
nulls = [r for r in runs if re.search(r"_(bf16|null_n\d)$", r)]
if len(nulls) < 2:
    sys.exit(f"{MODEL}/{DOM}: fewer than 2 completed null runs ({nulls}); nothing to test")
Y, YS, P = {}, {}, {}
for r in runs:
    Y[r], YS[r], P[r] = per_task(r)
tasks = sorted(set.intersection(*[set(Y[r]) for r in runs]))
N = np.array([[Y[r][t] for t in tasks] for r in nulls], float)
ybar_null = N.mean(0)
null_rates = N.mean(1)
res = {"model": MODEL, "domain": DOM, "n_tasks": len(tasks), "nulls": nulls,
       "null_rates": dict(zip(nulls, map(float, null_rates))),
       "null_sd": float(null_rates.std(ddof=1)),
       "bernoulli_sd": float(np.sqrt(np.mean(ybar_null * (1 - ybar_null)) / len(tasks))),
       "null_pairwise_task_disagreement": float(np.mean([np.mean(N[i] != N[j]) for i in range(len(N))
                                                         for j in range(i + 1, len(N))])),
       "cells": {}}
NS = np.array([[YS[r][t] for t in tasks] for r in nulls], float).mean(0)
print(f"{MODEL}/{DOM}: n_tasks={len(tasks)} nulls={nulls} rates={np.round(null_rates, 3)} sd={res['null_sd']:.3f} "
      f"bernoulli={res['bernoulli_sd']:.3f} null-pair task disagreement={res['null_pairwise_task_disagreement']:.3f}")
idx = np.arange(len(tasks))
for r in runs:
    y = np.array([Y[r][t] for t in tasks], float)
    d = y - ybar_null
    boots = np.array([d[rng.choice(idx, len(idx))].mean() for _ in range(B)])
    lo, hi = np.quantile(boots, [0.025, 0.975])
    ys = np.array([YS[r][t] for t in tasks], float)
    ds = ys - NS
    bs = np.array([ds[rng.choice(idx, len(idx))].mean() for _ in range(B)])
    cell = {"db_match": float(y.mean()), "delta_vs_null_mean": float(d.mean()), "ci95": [float(lo), float(hi)],
            "strict_budget_db_match": float(ys.mean()), "strict_delta_vs_null_mean": float(ds.mean()),
            "strict_ci95": [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))],
            "is_null_member": r in nulls, **P[r]}
    res["cells"][r] = cell
    print(f"  {r:26s} db={y.mean():.3f} Δ={d.mean():+.3f} [{lo:+.3f},{hi:+.3f}] "
          f"strictΔ={ds.mean():+.3f} [{cell['strict_ci95'][0]:+.3f},{cell['strict_ci95'][1]:+.3f}] "
          f"toolerr={P[r]['tool_error_rate']:.3f} rep={P[r]['repeated_tool_call_rate']:.3f} "
          f"prem={P[r]['premature_rate']:.3f} dec={P[r]['mean_decisions']:.1f} empty={P[r]['n_empty_or_premature']}"
          f"{'  (null)' if r in nulls else ''}")
dump(f"s06_pilot_delta_{MODEL}_{DOM}.json", res)
