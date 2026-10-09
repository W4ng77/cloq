# Independent self-review of the current CLOQ paper

Reviewed version: cloq `3228ba463cc6714555bad2d2b7fe19bef9ed87d0`; paper mirror `152abf1ea4ca7cc16c0b247b8ecbd457b8687d37`.

This is a self-review, not a review by an independent human or a panel of four reviewers. The Feynman skill was unavailable. I read all eight main pages, the limitations, and the supporting replay, consequence, reference, selection, fidelity and scope sections. I inspected the rendered main pages and checked headline values against committed analysis reports. I did not rerun all raw rollouts or certify metadata that exists only on the cluster. I checked the nearest work against its public primary sources. No paper text or experimental result was changed during this review.

## Overall judgment

### Story-first reassessment after the author's clarification

The paper should persuade through its scientific argument. Audit details establish that the comparisons can be trusted; they are not the reason a reader should care. The earlier review overemphasized compliance relative to motivation and contribution.

The intended reader is choosing where to spend high-precision inference in a closed-loop agent. The central claim is: **evaluate fallback by the signed task value of the intervention that will actually run.** The evidence chain has three parts:

1. **Specify the intervention.** Replacing an action, taking over the continuation and replacing both can reach different successes from the same state. The factorial measurement makes these distinct deployment choices visible. This is not a claim to invent factorial design.
2. **Interpret the change.** A different outcome does not identify a precision requirement. The same-bit-width substitute and the operation-preserving representation control are the decisive evidence. Common states provide the direct additional-value comparison, whose precision limits are stated alongside it.
3. **Evaluate the selector's target.** The frozen trigger captures more changed outcomes while rescues and damages cancel much of its benefit. This is a concrete demonstration that enrichment and utility are different selection objectives, rather than a blanket verdict on learned routing.

The strongest framing is therefore a measurement contribution with a useful change of evaluation target. Avoid selling it as a catalogue of null results, a failed router project, a universal chaos theory, or a report of engineering discipline. The same-precision and semantic references deserve the most visual and narrative emphasis.

The main results should be ordered around **what is executed → what outcome changes mean → what the selection rule must optimize**. Full protocol chronology belongs in the relevant appendix. The holdout is an important boundary case, not the opening hook. Its negative estimate should remain visible, with the omitted decision category explained briefly where inference is described. Scope checks should answer whether the central distinction survives other settings; they should not be narrated as a sequence of completed configurations.

For the opening, a concrete deployment decision is more compelling than a list of metrics: a W4 agent reaches a decision, BF16 is available, and the designer can request one action or transfer control. A signal that marks disagreement has not yet valued either choice. Figure 1 defines the choices, Figure 2 measures their consequences, Figure 3 prevents attributing every consequence to bit width, and Figure 4 tests whether a sensitivity signal selects benefit. This is the argument the reader should remember.

The main packaging risk is that the draft calls itself a study of task value but presents too many findings as “unresolved.” Give each section a positive takeaway supported by its strongest evidence, and state precision limits locally. In particular, the reference interventions establish that flips are insufficient evidence of a need for more bits even though the direct BF16-versus-Q′ advantage remains unresolved. Do not require an equivalence claim to communicate that established result.

Final priorities are the contribution sentence, paragraph topic sentences, and the interpretation attached to each figure. Venue corrections and numerical checks are submission hygiene; they should not displace this scientific work. This reassessment changes the review's emphasis, not the underlying estimates or its assessment of their scope.

I would support this as a carefully scoped measurement paper for Findings. For the main conference, I am borderline: the reference-intervention argument is useful, but the paper does not establish a broadly predictive signal, a profitable upgrade policy, or a precise estimate of BF16's additional value. This is a contribution-strength judgment, rather than evidence of an invalid core experiment. Acceptance cannot be inferred reliably from a self-review score.

| Dimension | My assessment, out of 5 |
|---|---:|
| Soundness | 3.5–4 |
| Contribution / excitement | 3 |
| Readability | 3.5 |
| Reproducibility | 4 |
| Overall | 3 |
| Confidence in this review | 4 |

## Paper summary

The paper evaluates a specific fallback intervention, rather than treating a difference between two complete agents as the value of switching. It crosses the source of the current action with the subsequent controller, obtaining action-only, continuation-only and joint replacement effects. Audited state restoration makes those effects interpretable under a fixed greedy execution stack. Rescues and damages expose changes that can cancel in average success.

The distinctive evidence comes from two references. Another GPTQ checkpoint at the same bit width produces substantial turnover; an argument-key reorder also changes outcomes while preserving the parsed tool operation and its immediate environment effects. These observations refute the sufficiency of turnover as evidence that a state requires more bits. A direct common-state comparison does not resolve BF16's additional value over the other W4 action, and does not show equivalence. Finally, one prospectively frozen margin rule enriches outcome-changing states without reliably outperforming matched random selection in net benefit.

## Strengths

1. **The evaluation target is well specified.** Action replacement and continuation takeover are distinct interventions. The main text now actually reports all three mode estimates, rather than promising a factorial contribution and showing only action replacement. Different denominators are identified in the method and Figure 2.

2. **The reference interventions are the main intellectual contribution.** Their roles are distinct: same precision tests whether changing bit width is necessary for turnover; key order demonstrates consequences from a representation change without a changed tool operation; shared states compare the additional value of two action sources directly. The paper correctly avoids subtracting a reference as a universal noise floor.

3. **Replay auditing now addresses the central baseline concern.** The 1202/1202 full holdout QQ replays match. The previous criticism that only a 10% sample checked this particular baseline is obsolete for the current paper. This audit does not make deployment generalization automatic, but it does address original-versus-reexecuted QQ asymmetry on these states.

4. **The scope of negative results is mostly handled correctly.** The trigger result is restricted to one frozen rule. Unresolved comparisons are not called equivalent. The holdout estimate, omitted negative category and passed secondary checks are all reported. The paper explicitly uses simulated quantization and does not claim measured kernel speedups or routing efficiency.

5. **The revision is substantially more readable.** The three questions align with Results 1–3. Figure 1 combines the intervention and state-population overview. Main figures have coherent signs, readable legends and distinguish capture from gain. Internal bank names no longer dominate the main narrative. The appendix has explicit main-claim hooks.

## Weaknesses that remain

### W1. The paper's contribution needs one sharper statement

The current contribution paragraph combines an audited protocol, standard factorial contrasts, bookkeeping and references. It is accurate, but the reader has to infer which addition changes how prior measurements should be interpreted.

The strongest contribution is a **reference-backed evaluation of intervention-specific upgrade value**. A switch is a defined action-plus-continuation intervention; observing an outcome change does not attribute value to precision; a selector must therefore be tested on the signed benefit of the intervention it executes. This chain should be stated once and used consistently. It does not require claiming to invent factorial experiments, or claiming that precision is generally unnecessary.

Related work already covers live branching, single-step replay values and KL-informed routing. Replay Gap reconstructs environments and uses same-model control forks; DMR combines KL supervision with reward-based GRPO. Neither should be described as assuming that raw sensitivity alone is an adequate deployed objective. The manuscript mostly respects this distinction. The new reference interventions, rather than branching alone or a negative margin baseline, should carry the novelty claim.

### W2. Common-state results are informative but still imprecise

At Q continuation, the reported +1.0 pp interval [-4.2, +6.2] allows a practically meaningful advantage or disadvantage. At B continuation, +0.8 [-2.2, +3.8] is narrower but does not establish equivalence. Thus the direct comparison cannot support “BF16 is only a re-roll,” “there is no precision value,” or “the methods are equivalent.” The current wording largely avoids these claims.

The adaptive extension and two-look approximation are disclosed; the appendix explicitly states that the procedure has no exact error guarantee for the small-block joint reading. I would treat this evidence as a limited, adaptively collected comparison, not as a clean independent confirmation. The absence of a positive claim makes this less damaging than it would be in a method claiming improvement.

The useful next writing step is a one-sentence precision interpretation: these data cannot distinguish benefits of a few percentage points. Do not add observed-effect post hoc power, or manufacture an MDE from a confidence interval. Any formal MDE calculation needs a specified effect, power and variance model.

### W3. The selector experiment is a diagnostic, not a broad verdict on routing

The validation contains 38 rescues and 31 damages, and tests one selected margin statistic on later prompt blocks of the same tasks. Its failure to beat random after correction is useful alongside its turnover enrichment, but does not establish that Q-visible features cannot predict signed value, or that learned routing fails. The oracle is a hindsight bound and positive by construction.

The manuscript now states these limits. Keep the experiment as a concrete demonstration of a mismatch between a sensitivity score and the desired target. A full DMR reproduction is not required for this bounded measurement claim. It would be required for a stronger claim of superior routing or a systematic critique of learned routers.

### W4. Fixed-stack task effects should remain distinct from expected deployment value

A deterministic single rollout is not automatically an invalid counterfactual. Under the restored, fixed stack, it is an identified realized consequence. Running the identical deterministic branch several times adds little information. Estimating expected benefit across prompts, simulator randomness or serving conditions instead requires a specified nuisance distribution and paired evaluation over that distribution.

The present paper explicitly separates those targets in Discussion. The semantic reference supports representation sensitivity on its eligible states; it does not prove dynamical chaos, establish a universal noise floor, or quantify the fraction of all BF16 flips attributable to arbitrary perturbations. Likewise, the Sonnet relay control changes model, sampling and interface simultaneously and should remain low-weight scope evidence. The paper generally makes these distinctions correctly.

### W5. A little protocol language still distracts from the result

The abstract's negative-category explanation, the fixed/new-task/two-look distinctions and repeated “unresolved” statements remain demanding for a first-time reader. These are material disclosures, so simply deleting them would make the paper less sound. The improvement should come from ordering: state the empirical result first, explain the relevant inference target once, then give the interpretation.

Two specific examples:

- Method repeats the statement that an action is not intrinsically correct in both “Four branches” and “The action being replaced.” One occurrence is enough.
- “Fragility repeats without identifying gain” is good evidence of recurring turnover, but the sentence contrasting repeatable susceptibility with repeatable benefit should not suggest that repeatable benefit has been disproved. Neither subgroup's net gain is resolved.

These are polishing issues. I do not recommend another wholesale change of storyline.

## Figures and tables

| Item | Assessment | Remaining action |
|---|---|---|
| Figure 1 | Clear factorial hook and compact sampling overview. The example's scope is explicit. | Retain. If adjusting anything, enlarge the small contrast formulas rather than add another panel. |
| Figure 2 | Rescue/damage coding works; G/H/F now fulfills the introductory promise; holdout is separated and labeled 90%. | The thick/thin interval convention is still subtle at normal print size. Test a grayscale print; avoid another statistical encoding unless it improves legibility. |
| Figure 3 | Strongest scientific figure: same-precision reference, semantic reference, direct shared-state comparison. Difference directions are consistent. | Labels are readable. Keep the distinct populations and the reference-not-subtracted note. Panel (c) must not visually imply a formally calibrated sequential guarantee. |
| Figure 4 | Correctly separates capture from net gain and keeps the oracle off the measured net axis. | Show nominal and actual selection rates clearly; matched-count random expectation is not a confidence interval. Current p-values supply the conditional random-selection test. |
| Table 1 | Compact and useful as a scope map. | “Sampled B” / “Div. / B” are unnecessarily cryptic. Use “BF16-history” / “mixed sources,” or plain wording in the caption. The stress F example is selected exploratory evidence, not a pre-specified positive-control validation. |
| Appendices A–F | Every section now has a reason to exist. Primary comparison families and adverse controls remain visible. | Keep complete primary families. Redundant interpretation sentences can still be cut, but do not remove unfavorable results to make the paper look cleaner. |

The main text fills eight pages naturally and the Conclusion is complete. Filling the page is not itself evidence of quality; further material should only enter if it improves this argument.

## Concrete consistency checks

I found no central numerical contradiction in the checked claims. The report-backed checks include:

- same-precision 16.8% versus 17.7%, and the failed pooled ±3 pp turnover equivalence test;
- common-state +1.0 / +0.8 and the corresponding two-look intervals;
- key-order 6.7% versus BF16 9.0%, with a correctly reversed BF16-minus-reference difference +2.3 [-2.9, +8.4];
- holdout -4.57 [-7.17, -1.96], its frozen inconclusive category, passed secondaries and 1202/1202 full baseline replay;
- trigger selections 50/114/222, net +4/+2/+5, random expectations and Holm-adjusted net results;
- task-fragility and KL diagnostics promoted into Discussion, which match their committed reports.

These are source-report checks, not a new complete raw-data audit. The local numeric checker still has seven previously unverified metadata values and 28 absent source paths; it cannot certify the cluster-only metadata.

**A reference correction is needed.** The Replay Gap HTML full text explicitly says “Accepted at the Efficient Reasoning Workshop, COLM 2026.” The current BibTeX entry lists “Conference on Language Modeling (COLM),” which implies the main conference. The arXiv landing-page comment is less specific, so the full-text statement should govern the venue label or the entry should simply be an arXiv preprint. This correction does not alter the comparison of methods.

The default “Anonymous ACL submission” template heading is not, by itself, a scientific inconsistency. Template compliance should be checked against the actual submission instructions rather than changed based on the acronym alone.

## Recommended final actions, in order

1. Correct the Replay Gap venue attribution.
2. Make the contribution paragraph identify the reference-backed interpretation of intervention-specific value in one direct sentence.
3. Replace Table 1's compressed state-source abbreviations with plain wording and remove the duplicated intrinsic-correctness sentence in Method.
4. Give one short interpretation of the common-state precision; retain its adaptive timeline and avoid a new equivalence conclusion.
5. Rebuild with the production compiler, run the complete metadata audit, regenerate the anonymous copy, and do one grayscale/read-at-column-width check of the main figures.

I would not require a new GPU experiment for the current bounded claim. A clean learned selector or a nuisance-averaged deployment evaluation could strengthen a future paper, but would change the present research scope and cannot be replaced by a last-minute small panel.

## Primary sources checked for novelty and citation scope

- Replay Gap: https://arxiv.org/html/2608.08239v1 (branching protocol; model controls; explicit workshop acceptance statement).
- Flat Score, Amplified Failures: https://arxiv.org/html/2607.27275v1 (task-level paired analysis and process/recovery comparison, not a shared-state action-by-controller intervention).
- Dynamic Mixed-Precision Routing: https://arxiv.org/html/2602.02711v2 (KL-supervised routing followed by reward-based GRPO).

The paper's main narrative should stay fixed. Its strongest evidence supports a measurement lesson with concrete controls. It does not yet support a general high-precision routing policy, an equivalence result, or a universal perturbation model.
