> **DRY RUN ON DEV** — telecom dev blocks f01–f06 relabelled as a pseudo-holdout to prove the confirmatory pipeline executes end to end. Exploratory; not a holdout result; confirms nothing.

**TL;DR** DRY RUN ON DEV (telecom dev f01-f06 relabelled as pseudo-holdout; exploratory, not confirmatory): G_all +1.04 [-0.97, +3.06] pp (crossed, decisional; 90% CI), block-t +1.04 [-1.43, +3.51]; reading: not estimable for the decision rules (K' = 6 < 8); computed values descriptive only. S1 r>0 & d>0: True. S2 rho 0.5701, p 0.0001. K' = 6.

# Holdout confirmation analysis — DRY RUN ON DEV (2026-10-01T14:44:57Z)

Prereg `docs/insights/PREREG_FORK_CONFIRM.md` sha256 `902892dd63e99e16…` (recorded in splits_v1: `None`); script sha `2af1b6890defcf03…`, git `cb0ec33aae`; cut points `ab46abe91960f6c2…`; snapshot `20261001T1411Z`. JSON: `analysis/fork/out/holdout_confirm_DRYRUN_DEV_20261001T144457Z.json`.

Cells and weights: {"q8:gptq_w4_d1": {"prereg_weight": 0.25, "weight_used": 0.5}, "q8:awq_w4": {"prereg_weight": 0.25, "weight_used": 0.5}}. cells ['q4:gptq_w4_d1'] have no units (dev: no q4 telecom forks exist); weights renormalised over present cells.

Blocks used (6): ['f01', 'f02', 'f03', 'f04', 'f05', 'f06']; halves {'f01': 'B', 'f02': 'B', 'f03': 'A', 'f04': 'A', 'f05': 'B', 'f06': 'A'}; block map {'f01': 'f01', 'f02': 'f02', 'f03': 'f03', 'f04': 'f04', 'f05': 'f05', 'f06': 'f06'}.

## Primary G_all (pp; 90% two-sided interval, lower end = one-sided 95% LB)

| interval | estimate [90% CI] | one-sided 95% LB |
|---|---|---|
| crossed task × block (decisional) | +1.04 [-0.97, +3.06] | -0.97 |
| t over block means (alongside) | +1.04 [-1.43, +3.51] | -1.43 |

Readings: {"estimable": false, "L_pp": -0.974, "U_pp": 3.057, "positive_gain": false, "gain_above_3pp": false, "small_average_effect_pm3pp": false, "sensitivity_5pp": {"gain_above_5pp": false, "small_average_effect_pm5pp": true}, "reading": "not estimable for the decision rules (K' = 6 < 8); computed values descriptive only"}

## S1 two-sided consequences (pp)

| stat | crossed (decisional) | block t | LB > 0 |
|---|---|---|---|
| rescue | +7.29 [+5.48, +9.11] | +7.29 [+6.18, +8.40] | True |
| damage | +6.25 [+3.83, +8.67] | +6.25 [+3.71, +8.79] | True |
| M | +13.54 [+9.88, +17.20] | +13.54 [+10.50, +16.59] | True |

S1 pass (r > 0 and d > 0): **True**

## S2 cross-half repeatability

rho = 0.5701, one-sided permutation p = 0.0001 (10000 draws, seed 20261001); null quantiles {'0.5': 0.0309, '0.9': 0.1384, '0.95': 0.1677, '0.99': 0.2257}. Halves A ['f03', 'f04', 'f06'], B ['f01', 'f02', 'f05'].
- q8:gptq_w4_d1: {"n_tasks": 80, "levels_A": [0.0, 0.3333, 0.6667], "levels_B": [0.0, 0.3333, 0.6667, 1.0], "tasks_with_mA_plus_mB_gt_0": 30, "estimable": true, "rho_c": 0.6259, "weight": 0.5, "weight_renormalised": 0.5}
- q8:awq_w4: {"n_tasks": 80, "levels_A": [0.0, 0.3333, 0.6667], "levels_B": [0.0, 0.3333, 0.6667], "tasks_with_mA_plus_mB_gt_0": 31, "estimable": true, "rho_c": 0.5142, "weight": 0.5, "weight_renormalised": 0.5}

real task pairing across independent nonce halves is more consistent than persona-preserving random pairing; this does not rule out task properties correlated with flip propensity within persona (fault load, issue type, BF16 difficulty), and makes no 'beyond difficulty' claim

## Strata (G per level; crossed interval; Holm within family)

**step_budget** (m = 3; contribution of divergent units in the level to G_all (sums with the other levels to G_all); cut {'cuts': [191.0, 197.0]})
- T1: n {'q8:gptq_w4_d1': 151, 'q8:awq_w4': 134}, G +0.31 [-1.03, +1.66], p 0.7027, Holm p 1.0000
- T2: n {'q8:gptq_w4_d1': 122, 'q8:awq_w4': 184}, G +0.62 [-0.71, +1.96], p 0.4397, Holm p 1.0000
- T3: n {'q8:gptq_w4_d1': 204, 'q8:awq_w4': 162}, G +0.10 [-0.67, +0.87], p 0.8239, Holm p 1.0000

**persona** (m = 3; G_all of the tasks in the level (task-equal, non-divergent = 0); cut {})
- Hard: n 25, G +3.67 [-0.87, +8.21], p 0.1838, Holm p 0.5515
- None: n 28, G -0.89 [-4.67, +2.88], p 0.6971, Holm p 1.0000
- Easy: n 27, G +0.62 [-3.29, +4.52], p 0.7949, Holm p 1.0000

**bf16_difficulty** (m = 3; G_all of the tasks in the level (task-equal, non-divergent = 0); cut {'c': 0.3333333333333333})
- 0: n 46, G +0.00 [-1.21, +1.21], p 1.0000, Holm p 1.0000
- low: n 23, G +0.72 [-4.63, +6.08], p 0.8239, Holm p 1.0000
- high: n 11, G +6.06 [-4.51, +16.63], p 0.3455, Holm p 1.0000

**task_length** (m = 3; G_all of the tasks in the level (task-equal, non-divergent = 0); cut {'cuts': [15.666666666666666, 20.333333333333332]})
- T1: n 26, G -0.32 [-2.46, +1.82], p 0.8057, Holm p 1.0000
- T2: n 27, G +1.85 [-2.04, +5.75], p 0.4341, Holm p 1.0000
- T3: n 27, G +1.54 [-3.14, +6.22], p 0.5876, Holm p 1.0000

**issue_type** (m = 3; G_all of the tasks in the level (task-equal, non-divergent = 0); cut {})
- mms_issue: n 35, G +0.00 [-1.21, +1.21], p 1.0000, Holm p 1.0000
- mobile_data_issue: n 25, G +1.67 [-2.67, +6.00], p 0.5271, Holm p 1.0000
- service_issue: n 20, G +2.08 [-5.07, +9.24], p 0.6320, Holm p 1.0000

**n_faults** (m = 3; G_all of the tasks in the level (task-equal, non-divergent = 0); cut {'cuts': [3.0, 5.0]})
- T1: n 32, G +3.65 [-0.04, +7.33], p 0.1041, Holm p 0.3123
- T2: n 24, G -0.69 [-5.75, +4.36], p 0.8213, Holm p 0.9848
- T3: n 24, G -0.69 [-2.36, +0.97], p 0.4924, Holm p 0.9848

## Per-cell components (descriptive)

| cell | G | r | d | M | units | divergent | excl. tasks |
|---|---|---|---|---|---|---|---|
| q8:gptq_w4_d1 | +2.71 [-2.02, +7.44] | +8.75 [+5.09, +12.40] | +6.04 [+2.83, +9.25] | +14.79 [+9.63, +19.95] | 480 | 477 | 0 |
| q8:awq_w4 | -0.62 [-3.37, +2.12] | +5.83 [+3.59, +8.07] | +6.46 [+4.23, +8.69] | +12.29 [+8.62, +15.96] | 480 | 480 | 0 |

Missing units by reason: {}
