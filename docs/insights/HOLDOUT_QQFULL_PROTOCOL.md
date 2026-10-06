# Holdout full QQ no-op replay (W100av), frozen 2026-10-05 before any QQ-full task runs

**TL;DR.** The telecom holdout ran the QQ no-op (re-execute Q's own continuation from the restored state) on a fixed 10%
hash sample: 135 of 1202 analysed divergent states, all 135 pass (analysis/fork/out/holdout_noop_audit_20261004T152207Z.md).
That bounds, but does not exclude, a replay defect on the 1067 unsampled states, and every holdout contrast shares the
original Y_QQ as its baseline. This protocol re-runs QQ on **every** state and applies the prereg's own no-op rule
(PREREG_FORK_CONFIRM.md §5 items 2-3) at full coverage.

## 1. State list (fixed)
- All `states/*.json` in the 18 dirs analysed by holdout_confirm_20261002T012353Z (`provenance.input_dirs`):
  {q4_gptq_w4_d1, q8_gptq_w4_d1, q8_awq_w4} x g01-g06. Expected: 1202 states that load_dir analyses as divergent,
  plus any state of an excluded unit (none in the 2026-10-04 audit).
- The audit records the count and the sha256 of the sorted state_id list; the list itself is not printed.

## 2. Execution
- `scripts/a6000/make_tasks_holdout_qqfull.py --write`: 18 fork tasks, mode `branches`, branches [], noop_frac 1.0,
  B/Q checkpoint spec, GPU count, gpu_util and concurrency copied from the done `fork_hold_*` task.
- Output `analysis/fork/holdout_qqfull/<cell>/gNN/`. Nothing under `analysis/fork/holdout/` is written.
- The 135 already-sampled states are re-run too (a repeat check; their original QQ files are untouched).

## 3. Preconditions (per task; a failure makes the task invalid, not a mismatch)
- Q server `ckpt_sha256` and `effective_config_sha` equal the original `fork_hold_*` task's (per cell:
  q4_gptq_w4_d1 e6c24bc2.../29ba0176bfc6a4e0, q8_awq_w4 9ce71e4a.../b8608c0732512633, q8_gptq_w4_d1 6ee628e6.../cd7c70f5e9fe40d4).
- Numerics canary passes (worker's own check).

## 4. Match criterion (per state; identical to holdout_noop_audit.py)
`analyze_dev.noop_ok` (trajectory, decision counts, termination, official_reward, db_match vs the original episode) AND
`fork_driver.noop_check` (env_hash_init, env_hash_replay_vs_live, history_prefix, final env hash vs a strict tau2 replay of
the original episode) AND `fork_driver.budget_check`. A state matches iff all are true.

## 5. Mismatch handling
1. Locate the cause per mismatching state from status fields only (error text, failing check names, server log):
   infrastructure (server/simulator error, timeout) vs a reproducible replay difference.
2. Infrastructure: re-run that state (fork `branches` task on a states_dir holding only it), at most 3 attempts (prereg §5.2).
3. A mismatch that persists after the budget is a structural exclusion (prereg §5.3c): the task is excluded from that cell
   in all blocks. holdout_confirm is then re-run with this exclusion set and published as a **dated correction** next to
   the original reading; the paper reports both, and the original output is never edited.
4. If coverage is incomplete when the paper freezes, the paper reports the actual coverage (states checked / 1202) and keeps
   the remaining uncertainty explicit.

## 6. Outputs and leak guard
- `analysis/fork/holdout_qqfull_audit.py --split holdout` (split_guard first) writes counts, categories, booleans, the
  precondition checks, input sha256, git head and script sha256. No outcome value and no outcome-derived count is written.
  Mismatches are listed by state_id prefix and failing check names only.
