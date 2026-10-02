# SIMCTRL-P — Bank P four-arm simulator control — INTERIM (partial data; protocol gate not met) — 20261002T003506Z

**TL;DR.** INTERIM look, 30 complete states in 3 of 4 cells (batch 1 (pre-planned)). Pooled, original → Sonnet 5.5 (pp, [95% state bootstrap]): G +13.3 [-3.3, +30.0] → +2.7 [-7.3, +13.3] (change -10.7 [-30.7, +8.7]); H +10.0 [-6.7, +26.7] → +11.3 [+3.3, +20.0] (change +1.3 [-16.7, +19.3]); F +23.3 [+3.3, +43.3] → +12.7 [+3.3, +22.7] (change -10.7 [-28.7, +7.3]); G−H +3.3 [-10.0, +16.7] → -8.7 [-17.3, -0.7] (change -12.0 [-29.3, +4.0]). Robustness check only; per-cell tables below.

- **Robustness check only.** n is small (≤ 20 states per cell); nothing here confirms or refutes a few-pp G/H/F advantage.
- **Data:** 30/80 expected states complete ({'not run': 50, 'ok': 30}); q4:gptq_w4_d1|b1 not finished, q4:gptq_w4_d1|b2 not started, q4:awq_w4|b1 finished, q4:awq_w4|b2 not started, q8:gptq_w4_d1|b1 finished, q8:gptq_w4_d1|b2 not started, q8:awq_w4|b1 finished, q8:awq_w4|b2 not started.
- **Integrity:** row re-verification failures 0; v2 checks all pass over 600 exposed branches; 3091 unique request ids; missing replicates 0.
- **Unexposed:** 0 unexposed branches ({'BB': 0, 'BQ': 0, 'QB': 0, 'QQ': 0}); Y kept.
- **Evidence:** `analysis/fork/analyze_simctrl_p.py`; this file and its .json; inputs (with sha256) in the json `inputs`; `docs/insights/SIMCTRL_P_PROTOCOL.md`; `manifests/fork/simctrl_p_v1.json`.

> **INTERIM.** Run with `--allow-partial`. Gate failures:

> - q4:gptq_w4_d1|b1: no summary/rows (not finished, 8 branch files)
> - q4:gptq_w4_d1|b2: no summary/rows (not started, 0 branch files)
> - q4:awq_w4|b2: no summary/rows (not started, 0 branch files)
> - q8:gptq_w4_d1|b2: no summary/rows (not started, 0 branch files)
> - q8:awq_w4|b2: no summary/rows (not started, 0 branch files)

## 1. Inputs and protocol status

| cell × batch | state | units ran / expected | state ok | branches | arm errors | unexposed | protocol_ok | pass | user calls | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1|b1 | not finished (8 branch files) | 0 / 10 | | | | | | | | |
| q4:gptq_w4_d1|b2 | not started (0 branch files) | 0 / 10 | | | | | | | | |
| q4:awq_w4|b1 | finished | 10 / 10 | 10 | 200 | 0 | 0  | True | True | 926 | 7.00 |
| q4:awq_w4|b2 | not started (0 branch files) | 0 / 10 | | | | | | | | |
| q8:gptq_w4_d1|b1 | finished | 10 / 10 | 10 | 200 | 0 | 0  | True | True | 1003 | 9.32 |
| q8:gptq_w4_d1|b2 | not started (0 branch files) | 0 / 10 | | | | | | | | |
| q8:awq_w4|b1 | finished | 10 / 10 | 10 | 200 | 0 | 0  | True | True | 1162 | 8.58 |
| q8:awq_w4|b2 | not started (0 branch files) | 0 / 10 | | | | | | | | |

Row re-verification failures: 0

Relay v2 checks over exposed branches: v2_all_calls 600/600, v2_integrity_ok 600/600, v2_answer_model 600/600, v2_template 600/600, relay_all_answered 600/600. Request ids: 3091 (3091 unique; duplicates/non-v2: 0).

Original outcomes: admission re-run (units digests vs reference: q4:gptq_w4_d1 ok, q4:awq_w4 ok, q8:gptq_w4_d1 ok, q8:awq_w4 ok); dev state + branch file sha vs manifest 80/80.

States: {'not run': 50, 'ok': 30}.

## 2. G/H/F/G−H: original vs Sonnet 5.5 on the same states

### batch 1 (pre-planned) (n = 30 states)

Point estimate [95% stratified state bootstrap] in pp; the task-cluster interval is in the second table. Original = the single-run dev-fork outcomes of the same states; change = mean over states of (Sonnet contrast − original contrast).

**q4:awq_w4** (n = 10)

| estimand | original | Sonnet 5.5 (R = 5 mean) | change (Sonnet − original) |
|---|---|---|---|
| G | -10.0 [-40.0, +20.0] | -10.0 [-20.0, +0.0] | +0.0 [-28.0, +32.0] |
| H | +0.0 [-40.0, +40.0] | +10.0 [+4.0, +16.0] | +10.0 [-26.1, +46.0] |
| F | +0.0 [-40.0, +40.0] | +0.0 [-8.0, +8.0] | +0.0 [-36.0, +36.0] |
| G−H | -10.0 [-40.0, +20.0] | -20.0 [-34.0, -8.0] | -10.0 [-40.0, +16.0] |
| F−G | +10.0 [+0.0, +30.0] | +10.0 [+2.0, +20.0] | +0.0 [-20.0, +16.0] |
| F−H | +0.0 [-30.0, +30.0] | -10.0 [-22.0, -2.0] | -10.0 [-34.0, +12.1] |

**q8:gptq_w4_d1** (n = 10)

| estimand | original | Sonnet 5.5 (R = 5 mean) | change (Sonnet − original) |
|---|---|---|---|
| G | +20.0 [+0.0, +50.0] | +0.0 [-18.0, +18.0] | -20.0 [-52.0, +8.0] |
| H | +10.0 [+0.0, +30.0] | +4.0 [+0.0, +12.0] | -6.0 [-18.0, +0.0] |
| F | +30.0 [+0.0, +60.0] | +8.0 [-10.0, +26.0] | -22.0 [-50.0, +0.1] |
| G−H | +10.0 [+0.0, +30.0] | -4.0 [-20.0, +12.0] | -14.0 [-46.0, +12.0] |
| F−G | +10.0 [+0.0, +30.0] | +8.0 [-4.0, +26.0] | -2.0 [-30.0, +24.0] |
| F−H | +20.0 [+0.0, +50.0] | +4.0 [-10.0, +18.0] | -16.0 [-46.0, +8.0] |

**q8:awq_w4** (n = 10)

| estimand | original | Sonnet 5.5 (R = 5 mean) | change (Sonnet − original) |
|---|---|---|---|
| G | +30.0 [+0.0, +60.0] | +18.0 [-2.0, +42.0] | -12.0 [-50.0, +26.0] |
| H | +20.0 [+0.0, +50.0] | +20.0 [-4.0, +44.0] | +0.0 [-42.0, +36.0] |
| F | +40.0 [+10.0, +70.0] | +30.0 [+12.0, +52.0] | -10.0 [-44.0, +24.0] |
| G−H | +10.0 [+0.0, +30.0] | -2.0 [-16.0, +12.0] | -12.0 [-44.0, +12.0] |
| F−G | +10.0 [+0.0, +30.0] | +12.0 [+0.0, +26.0] | +2.0 [-10.0, +14.0] |
| F−H | +20.0 [+0.0, +50.0] | +10.0 [-4.0, +26.0] | -10.0 [-34.0, +12.0] |

**pool (equal weight over q4:awq_w4, q8:gptq_w4_d1, q8:awq_w4)** (n = 30)

| estimand | original | Sonnet 5.5 (R = 5 mean) | change (Sonnet − original) |
|---|---|---|---|
| G | +13.3 [-3.3, +30.0] | +2.7 [-7.3, +13.3] | -10.7 [-30.7, +8.7] |
| H | +10.0 [-6.7, +26.7] | +11.3 [+3.3, +20.0] | +1.3 [-16.7, +19.3] |
| F | +23.3 [+3.3, +43.3] | +12.7 [+3.3, +22.7] | -10.7 [-28.7, +7.3] |
| G−H | +3.3 [-10.0, +16.7] | -8.7 [-17.3, -0.7] | -12.0 [-29.3, +4.0] |
| F−G | +10.0 [+0.0, +23.3] | +10.0 [+2.7, +18.0] | +0.0 [-12.0, +10.7] |
| F−H | +13.3 [+0.0, +26.7] | +1.3 [-6.7, +9.3] | -12.0 [-26.7, +1.3] |

Task-cluster bootstrap intervals (pp; tasks resampled within cell, and across cells for the pool):

| cell | n states / tasks | G Sonnet | H Sonnet | F Sonnet | G−H Sonnet | G change | H change | F change | G−H change |
|---|---|---|---|---|---|---|---|---|---|
| q4:awq_w4 | 10 / 10 | -10.0 [-20.0, +0.0] | +10.0 [+4.0, +16.0] | +0.0 [-8.0, +8.0] | -20.0 [-34.0, -6.0] | +0.0 [-28.0, +30.0] | +10.0 [-26.0, +46.0] | +0.0 [-36.0, +36.0] | -10.0 [-40.0, +18.0] |
| q8:gptq_w4_d1 | 10 / 10 | +0.0 [-18.0, +20.0] | +4.0 [+0.0, +12.0] | +8.0 [-10.0, +26.0] | -4.0 [-20.0, +14.0] | -20.0 [-52.0, +8.0] | -6.0 [-18.0, +0.0] | -22.0 [-52.0, +4.0] | -14.0 [-48.0, +12.0] |
| q8:awq_w4 | 10 / 10 | +18.0 [-4.0, +44.0] | +20.0 [-2.0, +44.0] | +30.0 [+12.0, +52.0] | -2.0 [-16.0, +12.0] | -12.0 [-48.0, +26.0] | +0.0 [-38.0, +36.0] | -10.0 [-42.0, +24.0] | -12.0 [-42.0, +10.0] |
| pool | 30 / 23 | +2.7 [-9.0, +14.5] | +11.3 [+2.2, +20.6] | +12.7 [+1.6, +23.9] | -8.7 [-17.9, -0.2] | -10.7 [-30.6, +9.2] | +1.3 [-14.9, +16.9] | -10.7 [-29.6, +9.0] | -12.0 [-28.9, +3.1] |

Arm success rates (%, mean over states):

| cell | BB orig / Sonnet | BQ orig / Sonnet | QB orig / Sonnet | QQ orig / Sonnet |
|---|---|---|---|---|
| q4:awq_w4 | 60 / 74 | 50 / 64 | 60 / 84 | 60 / 74 |
| q8:gptq_w4_d1 | 50 / 44 | 40 / 36 | 30 / 40 | 20 / 36 |
| q8:awq_w4 | 50 / 58 | 40 / 46 | 30 / 48 | 10 / 28 |
| pool | 53 / 59 | 43 / 49 | 40 / 57 | 30 / 46 |

## 3. Within-simulator variability and agreement with the original

Share of states whose 5 Sonnet replicates of the arm are not all equal (exact 95%). This is sampling variability of the new simulator; it is not an off-diagonal share and is not comparable with W93's 26.9%.

| arm | q4:awq_w4 | q8:gptq_w4_d1 | q8:awq_w4 | all |
|---|---|---|---|---|
| BB | 4/10 [0.122, 0.738] | 1/10 [0.003, 0.445] | 4/10 [0.122, 0.738] | 9/30 [0.147, 0.494] |
| BQ | 5/10 [0.187, 0.813] | 3/10 [0.067, 0.652] | 3/10 [0.067, 0.652] | 11/30 [0.199, 0.561] |
| QB | 3/10 [0.067, 0.652] | 4/10 [0.122, 0.738] | 3/10 [0.067, 0.652] | 10/30 [0.173, 0.528] |
| QQ | 6/10 [0.262, 0.878] | 4/10 [0.122, 0.738] | 4/10 [0.122, 0.738] | 14/30 [0.283, 0.657] |

Distribution of the number of successful replicates (0–5) per state, all cells: BB {0: 9, 1: 1, 2: 1, 3: 3, 4: 4, 5: 12}; BQ {0: 10, 1: 2, 2: 3, 3: 4, 4: 2, 5: 9}; QB {0: 8, 1: 2, 2: 3, 3: 2, 4: 3, 5: 12}; QQ {0: 9, 1: 4, 2: 4, 3: 2, 4: 4, 5: 7}

Per-state agreement, original single-run outcome vs Sonnet arm mean (all cells pooled; Pearson r with a stratified bootstrap 95% CI):

| arm | r [95%] | orig = 1 / 0 (states) | Sonnet mean given orig 1 | given orig 0 | mean abs diff | orig rate | Sonnet rate |
|---|---|---|---|---|---|---|---|
| BB | 0.719 [0.444, 0.915] | 16 / 14 | 0.875 | 0.257 | 0.187 | 0.533 | 0.587 |
| BQ | 0.757 [0.548, 0.912] | 13 / 17 | 0.846 | 0.212 | 0.187 | 0.433 | 0.487 |
| QB | 0.632 [0.431, 0.825] | 12 / 18 | 0.9 | 0.356 | 0.253 | 0.4 | 0.573 |
| QQ | 0.597 [0.318, 0.814] | 9 / 21 | 0.822 | 0.305 | 0.267 | 0.3 | 0.46 |

## 4. Unexposed branches and sensitivity

| arm | unexposed branches | states with any (exact 95%) |
|---|---|---|
| BB | 0/150 | 0/30 [0.0, 0.116] |
| BQ | 0/150 | 0/30 [0.0, 0.116] |
| QB | 0/150 | 0/30 [0.0, 0.116] |
| QQ | 0/150 | 0/30 [0.0, 0.116] |

S1_exclude_states_with_unexposed: identical (no unexposed branch).

S2_exposed_replicates_only: identical (no unexposed branch).

## 5. Operations

| arm | termination | user calls total / mean / median / max | branches with 0 calls | missing replicates |
|---|---|---|---|---|
| BB | {'user_stop': 143, 'too_many_errors': 6, 'max_steps': 1} | 690 / 4.6 / 4.0 / 18 | 0 | 0 |
| BQ | {'user_stop': 145, 'too_many_errors': 2, 'max_steps': 3} | 774 / 5.16 / 4.0 / 18 | 0 | 0 |
| QB | {'user_stop': 146, 'too_many_errors': 1, 'max_steps': 3} | 738 / 4.92 / 4.0 / 18 | 0 | 0 |
| QQ | {'user_stop': 146, 'too_many_errors': 4} | 889 / 5.93 / 5.0 / 23 | 0 | 0 |

Context-overflow branches: 0; budget-check failures: 0. Sonnet usage: 3091 calls, $24.90 ($0.00805 per call).

## 6. Caveats (protocol §9)

- Robustness check only: whether the sign/size picture of G/H/F/G−H on these states survives a change of user simulator. It cannot confirm or refute few-pp G/H/F effects (W93 intervals are a few pp; n ≤ 80 states, 20 per cell).
- Histories up to h_t are fixed and come from the original user simulator; only the simulator after h_t changes.
- The new simulator (Sonnet 5.5 via headless `claude -p`, Claude Code default sampling) is stochastic; the original arm outcomes are single runs, so per-state original contrasts are in {−1, 0, 1} and carry the original simulator's sampling noise; part of any new − original change is noise, not a simulator effect.
- Says nothing about rates under the new simulator beyond these states; not a benchmark re-run.
- The per-state four outcomes are NOT summarised as an off-diagonal share and NOT compared with W93's 26.9% (with R = 5 replicate means, sampling noise alone creates arm disagreement).
- Cross-cell comparisons are descriptive (each cell selects its own divergent states).
