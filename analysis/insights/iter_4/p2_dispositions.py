"""p2/p3: do checkpoints carry a reproducible behavioural "disposition" shift, and does it explain their net effect?

P2 (disposition persistence). For every nonce draw r of a nonce-stratum checkpoint, the disposition shift is
  s_r[f] = mean over tasks of ( x_{r,t,f} - mean_{u in ref(r)} x_{u,t,f} ),   ref(r) = U minus r's nonce-mate (NR1-3),
for the 12 declared features common4.DISP (act-vs-talk tool_share, turns, writes, transfer, tool errors, not-found
errors, confirm-before-write, ask rate, first-write position, max-steps / too-many-errors endings). Tasks where a feature
is undefined (no write, no text) are skipped for that feature. Standardisation: z = s / sd_w[f], where sd_w[f] is the
pooled within-checkpoint nonce SD of s (sqrt(mean_j (s_jA - s_jB)^2 / 2) over all units of the model), so z is in
units of "one nonce draw". Features with sd_w = 0 are dropped for that model.
Units, draws A/B, tasks and dose groups as in p1_overdispersion.py (first two draws; complete-case tasks).
  Fingerprint statistic (declared P2): per model x dose group with J >= 2,
    F = mean_j cos(zA_j, zB_j) - mean_{j != k} cos(zA_j, zB_k),
  pooled as the J-weighted mean over blocks. The shared dose direction cancels in the difference, so F > 0 means the
  same checkpoint re-drawn under a different nonce shifts behaviour in its own direction, unlike other checkpoints of
  the same dose. Null: permute the draw-B labels within each block (B = CLOQ_B, default 5000), one-sided.
  Exploratory: F on W4 production quantizers only (w4_core); leave-one-feature-out F; F per model; per-feature reliability ratio (between-checkpoint variance of the pair mean, nonce part
  removed, over the nonce variance of one draw; permutation p within blocks); raw same-checkpoint cosine; the
  nonce-null analogue (cosine between two U draws' leave-one-out shifts).
P3 (dispositions explain outcomes). Net success Delta_r = mean_t y_{r,t} - mean_t mean_{u in ref(r)} y_{u,t}.
  Declared P3: cross-fitted and leave-one-block-out. For each model x dose-group block with J >= 2, a ridge regression
  (alpha = 1, standardised features, no intercept) is trained on the other blocks, with features and labels centred within
  their own block, and predicts the held-out block's centred Delta. Features come from draw A and labels from draw B, and
  vice versa; the two Spearman correlations (predictions vs centred Delta over all held-out units) are averaged. Features
  are centred within the held-out block from draw-A features only (no label leakage). Null: permute Delta within blocks,
  refit everything (B = CLOQ_B3, default 2000). One-sided.
  Exploratory: ridge alpha 0.1 / 10 / 100 (point estimate only); the same without dose-group centring (dose included); per-feature pooled Spearman of centred zA vs
  centred Delta_B; task-level: on null-robust tasks, does a task broken in draw B move along its checkpoint's direction
  (the draw-A mean shift over the other tasks; per-task shifts scaled by the per-feature SD over all perturbed draws
  and tasks)? The AUC of the projection for break vs no break is compared with
  the same projection on a different checkpoint's direction from the same block; fixes are handled the same way on
  null-fail tasks.
Usage: CLOQ_SNAPSHOT=<manifest> [CLOQ_TAG=live_<id>] python p2_dispositions.py -> out/p2_dispositions_<tag>.json
"""
import os
import re
from collections import defaultdict

import numpy as np
from scipy.stats import spearmanr

from common4 import DISP, MODELS, dose_group, dump, fmat, model_data, ref_for, rnd, ymat
from p1_overdispersion import W4_CORE, pairs

B = int(os.environ.get("CLOQ_B", 5000))
B3 = int(os.environ.get("CLOQ_B3", 2000))
rng = np.random.default_rng(20260930)


def shift(D, r, tasks, feats=DISP):
    R = ref_for(r, D["meta"], D["U"])
    X = fmat(D["F"], [r], tasks, feats)[0]  # (T, F)
    X0 = np.nanmean(fmat(D["F"], R, tasks, feats), 0)
    with np.errstate(invalid="ignore"):
        dlt = X - X0
    return np.nanmean(dlt, 0), dlt


def cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na > 0 and nb > 0 else np.nan


def fingerprint(blocks):
    """blocks: list of (ZA, ZB) (J, F). -> J-weighted mean of same - different cosine, and per-block values."""
    num, den, per = 0.0, 0, []
    for ZA, ZB in blocks:
        J = len(ZA)
        C = np.array([[cos(ZA[i], ZB[k]) for k in range(J)] for i in range(J)])
        same = np.nanmean(np.diag(C))
        diff = np.nanmean(C[~np.eye(J, dtype=bool)])
        per.append((same, diff))
        num += J * (same - diff); den += J
    return num / den, per


ALPHA = 1.0


def ridge_fit(X, y, alpha=None):
    alpha = ALPHA if alpha is None else alpha
    return np.linalg.solve(X.T @ X + alpha * np.eye(X.shape[1]), X.T @ y)


def lobo(blocks, centre=True):
    """blocks: list of dict(ZA, ZB, dA, dB). Leave-one-block-out ridge, both cross-fit directions -> mean Spearman."""
    rhos = []
    for fa, la in (("ZA", "dB"), ("ZB", "dA")):
        pred, obs = [], []
        for h in range(len(blocks)):
            Xtr, ytr = [], []
            for i, b in enumerate(blocks):
                if i == h:
                    continue
                X, y = b[fa], b[la]
                if centre:
                    X, y = X - X.mean(0), y - y.mean()
                Xtr.append(X); ytr.append(y)
            Xtr, ytr = np.vstack(Xtr), np.concatenate(ytr)
            if not centre:
                Xtr = np.hstack([Xtr, np.ones((len(Xtr), 1))])
            w = ridge_fit(Xtr, ytr)
            Xh, yh = blocks[h][fa], blocks[h][la]
            if centre:
                Xh, yh = Xh - Xh.mean(0), yh - yh.mean()
            else:
                Xh = np.hstack([Xh, np.ones((len(Xh), 1))])
            pred.append(Xh @ w); obs.append(yh)
        rhos.append(spearmanr(np.concatenate(pred), np.concatenate(obs))[0])
    return float(np.mean(rhos)), rhos


def auc(s, y):
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def main():
    global ALPHA
    res = {"B": B, "B3": B3, "features": DISP, "models": {}}
    fp_blocks, p3_blocks, fp_blocks_all = [], [], []
    task_level = defaultdict(list)
    for m in MODELS:
        D = model_data(m)
        meta, Y, U = D["meta"], D["Y"], D["U"]
        P = pairs(D)
        used = [r for _, _, a, b in P for r in (a, b)] + U
        tasks = [t for t in D["tasks"] if all(t in Y[r] for r in used)]
        S, Dt, dlt_task = {}, {}, {}
        for _, _, a, b in P:
            for r in (a, b):
                S[r], dlt_task[r] = shift(D, r, tasks)
                R = ref_for(r, meta, U)
                Dt[r] = float(ymat(Y, [r], tasks)[0].mean() - ymat(Y, R, tasks).mean())
        sA = np.array([S[a] for _, _, a, _ in P]); sB = np.array([S[b] for _, _, _, b in P])
        sd_w = np.sqrt(np.nanmean((sA - sB) ** 2, 0) / 2)
        keep = np.isfinite(sd_w) & (sd_w > 1e-9)
        feats = [f for f, k in zip(DISP, keep) if k]
        zA, zB = np.nan_to_num(sA[:, keep] / sd_w[keep]), np.nan_to_num(sB[:, keep] / sd_w[keep])
        # nonce-null analogue: leave-one-out shifts of U draws, scaled by the same sd_w
        sU = []
        for u in U:
            Xu = fmat(D["F"], [u], tasks, DISP)[0]
            X0 = np.nanmean(fmat(D["F"], [v for v in U if v != u], tasks, DISP), 0)
            with np.errstate(invalid="ignore"):
                sU.append(np.nanmean(Xu - X0, 0))
        zU = np.nan_to_num(np.array(sU)[:, keep] / sd_w[keep])
        cosU = [cos(zU[i], zU[k]) for i in range(len(U)) for k in range(i + 1, len(U))]
        groups = defaultdict(list)
        for i, (u, g, a, b) in enumerate(P):
            groups[g].append(i)
        mblocks = []
        for g, idx in groups.items():
            if len(idx) < 2:
                continue
            blk = dict(model=m, group=g, units=[P[i][0] for i in idx], ZA=zA[idx], ZB=zB[idx],
                       dA=np.array([Dt[P[i][2]] for i in idx]), dB=np.array([Dt[P[i][3]] for i in idx]))
            mblocks.append(blk)
        # per-feature reliability: between-ckpt variance of pair means minus nonce part, over one-draw nonce variance
        rel = {}
        for fi, f in enumerate(feats):
            num = den = 0.0
            for b in mblocks:
                a_, b_ = b["ZA"][:, fi], b["ZB"][:, fi]
                J = len(a_)
                mm = (a_ + b_) / 2
                num += (J - 1) * (mm.var(ddof=1) - np.mean((a_ - b_) ** 2) / 4)
                den += (J - 1) * np.mean((a_ - b_) ** 2) / 2
            rel[f] = rnd(num / den if den > 0 else np.nan, 3)
        fpm, per = fingerprint([(b["ZA"], b["ZB"]) for b in mblocks]) if mblocks else (np.nan, [])
        # full-feature matrices for pooling must share feature set: pool on DISP with zeros for dropped features
        for b in mblocks:
            ZA = np.zeros((len(b["ZA"]), len(DISP))); ZB = np.zeros_like(ZA)
            ZA[:, keep], ZB[:, keep] = b["ZA"], b["ZB"]
            fp_blocks.append((ZA, ZB)); p3_blocks.append(dict(b, ZA=ZA, ZB=ZB))
        # task-level P3 (exploratory): projection of a task's draw-B shift on its checkpoint's draw-A direction
        pr_all = {}
        sd_task = np.nanstd(np.concatenate([np.array([dlt_task[r] for r in dlt_task])]), axis=(0, 1))
        sd_task[~np.isfinite(sd_task) | (sd_task < 1e-9)] = np.inf
        for b in mblocks:
            for j, u in enumerate(b["units"]):
                i = next(ii for ii, p in enumerate(P) if p[0] == u)
                a, bb = P[i][2], P[i][3]
                others = [k for k in range(len(b["units"])) if k != j]
                R = sorted(set(ref_for(a, meta, U)) & set(ref_for(bb, meta, U)))
                pr = ymat(Y, R, tasks).mean(0)
                yB = ymat(Y, [bb], tasks)[0]
                dB = np.nan_to_num(dlt_task[bb] / sd_task)
                dA = np.nan_to_num(dlt_task[a] / sd_task)
                k = others[0]
                ak = P[next(ii for ii, p in enumerate(P) if p[0] == b["units"][k])][2]
                dK = np.nan_to_num(dlt_task[ak] / sd_task)
                own = np.array([dB[t] @ (dA.sum(0) - dA[t]) for t in range(len(tasks))])
                oth = np.array([dB[t] @ (dK.sum(0) - dK[t]) for t in range(len(tasks))])
                ok, fl = pr == 1, pr == 0
                for lab, sel, ev in (("break", ok, 1 - yB), ("fix", fl, yB)):
                    if sel.sum() >= 5 and 0 < ev[sel].sum() < sel.sum():
                        task_level[lab].append(dict(model=m, unit=u, n_events=int(ev[sel].sum()),
                                                    auc_own=auc(own[sel], ev[sel]), auc_other=auc(oth[sel], ev[sel])))
        res["models"][m] = dict(n_tasks=len(tasks), features_used=feats, sd_w=dict(zip(DISP, rnd(sd_w))),
                                units={P[i][0]: dict(group=P[i][1], A=P[i][2], B=P[i][3], zA=rnd(zA[i], 2), zB=rnd(zB[i], 2),
                                                     delta_A=rnd(Dt[P[i][2]]), delta_B=rnd(Dt[P[i][3]]),
                                                     cos_AB=rnd(cos(zA[i], zB[i]), 3)) for i in range(len(P))},
                                fingerprint=rnd(fpm, 3), fingerprint_blocks={f"{b['group']}": dict(zip(("same", "diff"), rnd(p, 3)))
                                                                              for b, p in zip(mblocks, per)},
                                reliability_per_feature=rel, nullU_mean_cos=rnd(np.nanmean(cosU), 3),
                                same_ckpt_mean_cos=rnd(np.nanmean([cos(zA[i], zB[i]) for i in range(len(P))]), 3))
        print(m, "fingerprint", rnd(fpm, 3), "same cos", res["models"][m]["same_ckpt_mean_cos"], "nullU cos",
              res["models"][m]["nullU_mean_cos"], "rel", rel)
    # ---- P2 pooled permutation
    T, _ = fingerprint(fp_blocks)
    Ts = np.zeros(B)
    for bi in range(B):
        Ts[bi] = fingerprint([(ZA, ZB[rng.permutation(len(ZB))]) for ZA, ZB in fp_blocks])[0]
    p2 = dict(F=rnd(T, 4), perm_mean=rnd(Ts.mean(), 4), perm_q95=rnd(np.quantile(Ts, .95), 4),
              p=float((1 + np.sum(Ts >= T)) / (1 + B)), n_blocks=len(fp_blocks), n_units=sum(len(a) for a, _ in fp_blocks))
    print("P2 pooled", p2)
    # exploratory P2 robustness: W4 production quantizers only; leave-one-feature-out fingerprint
    core_blocks = []
    for b in p3_blocks:
        if b["group"] != "w4":
            continue
        k = [i for i, u in enumerate(b["units"]) if re.match(W4_CORE, u)]
        if len(k) >= 2:
            core_blocks.append((b["ZA"][k], b["ZB"][k]))
    Tc, _ = fingerprint(core_blocks)
    Tcs = np.array([fingerprint([(ZA, ZB[rng.permutation(len(ZB))]) for ZA, ZB in core_blocks])[0] for _ in range(B // 5)])
    p2["w4_core"] = dict(F=rnd(Tc, 4), p=float((1 + np.sum(Tcs >= Tc)) / (1 + len(Tcs))), n_blocks=len(core_blocks),
                         n_units=sum(len(a) for a, _ in core_blocks))
    lofo = {}
    for fi, f in enumerate(DISP):
        keepf = [i for i in range(len(DISP)) if i != fi]
        lofo[f] = rnd(fingerprint([(ZA[:, keepf], ZB[:, keepf]) for ZA, ZB in fp_blocks])[0], 3)
    p2["leave_one_feature_out_F"] = lofo
    print("P2 w4_core", p2["w4_core"], "LOFO", lofo)
    # ---- P3
    rho, rhos = lobo(p3_blocks, True)
    Rs = np.zeros(B3)
    for bi in range(B3):
        pb = []
        for b in p3_blocks:
            pi = rng.permutation(len(b["dA"]))
            pb.append(dict(b, dA=b["dA"][pi], dB=b["dB"][pi]))
        Rs[bi] = lobo(pb, True)[0]
    p3 = dict(rho=rnd(rho, 3), rho_AtoB_BtoA=rnd(rhos, 3), perm_mean=rnd(Rs.mean(), 3), perm_q95=rnd(np.quantile(Rs, .95), 3),
              p=float((1 + np.sum(Rs >= rho)) / (1 + B3)), n_blocks=len(p3_blocks))
    p3["ridge_alpha_sensitivity"] = {}
    for al in (0.1, 10.0, 100.0):
        ALPHA = al
        p3["ridge_alpha_sensitivity"][str(al)] = rnd(lobo(p3_blocks, True)[0], 3)
    ALPHA = 1.0
    rho_u, rhos_u = lobo(p3_blocks, False)
    p3["uncentred_rho"] = rnd(rho_u, 3)
    feat_rho = {}
    zc = np.vstack([b["ZA"] - b["ZA"].mean(0) for b in p3_blocks])
    dc = np.concatenate([b["dB"] - b["dB"].mean() for b in p3_blocks])
    for fi, f in enumerate(DISP):
        r_, p_ = spearmanr(zc[:, fi], dc)
        feat_rho[f] = dict(rho=rnd(r_, 3), p=rnd(p_, 4))
    p3["per_feature_centred_zA_vs_deltaB"] = feat_rho
    # raw correlation between checkpoint net Delta (mean of A,B) and centred disposition norm etc.
    print("P3", p3)
    tl = {}
    for lab, lst in task_level.items():
        a_own = np.array([x["auc_own"] for x in lst]); a_oth = np.array([x["auc_other"] for x in lst])
        ok = np.isfinite(a_own) & np.isfinite(a_oth)
        dd = a_own[ok] - a_oth[ok]
        # sign-flip permutation on the paired difference (units as independent; approximate)
        flips = rng.choice([-1, 1], size=(B, ok.sum()))
        null = (flips * dd).mean(1)
        tl[lab] = dict(n_units=int(ok.sum()), mean_auc_own=rnd(a_own[ok].mean(), 3), mean_auc_other=rnd(a_oth[ok].mean(), 3),
                       diff=rnd(dd.mean(), 3), p_signflip=float((1 + np.sum(null >= dd.mean())) / (1 + B)), units=lst)
        print("task-level", lab, {k: v for k, v in tl[lab].items() if k != "units"})
    res.update(P2=p2, P3=p3, task_level=tl,
               primary=dict(P2=dict(test="P2", p=p2["p"], F=p2["F"]), P3=dict(test="P3", p=p3["p"], rho=p3["rho"])))
    dump("p2_dispositions", res)


if __name__ == "__main__":
    main()
