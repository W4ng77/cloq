**TL;DR** CONFIRMATORY (telecom holdout): G_all -4.57 [-7.17, -1.96] pp (crossed, decisional; 90% CI), block-t -4.57 [-6.08, -3.05]; reading: inconclusive. S1 r>0 & d>0: True. S2 rho 0.5883, p 0.0001. K' = 12.

# Holdout confirmation analysis — telecom holdout (2026-10-02T01:23:53Z)

Prereg `docs/insights/PREREG_FORK_CONFIRM.md` sha256 `902892dd63e99e16…` (recorded in splits_v1: `902892dd63e99e16ab9beefee9d39319d835eacdada3d4d92c4a1022d13fd622`); script sha `2af1b6890defcf03…`, git `d00b079555`; cut points `ab46abe91960f6c2…`; snapshot `20261002T0123Z`. JSON: `analysis/fork/out/holdout_confirm_20261002T012353Z.json`.

Cells and weights: {"q4:gptq_w4_d1": {"prereg_weight": 0.5, "weight_used": 0.5}, "q8:gptq_w4_d1": {"prereg_weight": 0.25, "weight_used": 0.25}, "q8:awq_w4": {"prereg_weight": 0.25, "weight_used": 0.25}}. prereg weights.

Blocks used (12): ['h01', 'h02', 'h03', 'h04', 'h05', 'h06', 'h07', 'h08', 'h09', 'h10', 'h11', 'h12']; halves {'h01': 'A', 'h02': 'B', 'h03': 'B', 'h04': 'A', 'h05': 'A', 'h06': 'B', 'h07': 'B', 'h08': 'B', 'h09': 'A', 'h10': 'B', 'h11': 'A', 'h12': 'A'}; block map {'h01': 'h01', 'h02': 'h02', 'h03': 'h03', 'h04': 'h04', 'h05': 'h05', 'h06': 'h06', 'h07': 'h07', 'h08': 'h08', 'h09': 'h09', 'h10': 'h10', 'h11': 'h11', 'h12': 'h12'}.

## Primary G_all (pp; 90% two-sided interval, lower end = one-sided 95% LB)

| interval | estimate [90% CI] | one-sided 95% LB |
|---|---|---|
| crossed task × block (decisional) | -4.57 [-7.17, -1.96] | -7.17 |
| t over block means (alongside) | -4.57 [-6.08, -3.05] | -6.08 |

Readings: {"estimable": true, "L_pp": -7.172, "U_pp": -1.96, "positive_gain": false, "gain_above_3pp": false, "small_average_effect_pm3pp": false, "sensitivity_5pp": {"gain_above_5pp": false, "small_average_effect_pm5pp": false}, "reading": "inconclusive"}

## S1 two-sided consequences (pp)

| stat | crossed (decisional) | block t | LB > 0 |
|---|---|---|---|
| rescue | +5.21 [+3.30, +7.11] | +5.21 [+4.02, +6.39] | True |
| damage | +9.77 [+6.45, +13.10] | +9.77 [+7.78, +11.77] | True |
| M | +14.98 [+10.09, +19.86] | +14.98 [+12.07, +17.89] | True |

S1 pass (r > 0 and d > 0): **True**

## S2 cross-half repeatability

rho = 0.5883, one-sided permutation p = 0.0001 (10000 draws, seed 20261001); null quantiles {'0.5': 0.0454, '0.9': 0.1952, '0.95': 0.2386, '0.99': 0.309}. Halves A ['h01', 'h04', 'h05', 'h09', 'h11', 'h12'], B ['h02', 'h03', 'h06', 'h07', 'h08', 'h10'].
- q4:gptq_w4_d1: {"n_tasks": 33, "levels_A": [0.0, 0.1667, 0.3333, 0.5, 0.6667], "levels_B": [0.0, 0.1667, 0.3333, 0.5, 0.6667], "tasks_with_mA_plus_mB_gt_0": 16, "estimable": true, "rho_c": 0.6679, "weight": 0.5, "weight_renormalised": 0.5}
- q8:gptq_w4_d1: {"n_tasks": 34, "levels_A": [0.0, 0.1667, 0.3333, 0.5, 0.6667], "levels_B": [0.0, 0.1667, 0.3333, 0.5, 0.6667, 0.8333], "tasks_with_mA_plus_mB_gt_0": 21, "estimable": true, "rho_c": 0.3738, "weight": 0.25, "weight_renormalised": 0.25}
- q8:awq_w4: {"n_tasks": 33, "levels_A": [0.0, 0.1667, 0.3333, 0.5, 0.6667, 0.8333], "levels_B": [0.0, 0.1667, 0.3333, 0.5, 0.6667, 0.8333], "tasks_with_mA_plus_mB_gt_0": 21, "estimable": true, "rho_c": 0.6436, "weight": 0.25, "weight_renormalised": 0.25}

real task pairing across independent nonce halves is more consistent than persona-preserving random pairing; this does not rule out task properties correlated with flip propensity within persona (fault load, issue type, BF16 difficulty), and makes no 'beyond difficulty' claim

## Strata (G per level; crossed interval; Holm within family)

**step_budget** (m = 3; contribution of divergent units in the level to G_all (sums with the other levels to G_all); cut {'cuts': [191.0, 197.0]})
- T1: n {'q4:gptq_w4_d1': 138, 'q8:gptq_w4_d1': 129, 'q8:awq_w4': 110}, G -0.32 [-1.57, +0.94], p 0.6771, Holm p 0.6771
- T2: n {'q4:gptq_w4_d1': 124, 'q8:gptq_w4_d1': 126, 'q8:awq_w4': 162}, G -2.30 [-3.88, -0.72], p 0.0165, Holm p 0.0495
- T3: n {'q4:gptq_w4_d1': 123, 'q8:gptq_w4_d1': 144, 'q8:awq_w4': 124}, G -1.94 [-3.35, -0.54], p 0.0229, Holm p 0.0495

**persona** (m = 3; G_all of the tasks in the level (task-equal, non-divergent = 0); cut {})
- Hard: n 11, G -5.99 [-12.23, +0.26], p 0.1147, Holm p 0.3355
- None: n 12, G -3.65 [-7.42, +0.13], p 0.1118, Holm p 0.3355
- Easy: n 11, G -4.36 [-9.19, +0.48], p 0.1385, Holm p 0.3355

**bf16_difficulty** (m = 3; G_all of the tasks in the level (task-equal, non-divergent = 0); cut {'c': 0.3333333333333333})
- 0: n 20, G -2.35 [-4.09, -0.62], p 0.0257, Holm p 0.0772
- low: n 11, G -4.54 [-8.90, -0.19], p 0.0860, Holm p 0.1720
- high: n 3, G -18.75 [-38.00, +0.50], p 0.1091, Holm p 0.1720

**task_length** (m = 3; G_all of the tasks in the level (task-equal, non-divergent = 0); cut {'cuts': [15.666666666666666, 20.333333333333332]})
- T1: n 9, G -5.09 [-9.81, -0.38], p 0.0755, Holm p 0.1511
- T2: n 8, G -0.78 [-4.46, +2.90], p 0.7270, Holm p 0.7270
- T3: n 17, G -6.17 [-10.49, -1.84], p 0.0189, Holm p 0.0567

**issue_type** (m = 3; G_all of the tasks in the level (task-equal, non-divergent = 0); cut {})
- mms_issue: n 14, G -1.15 [-3.33, +1.04], p 0.3880, Holm p 0.4434
- mobile_data_issue: n 11, G -9.09 [-14.98, -3.20], p 0.0111, Holm p 0.0333
- service_issue: n 9, G -4.40 [-10.32, +1.52], p 0.2217, Holm p 0.4434

**n_faults** (m = 3; G_all of the tasks in the level (task-equal, non-divergent = 0); cut {'cuts': [3.0, 5.0]})
- T1: n 19, G -6.37 [-9.91, -2.83], p 0.0030, Holm p 0.0091
- T2: n 10, G -1.94 [-7.58, +3.69], p 0.5704, Holm p 0.5704
- T3: n 5, G -2.92 [-5.18, -0.66], p 0.0337, Holm p 0.0674

## Per-cell components (descriptive)

| cell | G | r | d | M | units | divergent | excl. tasks |
|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 | -3.03 [-7.86, +1.80] | +5.05 [+2.13, +7.97] | +8.08 [+3.04, +13.12] | +13.13 [+6.46, +19.81] | 396 | 385 | 1 |
| q8:gptq_w4_d1 | -5.64 [-9.33, -1.94] | +4.41 [+2.14, +6.68] | +10.05 [+6.13, +13.96] | +14.46 [+9.34, +19.58] | 408 | 399 | 0 |
| q8:awq_w4 | -6.57 [-11.98, -1.15] | +6.31 [+3.74, +8.88] | +12.88 [+7.70, +18.05] | +19.19 [+12.85, +25.53] | 396 | 396 | 1 |

Missing units by reason: {"q4:gptq_w4_d1": {"structural: search: decision/trajectory count mismatch 61 vs 0": 1}, "q8:awq_w4": {"structural: search: decision/trajectory count mismatch 94 vs 0": 1}}
