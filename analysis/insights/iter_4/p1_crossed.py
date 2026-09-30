"""p1_crossed: CORRECTED (POST-HOC) RE-ANALYSIS of the P1/H1 variance decomposition with a crossed checkpoint x nonce model.

Not the pre-registered analysis; the pre-registered output (out/prereg_h1_h4_CONF_20260930T0044Z.json) stays as history.

Issue (docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md §B "p1 variance decomposition"). Within a (model, set) block every
checkpoint j is drawn under the SAME two nonces (q1, q2), so nonce is crossed with checkpoint, not nested in it.
p1_overdispersion.stats subtracts
    nonce = mean_j d_j^2 / 4,   d_j = mean_t yA_j - mean_t yB_j,
whose expectation is sigma2_res/2 + (b1 - b2)^2/4: it contains the SHARED nonce main effect (b1 - b2), which moves every
checkpoint's mean by the same amount and therefore does not inflate the between-checkpoint variance it is subtracted
from. sig_ck is biased low by (b1 - b2)^2/4 (in expectation), so phi = sig_ck / indep was biased low.

Crossed model (per model x block; run-level success m_jn = mean over the block's fixed task set of y):
    m_jn = mu + a_j + b_n + e_jn,   j = 1..J checkpoints (random), n in {q1, q2} (nonce main effect; fixed or random),
    e_jn = checkpoint x nonce interaction + run noise (iid, variance sigma2_e).
Design matrix X = [1 | checkpoint indicators (J) | nonce indicators (2)], rank J + 1, n = 2J runs, residual df J - 1.
Two-way ANOVA without replication:
    MS_ck  = 2 var_j(mbar_j.)                  df J - 1   E = sigma2_e + 2 sigma2_a
    MS_res = sum_j (d_j - dbar)^2 / (2 (J-1))  df J - 1   E = sigma2_e
    sigma2_a (crossed) = (MS_ck - MS_res)/2 = between - sum_j (d_j - dbar)^2 / (4 (J-1))
    shared nonce main effect (b1-b2)^2/4, unbiased: (dbar^2 - s_d^2 / J)/4
Independent-landing denominator, crossed version: E_x = N^-2 sum_t [var_j m_jt - sum_j (d_jt - dbar_t)^2 / (4 (J-1))]
(p1's `indep` subtracts mean_j d_jt^2/4, which holds the per-task shared nonce effect in the same way).
Assumptions: additive checkpoint and nonce effects on the run-level success rate; interaction + run noise iid across
checkpoints; tasks fixed (the population is repeated runs on this task set). Negative moment estimates are reported as
they are; they are not "negative variance" and are never truncated at 0 (truncation is not evidence of absence).

H1 permutation invariance. The P1 null permutes, within each task, the checkpoint labels of the (yA, yB) pair.
dbar = mean over j and t of (yA - yB) is invariant under that relabelling, so removing only the main-effect term,
    T_narrow = sum_blocks (J-1) (between - [mean_j d_j^2 - dbar^2]/4) = T_p1 + sum_blocks (J-1) dbar^2 / 4,
shifts every permuted statistic by the same constant: the H1 permutation p-value is unchanged (checked numerically
with the pre-registered relabelling stream rng_for("phi:H1:primary")). The fully crossed estimator (divisor J-1 for
the interaction) is not a constant shift; its permutation p is recomputed on the same relabellings and reported.

Variance components (replaces prereg A13, which nested nonce inside checkpoint): Henderson method III (fitting
constants) for the unbalanced crossed design over all admitted draws of GPTQ/AWQ-W4 d1-d4 (and a variant with Gaussian
k=1 fixed seeds s1-s5 as a third method), per model:
    y_r = mu + M_method + C_checkpoint(method) + N_nonce + e_r    (M, C, N random; e iid)
Quadratic forms: SSE (full model), R(C | mu, M, N), R(N | mu, M, C), R(M | mu, N); E[y'Ay] = tr(A) s2_e +
sum_k s2_k tr(Z_k' A Z_k); the 4x4 system is solved exactly (moment estimates, unbiased, can be negative). Response =
run-level success on the complete-case task set (the NR1-3 reference offset of Delta depends only on the nonce and is
absorbed by N, so the checkpoint, method and residual components are the same for Delta). Shared nonces: n1, n2 (d1, d2
of both methods), q1-q3 (AWQ d2, d3/d4 on q1, q2), q3-q5 (d1 of both methods).

Usage:
  source scripts/a6000/env.sh; cd analysis/insights/iter_4
  python p1_crossed.py --snapshot /data/ziyangs/cloq/analysis/insights/iter_3/out/snapshot_live_20260930T0044Z.json
-> out/p1_crossed_<snapshot id>.json
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path("/data/ziyangs/cloq")
ORIG = HERE / "out/prereg_h1_h4_CONF_20260930T0044Z.json"
LABEL = "corrected (post-hoc) re-analysis; NOT the pre-registered test"
B = 5000


def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def rnd(x, k=6):
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [rnd(v, k) for v in list(x)]
    x = float(x)
    return None if not np.isfinite(x) else round(x, k)


# ------------------------------------------------------------------------------------------------ block statistics
def block_stats(yA, yB):
    """yA, yB (J, N). Returns p1 terms and crossed terms."""
    J, N = yA.shape
    m = (yA + yB) / 2
    between = m.mean(1).var(ddof=1)
    d = yA.mean(1) - yB.mean(1)
    dbar = d.mean()
    nonce_p1 = np.mean(d ** 2) / 4
    inter = np.sum((d - dbar) ** 2) / (4 * (J - 1))
    dt = yA - yB
    indep_p1 = np.sum(m.var(0, ddof=1) - np.mean(dt ** 2, 0) / 4) / N ** 2
    indep_x = np.sum(m.var(0, ddof=1) - np.sum((dt - dt.mean(0)) ** 2, 0) / (4 * (J - 1))) / N ** 2
    MS_ck = 2 * between
    MS_res = np.sum((d - dbar) ** 2) / (2 * (J - 1))
    return dict(J=J, N=N, between=between, nonce_p1=nonce_p1, nonce_main_naive=dbar ** 2 / 4,
                nonce_main_unbiased=(dbar ** 2 - d.var(ddof=1) / J) / 4, interaction_term=inter,
                sig_p1=between - nonce_p1, sig_narrow=between - (nonce_p1 - dbar ** 2 / 4), sig_crossed=between - inter,
                indep_p1=indep_p1, indep_crossed=indep_x, MS_ck=MS_ck, MS_res=MS_res, df_ck=J - 1, df_res=J - 1, df_nonce=1,
                sigma2_ck_anova=(MS_ck - MS_res) / 2, sigma2_e=MS_res, dbar=dbar)


def perm_three(blocks, rng, B=B):
    """Same RNG consumption as p1_overdispersion.perm_T (one rng.random((J, N)) per block per replicate)."""
    Ts = np.zeros((B, 3))
    for bi in range(B):
        s = np.zeros(3)
        for a, b in blocks:
            J, N = a.shape
            idx = np.argsort(rng.random((J, N)), axis=0)
            st = block_stats(np.take_along_axis(a, idx, 0), np.take_along_axis(b, idx, 0))
            s += (J - 1) * np.array([st["sig_p1"], st["sig_narrow"], st["sig_crossed"]])
        Ts[bi] = s
    return Ts


def pooled(blocks):
    ss = [block_stats(a, b) for a, b in blocks]
    w = [s["J"] - 1 for s in ss]
    T = {k: sum(wi * s[k] for wi, s in zip(w, ss)) for k in ("sig_p1", "sig_narrow", "sig_crossed", "indep_p1", "indep_crossed")}
    return T, ss


def phi_table(T):
    f = lambda a, b: T[a] / T[b] if T[b] > 0 else np.nan  # noqa: E731
    return dict(phi_p1=rnd(f("sig_p1", "indep_p1"), 4), phi_numerator_corrected=rnd(f("sig_narrow", "indep_p1"), 4),
                phi_crossed=rnd(f("sig_crossed", "indep_crossed"), 4),
                note="phi_p1 = pre-registered estimator; phi_numerator_corrected removes only the shared nonce main effect "
                     "from the numerator; phi_crossed uses the crossed interaction term in numerator and denominator")


# ------------------------------------------------------------------------------------------------ Henderson III
def henderson3(y, factors, forms):
    """y (n,); factors {name: list of level labels (n)}; forms: list of (name, reduced-model factor list, full-model
    factor list) giving R(full) - R(reduced) (full=None: SSE of the model with all factors). Returns estimates,
    coefficient matrix and df."""
    n = len(y)
    Z = {}
    for k, lv in factors.items():
        levels = sorted(set(lv))
        Z[k] = np.array([[1.0 if x == L else 0.0 for L in levels] for x in lv])
    one = np.ones((n, 1))

    def P(fs):
        X = np.hstack([one] + [Z[f] for f in fs])
        return X @ np.linalg.pinv(X), np.linalg.matrix_rank(X)
    names = list(factors)
    rows, rhs, dfs = [], [], []
    for lab, red, full in forms:
        if full is None:
            Pf, rf = P(names)
            A = np.eye(n) - Pf
            df = n - rf
        else:
            Pf, rf = P(full)
            Pr, rr = P(red)
            A = Pf - Pr
            df = rf - rr
        rows.append([np.trace(A)] + [np.sum((A @ Z[k]) * Z[k]) for k in names])
        rhs.append(float(y @ A @ y))
        dfs.append(int(df))
    Cm = np.array(rows)
    est = np.linalg.solve(Cm, np.array(rhs))
    return dict(zip(["residual"] + names, est)), Cm, dfs, rhs


def varcomp(D, vunits, method_set):
    rows = []
    for u in vunits:
        if u["model"] != D.m or u["method"] not in method_set:
            continue
        for r in u["draws"]:
            if r not in D.Y:
                continue
            rows.append(dict(run=r, method=u["method"], ckpt=u["method"] + ":" + u["cal"], nonce=D.nonce[r],
                             nonce_label=r.rsplit("_", 1)[1], y=float(D.y(r, D.vtasks).mean())))
    y = np.array([x["y"] for x in rows])
    fac = {"method": [x["method"] for x in rows], "checkpoint": [x["ckpt"] for x in rows], "nonce": [x["nonce"] for x in rows]}
    forms = [("SSE", None, None), ("R(C|mu,M,N)", ["method", "nonce"], ["method", "nonce", "checkpoint"]),
             ("R(N|mu,M,C)", ["method", "checkpoint"], ["method", "checkpoint", "nonce"]),
             ("R(M|mu,N)", ["nonce"], ["nonce", "method"])]
    est, Cm, dfs, rhs = henderson3(y, fac, forms)
    return dict(n_runs=len(rows), n_tasks=len(D.vtasks), n_checkpoints=len(set(fac["checkpoint"])), n_nonces=len(set(fac["nonce"])),
                n_methods=len(set(fac["method"])),
                var=dict((k, rnd(v, 7)) for k, v in est.items()),
                sd_pp_signed={k: rnd(np.sign(v) * 100 * np.sqrt(abs(v)), 2) for k, v in est.items()},
                forms=[dict(form=f[0], df=d, value=rnd(v, 7), coef_row=rnd(c, 4)) for f, d, v, c in zip(forms, dfs, rhs, Cm)],
                coef_columns=["residual"] + list(fac), design=[dict(x, y=rnd(x["y"], 5)) for x in rows])


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--procs", type=int, default=8)
    a = ap.parse_args()
    sys.path.insert(0, str(HERE))
    import h3_corrected as H  # noqa: E402  (sets up prereg_h1_h4 with the snapshot gate)
    PR = H.setup(a.snapshot)
    units = PR.confirmatory_units()
    vunits = PR.varcomp_units(False)
    blocks = {"RECAL": [], "RAND": []}
    per_block, vc = {}, {}
    for m in PR.MODELS:
        runs = sorted({r for u in units if u["model"] == m for r in u["draws"]})
        vruns = sorted({r for u in vunits if u["model"] == m for r in u["draws"] if r in PR.SNAP["frozen"]} - set(runs))
        D = PR.ModelData(m, runs + vruns, lambda r: None, a.procs)
        D.vtasks = D.tasks
        prim = set.intersection(*[set(D.Y[r]) for r in D.U + runs]) - PR.DROP_TASKS.get(m, set())
        D.tasks = sorted(prim)
        for s in ("RECAL", "RAND"):
            us = [u for u in units if u["model"] == m and u["set"] == s]
            yA = np.array([D.y(u["draws"][0]) for u in us]); yB = np.array([D.y(u["draws"][1]) for u in us])
            blocks[s].append((yA, yB))
            st = block_stats(yA, yB)
            per_block[f"{m}:{s}"] = {k: (rnd(v) if isinstance(v, float) else v) for k, v in st.items()}
            per_block[f"{m}:{s}"].update(phi_table({k: st[k] for k in ("sig_p1", "sig_narrow", "sig_crossed", "indep_p1", "indep_crossed")}))
            per_block[f"{m}:{s}"]["sd_ck_pp_signed"] = dict(
                p1=rnd(np.sign(st["sig_p1"]) * 100 * np.sqrt(abs(st["sig_p1"])), 2),
                crossed=rnd(np.sign(st["sig_crossed"]) * 100 * np.sqrt(abs(st["sig_crossed"])), 2))
        vc[m] = dict(gptq_awq=varcomp(D, vunits, {"gptq_w4", "awq_w4"}), gptq_awq_gauss1=varcomp(D, vunits, {"gptq_w4", "awq_w4", "gauss1"}))
        print(m, "varcomp", vc[m]["gptq_awq"]["sd_pp_signed"], vc[m]["gptq_awq_gauss1"]["sd_pp_signed"], flush=True)
    # H1: pooled RECAL, same relabellings as the pre-registered run
    T, _ = pooled(blocks["RECAL"])
    Ts = perm_three(blocks["RECAL"], PR.rng_for("phi:H1:primary"))
    obs = np.array([T["sig_p1"], T["sig_narrow"], T["sig_crossed"]])
    ps = [(1 + np.sum(Ts[:, k] >= obs[k])) / (1 + B) for k in range(3)]
    shift = Ts[:, 1] - Ts[:, 0]
    h1 = dict(T=dict(p1=rnd(obs[0]), narrow=rnd(obs[1]), crossed=rnd(obs[2])),
              p=dict(p1=rnd(ps[0], 5), narrow=rnd(ps[1], 5), crossed=rnd(ps[2], 5)),
              p_prereg=json.load(open(ORIG))["primary"]["H1"]["p"],
              narrow_minus_p1_constant_under_permutation=bool(np.ptp(shift) < 1e-12 and abs(shift[0] - (obs[1] - obs[0])) < 1e-12),
              constant=rnd(obs[1] - obs[0]), **phi_table(T))
    TR, _ = pooled(blocks["RAND"])
    orig = json.load(open(ORIG))
    res = dict(label=LABEL, snapshot=dict(id=PR.SNAP["snapshot_id"], path=str(Path(a.snapshot).resolve()), sha256=sha256(a.snapshot)),
               script=dict(path=str(Path(__file__).resolve()), sha256=sha256(__file__),
                           git_head=subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()),
               run_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               H1_RECAL_pooled=h1, RAND_pooled=phi_table(TR), per_block=per_block,
               variance_components_crossed=vc,
               variance_components_prereg_A13_nested=orig["secondary"]["variance_components"])
    p = HERE / "out" / f"p1_crossed_{PR.SNAP['snapshot_id']}.json"
    json.dump(res, open(p, "w"), indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x))
    print("H1", json.dumps(h1))
    print("RAND", phi_table(TR))
    for k, v in per_block.items():
        print(k, {x: v[x] for x in ("phi_p1", "phi_numerator_corrected", "phi_crossed", "nonce_main_unbiased", "sd_ck_pp_signed")})
    print("wrote", p)


if __name__ == "__main__":
    main()
