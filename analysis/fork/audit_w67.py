"""W67 audit (W68; CONSEQUENCE_ANALYSIS_PLAN §5): dependence-preserving references and nonce-split replication.

INTERNAL REPLICATION ONLY: these development outcomes were already viewed (W67); nothing here is fresh confirmation.
The original W67 output and script (analysis/fork/analyze_consequence.py, consequence_*.json) are kept for provenance.

Population: the common retail/airline pool (85 split tasks) on the nonce blocks complete in every compared cell (q4/q8 x
GPTQ-W4, AWQ-W4, KV8; analyze_dev units, split guard, complete blocks). Exposure is therefore equal: every task has the
same blocks in every cell (no 85-vs-165 mixing). Per unit: G (primary-policy gain, 0 without divergence), M = |G|, QQ
outcome, rescue/damage indicators.

Frozen nonce split (before any statistic): blocks ordered by sha256("w67-split-v1|" + block); the first half is A, the
rest B. Every statistic is computed A->B and B->A (both reported, no choice of the stronger), plus 50 further hash splits
("w67-split-v1|s<k>|") as sensitivity.

1. Concentration (does gross consequence M belong to tasks?). Task M rates on A vs B: Spearman correlation and capture of
   B's M by A's top-20% tasks. Reference: whole B task vectors permuted within domain (keeps block structure, B-side
   heterogeneity and every within-task dependence; breaks only task identity), B = 2000, p = (1 + #>=)/(B + 1).
   Opportunity baseline: the same statistics for QQ failure (a task's baseline outcome), and capture of B's M by A's
   QQ-propensity ranking (tasks near 50% QQ success have the most flip opportunity).
2. Direction (do signs persist?). A-defined groups by the task's mean G on A: positive / negative / zero. On B: mean G per
   group (all A-selected tasks kept, also those without B events) with a t interval over B blocks, and the
   difference positive - negative; reference: B task vectors permuted within domain. Opportunity-only prediction: with
   pooled A rates rho = P(rescue | QQ fail) and delta = P(damage | QQ success), task i's expected B gain is
   rho (1 - q_i) - delta q_i from its A QQ success q_i; the same group contrast is reported for groups formed by this
   prediction, separating baseline opportunity from quantization-specific direction.
3. Cross-quantizer co-susceptibility (task/block level, NOT same-state): phi of M indicators on shared task x block units
   for each cell pair. Two references: (a) task identity: permute whole task vectors of the second cell within domain
   (keeps its task-level propensity distribution and nonce columns); (b) nonce alignment beyond task propensity: permute
   whole block columns of the second cell (keeps task identity; blocks exchangeable). Also the same-direction share among
   units where both flip.
4. Task-heterogeneity diagnostic (plan §5.1): mean over block pairs b<c of [sum_i w_i g_ib g_ic - gbar_b gbar_c] for G and
   M (equal task weights); negative estimates kept; descriptive.

usage: python analysis/fork/audit_w67.py --snapshot <snapshot.json> [--B 2000]
-> analysis/fork/out/w67_audit_<s>.md, analysis/fork/out/direction_replication_<s>.json
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--n-splits", type=int, default=50)
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
    split_info = AD.split_guard(allu, "dev", "audit_w67")
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined")
    AD.mark_incomplete_blocks(allu, "dev")
    seen, units = set(), []
    for u in allu:
        k = (u["run_id"], u["domain"], u["task"])
        if k not in seen and "excluded" not in u and u["domain"] in ("retail", "airline"):
            seen.add(k)
            units.append(u)
    by = defaultdict(dict)
    for u in units:
        e = AD.effects(u["Y"], u["div"])
        by[(u["model"], u["cell"])][(u["task"], u["block"])] = (e["G"], e["M"], u["Y"]["QQ"], e["rescue"], e["damage"])
    present = [mc for mc in CELLS if by.get(mc)]
    blocks = sorted(set.intersection(*[{b for _, b in by[mc]} for mc in present]))
    tasks = sorted(set.intersection(*[{t for t, _ in by[mc]} for mc in present]))
    # keep only tasks observed in every common block of every cell (equal exposure)
    tasks = [t for t in tasks if all((t, b) in by[mc] for mc in present for b in blocks)]
    dom_idx = defaultdict(list)
    for i, t in enumerate(tasks):
        dom_idx[t.split(":")[0]].append(i)
    T, K = len(tasks), len(blocks)

    def arr(mc, j):  # tasks x blocks
        return np.array([[by[mc][(t, b)][j] for b in blocks] for t in tasks], float)

    data = {mc: {"G": arr(mc, 0), "M": arr(mc, 1), "QQ": arr(mc, 2), "r": arr(mc, 3), "d": arr(mc, 4)} for mc in present}
    A0, B0 = hsplit(blocks, "w67-split-v1|")
    frozen = {"salt": "w67-split-v1|", "A": A0, "B": B0}
    bix = {b: i for i, b in enumerate(blocks)}

    def cols(s):
        return [bix[b] for b in s]

    def concentration(D, sa, sb):
        mA, mB = D["M"][:, cols(sa)].mean(1), D["M"][:, cols(sb)].mean(1)
        qA, qB = 1 - D["QQ"][:, cols(sa)].mean(1), 1 - D["QQ"][:, cols(sb)].mean(1)
        oppA = D["QQ"][:, cols(sa)].mean(1) * (1 - D["QQ"][:, cols(sa)].mean(1))  # flip opportunity ~ q(1-q)
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
        for name, g in (("positive", 1), ("negative", -1), ("zero", 0)):
            sel = grp == g
            per_block = D["G"][sel][:, cols(sb)].mean(0) if sel.any() else np.array([])
            t = AD.t_interval(per_block)
            res[name] = {"n_tasks": int(sel.sum()), "mean_G_on_B_pp": round(100 * float(gB[sel].mean()), 3) if sel.any() else None,
                         "t_ci95_over_B_blocks_pp": [round(100 * t["lo"], 3), round(100 * t["hi"], 3)] if t else None}
        diff = lambda gb, gr: float(gb[gr == 1].mean() - gb[gr == -1].mean()) if (gr == 1).any() and (gr == -1).any() else float("nan")
        obs = diff(gB, grp)
        null = [diff(gB[perm_within_domain(rng, dom_idx)], grp) for _ in range(a.B)]
        nz = (grp != 0) & (np.sign(gB) != 0)
        # opportunity-only prediction from A
        qA = D["QQ"][:, cols(sa)].mean(1)
        fail, succ = D["QQ"][:, cols(sa)] == 0, D["QQ"][:, cols(sa)] == 1
        rho = D["r"][:, cols(sa)][fail].mean() if fail.any() else 0.0
        delta = D["d"][:, cols(sa)][succ].mean() if succ.any() else 0.0
        pred = rho * (1 - qA) - delta * qA
        order = np.argsort(pred, kind="mergesort")  # rank-based thirds (ties broken by task order)
        pg = np.zeros(len(pred), int)
        pg[order[: len(pred) // 3]] = -1
        pg[order[len(pred) - len(pred) // 3:]] = 1
        # direction beyond opportunity: on B, rescue rate among QQ-fail units and damage rate among QQ-success units,
        # by A-defined group; reference: B task vectors permuted within domain
        fB, sBm = D["QQ"][:, cols(sb)] == 0, D["QQ"][:, cols(sb)] == 1
        rB, dB = D["r"][:, cols(sb)], D["d"][:, cols(sb)]

        def cond_rates(gr, perm=None):
            ix = np.arange(len(gr)) if perm is None else perm
            rf, rs = rB[ix], dB[ix]
            ff, ss = fB[ix], sBm[ix]
            out = {}
            for name, g in (("positive", 1), ("negative", -1)):
                sel = gr == g
                out[f"rescue_given_QQfail_{name}"] = float(rf[sel][ff[sel]].mean()) if ff[sel].any() else float("nan")
                out[f"damage_given_QQsucc_{name}"] = float(rs[sel][ss[sel]].mean()) if ss[sel].any() else float("nan")
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

    out = {"label": "INTERNAL REPLICATION (development outcomes already viewed, W67); not confirmation",
           "snapshot_id": sid, "split": split_info, "population": {"cells": [f"{m}:{c}" for m, c in present], "n_tasks": T,
                                                                     "n_blocks": K, "blocks": blocks, "domains": {d: len(v) for d, v in dom_idx.items()}},
           "frozen_split": frozen, "B": a.B, "seed": AD.SEED, "cells": {}, "overlap": {}}
    extra = [hsplit(blocks, f"w67-split-v1|s{k}|") for k in range(a.n_splits)]
    for mc in present:
        D = data[mc]
        lab = f"{mc[0]}:{mc[1]}"
        r = {"concentration": {"A->B": concentration(D, A0, B0), "B->A": concentration(D, B0, A0)},
             "direction": {"A->B": direction(D, A0, B0), "B->A": direction(D, B0, A0)}}
        sens = []
        for sa, sb in extra:
            gA, gB = D["G"][:, cols(sa)].mean(1), D["G"][:, cols(sb)].mean(1)
            gr = np.sign(gA)
            sens.append(float(gB[gr == 1].mean() - gB[gr == -1].mean()) if (gr == 1).any() and (gr == -1).any() else np.nan)
        r["direction_sensitivity_50_splits_pos_minus_neg_pp"] = {"median": round(100 * float(np.nanmedian(sens)), 3),
                                                                  "q10_q90": [round(100 * float(np.nanquantile(sens, q)), 3) for q in (0.1, 0.9)],
                                                                  "share_positive": float(np.nanmean(np.array(sens) > 0))}
        # heterogeneity diagnostic
        het = {}
        for key in ("G", "M"):
            g = D[key]
            gb = g.mean(0)
            vals = [float((g[:, b] * g[:, c]).mean() - gb[b] * gb[c]) for b, c in combinations(range(K), 2)]
            het[key] = {"stable_task_variance": float(np.mean(vals)), "total_task_variance_pooled": float(g.mean(1).var())}
        r["task_heterogeneity_diagnostic"] = het
        out["cells"][lab] = r
    for c1, c2 in PAIRS:
        if c1 not in data or c2 not in data:
            continue
        m1, m2 = data[c1]["M"], data[c2]["M"]

        def phi(x, y):
            x, y = x.ravel(), y.ravel()
            return float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else float("nan")
        obs = phi(m1, m2)
        null_task = [phi(m1, m2[perm_within_domain(rng, dom_idx)]) for _ in range(a.B)]
        null_block = [phi(m1, m2[:, rng.permutation(K)]) for _ in range(a.B)]
        both = (m1 == 1) & (m2 == 1)
        g1, g2 = data[c1]["G"], data[c2]["G"]
        out["overlap"][f"{c1[0]}:{c1[1]} vs {c2[0]}:{c2[1]}"] = {
            "phi_M": round(obs, 4), "n_units": int(m1.size), "both_flip": int(both.sum()),
            "task_identity_null": {"p": pval(obs, null_task), "median": round(float(np.nanmedian(null_task)), 4),
                                   "q95": round(float(np.nanquantile(null_task, 0.95)), 4)},
            "nonce_alignment_null": {"p": pval(obs, null_block), "median": round(float(np.nanmedian(null_block)), 4),
                                     "q95": round(float(np.nanquantile(null_block, 0.95)), 4)},
            "same_direction_share_when_both_flip": float(np.mean(np.sign(g1[both]) == np.sign(g2[both]))) if both.any() else None,
            "interpretation": "task/block co-susceptibility; not same-state (histories differ across cells)"}
    out["seconds"] = round(time.time() - t0, 1)
    out["script_sha256"] = AD.sha256(__file__)
    out["analysis_commit"] = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    jp = OUT / f"direction_replication_{sid}.json"
    jp.write_text(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"w67_audit_{sid}.md").write_text(markdown(out, jp))
    print(f"audit_w67: wrote {jp.name} and w67_audit_{sid}.md ({out['seconds']} s)")


def markdown(o: dict, jp: Path) -> str:
    L = [f"**TL;DR** W67 audit (internal replication on the common {o['population']['n_tasks']}-task x {o['population']['n_blocks']}-block "
         "retail/airline panel, frozen hash nonce split, dependence-preserving references): see the table; the original W67 claims are "
         "re-graded below.", "", f"# W67 audit ({o['snapshot_id']})", "",
         f"Full numbers `{jp.relative_to(ROOT)}`. Frozen split A = {o['frozen_split']['A']}, B = {o['frozen_split']['B']}. "
         "Monte Carlo p = (1 + #extreme)/(B + 1). INTERNAL REPLICATION ONLY.", "",
         "## Concentration: task M rate on A predicts task M rate on B (whole task vectors permuted within domain)", "",
         "| cell | dir | Spearman M (p) | capture top 20% by A-M (null median) | capture by QQ opportunity | Spearman QQ fail |", "|---|---|---|---|---|---|"]
    for k, v in o["cells"].items():
        for d, c in v["concentration"].items():
            L.append(f"| {k} | {d} | {c['spearman_M']:.2f} ({c['p_spearman_M']:.4f}) | {c['capture_top20_by_A_M']:.2f} ({c['null_capture_median']:.2f}) | "
                     f"{c['capture_top20_by_A_QQ_opportunity']:.2f} | {c['spearman_QQ_fail']:.2f} |")
    L += ["", "## Direction: A-defined sign groups, mean G on B (pp)", "",
          "| cell | dir | positive (n) | negative (n) | pos − neg (perm p) | opportunity-only top−bottom third | 50 splits: median pos−neg [q10, q90] |",
          "|---|---|---|---|---|---|---|"]
    for k, v in o["cells"].items():
        s = v["direction_sensitivity_50_splits_pos_minus_neg_pp"]
        for d, r in v["direction"].items():
            L.append(f"| {k} | {d} | {r['positive']['mean_G_on_B_pp']} ({r['positive']['n_tasks']}) | {r['negative']['mean_G_on_B_pp']} ({r['negative']['n_tasks']}) | "
                     f"{r['pos_minus_neg_on_B_pp']} ({r['p_perm']:.4f}) | {r['opportunity_only']['top_minus_bottom_third_on_B_pp']} | "
                     f"{s['median']} {s['q10_q90']} |")
    L += ["", "## Direction beyond opportunity (on B: rescue | QQ fail and damage | QQ success, by A-defined group; perm p)", "",
          "| cell | dir | rescue|fail pos vs neg (p) | damage|success neg vs pos (p) |", "|---|---|---|---|"]
    for k, v in o["cells"].items():
        for d, r in v["direction"].items():
            b = r["beyond_opportunity_on_B"]
            L.append(f"| {k} | {d} | {b['rescue_given_QQfail_positive']:.3f} vs {b['rescue_given_QQfail_negative']:.3f} ({b['p_rescue_diff']:.4f}) | "
                     f"{b['damage_given_QQsucc_negative']:.3f} vs {b['damage_given_QQsucc_positive']:.3f} ({b['p_damage_diff']:.4f}) |")
    L += ["", "## Cross-quantizer co-susceptibility (task/block level, not same-state)", "",
          "| pair | phi(M) | task-identity null p (q95) | nonce-alignment null p (q95) | same direction when both flip |", "|---|---|---|---|---|"]
    for k, v in o["overlap"].items():
        L.append(f"| {k} | {v['phi_M']} | {v['task_identity_null']['p']:.4f} ({v['task_identity_null']['q95']}) | "
                 f"{v['nonce_alignment_null']['p']:.4f} ({v['nonce_alignment_null']['q95']}) | {v['same_direction_share_when_both_flip']} |")
    L += ["", "## Task-heterogeneity diagnostic (stable task variance; negative kept)", ""]
    for k, v in o["cells"].items():
        h = v["task_heterogeneity_diagnostic"]
        L.append(f"- {k}: G {h['G']['stable_task_variance']:.4f} (of total {h['G']['total_task_variance_pooled']:.4f}); "
                 f"M {h['M']['stable_task_variance']:.4f} (of total {h['M']['total_task_variance_pooled']:.4f})")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
