"""Holdout K planning-precision simulation (W85; telecom DEV only; GPT-6.1 review 4 point 6).

Purpose: confirm that K = 12 nonce blocks per holdout cell is adequate for (a) the primary G_all interval and (b) the
pre-registered cross-half repeatability secondary (FORK_PROTOCOL §12 amendment 1, as revised in the draft
docs/insights/PREREG_FORK_CONFIRM.md). It is NOT a K-selection exercise: K = 12 is fixed by the review on cost and
rate-level grounds; this script only reports power and interval widths for K = 6/8/12/16.

Data: telecom DEV fork units only (80 tasks, blocks f01-f06, cells q8 GPTQ-W4 d1 and q8 AWQ-W4). The analysis goes
through analyze_dev's split guard (it aborts if any unit belongs to the holdout). No holdout task id is read: the
holdout persona mix is approximated from the dev mix (the split is stratified by issue type x persona).

Model fitted per cell on dev (logistic, task random effect, block fixed effects -> block-shock variance by moments):
    M_{c,j,b} ~ Bernoulli(expit(mu_{c,persona(j)} + v_{c,b} + u_{c,j})),  u_{c,.} ~ N(0, s_u,c^2)  (within persona)
    (u_{gptq,j}, u_{awq,j}) bivariate normal with correlation rho_u (fitted jointly, 2-D Gauss-Hermite)
    given M = 1: rescue with probability q_{c,j} ~ Beta(a_c, b_c)  (beta-binomial on per-task rescue counts)
    block shocks v_{c,b} ~ N(0, s_v,c^2), cross-cell correlation rho_v (moments; shared nonces and BF16 runs)
The q4 GPTQ-W4 d1 holdout cell has NO telecom dev forks; it borrows the q8 GPTQ-W4 parameters (flagged).

Simulated holdout: J = 34 tasks (persona mix 11 Easy / 11 Hard / 12 None), 3 cells, K blocks, halves K/2 + K/2.
Reported per K: 90% and 95% CI width of G_all (equal-weight mean over cells) by (i) t over K block means and (ii) the
crossed task x block variance (two-way ANOVA moments); power of the repeatability test (one-sided, alpha 0.05,
persona-stratified permutation of task labels of m_B, identical across cells; constant vectors -> cell not estimable);
size under the null (s_u = 0); sensitivity with s_u halved.

usage: python analysis/fork/holdout_k_planning.py [--reps 1000] [--perms 2000] [--snapshot PATH]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import optimize, special, stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis" / "fork"))
import analyze_dev as AD  # noqa: E402

OUT = ROOT / "analysis" / "fork" / "out"
SEED = 20261001
KS = (6, 8, 12, 16)
J_HOLD = 34
CELLS_DEV = ("gptq_w4_d1", "awq_w4")
HOLD_CELLS = (("q4", "gptq_w4_d1", "gptq_w4_d1"), ("q8", "gptq_w4_d1", "gptq_w4_d1"), ("q8", "awq_w4", "awq_w4"))
PERSONAS = ("Easy", "Hard", "None")
PERSONA_RE = re.compile(r"PERSONA:(\w+)")
GH_N = 24


# ---------------------------------------------------------------------------------------------------------------- data
def load_dev_units(snap_path: Path) -> tuple[list[dict], dict]:
    snap = json.load(open(snap_path))
    cache, units = {}, []
    for d in AD.discover(False):
        if "analysis/fork/telecom" not in str(d):
            continue
        r = AD.load_dir(d, snap, cache)
        for u in r["units"]:
            if r["quarantined"]:
                u.setdefault("excluded", "quarantined fork task (QQ no-op mismatch)")
            units.append(u)
    guard = AD.split_guard(units, "dev", "holdout_k_planning")
    units, ndup = AD.dedupe_units(units)
    incomplete = AD.mark_incomplete_blocks(units, "dev", strict=True)
    out = []
    for u in units:
        if "excluded" in u or u["domain"] != "telecom":
            continue
        e = AD.effects(u["Y"], u.get("div", True))
        pm = PERSONA_RE.search(u["task"])
        out.append({**u, **e, "persona": pm.group(1) if pm else "None"})
    return out, {"guard": guard, "deduplicated": ndup, "incomplete_blocks": incomplete}


# --------------------------------------------------------------------------------------------------------------- fit
def arrays(units, cell):
    us = [u for u in units if u["model"] == "q8" and u["cell"] == cell]
    tasks = sorted({u["task"] for u in us})
    blocks = sorted({u["block"] for u in us})
    ti, bi = {t: i for i, t in enumerate(tasks)}, {b: i for i, b in enumerate(blocks)}
    M = np.full((len(tasks), len(blocks)), np.nan)
    R = np.full((len(tasks), len(blocks)), np.nan)
    for u in us:
        M[ti[u["task"]], bi[u["block"]]] = u["M"]
        R[ti[u["task"]], bi[u["block"]]] = u["rescue"]
    pers = np.array([PERSONAS.index(PERSONA_RE.search(t).group(1) if PERSONA_RE.search(t) else "None") for t in tasks])
    return tasks, blocks, M, R, pers


def fit_joint(Ms, pers):
    """Bivariate logistic GLMM: per cell persona intercepts + block fixed effects (sum-to-zero) + correlated task effects."""
    x, w = np.polynomial.hermite_e.hermegauss(GH_N)
    w = w / w.sum()
    Z1, Z2 = np.meshgrid(x, x, indexing="ij")
    W = np.outer(w, w)
    K = Ms[0].shape[1]

    def unpack(th):
        i = 0
        mu = th[i:i + 6].reshape(2, 3); i += 6
        vb = []
        for _ in range(2):
            v = th[i:i + K - 1]; i += K - 1
            vb.append(np.append(v, -v.sum()))
        ls1, ls2, z = th[i:i + 3]
        return mu, vb, np.exp(ls1), np.exp(ls2), np.tanh(z)

    def nll(th):
        mu, vb, s1, s2, rho = unpack(th)
        u1 = s1 * Z1
        u2 = s2 * (rho * Z1 + np.sqrt(1 - rho ** 2) * Z2)
        ll = np.zeros(Ms[0].shape[0])
        lik = np.ones((Ms[0].shape[0],) + Z1.shape)
        for c, (M, u) in enumerate(((Ms[0], u1), (Ms[1], u2))):
            eta = mu[c][pers][:, None, None, None] + vb[c][None, :, None, None] + u[None, None]
            p = special.expit(eta)
            y = M[:, :, None, None]
            lik = lik * np.prod(np.where(y == 1, p, 1 - p), axis=1)
        ll = np.log(np.maximum((lik * W[None]).sum(axis=(1, 2)), 1e-300))
        return -ll.sum()

    th0 = np.zeros(6 + 2 * (K - 1) + 3)
    th0[:6] = -2.0
    th0[-3:] = [0.0, 0.0, 0.5]
    r = optimize.minimize(nll, th0, method="L-BFGS-B")
    mu, vb, s1, s2, rho = unpack(r.x)
    # block-fixed-effect standard errors from the numerical Hessian diagonal (approximate) via finite differences
    return {"mu": mu, "vb": vb, "s_u": (float(s1), float(s2)), "rho_u": float(rho), "nll": float(r.fun), "ok": bool(r.success),
            "theta": r.x, "nll_fn": nll, "unpack": unpack}


def profile_su(fit, which):
    """Rough 95% profile-likelihood interval for s_u of one cell (others re-optimised)."""
    nll, th = fit["nll_fn"], fit["theta"]
    idx = len(th) - 3 + which
    base = fit["nll"]
    out = {}
    for side, grid in (("lo", np.linspace(th[idx], th[idx] - 4, 17)), ("hi", np.linspace(th[idx], th[idx] + 3, 13))):
        last = float(np.exp(th[idx]))
        x0 = th.copy()
        for g in grid[1:]:
            free = [i for i in range(len(th)) if i != idx]

            def f(z):
                t = x0.copy(); t[free] = z; t[idx] = g
                return nll(t)
            r = optimize.minimize(f, x0[free], method="L-BFGS-B")
            x0[free] = r.x
            if 2 * (r.fun - base) > 3.84:
                break
            last = float(np.exp(g))
        else:
            last = float(np.exp(grid[-1])) if side == "hi" else 0.0
        out[side] = last
    return out


def fit_direction(M, R):
    """Beta-binomial for per-task rescue share among consequential units (pooled over blocks)."""
    n = np.nansum(M, axis=1).astype(int)
    k = np.nansum(R, axis=1).astype(int)
    keep = n > 0
    n, k = n[keep], k[keep]

    def nll(t):
        a, b = np.exp(t)
        return -np.sum(special.betaln(k + a, n - k + b) - special.betaln(a, b))
    r = optimize.minimize(nll, [0.0, 0.0], method="L-BFGS-B", bounds=[(-5, 5), (-5, 5)])
    a, b = np.exp(r.x)
    return {"a": float(a), "b": float(b), "mean_rescue_share": float(a / (a + b)), "n_tasks_with_M": int(keep.sum()),
            "rescues": int(k.sum()), "consequential": int(n.sum())}


def block_shock_sd(vb, M):
    """Moment estimate: var of fitted block effects minus mean sampling variance (delta method on block rates)."""
    p = np.nanmean(M, axis=0)
    n = np.sum(~np.isnan(M), axis=0)
    se2 = 1.0 / np.maximum(n * p * (1 - p), 1e-9)  # var of logit(p_hat)
    v = np.var(vb, ddof=1) - np.mean(se2)
    return float(np.sqrt(max(v, 0.0))), float(np.var(vb, ddof=1)), float(np.mean(se2))


# --------------------------------------------------------------------------------------------------------- simulate
def spearman_ranks(X):
    """Average ranks along the last axis."""
    return stats.rankdata(X, axis=-1)


def persona_perms(pers, n_perm, rng):
    idx = np.arange(len(pers))
    P = np.tile(idx, (n_perm, 1))
    for g in np.unique(pers):
        members = idx[pers == g]
        P[:, members] = members[rng.permuted(np.tile(np.arange(len(members)), (n_perm, 1)), axis=1)]
    return P


def simulate(params, K, reps, n_perm, rng, su_scale=1.0, null=False):
    J = J_HOLD
    pers = np.array([0] * 11 + [1] * 11 + [2] * 12)
    C = len(HOLD_CELLS)
    mu = np.array([params["mu"][src] for _, _, src in HOLD_CELLS])           # C x 3
    su = np.array([params["s_u"][src] for _, _, src in HOLD_CELLS]) * su_scale
    if null:
        su = su * 0.0
    sv = np.array([params["s_v"][src] for _, _, src in HOLD_CELLS])
    ab = np.array([[params["dir"][src]["a"], params["dir"][src]["b"]] for _, _, src in HOLD_CELLS])
    ru, rv = params["rho_u"], params["rho_v"]
    Cu = np.full((C, C), ru); np.fill_diagonal(Cu, 1.0)
    Cv = np.full((C, C), rv); np.fill_diagonal(Cv, 1.0)
    Lu, Lv = np.linalg.cholesky(Cu), np.linalg.cholesky(Cv + 1e-9 * np.eye(C))
    P = persona_perms(pers, n_perm, rng)
    hA = K // 2
    res = collections.defaultdict(list)
    for _ in range(reps):
        u = (rng.standard_normal((J, C)) @ Lu.T) * su                      # J x C
        v = (rng.standard_normal((K, C)) @ Lv.T) * sv                      # K x C
        eta = mu[:, pers].T[:, None, :] + v[None] + u[:, None, :]          # J x K x C
        Mx = rng.random(eta.shape) < special.expit(eta)
        q = rng.beta(ab[:, 0], ab[:, 1], size=(J, C))
        resc = Mx & (rng.random(eta.shape) < q[:, None, :])
        G = resc.astype(float) - (Mx & ~resc).astype(float)               # J x K x C
        # ---- primary: G_all = equal-weight mean over cells; block means over tasks
        Gjb = G.mean(axis=2)                                               # J x K (cell-averaged per task-block)
        gb = Gjb.mean(axis=0)
        m, sd = gb.mean(), gb.std(ddof=1)
        se_t = sd / np.sqrt(K)
        res["G_hat"].append(m)
        res["t90_halfwidth"].append(stats.t.ppf(0.95, K - 1) * se_t)
        res["t95_halfwidth"].append(stats.t.ppf(0.975, K - 1) * se_t)
        # crossed task x block: Var(grand mean) = (MS_T + MS_B - MS_E) / (J K)
        gt = Gjb.mean(axis=1)
        msT = K * np.sum((gt - m) ** 2) / (J - 1)
        msB = J * np.sum((gb - m) ** 2) / (K - 1)
        resid = Gjb - gt[:, None] - gb[None, :] + m
        msE = np.sum(resid ** 2) / ((J - 1) * (K - 1))
        se_x = np.sqrt(max(msT + msB - msE, msE) / (J * K))
        res["crossed90_halfwidth"].append(1.645 * se_x)
        res["crossed95_halfwidth"].append(1.96 * se_x)
        lb_t = m - stats.t.ppf(0.95, K - 1) * se_t
        res["t_lb_gt0"].append(lb_t > 0)
        res["t_ci90_inside_pm3pp"].append((m - stats.t.ppf(0.95, K - 1) * se_t > -0.03) and (m + stats.t.ppf(0.95, K - 1) * se_t < 0.03))
        res["crossed_ci90_inside_pm3pp"].append((m - 1.645 * se_x > -0.03) and (m + 1.645 * se_x < 0.03))
        # ---- secondary: cross-half repeatability
        mA = Mx[:, :hA, :].mean(axis=1).T                                  # C x J
        mB = Mx[:, hA:, :].mean(axis=1).T
        est = (mA.std(axis=1) > 0) & (mB.std(axis=1) > 0)
        res["n_cells_estimable"].append(int(est.sum()))
        res["levels_used_A"].append(float(np.mean([len(np.unique(mA[c])) for c in range(C)])))
        if not est.any():
            res["p"].append(np.nan); res["rho"].append(np.nan)
            continue
        rA = spearman_ranks(mA[est]); rB = spearman_ranks(mB[est])
        rA = rA - rA.mean(axis=1, keepdims=True); rB = rB - rB.mean(axis=1, keepdims=True)
        nA, nB = np.linalg.norm(rA, axis=1), np.linalg.norm(rB, axis=1)
        rho_obs = np.mean(np.sum(rA * rB, axis=1) / (nA * nB))
        rBp = rB[:, P]                                                     # Ce x n_perm x J
        rho_perm = np.mean(np.einsum("cj,cpj->cp", rA, rBp) / (nA * nB)[:, None], axis=0)
        pval = (1 + np.sum(rho_perm >= rho_obs - 1e-12)) / (1 + n_perm)
        res["p"].append(pval); res["rho"].append(rho_obs)
    a = {k: np.asarray(v, float) for k, v in res.items()}
    p = a["p"]
    return {
        "K": K, "reps": reps, "n_perm": n_perm, "su_scale": su_scale, "null": null,
        "G_true_equal_weight": None,
        "G_hat_mean": round(float(a["G_hat"].mean()), 4), "G_hat_sd_across_reps": round(float(a["G_hat"].std()), 4),
        "ci90_width_t_blocks_pp": round(float(200 * np.median(a["t90_halfwidth"])), 2),
        "ci95_width_t_blocks_pp": round(float(200 * np.median(a["t95_halfwidth"])), 2),
        "ci90_width_crossed_pp": round(float(200 * np.median(a["crossed90_halfwidth"])), 2),
        "ci95_width_crossed_pp": round(float(200 * np.median(a["crossed95_halfwidth"])), 2),
        "P_t_LB_gt_0": round(float(a["t_lb_gt0"].mean()), 3),
        "P_t_ci90_inside_pm3pp": round(float(a["t_ci90_inside_pm3pp"].mean()), 3),
        "P_crossed_ci90_inside_pm3pp": round(float(a["crossed_ci90_inside_pm3pp"].mean()), 3),
        "repeatability_power_alpha05": round(float(np.nanmean(p < 0.05) * np.mean(np.isfinite(p))), 3),
        "P_not_estimable_endpoint": round(float(np.mean(~np.isfinite(p))), 3),
        "mean_cells_estimable": round(float(a["n_cells_estimable"].mean()), 2),
        "median_rho": round(float(np.nanmedian(a["rho"])), 3) if np.isfinite(a["rho"]).any() else None,
        "mean_distinct_rate_levels_per_half": round(float(a["levels_used_A"].mean()), 2),
    }


# ------------------------------------------------------------------------------------------------------------- cost
LOG_RE = re.compile(r"^\[(?P<ts>[\d\- :]+)\] (?P<node>\S+) (?P<ev>claimed|task) (?P<task>\S+)(?: exited rc=(?P<rc>-?\d+))? on GPUs \[(?P<gpus>[^\]]*)\]")


def telecom_costs() -> dict:
    ev = []
    for p in sorted(glob.glob("/data/ziyangs/cloq_work/logs/node_*.out")):
        for line in open(p, errors="replace"):
            m = LOG_RE.match(line.strip())
            if m and ("tel" in m["task"] or m["task"].startswith("fork_dev_q")):
                ev.append((datetime.strptime(m["ts"], "%Y-%m-%d %H:%M:%S"), m["node"], m["ev"], m["task"], m["rc"],
                           len([g for g in m["gpus"].split(",") if g.strip()])))
    ev.sort()
    open_ = {}
    att = []
    for ts, node, kind, task, rc, ng in ev:
        if kind == "claimed":
            open_[(node, task)] = (ts, ng)
        elif (node, task) in open_:
            t0, ng0 = open_.pop((node, task))
            att.append({"task": task, "node": node, "hours": (ts - t0).total_seconds() / 3600, "gpus": ng0, "rc": int(rc)})
    groups = collections.defaultdict(lambda: {"gpu_h_ok": 0.0, "gpu_h_all": 0.0, "attempts": 0, "failed": 0})
    for a in att:
        t = a["task"]
        m = re.match(r"^fork_tel_(q\d+)_(.+?)_(g\d)(?:_s\dof\d)?$", t)
        m2 = re.match(r"^a6k2_(q\d+)_tel_(.+?)_fdev(\d)$", t)
        m3 = re.match(r"^fork_dev_(q\d+)_(.+?)_(g\d)(?:_s\dof\d)?$", t)
        if m3:
            key = f"forkRA|{m3[1]}|{m3[2]}|{m3[3]}"
        elif m:
            key = f"fork|{m[1]}|{m[2]}|{m[3]}"
        elif m2:
            key = f"closed|{m2[1]}|{m2[2]}|fdev{m2[3]}"
        else:
            continue
        g = groups[key]
        g["attempts"] += 1
        g["gpu_h_all"] += a["hours"] * a["gpus"]
        if a["rc"] == 0:
            g["gpu_h_ok"] += a["hours"] * a["gpus"]
        else:
            g["failed"] += 1
    groups = {k: {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in sorted(groups.items())}
    # per 80-task block: fork groups g = 2 blocks; closed-loop fdev = 3 blocks
    per_block = collections.defaultdict(list)
    for k, v in groups.items():
        kind, m, cell, grp = k.split("|")
        if kind == "forkRA":
            per_block[f"forkRA_group|{m}|{cell}"].append(v["gpu_h_ok"])
            continue
        if kind == "fork":
            # resharded groups: g1 of q8 gptq had a killed unsharded attempt; ok-hours count only successful shards
            per_block[f"fork|{m}|{cell}"].append(v["gpu_h_ok"] / 2)
        else:
            per_block[f"closed|{m}|{cell}"].append(v["gpu_h_ok"] / 3)
    pb = {k: {"per_80task_block_gpu_h": [round(x, 2) for x in v], "median": round(float(np.median(v)), 2),
              "mean": round(float(np.mean(v)), 2)} for k, v in per_block.items()}
    # all-attempt (with failed/killed attempts) per-block fork cost, conservative
    for cell in ("gptq_w4_d1", "awq_w4"):
        xs = [v["gpu_h_all"] / 2 for k, v in groups.items() if k.startswith(f"fork|q8|{cell}|")]
        if xs:
            pb[f"fork|q8|{cell}"]["mean_all_attempts"] = round(float(np.mean(xs)), 2)
    return {"source": "/data/ziyangs/cloq_work/logs/node_*.out (claimed/exited pairs; GPU-h = wall x GPUs held)",
            "attempts": att, "groups": groups, "per_block": pb}


def holdout_cost(pb: dict, K: int = 12) -> dict:
    s = J_HOLD / 80
    get = lambda k: pb.get(k, {}).get("mean")
    f8g, f8a = get("fork|q8|gptq_w4_d1"), get("fork|q8|awq_w4")
    c8b, c8g, c8a = get("closed|q8|bfpair"), get("closed|q8|gptq_w4_d1"), get("closed|q8|awq_w4")
    c4b, c4g = get("closed|q4|bfpair"), get("closed|q4|gptq_w4_d1")
    # q4 fork cost: no telecom q4 fork was run; scale the q8 telecom fork cost by the retail/airline dev fork q4/q8 ratio
    # (fork_dev_q{4,8}_gptq_w4_d1_g1-g4, same blocks and tasks); the closed-loop q4/q8 ratio is reported as an alternative
    ra4, ra8 = pb.get("forkRA_group|q4|gptq_w4_d1", {}).get("mean"), pb.get("forkRA_group|q8|gptq_w4_d1", {}).get("mean")
    ratio = (ra4 / ra8) if (ra4 and ra8) else None
    ratio_cl = (c4g / c8g) if (c4g and c8g) else None
    f4g = f8g * ratio if ratio else None
    f8g_all, f8a_all = pb["fork|q8|gptq_w4_d1"].get("mean_all_attempts"), pb["fork|q8|awq_w4"].get("mean_all_attempts")
    rows = {"closed_q8_bfpair": c8b, "closed_q8_gptq": c8g, "closed_q8_awq": c8a, "closed_q4_bfpair": c4b,
            "closed_q4_gptq": c4g, "fork_q8_gptq": f8g, "fork_q8_awq": f8a, "fork_q4_gptq_scaled": f4g}
    per_block80 = sum(v for v in rows.values() if v)
    total = per_block80 * s * K
    cons = per_block80 - f8g - f8a - f4g + f8g_all + f8a_all + f8g_all * max(ratio or 1, ratio_cl or 1)
    total_cons = cons * s * K
    return {"K": K, "tasks_scale": f"{J_HOLD}/80", "per_80task_block_components_gpu_h": {k: (round(v, 2) if v else None) for k, v in rows.items()},
            "q4_over_q8_fork_ratio_retail_airline_dev": round(ratio, 3) if ratio else None,
            "q4_over_q8_closed_loop_ratio_telecom": round(ratio_cl, 3) if ratio_cl else None,
            "total_gpu_h_conservative": round(total_cons, 1),
            "conservative_rule": "fork costs include failed/killed attempts and q4 fork uses the larger of the two q4/q8 ratios",
            "per_holdout_block_gpu_h": round(per_block80 * s, 1), "total_gpu_h": round(total, 1),
            "range_x0.7_x1.5": [round(total * 0.7, 0), round(total * 1.5, 0)],
            "note": ("means over measured dev groups; linear in tasks (holdout tasks are a stratified draw of the same base split, so "
                     "per-task cost is assumed equal); q4 telecom forks were never run, so their cost is scaled; failed attempts "
                     "excluded from the central figure")}


# ------------------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--reps", type=int, default=1000)
    ap.add_argument("--perms", type=int, default=2000)
    a = ap.parse_args()
    t0 = time.time()
    snap = Path(a.snapshot) if a.snapshot else Path(sorted(glob.glob(str(ROOT / "analysis/insights/iter_3/out/snapshot_auto_*.json")))[-1])
    units, prov = load_dev_units(snap)
    data = {c: arrays(units, c) for c in CELLS_DEV}
    tasks0 = data[CELLS_DEV[0]][0]
    assert all(data[c][0] == tasks0 for c in CELLS_DEV), "cells must share the dev task list"
    assert all(not np.isnan(data[c][2]).any() for c in CELLS_DEV), "incomplete task x block matrix"
    pers = data[CELLS_DEV[0]][4]
    fit = fit_joint([data[c][2] for c in CELLS_DEV], pers)
    prof = {c: profile_su(fit, i) for i, c in enumerate(CELLS_DEV)}
    params = {"mu": {}, "s_u": {}, "s_v": {}, "dir": {}, "rho_u": fit["rho_u"]}
    desc = {}
    for i, c in enumerate(CELLS_DEV):
        tasks, blocks, M, R, _ = data[c]
        params["mu"][c] = fit["mu"][i]
        params["s_u"][c] = fit["s_u"][i]
        sv, var_vb, se2 = block_shock_sd(fit["vb"][i], M)
        params["s_v"][c] = sv
        params["dir"][c] = fit_direction(M, R)
        G = R - (M - R)
        tm = M.mean(axis=1)
        desc[c] = {"n_tasks": len(tasks), "blocks": blocks, "units": int(M.size), "M_rate": round(float(M.mean()), 4),
                   "M_rate_by_block": [round(float(x), 4) for x in M.mean(axis=0)],
                   "G_all": round(float(G.mean()), 4), "G_by_block": [round(float(x), 4) for x in G.mean(axis=0)],
                   "M_rate_by_persona": {p: round(float(M[pers == k].mean()), 4) for k, p in enumerate(PERSONAS)},
                   "tasks_with_any_M": int((tm > 0).sum()), "tasks_M_ge_half": int((tm >= 0.5).sum()),
                   "s_u_fit": round(fit["s_u"][i], 3), "s_u_profile95": {k: round(v, 3) for k, v in prof[c].items()},
                   "block_effects_logit": [round(float(x), 3) for x in fit["vb"][i]],
                   "s_v_moment": round(sv, 3), "var_block_effects": round(var_vb, 4), "mean_sampling_var": round(se2, 4),
                   "direction_beta": params["dir"][c],
                   "mu_logit_by_persona": {p: round(float(fit["mu"][i][k]), 3) for k, p in enumerate(PERSONAS)}}
    # dev split-half check (3 + 3 blocks, sha order of block ids, same rule as the holdout) - descriptive only
    import hashlib
    order = sorted(data[CELLS_DEV[0]][1], key=lambda b: hashlib.sha256(f"holdout-split-v1|{b}".encode()).hexdigest())
    for c in CELLS_DEV:
        tasks, blocks, M, R, _ = data[c]
        ia = [blocks.index(b) for b in order[:3]]; ib = [blocks.index(b) for b in order[3:]]
        mA, mB = M[:, ia].mean(axis=1), M[:, ib].mean(axis=1)
        desc[c]["dev_split_half_spearman_descriptive"] = round(float(stats.spearmanr(mA, mB).statistic), 3)
    rv = float(np.corrcoef(fit["vb"][0], fit["vb"][1])[0, 1])
    params["rho_v"] = float(np.clip(rv, 0.0, 1.0))
    rng = np.random.default_rng(SEED)
    sims = {"fitted": [], "s_u_halved": [], "null_s_u_0": []}
    for K in KS:
        sims["fitted"].append(simulate(params, K, a.reps, a.perms, rng))
        sims["s_u_halved"].append(simulate(params, K, a.reps, a.perms, rng, su_scale=0.5))
        sims["null_s_u_0"].append(simulate(params, K, max(a.reps // 2, 200), a.perms, rng, null=True))
    # true G under the model (equal weight over the 3 holdout cells; persona mix 11/11/12), Monte Carlo
    def g_true(pr, su_scale=1.0):
        rng2 = np.random.default_rng(SEED + 1)
        pers_h = np.array([0] * 11 + [1] * 11 + [2] * 12)
        out = []
        for _, _, src in HOLD_CELLS:
            u = rng2.standard_normal((400000,)) * pr["s_u"][src] * su_scale
            v = rng2.standard_normal((400000,)) * pr["s_v"][src]
            pj = pers_h[rng2.integers(0, J_HOLD, 400000)]
            pm = special.expit(pr["mu"][src][pj] + u + v).mean()
            d = pr["dir"][src]
            out.append((pm, pm * (2 * d["a"] / (d["a"] + d["b"]) - 1)))
        return out
    gfit = g_true(params)
    gt = [g for _, g in gfit]
    for name, sc in (("fitted", 1.0), ("s_u_halved", 0.5)):
        val = round(float(np.mean([g for _, g in g_true(params, sc)])), 4)
        for r in sims[name]:
            r["G_true_equal_weight"] = val
    # EXTERNAL_REVIEW §F plans power at true G = 3 pp: shift each cell's rescue share so its G is +3 pp (a + b kept)
    import copy
    p3 = copy.deepcopy(params)
    pm_src = {src: pm for (_, _, src), (pm, _) in zip(HOLD_CELLS, gfit)}
    for src, pm in pm_src.items():
        q = min(max((0.03 / pm + 1) / 2, 0.01), 0.99)
        tot = params["dir"][src]["a"] + params["dir"][src]["b"]
        p3["dir"][src] = {**params["dir"][src], "a": q * tot, "b": (1 - q) * tot, "mean_rescue_share": q}
    sims["G_3pp"] = [simulate(p3, K, a.reps, a.perms, rng) for K in KS]
    for r in sims["G_3pp"]:
        r["G_true_equal_weight"] = 0.03
    costs = telecom_costs()
    hc = holdout_cost(costs["per_block"], 12)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    res = {
        "schema": "holdout-k-planning-v1", "created_utc": stamp, "script": "analysis/fork/holdout_k_planning.py",
        "split": "dev (telecom only; analyze_dev.split_guard enforced; no holdout task id read)",
        "snapshot": str(snap.relative_to(ROOT)), "provenance": prov, "seed": SEED, "reps": a.reps, "perms_in_sim": a.perms,
        "assumptions": {
            "holdout_tasks": J_HOLD, "holdout_persona_mix": "11 Easy / 11 Hard / 12 None (dev mix 27/25/28 scaled; holdout ids not read)",
            "cells": [f"{m} {c}" for m, c, _ in HOLD_CELLS], "cell_weights": "equal (1/3)",
            "q4_gptq_w4_d1": "no telecom dev forks exist for q4; parameters borrowed from q8 GPTQ-W4 d1 (flag)",
            "cross_cell_task_corr_rho_u": round(fit["rho_u"], 3), "cross_cell_block_corr_rho_v": round(params["rho_v"], 3),
            "rho_v_raw": round(rv, 3), "halves": "first K/2 vs last K/2 blocks (exchangeable, equivalent to the sha order)",
            "repeatability_test": "Spearman per cell, equal-weight mean over estimable cells, one-sided, persona-stratified "
                                  "permutation of m_B task labels identical across cells; constant vector -> cell not estimable",
            "G_intervals": "t over K block means of the cell-averaged task mean (df K-1); crossed = two-way ANOVA moments, normal"},
        "dev_fit": desc, "fit_ok": fit["ok"], "simulation": sims, "cost": {"measured": {k: v for k, v in costs.items() if k != "attempts"},
                                                                           "attempts": costs["attempts"], "holdout_K12_3cells": hc},
        "runtime_s": round(time.time() - t0, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / f"holdout_k_planning_{stamp}.json"
    json.dump(res, open(jp, "w"), indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    mp = jp.with_suffix(".md")
    mp.write_text(markdown(res, jp))
    print(jp); print(mp)


def markdown(r: dict, jp: Path) -> str:
    L = [f"# Holdout K planning-precision simulation (telecom DEV only) — {r['created_utc']}", "",
         f"Script `{r['script']}`; snapshot `{r['snapshot']}`; seed {r['seed']}; {r['reps']} reps per K, {r['perms_in_sim']} "
         "permutations per rep (the prereg uses 10,000). JSON: `" + str(jp.relative_to(ROOT)) + "`.", "",
         "Purpose: confirm K = 12 is adequate (GPT-6.1 review 4); not a K-selection exercise. No holdout task was read.", "",
         "## Dev fit (q8, telecom dev, 80 tasks × blocks f01–f06, all 12 cell-blocks complete)", "",
         "| cell | M rate | G_all | tasks with any M | s_u (95% profile) | s_v | ρ_u (GPTQ–AWQ) | rescue share (beta mean) | dev split-half ρ (descr.) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for c, d in r["dev_fit"].items():
        L.append(f"| q8 {c} | {d['M_rate']:.3f} | {d['G_all']:+.4f} | {d['tasks_with_any_M']}/80 | {d['s_u_fit']:.2f} "
                 f"[{d['s_u_profile95']['lo']:.2f}, {d['s_u_profile95']['hi']:.2f}] | {d['s_v_moment']:.2f} | "
                 f"{r['assumptions']['cross_cell_task_corr_rho_u']:.2f} | {d['direction_beta']['mean_rescue_share']:.2f} | "
                 f"{d['dev_split_half_spearman_descriptive']:+.2f} |")
    L += ["", "Assumptions: " + "; ".join(f"{k}: {v}" for k, v in r["assumptions"].items()), ""]
    for name, title in (("fitted", "Fitted dev heterogeneity"), ("s_u_halved", "Sensitivity: task heterogeneity s_u halved"),
                        ("null_s_u_0", "Null: no task heterogeneity (size check)"),
                        ("G_3pp", "Planning alternative of EXTERNAL_REVIEW §F: true G_all = +3 pp (rescue share shifted)")):
        L += [f"## {title}", "",
              "| K | 90% CI width G_all, t over blocks (pp) | 95% width t (pp) | 90% width crossed (pp) | P(one-sided 95% t-LB > 0) | P(90% t-CI inside ±3 pp) | "
              "P(90% crossed CI inside ±3 pp) | repeatability power / size (α 0.05) | P(endpoint not estimable) | rate levels per half |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for s in r["simulation"][name]:
            L.append(f"| {s['K']} | {s['ci90_width_t_blocks_pp']} | {s['ci95_width_t_blocks_pp']} | {s['ci90_width_crossed_pp']} | {s['P_t_LB_gt_0']} | "
                     f"{s['P_t_ci90_inside_pm3pp']} | {s['P_crossed_ci90_inside_pm3pp']} | {s['repeatability_power_alpha05']} | "
                     f"{s['P_not_estimable_endpoint']} | {s['mean_distinct_rate_levels_per_half']} |")
        if name != "null_s_u_0":
            L.append(f"\nTrue G_all under the model (equal weight): {r['simulation'][name][0]['G_true_equal_weight']:+.4f}.")
        else:
            L.append("\nUnder this null the repeatability column is the test's size; the G columns use the dev G direction.")
        L.append("")
    hc = r["cost"]["holdout_K12_3cells"]
    L += ["## GPU cost from measured telecom dev logs", "",
          "| component (per 80-task block) | GPU-h (mean over dev groups) |", "|---|---|"]
    for k, v in hc["per_80task_block_components_gpu_h"].items():
        L.append(f"| {k} | {v} |")
    L += ["", f"Holdout, K = 12, 3 cells, 34 tasks: **≈ {hc['total_gpu_h']} GPU-h** (range ×0.7–×1.5: {hc['range_x0.7_x1.5']}); "
          f"≈ {hc['per_holdout_block_gpu_h']} GPU-h per block; conservative {hc['total_gpu_h_conservative']} GPU-h "
          f"({hc['conservative_rule']}). q4/q8 fork ratio (retail/airline dev) {hc['q4_over_q8_fork_ratio_retail_airline_dev']}, "
          f"closed-loop telecom {hc['q4_over_q8_closed_loop_ratio_telecom']}. {hc['note']}.", "",
          "Measured groups (GPU-h, successful attempts / all attempts):", ""]
    for k, v in r["cost"]["measured"]["groups"].items():
        L.append(f"- `{k}`: {v['gpu_h_ok']} / {v['gpu_h_all']} ({v['attempts']} attempts, {v['failed']} failed)")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
