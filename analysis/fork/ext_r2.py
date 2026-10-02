"""R2 on the external environments (BFCL multi-turn, ALFWorld): W93 estimands recomputed from the raw four-arm outcomes.

SUPPLEMENTARY AND EXPLORATORY. No LLM user simulator is involved in these environments. Post hoc; not pre-registered.

Estimands (success scale throughout, Y in {0,1}; analysis/fork/analyze_ghf.py notation), on each cell's divergent states:
  G = Y_BQ - Y_QQ, H = Y_QB - Y_QQ, F = Y_BB - Y_QQ; paired differences G - H = Y_BQ - Y_QB, F - G = Y_BB - Y_BQ,
  F - H = Y_BB - Y_QB; Delta_Q = Y_BQ - Y_QQ, Delta_B = Y_BB - Y_QB, I = Delta_Q - Delta_B; the 3x3 table of
  (Delta_Q, Delta_B); off-diagonal share P(Delta_Q != Delta_B); strict reversals P(Delta_Q * Delta_B < 0); the 16 outcome
  patterns in bit order BB, BQ, QB, QQ. Everything is recomputed here from the raw Y of the branch files and the original
  episode (Y_QQ); the A/C/I columns of the older ext_* outputs (loss scale) are not used.
Marginal-preserving pairing agreement control (not a null for interaction): with the 3x3 margins p_Q(a), p_B(a), the
  expected diagonal share under independent pairing is p_e = sum_a p_Q(a) p_B(a); expected off-diagonal = 1 - p_e;
  kappa = (p_o - p_e) / (1 - p_e) with p_o the observed diagonal share.

Inclusion (identical to analysis/fork/analyze_ext.py, whose load_dir and StratBoot are imported, not copied): task
  directories under analysis/fork/ext/dev; a directory whose QQ no-op sample mismatched (QUARANTINE file or
  dev_summary.qq_noop_ok) is dropped whole; excluded items (search exclusion, branch error/missing, state/original mismatch)
  leave the denominator; a divergent state enters only with all three B-involving branches present (four arms).
Unit = item (ALFWorld game, BFCL entry; one run per item and cell). Denominator = the cell's divergent states (ratio).
Intervals: percentile bootstrap, B = 2000, seed 20261001, items resampled with replacement within stratum (environment x
  category: alfworld; bfcl_base / bfcl_miss_param / bfcl_miss_func / bfcl_long_context), draws shared by all cells; ratio
  of resampled sums over divergent items. Item sampling only (there is no block structure).
Pools: equal weight per cell, families never mixed (W4 = gptq_w4_d1 + awq_w4_d1; stress = gptq_w3 + kvq_int4), per
  environment and across environments, as analyze_ext.

usage: python analysis/fork/ext_r2.py [--B 2000] -> analysis/fork/out/ext_r2_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/fork/out"
_spec = importlib.util.spec_from_file_location("analyze_ext", ROOT / "analysis/fork/analyze_ext.py")
AE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AE)
AD = AE.AD
VALS = (-1, 0, 1)
PATTERNS = [f"{i:04b}" for i in range(16)]  # bit order BB, BQ, QB, QQ
RATIOS = ["G", "H", "F", "GmH", "FmG", "FmH", "I", "offdiag", "strict_reversal", "Y_BB", "Y_BQ", "Y_QB", "Y_QQ"]
LABEL = "SUPPLEMENTARY, EXPLORATORY (post hoc; external environments without a user simulator)"
PAPER_COVERAGE = {  # paper/latex/sections/appendix.tex tab:coverage, column "BFCL / ALFWorld" (items, states) as printed
    "bfcl:q4:gptq_w4_d1": (788, 573), "bfcl:q4:awq_w4_d1": (788, 642), "bfcl:q8:gptq_w4_d1": (788, 533),
    "bfcl:q8:awq_w4_d1": (788, 548), "bfcl:q4:gptq_w3": (788, 720), "bfcl:q8:gptq_w3": (788, 696),
    "bfcl:q4:kvq_int4": (788, 787), "bfcl:q8:kvq_int4": (788, 788),
    "alfworld:q8:gptq_w4_d1": (134, 115), "alfworld:q8:awq_w4_d1": (134, 119), "alfworld:q8:gptq_w3": (134, 130),
    "alfworld:q8:kvq_int4": (134, 134),
}


def r2_effects(Y: dict) -> dict:
    dq, db = Y["BQ"] - Y["QQ"], Y["BB"] - Y["QB"]
    E = {"G": Y["BQ"] - Y["QQ"], "H": Y["QB"] - Y["QQ"], "F": Y["BB"] - Y["QQ"], "GmH": Y["BQ"] - Y["QB"],
         "FmG": Y["BB"] - Y["BQ"], "FmH": Y["BB"] - Y["QB"], "dQ": dq, "dB": db, "I": dq - db, "offdiag": int(dq != db),
         "strict_reversal": int(dq * db < 0), "pattern": f"{Y['BB']}{Y['BQ']}{Y['QB']}{Y['QQ']}",
         **{f"Y_{k}": Y[k] for k in ("BB", "BQ", "QB", "QQ")}}
    assert E["GmH"] == E["G"] - E["H"] and E["FmG"] == E["F"] - E["G"] and E["FmH"] == E["F"] - E["H"]
    return E


def table3(div: list[dict]) -> dict:
    n = len(div)
    cnt = {f"{a},{b}": sum(1 for u in div if u["E"]["dQ"] == a and u["E"]["dB"] == b) for a in VALS for b in VALS}
    diag = sum(cnt[f"{a},{a}"] for a in VALS)
    pQ = {a: sum(cnt[f"{a},{b}"] for b in VALS) / n for a in VALS} if n else {}
    pB = {b: sum(cnt[f"{a},{b}"] for a in VALS) / n for b in VALS} if n else {}
    ctrl = None
    if n:
        po = diag / n
        pe = sum(pQ[a] * pB[a] for a in VALS)
        ctrl = {"observed_diagonal_share": po, "observed_offdiag_share": 1 - po, "expected_diagonal_share_independent": pe,
                "expected_offdiag_share_independent": 1 - pe, "kappa": (po - pe) / (1 - pe) if pe < 1 else None,
                "margins_dQ": {str(a): pQ[a] for a in VALS}, "margins_dB": {str(b): pB[b] for b in VALS}}
    return {"n": n, "counts_dQ_dB": cnt, "diagonal_n": diag, "offdiag_n": n - diag,
            "strict_reversal_n": cnt["1,-1"] + cnt["-1,1"],
            "I_dist": {str(v): sum(1 for u in div if u["E"]["I"] == v) for v in (-2, -1, 0, 1, 2)},
            "marginal_preserving_pairing_agreement_control": ctrl}


def patterns16(div: list[dict]) -> dict:
    n = len(div)
    c = {p: sum(1 for u in div if u["E"]["pattern"] == p) for p in PATTERNS}
    return {"n": n, "bit_order": "BB,BQ,QB,QQ", "counts": c, "shares": {p: (v / n if n else None) for p, v in c.items()}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    a = ap.parse_args()
    t0 = time.time()
    dirs = sorted(p for p in AE.DEV.glob("*") if p.is_dir())
    loaded = [AE.load_dir(d) for d in dirs]
    done = [L for L in loaded if not L["incomplete"]]
    quarantined = [L["dir"] for L in done if L["quarantined"]]
    q_units = [u for L in done if L["quarantined"] for u in L["units"]]
    units = [u for L in done if not L["quarantined"] for u in L["units"]]
    excluded = [u for u in units if "excluded" in u]
    ok = [u for u in units if "excluded" not in u]
    for u in ok:
        if u["div"]:
            u["E"] = r2_effects(u["Y"])
            assert AD.effects(u["Y"], True)["G"] == u["E"]["G"]
    strata: dict = defaultdict(set)
    for u in ok:
        strata[u["stratum"]].add(u["task"])
    boot = AE.StratBoot({s: sorted(v) for s, v in strata.items()}, B=a.B)
    draws: dict = {}
    cells: dict = {}
    for env in sorted({u["env"] for u in ok}):
        for cell in sorted({u["cell"] for u in ok if u["env"] == env}):
            lab = f"{env}:{cell}"
            cu = [u for u in ok if u["env"] == env and u["cell"] == cell]
            div = [u for u in cu if u["div"]]
            ex = defaultdict(int)
            for u in excluded:
                if u["env"] == env and u["cell"] == cell:
                    ex[u["excluded"].split(":")[0] if u["excluded"].startswith("search") else u["excluded"]] += 1
            qn = sum(1 for u in q_units if u["env"] == env and u["cell"] == cell)
            qdiv = sum(1 for u in q_units if u["env"] == env and u["cell"] == cell and u.get("div"))
            r = {"family": AE.family(cell.split(":")[1]),
                 "coverage": {"items_searched_incl_quarantined": len(cu) + sum(ex.values()) + qn, "items_quarantined": qn,
                              "states_quarantined": qdiv, "items_excluded": dict(ex), "items_analysed": len(cu),
                              "divergent_states_four_arms": len(div), "divergence_rate": len(div) / len(cu) if cu else None,
                              "categories": {s: [sum(1 for u in cu if u["stratum"] == s), sum(1 for u in div if u["stratum"] == s)]
                                             for s in sorted({u["stratum"] for u in cu})}},
                 "pp_on_divergent": {}}
            if div:
                for s in RATIOS:
                    pt, dr = boot.mean(*boot.arrays(div, s))
                    draws.setdefault(lab, {})[s] = (pt, dr)
                    r["pp_on_divergent"][s] = AD.summarise(pt, dr)
                r["table3"] = table3(div)
                r["patterns16"] = patterns16(div)
            pc = PAPER_COVERAGE.get(lab)
            r["paper_tab_coverage"] = {"printed_items_states": pc, "recomputed_items_states": (len(cu), len(div)),
                                       "matches": bool(pc == (len(cu), len(div)))} if pc else None
            cells[lab] = r
    pools = {}
    for fam in AE.FAMILIES:
        fl = [l for l in cells if cells[l]["family"] == fam and l in draws]
        for name, labs in [(f"{fam}:{e}", [l for l in fl if l.startswith(e + ":")]) for e in ("alfworld", "bfcl")] + [(f"{fam}:all_envs", fl)]:
            if labs:
                pools[name + ":pooled_equal_weight"] = {"cells": labs, "pp_on_divergent": {
                    s: AD.summarise(float(np.mean([draws[l][s][0] for l in labs])), np.mean([draws[l][s][1] for l in labs], axis=0))
                    for s in RATIOS}}
    files = {k: v for L in done for k, v in L["files"].items()}
    res = {"label": LABEL, "analysis": "analysis/fork/ext_r2.py",
           "script": {"sha256": AE.sha256(__file__), "analyze_ext_sha256": AE.sha256(ROOT / "analysis/fork/analyze_ext.py"),
                      "analyze_dev_sha256": AE.sha256(ROOT / "analysis/fork/analyze_dev.py"),
                      "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "scale": "success (Y=1 success); recomputed from raw Y",
           "bootstrap": {"B": a.B, "seed": AD.SEED, "scheme": "items with replacement within stratum (env x category); ratio over divergent items; draws shared by all cells", "level": "95% percentile"},
           "input_dirs": [L["dir"] for L in done], "incomplete_dirs": [L["dir"] for L in loaded if L["incomplete"]],
           "quarantined_dirs": quarantined, "noop_sample": {L["dir"]: L.get("noop") for L in done},
           "excluded_by_reason": dict(sorted(defaultdict(int, {k: sum(1 for u in excluded if (u["excluded"].split(":")[0] if u["excluded"].startswith("search") else u["excluded"]) == k)
                                                               for k in {(u["excluded"].split(":")[0] if u["excluded"].startswith("search") else u["excluded"]) for u in excluded}}).items())),
           "cells": cells, "pooled": pools,
           "coverage_discrepancies_vs_paper": [{"cell": l, "paper": v["paper_tab_coverage"]["printed_items_states"],
                                                "recomputed": v["paper_tab_coverage"]["recomputed_items_states"]}
                                               for l, v in cells.items() if v["paper_tab_coverage"] and not v["paper_tab_coverage"]["matches"]],
           "n_input_files": len(files), "input_files_digest_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
    res["seconds"] = round(time.time() - t0, 1)
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / f"ext_r2_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"ext_r2_{utc}.md").write_text(markdown(res, jp))
    print(f"ext_r2: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


def markdown(res: dict, jp: Path) -> str:
    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]" if x else "n/a"

    def r(x):
        return f"{x['est']:.1f} [{x['ci95'][0]:.1f}, {x['ci95'][1]:.1f}]" if x else "n/a"
    C = res["cells"]
    tl = "; ".join(f"{k} ({v['coverage']['divergent_states_four_arms']} st): G {v['pp_on_divergent']['G']['est']:+.1f}, "
                   f"H {v['pp_on_divergent']['H']['est']:+.1f}, F {v['pp_on_divergent']['F']['est']:+.1f}, "
                   f"G-H {f(v['pp_on_divergent']['GmH'])}, off-diag {v['pp_on_divergent']['offdiag']['est']:.1f}%, "
                   f"reversals {v['table3']['strict_reversal_n']}" for k, v in C.items() if "table3" in v)
    disc = "; ".join(f"{d['cell']} paper {d['paper'][0]} items / {d['paper'][1]} st vs recomputed {d['recomputed'][0]} / {d['recomputed'][1]}"
                     for d in res["coverage_discrepancies_vs_paper"]) or "none"
    L = [f"**TL;DR** {res['label']}. W93 R2 estimands on the success scale, recomputed from raw four-arm Y, per cell on divergent "
         f"states (pp; 95% item bootstrap within env x category; G here is conditional on divergence, unlike G_all of ext_*): {tl}. "
         f"Coverage-table (tab:coverage) discrepancies: {disc}. KV4 cells: Y_QQ = 0 on every state (and Y_BQ ~ 0), so Δ_Q is "
         f"(almost) constant, their off-diagonal mass is H, and κ is degenerate (≈ 0 by construction).", "",
         f"> **{res['label']}.** Not part of any pre-registered analysis. Item-level inference only (one run per item).", "",
         f"Source: `{jp.relative_to(ROOT)}`; script sha `{res['script']['sha256'][:12]}`, analyze_ext sha "
         f"`{res['script']['analyze_ext_sha256'][:12]}`, git `{res['script']['git_head'][:10]}`. Inclusion = analyze_ext (imported "
         f"load_dir/StratBoot). Quarantined (dropped whole): {res['quarantined_dirs'] or 'none'}. Incomplete: "
         f"{len(res['incomplete_dirs'])}. Excluded items by reason: {res['excluded_by_reason'] or 'none'}.", "",
         "Notation: G = Y_BQ−Y_QQ, H = Y_QB−Y_QQ, F = Y_BB−Y_QQ; Δ_Q = G, Δ_B = Y_BB−Y_QB, I = Δ_Q−Δ_B; off-diag = P(Δ_Q ≠ Δ_B); "
         "strict reversal = Δ_Q·Δ_B < 0. Bootstrap: B = 2000, seed 20261001, items resampled within stratum (alfworld; "
         "bfcl_base/miss_param/miss_func/long_context), ratio over divergent items.", "",
         "## 1. Inclusion counts", "",
         "| cell | items searched (incl. quarantined) | quarantined items / states | excluded | items analysed | divergent states (4 arms) | paper tab:coverage | match |",
         "|---|---|---|---|---|---|---|---|"]
    for k, v in C.items():
        c, p = v["coverage"], v["paper_tab_coverage"]
        L.append(f"| {k} | {c['items_searched_incl_quarantined']} | {c['items_quarantined']} / {c['states_quarantined']} | "
                 f"{c['items_excluded'] or 0} | {c['items_analysed']} | {c['divergent_states_four_arms']} | "
                 f"{p['printed_items_states'][0]} · {p['printed_items_states'][1]} st | {'yes' if p['matches'] else '**NO**'} |")
    L += ["", "## 2. G, H, F and paired differences (pp, divergent states)", "",
          "| cell | n st | G | H | F | G−H | F−G | F−H | I |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in C.items():
        e = v["pp_on_divergent"]
        L.append(f"| {k} | {v['coverage']['divergent_states_four_arms']} | {f(e['G'])} | {f(e['H'])} | {f(e['F'])} | {f(e['GmH'])} | "
                 f"{f(e['FmG'])} | {f(e['FmH'])} | {f(e['I'])} |")
    L += ["", "## 3. Δ_Q × Δ_B table, off-diagonal share, strict reversals, marginal-preserving pairing agreement control", "",
          "Counts `(Δ_Q, Δ_B)`. The control is the off-diagonal share expected if Δ_Q and Δ_B were paired independently with "
          "their observed margins, and κ; it is a marginal-preserving pairing agreement control, not a null for interaction.", "",
          "| cell | (−1,−1) | (−1,0) | (−1,1) | (0,−1) | (0,0) | (0,1) | (1,−1) | (1,0) | (1,1) | off-diag % [95%] | expected off-diag % | κ | strict reversals % [95%] (n) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in C.items():
        t = v["table3"]
        ct = t["marginal_preserving_pairing_agreement_control"]
        kap = f"{ct['kappa']:.3f}" if ct["kappa"] is not None else "n/a"
        L.append(f"| {k} | " + " | ".join(str(t["counts_dQ_dB"][f"{a},{b}"]) for a in VALS for b in VALS) +
                 f" | {r(v['pp_on_divergent']['offdiag'])} | {100 * ct['expected_offdiag_share_independent']:.1f} | {kap} | "
                 f"{r(v['pp_on_divergent']['strict_reversal'])} ({t['strict_reversal_n']}) |")
    L += ["", "## 4. 16 outcome patterns (counts; bit order BB, BQ, QB, QQ)", "",
          "| cell | " + " | ".join(PATTERNS) + " |", "|---|" + "---|" * 16]
    for k, v in C.items():
        L.append(f"| {k} | " + " | ".join(str(v["patterns16"]["counts"][p]) for p in PATTERNS) + " |")
    L += ["", "## 5. Arm success rates (%, divergent states)", "", "| cell | Y_BB | Y_BQ | Y_QB | Y_QQ |", "|---|---|---|---|---|"]
    for k, v in C.items():
        e = v["pp_on_divergent"]
        L.append(f"| {k} | {r(e['Y_BB'])} | {r(e['Y_BQ'])} | {r(e['Y_QB'])} | {r(e['Y_QQ'])} |")
    L += ["", "## 6. Pools (equal weight per cell; W4 and stress never mixed; descriptive)", "",
          "| pool | cells | G | H | F | G−H | off-diag % | strict reversals % |", "|---|---|---|---|---|---|---|---|"]
    for k, v in res["pooled"].items():
        e = v["pp_on_divergent"]
        L.append(f"| {k} | {len(v['cells'])} | {f(e['G'])} | {f(e['H'])} | {f(e['F'])} | {f(e['GmH'])} | {r(e['offdiag'])} | {r(e['strict_reversal'])} |")
    L += ["", "## 7. Coverage per category (items analysed, divergent states)", ""]
    for k, v in C.items():
        L.append(f"- {k}: " + "; ".join(f"{s} {x[0]}/{x[1]}" for s, x in v["coverage"]["categories"].items()))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
