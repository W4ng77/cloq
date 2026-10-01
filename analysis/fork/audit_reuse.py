"""WP0 (W68): evidence-reuse manifest, population alignment and block-coverage audit (EXECUTION_PLAN §3, §9 WP0;
CONSEQUENCE_ANALYSIS_PLAN §4.1).

1. OLD_RESULT_REUSE.csv (docs/OLD_RESULT_REUSE.csv): one row per evidence source with path, sha256, generating script and
   the commit that last changed the file, hardware/backend, task population, checkpoint/draw, nonce blocks, endpoint,
   integrity status, permitted claim and required reanalysis. Rows are curated here (SOURCES) from analysis/RESULTS_INDEX.md
   and docs/RESEARCH_LOG.md. Paths resolve to the latest committed file matching the pattern.
2. Common-population panel: the primary-policy G, r, d, M (analyze_dev units, split guard, complete blocks) per cell
   (a) on its own population (every complete block, every domain it has: q8 W4 includes telecom dev), and
   (b) on the common retail/airline pool: the 85 split tasks x the blocks complete in EVERY compared cell (q4/q8 x
   GPTQ-W4, AWQ-W4, KV8), equal-task weights within block, equal block weights. Fixed-task (block) and crossed intervals.
3. Block coverage: every admitted closed-loop run of the fork-relevant cells must cover its full frozen split task pool
   per domain (snapshot n_tasks and infra_missing). Uncovered blocks are listed for completion/quarantine, never
   filtered to a complete-case subset.

usage: python analysis/fork/audit_reuse.py --snapshot <snapshot.json>
-> docs/OLD_RESULT_REUSE.csv, analysis/fork/out/population_panel_<s>.{json,md}, analysis/fork/out/block_coverage_<s>.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
A6 = "A6000 (sm86), vLLM 0.29 batch-invariant, frozen numerics + canary"
R85 = "tau2 retail 58 + airline 27 (manifests/eval_tasks_v0.json)"
SOURCES = [  # id, pattern, script, hardware, population, checkpoint/draw, blocks, endpoint, integrity, permitted claim, required reanalysis
    ("forks_tau2_all", "analysis/fork/out/dev_all_*.json", "analysis/fork/analyze_dev.py", A6,
     R85 + "; telecom dev 80 for q8 W4 telecom blocks", "q4/q8 GPTQ-W4 d1 + AWQ-W4 c1; KV8; stress (GPTQ-W3, KV4-rot, RTN-W3)",
     "q1-q5, f01-f17 (complete blocks only)", "primary_pivot_G_all + r/d/M; conditional A/C/I/H/F",
     "replay gate PASS (W30); W63 block-level inference; W68 sign dictionary", "two-sided consequences at first semantic divergence under the tested conditions",
     "common 85-task panel for cross-cell comparisons (population_panel); telecom separately"),
    ("patterns16", "analysis/fork/out/patterns16_*.csv", "analysis/fork/analyze_patterns.py", A6, R85 + " (+ telecom dev)", "as forks_tau2_all",
     "complete blocks", "16 outcome patterns, strict reversal", "W68", "descriptive pattern frequencies on divergent states", "none"),
    ("forks_ext", "analysis/fork/out/ext_*.json", "analysis/fork/analyze_ext.py", A6, "ALFWorld games; BFCL multi-turn entries",
     "q4/q8 GPTQ-W4, AWQ-W4, GPTQ-W3, KV4", "one run per item", "G_all, r/d/M (item-level)", "ext replay gate PASS (W39-extfork)",
     "external triangulation; item-level inference only", "none beyond item-level labelling"),
    ("w67_consequence", "analysis/fork/out/consequence_2*.json", "analysis/fork/analyze_consequence.py", A6, "mixed 85-task and 165-task pools",
     "W4, KV8", "q1-q5, f01-f17 (+ 2 telecom blocks)", "task concentration, sign consistency, overlap", "exploratory; nulls ignore block/task dependence",
     "hypotheses only (CONSEQUENCE_ANALYSIS_PLAN §5)", "audit_w67.py: dependence-preserving references, nonce-split replication"),
    ("pivot_detection", "analysis/fork/out/pivot_2*.json", "analysis/fork/analyze_pivot.py", A6, R85, "as forks_tau2_all", "complete blocks",
     "AUROC of Q uncertainty for first divergence; oracle contrasts", "exploratory", "detectability descriptive; oracle values are not policy values",
     "closed-loop escalation evaluation (FORK_PROTOCOL §14)"),
    ("difficulty", "analysis/fork/out/difficulty_*.json", "analysis/fork/analyze_difficulty.py", A6, R85, "as forks_tau2_all", "complete blocks",
     "moderators of G/A/C/I", "exploratory; realised-horizon moderator confounded", "descriptive", "fork-time strata only for confirmation"),
    ("restoration", "analysis/fork/out/restore_eval_*.json", "analysis/fork/analyze_restore_eval.py", A6, R85 + "; telecom dev f01-f06 for W53",
     "GPTQ-W4/W3, RTN-W3, AWQ-W4 bases; restore/resid/recal arms", "f01-f03 / q3-q5 (3 blocks)", "closed-loop success, turnover",
     "paused (W67); t over 3 blocks", "negative deployment result (dominated by GPTQ-W4 at matched storage); diagnostics only", "none (paused)"),
    ("pivot_arms", "analysis/fork/out/pivot_arms_*.json", "analysis/fork/analyze_pivot_arms.py", A6, "150 sampled fork states per cell",
     "W4, GPTQ-W3, RTN-W3 arms", "states from q3-q5 / dev blocks", "action reversion at the pivot", "selection rule §13 + amendments 1-2",
     "module-level action reversion vs byte-matched random", "RTN-W3 cells pending"),
    ("success_ni_aligned", "analysis/insights/iter_4/out/success_ni_ALIGNED_*.json", "analysis/insights/iter_4/success_ni_aligned.py", A6, R85,
     "W4 cells", "paired nonce blocks", "whole-episode success Q - B, NI/TOST", "task-resampled TOST fails (W64)",
     "NI/TOST language with all intervals; no global equivalence", "none"),
    ("success_ni_real", "analysis/insights/iter_4/out/success_ni_REAL_*.json", "analysis/insights/iter_4/success_ni.py", A6, R85,
     "W4 cells", "q1-q5", "success NI", "superseded by ALIGNED for fork-aligned claims", "historical", "use ALIGNED"),
    ("prereg_h1_h4", "analysis/insights/iter_4/out/prereg_h1_h4_CONF_*.json", "analysis/insights/iter_4/prereg_h1_h4.py", A6, R85,
     "GPTQ/AWQ-W4 d3/d4, Gaussian k=1 s2/s4/s5 (28 runs)", "q1/q2", "H1-H4 (lottery, net effect, fingerprint)",
     "preregistered confirmatory (W25); H3 later corrected (W29)", "negative confirmation of the checkpoint lottery", "none; keep as negative result"),
    ("h3_corrected", "analysis/insights/iter_4/out/h3_corrected_2*.json", "analysis/insights/iter_4/h3_corrected.py", A6, R85,
     "W4 recalibrations; random fixed perturbations", "q1/q2", "split-task fingerprint, corrected permutation", "corrected (W29)",
     "no detected W4 fingerprint; random-perturbation fingerprint exploratory", "none"),
    ("act_talk_selection", "analysis/insights/iter_4/out/act_talk_selection_*.json", "analysis/insights/iter_4/act_talk_selection.py", A6, R85,
     "W4", "q1-q5", "conditional act/talk shift vs selection null", "W29", "no quantization-specific act/talk channel claim",
     "new unconditional, null-controlled evidence before any claim"),
    ("turnover_floor", "analysis/insights/iter_3/out/r10_turnover_stats_live_*.json", "analysis/insights/iter_3/r10_turnover_stats.py", A6,
     R85, "W4 and controls, 5 models", "nonce draws", "task-outcome turnover vs numerics floor", "gated snapshot 20260929T1937Z",
     "motivation under tested serving conditions", "none"),
    ("wakv", "analysis/ahook/out/wakv_*.json", "analysis/ahook/analyze_wakv.py", A6, R85, "W x A x KV cube (QuaRot-rotated), kv16r controls",
     "f01-f06", "closed-loop success interactions", "WAKV_PREREG (q8 four corners)", "registered four corners; other interactions exploratory", "none"),
    ("gate", "analysis/fork/gate/*/gate*.json", "scripts/a6000/fork_driver.py", A6, "selected gate states", "q4 GPTQ, q8 AWQ, KVQ, QuaRot",
     "gate blocks", "replay acceptance (a)-(e)", "PASS", "engineering validity of replay for covered configurations", "repeat gates for new configurations"),
    ("v0_v1_4080", "analysis/results.json", "analysis/* (v0/v1, 4080)", "RTX 4080 (different backend)", "earlier eval set",
     "v0/v1 calibration arms", "single draw / 3 draws", "success, open-loop NLL", "historical", "history only; never pooled with A6000",
     "validated backend comparison before any pooling"),
]


def latest(pattern: str) -> str | None:
    fs = sorted(glob.glob(str(ROOT / pattern)))
    tracked = set(subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True).stdout.split())
    fs_t = [f for f in fs if str(Path(f).relative_to(ROOT)) in tracked]
    return (fs_t or fs or [None])[-1]


def last_commit(p: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%h", "--", p], capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    snap = json.load(open(a.snapshot))
    sid = snap["snapshot_id"]

    # 1. reuse manifest
    rows = []
    for (rid, pat, script, hw, pop, ck, blocks, endpoint, integ, claim, re_an) in SOURCES:
        p = latest(pat)
        rel = str(Path(p).relative_to(ROOT)) if p else None
        rows.append({"id": rid, "source_path": rel, "sha256": AD.sha256(p) if p else None, "generating_script": script,
                     "file_last_commit": last_commit(rel) if rel else None, "script_last_commit": last_commit(script.split(" ")[0]),
                     "hardware_backend": hw, "task_population": pop, "checkpoint_draw": ck, "nonce_blocks": blocks, "endpoint": endpoint,
                     "integrity_status": integ, "permitted_claim": claim, "required_reanalysis": re_an})
    cp = ROOT / "docs/OLD_RESULT_REUSE.csv"
    with open(cp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # 2. population panel
    loaded = [AD.load_dir(d, snap, {}) for d in AD.discover(False)]
    allu = [u for L in loaded for u in L["units"]]
    AD.split_guard(allu, "dev", "audit_reuse")
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined")
    units, _ = AD.dedupe_units(allu)
    AD.mark_incomplete_blocks(units, "dev", strict=True)
    units = [u for u in units if "excluded" not in u]
    for u in units:
        u["E"] = AD.effects(u["Y"], u["div"])
    compared = [(m, c) for m in ("q4", "q8") for c in ("gptq_w4_d1", "awq_w4", "kvq_int8")]
    blocks_of = {mc: {(u["domain"], u["block"]) for u in units if (u["model"], u["cell"]) == mc} for mc in compared}
    present = [mc for mc in compared if blocks_of[mc]]
    common = {}
    for dom in ("retail", "airline"):
        sets = [{b for d, b in blocks_of[mc] if d == dom} for mc in present]
        common[dom] = sorted(set.intersection(*sets)) if sets else []
    bo = defaultdict(set)
    for u in units:
        bo[u["task"]].add(u["block"])
    boot = AD.Boot(sorted(bo), {k: sorted(v) for k, v in bo.items()}, B=a.B)
    panel = {}
    for mc in present:
        cu = [u for u in units if (u["model"], u["cell"]) == mc]
        com = [u for u in cu if u["domain"] in ("retail", "airline") and u["block"] in common[u["domain"]]]
        r = {}
        for name, us in (("cell_specific", cu), ("common_85_task_pool", com)):
            r[name] = {"n_units": len(us), "n_tasks": len({u["task"] for u in us}), "domains": sorted({u["domain"] for u in us}),
                       "blocks": sorted({u["block"] for u in us}),
                       **{s: AD.summarise(*boot.task_mean(*boot.arrays(us, s))) for s in ("G", "rescue", "damage", "M")}}
        panel[f"{mc[0]}:{mc[1]}"] = r
    res = {"snapshot_id": sid, "compared_cells": [f"{m}:{c}" for m, c in present], "common_complete_blocks": common,
           "weights": "equal per task within block, equal per block (fixed task pool); crossed task x block secondary",
           "panel": panel}
    pp = OUT / f"population_panel_{sid}.json"
    pp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))

    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"
    L = [f"**TL;DR** Common-population panel: G/r/d/M per cell on its own population vs the common 85-task retail/airline pool "
         f"on the {len(common['retail'])} retail / {len(common['airline'])} airline blocks complete in all compared cells.", "",
         f"# Population panel ({sid})", "", "| cell | population | units | tasks | blocks | G | r | d | M |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in panel.items():
        for name, x in v.items():
            L.append(f"| {k} | {name} | {x['n_units']} | {x['n_tasks']} | {len(x['blocks'])} | {f(x['G'])} | {x['rescue']['est']:.1f} | "
                     f"{x['damage']['est']:.1f} | {x['M']['est']:.1f} |")
    L += ["", f"Common complete blocks: retail {common['retail']}; airline {common['airline']}."]
    (OUT / f"population_panel_{sid}.md").write_text("\n".join(L) + "\n")

    # 3. block coverage of admitted closed-loop runs
    need = {d: len(ts) for d, ts in json.load(open(AD.SPLITS))["splits"]["dev"]["tasks"].items()}
    rx = re.compile(r"^a6k2_(q4|q8)_(tel_)?(gptq_w4_d1|awq_w4|kvq_int8|kvq_int4_rot|gptq_w3|rtn_w3|bfpair)_(q\d|f\d\d)$")
    cov, bad = {}, []
    for rid, doms in snap["frozen"].items():
        if not rx.match(rid):
            continue
        for dom, fr in doms.items():
            n = fr.get("n_tasks")
            infra = fr.get("infra_missing") or []
            okc = (n == need.get(dom)) and not infra
            cov[f"{rid}|{dom}"] = {"n_tasks": n, "expected": need.get(dom), "infra_missing": infra, "complete": okc}
            if not okc:
                bad.append(f"{rid}|{dom}")
    bp = OUT / f"block_coverage_{sid}.json"
    bp.write_text(json.dumps({"snapshot_id": sid, "rule": "admitted run covers its full frozen split pool per domain, no infra-missing episodes",
                              "n_runs_domains": len(cov), "n_incomplete": len(bad), "incomplete": bad, "runs": cov}, indent=1))
    print(f"audit_reuse: {cp.relative_to(ROOT)} ({len(rows)} sources), {pp.name}, {bp.name}: {len(bad)}/{len(cov)} run-domains "
          f"not covering their pool ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
