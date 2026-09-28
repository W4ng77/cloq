"""Per-checkpoint pooled/long db_match success for the 18 GPTQ dev checkpoints + RTN + BF16,
plus an arm-label permutation test (conditional on tasks) and a draw-seed permutation test.

Independent re-computation: reads runs/*/trajectory.jsonl directly via common.task_db_match,
which calls cloq.metrics.resolved_db_match (premature termination = failure), and reads task
horizon from the frozen manifests/task_split_v0.json.

Usage: CUDA_VISIBLE_DEVICES="" ~/miniconda3/envs/cloq/bin/python 01_checkpoint_success.py
"""
from __future__ import annotations

import numpy as np

from common import ARMS, DRAWS, checkpoint_task_vector, bf16_task_vector, dev_task_ids, load_horizon, pooled_rate, save_json, RUNS

LONG_CUTOFF = 11
N_PERM = 20000
SEED = 0


def group_f_stat(values: np.ndarray, group_ids: np.ndarray) -> float:
    """Between-group / within-group variance ratio (one-way ANOVA F, up to constants that
    cancel in a permutation test)."""
    groups = np.unique(group_ids)
    grand = values.mean()
    ss_between = sum(len(values[group_ids == g]) * (values[group_ids == g].mean() - grand) ** 2 for g in groups)
    ss_within = sum(((values[group_ids == g] - values[group_ids == g].mean()) ** 2).sum() for g in groups)
    df_between = len(groups) - 1
    df_within = len(values) - len(groups)
    if ss_within <= 0 or df_within <= 0:
        return float("inf")
    return (ss_between / df_between) / (ss_within / df_within)


def permutation_test(values: np.ndarray, group_ids: np.ndarray, n_perm: int, seed: int) -> dict:
    obs = group_f_stat(values, group_ids)
    rng = np.random.default_rng(seed)
    n = len(values)
    perm_stats = np.empty(n_perm)
    for i in range(n_perm):
        perm = rng.permutation(group_ids)
        perm_stats[i] = group_f_stat(values, perm)
    p = float((perm_stats >= obs).mean())
    return {"observed_F": float(obs), "p": p, "n_perm": n_perm}


def main():
    horizon = load_horizon()
    task_ids = dev_task_ids()

    checkpoints = {}
    for arm in ARMS:
        for draw in DRAWS:
            tasks, long_mask = checkpoint_task_vector(arm, draw, horizon, LONG_CUTOFF)
            pooled = pooled_rate(tasks)
            long_keys = [k for k, v in long_mask.items() if v]
            long = pooled_rate(tasks, long_keys)
            checkpoints[f"{arm}_{draw}"] = {
                "arm": arm, "draw": draw, "n_pooled": len(tasks), "n_long": len(long_keys),
                "pooled_db_match": pooled, "long_db_match": long,
                "tasks": tasks,  # per-task bool, keyed dom:task_id
            }

    # RTN (single deterministic implementation, no draw)
    rtn_tasks, rtn_long_mask = bf16_task_vector("rtn_eval", horizon, task_ids, LONG_CUTOFF)
    rtn_long_keys = [k for k, v in rtn_long_mask.items() if v]
    rtn = {"pooled_db_match": pooled_rate(rtn_tasks), "long_db_match": pooled_rate(rtn_tasks, rtn_long_keys),
           "n_pooled": len(rtn_tasks), "n_long": len(rtn_long_keys)}

    # BF16 references
    bf16_v1_tasks, bf16_v1_long_mask = bf16_task_vector("bf16_v1", horizon, task_ids, LONG_CUTOFF)
    bf16_v1_long_keys = [k for k, v in bf16_v1_long_mask.items() if v]
    bf16_v1 = {"pooled_db_match": pooled_rate(bf16_v1_tasks), "long_db_match": pooled_rate(bf16_v1_tasks, bf16_v1_long_keys),
               "n_pooled": len(bf16_v1_tasks), "n_long": len(bf16_v1_long_keys)}

    # ---- Arm-label permutation test, conditional on tasks ----
    # Statistic: one-way ANOVA F on the 18 checkpoint-level pooled (resp. long) db_match rates,
    # grouped by arm (6 groups of 3 draws). Null: arm label carries no information, i.e. the
    # 18 checkpoint success rates are exchangeable across arm labels. This directly tests
    # STRATEGY_v2 A2's "18 W4 checkpoints are near-exchangeable given task difficulty" claim.
    order = [f"{a}_{d}" for a in ARMS for d in DRAWS]
    pooled_vals = np.array([checkpoints[k]["pooled_db_match"] for k in order])
    long_vals = np.array([checkpoints[k]["long_db_match"] for k in order])
    arm_ids = np.array([checkpoints[k]["arm"] for k in order])
    draw_ids = np.array([checkpoints[k]["draw"] for k in order])

    arm_perm_pooled = permutation_test(pooled_vals, arm_ids, N_PERM, SEED)
    arm_perm_long = permutation_test(long_vals, arm_ids, N_PERM, SEED + 1)

    # ---- Draw-seed permutation test ----
    # Statistic: same F-stat, but grouping factor is the calibration draw (c1/c2/c3) instead
    # of arm. Tests whether checkpoints sharing a draw seed are more similar than chance
    # (i.e. whether draw-level randomness, shared across arms for a given ci, systematically
    # shifts success), independent of arm identity.
    draw_perm_pooled = permutation_test(pooled_vals, draw_ids, N_PERM, SEED + 2)
    draw_perm_long = permutation_test(long_vals, draw_ids, N_PERM, SEED + 3)

    result = {
        "long_cutoff": LONG_CUTOFF,
        "checkpoints": {k: {kk: vv for kk, vv in v.items() if kk != "tasks"} for k, v in checkpoints.items()},
        "rtn_eval": rtn,
        "bf16_v1": bf16_v1,
        "arm_permutation_test": {"pooled": arm_perm_pooled, "long": arm_perm_long},
        "draw_seed_permutation_test": {"pooled": draw_perm_pooled, "long": draw_perm_long},
        "gptq_min_pooled": float(pooled_vals.min()),
        "gptq_min_long": float(long_vals.min()),
        "gptq_max_pooled": float(pooled_vals.max()),
        "gptq_max_long": float(long_vals.max()),
        "gptq_mean_pooled": float(pooled_vals.mean()),
        "gptq_mean_long": float(long_vals.mean()),
    }
    save_json("01_checkpoint_success.json", result)
    print("Saved out/01_checkpoint_success.json")
    print(f"BF16 v1: pooled={bf16_v1['pooled_db_match']:.3f} long={bf16_v1['long_db_match']:.3f}")
    print(f"RTN:     pooled={rtn['pooled_db_match']:.3f} long={rtn['long_db_match']:.3f} "
          f"(gptq min pooled={result['gptq_min_pooled']:.3f}, min long={result['gptq_min_long']:.3f})")
    print(f"Arm permutation (conditional on tasks): pooled F={arm_perm_pooled['observed_F']:.3f} p={arm_perm_pooled['p']:.3f}; "
          f"long F={arm_perm_long['observed_F']:.3f} p={arm_perm_long['p']:.3f}")
    print(f"Draw-seed permutation: pooled F={draw_perm_pooled['observed_F']:.3f} p={draw_perm_pooled['p']:.3f}; "
          f"long F={draw_perm_long['observed_F']:.3f} p={draw_perm_long['p']:.3f}")


if __name__ == "__main__":
    main()
