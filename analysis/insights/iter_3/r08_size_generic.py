"""r08: is reallocation quantization-specific or size-generic? Paired lam contrasts at matched weight-space size.

lam (r01 estimator, stratum-matched nonce null U) for:
  gauss1      Gaussian noise with per-linear ||N||_F = ||RTN-W4 error||_F (k = 1; canonical cells, composed-corrected for
              the canonical-prompt lam_K, AND the fixed-checkpoint control gauss1_s1_q1/q2 under fresh nonces)
  W4 quantizers  rtn_w4, gptq_w4 (d1+d2), awq_w4 (nonce draws)
  small-size controls  gauss0.03 fixed checkpoint (fresh nonces), rtn_w8
Contrasts (same task bootstrap for both sides, B = 2000): lam(gauss1) - lam(quantizer) per model, and pooled over models
(mean of per-model contrasts; bootstrap resamples tasks independently per model). Null calibration: SD of per-draw lam
of held-out nonce nulls (single-draw noise) and the pooled lam of pseudo-families of 2 held-out nulls.
Also the weight-space size of RTN in Gaussian units: k_eq = sqrt(err(RTN)/err(RTN-W4)) from quantization.json
mean_rel_weight_err (d01 convention).
Usage: CLOQ_SNAPSHOT=<manifest> python r08_size_generic.py -> out/r08_size_generic_<tag>.json
"""
import os
from itertools import combinations

import numpy as np

from r01_realloc import lamc, rows_for, stats
from r_common import dump, load, rnd, weight_err

MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3").split(",")
B = 2000
rng = np.random.default_rng(11)
FAMS = {"gauss1": lambda k: k["family"] == "gauss1", "gauss1_fixed": lambda k: k["family"] == "gauss1_fixed",
        "rtn_w4": lambda k: k["family"] == "rtn_w4", "gptq_w4": lambda k: k["family"] == "gptq_w4",
        "awq_w4": lambda k: k["family"] == "awq_w4", "gptq_w3": lambda k: k["family"] == "gptq_w3",
        "rtn_w3": lambda k: k["family"] == "rtn_w3", "rtn_w8": lambda k: k["family"] == "rtn_w8",
        "gauss0.03_fixed": lambda k: k["family"] == "gauss0.03_fixed", "gauss0.3": lambda k: k["family"] == "gauss0.3",
        "null_K": lambda k: k["family"] == "null_K"}
CONTRASTS = [("gauss1", q) for q in ("rtn_w4", "gptq_w4", "awq_w4")] + [("gauss1_fixed", q) for q in ("rtn_w4", "gptq_w4", "awq_w4")] + \
            [("rtn_w4", "gptq_w4"), ("rtn_w4", "awq_w4"), ("gauss1_fixed", "gauss0.03_fixed")]


def lam_of(Yf, Pf, Y0, P0, idx, lamK=None):
    l, _ = lamc(stats(Yf, Pf, idx=idx), stats(Y0, P0, idx=idx))
    if lamK is not None:
        l = 1 - (1 - l) / (1 - lamK)
    return l


def main():
    res = {"models": {}, "pooled": {}}
    boots = {c: [] for c in CONTRASTS}
    points = {c: [] for c in CONTRASTS}
    for m in MODELS:
        Y, meta = load(m)
        U = sorted(r for r in Y if meta[r]["family"] == "null_U")
        tasks = sorted(set.intersection(*[set(Y[u]) for u in U]))
        T = len(tasks)
        Y0, P0, who0 = rows_for(U, meta, U, Y, tasks)
        F = {}
        for f, sel in FAMS.items():
            runs = sorted(r for r, k in meta.items() if sel(k))
            if runs:
                F[f] = rows_for(runs, meta, U, Y, tasks)[:2] + (runs,)
        allidx = np.arange(T)
        lamK = lam_of(*F["null_K"][:2], Y0, P0, allidx) if "null_K" in F else None
        canon = {"gauss1", "gauss0.3"}
        lam = {f: lam_of(v[0], v[1], Y0, P0, allidx, lamK if f in canon else None) for f, v in F.items() if f != "null_K"}
        # single-draw null noise, and 2-draw pseudo-family noise
        s0 = stats(Y0, P0)
        per_null = [lamc(stats(Y0[[i]], P0[[i]]), s0)[0] for i in range(len(U))]
        pair_null = [lamc(stats(Y0[list(p)], P0[list(p)]), s0)[0] for p in combinations(range(len(U)), 2)]
        M = dict(U=U, n_tasks=T, lam_K=rnd(lamK), lam={f: rnd(v) for f, v in lam.items()},
                 n_draws={f: len(v[2]) for f, v in F.items()},
                 null_single_draw_lam_sd=rnd(np.std(per_null, ddof=1)), null_pair_lam_sd=rnd(np.std(pair_null, ddof=1)),
                 null_pair_lam_max=rnd(max(pair_null)),
                 k_eq_rtn={f: rnd(np.sqrt(weight_err(F[f][2][0]) / weight_err(F["rtn_w4"][2][0])))
                           for f in ("rtn_w8", "rtn_w3") if f in F and "rtn_w4" in F and weight_err(F[f][2][0])},
                 contrasts={})
        bl = {c: [] for c in CONTRASTS}
        for _ in range(B):
            idx = rng.integers(0, T, T)
            lk = lam_of(*F["null_K"][:2], Y0, P0, idx) if "null_K" in F else None
            L = {f: lam_of(v[0], v[1], Y0, P0, idx, lk if f in canon else None) for f, v in F.items() if f != "null_K"}
            for a, b in CONTRASTS:
                if a in L and b in L:
                    bl[(a, b)].append(L[a] - L[b])
        for a, b in CONTRASTS:
            if bl[(a, b)]:
                d = lam[a] - lam[b]
                M["contrasts"][f"{a}-{b}"] = dict(diff=rnd(d), ci95=rnd(np.percentile(bl[(a, b)], [2.5, 97.5])),
                                                  p_le0=rnd(np.mean(np.array(bl[(a, b)]) <= 0)))
                boots[(a, b)].append(np.array(bl[(a, b)])); points[(a, b)].append(d)
        res["models"][m] = M
        print(m, M["lam"], "lamK", M["lam_K"], "null sd", M["null_single_draw_lam_sd"], M["null_pair_lam_sd"])
        print("   ", {k: (v["diff"], v["ci95"]) for k, v in M["contrasts"].items()})
    for c in CONTRASTS:
        if len(points[c]) >= 2:
            pb = np.mean(np.vstack(boots[c]), 0)
            res["pooled"][f"{c[0]}-{c[1]}"] = dict(models=len(points[c]), diff=rnd(np.mean(points[c])),
                                                  ci95=rnd(np.percentile(pb, [2.5, 97.5])), p_le0=rnd(np.mean(pb <= 0)),
                                                  n_models_positive=int(sum(p > 0 for p in points[c])))
    print("pooled", res["pooled"])
    dump("r08_size_generic", res)


if __name__ == "__main__":
    main()
