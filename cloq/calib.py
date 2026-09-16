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
from cloq.metrics import load_decisions, read_jsonl


def load_states(run_id: str, domains: list[str], task_ids_by_domain: dict[str, list[str]], source: str) -> list[dict]:
    states = []
    for domain in domains:
        run_dir = C.RUNS_DIR / run_id / domain
        st = json.load(open(run_dir / "status.json"))
        assert st["status"] == "completed", f"{run_dir} not completed"
        allowed = set(task_ids_by_domain[domain])
        decs = [d for d in load_decisions(run_dir) if d["task_id"] in allowed]
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
                    "truncated": bool((d.get("context") or {}).get("truncated", False)),
                })
    return states


def _initial_pick(pool: list[dict], target: int, rng: np.random.Generator) -> list[dict]:
    """Uniform random draw without replacement until the running total first reaches target."""
    order = list(pool)
    rng.shuffle(order)
    chosen, total = [], 0
    for s in order:
        if total >= target:
            break
        chosen.append(s)
        total += s["n_tokens"]
    return chosen


def _refine_stratum(cur: list[dict], pool: list[dict], used: set, target: float, rng, max_iter: int = 4000) -> int:
    """Hill-climb same-stratum swaps/add/remove so this stratum's token sum approaches `target`."""
    total = sum(x["n_tokens"] for x in cur)
    for _ in range(max_iter):
        need = target - total
        if abs(need) < 1:
            break
        avail = [x for x in pool if x["prompt_sha256"] not in used]
        moved = False
        if avail and cur:
            i = int(rng.integers(len(cur))); j = int(rng.integers(len(avail)))
            delta = avail[j]["n_tokens"] - cur[i]["n_tokens"]
            if abs(need - delta) < abs(need):
                used.discard(cur[i]["prompt_sha256"]); used.add(avail[j]["prompt_sha256"])
                cur[i] = avail[j]; total += delta; moved = True
        if not moved:
            if need > 0 and avail:
                j = int(rng.integers(len(avail))); x = avail[j]
                if abs(need - x["n_tokens"]) < abs(need):
                    cur.append(x); used.add(x["prompt_sha256"]); total += x["n_tokens"]; moved = True
            elif need < 0 and len(cur) > 1:
                i = int(rng.integers(len(cur))); x = cur[i]
                if abs(need + x["n_tokens"]) < abs(need):
                    cur.pop(i); used.discard(x["prompt_sha256"]); total -= x["n_tokens"]; moved = True
        if not moved:
            break
    return total


def select_to_budget(
    pools: dict[int, list[dict]],
    target: int,
    tol: float,
    rng: np.random.Generator,
    max_iter: int = 50000,
) -> tuple[list[dict], dict]:
    """Choose contexts whose total token count lands inside [target*(1-tol), target*(1+tol)],
    giving every stratum an equal share of the budget.

    `pools` maps a stratum key (depth quartile, or 0 for an unstratified arm) to its candidates.
    Stage 1 draws uniformly at random inside each stratum up to its share of the budget.
    Stage 2 refines each stratum independently towards that share.
    Stage 3 trades context lengths (swaps only, so the per-stratum context counts and therefore
    the depth composition are preserved) until the *total* is inside the window.

    A greedy fill cannot hit the window here: contexts are ~5-8k tokens, so the budget is only
    8-13 contexts wide and one extra context overshoots the entire window.
    """
    lo, hi = target * (1 - tol), target * (1 + tol)
    keys = sorted(pools)
    share = target / len(keys)
    chosen = {k: _initial_pick(pools[k], share, rng) for k in keys}
    used = {k: {x["prompt_sha256"] for x in chosen[k]} for k in keys}
    for k in keys:
        _refine_stratum(chosen[k], pools[k], used[k], share, rng)
    total = sum(x["n_tokens"] for k in keys for x in chosen[k])
    n_swaps = 0
    for _ in range(max_iter):
        if lo <= total <= hi:
            break
        need = target - total
        k = keys[int(rng.integers(len(keys)))]
        cur = chosen[k]
        avail = [x for x in pools[k] if x["prompt_sha256"] not in used[k]]
        if not (avail and cur):
            continue
        i = int(rng.integers(len(cur))); j = int(rng.integers(len(avail)))
        delta = avail[j]["n_tokens"] - cur[i]["n_tokens"]
        if abs(need - delta) < abs(need):
            used[k].discard(cur[i]["prompt_sha256"]); used[k].add(avail[j]["prompt_sha256"])
            cur[i] = avail[j]; total += delta; n_swaps += 1
    out = [x for k in keys for x in chosen[k]]
    info = {
        "global_swaps": n_swaps,
        "reached_window": bool(lo <= total <= hi),
        "total_tokens": total,
        "tokens_per_stratum": {str(k): sum(x["n_tokens"] for x in chosen[k]) for k in keys},
        "contexts_per_stratum": {str(k): len(chosen[k]) for k in keys},
        "target_share_per_stratum": round(share, 1),
    }
    return out, info


def _by_quartile(states: list[dict]) -> dict[int, list[dict]]:
    pools = {q: [s for s in states if s["depth_quartile"] == q] for q in range(4)}
    return {q: v for q, v in pools.items() if v}


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
        init = [x for x in fp_states if x["decision_idx"] == 0]
        seen, uniq = set(), []
        for x in init:
            if x["prompt_sha256"] not in seen:
                seen.add(x["prompt_sha256"])
                uniq.append(x)
        chosen, info = select_to_budget({0: uniq}, budget, tol, rng)
        notes.append(f"{len(uniq)} unique initial states available; {len(chosen)} used; {info}")
    elif arm == "fp_traj":
        chosen, info = select_to_budget(_by_quartile(fp_states), budget, tol, rng)
        notes.append(f"fp_traj: {info}")
    elif arm in ("cloq", "q_only"):
        assert q_run, "--q-run required"
        q_states = load_states(q_run, domains, cal_ids, "q0")
        if arm == "cloq":
            half = budget // 2
            fp_part, i1 = select_to_budget(_by_quartile(fp_states), half, tol, rng)
            q_part, i2 = select_to_budget(_by_quartile(q_states), budget - half, tol, rng)
            chosen = fp_part + q_part
            notes.append(f"cloq fp half: {i1}; q0 half: {i2}")
        else:
            chosen, info = select_to_budget(_by_quartile(q_states), budget, tol, rng)
            notes.append(f"q_only: {info}")
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
