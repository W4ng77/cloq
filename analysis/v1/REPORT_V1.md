# CLOQ v1 development results

Dev set: 85 tasks (37 with BF16 horizon > 11). Three calibration draws per arm.

| arm | draw | retail | airline | pooled | long |
|---|---|---|---|---|---|
| bf16 | - | 0.362 | 0.407 | 0.376 | 0.297 |
| static | c1 | 0.328 | 0.444 | 0.365 | 0.243 |
| static | c2 | 0.293 | 0.370 | 0.318 | 0.162 |
| static | c3 | 0.328 | 0.370 | 0.341 | 0.162 |
| fp_traj | c1 | 0.241 | 0.370 | 0.282 | 0.054 |
| fp_traj | c2 | 0.345 | 0.407 | 0.365 | 0.243 |
| fp_traj | c3 | 0.241 | 0.333 | 0.271 | 0.135 |
| cloq_all | c1 | 0.310 | 0.333 | 0.318 | 0.189 |
| cloq_all | c2 | 0.276 | 0.333 | 0.294 | 0.081 |
| cloq_all | c3 | 0.397 | 0.407 | 0.400 | 0.243 |
| cloq_novel | c1 | 0.276 | 0.407 | 0.318 | 0.162 |
| cloq_novel | c2 | 0.259 | 0.370 | 0.294 | 0.108 |
| cloq_novel | c3 | 0.328 | 0.259 | 0.306 | 0.081 |
| cloq_matched_random | c1 | 0.276 | 0.444 | 0.329 | 0.243 |
| cloq_matched_random | c2 | 0.276 | 0.407 | 0.318 | 0.189 |
| cloq_matched_random | c3 | 0.397 | 0.370 | 0.388 | 0.216 |
| cloq_matched_alt | c1 | 0.379 | 0.519 | 0.424 | 0.270 |
| cloq_matched_alt | c2 | 0.345 | 0.407 | 0.365 | 0.216 |
| cloq_matched_alt | c3 | 0.310 | 0.222 | 0.282 | 0.162 |

## Crossed bootstrap (resample draw, then tasks within domain)

| contrast | pooled diff | 95% CI | long diff | 95% CI | all draws positive (long) |
|---|---|---|---|---|---|
| fp_traj - static | -0.035 | [-0.176, 0.129] | -0.045 | [-0.297, 0.216] | False |
| cloq_all - fp_traj | 0.031 | [-0.165, 0.188] | 0.027 | [-0.270, 0.243] | False |
| cloq_novel - fp_traj | 0.000 | [-0.153, 0.118] | -0.027 | [-0.243, 0.189] | False |
| cloq_novel - cloq_all | -0.031 | [-0.165, 0.094] | -0.054 | [-0.243, 0.135] | False |
| cloq_novel - static | -0.035 | [-0.141, 0.059] | -0.072 | [-0.216, 0.054] | False |
| cloq_all - static | -0.004 | [-0.129, 0.129] | -0.018 | [-0.189, 0.189] | False |
| cloq_novel - cloq_matched_random | -0.039 | [-0.141, 0.082] | -0.099 | [-0.243, 0.054] | False |
| cloq_novel - cloq_matched_alt | -0.051 | [-0.188, 0.094] | -0.099 | [-0.243, 0.027] | False |
| cloq_matched_random - cloq_all | 0.008 | [-0.094, 0.118] | 0.045 | [-0.108, 0.243] | False |
| cloq_matched_alt - cloq_all | 0.020 | [-0.188, 0.176] | 0.045 | [-0.189, 0.243] | False |
| cloq_matched_random - fp_traj | 0.039 | [-0.129, 0.188] | 0.072 | [-0.162, 0.297] | False |
| bf16 - static | 0.035 | [-0.082, 0.141] | 0.108 | [-0.081, 0.270] | True |
| bf16 - fp_traj | 0.071 | [-0.071, 0.188] | 0.153 | [-0.081, 0.351] | True |
| bf16 - cloq_all | 0.039 | [-0.106, 0.165] | 0.126 | [-0.081, 0.324] | True |
| bf16 - cloq_novel | 0.071 | [-0.035, 0.176] | 0.180 | [0.027, 0.351] | True |
| bf16 - cloq_matched_random | 0.031 | [-0.094, 0.165] | 0.081 | [-0.108, 0.243] | True |
| bf16 - cloq_matched_alt | 0.020 | [-0.129, 0.176] | 0.081 | [-0.135, 0.297] | True |

## Amendment 1 match audit

Reported whether or not the control wins. A high collision rate or a small novelty
separation means `cloq_novel - cloq_matched_*` is underpowered, and a null there is
inconclusive rather than evidence that novelty does not matter.

| arm | draw | same state as novel | novelty (novel) | novelty (control) | separation |
|---|---|---|---|---|---|
| cloq_matched_random | c1 | 10/29 | 0.320 | 0.175 | 0.145 |
| cloq_matched_random | c2 | 16/29 | 0.165 | 0.113 | 0.052 |
| cloq_matched_random | c3 | 8/29 | 0.177 | 0.107 | 0.070 |
| cloq_matched_alt | c1 | 0/29 | 0.320 | 0.115 | 0.205 |
| cloq_matched_alt | c2 | 2/29 | 0.165 | 0.059 | 0.105 |
| cloq_matched_alt | c3 | 2/29 | 0.177 | 0.089 | 0.087 |

## Pre-registered method selection (plan section 16)

Selected: **cloq_all**. cloq_novel did not satisfy both selection conditions.

long-task means: cloq_novel 0.117 vs cloq_all 0.171; pooled: 0.306 vs 0.337.