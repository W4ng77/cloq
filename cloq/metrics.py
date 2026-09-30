"""Closed-loop metrics, tool-call normalisation, and paired bootstrap."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np


# ----------------------------------------------------------------------------
# Tool-call normalisation (plan sections 15/16)
# ----------------------------------------------------------------------------


def _canon_value(v: Any) -> Any:
    if isinstance(v, str):
        return " ".join(v.strip().split())
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        if math.isfinite(v) and float(v).is_integer():
            return int(v)
        return round(v, 6)
    if isinstance(v, int):
        return v
    if isinstance(v, dict):
        return {str(k): _canon_value(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
    if isinstance(v, (list, tuple)):
        return [_canon_value(x) for x in v]
    return v


def normalize_tool_call(name: str, arguments: dict | None) -> str:
    return json.dumps({"name": name, "arguments": _canon_value(arguments or {})}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def normalize_action(content: str | None, tool_calls: list[dict] | None) -> str:
    """Normalised action string for a decision: tool calls if any, else a text marker."""
    if tool_calls:
        return "TOOL|" + "|".join(normalize_tool_call(tc["name"], tc.get("arguments")) for tc in tool_calls)
    return "TEXT|" + " ".join((content or "").strip().split())


def action_kind(content: str | None, tool_calls: list[dict] | None) -> str:
    return "tool" if tool_calls else "text"


# ----------------------------------------------------------------------------
# Per-run summaries
# ----------------------------------------------------------------------------


def read_jsonl(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_decisions(run_dir: Path, final_only: bool = True) -> list[dict]:
    """Decision records of a run. tau2 retries a task after an exception, and every
    attempt logs its own trajectory_id; with final_only we keep, per task, only the
    records of the last trajectory_id seen (the attempt that produced the SimulationRun)."""
    recs = read_jsonl(Path(run_dir) / "decisions.jsonl")
    if not final_only:
        return recs
    last: dict[str, str] = {}
    attempts: dict[str, set] = {}
    for d in recs:
        last[d["task_id"]] = d["trajectory_id"]
        attempts.setdefault(d["task_id"], set()).add(d["trajectory_id"])
    out = [d for d in recs if d["trajectory_id"] == last[d["task_id"]]]
    for d in out:
        d["n_attempts"] = len(attempts[d["task_id"]])
    return sorted(out, key=lambda d: (d["task_id"], d["decision_idx"]))


NORMAL_TERMINATIONS = ("user_stop", "agent_stop")


def resolved_db_match(traj: dict) -> bool | None:
    """DB end-state match with premature termination scored as a failure.

    tau2 short-circuits `evaluate_simulation` when a run did not end through normal
    conversation termination: it returns reward 0.0 and leaves `db_check` empty. Treating
    that empty check as a missing value would silently drop exactly those held-out tasks on
    which a quantized agent loops or errors out, inflating its score, so a premature run is
    recorded as db_match=False (which is what tau2's own reward of 0.0 means).
    """
    db = traj.get("db_match")
    if db is not None:
        return bool(db)
    if traj.get("termination_reason") not in NORMAL_TERMINATIONS:
        return False
    return None


# Endpoint names (docs/insights/METHODOLOGY_REVISION.md §C, 2026-09-30). What `task_success` returns per domain:
#   retail   "DB success" = DB end-state match and normal termination. NOT tau2's official retail reward, whose basis is
#            DB x NL_ASSERTION (112 of 114 tasks): the NL assertions need an LLM judge (cloq.nl_judge, not used by any
#            a6k2 analysis). official_reward in trajectory.jsonl is the product over the basis without NL (run_arm.py).
#   airline  "DB success". tau2's official airline reward is DB x COMMUNICATE (all 50 tasks); COMMUNICATE is reported
#            separately (communicate_all / official_reward), not folded into this endpoint.
#   telecom  "official task-basis success" = official_reward == 1, the product over the task's own reward_basis
#            (ENV_ASSERTION for 2253 of 2285 tasks, ENV_ASSERTION x ACTION for 32), deterministic, with premature
#            termination scored 0: this IS tau2's official telecom success.
ENDPOINT_NAME = {"retail": "DB success (not tau2 official: basis DB x NL_ASSERTION)",
                 "airline": "DB success (not tau2 official: basis DB x COMMUNICATE)",
                 "telecom": "official deterministic task-basis success (tau2 official)"}


def db_success(traj: dict) -> bool | None:
    """DB success: DB end-state match, premature termination scored as failure (= resolved_db_match)."""
    return resolved_db_match(traj)


def official_basis_success(traj: dict) -> bool | None:
    """tau2's deterministic task-basis success: official_reward == 1 (product over the task's reward_basis, NL
    assertions excluded; see run_arm.basis_reward). For retail tasks with NL_ASSERTION in the basis this is NOT the
    full official reward."""
    r = traj.get("official_reward")
    return None if r is None else bool(r == 1.0)


def task_success(traj: dict) -> bool | None:
    """Primary per-task endpoint (name per domain in ENDPOINT_NAME). retail/airline: DB success (DB end-state match,
    frozen v0 primary endpoint; not tau2's official reward). telecom (reward_basis without DB; dual control): tau2's
    official deterministic basis reward, i.e. all env assertions on the user device / agent DB [and the gold actions
    where ACTION is in the basis]. Behaviour unchanged; only the names above were added (2026-09-30)."""
    basis = traj.get("reward_basis_task")
    if basis is None:
        basis = (((traj.get("task") or {}).get("evaluation_criteria") or {}).get("reward_basis")) or ["DB"]
    if "DB" in basis or traj.get("official_reward") is None:
        return resolved_db_match(traj)
    return bool(traj["official_reward"] == 1.0)


def per_task_stats(traj: dict, decisions: list[dict]) -> dict:
    msgs = traj["messages"]
    agent_msgs = [m for m in msgs if m.get("role") == "assistant"]
    tool_msgs = [m for m in msgs if m.get("role") == "tool" and m.get("requestor", "assistant") == "assistant"]
    tool_calls = [tc for m in agent_msgs for tc in (m.get("tool_calls") or []) if tc.get("requestor", "assistant") == "assistant"]
    tool_errors = sum(1 for m in tool_msgs if m.get("error"))
    n_dec = len(decisions)
    parser_errors = sum(1 for d in decisions if d.get("parser_error"))
    finish_length = sum(1 for d in decisions if d.get("finish_reason") == "length")
    truncated = sum(1 for d in decisions if (d.get("context") or {}).get("truncated"))
    norm_calls = [normalize_tool_call(tc["name"], tc.get("arguments")) for tc in tool_calls]
    repeated = len(norm_calls) - len(set(norm_calls))
    # consecutive identical tool calls (looping)
    loops = sum(1 for a, b in zip(norm_calls, norm_calls[1:]) if a == b)
    prompt_lens = [d.get("n_prompt_tokens") for d in decisions if d.get("n_prompt_tokens") is not None]
    return {
        "task_id": traj["task_id"],
        "reward": traj.get("reward"),
        "db_match": resolved_db_match(traj),
        "db_match_raw": traj.get("db_match"),
        "success": task_success(traj),
        "official_reward": traj.get("official_reward"),
        "env_assert_all": traj.get("env_assert_all"),
        "n_user_tool_calls": traj.get("n_user_tool_calls"),
        "n_user_tool_errors": traj.get("n_user_tool_errors"),
        "communicate_all": traj.get("communicate_all"),
        "action_all": traj.get("action_all"),
        "termination_reason": traj.get("termination_reason"),
        "n_agent_messages": len(agent_msgs),
        "n_decisions": n_dec,
        "n_tool_calls": len(tool_calls),
        "n_tool_errors": tool_errors,
        "n_parser_errors": parser_errors,
        "n_finish_length": finish_length,
        "n_truncated_contexts": truncated,
        "n_repeated_tool_calls": repeated,
        "n_consecutive_repeats": loops,
        "max_prompt_tokens": max(prompt_lens) if prompt_lens else None,
        "mean_prompt_tokens": float(np.mean(prompt_lens)) if prompt_lens else None,
        "n_attempts": (decisions[0].get("n_attempts") if decisions else None),
        "premature": traj.get("termination_reason") not in NORMAL_TERMINATIONS,
    }


def summarize_run(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    trajs = read_jsonl(run_dir / "trajectory.jsonl")
    decs = load_decisions(run_dir) if (run_dir / "decisions.jsonl").exists() else []
    by_task: dict[str, list[dict]] = {}
    for d in decs:
        by_task.setdefault(d["task_id"], []).append(d)
    rows = [per_task_stats(t, sorted(by_task.get(t["task_id"], []), key=lambda d: d["decision_idx"])) for t in trajs]
    n = len(rows)

    def mean(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return float(np.mean(vals)) if vals else None

    n_dec_total = sum(r["n_decisions"] for r in rows)
    n_tool_total = sum(r["n_tool_calls"] for r in rows)
    n_err_total = sum(r["n_tool_errors"] for r in rows)
    n_parse_total = sum(r["n_parser_errors"] for r in rows)
    ids_from_server = sum(1 for d in decs if d.get("prompt_ids_from_server"))
    ids_match = sum(1 for d in decs if d.get("prompt_ids_match_local"))
    return {
        "n_tasks": n,
        "reward_mean": mean("reward"),
        "db_match_rate": mean("db_match"),
        "success_rate": mean("success"),
        "official_reward_mean": mean("official_reward"),
        "env_assert_rate": mean("env_assert_all"),
        "mean_user_tool_calls": mean("n_user_tool_calls"),
        "user_tool_error_rate": ((sum(r["n_user_tool_errors"] or 0 for r in rows) / sum(r["n_user_tool_calls"] or 0 for r in rows))
                                 if sum(r["n_user_tool_calls"] or 0 for r in rows) else None),
        "communicate_rate": mean("communicate_all"),
        "action_rate": mean("action_all"),
        "n_decisions_total": n_dec_total,
        "mean_decisions": mean("n_decisions"),
        "mean_tool_calls": mean("n_tool_calls"),
        "tool_error_rate": (n_err_total / n_tool_total) if n_tool_total else None,
        "parser_error_rate": (n_parse_total / n_dec_total) if n_dec_total else None,
        "finish_length_rate": (sum(r["n_finish_length"] for r in rows) / n_dec_total) if n_dec_total else None,
        "truncated_context_rate": (sum(r["n_truncated_contexts"] for r in rows) / n_dec_total) if n_dec_total else None,
        "premature_rate": mean("premature"),
        "repeated_tool_call_rate": (sum(r["n_repeated_tool_calls"] for r in rows) / n_tool_total) if n_tool_total else None,
        "termination_reasons": dict(Counter(r["termination_reason"] for r in rows)),
        "prompt_ids_from_server_frac": (ids_from_server / len(decs)) if decs else None,
        "prompt_ids_match_local_frac": (ids_match / len(decs)) if decs else None,
        "per_task": rows,
    }


# ----------------------------------------------------------------------------
# Paired task-level bootstrap (plan section 13)
# ----------------------------------------------------------------------------


def paired_bootstrap(a: dict[str, float], b: dict[str, float], n_boot: int = 10000, seed: int = 0, ci: float = 0.95) -> dict:
    """Bootstrap CI for mean(a) - mean(b) over shared task ids."""
    ids = sorted(set(a) & set(b))
    if not ids:
        return {"n": 0}
    x = np.array([a[i] for i in ids], dtype=float)
    y = np.array([b[i] for i in ids], dtype=float)
    d = x - y
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ids), size=(n_boot, len(ids)))
    boots = d[idx].mean(axis=1)
    lo, hi = np.quantile(boots, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    return {
        "n": len(ids), "mean_a": float(x.mean()), "mean_b": float(y.mean()), "diff": float(d.mean()),
        "ci_lo": float(lo), "ci_hi": float(hi), "p_diff_le_0": float((boots <= 0).mean()), "p_diff_ge_0": float((boots >= 0).mean()),
        "n_boot": n_boot,
    }


def bootstrap_gap_difference(
    bf16: dict[str, float], arm: dict[str, float], horizon: dict[str, float],
    n_boot: int = 10000, seed: int = 0, ci: float = 0.95,
) -> dict:
    """Direct test of horizon amplification (plan section 14).

    Splits the held-out tasks at the median BF16 horizon and bootstraps
        (BF16 - arm) on long tasks  -  (BF16 - arm) on short tasks,
    resampling task ids within each half. A positive interval excluding zero means the
    quantization gap grows with task horizon.
    """
    ids = sorted(set(bf16) & set(arm) & set(horizon))
    if len(ids) < 8:
        return {"n": len(ids)}
    h = np.array([horizon[i] for i in ids], dtype=float)
    d = np.array([bf16[i] - arm[i] for i in ids], dtype=float)
    med = float(np.median(h))
    long_i = np.where(h > med)[0]
    short_i = np.where(h <= med)[0]
    if len(long_i) < 3 or len(short_i) < 3:
        return {"n": len(ids), "note": "degenerate horizon split"}
    rng = np.random.default_rng(seed)
    bl = d[long_i][rng.integers(0, len(long_i), size=(n_boot, len(long_i)))].mean(axis=1)
    bs = d[short_i][rng.integers(0, len(short_i), size=(n_boot, len(short_i)))].mean(axis=1)
    diff = bl - bs
    lo, hi = np.quantile(diff, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    return {
        "n": len(ids), "median_horizon": med,
        "n_short": int(len(short_i)), "n_long": int(len(long_i)),
        "gap_short": float(d[short_i].mean()), "gap_long": float(d[long_i].mean()),
        "gap_long_minus_short": float(d[long_i].mean() - d[short_i].mean()),
        "ci_lo": float(lo), "ci_hi": float(hi),
        "p_amplification_le_0": float((diff <= 0).mean()),
        "n_boot": n_boot,
    }


def spearman(x: Iterable[float], y: Iterable[float]) -> float | None:
    from scipy.stats import spearmanr

    x = list(x); y = list(y)
    if len(x) < 3:
        return None
    r = spearmanr(x, y).correlation
    return None if (r is None or (isinstance(r, float) and math.isnan(r))) else float(r)
