# Current execution TODO: breadth, mechanisms and consequence evaluation

Updated 2026-09-30 America/Toronto (2026-10-01 UTC). Scope and scheduling authority: [execution plan](EXECUTION_PLAN_20260930.md). Technical specifications: [coverage](insights/QUANT_BENCHMARK_COVERAGE.md), [analysis](insights/CONSEQUENCE_ANALYSIS_PLAN.md), [positioning](insights/RELATED_WORK_POSITIONING.md).

This is a proposed work inventory. Unchecked items are not queued/completed claims. Owners first reconcile existing queues, results and code to avoid duplication. This document does not restart workers or unlock the protected holdout.

## Priority tiers (agreed 2026-10-01 with the author and GPT-6.1)

| tier | packages |
|---|---|
| **Must** | WP0 audit; WP1 four-arm consequences; WP5 annotation (events, blinded LLM rubric, ~80 human states); WP8 telecom confirmation; core coverage (BF16/W4/W3 × RTN/GPTQ/AWQ, A8/SmoothQuant/QuaRot, KV8/rotated KV4, matched W×A×KV cube with the registered q8 W×KV test); **small** Bank U (U1 + BF16-sourced U2 + a few Q-sourced shared states; native four-arm plus a common-continuation Q0 subsample); **small** real recovery intervention (§5.5) |
| **Best effort** | q14 / larger-model panel; label transport (WP7 first application); W2 stress expansion beyond the first ~24-task round; second model family |
| **Deferred** | latent capture and activation patching (WP6); full DMR training / complete routing comparison; WebShop; consequence-preserving calibration |

When the budget is short, cut best-effort expansion first, then reduce repetitions uniformly within a tier. Never drop a must-tier axis to make room for an attractive cell.

## WP0 — Evidence and population audit

- [ ] Create OLD_RESULT_REUSE.csv: path/hash, script/commit, checkpoint, hardware/backend, task/block identities, endpoint, integrity status, allowed use and required reanalysis.
- [ ] Align q4/q8/KV common-task estimates; report 85-task versus 165-task populations explicitly.
- [ ] Reanalyze W67 task concentration, sign consistency and overlap with dependence-preserving references and independent validation. Already-viewed splits are internal replication.
- [ ] Retain H3/act-talk/lottery corrections and original files. Replace obsolete active-paper claims.
- [ ] Check every admitted block covers its full frozen task pool; unresolved whole blocks follow quarantine/completion rules, never a hard-task complete-case filter.

## WP1 — Complete four-arm consequences

- [ ] Produce all 16 outcome patterns for every valid paired cell.
- [ ] Report A/C/I, action gain G, suffix gain H, both-replacement gain F, rescue/damage/turnover and fixed-task/crossed intervals.
- [ ] Check strict reversal separately from interaction; preserve denominators and no-divergence handling.
- [ ] Stratify by declared precision/model/task populations; show all signs and inconclusive estimates.

## WP2 — Quantization breadth

- [ ] Finish BF16 plus faithful RTN/GPTQ/AWQ W4/W3 panels on q4/q8.
- [ ] Add a small W2 stress panel on a frozen approximately 24-task subset: q4/q8 RTN-W2 plus one faithful advanced q8 W2 cell, with matched BF16/W4/W3 controls. Keep it outside the coverage floor.
- [ ] Omit a required W8-only sweep. Reuse available W8 or run a tiny reference only for a named low-error contrast with marginal-cost justification.
- [ ] Keep A8, SmoothQuant W8A8, QuaRot W4A4, KV8/rotated KV4 and K-only/V-only with their fidelity and transformation controls.
- [ ] Finish the matched rotated cube; preserve q8 registered A16 W×KV four corners/six blocks; label other interactions exploratory.
- [ ] Build the separate plain W4/A8/KV4 cube where the gate passes.
- [ ] Add bounded W5/W6, format/rounding, dose and matched-random panels only after balanced baseline coverage.
- [ ] Publish QUANT_MATRIX.csv with admitted/unsupported/failed/not-run cells, exact scale/group/clipping/calibration/cache settings and hashes.

## WP3 — Models, benchmarks and replay gates

- [ ] Complete retail/airline/telecom-dev, BFCL multi-turn and ALFWorld panels and scorer checks.
- [ ] Add q14, one audited larger model and an available second family with registry-pinned identities/templates.
- [ ] Gate WebShop as an extension; show adapter or model capability failures honestly.
- [ ] Keep telecom's 34 tasks protected; document untouched external confirmation slices before access.
- [ ] Audit the 22 historical excluded tasks as a separate sensitivity population; do not reuse 57 calibration tasks as an independent test set.
- [ ] Publish BENCHMARK_MATRIX.csv, task IDs, paired nonce blocks, scorer identity and no-op/hook gates.

## WP4 — Ordinary shared states and transport

- [ ] Freeze Bank U histories, prompt/token hashes, database/user state, counters and cache policy using outcome-independent sampling.
- [ ] Include agreement states; retain clustering for multiple states from one episode.
- [ ] Compare quantizer/draw proposals on the identical state and declared common continuation, with B-tail counterparts where feasible.
- [ ] Separate new-nonce, new-task, new-draw, new-quantizer and cross-model targets. Publish actual state identity checks.

## WP5 — Process labels and controlled pathways

- [ ] Freeze automatic tool/event rules and the blinded semantic rubric before annotation.
- [ ] Run automatic and blinded LLM labels with evidence spans and separate provenance.
- [ ] Schedule about 80 human-reviewed states with about 20 double-reviewed, stratified across consequence signs and task types.
- [ ] Run controlled recovery/action injections, remaining-budget ladder, context-position/length and validated simulator checks.
- [ ] Measure tool errors, policy/consent checks, irreversible writes, correction, termination and agent/simulator/tool cost.
- [ ] Validate and hash the proposed loop guard on about 20 loop/30 legitimate-repetition traces; run a small original-cap continuation sensitivity. Apply the identical rule across new stress comparisons only; preserve frozen stop rules. Persist loop evidence/reason, count guarded algorithmic failure and distinguish infrastructure stalls.

## WP6 — Latent diagnostics and bounded patching

- [ ] Validate offline diagnostic tokenizer/template/logit/action and quantizer parity against serving.
- [ ] Capture residual/attention/MLP outputs at matched action and argument positions on a frozen subset.
- [ ] Run layer profiles and task-grouped probes against simple proxy baselines.
- [ ] Patch bounded modules with sham/random/magnitude controls and full-tail evaluation.
- [ ] Report parity failures or no-outcome-change results; do not pool incompatible execution engines.

## WP7 — Application and fair closest baselines

- [ ] Evaluate continuation-matched label transport on held-out branch outcomes, using available prefix features.
- [ ] Compare KL/margin, semantic disagreement, failure-risk, unsigned and signed supervision at equal state pool/capacity/information.
- [ ] Only for competitive routing claims: compare DMR-style KL-ST and reward-refined complete methods, utility witness and honest COTA-inspired adaptation.
- [ ] Freeze one primary resource constraint and development-set thresholds; record previews, labels, model residence, classifier/train and simulator cost. Fixed-tail QB/BB uses an average/expected-budget constraint; hard-cap B→Q fallback is a separately defined controller requiring new labels and live evaluation.
- [ ] If eligible, run a one-trigger live policy on fresh full episodes. Choosing none commits to Q; oracle branch selection is not policy value.
- [ ] Keep consequence-aware quantizer calibration bounded and optional; no large retraining project.

## WP8 — Protected confirmation and statistics

- [ ] Freeze prospective confirmation/amendments and hashes before reading unseen outcomes.
- [ ] Preserve existing G_all primary, registered margins, W×KV design and multiplicity families.
- [ ] Use complete paired shared blocks and separate fixed-task/crossed-task/checkpoint inference.
- [ ] Run telecom confirmation under its split guard and any documented external untouched slices.
- [ ] Report NI/equivalence with intervals and justified prospective margins; no equality from nonsignificance.

## WP9 — Paper and reproducibility

- [ ] Draft using the current storyline and precise closest-work attribution.
- [ ] Produce coverage, consequence, pattern, controlled-mechanism and optional application figures.
- [ ] Build CLAIM_EVIDENCE.md mapping each main assertion to frozen outputs and scope.
- [ ] Publish all negative/inconclusive/unsupported lanes and corrected-statistic appendix.
- [ ] Freeze evidence by October 5 Toronto with config/code/input/result hashes; continue writing toward the author's October 12 target.

## Scheduling contract

Use the live allocation under the author's 42-A6000 ceiling and measured simulator/agent p90 costs. Complete one balanced paired panel before deep repetition; use three complete paired blocks as the descriptive coverage floor, five preferred where feasible, while retaining registered/core replication.

After that floor's first balanced panel, reserve capacity for coverage, mechanisms and confirmation rather than following attractive effects. Keep the agreed 20% completion/outage reserve. Use leases/canaries/drain and safe resume for infrastructure changes; preserve running episodes and paused queue records. This document updates the research plan only.
