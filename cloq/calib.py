"""Build token-budget-matched calibration buffers (plan sections 10-11).

Every context is an exact stored model input (post context policy) from a
decision record; the budget counts its prompt tokens. Depth of a decision is
decision_idx / (n_decisions - 1) within its trajectory (0 for length-1).

Arms:
  static  : decision_idx == 0 states (system + tools + greeting + first user request)
            of calibration tasks; cycle through tasks until the budget is met
            (each initial state is unique per task, so with 40 tasks the budget
            forces repeats -> we record the multiplicity; see notes).
  fp_traj : BF16 decision states of calibration tasks, uniform within depth quartile,
            25% of the token budget per quartile.
  cloq    : 50% tokens from fp_traj-style sampling + 50% tokens from Q0 decision states
            (Q0 run on calibration tasks), each depth-stratified.
  q_only  : 100% tokens from Q0 states (optional diagnostic).

usage:
  python -m cloq.calib --arm static  --split manifests/task_split_v0.json --fp-run bf16 --out manifests/calib_static.json
  python -m cloq.calib --arm fp_traj --split ... --fp-run bf16 --out manifests/calib_fp_traj.json
  python -m cloq.calib --arm cloq    --split ... --fp-run bf16 --q-run q0_fp_traj --out manifests/calib_cloq.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from cloq import config as C
from cloq.metrics import read_jsonl


def load_states(run_id: str, domains: list[str], task_ids_by_domain: dict[str, list[str]], source: str) -> list[dict]:
    states = []
    for domain in domains:
        run_dir = C.RUNS_DIR / run_id / domain
        st = json.load(open(run_dir / "status.json"))
        assert st["status"] == "completed", f"{run_dir} not completed"
        allowed = set(task_ids_by_domain[domain])
        decs = [d for d in read_jsonl(run_dir / "decisions.jsonl") if d["task_id"] in allowed]
        by_task = defaultdict(list)
        for d in decs:
            by_task[d["task_id"]].append(d)
        for tid, ds in by_task.items():
            ds.sort(key=lambda d: d["decision_idx"])
            n = len(ds)
            for d in ds:
                depth = d["decision_idx"] / (n - 1) if n > 1 else 0.0
                states.append({
                    "source": source, "run_id": run_id, "domain": domain, "task_id": tid,
                    "trajectory_id": d["trajectory_id"], "decision_idx": d["decision_idx"], "n_decisions": n,
                    "depth": depth, "depth_quartile": min(3, int(depth * 4)) if depth < 1.0 else 3,
                    "n_tokens": len(d["prompt_token_ids"]), "prompt_sha256": d["prompt_sha256"],
                    "prompt_token_ids": d["prompt_token_ids"],
                    "parser_error": d.get("parser_error", False), "finish_reason": d.get("finish_reason"),
                })
    return states


def sample_budget(states: list[dict], budget: int, rng: np.random.Generator, stratify: bool, tol: float) -> list[dict]:
    """Sample without replacement until the token budget is reached within tolerance."""
    chosen = []
    total = 0
    if stratify:
        pools = {q: [s for s in states if s["depth_quartile"] == q] for q in range(4)}
        for q in range(4):
            rng.shuffle(pools[q])
        per_q = budget / 4
        used = {q: 0 for q in range(4)}
        # round-robin over quartiles so each gets ~25% of tokens
        active = True
        while active:
            active = False
            for q in range(4):
                if used[q] >= per_q or not pools[q]:
                    continue
                s = pools[q].pop()
                if total + s["n_tokens"] > budget * (1 + tol):
                    continue
                chosen.append(s); total += s["n_tokens"]; used[q] += s["n_tokens"]; active = True
    else:
        pool = list(states)
        rng.shuffle(pool)
        while pool:
            s = pool.pop()
            if total + s["n_tokens"] > budget * (1 + tol):
                continue
            chosen.append(s); total += s["n_tokens"]
            if total >= budget * (1 - tol):
                break
    return chosen


def _top_up(chosen: list[dict], candidates: list[dict], budget: int, tol: float, rng: np.random.Generator) -> list[dict]:
    """If under budget - tol, greedily add the remaining candidates that fit."""
    total = sum(s["n_tokens"] for s in chosen)
    have = {(s["prompt_sha256"]) for s in chosen}
    rest = [s for s in candidates if s["prompt_sha256"] not in have]
    rng.shuffle(rest)
    rest.sort(key=lambda s: -s["n_tokens"])
    for s in rest:
        if total >= budget * (1 - tol):
            break
        if total + s["n_tokens"] <= budget * (1 + tol):
            chosen.append(s); total += s["n_tokens"]; have.add(s["prompt_sha256"])
    return chosen


def build(arm: str, split: dict, fp_run: str, q_run: str | None, seed: int) -> dict:
    cal = C.FROZEN["calibration"]
    budget = int(cal["token_budget"]); tol = float(cal["token_budget_tolerance"])
    domains = list(split["domains"].keys())
    cal_ids = {d: split["domains"][d]["calibration"] for d in domains}
    eval_ids = {d: set(split["domains"][d]["evaluation"]) for d in domains}
    rng = np.random.default_rng(seed)
    fp_states = load_states(fp_run, domains, cal_ids, "fp")
    notes = []
    if arm == "static":
        init = [s for s in fp_states if s["decision_idx"] == 0]
        # dedupe identical initial prompts (same task -> same prompt)
        seen = set(); uniq = []
        for s in init:
            if s["prompt_sha256"] not in seen:
                seen.add(s["prompt_sha256"]); uniq.append(s)
        chosen = []
        total = 0
        k = 0
        order = list(uniq); rng.shuffle(order)
        # cycle through initial states (with repetition) until budget reached
        while total < budget * (1 - tol):
            s = order[k % len(order)]
            if total + s["n_tokens"] > budget * (1 + tol):
                break
            chosen.append({**s, "repeat_index": k // len(order)}); total += s["n_tokens"]; k += 1
        notes.append(f"{len(uniq)} unique initial states; {len(chosen)} contexts with repetition (multiplicity up to {k // len(order) + 1})")
    elif arm == "fp_traj":
        chosen = sample_budget(fp_states, budget, rng, stratify=True, tol=tol)
        chosen = _top_up(chosen, fp_states, budget, tol, rng)
    elif arm in ("cloq", "q_only"):
        assert q_run, "--q-run required"
        q_states = load_states(q_run, domains, cal_ids, "q0")
        if arm == "cloq":
            half = budget // 2
            fp_part = sample_budget(fp_states, half, rng, stratify=True, tol=tol)
            fp_part = _top_up(fp_part, fp_states, half, tol, rng)
            q_part = sample_budget(q_states, budget - half, rng, stratify=True, tol=tol)
            q_part = _top_up(q_part, q_states, budget - half, tol, rng)
            chosen = fp_part + q_part
        else:
            chosen = sample_budget(q_states, budget, rng, stratify=True, tol=tol)
            chosen = _top_up(chosen, q_states, budget, tol, rng)
    else:
        raise ValueError(arm)

    total = sum(s["n_tokens"] for s in chosen)
    # leakage check: no evaluation task
    for s in chosen:
        assert s["task_id"] not in eval_ids[s["domain"]], f"leak: {s['domain']} {s['task_id']} is an evaluation task"
    lens = [s["n_tokens"] for s in chosen]
    manifest = {
        "arm": arm, "token_budget": budget, "tolerance": tol, "total_tokens": total,
        "within_tolerance": abs(total - budget) <= budget * tol,
        "n_contexts": len(chosen), "median_context_tokens": float(np.median(lens)) if lens else None,
        "mean_context_tokens": float(np.mean(lens)) if lens else None,
        "min_context_tokens": min(lens) if lens else None, "max_context_tokens": max(lens) if lens else None,
        "tokens_by_source": {src: sum(s["n_tokens"] for s in chosen if s["source"] == src) for src in {s["source"] for s in chosen}},
        "contexts_by_source": {src: sum(1 for s in chosen if s["source"] == src) for src in {s["source"] for s in chosen}},
        "tokens_by_depth_quartile": {q: sum(s["n_tokens"] for s in chosen if s["depth_quartile"] == q) for q in range(4)},
        "tokens_by_domain": {d: sum(s["n_tokens"] for s in chosen if s["domain"] == d) for d in domains},
        "fp_run": fp_run, "q_run": q_run, "seed": seed, "split_file_sha256": None,
        "notes": notes,
        "contexts": [
            {k: s[k] for k in ["source", "run_id", "domain", "task_id", "trajectory_id", "decision_idx", "n_decisions", "depth", "depth_quartile", "n_tokens", "prompt_sha256", "prompt_token_ids", "parser_error", "finish_reason"]}
            for s in chosen
        ],
    }
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["static", "fp_traj", "cloq", "q_only"])
    ap.add_argument("--split", default=str(C.MANIFEST_DIR / "task_split_v0.json"))
    ap.add_argument("--fp-run", default="bf16")
    ap.add_argument("--q-run", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=int(C.FROZEN["calibration"]["sampling_seed"]))
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f"{out} exists (frozen); refusing to overwrite")
    split = json.load(open(args.split))
    man = build(args.arm, split, args.fp_run, args.q_run, args.seed)
    man["split_file_sha256"] = hashlib.sha256(open(args.split, "rb").read()).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(man))
    summary = {k: v for k, v in man.items() if k != "contexts"}
    print(json.dumps(summary, indent=2))
    if not man["within_tolerance"]:
        raise SystemExit("token budget not within tolerance")


if __name__ == "__main__":
    main()
