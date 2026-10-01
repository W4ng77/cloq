# Simulator robustness control (Sonnet 5.5 user) — 20261001T225847Z

Scope: Robustness of continuations on FIXED histories generated with the old simulator (Qwen3-4B-Instruct-2507). Only the user simulator after the fork state is replaced. It does NOT replace a full benchmark re-run with a new simulator, and makes no claim about Bank U rates under Sonnet.

Blocks: f01. f01 only: at freeze time f02/f03 had not landed for every cell (pending: ['q4_gptq_w4_d1/f03', 'q4_kvq_int8/f02', 'q4_kvq_int8/f03', 'q8_kvq_int8/f03']).

Units with results: 76/78. User: {'provider': 'relay', 'model': 'claude-sonnet-5-5 (Claude Code subagent relay)'}.

## Original flips under the Sonnet user

Primary: sign of the replicate-mean flip indicator Dbar vs the original direction.

| group | n | missing | retained | reversed | vanished (both succeed / both fail / mixed tie) |
|---|---|---|---|---|---|
| all | 39 | 2 | 6 [0.062, 0.32] | 6 [0.062, 0.32] | 25 (15 / 2 / 8) |
| model=q4 | 31 | 2 | 5 [0.058, 0.358] | 6 [0.08, 0.397] | 18 (11 / 1 / 6) |
| model=q8 | 8 | 0 | 1 [0.003, 0.527] | 0 [0.0, 0.369] | 7 (4 / 1 / 2) |
| sub=U1 | 21 | 0 | 2 [0.012, 0.304] | 4 [0.054, 0.419] | 15 (8 / 2 / 5) |
| sub=U2B | 17 | 2 | 3 [0.043, 0.481] | 2 [0.017, 0.405] | 10 (7 / 0 / 3) |
| sub=U2Q | 1 | 0 | 1 [0.025, 1.0] | 0 [0.0, 0.975] | 0 (0 / 0 / 0) |
| sub_cls=ii_talk | 37 | 2 | 5 [0.048, 0.303] | 5 [0.048, 0.303] | 25 (15 / 2 / 8) |
| sub_cls=ii_act | 2 | 0 | 1 [0.013, 0.987] | 1 [0.013, 0.987] | 0 (0 / 0 / 0) |
| direction_orig=rescue | 17 | 0 | 2 [0.015, 0.364] | 3 [0.038, 0.434] | 12 (6 / 2 / 4) |
| direction_orig=damage | 22 | 2 | 4 [0.057, 0.437] | 3 [0.032, 0.379] | 13 (9 / 0 / 4) |

## Matched non-flip controls under the Sonnet user

| group | n | missing | new flips | rescue / damage |
|---|---|---|---|---|
| all | 39 | 0 | 11 [0.15, 0.449] | 7 / 4 |
| model=q4 | 31 | 0 | 10 [0.167, 0.514] | 6 / 4 |
| model=q8 | 8 | 0 | 1 [0.003, 0.527] | 1 / 0 |
| sub=U1 | 21 | 0 | 5 [0.082, 0.472] | 4 / 1 |
| sub=U2B | 17 | 0 | 6 [0.142, 0.617] | 3 / 3 |
| sub=U2Q | 1 | 0 | 0 [0.0, 0.975] | 0 / 0 |
| sub_cls=ii_talk | 38 | 0 | 10 [0.134, 0.431] | 6 / 4 |
| sub_cls=ii_act | 1 | 0 | 1 [0.025, 1.0] | 1 / 0 |

## Per-replicate distribution and within-simulator variability (R = 3)

Flips, units by number of replicates flipping in the original direction (0..R): {"0": 26, "1": 8, "2": 3, "3": 0}; in the reversed direction: {"0": 25, "1": 9, "2": 2, "3": 1}

Flips per replicate: {"0": {"n": 39, "retained": 5, "reversed": 6, "vanished": 28}, "1": {"n": 37, "retained": 6, "reversed": 5, "vanished": 26}, "2": {"n": 39, "retained": 4, "reversed": 5, "vanished": 30}}

Controls, units by number of replicates flipping (0..R): {"0": 26, "1": 3, "2": 9, "3": 1}

Controls per replicate: {"0": {"n": 39, "new_flip": 9, "stays_non_flip": 30}, "1": {"n": 39, "new_flip": 7, "stays_non_flip": 32}, "2": {"n": 39, "new_flip": 8, "stays_non_flip": 31}}

| role:arm | units whose replicates disagree | n | share [95%] |
|---|---|---|---|
| flip:BQ | 15 | 38 | 0.395 [0.24, 0.566] |
| flip:QQ | 16 | 38 | 0.421 [0.263, 0.592] |
| control:BQ | 10 | 39 | 0.256 [0.13, 0.421] |
| control:QQ | 8 | 39 | 0.205 [0.093, 0.365] |

Paired (flip x its control): {'flip_not_retained|control_no_flip': 24, 'flip_not_retained|control_new_flip': 7, 'incomplete_pair': 2, 'flip_retained|control_no_flip': 3, 'flip_retained|control_new_flip': 3}

Arm agreement with the original Y: {"flip:BQ": {"agree_replicates": 50, "n_replicates": 116, "ci95": [0.339, 0.526]}, "flip:QQ": {"agree_replicates": 65, "n_replicates": 116, "ci95": [0.465, 0.652]}, "control:BQ": {"agree_replicates": 86, "n_replicates": 117, "ci95": [0.645, 0.812]}, "control:QQ": {"agree_replicates": 94, "n_replicates": 117, "ci95": [0.72, 0.871]}}

Termination: {'user_stop': 467, 'too_many_errors': 1}

Sonnet usage: {'n_calls': 2337, 'prompt_tokens': 0, 'completion_tokens': 0, 'cost_usd': 0, 'n_request_ids': 2337}

Intervals: exact Clopper-Pearson 95% over units with both arms. No pass threshold was pre-specified.
