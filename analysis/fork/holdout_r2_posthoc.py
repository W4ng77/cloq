"""POST-HOC, descriptive, not part of the pre-registered confirmation: W93 R2 estimands on the telecom holdout forks.

Allowed by docs/insights/PREREG_FORK_CONFIRM.md §10 (supplementary descriptive outputs; advisor-approved). It changes no
frozen file and does not touch the frozen primary endpoint (G_all of analysis/fork/analyze_holdout_confirm.py).

Loading (guarded): analyze_dev.split_guard is called with split "holdout" before any holdout file is opened (it refuses
unless the prereg's sha256 equals manifests/fork/splits_v1.json holdout.prereg_sha256); the units are then loaded with
analyze_holdout_confirm.load (imported, unmodified), which calls analyze_dev.load_dir (snapshot admission, trajectory sha,
branch files) and analyze_dev.split_guard(units, "holdout"). Snapshot: analysis/insights/iter_3/out/snapshot_holdout_
20261002T0123Z.json (the one the confirmatory output records; sha256 checked).
Admission/inclusion = the confirmatory script's (§4.2-4.5, re-implemented line for line from its main(), not the
complete-case sensitivity): QQ no-op mismatch -> structural; structural exclusion of a task from a cell in all blocks;
per-(cell, block) completeness; incomplete primary blocks replaced by complete reserves h13, h14. Cells q4 gptq_w4_d1,
q8 gptq_w4_d1, q8 awq_w4 with prereg weights 1/2, 1/4, 1/4; blocks h01-h12. The analysed units' digest is asserted equal
to the confirmatory output's units_digest_sha256.

Estimands (success scale; analysis/fork/analyze_ghf.py notation), on each cell's divergent states:
  G = Y_BQ - Y_QQ, H = Y_QB - Y_QQ, F = Y_BB - Y_QQ; G - H = Y_BQ - Y_QB, F - G = Y_BB - Y_BQ, F - H = Y_BB - Y_QB;
  Delta_Q = Y_BQ - Y_QQ, Delta_B = Y_BB - Y_QB, I = Delta_Q - Delta_B; 3x3 (Delta_Q, Delta_B) table; off-diagonal share;
  strict reversals (Delta_Q * Delta_B < 0); 16 outcome patterns (bit order BB, BQ, QB, QQ).
Per cell: ratio R_c = sum over divergent units of X / number of divergent units (task x block matrix, units outside the
  cell's admitted set contribute nothing). Pool: prereg-weighted mean of the cell ratios, sum_c w_c R_c (w = 1/2, 1/4, 1/4).
Intervals (as the confirmatory script, applied to ratios):
  crossed task x block: two-way random-effects ANOVA moments (analyze_holdout_confirm.crossed, normal) on the delta-method
    linearisation Z_c[j,b] = (X_c[j,b] - R_c D_c[j,b]) / mean(D_c) (pool: Z = sum_c w_c Z_c), centred at R_c (or the pool);
  block t: t over the K per-block ratios R_{c,b} (pool: sum_c w_c R_{c,b}), centred at their mean.
  The md reports 95% two-sided intervals; the JSON also carries the 90% interval the confirmatory script uses.
Marginal-preserving pairing agreement control (not a null for interaction): from each 3x3 table, expected diagonal share
  under independent pairing with the observed margins p_e = sum_a p_Q(a) p_B(a), expected off-diagonal = 1 - p_e, and
  kappa = (p_o - p_e) / (1 - p_e). Pool: computed on the prereg-weighted 3x3 shares.

usage: python analysis/fork/holdout_r2_posthoc.py [--snapshot <SNAP>]
-> analysis/fork/out/holdout_r2_posthoc_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402
import analyze_holdout_confirm as HC  # noqa: E402  (frozen; imported, never modified)

ROOT, OUT = AD.ROOT, AD.OUT
LABEL = "POST-HOC, descriptive, not part of the pre-registered confirmation"
DEF_SNAPSHOT = "analysis/insights/iter_3/out/snapshot_holdout_20261002T0123Z.json"
SNAPSHOT_SHA256 = "f5023c633f029395a8bad81429bb4f9d637bdf43a47e762eadb9c89fb7f70f84"
CONFIRM_OUT = "analysis/fork/out/holdout_confirm_20261002T012353Z.json"
VALS = (-1, 0, 1)
PATTERNS = [f"{i:04b}" for i in range(16)]  # bit order BB, BQ, QB, QQ
RATIOS = ["G", "H", "F", "GmH", "FmG", "FmH", "I", "offdiag", "strict_reversal", "Y_BB", "Y_BQ", "Y_QB", "Y_QQ"]
CELLS3 = [f"{a},{b}" for a in VALS for b in VALS]
Z975 = float(stats.norm.ppf(0.975))


def r2_effects(Y: dict) -> dict:
    dq, db = Y["BQ"] - Y["QQ"], Y["BB"] - Y["QB"]
    E = {"G": Y["BQ"] - Y["QQ"], "H": Y["QB"] - Y["QQ"], "F": Y["BB"] - Y["QQ"], "GmH": Y["BQ"] - Y["QB"],
         "FmG": Y["BB"] - Y["BQ"], "FmH": Y["BB"] - Y["QB"], "dQ": dq, "dB": db, "I": dq - db, "offdiag": int(dq != db),
         "strict_reversal": int(dq * db < 0), "pattern": f"{Y['BB']}{Y['BQ']}{Y['QB']}{Y['QQ']}",
         **{f"Y_{k}": Y[k] for k in ("BB", "BQ", "QB", "QQ")}}
    assert E["GmH"] == E["G"] - E["H"] and E["FmG"] == E["F"] - E["G"] and E["FmH"] == E["F"] - E["H"]
    assert E["G"] == AD.effects(Y, True)["G"]
    return E


def admit(units: list[dict], tasks: list[str]) -> tuple[list[str], dict, dict, dict]:
    """analyze_holdout_confirm.main §4.3-4.5 (not complete-case), verbatim logic."""
    cells_w = {(m, c): w for m, c, w in HC.CELLS}
    excl = defaultdict(set)
    reasons = defaultdict(lambda: defaultdict(int))
    for u in units:
        if "excluded" in u:
            k = HC.classify(u["excluded"])
            reasons[f"{u['model']}:{u['cell']}"][f"{k}: {u['excluded'][:80]}"] += 1
            if k == "structural":
                excl[(u["model"], u["cell"])].add(u["task"])
    for u in units:
        if u["task"] in excl[(u["model"], u["cell"])]:
            u.setdefault("excluded", "structural exclusion of the task in this cell")
    have = defaultdict(set)
    for u in units:
        if "excluded" not in u:
            have[(u["model"], u["cell"], u["block"])].add(u["task"])
    status = {}
    for b in list(HC.PRIMARY_BLOCKS) + list(HC.RESERVE_BLOCKS):
        miss = {}
        for m, c in cells_w:
            n_miss = len(set(tasks) - excl[(m, c)] - have[(m, c, b)])
            if n_miss:
                miss[f"{m}:{c}"] = n_miss
        status[b] = {"complete": not miss, "missing_units": miss}
    used, block_map = [], {}
    free_res = [b for b in HC.RESERVE_BLOCKS if status[b]["complete"]]
    for b in HC.PRIMARY_BLOCKS:
        if status[b]["complete"]:
            used.append(b); block_map[b] = b
        elif free_res:
            r = free_res.pop(0)
            used.append(r); block_map[b] = r
        else:
            block_map[b] = None
    return used, {"status": status, "block_map": block_map}, {f"{m}:{c}": sorted(v) for (m, c), v in excl.items()}, {k: dict(v) for k, v in reasons.items()}


def interval(pt: float, cr: dict | None, bt: dict | None, K: int) -> dict:
    o = {"est_pp": 100 * pt}
    if cr is not None:
        se = cr["se"]
        o["crossed"] = {"se_pp": 100 * se, "ci95_pp": [100 * (pt - Z975 * se), 100 * (pt + Z975 * se)],
                        "ci90_pp": [100 * (pt - HC.Z90 * se), 100 * (pt + HC.Z90 * se)],
                        "components": cr.get("components")}
    if bt is not None:
        q95 = stats.t.ppf(0.975, K - 1)
        o["block_t"] = {"est_pp": 100 * bt["est"], "se_pp": 100 * bt["se"], "df": bt["df"],
                        "ci95_pp": [100 * (bt["est"] - q95 * bt["se"]), 100 * (bt["est"] + q95 * bt["se"])],
                        "ci90_pp": [100 * x for x in bt["ci90"]], "block_means_pp": [round(100 * x, 2) for x in bt["block_means"]]}
    return o


def control(shares: dict) -> dict:
    pQ = {a: sum(shares[f"{a},{b}"] for b in VALS) for a in VALS}
    pB = {b: sum(shares[f"{a},{b}"] for a in VALS) for b in VALS}
    po = sum(shares[f"{a},{a}"] for a in VALS)
    pe = sum(pQ[a] * pB[a] for a in VALS)
    return {"observed_diagonal_share": po, "observed_offdiag_share": 1 - po, "expected_diagonal_share_independent": pe,
            "expected_offdiag_share_independent": 1 - pe, "kappa": (po - pe) / (1 - pe) if pe < 1 else None,
            "margins_dQ": {str(a): pQ[a] for a in VALS}, "margins_dB": {str(b): pB[b] for b in VALS}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", default=DEF_SNAPSHOT)
    a = ap.parse_args()
    AD.split_guard([], "holdout", "holdout_r2_posthoc")  # refuses unless the prereg is frozen; before any holdout read
    if AD.sha256(HC.CUTPOINTS) != HC.CUTPOINTS_SHA256:
        raise SystemExit("holdout_r2_posthoc: cut points differ from the frozen sha")
    snap_path = ROOT / a.snapshot
    if AD.sha256(snap_path) != SNAPSHOT_SHA256:
        raise SystemExit(f"holdout_r2_posthoc: snapshot sha256 differs from the confirmatory one ({SNAPSHOT_SHA256})")
    try:
        from loguru import logger
        logger.remove(); logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    t0 = time.time()
    snap = json.load(open(snap_path))
    man = json.load(open(AD.SPLITS))
    tasks = sorted(f"telecom:{t}" for t in man["splits"]["holdout"]["tasks"]["telecom"])
    units, prov = HC.load(snap, "analysis/fork/holdout", "holdout", HC.CELLS, set(HC.PRIMARY_BLOCKS) | set(HC.RESERVE_BLOCKS))
    used, blocks, struct_excl, reasons = admit(units, tasks)
    analysed = [u for u in units if "excluded" not in u and u["block"] in used]
    digest = AD.units_digest(analysed)
    conf = json.load(open(ROOT / CONFIRM_OUT))
    assert digest == conf["units_digest_sha256"], "analysed units differ from the confirmatory analysis"
    assert used == conf["blocks"]["used"]
    J, K = len(tasks), len(used)
    ti, bi = {t: i for i, t in enumerate(tasks)}, {b: i for i, b in enumerate(used)}
    W = {f"{m}:{c}": w for m, c, w in HC.CELLS}
    res_cells, lin, blk, pts = {}, defaultdict(dict), defaultdict(dict), defaultdict(dict)
    for m, c, w in HC.CELLS:
        lab = f"{m}:{c}"
        cu = [u for u in analysed if (u["model"], u["cell"]) == (m, c)]
        div = [u for u in cu if u["div"]]
        for u in div:
            u["E"] = r2_effects(u["Y"])
        D = np.zeros((J, K))
        for u in div:
            D[ti[u["task"]], bi[u["block"]]] = 1.0
        out = {"prereg_weight": w, "n_units": len(cu), "n_divergent_states": len(div),
               "n_tasks_included": len({u["task"] for u in cu}), "structurally_excluded_tasks": struct_excl.get(lab, []),
               "confirm_n_divergent": conf["per_cell_descriptive"][lab]["n_divergent"], "stats": {}}
        assert out["n_divergent_states"] == out["confirm_n_divergent"] and len(cu) == conf["per_cell_descriptive"][lab]["n_units"]
        for s in RATIOS:
            X = np.zeros((J, K))
            for u in div:
                X[ti[u["task"]], bi[u["block"]]] = u["E"][s]
            R = X.sum() / D.sum()
            Z = (X - R * D) / D.mean()
            Rb = X.sum(0) / D.sum(0)
            lin[s][lab], blk[s][lab], pts[s][lab] = Z, Rb, R
            out["stats"][s] = interval(R, HC.crossed(Z), HC.block_t(Rb), K)
        n = len(div)
        cnt = {k: sum(1 for u in div if f"{u['E']['dQ']},{u['E']['dB']}" == k) for k in CELLS3}
        out["table3"] = {"n": n, "counts_dQ_dB": cnt, "shares": {k: v / n for k, v in cnt.items()},
                         "diagonal_n": sum(cnt[f"{x},{x}"] for x in VALS), "offdiag_n": n - sum(cnt[f"{x},{x}"] for x in VALS),
                         "strict_reversal_n": cnt["1,-1"] + cnt["-1,1"],
                         "I_dist": {str(v): sum(1 for u in div if u["E"]["I"] == v) for v in (-2, -1, 0, 1, 2)},
                         "marginal_preserving_pairing_agreement_control": control({k: v / n for k, v in cnt.items()})}
        pc = {p: sum(1 for u in div if u["E"]["pattern"] == p) for p in PATTERNS}
        out["patterns16"] = {"bit_order": "BB,BQ,QB,QQ", "counts": pc, "shares": {p: v / n for p, v in pc.items()}}
        res_cells[lab] = out
    pool = {"weights": W, "stats": {}}
    for s in RATIOS:
        R = sum(W[l] * pts[s][l] for l in W)
        Z = sum(W[l] * lin[s][l] for l in W)
        Rb = sum(W[l] * blk[s][l] for l in W)
        pool["stats"][s] = interval(R, HC.crossed(Z), HC.block_t(Rb), K)
    sh3 = {k: sum(W[l] * res_cells[l]["table3"]["shares"][k] for l in W) for k in CELLS3}
    pool["table3_weighted_shares"] = sh3
    pool["strict_reversal_weighted_share"] = sh3["1,-1"] + sh3["-1,1"]
    pool["marginal_preserving_pairing_agreement_control"] = control(sh3)
    pool["patterns16_weighted_shares"] = {p: sum(W[l] * res_cells[l]["patterns16"]["shares"][p] for l in W) for p in PATTERNS}
    res = {"label": LABEL, "prereg": HC.PREREG, "prereg_section": "§10 (supplementary descriptive; advisor-approved)",
           "script": {"path": "analysis/fork/holdout_r2_posthoc.py", "sha256": AD.sha256(__file__),
                      "analyze_holdout_confirm_sha256": AD.sha256(ROOT / "analysis/fork/analyze_holdout_confirm.py"),
                      "analyze_dev_sha256": AD.sha256(ROOT / "analysis/fork/analyze_dev.py"),
                      "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
           "snapshot": {"path": a.snapshot, "sha256": SNAPSHOT_SHA256, "id": snap.get("snapshot_id")},
           "confirmatory_output_checked": {"path": CONFIRM_OUT, "units_digest_sha256": digest, "digest_equal": True},
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "scale": "success (Y = 1 success); raw four-arm Y",
           "provenance": prov, "n_tasks": J, "blocks": {"used": used, "K": K, **blocks}, "missing_by_reason": reasons,
           "intervals": "crossed task x block (ANOVA moments on the delta-method linearisation of the ratio; normal) and t over per-block ratios; 95% and 90% two-sided",
           "cells": res_cells, "pool_prereg_weighted": pool}
    res["seconds"] = round(time.time() - t0, 1)
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / f"holdout_r2_posthoc_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"holdout_r2_posthoc_{utc}.md").write_text(markdown(res, jp))
    print(f"holdout_r2_posthoc: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


def markdown(r: dict, jp: Path) -> str:
    def cr(x):
        c = x.get("crossed")
        return f"{x['est_pp']:+.1f} [{c['ci95_pp'][0]:+.1f}, {c['ci95_pp'][1]:+.1f}]" if c else f"{x['est_pp']:+.1f}"

    def bt(x):
        b = x.get("block_t")
        return f"{b['est_pp']:+.1f} [{b['ci95_pp'][0]:+.1f}, {b['ci95_pp'][1]:+.1f}]" if b else "n/a"
    C, P = r["cells"], r["pool_prereg_weighted"]
    rows = list(C.items()) + [("pool (½, ¼, ¼)", {"stats": P["stats"]})]
    tl = "; ".join(f"{k} ({v['n_divergent_states']} st): G {v['stats']['G']['est_pp']:+.1f}, H {v['stats']['H']['est_pp']:+.1f}, "
                   f"F {v['stats']['F']['est_pp']:+.1f}, G−H {cr(v['stats']['GmH'])}, off-diag {v['stats']['offdiag']['est_pp']:.1f}% "
                   f"(expected under independent pairing {100 * v['table3']['marginal_preserving_pairing_agreement_control']['expected_offdiag_share_independent']:.1f}%, "
                   f"κ {v['table3']['marginal_preserving_pairing_agreement_control']['kappa']:.2f}), reversals {v['table3']['strict_reversal_n']}"
                   for k, v in C.items())
    ps = P["stats"]
    pc = P["marginal_preserving_pairing_agreement_control"]
    L = [f"**TL;DR** {r['label']}. Telecom holdout, W93 R2 on divergent states (success scale; pp; crossed task × block 95%): {tl}. "
         f"Prereg-weighted pool: G {cr(ps['G'])}, H {cr(ps['H'])}, F {cr(ps['F'])}, G−H {cr(ps['GmH'])}, off-diag "
         f"{ps['offdiag']['est_pp']:.1f}% (expected {100 * pc['expected_offdiag_share_independent']:.1f}%, κ {pc['kappa']:.2f}), strict reversals "
         f"{100 * P['strict_reversal_weighted_share']:.1f}%. The frozen primary endpoint (G_all) is untouched.", "",
         f"> **{r['label']}.** Supplementary descriptive output under {r['prereg']} {r['prereg_section']}. Decides nothing.", "",
         f"Source: `{jp.relative_to(ROOT)}`; script sha `{r['script']['sha256'][:12]}`, analyze_holdout_confirm sha "
         f"`{r['script']['analyze_holdout_confirm_sha256'][:12]}` (unmodified), git `{r['script']['git_head'][:10]}`. Snapshot "
         f"`{r['snapshot']['path']}` (sha `{r['snapshot']['sha256'][:12]}`). Loaded through analyze_dev.split_guard(--split holdout) and "
         f"analyze_holdout_confirm.load; admission = the confirmatory script's (§4.2–4.5). Analysed units digest = confirmatory "
         f"output's (`{r['confirmatory_output_checked']['units_digest_sha256'][:16]}…`, `{r['confirmatory_output_checked']['path']}`).", "",
         f"Blocks used (K = {r['blocks']['K']}): {r['blocks']['used']}. Tasks: {r['n_tasks']}. Missing by reason: {json.dumps(r['missing_by_reason'])}.", "",
         "Notation: G = Y_BQ−Y_QQ, H = Y_QB−Y_QQ, F = Y_BB−Y_QQ; Δ_Q = G, Δ_B = Y_BB−Y_QB, I = Δ_Q−Δ_B. Per cell: ratio over its "
         "divergent states; pool = ½·q4 GPTQ-W4 + ¼·q8 GPTQ-W4 + ¼·q8 AWQ-W4 of the cell ratios. Intervals: crossed task × block "
         "(two-way random-effects ANOVA moments on the delta-method linearisation of the ratio, normal) and t over the 12 "
         "per-block ratios (centred at their mean); 95% two-sided here, 90% in the JSON.", "",
         "## 1. G, H, F and paired differences (pp, divergent states; crossed 95%)", "",
         "| cell | n st | G | H | F | G−H | F−G | F−H | I |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in rows:
        s = v["stats"]
        L.append(f"| {k} | {v.get('n_divergent_states', sum(C[c]['n_divergent_states'] for c in C))} | {cr(s['G'])} | {cr(s['H'])} | {cr(s['F'])} | "
                 f"{cr(s['GmH'])} | {cr(s['FmG'])} | {cr(s['FmH'])} | {cr(s['I'])} |")
    L += ["", "## 2. Same, block t over 12 per-block ratios (95%)", "",
          "| cell | G | H | F | G−H | F−G | F−H | I | off-diag % | strict reversals % |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in rows:
        s = v["stats"]
        L.append(f"| {k} | " + " | ".join(bt(s[x]) for x in ("G", "H", "F", "GmH", "FmG", "FmH", "I", "offdiag", "strict_reversal")) + " |")
    L += ["", "## 3. Δ_Q × Δ_B table and the marginal-preserving pairing agreement control", "",
          "Counts `(Δ_Q, Δ_B)` per cell (pool row: prereg-weighted shares, %). The control gives the off-diagonal share expected "
          "if Δ_Q and Δ_B were paired independently with their observed margins, and Cohen's κ; it is a marginal-preserving pairing "
          "agreement control, not a null for interaction.", "",
          "| cell | (−1,−1) | (−1,0) | (−1,1) | (0,−1) | (0,0) | (0,1) | (1,−1) | (1,0) | (1,1) | off-diag % [crossed 95%] | expected off-diag % | κ | strict reversals % [crossed 95%] (n) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in C.items():
        t = v["table3"]; c = t["marginal_preserving_pairing_agreement_control"]
        L.append(f"| {k} | " + " | ".join(str(t["counts_dQ_dB"][x]) for x in CELLS3) +
                 f" | {cr(v['stats']['offdiag'])} | {100 * c['expected_offdiag_share_independent']:.1f} | {c['kappa']:.3f} | "
                 f"{cr(v['stats']['strict_reversal'])} ({t['strict_reversal_n']}) |")
    L.append(f"| pool (½, ¼, ¼) | " + " | ".join(f"{100 * P['table3_weighted_shares'][x]:.1f}" for x in CELLS3) +
             f" | {cr(ps['offdiag'])} | {100 * pc['expected_offdiag_share_independent']:.1f} | {pc['kappa']:.3f} | {cr(ps['strict_reversal'])} |")
    L += ["", "Margins (share of states with Δ = −1 / 0 / +1):", ""]
    for k, v in list(C.items()) + [("pool", {"table3": {"marginal_preserving_pairing_agreement_control": pc}})]:
        c = v["table3"]["marginal_preserving_pairing_agreement_control"]
        L.append(f"- {k}: Δ_Q " + " / ".join(f"{c['margins_dQ'][str(x)]:.3f}" for x in VALS) + "; Δ_B " +
                 " / ".join(f"{c['margins_dB'][str(x)]:.3f}" for x in VALS))
    L += ["", "## 4. 16 outcome patterns (bit order BB, BQ, QB, QQ; counts, pool = weighted %)", "",
          "| cell | " + " | ".join(PATTERNS) + " |", "|---|" + "---|" * 16]
    for k, v in C.items():
        L.append(f"| {k} | " + " | ".join(str(v["patterns16"]["counts"][p]) for p in PATTERNS) + " |")
    L.append("| pool (½, ¼, ¼) % | " + " | ".join(f"{100 * P['patterns16_weighted_shares'][p]:.1f}" for p in PATTERNS) + " |")
    L += ["", "## 5. Arm success rates (%, divergent states; crossed 95%)", "", "| cell | Y_BB | Y_BQ | Y_QB | Y_QQ |", "|---|---|---|---|---|"]
    for k, v in rows:
        s = v["stats"]
        L.append(f"| {k} | {cr(s['Y_BB'])} | {cr(s['Y_BQ'])} | {cr(s['Y_QB'])} | {cr(s['Y_QQ'])} |")
    L += ["", "## 6. Inclusion", ""]
    for k, v in C.items():
        L.append(f"- {k}: weight {v['prereg_weight']}; {v['n_units']} units, {v['n_divergent_states']} divergent states "
                 f"(= confirmatory {v['confirm_n_divergent']}); tasks included {v['n_tasks_included']}; structurally excluded {v['structurally_excluded_tasks'] or 'none'}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
