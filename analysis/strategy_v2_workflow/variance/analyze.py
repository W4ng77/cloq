"""Variance / exchangeability analysis of CLOQ v1 closed-loop outcomes (CPU only)."""
import json, itertools, numpy as np
from scipy import stats, optimize, special
from load import *

rng = np.random.default_rng(12345)
Y, bf, v0 = load_all()
C, T = Y.shape
res = {}
subsets = {'pooled': np.ones(T, bool), 'long': LONG, 'retail': RETAIL}

# ---------- 1. outcome matrix summaries
rows = []
for (a, d, r), y in zip(V1, Y):
    rows.append(dict(ckpt=r, arm=a, draw=d, pooled=y.mean(), long=y[LONG].mean(), retail=y[RETAIL].mean(), airline=y[~RETAIL].mean()))
rows.append(dict(ckpt='bf16_v1', arm='bf16', draw='-', pooled=bf.mean(), long=bf[LONG].mean(), retail=bf[RETAIL].mean(), airline=bf[~RETAIL].mean()))
res['per_ckpt'] = rows
res['v1_spread'] = {s: dict(mean=float(Y[:, m].mean(1).mean()), sd=float(Y[:, m].mean(1).std(ddof=1)),
                            min=float(Y[:, m].mean(1).min()), max=float(Y[:, m].mean(1).max())) for s, m in subsets.items()}
np.save(OUT / 'Y.npy', Y)

# ---------- 2. between-checkpoint dispersion test
def disp_test(Ysub, nsim=10000):
    p = Ysub.mean(0)
    obs = Ysub.mean(1).var(ddof=1)
    # (a) parametric Bernoulli(p_t) null
    sims = (rng.random((nsim, *Ysub.shape)) < p).mean(2).var(1, ddof=1)
    # (b) conditional null: permute each task column across checkpoints (keeps per-task totals exactly)
    perm = np.empty(nsim)
    k = Ysub.sum(0).astype(int)
    for i in range(nsim):
        r = rng.random(Ysub.shape).argsort(0)  # random ranks per column
        Yp = (r < k).astype(float)
        perm[i] = Yp.mean(1).var(ddof=1)
    return dict(n_ckpt=Ysub.shape[0], n_tasks=Ysub.shape[1], obs_var=float(obs), obs_sd=float(np.sqrt(obs)),
                null_bern_mean=float(sims.mean()), ratio_bern=float(obs / sims.mean()),
                p_bern=float((1 + (sims >= obs).sum()) / (nsim + 1)),
                null_perm_mean=float(perm.mean()), ratio_perm=float(obs / perm.mean()),
                p_perm=float((1 + (perm >= obs).sum()) / (nsim + 1)),
                p_perm_lower=float((1 + (perm <= obs).sum()) / (nsim + 1)),
                null_perm_q025_q975=[float(np.quantile(perm, .025)), float(np.quantile(perm, .975))])

res['dispersion'] = {}
for s, m in subsets.items():
    Ys = Y[:, m]
    k = Ys.sum(0)
    inf = (k > 0) & (k < C)
    res['dispersion'][s] = dict(all=disp_test(Ys), informative=disp_test(Ys[:, inf]),
                                n_zero=int((k == 0).sum()), n_all=int((k == C).sum()), n_informative=int(inf.sum()))

# ---------- 3. arm effect by permutation (and draw effect)
arm_idx = np.repeat(np.arange(6), 3)
draw_idx = np.tile(np.arange(3), 6)

def arm_stats(means, lab, ng):
    am = np.array([means[lab == g].mean() for g in range(ng)])
    return am.var(ddof=1), am.max() - am.min()

res['arm_perm'] = {}
for s, m in subsets.items():
    means = Y[:, m].mean(1)
    ov, orng = arm_stats(means, arm_idx, 6)
    pv = np.empty(10000); pr = np.empty(10000)
    for i in range(10000):
        lab = rng.permutation(arm_idx)
        pv[i], pr[i] = arm_stats(means, lab, 6)
    # draw effect: permute draw labels within each arm
    odv, odr = arm_stats(means, draw_idx, 3)
    dv = np.empty(10000)
    for i in range(10000):
        lab = draw_idx.copy()
        for g in range(6):
            lab[arm_idx == g] = rng.permutation(lab[arm_idx == g])
        dv[i] = arm_stats(means, lab, 3)[0]
    # one-way ANOVA F on checkpoint means (arm), for reference
    F, pF = stats.f_oneway(*[means[arm_idx == g] for g in range(6)])
    res['arm_perm'][s] = dict(arm_means={ARMS[g]: float(means[arm_idx == g].mean()) for g in range(6)},
                              obs_var=float(ov), p_var=float((1 + (pv >= ov).sum()) / 10001),
                              obs_range=float(orng), p_range=float((1 + (pr >= orng).sum()) / 10001),
                              anova_F=float(F), anova_p=float(pF),
                              draw_means={DRAWS[g]: float(means[draw_idx == g].mean()) for g in range(3)},
                              draw_var=float(odv), p_draw_within_arm_perm=float((1 + (dv >= odv).sum()) / 10001))

# ---------- 4. per-task consistency, variance components
kk = Y.sum(0).astype(int)
bfs = bf == 1
res['bf16_solved'] = dict(n=int(bfs.sum()), hist_k=np.bincount(kk[bfs], minlength=C + 1).tolist(),
                          hist_k_bf16_failed=np.bincount(kk[~bfs], minlength=C + 1).tolist(),
                          mean_frac=float(kk[bfs].mean() / C), mean_frac_bf16_failed=float(kk[~bfs].mean() / C))
# common-p binomial overdispersion test (on bf16-solved tasks)
def overdisp(k, n):
    p = k.sum() / (n * len(k))
    chi = ((k - n * p) ** 2 / (n * p * (1 - p))).sum()
    df = len(k) - 1
    return dict(p_common=float(p), chi2=float(chi), df=df, dispersion=float(chi / df), p=float(stats.chi2.sf(chi, df)))
res['bf16_solved']['common_p_test'] = overdisp(kk[bfs], C)
res['all_tasks_common_p_test'] = overdisp(kk, C)

# beta-binomial fit across tasks (distribution of task-specific p)
def bb_fit(k, n):
    def nll(th):
        a, b = np.exp(th)
        return -(special.betaln(k + a, n - k + b) - special.betaln(a, b)).sum()
    o = optimize.minimize(nll, [0, 0], method='Nelder-Mead')
    a, b = np.exp(o.x)
    return dict(alpha=float(a), beta=float(b), mean=float(a / (a + b)), rho=float(1 / (a + b + 1)))
res['betabinom_all'] = bb_fit(kk, C)
res['betabinom_bf16_solved'] = bb_fit(kk[bfs], C)
# expected histogram of k under beta-binomial vs observed
bb = res['betabinom_all']
res['betabinom_all']['expected_hist'] = (stats.betabinom.pmf(np.arange(C + 1), C, bb['alpha'], bb['beta']) * T).round(2).tolist()
res['betabinom_all']['observed_hist'] = np.bincount(kk, minlength=C + 1).tolist()

# linear-probability two-way ANOVA (checkpoint x task, no replication)
def lp_anova(Ys):
    c, t = Ys.shape
    g = Ys.mean(); rm = Ys.mean(1); cm = Ys.mean(0)
    ss_c = t * ((rm - g) ** 2).sum(); ss_t = c * ((cm - g) ** 2).sum()
    ss_e = ((Ys - rm[:, None] - cm[None, :] + g) ** 2).sum()
    ms_c = ss_c / (c - 1); ms_t = ss_t / (t - 1); ms_e = ss_e / ((c - 1) * (t - 1))
    s2c = max((ms_c - ms_e) / t, 0); s2t = max((ms_t - ms_e) / c, 0)
    F = ms_c / ms_e
    tot = s2c + s2t + ms_e
    return dict(ms_ckpt=float(ms_c), ms_task=float(ms_t), ms_resid=float(ms_e), F_ckpt=float(F),
                p_F_ckpt=float(stats.f.sf(F, c - 1, (c - 1) * (t - 1))),
                var_ckpt=float(s2c), var_task=float(s2t), var_resid=float(ms_e),
                share_ckpt=float(s2c / tot), share_task=float(s2t / tot), share_resid=float(ms_e / tot),
                icc_task=float(s2t / tot))
res['lp_anova'] = {s: lp_anova(Y[:, m]) for s, m in subsets.items()}

# logit scale: task random intercept (Gauss-Hermite), checkpoint effects fixed (sum-to-zero), then
# sigma_c^2 by method of moments = var(b_c) - mean(se_c^2)
gh_x, gh_w = np.polynomial.hermite_e.hermegauss(40)
gh_w = gh_w / gh_w.sum()

def glmm_fit(Ys):
    c, t = Ys.shape
    def unpack(th):
        mu, ls = th[0], th[1]
        b = np.concatenate([th[2:], [-th[2:].sum()]])
        return mu, np.exp(ls), b
    def nll(th):
        mu, s, b = unpack(th)
        eta = mu + b[:, None, None] + s * gh_x[None, None, :]  # c x 1 x q
        lp1 = -np.logaddexp(0, -eta); lp0 = -np.logaddexp(0, eta)
        ll = (Ys[:, :, None] * lp1 + (1 - Ys[:, :, None]) * lp0).sum(0)  # t x q
        return -special.logsumexp(ll + np.log(gh_w)[None, :], axis=1).sum()
    th0 = np.zeros(c + 1); th0[1] = np.log(2.)
    o = optimize.minimize(nll, th0, method='BFGS')
    mu, s, b = unpack(o.x)
    # standard errors of b from numerical Hessian of free params (approx via BFGS inverse)
    H = o.hess_inv
    # covariance for full b (including last = -sum)
    J = np.zeros((c, c + 1)); J[:c - 1, 2:] = np.eye(c - 1); J[c - 1, 2:] = -1
    cov_b = J @ H @ J.T
    se2 = np.diag(cov_b)
    s2c_mom = max(b.var(ddof=1) - se2.mean(), 0)
    tot = s * s + s2c_mom + np.pi ** 2 / 3
    return dict(mu=float(mu), sigma_task=float(s), var_task_logit=float(s * s), b=b.tolist(),
                var_b_raw=float(b.var(ddof=1)), mean_se2_b=float(se2.mean()), var_ckpt_logit_mom=float(s2c_mom),
                icc_task_latent=float(s * s / tot), icc_ckpt_latent=float(s2c_mom / tot), converged=bool(o.success), nll=float(o.fun))

def glmm_null(Ys):
    c, t = Ys.shape
    def nll(th):
        mu, s = th[0], np.exp(th[1])
        eta = mu + s * gh_x[None, None, :] + 0 * Ys[:, :, None]
        lp1 = -np.logaddexp(0, -eta); lp0 = -np.logaddexp(0, eta)
        ll = (Ys[:, :, None] * lp1 + (1 - Ys[:, :, None]) * lp0).sum(0)
        return -special.logsumexp(ll + np.log(gh_w)[None, :], axis=1).sum()
    o = optimize.minimize(nll, [0, np.log(2.)], method='BFGS')
    return float(o.fun), float(o.x[0]), float(np.exp(o.x[1]))

res['glmm'] = {}
for s, m in subsets.items():
    g = glmm_fit(Y[:, m])
    n0, mu0, s0 = glmm_null(Y[:, m])
    lr = 2 * (n0 - g['nll'])
    g['LR_ckpt_fixed_vs_none'] = float(lr); g['LR_df'] = C - 1; g['LR_p'] = float(stats.chi2.sf(lr, C - 1))
    g['null_mu'] = mu0; g['null_sigma_task'] = s0
    res['glmm'][s] = g

# ---------- 6. v0 checkpoints as extra samples
p_all = Y.mean(0)
def loglik_under(y, p):
    pc = np.clip(p, 0.5 / (C + 1), 1 - 0.5 / (C + 1))
    return float((y * np.log(pc) + (1 - y) * np.log(1 - pc)).sum())
# leave-one-out reference for v1 checkpoints
loo_ll = []
for i in range(C):
    p_loo = np.delete(Y, i, 0).mean(0)
    pc = (np.delete(Y, i, 0).sum(0) + 0.5) / (C - 1 + 1)
    loo_ll.append(float((Y[i] * np.log(pc) + (1 - Y[i]) * np.log(1 - pc)).sum()))
pc_full = (Y.sum(0) + 0.5) / (C + 1)
res['v0_as_samples'] = {'v1_loo_loglik': dict(min=min(loo_ll), max=max(loo_ll), mean=float(np.mean(loo_ll)))}
for r, y in v0.items():
    ll = float((y * np.log(pc_full) + (1 - y) * np.log(1 - pc_full)).sum())
    agree = float((y[None, :] == Y).mean())
    res['v0_as_samples'][r] = dict(pooled=float(y.mean()), long=float(y[LONG].mean()), retail=float(y[RETAIL].mean()),
                                   pooled_rank_in_v1=int((Y.mean(1) < y.mean()).sum()),
                                   long_rank_in_v1=int((Y[:, LONG].mean(1) < y[LONG].mean()).sum()),
                                   inside_pooled=bool(Y.mean(1).min() <= y.mean() <= Y.mean(1).max()),
                                   inside_long=bool(Y[:, LONG].mean(1).min() <= y[LONG].mean() <= Y[:, LONG].mean(1).max()),
                                   loglik_under_v1_p=ll, mean_agreement_with_v1_ckpts=agree,
                                   agree_with_bf16_v1=float((y == bf).mean()))
res['v1_pairwise_agreement'] = dict(mean=float(np.mean([(Y[i] == Y[j]).mean() for i, j in itertools.combinations(range(C), 2)])),
                                    min=float(min((Y[i] == Y[j]).mean() for i, j in itertools.combinations(range(C), 2))),
                                    max=float(max((Y[i] == Y[j]).mean() for i, j in itertools.combinations(range(C), 2))),
                                    expected_under_indep_bern=float((p_all ** 2 + (1 - p_all) ** 2).mean() * 0 + np.mean(
                                        [(p_all ** 2 + (1 - p_all) ** 2).mean()])),
                                    with_bf16_v1=[float((Y[i] == bf).mean()) for i in range(C)])

# ---------- 8. retrospective: single-draw retail comparison >= +0.121 under exchangeable null
pr = p_all[RETAIL]
# exact distribution of sum of independent (X1-X2) per task
dist = np.zeros(2 * len(pr) + 1); dist[len(pr)] = 1.0
for p in pr:
    q = np.array([p * (1 - p), p * p + (1 - p) ** 2, p * (1 - p)])  # -1, 0, +1
    dist = np.convolve(dist, q)[1:-1]
diffs = np.arange(-len(pr), len(pr) + 1)
thr = 7  # 0.121*58 = 7.0 tasks
res['retro'] = dict(v0_static_retail=float(v0['static_eval'][RETAIL].mean()), v0_fp_traj_retail=float(v0['fp_traj_eval'][RETAIL].mean()),
                    v0_diff_tasks=int(v0['fp_traj_eval'][RETAIL].sum() - v0['static_eval'][RETAIL].sum()),
                    null_sd_of_diff=float(np.sqrt((dist * diffs ** 2).sum()) / len(pr)),
                    p_one_sided_ge_7=float(dist[diffs >= thr].sum()), p_two_sided_abs_ge_7=float(dist[np.abs(diffs) >= thr].sum()))
# empirical among v1 ordered checkpoint pairs
dd = [Y[i, RETAIL].sum() - Y[j, RETAIL].sum() for i in range(C) for j in range(C) if i != j]
res['retro']['empirical_v1_ordered_pairs_ge_7'] = float(np.mean(np.array(dd) >= thr))
res['retro']['empirical_v1_pairs_abs_ge_7'] = float(np.mean(np.abs(np.array(dd)) >= thr))
res['retro']['n_ordered_pairs'] = len(dd)
# with p_t from all tasks including bf16-based informative only?  also the chance that a pre-registered one-sided single comparison "fires"
json.dump(res, open(OUT / 'results_variance.json', 'w'), indent=1, default=float)
print(json.dumps(res, indent=1, default=float)[:20000])
