"""Strata cut points for the telecom holdout confirmation (W86), fixed on telecom DEV data only.

PREREG_FORK_CONFIRM.md §9 references the output by sha256: manifests/fork/holdout_cutpoints_v1.json.
No holdout task id, trajectory or outcome is read: every input is a telecom dev run (blocks f01-f06, task file
manifests/telecom/dev_v1.json) or a dev fork unit, and analyze_dev.split_guard aborts on any holdout unit. Reading a BF16
trajectory whose task id is in the holdout also aborts.

Inputs (snapshot-admitted only):
  - fork units of analysis/fork/telecom/q8_{gptq_w4_d1,awq_w4}/g1-g3 (q8 GPTQ-W4 d1 and q8 AWQ-W4, f01-f06): remaining
    step budget at t* (state budget.steps_left) of every divergent unit, pooled over the two cells;
  - BF16 pair runs a6k2_{q4,q8}_tel_bfpair_f01..f06 (telecom dev): per task, the BF16 success rate and the mean number of
    agent decisions over all admitted, non-infrastructure episodes of both models (pooled, 12 episodes per task);
  - the 80 dev task ids: number of injected faults (the '|'-separated items between ']' and '[PERSONA').
Rules (stated in the prereg; tertile labels T1 = v <= c1, T2 = c1 < v <= c2, T3 = v > c2, as analyze_difficulty):
  step_budget, task_length, n_faults: tie-aware balanced tertiles of the dev values (balanced_tertile_cuts);
  bf16_difficulty: bins "0" (rate == 0), "low" (0 < rate <= c), "high" (rate > c), c = median of the positive dev rates.

usage: python analysis/fork/make_holdout_cutpoints.py --snapshot <snapshot.json>  -> manifests/fork/holdout_cutpoints_v1.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402

ROOT = AD.ROOT
OUTP = ROOT / "manifests/fork/holdout_cutpoints_v1.json"
DEV_BLOCKS = ("f01", "f02", "f03", "f04", "f05", "f06")
BF_RE = re.compile(r"^a6k2_(q4|q8)_tel_bfpair_(f0[1-6])$")


def n_faults(tid: str) -> int:
    return len(tid.split("]", 1)[1].split("[", 1)[0].split("|"))


def issue_type(tid: str) -> str:
    return tid[1:].split("]", 1)[0]


def bf16_task_stats(snap: dict, run_re: re.Pattern, allowed: set, forbidden: set) -> dict:
    """task id -> {'succ', 'len', 'n'} pooled over every admitted BF16 pair run matching run_re (both models).
    Episodes of infrastructure-missing tasks are skipped. A task outside `allowed` is skipped; one in `forbidden` aborts."""
    acc: dict = {}
    for rid, doms in sorted(snap["frozen"].items()):
        if not run_re.match(rid) or "telecom" not in doms:
            continue
        fr = doms["telecom"]
        infra = set(map(str, fr.get("infra_missing") or []))
        man = ROOT / "runs" / rid / "telecom" / "task_manifest.json"
        if man.exists():
            ids = {str(t) for t in json.load(open(man)).get("task_ids", [])}
            if ids & forbidden:
                raise SystemExit(f"bf16_task_stats: {rid} contains task(s) of a forbidden split; refusing to read it")
        for ln in open(ROOT / "runs" / rid / "telecom" / "trajectory.jsonl"):
            t = json.loads(ln)
            tid = str(t["task_id"])
            if tid in forbidden:
                raise SystemExit(f"bf16_task_stats: {rid} holds a task of a forbidden split; refusing")
            if tid not in allowed or tid in infra or t.get("termination_reason") == "infrastructure_error":
                continue
            n0 = len(((t.get("task") or {}).get("initial_state") or {}).get("message_history") or []) or 1
            a = acc.setdefault(tid, {"y": [], "len": []})
            a["y"].append(AD.success("telecom", t))
            a["len"].append(sum(1 for x in t["messages"][n0:] if x["role"] == "assistant"))
    return {k: {"succ": float(np.mean(v["y"])), "len": float(np.mean(v["len"])), "n": len(v["y"])} for k, v in acc.items()}


def balanced_tertile_cuts(x) -> list[float]:
    """Tie-aware tertile cuts: among pairs of observed distinct values c1 < c2, the pair minimising the sum over the three
    bins (T1: v <= c1, T2: c1 < v <= c2, T3: v > c2) of (bin share - 1/3)^2; ties broken by the smaller (c1, c2). For a
    continuous variable this is the empirical tertile; for a discrete one with heavy ties (step budget: 38% of dev values
    are 199) plain quantiles leave a bin empty."""
    x = np.asarray(x, float)
    vals = np.unique(x)
    best = None
    for i, c1 in enumerate(vals):
        for c2 in vals[i + 1:]:
            sh = np.array([np.mean(x <= c1), np.mean((x > c1) & (x <= c2)), np.mean(x > c2)])
            loss = float(np.sum((sh - 1 / 3) ** 2))
            if best is None or loss < best[0] - 1e-15:
                best = (loss, float(c1), float(c2))
    return [best[1], best[2]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    a = ap.parse_args()
    snap = json.load(open(a.snapshot))
    man = json.load(open(AD.SPLITS))
    dev = {str(t) for t in man["splits"]["dev"]["tasks"]["telecom"]}
    hold = {str(t) for t in man["splits"]["holdout"]["tasks"]["telecom"]}
    # (1) remaining step budget at t*: dev fork units, q8 GPTQ-W4 d1 + q8 AWQ-W4, f01-f06
    cache, units = {}, []
    dirs = [d for d in AD.discover(False) if "analysis/fork/telecom/" in str(d)]
    for d in dirs:
        r = AD.load_dir(d, snap, cache)
        for u in r["units"]:
            if r["quarantined"]:
                u.setdefault("excluded", "quarantined")
            units.append(u)
    guard = AD.split_guard(units, "dev", "make_holdout_cutpoints")
    units, _ = AD.dedupe_units(units)
    units = [u for u in units if "excluded" not in u and u["domain"] == "telecom" and u["block"] in DEV_BLOCKS
             and u["model"] == "q8" and u["cell"] in ("gptq_w4_d1", "awq_w4")]
    steps = [u["steps_left"] for u in units if u["div"]]
    # (2) BF16 per-task difficulty and length, q4 + q8 bfpair f01-f06
    bf = bf16_task_stats(snap, BF_RE, dev, hold)
    assert set(bf) == dev, f"BF16 stats cover {len(bf)} of {len(dev)} dev tasks"
    succ = np.array([bf[t]["succ"] for t in sorted(dev)])
    lens = np.array([bf[t]["len"] for t in sorted(dev)])
    nf = np.array([n_faults(t) for t in sorted(dev)])
    c_bf = float(np.median(succ[succ > 0]))
    q = balanced_tertile_cuts

    def counts(vals, cuts):
        return {"T1": int(np.sum(vals <= cuts[0])), "T2": int(np.sum((vals > cuts[0]) & (vals <= cuts[1]))), "T3": int(np.sum(vals > cuts[1]))}

    st = np.asarray(steps, float)
    out = {
        "schema": "holdout-cutpoints-v1",
        "purpose": "Strata cut points for docs/insights/PREREG_FORK_CONFIRM.md §9, fixed on telecom DEV data only (W86).",
        "script": "analysis/fork/make_holdout_cutpoints.py", "script_sha256": AD.sha256(__file__),
        "snapshot": {"id": snap.get("snapshot_id"), "path": str(Path(a.snapshot).resolve().relative_to(ROOT)), "sha256": AD.sha256(a.snapshot)},
        "split_guard": guard, "holdout_read": False,
        "tertile_rule": ("labels T1: v <= c1; T2: c1 < v <= c2; T3: v > c2; (c1, c2) = the pair of observed distinct dev values "
                         "minimising sum_k (share_k - 1/3)^2 over the three bins, ties to the smaller pair (balanced_tertile_cuts)"),
        "families": {
            "step_budget": {"variable": "remaining step budget at t* (state budget.steps_left = max_steps - steps used before t*); unit-level, divergent units only",
                            "source": "telecom dev fork units, q8 gptq_w4_d1 + q8 awq_w4, blocks f01-f06, divergent units pooled",
                            "n_values": int(len(st)), "cuts": q(st), "levels": ["T1", "T2", "T3"], "dev_counts": counts(st, q(st))},
            "persona": {"variable": "PERSONA:<x> parsed from the task id", "levels": ["Hard", "None", "Easy"], "cuts": None},
            "bf16_difficulty": {"variable": "task BF16 success rate (official_reward == 1), pooled over the q4 and q8 BF16 pair episodes of the analysis blocks",
                                "source": "a6k2_{q4,q8}_tel_bfpair_f01..f06 (dev), 12 episodes per task",
                                "rule": "'0': rate == 0; 'low': 0 < rate <= c; 'high': rate > c; c = median of the positive dev task rates",
                                "c": c_bf, "levels": ["0", "low", "high"],
                                "dev_counts": {"0": int(np.sum(succ == 0)), "low": int(np.sum((succ > 0) & (succ <= c_bf))), "high": int(np.sum(succ > c_bf))}},
            "task_length": {"variable": "task mean number of agent decisions over the q4 and q8 BF16 pair episodes of the analysis blocks",
                            "source": "a6k2_{q4,q8}_tel_bfpair_f01..f06 (dev), 12 episodes per task",
                            "cuts": q(lens), "levels": ["T1", "T2", "T3"], "dev_counts": counts(lens, q(lens))},
            "issue_type": {"variable": "issue type parsed from the task id prefix [<issue>]", "levels": ["mms_issue", "mobile_data_issue", "service_issue"], "cuts": None},
            "n_faults": {"variable": "number of injected faults = '|'-separated items between ']' and '[PERSONA' in the task id",
                         "source": "the 80 telecom dev task ids", "cuts": q(nf), "levels": ["T1", "T2", "T3"], "dev_counts": counts(nf, q(nf))},
        },
        "n_dev_tasks": len(dev), "dev_blocks": list(DEV_BLOCKS),
    }
    OUTP.write_text(json.dumps(out, indent=1) + "\n")
    print(OUTP.relative_to(ROOT), AD.sha256(OUTP))
    print(json.dumps({k: {kk: v.get(kk) for kk in ("cuts", "c", "dev_counts")} for k, v in out["families"].items()}))


if __name__ == "__main__":
    main()
