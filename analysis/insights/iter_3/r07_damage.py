"""r07: what turns reallocation into net damage? Attractor collapse (c < p_bar) and its process signature.

Per model x family (from out/r01_realloc_<tag>.json: lam, c, p_bar, delta_obs) add, from metrics.json per_task
(+ infra_causes.json context_overflow via common.outcomes):
  abn       rate of abnormal terminations (max_steps, too_many_errors, context_overflow) over all episodes
  abn_U     the same for the nonce nulls
  brk_abn   among breaks of reference-always-ok tasks, the fraction that are abnormal terminations
  brk_abn_U the same for held-out null draws (reference = other U draws)
  rep, terr mean repeated tool calls / tool errors per episode; dec mean decisions per episode (vs null)
Cross-family test (per model and pooled): Spearman between the attractor gap (p_bar - c) and the excess abnormal rate
(abn - abn_U), and between delta_obs and -lam * (p_bar - c) (the model's identity, a consistency check).
Usage: CLOQ_SNAPSHOT=<manifest> python r07_damage.py (needs r01 output) -> out/r07_damage_<tag>.json
"""
import json
import os

import numpy as np
from scipy.stats import spearmanr

from common import RUNS, check_frozen, outcomes
from r_common import OUT, TAG, dump, load, rnd

MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3").split(",")
ABN = {"max_steps", "too_many_errors", "context_overflow"}


def episodes(run):
    out = {}
    for d in ("retail", "airline"):
        reasons = outcomes(run, d, with_reason=True)
        p = RUNS / run / d / "metrics.json"
        if not p.exists():
            continue
        check_frozen(run, d, "metrics.json")
        for t in json.load(open(p))["per_task"]:
            k = (d, str(t["task_id"]))
            y, tr = reasons.get(str(t["task_id"]), (None, None))
            if tr == "infrastructure_error":
                continue
            out[k] = dict(y=y, abn=tr in ABN, rep=t.get("n_repeated_tool_calls", 0), terr=t.get("n_tool_errors", 0),
                          dec=t.get("n_decisions", 0))
    return out


def main():
    r01 = json.load(open(OUT / f"r01_realloc_{TAG}.json"))
    res = {"models": {}}
    pooled = []
    for m in MODELS:
        Y, meta = load(m)
        U = sorted(r for r in Y if meta[r]["family"] == "null_U")
        E = {r: episodes(r) for r in Y}
        tasks = sorted(set.intersection(*[set(Y[u]) for u in U]))

        def rates(runs):
            eps = [E[r][t] for r in runs for t in tasks if t in E[r]]
            return dict(abn=np.mean([e["abn"] for e in eps]), rep=np.mean([e["rep"] for e in eps]),
                        terr=np.mean([e["terr"] for e in eps]), dec=np.mean([e["dec"] for e in eps]))

        def brk_abn(runs):
            n = a = 0
            for r in runs:
                R = [u for u in U if u != r and meta[u]["nonce"] != meta[r]["nonce"]]
                for t in tasks:
                    if t in E[r] and all(Y[u][t] == 1 for u in R) and E[r][t]["y"] == 0:
                        n += 1; a += E[r][t]["abn"]
            return (a / n if n else None), n

        base = rates(U)
        bU, nU = brk_abn(U)
        fams = {}
        for f, v in r01["models"][m]["families"].items():
            if f.startswith("ckpt:") or f == "null_K":
                continue
            runs = [r for r in v["runs"] if r in E]
            if not runs:
                continue
            rt = rates(runs)
            ba, nb = brk_abn(runs)
            fams[f] = dict(lam=v["lam"], c=v["c"], p_bar=v["p_bar_null"], gap=rnd(v["p_bar_null"] - v["c"]) if v["c"] is not None else None,
                           delta_obs=v["delta_obs"], abn=rnd(rt["abn"]), abn_excess=rnd(rt["abn"] - base["abn"]),
                           rep=rnd(rt["rep"]), terr=rnd(rt["terr"]), dec=rnd(rt["dec"]), brk_abn=rnd(ba), n_breaks=nb)
            if v["lam"] is not None and v["lam"] > 0.15 and v["c"] is not None:
                pooled.append((m, f, v["p_bar_null"] - v["c"], rt["abn"] - base["abn"], v["delta_obs"], -v["lam"] * (v["p_bar_null"] - v["c"])))
        sel = [(fv["gap"], fv["abn_excess"]) for fv in fams.values() if fv["lam"] is not None and fv["lam"] > 0.15 and fv["gap"] is not None]
        rho = spearmanr(*zip(*sel)) if len(sel) > 3 else None
        res["models"][m] = dict(null=dict(**{k: rnd(x) for k, x in base.items()}, brk_abn=rnd(bU), n_breaks=nU), families=fams,
                                spearman_gap_vs_abn_excess=dict(rho=rnd(rho.statistic) if rho else None,
                                                                p=rnd(rho.pvalue) if rho else None, n=len(sel)))
        print(m, "null", res["models"][m]["null"])
        for f, fv in sorted(fams.items(), key=lambda kv: -(kv[1]["lam"] or 0)):
            print("  ", f, fv)
        print("   rho(gap, abn_excess)", res["models"][m]["spearman_gap_vs_abn_excess"])
    if len(pooled) > 3:
        r1 = spearmanr([p[2] for p in pooled], [p[3] for p in pooled])
        r2 = spearmanr([p[4] for p in pooled], [p[5] for p in pooled])
        res["pooled_lam_gt_0.15"] = dict(n=len(pooled), rho_gap_abn=rnd(r1.statistic), p_gap_abn=rnd(r1.pvalue),
                                         rho_delta_vs_model=rnd(r2.statistic), p_delta_vs_model=rnd(r2.pvalue),
                                         points=[dict(model=p[0], family=p[1], gap=rnd(p[2]), abn_excess=rnd(p[3]),
                                                      delta_obs=rnd(p[4]), delta_model=rnd(p[5])) for p in pooled])
        print("pooled", {k: v for k, v in res["pooled_lam_gt_0.15"].items() if k != "points"})
    dump("r07_damage", res)


if __name__ == "__main__":
    main()
