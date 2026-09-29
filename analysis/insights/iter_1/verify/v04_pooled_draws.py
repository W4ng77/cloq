"""Verifier: treat legacy (a6000_*) and clean (a6k2_*) runs of the same config as exchangeable draws (I4/R1 premise)
and pool them, per model.

  * canonical BF16 legacy vs a6k2 (same weights, same prompt; agent AND user-simulator numerics changed): per-task
    discordance + exact McNemar -> how far a pure serving-numerics change moves the canonical score (I4).
  * null family N = every bf16 / null_n* / bf16_eager run from both prefixes; ybar_N(t) per task (tasks where >= 3
    null draws exist). Per config family (gauss k, rtn wX, gptq/awq), all draws pooled: Δ = mean over (draw, task) of
    y − ybar_N(t), task-cluster bootstrap; cell-only wins vs null-majority-only wins (nestedness, P4e).
  * canonical rank: bf16 draws vs nonce draws vs weight-only (gauss0.03) draws, each against ybar over the *other*
    families (P4c pilot).
Writes analysis/insights/iter_1/verify/out/v04_pooled_draws.json
"""
import json
import re
from collections import defaultdict

import numpy as np
from scipy.stats import binomtest

from v01_legacy_recompute import OUT, RUNS
from v03_outcomes_pooled import outcomes

rng = np.random.default_rng(4)
B = 4000
DOMS = ("retail", "airline")


def fam(run, model):
    s = re.sub(rf"^(a6000|a6k2)_{model}_", "", run)
    if s in ("bf16", "bf16_eager") or s.startswith("null_n"):
        return "null:" + ("bf16" if s == "bf16" else "eager" if s == "bf16_eager" else "nonce")
    s = re.sub(r"_(s\d|n\d|d\d_n\d)$", "", s)
    s = re.sub(r"_d\d$", "", s)
    return s


def boot_ci(clusters):
    keys = list(clusters)
    sums = np.array([sum(clusters[k]) for k in keys]); cnts = np.array([len(clusters[k]) for k in keys])
    bs = []
    for _ in range(B):
        j = rng.choice(len(keys), len(keys))
        bs.append(sums[j].sum() / cnts[j].sum())
    return float(sums.sum() / cnts.sum()), [round(float(np.quantile(bs, .025)), 4), round(float(np.quantile(bs, .975)), 4)]


def main():
    res = {}
    for model in ("q4", "q8"):
        runs = sorted(p.name for p in RUNS.iterdir() if re.match(rf"^(a6000|a6k2)_{model}_", p.name) and not p.name.endswith("_cal"))
        Y = {}
        for r in runs:
            y = {(d, t): v for d in DOMS for t, v in outcomes(r, d).items()}
            if y:
                Y[r] = y
        m = {}
        a, b = f"a6000_{model}_bf16", f"a6k2_{model}_bf16"
        if a in Y and b in Y:
            ks = sorted(set(Y[a]) & set(Y[b]))
            ao = sum(1 for k in ks if Y[a][k] and not Y[b][k]); bo = sum(1 for k in ks if Y[b][k] and not Y[a][k])
            m["canonical_legacy_vs_a6k2"] = {"n_tasks": len(ks), "db_legacy": round(np.mean([Y[a][k] for k in ks]), 3),
                                             "db_a6k2": round(np.mean([Y[b][k] for k in ks]), 3), "legacy_only": ao, "a6k2_only": bo,
                                             "task_disagreement": round((ao + bo) / len(ks), 3) if ks else None,
                                             "mcnemar_p": round(binomtest(ao, ao + bo).pvalue, 3) if ao + bo else 1.0}
        nulls = [r for r in Y if fam(r, model).startswith("null:")]
        per = defaultdict(list)
        for r in nulls:
            for k, v in Y[r].items():
                per[k].append(v)
        pbar = {k: np.mean(v) for k, v in per.items() if len(v) >= 3}
        m["null_draws"] = {r: round(np.mean([Y[r][k] for k in Y[r] if k in pbar]), 3) for r in nulls}
        m["n_tasks_with_ge3_null_draws"] = len(pbar)
        # SD only over near-complete draws (>= 90% of the tasks with a null mean); partial draws cover biased task subsets
        full = [r for r in nulls if sum(1 for k in Y[r] if k in pbar) >= 0.9 * len(pbar)]
        m["null_draws_near_complete"] = full
        rates = np.array([m["null_draws"][r] for r in full])
        m["null_draw_sd"] = round(float(rates.std(ddof=1)), 4) if len(rates) > 1 else None
        pb = np.array(list(pbar.values()))
        m["bernoulli_sd_run"] = round(float(np.sqrt(np.mean(pb * (1 - pb)) / len(pb))), 4) if len(pb) else None
        fams = defaultdict(list)
        for r in Y:
            fams[fam(r, model)].append(r)
        m["families"] = {}
        for f, rs in sorted(fams.items()):
            clusters = defaultdict(list)
            wins = losses = 0
            for r in rs:
                for k, v in Y[r].items():
                    if k not in pbar:
                        continue
                    # for null members, leave the run itself out of the reference mean
                    if r in nulls:
                        others = [Y[x][k] for x in nulls if x != r and k in Y[x]]
                        ref = np.mean(others) if others else np.nan
                    else:
                        ref = pbar[k]
                    if np.isnan(ref):
                        continue
                    clusters[k].append(v - ref)
                    wins += int(v == 1 and ref < 0.5); losses += int(v == 0 and ref > 0.5)
            if not clusters:
                continue
            d, ci = boot_ci(clusters)
            m["families"][f] = {"draws": rs, "n_rows": sum(len(v) for v in clusters.values()), "n_tasks": len(clusters),
                                "delta_vs_null": round(d, 4), "ci95_task_cluster": ci,
                                "wins_vs_null_majority": wins, "losses_vs_null_majority": losses}
            print(model, f, len(rs), m["families"][f]["n_rows"], round(d, 3), ci, "wins/losses", wins, losses)
        res[model] = m
        print(model, {k: v for k, v in m.items() if k != "families"})
    json.dump(res, open(OUT / "v04_pooled_draws.json", "w"), indent=1, default=float)
    print("wrote", OUT / "v04_pooled_draws.json")


if __name__ == "__main__":
    main()
