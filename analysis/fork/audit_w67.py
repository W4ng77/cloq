"""W67 audit v2 (W78; W68/W70 audit corrected after GPT-6.1's review): dependence-preserving references, nonce-split
replication and a valid conditional "beyond baseline propensity" test, on the full retail/airline panel.

INTERNAL REPLICATION ONLY: these development outcomes were already viewed (W67); nothing here is fresh confirmation.
v1 outputs (w67_audit_<sid>.md, direction_replication_<sid>.json; 0224Z, 0255Z) are kept for provenance. v2 writes
w67_audit_v2_<sid>_<utc>.md and direction_replication_v2_<sid>_<utc>.json (never overwrites).

What changed vs v1 (W78):
  (1) Population. v1 intersected task ids across all (cell, block) pairs. One airline-only block (q4 AWQ-W4, q5: its
      retail units were excluded by the W70 strict rule) made every retail task "missing" in that block, so the 0255Z
      "27-task x 20-block" audit silently dropped all 58 retail tasks: its 11/12 was an airline-only result. v2 never
      intersects tasks. Populations are declared up front and checked:
        panel85 (PRIMARY)  all 58 retail + 27 airline split tasks x the blocks complete for all 85 tasks in EVERY compared
                           cell; task weights equal, so the domain weights are fixed at 58/85 and 27/85.
        retail58, airline27  per-domain analyses on the same blocks (same frozen split).
        legacy_airline27_x20 the v1 (0255Z) population, kept only to reproduce v1 and to show the effect of the test fix.
      A population whose tasks are not all observed in all its blocks aborts the run (no silent dropping).
  (2) Conditional test. v1 permuted the raw split-B task rates while holding the covariates fixed. That breaks the
      relation between the B outcome and the nuisance covariates (difficulty, propensity), which the null allows, so
      the reference distribution was not that of the null "the A rate adds nothing given the nuisance". v2 uses the
      Freedman-Lane procedure: fit the nuisance-only model yB ~ Z, permute its residuals WITHIN DOMAIN, add them back
      to the nuisance fit, refit the full model yB ~ Z + yA and recompute the statistic. The statistic is the
      HC3-robust t of the yA coefficient (pivotal; Anderson & Robinson 2001 and Winkler et al. 2014 recommend a pivotal
      statistic for Freedman-Lane, and HC3 limits the damage from the binomial heteroscedasticity of task rates).
      Why Freedman-Lane: it keeps the nuisance structure (yB's dependence on Z) intact under every permutation and is
      the best-behaved of the residual-permutation schemes in small samples. Why within domain: residual
      exchangeability is only plausible between tasks of the same domain (different simulators/policies, and the
      domain intercepts are part of Z). Exchangeability is checked (|residual| vs flip opportunity and fitted value;
      residual SD by domain), and a restricted wild bootstrap (Rademacher sign flips of the same nuisance-model
      residuals; valid under heteroscedasticity, needs only independence across tasks and symmetry) is reported
      alongside as a robustness check. Partial correlations are descriptive.
  (3) Dependence. Splits A and B are disjoint block sets (asserted). Given the task's latent propensities, A and B
      task rates are independent because they come from disjoint nonce blocks; within a split, a block's common effect
      shifts all tasks of a domain together and is absorbed by the domain intercepts. Residual cross-task dependence
      through block x task interactions is handled by a block-aware bootstrap: blocks are resampled with replacement
      within A and within B (independently), every task rate and covariate is recomputed, and the model refit. The
      reported interval is the delete-one-block jackknife (within A and within B; variances add); the with-replacement
      block bootstrap is kept in the JSON but labelled attenuated (duplicated blocks add noise to yA, biasing beta_A
      towards 0). 9-10 blocks per split: intervals are indicative.

Nuisance specifications (declared before any v2 result was seen):
  PRIMARY  "AB": domain intercepts + QQ success propensity on A and on B, their flip opportunities q(1-q), and BF16 task
           success over the model's admitted bfpair blocks. q_B is the opportunity structure of the outcome split itself
           (QQ is the original episode, unaffected by the fork intervention, so it is a legitimate covariate).
  SECONDARY "A": v1's covariates (q_A, q_A(1-q_A), BF16) plus domain intercepts.
  SENSITIVITY "ABL" (added after the first v2 run, so post hoc): AB + the task's mean BF16 trajectory length (agent
           decisions), i.e. longer tasks offer more pivots.
Per cell-direction we report beta_A, its HC3 t, Freedman-Lane one-sided p (H1: beta_A > 0) and two-sided p, wild p,
block-jackknife 95% interval, descriptive partial r, and counts of p < 0.05 over the 12 cell-directions raw and after
Holm. The legacy v1 statistic (raw-B permutation) is also reported for each population for comparison.

Other sections (unchanged methods, corrected population): concentration (task M rate A vs B), direction (A-defined sign
groups), direction beyond opportunity, cross-quantizer co-susceptibility (panel85 only), task heterogeneity.
Frozen nonce split: blocks of the population ordered by sha256("w67-split-v1|" + block); first half A, rest B; both
directions reported, plus 50 further hash splits as sensitivity. Monte Carlo p = (1 + #extreme)/(B + 1).

usage: python analysis/fork/audit_w67.py --snapshot <snapshot.json> [--B 2000] [--B-boot 1000]
-> analysis/fork/out/w67_audit_v2_<sid>_<utc>.md, analysis/fork/out/direction_replication_v2_<sid>_<utc>.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
CELLS = [(m, c) for m in ("q4", "q8") for c in ("gptq_w4_d1", "awq_w4", "kvq_int8")]
PAIRS = [(("q4", "gptq_w4_d1"), ("q4", "awq_w4")), (("q8", "gptq_w4_d1"), ("q8", "awq_w4")),
         (("q4", "gptq_w4_d1"), ("q4", "kvq_int8")), (("q4", "awq_w4"), ("q4", "kvq_int8")),
         (("q8", "gptq_w4_d1"), ("q8", "kvq_int8")), (("q8", "awq_w4"), ("q8", "kvq_int8")),
         (("q4", "awq_w4"), ("q8", "awq_w4")), (("q4", "gptq_w4_d1"), ("q8", "gptq_w4_d1"))]
SALT = "w67-split-v1|"


def hsplit(blocks: list[str], salt: str) -> tuple[list[str], list[str]]:
    o = sorted(blocks, key=lambda b: hashlib.sha256(f"{salt}{b}".encode()).hexdigest())
    h = len(o) // 2
    return sorted(o[:h]), sorted(o[h:])


def spearman(x, y) -> float:
    from scipy.stats import rankdata
    rx, ry = rankdata(x), rankdata(y)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def capture(rank_score, target, frac=0.2) -> float:
    n = max(1, int(round(frac * len(rank_score))))
    idx = np.argsort(-np.asarray(rank_score), kind="mergesort")[:n]
    tot = float(np.sum(target))
    return float(np.sum(np.asarray(target)[idx]) / tot) if tot > 0 else float("nan")


def perm_within_domain(rng, dom_idx: dict) -> np.ndarray:
    """A permutation of task indices that only moves tasks within their domain."""
    n = sum(len(v) for v in dom_idx.values())
    p = np.arange(n)
    for idx in dom_idx.values():
        p[idx] = rng.permutation(idx)
    return p


def pval(obs, null, greater=True) -> float:
    null = np.asarray(null)
    null = null[np.isfinite(null)]
    k = np.sum(null >= obs) if greater else np.sum(null <= obs)
    return float((1 + k) / (len(null) + 1))


def holm(ps: list[float], alpha: float = 0.05) -> list[bool]:
    order = np.argsort(ps)
    rej = [False] * len(ps)
    for r, i in enumerate(order):
        if ps[i] <= alpha / (len(ps) - r):
            rej[i] = True
        else:
            break
    return rej


# ---------------------------------------------------------------------------------------------------------------------
# regression machinery (vectorised over many response vectors)
# ---------------------------------------------------------------------------------------------------------------------


class OLS:
    """y (n,) or (n, B) on a fixed design X (n, p) whose LAST column is the tested regressor. Returns beta_last and its
    HC3-robust and classical t for every response column."""

    def __init__(self, X: np.ndarray):
        self.X = X
        self.P = np.linalg.pinv(X)                       # (p, n)
        self.h = np.clip(np.einsum("ij,ji->i", X, self.P), 0, 1 - 1e-8)  # leverages
        self.c = self.P[-1]                              # beta_last = c @ y
        self.df = max(1, X.shape[0] - np.linalg.matrix_rank(X))
        self.xtx_inv_last = float((self.P @ self.P.T)[-1, -1])

    def fit(self, Y: np.ndarray):
        Y2 = Y[:, None] if Y.ndim == 1 else Y
        beta = self.P @ Y2
        E = Y2 - self.X @ beta
        b = beta[-1]
        v_hc3 = np.sum((self.c[:, None] ** 2) * E ** 2 / (1 - self.h[:, None]) ** 2, axis=0)
        s2 = np.sum(E ** 2, axis=0) / self.df
        t_hc3 = np.where(v_hc3 > 0, b / np.sqrt(np.maximum(v_hc3, 1e-300)), np.nan)
        t_cl = np.where(s2 > 0, b / np.sqrt(np.maximum(s2 * self.xtx_inv_last, 1e-300)), np.nan)
        if Y.ndim == 1:
            return float(b[0]), float(t_hc3[0]), float(t_cl[0])
        return b, t_hc3, t_cl


def resid(Z: np.ndarray, v: np.ndarray) -> np.ndarray:
    return v - Z @ (np.linalg.pinv(Z) @ v)


def pcorr(Z, a, b) -> float:
    ra, rb = resid(Z, a), resid(Z, b)
    return float(np.corrcoef(ra, rb)[0, 1]) if ra.std() > 1e-12 and rb.std() > 1e-12 else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--B-boot", type=int, default=1000)
    ap.add_argument("--n-splits", type=int, default=50)
    ap.add_argument("--exclude-blocks", nargs="*", default=[], help="sensitivity: drop these blocks from every population")
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    rng = np.random.default_rng(AD.SEED)
    snap = json.load(open(a.snapshot))
    sid = snap["snapshot_id"]
    loaded = [AD.load_dir(d, snap, {}) for d in AD.discover(False)]
    allu = [u for L in loaded for u in L["units"]]
    files = {k: v for L in loaded for k, v in L["files"].items()}
    split_info = AD.split_guard(allu, "dev", "audit_w67")
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined")
    units, _ = AD.dedupe_units(allu)
    AD.mark_incomplete_blocks(units, "dev", strict=True)  # per-domain complete blocks; panels are selected explicitly below
    units = [u for u in units if "excluded" not in u and u["domain"] in AD.PANEL_DOMAINS]
    by, by_u = defaultdict(dict), defaultdict(dict)
    for u in units:
        by_u[(u["model"], u["cell"])][(u["task"], u["block"])] = u
        e = AD.effects(u["Y"], u["div"])
        by[(u["model"], u["cell"])][(u["task"], u["block"])] = (e["G"], e["M"], u["Y"]["QQ"], e["rescue"], e["damage"])
    present = [mc for mc in CELLS if by.get(mc)]
    man = json.load(open(AD.SPLITS))["splits"]["dev"]["tasks"]
    split_tasks = {d: sorted(f"{d}:{t}" for t in man[d]) for d in AD.PANEL_DOMAINS}
    all_blocks = sorted({b for mc in present for _, b in by[mc]} - set(a.exclude_blocks))

    def full_blocks(doms) -> list[str]:
        """Blocks in which EVERY split task of `doms` is observed in EVERY compared cell (no task intersection)."""
        ts = [t for d in doms for t in split_tasks[d]]
        return [b for b in all_blocks if all((t, b) in by[mc] for mc in present for t in ts)]

    # ---- populations (declared; checked) -------------------------------------------------------------------------
    b85 = full_blocks(AD.PANEL_DOMAINS)
    pops = {
        "panel85": {"domains": list(AD.PANEL_DOMAINS), "blocks": b85, "primary": True,
                    "label": "PRIMARY: complete 85-task retail+airline blocks (58 + 27 tasks; fixed domain weights 58/85, 27/85)"},
        "retail58": {"domains": ["retail"], "blocks": b85, "label": "per-domain: retail tasks on the panel85 blocks"},
        "airline27": {"domains": ["airline"], "blocks": b85, "label": "per-domain: airline tasks on the panel85 blocks"},
        "legacy_airline27_x20": {"domains": ["airline"], "blocks": full_blocks(["airline"]), "legacy": True,
                                 "label": "v1/0255Z population (airline only, every airline-complete block): reproduction only"},
    }
    for name, P in pops.items():
        P["tasks"] = [t for d in P["domains"] for t in split_tasks[d]]
        missing = [(mc, t, b) for mc in present for t in P["tasks"] for b in P["blocks"] if (t, b) not in by[mc]]
        if missing or len(P["blocks"]) < 4:
            raise SystemExit(f"audit_w67: population {name} is not fully observed ({len(missing)} missing units, "
                             f"{len(P['blocks'])} blocks); refusing to drop tasks silently")
        P["excluded_blocks"] = sorted(set(all_blocks) - set(P["blocks"]))

    import analyze_difficulty as ADF
    bfst = ADF.bf16_task_stats(snap)

    def run_population(name: str, P: dict) -> dict:
        tasks, blocks = P["tasks"], P["blocks"]
        T, K = len(tasks), len(blocks)
        dom_idx = defaultdict(list)
        for i, t in enumerate(tasks):
            dom_idx[t.split(":")[0]].append(i)
        doms = sorted(dom_idx)
        dom_of = np.array([doms.index(t.split(":")[0]) for t in tasks])

        def arr(mc, j):  # tasks x blocks
            return np.array([[by[mc][(t, b)][j] for b in blocks] for t in tasks], float)

        pop_digest = {f"{mc[0]}:{mc[1]}": AD.units_digest([by_u[mc][(t, b)] for t in tasks for b in blocks]) for mc in present}
        data = {mc: {"G": arr(mc, 0), "M": arr(mc, 1), "QQ": arr(mc, 2), "r": arr(mc, 3), "d": arr(mc, 4)} for mc in present}
        A0, B0 = hsplit(blocks, SALT)
        assert not set(A0) & set(B0) and set(A0) | set(B0) == set(blocks), "splits A and B must be disjoint and cover the population"
        bix = {b: i for i, b in enumerate(blocks)}

        def cols(s):
            return [bix[b] for b in s]

        def concentration(D, sa, sb):
            mA, mB = D["M"][:, cols(sa)].mean(1), D["M"][:, cols(sb)].mean(1)
            qA, qB = 1 - D["QQ"][:, cols(sa)].mean(1), 1 - D["QQ"][:, cols(sb)].mean(1)
            oppA = D["QQ"][:, cols(sa)].mean(1) * (1 - D["QQ"][:, cols(sa)].mean(1))
            obs = {"spearman_M": spearman(mA, mB), "capture_top20_by_A_M": capture(mA, mB),
                   "capture_top20_by_A_QQ_opportunity": capture(oppA, mB), "spearman_QQ_fail": spearman(qA, qB),
                   "share_tasks_M_zero_on_A": float(np.mean(mA == 0)), "pooled_M_B": float(mB.mean())}
            nul_s, nul_c = [], []
            for _ in range(a.B):
                p = perm_within_domain(rng, dom_idx)
                nul_s.append(spearman(mA, mB[p]))
                nul_c.append(capture(mA, mB[p]))
            obs["p_spearman_M"] = pval(obs["spearman_M"], nul_s)
            obs["p_capture"] = pval(obs["capture_top20_by_A_M"], nul_c)
            obs["null_capture_median"] = float(np.nanmedian(nul_c))
            return obs

        def direction(D, sa, sb):
            gA, gB = D["G"][:, cols(sa)].mean(1), D["G"][:, cols(sb)].mean(1)
            grp = np.sign(gA)
            res = {}
            for nm, g in (("positive", 1), ("negative", -1), ("zero", 0)):
                sel = grp == g
                per_block = D["G"][sel][:, cols(sb)].mean(0) if sel.any() else np.array([])
                t = AD.t_interval(per_block)
                res[nm] = {"n_tasks": int(sel.sum()), "mean_G_on_B_pp": round(100 * float(gB[sel].mean()), 3) if sel.any() else None,
                           "t_ci95_over_B_blocks_pp": [round(100 * t["lo"], 3), round(100 * t["hi"], 3)] if t else None}
            diff = lambda gb, gr: float(gb[gr == 1].mean() - gb[gr == -1].mean()) if (gr == 1).any() and (gr == -1).any() else float("nan")
            obs = diff(gB, grp)
            null = [diff(gB[perm_within_domain(rng, dom_idx)], grp) for _ in range(a.B)]
            nz = (grp != 0) & (np.sign(gB) != 0)
            qA = D["QQ"][:, cols(sa)].mean(1)
            fail, succ = D["QQ"][:, cols(sa)] == 0, D["QQ"][:, cols(sa)] == 1
            rho = D["r"][:, cols(sa)][fail].mean() if fail.any() else 0.0
            delta = D["d"][:, cols(sa)][succ].mean() if succ.any() else 0.0
            pred = rho * (1 - qA) - delta * qA
            order = np.argsort(pred, kind="mergesort")
            pg = np.zeros(len(pred), int)
            pg[order[: len(pred) // 3]] = -1
            pg[order[len(pred) - len(pred) // 3:]] = 1
            fB, sBm = D["QQ"][:, cols(sb)] == 0, D["QQ"][:, cols(sb)] == 1
            rB, dB = D["r"][:, cols(sb)], D["d"][:, cols(sb)]

            def cond_rates(gr, perm=None):
                ix = np.arange(len(gr)) if perm is None else perm
                rf, rs = rB[ix], dB[ix]
                ff, ss = fB[ix], sBm[ix]
                out = {}
                for nm, g in (("positive", 1), ("negative", -1)):
                    sel = gr == g
                    out[f"rescue_given_QQfail_{nm}"] = float(rf[sel][ff[sel]].mean()) if ff[sel].any() else float("nan")
                    out[f"damage_given_QQsucc_{nm}"] = float(rs[sel][ss[sel]].mean()) if ss[sel].any() else float("nan")
                out["rescue_diff_pos_minus_neg"] = out["rescue_given_QQfail_positive"] - out["rescue_given_QQfail_negative"]
                out["damage_diff_neg_minus_pos"] = out["damage_given_QQsucc_negative"] - out["damage_given_QQsucc_positive"]
                return out
            cr = cond_rates(grp)
            nulls = [cond_rates(grp, perm_within_domain(rng, dom_idx)) for _ in range(a.B)]
            cr["p_rescue_diff"] = pval(cr["rescue_diff_pos_minus_neg"], [n["rescue_diff_pos_minus_neg"] for n in nulls])
            cr["p_damage_diff"] = pval(cr["damage_diff_neg_minus_pos"], [n["damage_diff_neg_minus_pos"] for n in nulls])
            res["beyond_opportunity_on_B"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in cr.items()}
            res.update({
                "pos_minus_neg_on_B_pp": round(100 * obs, 3), "p_perm": pval(obs, null),
                "null_median_pp": round(100 * float(np.nanmedian(null)), 3),
                "signed_agreement_incl_ties": float(np.mean(np.sign(gA) == np.sign(gB))),
                "signed_agreement_nonzero_both": float(np.mean(np.sign(gA[nz]) == np.sign(gB[nz]))) if nz.any() else None,
                "opportunity_only": {"rho_rescue_given_QQ_fail_A": float(rho), "delta_damage_given_QQ_success_A": float(delta),
                                     "top_minus_bottom_third_on_B_pp": round(100 * diff(gB, pg), 3),
                                     "spearman_pred_vs_GB": spearman(pred, gB), "spearman_GA_vs_GB": spearman(gA, gB)}})
            return res

        # ---- beyond baseline propensity --------------------------------------------------------------------------
        bflen = None

        def bf_vec(mc, field="succ"):
            bf = np.array([(bfst.get((mc[0], t.split(":")[0], t)) or {}).get(field, np.nan) for t in tasks])
            for k in range(len(doms)):  # impute a missing BF16 rate with its domain mean
                sel = dom_of == k
                if np.isnan(bf[sel]).any():
                    bf[sel & np.isnan(bf)] = np.nanmean(bf[sel]) if np.isfinite(bf[sel]).any() else 0.5
            return bf

        def nuisance(D, ca, cb, bf, spec):
            qA, qB = D["QQ"][:, ca].mean(1), D["QQ"][:, cb].mean(1)
            Zc = [(dom_of == k).astype(float) for k in range(len(doms))] + [qA, qA * (1 - qA)]
            if spec in ("AB", "ABL"):
                Zc += [qB, qB * (1 - qB)]
            Zc.append(bf)
            if spec == "ABL":
                Zc.append(bflen)
            return np.column_stack(Zc), qB

        def beyond(D, mc, sa, sb, key, spec):
            nonlocal bflen
            ca, cb = cols(sa), cols(sb)
            yA, yB = D[key][:, ca].mean(1), D[key][:, cb].mean(1)
            bf = bf_vec(mc)
            bflen = bf_vec(mc, "len")
            Z, qB = nuisance(D, ca, cb, bf, spec)
            X = np.column_stack([Z, yA])
            ols = OLS(X)
            b0, t0_, tcl = ols.fit(yB)
            # Freedman-Lane: residuals of the nuisance-only model, permuted within domain
            fit0 = Z @ (np.linalg.pinv(Z) @ yB)
            e0 = yB - fit0
            perms = np.stack([perm_within_domain(rng, dom_idx) for _ in range(a.B)], axis=1)  # (T, B)
            _, t_fl, _ = ols.fit(fit0[:, None] + e0[perms])
            signs = rng.choice([-1.0, 1.0], size=(T, a.B))
            _, t_wild, _ = ols.fit(fit0[:, None] + e0[:, None] * signs)
            ok = lambda v: v[np.isfinite(v)]
            # block-aware bootstrap: blocks resampled within A and within B independently; everything recomputed
            bb, bp = [], []
            for _ in range(a.B_boot):
                ra = [ca[i] for i in rng.integers(0, len(ca), len(ca))]
                rb = [cb[i] for i in rng.integers(0, len(cb), len(cb))]
                ya, yb = D[key][:, ra].mean(1), D[key][:, rb].mean(1)
                Zb, _ = nuisance(D, ra, rb, bf, spec)
                bb.append(float((np.linalg.pinv(np.column_stack([Zb, ya])) @ yb)[-1]))
                bp.append(pcorr(Zb, ya, yb))
            bb, bp = np.array(bb), np.array(bp)
            # delete-one-block jackknife within A and within B (independent splits: variances add). Preferred block-aware
            # interval: the with-replacement bootstrap duplicates blocks, which adds noise to the regressor yA and
            # attenuates beta_A (errors in variables), so its percentile interval is shifted towards 0.
            def refit(ra, rb):
                ya, yb = D[key][:, ra].mean(1), D[key][:, rb].mean(1)
                Zj, _ = nuisance(D, ra, rb, bf, spec)
                return float((np.linalg.pinv(np.column_stack([Zj, ya])) @ yb)[-1]), pcorr(Zj, ya, yb)
            jk = {}
            for side, cs in (("A", ca), ("B", cb)):
                vals = np.array([refit([c for c in ca if c != x] if side == "A" else ca, [c for c in cb if c != x] if side == "B" else cb) for x in cs])
                nj = len(cs)
                jk[side] = ((nj - 1) / nj * ((vals - vals.mean(0)) ** 2).sum(0))
            se_b, se_r = np.sqrt(jk["A"][0] + jk["B"][0]), np.sqrt(jk["A"][1] + jk["B"][1])
            from scipy.stats import t as tdist
            qt = float(tdist.ppf(0.975, min(len(ca), len(cb)) - 1))
            pc0 = pcorr(Z, yA, yB)
            # exchangeability diagnostics of the nuisance-model residuals
            from scipy.stats import spearmanr
            opp = qB * (1 - qB)
            sd_dom = {d: round(float(e0[dom_of == k].std(ddof=1)), 4) for k, d in enumerate(doms) if (dom_of == k).sum() > 1}
            rho_opp = spearmanr(np.abs(e0), opp) if np.std(opp) > 0 else None
            rho_fit = spearmanr(np.abs(e0), fit0) if np.std(fit0) > 0 else None
            return {"beta_A": round(b0, 4), "t_hc3": round(t0_, 3), "t_classical": round(tcl, 3),
                    "partial_corr_A_descriptive": round(pcorr(Z, yA, yB), 4),
                    "p_FL_one_sided": pval(t0_, ok(t_fl)), "p_FL_two_sided": pval(abs(t0_), np.abs(ok(t_fl))),
                    "p_wild_one_sided": pval(t0_, ok(t_wild)), "p_wild_two_sided": pval(abs(t0_), np.abs(ok(t_wild))),
                    "block_jackknife_se_beta_A": round(float(se_b), 4),
                    "block_jackknife_ci95_beta_A": [round(b0 - qt * float(se_b), 4), round(b0 + qt * float(se_b), 4)],
                    "block_jackknife_ci95_partial_corr": [round(pc0 - qt * float(se_r), 4), round(pc0 + qt * float(se_r), 4)],
                    "block_jackknife_note": f"delete-one-block within A and B, SE^2 = SE_A^2 + SE_B^2, t quantile df = {min(len(ca), len(cb)) - 1}",
                    "block_boot_ci95_beta_A_attenuated": [round(float(x), 4) for x in np.nanpercentile(bb, [2.5, 97.5])],
                    "block_boot_ci95_partial_corr_attenuated": [round(float(x), 4) for x in np.nanpercentile(bp, [2.5, 97.5])],
                    "exchangeability": {"spearman_abs_resid_vs_flip_opportunity_B": [round(float(rho_opp[0]), 3), round(float(rho_opp[1]), 4)] if rho_opp is not None else None,
                                        "spearman_abs_resid_vs_nuisance_fit": [round(float(rho_fit[0]), 3), round(float(rho_fit[1]), 4)] if rho_fit is not None else None,
                                        "resid_sd_by_domain": sd_dom},
                    "n_tasks": T, "n_blocks_A": len(ca), "n_blocks_B": len(cb), "nuisance_spec": spec,
                    "n_tasks_bf16_imputed": int(sum(1 for t in tasks if (bfst.get((mc[0], t.split(':')[0], t)) or {}).get("succ") is None))}

        def legacy_v1(D, mc, sa, sb, key):
            """v1's statistic and reference exactly (raw B rates permuted within domain, covariates fixed): reproduction
            and comparison only; NOT a valid conditional test."""
            yA, yB = D[key][:, cols(sa)].mean(1), D[key][:, cols(sb)].mean(1)
            q = D["QQ"][:, cols(sa)].mean(1)
            bf = np.array([(bfst.get((mc[0], t.split(":")[0], t)) or {}).get("succ", np.nan) for t in tasks])
            Z = np.column_stack([np.ones(len(q)), q, q * (1 - q), np.nan_to_num(bf, nan=np.nanmean(bf))])
            X = np.column_stack([Z, yA])
            P = np.linalg.pinv(X)
            b0 = float((P @ yB)[-1])
            nb = [float((P @ yB[perm_within_domain(rng, dom_idx)])[-1]) for _ in range(a.B)]
            return {"beta_A": round(b0, 4), "partial_corr_A": round(pcorr(Z, yA, yB), 4), "p_beta_raw_perm": pval(b0, nb)}

        res = {"label": P["label"], "n_tasks": T, "n_blocks": K, "blocks": blocks, "excluded_blocks": P["excluded_blocks"],
               "domains": {d: len(v) for d, v in dom_idx.items()}, "frozen_split": {"salt": SALT, "A": A0, "B": B0},
               "units_per_cell": T * K, "units_digest_sha256_by_cell": pop_digest, "cells": {}}
        legacy = P.get("legacy")
        extra = [hsplit(blocks, f"{SALT}s{k}|") for k in range(a.n_splits)]
        for mc in present:
            D = data[mc]
            lab = f"{mc[0]}:{mc[1]}"
            r = {}
            if not legacy:
                r["concentration"] = {"A->B": concentration(D, A0, B0), "B->A": concentration(D, B0, A0)}
                r["direction"] = {"A->B": direction(D, A0, B0), "B->A": direction(D, B0, A0)}
            r["beyond_baselines"] = {key: {d: {"AB": beyond(D, mc, sa, sb, key, "AB"), "A": beyond(D, mc, sa, sb, key, "A"),
                                               "ABL": beyond(D, mc, sa, sb, key, "ABL"),
                                               "legacy_v1": legacy_v1(D, mc, sa, sb, key)}
                                           for d, (sa, sb) in (("A->B", (A0, B0)), ("B->A", (B0, A0)))}
                                     for key in ("M", "G")}
            if not legacy:
                sens = []
                for sa, sb in extra:
                    gA, gB = D["G"][:, cols(sa)].mean(1), D["G"][:, cols(sb)].mean(1)
                    gr = np.sign(gA)
                    sens.append(float(gB[gr == 1].mean() - gB[gr == -1].mean()) if (gr == 1).any() and (gr == -1).any() else np.nan)
                r["direction_sensitivity_50_splits_pos_minus_neg_pp"] = {
                    "median": round(100 * float(np.nanmedian(sens)), 3),
                    "q10_q90": [round(100 * float(np.nanquantile(sens, q)), 3) for q in (0.1, 0.9)],
                    "share_positive": float(np.nanmean(np.array(sens) > 0))}
                het = {}
                for key in ("G", "M"):
                    g = D[key]
                    gb = g.mean(0)
                    vals = [float((g[:, b] * g[:, c]).mean() - gb[b] * gb[c]) for b, c in combinations(range(K), 2)]
                    het[key] = {"stable_task_variance": float(np.mean(vals)), "total_task_variance_pooled": float(g.mean(1).var())}
                r["task_heterogeneity_diagnostic"] = het
            res["cells"][lab] = r
        # summary counts over the 12 cell-directions
        summ = {}
        for key in ("M", "G"):
            for spec in ("AB", "A", "ABL"):
                for pk in ("p_FL_one_sided", "p_wild_one_sided"):
                    ps = [res["cells"][c]["beyond_baselines"][key][d][spec][pk] for c in res["cells"] for d in ("A->B", "B->A")]
                    summ[f"{key}|{spec}|{pk}"] = {"n_p_lt_05": int(sum(p < 0.05 for p in ps)), "n_holm_05": int(sum(holm(ps))), "of": len(ps)}
            ps = [res["cells"][c]["beyond_baselines"][key][d]["legacy_v1"]["p_beta_raw_perm"] for c in res["cells"] for d in ("A->B", "B->A")]
            summ[f"{key}|legacy_v1|p_beta_raw_perm"] = {"n_p_lt_05": int(sum(p < 0.05 for p in ps)), "n_holm_05": int(sum(holm(ps))), "of": len(ps)}
        res["beyond_baselines_summary"] = summ
        if not legacy and len(P["domains"]) == 2:
            res["overlap"] = overlap(data, rng, dom_idx, K, a.B)
        return res

    out = {"version": "v2 (W78)", "label": "INTERNAL REPLICATION (development outcomes already viewed, W67); not confirmation",
           "snapshot": {"id": sid, "path": str(Path(a.snapshot).resolve()), "sha256": AD.sha256(a.snapshot)},
           "split": split_info, "exclude_blocks_sensitivity": a.exclude_blocks, "cells": [f"{m}:{c}" for m, c in present], "B": a.B, "B_boot": a.B_boot, "seed": AD.SEED,
           "primary": {"population": "panel85", "test": "Freedman-Lane, residuals of the nuisance-only model permuted within domain, HC3 t of beta_A, one-sided",
                       "nuisance": "AB: domain intercepts + q_A, q_A(1-q_A), q_B, q_B(1-q_B), BF16 task success"},
           "populations": {}}
    for name, P in pops.items():
        out["populations"][name] = run_population(name, P)
    out["seconds"] = round(time.time() - t0, 1)
    out["provenance"] = {
        "script_sha256": AD.sha256(__file__), "analyze_dev_sha256": AD.sha256(AD.__file__), "analyze_difficulty_sha256": AD.sha256(ADF.__file__),
        "splits_manifest_sha256": AD.sha256(AD.SPLITS), "n_input_files": len(files),
        "input_files_digest_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "analysis_commit": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
        "worktree_dirty_script": bool(subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "--", "analysis/fork/audit_w67.py", "analysis/fork/analyze_dev.py"]).returncode)}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    tag = ("_excl_" + "_".join(sorted(a.exclude_blocks))) if a.exclude_blocks else ""
    jp = OUT / f"direction_replication_v2_{sid}{tag}_{utc}.json"
    jp.write_text(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    mp = OUT / f"w67_audit_v2_{sid}{tag}_{utc}.md"
    mp.write_text(markdown(out, jp))
    print(f"audit_w67: wrote {jp.name} and {mp.name} ({out['seconds']} s)")


def overlap(data, rng, dom_idx, K, B) -> dict:
    res = {}
    for c1, c2 in PAIRS:
        if c1 not in data or c2 not in data:
            continue
        m1, m2 = data[c1]["M"], data[c2]["M"]

        def phi(x, y):
            x, y = x.ravel(), y.ravel()
            return float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else float("nan")
        obs = phi(m1, m2)
        null_task = [phi(m1, m2[perm_within_domain(rng, dom_idx)]) for _ in range(B)]
        null_block = [phi(m1, m2[:, rng.permutation(K)]) for _ in range(B)]
        both = (m1 == 1) & (m2 == 1)
        g1, g2 = data[c1]["G"], data[c2]["G"]
        res[f"{c1[0]}:{c1[1]} vs {c2[0]}:{c2[1]}"] = {
            "phi_M": round(obs, 4), "n_units": int(m1.size), "both_flip": int(both.sum()),
            "task_identity_null": {"p": pval(obs, null_task), "median": round(float(np.nanmedian(null_task)), 4),
                                   "q95": round(float(np.nanquantile(null_task, 0.95)), 4)},
            "nonce_alignment_null": {"p": pval(obs, null_block), "median": round(float(np.nanmedian(null_block)), 4),
                                     "q95": round(float(np.nanquantile(null_block, 0.95)), 4)},
            "same_direction_share_when_both_flip": float(np.mean(np.sign(g1[both]) == np.sign(g2[both]))) if both.any() else None,
            "interpretation": "task/block co-susceptibility; not same-state (histories differ across cells)"}
    return res


def markdown(o: dict, jp: Path) -> str:
    P = o["populations"]
    p85 = P["panel85"]
    s85, sleg = p85["beyond_baselines_summary"], P["legacy_airline27_x20"]["beyond_baselines_summary"]

    def cnt(s, k):
        return f"{s[k]['n_p_lt_05']}/{s[k]['of']} (Holm {s[k]['n_holm_05']})"
    L = [f"**TL;DR** W67 audit v2 (W78). Primary population: {p85['n_tasks']} tasks ({p85['domains']}) x {p85['n_blocks']} complete "
         f"85-task blocks per cell (excluded block(s): {p85['excluded_blocks'] or 'none'}). Beyond-baseline test (Freedman-Lane, "
         f"within-domain residual permutation, HC3 t, nuisance AB): A rate predicts B rate at p < 0.05 for M in "
         f"{cnt(s85, 'M|AB|p_FL_one_sided')} and for G in {cnt(s85, 'G|AB|p_FL_one_sided')} cell-directions. The v1 headline "
         f"(11/12 and 11/12) was the airline-only {P['legacy_airline27_x20']['n_tasks']}-task x {P['legacy_airline27_x20']['n_blocks']}-block "
         f"population with an invalid raw-outcome permutation (legacy reproduced here: M {cnt(sleg, 'M|legacy_v1|p_beta_raw_perm')}, "
         f"G {cnt(sleg, 'G|legacy_v1|p_beta_raw_perm')}).", "",
         f"# W67 audit v2 ({o['snapshot']['id']}){' SENSITIVITY: blocks ' + str(o['exclude_blocks_sensitivity']) + ' dropped' if o.get('exclude_blocks_sensitivity') else ''}", "",
         f"Full numbers `{jp.relative_to(ROOT)}`. Snapshot sha {o['snapshot']['sha256'][:12]}; script sha "
         f"{o['provenance']['script_sha256'][:12]}; analyze_dev sha {o['provenance']['analyze_dev_sha256'][:12]}; input files "
         f"{o['provenance']['n_input_files']} (digest {o['provenance']['input_files_digest_sha256'][:12]}). B = {o['B']} "
         f"(permutation / wild), {o['B_boot']} (block bootstrap). Monte Carlo p = (1 + #extreme)/(B + 1). INTERNAL REPLICATION ONLY.", "",
         "## Populations (task and block counts)", "", "| population | tasks (by domain) | blocks | split A / B | excluded blocks | role |",
         "|---|---|---|---|---|---|"]
    for k, v in P.items():
        L.append(f"| {k} | {v['n_tasks']} {v['domains']} | {v['n_blocks']} | {len(v['frozen_split']['A'])} / {len(v['frozen_split']['B'])} | "
                 f"{v['excluded_blocks'] or 'none'} | {v['label']} |")
    L += ["", "## Beyond baseline propensity: B task rate ~ nuisance + A task rate", "",
          "Primary: Freedman-Lane (nuisance-model residuals permuted within domain), statistic = HC3 t of beta_A, one-sided; "
          "wild = restricted Rademacher wild bootstrap of the same residuals (heteroscedasticity-robust check); block-jackknife = "
          "delete-one-block within A and within B, everything recomputed (the with-replacement block bootstrap is in the JSON, labelled "
          "attenuated: duplicated blocks add noise to the regressor). Partial r is descriptive. 'v1 p' = the old raw-outcome "
          "permutation (invalid; comparison only).", ""]
    for name in ("panel85", "retail58", "airline27", "legacy_airline27_x20"):
        v = P[name]
        s = v["beyond_baselines_summary"]
        L += [f"### {name}: {v['n_tasks']} tasks {v['domains']} x {v['n_blocks']} blocks (A {len(v['frozen_split']['A'])}, B {len(v['frozen_split']['B'])})", "",
              f"Counts p < 0.05 (Holm) over 12 cell-directions: M AB-FL {cnt(s, 'M|AB|p_FL_one_sided')}, AB-wild {cnt(s, 'M|AB|p_wild_one_sided')}, "
              f"A-FL {cnt(s, 'M|A|p_FL_one_sided')}, ABL-FL {cnt(s, 'M|ABL|p_FL_one_sided')}, v1 {cnt(s, 'M|legacy_v1|p_beta_raw_perm')}; G AB-FL {cnt(s, 'G|AB|p_FL_one_sided')}, "
              f"AB-wild {cnt(s, 'G|AB|p_wild_one_sided')}, A-FL {cnt(s, 'G|A|p_FL_one_sided')}, ABL-FL {cnt(s, 'G|ABL|p_FL_one_sided')}, v1 {cnt(s, 'G|legacy_v1|p_beta_raw_perm')}.", "",
              "| cell | dir | key | beta_A AB [block-jackknife 95%] | p FL AB | p wild AB | partial r AB | p FL A-spec | v1 beta (v1 p) |",
              "|---|---|---|---|---|---|---|---|---|"]
        for c, r in v["cells"].items():
            for key in ("M", "G"):
                for d in ("A->B", "B->A"):
                    x = r["beyond_baselines"][key][d]
                    ab, aa, lg = x["AB"], x["A"], x["legacy_v1"]
                    L.append(f"| {c} | {d} | {key} | {ab['beta_A']:+.3f} [{ab['block_jackknife_ci95_beta_A'][0]:+.2f}, {ab['block_jackknife_ci95_beta_A'][1]:+.2f}] | "
                             f"{ab['p_FL_one_sided']:.4f} | {ab['p_wild_one_sided']:.4f} | {ab['partial_corr_A_descriptive']:+.3f} | "
                             f"{aa['p_FL_one_sided']:.4f} | {lg['beta_A']:+.3f} ({lg['p_beta_raw_perm']:.4f}) |")
        L.append("")
    L += ["### Exchangeability diagnostics (panel85, nuisance AB, A->B): Spearman |residual| vs B flip opportunity and vs fitted; residual SD by domain", ""]
    for c, r in p85["cells"].items():
        for key in ("M", "G"):
            e = r["beyond_baselines"][key]["A->B"]["AB"]["exchangeability"]
            L.append(f"- {c} {key}: |e|~opp {e['spearman_abs_resid_vs_flip_opportunity_B']}, |e|~fit {e['spearman_abs_resid_vs_nuisance_fit']}, SD {e['resid_sd_by_domain']}")
    for name in ("panel85", "retail58", "airline27"):
        v = P[name]
        L += ["", f"## Concentration ({name}: {v['n_tasks']} tasks x {v['n_blocks']} blocks; whole task vectors permuted within domain)", "",
              "| cell | dir | Spearman M (p) | capture top 20% by A-M (null median) | capture by QQ opportunity | Spearman QQ fail |", "|---|---|---|---|---|---|"]
        for k, c0 in v["cells"].items():
            for d, c in c0["concentration"].items():
                L.append(f"| {k} | {d} | {c['spearman_M']:.2f} ({c['p_spearman_M']:.4f}) | {c['capture_top20_by_A_M']:.2f} ({c['null_capture_median']:.2f}) | "
                         f"{c['capture_top20_by_A_QQ_opportunity']:.2f} | {c['spearman_QQ_fail']:.2f} |")
        L += ["", f"## Direction ({name}: {v['n_tasks']} tasks x {v['n_blocks']} blocks): A-defined sign groups, mean G on B (pp)", "",
              "| cell | dir | positive (n) | negative (n) | pos − neg (perm p) | opportunity-only top−bottom third | 50 splits: median pos−neg [q10, q90] | rescue|fail pos vs neg (p) | damage|success neg vs pos (p) |",
              "|---|---|---|---|---|---|---|---|---|"]
        for k, c0 in v["cells"].items():
            s = c0["direction_sensitivity_50_splits_pos_minus_neg_pp"]
            for d, r in c0["direction"].items():
                b = r["beyond_opportunity_on_B"]
                L.append(f"| {k} | {d} | {r['positive']['mean_G_on_B_pp']} ({r['positive']['n_tasks']}) | {r['negative']['mean_G_on_B_pp']} ({r['negative']['n_tasks']}) | "
                         f"{r['pos_minus_neg_on_B_pp']} ({r['p_perm']:.4f}) | {r['opportunity_only']['top_minus_bottom_third_on_B_pp']} | "
                         f"{s['median']} {s['q10_q90']} | {b['rescue_given_QQfail_positive']:.3f} vs {b['rescue_given_QQfail_negative']:.3f} ({b['p_rescue_diff']:.4f}) | "
                         f"{b['damage_given_QQsucc_negative']:.3f} vs {b['damage_given_QQsucc_positive']:.3f} ({b['p_damage_diff']:.4f}) |")
    L += ["", f"## Cross-quantizer co-susceptibility (panel85: {p85['n_tasks']} tasks x {p85['n_blocks']} blocks; task/block level, not same-state)", "",
          "| pair | units | phi(M) | task-identity null p (q95) | nonce-alignment null p (q95) | same direction when both flip (n) |", "|---|---|---|---|---|---|"]
    for k, v in p85.get("overlap", {}).items():
        L.append(f"| {k} | {v['n_units']} | {v['phi_M']} | {v['task_identity_null']['p']:.4f} ({v['task_identity_null']['q95']}) | "
                 f"{v['nonce_alignment_null']['p']:.4f} ({v['nonce_alignment_null']['q95']}) | {v['same_direction_share_when_both_flip']} ({v['both_flip']}) |")
    L += ["", f"## Task-heterogeneity diagnostic (panel85: {p85['n_tasks']} x {p85['n_blocks']}; stable task variance; negative kept)", ""]
    for k, v in p85["cells"].items():
        h = v["task_heterogeneity_diagnostic"]
        L.append(f"- {k}: G {h['G']['stable_task_variance']:.4f} (of total {h['G']['total_task_variance_pooled']:.4f}); "
                 f"M {h['M']['stable_task_variance']:.4f} (of total {h['M']['total_task_variance_pooled']:.4f})")
    L += ["", "Note: the frequency of I != 0 on divergent states (about 15-30%) is not a significant mean I; the mean I intervals of "
          "the W4 cells cover 0 (consequence_estimands, W68).", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
