"""Power under fitted variance model. logit P(Y_ct)=logit(p_t)+b_c+delta*treat.
p_t ~ Beta fitted (beta-binomial) to the 18 v1 checkpoints; b_c ~ N(0, s_c^2) calibrated so the SD of
true checkpoint means (prob scale) equals the ANOVA estimate. Analysis = crossed bootstrap (resample draw
index, then tasks) 95% percentile CI excludes 0, as in results_v1."""
import json, numpy as np, sys
from scipy import special, optimize, stats
from multiprocessing import Pool
from load import *
Y, bf, v0 = load_all(); C, T0 = Y.shape

def bb_fit(k, n):
    def nll(th):
        a, b = np.exp(th)
        return -(special.betaln(k + a, n - k + b) - special.betaln(a, b)).sum()
    o = optimize.minimize(nll, [0, 0], method='Nelder-Mead'); return np.exp(o.x)

rng0 = np.random.default_rng(0)
PBIG = {}
def prob_sample(ab, n, rng):
    return np.clip(rng.beta(ab[0], ab[1], n), 1e-6, 1 - 1e-6)

def ckpt_sd(ab, s_c, rng, n_t=20000, n_c=2000):
    p = prob_sample(ab, n_t, rng); lg = special.logit(p)
    b = rng.normal(0, s_c, n_c)
    m = np.array([special.expit(lg + bi).mean() for bi in b]); return m.std()

def calib_sc(ab, target, rng):
    if target <= 0: return 0.0
    lo, hi = 0.0, 3.0
    for _ in range(25):
        mid = (lo + hi) / 2
        if ckpt_sd(ab, mid, rng, 5000, 600) < target: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def calib_delta(ab, s_c, eff, rng):
    p = prob_sample(ab, 200000, rng); lg = special.logit(p)
    b = rng.normal(0, s_c, 200000) if s_c > 0 else 0
    base = special.expit(lg + b).mean()
    f = lambda d: special.expit(lg + b + d).mean() - base - eff
    return optimize.brentq(f, 0, 10) if eff > 0 else 0.0, base

def one_cell(args):
    ab, s_c, delta, T, D, nsim, nboot, seed = args
    rng = np.random.default_rng(seed); rej = 0
    for _ in range(nsim):
        lg = special.logit(prob_sample(ab, T, rng))
        Ya = (rng.random((D, T)) < special.expit(lg + rng.normal(0, s_c, (D, 1)) + delta)).astype(float)
        Yb = (rng.random((D, T)) < special.expit(lg + rng.normal(0, s_c, (D, 1)))).astype(float)
        Dm = Ya - Yb  # draw-paired by index like results_v1
        wd = np.stack([np.bincount(rng.integers(0, D, D), minlength=D) for _ in range(nboot)])
        wt = np.stack([np.bincount(rng.integers(0, T, T), minlength=T) for _ in range(nboot)])
        bs = ((wd @ Dm) * wt).sum(1) / (D * T)
        lo, hi = np.quantile(bs, [.025, .975])
        rej += (lo > 0) or (hi < 0)
    return rej / nsim

if __name__ == '__main__':
    ex = json.load(open(OUT / 'extra.json'))
    res = {}
    cells = []
    meta = {}
    for sub, m in [('pooled', np.ones(T0, bool)), ('long', LONG)]:
        ab = bb_fit(Y[:, m].sum(0), C)
        sd_pt = ex['ckpt_sd'][sub]['sd_ckpt']; sd_hi = ex['ckpt_sd'][sub]['sd_ckpt_ci95'][1]
        for scen, sd in [('sc0', 0.0), ('sc_point', sd_pt), ('sc_upper', sd_hi)]:
            s_c = calib_sc(ab, sd, rng0)
            for eff in [0.0, 0.05, 0.10]:
                delta, base = calib_delta(ab, s_c, eff, rng0)
                meta[(sub, scen, eff)] = dict(alpha=float(ab[0]), beta=float(ab[1]), target_sd=sd, s_c_logit=s_c, delta_logit=float(delta), base=float(base))
                Ts = [37, 85, 170, 340, 680, 1360] if sub == 'long' else [85, 170, 340, 680, 1360]
                for T in Ts:
                    for D in [1, 3, 5, 10]:
                        cells.append(((sub, scen, eff, T, D), (ab, s_c, delta, T, D, 400, 400, hash((sub, scen, eff, T, D)) % 2**31)))
    with Pool(30) as pool:
        out = pool.map(one_cell, [c[1] for c in cells])
    rows = []
    for (key, _), pw in zip(cells, out):
        sub, scen, eff, T, D = key
        rows.append(dict(subset=sub, scenario=scen, effect=eff, n_tasks=T, draws_per_arm=D, reject_rate=pw, **meta[(sub, scen, eff)]))
    json.dump(rows, open(OUT / 'power.json', 'w'), indent=1)
    for r in rows: print(r['subset'], r['scenario'], r['effect'], r['n_tasks'], r['draws_per_arm'], round(r['reject_rate'], 3))
