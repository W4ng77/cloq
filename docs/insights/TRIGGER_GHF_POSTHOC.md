# Frozen Q-only trigger read under three upgrade modes (G / H / F): protocol

Status: EXPLORATORY, POST HOC. Written 2026-10-05 before `analysis/fork/trigger_ghf.py` was run on real data.
All Bank U outcomes used here (Y_BB, Y_BQ, Y_QB, Y_QQ on f01/f02/f03) have already been seen (W88, W98,
oracle_trigger_20261002T024423Z). Nothing below is a prospective test, and nothing here is a deployable router.

## Question

The frozen trigger (manifests/fork/token_trigger_rule_v1.json, sha256 335e737d...; score S_mm, per-cell thresholds at
5/10/20%) was chosen on f01 for one-step action replacement (G). Keep its selections fixed and read, on the same states:

- G = Y_BQ - Y_QQ: replace the current action only, Q continues (BF16 cost: one decision).
- H = Y_QB - Y_QQ: Q's action stands, B takes over the continuation (BF16 cost: the rest of the episode).
- F = Y_BB - Y_QQ: replace action and continuation (BF16 cost: one decision + the rest of the episode).

Rescue = label +1, damage = label -1, net = sum of labels (also in pp of all states in the frame).
Two questions are kept apart: (a) did the trigger pick states where some intervention helps (worth intervening),
(b) given those states, which intervention helps there (mode dependence).

## Frames (fixed)

- PRIMARY: Bank U sub-bank U1, validation blocks f02 + f03, 6 cells (q4/q8 x gptq_w4_d1/awq_w4/kvq_int8), 1020 rows:
  exactly the W98 validation rows. Loaded only via analyze_token_mech.load()/features() (existing loader).
  The W98 primary numbers (selected 50/114/222, G net +4/+2/+5, p .0345/.4169/.2617) must reproduce first, else abort.
- SECONDARY A: U1 f01 (the development block on which the rule was chosen with a G criterion; in-sample for G,
  H and F were not used in the choice). Labelled in-sample.
- SECONDARY B: U2B and U2Q on f02 + f03 with the same frozen thresholds (as W88/W98 secondary rows). Never pooled with U1.
- Coverage: every row in each frame is checked for all four arms as integers in {0,1}. Rows lacking an arm are counted
  and excluded from that mode only; the count is reported. No imputation, no substitution of another frame.

## Selections (fixed, nothing refit)

- Trigger: escalate iff S_mm > frozen threshold for the cell and rate (analyze_token_mech.escalate semantics, imported).
- Random: matched-count random trigger, same per-cell count m_c; reported as its exact expectation m_c * mean(label in
  cell); exact one-sided hypergeometric p of trigger net >= observed (analyze_token_mech.null_dist / convolve).
- Oracle (hindsight, per mode X): per cell, the m_c rows with the highest label X. Tie rule (fixed): within the boundary
  tie class, uniform random tie-break; reported as the exact expectation. The own-mode oracle net is tie-invariant and
  must equal min(m, R) - max(0, m - (N - D)) (identity, checked). Its expected G/H/F in the other two modes under the
  uniform tie-break is reported as a secondary column (a cross-label read, not Analysis 1).

## Budgets

5%, 10%, 20% = the frozen per-cell thresholds. These are state-selection budgets, not equal BF16 compute: H and F use
BF16 for the rest of the episode. A descriptive cost proxy is reported: mean (n_decisions - t) over selected states
(decisions remaining on Q's own trajectory after the state; not the realised BF16 continuation length).

## Statistics

Per frame x rate x mode: selected, rescues, damages, net (count and pp of frame rows), random expectation,
trigger - random, exact p; oracle net and trigger share of oracle net. Paired mode contrasts on the SAME selected
rows: net_H - net_G, net_F - net_G, net_F - net_H (random-adjusted versions also reported).
Selection quality: count of selected rows where some arm beats QQ (max(G,H,F) > 0) vs its random expectation;
forced-intervention hindsight best mode per selected row, sum of max(G,H,F).

Intervals (primary frame), B = 2000, seed 20261005, percentile 95%:
- task-cluster bootstrap (resample tasks; each task brings all its rows across cells and both blocks; per-cell m_c
  and random expectation recomputed with bootstrap weights; selections fixed). Fixed task pool / new-task reading.
- crossed task x block bootstrap (tasks and the 2 blocks resampled independently, row weight = product of counts).
  With k = 2 blocks a block-only bootstrap is degenerate and is not reported; the crossed interval carries the block
  component.
Multiplicity: Holm over the 9 trigger-vs-random exact p values (3 rates x 3 modes), reported alongside raw p.

## Readings (fixed in advance)

- "Resolved" requires both the task and the crossed 95% intervals to exclude 0; otherwise "not resolved".
- R1 (worth intervening): trigger's some-arm-beats-QQ count vs random expectation.
- R2 (mode dependence): a paired contrast resolved at a rate means the same selection has different net value
  depending on the executed intervention. Unresolved contrasts are reported as such, not as equality.
- R3 (trigger vs random per mode): resolved positive in a mode H or F but not G would say the selection signal is
  better matched to a different intervention; no mode resolved means the rule's ability is limited at these budgets
  regardless of intervention.
- Oracle gap per mode bounds what a perfect hindsight selector of that mode would add; it is not a policy.
- Any statement uses "post hoc, exploratory"; no claim that a new routing rule is proposed or validated.

## Amendments (appended, dated)

### 2026-10-05: run record (appended after the run; protocol text above unchanged)

- Selftest `analysis/fork/trigger_ghf_selftest.py` (sha256 13c330d7ee553806f6f1d775506c80fa50706b2f329bf8689e26b4faa064b678)
  passed before the real run: tie-break expectation vs exhaustive enumeration, oracle identity, frame counts with
  missing arms, bootstrap point = direct point, exact random expectation, Holm.
- Scripts: `analysis/fork/trigger_ghf.py` sha256 d92a3d678efc3d7e4898fae7583f67bb7901108b8fc1bb94c3407a227a34a27b;
  `trigger_ghf_core.py` sha256 fc7a4b3ad14905250dd2e0e1c31a3a9e109671778b52df2023f314984851a71e;
  `trigger_ghf_report.py` sha256 c873f0b2a4823744c7262384fe261f228ead51b74e0fb491159f17eacab8be58.
- Output `analysis/fork/out/trigger_ghf_20261005T184146Z.{md,json}`; git HEAD 224c6cea37850f6aa673f49d9689a66bbc152bad;
  B = 2000; seed = 20261005. W98 primary reproduced (50/114/222, +4/+2/+5, p .0345/.4169/.2617).
- Coverage: every frame has all four arms on every row (U1 f02+f03 1020/1020; U1 f01 510/510; U2B 1020/1020;
  U2Q 240/240). Nothing excluded or imputed.
- Deviation from the text above: the some-arm-beats-QQ random expectation is reported (bootstrap-adjusted) for the
  primary frame only; secondary frames show the raw count.
- Reading (post hoc): no mode resolves trigger minus random on the primary frame (H at 20%: +0.60 pp, task interval
  [+0.04, +1.18] but crossed [-0.20, +1.41]; Holm(9) min 0.31). No paired mode contrast resolves. The trigger does not
  pick states where some arm beats QQ more often than random. Oracle cross-read: the G-chosen oracle set carries only
  +12 to +14 H net and +19 to +22 F net, vs +47 to +59 (H) and +50 to +72 (F) for the matched-mode oracles.

### 2026-10-05 b: verifier fixes and rerun (appended; protocol text and amendment above unchanged)

- Interval naming correction (supersedes the label at "Intervals", line 57): the task interval is a new-task reading
  conditional on the 2 observed blocks; the crossed interval is also a new-task reading. No fixed-pool (block) interval
  exists with K = 2, so this analysis has no fixed-task-pool interval (analyze_dev Boot reserves "fixed task pool" for
  the block bootstrap). Boot docstring corrected the same way.
- Code checks added: own-mode oracle net asserted equal to min(m, R) - max(0, m - (N - D)) per cell on the real data
  (previously selftest only); score-row join keys and bootstrap keys asserted unique; "resolved" now computed from
  unrounded percentile bounds (no flag changed: F - G at 5% has upper bound exactly 0 from discrete counts).
- Reporting: realised selected share added (primary 50/114/222 of 1020 = 4.9/11.2/21.8%; the budgets are the frozen
  f01 thresholds, not exact quotas). Cost proxy convention: n_decisions - t with t 0-indexed, so it counts Q decisions
  from the state onward including the current one (minimum 1). Count columns relabelled "random net (count)" and
  "trig - rand (count)". Oracle cross-read now shows r / d / net per column mode plus the matched-count random net,
  with the caveat: hindsight, no interval, trigger-allocated budget (per-cell m_c), tie-filled from label-0 rows beyond
  R_X, H/F overlap partly mechanical (shared B continuation); not the label-transfer matrix and not Analysis 1 evidence.
- Rerun: selftest (sha256 13c330d7ee553806f6f1d775506c80fa50706b2f329bf8689e26b4faa064b678, unchanged) passed, then
  `trigger_ghf.py` sha256 d2fa1b4d57742448f7fdf77d48e44f47d8e269308f8144a1e57b2c376b13b16e;
  `trigger_ghf_core.py` sha256 2b719be6339db684f098fda8e4d29179da9b62332375030aa616fd1f5937e878;
  `trigger_ghf_report.py` sha256 1aa7d8e13bc2979a61105f5aa0acd6933adf4cbaf2a452025b52105a8bf440d1.
  Output `analysis/fork/out/trigger_ghf_20261005T185154Z.md` (sha256 dd431ad12b1e3235dd377b3e0cca31f3b16992d6ca40bbae2b3d4a71cf52d820)
  and `.json` (sha256 9aa2f91a5ead6f3c22ffd6160de62e0fc59124cbac767f1f552c3cc8822b1953); git HEAD
  224c6cea37850f6aa673f49d9689a66bbc152bad; B = 2000; seed = 20261005. All point values, exact p, oracle values and
  bootstrap intervals are identical to the 20261005T184146Z run; the earlier output is superseded for citation.
- Reading, reworded per R2 (supersedes the wording of the reading in the run record above; post hoc, exploratory):
  trigger minus random is not resolved in any mode on the primary frame. Paired mode contrasts on the same selection
  are unresolved at every rate; the data cannot distinguish the modes at these budgets (not evidence that they are
  equal). The selected states are not resolved better than random on "some arm beats QQ" (adjusted +0.14/+0.06/+0.29
  pp, all intervals include 0). Oracle cross-read: the G-chosen hindsight set carries +12.4 to +13.6 H net and +19.2 to
  +21.8 F net, well above matched random (H -0.27 to -1.08, F -0.28 to +0.28) but below the matched-mode oracles
  (+47 to +59 H, +50 to +72 F); partly tie-fill, no interval, not a label-transfer result.
