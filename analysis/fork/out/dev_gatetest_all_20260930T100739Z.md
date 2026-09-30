**TL;DR** Fork development analysis (INCLUDES GATE STATES: testing only): q4:awq_w4 G_all -0.4 [-7.9, +7.2] pp (states 370/631); q4:gptq_w4_d1 G_all -2.2 [-7.9, +4.2] pp (states 377/975); q4:kvq_int4_rot G_all -40.0 [-100.0, +0.0] pp (states 4/5); q8:awq_w4 G_all +4.2 [-3.0, +12.7] pp (states 289/358); q8:gptq_w4_d1 G_all -5.4 [-14.7, +5.5] pp (states 46/162). No-op sample 141/141; quarantined dirs 0.

# Fork development analysis (2026-09-30T10:07:39Z)

Snapshot `20260930T0911Z` (sha 758f1d452edd), script sha ccbc457e3565, git 1135b48bd2, fingerprint ff4b8bf12cc87c22. Full numbers: `analysis/fork/out/dev_gatetest_all_20260930T100739Z.json`.
Units = task x block; percentages in pp; 95% hierarchical bootstrap (tasks, blocks within task), B = 2000. G_all is the primary endpoint (g_min = eps = 3 pp).

| cell | units | states | G_all | rescue | damage | A | C | I | LB>0 | LB>3pp |
|---|---|---|---|---|---|---|---|---|---|---|
| q4:awq_w4 | 631 | 370 | -0.4 [-7.9, +7.2] | 9.3 | 9.7 | -1.7 [-9.1, +5.6] | -1.7 [-7.8, +3.9] | +1.3 [-6.7, +9.7] | False | False |
| q4:gptq_w4_d1 | 975 | 377 | -2.2 [-7.9, +4.2] | 5.8 | 8.0 | -2.7 [-8.5, +3.0] | -0.1 [-4.8, +4.3] | +0.4 [-6.4, +7.4] | False | False |
| q4:kvq_int4_rot | 5 | 4 | -40.0 [-100.0, +0.0] | 0.0 | 40.0 | -40.0 [-100.0, +0.0] | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] | False | False |
| q8:awq_w4 | 358 | 289 | +4.2 [-3.0, +12.7] | 10.3 | 6.0 | -0.1 [-7.5, +7.4] | -2.8 [-10.7, +5.8] | +4.3 [-5.3, +15.5] | False | False |
| q8:gptq_w4_d1 | 162 | 46 | -5.4 [-14.7, +5.5] | 3.6 | 9.0 | -8.4 [-19.8, +2.8] | -0.1 [-7.5, +6.7] | +3.0 [-9.3, +15.8] | False | False |

| pool (equal weight) | G_all | A | C | I |
|---|---|---|---|---|
| W4:q4:pooled_equal_weight | -1.3 [-6.0, +3.7] | -2.2 [-6.8, +2.5] | -0.9 [-4.9, +2.8] | +0.9 [-4.2, +6.5] |
| W4:q8:pooled_equal_weight | -0.6 [-6.5, +6.5] | -4.3 [-10.9, +2.6] | -1.5 [-7.2, +3.8] | +3.7 [-3.8, +12.1] |
| W4:all:pooled_equal_weight | -0.9 [-4.2, +3.4] | -3.2 [-7.4, +1.0] | -1.2 [-5.1, +2.2] | +2.3 [-2.1, +7.7] |
| stress:q4:pooled_equal_weight | -40.0 [-100.0, +0.0] | -40.0 [-100.0, +0.0] | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] |
| stress:all:pooled_equal_weight | -40.0 [-100.0, +0.0] | -40.0 [-100.0, +0.0] | +0.0 [+0.0, +0.0] | +0.0 [+0.0, +0.0] |

Consequence composition (divergent units: rescue / new damage / both succeed / both fail) and type breakdown:
- q4:awq_w4: {'rescue': 46, 'damage': 52, 'both_succeed': 80, 'both_fail': 192}; t* median 3.0; excluded {'state without branches': 1068, 'search': 1}
  - act->talk: n 65, {'rescue': 15, 'damage': 11, 'both_succeed': 13, 'both_fail': 26}, G|type +6.2 [-27.8, +38.3], contribution to G_all +0.9 [-2.5, +4.6]
  - talk->act: n 161, {'rescue': 20, 'damage': 23, 'both_succeed': 48, 'both_fail': 70}, G|type -1.9 [-14.7, +12.3], contribution to G_all -0.3 [-5.1, +4.8]
  - tool_name: n 74, {'rescue': 8, 'damage': 9, 'both_succeed': 13, 'both_fail': 44}, G|type -1.4 [-24.6, +21.1], contribution to G_all +0.4 [-3.2, +4.2]
  - tool_args: n 67, {'rescue': 3, 'damage': 9, 'both_succeed': 3, 'both_fail': 52}, G|type -9.0 [-31.1, +8.5], contribution to G_all -1.4 [-4.4, +0.8]
  - other: n 3, {'rescue': 0, 'damage': 0, 'both_succeed': 3, 'both_fail': 0}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
- q4:gptq_w4_d1: {'rescue': 39, 'damage': 55, 'both_succeed': 96, 'both_fail': 187}; t* median 4.0; excluded {'state without branches': 725}
  - act->talk: n 116, {'rescue': 12, 'damage': 34, 'both_succeed': 27, 'both_fail': 43}, G|type -19.0 [-41.5, +5.5], contribution to G_all -4.0 [-8.5, +0.4]
  - talk->act: n 90, {'rescue': 7, 'damage': 8, 'both_succeed': 16, 'both_fail': 59}, G|type -1.1 [-15.6, +13.4], contribution to G_all +0.3 [-1.6, +2.6]
  - tool_name: n 63, {'rescue': 9, 'damage': 2, 'both_succeed': 15, 'both_fail': 37}, G|type +11.1 [-5.3, +31.3], contribution to G_all +0.7 [-0.5, +2.2]
  - tool_args: n 104, {'rescue': 11, 'damage': 8, 'both_succeed': 38, 'both_fail': 47}, G|type +2.9 [-12.0, +19.8], contribution to G_all +1.1 [-0.9, +4.1]
  - other: n 4, {'rescue': 0, 'damage': 3, 'both_succeed': 0, 'both_fail': 1}, G|type -75.0 [-100.0, +0.0], contribution to G_all -0.3 [-1.2, +0.0]
- q4:kvq_int4_rot: {'rescue': 0, 'damage': 2, 'both_succeed': 0, 'both_fail': 2}; t* median 3.5; excluded {'state without branches': 7}
  - talk->act: n 2, {'rescue': 0, 'damage': 1, 'both_succeed': 0, 'both_fail': 1}, G|type -50.0 [-100.0, +0.0], contribution to G_all -20.0 [-100.0, +0.0]
  - tool_name: n 1, {'rescue': 0, 'damage': 0, 'both_succeed': 0, 'both_fail': 1}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
  - other: n 1, {'rescue': 0, 'damage': 1, 'both_succeed': 0, 'both_fail': 0}, G|type -100.0 [-100.0, +0.0], contribution to G_all -20.0 [-100.0, +0.0]
- q8:awq_w4: {'rescue': 35, 'damage': 19, 'both_succeed': 60, 'both_fail': 175}; t* median 1.0; excluded {'state without branches': 508}
  - act->talk: n 20, {'rescue': 3, 'damage': 2, 'both_succeed': 1, 'both_fail': 14}, G|type +5.0 [-31.6, +47.6], contribution to G_all +0.6 [-2.3, +3.9]
  - talk->act: n 145, {'rescue': 20, 'damage': 7, 'both_succeed': 22, 'both_fail': 96}, G|type +9.0 [-3.6, +23.2], contribution to G_all +3.3 [-2.2, +10.0]
  - tool_name: n 69, {'rescue': 10, 'damage': 8, 'both_succeed': 20, 'both_fail': 31}, G|type +2.9 [-17.6, +26.4], contribution to G_all +0.5 [-3.6, +5.0]
  - tool_args: n 42, {'rescue': 2, 'damage': 1, 'both_succeed': 17, 'both_fail': 22}, G|type +2.4 [-10.7, +21.1], contribution to G_all +0.0 [-1.3, +1.4]
  - other: n 13, {'rescue': 0, 'damage': 1, 'both_succeed': 0, 'both_fail': 12}, G|type -7.7 [-44.4, +0.0], contribution to G_all -0.2 [-1.2, +0.0]
- q8:gptq_w4_d1: {'rescue': 3, 'damage': 7, 'both_succeed': 7, 'both_fail': 29}; t* median 3.5; excluded {'state without branches': 688}
  - act->talk: n 1, {'rescue': 0, 'damage': 1, 'both_succeed': 0, 'both_fail': 0}, G|type -100.0 [-100.0, +0.0], contribution to G_all -0.9 [-5.1, +0.0]
  - talk->act: n 23, {'rescue': 3, 'damage': 5, 'both_succeed': 4, 'both_fail': 11}, G|type -8.7 [-48.3, +33.3], contribution to G_all -2.7 [-11.4, +7.2]
  - tool_name: n 10, {'rescue': 0, 'damage': 0, 'both_succeed': 0, 'both_fail': 10}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
  - tool_args: n 11, {'rescue': 0, 'damage': 1, 'both_succeed': 3, 'both_fail': 7}, G|type -9.1 [-50.0, +0.0], contribution to G_all -1.8 [-6.4, +0.0]
  - other: n 1, {'rescue': 0, 'damage': 0, 'both_succeed': 0, 'both_fail': 1}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
