# Upgrade-label transfer matrix (20261005T185537Z)

**EXPLORATORY, POST HOC (data already seen). Hindsight label-mismatch diagnostic, not a deployable router.**

Protocol `docs/insights/LABEL_TRANSFER_POSTHOC.md`. Script `analysis/fork/label_transfer.py` sha256 6a4f26e2bfa13a919a671606e51e6e1144b1c8de4c489e09a23f77dfc3c3a0d1; git HEAD 224c6cea37850f6aa673f49d9689a66bbc152bad; B = 2000; seed 20261001. Full numbers: `analysis/fork/out/label_transfer_20261005T185537Z.json`.
Values in pp of all states in the frame (rescue r, damage d, net = r - d of the EXECUTED mode). loss = oracle_Y - executed. Intervals 95% percentile; which scheme is shown is stated per table.
Same-draw selection is hindsight (labels and outcomes share the QQ arm). The split-half variant is a same-task replication across blocks, not new-task prediction. Budgets count states, not BF16 compute.
Same-draw losses are >= 0 by construction (the oracle maximises the weighted sum in every draw), so a same-draw loss interval excluding 0 is not evidence. Read 'over random' (executed minus random selection at the same capacity; can be negative) and 'retained' = (executed - random) / (oracle - random). Only the split-half loss can be negative.
Saturation: an oracle whose label has fewer +1 states than the capacity in every pooled cell adds only tie-fill at higher budgets; such oracles are listed per table. Point estimates are pooled unit sums (equal to analyze_dev's mean of block means only when blocks have equal state counts, as in Bank U).

## Frame counts

| frame | cell | four-arm states | units | tasks | blocks | G+/G- | H+/H- | F+/F- |
|---|---|---|---|---|---|---|---|---|
| U1 | q4:awq_w4 | 255 | 255 | 85 | f01,f02,f03 (3) | 7/14 | 21/13 | 20/20 |
| U1 | q4:gptq_w4_d1 | 255 | 255 | 85 | f01,f02,f03 (3) | 11/12 | 12/21 | 12/25 |
| U1 | q4:kvq_int8 | 255 | 255 | 85 | f01,f02,f03 (3) | 4/8 | 18/13 | 20/22 |
| U1 | q8:awq_w4 | 255 | 255 | 85 | f01,f02,f03 (3) | 14/8 | 14/21 | 19/18 |
| U1 | q8:gptq_w4_d1 | 255 | 255 | 85 | f01,f02,f03 (3) | 8/4 | 9/16 | 11/15 |
| U1 | q8:kvq_int8 | 255 | 255 | 85 | f01,f02,f03 (3) | 5/4 | 13/9 | 18/10 |
| U2B | q4:awq_w4 | 255 | 255 | 85 | f01,f02,f03 (3) | 7/13 | 18/16 | 20/24 |
| U2B | q4:gptq_w4_d1 | 255 | 255 | 85 | f01,f02,f03 (3) | 10/11 | 20/15 | 16/21 |
| U2B | q4:kvq_int8 | 255 | 255 | 85 | f01,f02,f03 (3) | 5/5 | 19/12 | 17/17 |
| U2B | q8:awq_w4 | 255 | 255 | 85 | f01,f02,f03 (3) | 15/8 | 21/10 | 27/13 |
| U2B | q8:gptq_w4_d1 | 255 | 255 | 85 | f01,f02,f03 (3) | 9/8 | 20/18 | 24/15 |
| U2B | q8:kvq_int8 | 255 | 255 | 85 | f01,f02,f03 (3) | 6/2 | 17/4 | 20/6 |
| P | q4:gptq_w4_d1 | 1102 | 1700 | 85 | f01,f02,f03... (20) | 116/148 | 96/88 | 111/138 |
| P | q4:awq_w4 | 1439 | 1700 | 85 | f01,f02,f03... (20) | 167/172 | 148/135 | 164/175 |
| P | q4:kvq_int8 | 593 | 1870 | 85 | f01,f02,f03... (22) | 58/64 | 24/39 | 68/75 |
| P | q8:gptq_w4_d1 | 1473 | 1700 | 85 | f01,f02,f03... (20) | 177/128 | 101/95 | 208/128 |
| P | q8:awq_w4 | 1562 | 1700 | 85 | f01,f02,f03... (20) | 194/161 | 153/173 | 192/183 |
| P | q8:kvq_int8 | 855 | 1870 | 85 | f01,f02,f03... (22) | 81/70 | 33/36 | 87/66 |

## Bank U U1 (PRIMARY, ordinary own-trajectory states): pool W4, same-draw (hindsight), budget 5% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +3.80 [+2.06, +4.66] | +4.56 [+2.99, +5.00] | +4.75 [+3.28, +5.00] |
| random (same capacity) | +0.01 [-0.12, +0.15] | -0.07 [-0.23, +0.08] | -0.08 [-0.25, +0.07] |
| G | net +3.80 (r 3.80, d 0.00) | net +1.52 (r 1.58, d 0.06); loss +3.03 [+1.71, +3.76]; over random +1.60 [+0.36, +2.60]; retained +34.49 [+10.66, +58.82]%, lost 67% of oracle | net +2.15 (r 2.22, d 0.06); loss +2.60 [+1.22, +3.61]; over random +2.23 [+0.88, +3.32]; retained +46.21 [+21.14, +71.32]%, lost 55% of oracle |
| H | net +1.41 (r 1.42, d 0.01); loss +2.39 [+1.19, +3.11]; over random +1.40 [+0.37, +2.21]; retained +37.00 [+14.46, +57.74]%, lost 63% of oracle | net +4.56 (r 4.56, d 0.00) | net +3.36 (r 3.37, d 0.00); loss +1.39 [+0.51, +2.18]; over random +3.44 [+2.10, +4.01]; retained +71.21 [+53.02, +87.19]%, lost 29% of oracle |
| F | net +1.80 (r 1.80, d 0.00); loss +2.00 [+0.72, +2.96]; over random +1.79 [+0.70, +2.77]; retained +47.16 [+23.25, +73.63]%, lost 53% of oracle | net +3.13 (r 3.13, d 0.00); loss +1.43 [+0.57, +1.95]; over random +3.20 [+2.08, +3.77]; retained +69.11 [+56.04, +84.18]%, lost 31% of oracle | net +4.75 (r 4.75, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.04 block / 0.08 crossed): G: G>F>H (oracle F>H>G; argmax in oracle top set 0.00 block / 0.04 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.04 block / 0.33 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 1.00 block / 0.71 crossed)
R3 within-row differences: G: H-G -2.27 [-3.08, -1.11], F-G -1.64 [-2.68, -0.60], F-H +0.63 [-0.53, +1.67]; H: H-G +3.15 [+1.83, +3.84], F-G +1.95 [+0.61, +2.89], F-H -1.20 [-1.82, -0.41]; F: H-G +1.33 [-0.23, +2.59], F-G +2.96 [+1.60, +3.86], F-H +1.63 [+0.70, +2.37]

Saturated oracles at 5% (all +1 states fit in every pooled cell): none.


## Bank U U1 (PRIMARY, ordinary own-trajectory states): pool W4, same-draw (hindsight), budget 10% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +3.92 [+2.16, +6.08] | +5.49 [+3.43, +7.55] | +6.08 [+3.73, +8.09] |
| random (same capacity) | +0.02 [-0.24, +0.29] | -0.15 [-0.46, +0.17] | -0.16 [-0.50, +0.15] |
| G | net +3.92 (r 3.92, d 0.00) | net +1.48 (r 1.84, d 0.35); loss +4.01 [+2.48, +5.53]; over random +1.63 [+0.44, +3.10]; retained +28.91 [+10.34, +49.47]%, lost 73% of oracle | net +2.17 (r 2.52, d 0.35); loss +3.91 [+2.17, +5.84]; over random +2.33 [+1.00, +4.16]; retained +37.30 [+18.63, +60.94]%, lost 64% of oracle |
| H | net +1.59 (r 1.69, d 0.11); loss +2.34 [+1.24, +3.69]; over random +1.57 [+0.44, +2.99]; retained +40.15 [+15.08, +62.24]%, lost 60% of oracle | net +5.49 (r 5.49, d 0.00) | net +4.15 (r 4.22, d 0.08); loss +1.93 [+0.85, +3.04]; over random +4.30 [+2.66, +6.02]; retained +69.00 [+55.13, +84.03]%, lost 32% of oracle |
| F | net +2.28 (r 2.34, d 0.06); loss +1.64 [+0.68, +3.17]; over random +2.26 [+0.94, +3.85]; retained +57.87 [+29.54, +79.26]%, lost 42% of oracle | net +4.13 (r 4.18, d 0.05); loss +1.36 [+0.55, +2.36]; over random +4.28 [+2.60, +5.80]; retained +75.87 [+60.00, +88.28]%, lost 25% of oracle | net +6.08 (r 6.08, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.04 crossed): G: G>F>H (oracle F>H>G; argmax in oracle top set 0.00 block / 0.01 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.00 block / 0.25 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 1.00 block / 0.78 crossed)
R3 within-row differences: G: H-G -2.44 [-3.85, -1.30], F-G -1.75 [-3.23, -0.71], F-H +0.69 [-0.49, +1.95]; H: H-G +3.90 [+2.29, +5.54], F-G +2.56 [+1.02, +4.08], F-H -1.34 [-2.35, -0.45]; F: H-G +1.85 [+0.03, +3.79], F-G +3.80 [+2.00, +5.82], F-H +1.95 [+0.84, +3.20]

Saturated oracles at 10% (all +1 states fit in every pooled cell): G, H, F.


## Bank U U1 (PRIMARY, ordinary own-trajectory states): pool W4, same-draw (hindsight), budget 20% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +3.92 [+2.16, +6.18] | +5.49 [+3.43, +8.04] | +6.08 [+3.82, +8.82] |
| random (same capacity) | +0.04 [-0.47, +0.59] | -0.29 [-0.92, +0.33] | -0.31 [-1.00, +0.29] |
| G | net +3.92 (r 3.92, d 0.00) | net +1.30 (r 2.26, d 0.96); loss +4.19 [+2.77, +5.85]; over random +1.60 [+0.52, +2.99]; retained +27.62 [+10.97, +45.28]%, lost 76% of oracle | net +2.00 (r 2.93, d 0.93); loss +4.08 [+2.49, +6.29]; over random +2.31 [+1.12, +4.04]; retained +36.17 [+18.96, +55.61]%, lost 67% of oracle |
| H | net +1.59 (r 1.96, d 0.38); loss +2.34 [+1.32, +3.58]; over random +1.55 [+0.50, +2.93]; retained +39.84 [+16.69, +61.38]%, lost 60% of oracle | net +5.49 (r 5.49, d 0.00) | net +4.14 (r 4.45, d 0.30); loss +1.93 [+1.03, +3.04]; over random +4.46 [+2.92, +6.38]; retained +69.74 [+57.22, +81.83]%, lost 32% of oracle |
| F | net +2.30 (r 2.53, d 0.23); loss +1.62 [+0.72, +2.86]; over random +2.26 [+1.08, +3.95]; retained +58.19 [+33.68, +79.65]%, lost 41% of oracle | net +4.14 (r 4.34, d 0.20); loss +1.35 [+0.56, +2.25]; over random +4.43 [+2.87, +6.35]; retained +76.67 [+62.00, +89.07]%, lost 25% of oracle | net +6.08 (r 6.08, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.05 crossed): G: G>F>H (oracle F>H>G; argmax in oracle top set 0.00 block / 0.01 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.00 block / 0.24 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 1.00 block / 0.80 crossed)
R3 within-row differences: G: H-G -2.62 [-4.19, -1.33], F-G -1.92 [-3.46, -0.81], F-H +0.70 [-0.45, +1.99]; H: H-G +3.90 [+2.26, +5.73], F-G +2.56 [+1.03, +4.27], F-H -1.35 [-2.43, -0.42]; F: H-G +1.84 [+0.00, +3.99], F-G +3.78 [+1.99, +6.14], F-H +1.94 [+0.83, +3.26]

Saturated oracles at 20% (all +1 states fit in every pooled cell): G, H, F.


## Bank U U1 (PRIMARY, ordinary own-trajectory states): pool KV8, same-draw (hindsight), budget 5% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +1.76 [+0.20, +3.68] | +5.00 [+2.75, +5.00] | +5.00 [+3.09, +5.00] |
| random (same capacity) | -0.03 [-0.16, +0.11] | +0.09 [-0.15, +0.30] | +0.06 [-0.18, +0.29] |
| G | net +1.76 (r 1.76, d 0.00) | net +0.08 (r 0.21, d 0.13); loss +4.92 [+2.73, +4.98]; over random -0.01 [-0.12, +0.11]; retained -0.18 [-2.62, +3.14]%, lost 98% of oracle | net +0.85 (r 1.01, d 0.16); loss +4.15 [+2.31, +4.86]; over random +0.79 [+0.05, +1.97]; retained +16.00 [+0.95, +45.83]%, lost 83% of oracle |
| H | net +0.00 (r 0.00, d 0.00); loss +1.76 [+0.20, +3.67]; over random +0.03 [-0.09, +0.15]; retained +1.64 [-3.19, +31.05]%, lost 100% of oracle | net +5.00 (r 5.00, d 0.00) | net +4.72 (r 4.72, d 0.00); loss +0.28 [+0.00, +1.54]; over random +4.66 [+2.51, +4.92]; retained +94.38 [+66.46, +100.00]%, lost 6% of oracle |
| F | net +0.54 (r 0.54, d 0.00); loss +1.22 [+0.06, +2.77]; over random +0.57 [+0.05, +1.16]; retained +31.83 [+4.64, +80.86]%, lost 69% of oracle | net +3.81 (r 3.81, d 0.00); loss +1.19 [+0.00, +1.64]; over random +3.72 [+2.20, +4.52]; retained +75.68 [+64.55, +99.97]%, lost 24% of oracle | net +5.00 (r 5.00, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point True, draws 0.68 block / 0.46 crossed): G: G>F>H (oracle H=F>G; argmax in oracle top set 0.00 block / 0.07 crossed); H: H>F>G (oracle H=F>G; argmax in oracle top set 0.68 block / 0.60 crossed); F: F>H>G (oracle H=F>G; argmax in oracle top set 1.00 block / 0.96 crossed)
R3 within-row differences: G: H-G -1.69 [-3.62, -0.06], F-G -0.92 [-2.33, +0.14], F-H +0.77 [-0.10, +2.15]; H: H-G +5.00 [+2.73, +5.00], F-G +4.72 [+2.44, +5.00], F-H -0.28 [-0.84, +0.03]; F: H-G +3.26 [+1.32, +4.62], F-G +4.46 [+2.69, +5.00], F-H +1.19 [+0.20, +2.09]

Saturated oracles at 5% (all +1 states fit in every pooled cell): G.


## Bank U U1 (PRIMARY, ordinary own-trajectory states): pool KV8, same-draw (hindsight), budget 10% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +1.76 [+0.20, +3.73] | +6.08 [+2.94, +8.63] | +7.45 [+4.12, +9.90] |
| random (same capacity) | -0.06 [-0.31, +0.22] | +0.18 [-0.29, +0.61] | +0.12 [-0.35, +0.59] |
| G | net +1.76 (r 1.76, d 0.00) | net +0.20 (r 0.52, d 0.32); loss +5.88 [+3.09, +8.17]; over random +0.03 [-0.10, +0.18]; retained +0.43 [-1.61, +4.24]%, lost 97% of oracle | net +0.95 (r 1.36, d 0.41); loss +6.50 [+3.70, +8.28]; over random +0.83 [+0.10, +1.94]; retained +11.37 [+1.51, +29.33]%, lost 87% of oracle |
| H | net +0.01 (r 0.08, d 0.07); loss +1.75 [+0.25, +3.65]; over random +0.07 [-0.11, +0.29]; retained +3.88 [-4.04, +40.69]%, lost 99% of oracle | net +6.08 (r 6.08, d 0.00) | net +5.69 (r 5.77, d 0.08); loss +1.77 [+0.29, +3.07]; over random +5.57 [+2.94, +7.78]; retained +75.92 [+55.47, +95.71]%, lost 24% of oracle |
| F | net +0.79 (r 0.81, d 0.02); loss +0.98 [+0.04, +2.37]; over random +0.85 [+0.10, +1.86]; retained +46.44 [+8.43, +95.11]%, lost 55% of oracle | net +5.69 (r 5.70, d 0.01); loss +0.39 [+0.00, +1.50]; over random +5.51 [+2.88, +7.37]; retained +93.42 [+75.30, +100.00]%, lost 6% of oracle | net +7.45 (r 7.45, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.03 block / 0.07 crossed): G: G>F>H (oracle F>H>G; argmax in oracle top set 0.00 block / 0.10 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.34 block / 0.33 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 1.00 block / 0.94 crossed)
R3 within-row differences: G: H-G -1.56 [-3.68, +0.16], F-G -0.81 [-2.34, +0.33], F-H +0.75 [-0.23, +2.19]; H: H-G +6.07 [+2.96, +8.66], F-G +5.67 [+2.71, +8.19], F-H -0.39 [-1.43, +0.12]; F: H-G +4.90 [+1.59, +7.37], F-G +6.66 [+3.53, +8.75], F-H +1.76 [+0.26, +3.33]

Saturated oracles at 10% (all +1 states fit in every pooled cell): G, H, F.


## Bank U U1 (PRIMARY, ordinary own-trajectory states): pool KV8, same-draw (hindsight), budget 20% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +1.76 [+0.20, +3.73] | +6.08 [+2.94, +9.41] | +7.45 [+4.12, +10.79] |
| random (same capacity) | -0.12 [-0.63, +0.43] | +0.35 [-0.59, +1.22] | +0.24 [-0.71, +1.18] |
| G | net +1.76 (r 1.76, d 0.00) | net +0.45 (r 1.16, d 0.71); loss +5.63 [+3.14, +8.36]; over random +0.09 [-0.07, +0.36]; retained +1.65 [-1.22, +6.87]%, lost 93% of oracle | net +1.16 (r 2.05, d 0.90); loss +6.29 [+3.80, +8.81]; over random +0.92 [+0.22, +1.96]; retained +12.76 [+3.10, +26.67]%, lost 84% of oracle |
| H | net +0.01 (r 0.28, d 0.27); loss +1.76 [+0.42, +3.46]; over random +0.13 [-0.08, +0.45]; retained +6.74 [-3.34, +40.68]%, lost 99% of oracle | net +6.08 (r 6.08, d 0.00) | net +5.64 (r 5.96, d 0.32); loss +1.81 [+0.53, +3.46]; over random +5.40 [+3.11, +7.93]; retained +74.87 [+55.84, +91.93]%, lost 24% of oracle |
| F | net +0.81 (r 0.93, d 0.11); loss +0.95 [+0.10, +2.11]; over random +0.93 [+0.21, +2.00]; retained +49.43 [+16.27, +89.27]%, lost 54% of oracle | net +5.71 (r 5.74, d 0.03); loss +0.36 [+0.00, +1.46]; over random +5.36 [+3.10, +7.77]; retained +93.65 [+76.79, +100.00]%, lost 6% of oracle | net +7.45 (r 7.45, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.05 crossed): G: G>F>H (oracle F>H>G; argmax in oracle top set 0.03 block / 0.20 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.34 block / 0.35 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 0.97 block / 0.92 crossed)
R3 within-row differences: G: H-G -1.32 [-3.68, +0.64], F-G -0.61 [-2.22, +0.80], F-H +0.71 [-0.47, +2.28]; H: H-G +6.07 [+2.84, +9.50], F-G +5.63 [+2.63, +8.82], F-H -0.44 [-1.81, +0.36]; F: H-G +4.90 [+1.50, +8.29], F-G +6.64 [+3.48, +9.81], F-H +1.74 [+0.22, +3.73]

Saturated oracles at 20% (all +1 states fit in every pooled cell): G, H, F.


## Bank U U1 (PRIMARY, ordinary own-trajectory states): pool W4, split-half (mean of A->B and B->A), budget 5% (crossed intervals; ratios suppressed: noisy oracle)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +0.35 [-0.44, +1.18] | +0.75 [-0.31, +1.43] | +1.11 [-0.10, +1.74] |
| random (same capacity) | +0.02 [-0.09, +0.13] | -0.08 [-0.21, +0.06] | -0.08 [-0.24, +0.06] |
| G | net +0.35 (r 0.73, d 0.38) | net +0.31 (r 0.86, d 0.55); loss +0.44 [-0.42, +1.31]; over random +0.39 [-0.36, +0.88] | net +0.76 (r 1.19, d 0.44); loss +0.35 [-0.44, +1.10]; over random +0.84 [-0.24, +1.39] |
| H | net +0.52 (r 0.63, d 0.12); loss -0.17 [-1.12, +0.81]; over random +0.49 [-0.10, +1.02] | net +0.75 (r 1.17, d 0.42) | net +0.83 (r 1.23, d 0.40); loss +0.28 [-0.45, +0.79]; over random +0.91 [-0.05, +1.54] |
| F | net +0.83 (r 0.94, d 0.12); loss -0.47 [-1.14, +0.57]; over random +0.80 [-0.05, +1.23] | net +0.82 (r 1.20, d 0.39); loss -0.07 [-0.65, +0.65]; over random +0.89 [-0.06, +1.46] | net +1.11 (r 1.60, d 0.49) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: F>G>H (oracle F>H>G; argmax in oracle top set 0.75 block / 0.67 crossed); H: F>H>G (oracle F>H>G; argmax in oracle top set 0.73 block / 0.60 crossed); F: F>G>H (oracle F>H>G; argmax in oracle top set 0.73 block / 0.62 crossed)
R3 within-row differences: G: H-G -0.04 [-1.11, +0.80], F-G +0.41 [-0.81, +1.01], F-H +0.44 [-0.17, +0.97]; H: H-G +0.23 [-0.85, +0.99], F-G +0.32 [-0.59, +1.05], F-H +0.08 [-0.34, +0.57]; F: H-G -0.01 [-0.77, +0.67], F-G +0.29 [-0.59, +0.91], F-H +0.29 [-0.26, +0.85]


## Bank U U1 (PRIMARY, ordinary own-trajectory states): pool W4, split-half (mean of A->B and B->A), budget 10% (crossed intervals; ratios suppressed: noisy oracle)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +0.48 [-0.58, +1.61] | +1.05 [-0.45, +2.09] | +1.51 [-0.30, +2.72] |
| random (same capacity) | +0.04 [-0.18, +0.26] | -0.15 [-0.43, +0.12] | -0.16 [-0.47, +0.13] |
| G | net +0.48 (r 1.08, d 0.59) | net +0.41 (r 1.34, d 0.93); loss +0.64 [-0.56, +1.89]; over random +0.56 [-0.45, +1.24] | net +0.99 (r 1.85, d 0.86); loss +0.52 [-0.54, +1.77]; over random +1.15 [-0.31, +1.96] |
| H | net +0.65 (r 0.89, d 0.24); loss -0.17 [-1.35, +1.05]; over random +0.61 [-0.12, +1.31] | net +1.05 (r 1.75, d 0.70) | net +1.21 (r 1.93, d 0.72); loss +0.30 [-0.60, +1.11]; over random +1.37 [-0.02, +2.31] |
| F | net +1.21 (r 1.44, d 0.23); loss -0.72 [-1.44, +0.58]; over random +1.16 [-0.03, +1.86] | net +1.05 (r 1.80, d 0.75); loss -0.01 [-0.77, +0.76]; over random +1.21 [-0.12, +2.07] | net +1.51 (r 2.40, d 0.89) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: F>G>H (oracle F>H>G; argmax in oracle top set 0.75 block / 0.65 crossed); H: F>H>G (oracle F>H>G; argmax in oracle top set 0.73 block / 0.66 crossed); F: F>G>H (oracle F>H>G; argmax in oracle top set 0.73 block / 0.63 crossed)
R3 within-row differences: G: H-G -0.08 [-1.53, +0.97], F-G +0.51 [-1.14, +1.28], F-H +0.58 [-0.26, +1.31]; H: H-G +0.39 [-1.17, +1.47], F-G +0.56 [-0.79, +1.60], F-H +0.16 [-0.43, +0.83]; F: H-G -0.15 [-1.14, +1.01], F-G +0.30 [-0.84, +1.41], F-H +0.45 [-0.41, +1.30]


## Bank U U1 (PRIMARY, ordinary own-trajectory states): pool W4, split-half (mean of A->B and B->A), budget 20% (crossed intervals; ratios suppressed: noisy oracle)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +0.47 [-0.71, +1.68] | +0.90 [-0.67, +2.17] | +1.34 [-0.61, +2.97] |
| random (same capacity) | +0.09 [-0.35, +0.53] | -0.31 [-0.85, +0.24] | -0.32 [-0.94, +0.25] |
| G | net +0.47 (r 1.36, d 0.89) | net +0.26 (r 1.83, d 1.58); loss +0.64 [-0.59, +1.92]; over random +0.57 [-0.36, +1.23] | net +0.75 (r 2.35, d 1.60); loss +0.59 [-0.50, +1.83]; over random +1.07 [-0.29, +1.97] |
| H | net +0.67 (r 1.19, d 0.52); loss -0.20 [-1.29, +0.93]; over random +0.58 [-0.07, +1.23] | net +0.90 (r 2.18, d 1.28) | net +1.11 (r 2.45, d 1.34); loss +0.23 [-0.60, +1.07]; over random +1.44 [-0.02, +2.46] |
| F | net +1.15 (r 1.69, d 0.54); loss -0.68 [-1.46, +0.49]; over random +1.06 [-0.02, +1.83] | net +0.90 (r 2.24, d 1.34); loss -0.00 [-0.79, +0.67]; over random +1.21 [-0.10, +2.23] | net +1.34 (r 2.86, d 1.52) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: F>G>H (oracle F>H>G; argmax in oracle top set 0.75 block / 0.63 crossed); H: F>H>G (oracle F>H>G; argmax in oracle top set 0.73 block / 0.67 crossed); F: F>G>H (oracle F>H>G; argmax in oracle top set 0.73 block / 0.61 crossed)
R3 within-row differences: G: H-G -0.21 [-1.74, +0.94], F-G +0.28 [-1.39, +1.21], F-H +0.49 [-0.43, +1.32]; H: H-G +0.23 [-1.33, +1.40], F-G +0.44 [-1.01, +1.61], F-H +0.22 [-0.50, +0.93]; F: H-G -0.25 [-1.35, +1.01], F-G +0.19 [-1.05, +1.40], F-H +0.44 [-0.53, +1.40]


## Bank P first-divergence states (SECONDARY): pool W4, same-draw (hindsight), budget 5% (block and crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +5.00 blk [+5.00, +5.00] cr [+5.00, +5.00] | +5.00 blk [+5.00, +5.00] cr [+4.68, +5.00] | +5.00 blk [+5.00, +5.00] cr [+5.00, +5.00] |
| random (same capacity) | +0.03 blk [-0.04, +0.09] cr [-0.14, +0.19] | +0.01 blk [-0.06, +0.08] cr [-0.14, +0.14] | +0.03 blk [-0.03, +0.11] cr [-0.16, +0.22] |
| G | net +5.00 (r 5.00, d 0.00) | net +1.84 (r 1.84, d 0.00); loss +3.16 blk [+3.00, +3.30] cr [+2.61, +3.57]; over random +1.83 blk [+1.70, +1.98] cr [+1.40, +2.32]; retained +36.75 blk [+34.02, +39.78] cr [+28.26, +46.85]%, lost 63% of oracle | net +2.94 (r 2.94, d 0.00); loss +2.06 blk [+1.90, +2.22] cr [+1.56, +2.61]; over random +2.90 blk [+2.73, +3.09] cr [+2.41, +3.36]; retained +58.46 blk [+55.32, +61.94] cr [+48.05, +67.98]%, lost 41% of oracle |
| H | net +2.41 (r 2.41, d 0.00); loss +2.59 blk [+2.43, +2.75] cr [+2.09, +3.21]; over random +2.39 blk [+2.21, +2.56] cr [+1.83, +2.84]; retained +47.99 blk [+44.55, +51.16] cr [+36.35, +57.59]%, lost 52% of oracle | net +5.00 (r 5.00, d 0.00) | net +2.25 (r 2.25, d 0.00); loss +2.75 blk [+2.56, +2.94] cr [+2.24, +3.33]; over random +2.21 blk [+2.02, +2.41] cr [+1.67, +2.68]; retained +44.58 blk [+40.82, +48.39] cr [+33.37, +54.32]%, lost 55% of oracle |
| F | net +2.87 (r 2.87, d 0.00); loss +2.13 blk [+1.97, +2.30] cr [+1.63, +2.64]; over random +2.84 blk [+2.68, +3.00] cr [+2.40, +3.27]; retained +57.12 blk [+53.83, +60.30] cr [+47.69, +66.68]%, lost 43% of oracle | net +1.68 (r 1.68, d 0.00); loss +3.32 blk [+3.11, +3.51] cr [+2.81, +3.75]; over random +1.67 blk [+1.50, +1.85] cr [+1.23, +2.13]; retained +33.51 blk [+29.97, +37.35] cr [+24.91, +43.03]%, lost 66% of oracle | net +5.00 (r 5.00, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point True, draws 1.00 block / 1.00 crossed): G: G>F>H (oracle H=G=F; argmax in oracle top set 1.00 block / 0.99 crossed); H: H>G>F (oracle H=G=F; argmax in oracle top set 1.00 block / 0.85 crossed); F: F>G>H (oracle H=G=F; argmax in oracle top set 1.00 block / 1.00 crossed)
R3 within-row differences: G: H-G -3.16 blk [-3.30, -3.00] cr [-3.64, -2.63], F-G -2.06 blk [-2.22, -1.90] cr [-2.60, -1.56], F-H +1.09 blk [+0.87, +1.33] cr [+0.42, +1.74]; H: H-G +2.59 blk [+2.43, +2.75] cr [+2.08, +3.13], F-G -0.17 blk [-0.40, +0.08] cr [-0.62, +0.31], F-H -2.75 blk [-2.94, -2.56] cr [-3.28, -2.22]; F: H-G -1.19 blk [-1.42, -0.96] cr [-1.80, -0.56], F-G +2.13 blk [+1.97, +2.30] cr [+1.63, +2.65], F-H +3.32 blk [+3.11, +3.51] cr [+2.83, +3.81]

Saturated oracles at 5% (all +1 states fit in every pooled cell): none.


## Bank P first-divergence states (SECONDARY): pool W4, same-draw (hindsight), budget 10% (block and crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +10.00 blk [+9.60, +10.00] cr [+8.37, +10.00] | +8.84 blk [+8.03, +9.34] cr [+6.65, +9.75] | +10.00 blk [+9.65, +10.00] cr [+8.58, +10.00] |
| random (same capacity) | +0.05 blk [-0.07, +0.17] cr [-0.29, +0.38] | +0.02 blk [-0.13, +0.16] cr [-0.27, +0.28] | +0.07 blk [-0.06, +0.21] cr [-0.31, +0.44] |
| G | net +10.00 (r 10.00, d 0.00) | net +3.69 (r 3.69, d 0.00); loss +5.15 blk [+4.47, +5.56] cr [+3.56, +5.99]; over random +3.67 blk [+3.38, +3.93] cr [+2.67, +4.46]; retained +41.58 blk [+38.55, +45.60] cr [+33.35, +51.90]%, lost 58% of oracle | net +5.87 (r 5.87, d 0.00); loss +4.13 blk [+3.72, +4.43] cr [+2.91, +5.06]; over random +5.80 blk [+5.45, +6.11] cr [+4.50, +6.54]; retained +58.46 blk [+55.26, +62.08] cr [+47.86, +68.72]%, lost 41% of oracle |
| H | net +4.34 (r 4.42, d 0.08); loss +5.66 blk [+5.23, +6.01] cr [+4.31, +6.65]; over random +4.29 blk [+3.91, +4.57] cr [+2.89, +5.15]; retained +43.09 blk [+39.60, +46.34] cr [+30.84, +53.85]%, lost 57% of oracle | net +8.84 (r 8.84, d 0.00) | net +4.02 (r 4.11, d 0.08); loss +5.98 blk [+5.49, +6.39] cr [+4.60, +6.97]; over random +3.95 blk [+3.51, +4.32] cr [+2.64, +4.85]; retained +39.82 blk [+35.54, +43.97] cr [+27.90, +50.39]%, lost 60% of oracle |
| F | net +5.74 (r 5.74, d 0.00); loss +4.26 blk [+3.92, +4.57] cr [+3.10, +5.01]; over random +5.68 blk [+5.34, +5.94] cr [+4.48, +6.32]; retained +57.12 blk [+53.97, +59.89] cr [+47.89, +65.94]%, lost 43% of oracle | net +3.36 (r 3.36, d 0.00); loss +5.48 blk [+4.84, +5.86] cr [+3.85, +6.29]; over random +3.34 blk [+3.00, +3.66] cr [+2.37, +4.11]; retained +37.91 blk [+34.78, +41.60] cr [+30.02, +48.41]%, lost 62% of oracle | net +10.00 (r 10.00, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point True, draws 0.44 block / 0.19 crossed): G: G>F>H (oracle G=F>H; argmax in oracle top set 0.80 block / 0.57 crossed); H: H>G>F (oracle G=F>H; argmax in oracle top set 0.00 block / 0.02 crossed); F: F>G>H (oracle G=F>H; argmax in oracle top set 0.65 block / 0.61 crossed)
R3 within-row differences: G: H-G -6.31 blk [-6.59, -5.84] cr [-7.11, -4.79], F-G -4.13 blk [-4.43, -3.71] cr [-5.03, -2.92], F-H +2.19 blk [+1.71, +2.63] cr [+0.74, +3.43]; H: H-G +4.50 blk [+3.92, +4.95] cr [+3.12, +5.46], F-G -0.32 blk [-0.68, +0.11] cr [-1.11, +0.53], F-H -4.82 blk [-5.23, -4.21] cr [-5.75, -3.30]; F: H-G -2.37 blk [-2.80, -1.90] cr [-3.45, -1.05], F-G +4.26 blk [+3.88, +4.59] cr [+3.10, +5.18], F-H +6.64 blk [+6.09, +6.99] cr [+5.20, +7.44]

Saturated oracles at 10% (all +1 states fit in every pooled cell): none.


## Bank P first-divergence states (SECONDARY): pool W4, same-draw (hindsight), budget 20% (block and crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +11.64 blk [+10.80, +12.46] cr [+8.81, +14.62] | +8.91 blk [+8.09, +9.85] cr [+6.69, +11.33] | +11.97 blk [+11.18, +12.81] cr [+9.26, +14.81] |
| random (same capacity) | +0.11 blk [-0.14, +0.35] cr [-0.58, +0.76] | +0.04 blk [-0.25, +0.32] cr [-0.55, +0.57] | +0.14 blk [-0.13, +0.43] cr [-0.62, +0.89] |
| G | net +11.64 (r 11.64, d 0.00) | net +4.44 (r 4.85, d 0.41); loss +4.47 blk [+3.95, +5.02] cr [+3.20, +5.96]; over random +4.40 blk [+4.08, +4.73] cr [+3.14, +5.77]; retained +49.61 blk [+46.05, +52.71] cr [+39.55, +59.30]%, lost 50% of oracle | net +6.96 (r 7.39, d 0.44); loss +5.01 blk [+4.55, +5.53] cr [+3.60, +6.47]; over random +6.82 blk [+6.45, +7.17] cr [+5.18, +8.64]; retained +57.63 blk [+54.70, +60.44] cr [+49.07, +66.48]%, lost 42% of oracle |
| H | net +4.51 (r 5.33, d 0.82); loss +7.13 blk [+6.49, +7.74] cr [+5.24, +9.16]; over random +4.40 blk [+4.06, +4.78] cr [+3.15, +5.77]; retained +38.18 blk [+35.41, +41.23] cr [+29.51, +47.80]%, lost 61% of oracle | net +8.91 (r 8.91, d 0.00) | net +4.23 (r 5.10, d 0.86); loss +7.74 blk [+7.07, +8.41] cr [+5.84, +9.78]; over random +4.09 blk [+3.72, +4.48] cr [+2.91, +5.36]; retained +34.61 blk [+31.36, +38.36] cr [+25.95, +43.57]%, lost 65% of oracle |
| F | net +6.93 (r 7.35, d 0.42); loss +4.71 blk [+4.11, +5.27] cr [+3.24, +6.33]; over random +6.82 blk [+6.43, +7.19] cr [+5.16, +8.65]; retained +59.17 blk [+55.97, +62.54] cr [+50.10, +68.26]%, lost 40% of oracle | net +4.13 (r 4.54, d 0.41); loss +4.78 blk [+4.25, +5.32] cr [+3.44, +6.31]; over random +4.09 blk [+3.74, +4.45] cr [+2.89, +5.43]; retained +46.12 blk [+42.88, +49.66] cr [+36.62, +55.71]%, lost 54% of oracle | net +11.97 (r 11.97, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: G>F>H (oracle F>G>H; argmax in oracle top set 0.23 block / 0.35 crossed); H: H>G>F (oracle F>G>H; argmax in oracle top set 0.00 block / 0.00 crossed); F: F>G>H (oracle F>G>H; argmax in oracle top set 0.77 block / 0.65 crossed)
R3 within-row differences: G: H-G -7.20 blk [-7.93, -6.50] cr [-9.58, -5.05], F-G -4.68 blk [-5.27, -4.04] cr [-6.38, -3.11], F-H +2.52 blk [+1.88, +3.16] cr [+0.75, +4.48]; H: H-G +4.40 blk [+3.82, +5.03] cr [+2.96, +6.09], F-G -0.28 blk [-0.69, +0.16] cr [-1.27, +0.68], F-H -4.68 blk [-5.34, -4.03] cr [-6.41, -3.09]; F: H-G -2.80 blk [-3.39, -2.25] cr [-4.70, -1.15], F-G +5.04 blk [+4.48, +5.66] cr [+3.44, +6.69], F-H +7.84 blk [+7.03, +8.67] cr [+5.60, +10.20]

Saturated oracles at 20% (all +1 states fit in every pooled cell): G, H, F.


## Bank P first-divergence states (SECONDARY): pool KV8, same-draw (hindsight), budget 5% (block and crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +5.00 blk [+5.00, +5.00] cr [+4.87, +5.00] | +3.95 blk [+2.96, +4.86] cr [+2.23, +5.00] | +5.00 blk [+5.00, +5.00] cr [+5.00, +5.00] |
| random (same capacity) | +0.01 blk [-0.14, +0.15] cr [-0.26, +0.28] | -0.07 blk [-0.13, -0.00] cr [-0.19, +0.05] | +0.03 blk [-0.09, +0.16] cr [-0.23, +0.31] |
| G | net +5.00 (r 5.00, d 0.00) | net +0.85 (r 0.85, d 0.00); loss +3.10 blk [+2.29, +3.80] cr [+1.65, +4.04]; over random +0.92 blk [+0.66, +1.19] cr [+0.44, +1.53]; retained +22.93 blk [+18.41, +28.52] cr [+12.84, +38.23]%, lost 78% of oracle | net +3.80 (r 3.80, d 0.00); loss +1.20 blk [+0.84, +1.62] cr [+0.65, +1.93]; over random +3.77 blk [+3.43, +4.04] cr [+3.11, +4.30]; retained +75.79 blk [+67.99, +82.70] cr [+61.89, +86.68]%, lost 24% of oracle |
| H | net +1.65 (r 1.73, d 0.08); loss +3.35 blk [+2.77, +3.98] cr [+2.29, +4.37]; over random +1.64 blk [+1.07, +2.16] cr [+0.68, +2.62]; retained +32.93 blk [+21.37, +43.66] cr [+13.56, +53.24]%, lost 67% of oracle | net +3.95 (r 3.95, d 0.00) | net +1.71 (r 1.79, d 0.08); loss +3.29 blk [+2.74, +3.79] cr [+2.37, +4.21]; over random +1.68 blk [+1.22, +2.16] cr [+0.76, +2.61]; retained +33.86 blk [+24.36, +44.16] cr [+15.44, +52.16]%, lost 66% of oracle |
| F | net +3.37 (r 3.37, d 0.00); loss +1.63 blk [+1.24, +2.05] cr [+0.90, +2.38]; over random +3.37 blk [+3.06, +3.65] cr [+2.67, +3.98]; retained +67.43 blk [+60.02, +74.59] cr [+53.15, +81.37]%, lost 33% of oracle | net +0.78 (r 0.78, d 0.00); loss +3.18 blk [+2.34, +3.92] cr [+1.67, +4.12]; over random +0.85 blk [+0.65, +1.07] cr [+0.45, +1.40]; retained +21.12 blk [+17.36, +25.83] cr [+12.79, +35.52]%, lost 80% of oracle | net +5.00 (r 5.00, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point True, draws 1.00 block / 0.96 crossed): G: G>F>H (oracle G=F>H; argmax in oracle top set 1.00 block / 0.97 crossed); H: H>F>G (oracle G=F>H; argmax in oracle top set 0.01 block / 0.05 crossed); F: F>G>H (oracle G=F>H; argmax in oracle top set 1.00 block / 0.99 crossed)
R3 within-row differences: G: H-G -4.15 blk [-4.44, -3.88] cr [-4.64, -3.46], F-G -1.20 blk [-1.62, -0.84] cr [-1.91, -0.65], F-H +2.95 blk [+2.38, +3.42] cr [+1.90, +3.72]; H: H-G +2.30 blk [+1.59, +2.95] cr [+1.02, +3.35], F-G +0.06 blk [-0.43, +0.58] cr [-0.73, +0.88], F-H -2.24 blk [-3.06, -1.46] cr [-3.29, -1.04]; F: H-G -2.60 blk [-2.98, -2.15] cr [-3.41, -1.63], F-G +1.63 blk [+1.24, +2.05] cr [+0.91, +2.40], F-H +4.22 blk [+3.99, +4.44] cr [+3.61, +4.64]

Saturated oracles at 5% (all +1 states fit in every pooled cell): H.


## Bank P first-divergence states (SECONDARY): pool KV8, same-draw (hindsight), budget 10% (block and crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +9.63 blk [+8.07, +10.00] cr [+6.33, +10.00] | +3.95 blk [+2.96, +4.96] cr [+2.23, +6.00] | +10.00 blk [+9.14, +10.00] cr [+7.06, +10.00] |
| random (same capacity) | +0.01 blk [-0.28, +0.30] cr [-0.51, +0.57] | -0.14 blk [-0.27, -0.01] cr [-0.38, +0.09] | +0.06 blk [-0.18, +0.31] cr [-0.45, +0.61] |
| G | net +9.63 (r 9.63, d 0.00) | net +1.64 (r 1.65, d 0.01); loss +2.32 blk [+1.68, +3.07] cr [+1.18, +3.98]; over random +1.78 blk [+1.19, +2.28] cr [+0.76, +2.71]; retained +43.43 blk [+32.28, +52.44] cr [+22.68, +60.96]%, lost 59% of oracle | net +7.33 (r 7.34, d 0.01); loss +2.67 blk [+1.82, +3.71] cr [+1.37, +4.00]; over random +7.26 blk [+5.89, +7.93] cr [+4.62, +8.17]; retained +73.11 blk [+61.64, +81.29] cr [+56.09, +84.96]%, lost 27% of oracle |
| H | net +1.72 (r 2.17, d 0.45); loss +7.91 blk [+6.69, +8.35] cr [+5.05, +8.59]; over random +1.71 blk [+1.16, +2.24] cr [+0.78, +2.89]; retained +17.76 blk [+12.84, +23.46] cr [+9.35, +32.47]%, lost 82% of oracle | net +3.95 (r 3.95, d 0.00) | net +1.84 (r 2.30, d 0.46); loss +8.16 blk [+7.36, +8.53] cr [+5.64, +8.70]; over random +1.77 blk [+1.32, +2.25] cr [+0.87, +2.96]; retained +17.84 blk [+13.56, +23.02] cr [+9.92, +31.00]%, lost 82% of oracle |
| F | net +6.75 (r 6.75, d 0.00); loss +2.88 blk [+2.15, +3.23] cr [+1.34, +3.72]; over random +6.73 blk [+5.85, +7.26] cr [+4.53, +7.66]; retained +70.05 blk [+66.41, +76.03] cr [+59.37, +82.98]%, lost 30% of oracle | net +1.56 (r 1.56, d 0.00); loss +2.40 blk [+1.69, +3.20] cr [+1.19, +4.09]; over random +1.70 blk [+1.29, +2.10] cr [+0.85, +2.56]; retained +41.49 blk [+33.02, +49.78] cr [+23.76, +58.97]%, lost 61% of oracle | net +10.00 (r 10.00, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.13 block / 0.17 crossed): G: G>F>H (oracle F>G>H; argmax in oracle top set 0.18 block / 0.34 crossed); H: H>F>G (oracle F>G>H; argmax in oracle top set 0.00 block / 0.00 crossed); F: F>G>H (oracle F>G>H; argmax in oracle top set 0.95 block / 0.83 crossed)
R3 within-row differences: G: H-G -7.99 blk [-8.54, -6.67] cr [-9.00, -4.98], F-G -2.30 blk [-2.99, -1.59] cr [-3.29, -1.08], F-H +5.69 blk [+4.20, +6.65] cr [+2.88, +7.11]; H: H-G +2.23 blk [+1.48, +3.01] cr [+0.86, +3.74], F-G +0.12 blk [-0.43, +0.69] cr [-0.79, +1.03], F-H -2.12 blk [-3.06, -1.31] cr [-3.61, -0.83]; F: H-G -5.19 blk [-5.93, -4.07] cr [-6.65, -2.74], F-G +3.25 blk [+2.45, +3.96] cr [+1.62, +4.45], F-H +8.44 blk [+7.54, +8.83] cr [+5.70, +9.16]

Saturated oracles at 10% (all +1 states fit in every pooled cell): G, H.


## Bank P first-divergence states (SECONDARY): pool KV8, same-draw (hindsight), budget 20% (block and crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +9.63 blk [+8.07, +11.22] cr [+6.33, +13.90] | +3.95 blk [+2.96, +4.96] cr [+2.23, +6.00] | +10.82 blk [+9.23, +12.65] cr [+7.09, +15.31] |
| random (same capacity) | +0.03 blk [-0.56, +0.60] cr [-1.02, +1.13] | -0.29 blk [-0.54, -0.01] cr [-0.75, +0.18] | +0.13 blk [-0.35, +0.62] cr [-0.91, +1.23] |
| G | net +9.63 (r 9.63, d 0.00) | net +1.60 (r 1.93, d 0.34); loss +2.36 blk [+1.74, +2.99] cr [+1.23, +3.66]; over random +1.88 blk [+1.35, +2.46] cr [+0.98, +3.02]; retained +44.44 blk [+35.18, +53.81] cr [+28.20, +62.86]%, lost 60% of oracle | net +7.42 (r 7.77, d 0.35); loss +3.40 blk [+2.67, +4.11] cr [+1.89, +5.14]; over random +7.29 blk [+6.13, +8.63] cr [+4.85, +10.32]; retained +68.20 blk [+61.71, +74.76] cr [+55.78, +81.05]%, lost 31% of oracle |
| H | net +1.86 (r 3.05, d 1.19); loss +7.77 blk [+6.73, +8.85] cr [+5.30, +10.94]; over random +1.83 blk [+1.33, +2.37] cr [+0.97, +2.90]; retained +19.09 blk [+14.27, +24.33] cr [+10.50, +29.90]%, lost 81% of oracle | net +3.95 (r 3.95, d 0.00) | net +2.08 (r 3.31, d 1.22); loss +8.74 blk [+7.54, +9.95] cr [+5.87, +12.02]; over random +1.95 blk [+1.53, +2.41] cr [+1.07, +3.10]; retained +18.26 blk [+14.43, +22.41] cr [+10.21, +28.87]%, lost 81% of oracle |
| F | net +7.36 (r 7.59, d 0.24); loss +2.27 blk [+1.63, +2.97] cr [+1.22, +3.53]; over random +7.33 blk [+6.17, +8.62] cr [+4.87, +10.34]; retained +76.35 blk [+69.21, +82.90] cr [+64.52, +86.39]%, lost 24% of oracle | net +1.71 (r 1.95, d 0.24); loss +2.25 blk [+1.57, +3.00] cr [+1.16, +3.57]; over random +1.99 blk [+1.56, +2.49] cr [+1.09, +3.08]; retained +47.02 blk [+37.62, +56.96] cr [+31.10, +64.37]%, lost 57% of oracle | net +10.82 (r 10.82, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: G>F>H (oracle F>G>H; argmax in oracle top set 0.05 block / 0.14 crossed); H: H>F>G (oracle F>G>H; argmax in oracle top set 0.00 block / 0.01 crossed); F: F>G>H (oracle F>G>H; argmax in oracle top set 0.95 block / 0.86 crossed)
R3 within-row differences: G: H-G -8.03 blk [-9.38, -6.70] cr [-11.72, -5.02], F-G -2.21 blk [-3.03, -1.43] cr [-3.64, -0.97], F-H +5.82 blk [+4.29, +7.43] cr [+2.94, +9.36]; H: H-G +2.09 blk [+1.20, +3.02] cr [+0.48, +3.84], F-G +0.22 blk [-0.45, +0.92] cr [-0.81, +1.26], F-H -1.87 blk [-2.95, -0.96] cr [-3.54, -0.34]; F: H-G -5.65 blk [-7.15, -4.15] cr [-9.15, -2.77], F-G +3.46 blk [+2.52, +4.42] cr [+1.74, +5.43], F-H +9.12 blk [+7.56, +10.66] cr [+5.69, +13.06]

Saturated oracles at 20% (all +1 states fit in every pooled cell): G, H, F.


## Bank P dev_all units (SECONDARY; pp of all units, non-divergent units count 0): pool W4, split-half (mean of A->B and B->A), budget 5% (block and crossed intervals; ratios suppressed: noisy oracle)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +2.83 blk [+2.11, +2.95] cr [+1.46, +3.19] | +1.39 blk [+0.79, +1.64] cr [+0.28, +2.16] | +2.54 blk [+1.94, +2.89] cr [+1.51, +3.04] |
| random (same capacity) | +0.03 blk [-0.02, +0.08] cr [-0.11, +0.17] | -0.00 blk [-0.05, +0.05] cr [-0.11, +0.11] | +0.04 blk [-0.02, +0.09] cr [-0.12, +0.20] |
| G | net +2.83 (r 2.96, d 0.14) | net +1.09 (r 1.45, d 0.36); loss +0.31 blk [-0.10, +0.78] cr [-0.29, +1.15]; over random +1.09 blk [+0.56, +1.26] cr [+0.09, +1.58] | net +2.18 (r 2.44, d 0.26); loss +0.36 blk [+0.08, +0.81] cr [-0.14, +1.19]; over random +2.14 blk [+1.50, +2.34] cr [+0.90, +2.60] |
| H | net +1.12 (r 1.76, d 0.63); loss +1.70 blk [+1.11, +2.13] cr [+0.57, +2.45]; over random +1.09 blk [+0.45, +1.38] cr [+0.03, +1.77] | net +1.39 (r 1.88, d 0.49) | net +0.84 (r 1.60, d 0.76); loss +1.70 blk [+1.09, +2.21] cr [+0.64, +2.50]; over random +0.80 blk [+0.28, +1.18] cr [-0.03, +1.52] |
| F | net +2.03 (r 2.42, d 0.39); loss +0.79 blk [+0.30, +1.12] cr [+0.01, +1.41]; over random +2.00 blk [+1.36, +2.26] cr [+0.72, +2.56] | net +0.71 (r 1.16, d 0.45); loss +0.68 blk [+0.10, +1.15] cr [-0.11, +1.56]; over random +0.71 blk [+0.21, +0.94] cr [-0.04, +1.19] | net +2.54 (r 2.71, d 0.17) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: G>F>H (oracle G>F>H; argmax in oracle top set 0.74 block / 0.61 crossed); H: H>G>F (oracle G>F>H; argmax in oracle top set 0.09 block / 0.22 crossed); F: F>G>H (oracle G>F>H; argmax in oracle top set 0.26 block / 0.44 crossed)
R3 within-row differences: G: H-G -1.74 blk [-2.05, -1.23] cr [-2.44, -0.75], F-G -0.65 blk [-0.95, -0.24] cr [-1.26, +0.06], F-H +1.09 blk [+0.56, +1.54] cr [+0.02, +2.08]; H: H-G +0.27 blk [-0.12, +0.65] cr [-0.45, +0.94], F-G -0.28 blk [-0.68, +0.31] cr [-0.88, +0.56], F-H -0.55 blk [-0.95, +0.10] cr [-1.34, +0.45]; F: H-G -1.32 blk [-1.68, -0.84] cr [-2.14, -0.27], F-G +0.51 blk [+0.18, +0.91] cr [-0.01, +1.31], F-H +1.83 blk [+1.40, +2.25] cr [+0.96, +2.60]


## Bank P dev_all units (SECONDARY; pp of all units, non-divergent units count 0): pool W4, split-half (mean of A->B and B->A), budget 10% (block and crossed intervals; ratios suppressed: noisy oracle)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +3.80 blk [+2.94, +4.14] cr [+1.81, +4.99] | +1.77 blk [+1.03, +2.15] cr [+0.38, +2.74] | +4.35 blk [+3.26, +4.56] cr [+2.41, +5.08] |
| random (same capacity) | +0.06 blk [-0.04, +0.15] cr [-0.21, +0.33] | -0.00 blk [-0.10, +0.10] cr [-0.23, +0.21] | +0.08 blk [-0.03, +0.19] cr [-0.24, +0.40] |
| G | net +3.80 (r 4.46, d 0.66) | net +0.92 (r 2.15, d 1.23); loss +0.84 blk [+0.09, +1.18] cr [-0.29, +1.51]; over random +0.92 blk [+0.51, +1.41] cr [-0.03, +2.01] | net +2.85 (r 3.76, d 0.92); loss +1.50 blk [+0.59, +1.84] cr [+0.20, +2.19]; over random +2.77 blk [+2.09, +3.10] cr [+1.20, +3.84] |
| H | net +1.37 (r 2.77, d 1.40); loss +2.43 blk [+1.62, +3.01] cr [+0.97, +3.68]; over random +1.31 blk [+0.62, +1.75] cr [+0.06, +2.32] | net +1.77 (r 2.71, d 0.94) | net +1.52 (r 2.93, d 1.40); loss +2.82 blk [+2.01, +3.36] cr [+1.40, +3.90]; over random +1.45 blk [+0.61, +1.67] cr [+0.08, +2.19] |
| F | net +2.92 (r 3.72, d 0.80); loss +0.88 blk [+0.36, +1.31] cr [-0.05, +1.82]; over random +2.86 blk [+2.08, +3.22] cr [+1.17, +3.92] | net +1.01 (r 2.04, d 1.03); loss +0.76 blk [+0.05, +1.14] cr [-0.26, +1.60]; over random +1.01 blk [+0.49, +1.35] cr [+0.04, +1.89] | net +4.35 (r 4.74, d 0.40) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: G>F>H (oracle F>G>H; argmax in oracle top set 0.15 block / 0.34 crossed); H: H>F>G (oracle F>G>H; argmax in oracle top set 0.17 block / 0.28 crossed); F: F>G>H (oracle F>G>H; argmax in oracle top set 0.85 block / 0.71 crossed)
R3 within-row differences: G: H-G -2.88 blk [-3.24, -1.97] cr [-3.91, -1.13], F-G -0.96 blk [-1.36, -0.34] cr [-1.95, +0.13], F-H +1.92 blk [+1.01, +2.36] cr [+0.22, +3.14]; H: H-G +0.40 blk [-0.20, +0.87] cr [-0.72, +1.41], F-G +0.15 blk [-0.60, +0.64] cr [-0.98, +0.98], F-H -0.24 blk [-0.94, +0.31] cr [-1.62, +0.88]; F: H-G -1.92 blk [-2.35, -1.22] cr [-3.08, -0.35], F-G +1.43 blk [+0.68, +1.70] cr [+0.22, +2.20], F-H +3.34 blk [+2.39, +3.51] cr [+1.58, +4.09]


## Bank P dev_all units (SECONDARY; pp of all units, non-divergent units count 0): pool W4, split-half (mean of A->B and B->A), budget 20% (block and crossed intervals; ratios suppressed: noisy oracle)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +4.20 blk [+3.38, +4.86] cr [+2.17, +6.13] | +2.13 blk [+1.15, +2.56] cr [+0.47, +3.36] | +5.35 blk [+4.29, +5.75] cr [+3.11, +6.96] |
| random (same capacity) | +0.12 blk [-0.07, +0.31] cr [-0.43, +0.67] | -0.00 blk [-0.21, +0.20] cr [-0.45, +0.43] | +0.15 blk [-0.06, +0.38] cr [-0.48, +0.80] |
| G | net +4.20 (r 5.79, d 1.59) | net +1.19 (r 3.27, d 2.08); loss +0.94 blk [+0.22, +1.41] cr [-0.19, +1.82]; over random +1.19 blk [+0.66, +1.54] cr [+0.07, +2.16] | net +3.13 (r 5.22, d 2.09); loss +2.22 blk [+1.19, +2.58] cr [+0.68, +3.14]; over random +2.98 blk [+2.43, +3.51] cr [+1.50, +4.51] |
| H | net +1.75 (r 4.08, d 2.33); loss +2.45 blk [+1.74, +3.44] cr [+1.19, +4.25]; over random +1.62 blk [+0.74, +2.12] cr [+0.13, +2.69] | net +2.13 (r 3.71, d 1.58) | net +1.96 (r 4.42, d 2.45); loss +3.39 blk [+2.63, +4.08] cr [+1.94, +4.91]; over random +1.81 blk [+0.84, +2.15] cr [+0.22, +2.82] |
| F | net +3.30 (r 5.27, d 1.98); loss +0.90 blk [+0.42, +1.48] cr [-0.11, +2.10]; over random +3.17 blk [+2.51, +3.61] cr [+1.54, +4.64] | net +1.39 (r 3.46, d 2.08); loss +0.74 blk [+0.05, +1.16] cr [-0.36, +1.70]; over random +1.39 blk [+0.72, +1.73] cr [+0.13, +2.32] | net +5.35 (r 6.67, d 1.32) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: G>F>H (oracle F>G>H; argmax in oracle top set 0.03 block / 0.20 crossed); H: H>F>G (oracle F>G>H; argmax in oracle top set 0.27 block / 0.35 crossed); F: F>G>H (oracle F>G>H; argmax in oracle top set 0.97 block / 0.87 crossed)
R3 within-row differences: G: H-G -3.01 blk [-3.79, -2.27] cr [-4.95, -1.30], F-G -1.07 blk [-1.63, -0.33] cr [-2.42, +0.24], F-H +1.94 blk [+1.18, +2.80] cr [+0.24, +3.92]; H: H-G +0.38 blk [-0.31, +1.03] cr [-1.07, +1.77], F-G +0.22 blk [-0.44, +0.80] cr [-1.16, +1.44], F-H -0.16 blk [-0.78, +0.53] cr [-1.77, +1.39]; F: H-G -1.91 blk [-2.67, -1.23] cr [-3.74, -0.34], F-G +2.05 blk [+1.09, +2.53] cr [+0.55, +3.21], F-H +3.96 blk [+3.09, +4.48] cr [+2.05, +5.64]


## Bank U U2B (SENSITIVITY, BF16-sourced states): pool W4, same-draw (hindsight), budget 5% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +3.80 [+1.96, +4.66] | +5.00 [+4.07, +5.00] | +5.00 [+3.97, +5.00] |
| random (same capacity) | +0.00 [-0.12, +0.13] | +0.10 [-0.07, +0.28] | +0.07 [-0.16, +0.29] |
| G | net +3.80 (r 3.80, d 0.00) | net +1.61 (r 1.67, d 0.06); loss +3.39 [+2.53, +4.25]; over random +1.51 [+0.54, +2.19]; retained +30.82 [+11.40, +45.74]%, lost 68% of oracle | net +2.69 (r 2.75, d 0.06); loss +2.31 [+1.34, +3.69]; over random +2.62 [+1.03, +3.38]; retained +53.19 [+21.86, +71.44]%, lost 46% of oracle |
| H | net +1.07 (r 1.07, d 0.00); loss +2.73 [+1.14, +3.54]; over random +1.06 [+0.47, +1.63]; retained +28.03 [+15.64, +51.60]%, lost 72% of oracle | net +5.00 (r 5.00, d 0.00) | net +3.68 (r 3.68, d 0.00); loss +1.32 [+0.64, +2.06]; over random +3.61 [+2.61, +4.18]; retained +73.18 [+57.21, +86.29]%, lost 26% of oracle |
| F | net +1.63 (r 1.63, d 0.00); loss +2.17 [+0.79, +2.87]; over random +1.62 [+0.78, +2.29]; retained +42.81 [+27.48, +67.80]%, lost 57% of oracle | net +3.39 (r 3.39, d 0.00); loss +1.61 [+0.92, +2.24]; over random +3.29 [+2.33, +3.88]; retained +67.20 [+52.61, +80.28]%, lost 32% of oracle | net +5.00 (r 5.00, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point True, draws 0.97 block / 0.55 crossed): G: G>F>H (oracle H=F>G; argmax in oracle top set 0.00 block / 0.01 crossed); H: H>F>G (oracle H=F>G; argmax in oracle top set 0.97 block / 0.78 crossed); F: F>H>G (oracle H=F>G; argmax in oracle top set 1.00 block / 0.77 crossed)
R3 within-row differences: G: H-G -2.19 [-2.98, -0.78], F-G -1.11 [-2.03, -0.11], F-H +1.08 [-0.58, +2.28]; H: H-G +3.93 [+3.02, +4.48], F-G +2.61 [+1.33, +3.58], F-H -1.32 [-2.04, -0.62]; F: H-G +1.76 [+0.56, +2.82], F-G +3.37 [+2.38, +4.12], F-H +1.61 [+0.88, +2.31]

Saturated oracles at 5% (all +1 states fit in every pooled cell): none.


## Bank U U2B (SENSITIVITY, BF16-sourced states): pool W4, same-draw (hindsight), budget 10% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +4.02 [+2.06, +6.18] | +7.75 [+5.00, +9.66] | +8.38 [+5.20, +9.85] |
| random (same capacity) | +0.01 [-0.24, +0.26] | +0.20 [-0.15, +0.56] | +0.14 [-0.32, +0.59] |
| G | net +4.02 (r 4.02, d 0.00) | net +1.77 (r 2.06, d 0.29); loss +5.97 [+3.70, +7.51]; over random +1.58 [+0.63, +2.59]; retained +20.86 [+10.09, +34.58]%, lost 77% of oracle | net +2.92 (r 3.21, d 0.29); loss +5.46 [+2.93, +6.70]; over random +2.78 [+1.19, +4.58]; retained +33.75 [+17.89, +56.60]%, lost 65% of oracle |
| H | net +1.66 (r 1.72, d 0.07); loss +2.36 [+0.97, +4.21]; over random +1.65 [+0.67, +2.55]; retained +41.10 [+20.54, +63.85]%, lost 59% of oracle | net +7.75 (r 7.75, d 0.00) | net +5.69 (r 5.76, d 0.07); loss +2.69 [+1.21, +3.59]; over random +5.55 [+3.26, +7.34]; retained +67.34 [+53.43, +84.37]%, lost 32% of oracle |
| F | net +2.80 (r 2.81, d 0.01); loss +1.22 [+0.39, +2.80]; over random +2.79 [+1.18, +3.89]; retained +69.48 [+39.67, +87.44]%, lost 30% of oracle | net +5.64 (r 5.65, d 0.01); loss +2.11 [+1.09, +3.38]; over random +5.44 [+3.24, +6.89]; retained +72.09 [+55.30, +83.22]%, lost 27% of oracle | net +8.38 (r 8.38, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.04 block / 0.03 crossed): G: G>F>H (oracle F>H>G; argmax in oracle top set 0.00 block / 0.01 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.04 block / 0.38 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 1.00 block / 0.65 crossed)
R3 within-row differences: G: H-G -2.25 [-4.02, -0.76], F-G -1.10 [-2.45, -0.10], F-H +1.15 [-0.67, +3.14]; H: H-G +6.09 [+3.76, +7.89], F-G +4.03 [+1.61, +6.10], F-H -2.06 [-3.25, -0.87]; F: H-G +2.84 [+0.71, +4.88], F-G +5.59 [+3.13, +7.19], F-H +2.74 [+1.29, +3.91]

Saturated oracles at 10% (all +1 states fit in every pooled cell): G, H.


## Bank U U2B (SENSITIVITY, BF16-sourced states): pool W4, same-draw (hindsight), budget 20% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +4.02 [+2.06, +6.37] | +7.75 [+5.00, +10.98] | +8.53 [+5.20, +12.35] |
| random (same capacity) | +0.02 [-0.47, +0.53] | +0.39 [-0.29, +1.12] | +0.27 [-0.65, +1.18] |
| G | net +4.02 (r 4.02, d 0.00) | net +1.96 (r 2.72, d 0.76); loss +5.78 [+3.71, +8.20]; over random +1.57 [+0.71, +2.56]; retained +21.37 [+10.58, +34.03]%, lost 75% of oracle | net +3.07 (r 3.83, d 0.76); loss +5.46 [+3.42, +7.76]; over random +2.80 [+1.35, +4.62]; retained +33.86 [+19.35, +49.25]%, lost 64% of oracle |
| H | net +1.65 (r 2.00, d 0.35); loss +2.37 [+1.05, +4.13]; over random +1.63 [+0.73, +2.64]; retained +40.66 [+22.07, +62.87]%, lost 59% of oracle | net +7.75 (r 7.75, d 0.00) | net +5.72 (r 6.08, d 0.36); loss +2.81 [+1.52, +4.42]; over random +5.45 [+3.34, +8.02]; retained +66.01 [+52.11, +78.55]%, lost 33% of oracle |
| F | net +2.87 (r 3.01, d 0.14); loss +1.15 [+0.26, +2.39]; over random +2.85 [+1.35, +4.75]; retained +71.16 [+45.05, +92.92]%, lost 29% of oracle | net +5.82 (r 5.97, d 0.15); loss +1.92 [+0.90, +3.16]; over random +5.43 [+3.34, +8.00]; retained +73.87 [+58.53, +86.74]%, lost 25% of oracle | net +8.53 (r 8.53, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.04 crossed): G: G>F>H (oracle F>H>G; argmax in oracle top set 0.00 block / 0.05 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.00 block / 0.27 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 1.00 block / 0.77 crossed)
R3 within-row differences: G: H-G -2.06 [-3.99, -0.54], F-G -0.95 [-2.33, +0.13], F-H +1.11 [-0.64, +3.12]; H: H-G +6.10 [+3.79, +8.91], F-G +4.08 [+1.67, +6.90], F-H -2.02 [-3.48, -0.75]; F: H-G +2.96 [+0.79, +5.47], F-G +5.66 [+3.21, +8.37], F-H +2.71 [+1.16, +4.59]

Saturated oracles at 20% (all +1 states fit in every pooled cell): G, H, F.


## Bank U U2B (SENSITIVITY, BF16-sourced states): pool KV8, same-draw (hindsight), budget 5% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +2.16 [+0.59, +4.07] | +5.00 [+3.68, +5.00] | +5.00 [+3.68, +5.00] |
| random (same capacity) | +0.04 [-0.08, +0.17] | +0.20 [-0.04, +0.42] | +0.14 [-0.07, +0.35] |
| G | net +2.16 (r 2.16, d 0.00) | net +1.07 (r 1.16, d 0.09); loss +3.93 [+2.48, +4.71]; over random +0.87 [-0.00, +1.99]; retained +18.18 [-0.10, +42.84]%, lost 79% of oracle | net +1.83 (r 1.93, d 0.10); loss +3.17 [+1.47, +4.25]; over random +1.69 [+0.45, +3.12]; retained +34.82 [+10.83, +66.11]%, lost 63% of oracle |
| H | net +0.69 (r 0.69, d 0.00); loss +1.47 [+0.09, +3.11]; over random +0.65 [+0.01, +1.46]; retained +30.68 [+0.75, +86.14]%, lost 68% of oracle | net +5.00 (r 5.00, d 0.00) | net +4.33 (r 4.33, d 0.00); loss +0.67 [+0.00, +1.75]; over random +4.19 [+2.76, +4.79]; retained +86.15 [+63.49, +100.00]%, lost 13% of oracle |
| F | net +1.19 (r 1.19, d 0.00); loss +0.97 [+0.00, +2.36]; over random +1.15 [+0.34, +2.07]; retained +54.40 [+27.76, +100.00]%, lost 45% of oracle | net +4.21 (r 4.21, d 0.00); loss +0.79 [+0.00, +1.99]; over random +4.01 [+2.52, +4.68]; retained +83.47 [+57.27, +100.00]%, lost 16% of oracle | net +5.00 (r 5.00, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point True, draws 1.00 block / 0.66 crossed): G: G>F>H (oracle F=H>G; argmax in oracle top set 0.30 block / 0.33 crossed); H: H>F>G (oracle F=H>G; argmax in oracle top set 1.00 block / 0.84 crossed); F: F>H>G (oracle F=H>G; argmax in oracle top set 1.00 block / 0.84 crossed)
R3 within-row differences: G: H-G -1.09 [-2.92, +0.21], F-G -0.33 [-1.51, +0.22], F-H +0.76 [-0.47, +2.35]; H: H-G +4.31 [+2.92, +4.87], F-G +3.64 [+1.76, +4.57], F-H -0.67 [-1.76, +0.00]; F: H-G +3.01 [+0.69, +4.44], F-G +3.81 [+2.36, +4.57], F-H +0.79 [+0.00, +1.95]

Saturated oracles at 5% (all +1 states fit in every pooled cell): G.


## Bank U U2B (SENSITIVITY, BF16-sourced states): pool KV8, same-draw (hindsight), budget 10% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +2.16 [+0.59, +4.31] | +7.06 [+4.12, +9.51] | +7.25 [+4.12, +9.71] |
| random (same capacity) | +0.08 [-0.16, +0.33] | +0.39 [-0.08, +0.84] | +0.27 [-0.14, +0.71] |
| G | net +2.16 (r 2.16, d 0.00) | net +1.23 (r 1.48, d 0.24); loss +5.83 [+3.38, +7.92]; over random +0.84 [+0.01, +1.97]; retained +12.59 [+0.11, +30.09]%, lost 83% of oracle | net +1.95 (r 2.21, d 0.26); loss +5.30 [+2.92, +7.36]; over random +1.68 [+0.52, +3.25]; retained +24.04 [+8.55, +44.99]%, lost 73% of oracle |
| H | net +0.98 (r 1.02, d 0.04); loss +1.17 [+0.02, +3.03]; over random +0.91 [+0.03, +2.06]; retained +43.60 [+2.60, +97.56]%, lost 54% of oracle | net +7.06 (r 7.06, d 0.00) | net +6.07 (r 6.12, d 0.05); loss +1.18 [+0.03, +2.84]; over random +5.80 [+3.28, +8.16]; retained +83.02 [+60.34, +99.51]%, lost 16% of oracle |
| F | net +1.78 (r 1.78, d 0.00); loss +0.38 [+0.00, +1.68]; over random +1.70 [+0.50, +3.10]; retained +81.86 [+44.37, +100.00]%, lost 17% of oracle | net +6.11 (r 6.11, d 0.01); loss +0.95 [+0.00, +2.55]; over random +5.71 [+3.23, +7.95]; retained +85.70 [+62.81, +100.00]%, lost 14% of oracle | net +7.25 (r 7.25, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.30 block / 0.15 crossed): G: G>F>H (oracle F>H>G; argmax in oracle top set 0.30 block / 0.35 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.30 block / 0.52 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 1.00 block / 0.69 crossed)
R3 within-row differences: G: H-G -0.93 [-3.03, +0.50], F-G -0.20 [-1.59, +0.51], F-H +0.72 [-0.54, +2.40]; H: H-G +6.07 [+3.41, +8.51], F-G +5.09 [+2.35, +7.79], F-H -0.99 [-2.48, -0.01]; F: H-G +4.33 [+1.03, +7.26], F-G +5.48 [+2.94, +7.84], F-H +1.15 [-0.02, +2.93]

Saturated oracles at 10% (all +1 states fit in every pooled cell): G, H, F.


## Bank U U2B (SENSITIVITY, BF16-sourced states): pool KV8, same-draw (hindsight), budget 20% (crossed intervals)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +2.16 [+0.59, +4.31] | +7.06 [+4.12, +10.20] | +7.25 [+4.12, +10.59] |
| random (same capacity) | +0.16 [-0.31, +0.67] | +0.78 [-0.16, +1.69] | +0.55 [-0.27, +1.41] |
| G | net +2.16 (r 2.16, d 0.00) | net +1.56 (r 2.11, d 0.55); loss +5.50 [+3.32, +7.90]; over random +0.77 [+0.04, +1.78]; retained +12.30 [+0.59, +27.64]%, lost 78% of oracle | net +2.20 (r 2.78, d 0.58); loss +5.06 [+3.01, +7.49]; over random +1.65 [+0.58, +3.03]; retained +24.55 [+10.26, +42.68]%, lost 70% of oracle |
| H | net +0.98 (r 1.15, d 0.17); loss +1.18 [+0.14, +2.81]; over random +0.82 [+0.05, +1.90]; retained +41.25 [+4.87, +88.01]%, lost 54% of oracle | net +7.06 (r 7.06, d 0.00) | net +6.02 (r 6.25, d 0.23); loss +1.23 [+0.22, +2.83]; over random +5.47 [+3.28, +8.04]; retained +81.63 [+61.56, +96.40]%, lost 17% of oracle |
| F | net +1.83 (r 1.83, d 0.00); loss +0.33 [+0.00, +1.43]; over random +1.67 [+0.59, +3.09]; retained +83.41 [+49.40, +100.00]%, lost 15% of oracle | net +6.20 (r 6.23, d 0.03); loss +0.86 [+0.00, +2.25]; over random +5.41 [+3.24, +7.87]; retained +86.24 [+66.03, +100.00]%, lost 12% of oracle | net +7.25 (r 7.25, d 0.00) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.30 block / 0.17 crossed): G: F>G>H (oracle F>H>G; argmax in oracle top set 0.61 block / 0.50 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.30 block / 0.51 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 1.00 block / 0.71 crossed)
R3 within-row differences: G: H-G -0.60 [-3.08, +1.14], F-G +0.04 [-1.56, +1.13], F-H +0.64 [-0.61, +2.43]; H: H-G +6.08 [+3.40, +9.13], F-G +5.04 [+2.35, +8.24], F-H -1.04 [-2.50, -0.09]; F: H-G +4.37 [+1.07, +7.83], F-G +5.43 [+2.94, +8.43], F-H +1.06 [-0.08, +2.98]

Saturated oracles at 20% (all +1 states fit in every pooled cell): G, H, F.


## Bank U U2B (SENSITIVITY, BF16-sourced states): pool W4, split-half (mean of A->B and B->A), budget 5% (crossed intervals; ratios suppressed: noisy oracle)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +0.17 [-0.51, +0.76] | +0.55 [-0.42, +1.56] | +0.69 [-0.50, +2.25] |
| random (same capacity) | +0.01 [-0.09, +0.12] | +0.11 [-0.05, +0.28] | +0.08 [-0.12, +0.29] |
| G | net +0.17 (r 0.52, d 0.35) | net +0.62 (r 1.13, d 0.51); loss -0.07 [-0.87, +1.16]; over random +0.51 [-0.40, +1.11] | net +0.33 (r 1.07, d 0.74); loss +0.36 [-0.45, +1.80]; over random +0.25 [-0.67, +1.02] |
| H | net +0.21 (r 0.66, d 0.45); loss -0.03 [-0.80, +0.60]; over random +0.19 [-0.34, +0.83] | net +0.55 (r 1.01, d 0.46) | net +0.43 (r 1.15, d 0.72); loss +0.26 [-0.18, +1.01]; over random +0.35 [-0.79, +1.62] |
| F | net +0.14 (r 0.46, d 0.33); loss +0.04 [-0.71, +0.57]; over random +0.12 [-0.32, +0.70] | net +0.48 (r 0.98, d 0.50); loss +0.07 [-0.75, +0.53]; over random +0.37 [-0.58, +1.65] | net +0.69 (r 1.26, d 0.56) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: H>F>G (oracle F>H>G; argmax in oracle top set 0.27 block / 0.40 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.25 block / 0.59 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 0.73 block / 0.75 crossed)
R3 within-row differences: G: H-G +0.45 [-0.50, +1.18], F-G +0.16 [-0.74, +1.02], F-H -0.29 [-0.75, +0.31]; H: H-G +0.34 [-0.59, +1.33], F-G +0.22 [-0.71, +1.30], F-H -0.12 [-0.65, +0.63]; F: H-G +0.34 [-0.52, +1.54], F-G +0.55 [-0.49, +1.90], F-H +0.21 [-0.15, +0.78]


## Bank U U2B (SENSITIVITY, BF16-sourced states): pool W4, split-half (mean of A->B and B->A), budget 10% (crossed intervals; ratios suppressed: noisy oracle)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +0.14 [-0.81, +1.05] | +1.26 [-0.49, +2.83] | +1.72 [-0.66, +4.00] |
| random (same capacity) | +0.03 [-0.18, +0.25] | +0.21 [-0.10, +0.56] | +0.17 [-0.24, +0.57] |
| G | net +0.14 (r 0.80, d 0.66) | net +1.00 (r 1.83, d 0.83); loss +0.26 [-1.12, +1.93]; over random +0.79 [-0.44, +1.63] | net +0.56 (r 1.71, d 1.15); loss +1.15 [-0.58, +3.03]; over random +0.40 [-0.80, +1.41] |
| H | net +0.39 (r 1.19, d 0.80); loss -0.25 [-1.24, +0.80]; over random +0.36 [-0.54, +1.33] | net +1.26 (r 2.04, d 0.78) | net +0.97 (r 2.32, d 1.35); loss +0.75 [-0.09, +1.59]; over random +0.80 [-1.08, +2.65] |
| F | net +0.18 (r 0.94, d 0.76); loss -0.04 [-1.07, +0.80]; over random +0.15 [-0.59, +1.12] | net +1.30 (r 2.12, d 0.82); loss -0.05 [-1.19, +0.79]; over random +1.09 [-0.74, +2.82] | net +1.72 (r 2.76, d 1.04) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: H>F>G (oracle F>H>G; argmax in oracle top set 0.00 block / 0.43 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.52 block / 0.56 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 0.73 block / 0.80 crossed)
R3 within-row differences: G: H-G +0.86 [-0.50, +1.83], F-G +0.42 [-0.85, +1.56], F-H -0.44 [-1.17, +0.42]; H: H-G +0.87 [-0.81, +2.47], F-G +0.58 [-1.04, +2.31], F-H -0.29 [-1.17, +1.06]; F: H-G +1.12 [-0.58, +2.78], F-G +1.54 [-0.62, +3.28], F-H +0.41 [-0.37, +1.31]


## Bank U U2B (SENSITIVITY, BF16-sourced states): pool W4, split-half (mean of A->B and B->A), budget 20% (crossed intervals; ratios suppressed: noisy oracle)

| select by \ execute | G (action only (BQ)) | H (continuation (QB)) | F (both (BB)) |
|---|---|---|---|
| oracle (select by Y) | +0.17 [-0.92, +1.18] | +1.65 [-0.43, +3.70] | +2.14 [-0.61, +5.04] |
| random (same capacity) | +0.06 [-0.37, +0.50] | +0.43 [-0.21, +1.12] | +0.34 [-0.47, +1.15] |
| G | net +0.17 (r 1.18, d 1.01) | net +1.10 (r 2.47, d 1.36); loss +0.55 [-1.00, +2.31]; over random +0.68 [-0.43, +1.58] | net +0.71 (r 2.45, d 1.74); loss +1.43 [-0.56, +3.61]; over random +0.37 [-0.77, +1.36] |
| H | net +0.38 (r 1.64, d 1.25); loss -0.22 [-1.35, +0.81]; over random +0.33 [-0.66, +1.37] | net +1.65 (r 2.97, d 1.31) | net +1.18 (r 3.29, d 2.12); loss +0.97 [-0.06, +1.82]; over random +0.84 [-1.10, +2.96] |
| F | net +0.13 (r 1.36, d 1.23); loss +0.04 [-1.06, +0.84]; over random +0.07 [-0.84, +1.20] | net +1.75 (r 3.06, d 1.31); loss -0.10 [-1.37, +0.89]; over random +1.32 [-0.75, +3.29] | net +2.14 (r 3.80, d 1.66) |

R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point False, draws 0.00 block / 0.00 crossed): G: H>F>G (oracle F>H>G; argmax in oracle top set 0.27 block / 0.50 crossed); H: H>F>G (oracle F>H>G; argmax in oracle top set 0.52 block / 0.58 crossed); F: F>H>G (oracle F>H>G; argmax in oracle top set 0.73 block / 0.81 crossed)
R3 within-row differences: G: H-G +0.93 [-0.43, +2.20], F-G +0.54 [-0.87, +1.92], F-H -0.39 [-1.29, +0.52]; H: H-G +1.27 [-0.75, +3.32], F-G +0.79 [-1.07, +2.99], F-H -0.48 [-1.56, +1.10]; F: H-G +1.62 [-0.62, +3.71], F-G +2.02 [-0.53, +4.18], F-H +0.40 [-0.63, +1.55]


## Per cell, same-draw, budget 10%: executed net (oracle on the diagonal) and BF16-decision proxy per selected state

| frame | cell | G->G | G->H | G->F | H->G | H->H | H->F | F->G | F->H | F->F | proxy BF16 dec/selected (G, H, F; diag) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| U1 | q4:gptq_w4_d1 | +4.31 | +1.32 | +2.08 | +1.52 | +4.71 | +2.70 | +2.38 | +2.79 | +4.71 | 1.0, 6.43, 6.45 |
| U1 | q4:awq_w4 | +2.75 | +1.49 | +1.33 | +1.14 | +8.24 | +6.61 | +1.16 | +6.68 | +7.84 | 1.0, 6.77, 7.76 |
| U1 | q8:gptq_w4_d1 | +3.14 | +1.31 | +1.06 | +1.62 | +3.53 | +2.47 | +1.28 | +2.38 | +4.31 | 1.0, 8.35, 9.38 |
| U1 | q8:awq_w4 | +5.49 | +1.81 | +4.20 | +2.06 | +5.49 | +4.81 | +4.30 | +4.67 | +7.45 | 1.0, 8.29, 8.33 |
| U1 | pool W4 | +3.92 | +1.48 | +2.17 | +1.59 | +5.49 | +4.15 | +2.28 | +4.13 | +6.08 | 1.0, 7.46, 7.98 |
| U1 | q4:kvq_int8 | +1.57 | +0.21 | +0.53 | -0.04 | +7.06 | +6.21 | +0.41 | +6.29 | +7.84 | 1.0, 6.92, 7.71 |
| U1 | q8:kvq_int8 | +1.96 | +0.20 | +1.37 | +0.06 | +5.10 | +5.16 | +1.16 | +5.09 | +7.06 | 1.0, 10.05, 10.79 |
| U1 | pool KV8 | +1.76 | +0.20 | +0.95 | +0.01 | +6.08 | +5.69 | +0.79 | +5.69 | +7.45 | 1.0, 8.49, 9.25 |
| U2B | q4:gptq_w4_d1 | +3.92 | +2.12 | +1.96 | +1.96 | +7.84 | +4.67 | +2.03 | +4.81 | +6.27 | 1.0, 8.18, 8.7 |
| U2B | q4:awq_w4 | +2.75 | +1.27 | +1.99 | +1.11 | +7.06 | +5.46 | +1.95 | +5.53 | +7.84 | 1.0, 7.4, 8.5 |
| U2B | q8:gptq_w4_d1 | +3.53 | +1.60 | +3.27 | +1.57 | +7.84 | +6.71 | +3.13 | +6.66 | +9.41 | 1.0, 8.71, 8.29 |
| U2B | q8:awq_w4 | +5.88 | +2.10 | +4.46 | +1.99 | +8.24 | +5.92 | +4.07 | +5.56 | +10.00 | 1.0, 7.98, 7.52 |
| U2B | pool W4 | +4.02 | +1.77 | +2.92 | +1.66 | +7.75 | +5.69 | +2.80 | +5.64 | +8.38 | 1.0, 8.07, 8.25 |
| U2B | q4:kvq_int8 | +1.96 | +1.31 | +1.24 | +1.14 | +7.45 | +5.84 | +1.21 | +5.93 | +6.67 | 1.0, 6.27, 7.47 |
| U2B | q8:kvq_int8 | +2.35 | +1.16 | +2.66 | +0.83 | +6.67 | +6.30 | +2.35 | +6.28 | +7.84 | 1.0, 10.35, 11.08 |
| U2B | pool KV8 | +2.16 | +1.23 | +1.95 | +0.98 | +7.06 | +6.07 | +1.78 | +6.11 | +7.25 | 1.0, 8.31, 9.27 |
| P | q4:gptq_w4_d1 | +10.00 | +2.50 | +5.69 | +2.61 | +8.71 | +2.53 | +5.95 | +2.52 | +10.00 | 1.0, 8.64, 8.94 |
| P | q4:awq_w4 | +10.00 | +4.37 | +5.69 | +4.93 | +10.00 | +4.66 | +5.79 | +4.21 | +10.00 | 1.0, 10.89, 10.31 |
| P | q8:gptq_w4_d1 | +10.00 | +2.82 | +6.55 | +3.54 | +6.86 | +3.65 | +5.58 | +2.45 | +10.00 | 1.0, 15.77, 15.57 |
| P | q8:awq_w4 | +10.00 | +5.05 | +5.57 | +6.28 | +9.80 | +5.25 | +5.63 | +4.27 | +10.00 | 1.0, 15.02, 14.45 |
| P | pool W4 | +10.00 | +3.69 | +5.87 | +4.34 | +8.84 | +4.02 | +5.74 | +3.36 | +10.00 | 1.0, 12.58, 12.32 |
| P | q4:kvq_int8 | +9.78 | +1.52 | +8.09 | +1.56 | +4.05 | +1.93 | +7.06 | +1.62 | +10.00 | 1.0, 6.31, 7.21 |
| P | q8:kvq_int8 | +9.47 | +1.76 | +6.56 | +1.88 | +3.86 | +1.74 | +6.44 | +1.49 | +10.00 | 1.0, 13.45, 13.62 |
| P | pool KV8 | +9.63 | +1.64 | +7.33 | +1.72 | +3.95 | +1.84 | +6.75 | +1.56 | +10.00 | 1.0, 9.88, 10.41 |

Inputs: {"bank_u_inputs_digest": "bc23f0bbcf35e9876142174010bbd18dfbce107aebf00a67f0a6aa58039608ae", "bank_u_missing_rows": 0, "bank_p_units_digest": {"q4:gptq_w4_d1": "d4b8404cc48c5025", "q4:awq_w4": "ed25a43c6af22805", "q4:kvq_int8": "d6f6a2db66ebffd7", "q8:gptq_w4_d1": "55103355340116c3", "q8:awq_w4": "4682d291cedfd736", "q8:kvq_int8": "06e9c3bf486b6790"}}

## Sources (sha256)

- `analysis/fork/label_transfer.py` 6a4f26e2bfa13a919a671606e51e6e1144b1c8de4c489e09a23f77dfc3c3a0d1
- `analysis/fork/label_transfer_report.py` 30c5d30545d6e6288c3ce0a0d0588a7a9ba38f2e302909db48ce06b100250d1a
- `analysis/fork/label_transfer_selftest.py` 1f856e4c888b17b9d4ad7bedd678bed9cd5d117d12cb9f4d31046c91e5b148ad
- `analysis/fork/analyze_bank_u.py` 2ae117f628ba9ce3ba8cf3c3cef8937be4ea3ad3d8047c8e64b6af6947ce3e2d
- `analysis/fork/offdiag_null.py` 897d3b61c4e918c5c16bc633265b3e0ce82958d0817e9e88017d85e0159b3112
- `analysis/fork/analyze_dev.py` 5851a57b1a7b6199a2e9ddb113b85df33faeefe49980ff03a158857e80fda372
- `analysis/fork/task_fragility.py` cbb15f23b5d5f8a4c37b23892da8729665ae87b94dcd315ae88b653980174111
- `docs/insights/LABEL_TRANSFER_POSTHOC.md` aa495cd2bf4752f52c5d7305fc29063c8b8b7c375a459b899bc5b38f874b1256
