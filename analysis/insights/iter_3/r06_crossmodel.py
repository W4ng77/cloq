"""r06: is fragility a property of the TASK (shared across models) or of the (model, task) pair?

For every ordered model pair (A, B): fragility score of task t in A =
    mean over A's large perturbation draws (quantizers <= 4 bits, Gaussian k >= 0.3) of (1 - y)  minus  mean over A's
    nonce nulls of (1 - y)            (excess failure under perturbation in A; defined on all tasks)
and 'fixability' in A = mean success under perturbation minus mean null success.
Target: breaks of B's reference-always-ok tasks by each of B's quantizer draws (<= 4 bits), and fixes of B's
always-fail tasks. AUC per draw, averaged. Within-model (A = B, Gaussian-only score) is in r03/r04 for comparison.
Usage: CLOQ_SNAPSHOT=<manifest> python r06_crossmodel.py -> out/r06_crossmodel_<tag>.json
"""
import os
import re

import numpy as np

from r_common import dump, load, rnd

MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3").split(",")


def big(r, k):
    if k["kind"].startswith("gauss"):
        return float(re.search(r"gauss([\d.]+)", r).group(1)) >= 0.3
    return k["kind"] == "quant" and "w8" not in r


def auc(score, y):
    pos, neg = score[y == 1], score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def main():
    D = {m: load(m) for m in MODELS}
    frag, fixab, tasksets = {}, {}, {}
    for m, (Y, meta) in D.items():
        U = [r for r in Y if meta[r]["family"] == "null_U"]
        P = [r for r in Y if big(r, meta[r])]
        ts = sorted(set.intersection(*[set(Y[r]) for r in U + P]))
        tasksets[m] = ts
        pn = {t: np.mean([Y[u][t] for u in U]) for t in ts}
        pp = {t: np.mean([Y[r][t] for r in P]) for t in ts}
        frag[m] = {t: pn[t] - pp[t] for t in ts}
        fixab[m] = {t: pp[t] - pn[t] for t in ts}
    res = {"pairs": {}}
    for A in MODELS:
        for Bm in MODELS:
            if A == Bm:
                continue
            Y, meta = D[Bm]
            U = sorted(r for r in Y if meta[r]["family"] == "null_U")
            Q = sorted(r for r in Y if meta[r]["kind"] == "quant" and "w8" not in r)
            ts = sorted(set(tasksets[Bm]) & set(tasksets[A]))
            ab, af = [], []
            for q in Q:
                R = [u for u in U if meta[u]["nonce"] != meta[q]["nonce"]]
                pr = np.array([np.mean([Y[u][t] for u in R]) for t in ts])
                y = np.array([Y[q][t] for t in ts], float)
                ok, fl = pr == 1, pr == 0
                sb = np.array([frag[A][t] for t in ts]); sf = np.array([fixab[A][t] for t in ts])
                a1, a2 = auc(sb[ok], (1 - y)[ok]), auc(sf[fl], y[fl])
                if a1 is not None: ab.append(a1)
                if a2 is not None: af.append(a2)
            res["pairs"][f"{A}->{Bm}"] = dict(auc_break_mean=rnd(np.mean(ab)) if ab else None, n_break=len(ab),
                                               auc_fix_mean=rnd(np.mean(af)) if af else None, n_fix=len(af))
            print(A, "->", Bm, res["pairs"][f"{A}->{Bm}"])
    # task-level correlation of fragility across models
    corr = {}
    for i, A in enumerate(MODELS):
        for Bm in MODELS[i + 1:]:
            ts = sorted(set(frag[A]) & set(frag[Bm]))
            corr[f"{A}~{Bm}"] = rnd(np.corrcoef([frag[A][t] for t in ts], [frag[Bm][t] for t in ts])[0, 1])
    res["fragility_pearson_across_models"] = corr
    print(corr)
    dump("r06_crossmodel", res)


if __name__ == "__main__":
    main()
