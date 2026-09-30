**TL;DR** Fork development analysis (INCLUDES GATE STATES: testing only): q4:gptq_w4_d1 G_all -6.2 [-20.0, +0.0] pp (states 8/16); q4:kvq_int4_rot G_all -40.0 [-100.0, +0.0] pp (states 4/5); q8:awq_w4 G_all +0.0 [-42.9, +42.9] pp (states 5/7). No-op sample 17/17; quarantined dirs 0.

# Fork development analysis (2026-09-30T07:55:14Z)

Snapshot `20260930T0541Z` (sha de9af2a6b325), script sha df0b9f578e01, git e9cfcdf728, fingerprint 6a97c3d6f695c045. Full numbers: `analysis/fork/out/dev_gatetest_all_20260930T075514Z.json`.
Units = task x block; percentages in pp; 95% hierarchical bootstrap (tasks, blocks within task), B = 2000. G_all is the primary endpoint (g_min = eps = 3 pp).

| cell | units | states | G_all | rescue | damage | A | C | I | LB>0 | LB>3pp |
|---|---|---|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 | 16 | 8 | -6.2 [-20.0, +0.0] | 0.0 | 6.2 | -6.2 [-21.1, +0.0] | +6.2 [+0.0, +20.0] | +0.0 [-17.6, +18.2] | False | False |
| q4:kvq_int4_rot | 5 | 4 | -40.0 [-100.0, +0.0] | 0.0 | 40.0 | -40.0 [-100.0, +0.0] | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] | False | False |
| q8:awq_w4 | 7 | 5 | +0.0 [-42.9, +42.9] | 14.3 | 14.3 | +14.3 [+0.0, +50.0] | +14.3 [-33.4, +62.5] | -14.3 [-85.7, +40.0] | False | False |

| pool (equal weight) | G_all | A | C | I |
|---|---|---|---|---|
| q4:pooled_equal_weight | -23.1 [-50.0, +0.0] | -23.1 [-50.0, +0.0] | +3.1 [+0.0, +10.0] | +0.0 [-8.8, +9.1] |
| q8:pooled_equal_weight | +0.0 [-42.9, +42.9] | +14.3 [+0.0, +50.0] | +14.3 [-33.4, +62.5] | -14.3 [-85.7, +40.0] |
| all:pooled_equal_weight | -15.4 [-37.5, +6.7] | -10.7 [-29.6, +9.5] | +6.8 [-10.6, +23.7] | -4.8 [-28.9, +14.7] |

Consequence composition (divergent units: rescue / new damage / both succeed / both fail) and type breakdown:
- q4:gptq_w4_d1: {'rescue': 0, 'damage': 1, 'both_succeed': 3, 'both_fail': 4}; t* median 4.0; excluded {'state without branches': 4}
  - act->talk: n 3, {'rescue': 0, 'damage': 1, 'both_succeed': 2, 'both_fail': 0}, G|type -33.3 [-100.0, +0.0], contribution to G_all -6.2 [-20.0, +0.0]
  - talk->act: n 1, {'rescue': 0, 'damage': 0, 'both_succeed': 0, 'both_fail': 1}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
  - tool_name: n 2, {'rescue': 0, 'damage': 0, 'both_succeed': 0, 'both_fail': 2}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
  - tool_args: n 2, {'rescue': 0, 'damage': 0, 'both_succeed': 1, 'both_fail': 1}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
- q4:kvq_int4_rot: {'rescue': 0, 'damage': 2, 'both_succeed': 0, 'both_fail': 2}; t* median 3.5; excluded {'state without branches': 7}
  - talk->act: n 2, {'rescue': 0, 'damage': 1, 'both_succeed': 0, 'both_fail': 1}, G|type -50.0 [-100.0, +0.0], contribution to G_all -20.0 [-71.4, +0.0]
  - tool_name: n 1, {'rescue': 0, 'damage': 0, 'both_succeed': 0, 'both_fail': 1}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
  - other: n 1, {'rescue': 0, 'damage': 1, 'both_succeed': 0, 'both_fail': 0}, G|type -100.0 [-100.0, +0.0], contribution to G_all -20.0 [-57.1, +0.0]
- q8:awq_w4: {'rescue': 1, 'damage': 1, 'both_succeed': 1, 'both_fail': 2}; t* median 1.0; excluded {'Q block a6k2_q8_tel_awq_w4_q1/telecom not admitted in snapshot': 8, 'state without branches': 1}
  - talk->act: n 2, {'rescue': 1, 'damage': 0, 'both_succeed': 1, 'both_fail': 0}, G|type +50.0 [+0.0, +100.0], contribution to G_all +14.3 [+0.0, +50.0]
  - tool_name: n 1, {'rescue': 0, 'damage': 1, 'both_succeed': 0, 'both_fail': 0}, G|type -100.0 [-100.0, +0.0], contribution to G_all -14.3 [-50.0, +0.0]
  - tool_args: n 1, {'rescue': 0, 'damage': 0, 'both_succeed': 0, 'both_fail': 1}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
  - other: n 1, {'rescue': 0, 'damage': 0, 'both_succeed': 0, 'both_fail': 1}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
