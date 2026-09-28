"""v0 FP-Traj vs Static retail gap under an exchangeable null (STRATEGY_v2 A6).

v0 runs: runs/static_eval (retail, 58 tasks) vs runs/fp_traj_eval (retail, 58 tasks), same
task_id set. Independent recomputation of db_match via cloq.metrics.resolved_db_match
(premature = failure), read directly from trajectory.jsonl.

Exchangeable null: under H0 arm label carries no information, so for each task the pair of
outcomes (static, fp_traj) is exchangeable -- i.e. each task's pair is independently swapped
with probability 0.5. Observed statistic: mean(fp_traj) - mean(static). One-sided p = P(permuted
diff >= observed diff) since the pre-registered claim was FP-Traj > Static.

Also reports the same statistic recomputed from the v1 c1 dev checkpoints (static_c1_dev vs
fp_traj_c1_dev, retail) as the "replication" data point referenced in A6 (v1 pooled replication
uses all 3 draws x both domains, computed already in 01_checkpoint_success.py; this script adds
the retail-only, single-draw comparison that is the closest structural analogue of the v0 test).
"""
from __future__ import annotations

import numpy as np

from common import RUNS, task_db_match, save_json

N_PERM = 100000
SEED = 0


def exchangeable_permutation(s: np.ndarray, f: np.ndarray, n_perm: int, seed: int) -> dict:
    obs = float(f.mean() - s.mean())
    rng = np.random.default_rng(seed)
    n = len(s)
    stacked = np.stack([s, f], axis=1).astype(float)  # (n, 2): col0=static, col1=fp_traj
    swap = rng.random((n_perm, n)) < 0.5
    # for each perm, if swap[i,t] True -> (f,s) else (s,t)
    perm_static = np.where(swap, stacked[:, 1], stacked[:, 0])
    perm_fp = np.where(swap, stacked[:, 0], stacked[:, 1])
    diffs = perm_fp.mean(axis=1) - perm_static.mean(axis=1)
    p_one_sided = float((diffs >= obs).mean()) if obs >= 0 else float((diffs <= obs).mean())
    p_two_sided = float((np.abs(diffs) >= abs(obs)).mean())
    return {"n_tasks": n, "mean_static": float(s.mean()), "mean_fp_traj": float(f.mean()),
            "observed_diff": obs, "p_one_sided": p_one_sided, "p_two_sided": p_two_sided, "n_perm": n_perm}


def main():
    static_ids = task_db_match(RUNS / "static_eval" / "retail")
    fp_ids = task_db_match(RUNS / "fp_traj_eval" / "retail")
    common = sorted(set(static_ids) & set(fp_ids))
    s = np.array([1.0 if static_ids[t] else 0.0 for t in common])
    f = np.array([1.0 if fp_ids[t] else 0.0 for t in common])
    v0 = exchangeable_permutation(s, f, N_PERM, SEED)

    # v1 c1 retail single-draw analogue
    s1 = task_db_match(RUNS / "static_c1_dev" / "retail")
    f1 = task_db_match(RUNS / "fp_traj_c1_dev" / "retail")
    common1 = sorted(set(s1) & set(f1))
    s1v = np.array([1.0 if s1[t] else 0.0 for t in common1])
    f1v = np.array([1.0 if f1[t] else 0.0 for t in common1])
    v1_c1 = exchangeable_permutation(s1v, f1v, N_PERM, SEED + 1)

    result = {"v0_static_eval_vs_fp_traj_eval_retail": v0, "v1_c1_dev_retail_replication": v1_c1}
    save_json("02_v0_gap.json", result)
    print("v0 retail FP-Traj - Static:", v0)
    print("v1 c1 dev retail FP-Traj - Static:", v1_c1)


if __name__ == "__main__":
    main()
