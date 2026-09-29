"""r01: capability reallocation under a shrink-to-attractor model, per model x family, against the nonce null U.

Model (PLAN_iter4 RQ2): a fixed perturbed checkpoint maps each task's null success probability p_i to
    p_i' = (1 - lam) p_i + lam c          (lam: reallocation intensity; c: attractor success rate)
Tasks are classified on a reference of n_ref = |U|-1 nonce-null draws as always-ok (p_hat = 1), always-fail (0),
coin (otherwise). With misclassification, a held-out NULL draw shows break b0 = E[1-p | ok], fix f0 = E[p | fail];
a family draw shows b = (1-lam) b0 + lam (1-c), f = (1-lam) f0 + lam c, hence
    lam = (b + f - b0 - f0) / (1 - b0 - f0),      c = (f - (1 - lam) f0) / lam.
Out-of-sample check: lam, c come from the extreme strata only; the model then PREDICTS the coin stratum:
    dCoin_pred = lam (c - mu0_coin),   mu0_coin = held-out null mean on coin tasks.
Reference sets are stratum-matched (docs/insights/NULL_RULE.md NR1-3): nonce-mates of a draw are removed from U; when
a draw has no mate, every size-n_ref subset of U is used and averaged, so family and null baselines always use the
same reference size. Canonical-prompt cells (gauss*_s*, bf16/eager = null_K) are also compared with U; their lam is
reported raw and composed-corrected: lam_P = 1 - (1 - lam_tot)/(1 - lam_K) (the canonical prompt is itself a fixed
nuisance with lam_K). Task bootstrap (B = 1000) for 95% CIs; tasks are the cluster, draws are not resampled
(few draws: the per-draw lam list is reported so draw spread is visible).
Usage: CLOQ_SNAPSHOT=<manifest> python r01_realloc.py  -> out/r01_realloc_<tag>.json
"""
import os
from collections import defaultdict
from itertools import combinations

import numpy as np

from r_common import dump, load, openloop, rnd, weight_err

MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3,q32").split(",")
B = 1000
rng = np.random.default_rng(20260929)


def ref_sets(r, meta, U):
    k = meta[r]
    if k["family"] == "null_U":
        return [tuple(u for u in U if u != r)]
    mates = [u for u in U if meta[u]["nonce"] is not None and meta[u]["nonce"] == k["nonce"]]
    pool = [u for u in U if u not in mates]
    n_ref = len(U) - 1
    if len(pool) <= n_ref:
        return [tuple(pool)]
    return list(combinations(pool, n_ref))


def rows_for(runs, meta, U, Y, tasks):
    """one row per (draw, reference set): y (nan = missing), p_hat."""
    ys, ps, who = [], [], []
    for r in runs:
        for R in ref_sets(r, meta, U):
            ys.append([Y[r].get(t, np.nan) for t in tasks])
            ps.append(np.mean([[Y[u][t] for t in tasks] for u in R], 0))
            who.append(r)
    return np.array(ys, float), np.array(ps, float), who


def stats(Yr, Pr, idx=None, mask=None):
    if idx is not None:
        Yr, Pr = Yr[:, idx], Pr[:, idx]
    if mask is not None:
        Yr, Pr = Yr[:, mask], Pr[:, mask]
    v = ~np.isnan(Yr)
    ok, fail = (Pr == 1) & v, (Pr == 0) & v
    coin = (Pr > 0) & (Pr < 1) & v
    y = np.nan_to_num(Yr)
    b = ((1 - y) * ok).sum() / max(ok.sum(), 1)
    f = (y * fail).sum() / max(fail.sum(), 1)
    mc = (y * coin).sum() / max(coin.sum(), 1)
    return dict(b=b, f=f, mu_coin=mc, mean_y=(y * v).sum() / v.sum(), n_ok=ok.sum() / len(Yr),
                n_fail=fail.sum() / len(Yr), n_coin=coin.sum() / len(Yr))


def lamc(s, s0):
    lam = (s["b"] + s["f"] - s0["b"] - s0["f"]) / (1 - s0["b"] - s0["f"])
    c = (s["f"] - (1 - lam) * s0["f"]) / lam if abs(lam) > 1e-9 else np.nan
    return lam, c


def analyse(Yf, Pf, Y0, P0, mask=None, lamK=None, cK=None, boot=True):
    s, s0 = stats(Yf, Pf, mask=mask), stats(Y0, P0, mask=mask)
    lam, c = lamc(s, s0)
    d_obs = s["mean_y"] - s0["mean_y"]
    dcoin_obs = s["mu_coin"] - s0["mu_coin"]
    dcoin_pred = lam * (c - s0["mu_coin"]) if np.isfinite(c) else np.nan
    res = dict(b=s["b"], f=s["f"], b0=s0["b"], f0=s0["f"], lam=lam, c=c, p_bar_null=s0["mean_y"],
               delta_obs=d_obs, delta_pred_from_extremes_plus_coin=None, dcoin_obs=dcoin_obs, dcoin_pred=dcoin_pred,
               n_ok=s["n_ok"], n_fail=s["n_fail"], n_coin=s["n_coin"])
    if lamK is not None:
        lamP = 1 - (1 - lam) / (1 - lamK)
        cP = (lam * c - (1 - lamP) * lamK * cK) / lamP if abs(lamP) > 1e-9 else np.nan
        res.update(lam_composed=lamP, c_composed=cP)
    if boot:
        T = Yf.shape[1] if mask is None else int(mask.sum())
        base = np.arange(Yf.shape[1]) if mask is None else np.where(mask)[0]
        bl, bc, bd, bdo = [], [], [], []
        for _ in range(B):
            idx = base[rng.integers(0, T, T)]
            sb, s0b = stats(Yf, Pf, idx=idx), stats(Y0, P0, idx=idx)
            l_, c_ = lamc(sb, s0b)
            bl.append(l_); bc.append(c_)
            bd.append(sb["mu_coin"] - s0b["mu_coin"] - (l_ * (c_ - s0b["mu_coin"]) if np.isfinite(c_) else np.nan))
            bdo.append(sb["mean_y"] - s0b["mean_y"])
        res.update(lam_ci=np.nanpercentile(bl, [2.5, 97.5]), c_ci=np.nanpercentile(bc, [2.5, 97.5]),
                   coin_resid_ci=np.nanpercentile(bd, [2.5, 97.5]), delta_obs_ci=np.nanpercentile(bdo, [2.5, 97.5]),
                   p_lam_le0=float(np.mean(np.array(bl) <= 0)))
    return {k: (rnd(v) if not isinstance(v, (dict, str)) and v is not None else v) for k, v in res.items()}


def per_draw_lam(Yf, Pf, who, Y0, P0):
    s0 = stats(Y0, P0)
    out = {}
    for r in sorted(set(who)):
        rows = [i for i, w in enumerate(who) if w == r]
        out[r] = rnd(lamc(stats(Yf[rows], Pf[rows]), s0)[0])
    return out


def main():
    res = {"models": {}}
    for m in MODELS:
        Y, meta = load(m)
        U = sorted(r for r in Y if meta[r]["family"] == "null_U")
        if len(U) < 4:
            print(m, "skip: |U| =", len(U)); continue
        tasks = sorted(set.intersection(*[set(Y[u]) for u in U]))
        dom = np.array([t[0] for t in tasks])
        Y0, P0, who0 = rows_for(U, meta, U, Y, tasks)
        fams = defaultdict(list)
        for r, k in meta.items():
            if k["family"] == "null_U":
                continue
            fams[k["family"]].append(r)
            if k["kind"] in ("gauss_canon", "gauss_fixed") or k["ckpt"].startswith("gptq_w4_d"):
                fams["ckpt:" + k["ckpt"] + ("_fixed" if k["kind"] == "gauss_fixed" else "")].append(r)
        M = {"U": U, "n_ref": len(U) - 1, "n_tasks": len(tasks), "null_loo": {}, "families": {}}
        s0 = stats(Y0, P0)
        M["null_loo"] = {k: rnd(v) for k, v in s0.items()}
        M["null_loo"]["per_draw_b_f"] = {w: rnd([stats(Y0[[i]], P0[[i]])[x] for x in ("b", "f")]) for i, w in enumerate(who0)}
        lamK = cK = None
        order = ["null_K"] + sorted(f for f in fams if f != "null_K")
        for f in order:
            if f not in fams:
                continue
            runs = sorted(fams[f])
            Yf, Pf, who = rows_for(runs, meta, U, Y, tasks)
            canon = meta[runs[0]]["stratum"] == "canonical" and f != "null_K"
            r_all = analyse(Yf, Pf, Y0, P0, lamK=lamK if canon else None, cK=cK if canon else None)
            if f == "null_K":
                lamK, cK = r_all["lam"], r_all["c"]
            dom_res = {d: analyse(Yf, Pf, Y0, P0, mask=(dom == d), boot=False) for d in ("retail", "airline")}
            k0 = meta[runs[0]]
            ol_cell = (k0["ckpt"] if k0["kind"] in ("quant", "gauss_canon") else None)
            fam_ol = None
            if k0["kind"] == "quant":
                fam_ol = openloop(m, k0["ckpt"]) or openloop(m, k0["family"])
            elif k0["kind"] == "gauss_canon" and f.startswith("ckpt:"):
                fam_ol = openloop(m, k0["ckpt"])
            elif k0["kind"] == "gauss_fixed":
                fam_ol = openloop(m, k0["ckpt"])  # same checkpoint as the canonical seed cell
            M["families"][f] = dict(kind=k0["kind"], stratum=k0["stratum"], runs=runs,
                                    nonces=sorted({str(meta[r]["nonce"]) for r in runs}), n_draws=len(runs),
                                    **r_all, per_draw_lam=per_draw_lam(Yf, Pf, who, Y0, P0),
                                    by_domain=dom_res, openloop=fam_ol,
                                    weight_err=weight_err(runs[0]))
            print(m, f, len(runs), "lam", r_all["lam"], r_all.get("lam_ci"), "c", r_all["c"], "pbar", r_all["p_bar_null"],
                  "dcoin obs/pred", r_all["dcoin_obs"], r_all["dcoin_pred"])
        res["models"][m] = M
    dump("r01_realloc", res)


if __name__ == "__main__":
    main()
