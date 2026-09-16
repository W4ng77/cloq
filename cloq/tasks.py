"""Task characterisation and frozen calibration / evaluation split (plan section 6).

Selection uses ONLY the BF16 run: environment stability (termination reason)
and BF16 horizon (= number of agent decision points). Never quantized outcomes.

usage:
  python -m cloq.tasks --bf16-run bf16 --out manifests/task_split_v0.json [--n-cal 20 --n-eval 30]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from cloq import config as C
from cloq.metrics import load_decisions, read_jsonl

# Environment stability (plan section 6), decided from the BF16 pilot ONLY and before any
# quantized run: a task is usable iff its BF16 episode ended through normal conversation
# termination. Episodes that hit the step cap (the 4B user simulator sometimes never emits
# ###STOP### and loops politely) or the tool-error cap have no well-defined task horizon and
# their states are dominated by a degenerate loop, so they cannot serve the horizon analysis.
STABLE_TERMINATIONS = {"user_stop", "agent_stop"}


def characterize(run_dir: Path) -> list[dict]:
    trajs = read_jsonl(run_dir / "trajectory.jsonl")
    decs = load_decisions(run_dir)
    n_dec = defaultdict(int)
    n_trunc = defaultdict(int)
    for d in decs:
        n_dec[d["task_id"]] += 1
        n_trunc[d["task_id"]] += int((d.get("context") or {}).get("truncated", False))
    rows = []
    for t in trajs:
        tid = t["task_id"]
        agent_tool_calls = sum(len(m.get("tool_calls") or []) for m in t["messages"] if m.get("role") == "assistant")
        rows.append({
            "task_id": tid,
            "bf16_db_match": t.get("db_match"),
            "bf16_reward_ignore_basis": t.get("reward"),
            "termination_reason": t.get("termination_reason"),
            "stable": t.get("termination_reason") in STABLE_TERMINATIONS,
            "horizon": n_dec[tid],
            "n_tool_calls": agent_tool_calls,
            "n_messages": t.get("n_messages"),
            "n_truncated_decisions": n_trunc[tid],
        })
    return rows


def stratified_split(rows: list[dict], n_cal: int, n_eval: int, seed: int) -> dict:
    """Stratify by horizon quartile; within each quartile, random assignment with
    the calibration / evaluation ratio preserved as closely as possible."""
    usable = [r for r in rows if r["stable"] and r["horizon"] > 0]
    rng = np.random.default_rng(seed)
    horizons = np.array([r["horizon"] for r in usable])
    qs = np.quantile(horizons, [0.25, 0.5, 0.75])
    for r in usable:
        r["horizon_quartile"] = int(np.searchsorted(qs, r["horizon"], side="right"))  # 0..3
    total = n_cal + n_eval
    if len(usable) < total:
        # preserve 40/60 ratio
        n_cal = int(round(len(usable) * 0.4))
        n_eval = len(usable) - n_cal
        total = len(usable)
    cal, ev = [], []
    by_q = defaultdict(list)
    for r in usable:
        by_q[r["horizon_quartile"]].append(r)
    # allocate the per-quartile quota proportional to quartile size
    sizes = {q: len(v) for q, v in by_q.items()}
    n_take = {q: int(round(total * sizes[q] / len(usable))) for q in sizes}
    # fix rounding so sum == total
    diff = total - sum(n_take.values())
    for q in sorted(sizes, key=lambda q: -sizes[q]):
        if diff == 0:
            break
        step = 1 if diff > 0 else -1
        n_take[q] += step
        diff -= step
    cal_quota_total = n_cal
    for q in sorted(by_q):
        items = list(by_q[q])
        rng.shuffle(items)
        items = items[: n_take[q]]
        n_cal_q = int(round(len(items) * n_cal / total))
        cal.extend(items[:n_cal_q])
        ev.extend(items[n_cal_q:])
    # adjust to exact counts by moving random items between sets
    while len(cal) > n_cal:
        ev.append(cal.pop(rng.integers(len(cal))))
    while len(cal) < n_cal and ev:
        cal.append(ev.pop(rng.integers(len(ev))))
    cal_ids = sorted(r["task_id"] for r in cal)
    ev_ids = sorted(r["task_id"] for r in ev)
    assert not set(cal_ids) & set(ev_ids)
    return {
        "calibration": cal_ids,
        "evaluation": ev_ids,
        "horizon_quartile_edges": [float(x) for x in qs],
        "horizon_by_task": {r["task_id"]: r["horizon"] for r in usable},
        "quartile_by_task": {r["task_id"]: r["horizon_quartile"] for r in usable},
        "excluded_unstable": [r["task_id"] for r in rows if not (r["stable"] and r["horizon"] > 0)],
        "n_usable": len(usable),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bf16-run", default="bf16")
    ap.add_argument("--out", default=str(C.MANIFEST_DIR / "task_split_v0.json"))
    ap.add_argument("--n-cal", type=int, default=None)
    ap.add_argument("--n-eval", type=int, default=None)
    ap.add_argument("--seed", type=int, default=2024)
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"{out} exists; the split is frozen. Delete it explicitly if you really want to re-split.")
    tgt = C.FROZEN["task_split"]["target_per_domain"]
    manifest = {"bf16_run": args.bf16_run, "seed": args.seed, "domains": {}}
    for domain in C.FROZEN["benchmark"]["domains"]:
        run_dir = C.RUNS_DIR / args.bf16_run / domain
        status = json.load(open(run_dir / "status.json"))
        assert status["status"] == "completed", f"{run_dir} not completed"
        rows = characterize(run_dir)
        n_cal = args.n_cal or tgt[domain]["calibration"]
        n_eval = args.n_eval or tgt[domain]["evaluation"]
        split = stratified_split(rows, n_cal, n_eval, args.seed + sum(map(ord, domain)))
        split["characterization"] = rows
        from collections import Counter
        split["termination_counts"] = dict(Counter(r["termination_reason"] for r in rows))
        split["stability_rule"] = sorted(STABLE_TERMINATIONS)
        manifest["domains"][domain] = split
        print(domain, "usable", split["n_usable"], "cal", len(split["calibration"]), "eval", len(split["evaluation"]), "quartile edges", split["horizon_quartile_edges"], "excluded", split["excluded_unstable"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2))
    # flat id files for run_arm --task-file
    (out.parent / "eval_tasks_v0.json").write_text(json.dumps({d: manifest["domains"][d]["evaluation"] for d in manifest["domains"]}, indent=2))
    (out.parent / "cal_tasks_v0.json").write_text(json.dumps({d: manifest["domains"][d]["calibration"] for d in manifest["domains"]}, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
