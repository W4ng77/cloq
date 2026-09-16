"""First-divergence analysis (plan section 16).

For each held-out task, align the BF16 and quantized closed-loop trajectories
from the same initial state and find
    t* = min{ t : Norm(a_t^Q) != Norm(a_t^FP) }
over agent decision indices. Because the user simulator is deterministic
(batch-invariant serving), identical agent actions produce identical
observations, so decision t of both trajectories sees the same context up to
t*. We verify that by also comparing prompt hashes and report the first index
where prompts differ (should be == t* + 1 or never).

usage: python -m cloq.divergence --bf16-run bf16 --arm-run static_eval --domain airline --eval-file manifests/eval_tasks_v0.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from cloq import config as C
from cloq.metrics import load_decisions, normalize_action, read_jsonl


def load_decisions_by_task(run_id: str, domain: str, task_ids: set[str]) -> dict[str, list[dict]]:
    by = defaultdict(list)
    for d in load_decisions(C.RUNS_DIR / run_id / domain):
        if d["task_id"] in task_ids:
            by[d["task_id"]].append(d)
    for v in by.values():
        v.sort(key=lambda d: d["decision_idx"])
    return by


def load_traj(run_id: str, domain: str) -> dict[str, dict]:
    return {t["task_id"]: t for t in read_jsonl(C.RUNS_DIR / run_id / domain / "trajectory.jsonl")}


def analyze_task(fp: list[dict], q: list[dict]) -> dict:
    """t_star  : first decision whose *normalised* action differs (plan definition).
    t_render : first decision whose rendered output differs = (first prompt difference) - 1,
               because the deterministic simulator answers identical rendered messages identically;
               after t_render the two trajectories' contexts are no longer aligned (occupancy alignment).
    t_raw    : first decision whose generated token ids differ (only when ids were recorded)."""
    H = len(fp)
    n = min(len(fp), len(q))
    t_star = None
    t_raw = None
    first_prompt_diff = None
    for i in range(n):
        if first_prompt_diff is None and fp[i]["prompt_sha256"] != q[i]["prompt_sha256"]:
            first_prompt_diff = i
        a_ids, b_ids = fp[i].get("completion_token_ids"), q[i].get("completion_token_ids")
        if t_raw is None and a_ids is not None and b_ids is not None and a_ids != b_ids:
            t_raw = i
        if t_star is None:
            a = normalize_action(fp[i]["content"], fp[i]["tool_calls"])
            b = normalize_action(q[i]["content"], q[i]["tool_calls"])
            if a != b:
                t_star = i
    if first_prompt_diff is not None:
        t_render = max(0, first_prompt_diff - 1)
    elif len(q) != len(fp):
        t_render = n - 1 if n > 0 else 0
    else:
        t_render = None
    if t_star is None and len(q) != len(fp):
        t_star = n  # identical while aligned, different length -> divergence at the end of the shorter one
    t_align = t_render if t_render is not None else t_star
    return {
        "H_fp": H, "H_q": len(q), "t_star": t_star, "diverged": t_star is not None,
        "t_star_norm": (t_star / H) if (t_star is not None and H > 0) else None,
        "t_render": t_render, "t_render_norm": (t_render / H) if (t_render is not None and H > 0) else None,
        "t_raw": t_raw, "t_align": t_align,
        "first_prompt_diff": first_prompt_diff,
        "prompt_consistent": (first_prompt_diff is None) or (first_prompt_diff >= 1 and (t_star is None or t_star >= first_prompt_diff - 1)),
        "t_star_kind_fp": (("tool" if fp[t_star]["tool_calls"] else "text") if (t_star is not None and t_star < len(fp)) else None),
        "t_star_kind_q": (("tool" if q[t_star]["tool_calls"] else "text") if (t_star is not None and t_star < len(q)) else None),
    }


def run(bf16_run: str, arm_run: str, domain: str, eval_ids: list[str], out_path: Path) -> dict:
    ids = set(eval_ids)
    fp = load_decisions_by_task(bf16_run, domain, ids)
    q = load_decisions_by_task(arm_run, domain, ids)
    tfp = load_traj(bf16_run, domain)
    tq = load_traj(arm_run, domain)
    rows = []
    for tid in eval_ids:
        if tid not in fp or tid not in q:
            continue
        r = analyze_task(fp[tid], q[tid])
        r.update({
            "task_id": tid, "fp_db_match": tfp[tid].get("db_match"), "q_db_match": tq[tid].get("db_match"),
            "fp_reward": tfp[tid].get("reward"), "q_reward": tq[tid].get("reward"),
            "q_termination": tq[tid].get("termination_reason"),
        })
        rows.append(r)
    div = [r for r in rows if r["diverged"]]
    tn = [r["t_star_norm"] for r in div if r["t_star_norm"] is not None]
    early = [r for r in div if r["t_star_norm"] is not None and r["t_star_norm"] < 0.5]
    late = [r for r in div if r["t_star_norm"] is not None and r["t_star_norm"] >= 0.5]
    nodiv = [r for r in rows if not r["diverged"]]

    def sr(rs):
        v = [bool(r["q_db_match"]) for r in rs if r["q_db_match"] is not None]
        return float(np.mean(v)) if v else None

    summ = {
        "arm_run": arm_run, "domain": domain, "n_tasks": len(rows),
        "frac_any_divergence": len(div) / len(rows) if rows else None,
        "median_t_star": float(np.median([r["t_star"] for r in div])) if div else None,
        "median_t_star_norm": float(np.median(tn)) if tn else None,
        "mean_t_star_norm": float(np.mean(tn)) if tn else None,
        "frac_any_render_divergence": (sum(1 for r in rows if r["t_render"] is not None) / len(rows)) if rows else None,
        "median_t_render_norm": float(np.median([r["t_render_norm"] for r in rows if r["t_render_norm"] is not None])) if any(r["t_render_norm"] is not None for r in rows) else None,
        "success_given_early_div": sr(early), "n_early": len(early),
        "success_given_late_div": sr(late), "n_late": len(late),
        "success_given_no_div": sr(nodiv), "n_nodiv": len(nodiv),
        "prompt_consistency_rate": float(np.mean([r["prompt_consistent"] for r in rows])) if rows else None,
        "fp_success": sr([{"q_db_match": r["fp_db_match"]} for r in rows]),
        "q_success": sr(rows),
        "per_task": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summ, indent=2))
    print(json.dumps({k: v for k, v in summ.items() if k != "per_task"}, indent=2))
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bf16-run", default="bf16")
    ap.add_argument("--arm-run", required=True)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--eval-file", default=str(C.MANIFEST_DIR / "eval_tasks_v0.json"))
    a = ap.parse_args()
    eval_ids = json.load(open(a.eval_file))[a.domain]
    run(a.bf16_run, a.arm_run, a.domain, eval_ids, C.RUNS_DIR / a.arm_run / a.domain / "divergence.json")


if __name__ == "__main__":
    main()
