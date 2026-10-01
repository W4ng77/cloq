# Simulator robustness control (Sonnet 5.5 user) — 20261001T195253Z — DRY RUN (mock user, not results)

Scope: Robustness of continuations on FIXED histories generated with the old simulator (Qwen3-4B-Instruct-2507). Only the user simulator after the fork state is replaced. It does NOT replace a full benchmark re-run with a new simulator, and makes no claim about Bank U rates under Sonnet.

Blocks: f01. f01 only: at freeze time f02/f03 had not landed for every cell (pending: ['q4_gptq_w4_d1/f03', 'q4_kvq_int8/f02', 'q4_kvq_int8/f03', 'q8_kvq_int8/f03']).

Units with results: 1/78. User: {'provider': 'relay', 'model': 'claude-sonnet-5-5 (Claude Code subagent relay)'}.

## Original flips under the Sonnet user

Primary: sign of the replicate-mean flip indicator Dbar vs the original direction.

| group | n | missing | retained | reversed | vanished (both succeed / both fail / mixed tie) |
|---|---|---|---|---|---|
| all | 39 | 39 | 0 [None, None] | 0 [None, None] | 0 (0 / 0 / 0) |
| model=q4 | 31 | 31 | 0 [None, None] | 0 [None, None] | 0 (0 / 0 / 0) |
| model=q8 | 8 | 8 | 0 [None, None] | 0 [None, None] | 0 (0 / 0 / 0) |
| sub=U1 | 21 | 21 | 0 [None, None] | 0 [None, None] | 0 (0 / 0 / 0) |
| sub=U2B | 17 | 17 | 0 [None, None] | 0 [None, None] | 0 (0 / 0 / 0) |
| sub=U2Q | 1 | 1 | 0 [None, None] | 0 [None, None] | 0 (0 / 0 / 0) |
| sub_cls=ii_talk | 37 | 37 | 0 [None, None] | 0 [None, None] | 0 (0 / 0 / 0) |
| sub_cls=ii_act | 2 | 2 | 0 [None, None] | 0 [None, None] | 0 (0 / 0 / 0) |
| direction_orig=rescue | 17 | 17 | 0 [None, None] | 0 [None, None] | 0 (0 / 0 / 0) |
| direction_orig=damage | 22 | 22 | 0 [None, None] | 0 [None, None] | 0 (0 / 0 / 0) |

## Matched non-flip controls under the Sonnet user

| group | n | missing | new flips | rescue / damage |
|---|---|---|---|---|
| all | 39 | 38 | 0 [0.0, 0.975] | 0 / 0 |
| model=q4 | 31 | 30 | 0 [0.0, 0.975] | 0 / 0 |
| model=q8 | 8 | 8 | 0 [None, None] | 0 / 0 |
| sub=U1 | 21 | 21 | 0 [None, None] | 0 / 0 |
| sub=U2B | 17 | 16 | 0 [0.0, 0.975] | 0 / 0 |
| sub=U2Q | 1 | 1 | 0 [None, None] | 0 / 0 |
| sub_cls=ii_talk | 38 | 37 | 0 [0.0, 0.975] | 0 / 0 |
| sub_cls=ii_act | 1 | 1 | 0 [None, None] | 0 / 0 |

## Per-replicate distribution and within-simulator variability (R = 3)

Flips, units by number of replicates flipping in the original direction (0..R): {"0": 0, "1": 0, "2": 0, "3": 0}; in the reversed direction: {"0": 0, "1": 0, "2": 0, "3": 0}

Flips per replicate: {"0": {"n": 0, "retained": 0, "reversed": 0, "vanished": 0}, "1": {"n": 0, "retained": 0, "reversed": 0, "vanished": 0}, "2": {"n": 0, "retained": 0, "reversed": 0, "vanished": 0}}

Controls, units by number of replicates flipping (0..R): {"0": 1, "1": 0, "2": 0, "3": 0}

Controls per replicate: {"0": {"n": 1, "new_flip": 0, "stays_non_flip": 1}, "1": {"n": 1, "new_flip": 0, "stays_non_flip": 1}, "2": {"n": 1, "new_flip": 0, "stays_non_flip": 1}}

| role:arm | units whose replicates disagree | n | share [95%] |
|---|---|---|---|
| flip:BQ | 0 | 0 | None [None, None] |
| flip:QQ | 0 | 0 | None [None, None] |
| control:BQ | 0 | 1 | 0.0 [0.0, 0.975] |
| control:QQ | 0 | 1 | 0.0 [0.0, 0.975] |

Paired (flip x its control): {'incomplete_pair': 39}

Arm agreement with the original Y: {"flip:BQ": {"agree_replicates": 0, "n_replicates": 0, "ci95": [null, null]}, "flip:QQ": {"agree_replicates": 0, "n_replicates": 0, "ci95": [null, null]}, "control:BQ": {"agree_replicates": 3, "n_replicates": 3, "ci95": [0.292, 1.0]}, "control:QQ": {"agree_replicates": 3, "n_replicates": 3, "ci95": [0.292, 1.0]}}

Termination: {'user_stop': 6}

Sonnet usage: {'n_calls': 18, 'prompt_tokens': 0, 'completion_tokens': 0, 'cost_usd': 0, 'n_request_ids': 18}

Intervals: exact Clopper-Pearson 95% over units with both arms. No pass threshold was pre-specified.
