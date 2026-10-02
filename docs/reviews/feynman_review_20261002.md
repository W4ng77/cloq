# Feynman review of the CLOQ paper (ARR/NAACL reviewer standard), 2026-10-02

**TL;DR.** Current PDF (pending slots unfilled): Soundness 3, Excitement 3, Overall 2.5, Confidence 4. If the same-precision
baseline lands as planned (in either direction) and edits E1–E4 below are made: Soundness 3.5, Overall 3. The writing
pass resolved 9 of the 12 mock items fully, 2 partly (hedge density, "small end-to-end differences" in the Discussion), and
1 mostly (holdout readings). The top remaining risks:
(1) the precision-specificity question rests on a pending control that the abstract attaches to the wrong finding;
(2) the related work omits the counterfactual-replay and forking line (CAR, AgenTracer, CRR, CSO, DAgger), although those
entries are already in `refs.bib` and the paragraph is commented out in `related_work.tex`;
(3) the only confirmatory test (holdout, −4.6 pp, CI below zero) contradicts the "net effect stays small" framing, and the
telecom-development numbers that would bear on the domain-shift confound exist (`analysis/fork/out/dev_all_20261001T093944Z.md`)
but are not reported.

Evidence read: `paper/latex/main.pdf` (19 pp., pdftotext raw and layout), `paper/latex/sections/*.tex`,
`docs/reviews/mock_arr_review_20261002.md`, `docs/insights/SAMEPREC_PROTOCOL.md`, `docs/RESEARCH_LOG.md` (W99m, W99j),
`paper/latex/figures/f{1..5}_*.pdf` rendered at 200 dpi with pdftoppm, and page renders p. 2, 5, 6, 8. `analysis/fork/holdout/` was not opened.
Page/line references below are PDF page and ACL margin line numbers.

---

## 1. Summary (3 sentences)

The paper proposes a crossed same-state intervention for quantized LLM agents. At a frozen τ²-bench state whose no-op
replay is bit-exact, the source of the current action (BF16 or quantized) is crossed with the controller of the rest of
the episode, which yields three escalation contrasts (G: this step only, H: from the next step, F: both) and a
(Δ_Q, Δ_B) table of controller dependence. On Qwen3-4B/8B with simulated W4/KV8 quantization and one greedy user
simulator, the paper reports three results. First, swapping the first tool-structure-divergent action turns over 15.5–20.9% of task×block units with a
near-zero development net gain. Second, in 26.9% of W4 divergent states the swap's effect depends on which controller continues.
Third, a frozen Q-uncertainty trigger finds outcome-changing states but not net-beneficial ones. A pre-registered
telecom holdout shows two-sided turnover, repeatable task fragility and a net effect of −4.6 pp (90% CI −7.2 to −2.0).

## 2. Scores (ARR scale)

| | Current PDF (pending unfilled) | After baseline filled + edits E1–E4 |
|---|---|---|
| Soundness | **3** (Acceptable): a rigorous replay gate, explicit denominators, fixed-pool vs new-task intervals and a real pre-registration. The headline controller-dependence finding has no precision-specific reference yet, and every within-cell ordering rests on one greedy simulator. | 3.5 |
| Excitement | **3** (Ambitious but limited): the 2×2 crossing is a clean, reusable idea. The empirical yield is mostly nulls, a negative holdout and a trigger that does not work, all on simulated quantization in one model family. | 3 |
| Overall | **2.5** (borderline Findings) | 3 (Findings; main conference is a stretch unless the same-precision result is clearly precision-specific) |
| Confidence | **4**: I checked most numbers against tables and the protocol. I did not rerun analyses. | 4 |

## 3. Strengths

- **S1. The design is clean and the identification is honest.** The 2×2 over (action source × continuation controller) at a
  replay-verified frozen state (§3.2–3.3, p. 3–4) separates "this step" from "from here on". The paper also states plainly
  that F is what the Replay Gap measures (p. 3, l. 166–171). The estimands are defined once and used consistently. The
  identities I checked all hold: I = Δ_Q − Δ_B per row of Table 3, Δ_B = F − H, and the stratum contributions sum to G_all in Table 17.
- **S2. Replay acceptance is real, not asserted.** The gate ran 20/20 QQ and 10/10 BB no-ops, with a 10% outcome-independent hash
  sample in production and quarantine on any mismatch (§3.3, p. 4 l. 263–281). This is stronger than any comparable agent
  fork paper.
- **S3. Inference discipline.** There are three named denominators that are never mixed (§3.5). Fixed-pool and crossed new-task
  intervals are always kept apart (Fig. 2–4 thick/thin; Tables 3/5). Stress cells are flagged and never pooled. The reader
  can see that most within-cell G−H orderings lose significance on new tasks (Table 5).
- **S4. Pre-registration with a result the authors did not want.** The holdout protocol (App. K) was frozen with a
  hash-checked script. The paper reports a negative primary estimate and discloses that the readings had no
  negative category (Limitations, p. 9 l. 755–758).
- **S5. Negative and robustness evidence is reported, not buried.** The Bank U simulator control (7/39 flips retained), the
  Bank P Sonnet control (G−H changes sign in pool), the W×KV retraction (App. L), the stopped Llama gate and the
  trigger's non-significant net gain are all in the paper.
- **S6. Numbers are internally consistent to a high degree.** I spot-checked about 60 quoted numbers against Tables 1–18. The
  only real inconsistencies are the narrative ones in §8, not arithmetic ones.

## 4. Weaknesses (ranked)

**W1 (MAJOR, decisive for finding (i)). Precision specificity is untested in the current PDF, and the planned text attaches
the control to the wrong finding.**
In a deterministic greedy closed loop, any perturbation of an action or controller can flip the outcome. So the 26.9%
off-diagonal share and the 15.5–20.9% turnover could be generic trajectory sensitivity. The same-precision baseline
(Q′ = GPTQ-W4 d2 in place of B) is the right control, but four problems remain:
(a) The frozen protocol (`SAMEPREC_PROTOCOL.md` §5–6) makes **ΔM (turnover, an R1/finding-(ii) quantity) the primary
comparison**, and the off-diagonal comparison is "always labelled descriptive (different state sets)". Yet the abstract
(p. 1 l. 023–027) and the intro bullet (p. 2 l. 104–106) attach the baseline only to finding (i), controller dependence. The
§5 paragraph (p. 5–6 l. 441–453) sits in R2.
(b) ΔM on the full pool mixes two things: how often Q′ diverges from Q, and how consequential a divergence is. If two GPTQ
draws diverge less often than GPTQ vs BF16, ΔM > 0 follows without any per-divergence precision effect. The divergence
rate of each design must be reported next to ΔM, as protocol §5 already computes.
(c) The protocol's "similar" branch requires the paper to say that "turnover and controller dependence largely reflect
generic trajectory sensitivity". That sentence would change the abstract, the intro bullets, the Discussion and the
contribution claim. No alternative text exists yet, and the main text currently fills exactly 8 pages.
(d) Limitations (p. 9 l. 742–746) calls the baseline "our only calibration of the off-diagonal share against
controller-independent sensitivity". By the protocol's own rule that comparison is descriptive and confounded by state
selection, so "calibration" overstates it.

**W2 (MAJOR). The related-work positioning omits the closest methodological line.** The rendered Related Work cites no
work that forks agent states and re-executes alternatives. `refs.bib` already contains
Causal Agent Replay (Shah 2026; a do-operation on one step, re-executed forward with confidence intervals), AgenTracer (Zhang et al.
2025; counterfactual replay for failure attribution), Counterfactual Rollout Replay (Li et al. 2026; restore state, swap one action, roll forward
under the policy), Verified Critical Step Optimization (Li et al. 2026; "decision points where alternate actions demonstrably flip task
outcomes", continued by the policy itself) and DAgger (expert takeover). The paragraph that discussed them is in a `%`
comment in `related_work.tex` l. 7. CSO and CRR compute exactly the G contrast (an expert action with policy continuation). A
reviewer who knows them will read Contribution (1), "a crossed-intervention framework" (p. 2 l. 126–133), as overclaimed
unless the paper says what is new: the crossing with the controller (H, F and the (Δ_Q, Δ_B) table), the bit-exact replay
acceptance, and the precision setting.

**W3 (MAJOR). The only confirmatory result contradicts the headline framing, and the evidence that bears on why is
omitted.**
Abstract finding (ii) says "the net effect stays small" and then reports holdout −4.6 pp (90% CI −7.2 to −2.0), "which the
pre-registered readings classify as inconclusive" (p. 1 l. 027–037). The interval lies entirely below 0 and beyond the
3 pp ε. "Inconclusive" is true only because the readings had no negative category. The abstract does not say this; the
Limitations do (p. 9 l. 755–757). The holdout, the paper's only confirmatory analysis, is a paragraph inside "R3: Do Sampling and
Environment Change the Answer?" (p. 7 l. 538–571). The Limitations blame a domain shift (retail/airline dev vs telecom holdout).
But telecom-development forks exist for two of the three holdout cells, with 80 tasks × 6 blocks (Table 8, "80 t · 477/480 st · 6/6 b"):
q8 GPTQ-W4 G_all +2.7 [−4.7, +10.1] and q8 AWQ-W4 −0.6 [−4.9, +3.7] (`analysis/fork/out/dev_all_20261001T093944Z.md`,
"Telecom development"). The holdout gives −5.64 and −6.57 for the same cells. That comparison bears directly on the
domain-shift explanation and is not reported. Table 8's caption ("The telecom development analysis uses these 6 blocks")
points at an analysis that appears nowhere.

**W4 (MAJOR). All R2 orderings depend on one greedy user simulator, and the second-simulator evidence leans against
them.**
The within-cell G−H claims (p. 5 l. 371–392; Discussion p. 8 l. 674–683) rest on fixed-pool intervals under a single greedy
Qwen3-30B-A3B user. Under Sonnet 5.5 (80 states), pooled G−H is −8.5 [−14.8, −2.8], while R2 reports positive G−H in both
q8 cells. Arm replicates disagree in 41% of Bank U flip arms. The text-difference labels kept their direction in only 7/39
cases. The paper's reading "neither confirmed nor shown to reverse" (p. 7 l. 531–533) is defensible but generous. A skeptical
reader will see an R2 that holds only on fixed tasks, under one deterministic simulator, and not on new tasks (Table 5: all
four W4 G−H crossed intervals cover zero). The deterministic setting also makes 26.9% a property of greedy decoding. The
stochastic analogue in App. E.2 (mean U_s = 0.050) is reported but explicitly declared not comparable, so the paper never
says what controller dependence looks like when the loop is not chaotic by construction.

**W5 (MODERATE). External validity is narrow and partly pending.** All quantization is simulated, using BF16 compute on a
deterministic path (Limitations p. 9 l. 717–725). There is one family at 4B/8B. The q14 scale check is pending, and the Llama
check stopped at its gate. The retail/airline endpoint is the final-database match, not τ²-bench's official reward (App. A, p. 10 l. 860–866).
The main text (§3.1, p. 3 l. 202–205) does not say that this deviates from the official metric.

**W6 (MODERATE). Finding (iii) is a weak result given finding-level billing.** The trigger's net gain passes one-sided
.05 only at the 5% rate and fails after Holm (p. 8 l. 640–647). It captures 4/34, 2/38 and 5/38 of oracle net. The turnover
result (2/3 rates) is a divergence/sensitivity detector, which §7 itself says is "associated with *where* quantization changes
the action". That supports a sentence or a short section, not one of three abstract findings. The space is better spent on W1/W3.

**W7 (MINOR). Unverifiable or dangling numbers.** BFCL/ALFWorld R1 turnover "5.2–24.6% of items" and BFCL q4 AWQ-W4 net
"−3.8 [−6.5, −1.3]" (p. 7 l. 574–579) appear in no table. Table 7 has only divergent-state G/H/F. The −3.8 is consistent
with G = −4.7 × 642/788, but a reader cannot check it. Telecom dev, as in W3. The Bank U f01 flip count is 58 in §7 (p. 8 l. 595)
and 56 in the Table 10 caption ("39 of 56 flips"), with no stated reason (probably the U2Q duplicates).

**W8 (MINOR). Residual draft artefacts and prose tics.** See §6 and §8. Examples: Table 9 "all are in the source"; Table 8
"completed after this table was compiled"; App. A "a stale default"; repeated aphorisms ("reproducibility, not
correctness" twice; "execution that follows" three times on p. 1).

**W9 (MINOR). Appendix M is three pending slots, and it overlaps App. L.** App. L "Static precision restoration" (p. 18)
says a byte-matched restoration comparison "is incomplete, and we report no result from it". App. M (p. 19) plans "Restoring
the BF16 weights ... compared with randomly chosen modules with the same number of BF16 parameter bytes". If M is
filled, L contradicts it. If M is not filled, an appendix made of placeholders cannot be submitted.

## 5. Mock-review items (W99m): status with evidence

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Remove rendered internal traces | **Resolved** (small residue) | `grep` of the PDF text finds no `analysis/`, W-ids, snapshot ids, `.json/.md`, `SIMCTRL`, `KLu`. App. N is one provenance sentence (p. 19 l. 1302–1306). Residue: Table 9 caption "all are in the source" (p. 15); Table 8 caption "q8 KV8 block f03 was completed after this table was compiled" (p. 14); App. A "The user-model field stored in fork state files is a stale default" (p. 10 l. 878–881); internal block codes f01–f03/f02/f03 still rendered (defined in §3.4, acceptable, but "blocks 1–3" reads better). |
| 2 | Fewer stacked hedges; ≤1 caveat per finding in the abstract | **Partly resolved** | The abstract has one caveat per finding. The main text still stacks: the R2 "Within cells" paragraph (p. 5 l. 371–392) carries five caveats (exploratory; fixed tasks; unadjusted; new-task intervals cover zero; second simulator; cells select different states). R2 "The action's consequence" (l. 406–410) adds a three-part disclaimer. The R3 Sonnet paragraph (p. 7 l. 528–533) is similar. Rewrites in §6. |
| 3 | κ de-emphasised; one sentence in R2; say what κ measures; out of abstract | **Resolved** | R2 p. 5 l. 410–415: "it measures how well the two effects agree across states, not whether the interaction is significant (Appendix E.1)". Absent from the abstract and intro. F1 has no control markers. App. E.1 and Table 6 hold the details. |
| 4 | Figure 2 (3×3) one aggregation (equal weight 26.9%) | **Resolved** (one nit) | Fig. 5 caption: "the equal-weight average over cells, the aggregation used throughout the paper". Nit: App. I reports the menu oracle "state-weighted" (0.202 vs 0.117, p. 15), which contradicts "used throughout". Label it as the exception, or use equal weight. |
| 5 | §3.3 sampling rate and rule for 924/924 | **Resolved** | p. 4 l. 272–279: "re-ran the QQ no-op on a 10% sample of its states, selected by a hash of the state identifier ... a single mismatch would have quarantined the task's whole output. All 924 sampled units ... passed". Nit: say "states", not "units" (units are task×block in §3.5). |
| 6 | Relay simulator reproducibility | **Resolved** | Limitations p. 9 l. 735–742: hosted Sonnet 5.5, default settings, no temperature/seed; Bank U relay subagents could see other arms; the Bank P control used isolated single-request calls. R3 points there (p. 7 l. 505). |
| 7 | Intro: end-to-end "cannot distinguish difference from equivalence" | **Partly resolved** | The intro is fixed (p. 1 l. 050–056; Table 1 caption). The Discussion still says "The four W4 cells have small end-to-end differences (Appendix B)" (p. 8 l. 665–666), which is the reassuring reading the item removed. |
| 8 | Explain why t over 3 blocks gives wider fixed-pool than crossed intervals | **Resolved** | §3.5 p. 4 l. 323–326: "Stress cells have 3 blocks, so their t intervals rest on two degrees of freedom and can be wider than the crossed intervals"; also Table 3 caption. |
| 9 | Full holdout strata table | **Resolved** | Table 17 (p. 18), six families, Holm within family. I checked that the level counts sum to 34 tasks and that the step-budget levels sum to G_all = −4.57. |
| 10 | Limitations: no negative reading category; holdout confounds domain shift with new tasks | **Resolved in Limitations; abstract still silent** | p. 9 l. 755–760. The abstract (l. 035–037) and intro (l. 115–116) still say only "inconclusive". One clause fixes this (E2). The domain-shift point can now be partly addressed with existing telecom-dev numbers (W3). |
| 11 | R4: hindsight oracle positive by construction | **Resolved** | p. 8 l. 654–657 ("positive by construction: the oracle picks only rescues ... and never a damage"); intro l. 124–125. |
| 12 | Bank P vs Bank U tension | **Resolved** | Discussion p. 8 l. 684–696: P skips text-only differences, which are 150/208 of Bank U flips, and those labels did not reproduce. |

The mock's top weakness (no same-precision baseline) is **in progress**: the protocol is frozen and hash-checked, and the
slots are placed. See W1 for the placement and wording problems in those slots.

### Assessment of the `\pending{}` slots

| Slot | Where | Neutral? | Well placed? | Fix |
|---|---|---|---|---|
| Same-precision, abstract | p. 1 l. 025–027 "tests how much of it is specific to precision: [reading]" | Mostly ("how much of it" presumes some is) | **No**: attached to finding (i); the frozen primary is ΔM (finding ii) | "A same-precision baseline (a second GPTQ-W4 calibration draw in place of BF16) tests whether turnover and controller dependence are specific to precision: [reading]." Place it after (ii) or as its own sentence. |
| Same-precision, intro bullet | p. 2 l. 104–106 | Yes | Same issue | Move to bullet 2, or make it a fourth bullet. |
| Same-precision, §5 paragraph | p. 5–6 l. 441–453 | Yes | Primary quantity belongs to R1 (§4) | Split: ΔM (primary) at the end of §4. Δoff (descriptive) plus readings (a)/(b) stay in §5. Name the analysis set ("the first K blocks"); put the M′ divergence rate beside ΔM. Replace "a paired difference of [paired difference]" with "ΔM = M − M′ = x [CI]". Quote the 3 pp threshold of the frozen rule. |
| Same-precision, Limitations | p. 9 l. 742–746 | **No** ("calibration") | OK | "is our only reference for how much turnover and controller dependence a non-precision perturbation produces; it covers GPTQ-W4 on the development panel only". |
| q14 BFCL | R3 p. 7 l. 581–586; Limitations p. 9 l. 707; Table 8 | Yes ("a single configuration, not second-family evidence") | Yes | If not filled by the freeze, delete all three mentions. Do not leave "(pending)". |
| Backfill (App. M) | p. 19 | Yes | Overlaps App. L static restoration | Merge with L's paragraph; delete App. M if any slot is unfilled at the freeze. |

## 6. Prose quality: remaining AI-sounding or over-hedged sentences

| # | Page/line | Current | Proposed |
|---|---|---|---|
| P1 | p. 1 l. 002–004 (and l. 062–063, l. 043–045) | "In a closed-loop agent, the value of a single precision upgrade depends on the action it changes and on the execution that follows." | Delete. Open with the question: "When a quantized agent and its BF16 reference act differently at a state, should BF16 supply this step, take over from the next step, or both?" The idea already appears in intro l. 062–063 and in the closing abstract sentence. |
| P2 | p. 1 l. 012–014 | "a standard 2×2 factorial design made executable for agents" | "a 2×2 factorial design over action source and continuation controller" |
| P3 | p. 1 l. 064 | "Judging the two actions is not enough." | Delete; start with "Consider one state from our data (...)". |
| P4 | p. 1 l. 075–077 | "The better-looking action has task value under one continuation and none under the other, and no judgement of the action alone could show this." | "B's action helps only if B also continues, which no judgement of the action alone can reveal." |
| P5 | p. 3 l. 256–257 | "These contrasts judge consequences, not correctness." | "The contrasts measure effects on task success, not which action is correct." |
| P6 | p. 5 l. 361–364 | "S2 tests neither concentration nor direction, and it does not rule out task difficulty as the explanation." | "S2 tests repeatability only; task difficulty could explain it." |
| P7 | p. 5 l. 371–373 and 389–392 | "The following contrasts are exploratory, and their intervals treat the 85 tasks as fixed." ... "and a smaller second-simulator control neither confirms nor reverses them (§6). Cells select different states, so orderings across cells cannot be attributed to the quantizer or bit width alone." | One closing sentence: "These within-cell orderings are exploratory: they hold on the fixed 85 tasks, not on new tasks (Table 5) or under a second simulator (§6), and cells select different states." |
| P8 | p. 5 l. 398–399 | "Here the reference action is not reliably better." | Delete (the paragraph heading already says it). |
| P9 | p. 5 l. 406–410 | "Because the setting is deterministic and replay-verified, each such state shows a non-additive interaction on the success scale; on its own this does not establish a recovery or quantization-specific mechanism, or a deployment gain." | "Because replay is exact, each such state is a true interaction on the success scale, not noise; whether it is specific to precision is what the same-precision baseline tests (below)." |
| P10 | p. 6 l. 471–472 | "nearly always two natural-language replies" | Give the count (x of 150), or drop "nearly always". |
| P11 | p. 6 l. 491–492 | "The user simulator is a plausible mediator of text consequences;" | "Text actions act through the user simulator, and changing the simulator moves τ-bench outcomes by 9–15 points (...)." |
| P12 | p. 7 l. 510–513 | "That does not make text consequences simulator artefacts: the control changes the simulator model, adds sampling randomness and uses a relay interface" | "The control changes three things at once (simulator model, sampling, relay interface), so it cannot say which removed the flips." |
| P13 | p. 7 l. 528–533 | "This sample is too small to test the few-pp G − H contrasts of Table 3; ... so R2's within-cell orderings are neither confirmed nor shown to reverse under another simulator." | "With 20 states per cell this control cannot resolve few-pp contrasts (on this sample even the original simulator gives G − H = 0.0 in both q8 cells). Under Sonnet the pooled G − H is −8.5 [−14.8, −2.8]; its change from the original simulator, −6.0 [−16.2, +4.2], covers zero." |
| P14 | p. 8 l. 649–652 | "The frozen Q-only rule has not been shown to select net-beneficial replacements, and two new nonce blocks of the same tasks do not establish routing gains on new tasks." | "The frozen rule finds outcome-changing states but not net-beneficial ones, and its held-out blocks reuse the development tasks." |
| P15 | p. 8 l. 663–664 | "Average success, action divergence and replacement gain answer different questions." | "Average success, action divergence and replacement gain disagree here:" (then the evidence). |
| P16 | p. 8 l. 665–666 | "The four W4 cells have small end-to-end differences (Appendix B)" | "The four W4 cells have end-to-end differences we can neither distinguish from zero nor bound within ±3 pp (Appendix B)" |
| P17 | p. 9 l. 742–746 | "is our only calibration of the off-diagonal share against controller-independent sensitivity" | See §5 slot table. |
| P18 | p. 9 l. 752 and p. 17 l. 1205 | "...shows reproducibility, not correctness." (twice) | Keep it once, in Limitations. In App. J write "Re-labelling 30 states with fresh instances reproduces the key pattern." |
| P19 | p. 15 l. 1052–1054 | "What is new here is the signed, two-sided view: shared fragility, but with near-random relative direction across quantizers." | "Unlike that work, we record direction: quantizers flip the same tasks but agree in direction in only 42–81% of joint flips." |
| P20 | p. 15 l. 1059–1061 | "They limit what it can explain; they do not identify a mechanism." | Delete the second clause; the paragraph already says "constrain". |
| P21 | p. 1 l. 040–042 | "but has not been shown to yield a net gain" | "but its net gain over random selection is not significant after correction" (more specific, same length). |

## 7. Figures and tables

All five matplotlib PDFs were rendered at 200 dpi and inspected. Page renders were checked for placement.

| Item | Needed? | Readable? | Consistent with text? | Notes |
|---|---|---|---|---|
| Fig. 1 (TikZ schematic, p. 2) | Yes | Yes | Yes | Δ_Q = G and Δ_B = YBB − YQB match §3.2. |
| Fig. 2 = f3_rescue_damage (p. 4) | Yes | Yes. Bars, diamonds and both interval weights are distinct. | Yes: r/d/net match Table 2; the holdout thick bar [−6.08, −3.05] and thin bar [−7.17, −1.96] match Table 16. | The shared axis carries both "% of units" (bars) and "net pp" (diamonds, sign by side). Add "net < 0 plotted left" to the caption. KV8 has no pool row here but does in Figs. 3 and 4 (minor). |
| Fig. 3 = f2_ghf_forest (p. 6, full width) | Yes (replaces Table 3 in the main text) | Yes at full width | Yes: W4 pool G +0.5, H +0.2, F +0.7; q8 GPTQ F +5.4 etc. | KV8 uses orange triangles here but blue circles in Fig. 4. Pick one encoding per cell family across figures. |
| Fig. 4 = f1_controller_dependence (p. 6, column) | Yes (central) | Small but legible (~7 pt) | Yes: 26.9 / 15.3 / BFCL 10.3 / ALFWorld 36.4 / holdout 20.7. | The caption says thick = fixed-pool, thin = new-task, but BFCL/ALFWorld have item bootstrap only. Say "BFCL/ALFWorld: a single item-bootstrap interval". |
| Fig. 5 (TikZ 3×3, App. E) | Useful | Yes | Yes (5576/1448 states; 26.9/15.3) | Fine. |
| Fig. 6 = f5_simctrl_p (App. G) | Yes (supports §6) | Yes | Yes: Sonnet pool G−H ≈ −8.5, original ≈ −2.5. | Fine. |
| Fig. 7 = f4_trigger_oracle (App. I) | Optional | Yes | Partly | **The legend says "matched oracle" in both panels, but in panel (b) the black series is the turnover ceiling Σ_c min(m_c, R_c+D_c), not the oracle** (the caption admits this). Use a panel-specific legend label, "max. capturable (same counts)". |
| Table 1 (App. B) | Yes | Yes | Yes (NI/TOST pattern matches intervals) | TOST is applied to 95% intervals; standard TOST uses 90%. That is conservative, but say so. |
| Tables 2–5 (App. C–D) | Yes | Table 4 is dense but fine | Yes (state counts match Table 8 sums; 0000 39–58%, 1111 6–20% checked) | — |
| Table 6 (pairing control) | Appendix only, OK | Yes | Yes (κ 0.291 etc.) | — |
| Table 7 (BFCL/ALFWorld R2) | Yes | Yes | Yes | Add r, d, M, G_all columns so the R3 "5.2–24.6%" and "−3.8" are checkable (W7). |
| Table 8 (coverage) | Yes | Yes | **Partly** | The telecom-dev column points at an unreported analysis; the caption says "f03 completed after this table was compiled" while the row says "3 b"; the q4 RTN-W3 row is all zeros (drop it or footnote it); the q14 row is pending. |
| Tables 9–11 (Bank U) | Yes | Yes | Yes (150/208, 1045/1357, 7/39, 41% checked) | They float out of order (10, 11 before 9). Remove "all are in the source". |
| Table 12 (trigger) | Yes | Yes | Yes (34/1020 = 3.33 pp etc.) | — |
| Tables 13–15 (injection, audit) | Appendix, OK | Yes | Yes | — |
| Tables 16–18 (holdout) | Yes | Yes | Yes (weights reproduce −4.57; r 5.21, d 9.77; 1180 states) | — |

## 8. Inconsistencies between sections

1. **Abstract (ii) vs holdout.** "the net effect stays small" (p. 1 l. 029) is followed in the same sentence by a holdout
   estimate whose 90% CI lies entirely beyond −1.96 pp, and partly beyond the 3 pp ε. Scope "small" to development, or drop it.
2. **Discussion vs Intro/Table 1.** "small end-to-end differences" (p. 8 l. 665) vs "cannot distinguish difference from
   equivalence" (p. 1 l. 050–051; Table 1 caption).
3. **Same-precision primary endpoint.** The abstract and intro attach it to the off-diagonal share. The protocol's primary is ΔM, and
   the off-diagonal comparison is descriptive (the §5 text itself says "a descriptive comparison because each design selects
   its own states"). Limitations then calls it a "calibration of the off-diagonal share".
4. **Telecom development.** Table 8 lists 6 complete telecom-dev blocks for q8 GPTQ/AWQ, and its caption says "The telecom
   development analysis uses these 6 blocks". No telecom-dev result appears anywhere. The committed numbers (q8 GPTQ +2.7
   [−4.7, +10.1], q8 AWQ −0.6 [−4.9, +3.7]) differ in sign from the holdout's −5.64 and −6.57.
5. **Aggregation.** The Fig. 5 caption says equal weight is "the aggregation used throughout the paper". App. I's menu oracle is
   "state-weighted".
6. **Bank U f01 flips.** §7 says "1140 cell × state rows, 58 flips" (p. 8 l. 595). The Table 10 caption says "In block f01 alone ... 39 of
   56 flips". The difference is presumably U2Q duplicates (cf. 216 → 208), but this is not stated.
7. **Table 8 caption vs row.** "q8 KV8 block f03 was completed after this table was compiled", while the q8 KV8 Bank U cell reads
   "3 b · 393 / 177 rows" and Table 9 uses f01–f03 for q8 KV8.
8. **App. L vs App. M.** L says no result is reported from the byte-matched restoration comparison; M reserves a slot for
   exactly that comparison.
9. **κ ranges.** App. E.1 reports BFCL/ALFWorld κ "0.47–0.71 and 0.14–0.24" (W4 cells); App. E.3 reports "0.44–0.71 and 0.10–0.24
   (incl. GPTQ-W3)". Both are correct for their cell sets, but the reader sees two ranges for the same quantity. Keep one.
10. **§3.3 terminology.** "All 924 sampled units" are states (the no-op runs per state); §3.5 defines units as task×block.
11. **§3.1 vs the rest.** "The development panel has 58 retail and 27 airline tasks plus 80 telecom development tasks" (p. 3 l. 196–198).
    Every development result uses the 85-task retail/airline panel. Say that the 80 telecom-dev tasks were used only to fix the
    holdout stratum cut points, or report them (item 4).
12. **Intro bullet 1 vs abstract.** The intro says the telecom-holdout off-diagonal is 20.7% "post hoc". The abstract says only "this dependence
    also appears on BFCL and ALFWorld". This is fine, but the BFCL q8 GPTQ-W4 cell is 4.7%, so "appears" should carry "to differing degrees" or the range.

I found no arithmetic inconsistencies. I checked: M/r/d ranges; G/H/F/G−H for every quoted cell; mean I = G − (F − H); reversal share 8–14%;
holdout weights and counts (1224 − 24 = 1200; 385 + 399 + 396 = 1180); strata sums; Bank U class counts (150 + 26 + 32 = 208;
1045 + 143 + 169 = 1357); trigger counts and oracle pp; Table 4 n vs Table 8 state sums.

## 9. The 10 highest-value edits (writing only)

- **E1. Pre-write both same-precision branches now, and re-place the slot.** Following protocol §6, write the "similar" and the
  "precision-specific excess" versions of the abstract clause, intro bullet, §4/§5 text, Discussion sentence and Limitations
  sentence, so that filling the slots takes minutes. Put ΔM (primary) at the end of §4 next to M, with the divergence rate of
  each design. Keep Δoff with readings (a)/(b) in §5, labelled descriptive. Change the abstract clause to "tests whether turnover
  and controller dependence are specific to precision". Reserve about 4 lines on p. 8 by applying E6/P7/P13 first.
- **E2. Make the abstract and intro honest about the holdout.** Replace "while the net effect stays small; on unseen telecom
  tasks the estimated effect is −4.6 pp (90% CI −7.2 to −2.0), which the pre-registered readings classify as inconclusive"
  with "with a near-zero net effect on development tasks. On 34 pre-registered unseen telecom tasks the swap lowered success
  by 4.6 pp (90% CI 2.0–7.2); the pre-registered readings had no negative category." Make the same change in intro bullet 2.
- **E3. Restore the counterfactual-replay paragraph in Related Work** (the bib entries exist; the text is commented out in
  `related_work.tex` l. 7). Three sentences: CAR, AgenTracer, CRR and CSO intervene on one action and continue with the original policy,
  which is our G; none crosses the action with the continuation controller (H, F, (Δ_Q, Δ_B)), checks bit-exact replay, or
  studies precision. DAgger-style takeover is our H. Scope Contribution (1) to the crossing, not to forking itself.
- **E4. Report telecom development (existing committed numbers).** Add one sentence in the holdout paragraph or Limitations, and two rows in
  Table 2 or a footnote: q8 GPTQ-W4 +2.7 [−4.7, +10.1], q8 AWQ-W4 −0.6 [−4.9, +3.7] (80 tasks × 6 blocks, fixed-pool). Then
  reword the domain-shift limitation: "on telecom development tasks the same cells show no negative effect, so the holdout
  drop is not explained by the telecom domain alone; it may reflect task-level heterogeneity in 34 tasks". Run it
  through `check_numbers.py` with a `% src:` comment.
- **E5. Fix the Discussion end-to-end sentence** (p. 8 l. 665–666) as in P16. This closes mock item 7.
- **E6. Collapse the caveat stacks** in R2 "Within cells" (P7), R2 interaction (P9) and the R3 Sonnet paragraph (P13), and delete P8.
  This saves about 5 lines for E1/E4.
- **E7. Fix the Limitations "calibration" sentence** (P17) and the abstract trigger clause (P21).
- **E8. Clean the appendix remnants.** Table 9 "all are in the source"; Table 8 "after this table was compiled" (re-check the q8 KV8
  f03 count) and the all-zero q4 RTN-W3 row; App. A "stale default" (move it to the code release or say "the served simulator is
  ..."); §3.3 "units" → "states"; App. I state-weighted → note or equal weight; explain 58 vs 56 f01 flips; one κ range in E.1/E.3;
  Fig. 7 panel-(b) legend; the Fig. 2 caption sign convention.
- **E9. Set a deletion rule for the slots that will not fill.** At the evidence freeze, any unfilled q14 slot deletes the q14
  sentence in R3, "(pending)" in Limitations and the Table 8 row. Any unfilled App. M slot deletes App. M. Merge whatever lands
  into App. L "Static precision restoration" so L and M do not contradict each other.
- **E10. Make the BFCL/ALFWorld R1 numbers checkable, and demote finding (iii).** Add r, d, M and G_all columns (from the
  existing ext output) to Table 7, or a two-line table, for "5.2–24.6%" and "−3.8 [−6.5, −1.3]". In the abstract, shorten (iii) to one
  clause ("a frozen uncertainty trigger finds outcome-changing decisions but not net-beneficial ones") to free space for E2.

## Sources

- Shah 2026, Causal Agent Replay: https://arxiv.org/abs/2606.08275
- Li et al. 2026, Verified Critical Step Optimization: https://arxiv.org/abs/2602.03412
- Li et al. 2026, Counterfactual Rollout Replay: https://arxiv.org/abs/2609.33875
- Zhang et al. 2025, AgenTracer: https://arxiv.org/abs/2509.03312
- Local: `paper/latex/main.pdf`; `paper/latex/sections/related_work.tex` l. 7 (commented paragraph);
  `docs/insights/SAMEPREC_PROTOCOL.md` §5–6; `analysis/fork/out/dev_all_20261001T093944Z.md` (Telecom development);
  `docs/RESEARCH_LOG.md` W99m.
