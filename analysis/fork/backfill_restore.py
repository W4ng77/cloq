"""Appendix backfill part 1 (W100x): restoration location vs byte-matched random modules (perturb-v1 closed-loop arms,
docs/insights/PERTURBATION_PROTOCOL.md §2.1, §3a-3e) and the W55 pivot-arm reversion copied from analyze_pivot_arms."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from backfill_common import (ALPHAS, CELL_BLOCKS, CELLS, DOMAINS, FAMILY, ROOT, SEEDS, admitted_arms, boot_for, cell_units,
                             complete, fmt, pool, sha256, stat, summ)

def unfinished_arms(snap: dict) -> list[dict]:
    """Expected perturb-v1 arm runs (5 structured + 9 random + 3 resid per cell, + 8 recal on GPTQ-W3) that are not admitted
    for both domains: excluded by the integrity gate (first reason), pending in the queue, or without a run directory."""
    fz, ex, pend = snap["frozen"], snap.get("excluded") or {}, set(snap.get("queue_pending_run_ids") or [])
    out = []
    for model, cell in CELLS:
        arms = [f"restore_{x}" for x in FAMILY] + [f"restore_rand_{f}_{s}" for f in ("third", "attn", "mlp") for s in SEEDS]
        arms += [f"resid_a{a:g}" for a in ALPHAS[cell]]
        if cell == "gptq_w3":
            arms += [f"restore_recal_{x}" for x in FAMILY] + [f"restore_recal_rand_{f}_s1" for f in ("third", "attn", "mlp")]
        for arm in arms:
            for blk in CELL_BLOCKS[cell]:
                rid = f"a6k2_pert_{model}_{cell}_{arm}_{blk}"
                if rid in fz and set(fz[rid]) >= set(DOMAINS):
                    continue
                st = ("pending in queue; " if rid in pend else "") + ((ex.get(rid) or [""])[0][:80] if rid in ex else
                                                                       ("" if rid in pend else "no run in snapshot"))
                out.append({"cell": f"{model}:{cell}", "arm": arm, "block": blk, "run": rid,
                            "admitted_domains": sorted(fz.get(rid, {})), "status": st.strip("; ")})
    return out


def restoration(fz: dict, rule: str) -> dict:
    res = {"contrasts": {}, "pooled": {}, "incomplete": []}
    pairs_for_pool = defaultdict(dict)
    for model, cell in CELLS:
        adm = admitted_arms(fz, model, cell)
        variants = [("", "restore_", "restore_rand_", SEEDS)]
        if cell == "gptq_w3":
            variants.append(("recal_", "restore_recal_", "restore_recal_rand_", ("s1",)))
        for vtag, spre, rpre, seeds in variants:
            for x, fam in FAMILY.items():
                xs = f"{spre}{x}"
                key = f"{model}:{cell}:{vtag}{x}"
                seeds_all = [f"{rpre}{fam.split('_', 1)[1]}_{s}" for s in seeds]
                inc = [s for s in seeds_all if complete(adm, s, cell)]
                exc = [s for s in seeds_all if s not in inc]
                if not complete(adm, xs, cell) or not inc:
                    res["incomplete"].append({"contrast": key, "structured": xs, "structured_admitted": adm.get(xs, []),
                                              "seeds_complete": inc, "seeds_incomplete": {s: adm.get(s, []) for s in exc}})
                    continue
                units, info = cell_units(fz, model, cell, [xs] + inc, rule)
                res["contrasts"][key] = {"units": units, "seeds": inc, "seeds_excluded": {s: adm.get(s, []) for s in exc},
                                         "skipped": info["skipped"], "structured": xs}
    # one Boot per block family (q3-q5 vs f01-f03), so draws are shared by every contrast and pool within a family
    fams = {"q": {k: v["units"] for k, v in res["contrasts"].items() if CELL_BLOCKS[k.split(":")[1]][0].startswith("q")},
            "f": {k: v["units"] for k, v in res["contrasts"].items() if CELL_BLOCKS[k.split(":")[1]][0].startswith("f")}}
    boots = {f: boot_for(us) for f, us in fams.items() if us}
    for key, c in res["contrasts"].items():
        model, cell, arm = key.split(":")
        boot = boots["q" if CELL_BLOCKS[cell][0].startswith("q") else "f"]
        us, xs, sd = c.pop("units"), c["structured"], c["seeds"]

        def ymean(u, arms=sd):
            return float(np.mean([u["ep"][a]["Y"] for a in arms]))

        r = {"n_units": len(us), "n_tasks": len({u["task"] for u in us}), "blocks": sorted({u["block"] for u in us})}
        raw = {"diff": stat(boot, us, lambda u: u["ep"][xs]["Y"] - ymean(u)),
               "x": stat(boot, us, lambda u: u["ep"][xs]["Y"]), "rand": stat(boot, us, ymean),
               "q": stat(boot, us, lambda u: u["ep"]["Q"]["Y"]), "b": stat(boot, us, lambda u: u["ep"]["B"]["Y"]),
               "x_minus_q": stat(boot, us, lambda u: u["ep"][xs]["Y"] - u["ep"]["Q"]["Y"]),
               "rand_minus_q": stat(boot, us, lambda u: ymean(u) - u["ep"]["Q"]["Y"]),
               "turnover_diff": stat(boot, us, lambda u: int(u["ep"][xs]["Y"] != u["ep"]["B"]["Y"])
                                     - float(np.mean([int(u["ep"][a]["Y"] != u["ep"]["B"]["Y"]) for a in sd])))}
        r.update({k: summ(v) for k, v in raw.items()})
        r["seed_success"] = {s: round(100 * float(np.mean([u["ep"][s]["Y"] for u in us])), 1) for s in sd}
        r["x_success_unitmean"] = round(100 * float(np.mean([u["ep"][xs]["Y"] for u in us])), 1)
        r["x_outside_seed_range"] = ("above" if r["x_success_unitmean"] > max(r["seed_success"].values()) else
                                     "below" if r["x_success_unitmean"] < min(r["seed_success"].values()) else "inside")
        c.update(r)
        if not arm.startswith("recal_"):
            pairs_for_pool[(cell, arm)][model] = raw["diff"]
    for (cell, arm), d in pairs_for_pool.items():
        if set(d) == {"q4", "q8"} and CELL_BLOCKS[cell][0].startswith("q"):
            res["pooled"][f"{cell}:{arm}"] = pool([d["q4"], d["q8"]])
    return res


def pivot_extract(path: Path) -> dict:
    d = json.load(open(path))
    out = {"file": str(path.relative_to(ROOT)), "sha256": sha256(path), "utc": d.get("utc"), "selection": d.get("selection"), "cells": {}}
    for cell, c in d["cells"].items():
        arms = c.get("arms") or {}
        row = {}
        for arm, a in arms.items():
            row[arm] = {"n": a.get("n"), "eq_B": (a.get("eq_B") or {}).get("est")}
            dl = (c.get("delta_vs_matched_random_pp") or {}).get(arm)
            if dl:
                row[arm]["delta"] = {k: dl.get(k) for k in ("control", "n_paired", "est", "ci95", "crossed_ci95", "primary")}
        out["cells"][cell] = row
    out["gptq_w3_pooled_delta"] = {arm: {k: v.get(k) for k in ("est", "ci95", "crossed_ci95")}
                                   for arm, v in (d.get("secondary_gptq_w3_pooled_delta_pp") or {}).items() if isinstance(v, dict)}
    return out


def render_restore(res: dict) -> list[str]:
    R, P = res["restoration"], res["pivot"]
    L = []
    L += ["## 1. Restoration location vs byte-matched random modules", "",
          "Contrast = Y(located arm) - mean over the complete random seeds of the byte-matched family (early/middle/late vs rand_third, "
          "attn vs rand_attn, mlp vs rand_mlp), on joint task x block units (located arm, every included seed, Q and BF16 all have a data "
          "episode). turnover diff = P(arm outcome != BF16) - mean over seeds (negative = located arm closer to BF16). "
          "'seed range' says whether the located arm's success lies above, inside or below the per-seed successes (PERTURBATION_PROTOCOL §4). "
          "W4 cells: Q is not damaged on f01-f03, so success differences there are not recovery (behaviour primary, §4a). "
          "GPTQ-W3 plain arms carry the sequential-compensation mismatch (§3c), equally in located and random arms; recal arms have one random seed.", "",
          "| contrast | units | seeds | located | random mean | located - random | turnover diff | located - Q | random - Q | seed range |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for k, c in R["contrasts"].items():
        L.append(f"| {k} | {c['n_units']} | {len(c['seeds'])} | {c['x']['est']:.1f} | {c['rand']['est']:.1f} | {fmt(c['diff'])} | "
                 f"{fmt(c['turnover_diff'])} | {fmt(c['x_minus_q'])} | {fmt(c['rand_minus_q'])} | {c['x_outside_seed_range']} "
                 f"({', '.join(f'{s[-2:]} {v}' for s, v in c['seed_success'].items())}) |")
    L += ["", "**Pooled q4 + q8 (equal weight, shared draws), located - random:**", "", "| cell:arm | located - random |", "|---|---|"]
    for k, v in R["pooled"].items():
        L.append(f"| {k} | {fmt(v)} |")
    L += ["", "**Incomplete or unavailable contrasts (not analysed; admitted run-domains listed):**", ""]
    for i in R["incomplete"]:
        L.append(f"- {i['contrast']}: located `{i['structured']}` admitted {i['structured_admitted'] or 'none'}; complete seeds {i['seeds_complete'] or 'none'}; "
                 f"incomplete seeds {json.dumps(i['seeds_incomplete'])}")
    exs = [(k, c["seeds_excluded"]) for k, c in R["contrasts"].items() if c["seeds_excluded"]]
    if exs:
        L += ["", "Seeds left out of an analysed contrast because they are not complete on all three blocks x both domains:", ""]
        L += [f"- {k}: {json.dumps(v)}" for k, v in exs]
    L += ["", "**Sensitivity, restore_eval convention (every infrastructure episode missing, incl. context overflow):**", "",
          "| contrast | units | located - random |", "|---|---|---|"]
    for k, v in res["restoration_sens_allinfra"].items():
        L.append(f"| {k} | {v['n_units']} | {fmt(v['diff'])} |")
    L += ["", "### Pivot-time action reversion (W55, single decision at the frozen first-divergence state; one random seed)", "",
          f"Copied from `{P['file']}` (sha {P['sha256'][:12]}, {P['utc']}). r_B = P(arm's action equals BF16's action at the pivot); "
          f"delta = r_B(arm) - r_B(byte-matched random s1), paired on 150 states. Step-3 selection: {json.dumps(P['selection'])}.", "",
          "| cell | arm | n | r_B | delta vs random s1 |", "|---|---|---|---|---|"]
    for cell, arms in P["cells"].items():
        for arm, a in arms.items():
            if "delta" in a:
                L.append(f"| {cell} | {arm} | {a['n']} | {a['eq_B']:.1f} | {fmt(a['delta'])} |")
    if P.get("gptq_w3_pooled_delta"):
        L += ["", "GPTQ-W3 q4+q8 pooled delta (secondary population of FORK_PROTOCOL §13): " +
              "; ".join(f"{k} {fmt(v)}" for k, v in P["gptq_w3_pooled_delta"].items())]
    L += ["", "### Unfinished closed-loop arm runs (expected by perturb-v1, not admitted for both domains in the snapshot; not used)", "",
          "| cell | arm | block | admitted domains | status |", "|---|---|---|---|---|"]
    L += [f"| {u['cell']} | {u['arm']} | {u['block']} | {', '.join(u['admitted_domains']) or '-'} | {u['status']} |" for u in res.get("unfinished_arm_runs", [])]
    return L
