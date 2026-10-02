# Final-plan review (ARR/NAACL reviewer view), 2026-10-01

## Summary assessment
The plan can produce a coherent paper. It is an honest measurement paper whose results are mostly two-sided or null, and its centre (R2) is still exposed. The protocol is the strongest asset. It uses bit-exact no-op replay (924/924 and 135/135 checks), separate denominators, and fixed-pool versus new-task intervals, and in these respects it is stricter than the closest work. Three things are weak. (a) The 26.9% controller-dependence share has no null calibration. (b) The G vs H ordering is fragile: the crossed intervals cover 0, it survives Holm in the q8 cells only, and in the SIMCTRL-P interim it flips from +3.3 to −8.7 under Sonnet. (c) The only confirmatory result is a negative G_all (−4.6 [−7.2, −2.0]) that the prereg can only label "inconclusive". As planned, the paper holds together if R2 is reframed and G−H is moved out of the headline.

## Strongest version of the story
At the same frozen, bit-exactly replayable state, replacing a quantized agent's action with the BF16 action turns over 15–21% of outcomes in both directions, while the net gain is near zero. On unseen telecom tasks, under a pre-registered protocol, the net effect is negative. Whether the swap helps depends on which controller continues. The action effects under the two controllers agree only moderately, so "is B's action better?" is not a property of the action. Uncertainty locates where the two models diverge, not which divergences pay off. Escalation therefore has to be evaluated as a paired intervention on outcomes (G/H/F), not inferred from success averages, divergence rates or token proxies.

## Top 5 weaknesses (ranked)
1. **The 26.9% share may just reflect that outcomes are sensitive to small trajectory changes, not "controller dependence".** Δ_Q and Δ_B are each nonzero in about 23% of W4 states. I recomputed from the Fig. 3 counts: if the two were independent, the off-diagonal share would be **37.9%**. The observed share is 27.1%, and Cohen's κ = 0.28 (KV8: 33.2% expected vs 15.2% observed, κ = 0.54). Under Sonnet, the 5 replicates of a single arm disagree in 30–47% of states. *The plan only partly addresses this* (wording fixes, the BFCL/ALFWorld 3×3). Changes:
   - report the independence baseline and κ next to 26.9%;
   - add an exploratory, noise-calibrated estimate of the between-state variance of the interaction I from the SIMCTRL-P replicates. Do not report it as an off-diagonal share, which the protocol forbids;
   - use the BFCL/ALFWorld 3×3 explicitly as the simulator-free test.
2. **The G−H ordering ("where to replace") is fragile.** *The plan waits for SIMCTRL-P.* Before batch 2 is analysed, write a decision rule into the log. If the final Sonnet G−H on the same states has the opposite sign to the original, or its paired-change interval excludes 0, then:
   - delete the q8/W3 ordering from the abstract, intro and discussion;
   - report it as a finding: "the ranking of G/H/F was not stable across cells, task sampling or user simulator; it must be measured per configuration, simulator included". This supports the thesis rather than undermining it.

   Even if the sign holds, take G−H out of the abstract, because the crossed intervals cover 0.
3. **The holdout handling invites suspicion.** A significantly negative primary result is labelled "inconclusive" because the prereg had no negative category. The holdout is also a different domain from dev, and the q4 GPTQ cell (weight 1/2) had no telecom dev forks. *The plan, which confirms only G_all, is correct but thin.* Changes:
   - state the result plainly ("lowered success; formally inconclusive under the frozen readings");
   - add descriptive, post-hoc-labelled holdout H, F and 3×3 shares from the existing four-arm data. This is the cheapest out-of-sample check of the centre, and it shows whether B's action hurts *under Q's continuation* specifically.
4. **The scope is narrow.** Only Qwen3 4B/8B were tested; quantization is simulated (BF16 compute); there is one greedy simulator; and the design forks only at the first divergence. *The plan does not address this, and that is acceptable without new GPU work.* State it in the first page and the abstract, not only in Limitations.
5. **"So what?": novelty and actionability.** The 2×2 is a standard factorial, and the plan rightly does not claim to have invented it. G/H/F are oracle quantities, and the trigger gives no reliable net gain. Change: add the **oracle headroom** from the 16 patterns: the share of states where some arm succeeds and QQ fails, and E[max(G, H, F, 0)]. Compare it with what the frozen trigger captures. This turns R4 into "headroom X pp, Q-visible proxy recovers ~0" (CPU only).

Polish: the main text is dense with notation (r, d, M, G_all, G, H, F, Δ_Q, Δ_B, I, U1/U2B/U2Q). Move KV8, the stress cells and recovery to the appendix.

## Novelty vs closest work
- **Flat Score (2607.27275):** same setting and same "flat score hides damage" claim, including a two-sided task split. **R1's two-sidedness is therefore not new.** What is new is same-state attribution that separates the action from the recovering controller.
- **Replay Gap (2608.08239):** model-switch forks with controls, which corresponds to our F only. The new parts are G and H, the crossing, and a pair with the same weights. Make no noise-advantage claim; the plan already drops it.
- **Lotfi et al. (2606.00206):** frame R4 as a transfer test of their entropy/KL mechanism to agent actions. Result: it locates divergence, not consequence.
- **DMR (2602.02711):** DMR learns a KL-supervised router; we measure the gain such a router could harvest. Reviewers will ask for a DMR-style KL trigger row. The top-20-union KL is already scored, so add it to the frozen-trigger table as a labelled secondary.

Overall novelty risk: **medium**.

## Likely scores (subjective, not a prediction)
- Soundness 3.5–4.
- Excitement 2.5–3.
- Overall 2.5–3.5.

My rough read is Findings-level, with main-conference odds roughly 20–30% (Findings around 45–55%) if items 1–3 are fixed. Revision risk is concentrated in R2.

## Cut / add (cheap only)
**Add** (all CPU-only, about 1 day in total):
- κ and the independence baseline (minutes);
- the pre-committed SIMCTRL-P decision rule;
- the noise-calibrated interaction variance;
- descriptive holdout H/F/3×3;
- oracle headroom;
- a KL row in the trigger table.

Keep the planned BFCL/ALFWorld 3×3, the coverage fix and the claim audit.

**Cut:**
- "decision diagnostic" as a *contribution*; it becomes a finding;
- G−H from the abstract;
- the stress-cell sentence from the abstract;
- the in-text recovery material.

No new GPU lines.

## Riskiest sentences
> "We argue that the answer depends on the state and on the controller that continues, so … must be measured separately." (abstract)

The "so" is a non sequitur, and the intro supports this with one anecdote.

> "In about a quarter of the divergent states … the outcome effect of the same action swap changes with the controller that continues." (abstract)

There is no null baseline (W1).

> "replacing the current action gains more than replacing the continuation in both q8 W4 cells, and less in a severe W3 stress cell" (abstract)

At risk from SIMCTRL-P (W2).

> "The better-looking action has value only under one continuation; elsewhere, a handover to B … damages a task that Q would have recovered" (intro)

This generalises from Case 5 and Case 6, which are different states.

> "Q's token-level uncertainty locates where B and Q diverge, but not which divergences matter." (intro R4)

This **contradicts** the abstract: "enriches outcome-changing decisions", with turnover p = .0002 at the 20% rate.

> "The replay noise of a branch is therefore zero." (method)

> "only the continuation matters" (discussion)

Both of these are already flagged in the plan.

> "A rule that escalates whenever B's action 'looks better' would not gain." (discussion)

No such rule was tested.

## Sources
- `analysis/fork/out/{ghf_20261001T211519Z,ghf_multiplicity_20261001T225727Z,simctrl_p_interim_20261002T003506Z}.md`
- `paper/latex/sections/*.tex`
- `docs/RESEARCH_LOG.md` (W93–W99, W98a/b)
- `outputs/.drafts/storyline-v7-lit.md`
- κ and the independence baseline were computed here from the Fig. 3 counts.
- https://arxiv.org/abs/2607.27275
- https://arxiv.org/abs/2608.08239
- https://arxiv.org/abs/2606.00206
- https://arxiv.org/abs/2602.02711
