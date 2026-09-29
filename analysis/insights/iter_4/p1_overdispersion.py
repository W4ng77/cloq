"""p1: is a checkpoint's net success effect a coherent "lottery" draw, or the sum of independently landing tasks?

Question (hypothesis P1). If quantization adds one fixed, checkpoint-specific bias at a few policy forks, the tasks a
checkpoint re-rolls should land in a correlated way (mostly breaks, or mostly fixes), so checkpoint net success varies
between checkpoints of the same dose MORE than if each re-rolled task landed independently.

Units. Nonce-stratum checkpoints (fixed quantized / E17-control / Gaussian-fixed checkpoints) with >= 2 nonce draws.
Balanced design: draws A, B = the first two run names in sorted order (sensitivity: the last two). Tasks = complete
case over the nonce null U and every used draw. Checkpoints are compared only within model x dose group (common4.dose_group),
so dose effects (W3 << W4 < W8) are not counted as checkpoint-specific.

Statistic (method of moments, per model x group with J >= 2 checkpoints, N tasks, y in {0,1}):
  m_j      = mean over tasks of (yA + yB)/2                    checkpoint net success (constant null offset irrelevant)
  between  = var_j(m_j) (ddof 1)
  nonce    = mean_j (mean_t yA - mean_t yB)^2 / 4               nonce noise of m_j (includes any nonce coherence)
  sig_ck   = between - nonce                                    true between-checkpoint variance
  indep    = N^-2 sum_t [ var_j((yA+yB)/2 at t) - mean_j (yA-yB)^2/4 at t ]
             = the between-checkpoint variance expected if every task landed independently (no cross-task correlation
               within a checkpoint), given each task's observed spread across checkpoints
  phi      = sum_g (J-1) sig_ck / sum_g (J-1) indep              overdispersion (1 = independent landing)
Null: within each task (and model x group), permute the checkpoint labels of the (yA, yB) pair; this keeps every task's
turnover and its nonce noise, and destroys cross-task coherence at both checkpoint and nonce level. Monte Carlo
B = CLOQ_B (default 5000), p = (1 + #{T* >= T})/(B + 1), T = sum_g (J-1) sig_ck. One-sided.
Declared primary (Holm family in common4.DECLARED['P1']): pooled over models, all dose groups.
Exploratory: all groups except W3 (no_w3; the W3 group is RTN vs GPTQ, a method gap); W4 group only; W4 production quantizers only (w4_core: RTN/GPTQ/AWQ/rotated/MXFP4/NF4, no E17
controls); W4 leave-one-checkpoint-out phi; same-method recalibration pairs (GPTQ d1/d2, AWQ d1/d2); nonce-null baseline (U draws as
units; phi_U > 1 would mean a prompt nonce also shifts many tasks coherently); within-checkpoint nonce coherence
(run-level nonce variance / task-level nonce variance); last-two-draw sensitivity; per-checkpoint net
success (draws A and B separately) and break/fix rates vs U minus nonce-mates (descriptive).
Usage: CLOQ_SNAPSHOT=<manifest> [CLOQ_TAG=live_<id>] python p1_overdispersion.py -> out/p1_overdispersion_<tag>.json
"""
import os
import re
from collections import defaultdict

import numpy as np

from common4 import MODELS, dose_group, dump, model_data, ref_for, rnd, ymat

B = int(os.environ.get("CLOQ_B", 5000))
rng = np.random.default_rng(20260929)
W4_CORE = r"^(rot_)?(rtn|gptq|awq)_w4(_d\d)?$|^mxfp4$|^nf4$"  # production W4 quantizers (no E17 controls)


def pairs(D, which="first"):
    """-> list of (unit, group, runA, runB) for units with >= 2 draws."""
    out = []
    for u, rs in sorted(D["units"].items()):
        if len(rs) < 2:
            continue
        a, b = (rs[0], rs[1]) if which == "first" else (rs[-2], rs[-1])
        out.append((u, dose_group(D["meta"][rs[0]]), a, b))
    return out


def stats(yA, yB):
    """yA, yB: (J, N). -> sig_ck, indep, between, nonce, nonce_task."""
    J, N = yA.shape
    m = (yA + yB) / 2
    between = m.mean(1).var(ddof=1)
    nonce = np.mean((yA.mean(1) - yB.mean(1)) ** 2) / 4
    nonce_task = np.sum(np.mean((yA - yB) ** 2, 0) / 4) / N ** 2
    indep = np.sum(m.var(0, ddof=1) - np.mean((yA - yB) ** 2, 0) / 4) / N ** 2
    return between - nonce, indep, between, nonce, nonce_task


def perm_T(blocks, B):
    """blocks: list of (yA, yB) arrays; returns observed T, indep sum and B permuted T."""
    T = sum((a.shape[0] - 1) * stats(a, b)[0] for a, b in blocks)
    E = sum((a.shape[0] - 1) * stats(a, b)[1] for a, b in blocks)
    Ts = np.zeros(B)
    for bi in range(B):
        s = 0.0
        for a, b in blocks:
            J, N = a.shape
            idx = np.argsort(rng.random((J, N)), axis=0)  # independent permutation per task
            ap = np.take_along_axis(a, idx, 0)
            bp = np.take_along_axis(b, idx, 0)
            s += (J - 1) * stats(ap, bp)[0]
        Ts[bi] = s
    return T, E, Ts


def summarize(T, E, Ts, n_blocks, df):
    return dict(T=rnd(T, 6), E_indep=rnd(E, 6), phi=rnd(T / E if E > 0 else np.nan, 3),
                T_perm_mean=rnd(Ts.mean(), 6), T_perm_q95=rnd(np.quantile(Ts, 0.95), 6),
                phi_perm_q95=rnd(np.quantile(Ts, 0.95) / E if E > 0 else np.nan, 3),
                p=float((1 + np.sum(Ts >= T)) / (1 + len(Ts))), n_blocks=n_blocks, df_between=df)


def lam_c(y, pr):
    """checkpoint-level break/fix vs reference success rates pr (per task): lam, c, turnover count."""
    ok, fl = pr == 1, pr == 0
    b = np.mean(1 - y[ok]) if ok.any() else np.nan
    f = np.mean(y[fl]) if fl.any() else np.nan
    return b, f


def main():
    res = {"B": B, "models": {}}
    pooled = defaultdict(list)  # key -> list of (yA, yB)
    w4_units = {}
    for m in MODELS:
        D = model_data(m)
        meta, Y, U = D["meta"], D["Y"], D["U"]
        P = pairs(D)
        used = [r for _, _, a, b in P for r in (a, b)] + U
        tasks = [t for t in D["tasks"] if all(t in Y[r] for r in used)]
        N = len(tasks)
        yU = ymat(Y, U, tasks)
        units = []
        for u, g, a, b in P:
            ya, yb = ymat(Y, [a], tasks)[0], ymat(Y, [b], tasks)[0]
            pr = np.mean(ymat(Y, sorted(set(ref_for(a, meta, U)) & set(ref_for(b, meta, U))), tasks), 0)
            bb, ff = lam_c((ya + yb) / 2, pr)
            units.append(dict(unit=u, group=g, A=a, B=b, net_A=rnd(ya.mean() - pr.mean()), net_B=rnd(yb.mean() - pr.mean()),
                              break_rate=rnd(bb), fix_rate=rnd(ff), n_ok=int((pr == 1).sum()), n_fail=int((pr == 0).sum())))
        groups = defaultdict(list)
        for i, (u, g, a, b) in enumerate(P):
            groups[g].append(i)
        per_group = {}
        for g, idx in groups.items():
            if len(idx) < 2:
                continue
            yA = ymat(Y, [P[i][2] for i in idx], tasks)
            yB = ymat(Y, [P[i][3] for i in idx], tasks)
            sig, ind, bet, non, nt = stats(yA, yB)
            per_group[g] = dict(units=[P[i][0] for i in idx], J=len(idx), sig_ck=rnd(sig, 6), sd_ck_pp=rnd(100 * np.sqrt(max(sig, 0)), 2),
                                indep=rnd(ind, 6), sd_indep_pp=rnd(100 * np.sqrt(max(ind, 0)), 2),
                                phi=rnd(sig / ind if ind > 0 else np.nan, 3), between=rnd(bet, 6), nonce=rnd(non, 6),
                                nonce_coherence=rnd(non / nt if nt > 0 else np.nan, 3))
            pooled["all"].append((m, yA, yB))
            if g != "w3":
                pooled["no_w3"].append((m, yA, yB))
            if g == "w4":
                pooled["w4"].append((m, yA, yB))
                core = [k for k, i in enumerate(idx) if re.match(W4_CORE, P[i][0])]
                if len(core) >= 2:
                    pooled["w4_core"].append((m, yA[core], yB[core]))
                w4_units[m] = (idx, yA, yB)
        # same-method recalibration pairs
        for base in ("gptq_w4", "awq_w4"):
            d1 = next((i for i, p in enumerate(P) if p[0] in (base + "_d1", base)), None)
            d2 = next((i for i, p in enumerate(P) if p[0] == base + "_d2"), None)
            if d1 is not None and d2 is not None:
                pooled["recal"].append((m, ymat(Y, [P[d1][2], P[d2][2]], tasks), ymat(Y, [P[d1][3], P[d2][3]], tasks)))
        # sensitivity: last two draws
        P2 = pairs(D, "last")
        g2 = defaultdict(list)
        for i, p in enumerate(P2):
            g2[p[1]].append(i)
        for g, idx in g2.items():
            if len(idx) >= 2:
                pooled["all_lasttwo"].append((m, ymat(Y, [P2[i][2] for i in idx], tasks), ymat(Y, [P2[i][3] for i in idx], tasks)))
        # nonce-null baseline: each U draw is a unit (single draw, no nonce correction possible)
        mu = yU.mean(1)
        indU = np.sum(yU.var(0, ddof=1)) / N ** 2
        TsU = np.zeros(B)
        for bi in range(B):
            idx = np.argsort(rng.random(yU.shape), axis=0)
            TsU[bi] = np.take_along_axis(yU, idx, 0).mean(1).var(ddof=1)
        null_U = dict(n=len(U), between=rnd(mu.var(ddof=1), 6), indep=rnd(indU, 6), phi=rnd(mu.var(ddof=1) / indU, 3),
                      p=float((1 + np.sum(TsU >= mu.var(ddof=1))) / (1 + B)), sd_between_pp=rnd(100 * mu.std(ddof=1), 2))
        # per-model permutation over all groups
        blocks = [(a, b) for mm, a, b in pooled["all"] if mm == m]
        pm = summarize(*perm_T(blocks, B), len(blocks), sum(a.shape[0] - 1 for a, _ in blocks)) if blocks else None
        res["models"][m] = dict(n_tasks=N, U=U, units=units, groups=per_group, perm_all_groups=pm, null_U_baseline=null_U)
        print(m, "N", N, "groups", {g: (v["J"], v["phi"], v["sd_ck_pp"], v["sd_indep_pp"]) for g, v in per_group.items()},
              "perm", pm and (pm["phi"], pm["p"]), "nullU phi", null_U["phi"], null_U["p"])
    res["pooled"] = {}
    for key, lst in pooled.items():
        blocks = [(a, b) for _, a, b in lst]
        T, E, Ts = perm_T(blocks, B)
        res["pooled"][key] = summarize(T, E, Ts, len(blocks), sum(a.shape[0] - 1 for a in [x for x, _ in blocks]))
        print("pooled", key, res["pooled"][key])
    # influence: W4 pooled phi with one checkpoint left out (no permutation; point estimate only)
    infl = {}
    for m, (idx, yA, yB) in w4_units.items():
        for k in range(len(idx)):
            keep = [j for j in range(len(idx)) if j != k]
            T = E = 0.0
            for mm, (ii, a, b) in w4_units.items():
                a2, b2 = (a[keep], b[keep]) if mm == m else (a, b)
                if a2.shape[0] < 2:
                    continue
                s_, e_ = stats(a2, b2)[:2]
                T += (a2.shape[0] - 1) * s_; E += (a2.shape[0] - 1) * e_
            infl[f"{m}:{res['models'][m]['groups']['w4']['units'][k]}"] = rnd(T / E, 3)
    res["w4_leave_one_ckpt_out_phi"] = infl
    print("w4 LOO phi range", min(infl.values()), max(infl.values()), sorted(infl.items(), key=lambda x: x[1])[:3])
    res["primary"] = dict(test="P1", p=res["pooled"]["all"]["p"], phi=res["pooled"]["all"]["phi"])
    dump("p1_overdispersion", res)


if __name__ == "__main__":
    main()
