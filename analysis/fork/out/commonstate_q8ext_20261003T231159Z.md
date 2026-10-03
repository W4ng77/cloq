**TL;DR** q8, k = 6 of 6 blocks (commonstate-v1 + A1 + D2), 510 common states. Confirmatory two-look (Pocock) reading: K(d1) = +1.0 pp (t97 [-4.2, +6.2], boot97 [-1.4, +3.5]): not resolved; K(BF16) = +0.8 pp (t97 [-2.2, +3.8], boot97 [-2.0, +3.7]): not resolved. Unadjusted (frozen levels): K(d1) (t95 [-3.5, +5.4], boot95 [-1.2, +3.1]): not resolved; K(BF16) (t95 [-1.8, +3.3], boot95 [-1.8, +3.3]): equivalent within ±3 pp (TOST). First look (k = 3, W100b): K(d1) -0.4 pp, not resolved; K(BF16) +2.4 pp, not resolved. Sensitivity without the 26 D2.1 states (n = 484): K(d1) +0.5 pp, not resolved; K(BF16) +0.8 pp, not resolved.

# Common-state action sources on q8, k = 6 of 6 blocks (commonstate-v1 + A1 + D2) — 2026-10-03T23:11:59Z

Protocol `docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md` sha256 `288fc65a20cd3aa0830c81d099457b1a0b5550aeb379108750adabd90a92478a` (verified). Analysis set: blocks ['f01', 'f02', 'f03', 'f04', 'f05', 'f06'] (k = 6), 510 states, 85 tasks. Intervals: t over block means (df = k − 1) and task-cluster bootstrap (B = 2000, seed 20261002); margin ±3 pp.

## V(source, continuation) (success, %)

| source \ continuation | BF16 | d1 (GPTQ-W4 d1) |
|---|---|---|
| bf16 | 30.6 (t95 [+28.7, +32.5]) | 30.0 (t95 [+23.9, +36.1]) |
| d1 | 29.0 (t95 [+27.0, +31.0]) | 28.8 (t95 [+23.6, +34.0]) |
| d2 | 29.8 (t95 [+28.1, +31.5]) | 29.0 (t95 [+24.1, +33.9]) |

## Key estimand K(c) = Δ_{BF16−d1}(c) − Δ_{d2−d1}(c) = Δ_{BF16−d2}(c) (pp): unadjusted, frozen levels (D2.2)

| c | K | t95 | boot95 | t90 | boot90 | boot p (Holm) | reading |
|---|---|---|---|---|---|---|---|
| bf16 | +0.8 | [-1.8, +3.3] | [-1.8, +3.3] | [-1.2, +2.8] | [-1.4, +2.9] | 0.603 (0.792) | equivalent within ±3 pp (TOST) |
| d1 | +1.0 | [-3.5, +5.4] | [-1.2, +3.1] | [-2.5, +4.5] | [-0.8, +2.7] | 0.396 (0.792) | not resolved |
| average (secondary) | +0.9 | [-2.0, +3.8] | [-1.0, +2.9] | [-1.4, +3.2] | [-0.7, +2.5] | 0.379 | not resolved |

## Two-look reading, confirmatory (A1.3 + D2.2, Pocock: difference two-sided 0.0294, TOST one-sided 0.0304 per side)

Levels derived for looks at 3 and 6 blocks (correlation √(1/2)); at k = 6 the correlation is √(3/k) ≥ √(1/2), so the same levels are conservative (D2.3).

| c | K | t97 | boot97 | t94 | boot94 | Holm p | reading |
|---|---|---|---|---|---|---|---|
| bf16 | +0.8 | [-2.2, +3.8] | [-2.0, +3.7] | [-1.6, +3.2] | [-1.6, +3.3] | 0.792 | not resolved |
| d1 | +1.0 | [-4.2, +6.2] | [-1.4, +3.5] | [-3.2, +5.2] | [-1.0, +3.1] | 0.792 | not resolved |

First look (k = 3, W100b, `analysis/fork/out/commonstate_20261002T201612Z.json`, unchanged): K[d1] -0.4 pp (t95 [-9.3, +8.5], boot95 [-3.5, +2.7]): not resolved; K[bf16] +2.4 pp (t95 [-3.5, +8.2], boot95 [-0.8, +5.5]): not resolved


## Sensitivity without the D2.1 states (prespecified; 26 of 26 listed states were in the analysis set, n = 484, k = 6)

| c | K | t95 | boot95 | t97 | boot97 | reading (frozen) | reading (two-look) |
|---|---|---|---|---|---|---|---|
| bf16 | +0.8 | [-1.9, +3.5] | [-1.9, +3.5] | [-2.4, +4.0] | [-2.1, +3.9] | not resolved | not resolved |
| d1 | +0.5 | [-4.0, +4.9] | [-1.6, +2.7] | [-4.7, +5.7] | [-1.8, +2.9] | not resolved | not resolved |

## Contrasts Δ, rescue r, damage d, turnover M (pp)

| contrast | c | Δ | Δ t95 | Δ boot95 | r | d | M | reading (descriptive) |
|---|---|---|---|---|---|---|---|---|
| bf16 − d1 | bf16 | +1.6 | [-0.6, +3.7] | [-1.6, +4.9] | 5.3 | 3.7 | 9.0 | not resolved |
| bf16 − d1 | d1 | +1.2 | [-1.3, +3.6] | [-1.4, +3.7] | 4.1 | 2.9 | 7.1 | not resolved |
| bf16 − d2 | bf16 | +0.8 | [-1.8, +3.3] | [-1.8, +3.3] | 3.3 | 2.5 | 5.9 | equivalent within ±3 pp (TOST) |
| bf16 − d2 | d1 | +1.0 | [-3.5, +5.4] | [-1.2, +3.1] | 3.9 | 2.9 | 6.9 | not resolved |
| d2 − d1 | bf16 | +0.8 | [-1.1, +2.6] | [-2.2, +3.5] | 4.7 | 3.9 | 8.6 | not resolved |
| d2 − d1 | d1 | +0.2 | [-2.3, +2.7] | [-2.4, +2.5] | 4.1 | 3.9 | 8.0 | equivalent within ±3 pp (TOST) |

## Interaction with the continuation I = Δ(c = BF16) − Δ(c = d1) (pp; secondary reading)

| contrast | I | t95 | boot95 | t90 | boot90 | reading |
|---|---|---|---|---|---|---|
| bf16 − d1 | +0.4 | [-2.8, +3.6] | [-2.5, +3.5] | [-2.1, +2.9] | [-2.0, +2.9] | equivalent within ±3 pp (TOST) |
| bf16 − d2 | -0.2 | [-4.5, +4.1] | [-2.7, +2.4] | [-3.6, +3.2] | [-2.4, +2.2] | not resolved |
| d2 − d1 | +0.6 | [-2.4, +3.6] | [-2.5, +3.7] | [-1.8, +2.9] | [-2.2, +3.3] | not resolved |

## Action agreement among the three sources

Exact canonical agreement: BF16 = d1 55.7%, BF16 = d2 57.3%, d1 = d2 53.9% (n = 510).

| pattern | n |
|---|---|
| all equal | 251 |
| all different | 161 |
| BF16 = d2 != d1 | 41 |
| BF16 = d1 != d2 | 33 |
| d1 = d2 != BF16 | 24 |

Comparator categories: bf16_d1: {'class:talk->act': 30, 'tool_name': 25, 'text_only': 145, 'same': 284, 'tool_args': 18, 'class:act->talk': 8}; bf16_d2: {'class:act->talk': 18, 'same': 292, 'text_only': 151, 'tool_args': 20, 'tool_name': 25, 'class:talk->act': 4}; d1_d2: {'text_only': 156, 'tool_name': 31, 'same': 275, 'tool_args': 16, 'class:talk->act': 20, 'class:act->talk': 12}

Descriptive (labelled exploratory): on the 218 states where a_d2 ≠ a_BF16, K(d1) = +2.3 pp, K(BF16) = +1.8 pp (point estimates, unit means).

## Per block

| block | n | V[bf16,bf16] | V[bf16,d1] | V[d1,bf16] | V[d1,d1] | V[d2,bf16] | V[d2,d1] | K[d1] | K[bf16] |
|---|---|---|---|---|---|---|---|---|---|
| f01 | 85 | 29.4 | 21.2 | 27.1 | 23.5 | 29.4 | 24.7 | -3.5 | +0.0 |
| f02 | 85 | 32.9 | 31.8 | 31.8 | 31.8 | 30.6 | 32.9 | -1.2 | +2.4 |
| f03 | 85 | 31.8 | 31.8 | 27.1 | 28.2 | 27.1 | 28.2 | +3.5 | +4.7 |
| f04 | 85 | 29.4 | 27.1 | 30.6 | 23.5 | 29.4 | 22.4 | +4.7 | +0.0 |
| f05 | 85 | 31.8 | 38.8 | 29.4 | 36.5 | 31.8 | 32.9 | +5.9 | +0.0 |
| f06 | 85 | 28.2 | 29.4 | 28.2 | 29.4 | 30.6 | 32.9 | -3.5 | -2.4 |

## Acceptance

Gate: {"d2_bf16": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 12, "n_ok": 12, "ref_rerun": [12, 12], "n_implicit": 4, "idcheck": {"idcheck_Q": [16, 16], "idcheck_B": [16, 16]}, "canary": {"ok": true, "canary": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "want": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "ckpt_sha256": {"B": null, "Q": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e"}, "host": "node001"}}, "d2_d1": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 12, "n_ok": 12, "ref_rerun": [12, 12], "n_implicit": 5, "idcheck": {"idcheck_B": [16, 16], "idcheck_Q": [16, 16]}, "canary": {"ok": true, "canary": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "want": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "ckpt_sha256": {"B": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e", "Q": "6ee628e67194f0c073cb8efe917eaa083fe53281f507a48b1d6146f636e10d70"}, "host": "node007"}}}

- f01: {"n_ref": 85, "finished_by_freeze": {"cs_q8_d2_bf16_f01": true, "cs_q8_d2_d1_f01": true}, "d2_bf16": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [22, 22], "n_implicit": 55, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "want": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "ckpt_sha256": {"B": null, "Q": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e"}, "host": "node001"}, "manifest_sha_ok": true}, "d2_d1": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [19, 19], "n_implicit": 53, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "want": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "ckpt_sha256": {"B": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e", "Q": "6ee628e67194f0c073cb8efe917eaa083fe53281f507a48b1d6146f636e10d70"}, "host": "node005"}, "manifest_sha_ok": true}, "quarantined_by": [], "n_admitted": 85, "complete": true}
- f02: {"n_ref": 85, "finished_by_freeze": {"cs_q8_d2_bf16_f02": true, "cs_q8_d2_d1_f02": true}, "d2_bf16": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [15, 15], "n_implicit": 48, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "want": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "ckpt_sha256": {"B": null, "Q": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e"}, "host": "node004"}, "manifest_sha_ok": true}, "d2_d1": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [18, 18], "n_implicit": 48, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "want": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "ckpt_sha256": {"B": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e", "Q": "6ee628e67194f0c073cb8efe917eaa083fe53281f507a48b1d6146f636e10d70"}, "host": "node005"}, "manifest_sha_ok": true}, "quarantined_by": [], "n_admitted": 85, "complete": true}
- f03: {"n_ref": 85, "finished_by_freeze": {"cs_q8_d2_bf16_f03": true, "cs_q8_d2_d1_f03": true}, "d2_bf16": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [23, 23], "n_implicit": 42, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "want": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "ckpt_sha256": {"B": null, "Q": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e"}, "host": "node008"}, "manifest_sha_ok": true}, "d2_d1": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [19, 19], "n_implicit": 41, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "want": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "ckpt_sha256": {"B": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e", "Q": "6ee628e67194f0c073cb8efe917eaa083fe53281f507a48b1d6146f636e10d70"}, "host": "node004"}, "manifest_sha_ok": true}, "quarantined_by": [], "n_admitted": 85, "complete": true}
- f04: {"n_ref": 85, "reference": {"ok": true, "task": "cs_ref_q8_gptq_w4_d1_f04", "n_rows": 85, "n_ok": 85, "n_errors": 0, "n_missing": 0, "noop": {"n": 14, "n_pass": 14}, "canary": {"ok": true, "canary": {"B": "e340c7991fa5bc08", "Q": "a9f812fb17241b72"}, "want": {"B": "e340c7991fa5bc08", "Q": "a9f812fb17241b72"}, "ckpt_sha256": {"B": null, "Q": "6ee628e67194f0c073cb8efe917eaa083fe53281f507a48b1d6146f636e10d70"}, "host": "node007"}}, "finished_by_freeze": {"cs_q8_d2_bf16_f04": true, "cs_q8_d2_d1_f04": true, "cs_ref_q8_gptq_w4_d1_f04": true}, "nmp_crosscheck": null, "d2_bf16": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [13, 13], "n_implicit": 47, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "want": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "ckpt_sha256": {"B": null, "Q": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e"}, "host": "node007"}, "manifest_sha_ok": true}, "d2_d1": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [19, 19], "n_implicit": 47, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "want": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "ckpt_sha256": {"B": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e", "Q": "6ee628e67194f0c073cb8efe917eaa083fe53281f507a48b1d6146f636e10d70"}, "host": "node007"}, "manifest_sha_ok": true}, "quarantined_by": [], "n_admitted": 85, "complete": true}
- f05: {"n_ref": 85, "reference": {"ok": true, "task": "cs_ref_q8_gptq_w4_d1_f05", "n_rows": 85, "n_ok": 85, "n_errors": 0, "n_missing": 0, "noop": {"n": 10, "n_pass": 10}, "canary": {"ok": true, "canary": {"B": "e340c7991fa5bc08", "Q": "a9f812fb17241b72"}, "want": {"B": "e340c7991fa5bc08", "Q": "a9f812fb17241b72"}, "ckpt_sha256": {"B": null, "Q": "6ee628e67194f0c073cb8efe917eaa083fe53281f507a48b1d6146f636e10d70"}, "host": "node007"}}, "finished_by_freeze": {"cs_q8_d2_bf16_f05": true, "cs_q8_d2_d1_f05": true, "cs_ref_q8_gptq_w4_d1_f05": true}, "nmp_crosscheck": null, "d2_bf16": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [11, 11], "n_implicit": 52, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "want": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "ckpt_sha256": {"B": null, "Q": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e"}, "host": "node007"}, "manifest_sha_ok": true}, "d2_d1": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [21, 21], "n_implicit": 44, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "want": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "ckpt_sha256": {"B": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e", "Q": "6ee628e67194f0c073cb8efe917eaa083fe53281f507a48b1d6146f636e10d70"}, "host": "node001"}, "manifest_sha_ok": true}, "quarantined_by": [], "n_admitted": 85, "complete": true}
- f06: {"n_ref": 85, "reference": {"ok": true, "task": "cs_ref_q8_gptq_w4_d1_f06", "n_rows": 85, "n_ok": 85, "n_errors": 0, "n_missing": 0, "noop": {"n": 9, "n_pass": 9}, "canary": {"ok": true, "canary": {"B": "e340c7991fa5bc08", "Q": "a9f812fb17241b72"}, "want": {"B": "e340c7991fa5bc08", "Q": "a9f812fb17241b72"}, "ckpt_sha256": {"B": null, "Q": "6ee628e67194f0c073cb8efe917eaa083fe53281f507a48b1d6146f636e10d70"}, "host": "node007"}}, "finished_by_freeze": {"cs_q8_d2_bf16_f06": true, "cs_q8_d2_d1_f06": true, "cs_ref_q8_gptq_w4_d1_f06": true}, "nmp_crosscheck": null, "d2_bf16": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [18, 18], "n_implicit": 48, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "want": {"B": "e340c7991fa5bc08", "Q": "15e5098c08c412da"}, "ckpt_sha256": {"B": null, "Q": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e"}, "host": "node007"}, "manifest_sha_ok": true}, "d2_d1": {"verdict": {"idcheck": true, "rows_complete": true, "ref_rerun": true, "identity": true, "budget": true, "pass": true}, "n_rows": 85, "n_ok": 85, "n_missing": 0, "n_errors": 0, "ref_rerun": [16, 16], "n_implicit": 42, "n_identity_fail": 0, "canary": {"ok": true, "canary": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "want": {"B": "15e5098c08c412da", "Q": "a9f812fb17241b72"}, "ckpt_sha256": {"B": "320409ad7d28102cd4b78c32c5233f76a03b65cb6cb137c1309eee5fddfd873e", "Q": "6ee628e67194f0c073cb8efe917eaa083fe53281f507a48b1d6146f636e10d70"}, "host": "node001"}, "manifest_sha_ok": true}, "quarantined_by": [], "n_admitted": 85, "complete": true}

Excluded units: 0 []

Inputs (sha256): {
"manifests/fork/commonstate_v1.json": "649d34166c41cfb7d928db62f10c164a24663e71295cc984d086e0aeedc25ff4",
"docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md": "288fc65a20cd3aa0830c81d099457b1a0b5550aeb379108750adabd90a92478a",
"manifests/fork/commonstate_q8ext_v1.json": "2a5b61c743e76414b1b3c455fe720ae8552ed14bbd6954386bf95ef45928fd34",
"manifests/fork/commonstate_d2_v1.json": "88b228b0838125537610b85985ffa21da768594a13dc6a705f8b33159c5a9af2",
"analysis/fork/commonstate/q8/gate/d2_bf16/cs_summary.json": "5fd4696cdcb34315dd4b8b05e8cc1b856a93ce802d6025f57c61f169f80cffca",
"analysis/fork/commonstate/q8/gate/d2_d1/cs_summary.json": "3f6bbfda36cc617e2d7026e44bca3592eb3f62082707e1bac144cc356c23a4a0",
"analysis/fork/bank_u/q8_gptq_w4_d1/f01/bank_rows.jsonl": "a8433f8b800f9820f20cddddd9fd998a76c4a734c16aafa71133dd55af4a7b49",
"analysis/fork/commonstate/q8/panel/d2_bf16/f01/cs_rows.jsonl": "2df8c3670627ed343dc3c8931c08c1243aafdac586eb2d136c0d78cca460b646",
"analysis/fork/commonstate/q8/panel/d2_bf16/f01/cs_summary.json": "f767931390ea1abeca325c1cdd4b0a3c938d532df7ce568a94c7f37f67a397b5",
"analysis/fork/commonstate/q8/panel/d2_d1/f01/cs_rows.jsonl": "4b8bba023b67c579689c8fef1d98b41ea57438d03b924f511f8cd79ec690603b",
"analysis/fork/commonstate/q8/panel/d2_d1/f01/cs_summary.json": "066d65cbc1446bce54ee6764845ca3222a433508dca6352b48437e48cf77a692",
"analysis/fork/bank_u/q8_gptq_w4_d1/f02/bank_rows.jsonl": "444d6ae5639c7439a637bb565d070f371bbf51f7f0164a5896d8892740d4b27a",
"analysis/fork/commonstate/q8/panel/d2_bf16/f02/cs_rows.jsonl": "b49aed7f3ebb271798d6eea21540284c3c6823778b5c9eb4698609d509f76778",
"analysis/fork/commonstate/q8/panel/d2_bf16/f02/cs_summary.json": "f33a14be53c34b8c4c20250ffa085efd0ff0907bfca60a60ad3d8d3015561525",
"analysis/fork/commonstate/q8/panel/d2_d1/f02/cs_rows.jsonl": "f8c40b3d2730ed319fdedb3d891bef35b2d76bf5d8dbf6569867b2d4c3733614",
"analysis/fork/commonstate/q8/panel/d2_d1/f02/cs_summary.json": "bb96d212bae03a6d5c0fe56424bed9c3fc009cc0e9008742c31d49f23a601017",
"analysis/fork/bank_u/q8_gptq_w4_d1/f03/bank_rows.jsonl": "4d2aa5dd06ee50e18fc53633619759010e33c3a3e221bf62a78eecf3758161b3",
"analysis/fork/commonstate/q8/panel/d2_bf16/f03/cs_rows.jsonl": "a86e9011e5def973b4448d193c2777f58aba059bcfefb8626651b309c7aee3ff",
"analysis/fork/commonstate/q8/panel/d2_bf16/f03/cs_summary.json": "a685aeba93fd5838af21d499500d11f988fdb7a2cc259b9a87523a5bfdc3e49b",
"analysis/fork/commonstate/q8/panel/d2_d1/f03/cs_rows.jsonl": "70fcea70950f32136bf5d049568e65fbb7e4b55594f35d19ac71fae9a5c0f3e3",
"analysis/fork/commonstate/q8/panel/d2_d1/f03/cs_summary.json": "654fff901494e2fc281279f4726d2befe8d771c91a7931c32ef70a1b3062a407",
"analysis/fork/commonstate/q8/ref_d1/f04/bank_rows.jsonl": "16e3e6bd446f8a7077e0df5fe845d99d86c54db72401ec4bf3b75067b668d817",
"analysis/fork/commonstate/q8/panel/d2_bf16/f04/cs_rows.jsonl": "8f7a16e11d70417429e9961eeefaa49c989f1fec37440b58a76c7febe744d029",
"analysis/fork/commonstate/q8/panel/d2_bf16/f04/cs_summary.json": "d3d61740c909a09b0b3adaab9c7e6102ce7538a8b5318cf40ed3acf259d24a1f",
"analysis/fork/commonstate/q8/panel/d2_d1/f04/cs_rows.jsonl": "ec0ef93a2cdcef321e9f15279dc479b2589be5e5a2f3f03264df7f92aa1ddebd",
"analysis/fork/commonstate/q8/panel/d2_d1/f04/cs_summary.json": "a27fa196742d49eccb38857d020e1293d25b7d50bc43924559d21ee4126811d7",
"analysis/fork/commonstate/q8/ref_d1/f05/bank_rows.jsonl": "baaa83d4812f0a3eafd1a63a5f7872381d97fc8f514070cf45d9d0908283082d",
"analysis/fork/commonstate/q8/panel/d2_bf16/f05/cs_rows.jsonl": "39932881b1e8edf36af7f77a0089041b1756b7e4ec2e46ef78394a29fc9869d4",
"analysis/fork/commonstate/q8/panel/d2_bf16/f05/cs_summary.json": "e411233e3bf8c61c875e38dda0fb80224b56e6dbda1319fbd1bd9939ce00510e",
"analysis/fork/commonstate/q8/panel/d2_d1/f05/cs_rows.jsonl": "56cf0a56fdfd4d806bd78e8ed0bdcc1da44d5a0a24e941a454af5854533678a8",
"analysis/fork/commonstate/q8/panel/d2_d1/f05/cs_summary.json": "29861cc199652f15a463531b44380fce88f432d5e1b7812b616139f06cde580e",
"analysis/fork/commonstate/q8/ref_d1/f06/bank_rows.jsonl": "84f03d445816b1afb57774cf54241d9eb6e9d22f48a94eb194af3e5235b60500",
"analysis/fork/commonstate/q8/panel/d2_bf16/f06/cs_rows.jsonl": "fabea53228b518a7f79c73f2ddf2b99e58f235be93f00336bd39908018b7826b",
"analysis/fork/commonstate/q8/panel/d2_bf16/f06/cs_summary.json": "3e475ec38f0c8818cf8047cda82adfebbe85d7c5a9a070e65073734eb5616330",
"analysis/fork/commonstate/q8/panel/d2_d1/f06/cs_rows.jsonl": "99b50f36b8523b606856ee5a4a8df9614918205148e23ec031036c3068f60d88",
"analysis/fork/commonstate/q8/panel/d2_d1/f06/cs_summary.json": "c5630a53f2a1af2cf51d72449a71984617a64831060c08581e5d05f9e58c821a",
"analysis/fork/out/commonstate_20261002T201612Z.json": "3dbe19a5df63847ad150c1a1ab5dc7e853713b25a958731391569937b902f909"
}
