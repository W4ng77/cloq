# CLOQ v0 findings

Generated 2026-09-16T11:28:26+00:00 from `analysis/results.json`.
Model Qwen/Qwen3-4B-Instruct-2507 at revision `cdbee75f17c0`, tau2-bench text mode, GPTQ W4 group 128,
calibration budget 64000 tokens per arm within 1%.

## Headline: closed-loop task success (database end-state match)

| domain | n | bf16 | static | fp_traj | cloq |
|---|---|---|---|---|---|
| retail | 58 | 0.362 | 0.241 | 0.362 | 0.293 |
| airline | 27 | 0.407 | 0.407 | 0.333 | 0.444 |
| pooled | 85 | 0.376 | 0.294 | 0.353 | 0.341 |

Paired task-level bootstrap, 10,000 replicates:

| contrast | pooled difference | 95% CI |
|---|---|---|
| fp_traj - static | 0.059 | [-0.024, 0.141] |
| cloq - fp_traj | -0.012 | [-0.106, 0.082] |
| cloq - static | 0.047 | [-0.047, 0.141] |
| bf16 - static | 0.082 | [-0.024, 0.188] |
| bf16 - fp_traj | 0.024 | [-0.094, 0.129] |
| bf16 - cloq | 0.035 | [-0.082, 0.153] |

## Agent behaviour

| arm | domain | premature | mean decisions | repeated tool calls | parser errors |
|---|---|---|---|---|---|
| bf16 | retail | 0.000 | 12.8 | 0.129 | 0.0000 |
| static | retail | 0.224 | 30.4 | 0.380 | 0.0000 |
| fp_traj | retail | 0.121 | 23.6 | 0.255 | 0.0000 |
| cloq | retail | 0.086 | 20.6 | 0.080 | 0.0000 |
| bf16 | airline | 0.000 | 11.3 | 0.065 | 0.0000 |
| static | airline | 0.074 | 17.6 | 0.091 | 0.0000 |
| fp_traj | airline | 0.037 | 14.4 | 0.085 | 0.0000 |
| cloq | airline | 0.037 | 16.0 | 0.037 | 0.0000 |

## Open-loop fidelity versus closed-loop success

Replay of stored BF16 held-out contexts without executing the result.

| arm | domain | tool-name agr. | full tool-call agr. | NLL/token | closed-loop success |
|---|---|---|---|---|---|
| static | retail | 0.859 | 0.806 | 0.0929 | 0.241 |
| fp_traj | retail | 0.908 | 0.851 | 0.0745 | 0.362 |
| cloq | retail | 0.896 | 0.836 | 0.0743 | 0.293 |
| static | airline | 0.893 | 0.828 | 0.0937 | 0.407 |
| fp_traj | airline | 0.893 | 0.828 | 0.0897 | 0.333 |
| cloq | airline | 0.905 | 0.828 | 0.0842 | 0.444 |

## Horizon amplification (pooled, tasks split at the median BF16 horizon)

| arm | gap on short tasks | gap on long tasks | difference | 95% CI | one-sided p |
|---|---|---|---|---|---|
| static | 0.000 (n=48) | 0.189 (n=37) | 0.189 | [-0.017, 0.399] | 0.039 |
| fp_traj | -0.083 (n=48) | 0.162 (n=37) | 0.245 | [0.015, 0.470] | 0.019 |
| cloq | -0.021 (n=48) | 0.108 (n=37) | 0.129 | [-0.117, 0.374] | 0.156 |

## First divergence in tool-call behaviour

| arm | domain | diverged | median t*/H | success early div | success late div | success no div |
|---|---|---|---|---|---|---|
| static | retail | 0.931 | 0.369 | 0.182 | 0.286 | 0.500 |
| fp_traj | retail | 0.948 | 0.400 | 0.265 | 0.429 | 1.000 |
| cloq | retail | 0.897 | 0.283 | 0.250 | 0.333 | 0.500 |
| static | airline | 1.000 | 0.222 | 0.421 | 0.375 | n/a |
| fp_traj | airline | 0.963 | 0.232 | 0.176 | 0.556 | 1.000 |
| cloq | airline | 0.963 | 0.225 | 0.400 | 0.455 | 1.000 |

## Occupancy: distance from visited states to each calibration buffer

Cosine support distance in the frozen BF16 final-layer representation at the action boundary.

| domain | arm | Q to static | Q to fp_traj | Q to cloq | pre-divergence | post-divergence | MMD(FP,Q) | MMD null |
|---|---|---|---|---|---|---|---|---|
| retail | BF16 states | 0.137 | 0.108 | 0.102 | | | | |
| retail | static | 0.298 | 0.281 | 0.083 | 0.058 | 0.299 | 0.2105 | -0.0000 |
| retail | fp_traj | 0.255 | 0.236 | 0.082 | 0.062 | 0.253 | 0.1226 | -0.0000 |
| retail | cloq | 0.234 | 0.211 | 0.088 | 0.057 | 0.226 | 0.0896 | -0.0000 |
| airline | BF16 states | 0.132 | 0.101 | 0.101 | | | | |
| airline | static | 0.236 | 0.218 | 0.077 | 0.060 | 0.246 | 0.1124 | -0.0006 |
| airline | fp_traj | 0.135 | 0.107 | 0.103 | 0.064 | 0.118 | 0.0023 | -0.0006 |
| airline | cloq | 0.201 | 0.179 | 0.078 | 0.063 | 0.202 | 0.0541 | -0.0006 |

## Composition of the CLOQ on-policy half (plan section 19)

5 Q0 contexts, 31825 tokens; categories overlap.

| category | share of Q0 tokens |
|---|---|
| before_divergence | 0.313 |
| after_divergence | 0.687 |
| parser_error | 0.000 |
| tool_error | 0.000 |
| repeated_tool_call | 0.000 |
| near_failed_end | 0.257 |
| truncated_context | 0.491 |

## Pre-specified continuation rules (plan section 24)

- **A_horizon_amplification**: FIRED. Rule: Static gap larger on long-horizon tasks (median split), one-sided p < 0.10
- **B_occupancy_shift**: FIRED. Rule: support distance to the FP-Traj buffer higher after first divergence than before, and MMD(FP, Q) above twice its FP-split null, for at least one arm/domain
- **C_trajectory_calibration**: FIRED. Rule: in at least one domain: FP-Traj beats Static on closed-loop success with a CI excluding 0, or diverges later AND reproduces more tool calls
- **strong_method_cloq_over_fp_traj**: not met. Rule: pooled CLOQ - FP-Traj on db_match with a CI excluding 0

**3 of 3 core signals fired. Proceed to the full paper: yes** (plan section 24: proceed if at least two of A, B, C fired).

Stop/rethink rules that fired: none

## Deliverables (plan section 29)

1. frozen task/calibration manifests — `manifests/task_split_v0.json, manifests/calib_*.json`
2. BF16 trajectories — `runs/bf16/*/trajectory.jsonl and decisions.jsonl`
3. Static-W4 checkpoint — `ckpts/static_w4`
4. FP-Traj-W4 checkpoint — `ckpts/fp_traj_w4`
5. paired held-out closed-loop results — `runs/*_eval/*/metrics.json, analysis/results.json`
6. open-loop action agreement and NLL — `runs/*_eval/*/openloop.summary.json`
7. first-divergence statistics — `runs/*_eval/*/divergence.json`
8. FP-versus-Q occupancy distance — `analysis/occupancy_last.json, analysis/occupancy_obs.json`
9. CLOQ-W4 checkpoint and evaluation — `ckpts/cloq_w4, runs/cloq_eval/`

## Integrity

All checks passed: yes.

## Limitations

- The 64k-token budget buys only 10 to 13 calibration contexts, because one agent context is 5 to 8k
  tokens. Each arm therefore rests on a single small random draw, and draw variance is not separated
  from method effect. Repeating every arm under two or three calibration seeds is the first thing the
  full paper needs.
- The user simulator and the natural-language assertion judge are the same 4B model as the agent,
  because this machine has no external API. The primary endpoint avoids the judge entirely, but the
  simulator occasionally fails to end a conversation, which is what produces the step-cap terminations.
- Held-out sets are retail n=58, airline n=27; the airline
  set is small enough that a two-task swing moves its rate by 0.074.
- Free-text agreement across arms is bounded by launch-to-launch nondeterminism; only the tool-call
  metrics and the database end-state are safe to compare. See `scripts/bf16_replicate.sh`.