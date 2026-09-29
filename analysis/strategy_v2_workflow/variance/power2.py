"""Same generative model as power.py; three analyses per simulated experiment:
 xboot : crossed bootstrap (draw index, then tasks) 95% percentile CI excludes 0 (results_v1 procedure)
 ttest : Student t-test on the 2D checkpoint-level means (unit = calibration draw; needs D>=2)
 paired: paired t-test over tasks on per-task arm difference averaged over draws (ignores draw variance)"""
import json, numpy as np
from scipy import special, stats
from multiprocessing import Pool
from power import bb_fit, prob_sample, calib_sc, calib_delta
from load import *

def one_cell(args):
    ab, s_c, delta, T, D, nsim, nboot, seed = args
    rng = np.random.default_rng(seed); rx = rt = rp = 0
    for _ in range(nsim):
        lg = special.logit(prob_sample(ab, T, rng))
        Ya = (rng.random((D, T)) < special.expit(lg + rng.normal(0, s_c, (D, 1)) + delta)).astype(float)
        Yb = (rng.random((D, T)) < special.expit(lg + rng.normal(0, s_c, (D, 1)))).astype(float)
        Dm = Ya - Yb
        wd = np.stack([np.bincount(rng.integers(0, D, D), minlength=D) for _ in range(nboot)])
        wt = np.stack([np.bincount(rng.integers(0, T, T), minlength=T) for _ in range(nboot)])
        bs = ((wd @ Dm) * wt).sum(1) / (D * T)
        lo, hi = np.quantile(bs, [.025, .975]); rx += (lo > 0) or (hi < 0)
        if D >= 2:
            rt += stats.ttest_ind(Ya.mean(1), Yb.mean(1)).pvalue < 0.05
        d = Dm.mean(0)
        if d.std() > 0: rp += stats.ttest_1samp(d, 0).pvalue < 0.05
    return rx / nsim, (rt / nsim if D >= 2 else None), rp / nsim

if __name__ == '__main__':
    ex = json.load(open(OUT / 'extra.json'))
    rng0 = np.random.default_rng(1)
    Y, bf, v0 = load_all(); C, T0 = Y.shape
    cells, meta = [], {}
    for sub, m in [('pooled', np.ones(T0, bool)), ('long', LONG)]:
        ab = bb_fit(Y[:, m].sum(0), C)
        sd_pt = ex['ckpt_sd'][sub]['sd_ckpt']; sd_hi = ex['ckpt_sd'][sub]['sd_ckpt_ci95'][1]
        for scen, sd in [('sc0', 0.0), ('sc_point', sd_pt), ('sc_upper', sd_hi)]:
            s_c = calib_sc(ab, sd, rng0)
            for eff in [0.0, 0.05, 0.10]:
                delta, base = calib_delta(ab, s_c, eff, rng0)
                meta[(sub, scen, eff)] = dict(alpha=float(ab[0]), beta=float(ab[1]), target_sd=sd, s_c_logit=s_c, delta_logit=float(delta), base=float(base))
                for T in [37, 85, 170, 340, 680, 1360]:
                    for D in [1, 2, 3, 5, 10, 20]:
                        cells.append(((sub, scen, eff, T, D), (ab, s_c, delta, T, D, 500, 300, abs(hash((sub, scen, eff, T, D, 'v2'))) % 2**31)))
    with Pool(30) as pool:
        out = pool.map(one_cell, [c[1] for c in cells])
    rows = []
    for (key, _), (px, pt, pp) in zip(cells, out):
        sub, scen, eff, T, D = key
        rows.append(dict(subset=sub, scenario=scen, effect=eff, n_tasks=T, draws_per_arm=D, xboot=px, ttest=pt, paired=pp, **meta[(sub, scen, eff)]))
    json.dump(rows, open(OUT / 'power2.json', 'w'), indent=1)
    print('done', len(rows))
