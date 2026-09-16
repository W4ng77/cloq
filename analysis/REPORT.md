# CLOQ v0 results (auto-generated)

## retail (n_eval = 58)

| metric | bf16 | static | fp_traj | cloq | bf16_rep |
|---|---|---|---|---|---|
| db_match | 0.362 | 0.241 | 0.362 | 0.293 | 0.362 |
| task_success | 0.310 | 0.207 | 0.310 | 0.259 | 0.310 |
| reward | 0.207 | 0.158 | 0.190 | 0.190 | 0.207 |

### Paired bootstrap contrasts (db_match)

| contrast | diff | 95% CI | n |
|---|---|---|---|
| fp_traj - static | 0.121 | [0.034, 0.224] | 58 |
| cloq - fp_traj | -0.069 | [-0.190, 0.052] | 58 |
| cloq - static | 0.052 | [-0.086, 0.172] | 58 |
| bf16 - static | 0.121 | [0.000, 0.241] | 58 |
| bf16 - fp_traj | 0.000 | [-0.121, 0.121] | 58 |
| bf16 - cloq | 0.069 | [-0.069, 0.207] | 58 |
| bf16 - bf16_rep | 0.000 | [0.000, 0.000] | 58 |

### Paired bootstrap contrasts (task_success, local judge)

| contrast | diff | 95% CI | n |
|---|---|---|---|
| fp_traj - static | 0.103 | [0.017, 0.207] | 58 |
| cloq - fp_traj | -0.052 | [-0.172, 0.069] | 58 |
| cloq - static | 0.052 | [-0.052, 0.155] | 58 |
| bf16 - static | 0.103 | [-0.017, 0.224] | 58 |
| bf16 - fp_traj | 0.000 | [-0.138, 0.138] | 58 |
| bf16 - cloq | 0.052 | [-0.086, 0.190] | 58 |
| bf16 - bf16_rep | 0.000 | [0.000, 0.000] | 58 |

### Horizon amplification (db_match; BF16 horizon quartile)

| quartile | n | bf16 | static (Δ) | fp_traj (Δ) | cloq (Δ) | bf16_rep (Δ) |
|---|---|---|---|---|---|---|
| Q1 | 11 | 0.455 | 0.545 (-0.091) | 0.727 (-0.273) | 0.364 (0.091) | 0.455 (0.000) |
| Q2 | 16 | 0.562 | 0.312 (0.250) | 0.500 (0.062) | 0.500 (0.062) | 0.562 (0.000) |
| Q3 | 17 | 0.294 | 0.176 (0.118) | 0.235 (0.059) | 0.235 (0.059) | 0.294 (0.000) |
| Q4 | 14 | 0.143 | 0.000 (0.143) | 0.071 (0.071) | 0.071 (0.071) | 0.143 (0.000) |

Spearman(horizon, failure): static=0.401, fp_traj=0.464, cloq=0.293, bf16_rep=0.311

Horizon amplification, tasks split at the median BF16 horizon (gap = BF16 - arm; a positive interval excluding zero means the gap grows with horizon):

| arm | gap short | gap long | long - short | 95% CI |
|---|---|---|---|---|
| static | 0.091 (n=33) | 0.160 (n=25) | 0.069 | [-0.171, 0.310] |
| fp_traj | -0.061 (n=33) | 0.080 (n=25) | 0.141 | [-0.130, 0.401] |
| cloq | 0.061 (n=33) | 0.080 (n=25) | 0.019 | [-0.272, 0.302] |
| bf16_rep | 0.000 (n=33) | 0.000 (n=25) | 0.000 | [0.000, 0.000] |

### Open-loop fidelity on BF16 held-out states

Replay of each stored BF16 context without executing the result. Full-action agreement includes free-text
rewording and is therefore bounded by the launch-noise floor; the tool-call columns are the primary readout.

| arm | states | tool-name agr. | full tool-call agr. | full action agr. | field F1 | NLL/token |
|---|---|---|---|---|---|---|
| static | 742 | 0.859 | 0.806 | 0.480 | 0.957 | 0.093 |
| fp_traj | 742 | 0.908 | 0.851 | 0.505 | 0.952 | 0.075 |
| cloq | 742 | 0.896 | 0.836 | 0.500 | 0.951 | 0.074 |
| bf16_rep | 742 | 1.000 | 1.000 | 1.000 | 1.000 | 0.038 |

### First divergence (t* = first decision whose tool-call behaviour differs from BF16)

Free-text rewording is excluded: it also differs between two launches of the same BF16 weights.
The last column is the fraction of tasks whose action string differs at all, wording included.

| arm | tool-div frac | median t* | median t*/H | SR early div | SR late div | SR no div | any-action div |
|---|---|---|---|---|---|---|---|
| static | 0.931 | 4.000 | 0.369 | 0.182 (n=33) | 0.286 (n=21) | 0.500 (n=4) | 1.000 |
| fp_traj | 0.948 | 4.000 | 0.400 | 0.265 (n=34) | 0.429 (n=21) | 1.000 (n=3) | 1.000 |
| cloq | 0.897 | 3.500 | 0.283 | 0.250 (n=40) | 0.333 (n=12) | 0.500 (n=6) | 1.000 |
| bf16_rep | 0.000 | n/a | n/a | n/a (n=0) | n/a (n=0) | 0.362 (n=58) | 0.000 |

### Secondary closed-loop statistics

| arm | decisions | tool calls | tool err | parser err | premature | repeated | truncated ctx |
|---|---|---|---|---|---|---|---|
| bf16 | 12.793 | 6.948 | 0.132 | 0.000 | 0.000 | 0.129 | 0.286 |
| static | 30.397 | 9.310 | 0.113 | 0.000 | 0.224 | 0.380 | 0.672 |
| fp_traj | 23.638 | 8.379 | 0.109 | 0.000 | 0.121 | 0.255 | 0.575 |
| cloq | 20.603 | 6.879 | 0.193 | 0.000 | 0.086 | 0.080 | 0.470 |
| bf16_rep | 12.793 | 6.948 | 0.132 | 0.000 | 0.000 | 0.129 | 0.286 |

## airline (n_eval = 27)

| metric | bf16 | static | fp_traj | cloq | bf16_rep |
|---|---|---|---|---|---|
| db_match | 0.407 | 0.407 | 0.333 | 0.444 | 0.407 |
| task_success | 0.370 | 0.333 | 0.222 | 0.333 | 0.370 |
| reward | 0.333 | 0.296 | 0.222 | 0.333 | 0.333 |

### Paired bootstrap contrasts (db_match)

| contrast | diff | 95% CI | n |
|---|---|---|---|
| fp_traj - static | -0.074 | [-0.222, 0.074] | 27 |
| cloq - fp_traj | 0.111 | [0.000, 0.259] | 27 |
| cloq - static | 0.037 | [-0.074, 0.148] | 27 |
| bf16 - static | 0.000 | [-0.222, 0.185] | 27 |
| bf16 - fp_traj | 0.074 | [-0.148, 0.296] | 27 |
| bf16 - cloq | -0.037 | [-0.259, 0.185] | 27 |
| bf16 - bf16_rep | 0.000 | [0.000, 0.000] | 27 |

### Paired bootstrap contrasts (task_success, local judge)

| contrast | diff | 95% CI | n |
|---|---|---|---|
| fp_traj - static | -0.111 | [-0.259, 0.000] | 27 |
| cloq - fp_traj | 0.111 | [0.000, 0.259] | 27 |
| cloq - static | 0.000 | [-0.111, 0.111] | 27 |
| bf16 - static | 0.037 | [-0.148, 0.222] | 27 |
| bf16 - fp_traj | 0.148 | [-0.074, 0.370] | 27 |
| bf16 - cloq | 0.037 | [-0.185, 0.259] | 27 |
| bf16 - bf16_rep | 0.000 | [0.000, 0.000] | 27 |

### Horizon amplification (db_match; BF16 horizon quartile)

| quartile | n | bf16 | static (Δ) | fp_traj (Δ) | cloq (Δ) | bf16_rep (Δ) |
|---|---|---|---|---|---|---|
| Q1 | 4 | 0.500 | 1.000 (-0.500) | 1.000 (-0.500) | 1.000 (-0.500) | 0.500 (0.000) |
| Q2 | 8 | 0.125 | 0.250 (-0.125) | 0.250 (-0.125) | 0.250 (-0.125) | 0.125 (0.000) |
| Q3 | 7 | 0.714 | 0.429 (0.286) | 0.143 (0.571) | 0.571 (0.143) | 0.714 (0.000) |
| Q4 | 8 | 0.375 | 0.250 (0.125) | 0.250 (0.125) | 0.250 (0.125) | 0.375 (0.000) |

Spearman(horizon, failure): static=0.330, fp_traj=0.420, cloq=0.327, bf16_rep=-0.073

Horizon amplification, tasks split at the median BF16 horizon (gap = BF16 - arm; a positive interval excluding zero means the gap grows with horizon):

| arm | gap short | gap long | long - short | 95% CI |
|---|---|---|---|---|
| static | -0.214 (n=14) | 0.231 (n=13) | 0.445 | [0.071, 0.824] |
| fp_traj | -0.143 (n=14) | 0.308 (n=13) | 0.451 | [0.011, 0.890] |
| cloq | -0.214 (n=14) | 0.154 (n=13) | 0.368 | [-0.022, 0.808] |
| bf16_rep | 0.000 (n=14) | 0.000 (n=13) | 0.000 | [0.000, 0.000] |

### Open-loop fidelity on BF16 held-out states

Replay of each stored BF16 context without executing the result. Full-action agreement includes free-text
rewording and is therefore bounded by the launch-noise floor; the tool-call columns are the primary readout.

| arm | states | tool-name agr. | full tool-call agr. | full action agr. | field F1 | NLL/token |
|---|---|---|---|---|---|---|
| static | 304 | 0.893 | 0.828 | 0.490 | 0.960 | 0.094 |
| fp_traj | 304 | 0.893 | 0.828 | 0.490 | 0.958 | 0.090 |
| cloq | 304 | 0.905 | 0.828 | 0.490 | 0.954 | 0.084 |
| bf16_rep | 304 | 1.000 | 1.000 | 1.000 | 1.000 | 0.040 |

### First divergence (t* = first decision whose tool-call behaviour differs from BF16)

Free-text rewording is excluded: it also differs between two launches of the same BF16 weights.
The last column is the fraction of tasks whose action string differs at all, wording included.

| arm | tool-div frac | median t* | median t*/H | SR early div | SR late div | SR no div | any-action div |
|---|---|---|---|---|---|---|---|
| static | 1.000 | 2.000 | 0.222 | 0.421 (n=19) | 0.375 (n=8) | n/a (n=0) | 1.000 |
| fp_traj | 0.963 | 2.500 | 0.232 | 0.176 (n=17) | 0.556 (n=9) | 1.000 (n=1) | 1.000 |
| cloq | 0.963 | 2.500 | 0.225 | 0.400 (n=15) | 0.455 (n=11) | 1.000 (n=1) | 1.000 |
| bf16_rep | 0.000 | n/a | n/a | n/a (n=0) | n/a (n=0) | 0.407 (n=27) | 0.000 |

### Secondary closed-loop statistics

| arm | decisions | tool calls | tool err | parser err | premature | repeated | truncated ctx |
|---|---|---|---|---|---|---|---|
| bf16 | 11.259 | 6.259 | 0.112 | 0.000 | 0.000 | 0.065 | 0.197 |
| static | 17.630 | 6.074 | 0.098 | 0.000 | 0.074 | 0.091 | 0.511 |
| fp_traj | 14.444 | 6.556 | 0.068 | 0.000 | 0.037 | 0.085 | 0.395 |
| cloq | 16.000 | 8.000 | 0.056 | 0.000 | 0.037 | 0.037 | 0.394 |
| bf16_rep | 11.259 | 6.259 | 0.112 | 0.000 | 0.000 | 0.065 | 0.197 |

## Pooled (db_match is definitionally identical across domains)

### db_match

means: static=0.294, fp_traj=0.353, cloq=0.341, bf16_rep=0.376, bf16=0.376

| contrast | diff | 95% CI | n |
|---|---|---|---|
| fp_traj - static | 0.059 | [-0.024, 0.141] | 85 |
| cloq - fp_traj | -0.012 | [-0.106, 0.082] | 85 |
| cloq - static | 0.047 | [-0.047, 0.141] | 85 |
| bf16 - static | 0.082 | [-0.024, 0.188] | 85 |
| bf16 - fp_traj | 0.024 | [-0.094, 0.129] | 85 |
| bf16 - cloq | 0.035 | [-0.082, 0.153] | 85 |
| bf16 - bf16_rep | 0.000 | [0.000, 0.000] | 85 |

### task_success

means: static=0.247, fp_traj=0.282, cloq=0.282, bf16_rep=0.329, bf16=0.329

| contrast | diff | 95% CI | n |
|---|---|---|---|
| fp_traj - static | 0.035 | [-0.035, 0.118] | 85 |
| cloq - fp_traj | 0.000 | [-0.094, 0.094] | 85 |
| cloq - static | 0.035 | [-0.047, 0.118] | 85 |
| bf16 - static | 0.082 | [-0.012, 0.188] | 85 |
| bf16 - fp_traj | 0.047 | [-0.071, 0.165] | 85 |
| bf16 - cloq | 0.047 | [-0.071, 0.165] | 85 |
| bf16 - bf16_rep | 0.000 | [0.000, 0.000] | 85 |

### long_horizon_subset_db_match

means: bf16={'short': 0.4375, 'long': 0.2972972972972973}, static={'short': 0.4375, 'long': 0.10810810810810811}, fp_traj={'short': 0.5208333333333334, 'long': 0.13513513513513514}, cloq={'short': 0.4583333333333333, 'long': 0.1891891891891892}, bf16_rep={'short': 0.4375, 'long': 0.2972972972972973}

| contrast | diff | 95% CI | n |
|---|---|---|---|
| cloq - static | 0.081 | [-0.027, 0.189] | 37 |
| cloq - fp_traj | 0.054 | [-0.054, 0.162] | 37 |
| fp_traj - static | 0.027 | [-0.081, 0.162] | 37 |
| bf16 - cloq | 0.108 | [-0.081, 0.297] | 37 |
| bf16 - static | 0.189 | [0.027, 0.351] | 37 |

### Long-horizon subset (BF16 horizon > 11; n=37 of 85)

The tasks on which quantization degradation exists at all. Averaging over every held-out task
dilutes a method effect with short tasks that have no gap to close.

| arm | short tasks | long tasks |
|---|---|---|
| bf16 | 0.438 | 0.297 |
| static | 0.438 | 0.108 |
| fp_traj | 0.521 | 0.135 |
| cloq | 0.458 | 0.189 |
| bf16_rep | 0.438 | 0.297 |

| contrast on long tasks | diff | 95% CI | P(>0) |
|---|---|---|---|
| cloq - static | 0.081 | [-0.027, 0.189] | 0.881 |
| cloq - fp_traj | 0.054 | [-0.054, 0.162] | 0.781 |
| fp_traj - static | 0.027 | [-0.081, 0.162] | 0.588 |
| bf16 - cloq | 0.108 | [-0.081, 0.297] | 0.830 |
| bf16 - static | 0.189 | [0.027, 0.351] | 0.983 |

### Pooled horizon amplification (db_match)

| arm | gap short | gap long | long - short | 95% CI | P(<=0) |
|---|---|---|---|---|---|
| static | 0.000 (n=48) | 0.189 (n=37) | 0.189 | [-0.017, 0.399] | 0.039 |
| fp_traj | -0.083 (n=48) | 0.162 (n=37) | 0.245 | [0.015, 0.470] | 0.019 |
| cloq | -0.021 (n=48) | 0.108 (n=37) | 0.129 | [-0.117, 0.374] | 0.156 |
| bf16_rep | 0.000 (n=48) | 0.000 (n=37) | 0.000 | [0.000, 0.000] | 1.000 |

## Where the CLOQ Q0 states come from (plan section 19)

5 Q0 contexts, 31825 tokens. Categories overlap by construction.

| category | share of Q0 tokens | contexts |
|---|---|---|
| before_divergence | 0.313 | 2 |
| after_divergence | 0.687 | 3 |
| parser_error | 0.000 | 0 |
| tool_error | 0.000 | 0 |
| repeated_tool_call | 0.000 | 0 |
| near_failed_end | 0.257 | 1 |
| truncated_context | 0.491 | 2 |

## Occupancy (occupancy_last)

### retail

FP states -> support: static=0.137, fp_traj=0.108, cloq=0.102

| arm | Q->static | Q->fp_traj | Q->cloq | pre-div (fp_traj supp) | post-div (fp_traj supp) | MMD(FP,Q) | MMD null |
|---|---|---|---|---|---|---|---|
| static | 0.298 | 0.281 | 0.083 | 0.058 (n=101) | 0.299 (n=1302) | 0.211 | -0.000 |
| fp_traj | 0.255 | 0.236 | 0.082 | 0.062 (n=105) | 0.253 (n=1043) | 0.123 | -0.000 |
| cloq | 0.234 | 0.211 | 0.088 | 0.057 (n=93) | 0.226 (n=973) | 0.090 | -0.000 |
| bf16_rep | 0.137 | 0.108 | 0.102 | 0.108 (n=732) | n/a (n=0) | -0.002 | -0.000 |

### airline

FP states -> support: static=0.132, fp_traj=0.101, cloq=0.101

| arm | Q->static | Q->fp_traj | Q->cloq | pre-div (fp_traj supp) | post-div (fp_traj supp) | MMD(FP,Q) | MMD null |
|---|---|---|---|---|---|---|---|
| static | 0.236 | 0.218 | 0.077 | 0.060 (n=63) | 0.246 (n=364) | 0.112 | -0.001 |
| fp_traj | 0.135 | 0.107 | 0.103 | 0.064 (n=63) | 0.118 (n=254) | 0.002 | -0.001 |
| cloq | 0.201 | 0.179 | 0.078 | 0.063 (n=71) | 0.202 (n=361) | 0.054 | -0.001 |
| bf16_rep | 0.132 | 0.101 | 0.101 | 0.101 (n=304) | n/a (n=0) | -0.004 | -0.001 |

## Occupancy (occupancy_obs)

### retail

FP states -> support: static=0.520, fp_traj=0.173, cloq=0.111

| arm | Q->static | Q->fp_traj | Q->cloq | pre-div (fp_traj supp) | post-div (fp_traj supp) | MMD(FP,Q) | MMD null |
|---|---|---|---|---|---|---|---|
| static | 0.416 | 0.229 | 0.129 | 0.092 (n=101) | 0.239 (n=1302) | 0.090 | -0.001 |
| fp_traj | 0.434 | 0.205 | 0.116 | 0.097 (n=105) | 0.216 (n=1043) | 0.049 | -0.001 |
| cloq | 0.438 | 0.207 | 0.109 | 0.089 (n=93) | 0.219 (n=973) | 0.041 | -0.001 |
| bf16_rep | 0.520 | 0.173 | 0.111 | 0.173 (n=732) | n/a (n=0) | -0.001 | -0.001 |

### airline

FP states -> support: static=0.558, fp_traj=0.199, cloq=0.131

| arm | Q->static | Q->fp_traj | Q->cloq | pre-div (fp_traj supp) | post-div (fp_traj supp) | MMD(FP,Q) | MMD null |
|---|---|---|---|---|---|---|---|
| static | 0.460 | 0.217 | 0.123 | 0.089 (n=63) | 0.239 (n=364) | 0.044 | -0.004 |
| fp_traj | 0.570 | 0.227 | 0.136 | 0.092 (n=63) | 0.261 (n=254) | 0.000 | -0.004 |
| cloq | 0.604 | 0.313 | 0.143 | 0.081 (n=71) | 0.358 (n=361) | 0.035 | -0.004 |
| bf16_rep | 0.558 | 0.199 | 0.131 | 0.199 (n=304) | n/a (n=0) | -0.003 | -0.004 |
