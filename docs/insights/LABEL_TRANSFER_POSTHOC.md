# Upgrade-label transfer matrix (label-transfer-v1)

**TL;DR** EXPLORATORY, POST HOC. Every input below has already been seen. This is a hindsight diagnostic of label mismatch, not a deployable router. It asks a budgeted question: if states are chosen for upgrade with the gain label of one upgrade mode and a different mode is then executed, how much of that executed mode's own oracle gain is lost? It also asks whether the selection label changes which of the three modes ranks best.

Written 2026-10-05, before any number in this file was computed. The analysis script and its sha256 are recorded in §9 (appended after the selftest passes).

## 1. Labels (per state with all four arms BB, BQ, QB, QQ)

- G = Y_BQ - Y_QQ: replace only the current action; Q continues.
- H = Y_QB - Y_QQ: Q's action stands; B takes over the continuation.
- F = Y_BB - Y_QQ: replace the action and the continuation.
- For an executed mode Y in {G, H, F}: rescue = 1[Y = +1], damage = 1[Y = -1], net = Y.
- Reporting scale: share of all states in the frame (pp), not of the selected states.

## 2. Frames (loaded only through existing loaders)

- **PRIMARY: Bank U U1** (own-trajectory ordinary states, outcome-independent hash sampling, FORK_PROTOCOL §15 amendment 1).
  - Loaded with `analyze_bank_u.load`. Rows whose four Y are incomplete are already dropped there; counts are reported.
  - Cells: q4/q8 x {gptq_w4_d1, awq_w4, kvq_int8}; blocks f01 to f03; 85 retail/airline tasks.
  - Bank U reuse rows are used as loaded. The one token-different reuse row was measured and does not change (analysis/fork/reuse_audit/REUSE_FIX_RESULT.md).
- **SENSITIVITY: Bank U U2B** (BF16-sourced shared states), same loader and cells. Never pooled with U1.
- **SECONDARY: Bank P** (dev first-divergence states). Loaded with `offdiag_null.load_tau2` (analyze_dev admission over the analyze_ghf roots; `analysis/fork/holdout/` is never opened).
  - Same-draw frame: the divergent states, which have all four arms, in retail/airline (telecom excluded), cells as above where present.
  - Split-half frame: the dev_all convention. A non-divergent unit contributes 0 to every label (no intervention possible), so task scores are means over all of the task's units.
- **Pools.** W4 = q4/q8 x {gptq_w4_d1, awq_w4}, equal cell weight, restricted to the blocks common to the pooled cells. KV8 cells are reported per cell and as a 2-cell pool.

## 3. Selection

- Budgets b in {5%, 10%, 20%} of the states in the frame. The capacity is b x N and is not rounded. A fractional capacity is the expectation over randomising between floor and ceil.
- Budgets count states, not BF16 compute. G spends 1 BF16 decision per selected state. H and F spend a whole continuation.
  - BF16 decisions per selected state are reported as a PROXY: the remaining decisions of the source Q trajectory (G: 1; H: n_decisions - t - 1; F: n_decisions - t; t is 0-based).
  - The true B-continuation decision counts are not exposed by the existing loaders, so they are unavailable here.
- Rule: select the top-b states by the selection label X. The budget is always filled: after the X = +1 states, X = 0 states, then X = -1 states.
- **Ties.** Within the boundary tie group every state is selected with equal probability. The expected executed rescues, damages and net are computed analytically: inclusion probability p = clip((capacity - weight strictly above) / weight of the tie group, 0, 1). There is no simulation noise.
- **Oracle for Y** = select by Y itself. Loss(X -> Y) = oracle_Y - executed(X -> Y), in pp, and as % of oracle_Y (undefined when oracle_Y <= 0).
- The same rule is applied with bootstrap multiplicities as weights, so capacity = b x (sum of weights) in each draw.

## 4. Same-draw (hindsight) matrix

- Labels and outcomes share the QQ arm, and selection uses the outcomes being evaluated. This is a hindsight upper-bound diagnostic of label mismatch, not a prediction.
- For each frame, cell, pool and budget: the 3 x 3 matrix of executed net, rescues, damages, loss and loss %, plus the oracle row (the diagonal).

## 5. Split-half variant (closer to deployment)

- Block halves: half(b) = int(sha256('frag-v1|' + b), 16) mod 2, the existing rule and split file of task_fragility.py, fixed before outcomes.
  - Bank U: half A = {f01, f03}, half B = {f02}.
- Rank TASKS by their mean X over the defining half's blocks (per cell; a missing state counts as 0, as in §2).
- Select the top-b tasks (capacity b x T, same analytic tie rule).
- Evaluate Y on the other half: the sum of Y over the selected tasks' states in that half, divided by all states in that half (pp).
- Oracle for Y = the same procedure with X = Y. Both directions are reported, plus their mean.
- This is a same-task replication across blocks (nonces), not prediction on new tasks.

## 6. Intervals (95% percentile, B = 2000, seed 20261001)

- **Same-draw.** analyze_dev.Boot draws (block bootstrap Vb; crossed task x block Wc x Vc), one Boot per frame over the union of its cells, so cells and pools share draws. The selection is recomputed inside every draw.
  - Bank U has K = 3 blocks, so its block bootstrap is coarse (at most 10 distinct resamples). The crossed interval is the one to read there.
- **Split-half.** Draws from default_rng(20261001):
  - block scheme: defining-half and evaluation-half blocks resampled within their halves;
  - crossed scheme: also tasks resampled.
  - A 1-block half cannot be resampled, so for Bank U the block scheme varies only the 2-block half.

## 7. Readings (numbers only; no verdict words)

- R1: for each budget and off-diagonal (X, Y), the loss in pp, its % of oracle_Y, and whether the 95% interval excludes 0 (reported as "CI excludes 0: yes/no", block and crossed separately).
- R2: for each selection label X, the ordering of the executed nets of G, H, F (point estimate), whether it equals the ordering on the oracle diagonal, and the bootstrap share of draws in which the argmax mode under X equals the oracle argmax mode.
- R3: within-row differences of executed net (H - G, F - G, F - H) with intervals.

## 8. Scope and limits

- No new router is proposed or validated. The labels are hindsight labels.
- Budgets are state budgets, not equal compute.
- Binary outcomes produce large tie groups; at the 20% budget most of the selection can be tie-filling.
  - The counts of X = +1 states per frame are reported so this is visible.
- Cross-cell comparisons are descriptive (each cell has its own states; for Bank P, its own first-divergence selection).

## 9. Script record (appended after the selftest)

- 2026-10-05: selftest `python analysis/fork/label_transfer.py --selftest` PASS (tie-break vs exact enumeration and Monte Carlo, weights = replication, 1-D vs 2-D path, oracle identity, frame counts, hand-computed split-half case).
- `analysis/fork/label_transfer.py` sha256 d300195ac10a783ed3bb2a2f46796b6c5719be36475aaf000d0a07429eb933bb
- `analysis/fork/label_transfer_report.py` sha256 90260bf352f2bf2366115ba638d01832bbfdf8776a4ae5d7456eda9bacdf4fc4
- `analysis/fork/label_transfer_selftest.py` sha256 f42da9fd0fe3d6e6c900f368869c742e0b02a250f67faf35f8178241eb3aa1ce
- Run: git HEAD 224c6cea37850f6aa673f49d9689a66bbc152bad, B = 2000, seed 20261001 -> `analysis/fork/out/label_transfer_20261005T184709Z.{json,md}`.
- Note added with the record (no rule change): for U2B the BF16-decision proxy uses the BF16 source trajectory's remaining decisions, not a Q trajectory's.

## 10. Amendment 2026-10-05b (after verifier review of run 20261005T184709Z; EXPLORATORY, POST HOC; written before the rerun)

Reason: two independent verifier reviews. No label, frame, budget or tie rule changes. Changes are to the reference, the bootstrap grouping and the reporting.

- **R1 (same-draw).** The oracle maximises the weighted sum of Y in every draw, so a same-draw loss is >= 0 by construction (the selftest asserts it). "CI excludes 0" for a same-draw loss is therefore not reported as evidence. Added reference: random selection at the same capacity (all scores tied, same analytic rule; expectation b x weighted mean of Y). Reported per cell: excess over random = executed - random (can be negative, with intervals) and retained share = (executed - random) / (oracle - random). Only the split-half loss can be negative.
- **R2 ties.** Orderings write ties within 1e-9 as "=" (e.g. "G=F>H"). The argmax match counts the probability that the argmax under X (uniform among X's tied top modes) lies in the oracle's tied top set. The share of draws with a tied oracle top is reported.
- **Ratios.** Loss % of oracle and retained share are reported only for the same-draw frame, with the share of draws dropped because the denominator is <= 0. They are suppressed in split-half tables (the split-half oracle is often <= 0 in a draw).
- **Bootstrap grouping.** analyze_dev.Boot (same-draw) and the split-half draws are built per pool (W4, KV8) over that pool's own blocks and tasks, shared by the pool's cells. Bank U is unaffected (all cells share f01 to f03). For Bank P W4 this removes the two KV8-only blocks from the resampling set and from split-half half 0. Pooled split-half cells must have one common block set (asserted).
- **Split-half BF16 proxy.** Divided by the weighted count of divergent evaluation-half units of the selected tasks (was all units, which diluted it).
- **Saturation.** Each same-draw pool table lists the oracles whose +1 states all fit in the capacity of every pooled cell. Bank U W4: all three oracles saturate by 10%; at 20% the off-diagonals differ from 10% only by tie-fill among X = 0 states.
- **Notes (no rule change).** (a) The split-half block and crossed schemes reuse the same block draws; the crossed scheme adds task resampling. (b) Point estimates are pooled unit sums over the frame; analyze_dev.Boot uses the mean of block means. They are identical for Bank U (85 states per block) and differ slightly for the Bank P same-draw frame, where divergent counts vary by block. (c) The Bank P split-half tables are on the dev_all scale (pp of all units, non-divergent units count 0), now labelled so, with both block and crossed intervals shown.

## 11. Script record for amendment 2026-10-05b

- 2026-10-05: selftest PASS (adds: random row = b x weighted mean label; split-half random row; undiluted split-half BF16 proxy with a non-divergent unit present; tie-aware ordering "G=F>H").
- `analysis/fork/label_transfer.py` sha256 6a4f26e2bfa13a919a671606e51e6e1144b1c8de4c489e09a23f77dfc3c3a0d1
- `analysis/fork/label_transfer_report.py` sha256 30c5d30545d6e6288c3ce0a0d0588a7a9ba38f2e302909db48ce06b100250d1a
- `analysis/fork/label_transfer_selftest.py` sha256 1f856e4c888b17b9d4ad7bedd678bed9cd5d117d12cb9f4d31046c91e5b148ad
- Run: git HEAD 224c6cea37850f6aa673f49d9689a66bbc152bad (working tree, uncommitted), B = 2000, seed 20261001 -> `analysis/fork/out/label_transfer_20261005T185537Z.{json,md}`. Supersedes 20261005T184709Z for reading; that file is kept.
- Checks: Bank U U1/U2B same-draw numbers are identical to the previous run (Bank U pools already shared f01 to f03). Bank P W4 now resamples its own 20 blocks (KV8: 22, 84 tasks); split-half W4 half 0 has 11 blocks, half 1 has 9.
- Caveat on the new reference: in the same-draw frame, "over random" is still partly mechanical, because the labels share the QQ arm (X = +1 implies Y_QQ = 0, so every mode's outcome there is >= 0). Only the split-half rows test label transfer without that coupling.
