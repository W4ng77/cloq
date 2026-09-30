**TL;DR** Fork development analysis: q4:gptq_w3 G_all -1.2 [-10.1, +7.0] pp (states 232/255); q4:kvq_int4_rot G_all +4.7 [-3.9, +13.5] pp (states 233/255); q8:kvq_int4_rot G_all +3.1 [-5.6, +12.6] pp (states 239/255). No-op sample 62/62; quarantined dirs 0.

# Fork development analysis (2026-09-30T20:48:21Z)

Snapshot `20260930T2047Z` (sha e9d1cf7b6799), script sha 7a368e272d26, git 85bc003134, fingerprint b6c92ef485981e1b. Full numbers: `analysis/fork/out/dev_gptq_w3_kvq_int4_rot_20260930T204821Z.json`.
Units = task x block; percentages in pp; 95% hierarchical bootstrap (tasks, blocks within task), B = 2000. G_all is the primary endpoint (g_min = eps = 3 pp).

| cell | units | states | G_all | rescue | damage | A | C | I | LB>0 | LB>3pp |
|---|---|---|---|---|---|---|---|---|---|---|
| q4:gptq_w3 | 255 | 232 | -1.2 [-10.1, +7.0] | 9.0 | 10.2 | -2.7 [-12.3, +6.2] | +2.4 [-5.8, +11.1] | +1.6 [-10.8, +13.6] | False | False |
| q4:kvq_int4_rot | 255 | 233 | +4.7 [-3.9, +13.5] | 11.8 | 7.1 | +2.7 [-7.3, +12.1] | +6.7 [-2.9, +15.9] | +2.0 [-9.5, +13.9] | False | False |
| q8:kvq_int4_rot | 255 | 239 | +3.1 [-5.6, +12.6] | 11.8 | 8.6 | +5.1 [-4.5, +15.6] | +1.2 [-8.4, +10.6] | -2.0 [-15.2, +11.2] | False | False |

| pool (equal weight) | G_all | A | C | I |
|---|---|---|---|---|
| stress:q4:pooled_equal_weight | +1.8 [-4.7, +7.9] | +0.0 [-7.2, +6.8] | +4.5 [-1.9, +11.4] | +1.8 [-6.9, +10.5] |
| stress:q8:pooled_equal_weight | +3.1 [-5.6, +12.6] | +5.1 [-4.5, +15.6] | +1.2 [-8.4, +10.6] | -2.0 [-15.2, +11.2] |
| stress:all:pooled_equal_weight | +2.2 [-3.7, +7.5] | +1.7 [-3.6, +6.8] | +3.4 [-2.3, +9.0] | +0.5 [-6.7, +7.3] |

Consequence composition (divergent units: rescue / new damage / both succeed / both fail) and type breakdown:
- q4:gptq_w3: {'rescue': 23, 'damage': 26, 'both_succeed': 52, 'both_fail': 131}; t* median 2.0; excluded none
  - act->talk: n 25, {'rescue': 1, 'damage': 4, 'both_succeed': 5, 'both_fail': 15}, G|type -12.0 [-43.8, +14.8], contribution to G_all -1.2 [-4.6, +1.2]
  - talk->act: n 131, {'rescue': 13, 'damage': 16, 'both_succeed': 29, 'both_fail': 73}, G|type -2.3 [-16.2, +10.6], contribution to G_all -1.2 [-7.9, +5.3]
  - tool_name: n 43, {'rescue': 9, 'damage': 3, 'both_succeed': 11, 'both_fail': 20}, G|type +14.0 [-10.7, +38.9], contribution to G_all +2.4 [-1.6, +7.1]
  - tool_args: n 23, {'rescue': 0, 'damage': 2, 'both_succeed': 4, 'both_fail': 17}, G|type -8.7 [-37.5, +0.0], contribution to G_all -0.8 [-3.5, +0.0]
  - other: n 10, {'rescue': 0, 'damage': 1, 'both_succeed': 3, 'both_fail': 6}, G|type -10.0 [-54.6, +0.0], contribution to G_all -0.4 [-2.4, +0.0]
- q4:kvq_int4_rot: {'rescue': 30, 'damage': 18, 'both_succeed': 52, 'both_fail': 133}; t* median 2.0; excluded none
  - act->talk: n 19, {'rescue': 1, 'damage': 1, 'both_succeed': 6, 'both_fail': 11}, G|type +0.0 [-28.6, +26.1], contribution to G_all +0.0 [-1.8, +2.3]
  - talk->act: n 154, {'rescue': 25, 'damage': 12, 'both_succeed': 39, 'both_fail': 78}, G|type +8.4 [-2.9, +20.4], contribution to G_all +5.1 [-2.3, +13.0]
  - tool_name: n 23, {'rescue': 1, 'damage': 4, 'both_succeed': 2, 'both_fail': 16}, G|type -13.0 [-46.2, +14.3], contribution to G_all -1.2 [-4.5, +1.2]
  - tool_args: n 20, {'rescue': 1, 'damage': 0, 'both_succeed': 3, 'both_fail': 16}, G|type +5.0 [+0.0, +25.0], contribution to G_all +0.4 [+0.0, +2.4]
  - other: n 17, {'rescue': 2, 'damage': 1, 'both_succeed': 2, 'both_fail': 12}, G|type +5.9 [-26.3, +42.9], contribution to G_all +0.4 [-1.8, +2.9]
- q8:kvq_int4_rot: {'rescue': 30, 'damage': 22, 'both_succeed': 45, 'both_fail': 142}; t* median 1.0; excluded none
  - act->talk: n 9, {'rescue': 0, 'damage': 0, 'both_succeed': 2, 'both_fail': 7}, G|type +0.0 [+0.0, +0.0], contribution to G_all +0.0 [+0.0, +0.0]
  - talk->act: n 144, {'rescue': 19, 'damage': 17, 'both_succeed': 29, 'both_fail': 79}, G|type +1.4 [-11.7, +15.3], contribution to G_all +0.8 [-6.9, +8.5]
  - tool_name: n 54, {'rescue': 6, 'damage': 4, 'both_succeed': 10, 'both_fail': 34}, G|type +3.7 [-13.6, +24.0], contribution to G_all +0.8 [-3.0, +5.2]
  - tool_args: n 25, {'rescue': 2, 'damage': 1, 'both_succeed': 3, 'both_fail': 19}, G|type +4.0 [-17.9, +28.6], contribution to G_all +0.4 [-1.8, +3.0]
  - other: n 7, {'rescue': 3, 'damage': 0, 'both_succeed': 1, 'both_fail': 3}, G|type +42.9 [+0.0, +100.0], contribution to G_all +1.2 [+0.0, +3.9]
