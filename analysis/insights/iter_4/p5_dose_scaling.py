"""p5 (exploratory): how do checkpoint coherence and disposition shift scale with perturbation size?

(a) Gaussian seed lottery by dose. Canonical Gaussian cells gauss<k>_s<seed> are independent checkpoints of a matched
random perturbation at relative size k, one canonical-prompt draw each. For each model x k with >= 2 seeds:
  between = var_seeds(mean_t y)          (includes one draw of nonce/numerics noise per seed)
  indep   = N^-2 sum_t var_seeds(y_t)     (the same if tasks landed independently, noise included)
  phi_k   = between / indep; permutation p (task-wise shuffle of seed labels, B = CLOQ_B, default 5000), one-sided.
Nonce noise is close to independent across tasks (p1: phi_U for the nonce null is 0.36-1.19, none significant), so
phi_k > 1 measures checkpoint coherence. If a fixed fork bias whose size grows with k drives the effect, coherence
(variance ~ lam^2) should outgrow independent landing (~ lam), and phi_k should rise with k.
Pooled per k over models: sum of between / sum of indep; permutation within model.
(b) Disposition-shift size vs turnover. For nonce-stratum checkpoints with >= 2 draws, |z| = norm of the mean
standardised disposition shift (p2 scaling; features with zero nonce SD dropped) against the checkpoint's lam
(iter_3 r10 output, same snapshot), Spearman per model and the task-count-weighted mean.
Usage: CLOQ_SNAPSHOT=<manifest> [CLOQ_TAG=live_<id>] python p5_dose_scaling.py -> out/p5_dose_scaling_<tag>.json
"""
import json
import os
import re
from collections import defaultdict

import numpy as np
from scipy.stats import spearmanr

from common4 import DISP, MODELS, TAG, dump, model_data, rnd, ymat
from p1_overdispersion import pairs
from p2_dispositions import shift

B = int(os.environ.get("CLOQ_B", 5000))
rng = np.random.default_rng(20261003)
R10 = os.environ.get("CLOQ_R10", f"/data/ziyangs/cloq/analysis/insights/iter_3/out/r10_turnover_stats_{TAG}.json")


def phi_perm(Ymat):
    N = Ymat.shape[1]
    bet = Ymat.mean(1).var(ddof=1)
    ind = Ymat.var(0, ddof=1).sum() / N ** 2
    ts = np.array([np.take_along_axis(Ymat, np.argsort(rng.random(Ymat.shape), 0), 0).mean(1).var(ddof=1) for _ in range(B)])
    return bet, ind, ts


def main():
    res = {"B": B, "r10": R10, "gauss_seed": {}, "shift_size": {}}
    r10 = json.load(open(R10))
    pooled = defaultdict(list)
    ss_rho = []
    for m in MODELS:
        D = model_data(m)
        meta, Y, U = D["meta"], D["Y"], D["U"]
        byk = defaultdict(list)
        for r, k in meta.items():
            if k["kind"] == "gauss_canon":
                byk[float(re.match(r"gauss([\d.]+)_s", k["ckpt"]).group(1))].append(r)
        res["gauss_seed"][m] = {}
        for k, rs in sorted(byk.items()):
            if len(rs) < 2:
                continue
            tasks = [t for t in D["tasks"] if all(t in Y[r] for r in rs)]
            Ym = ymat(Y, sorted(rs), tasks)
            bet, ind, ts = phi_perm(Ym)
            res["gauss_seed"][m][str(k)] = dict(n_seeds=len(rs), between=rnd(bet, 6), indep=rnd(ind, 6), phi=rnd(bet / ind, 3),
                                                p=float((1 + np.sum(ts >= bet)) / (1 + B)),
                                                sd_net_pp=rnd(100 * np.sqrt(bet), 2))
            pooled[k].append((bet, ind, ts))
        print(m, {k: (v["n_seeds"], v["phi"], v["p"]) for k, v in res["gauss_seed"][m].items()})
        # (b)
        fam = r10["models"].get(m, {}).get("families", {})
        P = pairs(D)
        used = [r for _, _, a, b in P for r in (a, b)] + U
        tasks = [t for t in D["tasks"] if all(t in Y[r] for r in used)]
        sA = np.array([shift(D, a, tasks)[0] for _, _, a, _ in P]); sB = np.array([shift(D, b, tasks)[0] for _, _, _, b in P])
        sd_w = np.sqrt(np.nanmean((sA - sB) ** 2, 0) / 2)
        keep = np.isfinite(sd_w) & (sd_w > 1e-9)
        z = np.nan_to_num(((sA + sB) / 2)[:, keep] / sd_w[keep])
        rows = {}
        for i, (u, g, a, b) in enumerate(P):
            f = fam.get(u) if (u in fam and fam[u].get("n_ckpt") == 1) else fam.get("ckpt:" + u)
            if f is None or f.get("lam") is None:
                continue
            rows[u] = dict(group=g, norm_z=rnd(np.linalg.norm(z[i]), 3), lam=f["lam"], delta=f.get("delta"))
        if len(rows) >= 4:
            x = [v["norm_z"] for v in rows.values()]; y = [v["lam"] for v in rows.values()]
            rho = spearmanr(x, y)[0]
            ss_rho.append((len(rows), rho))
        else:
            rho = None
        res["shift_size"][m] = dict(units=rows, spearman_normz_lam=rnd(rho, 3))
        print("  shift size vs lam", m, rnd(rho, 3), len(rows))
    res["gauss_seed_pooled"] = {}
    for k, lst in sorted(pooled.items()):
        bet = sum(x[0] for x in lst); ind = sum(x[1] for x in lst); ts = sum(x[2] for x in lst)
        res["gauss_seed_pooled"][str(k)] = dict(n_models=len(lst), phi=rnd(bet / ind, 3), p=float((1 + np.sum(ts >= bet)) / (1 + B)))
    print("pooled by k", res["gauss_seed_pooled"])
    if ss_rho:
        res["shift_size_pooled_rho"] = rnd(sum(n * r for n, r in ss_rho) / sum(n for n, _ in ss_rho), 3)
        print("shift size pooled rho", res["shift_size_pooled_rho"])
    dump("p5_dose_scaling", res)


if __name__ == "__main__":
    main()
