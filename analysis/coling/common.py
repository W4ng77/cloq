"""Shared helpers for the COLING independent re-audit.

CPU-only, read-only against runs/. Reuses cloq.metrics.load_decisions and the project's
own resolved_db_match() convention (premature termination = failure) rather than
re-deriving it, per project instructions. Everything else here (task horizon lookup,
permutation tests, NLL pooling) is independent re-computation from raw run files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cloq.metrics import load_decisions, read_jsonl, resolved_db_match  # noqa: E402

RUNS = ROOT / "runs"
MANIFESTS = ROOT / "manifests"
OUT = Path(__file__).resolve().parent / "out"
FIGS = Path(__file__).resolve().parent / "figs"

DOMAINS = ("retail", "airline")

# The 6 calibration arms x 3 draws that make up the 18 W4 GPTQ checkpoints in the v1 dev sweep.
ARMS = ["static", "fp_traj", "cloq_all", "cloq_novel", "cloq_matched_random", "cloq_matched_alt"]
DRAWS = ["c1", "c2", "c3"]


def dev_run_dir(arm: str, draw: str, domain: str) -> Path:
    return RUNS / f"{arm}_{draw}_dev" / domain


def task_db_match(run_dir: Path) -> dict[str, bool]:
    """task_id -> resolved db_match (premature termination counted as failure), from raw
    trajectory.jsonl, independent of any cached metrics.json field."""
    trajs = read_jsonl(run_dir / "trajectory.jsonl")
    out = {}
    for t in trajs:
        v = resolved_db_match(t)
        # resolved_db_match returns None only when termination is normal but db_check missing;
        # per project convention this should not happen for normal terminations, but guard it.
        out[t["task_id"]] = bool(v) if v is not None else False
    return out


def load_horizon() -> dict[str, dict[str, int]]:
    """BF16 horizon (agent decision count) per domain per task_id, from the frozen v0 split
    file (manifests/task_split_v0.json), which is what STRATEGY_v2's '85 dev tasks, 37 with
    BF16 horizon > 11' refers to (verified: 25 retail + 12 airline = 37 of 58+27=85)."""
    d = json.loads((MANIFESTS / "task_split_v0.json").read_text())
    return {dom: {tid: int(h) for tid, h in d["domains"][dom]["horizon_by_task"].items()} for dom in DOMAINS}


def dev_task_ids() -> dict[str, list[str]]:
    d = json.loads((MANIFESTS / "task_split_v0.json").read_text())
    return {dom: list(d["domains"][dom]["evaluation"]) for dom in DOMAINS}


def checkpoint_task_vector(arm: str, draw: str, horizon: dict, long_cutoff: int = 11) -> dict:
    """Return per-task db_match (pooled over both domains) plus a long-task mask, for one
    checkpoint (arm x draw)."""
    tasks = {}
    long_mask = {}
    for dom in DOMAINS:
        rd = dev_run_dir(arm, draw, dom)
        dbm = task_db_match(rd)
        for tid, v in dbm.items():
            key = f"{dom}:{tid}"
            tasks[key] = v
            long_mask[key] = horizon[dom].get(tid, 0) > long_cutoff
    return tasks, long_mask


def bf16_task_vector(run_name: str, horizon: dict, task_ids: dict, long_cutoff: int = 11) -> tuple[dict, dict]:
    tasks = {}
    long_mask = {}
    for dom in DOMAINS:
        rd = RUNS / run_name / dom
        dbm = task_db_match(rd)
        for tid in task_ids[dom]:
            key = f"{dom}:{tid}"
            tasks[key] = dbm.get(tid, False)
            long_mask[key] = horizon[dom].get(tid, 0) > long_cutoff
    return tasks, long_mask


def pooled_rate(tasks: dict, keys=None) -> float:
    if keys is None:
        keys = list(tasks.keys())
    if not keys:
        return float("nan")
    return float(np.mean([1.0 if tasks[k] else 0.0 for k in keys]))


def openloop_pool(run_dir: Path) -> tuple[float, float, int]:
    """Recompute NLL/token directly from openloop.jsonl as sum(nll) / sum(action tokens)
    (token-weighted). Returns (total_nll, total_tokens, n_states). See also
    openloop_state_ratios() for the mean-of-per-state-ratio convention used by the cached
    openloop.summary.json field ("nll_per_token_mean"), which is what STRATEGY_v2's NLL
    numbers appear to use."""
    p = run_dir / "openloop.jsonl"
    if not p.exists():
        return (float("nan"), float("nan"), 0)
    recs = read_jsonl(p)
    total_nll = sum(r["nll"] for r in recs if r.get("nll") is not None)
    total_tok = sum(r["n_action_tokens"] for r in recs if r.get("nll") is not None)
    return (float(total_nll), float(total_tok), len(recs))


def openloop_state_ratios(run_dir: Path) -> list[float]:
    """Per-state nll_per_token values from openloop.jsonl (unweighted list), matching the
    convention behind the cached openloop.summary.json 'nll_per_token_mean' field."""
    p = run_dir / "openloop.jsonl"
    if not p.exists():
        return []
    recs = read_jsonl(p)
    return [r["nll_per_token"] for r in recs if r.get("nll_per_token") is not None]


def save_json(name: str, obj) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(obj, indent=2, default=str))
    return p
