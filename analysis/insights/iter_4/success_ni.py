"""success_ni (population of calibration draws; W64 label): paired quantized-vs-BF16 success differences with non-inferiority / equivalence (TOST) / ordinary tests,
and task-level difference effect sizes (Delta, D, V), per model x method x checkpoint and pre-declared equal-weight pools.

W64 (GPT-6.1 code review): the model x method pools here average checkpoints d1-d4, i.e. they describe the population
of calibration draws. They are not an equivalence statement about d1, the checkpoint every fork uses; the fork-aligned
analysis is success_ni_aligned.py (d1 only, fork tasks x nonce blocks, crossed bootstrap, joint across models).

Plan: docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md §B "Success" and §F; decisions and the epsilon justification in
docs/insights/METHODOLOGY_REVISION.md §Success (epsilon = 3 pp fixed on 2026-09-30, before any a6k2_*_bfpair outcome
exists; 5 pp is a looser sensitivity analysis only and never replaces 3 pp).

Design (paired on the prompt nonce; simulator configuration is shared). Each quantized draw Q (checkpoint j, nonce nu)
is paired with the BF16 draw B on the SAME nonce nu: a6k2_<m>_null_n<k> for the null nonces n1-n8 and
a6k2_<m>_bfpair_q<k> for the fresh nonces q1-q5 (queued W28). One pair = one replicate block r of checkpoint j.
Outcome y = DB success (iter_2 common.outcomes: db_match and normal termination; infrastructure_error = missing,
agent-side overflow / parse error = failure), retail + airline dev tasks, q4 airline 45 removed (W17).
Task set per cell = tasks scored in every pair of the cell (complete case; dropped counts reported).
  Run-level first:  D_jr = mean_t (y_Q - y_B) over the cell's tasks;  cell estimate  Dbar_j = mean_r D_jr.
  SE (fixed tasks, fixed checkpoints; population = repeated runs):  s2 = pooled within-cell variance of D_jr over the
    model's primary cells (df = sum_j (R_j - 1)), SE_j = sqrt(s2 / R_j); t quantiles with that df.
  Pools (equal weights, pre-declared): model x method (d1-d4), model (GPTQ, AWQ), method (q4, q8), all (q4, q8).
    Cells of one model share BF16 draws on common nonces, so Cov(D_jr, D_kr) = c for j != k on the same nonce;
    c = sigma2_u of D_jr = theta_j + u_nu + e_jr (Henderson III: SSE and R(u | mu, theta)); Var(pool) =
    sum_j w_j^2 s2/R_j + sum_{j != k} w_j w_k |nu_j & nu_k| / (R_j R_k) max(c, 0). Models are independent; across
    models Welch-Satterthwaite df.
  Tests (epsilon = 0.03 primary, 0.05 sensitivity):
    non-inferiority  H0: Delta <= -eps;  pass iff lower one-sided 95% bound  Dbar - t_.95 SE > -eps
    equivalence TOST pass iff the 90% CI  Dbar +- t_.95 SE  lies inside (-eps, +eps)
    ordinary         two-sided 95% CI and t-test p for Delta = 0 (reported separately)
  Task-level effect sizes (per cell, R >= 2 blocks; Z_rt = y_Qrt - y_Brt, equal task weights w_t = 1/N):
    Delta_hat = mean_t mean_r Z_rt
    D_hat     = sum_t w_t [ (sum_r Z_rt)^2 - sum_r Z_rt^2 ] / (R (R-1))    unbiased for E_t[(q_t - p_t)^2]; only
                cross-block products (independent replicate blocks); the same-nonce coupled (Q_r, B_r) products are
                excluded by construction
    Delta2_U  = sum_{r != s} Zbar_r Zbar_s / (R (R-1))                    unbiased for Delta^2
    V_hat     = D_hat - Delta2_U                                          task heterogeneity beyond the mean change
    Hamming cross-check: D_H = H_QB - (H_QQ + H_BB)/2 with H over distinct blocks r != s (identical to D_hat by
    algebra; checks the implementation) and an extended form using every same-model BF16 draw for H_BB and every
    different-nonce (Q, B) pair for H_QB.
    Negative estimates are kept; no exact test is claimed for D near 0.
  Generalisation to new tasks (separate analysis): task-id-clustered crossed resampling, B = 2000: task ids resampled
    with replacement (shared by every cell of the model, crossed with checkpoints and nonces) and nonce blocks by
    Poisson(1) weights per nonce (shared across cells), percentile CIs.
Secondary cells (same machinery, outside the pools): RTN-W4, rotated BF16 (numerics control), Gaussian k=1 fixed seeds
s1-s5 (fixed random weight perturbation: a control intervention, not a 'no change' null).

Modes
  real (default): refuses unless every a6k2_{q4,q8}_bfpair_q{1..5} run is admitted in the snapshot with its registered
       nonce (q1 6d1f0b3e, q2 f07a5c21, q3 4c8e1a7f, q4 b9d2e605, q5 e1a47c3d). Make a fresh snapshot after they finish:
       python analysis/insights/iter_2/integrity.py --out analysis/insights/iter_3/out/snapshot_live_<utc>.json
  --dev: DEVELOPMENT ONLY, NOT A RESULT. BF16 on fresh nonce q<k> is replaced by the null draw null_n<k> (a different
       nonce), so those pairs are NOT nonce-paired; pairs on n1/n2 (and RTN n1-n5) are genuine. Output tagged DEV.
Usage:
  source scripts/a6000/env.sh; cd analysis/insights/iter_4
  python success_ni.py --dev --snapshot /data/ziyangs/cloq/analysis/insights/iter_3/out/snapshot_live_20260930T0044Z.json
  python success_ni.py --snapshot /data/ziyangs/cloq/analysis/insights/iter_3/out/snapshot_live_<utc>.json [--with-fdev]
-> out/success_ni_{DEV|REAL}[_fdev]_<snapshot id>.json
Primary = pairs on n1-n8 and q1-q5 (the W28 design). --with-fdev (declared sensitivity) adds the fork development
blocks f01-f17 (W29a) where both the BF16 and the quantized draw on that nonce are admitted.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = Path("/data/ziyangs/cloq")
MODELS = ("q4", "q8")
DOMS = ("retail", "airline")
DROP = {"q4": {("airline", "45")}}
EPS = (0.03, 0.05)
FRESH = {"q1": "6d1f0b3e", "q2": "f07a5c21", "q3": "4c8e1a7f", "q4": "b9d2e605", "q5": "e1a47c3d"}
SEED = 20260930
B_BOOT = 2000
PRIMARY = {  # method -> checkpoint -> run suffix stem (draw suffix appended)
    "gptq_w4": {"d1": "gptq_w4_d1", "d2": "gptq_w4_d2", "d3": "gptq_w4_d3", "d4": "gptq_w4_d4"},
    "awq_w4": {"d1": "awq_w4", "d2": "awq_w4_d2", "d3": "awq_w4_d3", "d4": "awq_w4_d4"},
}
SECONDARY = {"rtn_w4": {"d1": "rtn_w4"}, "rot_bf16": {"-": "rot_bf16"},
             "gauss1_fixed": {f"s{s}": f"gauss1_s{s}" for s in (1, 2, 4, 5)}}
C2 = SNAP = None


def rng_for(name):
    return np.random.default_rng([SEED, zlib.crc32(name.encode())])


def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def rnd(x, k=4):
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [rnd(v, k) for v in list(x)]
    x = float(x)
    return None if not np.isfinite(x) else round(x, k)


def refuse(msg):
    sys.stderr.write(f"REFUSED: {msg}\n")
    sys.exit(2)


# ------------------------------------------------------------------------------------------------ data
def outcomes(run, m):
    y = {}
    for d in DOMS:
        for t, (v, why) in C2.outcomes(run, d, True).items():
            if why != C2.INFRA and (d, t) not in DROP.get(m, set()):
                y[(d, t)] = v
    return y


def nonce(run):
    return SNAP["frozen"][run]["retail"]["prompt_nonce"]


def bf16_pairs(m, dev, fdev=False):
    """nonce string -> (BF16 run, genuine pairing flag)."""
    out = {}
    if fdev:  # fork development blocks f01-f17 (manifests/fork/dev_blocks_v1.json), BF16 on the same nonce
        for r in sorted(SNAP["frozen"]):
            if r.startswith(f"a6k2_{m}_bfpair_f"):
                out[nonce(r)] = (r, True)
    for k in range(1, 9):
        r = f"a6k2_{m}_null_n{k}"
        if r in SNAP["frozen"]:
            out[nonce(r)] = (r, True)
    for q, nv in FRESH.items():
        r = f"a6k2_{m}_bfpair_{q}"
        if dev:
            s = f"a6k2_{m}_null_n{q[1:]}"  # stand-in: a different nonce
            if s in SNAP["frozen"]:
                out[nv] = (s, False)
        elif r in SNAP["frozen"]:
            out[nv] = (r, True)
    return out


def cell_pairs(m, stem, B, fdev=False):
    runs = sorted(r for r in SNAP["frozen"] if r.startswith(f"a6k2_{m}_{stem}_") and r.rsplit("_", 1)[1][:1] in ("nqf" if fdev else "nq")
                  and r[len(f"a6k2_{m}_{stem}_"):].count("_") == 0)
    pairs = []
    for r in runs:
        nv = nonce(r)
        if nv in B:
            pairs.append(dict(Q=r, B=B[nv][0], nonce=nv, genuine=B[nv][1]))
    return pairs


# ------------------------------------------------------------------------------------------------ estimators
def cell_arrays(m, pairs, Y):
    tasks = sorted(set.intersection(*[set(Y[p["Q"]]) & set(Y[p["B"]]) for p in pairs]))
    Q = np.array([[Y[p["Q"]][t] for t in tasks] for p in pairs], float)
    Bm = np.array([[Y[p["B"]][t] for t in tasks] for p in pairs], float)
    all_t = set.union(*[set(Y[p["Q"]]) | set(Y[p["B"]]) for p in pairs])
    return tasks, Q, Bm, len(all_t) - len(tasks)


def effect_sizes(Q, Bm, Bext=None, nonces=None, ext_nonces=None):
    Z = Q - Bm
    R, N = Z.shape
    out = dict(R=R, N=N, Delta=float(Z.mean()))
    if R < 2:
        return out
    S = Z.sum(0)
    D = float(np.mean((S ** 2 - (Z ** 2).sum(0)) / (R * (R - 1))))
    zb = Z.mean(1)
    d2u = float((zb.sum() ** 2 - (zb ** 2).sum()) / (R * (R - 1)))
    off = ~np.eye(R, dtype=bool)
    H = lambda A, Bb: np.array([[np.mean((A[i] - Bb[k]) ** 2) for k in range(len(Bb))] for i in range(len(A))])  # noqa: E731
    HQB, HQQ, HBB = H(Q, Bm)[off].mean(), H(Q, Q)[off].mean(), H(Bm, Bm)[off].mean()
    out.update(D=D, Delta2_U=d2u, V=D - d2u, D_hamming=float(HQB - (HQQ + HBB) / 2),
               rms_D_signed_pp=float(np.sign(D) * 100 * np.sqrt(abs(D))))
    if Bext is not None and len(Bext) >= 2:
        hqb = H(Q, Bext)
        mask = np.array([[nonces[i] != ext_nonces[k] for k in range(len(Bext))] for i in range(R)])
        hbb = H(Bext, Bext)[~np.eye(len(Bext), dtype=bool)].mean()
        out["D_hamming_ext"] = float(hqb[mask].mean() - (HQQ + hbb) / 2)
        out["n_bf16_ext"] = int(len(Bext))
    return out


def tests(est, se, df):
    r = dict(estimate=rnd(est, 5), se=rnd(se, 5), df=rnd(df, 1))
    if not (np.isfinite(se) and se > 0 and np.isfinite(df) and df > 0):
        r["note"] = "SE/df not available"
        return r
    t95, t975 = stats.t.ppf(0.95, df), stats.t.ppf(0.975, df)
    lo1 = est - t95 * se
    ci90 = (est - t95 * se, est + t95 * se)
    r.update(lower_95_one_sided=rnd(lo1, 5), ci90=rnd(ci90, 5), ci95=rnd((est - t975 * se, est + t975 * se), 5),
             p_diff_two_sided=rnd(2 * stats.t.sf(abs(est) / se, df), 5))
    for e in EPS:
        k = f"eps_{int(round(e * 100))}pp"
        r[k] = dict(NI_pass=bool(lo1 > -e), p_NI=rnd(stats.t.sf((est + e) / se, df), 5),
                    TOST_pass=bool(ci90[0] > -e and ci90[1] < e),
                    p_TOST=rnd(max(stats.t.sf((est + e) / se, df), stats.t.cdf((est - e) / se, df)), 5))
    return r


def sigma2_u(cells):
    """Henderson III for D_jr = theta_j + u_nu + e_jr (theta fixed): SSE and R(u | mu, theta)."""
    rows = [(j, p["nonce"], d) for j, c in enumerate(cells) for p, d in zip(c["pairs"], c["D_run"])]
    if len({r[1] for r in rows}) < 2:
        return np.nan, np.nan
    y = np.array([r[2] for r in rows])
    n = len(y)
    Zt = np.array([[1.0 * (r[0] == j) for j in range(len(cells))] for r in rows])
    nl = sorted({r[1] for r in rows})
    Zu = np.array([[1.0 * (r[1] == v) for v in nl] for r in rows])
    P = lambda X: X @ np.linalg.pinv(X)  # noqa: E731
    Pf, Pr = P(np.hstack([Zt, Zu])), P(Zt)
    A1, A2 = np.eye(n) - Pf, Pf - Pr
    C = np.array([[np.trace(A1), np.sum((A1 @ Zu) * Zu)], [np.trace(A2), np.sum((A2 @ Zu) * Zu)]])
    s2e, s2u = np.linalg.solve(C, [y @ A1 @ y, y @ A2 @ y])
    return float(s2u), float(s2e)


def model_analysis(m, cells):
    """Pooled within-cell variance, per-cell tests, shared-nonce covariance."""
    ss = sum(((np.array(c["D_run"]) - np.mean(c["D_run"])) ** 2).sum() for c in cells)
    df = sum(len(c["D_run"]) - 1 for c in cells)
    s2 = ss / df if df > 0 else np.nan
    c_u, s2e = sigma2_u(cells)
    for c in cells:
        R = len(c["D_run"])
        c["var"] = s2 / R
        c["tests"] = tests(float(np.mean(c["D_run"])), np.sqrt(s2 / R), df)
    return dict(s2_run=s2, df=df, sd_run_pp=100 * np.sqrt(s2) if s2 > 0 else np.nan, sigma2_u_shared_nonce=c_u,
                sigma2_e=s2e)


def pool_var(cells, w, c_u):
    v = 0.0
    for i, a in enumerate(cells):
        for k, b in enumerate(cells):
            if i == k:
                v += w[i] ** 2 * a["var"]
            else:
                na, nb = {p["nonce"] for p in a["pairs"]}, {p["nonce"] for p in b["pairs"]}
                v += w[i] * w[k] * len(na & nb) / (len(na) * len(nb)) * max(c_u, 0.0)
    return v


def combine(parts):
    """parts: list of (weight, est, var, df) of independent components -> est, var, Welch df."""
    est = sum(w * e for w, e, _, _ in parts)
    var = sum(w ** 2 * v for w, _, v, _ in parts)
    den = sum((w ** 2 * v) ** 2 / d for w, _, v, d in parts if d > 0)
    return est, var, (var ** 2 / den if den > 0 else np.nan)


# ------------------------------------------------------------------------------------------------ generalisation
def gen_boot(model_cells, B=B_BOOT):
    """Task-clustered crossed resampling: tasks (shared within model) x nonce Poisson weights (shared within model)."""
    rng = rng_for("gen_boot")
    reps = {}
    for m, cells in model_cells.items():
        tl = sorted(set.union(*[set(c["tasks"]) for c in cells]))
        nl = sorted({p["nonce"] for c in cells for p in c["pairs"]})
        est = np.full((B, len(cells)), np.nan)
        for b in range(B):
            cnt = np.bincount(rng.integers(0, len(tl), len(tl)), minlength=len(tl))
            tw = dict(zip(tl, cnt))
            for _ in range(100):
                nw = dict(zip(nl, rng.poisson(1.0, len(nl))))
                if all(sum(nw[p["nonce"]] for p in c["pairs"]) > 0 for c in cells):
                    break
            for j, c in enumerate(cells):
                w_t = np.array([tw[t] for t in c["tasks"]], float)
                if w_t.sum() == 0:
                    continue
                Dr = (c["Z"] * w_t).sum(1) / w_t.sum()
                w_n = np.array([nw[p["nonce"]] for p in c["pairs"]], float)
                est[b, j] = (Dr * w_n).sum() / w_n.sum() if w_n.sum() > 0 else np.nan
        reps[m] = est
    return reps


def ci_from(x):
    x = x[np.isfinite(x)]
    return dict(ci90=rnd(np.quantile(x, [0.05, 0.95]), 5), ci95=rnd(np.quantile(x, [0.025, 0.975]), 5),
                lower_95_one_sided=rnd(np.quantile(x, 0.05), 5),
                **{f"eps_{int(round(e * 100))}pp": dict(NI_pass=bool(np.quantile(x, 0.05) > -e),
                                                         TOST_pass=bool(np.quantile(x, 0.05) > -e and np.quantile(x, 0.95) < e)) for e in EPS})


# ------------------------------------------------------------------------------------------------ main
def main():
    global C2, SNAP
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--dev", action="store_true", help="stand-in BF16 draws (NOT nonce-paired); development only")
    ap.add_argument("--with-fdev", action="store_true", help="sensitivity: add the fork development blocks f01-f17 "
                    "(a6k2_<m>_bfpair_f* paired with a6k2_<m>_<ckpt>_f*) where admitted")
    a = ap.parse_args()
    os.environ["CLOQ_SNAPSHOT"] = str(Path(a.snapshot).resolve())
    sys.path.insert(0, str(HERE.parent / "iter_2"))
    import common as C2_  # noqa: E402
    C2, SNAP = C2_, C2_.SNAP
    sid = SNAP["snapshot_id"]
    if not a.dev:
        bad = {}
        for m in MODELS:
            for q, nv in FRESH.items():
                r = f"a6k2_{m}_bfpair_{q}"
                f = SNAP["frozen"].get(r)
                if f is None or set(f) != set(DOMS):
                    bad[r] = "not admitted"
                elif any(f[d]["prompt_nonce"] != nv for d in DOMS):
                    bad[r] = "nonce mismatch"
        if bad:
            refuse(f"real mode waits for the BF16 pairing runs; {len(bad)} of 10 not ready in snapshot {sid}: {bad}. "
                   "Use --dev for a labelled stand-in test.")
    tag = ("DEV" if a.dev else "REAL") + ("_fdev" if a.with_fdev else "") + f"_{sid}"
    res = dict(mode="DEV: stand-in BF16 draws on fresh nonces (NOT nonce-paired); development only, NOT a result" if a.dev
               else "REAL: BF16 nonce-paired", eps_primary=EPS[0], eps_sensitivity=EPS[1],
               snapshot=dict(id=sid, path=str(Path(a.snapshot).resolve()), sha256=sha256(a.snapshot)),
               script=dict(path=str(Path(__file__).resolve()), sha256=sha256(__file__),
                           git_head=subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()),
               run_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), models={})
    model_cells, secondary = {}, {}
    for m in MODELS:
        B = bf16_pairs(m, a.dev, a.with_fdev)
        Y = {}
        bruns = sorted({r for r, _ in B.values()})
        for r in bruns:
            Y[r] = outcomes(r, m)
        cells = []
        for grp, spec in (("primary", PRIMARY), ("secondary", SECONDARY)):
            for meth, cks in spec.items():
                for ck, stem in cks.items():
                    pairs = cell_pairs(m, stem, B, a.with_fdev)
                    if not pairs:
                        continue
                    for p in pairs:
                        Y.setdefault(p["Q"], outcomes(p["Q"], m))
                    tasks, Q, Bm, dropped = cell_arrays(m, pairs, Y)
                    ext = [r for r in bruns]
                    Bext = np.array([[Y[r].get(t, np.nan) for t in tasks] for r in ext])
                    okc = ~np.isnan(Bext).any(1)
                    es = effect_sizes(Q, Bm, Bext[okc], [p["nonce"] for p in pairs], [nonce(r) for r, k in zip(ext, okc) if k])
                    cells.append(dict(group=grp, method=meth, ckpt=ck, pairs=pairs, tasks=tasks, n_tasks_dropped=dropped,
                                      Z=Q - Bm, D_run=list((Q - Bm).mean(1)), effect=es))
        prim = [c for c in cells if c["group"] == "primary"]
        ma = model_analysis(m, prim)
        for c in cells:
            if c["group"] == "secondary":  # own-cell variance only when R >= 2, else the model's pooled run variance
                R = len(c["D_run"])
                v = np.var(c["D_run"], ddof=1) if R >= 3 else ma["s2_run"]
                dfc = R - 1 if R >= 3 else ma["df"]
                c["var"] = v / R
                c["tests"] = tests(float(np.mean(c["D_run"])), np.sqrt(v / R), dfc)
                c["tests"]["variance_source"] = "own cell" if R >= 3 else "model pooled primary-cell run variance"
        model_cells[m] = prim
        pools = {}
        for meth in PRIMARY:
            cs = [c for c in prim if c["method"] == meth]
            w = [1 / len(cs)] * len(cs)
            est = sum(wi * np.mean(c["D_run"]) for wi, c in zip(w, cs))
            var = pool_var(cs, w, ma["sigma2_u_shared_nonce"])
            pools[f"{m}:{meth}"] = dict(est=est, var=var, df=ma["df"], cells=[c["ckpt"] for c in cs])
        cs = prim
        w = []
        for c in cs:
            w.append(0.5 / sum(1 for x in cs if x["method"] == c["method"]))
        est = sum(wi * np.mean(c["D_run"]) for wi, c in zip(w, cs))
        pools[f"{m}:all"] = dict(est=est, var=pool_var(cs, w, ma["sigma2_u_shared_nonce"]), df=ma["df"],
                                 cells=[c["method"] + ":" + c["ckpt"] for c in cs])
        res["models"][m] = dict(
            run_level=dict(sd_run_pp=rnd(ma["sd_run_pp"], 3), df=ma["df"], sigma2_u_shared_nonce=rnd(ma["sigma2_u_shared_nonce"], 7),
                           sigma2_e=rnd(ma["sigma2_e"], 7)),
            cells=[dict(group=c["group"], method=c["method"], ckpt=c["ckpt"], n_pairs=len(c["pairs"]), n_tasks=len(c["tasks"]),
                        n_tasks_dropped=c["n_tasks_dropped"], pairs=c["pairs"], D_run=rnd(c["D_run"], 5),
                        tests=c["tests"], effect_sizes={k: (rnd(v, 6) if isinstance(v, float) else v) for k, v in c["effect"].items()})
                   for c in cells],
            pools={k: dict(cells=v["cells"], **tests(v["est"], np.sqrt(v["var"]), v["df"])) for k, v in pools.items()})
        res["models"][m]["_pools_raw"] = pools
        secondary[m] = [c for c in cells if c["group"] == "secondary"]
        print(m, "sd_run_pp", rnd(ma["sd_run_pp"], 2), "df", ma["df"], "sigma2_u", rnd(ma["sigma2_u_shared_nonce"], 7), flush=True)
    # cross-model pools (independent models)
    xp = {}
    for meth in list(PRIMARY) + ["all"]:
        parts = [(0.5, res["models"][m]["_pools_raw"][f"{m}:{meth}"]["est"], res["models"][m]["_pools_raw"][f"{m}:{meth}"]["var"],
                  res["models"][m]["_pools_raw"][f"{m}:{meth}"]["df"]) for m in MODELS]
        est, var, df = combine(parts)
        xp[f"all_models:{meth}"] = tests(est, np.sqrt(var), df)
    res["pools_across_models"] = xp
    for m in MODELS:
        res["models"][m].pop("_pools_raw")
    # generalisation analysis (new tasks)
    reps = gen_boot(model_cells)
    gen = {}
    for m, est in reps.items():
        cs = model_cells[m]
        for j, c in enumerate(cs):
            gen[f"{m}:{c['method']}:{c['ckpt']}"] = ci_from(est[:, j])
        for meth in PRIMARY:
            idx = [j for j, c in enumerate(cs) if c["method"] == meth]
            gen[f"{m}:{meth}"] = ci_from(np.nanmean(est[:, idx], 1))
        wa = np.array([0.5 / sum(1 for x in cs if x["method"] == c["method"]) for c in cs])
        gen[f"{m}:all"] = ci_from((est * wa).sum(1))
    allm = np.mean([np.array([(reps[m] * np.array([0.5 / sum(1 for x in model_cells[m] if x["method"] == c["method"]) for c in model_cells[m]])).sum(1)])[0] for m in MODELS], 0)
    gen["all_models:all"] = ci_from(allm)
    res["generalisation_task_clustered_crossed"] = dict(B=B_BOOT, note="separate analysis: population = new tasks from the "
                                                        "same distribution; task ids crossed with checkpoints and nonces", ci=gen)
    res["population_label"] = ("population of calibration draws: method pools average the d1-d4 checkpoints, so they are "
                               "NOT an equivalence statement about d1 (the fork checkpoint); see success_ni_aligned.py (W64)")
    p = HERE / "out" / f"success_ni_{tag}.json"
    json.dump(res, open(p, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else (x.tolist() if hasattr(x, "tolist") else str(x)))
    print(res["mode"])
    for m in MODELS:
        for c in res["models"][m]["cells"]:
            t, e = c["tests"], c["effect_sizes"]
            print(f"{m} {c['group'][:3]} {c['method']:12} {c['ckpt']:3} R={c['n_pairs']} N={c['n_tasks']} est {t['estimate']:+.4f} "
                  f"lo95 {t.get('lower_95_one_sided')} ci90 {t.get('ci90')} NI3 {t.get('eps_3pp', {}).get('NI_pass')} "
                  f"TOST3 {t.get('eps_3pp', {}).get('TOST_pass')} | D {e.get('D')} DH {e.get('D_hamming')} DHx {e.get('D_hamming_ext')} V {e.get('V')}")
        for k, v in res["models"][m]["pools"].items():
            print(" pool", k, v["estimate"], v.get("ci90"), v.get("eps_3pp"))
    for k, v in xp.items():
        print(" pool", k, v["estimate"], v.get("ci90"), v.get("eps_3pp"))
    print("wrote", p)


if __name__ == "__main__":
    main()
