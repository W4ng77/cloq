**TL;DR** Fork-aligned Q - BF16 success (d1 checkpoints, fork tasks x 20 nonce blocks, crossed task x block bootstrap, joint across models). Snapshot 20260930T2115Z. q4:gptq_w4_d1 +4.2 pp [-2.4, +10.5]; q4:awq_w4 +0.9 pp [-5.8, +7.5]; q8:gptq_w4_d1 -0.2 pp [-7.7, +6.8]; q8:awq_w4 +1.2 pp [-5.3, +7.6]

# Success, fork-aligned (W64, 20260930T213009Z)

Population: the d1 checkpoint of each fork cell on exactly the forks' tasks and nonce blocks. The d1-d4 mixture analysis (`success_ni.py`) is the *population of calibration draws* and is not an equivalence statement about d1.
Full numbers: `analysis/insights/iter_4/out/success_ni_ALIGNED_20260930T213009Z.json`.

| cell / pool | Q - BF16 (pp) | 95% CI | 90% CI | NI / TOST at 3 pp | TOST 5 pp | p | 90% CI, fixed tasks |
|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 (Q 40.0, BF16 35.8; 1700 units) | +4.2 | [-2.4, +10.5] | [-1.3, +9.5] | pass / fail | fail | 0.206 | [+2.2, +6.1] |
| q4:awq_w4 (Q 36.8, BF16 35.8; 1699 units) | +0.9 | [-5.8, +7.5] | [-4.5, +6.5] | fail / fail | fail | 0.779 | [-1.1, +2.9] |
| q8:gptq_w4_d1 (Q 30.1, BF16 30.4; 1700 units) | -0.2 | [-7.7, +6.8] | [-6.4, +5.5] | fail / fail | fail | 0.950 | [-1.6, +1.0] |
| q8:awq_w4 (Q 31.5, BF16 30.4; 1700 units) | +1.2 | [-5.3, +7.6] | [-4.3, +6.5] | fail / fail | fail | 0.754 | [-0.3, +2.8] |
| pool: q4 (GPTQ, AWQ) | +2.6 | [-3.4, +8.4] | [-2.4, +7.5] | pass / fail | fail | 0.392 | [+0.7, +4.4] |
| pool: q8 (GPTQ, AWQ) | +0.5 | [-5.5, +6.2] | [-4.7, +5.3] | fail / fail | fail | 0.899 | [-0.8, +1.7] |
| pool: GPTQ-W4 d1 (q4, q8) | +2.0 | [-3.0, +6.7] | [-2.2, +5.9] | pass / fail | fail | 0.424 | [+0.7, +3.2] |
| pool: AWQ-W4 d1 (q4, q8) | +1.1 | [-3.5, +5.9] | [-2.7, +4.8] | pass / fail | pass | 0.668 | [-0.3, +2.3] |
| pool: all four | +1.5 | [-2.7, +5.6] | [-2.0, +5.0] | pass / fail | fail | 0.479 | [+0.3, +2.6] |
