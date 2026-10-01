# CLOQ vs. *Flat Score, Amplified Failures* (arXiv:2607.27275v1): overlap and positioning

Status: positioning note, 2026-09-30 (America/Toronto). Requested by the GPT-6.1 review. It refines the one-row entry in `RELATED_WORK_POSITIONING.md` §2.1 and does not change any frozen endpoint.

**Source read:** Jang, Yang, Lim, Park, *Flat Score, Amplified Failures: How the Error Budget Masks Damage in Quantized LLM Agents*, arXiv:2607.27275 **v1** (submitted 29 Jul 2026; arXiv comment "preprint"; only v1 listed on 2026-09-30).
- Full text read from the PDF (https://arxiv.org/pdf/2607.27275, all pages including appendices A–D).
- Checked against the HTML version (https://arxiv.org/html/2607.27275) and the abstract page (https://arxiv.org/abs/2607.27275).

**Citation convention:** the paper uses unnumbered AAAI-style sections, so locations below give section titles plus Table/Figure numbers. Appendices are A (Additional Results), B (Limitations), C (Reproducibility Details) and D (Sample Trajectories).

---

## 1. TL;DR

- **Their paper already covers the following** on τ²-bench:
  - flat W4 task score alongside large process damage;
  - a two-sided paired task-level count;
  - the error budget as the reason the score stays flat, shown by a counterfactual K-projection;
  - "recovery is equally reliable at both precisions";
  - a reflexive repair prompt that helps only in the damaged cell;
  - a thin-margin (logit-margin) account.
- **What remains ours** (a narrow increment, but a real one) is the **same-state intervention**. At one immutable state, we cross the current action's source (B or Q) with the continuation controller (B or Q).
  - Their comparisons are explicitly task-level. Their own words (Fig. 7 caption): the paired episodes do "not [share] token-identical user turns; the comparison is task-level, as everywhere in the paper".
  - Their "recovery is unchanged" is an observational rate (55% vs 55%, Table 2), computed over different failure states.
  - We can measure, at identical states:
    - the signed effect of the action (rescue r vs damage d);
    - the effect of switching the recovering controller (H = Y_QB − Y_QQ);
    - whether the action's effect depends on that controller (I).
- **Main overlap risks:**
  1. "Flat score hides two-sided change" is already theirs, both as the flat score and as the 33/26/55 task split.
  2. "Recovery/error budget explains flatness" is theirs.
  3. Telecom user-side tool calls exhausting the budget is their central mechanism, and we see the same phenomenon in our telecom forks.
  4. We have **no** repair-prompt or budget-manipulation result yet. We must not imply one.

## 2. Their setup (verified against the text)

| Item | Their setup | Location |
|---|---|---|
| Models | Gemma-4-31B (dense), Gemma-4-26B-A4B (MoE, 4B active), Qwen-3.6-27B (dense), Qwen-3.6-35B-A3B (MoE, 3B active), plus Qwen-3.5-27B and Qwen-3.5-9B (dense) as telecom-only extensions | Experimental Setup › Models and quantization; Table 1 |
| Quantizers / bits | Three arms: BF16; FP8, run weight-only as W8A16 via Marlin on A100; INT4 AWQ. **Gemma INT4:** AWQ-style g=32 (31B asymmetric, 26B symmetric), compressed-tensors, MSE observer. **Qwen INT4:** zero-point AWQ g=128. **Gemma FP8:** per-channel symmetric. **Qwen FP8:** E4M3 with 128×128 block scales. Activations and KV cache are 16-bit in every arm ("all three arms are weight-only"). No GPTQ, RTN, W3, activation or KV quantization. | Models and quantization; App. C Serving; Table 6 |
| Benchmark | τ²-bench retail (single-control) and telecom (dual-control), 114 tasks each. `max_errors=10`, `max_steps=300` (Gemma-4-31B retail BF16/INT4 used 200; "no episode reaches either cap"). Agent temperature 0.0; user temperature 0.7 (0.6 in repair arms); seed 300; `num_trials=4`. No airline, BFCL or ALFWorld. | Experimental Setup › Benchmark; App. C Benchmark and protocol |
| User simulator | Qwen-3.6-27B BF16, fixed across all conditions | Protocol; App. C |
| Sample sizes | 456 simulations per cell × precision arm (114 × 4); n ≥ 453 in three arms after infrastructure exclusions (≤ 3 per arm). Ten cells (the 8-cell grid plus 2 Qwen-3.5 telecom extensions) × 3 precisions. Repair grid: 5 telecom models × 3 precisions, 456 each. **Totals computed by us, not stated in the paper:** about 13.7k base and 6.8k repair episodes. | Protocol; Table 1 caption; Table 3 |
| Metrics | Final score (mean binary reward, %). **Channel rate**: the fraction of the agent's own tool calls triggering a channel; "Tool 'X' not found" is tool-name hallucination (telecom), and unresolved-entity errors are the entity/argument channel (retail). Also: trajectory length, termination reasons, per-tool-name and per-task hallucination distributions, "recovery rate after at least one failed call". | Process metrics and failure channels; Table 2 |
| Error-budget manipulation | **Counterfactual projection from existing logs, not a rerun.** S(K) is the fraction of episodes that succeeded using at most K failed tool calls. An episode exceeding K counts as failed even if it finished, which is conservative. Applied to both precisions. | Counterfactual error budget; Fig. 3; App. B (ii): "a rerun at tightened budgets would confirm it directly" |
| Repair prompt | On a failed tool call, the agent is prompted to diagnose and reissue a corrected call, up to 3 attempts. A validator checks the tool name and argument schema before the call reaches the environment. The injected text is "ERROR: {err} Reissue this tool call with corrected, schema-valid arguments." | Repair arm; Fig. 8(c) |
| Statistics | 95% CIs from a 5,000-resample **cluster bootstrap over the 114 tasks**, keeping all 4 trials of each task. Paired-by-task comparisons; TOST at ±7.5 points. Run-to-run noise floor ≈ 1.5 points from one repeated 456-episode run, and a ±2.0-point repeat band from two identical repair runs (Table 3 note a). Mechanism statistics: BF16/INT4 correlation of per-tool-name frequencies, novel-event fraction, and a per-task regression slope. | Statistics; Table 3 note |
| Multiple-comparison correction | Invoked ("survives neither multiple-comparison correction…"), but **the procedure is not specified in the text. Unverified.** | Results › Final Task Reward Is Blind |
| Code / logs | "Will be released upon publication"; not available | App. C Analysis |

## 3. Their main findings (with locations)

1. **The final score is flat.**
   - In all ten cells the 95% interval for the BF16→INT4 score change includes zero, and the largest point estimate is 4.6 points.
   - Seven cells are TOST-equivalent at ±7.5 points.
   - The largest paired decline is 2.0 points (Qwen-3.6 MoE telecom, p=.049).
   - Location: Results › Final Task Reward Is Blind to Quantization; Table 1.
2. **Two-sided per-task changes, highest-signal cell.** "Paired by task in the highest-signal cell, 4-bit is worse on 33 tasks, better on 26, tied on 55" (same section). This is their only per-task two-sided count. It is not decomposed further and has no rerun null.
3. **Process damage in two of ten cells.**
   - Gemma-4-31B telecom tool-name hallucination goes from 19.5% to 38.3% of agent tool calls (+18.8, CI [14.0, 23.6]).
   - Event volume grows 2.5× (649 → 1,646), and budget-exhausting terminations go from 5 to 46 of 456.
   - Qwen-3.5-27B telecom: 0.26% → 1.21% (+0.95 [0.5, 1.5]).
   - Retail Gemma-4 MoE entity errors are a non-significant trend (+1.5, CI [−0.1, +3.1]).
   - Location: Results › The Damage Is Real…; Table 1.
4. **The cliff is at 4 bits.** FP8 shows no significant score degradation and no significant channel move (Results › The Cliff Is (Mostly) at Four Bits; Table 4; Fig. 5).
5. **Existing failures are amplified rather than new ones created.**
   - The per-tool-name BF16/INT4 frequencies correlate at 0.97. Only 3 of 1,646 INT4 events (0.18%) name a tool never used at BF16.
   - 23 of 24 hallucinated names are real **user-side** tools, which they read as "role-boundary confusion".
   - The per-task increase is additive (slope −0.06).
   - Location: Results › Quantization Amplifies the Existing Failure Set; Fig. 2; Table 5.
   - *Discrepancy:* the abstract says "rank correlation ≥ 0.94", while the body, contributions and Fig. 2 report 0.97. We could not locate the 0.94 figure in the body.
6. **The error budget masks the damage.**
   - Failed calls per episode rise from 1.45 to 3.64, while the "recovery rate after at least one failed call is 55% at both BF16 and INT4" ("Quantization does not weaken recovery").
   - The BF16–INT4 gap is 1.3 points at K=10, 7.5 at K=5 and 16.7 at K=2.
   - The gap widens by 15.4 points in the one volume-adding cell and by at most 0.2 in the other cells.
   - The positive arm has a single member.
   - Location: Results › Why the Score Stays Flat; Table 2; Figs. 3–4.
   - *Unverified detail:* the exact denominator of the "recovery rate" is not defined beyond that phrase.
7. **Mechanism: a logit-margin account.**
   - Quantization noise flips thin-margin argmax decisions, so it reuses the existing failure set. Full-precision propensity is a necessary "gate" but not a sufficient one (Gemma-4 MoE telecom: an equally open gate, 1.05×).
   - **The margin account is not tested on logits**: "token log-probabilities are not in our logs" (App. B (ii)).
   - The INT4/BF16 ratio stays between 1.3× and 2.0× across turn bins (Fig. 6), which argues against a context-erosion account.
   - Location: Why Quantization Amplifies Existing Failures; App. A; App. B.
8. **The repair prompt.**
   - The only individually significant repair gain is Gemma-4-31B INT4: +5.9 points (CI [+1.1, +10.8], p=.017) to 71.3%, above unmitigated BF16 (66.7%).
   - Hallucination events fall from 1,646 to 82.
   - The authors state that the precision × repair interaction is **not** resolved (+3.7, CI [−3.2, +10.7]). Localization rests on the cross-arm pattern.
   - Location: Discussion › A mechanism-targeted mitigation; Table 3; Fig. 8.
   - *Tension:* the abstract's "removes the damage exactly and only where it lives" is stronger than this non-significant interaction.
   - *Internal inconsistency:* the Table 2 caption says repair "re-injects the tool inventory after each failed call", but the prompt in Fig. 8(c) shows only an error message and a reissue instruction. It is unclear which description is accurate.
9. **Recommendations.**
   - Report per-channel error rates and S(K) next to task reward.
   - Use full-precision propensity as a one-directional risk screen.
   - "Deployment slack is not always benchmark slack."
   - Location: Discussion; Conclusion.
10. **Self-declared limits** (App. B): one benchmark; two domains; weight-only recipes; 16-bit KV; fixed BF16 user simulator; telecom-only repair. The S(K) projection and the margin account are indirect, and the INT4 recipes differ by family.

## 4. Item-by-item overlap

The "ours" column uses the numbers in `docs/RESEARCH_LOG.md` W63/W67/W68, `analysis/fork/out/consequence_estimands_20261001T0224Z.json` and `analysis/fork/out/w67_audit_20261001T0224Z.md`.

| # | Their finding / method | Our corresponding result | Overlap | Genuinely new for us, if anything |
|---|---|---|---|---|
| 1 | **(a) Flat task-level score under W4** (no cell significant; TOST ±7.5 in 7 cells) | W4 pooled G = +0.6 pp [−0.4, +1.7] (crossed [−2.2, +3.4]). Checkpoint-aligned success shows no detected loss; TOST at 3 pp fails everywhere under task resampling. | **Same** finding | Nothing about flatness itself. Our only difference is a tighter declared margin (3 pp) and the honest statement that equivalence is *not* shown. |
| 2 | **(a) Two-sided task-level change**: 33 worse / 26 better / 55 tied, paired by task (Gemma-4-31B telecom, 4 trials per task) | Rescue r = 9.7%, damage d = 9.0%, M = 18.7% of task × block units at W4 (Y_BQ vs Y_QQ at the first semantic divergence) | **Partial** | **The level of the change.** Theirs compares whole episodes whose user turns are not token-identical, so per-task flips mix quantization with user-simulator sampling (their noise floor is about 1.5 points). Ours swaps only the action at one restored state with coupled randomness, and the Q→Q no-op reproduces exactly (FORK_PROTOCOL gate (a)). So the two-sidedness is attributable to the action. We also replicate it across cells, domains and two simulator-free benchmarks (ALFWorld, BFCL). The *existence* of two-sided change is not new. |
| 3 | **(b) The error budget masks damage** (S(K) projection; K=10 → K=2 gap 1.3 → 16.7) | None yet. Our forks restore step and error counters exactly (FORK_PROTOCOL §10 item 10; gate (d)). We document that the budget binds in telecom: the q8 BF16 telecom run ends in `too_many_errors` in 63/80 episodes. A live budget intervention is designed (CONSEQUENCE_ANALYSIS_PLAN, "declared resource intervention") but not run. | **Partial** (same mechanism observed; no test) | Nothing yet. We could run the *live, same-state* version that their App. B calls "the decisive version of the test" (§6, E2). |
| 4 | **(b) Recovery equally reliable at both precisions** (55% vs 55%, observational) | H = Y_QB − Y_QQ (switch only the continuation controller after Q's action) and I = Y_BQ + Y_QB − Y_BB − Y_QQ. I ≠ 0 in 14.9–33.0% of divergent states across cells. Strict ranking reversal is 1.2–4.6%. | **Partial**: same question, different identification | **Core increment.** Their 55%/55% is conditioned on *different* failure states, generated by different-precision runs. Equal rates are compatible with Q recovering worse from harder states, or better from easier ones. We hold the state fixed and swap only the controller, which identifies the controller's recovery contribution (H) and whether the action's consequence depends on the controller (I). Strict reversal is rare, so the controller mostly changes the *magnitude* of the action's consequence, not its *sign*. |
| 5 | **(c) Reflexive repair prompt**: 5 telecom models × 3 precisions; +5.9 only in the damaged cell; interaction not significant | **None.** Our interventions are precision swaps (BF16 action and/or BF16 continuation), not prompts. Our static BF16 layer restoration is dominated by GPTQ-W4 at matched storage (W67, STATUS §4). | **Different** | Nothing on repair prompts. We must not present a BF16 continuation as a "repair method". It is an oracle-style intervention; Y_BB − Y_QQ is labelled "oracle intervention value" (W63). |
| 6 | Failure set is precision-invariant (0.97; 0.18% novel); "a property of the model" | No channel-level analysis. At the task level, QQ outcomes persist across nonces (Spearman 0.88–0.95), task M rates replicate across a frozen nonce split (0.52–0.86), and tasks co-flip across quantizers (φ 0.07–0.18; task-identity null rejected in 7/8 pairs). | **Partial, thematic** | Task-level persistence of *consequential pivots*, and their sign, is not in their paper. But this is internal replication on viewed dev data, persistence under prompt perturbation on the same tasks (W68). Do not equate it with their failure-set invariance. |
| 7 | Volume amplification of one channel (2.5×; 1×–4.6× by cell) | Not measured | **Different** | None, unless E3 is run. |
| 8 | Telecom: hallucinated tools are real user-side tools; budget exhaustion | Same phenomenon, independently: our q8 BF16 telecom exhausts the budget mostly by calling user-side tools, and 6/8 q8 telecom divergences sit at t=0 where both B and Q call user-side tools (FORK_PROTOCOL §9, telecom development option) | **Same** observation (already at BF16 for us) | None. Cite them when describing telecom. Our telecom states are dominated by one shared failure mode, so treat telecom fork results with that caveat. |
| 9 | Full-precision propensity as a gate | QQ-failure "opportunity" ranking; top-20% capture by opportunity is 0.35–0.54 vs 0.44–0.64 by A-defined M (W67 audit) | **Partial** | Our consequence ranking beats an opportunity-only ranking, internally. Theirs is model × channel; ours is task-level. |
| 10 | Logit-margin account, untested on logits | AUROC of −first-token margin for locating Q's first divergence from B: 0.60–0.71 (W63, `analyze_pivot.py`) | **Partial** | We actually have margins. But our AUROC predicts *where divergence happens*, not its consequence. A margin → consequence test would be new, and is not done. |
| 11 | Cliff at 4 bits (FP8 ≈ free; weight-only) | KV8 M = 7.3% vs W4 M = 18.7%. W8-only weight runs were descoped. | **Partial**, different axis | A KV-axis comparison at the consequence level, plus W3 and rotated KV4/A4 cells (QuaRot), which they do not cover. This is breadth, not a headline. |
| 12 | Position: INT4/BF16 ratio flat across turn bins | M given divergence: 21% (t*=0), 29% (1–2), 21% (3–6), 11% (≥7) | **Different** quantity | Consequence by pivot position is not in their paper. It is exploratory and selection-dependent (first-divergence bank). |
| 13 | Statistics: task-cluster bootstrap, paired by task, TOST ±7.5 | Block bootstrap over complete shared nonce blocks (primary) plus a crossed task × block bootstrap (new tasks); NI/TOST at 3 pp | **Partial** | Our design has repeated nonce blocks shared across arms, which their four trials per task are not. Methodological care, not a novelty claim. |
| 14 | Fixed BF16 user simulator; greedy agent | Fixed user simulator identical across branches; agent temperature 0.0 | **Same** design choice | None. |
| 15 | Recommendation: report process metrics with reward | Plan §5.4: process cost, termination and event extraction | **Same** | None. Cite them. |
| 16 | Scope: τ² retail+telecom; AWQ INT4 + FP8; 9B–35B models | τ² retail/airline/telecom, BFCL multi-turn, ALFWorld; GPTQ/AWQ/RTN at W4/W3, KV8/KV4, QuaRot A/KV; Qwen3-4B/8B | **Different** coverage | Broader quantizer and benchmark axes, but smaller models. Coverage breadth supports generality; it is not the contribution. |

## 5. What we can defend, and what we must not claim

### Increments we can defend (conditional on the numbers above holding)

1. **Same-state separation of action and continuation.**
   - At an immutable, replay-verified state we cross action source × continuation controller (BB, BQ, QB, QQ).
   - This identifies three things their whole-episode design cannot:
     - (i) the signed consequence of the quantized action alone (r, d, G);
     - (ii) the contribution of the recovering controller (H = Y_QB − Y_QQ);
     - (iii) whether the action's consequence depends on that controller (I).
   - Their design cannot identify these because each of their arms changes both factors at every step, and their episodes are not token-aligned (Fig. 7 caption).
2. **Recovery measured by intervention, not by observation.**
   - Their "recovery is equally reliable" (55%/55%) conditions on different failure states.
   - Our H and I hold the state fixed. Our results show the continuation controller changes the consequence of the same action in 15–33% of divergent states. Yet strict ranking reversal is rare (1.2–4.6%), so the sign of an action's consequence is mostly stable across controllers.
   - This sharpens their "recovery" account rather than contradicting it. Phrase it as a refinement.
3. **Two-sidedness attributed to the action.**
   - Rescue and damage of similar size (9.7% vs 9.0% at W4) are measured at the action level, on a coupled-randomness substrate, across τ², BFCL and ALFWorld.
   - Their 33/26/55 is task-level and includes user-simulator sampling noise.
4. **Persistence of consequence across nonces** (internal replication only). Task-level consequence rates and rescue direction replicate across a frozen nonce split. The direction holds beyond opportunity for rescues in 11/12 split-directions and for damage in 7/12.
5. **Breadth on the precision axis** (W3, KV8/KV4, QuaRot A/KV, GPTQ/RTN). This is supporting evidence, not a headline.

### Claims we must NOT make

- That we are the first to show a flat score or unchanged success hiding behavioural or process damage in quantized agents. This is their RQ1.
- That we are the first to show two-sided or offsetting task-level changes under W4 quantization. They report 33 worse / 26 better / 55 tied.
- That we discovered the error budget, retries or recovery masking quantization damage, or that telecom failures are user-side tool calls exhausting the budget. This is their RQ2, Table 2 and Fig. 7.
- Any repair-prompt result, or framing BF16 continuation as a mitigation. We have run no repair prompt; BF16 continuation is an oracle intervention.
- That our forks show budget masking, until E1/E2 below are run. Even after E1, a log projection is a projection.
- That their recovery claim is wrong. Our data show controller-dependence of consequences, not that their 55%/55% is incorrect.
- That "quantization amplifies the existing failure set" holds or fails for our models. We have no channel analysis yet.
- That their paper lacks paired analysis. It has paired-by-task tests and TOST. The precise statement is that it lacks **same-state** pairing.
- That they use only one model or one quantizer family. They have six checkpoints in two families, but **one INT4 method (AWQ)** and weight-only arms.
- "Equivalence" of our success rates. TOST fails under task resampling.

## 6. Concrete text and cheap experiments

### Intro (suggested, 3 sentences)

> Recent work shows that 4-bit agents on τ²-bench can keep a flat task score while their tool-call failures multiply, because the benchmark's error budget and the agent's own recovery absorb the extra errors (Jang et al., 2026). That account compares whole episodes at each precision, so the precision of the action that went wrong and the precision of the controller that must recover from it change together. We separate the two: at the exact state where a quantized agent first diverges from its BF16 reference, we cross the source of the current action with the controller that continues the episode, which measures the action's signed consequence and the recovering controller's contribution on identical histories.

### Related work (suggested, 3 sentences)

> Jang et al. (2026) find no significant BF16→INT4 score change across ten τ²-bench cells. In the most affected cell, failed tool calls rise 2.5×, a counterfactual tightening of the error budget re-exposes a 16.7-point gap, per-failure recovery rates are equal across precisions, and a reflexive repair prompt helps significantly only in that cell; they also report a two-sided paired task split (33 worse, 26 better). Their comparisons are task-level between independently sampled episodes, and their budget analysis is a projection from logs. Our four-branch replay holds the state, budget counters and randomness fixed while varying only the action source and the continuation controller, so rescue, damage and controller dependence (I) are estimated at the level of the decision rather than inferred from whole-episode rates.

### Cheap experiments that sharpen the distinction

| ID | Experiment | What it adds | Cost (our estimate) |
|---|---|---|---|
| **E1** | **Reproduce their S(K) projection** on our existing closed-loop Q and BF16 runs (τ² retail/airline/telecom dev; q4/q8 × GPTQ/AWQ-W4, KV8), and on each fork branch (BB/BQ/QB/QQ): success using ≤ K failed calls, K ∈ {2, 5, 10}. Report r(K), d(K), G(K). | Shows whether their masking pattern holds on our models and quantizers, and whether the projection changes the *balance* of rescue and damage. That is a question their whole-episode design cannot ask. | CPU only; error counters and termination reasons are already logged (`cloq/fork.py` budget record; `analysis/insights/iter_4/common4.py`) |
| **E2** | **Live budget intervention at fixed fork states** (their App. B "decisive version"). On a frozen, hash-sampled subset of first-divergence states, especially telecom dev where the budget binds, set the remaining error budget to a prespecified ladder (e.g. 1, 3, as-is) for **all four branches**, keeping the used counters (CONSEQUENCE_ANALYSIS_PLAN, declared resource intervention). | A live, same-state test of budget masking. It also tests whether controller dependence (I) shrinks as the budget tightens, which would quantify "recovery slack" interventionally. Must be labelled a change to the target environment. | Branches cost ~83 s each (FORK_PROTOCOL telecom estimate). About 100 states × 4 branches × 3 levels ≈ 1,200 branches. This is a rough estimate, to be confirmed by a dry run. |
| **E3** | **Channel replication**: on existing telecom/retail Q vs BF16 logs, compute the tool-name hallucination rate ("Tool 'X' not found"), the novel-name fraction and the per-name correlation, mirroring their Table 5. | Tells us whether "amplify, don't invent" holds at 4B/8B with GPTQ/RTN/KV, and whether our rescue/damage pivots concentrate in that channel. | CPU only |
| **E4** (optional) | **A repair prompt as a third continuation controller** at the same states: Q + reflexive repair vs Q vs B. | Separates "a better recovering controller" (prompt) from "a higher-precision controller", using their exact repair prompt from Fig. 8(c). Only worth running if E2 shows a budget-dependent I. | Similar to E2 for one extra branch per state |

Freeze the E1/E2 definitions (K ladder, state sample, endpoints) before reading outcomes, and label all results exploratory on dev data.

## 7. Verification status

| Claim about their paper | Status |
|---|---|
| Models, precision arms, recipes, serving, benchmark settings, user simulator, sample sizes per arm | Verified (Setup; App. C; Tables 1, 6) |
| Flat score; TOST ±7.5 in 7 cells; 33/26/55 | Verified (Results; Table 1) |
| 19.5% → 38.3%; 649 → 1,646; 5 → 46 exhaustions; 1.45 → 3.64 failed calls; 55%/55% recovery | Verified (Results; Table 2) |
| S(K) gap 1.3 / 7.5 / 16.7; +15.4 vs ≤ 0.2 | Verified (Results; Fig. 3) |
| Repair +5.9 [+1.1, +10.8]; interaction +3.7 [−3.2, +10.7] not significant | Verified (Table 3) |
| 0.97 correlation; 0.18% novel; 23/24 user-side tools | Verified (Results; Fig. 2; Table 5). The abstract's "≥ 0.94" is **not found in the body** |
| Multiple-comparison correction method | **Unverified**: not specified in the text |
| Exact definition of "recovery rate after a failure" | **Partially verified**: the phrase only; denominator not defined |
| Whether repair re-injects the tool inventory | **Inconsistent in the source** (Table 2 caption vs Fig. 8(c)) |
| Total episode counts (~13.7k base, ~6.8k repair) | **Inferred** by arithmetic, not stated |
| Later versions (v2+) | Only v1 listed as of 2026-09-30; recheck before submission |

Our-side numbers come from the repository files cited in §4. Strict reversal and I ≠ 0 per cell were read directly from `consequence_estimands_20261001T0224Z.json` (`pivot_four_branch_conditional`). All W67 and W68 results are exploratory and dev-only.
