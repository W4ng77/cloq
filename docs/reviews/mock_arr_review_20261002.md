# Mock ARR review (pasted by the user, 2026-10-02) — action items

**TL;DR** Soundness 3, Excitement 3, Overall 2.5 (borderline Findings). The top weakness is the missing
same-precision perturbation baseline: it is being run as W99k/W99l (Q = GPTQ-W4 d1 vs Q′ = d2), protocol frozen
before any results. The other items go to the writing pass (W99m).

Writing-pass items (for the Feynman writer):
1. Remove internal traces from the submission text and captions: file paths/timestamps ("Source: \nolinkurl{analysis/...}"),
   "W89 draft", "W93 audit", work-item ids, snapshot ids, "nonce block f13" style ids. Keep `% src:` LaTeX comments
   (they are not rendered) but strip rendered paths. Put provenance in a single appendix sentence ("all numbers are
   traceable to released analysis outputs").
2. Fewer stacked hedges: state each main claim once with its scope; put labels (post hoc / exploratory) in one place per
   result, not in every sentence. The abstract carries one caveat per finding at most.
3. De-emphasise the marginal-preserving pairing agreement control: one sentence in R2 plus the appendix. Say plainly
   that κ measures agreement between Δ_Q and Δ_B, not whether the interaction is significant. Remove it from the abstract.
4. Figure 2: use one aggregation only (equal-weight 26.9%), not the summed 27.1%.
5. §3.3: state the sampling rate and rule for the 924/924 QQ no-ops.
6. Relay simulator: state its reproducibility (model, no temperature control, cross-request context exposure in the
   W95 relay; SIMCTRL-P used isolated single-request calls).
7. Intro: the end-to-end comparison "cannot distinguish difference from equivalence" (TOST fails), not "looks reassuring".
8. Table 1 stress cells: explain why t over 3 blocks (2 df) gives wider fixed-pool intervals than crossed ones.
9. Holdout strata: give the full table in the appendix.
10. Limitations: pre-registered readings had no negative category; the holdout confounds a domain shift (telecom) with
    new-task generalisation.
11. R4: say that the hindsight oracle headroom is positive by construction.
12. Bank P vs Bank U tension: discuss it explicitly (Bank P skips text-only differences, which are most Bank U flips, and
    those labels are not robust to the simulator).
