"""EXPLORATORY: difficulty-stratified fork effects (W52). Post hoc moderators on development data. Nothing here is
confirmatory; the moderator list for the telecom holdout is fixed separately (FORK_PROTOCOL.md §12) before 10-03.

Units and effects exactly as analysis/fork/analyze_dev.py (task x block; Y = DB success for retail/airline, official
task-basis success for telecom; G = Y_BQ - Y_QQ, A = L_QB - L_BB, C = L_BQ - L_BB, I = L_QQ - L_QB - L_BQ + L_BB), and
the same inputs, exclusions, quarantine, split guard and inference (analyze_dev.Boot, W63: complete shared blocks, block
bootstrap with >= 10 blocks else t over blocks; crossed task x block bootstrap alongside; B = 2000, seed 20261001).
Moderators (per model x cell):
  (a) EXPLORATORY ONLY: remaining horizon after the fork state h = n_decisions(Q episode) - t*, tertiles within the cell
      (divergent units only; conditional effects). h is Q's realised trajectory length, confounded by loops and failure,
      so it is never a confirmatory stratum. Plus the compounding test: bootstrap slope of C (and G, A, I) on h, per 10 decisions,
      weighted least squares under the hierarchical draws; two-sided bootstrap p = 2 min(P(slope <= 0), P(slope >= 0)).
  (b) task length = mean number of agent decisions of the task's BF16 (bfpair) episodes, tertiles within the cell.
  (c) task difficulty = BF16 success rate of the task over all admitted bfpair blocks of that model and domain,
      bins {0}, (0, 0.5], (0.5, 1].
  (d) domain.
  (e) telecom persona: Hard / None / Easy (from the task id).
  (f) remaining step budget at the fork (max_steps - steps used before t*), tertiles: known at the fork.
For (b)-(e), each stratum reports G_all (all units of the stratum, non-divergent = 0) and the effects conditional on
divergence; strata use the cell's shared draws.
--include-gate-telecom adds the telecom units of the gate directories (a6k2_q8_tel_awq_w4_q1; selected tasks, not the
full pool), as requested for W52.

usage: python analysis/fork/analyze_difficulty.py --snapshot <snapshot.json> [--cells ...] [--include-gate-telecom]
-> analysis/fork/out/difficulty_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
BF_RE = re.compile(r"^a6k2_(q\d+)_(?:tel_)?bfpair_(q\d+|f\d\d)$")
PERSONA_RE = re.compile(r"PERSONA:(\w+)")


def bf16_task_stats(snap: dict) -> dict:
    """(model, domain, task) -> {'succ': BF16 success rate over blocks, 'len': mean agent decisions, 'n': blocks}."""
    acc = defaultdict(lambda: {"y": [], "len": []})
    for rid, doms in snap["frozen"].items():
        m = BF_RE.match(rid)
        if not m:
            continue
        for dom, fr in doms.items():
            p = ROOT / "runs" / rid / dom / "trajectory.jsonl"
            if not p.exists():
                continue
            infra = set(map(str, fr.get("infra_missing") or []))
            for ln in open(p):
                t = json.loads(ln)
                if str(t["task_id"]) in infra or t.get("termination_reason") == "infrastructure_error":
                    continue
                msgs = t["messages"]
                n0 = len(((t.get("task") or {}).get("initial_state") or {}).get("message_history") or []) or 1
                k = (m.group(1), dom, f"{dom}:{t['task_id']}")
                acc[k]["y"].append(AD.success(dom, t))
                acc[k]["len"].append(sum(1 for x in msgs[n0:] if x["role"] == "assistant"))
    return {k: {"succ": float(np.mean(v["y"])), "len": float(np.mean(v["len"])), "n": len(v["y"])} for k, v in acc.items()}


def tertile_labels(vals: list[float]) -> tuple[list[str], list[float]]:
    q = list(np.quantile(vals, [1 / 3, 2 / 3])) if vals else [0, 0]
    return [("T1" if v <= q[0] else "T2" if v <= q[1] else "T3") for v in vals], [float(x) for x in q]


def slope_test(units: list[dict], boot: AD.Boot, key: str) -> dict:
    """Slope of effect `key` on remaining horizon h (pp per 10 decisions), weighted LS. Primary per AD.summarise:
    block bootstrap (blocks resampled whole) with >= 10 blocks, else t over per-block slopes; crossed task x block
    bootstrap (generalisation) alongside."""
    if len(units) < 5:
        return {"n": len(units), "note": "too few units"}
    ti = np.array([boot.tix[u["task"]] for u in units])
    ki = np.array([boot.bix[u["block"]] for u in units])
    x = np.array([u["h"] for u in units], float)
    y = np.array([u["E"][key] for u in units], float)

    def fit(w):
        sw = np.maximum(w.sum(-1, keepdims=True), 1e-12)
        mx, my = (w * x).sum(-1, keepdims=True) / sw, (w * y).sum(-1, keepdims=True) / sw
        return 10 * ((w * (x - mx) * (y - my)).sum(-1) / np.maximum((w * (x - mx) ** 2).sum(-1), 1e-12))

    pt = float(fit(np.ones((1, len(x))))[0])
    blk = []
    for k in np.unique(ki):
        m = ki == k
        if m.sum() >= 3 and np.ptp(x[m]) > 0:
            blk.append(float(fit(m[None, :].astype(float))[0]))
    t = AD.t_interval(blk)
    dr = fit(boot.unit_weights(ti, ki, "block"))
    cr = fit(boot.unit_weights(ti, ki, "crossed"))
    r = AD.summarise(pt, dr[np.isfinite(dr)], t=t, crossed=(pt, cr[np.isfinite(cr)]))
    d = dr[np.isfinite(dr)]
    r.update({"n": len(units), "h_range": [float(x.min()), float(x.max())], "unit": "pp per 10 decisions",
              "p_two_sided_block_boot": float(min(1.0, 2 * min((d <= 0).mean(), (d >= 0).mean()))) if len(d) else None})
    return r


def strata(units, boot, label_of, levels, conditional_only=False):
    out = {}
    for lv in levels:
        su = [u for u in units if label_of(u) == lv]
        if not su:
            continue
        if conditional_only:
            r = {"n_states": len(su), "counts": {k: int(sum(u["E"][k] for u in su)) for k in ("rescue", "damage", "M", "both_succeed", "both_fail")}}
            for s in ("G", "rescue", "damage", "M", "A", "C", "I"):
                X, M = boot.arrays(su, s)
                r[f"{s}_cond_pp"] = AD.summarise(*boot.ratio(X, M))  # Draws carry t and crossed
        else:
            r = AD.analyse(su, boot)
            r = {k: r[k] for k in ("n_units", "n_tasks", "n_states", "divergence_rate", "all_pp", "conditional_on_divergence_pp", "counts") if k in r}
            if "all_pp" in r:  # keep the headline r/d/M/G and the decomposition; drop the per-branch levels for size
                r["all_pp"] = {k: v for k, v in r["all_pp"].items() if k in ("G", "rescue", "damage", "M", "H_policy", "F_policy")}
        out[lv] = r
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--cells", nargs="*", default=None)
    ap.add_argument("--include-gate-telecom", action="store_true")
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    ap.add_argument("--split", default="dev")
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    snap = json.load(open(a.snapshot))
    dirs = AD.discover(False)
    if a.include_gate_telecom:
        dirs += [d for d in AD.discover(True) if "analysis/fork/gate" in str(d)]
    cache: dict = {}
    loaded = [AD.load_dir(d, snap, cache) for d in dirs]
    split_info = AD.split_guard([u for L in loaded for u in L["units"]], a.split, "analyze_difficulty")
    split_info["incomplete_blocks"] = AD.mark_incomplete_blocks([u for L in loaded for u in L["units"]], a.split)
    units, seen = [], set()
    for L in loaded:
        if L["quarantined"]:
            continue
        gate = "analysis/fork/gate" in L["dir"]
        for u in L["units"]:
            if "excluded" in u or (gate and u["domain"] != "telecom"):
                continue
            k = (u["run_id"], u["domain"], u["task"])
            if k in seen:
                continue
            seen.add(k)
            units.append(u)
    if a.cells:
        known = sorted({u["cell"] for u in units})
        units = [u for u in units if u["cell"] in a.cells]
        if not units:
            print(f"analyze_difficulty: no fork units for cell(s) {a.cells} (cells with units: {known or 'none'}); nothing to do.")
            return
    if not units:
        print("analyze_difficulty: no analysable fork units yet; nothing to do.")
        return
    bf = bf16_task_stats(snap)
    files = {k: v for L in loaded for k, v in L["files"].items()}
    fp = hashlib.sha256(json.dumps({"script": AD.sha256(__file__), "dev": AD.sha256(AD.__file__), "snapshot": AD.sha256(a.snapshot),
                                    "files": files, "cells": a.cells, "gate": a.include_gate_telecom, "B": a.B, "split": a.split, "splits": AD.sha256(AD.SPLITS)}, sort_keys=True).encode()).hexdigest()[:16]
    OUT.mkdir(parents=True, exist_ok=True)
    for p in sorted(OUT.glob("difficulty_*.json")):
        try:
            if json.load(open(p)).get("input_fingerprint") == fp:
                print(f"analyze_difficulty: unchanged inputs (fingerprint {fp}); existing output {p.relative_to(ROOT)}")
                return
        except Exception:
            continue
    for u in units:
        u["E"] = AD.effects(u["Y"], u["div"])
        s = bf.get((u["model"], u["domain"], u["task"]))
        u["bf_succ"] = s["succ"] if s else None
        u["bf_len"] = s["len"] if s else None
        pm = PERSONA_RE.search(u["task"])
        u["persona"] = pm.group(1) if pm else None
        if u["div"]:
            u["h"] = (u["n_decisions"] or 0) - u["t"]
    res_cells = {}
    for m, c in sorted({(u["model"], u["cell"]) for u in units}):
        cu = [u for u in units if u["model"] == m and u["cell"] == c]
        bo = defaultdict(set)
        for u in cu:
            bo[u["task"]].add(u["block"])
        boot = AD.Boot(sorted(bo), {k: sorted(v) for k, v in bo.items()}, B=a.B)
        div = [u for u in cu if u["div"]]
        hl, hq = tertile_labels([u["h"] for u in div])
        for u, l in zip(div, hl):
            u["h_t"] = l
        bl, bq = tertile_labels([u["steps_left"] for u in div])
        for u, l in zip(div, bl):
            u["budget_t"] = l
        lu = [u for u in cu if u["bf_len"] is not None]
        ll, lq = tertile_labels([u["bf_len"] for u in lu])
        for u, l in zip(lu, ll):
            u["len_t"] = l
        r = {"n_units": len(cu), "n_states": len(div), "n_units_without_bf16_stats": sum(1 for u in cu if u["bf_succ"] is None),
             "f_remaining_step_budget_at_fork": {"note": "known at the fork: max_steps - steps used before t* (conditional effects)",
                                                 "tertile_cuts": bq, "strata": strata(div, boot, lambda u: u.get("budget_t"), ["T1", "T2", "T3"], True)},
             "a_remaining_horizon": {"note": "EXPLORATORY: realised Q trajectory length after t*, confounded by loops and failure",
                                     "tertile_cuts": hq, "strata": strata(div, boot, lambda u: u.get("h_t"), ["T1", "T2", "T3"], True),
                                     "slope": {k: slope_test(div, boot, k) for k in ("C", "G", "A", "I")}},
             "b_task_length_bf16": {"tertile_cuts": lq, "strata": strata(cu, boot, lambda u: u.get("len_t"), ["T1", "T2", "T3"])},
             "c_bf16_difficulty": {"bins": ["0", "(0,0.5]", "(0.5,1]"],
                                   "strata": strata(cu, boot, lambda u: None if u["bf_succ"] is None else
                                                    ("0" if u["bf_succ"] == 0 else "(0,0.5]" if u["bf_succ"] <= 0.5 else "(0.5,1]"),
                                                    ["0", "(0,0.5]", "(0.5,1]"])},
             "d_domain": strata(cu, boot, lambda u: u["domain"], sorted({u["domain"] for u in cu})),
             "e_telecom_persona": strata([u for u in cu if u["domain"] == "telecom"], boot, lambda u: u["persona"], ["Hard", "None", "Easy"])}
        res_cells[f"{m}:{c}"] = r
    res = {"label": "EXPLORATORY (post hoc moderators on development data; not confirmatory)", "input_fingerprint": fp,
           "analysis": "analysis/fork/analyze_difficulty.py",
           "snapshot": {"id": snap.get("snapshot_id"), "path": str(Path(a.snapshot).resolve()), "sha256": AD.sha256(a.snapshot)},
           "script": {"path": str(Path(__file__).resolve()), "sha256": AD.sha256(__file__), "analyze_dev_sha256": AD.sha256(AD.__file__),
                      "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "split": split_info,
           "bootstrap": {"B": a.B, "seed": AD.SEED, "scheme": "analyze_dev.Boot (W63): complete shared blocks (block bootstrap if >= 10 blocks, else t over blocks) + crossed task x block"},
           "include_gate_telecom": a.include_gate_telecom, "input_dirs": [L["dir"] for L in loaded],
           "cells": res_cells, "seconds": round(time.time() - t0, 1)}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"difficulty_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))

    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"
    L = [f"**TL;DR** EXPLORATORY difficulty moderators of fork effects ({len(res_cells)} cells, "
         f"{sum(v['n_states'] for v in res_cells.values())} states). Exploratory compounding slope of C on realised remaining horizon "
         "(pp per 10 decisions; confounded by loops, not confirmatory): " + "; ".join(
             f"{k} {v['a_remaining_horizon']['slope']['C'].get('est')} {v['a_remaining_horizon']['slope']['C'].get('ci95')}" for k, v in res_cells.items()) + ".",
         "", f"# Difficulty-stratified fork effects, exploratory ({res['utc']})", "",
         f"Snapshot `{res['snapshot']['id']}`, script sha {res['script']['sha256'][:12]}, git {res['script']['git_head'][:10]}. "
         f"Full numbers: `{jp.relative_to(ROOT)}`. pp; 95% hierarchical bootstrap. Post hoc: do not read p-values as confirmatory.", ""]
    for k, v in res_cells.items():
        L.append(f"## {k} ({v['n_units']} units, {v['n_states']} states)")
        for name, key in (("(a) remaining horizon (conditional)", "a_remaining_horizon"),):
            L.append(f"- {name}, cuts {v[key]['tertile_cuts']}: " + "; ".join(
                f"{lv}: n {r['n_states']}, G {f(r['G_cond_pp'])}, C {f(r['C_cond_pp'])}" for lv, r in v[key]["strata"].items()))
            s = v[key]["slope"]["C"]
            if "est" in s:
                L.append(f"  - EXPLORATORY slope of C: {s['est']:+.2f} pp/10 decisions [{s['ci95'][0]:+.2f}, {s['ci95'][1]:+.2f}] ({s['primary']}); crossed {s.get('crossed_ci95')}")
        fb = v["f_remaining_step_budget_at_fork"]
        L.append(f"- (f) remaining step budget at the fork (known at t*), cuts {fb['tertile_cuts']}: " + "; ".join(
            f"{lv}: n {r['n_states']}, G {f(r['G_cond_pp'])}, C {f(r['C_cond_pp'])}" for lv, r in fb["strata"].items()))
        for name, key in (("(b) BF16 task length", "b_task_length_bf16"), ("(c) BF16 difficulty", "c_bf16_difficulty")):
            L.append(f"- {name}: " + "; ".join(f"{lv}: units {r['n_units']}, G_all {f(r['all_pp']['G'])}, C_all {f(r['all_pp']['C'])}"
                                              for lv, r in v[key]["strata"].items() if "all_pp" in r))
        for name, key in (("(d) domain", "d_domain"), ("(e) telecom persona", "e_telecom_persona")):
            if v[key]:
                L.append(f"- {name}: " + "; ".join(f"{lv}: units {r['n_units']}, G_all {f(r['all_pp']['G'])}" for lv, r in v[key].items() if "all_pp" in r))
        L.append("")
    (OUT / f"difficulty_{utc}.md").write_text("\n".join(L) + "\n")
    print(f"analyze_difficulty: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


if __name__ == "__main__":
    main()
