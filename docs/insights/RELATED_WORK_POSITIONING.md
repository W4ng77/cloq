# Related-work positioning and comparison plan

Status: research plan, 2026-09-30 America/Toronto (2026-10-01 UTC). This document accompanies the execution plan; it does not change a frozen preregistration or turn an exploratory result into a confirmatory one. Method descriptions below refer to the explicitly linked versions inspected during the review. A later version can change the comparison.

## 1. Contribution target

The defensible target is a **quantization evaluation methodology, replicated quantization-specific findings, a reusable branch dataset, and application validation**. A new router, new causal estimator, or new quantizer is not a prerequisite for completing this contribution. Nor is adding a name to an existing estimator a contribution.

The paper should establish what numerical fidelity and whole-episode scores miss, identify which conclusions survive controlled intervention and replication, and show how another researcher or deployment engineer can use the resulting evidence. This is a joint evidence package, not a bet that one subgroup or one controller will win.

| Component | Concrete deliverable | What would make it useful | What would weaken the claim |
|---|---|---|---|
| Methodology | Audited replay and an action-source × continuation-policy experiment, with an explicit target population and uncertainty | Separates the consequence of a changed action from the ability of a subsequent controller to recover; makes policy-dependent conclusions inspectable | Replay fidelity alone; an unexplained four-cell table; calling standard factorial contrasts a new causal estimator |
| Replicated findings | A prespecified collection of weight, activation, and KV comparisons where feasible, across task groups and more than one independent model setting | Quantifies both beneficial and harmful changes, their heterogeneity, and the limits of proxy-based ranking | A pooled cancellation statistic alone, repeated nonces treated as independent tasks, or one favorable stress cell |
| Reusable resource | Branch manifests, integrity checks, outcome tables, split definitions, and executable analyses with appropriate release permissions | Supports new proxy studies, controlled supervision comparisons, and reproduction of all reported denominators | Only aggregate plots; unavailable pivot states; labels that silently change with the continuation policy |
| Application validation | A held-out decision made using the evidence, with its actual costs and consequences | Demonstrates use in precision selection, targeted validation, or a bounded intervention policy | Treating retrospective oracle gains as a deployed policy; claiming a novel routing algorithm without comparison |

Publication suitability depends on the completed evidence, not on this positioning text. The strongest scope is narrower than “quantization changes behavior” and broader than “our router gained a few points.”

## 2. Closest primary sources and exact overlap

The following is a targeted audit, not an exhaustive survey. “Difference to test” describes a candidate empirical distinction, not established novelty. Sources are preprints unless their venue status is separately verified; do not imply main-conference acceptance from a workshop association.

### 2.1 Quantized agents and model switching

| Source and inspected location | Already covered | Difference to test in CLOQ |
|---|---|---|
| **Dynamic Mixed-Precision Routing for Efficient Multi-step LLM Interaction (DMR)**, [arXiv:2602.02711v2](https://arxiv.org/html/2602.02711v2), §§4.1–4.3 and Appendices C–D | A trajectory-conditioned precision router; action-distribution KL supervision at shared high-precision trajectory states; supervised initialization followed by GRPO using episode reward and latency. The paper explicitly treats KL as a local surrogate and studies deployment-state shift. | Quantization-specific branch evidence that separates signed action consequences from continuation effects. Demonstrate whether it improves prediction, data efficiency, or decisions beyond both KL supervision and outcome-optimized routing. “Outcome-aware precision routing” is not an available novelty claim. |
| **Flat Score, Amplified Failures: How the Error Budget Masks Damage in Quantized LLM Agents**, [arXiv:2607.27275v1](https://arxiv.org/html/2607.27275v1), experimental protocol, error-budget analysis, and Appendix B | Nearly flat success can coexist with more tool errors; tolerance for errors can mask operational differences. It compares whole-episode precision conditions and includes budget and repair analyses. | Same-state intervention can distinguish harmful, helpful, and outcome-neutral action changes, including how a fixed subsequent policy changes their consequences. Do not repackage flat score plus changed behavior as the central novelty. |
| **The Replay Gap: Static Evaluation of Model Switching in LLM Agents Scores the Wrong World**, [arXiv:2608.08239v1](https://arxiv.org/pdf/2608.08239v1), §3 and replay-fidelity experiments; [author code](https://github.com/AshrithaG/replay-gap) | Reconstructed executable prefixes, live continuation after model switching, and checks showing that static replay can evaluate the wrong future. The inspected manuscript is associated with a COLM workshop, not evidence of a COLM main-track paper. | A quantization experiment crossing the current action with the subsequent controller, rather than a continuation switch alone; a larger replicated consequence dataset if completed. Live forking and faithful replay are established ingredients. |

### 2.2 Counterfactual intervention, credit assignment, and routing

| Source and inspected location | Already covered | Difference to test in CLOQ |
|---|---|---|
| **Look Ahead Before You Distill: Future Trajectory Validation of Teacher Guidance for Agentic On-Policy Distillation (FutureBridge-OPD)**, [arXiv:2608.01953v2](https://arxiv.org/html/2608.01953v2), §3.2, Eqs. 4–6, and Appendix B | At most one teacher bridge per trajectory; the same restored history and a frozen student continuation; downstream validation of a local replacement. Its training gate uses future teacher-preferred token density, not a terminal environment-return difference. | Terminal consequence and numerical-precision specificity. One intervention, returning to the original policy, and testing whether reference guidance helps are not themselves new. Its motivating failed-trajectory subset should not be compared directly with CLOQ's all-unit rates. |
| **Don't Solve, Just Compare: Tiny Advisors for Runtime Intervention in LLM Agents (COTA)**, [arXiv:2608.21027v1](https://arxiv.org/html/2608.21027v1), §3.2, Eqs. 7–8, Appendix A.3 | Same-prefix sibling actions followed by the same frozen actor; downstream returns supervise a small pairwise comparator with ties. At runtime, preferred alternatives become non-binding advice and the actor replans. | Quantization-specific four-cell diagnosis and a rigorously costed adaptation, not the invention of fork-supervised action comparison. **Version limit:** the latest v2 listing was verified during review, but its full method was unavailable; this row describes v1 only. Recheck v2 before submission. |
| **Calibration Is Not Control: Why LLM-Agent Oversight Needs Intervention**, [arXiv:2606.21399v1](https://arxiv.org/html/2606.21399v1), §2.1, Eq. 1, §3, and §4.1 | Failure risk differs from intervention advantage. Same-prefix branches expose utilities of continue/intervene/quit; a prefix-only per-action utility witness demonstrates information lost by scalar risk routing. | Numerical perturbations create a controlled family of action alternatives and continuation policies. “Predict benefit rather than failure” and prefix utility estimation are already covered; use the witness as a comparison. |
| **Policy-Conditioned Counterfactual Credit for Verifiable Reinforcement Learning of Long-Horizon Language Agents (CVT-RL)**, [arXiv:2606.05263v1](https://arxiv.org/html/2606.05263v1), §3.2, Eq. 4 | Terminal verified outcomes under a specified frozen continuation policy, intervention-validity gating, and counterfactual credit for policy training. Interventions include evidence, tool-output, and textual changes. | Study a concrete numerical treatment and controller interaction. Do not claim counterfactual credit transfers to arbitrary future policies without evidence; the continuation policy is part of the estimand. |
| **Counterfactual Rollout Replay: Forkable Environments as Free Process Rewards for Software Engineering Agents (CRR)**, [arXiv:2609.33875v2](https://arxiv.org/html/2609.33875v2), §4.1, Eq. 2 | Forkable environments yield signed terminal-return contrasts between an original trajectory and an alternative-action rollout; the resulting signal trains an agent. | A quantization evaluation resource and replicated treatment decomposition. Neither signed fork labels nor generating process supervision without human step labels is new. Simulation and GPU costs still exist even when rewards need no human annotation. |
| **CounterRoute: Self-Routed Reasoning via Hierarchical Counterfactual Credit Assignment**, [arXiv:2609.29109v2](https://arxiv.org/html/2609.29109v2), §3.2 | Paired mode outcomes generate signed, cost-adjusted credit for the routing token, with separate within-mode optimization. | A mid-trajectory quantized-agent intervention is a different setting, but signed counterfactual routing supervision is already covered. |
| **Causal LLM Routing: End-to-End Regret Minimization from Observational Data**, [arXiv:2505.16037v2](https://arxiv.org/html/2505.16037v2), §2 | Cost-sensitive routing with counterfactual utility estimation from observational query–model data, using causal identification assumptions and doubly robust estimation. | Executable same-state branches provide different evidence from observational missing-outcome estimation. Do not claim generic causal or utility-based routing novelty. |
| **Causal Agent Replay: Counterfactual Attribution for LLM-Agent Failures (CAR)**, [arXiv:2606.08275v1](https://arxiv.org/html/2606.08275v1), §2 | Explicit action interventions and policy replacement from a chosen step onward, plus attribution of interacting steps. | A controlled numerical treatment and its replicated action × continuation pattern may be useful. “We intervene on actions and policies” is insufficient as a distinction; report the actual factorial results and their implications. |

The generic pattern “restore a state, change an action, keep the subsequent policy fixed, compare returns” is established. Four cells can make a specific question identifiable, but the experiment's scientific value must come from what it resolves about quantization and what decisions it enables.

### 2.3 Agent-aware and task-aware quantization

| Source and inspected location | Already covered | Difference to test in CLOQ |
|---|---|---|
| **TriAxialKV: Toward Extreme Low-Precision KV-Cache Quantization for Agentic Inference Tasks**, [arXiv:2605.17170v1](https://arxiv.org/html/2605.17170v1), §§3.1.3–3.1.4 and §3.2 | Semantic, temporal, and modal token tags; attention-output MSE calibration by tag; INT2/INT4 allocation under a cache budget; an implemented serving system and agentic evaluations. | Terminal consequences may reveal limits of local attention reconstruction. Agent-aware KV calibration and budgeted precision allocation are already covered. |
| **QuantWAMs: Calibrating at the Right Granularity for World Action Models**, [arXiv:2607.28405v1](https://arxiv.org/html/2607.28405v1), §§3.2–3.3, Eqs. 18–22, and §6 | Joint video–action saliency for weight precision; immutable rollout snapshots with matched randomness; budget-neutral schedule repair using local discrepancy on reachable states. It explicitly distinguishes this one-call diagnostic from marginal task gain. | Terminal action consequences under fixed continuations, and transfer of useful supervision beyond calibration tasks. Real-state replay and task-aware precision repair alone are not new. |
| **You Had One Job: Per-Task Quantization Using LLMs' Hidden Representations (TAQ/TAQO)**, [arXiv:2511.06516v1](https://arxiv.org/html/2511.06516v1), §§3.1–3.2 | Task-conditioned hidden-state scoring, quantizer-parameter calibration, and direct task-sensitivity tests for allocating layer precision. | Closed-loop, signed consequences could supply a different calibration signal; merely protecting task-important layers is already covered. |

## 3. Claims that should and should not be made

| Proposed wording | Assessment | Defensible replacement or requirement |
|---|---|---|
| “We discover equal accuracy can hide behavioral changes.” | Too broad and already covered. | State the measured quantization-specific consequence pattern and its uncertainty. |
| “The first causal evaluation / counterfactual router for agents.” | Unsupported by this audit. | Describe the exact treatment, target population, continuation policies, and reusable implementation. |
| “BF16 is an oracle action.” | Incorrect in this experiment. | BF16 supplies a reference action that can rescue or damage an episode. A label-informed best-branch policy is a retrospective oracle. |
| “A large behavior flip rate means quantization is harmful.” | Does not follow. | Report rescue, damage, both-success, and both-failure outcomes; keep unsigned change separate from signed net effect. |
| “The same tasks are fragile, therefore the same states are fragile.” | Requires more evidence. | Different quantizers can diverge at different states. Claim task-instance susceptibility unless states and pivot times are actually matched. |
| “One-shot signed routing is the new method.” | Strong overlap with the intervention and routing literature. | Treat it as an application of the evaluation resource unless a separately demonstrated methodological advance survives the comparisons below. |
| “Quantization is success-rate equivalent.” | Requires a task-generalizing equivalence analysis and a justified margin. | Preserve the current distinction between point estimates, non-inferiority, and equivalence. Failure to reject a difference is not equivalence. |
| “We make inference faster.” | Not supported by fake quantization or fewer nominal bits alone. | Make behavioral conclusions under the tested execution path; claim speed only after a real-kernel, end-to-end measurement. |

Use a claim-to-evidence table in the paper draft. Every headline should name its population, direction, uncertainty, replication setting, and confirmatory or exploratory status. Mixed or null findings remain part of the resource and should not be replaced by a new favorable subgroup after inspection.

## 4. Two levels of baseline comparisons

These levels answer different questions. A controlled comparison isolates a supervision signal; a method comparison tests competitiveness with a complete existing approach. Neither substitutes for the other.

### Level 1: Controlled supervision and decision comparisons

Use the same task-level train/validation/test partition, the same collected states, the same available features, the same predictor capacity, the same hyperparameter-search budget, and the same intervention mechanism. Keep sibling branches and repeated nonces of a task in one partition. Fix thresholds on validation data. Do not train a large language comparator for one label and a small linear model for another and attribute the gap to supervision.

Candidate targets are listed below. The signed and unsigned targets are definitions for comparisons, not proposed new estimators. With `B` denoting the reference action/policy and `Q` the quantized one, `Y_BQ` uses B's action followed by Q, while `Y_QQ` uses Q's action followed by Q.

| Comparison | Supervision or score | Question answered |
|---|---|---|
| Random and fixed-time policies | No learned signal; match eligible states and intervention counts | Is any gain just extra reference compute or favorable timing? |
| Task/prefix-only difficulty control | Task metadata and prefix information available before the action | Does a new signal add value beyond broad task susceptibility? Avoid memorizing task IDs when claiming unseen-task transfer. |
| Quantized-policy uncertainty | Entropy, margin, or related quantities available without a reference query | Can a cheap local signal achieve the same decision quality? |
| Reference-alignment target | Action disagreement or action-distribution KL on the shared state | Is matching the reference sufficient? Distinguish a learned predictor of this target from observing reference logits online. |
| Continuation-risk target | Outcome of the unmodified Q continuation | Does predicting failure suffice? |
| Unsigned consequence target | Probability that the two branch outcomes differ | Is predicting sensitivity sufficient, even without its direction? |
| Signed consequence target | Expected `Y_BQ - Y_QQ`, or rescue/damage/tie probabilities with a declared tie rule | Does the direction of consequence change the useful intervention ranking? |
| Per-action utility witness | Predict each available action's outcome/utility from the prefix; select using the same cost rule | Is a direct advantage head better than a standard action-conditional value formulation? |

Match state distributions as well as sample counts. A first-disagreement dataset is appropriate for a first-disagreement estimand, but a deployable policy cannot identify that state for free if it requires running both models. For a general runtime trigger, collect ordinary Q-visited states, including agreement and outcome-neutral states, and measure the cost of screening. Do not silently train at oracle-selected pivots and evaluate at arbitrary prefixes.

For a deployment application, a frozen one-intervention policy is a useful initial scope because its pre-trigger trajectory remains Q-controlled and its post-trigger continuation matches the label definition. This restriction is a scope control, not novelty. Repeated interventions need new on-policy evaluation because local gains do not simply add after the state distribution changes.

Evaluate both prediction and decisions: calibration and ranking on held-out states; rescue and damage among selected states; net utility at matched budgets; realized whole-episode success, steps, tool errors, and cost. A prediction/label-transport conclusion uses independently collected held-out branch outcomes and is restricted to its declared state distribution. A deployed-policy or routing-utility conclusion additionally requires fresh end-to-end episodes; a retrospective sum of selected oracle branch labels is insufficient.

### Level 2: Closest complete methods and honest adaptations

This level is required for competitive routing claims. Label-transport and controlled prediction comparisons can stand on held-out branch outcomes and Level 1 controls without completing full routing-method training.

1. **DMR comparison.** Include both KL-supervised training (`KL-ST`, this document's shorthand) and its GRPO-refined stage. A KL threshold alone is not a reproduction of the complete method. Run a feasibility pilot and allocate a declared compute budget before inspecting application test results. Compare both fixed-resource results and a cost–quality curve when feasible. If the full stage cannot be run credibly, document the limitation and remove any claim of beating the full approach.

2. **Prefix-utility witness.** Implement a compact action-conditional utility model inspired by *Calibration Is Not Control*, using the same features, split, predictor budget, and action choices as the proposed application. Report this as a controlled adaptation unless the original protocol is reproduced. Comparing a signed head only against failure risk would omit this closer alternative.

3. **COTA-inspired comparator.** Use the same branch pool to train a pairwise comparator, including ties and action-order checks where applicable. For signal isolation, give it the same candidates and the same execution rule. Separately evaluate advice-and-replanning if making claims about the full intervention mechanism. A two-candidate forced-action comparator is a controlled adaptation, not a reproduction of the original multi-candidate advisor.

4. **Reference-alignment and future-alignment proxies.** Include local alignment targets and, where already available at reasonable offline cost, a future reference-preference target inspired by FutureBridge-OPD. Offline future information can supervise a prefix predictor; it cannot be supplied to the deployed policy for free. Running counterfactual continuations online makes this an online-search baseline, with the full search cost charged.

Do not mandate a full retraining of every cited system to finish the paper. Prioritize the closest precision-routing method, the two strong controlled intervention formulations, and appropriate quantization baselines. The remaining sources establish attribution and scope. If a complete comparison is infeasible, narrow the competitiveness claim instead of relabeling a weaker adaptation as the original method.

### Cost ledger for both levels

Record the following per method, stage, seed, and budget point:

- Number of source tasks, source episodes, sampled states, and distinct branch outcomes. Duplicating action order or labels does not create new environment observations.
- Simulator/environment calls and steps, generated tokens, reference-model tokens, quantized-model tokens, label generation GPU-hours, training GPU-hours, and tuning GPU-hours.
- At deployment: screening cost, reference queries, candidate generation, comparator calls, replanning, switches, cache rebuild/re-prefill, and failed episodes. Include unsuccessful episodes in time and cost summaries.
- Hardware, batching, concurrency, model residency, cache policy, software versions, seeds, and wall-clock measurement procedure.
- Both reused-data and total-data accounting. A method receiving existing forks has an amortized-cost advantage only if the fork collection cost is also disclosed.

A fixed number of high-precision calls is a useful experimental budget but is not equivalent to measured latency, memory, or energy. Report these as separate quantities.

## 5. What the factorial experiment needs to establish

The four branches are `BB`, `BQ`, `QB`, and `QQ`: first letter = current action source; second letter = subsequent policy. Their outcome differences have distinct meanings:

- `Y_BQ - Y_QQ`: replacing the current Q action while retaining Q afterward.
- `Y_QB - Y_QQ`: escalating the subsequent controller after Q's action.
- `Y_BB - Y_QB`: the action replacement effect under B continuation.
- `(Y_BB - Y_QB) - (Y_BQ - Y_QQ)`: how the action effect depends on the continuation policy.

These are standard controlled contrasts. Their estimands must be defined over a declared pivot-selection population and randomness coupling. They are not automatically natural direct/indirect effects or an additive decomposition of the total full-episode precision gap. Keep the repository's signed loss-based `A/C/I` convention where used; do not mix outcome and loss signs across tables.

The useful scientific questions are whether consequences cancel, whether recovery changes their direction, whether numerical proxies rank them, and whether the patterns replicate across genuinely distinct cells. For stochastic environments, a single matched draw estimates a coupled branch contrast; repeated continuations are needed to assess expected effects and label stability. Describe task-level and seed-level uncertainty separately.

Do not make all of these questions pass/fail prerequisites for a paper. Report the predefined matrix with coverage and uncertainty, preserve the preregistered primary endpoint, and label new tests as exploratory until an untouched replication set is used. A collection of adequately estimated nulls can constrain precision interventions; an underpowered collection of nulls cannot establish their irrelevance.

## 6. Dataset and reusable analysis requirements

The resource should permit a new researcher to reconstruct the claims without guessing hidden selection rules. Subject to benchmark and model terms, release or document:

- Stable task, episode, checkpoint, quantizer/calibration-seed, state, and branch identifiers; schema and version hashes; complete eligibility and exclusion reasons.
- Pivot selection, semantic action canonicalization, actor-visible prefix, environment snapshot or reconstruction recipe, remaining budgets, RNG state/coupling, user simulator state, and cache handling.
- The two candidate actions, continuation policy per branch, raw outcome and termination reason, resource use, and replay-gate results. Preserve all four outcomes, including ties and invalid branches.
- Task-level split manifests; chronology of preregistration and amendments; outcome-blind selection code; separate exploratory and confirmatory outputs.
- Scripts for coverage tables, clustered uncertainty, consequence distributions, proxy benchmarking, and budget curves. Include a small executable example with an integrity check.

Provide a dataset card with scope limitations: reference policy is not ground truth; first-pivot sampling is selective; labels depend on the tail policy, horizon, tool/user simulator, and stochastic coupling; fake-quantization results characterize the tested numerical path. Counts must distinguish tasks, task–nonce units, forks, and training examples.

## 7. Optional consequence-preserving calibration: bounded exploration

This is a future-method candidate, not a deadline-critical requirement and not a claimed completed algorithm. Existing work already covers task-aware calibration and budgeted precision allocation. A useful new experiment would test whether terminal consequence supervision changes a quantizer in a way that local reconstruction or alignment supervision cannot reproduce.

Before launching training, specify the actual quantizer parameters to change, the fixed bit/storage budget, the surrogate loss, and why that loss can preserve beneficial deviations while reducing harmful ones. Merely weighting reconstruction by unsigned importance tends to preserve reference behavior regardless of whether the reference helps. Conversely, a signed weight on a squared reconstruction loss can make the objective ill-posed; do not introduce it without a valid bounded formulation.

Use one bounded pilot with a fixed tuning budget and a stop rule. Compare generic calibration, task-trajectory calibration, action-focused calibration, and local KL/MSE weighting using the same data and quantization implementation. Evaluate on untouched tasks and, if feasible, an additional quantizer or model setting. Record all pilot outcomes. If there is no stable matched-budget benefit, retain the diagnostic conclusion and stop; do not expand into full new model training to rescue the deadline.

## 8. Execution and reporting decisions

The execution plan should assign owners and resources to four parallel deliverables: replay/data integrity, replicated numerical-treatment comparisons, controlled proxy/intervention comparisons, and resource packaging. Application experiments can proceed while replication completes; their outcome must not determine which completed cells are reported.

Before submission, update this document with actual implementation status, exact baseline commits, source-version changes, and a table separating reproduced methods from adaptations. Resolve the COTA v2 access gap. Recheck cited primary versions and any venue claims. Keep broad review coverage in the related-work section while placing the most direct experimental comparisons in the main results.

The final claim should reflect the completed evidence: a controlled and reusable account of when numerical changes matter for agents, how that depends on subsequent control, and which inexpensive signals or interventions are useful under stated budgets. A winning router or calibration pilot can strengthen that account; neither should be used to replace missing replication or justify a novelty claim contradicted by the sources above.
