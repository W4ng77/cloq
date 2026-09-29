"""Pilot outcome check on completed A6000 domains (live snapshot; q4 airline, n=27 tasks at time of writing).

db_match per task from metrics.json (premature terminations scored False, as cloq.metrics does).
Reports pooled success per completed config, the 'free-zone' spread (BF16 + nonce + gauss k<=0.3 + RTN W8),
and a task-level test of the margin-cost claim: for each (config, task), outcome change relative to the
free-zone mean of that task, split by the type/margin of the config's first divergence (s02 rows).
"""
import json
import re
import sys
from collections import defaultdict

import numpy as np

from common import RUNS, a6000_runs, dump, load_both, status
from s02_trajectory_divergence import first_divergence

MODEL = sys.argv[1] if len(sys.argv) > 1 else "q4"
DOM = sys.argv[2] if len(sys.argv) > 2 else "airline"
FREE = re.compile(rf"a6000_{MODEL}_(bf16|null_n\d|gauss0\.(03|1|3)_s\d|rtn_w8_n\d)$")


def succ(run):
    m = json.load(open(RUNS / run / DOM / "metrics.json"))
    return {str(t["task_id"]): int(bool(t["db_match"]) and not t.get("premature", False)) for t in m["per_task"]}


runs = [r for r in a6000_runs(f"a6000_{MODEL}_") if not r.endswith("_cal") and status(r, DOM) == "completed"]
S = {r: succ(r) for r in runs}
tasks = sorted(set.intersection(*[set(v) for v in S.values()]))
rate = {r: float(np.mean([S[r][t] for t in tasks])) for r in runs}
free = [r for r in runs if FREE.match(r)]
p_free = {t: np.mean([S[r][t] for r in free]) for t in tasks}
bern_sd = float(np.sqrt(np.mean([p * (1 - p) for p in p_free.values()]) / len(tasks)))
print(f"{MODEL} {DOM}: n_tasks={len(tasks)}; free-zone runs={free}")
for r in runs:
    print(f"  {r:28s} db_match={rate[r]:.3f}{'  (free zone)' if r in free else ''}")
fr = [rate[r] for r in free]
print(f"free-zone mean={np.mean(fr):.3f} sd={np.std(fr, ddof=1):.3f} (Bernoulli-predicted run SD from task p's = {bern_sd:.3f})")

# task-level cost by first-divergence type (vs the BF16 reference trajectory)
bf = {k: v for k, v in load_both(f"a6000_{MODEL}_bf16").items() if k[0] == DOM}
cost = defaultdict(list)
for r in runs:
    if r == f"a6000_{MODEL}_bf16":
        continue
    m = re.search(r"_n(\d+)$", r)
    nonce = "_null_" in r or bool(m)
    pert = {k: v for k, v in load_both(r).items() if k[0] == DOM}
    for row in first_divergence(bf, pert, nonce):
        t = row["task"].split("/")[1]
        if t not in p_free:
            continue
        d = S[r][t] - p_free[t]
        if not row["event"]:
            key = "no divergence"
        elif row["type"] == "wording":
            key = "wording"
        else:
            key = "action (args/behaviour)"
        cost[key].append(d)
        fm = row.get("ref_margin_at_flip")
        if fm is not None:
            cost["flip margin < 1" if fm < 1 else "flip margin >= 1"].append(d)
out = {k: {"n": len(v), "mean_delta_vs_freezone_task_mean": float(np.mean(v))} for k, v in cost.items()}
for k, v in out.items():
    print(f"  first divergence {k:26s} n={v['n']:3d} mean task-level delta={v['mean_delta_vs_freezone_task_mean']:+.3f}")
dump(f"s05_pilot_success_{MODEL}_{DOM}.json", {"tasks": tasks, "rate": rate, "free": free, "free_sd": float(np.std(fr, ddof=1)),
                                             "bernoulli_sd": bern_sd, "cost_by_first_divergence": out})
