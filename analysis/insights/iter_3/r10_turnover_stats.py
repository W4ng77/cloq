"""r10: R3/R4 statistics for the lambda-c turnover analysis (paper/review_storyline_v4.md W1-W8, R3, R4). 0 GPU-h.

TL;DR of method. Same estimator as r01 (shrink-to-attractor lam, c against the stratum-matched nonce null U, nonce-mates
removed, reference size n_ref = |U|-1), with five changes:
  1. Draw weighting. Each draw gets weight 1 (its per-task counts are averaged over its reference sets). r01 pools rows,
     so a fresh-nonce draw (|U| reference sets) weighs |U| times a nonce-mate draw (1 set); r01's point estimates
     differ slightly for mixed families.
  2. Hierarchical, paired bootstrap (B = CLOQ_B, default 2000). One replicate = one task resample (shared by every family
     of the model, and by the null) + a null-draw resample (U draws with replacement, shared) + for every family a
     two-stage resample: checkpoints with replacement, then draws with replacement inside each checkpoint. Contrasts
     (dlam, dc, dDelta) are differences within the same replicate (paired). Single-checkpoint families contribute no
     checkpoint variance: that is a data limit, flagged per family (n_ckpt).
  3. Numerics/perturbation floor (R3). Floor families (declared): rot_bf16 (function-preserving rotation, fresh nonces),
     null_K (canonical prompt and eager numerics), gauss0.001, gauss0.003 (canonical cells, composed-corrected for lam_K).
     floor = equal-weight mean of the available floor families' lam, in the same replicate; band = [min, max] of their
     point estimates. excess = lam - floor with CI and one-sided p = P*(excess <= 0); also break/fix ratios to the
     floor's b/f.
  4. Declared tests, margin 0.10 on lam:
       TOST   |lam_m - lam_RTN| < 0.10 (W4 methods), p = max(P*(d >= .1), P*(d <= -.1)) (percentile bootstrap);
       NI     lam_RTN - lam_rand < 0.10 for matched random error (gauss1 canonical-composed, gauss1_fixed, gshape_w4,
              rtnsign_w4), p = P*(d >= .1); also the strict one-sided P*(d >= 0);
       floor  excess > 0 (one-sided) for RTN/GPTQ/AWQ-W4; W8 within +-0.10 of the floor (TOST);
       c      dc = c_m - c_RTN != 0 (two-sided), only where both c are identified (below).
     Pooling across models: equal-weight mean of per-model estimates; per-model bootstraps are independent and combined
     replicate by replicate (a stratified bootstrap, strata = models). Inverse-variance pooling reported as sensitivity.
     Holm (alpha 0.05) over the whole declared family (listed in out JSON 'holm_family'); per-model tests are descriptive.
  5. Identification and model checks. c (and dc) is reported as 'unidentified' when the lam 2.5% bound <= 0.10.
     Coin-stratum check (declared rule): a cell PASSES iff the 95% CI of dCoin_obs - dCoin_pred contains 0
     (dCoin_pred = lam c - lam mu0_coin = f - (1-lam) f0 - lam mu0_coin, finite even when c is not identified). Expected
     pass rate under the model ~95%; the binomial tail of the observed fails vs 5% is reported (cells share the null, so
     it is approximate).
Also: variance decomposition of lam, c, Delta into method / checkpoint / nonce (method-of-moments, conditional on the
task set: a draw-only bootstrap with tasks and null fixed gives each checkpoint's nonce variance); the lambda-level
partial Spearman rho(open-loop flip rate, lam | log dose) from E3 (analysis/openloop/a6k2) with a model-stratified cell
bootstrap (fixes the 'partial rho 0.86' provenance: that number is A2-15, flip vs per-decision hazard, d01); and the
task-set provenance (manifests/task_split_v0.json evaluation split vs every model's run task_manifest).
Usage: CLOQ_SNAPSHOT=<manifest> CLOQ_TAG=<tag> python r10_turnover_stats.py -> out/r10_turnover_stats_<tag>.json
"""
import hashlib
import json
import os
import re
from collections import defaultdict

import numpy as np
from scipy.stats import binomtest, rankdata, spearmanr

from r01_realloc import ref_sets
from r_common import OPENLOOP, RUNS, SNAP, dump, load, rnd, weight_err

MODELS = os.environ.get("CLOQ_MODELS", "q4,q8,q14,q30a3,q32,l8").split(",")
B = int(os.environ.get("CLOQ_B", 2000))
BD = 1000  # draw-only bootstrap for the variance decomposition
MARGIN = 0.10
LAM_ID = 0.10
ALPHA = 0.05
W4 = ["rtn_w4", "gptq_w4", "awq_w4", "rot_rtn_w4", "rot_gptq_w4", "mxfp4", "nf4"]
RANDOM = ["gauss1", "gauss1_fixed", "gshape_w4", "rtnsign_w4"]
FLOOR = ["rot_bf16", "null_K", "gauss0.001", "gauss0.003"]
rng = np.random.default_rng(20260930)
ROOT = RUNS.parent


# ---------------------------------------------------------------- data
def draw_arrays(r, meta, U, Y, tasks):
    """(8, T) per-task sums for one draw, averaged over its reference sets:
    ok, fail, coin, break (1-y on ok), fix (y on fail), y on coin, valid, y."""
    y = np.array([Y[r].get(t, np.nan) for t in tasks], float)
    v = (~np.isnan(y)).astype(float)
    y0 = np.nan_to_num(y)
    Rs = ref_sets(r, meta, U)
    acc = np.zeros((3, len(tasks)))
    for R in Rs:
        p = np.mean([[Y[u][t] for t in tasks] for u in R], 0)
        acc += np.stack([p == 1, p == 0, (p > 0) & (p < 1)])
    ok, fail, coin = acc / len(Rs) * v
    return np.stack([ok, fail, coin, (1 - y0) * ok, y0 * fail, y0 * coin, v, y0 * v])


def summ(S):
    with np.errstate(invalid="ignore", divide="ignore"):
        return dict(b=S[3] / S[0], f=S[4] / S[1], mu_coin=S[5] / S[2], mean_y=S[7] / S[6])


def est(S, S0, K=None):
    """lam, c, Delta, coin check for one family; K = (lam_K, c_K, Delta_K) composes canonical-prompt cells."""
    s, s0 = summ(S), summ(S0)
    den = 1 - s0["b"] - s0["f"]
    lam = (s["b"] + s["f"] - s0["b"] - s0["f"]) / den
    lamc = s["f"] - (1 - lam) * s0["f"]
    c = lamc / lam if abs(lam) > 1e-9 else np.nan
    d = s["mean_y"] - s0["mean_y"]
    dco = s["mu_coin"] - s0["mu_coin"]
    dcp = lamc - lam * s0["mu_coin"]
    o = dict(lam=lam, c=c, delta=d, b=s["b"], f=s["f"], dcoin_obs=dco, dcoin_pred=dcp, coin_resid=dco - dcp)
    o["lam_raw"], o["c_raw"], o["delta_raw"] = lam, c, d
    if K is not None:  # composed: remove the canonical-prompt nuisance (r01 lam_P, c_P)
        lK, cK, dK = K
        lP = 1 - (1 - lam) / (1 - lK)
        o["lam"] = lP
        o["c"] = (lamc - (1 - lP) * lK * cK) / lP if abs(lP) > 1e-9 else np.nan
        o["delta"] = d - dK
    return o


def build(m):
    Y, meta = load(m)
    U = sorted(r for r in Y if meta[r]["family"] == "null_U")
    if len(U) < 4:
        return None, f"|U| = {len(U)} < 4"
    tasks = sorted(set.intersection(*[set(Y[u]) for u in U]))
    X0 = np.stack([draw_arrays(u, meta, U, Y, tasks) for u in U])
    fams = defaultdict(lambda: defaultdict(list))
    for r, k in meta.items():
        if k["family"] == "null_U":
            continue
        ck = "ref" if k["family"] == "null_K" else k["ckpt"]
        fams[k["family"]][ck].append(r)
    units = {}
    for f, cks in fams.items():
        runs = [r for ck in sorted(cks) for r in sorted(cks[ck])]
        X = np.stack([draw_arrays(r, meta, U, Y, tasks) for r in runs])
        cid = np.array([ck for ck in sorted(cks) for _ in cks[ck]])
        k0 = meta[runs[0]]
        base = dict(kind=k0["kind"], stratum=k0["stratum"], canon=(k0["stratum"] == "canonical" and f != "null_K"))
        units[f] = dict(base, family=f, runs=runs, cid=cid, X=X, n_ckpt=len(cks), n_draws=len(runs))
        if len(cks) > 1 or k0["kind"] in ("gauss_canon", "gauss_fixed"):
            for ck in sorted(cks):
                name = "ckpt:" + ck + ("_fixed" if k0["kind"] == "gauss_fixed" else "")
                i = cid == ck
                units[name] = dict(base, family=f, runs=[r for r, c_ in zip(runs, cid) if c_ == ck], cid=cid[i],
                                   X=X[i], n_ckpt=1, n_draws=int(i.sum()))
    return dict(U=U, tasks=tasks, X0=X0, units=units, meta=meta), None


def weights(cid, hier=True, ckpt_level=True):
    """two-stage resample: checkpoints with replacement, then draws within each checkpoint -> count per draw."""
    w = np.zeros(len(cid))
    cks = sorted(set(cid))
    picks = [cks[i] for i in rng.integers(0, len(cks), len(cks))] if ckpt_level else cks
    for ck in picks:
        idx = np.where(cid == ck)[0]
        sel = idx[rng.integers(0, len(idx), len(idx))] if hier else idx
        np.add.at(w, sel, 1)
    return w


def run_all(D, w0, u, wf):
    S0 = np.einsum("d,dkt,t->k", w0, D["X0"], u)
    out = {}
    K = None
    if "null_K" in D["units"]:
        x = D["units"]["null_K"]
        out["null_K"] = est(np.einsum("d,dkt,t->k", wf["null_K"], x["X"], u), S0)
        K = (out["null_K"]["lam"], out["null_K"]["c"], out["null_K"]["delta"])
    for n, x in D["units"].items():
        if n == "null_K":
            continue
        out[n] = est(np.einsum("d,dkt,t->k", wf[n], x["X"], u), S0, K if x["canon"] else None)
    fl = [out[f] for f in FLOOR if f in out]
    if fl:
        out["_floor"] = dict(lam=np.mean([o["lam"] for o in fl]), b=np.mean([o["b"] for o in fl]),
                             f=np.mean([o["f"] for o in fl]))
    return out


# ---------------------------------------------------------------- statistics helpers
def ci(a, q=(2.5, 97.5)):
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    return rnd(np.percentile(a, q)) if len(a) else None


def p_ge(a, x):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    return float((1 + np.sum(a >= x)) / (1 + len(a))) if len(a) else None


def p_le(a, x):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    return float((1 + np.sum(a <= x)) / (1 + len(a))) if len(a) else None


def p_two(a):
    return min(1.0, 2 * min(p_ge(a, 0), p_le(a, 0)))


def holm(ps):
    order = np.argsort(ps)
    adj = np.zeros(len(ps)); run = 0
    for r, i in enumerate(order):
        run = max(run, min(1, (len(ps) - r) * ps[i]))
        adj[i] = run
    return adj


# ---------------------------------------------------------------- variance decomposition
def decompose(D, point, lamci):
    """method / checkpoint / nonce components of lam, c, Delta for W4 methods, and of gaussian seeds, conditional on
    the task set (tasks and null fixed; draws resampled within each checkpoint)."""
    T = len(D["tasks"]); u = np.ones(T); w0 = np.ones(len(D["X0"]))
    S0 = np.einsum("d,dkt,t->k", w0, D["X0"], u)
    K = None
    if "null_K" in D["units"]:
        x = D["units"]["null_K"]; o = est(np.einsum("d,dkt,t->k", np.ones(len(x["cid"])), x["X"], u), S0)
        K = (o["lam"], o["c"], o["delta"])
    # checkpoint-level units: W4 families with one checkpoint (the family itself), ckpt:<name> sub-units of W4 families
    # with several, and fixed-checkpoint gaussian controls (nonce variance of a gaussian checkpoint)
    ck_units = {n: x for n, x in D["units"].items()
                if (x["family"] in W4 and (n.startswith("ckpt:") or (n == x["family"] and x["n_ckpt"] == 1)))
                or (x["kind"] == "gauss_fixed" and n.startswith("ckpt:"))}
    rows = {}
    for n, x in ck_units.items():
        th = {s: [] for s in ("lam", "c", "delta")}
        for _ in range(BD if x["n_draws"] > 1 else 0):
            w = weights(x["cid"], hier=True, ckpt_level=False)
            o = est(np.einsum("d,dkt,t->k", w, x["X"], u), S0, K if x["canon"] else None)
            for s in th:
                th[s].append(o[s])
        p = point[n]
        nd = x["n_draws"]
        rows[n] = dict(family=x["family"], n_draws=nd, lam=p["lam"], c=p["c"], delta=p["delta"],
                       c_identified=bool(lamci[n] is not None and lamci[n][0] > LAM_ID),
                       single_draw_var={s: (float(np.nanvar(v, ddof=1)) * nd * nd / (nd - 1) if nd > 1 else None)
                                        for s, v in th.items()})
    out = {}
    for s in ("lam", "c", "delta"):
        # nonce: single-draw variance pooled over checkpoints with >= 2 draws (W4 quantizer checkpoints only)
        sv = [(r["single_draw_var"][s], r["n_draws"] - 1) for r in rows.values()
              if r["family"] in W4 and r["single_draw_var"][s] is not None and np.isfinite(r["single_draw_var"][s])
              and (s != "c" or r["c_identified"])]
        s2n = sum(v * d for v, d in sv) / sum(d for _, d in sv) if sv else None
        by_m = defaultdict(list)
        for n, r in rows.items():
            if r["family"] in W4 and (s != "c" or r["c_identified"]):
                by_m[r["family"]].append((r[s], r["n_draws"]))
        # checkpoint: within-method between-checkpoint variance minus nonce noise of the checkpoint means
        ck = []
        for f, v in by_m.items():
            if len(v) >= 2 and s2n is not None:
                vals = np.array([a for a, _ in v]); S2 = float(np.var(vals, ddof=1))
                ck.append((S2 - np.mean([s2n / nd for _, nd in v]), len(v) - 1, f, S2))
        s2c = sum(a * d for a, d, _, _ in ck) / sum(d for _, d, _, _ in ck) if ck else None
        # method: between-method variance of method means minus checkpoint + nonce noise of those means
        mm = {f: (np.mean([a for a, _ in v]), len(v), np.mean([s2n / nd for _, nd in v]) if s2n is not None else None)
              for f, v in by_m.items()}
        s2m = None
        if len(mm) >= 2 and s2c is not None:
            S2b = float(np.var([a for a, _, _ in mm.values()], ddof=1))
            s2m = S2b - np.mean([(max(s2c, 0) + e) / k for _, k, e in mm.values()])
        out[s] = dict(nonce_var_single_draw=rnd(s2n), nonce_df=sum(d for _, d in sv),
                      ckpt_var=rnd(s2c), ckpt_df=sum(d for _, d, _, _ in ck),
                      ckpt_by_method={f: dict(S2_between_ckpts=rnd(S2), minus_nonce=rnd(a)) for a, _, f, S2 in ck},
                      method_var=rnd(s2m), n_methods=len(mm),
                      method_means={f: rnd(a) for f, (a, _, _) in mm.items()},
                      ratio_method_to_ckpt=rnd(s2m / s2c) if (s2m is not None and s2c and s2c > 0) else None)
    # gaussian seeds: spread of canonical single-draw seed cells (checkpoint + draw, inseparable) vs fixed-ckpt nonce var
    gs = {}
    for k in sorted({x["family"] for x in D["units"].values() if x["kind"] == "gauss_canon"}):
        seeds = [n for n, x in D["units"].items() if n.startswith("ckpt:") and x["family"] == k]
        fixed = [n for n, r in rows.items() if D["units"][n]["kind"] == "gauss_fixed" and
                 D["units"][n]["family"] == k + "_fixed"]
        if len(seeds) < 2:
            continue
        e = {}
        for s in ("lam", "c", "delta"):
            vals = [point[n][s] for n in seeds if s != "c" or (lamci[n] is not None and lamci[n][0] > LAM_ID)]
            nv = [rows[n]["single_draw_var"][s] for n in fixed if rows[n]["single_draw_var"][s] is not None]
            S2 = float(np.var(vals, ddof=1)) if len(vals) >= 2 else None
            e[s] = dict(n_seeds=len(vals), values=rnd(vals), S2_across_seeds=rnd(S2),
                        nonce_var_from_fixed_ckpt=rnd(np.mean(nv)) if nv else None,
                        ckpt_var_est=rnd(S2 - np.mean(nv)) if (S2 is not None and nv) else None)
        gs[k] = e
    return dict(components=out, gauss_seeds=gs,
                per_ckpt={n: dict(family=r["family"], n_draws=r["n_draws"], lam=rnd(r["lam"]),
                                  c=rnd(r["c"]) if r["c_identified"] else None, delta=rnd(r["delta"]),
                                  single_draw_var={s: rnd(v) for s, v in r["single_draw_var"].items()})
                          for n, r in rows.items()})


# ---------------------------------------------------------------- open-loop partial rho for lam (provenance fix)
def dose_of(m, stem, D):
    g = re.match(r"gauss([\d.]+)_s\d+$", stem)
    if g:
        return float(g.group(1)), "gauss k (by construction)"
    w4 = weight_err(f"a6k2_{m}_rtn_w4_n1") or weight_err(f"a6k2_{m}_rtn_w4_q2")
    runs = [r for x in D["units"].values() for r, c_ in zip(x["runs"], x["cid"]) if c_ == stem]
    e = weight_err(runs[0]) if runs else None
    if e and w4:
        return (e / w4) ** 0.5, "measured sqrt(rel. weight err / RTN-W4)"
    b = re.search(r"_w(\d)", stem)
    if b:
        rt = [r for x in D["units"].values() for r, c_ in zip(x["runs"], x["cid"]) if c_ == f"rtn_w{b.group(1)}"]
        e = weight_err(rt[0]) if rt else None
        if e and w4:
            return (e / w4) ** 0.5, f"nominal: RTN-W{b.group(1)} k_eq"
    return None, None


def partial_spearman(x, y, z):
    rxy = spearmanr(x, y)[0]; rxz = spearmanr(x, z)[0]; ryz = spearmanr(y, z)[0]
    return float((rxy - rxz * ryz) / np.sqrt(max(1e-12, (1 - rxz ** 2) * (1 - ryz ** 2))))


def openloop_lambda(cells):
    out = {"n_cells": len(cells), "cells": cells}
    if len(cells) < 6:
        return out
    g = np.array([c["model"] for c in cells])

    def one(rows_idx):
        fl = np.array([cells[i]["flip_rate"] for i in rows_idx]); da = np.array([cells[i]["decision_any_flip"] for i in rows_idx])
        la = np.array([cells[i]["lam"] for i in rows_idx]); ds = np.log10([cells[i]["k_eq"] for i in rows_idx])
        return dict(rho_flip_lam=spearmanr(fl, la)[0], rho_dose_lam=spearmanr(ds, la)[0],
                    rho_dose_flip=spearmanr(ds, fl)[0], partial_flip_lam_given_dose=partial_spearman(fl, la, ds),
                    partial_anyflip_lam_given_dose=partial_spearman(da, la, ds))
    idx = np.arange(len(cells))
    pt = one(idx)
    bs = defaultdict(list)
    for _ in range(4000):
        sel = np.concatenate([rng.choice(np.where(g == mm)[0], (g == mm).sum()) for mm in sorted(set(g))])
        try:
            for k, v in one(sel).items():
                bs[k].append(v)
        except Exception:
            pass
    out.update({k: dict(est=rnd(v, 3), ci95=ci(bs[k])) for k, v in pt.items()})
    out["by_model"] = {}
    for mm in sorted(set(g)):
        i = np.where(g == mm)[0]
        if len(i) >= 5:
            out["by_model"][mm] = {k: rnd(v, 3) for k, v in one(i).items()}
    return out


# ---------------------------------------------------------------- provenance
def provenance(models):
    p = ROOT / "manifests/task_split_v0.json"
    d = json.load(open(p))
    dom = {k: dict(evaluation=len(v["evaluation"]), calibration=len(v["calibration"]),
                   excluded_unstable=len(v["excluded_unstable"]), n_usable=v["n_usable"],
                   stability_rule=v["stability_rule"]) for k, v in d["domains"].items()}
    match = {}
    for m in models:
        for r in (f"a6k2_{m}_null_n1", f"a6k2_{m}_bf16"):
            if (RUNS / r).exists():
                match[m] = {k: set(json.load(open(RUNS / r / k / "task_manifest.json"))["task_ids"]) ==
                            set(d["domains"][k]["evaluation"]) for k in d["domains"]}
                break
    return dict(task_split=dict(path=str(p.relative_to(ROOT)), sha256=hashlib.sha256(open(p, "rb").read()).hexdigest(),
                                bf16_run=d["bf16_run"], seed=d["seed"], by_domain=dom,
                                run_task_manifest_equals_evaluation_split=match,
                                note="85 tasks = 'evaluation' split (58 retail + 27 airline) of the 142 usable tasks; "
                                     "57 'calibration' tasks unused; 22 tasks excluded as unstable (legacy BF16 run "
                                     "ended by max_steps/error, i.e. termination not in stability_rule)."),
                partial_rho_086=dict(
                    source="analysis/insights/iter_2/out/d01_matched_dose.json (A2-15, docs/insights/iter_2_integrity.md s4)",
                    measures="partial Spearman rho(open-loop token flip rate, closed-loop per-decision first-divergence "
                             "HAZARD | log dose), 27 E3 cells on q4+q8, iteration-2 frozen snapshot 20260929T0732Z",
                    not_="a correlation with lam (task-outcome turnover); the lam correlations of r05 (rho 0.83 q4, "
                         "0.76 q8) have no dose control. The lam-level partial rho is computed here ('openloop_lambda')."),
                r01_unfrozen=dict(path="analysis/insights/iter_3/out/r01_realloc_unfrozen.json",
                                  note="last produced 2026-09-29 12:09 PDT (commit 11ca12d) with CLOQ_MODELS=q4,q8 and no "
                                       "snapshot (_snapshot.id null); left unchanged. The gated all-model r01 for this "
                                       "snapshot is out/r01_realloc_<tag>.json with the same tag as this file."))


# ---------------------------------------------------------------- main
def main():
    res = {"declared": dict(
        margin_lam=MARGIN, lam_identification_bound=LAM_ID, alpha=ALPHA, B=B, B_draw_only=BD,
        w4_methods=W4, matched_random=RANDOM, floor_families=FLOOR,
        floor_rule="floor = equal-weight mean of available floor families' lam (canonical gauss composed with lam_K); "
                   "band = [min, max] of their point estimates",
        coin_rule="PASS iff 95% hierarchical-bootstrap CI of (dCoin_obs - dCoin_pred) contains 0",
        c_rule="c reported only if the lam 2.5% bound > 0.10, else 'unidentified'",
        pooling="equal-weight mean over models having both families; per-model hierarchical bootstraps are independent "
                "and combined replicate-wise (stratified bootstrap, strata = models); inverse-variance weights as "
                "sensitivity",
        bootstrap="per replicate: tasks resampled (shared by all families + null), U null draws resampled (shared), "
                  "each family: checkpoints with replacement then draws within checkpoint with replacement",
        holm="Holm at alpha 0.05 over every test in 'holm_family' (pooled tests + per-model c contrasts)",
        declaration_status="declared in this script before its first run on snapshot " +
                           (SNAP["snapshot_id"] if SNAP else "none") + "; NOT a pre-registration: the reviewer and "
                           "the team had seen ungated q4/q8/q14 numbers"), "models": {}, "pooled": {}}
    boots, points, lamcis = {}, {}, {}
    skipped = {}
    ol_cells = []
    for m in MODELS:
        D, why = build(m)
        if D is None:
            skipped[m] = why; print(m, "skip:", why); continue
        T = len(D["tasks"]); units = D["units"]
        pt = run_all(D, np.ones(len(D["X0"])), np.ones(T), {n: np.ones(len(x["cid"])) for n, x in units.items()})
        bs = defaultdict(lambda: defaultdict(list))
        for _ in range(B):
            u = np.bincount(rng.integers(0, T, T), minlength=T).astype(float)
            w0 = np.bincount(rng.integers(0, len(D["X0"]), len(D["X0"])), minlength=len(D["X0"])).astype(float)
            wf = {n: weights(x["cid"]) for n, x in units.items()}
            o = run_all(D, w0, u, wf)
            for n, v in o.items():
                for s, val in v.items():
                    bs[n][s].append(val)
        bs = {n: {s: np.array(v, float) for s, v in d.items()} for n, d in bs.items()}
        boots[m], points[m] = bs, pt
        lamci = {n: ci(bs[n]["lam"]) for n in units}
        lamcis[m] = lamci
        fl_pts = {f: pt[f]["lam"] for f in FLOOR if f in pt}
        fams = {}
        for n, x in sorted(units.items()):
            p, b = pt[n], bs[n]
            ident = lamci[n] is not None and lamci[n][0] > LAM_ID
            e = dict(kind=x["kind"], stratum=x["stratum"], composed=x["canon"], n_ckpt=x["n_ckpt"], n_draws=x["n_draws"],
                     runs=x["runs"], ckpt_variance_in_ci=x["n_ckpt"] > 1,
                     lam=rnd(p["lam"]), lam_ci=lamci[n], p_lam_le0=rnd(p_le(b["lam"], 0)),
                     c=rnd(p["c"]) if ident else None, c_ci=ci(b["c"]) if ident else None,
                     c_status="identified" if ident else "unidentified (lam 2.5% bound <= 0.10)",
                     delta=rnd(p["delta"]), delta_ci=ci(b["delta"]), b=rnd(p["b"]), f=rnd(p["f"]),
                     dcoin_obs=rnd(p["dcoin_obs"]), dcoin_pred=rnd(p["dcoin_pred"]), coin_resid=rnd(p["coin_resid"]),
                     coin_resid_ci=ci(b["coin_resid"]))
            rc = e["coin_resid_ci"]
            e["coin_check"] = None if rc is None else ("pass" if rc[0] <= 0 <= rc[1] else "fail")
            if x["canon"]:
                e.update(lam_raw=rnd(p["lam_raw"]), delta_raw=rnd(p["delta_raw"]))
            if "_floor" in pt and n not in FLOOR:
                np.seterr(divide="ignore", invalid="ignore")  # floor b or f = 0 in a replicate -> inf ratio, dropped by ci()
                ex = b["lam"] - bs["_floor"]["lam"]
                e.update(excess_lam=rnd(p["lam"] - pt["_floor"]["lam"]), excess_lam_ci=ci(ex),
                         p_excess_le0=rnd(p_le(ex, 0)),
                         break_ratio_to_floor=rnd(p["b"] / pt["_floor"]["b"]) if pt["_floor"]["b"] > 0 else None,
                         break_ratio_ci=ci(b["b"] / bs["_floor"]["b"]),
                         fix_ratio_to_floor=rnd(p["f"] / pt["_floor"]["f"]) if pt["_floor"]["f"] > 0 else None,
                         fix_ratio_ci=ci(b["f"] / bs["_floor"]["f"]))
            fams[n] = e
        M = dict(U=D["U"], n_ref=len(D["U"]) - 1, n_tasks=T,
                 floor=dict(families={f: rnd(v) for f, v in fl_pts.items()},
                            lam=rnd(pt["_floor"]["lam"]) if "_floor" in pt else None,
                            lam_ci=ci(bs["_floor"]["lam"]) if "_floor" in pt else None,
                            band=rnd([min(fl_pts.values()), max(fl_pts.values())]) if fl_pts else None,
                            b=rnd(pt["_floor"]["b"]) if "_floor" in pt else None,
                            f=rnd(pt["_floor"]["f"]) if "_floor" in pt else None,
                            only_null_K=set(fl_pts) == {"null_K"}),
                 families=fams)
        # paired contrasts (descriptive per model)
        con = {}
        pairs = [(a, "rtn_w4") for a in W4[1:]] + [("gptq_w4", "awq_w4"), ("rot_rtn_w4", "rot_gptq_w4")] + \
                [("rtn_w4", r) for r in RANDOM] + [("ckpt:gptq_w4_d1", "ckpt:gptq_w4_d2"), ("ckpt:awq_w4", "ckpt:awq_w4_d2")]
        for a, bb in pairs:
            if a not in bs or bb not in bs:
                continue
            dl = bs[a]["lam"] - bs[bb]["lam"]; dd = bs[a]["delta"] - bs[bb]["delta"]
            both = (lamci[a][0] > LAM_ID) and (lamci[bb][0] > LAM_ID)
            dc = bs[a]["c"] - bs[bb]["c"]
            con[f"{a}-{bb}"] = dict(
                dlam=rnd(pt[a]["lam"] - pt[bb]["lam"]), dlam_ci95=ci(dl), dlam_ci90=ci(dl, (5, 95)),
                p_tost=rnd(max(p_ge(dl, MARGIN), p_le(dl, -MARGIN))), p_ni=rnd(p_ge(dl, MARGIN)),
                p_dlam_ge0=rnd(p_ge(dl, 0)),
                dc=rnd(pt[a]["c"] - pt[bb]["c"]) if both else None, dc_ci95=ci(dc) if both else None,
                p_dc_two=rnd(p_two(dc)) if both else None,
                dc_status="identified" if both else "unidentified",
                ddelta=rnd(pt[a]["delta"] - pt[bb]["delta"]), ddelta_ci95=ci(dd), p_ddelta_two=rnd(p_two(dd)))
        M["contrasts"] = con
        M["variance_decomposition"] = decompose(D, pt, lamci)
        # open-loop cells for the lam-level partial rho
        for pth in sorted((OPENLOOP / m).glob("*.json")) if (OPENLOOP / m).exists() else []:
            stem = pth.stem
            if stem.startswith("bf16"):
                continue
            unit = ("ckpt:" + stem) if ("ckpt:" + stem) in units else (stem if stem in units and units[stem]["n_ckpt"] == 1 else None)
            if unit is None:
                continue
            k_eq, src = dose_of(m, stem, D)
            ol = json.load(open(pth))
            if k_eq:
                ol_cells.append(dict(model=m, cell=stem, lam_unit=unit, lam=rnd(pt[unit]["lam"]), k_eq=rnd(k_eq),
                                     dose_source=src, flip_rate=rnd(ol["flip_rate"]),
                                     decision_any_flip=rnd(ol["decision_any_flip"]),
                                     # E3 outputs are not covered by the integrity gate and are still being written:
                                     # pin the exact input
                                     ol_file=str(pth.relative_to(ROOT)),
                                     ol_sha256=hashlib.sha256(open(pth, "rb").read()).hexdigest()[:16]))
        res["models"][m] = M
        print(m, "U", len(D["U"]), "T", T, "floor", M["floor"]["lam"], M["floor"]["band"])
        for n in [f for f in W4 + RANDOM + FLOOR + ["rtn_w8", "rtn_w3", "gptq_w3"] if f in fams]:
            e = fams[n]
            print(f"   {n:14s} lam {e['lam']} {e['lam_ci']} ex {e.get('excess_lam')} {e.get('excess_lam_ci')} "
                  f"c {e['c']} d {e['delta']} coin {e['coin_check']}")
    res["skipped_models"] = skipped
    # ---------------- pooled tests + Holm family
    fam_tests = []

    def pooled(a, bb, kind):
        ms = [m for m in boots if a in boots[m] and bb in boots[m]]
        if not ms:
            return None
        if bb == "_floor":
            d = [boots[m][a]["lam"] - boots[m]["_floor"]["lam"] for m in ms]
            pt_ = [points[m][a]["lam"] - points[m]["_floor"]["lam"] for m in ms]
        else:
            d = [boots[m][a]["lam"] - boots[m][bb]["lam"] for m in ms]
            pt_ = [points[m][a]["lam"] - points[m][bb]["lam"] for m in ms]
        pb = np.mean(np.vstack(d), 0)
        iv = np.array([1 / np.nanvar(x) for x in d]); iv /= iv.sum()
        pbiv = (np.vstack(d) * iv[:, None]).sum(0)
        o = dict(models=ms, per_model=dict(zip(ms, rnd(pt_))), est=rnd(np.mean(pt_)), ci95=ci(pb), ci90=ci(pb, (5, 95)),
                 est_iv=rnd(float(np.dot(iv, pt_))), ci90_iv=ci(pbiv, (5, 95)), iv_weights=dict(zip(ms, rnd(iv, 3))))
        if kind == "tost":
            o["p"] = max(p_ge(pb, MARGIN), p_le(pb, -MARGIN)); o["p_iv"] = max(p_ge(pbiv, MARGIN), p_le(pbiv, -MARGIN))
        elif kind == "ni":
            o["p"] = p_ge(pb, MARGIN); o["p_strict_le0"] = rnd(p_ge(pb, 0)); o["p_iv"] = p_ge(pbiv, MARGIN)
        elif kind == "excess":
            o["p"] = p_le(pb, 0); o["p_iv"] = p_le(pbiv, 0)
        return o

    for a in W4[1:]:
        o = pooled(a, "rtn_w4", "tost")
        if o:
            fam_tests.append(dict(id=f"TOST dlam {a}-rtn_w4 pooled", claim="lam method-invariant at W4 (|dlam|<0.10)", **o))
    for r in RANDOM:
        o = pooled("rtn_w4", r, "ni")
        if o:
            fam_tests.append(dict(id=f"NI lam rtn_w4-{r} < +0.10 pooled", claim="RTN re-rolls no more than matched random error", **o))
    for a in ("rtn_w4", "gptq_w4", "awq_w4"):
        o = pooled(a, "_floor", "excess")
        if o:
            fam_tests.append(dict(id=f"excess lam {a} - floor > 0 pooled", claim="W4 turnover above the numerics floor", **o))
    o = pooled("rtn_w8", "_floor", "tost")
    if o:
        fam_tests.append(dict(id="TOST lam rtn_w8 - floor pooled", claim="W8 at the floor (|excess|<0.10)", **o))
    for m, M in res["models"].items():
        for a in W4[1:]:
            k = f"{a}-rtn_w4"
            if k in M["contrasts"] and M["contrasts"][k]["dc_status"] == "identified":
                cc = M["contrasts"][k]
                fam_tests.append(dict(id=f"dc {a}-rtn_w4 {m}", claim="c follows method (dc != 0)", models=[m],
                                      est=cc["dc"], ci95=cc["dc_ci95"], p=cc["p_dc_two"]))
    adj = holm([t["p"] for t in fam_tests])
    for t, a in zip(fam_tests, adj):
        t["p"] = rnd(t["p"]); t["p_holm"] = rnd(a)
        t["verdict"] = "reject H0 (claim supported)" if a < ALPHA else "not supported after Holm"
    res["holm_family"] = fam_tests
    res["holm_family_not_testable"] = [
        f"dc {a}-rtn_w4 {m}" for m, M in res["models"].items() for a in W4[1:]
        if f"{a}-rtn_w4" in M["contrasts"] and M["contrasts"][f"{a}-rtn_w4"]["dc_status"] != "identified"]
    # ---------------- coin-check pass rate (families only, not ckpt sub-units)
    cc = defaultdict(lambda: [0, 0])
    fails = []
    widths = defaultdict(list)
    for m, M in res["models"].items():
        for n, e in M["families"].items():
            if n.startswith("ckpt:") or e["coin_check"] is None:
                continue
            cc[m][0] += 1; cc["all"][0] += 1
            w = e["coin_resid_ci"][1] - e["coin_resid_ci"][0]
            widths[m].append(w); widths["all"].append(w)
            if e["coin_check"] == "pass":
                cc[m][1] += 1; cc["all"][1] += 1
            else:
                fails.append(f"{m}/{n} resid {e['coin_resid']} {e['coin_resid_ci']}")
    res["coin_check"] = {k: dict(n_cells=v[0], n_pass=v[1], pass_rate=rnd(v[1] / v[0]) if v[0] else None,
                                 binom_p_fails_vs_5pct=rnd(binomtest(v[0] - v[1], v[0], 0.05, alternative="greater").pvalue)
                                 if v[0] else None, median_resid_ci_width=rnd(np.median(widths[k])))
                         for k, v in cc.items()}
    res["coin_check"]["fails"] = fails
    res["openloop_lambda"] = openloop_lambda(ol_cells)
    res["provenance"] = provenance([m for m in MODELS if m in res["models"]])
    print("holm:")
    for t in fam_tests:
        print(f"  {t['id']:42s} est {t['est']} ci95 {t['ci95']} p {t['p']} holm {t['p_holm']}")
    print("coin", {k: v for k, v in res["coin_check"].items() if k != "fails"})
    ol = res["openloop_lambda"]
    print("openloop lam", ol["n_cells"], {k: ol[k] for k in ol if k.startswith(("rho", "partial"))})
    dump("r10_turnover_stats", res)


if __name__ == "__main__":
    main()
