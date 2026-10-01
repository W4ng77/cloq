# Review: CLOQ storyline v7 as an ARR (NAACL) submission

## Summary Assessment
- **The idea is sound and distinct.** Same-state forks that cross {current action} × {continuation controller} at the first BF16-vs-quantized divergence, with signed estimands (r, d, M, G, A/C/I), are not done by any of the 32 closest 2024–2026 papers found.
- **Novelty risk is medium**, because the parts exist separately:
  - continuation-only swaps (Replay Gap, 2608.08239);
  - action-only swaps (CSO, Counterfactual Rollout Replay, AgenTracer);
  - "flat score hides failures" on τ²-bench with INT4 (2607.27275);
  - two-sided flips in compressed models (2407.09141).
- **The strongest assets** are deterministic replay controls that are stricter than the closest work, and a large, honestly inferred dev atlas.
- **The weakest point:** the "mechanism" layers (L2 and L3) are currently small-n or null. The headline therefore rests on L1 plus the pending holdout.
- **As of today:** a borderline-to-weak accept at a *Findings* level. The main-conference odds depend on the holdout confirming and on L2 at f01–f03 yielding one crisp, controlled result.

## Strengths
1. **Protocol rigor exceeds the closest work.**
   - No-op replay matches prompt-token hashes, messages and DB hashes (FORK_PROTOCOL gate tables), and the 10% production no-op sample plus Bank U gates pass 135/135.
   - Replay Gap needed same-model control forks because FP8 serving diverged on more than 90% of forks. We can show the replay noise floor is exactly 0.
   - This directly answers the prefix-caching and nondeterminism critique (2609.04748).
2. **Signed estimands and statistics.** Complete-block primary inference, crossed intervals, a split guard, a pre-registered holdout, and published negatives (W×KV, restoration, "absorption" retracted). Reviewers in evaluation tracks reward this.
3. **Breadth:** 3 benchmarks (τ², BFCL multi-turn, ALFWorld), RTN/GPTQ/AWQ/QuaRot/KV axes and 2 sizes. The flat-G-with-large-M pattern holds across all of them.

## Critical Issues
1. **The holdout is not yet run.** Without it, fragility is "retrospective conditional association on viewed dev data", and reviewers will treat concentration as an exploratory observation. Run it the moment the prereg is frozen; the measured cost is about 100 GPU-h.
2. **Positioning against 2607.27275 and 2608.08239 must be explicit and early.**
   - Flat Score already shows the flat τ²-bench score under INT4 and a stable failure set. Our "fragile tasks shared across quantizers" overlaps its rank correlation ≥ 0.94 finding.
   - Our increment must be stated as: (i) same-state signed attribution of action vs continuation, and (ii) two-sided turnover, rescues *and* damages, which an error-budget analysis cannot see.
   - **Lead with the 2×2 decomposition, not with "flat success hides turnover".**

## Major Issues
3. **User-simulator dependence (likely reviewer question).**
   - L2 finds about 71% of consequential differences are pure text differences. A reviewer will say these consequences may be properties of the simulator model (Qwen3-30B-A3B) rather than of the task.
   - Cheapest decisive control: re-branch a frozen subset of Bank U text-difference flips (for example the ~40 class-(ii) states) with a different user-simulator model or seed, and report whether the flips persist.
   - Without this, L2 is vulnerable. User-simulator variance is documented at 9–15 pp (2601.17087, 2609.38043).
4. **L3 is a null with a design flaw.**
   - wrong_tool mostly produced argument errors, and premature_write is mostly failure → failure (W83).
   - Present the intervention as a bounding result ("injected local defects cause turnover comparable to generic perturbation; no controller dependence detected at n = 30 per model"), and keep it short.
   - Do not let it be framed as a mechanism. A redesigned wrong_tool with argument-compatible tools is justified by the manipulation-check rule, but only if it fits before 10-05.
5. **Model scale and family.** 4B/8B Qwen3 only. q14 paired BF16/W4 forks would blunt the "small models only" criticism; a second family helps more than a third size. This is the 35% coverage budget; prioritise q14 forks on τ² retail/airline.
6. **"Fragility" needs a content description,** or reviewers will read it as task difficulty. W78 controls for measured difficulty proxies. Add the Table 4/Bank U characterisation of what fragile states look like, even descriptively (e.g. early pivots t* = 1–2 carry M 29%).

## Minor Issues
7. Change "12/12" to "6 configurations × 2 directions" everywhere (W78 wording).
8. Mark the Table 4 LLM annotation in captions, and keep the consent field out of claims.
9. The title should signal the method ("same-state counterfactual forks") so that it differentiates from Flat Score at a glance.

## Reproducibility and Verification
- **Verified:** the replay no-op controls (FORK_PROTOCOL L295–315); the literature overlap (32 URLs verified to resolve, abstracts read, 3 full texts).
- **Not verified here:** whether prefix caching was on in every production run. The no-op token-hash equality implies identical outputs, but the per-run config should be listed in the appendix.
- **Blocked:** the holdout outcomes (not run, by design).

## Inline Annotations
- **§1 Gap:** add Replay Gap (2608.08239) and the single-step action-swap papers. Currently only Flat Score and DMR are named.
- **§3 "Different quantizers flip the same tasks":** cite the overlap with 2607.27275's stable failure set and state what is new (signed direction near random; same-state co-flips in Bank U).
- **§4 claim:** testable only after f02/f03 and the user-simulator control. Phrase it as a hypothesis until then.
- **§5:** shorten; it is a bounding result.

## Recommendation
**Proceed with this storyline, re-centred on the 2×2 same-state attribution.** In priority order before 10-05:
1. Freeze the prereg and run the holdout, about 100 GPU-h. *Highest value.*
2. Finish Bank U f02/f03 and Q0.
3. **New:** a user-simulator swap control on a frozen subset of Bank U text-difference flips (and a few L1 pivots). Small GPU cost, and it closes the most likely reviewer attack.
4. q14 paired forks.
5. Optionally, the wrong_tool redesign.

Expected outcome:
- **If the holdout confirms** G within ±3 pp and M > 0 with repeatability: main-conference odds are moderate (~35–45%) and Findings is likely.
- **If it does not confirm:** a Findings-level evaluation/protocol paper.

## Sources
- `docs/STORYLINE_v7.md`; `docs/RESEARCH_LOG.md` (W63–W86); `docs/insights/FORK_PROTOCOL.md` (L295–315)
- `outputs/.drafts/storyline-v7-lit.md`
- arXiv 2608.08239, 2607.27275, 2602.02711, 2407.09141, 2602.03412, 2609.33875, 2606.08275, 2509.03312, 2609.04748, 2601.17087, 2609.38043
