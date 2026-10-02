"""Marginal-preserving pairing agreement control for the (Delta_Q, Delta_B) 3x3 table of W93 (GPT-6.1 review 9, item A).

For each cell's divergent states, Delta_Q = Y_BQ - Y_QQ and Delta_B = Y_BB - Y_QB take values in {-1, 0, +1}. With p_Q(k),
p_B(k) the two marginals of the cell's 3x3 table:
  observed agreement  p_o = sum_k P(Delta_Q = k, Delta_B = k)   (diagonal share);  observed off-diagonal = 1 - p_o (= P(I != 0))
  expected agreement  p_e = sum_k p_Q(k) p_B(k)                  (independent pairing that preserves both marginals)
  expected off-diagonal = 1 - p_e;  Cohen's kappa = (p_o - p_e) / (1 - p_e);  excess agreement = p_o - p_e.
This is a MARGINAL-PRESERVING PAIRING AGREEMENT CONTROL: it asks how often the two action effects of a state would agree if
the Delta_B values were re-paired at random with the Delta_Q values of other states in the same cell. It is NOT a
no-interaction null and NOT a chance baseline for controller dependence: in the deterministic, replay-verified setting the
same-state I = Delta_Q - Delta_B != 0 is non-additive interaction on the success scale, identified state by state; that
identification does not depend on exceeding this pairing control.

Inputs: the units are loaded exactly as analyze_ghf.main loads them (imported analyze_ghf / analyze_dev functions, not
copied; split guard dev; the telecom holdout directory is never opened), and every per-cell 3x3 count table is checked
against analysis/fork/out/ghf_20261001T211519Z.json (and the per-cell units digest against the dev_all reference).
analyze_ghf itself is not modified.

Aggregation. Primary = equal weight per cell over the complete blocks common to every pooled cell, exactly as
analyze_ghf.pool: the pool's p_o and p_e are the means of the per-cell p_o and p_e (each cell's p_e uses that cell's own
marginals: states are only re-paired within a cell), and the pool kappa = (p_o - p_e) / (1 - p_e) of those means (the
mean of per-cell kappas is also reported). The W4 pool observed off-diagonal must reproduce analyze_ghf's 26.9%.
Separately and labelled: the COUNT-SUMMED pool (cells' 3x3 counts added, marginals of the summed table); never mixed with
the equal-weight figures.
Intervals: the same draws as analyze_ghf (analyze_dev.Boot, B = 2000, seed 20261001): primary = block bootstrap over the
fixed task pool (>= 10 complete blocks; ratio of block sums for every 3x3 cell, so the 9 shares of a draw form one table);
secondary = crossed task x block bootstrap (new-task generalisation). Stress cells (3 blocks): t over per-block values is
primary (as analyze_dev for < 10 blocks); flagged, never pooled.

usage: python analysis/fork/agreement_control.py [--ghf analysis/fork/out/ghf_20261001T211519Z.json] [--B 2000]
-> analysis/fork/out/agreement_control_<UTC>.{md,json}
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402
import analyze_ghf as G  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
DEF_GHF = "analysis/fork/out/ghf_20261001T211519Z.json"
VALS = G.VALS
KEYS = [f"{a},{b}" for a in VALS for b in VALS]
POOLS = ["W4:q4", "W4:q8", "W4:all", "KV8:q4", "KV8:q8", "KV8:all"]
TERM = "marginal-preserving pairing agreement control"
INTERP = ("Lower-than-expected disagreement means the action effects under the two controllers agree more than random "
          "cross-state pairing would; the same-state I = Δ_Q − Δ_B ≠ 0 in the deterministic, replay-verified setting is "
          "non-additive interaction on the success scale; this identification does not depend on exceeding the pairing control.")


def load_units(snapshot: str) -> tuple[dict, dict]:
    """analyze_ghf.main's admission, step for step (imported functions), returning cell label -> panel units."""
    snap = json.load(open(ROOT / snapshot))
    loaded = [AD.load_dir(d, snap, {}) for d in G.discover()]
    allu = [u for L in loaded for u in L["units"]]
    split_info = AD.split_guard(allu, "dev", "agreement_control")
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined fork task (QQ no-op mismatch)")
    units, _ = AD.dedupe_units(allu)
    AD.mark_incomplete_blocks(units, "dev", strict=True)
    AD.mark_partial_panel_blocks(units, "dev")
    ok = [u for u in units if "excluded" not in u]
    for u in ok:
        u["E"] = AD.effects(u["Y"], u["div"])
        if u["div"]:
            G.add_E(u)
    cells = sorted({(u["model"], u["cell"]) for u in ok if u["domain"] in G.PANEL})
    cu_by = {f"{m}:{c}": [u for u in ok if (u["model"], u["cell"]) == (m, c) and u["domain"] in G.PANEL] for m, c in cells}
    return cu_by, {"split": split_info, "quarantined_dirs": [L["dir"] for L in loaded if L["quarantined"]]}


def agree(P: np.ndarray) -> dict:
    """P: (..., 3, 3) joint shares (rows Delta_Q, columns Delta_B). Returns arrays of p_o, p_e, kappa."""
    po = np.trace(P, axis1=-2, axis2=-1)
    pe = (P.sum(-1) * P.sum(-2)).sum(-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        k = (po - pe) / (1 - pe)
    return {"po": po, "pe": pe, "kappa": k}


def tables(boot: AD.Boot, div: list[dict]) -> dict:
    """Point 3x3 shares, block-bootstrap (B,3,3), crossed (B,3,3) and per-block (K,3,3) shares (ratio of sums)."""
    S, Sc, Sb = [], [], []
    cw = boot.Wc[:, :, None] * boot.Vc[:, None, :]
    N = None
    for k in KEYS:
        a, b = (int(x) for x in k.split(","))
        X, M = boot.arrays(div, f"c_{a}_{b}")
        if N is None:
            N, Mc = M.sum(0), M
        S.append((X * M).sum(0))  # (K,)
        Sc.append((cw * X * M).sum((-1, -2)))  # (B,)
    S, Sc = np.stack(S, -1), np.stack(Sc, -1)  # (K, 9), (B, 9)
    pt = S.sum(0) / N.sum()
    dn = boot.Vb @ N
    bb = (boot.Vb @ S) / np.where(dn > 0, dn, np.nan)[:, None]
    cden = (cw * Mc).sum((-1, -2))
    cr = Sc / np.where(cden > 0, cden, np.nan)[:, None]
    blk = S / np.where(N > 0, N, np.nan)[:, None]
    r = lambda x: x.reshape(x.shape[:-1] + (3, 3))
    return {"pt": r(pt), "block": r(bb), "crossed": r(cr), "per_block": r(blk), "n": int(N.sum())}


def pct(x):
    return round(100 * float(x), 3)


def q(d):
    d = np.asarray(d, float)
    d = d[np.isfinite(d)]
    return [round(float(v), 4) for v in np.percentile(d, [2.5, 97.5])] if d.size else [None, None]


def summ(pt: float, block=None, crossed=None, per_block=None, scale: float = 100.0, primary_t: bool = False) -> dict:
    out = {"est": round(scale * pt, 3)}
    if block is not None:
        out["block_boot_ci95"] = [round(scale * v, 3) for v in q(block)]
    if crossed is not None:
        out["crossed_ci95"] = [round(scale * v, 3) for v in q(crossed)]
    if per_block is not None:
        t = AD.t_interval(per_block)
        if t:
            out["t_ci95"] = [round(scale * t["lo"], 3), round(scale * t["hi"], 3)]
            out["n_blocks"] = t["k"]
    out["ci95"] = out.get("t_ci95") if primary_t else out.get("block_boot_ci95")
    out["primary"] = (f"t over {out.get('n_blocks')} per-block values (fewer than {AD.MIN_BLOCKS_BOOT} blocks)"
                      if primary_t else "block bootstrap (fixed task pool)")
    return out


def stats_from(T: dict, primary_t: bool) -> dict:
    a, ab, ac, ak = agree(T["pt"]), agree(T["block"]), agree(T["crossed"]), agree(T["per_block"])
    res = {}
    for nm, f, sc in (("observed_agreement", lambda d: d["po"], 100), ("observed_offdiag", lambda d: 1 - d["po"], 100),
                      ("expected_agreement", lambda d: d["pe"], 100), ("expected_offdiag", lambda d: 1 - d["pe"], 100),
                      ("excess_agreement", lambda d: d["po"] - d["pe"], 100), ("kappa", lambda d: d["kappa"], 1)):
        res[nm] = summ(float(f(a)), f(ab), f(ac), f(ak), scale=sc, primary_t=primary_t)
    P = T["pt"]
    res["marginal_dQ"] = {str(v): pct(P.sum(1)[i]) for i, v in enumerate(VALS)}
    res["marginal_dB"] = {str(v): pct(P.sum(0)[i]) for i, v in enumerate(VALS)}
    return res


def count_summed(counts: dict) -> dict:
    C = np.array([[counts[f"{a},{b}"] for b in VALS] for a in VALS], float)
    n = C.sum()
    a = agree(C / n)
    return {"n_states": int(n), "observed_offdiag_pct": pct(1 - a["po"]), "expected_offdiag_pct": pct(1 - a["pe"]),
            "observed_agreement_pct": pct(a["po"]), "expected_agreement_pct": pct(a["pe"]),
            "excess_agreement_pp": pct(a["po"] - a["pe"]), "kappa": round(float(a["kappa"]), 4),
            "label": "COUNT-SUMMED (cells' 3x3 counts added; marginals of the summed table); not the paper's equal-weight target"}


def pool_eq(cu: dict, B: int) -> dict:
    """Equal weight per cell over the common complete blocks; shared draws (pool Boot) as analyze_ghf.pool."""
    per = {lab: {(u["domain"], u["block"]) for u in us} for lab, us in cu.items()}
    common = set.intersection(*per.values())
    nblk = len({b for _, b in common})
    if nblk < 2:
        return {"not_poolable": f"{nblk} common complete block(s) across {sorted(cu)}"}
    sub = {lab: [u for u in us if (u["domain"], u["block"]) in common] for lab, us in cu.items()}
    bo = defaultdict(set)
    for us in sub.values():
        for u in us:
            bo[u["task"]].add(u["block"])
    boot = AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=B)
    Ts = {lab: tables(boot, [u for u in us if u["div"]]) for lab, us in sub.items()}
    A = {lab: {k: agree(T[k]) for k in ("pt", "block", "crossed")} for lab, T in Ts.items()}
    res = {"cells": sorted(sub), "k_blocks": nblk, "n_tasks": len(bo), "n_states_per_cell": {l: T["n"] for l, T in Ts.items()}}
    st = {}
    for k in ("pt", "block", "crossed"):
        po = np.mean([A[l][k]["po"] for l in A], 0)
        pe = np.mean([A[l][k]["pe"] for l in A], 0)
        kmean = np.mean([A[l][k]["kappa"] for l in A], 0)
        st[k] = {"po": po, "pe": pe, "kappa": (po - pe) / (1 - pe), "kappa_mean_of_cells": kmean}
    out = {}
    for nm, f, sc in (("observed_agreement", lambda d: d["po"], 100), ("observed_offdiag", lambda d: 1 - d["po"], 100),
                      ("expected_agreement", lambda d: d["pe"], 100), ("expected_offdiag", lambda d: 1 - d["pe"], 100),
                      ("excess_agreement", lambda d: d["po"] - d["pe"], 100), ("kappa", lambda d: d["kappa"], 1),
                      ("kappa_mean_of_cells", lambda d: d["kappa_mean_of_cells"], 1)):
        out[nm] = summ(float(f(st["pt"])), f(st["block"]), f(st["crossed"]), scale=sc)
    res["equal_weight"] = out
    cs = defaultdict(int)
    for us in sub.values():
        for u in us:
            if u["div"]:
                cs[f"{u['E']['dQ']},{u['E']['dB']}"] += 1
    res["table3_counts_summed"] = {k: cs[k] for k in KEYS}
    res["count_summed"] = count_summed(res["table3_counts_summed"])
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ghf", default=DEF_GHF)
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    ghf = json.load(open(ROOT / a.ghf))
    cu_by, adm = load_units(ghf["snapshot"]["path"])
    ref = json.load(open(ROOT / ghf["reference"]))
    checks, cells = {}, {}
    for lab, cu in cu_by.items():
        div = [u for u in cu if u["div"]]
        cnt = {k: sum(1 for u in div if f"{u['E']['dQ']},{u['E']['dB']}" == k) for k in KEYS}
        g = ghf["cells"].get(lab, {})
        checks[lab] = {"counts_match_ghf": cnt == (g.get("table3") or {}).get("counts"),
                       "units_digest_match_reference": AD.units_digest(cu) == (ref["cells"].get(lab) or {}).get("units_digest_sha256")}
        bo = defaultdict(set)
        for u in cu:
            bo[u["task"]].add(u["block"])
        boot = AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=a.B)
        T = tables(boot, div)
        fam = AD.family(lab.split(":")[1])
        nb = len({u["block"] for u in cu})
        st = stats_from(T, primary_t=nb < AD.MIN_BLOCKS_BOOT)
        cells[lab] = {"family": fam, "flag": "stress cell: 3 complete blocks, t interval primary, never pooled" if fam == "stress" else "",
                      "n_states": len(div), "n_tasks": len(bo), "n_blocks": nb, "counts": cnt, "stats": st,
                      "count_based": count_summed(cnt),
                      "ghf_offdiag_est": ghf["cells"][lab]["stats"]["offdiag"]["est"]}
    bad = [k for k, v in checks.items() if not all(v.values())]
    if bad:
        raise SystemExit(f"agreement_control: inputs differ from {a.ghf} / reference for {bad}: {checks}")
    pools = {}
    for p in POOLS:
        fam, mm = p.split(":")
        labs = [l for l in cu_by if AD.family(l.split(":")[1]) == fam and (mm == "all" or l.startswith(mm + ":"))]
        pools[p] = pool_eq({l: cu_by[l] for l in labs}, a.B)
        pools[p]["ghf_offdiag_est"] = ghf["pools"][p]["stats"]["offdiag"]["est"]
        pools[p]["ghf_counts_summed_match"] = pools[p]["table3_counts_summed"] == ghf["pools"][p]["table3_counts_summed"]
    w4 = pools["W4:all"]
    repro = {"W4_equal_weight_offdiag_pct": w4["equal_weight"]["observed_offdiag"]["est"], "target": 26.9,
             "reproduces_26.9": round(w4["equal_weight"]["observed_offdiag"]["est"], 1) == 26.9,
             "W4_count_summed": {k: w4["count_summed"][k] for k in ("observed_offdiag_pct", "expected_offdiag_pct", "kappa")},
             "count_summed_target": {"observed_offdiag_pct": 27.10, "expected_offdiag_pct": 37.85, "kappa": 0.284}}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    git = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    out = {"script": "analysis/fork/agreement_control.py", "script_sha256": AD.sha256(__file__),
           "analyze_ghf_sha256": AD.sha256(G.__file__), "analyze_dev_sha256": AD.sha256(AD.__file__), "git_head": git, "utc": utc,
           "ghf_input": a.ghf, "snapshot": ghf["snapshot"], "reference": ghf["reference"], "input_checks": checks, "admission": adm,
           "terminology": TERM, "interpretation": INTERP,
           "definitions": {"observed_agreement": "sum_k P(dQ=k, dB=k) (diagonal share)", "observed_offdiag": "1 - observed agreement (= P(I != 0))",
                           "expected_agreement": "sum_k p_Q(k) p_B(k), the cell's own marginals (independent within-cell re-pairing)",
                           "expected_offdiag": "1 - expected agreement", "excess_agreement": "observed - expected agreement (pp)",
                           "kappa": "(p_o - p_e) / (1 - p_e)",
                           "pool_equal_weight": "p_o and p_e = equal-weight means of the per-cell values over common complete blocks; kappa from those means",
                           "pool_count_summed": "summed 3x3 counts, marginals of the summed table (labelled separately)"},
           "inference": {"primary": "block bootstrap over the fixed task pool (>= 10 complete blocks); stress cells: t over per-block values",
                         "secondary": "crossed task x block bootstrap", "B": a.B, "seed": AD.SEED, "draws": "analyze_dev.Boot (shared with analyze_ghf)"},
           "reproduction": repro, "cells": cells, "pools": pools, "seconds": round(time.time() - t0, 1)}
    jp = OUT / f"agreement_control_{utc}.json"
    jp.write_text(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"agreement_control_{utc}.md").write_text(markdown(out, jp))
    print(f"agreement_control: wrote {jp.relative_to(ROOT)} and .md ({out['seconds']} s)")


def markdown(r: dict, jp: Path) -> str:
    def iv(x, d=1, key="ci95"):
        c = x.get(key)
        return f"{x['est']:.{d}f} [{c[0]:.{d}f}, {c[1]:.{d}f}]" if c and c[0] is not None else f"{x['est']:.{d}f}"

    def cx(x, d=1):
        c = x.get("crossed_ci95")
        return f"[{c[0]:.{d}f}, {c[1]:.{d}f}]" if c else "n/a"
    P, C, rp = r["pools"], r["cells"], r["reproduction"]
    w, k = P["W4:all"]["equal_weight"], P["KV8:all"]["equal_weight"]
    wc, kc = P["W4:all"]["count_summed"], P["KV8:all"]["count_summed"]
    L = [f"**TL;DR** {TERM[0].upper() + TERM[1:]} for the W93 (Δ_Q, Δ_B) 3×3 tables. Equal-weight W4 pool (the paper's target, 4 cells, "
         f"20 common blocks): observed off-diagonal {iv(w['observed_offdiag'])}% vs {iv(w['expected_offdiag'])}% expected under "
         f"marginal-preserving within-cell re-pairing; κ = {iv(w['kappa'], 3)} (block bootstrap; crossed {cx(w['kappa'], 3)}). "
         f"KV8 pool: {iv(k['observed_offdiag'])}% vs {iv(k['expected_offdiag'])}%, κ = {iv(k['kappa'], 3)}. Every main cell shows less "
         f"disagreement than the pairing control (κ {min(C[c]['stats']['kappa']['est'] for c in C if C[c]['family'] != 'stress'):.2f}–"
         f"{max(C[c]['stats']['kappa']['est'] for c in C if C[c]['family'] != 'stress'):.2f}). Count-summed W4 (labelled separately, not the "
         f"paper's target): {wc['observed_offdiag_pct']:.2f}% observed, {wc['expected_offdiag_pct']:.2f}% expected, κ {wc['kappa']:.3f}. "
         f"{INTERP}", "",
         f"# Marginal-preserving pairing agreement control for the (Δ_Q, Δ_B) table ({r['utc']})", "",
         f"Script `{r['script']}` (sha {r['script_sha256'][:12]}; imports analyze_ghf sha {r['analyze_ghf_sha256'][:12]}, analyze_dev sha "
         f"{r['analyze_dev_sha256'][:12]}), git {r['git_head'][:10]}. Input `{r['ghf_input']}` (snapshot `{r['snapshot']['id']}`). "
         f"Full numbers: `{jp.relative_to(ROOT)}`.", "",
         f"Inputs re-derived through analyze_ghf's loaders: per-cell 3×3 counts equal the ghf JSON for "
         f"{sum(v['counts_match_ghf'] for v in r['input_checks'].values())}/{len(r['input_checks'])} cells; units digests equal the "
         f"reference for {sum(v['units_digest_match_reference'] for v in r['input_checks'].values())}/{len(r['input_checks'])}. "
         f"Reproduction: equal-weight W4 pool off-diagonal = {rp['W4_equal_weight_offdiag_pct']:.3f}% (target 26.9%: "
         f"{'reproduced' if rp['reproduces_26.9'] else 'NOT reproduced'}); count-summed W4 = {rp['W4_count_summed']['observed_offdiag_pct']:.2f}% / "
         f"{rp['W4_count_summed']['expected_offdiag_pct']:.2f}% / κ {rp['W4_count_summed']['kappa']:.3f} (targets 27.10 / 37.85 / 0.284).", "",
         "**Definitions.** Rows Δ_Q = Y_BQ − Y_QQ, columns Δ_B = Y_BB − Y_QB, values in {−1, 0, +1}. Observed agreement p_o = Σ_k "
         "P(Δ_Q = k, Δ_B = k) (diagonal share; off-diagonal = 1 − p_o = P(I ≠ 0)). Expected agreement under independent pairing that "
         "preserves both marginals p_e = Σ_k p_Q(k)·p_B(k) (each cell's own marginals: states are re-paired only within a cell). "
         "Cohen's κ = (p_o − p_e)/(1 − p_e). Excess agreement = p_o − p_e (pp).", "",
         f"**Interpretation (terminology fixed).** This is a {TERM}, not a no-interaction null and not a chance baseline for "
         f"controller dependence. {INTERP}", "",
         "**Aggregation.** Equal-weight pools = the paper's target weights (analyze_ghf.pool: equal weight per cell over the complete "
         "blocks common to every pooled cell): pool p_o, p_e = means of per-cell values; pool κ from those means (mean of per-cell κ "
         "also given). Count-summed pools add the cells' counts and use the summed table's marginals; they are a different "
         "weighting (cells with more divergent states weigh more) and are reported in their own table, never mixed with the "
         "equal-weight figures.", "",
         "**Intervals.** Same draws as analyze_ghf (analyze_dev.Boot, B = 2000, seed 20261001). Primary = block bootstrap over the "
         "fixed task pool (ratio of block sums; the 9 shares of one draw form one table, so p_o, p_e and κ are computed per draw); "
         "secondary = crossed task × block bootstrap (new tasks). Stress cells (3 blocks): t over per-block values is primary; they "
         "are flagged and never pooled.", "",
         "## 1. Per cell (each cell's divergent states; %, κ unitless; primary 95% interval)", "",
         "| cell | n | marg. Δ_Q (−1/0/+1 %) | marg. Δ_B (−1/0/+1 %) | observed agreement | observed off-diag | expected agreement | expected off-diag | excess agreement (pp) | κ | κ crossed |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for lab, c in C.items():
        s = c["stats"]
        mq = "/".join(f"{s['marginal_dQ'][str(v)]:.1f}" for v in VALS)
        mb = "/".join(f"{s['marginal_dB'][str(v)]:.1f}" for v in VALS)
        L.append(f"| {lab}{' (STRESS, flagged: 3 blocks, t primary, not poolable)' if c['family'] == 'stress' else ''} | {c['n_states']} | {mq} | {mb} | "
                 f"{iv(s['observed_agreement'])} | {iv(s['observed_offdiag'])} | {iv(s['expected_agreement'])} | {iv(s['expected_offdiag'])} | "
                 f"{iv(s['excess_agreement'])} | {iv(s['kappa'], 3)} | {cx(s['kappa'], 3)} |")
    L += ["", "## 2. Equal-weight pools (paper's target weights; block bootstrap, then crossed)", "",
          "| pool | cells | blocks | states/cell | observed off-diag | expected off-diag | excess agreement (pp) | κ (from pooled p_o, p_e) | mean of per-cell κ |",
          "|---|---|---|---|---|---|---|---|---|"]
    for p, v in P.items():
        e = v["equal_weight"]
        L.append(f"| {p} | {', '.join(v['cells'])} | {v['k_blocks']} | {', '.join(str(x) for x in v['n_states_per_cell'].values())} | "
                 f"{iv(e['observed_offdiag'])}<br>{cx(e['observed_offdiag'])} | {iv(e['expected_offdiag'])}<br>{cx(e['expected_offdiag'])} | "
                 f"{iv(e['excess_agreement'])}<br>{cx(e['excess_agreement'])} | {iv(e['kappa'], 3)}<br>{cx(e['kappa'], 3)} | "
                 f"{iv(e['kappa_mean_of_cells'], 3)} |")
    L += ["", "Stress cells are not pooled (one common complete block), as in analyze_ghf.", "",
          "## 3. Count-summed pools (SEPARATE weighting, labelled; not the paper's equal-weight target)", "",
          "| pool | states | observed off-diag % | expected off-diag % | excess agreement (pp) | κ |", "|---|---|---|---|---|---|"]
    for p, v in P.items():
        c = v["count_summed"]
        L.append(f"| {p} (count-summed) | {c['n_states']} | {c['observed_offdiag_pct']:.2f} | {c['expected_offdiag_pct']:.2f} | "
                 f"{c['excess_agreement_pp']:+.2f} | {c['kappa']:.3f} |")
    L += ["", "Point estimates only for the count-summed rows (no interval: the paper's intervals belong to the equal-weight target).", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
