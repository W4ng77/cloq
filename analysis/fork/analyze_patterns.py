"""WP1 (W68): complete four-arm consequences, all 16 outcome patterns, unit registry (CONSEQUENCE_ANALYSIS_PLAN §2-§4, §13).

Inputs and admission are exactly analyze_dev's: split guard first (--split dev; telecom holdout refused), snapshot
gate, quarantine, complete-block rule (only complete shared blocks), duplicate units counted once.
Sign dictionary: analyze_dev.SIGN_DICTIONARY (A = Y_BB-Y_QB, C = Y_BB-Y_BQ, I = Y_BQ+Y_QB-Y_BB-Y_QQ, G = A+I,
H = C+I, F = A+C+I). Bit order of patterns: BB, BQ, QB, QQ; the 16-row table is generated from the equations and
asserted against the plan's table (§3) before any summary.
Estimand IDs:
  primary_pivot_G_all            every admitted task x block; no divergence = the pivot policy does nothing: G = r = d = M = 0
                                 (effect_source no_intervention). Reported with r, d, M on the identical denominator.
  policy_pivot_H_all / F_all     explicit pivot policies (switch the suffix / action+suffix at the pivot; nothing without one)
  pivot_four_branch_conditional  observed divergent states: all 16 patterns; for each binary contrast X - Y in {G (BQ-QQ),
                                 H (QB-QQ), F (BB-QQ), A (BB-QB), C (BB-BQ)}: mean, P(+1), P(-1) and turnover P(+1)+P(-1);
                                 I distribution; strict action-ranking reversal (A*G < 0: 0110, 1001), reported apart from I.
Intervals (analyze_dev.Boot, W63): fixed task pool over complete shared blocks (block bootstrap with >= 10 blocks, else t
over block means) and the crossed task x block bootstrap; B = 2000, seed 20261001.
Outputs (analysis/fork/out/, suffix = snapshot id): consequence_units_<s>.jsonl (§13.1 schema, every unit incl.
no-divergence and missing), patterns16_<s>.csv (all 16 patterns incl. zero counts, by model x cell x domain and model x
cell), consequence_estimands_<s>.json, coverage_<s>.json (expected/observed tensor, common intersections).
Exploratory development analysis (internal; development outcomes were already viewed).

usage: python analysis/fork/analyze_patterns.py --snapshot <snapshot.json> [--split dev] [--B 2000]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
PATTERNS = [f"{i:04b}" for i in range(16)]  # bit order BB, BQ, QB, QQ
# plan §3 table: pattern -> (G, H, F, A, strict reversal)
PLAN_TABLE = {"0000": (0, 0, 0, 0, 0), "0001": (-1, -1, -1, 0, 0), "0010": (0, 1, 0, -1, 0), "0011": (-1, 0, -1, -1, 0),
              "0100": (1, 0, 0, 0, 0), "0101": (0, -1, -1, 0, 0), "0110": (1, 1, 0, -1, 1), "0111": (0, 0, -1, -1, 0),
              "1000": (0, 0, 1, 1, 0), "1001": (-1, -1, 0, 1, 1), "1010": (0, 1, 1, 0, 0), "1011": (-1, 0, 0, 0, 0),
              "1100": (1, 0, 1, 1, 0), "1101": (0, -1, 0, 1, 0), "1110": (1, 1, 1, 0, 0), "1111": (0, 0, 0, 0, 0)}
CONTRASTS = {"G": ("BQ", "QQ"), "H": ("QB", "QQ"), "F": ("BB", "QQ"), "A": ("BB", "QB"), "C": ("BB", "BQ")}
EVAL = {"retail": "retail-db-success", "airline": "airline-db-success", "telecom": "telecom-official-task-basis-success"}


def pattern_effects(p: str) -> dict:
    Y = dict(zip(("BB", "BQ", "QB", "QQ"), map(int, p)))
    return AD.effects(Y, True)


def check_table() -> None:
    for p in PATTERNS:
        e = pattern_effects(p)
        assert (e["G"], e["H"], e["F"], e["A"], e["strict_reversal"]) == PLAN_TABLE[p], (p, e)
        assert e["pattern"] == p


def contrast_units(div: list[dict], x: str, y: str) -> None:
    for u in div:
        Y = u["Y"]
        u["E"][f"pos_{x}{y}"] = int(Y[x] == 1 and Y[y] == 0)
        u["E"][f"neg_{x}{y}"] = int(Y[x] == 0 and Y[y] == 1)
        u["E"][f"turn_{x}{y}"] = u["E"][f"pos_{x}{y}"] + u["E"][f"neg_{x}{y}"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    ap.add_argument("--complete-case", action="store_true", help="sensitivity: pre-W70 complete-block rule")
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    check_table()
    snap = json.load(open(a.snapshot))
    sid = ("cc_" if a.complete_case else "") + str(snap.get("snapshot_id"))
    loaded = [AD.load_dir(d, snap, {}) for d in AD.discover(False)]
    allu = [u for L in loaded for u in L["units"]]
    split_info = AD.split_guard(allu, a.split, "analyze_patterns")
    quarantined = {L["dir"] for L in loaded if L["quarantined"]}
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined fork task (QQ no-op mismatch)")
    units, _dups = AD.dedupe_units(allu)
    incomplete = AD.mark_incomplete_blocks(units, a.split, strict=not a.complete_case)
    ok = [u for u in units if "excluded" not in u]
    for u in ok:
        u["E"] = AD.effects(u["Y"], u["div"])
    git = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    splits_sha = AD.sha256(AD.SPLITS)
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- unit registry (§13.1)
    qsha = {}
    up = OUT / f"consequence_units_{sid}.jsonl"
    with open(up, "w") as fh:
        for u in units:
            st = None
            if u.get("div") and "excluded" not in u:
                sp = ROOT / u["dir"] / "states" / f"{u['state_id']}.json"
                st = json.loads(sp.read_text()) if sp.exists() else None
            if u["cell"] not in qsha:
                qsha[u["cell"]] = hashlib.sha256(json.dumps((st or {}).get("checkpoint") or u["cell"], sort_keys=True).encode()).hexdigest()[:16]
            e = u.get("E") or {}
            excl = u.get("excluded")
            status = ("missing" if excl else "divergent" if u.get("div") else "no_divergence")
            rec = {
                "schema_version": "consequence-v1", "source_commit": git, "analysis_commit": git, "snapshot_id": sid,
                "split": a.split, "task_pool_manifest_sha": splits_sha, "suite": "tau2", "domain": u["domain"],
                "task_id": u["task"].split(":", 1)[1], "model_id": u["model"], "cell": u["cell"],
                "quantizer_config_sha": qsha.get(u["cell"]), "calibration_draw_id": "d1" if ("gptq" in u["cell"] or "awq" in u["cell"]) else None,
                "prompt_block_id": u["block"], "prompt_nonce_sha": hashlib.sha256(str((st or {}).get("nonce")).encode()).hexdigest()[:16] if st else None,
                "simulator_config_sha": hashlib.sha256(json.dumps((st or {}).get("simulator"), sort_keys=True).encode()).hexdigest()[:16] if st else None,
                "user_seed": ((st or {}).get("simulator") or {}).get("sim_seed"), "continuation_repeat_id": None,
                "randomness_coupling": "deterministic-frozen", "state_bank_id": "legacy-first-semantic-divergence",
                "state_id": u.get("state_id"), "history_sha": (st or {}).get("history_sha"), "env_sha": (hashlib.sha256(json.dumps(st["env_hash"], sort_keys=True).encode()).hexdigest()[:16] if st else None),
                "prompt_ids_sha": ((st or {}).get("q_decision") or {}).get("prompt_ids_sha"), "decision_idx": u.get("t"),
                "selection_probability": 1.0, "analysis_weight": 1.0, "eligibility_status": status, "missing_reason": excl,
                "replay_gate_pass": None if excl else True, "evaluator_id": EVAL.get(u["domain"]),
                "Y": ({k: u["Y"][k] for k in ("BB", "BQ", "QB", "QQ")} if status == "divergent" else
                      {"BB": None, "BQ": None, "QB": None, "QQ": u["Y"]["QQ"]} if status == "no_divergence" else None),
                "pattern_BB_BQ_QB_QQ": e.get("pattern"),
                "effects": ({k: e[k] for k in ("A", "C", "I", "G", "H", "F")} if status == "divergent" else
                            {"A": None, "C": None, "I": None, "G": 0, "H": None, "F": None} if status == "no_divergence" else None),
                "primary_policy_gain": (e.get("G") if status != "missing" else None),
                "effect_source": e.get("effect_source") if status != "missing" else None,
                "rescue": e.get("rescue") if status != "missing" else None, "damage": e.get("damage") if status != "missing" else None,
                "gross_change": e.get("M") if status != "missing" else None,
                "strict_reversal_observed": (bool(e["strict_reversal"]) if status == "divergent" else None),
                "divergence_category": u.get("category"), "divergence_type": u.get("type"),
                "branch_artifact_refs": ({"dir": u["dir"], "state": f"states/{u['state_id']}.json"} if u.get("state_id") else {"dir": u["dir"]}),
                "process_cost_refs": None, "annotation_refs": None}
            fh.write(json.dumps(rec) + "\n")

    # ---- 16 patterns
    pp = OUT / f"patterns16_{sid}.csv"
    rows = []
    cells = sorted({(u["model"], u["cell"]) for u in ok})
    for m, c in cells:
        cu = [u for u in ok if u["model"] == m and u["cell"] == c and u["div"]]
        for dom in sorted({u["domain"] for u in cu}) + ["all"]:
            sub = [u for u in cu if dom == "all" or u["domain"] == dom]
            cnt = defaultdict(int)
            for u in sub:
                cnt[u["E"]["pattern"]] += 1
            n = len(sub)
            for p in PATTERNS:
                e = pattern_effects(p)
                rows.append({"model": m, "cell": c, "domain": dom, "calibration_draw_id": "d1" if ("gptq" in c or "awq" in c) else "",
                             "state_bank_id": "legacy-first-semantic-divergence", "pattern_BB_BQ_QB_QQ": p, "count": cnt[p],
                             "fraction_of_divergent": round(cnt[p] / n, 6) if n else "", "n_divergent": n,
                             "G": e["G"], "H": e["H"], "F": e["F"], "A": e["A"], "C": e["C"], "I": e["I"], "strict_reversal": e["strict_reversal"]})
            assert sum(cnt.values()) == n
    with open(pp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- estimands
    bo = defaultdict(set)
    for u in ok:
        bo[u["task"]].add(u["block"])
    boot = AD.Boot(sorted(bo), {k: sorted(v) for k, v in bo.items()}, B=a.B)
    draws: dict = {}
    est = {}
    for m, c in cells:
        cu = [u for u in ok if u["model"] == m and u["cell"] == c]
        div = [u for u in cu if u["div"]]
        for x, y in CONTRASTS.values():
            contrast_units(div, x, y)
        lab = f"{m}:{c}"
        full = {}
        for s in ("G", "rescue", "damage", "M", "H_policy", "F_policy"):
            pt, dr = boot.task_mean(*boot.arrays(cu, s))
            full[s] = AD.summarise(pt, dr)
            draws.setdefault(lab, {})[s] = (pt, dr, dr.block_means, dr.crossed, dr.crossed_pt)
        assert abs(full["G"]["est"] - (full["rescue"]["est"] - full["damage"]["est"])) < 1e-6 + 1e-3, (lab, full)
        assert abs(full["M"]["est"] - (full["rescue"]["est"] + full["damage"]["est"])) < 1e-3, (lab, full)
        cond = {}
        for name, (x, y) in CONTRASTS.items():
            r = {}
            for s, key in (("mean", name), ("pos", f"pos_{x}{y}"), ("neg", f"neg_{x}{y}"), ("turnover", f"turn_{x}{y}")):
                r[s] = AD.summarise(*boot.ratio(*boot.arrays(div, key)))
            r["contrast"] = f"Y_{x} - Y_{y}"
            cond[name] = r
        cond["I"] = {"mean": AD.summarise(*boot.ratio(*boot.arrays(div, "I"))),
                     "distribution": {str(v): sum(1 for u in div if u["E"]["I"] == v) for v in (-2, -1, 0, 1, 2)}}
        cond["strict_reversal"] = AD.summarise(*boot.ratio(*boot.arrays(div, "strict_reversal")))
        cond["I_nonzero"] = {"n": sum(1 for u in div if u["E"]["I"] != 0), "of": len(div)}
        cond["strict_reversal_counts"] = {"0110": sum(1 for u in div if u["E"]["pattern"] == "0110"),
                                          "1001": sum(1 for u in div if u["E"]["pattern"] == "1001"), "of": len(div)}
        for u in div:  # identities on every unit
            E = u["E"]
            assert E["G"] == E["A"] + E["I"] and E["H"] == E["C"] + E["I"] and E["F"] == E["A"] + E["C"] + E["I"]
        est[lab] = {"n_units": len(cu), "n_divergent": len(div), "n_no_divergence": len(cu) - len(div),
                    "n_blocks": len({u["block"] for u in cu}), "domains": sorted({u["domain"] for u in cu}),
                    "primary_pivot_G_all": full, "pivot_four_branch_conditional": cond}
    pools = {}
    for fam in sorted({AD.family(c) for _, c in cells}):
        labs = [f"{m}:{c}" for m, c in cells if AD.family(c) == fam]
        for mm in sorted({m for m, c in cells if AD.family(c) == fam}):
            pools[f"{fam}:{mm}"] = AD.pooled(draws, [l for l in labs if l.startswith(mm + ":")])
        pools[f"{fam}:all"] = AD.pooled(draws, labs)
    ep = OUT / f"consequence_estimands_{sid}.json"
    ep.write_text(json.dumps({
        "schema_version": "consequence-v1", "label": "exploratory development analysis (outcomes previously viewed)",
        "snapshot": {"id": sid, "sha256": AD.sha256(a.snapshot)}, "analysis_commit": git, "script_sha256": AD.sha256(__file__),
        "analyze_dev_sha256": AD.sha256(AD.__file__), "split": split_info, "sign_dictionary": AD.SIGN_DICTIONARY,
        "pattern_table_check": "16 patterns generated from the equations equal CONSEQUENCE_ANALYSIS_PLAN §3 (asserted)",
        "inference": {"fixed_task_pool": "complete shared blocks: block bootstrap if >= 10 blocks else t over block means",
                      "crossed": "task x block bootstrap (tasks and blocks resampled jointly)", "B": a.B, "seed": AD.SEED,
                      "weights": "equal per task within block, equal per block; pools equal per cell within family"},
        "cells": est, "pools_primary_policy": pools, "units_file": up.name, "patterns_file": pp.name}, indent=1,
        default=lambda o: o.item() if hasattr(o, "item") else str(o)))

    # ---- coverage tensor
    need = {d: {str(t) for t in ts} for d, ts in json.load(open(AD.SPLITS))["splits"][a.split]["tasks"].items()}
    tens = defaultdict(lambda: {"observed": 0, "divergent": 0, "no_divergence": 0, "excluded": defaultdict(int)})
    for u in units:
        k = f"{u['model']}:{u['cell']}|{u['domain']}|{u['block']}"
        t = tens[k]
        t["observed"] += 1
        if "excluded" in u:
            t["excluded"][u["excluded"].split(":")[0]] += 1
        elif u["div"]:
            t["divergent"] += 1
        else:
            t["no_divergence"] += 1
    cov = {}
    for k, t in sorted(tens.items()):
        lab, dom, blk = k.split("|")
        cov[k] = {**{x: t[x] for x in ("observed", "divergent", "no_divergence")}, "excluded": dict(t["excluded"]),
                  "expected": len(need.get(dom, ())), "complete": k not in incomplete}
    common = {}
    for m in sorted({m for m, _ in cells}):
        for dom in ("retail", "airline", "telecom"):
            per_cell = {c: {k.split("|")[2] for k, v in cov.items() if k.startswith(f"{m}:{c}|{dom}|") and v["complete"]} for mm, c in cells if mm == m}
            per_cell = {c: b for c, b in per_cell.items() if b}
            if len(per_cell) >= 2:
                inter = sorted(set.intersection(*per_cell.values()))
                common[f"{m}|{dom}"] = {"cells": sorted(per_cell), "common_complete_blocks": inter,
                                        "excluded_from_intersection": {c: sorted(b - set(inter)) for c, b in per_cell.items()}}
    cp = OUT / f"coverage_{sid}.json"
    cp.write_text(json.dumps({"snapshot_id": sid, "split": split_info, "quarantined_dirs": sorted(quarantined),
                              "incomplete_blocks": incomplete, "tensor": cov, "common_intersections": common,
                              "duplicate_units_dropped": len(allu) - len(units), "block_rule": "complete-case sensitivity" if a.complete_case else "strict (W70)"}, indent=1))
    print(f"analyze_patterns: wrote {up.name}, {pp.name}, {ep.name}, {cp.name} ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
