**TL;DR** Four core W4 G-H contrasts (fixed task pool, t over blocks), Holm-adjusted over the family of 4: q4:gptq_w4_d1 -3.6 pp, p_holm 0.069; q4:awq_w4 -1.3 pp, p_holm 0.199; q8:gptq_w4_d1 +2.9 pp, p_holm 0.013; q8:awq_w4 +3.4 pp, p_holm 0.012. Crossed (new-task) intervals cover 0 in all four. Exploratory label stays.

# G-H multiplicity (W96)

Source: `analysis/fork/out/ghf_20261001T211519Z.json`; script `analysis/fork/ghf_multiplicity.py`.

| cell | G-H (pp) | fixed-pool boot 95% | t 95% | p (t, 2-sided) | p Holm (m=4) | Bonferroni 98.75% (t) | crossed 95% |
|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 | -3.6 | [-6.6, -0.6] | [-6.9, -0.3] | 0.0343 | 0.0686 | [-8.0, +0.8] | [-11.2, +3.6] |
| q4:awq_w4 | -1.3 | [-3.0, +0.6] | [-3.2, +0.7] | 0.1993 | 0.1993 | [-3.8, +1.3] | [-7.7, +5.1] |
| q8:gptq_w4_d1 | +2.9 | [+1.3, +4.7] | [+1.0, +4.8] | 0.0043 | 0.0129 | [+0.4, +5.4] | [-3.2, +9.3] |
| q8:awq_w4 | +3.4 | [+1.5, +5.2] | [+1.3, +5.5] | 0.0030 | 0.0119 | [+0.6, +6.1] | [-1.6, +8.6] |
