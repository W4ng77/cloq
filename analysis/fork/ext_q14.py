"""W99h: q14 (Qwen3-14B) BFCL multi-turn four-arm fork, GPTQ-W4 d1, compared with q4/q8 (protocol fork-ext-v1).

WITHIN-QWEN-FAMILY SCALE SENSITIVITY CHECK; SINGLE CONFIGURATION (GPTQ-W4 d1); NOT SECOND-FAMILY EVIDENCE; EXPLORATORY.

Pipeline = the existing ext pipeline, imported, not copied:
  admission  analysis/fork/analyze_ext.py load_dir (quarantine of a task directory whose QQ no-op sample mismatched; items
             excluded by search exclusion / branch error / branch missing / state-original mismatch leave the denominator;
             non-divergent items enter with four equal arms); G_all, r/d/M via analyze_ext.analyse (analyze_dev.effects);
  R2         analysis/fork/ext_r2.py r2_effects / table3 / patterns16 on divergent states: G, H, F, the paired differences
             G-H, F-G, F-H, I, the (dQ, dB) 3x3, the 16 patterns, the off-diagonal share, strict reversals and the
             marginal-preserving pairing agreement control (kappa; not a null for interaction).
Bootstrap: analyze_ext.StratBoot, B = 2000, seed 20261001, items within stratum (bfcl category), draws shared by all cells.
Cells: bfcl:{q4,q8,q14}:gptq_w4_d1 (only these directories are read; nothing is pooled with the paper's W4 pool here).
Common task panel: the items analysed (not excluded) in all three cells. Each model selects its own divergent states on
it, so the cross-model comparison is DESCRIPTIVE (different state sets, different t*, different base rates).
Also reported (not used for admission, as in the existing pipeline): the per-state replay-consistency flag of the dev
forks (effects.jsonl "replay"), divergence types, and failure types (termination reason / official error type of
failing arms on divergent states).

usage: python analysis/fork/ext_q14.py [--B 2000] -> analysis/fork/out/ext_q14_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/fork/out"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R2 = _load("ext_r2", "analysis/fork/ext_r2.py")
AE, AD = R2.AE, R2.AE.AD
MODELS = ("q4", "q8", "q14")
CATS = ("base", "miss_param", "miss_func", "long_context")
LABEL = ("within-Qwen-family scale sensitivity check; single configuration (GPTQ-W4 d1); not second-family evidence; "
         "exploratory")


def r2_block(div, boot):
    r = {"n": len(div), "pp_on_divergent": {}}
    if div:
        for s in R2.RATIOS:
            r["pp_on_divergent"][s] = AD.summarise(*boot.mean(*boot.arrays(div, s)))
        r["table3"] = R2.table3(div)
        r["patterns16"] = R2.patterns16(div)
    return r


def failure_types(d: Path, div_units) -> dict:
    term, err = defaultdict(Counter), defaultdict(Counter)
    for u in div_units:
        br = json.loads((d / "branches" / f"{u['state_id']}.json").read_text()) if (d / "branches" / f"{u['state_id']}.json").exists() else {}
        st = json.loads((d / "states" / f"{u['state_id']}.json").read_text())
        arms = {b: br[b] for b in ("BB", "BQ", "QB") if b in br}
        arms["QQ"] = st["orig"]
        for b, o in arms.items():
            if not o.get("reward"):
                term[b][o.get("termination_reason") or "?"] += 1
                err[b][o.get("error_type") or "none"] += 1
    return {"termination_reason_of_failing_arms": {b: dict(c) for b, c in term.items()},
            "official_error_type_of_failing_arms": {b: dict(c.most_common()) for b, c in err.items()}}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    a = ap.parse_args()
    t0 = time.time()
    dirs = {m: [AE.DEV / f"bfcl_{m}_gptq_w4_d1_{c}" for c in CATS] for m in MODELS}
    loaded = {m: [AE.load_dir(d) for d in ds if d.is_dir()] for m, ds in dirs.items()}
    task_status = {}
    for m in MODELS:
        for c, d in zip(CATS, dirs[m]):
            L = next((x for x in loaded[m] if x["dir"].endswith(d.name)), None)
            ds = json.loads((d / "dev_summary.json").read_text()) if (d / "dev_summary.json").exists() else {}
            task_status[d.name] = {"present": L is not None, "incomplete": bool(L and L["incomplete"]), "quarantined": bool(L and L["quarantined"]),
                                   "qq_noop_ok": ds.get("qq_noop_ok"), "n_items": ds.get("n_items"), "n_states": ds.get("n_states"),
                                   "replay_ok_states": ds.get("replay_ok"), "n_excluded_search": ds.get("n_excluded")}
    units, excluded, qunits = {}, {}, {}
    for m in MODELS:
        done = [L for L in loaded[m] if not L["incomplete"]]
        qunits[m] = [u for L in done if L["quarantined"] for u in L["units"]]
        us = [u for L in done if not L["quarantined"] for u in L["units"]]
        excluded[m] = [u for u in us if "excluded" in u]
        units[m] = [u for u in us if "excluded" not in u]
        for u in units[m]:
            u["E"] = AD.effects(u["Y"], u.get("div", True))
            if u["div"]:
                u["E"].update(R2.r2_effects(u["Y"]))
                assert u["E"]["G"] == AD.effects(u["Y"], True)["G"]
    strata = defaultdict(set)
    for m in MODELS:
        for u in units[m]:
            strata[u["stratum"]].add(u["task"])
    if not strata:
        print("ext_q14: no complete directories")
        return
    boot = AE.StratBoot({s: sorted(v) for s, v in strata.items()}, B=a.B)
    replay_flag = {}
    for m in MODELS:
        for d in dirs[m]:
            if (d / "effects.jsonl").exists():
                for l in (d / "effects.jsonl").read_text().splitlines():
                    if l.strip():
                        e = json.loads(l)
                        replay_flag[(m, e["state_id"])] = bool(e.get("replay"))
    cells = {}
    for m in MODELS:
        cu = units[m]
        if not cu:
            cells[m] = {"present": False}
            continue
        div = [u for u in cu if u["div"]]
        ex = Counter((u["excluded"].split(":")[0] if u["excluded"].startswith("search") else u["excluded"]) for u in excluded[m])
        g = AE.analyse(cu, boot)
        ft = {}
        for c, d in zip(CATS, dirs[m]):
            sub = [u for u in div if u["stratum"] == f"bfcl_{c}"]
            if sub:
                for k, v in failure_types(d, sub).items():
                    for b, cnt in v.items():
                        ft.setdefault(k, {}).setdefault(b, Counter()).update(cnt)
        cells[m] = {
            "present": True,
            "coverage": {"tasks": sum(1 for d in dirs[m] if task_status[d.name]["present"] and not task_status[d.name]["incomplete"]),
                         "items_searched_incl_quarantined": len(cu) + len(excluded[m]) + len(qunits[m]), "items_quarantined": len(qunits[m]),
                         "items_excluded": dict(ex), "items_analysed": len(cu), "divergent_states_four_arms": len(div),
                         "divergence_rate": len(div) / len(cu),
                         "per_category_items_states": {f"bfcl_{c}": [sum(1 for u in cu if u["stratum"] == f"bfcl_{c}"),
                                                                     sum(1 for u in div if u["stratum"] == f"bfcl_{c}")] for c in CATS},
                         "replay_consistent_states": sum(replay_flag.get((m, u["state_id"]), False) for u in div)},
            "divergence_types": dict(Counter(u["type"] for u in div)),
            "failure_types": {k: {b: dict(c.most_common()) for b, c in v.items()} for k, v in ft.items()},
            "analyze_ext": {k: g.get(k) for k in ("all_pp", "G_all_decision", "counts", "conditional_on_divergence_pp", "t_star_median")},
            "r2": r2_block(div, boot),
        }
    present = [m for m in MODELS if cells[m].get("present")]
    common = set.intersection(*[{u["task"] for u in units[m]} for m in present]) if present else set()
    common_res = {"n_items": len(common), "models": present, "per_model": {}}
    for m in present:
        cu = [u for u in units[m] if u["task"] in common]
        div = [u for u in cu if u["div"]]
        common_res["per_model"][m] = {"items": len(cu), "divergent_states": len(div), "divergence_rate": len(div) / len(cu) if cu else None,
                                      "G_all_pp": AD.summarise(*boot.mean(*boot.arrays(cu, "G"))) if cu else None,
                                      "r2": r2_block(div, boot)}
    q14 = cells.get("q14", {})
    files = {k: v for m in MODELS for L in loaded[m] if not L["incomplete"] for k, v in L["files"].items()}
    res = {"label": LABEL, "analysis": "analysis/fork/ext_q14.py",
           "script": {"sha256": AE.sha256(__file__), "ext_r2_sha256": AE.sha256(ROOT / "analysis/fork/ext_r2.py"),
                      "analyze_ext_sha256": AE.sha256(ROOT / "analysis/fork/analyze_ext.py"),
                      "analyze_dev_sha256": AE.sha256(ROOT / "analysis/fork/analyze_dev.py"),
                      "bfcl_run_sha256": AE.sha256(ROOT / "scripts/ext/bfcl_run.py"),
                      "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "bootstrap": {"B": a.B, "seed": AD.SEED, "scheme": "items with replacement within bfcl category; draws shared by all cells", "level": "95% percentile"},
           "tasks": task_status, "cells": cells, "common_panel": common_res,
           "n_input_files": len(files), "input_files_digest_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
           "complete": bool(q14.get("present")) and q14["coverage"]["tasks"] == 4}
    res["seconds"] = round(time.time() - t0, 1)
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / f"ext_q14_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"ext_q14_{utc}.md").write_text(markdown(res, jp))
    print(f"ext_q14: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


def markdown(res, jp):
    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]" if x else "n/a"

    def r(x):
        return f"{x['est']:.1f} [{x['ci95'][0]:.1f}, {x['ci95'][1]:.1f}]" if x else "n/a"
    C, P = res["cells"], res["common_panel"]
    q = C.get("q14", {})
    L = []
    if q.get("present"):
        e, cov, t3 = q["r2"]["pp_on_divergent"], q["coverage"], q["r2"]["table3"]
        k = t3["marginal_preserving_pairing_agreement_control"]
        cmp = "; ".join(f"{m} {P['per_model'][m]['divergent_states']} st, G {P['per_model'][m]['r2']['pp_on_divergent']['G']['est']:+.1f}, "
                        f"H {P['per_model'][m]['r2']['pp_on_divergent']['H']['est']:+.1f}, off-diag "
                        f"{P['per_model'][m]['r2']['pp_on_divergent']['offdiag']['est']:.1f}%" for m in P["models"] if P['per_model'][m]['r2']['n'])
        L += [f"**TL;DR** ({res['label']}.) q14 BFCL GPTQ-W4 d1 four-arm fork: {cov['tasks']}/4 tasks, {cov['items_analysed']} items analysed, "
              f"{cov['divergent_states_four_arms']} divergent states ({100 * cov['divergence_rate']:.0f}%). On divergent states (pp, 95% item bootstrap): "
              f"G {f(e['G'])}, H {f(e['H'])}, F {f(e['F'])}, G−H {f(e['GmH'])}; off-diagonal {r(e['offdiag'])}% "
              f"(independent-pairing expectation {100 * k['expected_offdiag_share_independent']:.1f}%, κ {k['kappa']:.3f}); strict reversals "
              f"{t3['strict_reversal_n']}. Common panel ({P['n_items']} items; descriptive, each model selects its own divergent states): {cmp}.", ""]
    else:
        L += [f"**TL;DR** ({res['label']}.) q14 fork outputs not present yet; nothing to report for q14.", ""]
    L += [f"> **{res['label']}.** Post hoc relative to the paper's pre-registered analyses. Item-level inference only (one run per item).", "",
          f"Source: `{jp.relative_to(ROOT)}`; script sha `{res['script']['sha256'][:12]}`, ext_r2 `{res['script']['ext_r2_sha256'][:12]}`, "
          f"analyze_ext `{res['script']['analyze_ext_sha256'][:12]}`, bfcl_run `{res['script']['bfcl_run_sha256'][:12]}`, git `{res['script']['git_head'][:10]}`. "
          f"Bootstrap B = {res['bootstrap']['B']}, seed {res['bootstrap']['seed']}, items within bfcl category, shared draws.", "",
          "Notation (success scale): G = Y_BQ−Y_QQ, H = Y_QB−Y_QQ, F = Y_BB−Y_QQ; Δ_Q = G, Δ_B = Y_BB−Y_QB, I = Δ_Q−Δ_B; "
          "off-diag = P(Δ_Q ≠ Δ_B); patterns in bit order BB, BQ, QB, QQ. G_all = mean of G over all analysed items (non-divergent = 0).", "",
          "## 1. Tasks and admission", "", "| task dir | present | complete | quarantined | QQ no-op | items | states | replay-consistent states | search-excluded |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res["tasks"].items():
        L.append(f"| {k} | {v['present']} | {v['present'] and not v['incomplete']} | {v['quarantined']} | {v['qq_noop_ok']} | {v['n_items']} | "
                 f"{v['n_states']} | {v['replay_ok_states']} | {v['n_excluded_search']} |")
    L += ["", "## 2. Per model (full own coverage)", "",
          "| cell | items analysed | excluded | divergent (4 arms) | G_all (pp) | G | H | F | G−H | F−G | F−H | I |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, v in C.items():
        if not v.get("present"):
            continue
        c, e = v["coverage"], v["r2"]["pp_on_divergent"]
        L.append(f"| bfcl:{m}:gptq_w4_d1 | {c['items_analysed']} | {c['items_excluded'] or 0} | {c['divergent_states_four_arms']} ({100 * c['divergence_rate']:.0f}%) | "
                 f"{f(v['analyze_ext']['all_pp']['G'])} | {f(e['G'])} | {f(e['H'])} | {f(e['F'])} | {f(e['GmH'])} | {f(e['FmG'])} | {f(e['FmH'])} | {f(e['I'])} |")
    L += ["", "### 3×3 (Δ_Q, Δ_B), off-diagonal share, marginal-preserving pairing agreement control", "",
          "| cell | (−1,−1) | (−1,0) | (−1,1) | (0,−1) | (0,0) | (0,1) | (1,−1) | (1,0) | (1,1) | off-diag % [95%] | expected off-diag % | κ | strict reversals |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, v in C.items():
        if not v.get("present") or not v["r2"]["n"]:
            continue
        t, e = v["r2"]["table3"], v["r2"]["pp_on_divergent"]
        k = t["marginal_preserving_pairing_agreement_control"]
        L.append(f"| bfcl:{m}:gptq_w4_d1 | " + " | ".join(str(t["counts_dQ_dB"][f"{x},{y}"]) for x in R2.VALS for y in R2.VALS) +
                 f" | {r(e['offdiag'])} | {100 * k['expected_offdiag_share_independent']:.1f} | {k['kappa']:.3f} | {t['strict_reversal_n']} |")
    L += ["", "### 16 outcome patterns (counts; bit order BB, BQ, QB, QQ)", "", "| cell | " + " | ".join(R2.PATTERNS) + " |", "|---|" + "---|" * 16]
    for m, v in C.items():
        if v.get("present") and v["r2"]["n"]:
            L.append(f"| bfcl:{m}:gptq_w4_d1 | " + " | ".join(str(v["r2"]["patterns16"]["counts"][p]) for p in R2.PATTERNS) + " |")
    L += ["", "### Arm success on divergent states (%)", "", "| cell | Y_BB | Y_BQ | Y_QB | Y_QQ |", "|---|---|---|---|---|"]
    for m, v in C.items():
        if v.get("present") and v["r2"]["n"]:
            e = v["r2"]["pp_on_divergent"]
            L.append(f"| bfcl:{m}:gptq_w4_d1 | {r(e['Y_BB'])} | {r(e['Y_BQ'])} | {r(e['Y_QB'])} | {r(e['Y_QQ'])} |")
    L += ["", "### Coverage per category (items analysed / divergent states), divergence types, failure types", ""]
    for m, v in C.items():
        if not v.get("present"):
            continue
        L.append(f"- **{m}**: " + "; ".join(f"{s} {x[0]}/{x[1]}" for s, x in v["coverage"]["per_category_items_states"].items()) +
                 f". Replay-consistent divergent states: {v['coverage']['replay_consistent_states']}/{v['coverage']['divergent_states_four_arms']}.")
        L.append(f"  - divergence types: {v['divergence_types']}")
        for kk, vv in v["failure_types"].items():
            L.append(f"  - {kk.replace('_', ' ')}: " + "; ".join(f"{b} {dict(list(c.items())[:6])}" for b, c in sorted(vv.items())))
    L += ["", f"## 3. Common task panel ({P['n_items']} items analysed in all of {', '.join(P['models'])}) — DESCRIPTIVE", "",
          "Each model selects its own divergent states on these items, so the rows differ in state set, t* and base rate; they are "
          "not paired comparisons and carry no test.", "",
          "| model | items | divergent | G_all (pp) | G | H | F | G−H | I | off-diag % | expected off-diag % | κ | strict reversals | Y_QQ % |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, v in P["per_model"].items():
        e = v["r2"]["pp_on_divergent"]
        if not v["r2"]["n"]:
            continue
        t = v["r2"]["table3"]
        k = t["marginal_preserving_pairing_agreement_control"]
        L.append(f"| {m} | {v['items']} | {v['divergent_states']} ({100 * v['divergence_rate']:.0f}%) | {f(v['G_all_pp'])} | {f(e['G'])} | {f(e['H'])} | "
                 f"{f(e['F'])} | {f(e['GmH'])} | {f(e['I'])} | {r(e['offdiag'])} | {100 * k['expected_offdiag_share_independent']:.1f} | {k['kappa']:.3f} | "
                 f"{t['strict_reversal_n']} | {r(e['Y_QQ'])} |")
    L += ["", "Patterns on the common panel (counts):", ""]
    for m, v in P["per_model"].items():
        if v["r2"]["n"]:
            L.append(f"- {m}: " + ", ".join(f"{p} {c}" for p, c in v["r2"]["patterns16"]["counts"].items() if c))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
