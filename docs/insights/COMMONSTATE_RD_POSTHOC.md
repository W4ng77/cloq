# Common-state BF16 vs Q' rescue/damage decomposition (Analysis 3): EXPLORATORY, POST HOC

**TL;DR** At the same common states and the same continuation controller, split the published common-state net difference
K(c) = Δ_{BF16−d1}(c) − Δ_{d2−d1}(c) into extra rescues (r_B − r_Q') and extra damages (d_B − d_Q'). Q' = W4-d2 (the
same-precision substitute). No new GPU runs; the existing loader and interval machinery are reused unchanged. Every
number here is EXPLORATORY, POST HOC: the outcomes were already read in the published common-state readings
(`analysis/fork/out/commonstate_q8ext_20261003T231159Z.*`, `commonstate_q4_20261004T001159Z.*`). Nothing here changes
or adds to those confirmatory readings.

Written 2026-10-05, before computing anything in this file's scope. Script: `analysis/fork/commonstate_rd.py`
(selftest `analysis/fork/commonstate_rd_selftest.py`); sha256 appended below after the run.

## 1. Frames (fixed)

- **States.** Exactly the analysis sets of the published readings, loaded through `analyze_commonstate.load` with the
  same manifests, admission, block quarantine and freeze:
  - q8: design `q8ext`, blocks f01-f06, expected n = 510 states, 85 tasks;
  - q4: design `q4`, blocks f02-f03 (f01 quarantined, errata E-2), expected n = 170 states, 85 tasks.
  The script asserts these counts. No other subset (no D2.1 sensitivity set, no a_d2 ≠ a_BF16 subset) is used.
- **Cells.** model ∈ {q8, q4} × continuation c ∈ {BF16, d1}. Baseline action = d1 (the deployed W4 action) under the
  same c. "Pooled" = the continuation average (as K̄ in the published analysis), within each model. The published
  analysis does not pool q4 with q8 (separate prospective analyses, different k), so neither does this one.

## 2. Estimands (per state, then equal weight per task within block, then mean over blocks, as §5 of the protocol)

With Y_s = Y(source s, continuation c) and the d1 baseline Y_1:
- r_B = 1[Y_BF16 = 1, Y_1 = 0], d_B = 1[Y_BF16 = 0, Y_1 = 1]; r_Q' = 1[Y_d2 = 1, Y_1 = 0], d_Q' = 1[Y_d2 = 0, Y_1 = 1].
- net_B = r_B − d_B = Δ_{BF16−d1}(c); net_Q' = r_Q' − d_Q' = Δ_{d2−d1}(c).
- Extra rescues XR = r_B − r_Q'; extra damages XD = d_B − d_Q'; net difference XN = XR − XD = K(c).
  Identity XN = K(c) holds state by state; the script asserts it per state and asserts that the point estimate of
  K(c) and K̄ equal the published JSON values exactly (float equality), and that the published r, d of the
  BF16-d1 and d2-d1 contrasts are reproduced.
- Descriptive cross-tab (counts, not weighted): among states with Y_1 = 0: rescued by both, BF16 only, Q' only,
  neither; among Y_1 = 1: damaged by both, BF16 only, Q' only, neither. XR's numerator is (BF16 only − Q' only)
  among Y_1 = 0 states, before weighting.

## 3. Budgets, tie rule, oracle

Not applicable to this analysis: no state is selected, ranked or budgeted, so there are no ties and no oracle. These
items belong to Analyses 1 and 2. The selftest checks the decomposition identity, the frame counts and the
cross-tab bookkeeping instead.

## 4. Intervals (named, reused unchanged)

`analyze_commonstate.estimate`: (a) t over the k block means (df = k − 1; for q4 k = 2, df = 1, very wide);
(b) task-cluster bootstrap (resample the 85 tasks, each bringing its rows in every block), B = 2000, seed 20261002, the
same draws as the published analysis. 95 % and 90 %. A crossed task × block bootstrap is not part of this machinery
and is not added. For q8 the Pocock 97 % intervals are also printed for reference only.

## 5. Readings (fixed before computing)

Applied to XR and XD in each cell and pooled, with the protocol §6 three-way rule at margin ±3 pp, no Holm adjustment
(exploratory): "more" / "fewer" only if both 95 % intervals exclude 0 on the same side; "equivalent within ±3 pp" if
both 90 % intervals lie inside (−3, +3) pp; else "not resolved". Overall reading per model:
- "BF16's extra value comes from more rescues" if XR reads "more" and XD does not read "more";
- "from fewer damages" if XD reads "fewer" and XR does not read "fewer";
- "both" if XR "more" and XD "fewer"; "rescues and damages both higher (offsetting)" if XR "more" and XD "more";
- otherwise "unresolved: neither component separated from zero", with point estimates reported descriptively.
An interval including 0 is never read as "no effect". This analysis is not a router and not a confirmatory test.

## 6. Outputs

`analysis/fork/out/commonstate_rd_<UTC>.{md,json}` with script sha256, git HEAD, B, seed, input sha256.

## Run record (appended 2026-10-05, after the run)

- Script `analysis/fork/commonstate_rd.py` sha256 `9cb80bbad0453e09f96192b981e27a9c72897934e67cbe060ce96d21edeb933b`;
  selftest `analysis/fork/commonstate_rd_selftest.py` sha256 `a3eea41916e8133ec4c0817b1efd05e3932a724883791e6664f32a2b305115fc` (passed).
- Git HEAD `224c6cea37850f6aa673f49d9689a66bbc152bad` (uncommitted files), B = 2000, seed 20261002.
- Output `analysis/fork/out/commonstate_rd_20261005T184031Z.{md,json}`. Frames as fixed in section 1 (q8 510 / k 6,
  q4 170 / k 2); published K, Kbar points and K t95/boot95, and published r/d of BF16-d1 and d2-d1, reproduced exactly.
- Wording note (no rule change): in the q8 rows the per-component reading is "equivalent within ±3 pp" for both XR and
  XD, which the section 5 overall rule maps to "unresolved: neither component separated from zero".

## Amendment (appended 2026-10-05, after verifier review; no estimand, data, rule or threshold change)

- Provenance correction: the pre-run protocol sha256 was `6e773cdab6fb6804a1a895a20c6fc8055c39387d48a164d753abc0ca9b33d595`,
  as recorded in `analysis/fork/out/commonstate_rd_20261005T184031Z.json`; everything from "Run record" down was appended
  after that run. This shows the protocol was unchanged at run time; it does not by itself prove when it was written
  (all files are untracked).
- Code fix: the overall rule now returns "from fewer damages" only if XD reads "fewer" and XR does not read "fewer",
  as section 5 already states (the old code skipped the XR condition; it did not fire on these data). XR "fewer" with
  XD "fewer" maps to "unresolved", per section 5 "otherwise"; no new label is added.
- Weighting note: `analyze_commonstate.estimate` weights rows equally within a block. This equals the section 2
  task-equal weighting because the design has exactly 1 state per (task, block); this is now asserted in the script and
  the selftest uses 1 state per (task, block).
- Reporting only: title before TL;DR; TL;DR lists per-component readings and the margin scale; header states inference
  is to these 85 tasks (task bootstrap with blocks fixed, no crossed interval) and that these are hindsight contrasts,
  not a router; q4 (k = 2) flags degenerate t intervals (XN[d1] t95 = [-1.2, -1.2], zero spread); "avg (pooled)"
  relabelled "avg over c (Kbar-style)". The q8 c = d1 split of K into damages is descriptive only, K not resolved.
- Rerun: script `analysis/fork/commonstate_rd.py` sha256 `5805d49d6445410eb2801285e192e6ebdb544b2d8be640ab3347efaea5f57764`,
  selftest `analysis/fork/commonstate_rd_selftest.py` sha256 `f5207a15c7135968612f6147d07155a90905438206d80c37f822379a17530851`
  (passed), git HEAD `224c6cea37850f6aa673f49d9689a66bbc152bad`, B = 2000, seed 20261002. Output
  `analysis/fork/out/commonstate_rd_20261005T185153Z.{md,json}`. Stats, readings, cross-tabs and frames are identical to
  the 20261005T184031Z run (checked by equality). The run JSON records protocol sha256 `832cb01b...` (state before this
  amendment).
