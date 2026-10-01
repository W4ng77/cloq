"""Confirmatory analysis of the telecom holdout forks, implementing docs/insights/PREREG_FORK_CONFIRM.md exactly (W86).

Refuses `--split holdout` unless analyze_dev.split_guard passes, i.e. the prereg's sha256 equals
manifests/fork/splits_v1.json splits.holdout.prereg_sha256 (the guard runs before any holdout file is opened). It also
refuses to run if manifests/fork/holdout_cutpoints_v1.json does not have the sha256 frozen below (= prereg §9).

`--dry-run-dev` runs the identical pipeline on telecom DEV data (analysis/fork/telecom, blocks f01-f06, relabelled as a
pseudo-holdout; split guard "dev", which aborts on any holdout unit). Its output is labelled DRY RUN ON DEV, is
exploratory, and exists only to prove that the code executes end to end. Differences forced by the dev data: K = 6
(halves 3 + 3 by the same hash rule), 80 tasks, and no q4 telecom forks exist, so the q4 cell is absent and the
weights of the present cells are renormalised (labelled in the output).

Pipeline (prereg section in brackets):
  load fork units (analyze_dev.load_dir: snapshot admission, trajectory sha, branch files)      [§4, §12]
  classify missing units: structural (B prompt-id mismatch at search, decision/trajectory count mismatch, QQ no-op
    mismatch still present at analysis time) vs infrastructure (everything else)                [§4.2-4.3]
  structural: task excluded from that cell in all blocks; kept and reported, flagged if > 3     [§4.3]
  block completeness per (cell, block); incomplete primary blocks replaced by complete reserves
    h13, h14 in order (inheriting the half); otherwise dropped (K' < 12); K' < 8 -> decision readings not estimable [§4.4-4.5]
  unit effects G, r, d, M (no-divergence = 0); cell-weighted task x block matrix Z               [§5]
  primary G_all: crossed task x block interval (two-way random-effects ANOVA moments, normal) DECIDES; t over the K'
    block means alongside; readings at +-3 pp, +-5 pp sensitivity                               [§6]
  S1: r > 0 and d > 0, each by the crossed one-sided 95% lower bound (intersection-union)       [§7]
  S2: cross-half repeatability rho (Spearman per cell, weighted mean over estimable cells, persona-stratified
    permutation, 10,000 draws, seed 20261001; constant vector -> cell not estimable; no outcome screen) [§8]
  strata: six families, G per level by the crossed interval, two-sided p, Holm within family; r/d/M descriptive [§9]

usage: python analysis/fork/analyze_holdout_confirm.py --snapshot <SNAP> --split holdout [--complete-case]
       python analysis/fork/analyze_holdout_confirm.py --dry-run-dev [--snapshot <SNAP>]
-> analysis/fork/out/holdout_confirm_<UTC>.{json,md}  |  analysis/fork/out/holdout_confirm_DRYRUN_DEV_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402
from make_holdout_cutpoints import bf16_task_stats, issue_type, n_faults  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
PREREG = "docs/insights/PREREG_FORK_CONFIRM.md"
CUTPOINTS = ROOT / "manifests/fork/holdout_cutpoints_v1.json"
CUTPOINTS_SHA256 = "ab46abe91960f6c2cb1b228ffa7ada8128d4018f21be80ef017d1a95429d32de"  # = prereg §9
# prereg §2: weights 1/2 per model; q4 cell 1/2, each q8 cell 1/4
CELLS = (("q4", "gptq_w4_d1", 0.5), ("q8", "gptq_w4_d1", 0.25), ("q8", "awq_w4", 0.25))
# prereg §3
PRIMARY_BLOCKS = tuple(f"h{k:02d}" for k in range(1, 13))
RESERVE_BLOCKS = ("h13", "h14")
DEV_BLOCKS = ("f01", "f02", "f03", "f04", "f05", "f06")
NONCE_SALT, SPLIT_SALT = "cloq-fork-holdout-v1|", "holdout-split-v1|"
MIN_K_DECISION = 8        # §4.5
MIN_BLOCKS_PER_HALF = 3   # §4.5 / §8
G_MIN, G_SENS = 0.03, 0.05
Z90 = float(stats.norm.ppf(0.95))  # 90% two-sided / one-sided 95%
N_PERM, PERM_SEED = 10_000, 20261001
ALPHA = 0.05
STRUCTURAL = ("search: B prompt ids differ", "search: decision/trajectory count mismatch", "QQ no-op mismatch")
PERSONA_RE = re.compile(r"PERSONA:(\w+)")
STATS4 = ("G", "rescue", "damage", "M")


def half_of(blocks: list[str]) -> dict:
    """§3: H_A = first len/2 block ids in ascending sha256('holdout-split-v1|' + id) order; H_B = the rest."""
    order = sorted(blocks, key=lambda b: hashlib.sha256(f"{SPLIT_SALT}{b}".encode()).hexdigest())
    return {b: ("A" if i < len(order) // 2 else "B") for i, b in enumerate(order)}


def persona(tid: str) -> str:
    m = PERSONA_RE.search(tid)
    return m.group(1) if m else "None"


def classify(reason: str) -> str:
    return "structural" if reason.startswith(STRUCTURAL) else "infrastructure"


# ------------------------------------------------------------------------------------------------------------ loading
def load(snap: dict, root: str, split: str, cells, blocks_all) -> tuple[list[dict], dict]:
    dirs = [d for d in AD.discover(False) if str(d.relative_to(ROOT)).startswith(root + "/")]
    cache: dict = {}
    loaded = [AD.load_dir(d, snap, cache) for d in dirs]
    units = [u for L in loaded for u in L["units"]]
    guard = AD.split_guard(units, split, "analyze_holdout_confirm")
    # §4.3: a QQ no-op mismatch is unit-level (no whole-directory quarantine); at analysis time it is structural
    bad_noop = {(L["dir"], x["state_id"]) for L in loaded for x in L["noop"] if not x["ok"]}
    for u in units:
        if "excluded" not in u and u.get("div") and (u["dir"], u.get("state_id")) in bad_noop:
            u["excluded"] = "QQ no-op mismatch (persisting at analysis time)"
    units, ndup = AD.dedupe_units(units)
    keep = {(m, c) for m, c, _ in cells}
    units = [u for u in units if u["domain"] == "telecom" and (u["model"], u["cell"]) in keep and u["block"] in blocks_all
             and not u.get("excluded", "").startswith("not in split")]
    files = {k: v for L in loaded for k, v in L["files"].items()}
    prov = {"split_guard": guard, "input_dirs": [L["dir"] for L in loaded], "duplicates_dropped": ndup,
            "noop_sample": {"n": sum(len(L["noop"]) for L in loaded), "n_fail": len(bad_noop)},
            "n_input_files": len(files), "input_files_digest_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
    return units, prov


# --------------------------------------------------------------------------------------------------------- inference
def crossed(Z: np.ndarray) -> dict | None:
    """Grand mean of a complete J x K matrix and its crossed task x block standard error (two-way random effects without
    replication, ANOVA moments, negative components truncated at 0):
      Var = (MS_E + max(MS_T - MS_E, 0) + max(MS_B - MS_E, 0)) / (J K)."""
    J, K = Z.shape
    if J < 2 or K < 2:
        return None
    m = Z.mean()
    rt, cb = Z.mean(1), Z.mean(0)
    msT = K * np.sum((rt - m) ** 2) / (J - 1)
    msB = J * np.sum((cb - m) ** 2) / (K - 1)
    msE = np.sum((Z - rt[:, None] - cb[None, :] + m) ** 2) / ((J - 1) * (K - 1))
    se = float(np.sqrt((msE + max(msT - msE, 0.0) + max(msB - msE, 0.0)) / (J * K)))
    return {"est": float(m), "se": se, "ci90": [float(m - Z90 * se), float(m + Z90 * se)], "lb95_one_sided": float(m - Z90 * se),
            "components": {"MS_T": float(msT), "MS_B": float(msB), "MS_E": float(msE)}, "J": J, "K": K}


def block_t(bm: np.ndarray) -> dict | None:
    bm = np.asarray(bm, float)
    K = len(bm)
    if K < 2:
        return None
    m, se = bm.mean(), bm.std(ddof=1) / np.sqrt(K)
    q = stats.t.ppf(0.95, K - 1)
    return {"est": float(m), "se": float(se), "ci90": [float(m - q * se), float(m + q * se)], "lb95_one_sided": float(m - q * se),
            "df": K - 1, "block_means": [float(x) for x in bm]}


def pp(d: dict | None) -> dict | None:
    if d is None:
        return None
    o = {k: (round(100 * v, 3) if isinstance(v, float) else v) for k, v in d.items() if k not in ("components", "block_means")}
    o["ci90"] = [round(100 * x, 3) for x in d["ci90"]]
    if "block_means" in d:
        o["block_means"] = [round(100 * x, 2) for x in d["block_means"]]
    return o


def readings(cr: dict | None, k_used: int) -> dict:
    """§6: on the crossed 90% interval [L, U] (one-sided 95% LB = L)."""
    if cr is None or not np.isfinite(cr["se"]):
        return {"estimable": False, "reading": "not estimable"}
    L, U = cr["ci90"]
    r = {"estimable": k_used >= MIN_K_DECISION, "L_pp": round(100 * L, 3), "U_pp": round(100 * U, 3),
         "positive_gain": bool(L > 0), "gain_above_3pp": bool(L > G_MIN), "small_average_effect_pm3pp": bool(-G_MIN < L and U < G_MIN),
         "sensitivity_5pp": {"gain_above_5pp": bool(L > G_SENS), "small_average_effect_pm5pp": bool(-G_SENS < L and U < G_SENS)}}
    r["reading"] = ("gain above 3 pp" if r["gain_above_3pp"] else "positive gain" if r["positive_gain"]
                    else "small average effect (inside ±3 pp)" if r["small_average_effect_pm3pp"] else "inconclusive")
    if not r["estimable"]:
        r["reading"] = f"not estimable for the decision rules (K' = {k_used} < {MIN_K_DECISION}); computed values descriptive only"
    return r


def holm(ps: list[float]) -> list[float]:
    m = len(ps)
    order = np.argsort(ps, kind="stable")
    adj = np.empty(m)
    run = 0.0
    for i, j in enumerate(order):
        run = max(run, min(1.0, (m - i) * ps[j]))
        adj[j] = run
    return [float(x) for x in adj]


# --------------------------------------------------------------------------------------------------------- main body
class Matrix:
    """Per-cell task x block arrays over the fixed task list and the used blocks; NaN = not available."""

    def __init__(self, tasks, blocks, units, cells):
        self.tasks, self.blocks = tasks, blocks
        self.ti = {t: i for i, t in enumerate(tasks)}
        self.bi = {b: i for i, b in enumerate(blocks)}
        J, K = len(tasks), len(blocks)
        self.X = {(m, c): {s: np.full((J, K), np.nan) for s in STATS4 + ("div", "steps_left")} for m, c, _ in cells}
        for u in units:
            if "excluded" in u or u["block"] not in self.bi:
                continue
            e = AD.effects(u["Y"], u["div"])
            j, k = self.ti[u["task"]], self.bi[u["block"]]
            A = self.X[(u["model"], u["cell"])]
            for s in STATS4:
                A[s][j, k] = e[s]
            A["div"][j, k] = 1.0 if u["div"] else 0.0
            A["steps_left"][j, k] = u["steps_left"] if u["div"] else np.nan

    def Z(self, stat: str, cells_w: dict, task_mask=None, unit_mask=None) -> np.ndarray | None:
        """§5: Z[j,b] = sum_c w_c (J_S / n_{c,b,S}) X_c[j,b] 1[j available in (c,b) and in S] over the task subset S
        (task_mask), with unit_mask zeroing units outside a unit-level stratum (contribution form). The mean over j of
        Z[., b] is G_all,b of the subset; None if some cell has no available task of S in some block."""
        J, K = len(self.tasks), len(self.blocks)
        S = np.ones(J, bool) if task_mask is None else task_mask
        Z = np.zeros((int(S.sum()), K))
        for mc, w in cells_w.items():
            X = self.X[mc][stat][S]
            avail = np.isfinite(X)
            n = avail.sum(0)
            if (n == 0).any():
                return None
            V = np.where(avail, X, 0.0)
            if unit_mask is not None:
                V = V * unit_mask[mc][S]
            Z += w * (S.sum() / n)[None, :] * V
        return Z


def estimate(Mx: Matrix, stat: str, cells_w: dict, task_mask=None, unit_mask=None) -> dict:
    Z = Mx.Z(stat, cells_w, task_mask, unit_mask)
    if Z is None:
        return {"estimable": False, "why": "a cell has no available task in this subset in some block"}
    cr, bt = crossed(Z), block_t(Z.mean(0))
    return {"estimable": cr is not None, "crossed_decisional": cr, "block_t": bt, "J": int(Z.shape[0]), "K": int(Z.shape[1])}


def repeatability(Mx: Matrix, cells_w: dict, halves: dict, n_perm: int = N_PERM) -> dict:
    """§8. Per cell: m_A, m_B = share of the half's blocks in which the unit is consequential (M = 1), over the cell's
    included tasks; rho_c = Spearman (average ranks); not estimable iff m_A or m_B is constant. rho = sum of w_c rho_c over
    estimable cells, weights renormalised over them. Permutation: per draw r, keys U[r, j] ~ iid U(0, 1) over the full
    sorted task list (rng default_rng(20261001), U = rng.random((n_perm, J))); within each persona, a cell's included
    tasks (in task-id order) receive the m_B of the same tasks re-ordered by key (identical permutation across cells when
    no task is excluded). p = (1 + #{rho* >= rho}) / (1 + n_perm)."""
    hA = [Mx.bi[b] for b in Mx.blocks if halves[b] == "A"]
    hB = [Mx.bi[b] for b in Mx.blocks if halves[b] == "B"]
    out = {"blocks_A": [b for b in Mx.blocks if halves[b] == "A"], "blocks_B": [b for b in Mx.blocks if halves[b] == "B"]}
    if min(len(hA), len(hB)) < MIN_BLOCKS_PER_HALF:
        return {**out, "estimable": False, "why": f"fewer than {MIN_BLOCKS_PER_HALF} complete blocks in a half"}
    pers = np.array([persona(t) for t in Mx.tasks])
    rng = np.random.default_rng(PERM_SEED)
    U = rng.random((n_perm, len(Mx.tasks)))
    per, obs, perm_rho, wts = {}, [], [], []
    for mc, w in cells_w.items():
        M = Mx.X[mc]["M"]
        inc = np.where(np.isfinite(M[:, hA]).all(1) & np.isfinite(M[:, hB]).all(1))[0]
        mA, mB = M[inc][:, hA].mean(1), M[inc][:, hB].mean(1)
        key = f"{mc[0]}:{mc[1]}"
        info = {"n_tasks": int(len(inc)), "levels_A": sorted({round(float(x), 4) for x in mA}),
                "levels_B": sorted({round(float(x), 4) for x in mB}), "tasks_with_mA_plus_mB_gt_0": int(np.sum(mA + mB > 0))}
        if len(inc) < 3 or np.ptp(mA) == 0 or np.ptp(mB) == 0:
            per[key] = {**info, "estimable": False, "why": "m_A or m_B constant (Spearman undefined)" if len(inc) >= 3 else "fewer than 3 tasks"}
            continue
        rA = stats.rankdata(mA); rB = stats.rankdata(mB)
        rA = rA - rA.mean(); rB = rB - rB.mean()
        den = np.linalg.norm(rA) * np.linalg.norm(rB)
        rho_c = float(rA @ rB / den)
        assert abs(rho_c - stats.spearmanr(mA, mB).statistic) < 1e-9
        P = np.tile(np.arange(len(inc)), (n_perm, 1))
        for p in np.unique(pers[inc]):
            loc = np.where(pers[inc] == p)[0]
            order = np.argsort(U[:, inc[loc]], axis=1, kind="stable")
            P[:, loc] = loc[order]
        rBp = rB[P]
        # the estimable set cannot change under a permutation (constancy is permutation invariant): assert it
        assert np.all(np.ptp(mB[P], axis=1) > 0)
        perm_rho.append((rBp @ rA) / den)
        obs.append(rho_c); wts.append(w)
        per[key] = {**info, "estimable": True, "rho_c": round(rho_c, 4), "weight": w}
    if not obs:
        return {**out, "estimable": False, "why": "no cell estimable (reported as not estimable, never as rho = 0)", "cells": per}
    wn = np.array(wts) / np.sum(wts)
    rho = float(wn @ np.array(obs))
    null = wn @ np.vstack(perm_rho)
    p = float((1 + np.sum(null >= rho - 1e-12)) / (1 + n_perm))
    for (k, v), x in zip([(k, v) for k, v in per.items() if v.get("estimable")], wn):
        v["weight_renormalised"] = round(float(x), 4)
    return {**out, "estimable": True, "rho": round(rho, 4), "p_one_sided": round(p, 5), "reject_H0_at_0.05": bool(p < ALPHA),
            "n_perm": n_perm, "seed": PERM_SEED, "null_quantiles": {str(q): round(float(np.quantile(null, q)), 4) for q in (0.5, 0.9, 0.95, 0.99)},
            "cells": per,
            "reading": ("real task pairing across independent nonce halves is more consistent than persona-preserving random "
                        "pairing; this does not rule out task properties correlated with flip propensity within persona "
                        "(fault load, issue type, BF16 difficulty), and makes no 'beyond difficulty' claim")}


def tertile(v: float, cuts: list[float]) -> str:
    return "T1" if v <= cuts[0] else "T2" if v <= cuts[1] else "T3"


def strata(Mx: Matrix, cells_w: dict, cut: dict, bf: dict) -> dict:
    """§9. Six families; per pre-specified level: G (crossed decisional + block t), two-sided p from the crossed normal
    statistic, Holm within the family over all pre-specified levels (not-estimable levels keep their place with p = 1);
    r, d, M per level descriptive."""
    F = cut["families"]
    tasks = Mx.tasks
    lab = {
        "persona": [persona(t) for t in tasks],
        "issue_type": [issue_type(t.split(":", 1)[1]) for t in tasks],
        "n_faults": [tertile(n_faults(t.split(":", 1)[1]), F["n_faults"]["cuts"]) for t in tasks],
        "bf16_difficulty": [None if t not in bf else ("0" if bf[t]["succ"] == 0 else "low" if bf[t]["succ"] <= F["bf16_difficulty"]["c"] else "high") for t in tasks],
        "task_length": [None if t not in bf else tertile(bf[t]["len"], F["task_length"]["cuts"]) for t in tasks],
    }
    out = {}
    for fam in ("step_budget", "persona", "bf16_difficulty", "task_length", "issue_type", "n_faults"):
        levels = F[fam]["levels"]
        res = {}
        for lv in levels:
            if fam == "step_budget":  # unit-level, divergent units only: contribution form on the full task set
                um = {mc: np.where(np.isfinite(Mx.X[mc]["steps_left"]),
                                   np.vectorize(lambda v: float(tertile(v, F["step_budget"]["cuts"]) == lv))(np.nan_to_num(Mx.X[mc]["steps_left"], nan=-1)), 0.0)
                      for mc in cells_w}
                tm, kw = None, {"unit_mask": um}
                n_desc = {f"{mc[0]}:{mc[1]}": int(um[mc].sum()) for mc in cells_w}
            else:
                tm = np.array([x == lv for x in lab[fam]])
                kw = {"task_mask": tm}
                n_desc = int(tm.sum())
            if fam != "step_budget" and tm.sum() < 2:
                r = {"estimable": False, "why": f"{int(tm.sum())} task(s) in level"}
            else:
                r = estimate(Mx, "G", cells_w, **kw)
                if r["estimable"] and r["crossed_decisional"]["se"] > 0:
                    z = r["crossed_decisional"]["est"] / r["crossed_decisional"]["se"]
                    r["p_two_sided"] = float(2 * stats.norm.sf(abs(z)))
                else:
                    r["estimable"] = False
                    r["why"] = r.get("why", "zero crossed variance")
                r["descriptive_rdM"] = {s: pp(estimate(Mx, s, cells_w, **kw).get("crossed_decisional")) for s in ("rescue", "damage", "M")}
                r["G_crossed_pp"], r["G_block_t_pp"] = pp(r.pop("crossed_decisional", None)), pp(r.pop("block_t", None))
            r["n"] = n_desc
            res[lv] = r
        ps = [res[lv].get("p_two_sided", 1.0) if res[lv].get("estimable") else 1.0 for lv in levels]
        adj = holm(ps)
        for lv, p, a in zip(levels, ps, adj):
            res[lv]["p_holm"] = round(a, 5)
            res[lv]["reject_holm_0.05"] = bool(a < ALPHA)
        out[fam] = {"levels": levels, "m": len(levels), "cut": {k: F[fam].get(k) for k in ("cuts", "c") if F[fam].get(k) is not None},
                    "unit": "contribution of divergent units in the level to G_all (sums with the other levels to G_all)" if fam == "step_budget"
                    else "G_all of the tasks in the level (task-equal, non-divergent = 0)", "results": res}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--split", default=None, help="holdout (only after the prereg freeze)")
    ap.add_argument("--dry-run-dev", action="store_true", help="identical pipeline on telecom dev blocks f01-f06 (pseudo-holdout)")
    ap.add_argument("--complete-case", action="store_true", help="§4.6 sensitivity: infrastructure-missing units do not make a block incomplete")
    ap.add_argument("--n-perm", type=int, default=N_PERM)
    a = ap.parse_args()
    if a.dry_run_dev == (a.split == "holdout"):
        raise SystemExit("analyze_holdout_confirm: use exactly one of --split holdout or --dry-run-dev")
    if a.n_perm != N_PERM and not a.dry_run_dev:
        raise SystemExit("analyze_holdout_confirm: the prereg fixes 10,000 permutations")
    split = "dev" if a.dry_run_dev else "holdout"
    if split == "holdout":
        AD.split_guard([], "holdout", "analyze_holdout_confirm")  # refuses unless the prereg sha matches; before any holdout read
        if not a.snapshot:
            raise SystemExit("analyze_holdout_confirm: --snapshot is required for the holdout")
    if AD.sha256(CUTPOINTS) != CUTPOINTS_SHA256:
        raise SystemExit(f"analyze_holdout_confirm: {CUTPOINTS.relative_to(ROOT)} sha256 differs from the frozen value {CUTPOINTS_SHA256}")
    try:
        from loguru import logger
        logger.remove(); logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    t0 = time.time()
    snap_path = Path(a.snapshot) if a.snapshot else Path(sorted(glob.glob(str(ROOT / "analysis/insights/iter_3/out/snapshot_auto_*.json")))[-1])
    snap = json.load(open(snap_path))
    cut = json.load(open(CUTPOINTS))
    man = json.load(open(AD.SPLITS))
    tasks = sorted(f"telecom:{t}" for t in man["splits"][split]["tasks"]["telecom"])
    if split == "holdout":
        root, primary, reserve, label = "analysis/fork/holdout", PRIMARY_BLOCKS, RESERVE_BLOCKS, "CONFIRMATORY (telecom holdout)"
        cells = CELLS
    else:
        root, primary, reserve, label = "analysis/fork/telecom", DEV_BLOCKS, (), "DRY RUN ON DEV (telecom dev f01-f06 relabelled as pseudo-holdout; exploratory, not confirmatory)"
        cells = CELLS
    units, prov = load(snap, root, split, cells, set(primary) | set(reserve))
    present = sorted({(u["model"], u["cell"]) for u in units})
    cells_used = [(m, c, w) for m, c, w in cells if (m, c) in present]
    missing_cells = [f"{m}:{c}" for m, c, _ in cells if (m, c) not in present]
    if split == "holdout" and missing_cells:
        raise SystemExit(f"analyze_holdout_confirm: no units for cell(s) {missing_cells}; the matrix is not complete (§4)")
    wsum = sum(w for _, _, w in cells_used)
    cells_w = {(m, c): w / wsum for m, c, w in cells_used}
    # ---- §4.3 structural exclusions (task x cell, all blocks)
    excl = defaultdict(set)
    reasons = defaultdict(lambda: defaultdict(int))
    for u in units:
        if "excluded" in u:
            k = classify(u["excluded"])
            reasons[f"{u['model']}:{u['cell']}"][f"{k}: {u['excluded'][:80]}"] += 1
            if k == "structural":
                excl[(u["model"], u["cell"])].add(u["task"])
    for u in units:
        if u["task"] in excl[(u["model"], u["cell"])]:
            u.setdefault("excluded", "structural exclusion of the task in this cell")
            u["structurally_excluded"] = True
    # ---- §4.4 completeness per (cell, block)
    have = defaultdict(set)
    for u in units:
        if "excluded" not in u:
            have[(u["model"], u["cell"], u["block"])].add(u["task"])
    status = {}
    for b in list(primary) + list(reserve):
        miss = {}
        for m, c in cells_w:
            need = set(tasks) - excl[(m, c)]
            n_miss = len(need - have[(m, c, b)])
            if n_miss and not (a.complete_case and have[(m, c, b)]):
                miss[f"{m}:{c}"] = n_miss
        status[b] = {"complete": not miss, "missing_units": miss}
    halves0 = half_of(list(primary))
    used, block_map = [], {}
    free_res = [b for b in reserve if status[b]["complete"]]
    for b in primary:
        if status[b]["complete"]:
            used.append(b); block_map[b] = b
        elif free_res:
            r = free_res.pop(0)
            used.append(r); block_map[b] = r
        else:
            block_map[b] = None
    halves = {block_map[b]: halves0[b] for b in primary if block_map[b]}
    Mx = Matrix(tasks, used, units, cells_used)
    k_used = len(used)
    # ---- §6 primary, §7 S1, per-cell descriptive
    prim = estimate(Mx, "G", cells_w)
    prim["readings"] = readings(prim.get("crossed_decisional"), k_used)
    prim_pp = {"crossed_decisional": pp(prim["crossed_decisional"]), "block_t_alongside": pp(prim["block_t"]), "readings": prim["readings"],
               "J": prim["J"], "K": prim["K"]}
    s1 = {}
    for s in ("rescue", "damage", "M"):
        e = estimate(Mx, s, cells_w)
        s1[s] = {"crossed_decisional": pp(e["crossed_decisional"]), "block_t_alongside": pp(e["block_t"]),
                 "lb_gt_0": bool(e["crossed_decisional"] and e["crossed_decisional"]["lb95_one_sided"] > 0)}
    s1["S1_pass_r_and_d"] = bool(s1["rescue"]["lb_gt_0"] and s1["damage"]["lb_gt_0"])
    per_cell = {}
    for mc in cells_w:
        one = {mc: 1.0}
        d = {s: {"crossed": pp(estimate(Mx, s, one)["crossed_decisional"]), "block_t": pp(estimate(Mx, s, one)["block_t"])} for s in STATS4}
        div = Mx.X[mc]["div"]
        d["n_units"] = int(np.isfinite(div).sum()); d["n_divergent"] = int(np.nansum(div))
        d["n_rescue"], d["n_damage"] = int(np.nansum(Mx.X[mc]["rescue"])), int(np.nansum(Mx.X[mc]["damage"]))
        n_ex = len(excl[mc])
        d["structural_exclusions"] = {"n_tasks": n_ex, "n_c": len(tasks) - n_ex, "compromised_flag_gt3_kept": n_ex > 3}
        per_cell[f"{mc[0]}:{mc[1]}"] = d
    s2 = repeatability(Mx, cells_w, halves, a.n_perm)
    # ---- §9 strata
    bf_re = re.compile(r"^a6k2_(q4|q8)_tel_bfpair_(" + "|".join(used) + r")$")
    hold_ids = {str(t) for t in man["splits"]["holdout"]["tasks"]["telecom"]}
    allowed = {t.split(":", 1)[1] for t in tasks}
    bf_raw = bf16_task_stats(snap, bf_re, allowed, set() if split == "holdout" else hold_ids)
    bf = {f"telecom:{k}": v for k, v in bf_raw.items()}
    st = strata(Mx, cells_w, cut, bf)
    res = {
        "label": label, "prereg": PREREG, "prereg_sha256": AD.sha256(ROOT / PREREG),
        "splits_prereg_sha256_recorded": man["splits"]["holdout"].get("prereg_sha256"),
        "script": {"path": "analysis/fork/analyze_holdout_confirm.py", "sha256": AD.sha256(__file__),
                   "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
        "cutpoints": {"path": str(CUTPOINTS.relative_to(ROOT)), "sha256": CUTPOINTS_SHA256},
        "snapshot": {"id": snap.get("snapshot_id"), "path": str(snap_path.resolve().relative_to(ROOT)), "sha256": AD.sha256(snap_path)},
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "split": split, "complete_case_sensitivity": a.complete_case,
        "provenance": prov, "n_tasks": len(tasks),
        "cells": {f"{m}:{c}": {"prereg_weight": w, "weight_used": round(cells_w[(m, c)], 4)} for m, c, w in cells_used},
        "cells_absent": missing_cells,
        "weights_note": ("prereg weights" if not missing_cells else
                         f"cells {missing_cells} have no units (dev: no q4 telecom forks exist); weights renormalised over present cells"),
        "blocks": {"primary": list(primary), "reserve": list(reserve), "status": status, "block_map": block_map, "used": used,
                   "K_used": k_used, "halves": halves, "decision_rules_estimable": k_used >= MIN_K_DECISION},
        "missing_by_reason": {k: dict(v) for k, v in reasons.items()},
        "primary_G_all": prim_pp, "S1_two_sided_consequences": s1, "S2_repeatability": s2, "strata": st, "per_cell_descriptive": per_cell,
        "units_digest_sha256": AD.units_digest([u for u in units if "excluded" not in u and u["block"] in used]),
        "seconds": None,
    }
    res["seconds"] = round(time.time() - t0, 1)
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    stem = f"holdout_confirm_{'DRYRUN_DEV_' if a.dry_run_dev else ''}{'cc_' if a.complete_case else ''}{utc}"
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / f"{stem}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"{stem}.md").write_text(markdown(res, jp))
    print(f"analyze_holdout_confirm: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


def markdown(r: dict, jp: Path) -> str:
    def ci(d):
        return "n/a" if not d else f"{d['est']:+.2f} [{d['ci90'][0]:+.2f}, {d['ci90'][1]:+.2f}]"
    p, s1, s2 = r["primary_G_all"], r["S1_two_sided_consequences"], r["S2_repeatability"]
    dry = r["split"] == "dev"
    L = []
    if dry:
        L += ["> **DRY RUN ON DEV** — telecom dev blocks f01–f06 relabelled as a pseudo-holdout to prove the confirmatory pipeline "
              "executes end to end. Exploratory; not a holdout result; confirms nothing.", ""]
    L += [f"**TL;DR** {r['label']}: G_all {ci(p['crossed_decisional'])} pp (crossed, decisional; 90% CI), block-t "
          f"{ci(p['block_t_alongside'])}; reading: {p['readings']['reading']}. S1 r>0 & d>0: {s1['S1_pass_r_and_d']}. "
          f"S2 rho {s2.get('rho', 'not estimable')}, p {s2.get('p_one_sided', '—')}. K' = {r['blocks']['K_used']}.", "",
          f"# Holdout confirmation analysis — {'DRY RUN ON DEV' if dry else 'telecom holdout'} ({r['utc']})", "",
          f"Prereg `{r['prereg']}` sha256 `{r['prereg_sha256'][:16]}…` (recorded in splits_v1: `{r['splits_prereg_sha256_recorded']}`); "
          f"script sha `{r['script']['sha256'][:16]}…`, git `{r['script']['git_head'][:10]}`; cut points `{r['cutpoints']['sha256'][:16]}…`; "
          f"snapshot `{r['snapshot']['id']}`. JSON: `{jp.relative_to(ROOT)}`.", "",
          f"Cells and weights: {json.dumps(r['cells'])}. {r['weights_note']}.", "",
          f"Blocks used ({r['blocks']['K_used']}): {r['blocks']['used']}; halves {r['blocks']['halves']}; block map {r['blocks']['block_map']}.", "",
          "## Primary G_all (pp; 90% two-sided interval, lower end = one-sided 95% LB)", "",
          "| interval | estimate [90% CI] | one-sided 95% LB |", "|---|---|---|",
          f"| crossed task × block (decisional) | {ci(p['crossed_decisional'])} | {p['crossed_decisional']['lb95_one_sided']:+.2f} |",
          f"| t over block means (alongside) | {ci(p['block_t_alongside'])} | {p['block_t_alongside']['lb95_one_sided']:+.2f} |", "",
          f"Readings: {json.dumps(p['readings'])}", "",
          "## S1 two-sided consequences (pp)", "", "| stat | crossed (decisional) | block t | LB > 0 |", "|---|---|---|---|"]
    for s in ("rescue", "damage", "M"):
        L.append(f"| {s} | {ci(s1[s]['crossed_decisional'])} | {ci(s1[s]['block_t_alongside'])} | {s1[s]['lb_gt_0']} |")
    L += ["", f"S1 pass (r > 0 and d > 0): **{s1['S1_pass_r_and_d']}**", "", "## S2 cross-half repeatability", ""]
    if s2.get("estimable"):
        L.append(f"rho = {s2['rho']}, one-sided permutation p = {s2['p_one_sided']} ({s2['n_perm']} draws, seed {s2['seed']}); "
                 f"null quantiles {s2['null_quantiles']}. Halves A {s2['blocks_A']}, B {s2['blocks_B']}.")
    else:
        L.append(f"Not estimable: {s2.get('why')}.")
    for k, v in (s2.get("cells") or {}).items():
        L.append(f"- {k}: " + json.dumps(v))
    L += ["", s2.get("reading", ""), "", "## Strata (G per level; crossed interval; Holm within family)", ""]
    for fam, f in r["strata"].items():
        L.append(f"**{fam}** (m = {f['m']}; {f['unit']}; cut {f['cut']})")
        for lv, x in f["results"].items():
            if x.get("estimable"):
                L.append(f"- {lv}: n {x['n']}, G {ci(x['G_crossed_pp'])}, p {x['p_two_sided']:.4f}, Holm p {x['p_holm']:.4f}")
            else:
                L.append(f"- {lv}: n {x['n']}, not estimable ({x.get('why')}), Holm p {x['p_holm']}")
        L.append("")
    L += ["## Per-cell components (descriptive)", "", "| cell | G | r | d | M | units | divergent | excl. tasks |", "|---|---|---|---|---|---|---|---|"]
    for k, d in r["per_cell_descriptive"].items():
        L.append(f"| {k} | {ci(d['G']['crossed'])} | {ci(d['rescue']['crossed'])} | {ci(d['damage']['crossed'])} | {ci(d['M']['crossed'])} | "
                 f"{d['n_units']} | {d['n_divergent']} | {d['structural_exclusions']['n_tasks']}{' (>3: kept, flagged)' if d['structural_exclusions']['compromised_flag_gt3_kept'] else ''} |")
    L += ["", f"Missing units by reason: {json.dumps(r['missing_by_reason'])}"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
