import json, itertools, numpy as np
from scipy import stats
from load import *
rng = np.random.default_rng(7)
Y, bf, v0 = load_all(); C, T = Y.shape
out = {}
k = Y.sum(0)
# exact expected pairwise agreement under column-permutation null
exp_agree = ((k * (k - 1) + (C - k) * (C - k - 1)) / (C * (C - 1))).mean()
obs_agree = np.mean([(Y[i] == Y[j]).mean() for i, j in itertools.combinations(range(C), 2)])
out['pairwise_agreement'] = dict(obs=float(obs_agree), expected_perm_null=float(exp_agree))
# is BF16 exchangeable with the quantized checkpoints? P(ckpt score >= bf16) under Bernoulli(p_t)
for name, m in [('pooled', np.ones(T, bool)), ('long', LONG), ('short', ~LONG)]:
    p = Y[:, m].mean(0)
    sims = (rng.random((100000, m.sum())) < p).sum(1)
    obs = bf[m].sum()
    # also include BF16 in the p_t (19 checkpoints) to be conservative
    p19 = np.vstack([Y, bf])[:, m].mean(0)
    sims19 = (rng.random((100000, m.sum())) < p19).sum(1)
    out[f'bf16_vs_quant_{name}'] = dict(bf16=float(bf[m].mean()), quant_mean=float(Y[:, m].mean()), n=int(m.sum()),
        p_ge_bf16=float((sims >= obs).mean()), p_ge_bf16_p19=float((sims19 >= obs).mean()),
        n_quant_ge_bf16=int((Y[:, m].sum(1) >= obs).sum()))
# paired: per-task BF16 vs mean of quantized, sign test on discordant
d = bf - Y.mean(0)
out['bf16_minus_quant_by_task'] = {}
for name, m in [('pooled', np.ones(T, bool)), ('long', LONG), ('short', ~LONG)]:
    bs = np.array([d[rng.integers(0, m.sum(), m.sum())].mean() for _ in range(1)])
    idx = np.where(m)[0]
    boots = np.array([d[idx[rng.integers(0, len(idx), len(idx))]].mean() for _ in range(10000)])
    out['bf16_minus_quant_by_task'][name] = dict(diff=float(d[m].mean()), ci=[float(np.quantile(boots, .025)), float(np.quantile(boots, .975))],
                                                 wilcoxon_p=float(stats.wilcoxon(d[m][d[m] != 0]).pvalue))
# CI for checkpoint variance component (linear-probability ANOVA), via F distribution
def vc_ci(Ys):
    c, t = Ys.shape
    g = Ys.mean(); rm = Ys.mean(1); cm = Ys.mean(0)
    ms_c = t * ((rm - g) ** 2).sum() / (c - 1)
    ms_e = ((Ys - rm[:, None] - cm[None, :] + g) ** 2).sum() / ((c - 1) * (t - 1))
    F = ms_c / ms_e; df1, df2 = c - 1, (c - 1) * (t - 1)
    # theta = 1 + t*s2c/s2e ; F/theta ~ F(df1,df2)
    lo = max(F / stats.f.ppf(.975, df1, df2) - 1, 0) * ms_e / t
    hi = max(F / stats.f.ppf(.025, df1, df2) - 1, 0) * ms_e / t
    pt = max(F - 1, 0) * ms_e / t
    return dict(sd_ckpt=float(np.sqrt(pt)), sd_ckpt_ci95=[float(np.sqrt(lo)), float(np.sqrt(hi))],
                binomial_sd_of_mean=float(np.sqrt(ms_e / t)), F=float(F))
out['ckpt_sd'] = {n: vc_ci(Y[:, m]) for n, m in [('pooled', np.ones(T, bool)), ('long', LONG), ('retail', RETAIL)]}
# split-half reliability of checkpoint means: correlation between checkpoint scores on random half of tasks vs other half
rel = {}
for n, m in [('pooled', np.ones(T, bool)), ('long', LONG)]:
    idx = np.where(m)[0]; rs = []
    for _ in range(5000):
        p = rng.permutation(idx); a, b = p[:len(p) // 2], p[len(p) // 2:]
        rs.append(np.corrcoef(Y[:, a].mean(1), Y[:, b].mean(1))[0, 1])
    rs = np.array(rs)
    r = rs.mean(); rel[n] = dict(mean_split_half_r=float(r), spearman_brown=float(2 * r / (1 + r)), q025=float(np.quantile(rs, .025)), q975=float(np.quantile(rs, .975)))
out['split_half'] = rel
json.dump(out, open(OUT / 'extra.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
