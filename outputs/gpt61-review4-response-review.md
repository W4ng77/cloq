# Review: GPT-6.1 review 4 and the main session's response plan

## Summary Assessment
- GPT-6.1's review 4 is **factually correct on every checked number** (E1–E4, E6). Its central correction holds: the q4 recovery mean D ≈ 0 hides two-sided per-state turnover, 9/30 states. "Defects are absorbed" is an unsupported reading of a null average.
- Its most valuable contribution is redirecting attention to Bank U: **most outcome-changing differences in q4 are `text_only`** (25 of 38). That redirects the mechanism question from tool choice to the full language action.
- **The one point to contest is cost.** GPT-6.1's 1,080 GPU-h for K = 12 rests on our own overestimate (30 GPU-h per cell-block). Measured cost is about 6–8 GPU-h per q8 cell-block (E5), so K = 12 is affordable, and GPT-6.1's statistical argument for K = 12 (7 vs 4 rate levels per half) should be accepted.

## Strengths
- It recomputes from raw files instead of trusting summaries.
- It separates manipulation failure from null effects, and forbids escalating injection strength because of a null average. This is a correct guard against forking paths.
- Its estimand hygiene is right: per sub-bank reporting, unique states, and a task-equal target without n_decisions weighting.
- Its holdout protocol fixes are right: no post-hoc cell screening, constant-vector handling, and an honest description of what the persona-stratified permutation tests.

## Critical Issues
1. **Report 2 overstated recovery.** "Single injected defects seldom change outcomes" must be retracted. The correct statement is: heterogeneous two-sided turnover (B 7/30, Q 4/30) with no detected mean controller difference.
2. **The "full replay" claim lacks a separate audit artifact** (E2). Until pre-state, budget and prompt-hash equality are written out per state, "full" is too strong.

## Major Issues
3. **Process-perturbation changes 5/30 under both controllers**, comparable to INV. The error-specific effect is not separated from generic trajectory perturbation. Any recovery claim must be a contrast against the process-perturbation control, not against VAL alone.
4. **premature_write is uninformative as currently built.** VAL×Q fails in 7/10 states, so "unchanged outcome" is mostly failure → failure. A manipulation check (did the write execute? did it change the DB?) is needed before interpreting it.
5. **Bank U `text_only` is a comparator class, not a semantic class.** GPT-6.1 says so correctly. *Missing from both GPT-6.1 and the plan:* a cheap content split of `text_only` differences, for example question vs statement, a commitment or confirmation request, or new entity or number. Without it, "the full language action matters" stays vague. Use the programmatic and LLM tooling already built for WP5.
6. **Holdout K.** Accept K = 12, with the cost corrected (E5). Before freezing, run the planning-precision simulation on telecom dev for K = 6/8/12/16. Treat it as confirmation that K = 12 is adequate, not as a K-selection fishing exercise.

## Minor Issues
7. Change W78 "12/12" to "6 configurations × 2 directions". Call the A→B adjustment "retrospective conditional association". Add the shared-nonce null.
8. Withdraw the budget line in report 2 §6 (30 GPU-h per block) explicitly, so the reviewer's cost reasoning is corrected.
9. Q0 analysis: report native and Q0 separately, as GPT-6.1 says. The Q0 subsample is about 25% of U2 rows (19–27 per cell), so per-cell Q0 intervals will be wide; pool across cells only with stated weights.

## Reproducibility and Verification
- **Verified from raw data:** E1, E3, E4 and E6 (exact match with GPT-6.1).
- **Verified from code:** E2.
- **Estimated from logs, inference ±50%:** E5.
- Not re-run: no new GPU work was needed for this review.

## Inline Annotations
- **Report 2 §4 "Reading:"** retract (Critical 1).
- **Report 2 §4 "full replay 30/30":** qualify to "reward, termination and suffix-sha replay; audit pending" (Critical 2).
- **Report 2 §6 Q3 "≈ 30 GPU-h per q8 block":** wrong; ≈ 6–8 (E5).
- **Report 2 Bank U table:** missing the sub-bank split, unique-state counts and the action-difference taxonomy (GPT-6.1 point 2).

## Recommendation
**Accept points 1, 2, 3, 5 and 6 fully. Accept point 4 including K = 12, with the corrected cost; the contest in the draft plan should be dropped.** Add the `text_only` content split (Major 5).

Order of work today:
1. **CPU:** recovery per-state and manipulation checks, plus the replay audit artifact.
2. **CPU:** Bank U taxonomy, sub-bank split, unique states, Q0, and the `text_only` content split.
3. **CPU:** holdout protocol fixes and the K-precision simulation; freeze PREREG.
4. **GPU:** queue holdout K = 12 (3 cells) and Bank U f02/f03, then q14 and coverage gaps.

## Sources
- `docs/REPORT_GPT61_20261001_0700.md` (1542f21)
- `analysis/recovery/inject_q4/inject.json`
- `scripts/a6000/inject_driver.py`
- `analysis/fork/bank_u/{q4_awq_w4,q4_gptq_w4_d1}/f01/bank_rows.jsonl`
- `analysis/fork/telecom/q8_gptq_w4_d1/g{1,2,3}/branches_shard*.json`
- `/data/ziyangs/cloq_work/logs/node_*.out`
- `analysis/fork/out/w67_audit_v2_20261001T0600Z_20261001T070500Z.md`
- GPT-6.1 review 4 (author relay)
