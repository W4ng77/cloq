# Execution plan: tracing quantization consequences in closed-loop agents

Updated 2026-09-30, America/Toronto. Prepared against master snapshot [2c68559](https://github.com/W4ng77/cloq/tree/2c68559f619810dc82a2de008f2030656df1f420). This replaces the earlier schedule at this path. The author's instruction is to preserve substantial breadth and depth rather than make the project depend on one or two positive findings.

**Paper direction:** a methodology-driven empirical research paper on how quantization changes local decisions and their closed-loop consequences. The experimental method, replicated findings, reusable evidence, and a measured application form the contribution portfolio. A literature survey is supporting work. A new routing or calibration algorithm is a possible application contribution, conditional on evidence.

**Working title:** *Tracing the Consequences of Quantization in Closed-Loop Agents*.

**Research question:** how do the precision of the current action and the precision of subsequent execution affect task outcomes, which consequences persist across tasks and quantization configurations, and when is local precision information useful for an actual deployment decision?

**Evidence status:** the research question and work program can be fixed now. The stronger findings below remain hypotheses. This plan does not declare ranking reversal, transferable state fragility, success equivalence, or a useful learned policy to have been established.

**Resources:** 42 A6000s are the author's available ceiling. The committed resource inventory separately reported 38 held GPUs and six simulator replicas. Scheduling must use the live allocation, not turn either historical number into a current utilization claim. Experiment freeze is targeted for October 5 and submission for October 12, as specified by the author; dates in this plan are Toronto dates.

## 1. Entry points and authority

| Document | Role |
|---|---|
| [This execution plan](EXECUTION_PLAN_20260930.md) | Current scope, storyline, priorities, scheduling and acceptance rules |
| [Coverage plan](insights/QUANT_BENCHMARK_COVERAGE.md) | Quantizer, model, benchmark and factorial coverage; fidelity gates |
| [Consequence analysis plan](insights/CONSEQUENCE_ANALYSIS_PLAN.md) | Estimands, shared-state experiments, uncertainty, mechanisms, latent analysis and applications |
| [Related-work positioning](insights/RELATED_WORK_POSITIONING.md) | Primary-source comparisons, contribution boundaries and required baselines |
| [Current storyline](insights/STORYLINE_v6.md) | Manuscript structure and claim wording |
| [Current TODO](TODO_v2.md) | Implementable work packages and deliverables |
| [Night status](STATUS_20260930_night.md) | Historical result snapshot; W67 interpretations require the audits specified below |
| [Fork protocol](insights/FORK_PROTOCOL.md) | Implemented replay, budgets, scoring, gates and existing confirmation design |
| [Method fidelity](insights/METHOD_FIDELITY.md) | Verified A/KV and rotation configurations |
| [Resource plan](insights/RESOURCE_PLAN.md) | Simulator leases, canaries, drain-based allocation and monitoring |
| [Result index](../analysis/RESULTS_INDEX.md) / [research log](RESEARCH_LOG.md) | Provenance and chronological evidence |

Existing frozen manifests and registrations retain their historical status. This execution plan is not a preregistration and does not itself change a frozen endpoint, unlock holdout data, enqueue jobs, restart servers, or declare proposed code implemented. New confirmation endpoints require a dated amendment before unseen outcomes are read. Conflicts with stale planning prose are resolved using this plan; conflicts with a frozen scientific protocol require an explicit recorded amendment.

## 2. The paper's contribution portfolio

### 2.1 Contributions we intend to substantiate

1. **Precision-intervention methodology.** Independently vary the source of a complete current action and the controller used afterward, on verified identical histories and environments. Provide explicit estimands, replay controls, denominators, inference and a reusable output format. Forking and factorial design are established tools; the claim is their carefully validated use to answer precision-specific questions.
2. **A broad account of consequences.** Measure both rescue and new damage across weight, activation and KV compression, mild and damaging regimes, model scale/family and interactive task types. Relate aggregate changes to per-task and per-state heterogeneity, with separate fixed-pool and new-task uncertainty.
3. **Mechanism evidence.** Test several complementary explanations: semantic action differences, action–continuation interaction, irreversible operations and recovery, budget/context dependence, and structured quantization error versus matched perturbations. Latent diagnostics and controlled patching support this part when their fidelity gates pass.
4. **Decision relevance and reusable evidence.** Evaluate transport of action-value labels across continuation precision and quantizers. Where prediction is useful, test a bounded precision-intervention policy in the full environment. Release the audited protocol, manifests and supported data products.

The eight-page manuscript can merge contributions 2 and 3 into one empirical contribution. The full experiment portfolio remains in the appendix and reproducible artifacts.

### 2.2 Parallel research questions

| ID | Question | Evidence required; no positive answer is assumed |
|---|---|---|
| RQ1 | Which quantization settings change behavior and outcomes, and how much? | Balanced coverage, paired unintervened whole-episode outcomes, semantic actions, local consequences and process cost |
| RQ2 | How much comes from the current action, subsequent execution and their interaction? | Complete four-arm outcomes and their 16 binary patterns |
| RQ3 | What persists across nonces, tasks, calibration draws, quantizers and model families? | Independent replication; actual shared-state comparisons; explicit transport splits |
| RQ4 | Which pathways connect local changes to rescue, damage or absorption? | Blinded content labels, event traces and controlled error/budget/context interventions |
| RQ5 | Which observable signals predict useful intervention rather than merely disagreement? | Task-grouped evaluation of local proxies, risk, signed gains and continuation-matched labels |
| RQ6 | Does consequence information improve a practical precision decision? | Full closed-loop, information- and budget-matched application evaluation |

Strict ranking reversal is one RQ2 diagnostic. A learned router is one RQ6 experiment. Neither controls whether RQ1–RQ5 continue.

### 2.3 Claim strength follows results

- Report broad two-sided changes if they replicate; do not infer equivalence from a small mean.
- Report action–continuation interaction or ranking reversal only where matched four-arm evidence supports it.
- Report task-level regularity separately from state-level regularity. A task/nonce join does not establish identical states.
- Report useful prediction only on unseen tasks or declared transport splits; report useful control only after live closed-loop evaluation.
- If richer predictors or intervention policies do not improve outcomes, publish their measured limits and retain them as comparisons. Do not manufacture an algorithm claim.
- A mechanism claim needs a controlled contrast or intervention in addition to a visually appealing trace or embedding.
- A comprehensive matrix strengthens generality but does not substitute for a distinctive, independently checked finding. Acceptance at a particular venue cannot be guaranteed.

## 3. Existing evidence and reuse

The following is a snapshot of committed evidence, not a new analysis. Consult the result index before making numerical claims.

| Evidence | Treatment in the new paper |
|---|---|
| W4 task-outcome turnover above the validated numerical floor | Motivation, restricted to the tested serving/configuration conditions |
| Corrected H3: no detected persistent fingerprint for W4 recalibrations; random fixed perturbation fingerprint exploratory | Transparent audit appendix; no W4 fingerprint headline |
| Preregistered checkpoint-lottery tests did not support the hypothesis | Retain the negative confirmation; do not relabel later dev associations as its confirmation |
| Conditional act/talk changes largely reproduced by a selection null | Do not claim a quantization-specific act/talk channel without new unconditional and null-controlled evidence |
| W4 pivot swaps: pooled rescue 9.7%, damage 9.0%, M 18.7%, G +0.6 pp; crossed G interval includes zero | Initial two-sided-consequence evidence; specify checkpoint, task pool, block and scoring |
| KV8 and simulator-free BFCL/ALFWorld forks | External checks already worth reusing; adapters and scoring retain their own validity scope |
| Paired, checkpoint-aligned whole-episode success analyses; task-resampled TOST fails | Use correct NI/TOST language and all intervals; no global success-equivalence claim |
| Replay and server canaries, including q8/telecom and hook-specific checks | Reuse only for configurations actually covered; repeat gates for new configurations |
| Matched rotated-KV16 controls and q8 fixed-A16 W×KV registration | Preserve the registered four corners and six blocks; wider A4-cube interactions remain exploratory; keep rotation controlled |
| W67 task concentration, sign consistency and cross-quantizer overlap | Exploratory candidates requiring dependence, double-use and shared-state audits |
| Static restoration dominated by GPTQ-W4 at matched storage | Preserve the negative deployment result. Reuse restoration/dose data as mechanistic diagnostics, not as a claimed competitive method |

Create a reuse manifest with one row per source: source path/hash, generating script/commit, hardware/backend, task population, checkpoint/draw, nonce, endpoint definition, integrity status, permitted claim and required reanalysis. Never pool 4080 and A6000 results without a validated backend comparison and an explicit estimand.

## 4. Width: minimum coverage before expansion

The detailed matrix is in the [coverage plan](insights/QUANT_BENCHMARK_COVERAGE.md). Width is protected by a minimum viable panel; it is not left to whichever configurations first produce an attractive result.

### 4.1 Quantization panel

| Axis | Minimum panel | Additional informative coverage |
|---|---|---|
| Weight | BF16; RTN/GPTQ/AWQ at W4/W3 wherever faithfully supported | W6/W5 precision anchors, NF4/MXFP4, stochastic rounding, rotation with matched BF16; optional small W8-only reference for a specified low-error contrast, never a required full grid |
| Activation | A16, verified dynamic A8, SmoothQuant W8A8, verified QuaRot W4A4 | Within-family A-only and W-only contrasts; module-specific activation quantization |
| KV | KV16, K8V8, rotated K4V4, K-only and V-only | Plain low-bit stress controls; semantic-role and context-length sensitivity diagnostics |
| Joint axes | Existing matched rotated W×A×KV 2×2×2 cube | Separately identified A8-based deployment-style combinations; never combine incompatible families into one factorial interaction |
| Perturbations | Numerical no-ops/rotation controls; fixed norm/shape/sign-matched random errors | Multiple random seeds and residual-error dose; standard and structured error controls |
| Deployment | Fake-quant behavior under a common backend | A small native-format comparison if fidelity and measurement gates pass |

**Small W2 stress panel:** add q4 RTN-W2, q8 RTN-W2 and q8 GPTQ-W2 if supported faithfully (an AWQ alternative only for a declared support reason). Start on about 24 hash-selected, domain/difficulty-stratified tasks from the canonical 85, with one matched paired block and the same subset for BF16/W4/W3 references. Freeze IDs before outcomes. W2 is outside the minimum coverage floor; expand only under a prespecified runtime/coverage budget, never because its outcomes look interesting. Record destructive, invalid-output and looping behavior as adverse outcomes when the implementation passes its fidelity gate. A failed quantizer build is a support result. See the coverage contract for cell accounting.

Bit labels require actual grouping, scaling, clipping, outlier handling, residual policy and calibration records. An INT4 KV implementation without rotation is a stress implementation, not evidence that all INT4 KV methods fail.

**Author scope update:** W8-only is removed from the required weight panel. Its expected incremental value is lower than W3, joint-axis coverage and replicated mechanisms. SmoothQuant W8A8 remains an activation-method comparator, not a requirement to repeat a full W8 weight-only sweep. A8 and KV8 remain independent axes. Existing W8 results can be reused as references; no new W8-only cell is scheduled without an explicit contrast and marginal-cost justification.

### 4.2 Models and tasks

- **Dense core:** q4 and q8, with matched common populations.
- **Scale:** q14 plus one of q32/q30a3 for an audited panel. Existing large-model results should be reused before rebuilding.
- **Family:** an available second family from the model registry, after parser/template and BF16 capability checks. Weak valid performance is reported; a serving failure is not reported as a scientific zero.
- **Interactive task types:** τ² retail, airline and telecom development; BFCL multi-turn; ALFWorld.
- **Independent confirmation:** telecom's 34 protected tasks remain protected. Add independently frozen external task slices for transport only when their untouched status is documented.
- **Additional environment:** WebShop is an extension lane with an adapter/scoring/replay pilot. Keep it outside the core deadline dependency until the gate passes.
- **Population sensitivity:** retain the canonical 85 retail/airline tasks; separately audit the 22 previously excluded BF16-unstable tasks. The 57 calibration tasks are not a new independent test set.

For the existing snapshot, q8 W4 summaries may include 165 tasks (85 retail/airline + 80 telecom dev) while q4/KV summaries may include 85. Every comparison reports both the common-population panel and cell-specific full coverage. Raw rates from these different populations do not identify a model-size or quantizer effect.

### 4.3 Coverage floor and replication ladder

1. Validate each implementation and adapter without holdout outcomes.
2. Give every feasible minimum-panel cell a pilot with the same prespecified task IDs and nonce rules. Unsupported, failed and not-run cells remain visible.
3. Complete the first balanced evaluable panel before adding many repeats to a single promising cell.
4. Use the same ladder as the coverage plan: one complete paired block for the balanced first panel; three completed paired blocks as the descriptive breadth floor; five as the preferred expansion target where throughput permits. None guarantees sufficient statistical power. Existing q4/q8 core cells with about 20 blocks and the registered six-block W×KV test retain their designs. Extend paired contrast families jointly rather than only attractive cells.
5. Add blocks on prespecified precision/coverage criteria using development variance and measured runtime. Allocate equally within contrast families; do not allocate by observed effect sign or significance.
6. Larger models and extra formats may use a frozen task subset for cost. Hash/stratify it before their outcomes and publish its membership; do not call that subset the full benchmark.
7. Record checkpoint variation separately: d1 is the existing primary checkpoint; d2 is the minimum calibration-draw transport panel where feasible, with d3/d4 reused for exploratory stability. Two draws are not enough to characterize a general checkpoint population.

If throughput falls, first reduce redundant repetitions uniformly within a tier. Preserve minimum axes, task types and valid contrasts. More nonces cannot replace missing task diversity. Scientific validity gates remain mandatory even when breadth is a priority.

## 5. Depth: a portfolio of complementary analyses

### 5.1 Complete four-arm consequences

At one immutable pre-action history, let B denote BF16 and Q the declared quantized configuration:

| Current action | B continuation | Q continuation |
|---|---:|---:|
| B action | Y_BB | Y_BQ |
| Q action | Y_QB | Y_QQ |

Use complete generated and parsed actions, not a tool-start token or top-k proxy. Preserve the current loss-oriented decomposition:

\[
A=Y_{BB}-Y_{QB},\qquad C=Y_{BB}-Y_{BQ},
\]
\[
I=Y_{BQ}+Y_{QB}-Y_{BB}-Y_{QQ}.
\]

Intervention gains relative to QQ are

\[
G=Y_{BQ}-Y_{QQ}=A+I,\quad
H=Y_{QB}-Y_{QQ}=C+I,\quad
F=Y_{BB}-Y_{QQ}=A+C+I.
\]

F is both action and continuation replacement; H is escalation after retaining Q's action. Neither is the gain of a cheap single-action replacement.

Report rescue, damage, M and net gain for each intervention on its correct denominator. Include all 16 binary outcome patterns. Strict action-ranking reversal means

\[
(Y_{BB}-Y_{QB})(Y_{BQ}-Y_{QQ})<0.
\]

Nonzero I does not imply strict reversal. With stochastic continuations, individual realized patterns are not proof of a reversal in expected action value; use repeated matched continuations and uncertainty.

### 5.2 Two state banks with different purposes

**Bank P: first semantic divergence.** Reuse the existing full-task design. First semantic divergence concerns act/talk type, complete tool name or normalized arguments; text-only differences are recorded separately. No-divergence units retain the protocol's zero action-swap effect. Missing or unreplayable units are not recoded as no divergence.

**Bank U: ordinary Q decision states.** Hash-sample eligible decision states from genuine Q prefixes before consulting terminal outcomes or BF16 agreement. Stratify by prefix-visible action type, time and remaining budget. Include agreement states. Freeze history, prompt IDs, both environment states, counters and cache/re-prefill policy.

Bank P answers a selected-pivot intervention question. Bank U supports cross-quantizer comparison, proxy evaluation, label transport and deployable triggers. Multiple states from a task/episode remain clustered and cannot be counted as independent tasks.

For Bank U, do not impute suffix-controller effects to zero merely because the current actions agree. The first-divergence task-pool estimand and the ordinary-state estimand are reported separately.

### 5.3 Heterogeneity, persistence and transport

- Reanalyze W67 concentration against baselines preserving shared-block dependence and task heterogeneity.
- Split nonces into discovery and validation sets before assigning task direction or fragility; repeat with symmetric splits as a sensitivity analysis. Splits of already viewed development runs are internal replication, not independent confirmation. Fresh untouched tasks/blocks are identified separately.
- Compare d1 and d2 on the same immutable Bank U histories and suffix controllers. A task/nonce alignment alone is insufficient.
- Let GPTQ, AWQ and KV variants propose actions on the same history, then compare them under a common declared continuation. Add B-continuation counterparts for the four-arm extension.
- Separate within-task nonce replication, new-task prediction, new-draw transport, new-quantizer transport and cross-model transport.
- Treat benchmark composition as a sensitivity analysis with explicit weights. Reweighting to manufacture a positive average is not a new result.

### 5.4 Semantic pathways and real process cost

Measure wrong tool/argument/ID, premature completion, consent-before-write, irreversible state mutation, retry loops, transfer, successful correction and budget exhaustion. Distinguish a syntactically different action, a benchmark error, a policy violation and an outcome-changing event.

Use automatic extraction for checkable fields; a frozen blinded LLM rubric for semantic fields; about 80 author/collaborator-reviewed states, with about 20 double-reviewed. Sample across rescue/damage/unchanged outcomes and task types, not just dramatic failures. Labeling instructions and disagreement adjudication precede unblinding.

Report turns, agent and simulator tokens, tool calls, errors, recovery overhead and termination. DB success, official task-basis success and any stricter assertion/judge score retain their separate names.

### 5.5 Controlled recovery, budget and context tests

- Freeze representative semantic error categories from development and inject matched valid/invalid actions at identical states.
- Compare recovery under B and Q with the same remaining step/error budget. Include negative-control injections that should not alter the requirement.
- Evaluate a small prespecified ladder of step/error budgets by live continuation; a truncation of existing logs is a diagnostic projection and receives that label.
- For context stress, replay exactly the same retained history and token budget across configurations; distinguish length, truncation and relevant-information position.
- Report failure to reproduce an injected natural error's effect. Synthetic interventions are a separate population.
- Simulator robustness uses paired matched conditions with one alternative validated simulator or a small human/scripted-user check. Do not mix simulator changes into a precision contrast.

### 5.6 Perturbation, dose and module diagnostics

Preserve the existing matched-random controls and error-dose results. Add only controlled diagnostic arms: weight norm/shape/sign, K versus V, attention versus MLP, and early/middle/late layers, with storage- or intervention-size-matched random controls.

Residual interpolation \(W_\alpha=W+\alpha(W_Q-W)\) is an error-dose experiment. Alpha controls residual-error dose, not numerical precision or deployable bits. W5/W6 are separate actual-bit experiments. Local BF16 restoration remains a mechanism contrast; the existing dominated storage frontier is retained.

Assess whether local distortion, complete semantic changes and task consequences respond similarly to dose. Do not assume higher BF16 agreement monotonically improves task success.

### 5.7 Latent analysis and bounded activation patching

The latent lane is part of depth, with its own fidelity gate rather than an untested promise:

1. Run an offline HF diagnostic engine on a frozen same-history Bank U subset. Verify tokenizer/template, logits/actions and quantizer semantics against the serving reference; document deviations.
2. Extract residual-stream, attention and MLP outputs at fixed token positions: action boundary, tool-name/argument spans and matched history segments.
3. Compare norms, angular changes, attention-output distortion, layer profiles and representation similarity on identical inputs. Contrast rescue, damage and unchanged outcomes without using those outcome labels as deployable features.
4. Train simple diagnostic probes under task-grouped splits. Report whether they add predictive information beyond action disagreement, margin and task metadata. Correlation/probe accuracy alone is not a causal mechanism.
5. On a small frozen subset, patch one module/layer segment B→Q and use sham, random-vector and magnitude-matched controls. Rerun the complete tail with one consistent diagnostic engine and budget.
6. Record effects on full action semantics and terminal outcome. A patch that changes logits but not outcomes is an informative negative result.

Do not start whole-model training or a large PRM project to finish this lane. If engine parity fails, publish the fidelity limit and retain trace/event/module diagnostics; never silently pool incomparable HF and vLLM results.

## 6. Applications and closest baselines

See [positioning](insights/RELATED_WORK_POSITIONING.md). Controlled supervision comparisons are required for label/prediction claims. Competitive precision-routing claims additionally require the closest complete-method comparisons:

1. **Controlled supervision:** same ordinary-state pool, prefix-visible features, learner capacity and execution rule; compare KL/margin, semantic disagreement, Q-failure risk, unsigned consequence and signed intervention-specific outcome supervision.
2. **Closest methods:** DMR KL-ST and KL-ST plus trajectory-reward refinement; a prefix-only action-conditioned utility witness; and a same-state action comparator inspired by COTA. Exact replication and controlled reimplementation are labelled differently.

The first application is **label transport**: train/evaluate an action comparator under B versus Q continuation and test it under the declared deployment continuation. Measure selected-action value, regret and new damage on independently collected, held-out-state branch outcomes, rather than only AUROC. This establishes label/prediction transport for the declared state distribution; it is not a deployed-policy benefit claim and does not require full routing-method training.

The second application, if engineering and development support permit, is **one-trigger precision intervention**. Before the first trigger, follow Q. At the trigger choose none, action-only BQ, suffix-only QB or both BB, with the chosen continuation fixed afterward. Choosing none commits to Q through termination; repeated re-triggering requires a different prospective protocol. Compare against action-only supervision and closest routing baselines under one frozen primary resource constraint, such as average BF16 generated tokens per episode; report all other costs separately. Set thresholds and expected-budget targets on development, report realized test-budget drift, and never retrospectively match observed test trajectories. A per-episode hard cap that forces B→Q fallback or truncation changes the controller: define it separately, recollect its labels and evaluate it live instead of reusing fixed-tail QB/BB values.

Use prefix-visible inputs only. BF16 previews, rollout lookahead, classifier computation, both resident models and label-generation simulator calls are charged when used. Allow DMR multiple precision decisions under the same primary resource constraint; do not weaken its execution policy to obtain a favorable comparison. If full-method training or engineering is infeasible, report the limitation and restrict competitive routing claims; the empirical and label-transport contributions continue.

Fork outcomes at oracle first divergences are not an end-to-end policy evaluation. The existing oracle union/rescue statistics are not the value of an action-only policy.

Consequence-preserving quantizer calibration is a bounded extension, not a deadline dependency. If explored, alter quantizer parameters rather than retrain the LLM, use a separate calibration population, and compare against task-trajectory/action-token calibration plus MSE/KL and unsigned weighting at identical bits and compute. Keep helpful Q changes as well as harmful changes in the objective. A new importance weight alone does not establish algorithm novelty.

Fake quantization is sufficient for the numerical-behavior study. It does not establish native memory, latency or throughput savings. With fake quantization, report BF16-call/token allocation as a logical resource budget and backend cost separately. Native deployment claims require actual measurements.

## 7. Statistics, confirmation and reporting

The [analysis plan](insights/CONSEQUENCE_ANALYSIS_PLAN.md) gives full rules. Mandatory points:

- Preserve the existing confirmation primary endpoint G_all. New pattern, interaction, transport and mechanism hypotheses are exploratory on viewed development data and can become registered secondary endpoints only before unseen confirmation outcomes.
- Keep telecom's 34 holdout tasks and preregistration-hash guard. Do not unlock them through this plan update.
- Report fixed-task/declared-checkpoint block inference, crossed new-task uncertainty, and checkpoint generalization separately. Nonces are shared prompt perturbations, not independent task replicates or an unrestricted sample of deployment randomness.
- Resample complete shared blocks jointly across paired cells. For new-task intervals resample task and block indices in a crossed design, retaining common identities and stratification.
- Use the common population for paired comparisons. Publish cell-specific coverage and unresolved missingness, and retain agent-caused failures in the endpoint.
- W67's iid-binomial and unrestricted task-permutation references do not by themselves establish systematic direction or state fragility. Audit their exchangeability assumptions.
- Retain the previously specified 3 pp NI/equivalence and practical-gain margins where applicable; do not enlarge margins after viewing results. A margin for a different endpoint needs its own justification and prospective registration.
- Failing to reject a difference, or a CI containing zero, is not equivalence. Both sides of an equivalence interval must meet the declared bounds.
- Define multiplicity families before confirmation. Report effect sizes and intervals for all cells, including failures and negative effects.
- Any rank/fragility label selected from outcome data is validated on separate blocks/tasks. A pooled correlation across doses is not evidence of within-dose prediction.
- Quarantine residual systematic replay bias. Additional stochastic repeats cannot repair hidden-state loss or cross-branch contamination.

Do not retrofit conformal into the core. A statistical collaborator's main remit is estimands, crossed inference, rare/degenerate contrasts, multiplicity and prospective confirmation.

## 8. Resource plan and budget governance

### 8.1 Two budgets must be tracked

1. **GPU budget:** agent, simulator, checkpoint construction, diagnostic extraction, application learning and native benchmarking hours.
2. **Environment budget:** requests/turns, concurrent simulator leases, tail duration and benchmark reset cost.

Every work package has predicted and observed agent GPU-hours, simulator GPU-hours, calls/tokens, p50/p90 suffix time, retries and engineering dependencies. The old 80k-episode estimate is a historical approximation, not an assurance that all extensions fit.

### 8.2 Allocation principles

| Use | Operating rule |
|---|---|
| Simulators | Use the registry's healthy replicas; current committed layout had six (12 GPUs). Add the ready seventh only when the existing load threshold and measured throughput justify it; drain via leases |
| Small agents/forks | q4 B/Q packing only on validated memory/canary settings; q8 B and Q need separate cards at the recorded context length |
| Large models | Allocate local NVLink pairs for TP=2 servers; no assumed fast cross-node parallelism |
| Simulator-free backlog | Always maintain BFCL/ALFWorld, builds, local probes, representation extraction and analysis tasks |
| Stress tasks | Bound concurrency; preserve the same scientific caps across compared arms; never silently truncate only expensive configurations |
| Existing paused work | Reuse artifacts; keep dominated restoration tasks as low-priority diagnostics rather than deleting results or interrupting jobs |
| Reserve | Keep explicit capacity for replay quarantine/retries and independent confirmation |

After the first balanced coverage panel, use an initial GPU-hour planning split of 30% shared-state replication/confirmation, 20% coverage expansion, 20% mechanisms/latent diagnostics, 10% applications/closest baselines and 20% reserve. Before that panel is complete, coverage may borrow discretionary depth/application capacity while confirmation remains protected. This is a planning allocation, not live usage. Simulator GPUs count in the corresponding workstream cost. Independently retain 20% of schedulable time to the freeze as a p90 completion/outage reserve, as specified in the coverage plan; GPU-hour and wall-clock reserves are two constraints, not a doubled experiment charge.

The minimum coverage panel has reserved capacity. When adapting the schedule, reduce repetitions uniformly or move named extensions to a later release; never quietly collapse the paper to the one cell with the best result.

### 8.3 Queue safety and utilization

- Read live runner allocations, GPU probes, healthy simulator registry, lease count and queue load before generating tasks.
- Use task-generator dry runs; check split and prereg guards, config hashes, checkpoint availability, dependencies, GPU count and remaining budget.
- Split tasks into resumable small groups. Record attempted, complete, quarantined, unsupported and not-run states.
- Route new tasks through the existing balancer. Running episodes keep their simulator.
- Add/retire replicas by draining, not an all-runner restart. A documentation update provides no evidence that a cluster operation has occurred.
- Keep checkpoint building ahead of evaluation and preserve content hashes. Store reusable captures/results outside temporary runner scratch according to the existing artifact policy.
- Report utilization and scientific throughput, not just occupied cards. Reevaluate every six hours using measured p90 costs; maintain a reserve for long tails.

### 8.4 Loop early stopping and stress-run caps

Low-bit loops are part of the scientific outcome and a resource risk. Add an explicit, prospective loop guard to **new stress panels**, with identical policy for every compared configuration and branch, including BF16. Existing frozen primary/confirmation runs retain their registered stop rules; do not mix old-cap and new-guard success values into one paired estimate. This plan specifies proposed behavior, not an implemented or validated guard.

1. **Conservative candidate rule:** inspect at most the last 16 agent decisions. A cycle of length 1–4 must repeat at least four complete times, with identical canonical actions (tool name and complete normalized arguments, or full normalized talk text), matching tool-result digests, unchanged task-relevant environment/DB hash and no new user-information event. Preserve IDs, numeric arguments and action order when canonicalizing. If required evidence is unavailable, the guard does not fire. Repeated tool names, long output or a classifier's impression alone are insufficient.
2. **Separate lack of progress from legitimate repetition:** calls on different IDs, iterative writes that change state, new tool results, new user requirements and valid multi-item work reset the cycle. A read-only repeated lookup needs result/history evidence; an unchanged DB alone cannot establish a loop. Text-only loops require the full repeated assistant/user turn evidence. No loop decision is based on final success or which precision arm is running.
3. **Candidate validation before launch:** test on a frozen sample of approximately 20 obvious-loop and 30 legitimate-repetition/long-success traces, blinded to configuration, reusing the annotation lane. Pin normalization, thresholds and code hash before the stress outcomes. Continue a small declared sample with the original cap to measure premature stopping; report any successes the guard would cut off. If false positives appear, tighten or disable the rule and record the revision before new runs.
4. **Endpoint and logs:** a guard termination is an algorithmic failure under that panel's explicitly loop-guarded success definition, with reason loop_early_stop. Retain the last-window evidence, cycle length/repeats, action/result/environment hashes, budget counters and tokens/tool calls consumed. Report loop incidence and guarded success alongside a declared original-cap sensitivity; do not assert every early stop would inevitably have failed under a longer cap.
5. **Other caps:** pin common max steps, error budget, per-generation max tokens and any total episode-token cap. Actual GPU memory/build faults and blocked/dead serving requests remain infrastructure incidents with exact-input recovery and attempt accounting. A watchdog may release stalled workers, but infrastructure interruption is not silently recoded as a model loop. A prospective wall-time cap, if used as an endpoint, is identical across compared arms and reported separately because backend speed affects it.
6. **Queue integration:** terminate and persist an eligible looping episode immediately, then release its simulator/agent capacity and continue the next task. Bound W2/W3/KV4 stress concurrency using live leases; short-cycle detection is complementary to the common hard caps. Do not kill or change already running episodes merely because this documentation changed.

The guard provides an explicit evaluation contract and prevents repeated unproductive suffix work. It is not a repair method or evidence that a low-bit agent lacks recovery under all longer budgets.

## 9. Parallel work packages

| WP | Owner role | Work | Outputs / acceptance |
|---|---|---|---|
| WP0 | Audit/statistics | Reuse manifest, population alignment, W67 null audit, result integrity | OLD_RESULT_REUSE.csv, coverage and inference audit; old invalid claims removed |
| WP1 | Fork analysis | 16 patterns, all contrasts, strict reversal, split-block stability | Complete-pattern table, uncertainty, all-cell outcome matrix |
| WP2 | Quantization engineer | Baseline panels, matched W/A/KV families and bounded W2 stress | QUANT_MATRIX.csv, fidelity records, balanced coverage states and pinned stress subset |
| WP3 | Benchmark/model engineer | BFCL/ALFWorld completion, q14/large model/family panels, WebShop pilot | BENCHMARK_MATRIX.csv; pinned manifests and adapter gates |
| WP4 | Shared-state engineer | Bank U, cross-quantizer proposals and fixed-tail comparisons | STATE_BANK manifest, hashes, matched proposal/outcome table |
| WP5 | Mechanisms/annotation | Events, blinded rubric, human review, recovery and budget/context interventions; loop-guard validation | ANNOTATION_PROTOCOL.md, labelled samples, controlled pathway contrasts and loop false-positive audit |
| WP6 | Representation engineer | HF parity, local hidden captures, probes, bounded patching | LATENT_FIDELITY.json, layer diagnostics and controlled patch outcomes |
| WP7 | Application engineer | Label transport, supervised signal controls, DMR-style comparisons, live intervention pilot | Budgeted performance and training-cost curves; no oracle policy claim |
| WP8 | Confirmation/statistics | Prospective protocol amendment, holdout execution and crossed intervals | PREREG_FORK_CONFIRM.md with frozen hash; confirmation tables |
| WP9 | Writing/artifacts | Current storyline, primary-source references, claim ledger and figures | Eight-page draft, appendix coverage, reproducibility package |

Roles can share workers. Each owner checks the current queue before creating duplicates. This table assigns responsibilities, not a claim that ten engineering agents or all implementations already exist.

## 10. Schedule through evidence freeze

| Toronto date | Required progress | Parallel work |
|---|---|---|
| Sep 30 night–Oct 1 | Reconcile old results and populations; produce 16-pattern/W67 audits; freeze coverage/task/cost manifests | Finish existing matched rotation controls; start Bank U; model/adapter and HF diagnostic pilots |
| Oct 1–2 | Complete balanced minimum weight/A/KV and benchmark panels; start shared-state cross-quantizer runs | Annotation and latent extraction; recovery/budget/context contrasts; independent blocks/draw transport |
| Oct 2–3 | Summarize development evidence across all RQs; freeze confirmation endpoints and cut points before holdout access | Label-transport and controlled supervision tests; closest-baseline pilot; human review |
| Oct 3–4 | Run protected telecom confirmation and declared external untouched slices | Full closed-loop application if eligible; simulator robustness; remaining feasible coverage repetitions |
| Oct 4–5 | Resolve integrity issues, finish registered analyses and negative/unsupported-cell reporting | Native-format measurements if gated; finalize figures, claims and reproducible artifacts |
| Oct 5 | Freeze evidence with snapshot/script hashes and explicit incomplete lanes | Writing continues through the author's Oct 12 submission target |

Each morning publish expected completion against measured p90 runtime and live resources. Cut dates apply to engineering scope, not to whether a result is positive. A failed optional fidelity gate limits that lane; it does not reopen retired equivalence/fingerprint stories or replace registered endpoints.

## 11. Manuscript storyline and figures

The introduction should make three connected points: local precision changes can alter complete agent actions; an action's consequence is evaluated through a specific subsequent controller; evaluating and allocating precision therefore requires both directions of outcome change and the declared continuation.

Suggested eight-page allocation: introduction/related work 1.5 pages, setting and methodology 1.5, broad outcomes and consequences 2, mechanism/transport 1.5, application/limitations/conclusion 1.5. Adjust to the evidence; do not claim measurements still pending.

| Item | Content |
|---|---|
| Figure 1 | One real, independently reviewed state with four branches; accompanying aggregate rescue/damage/net effect. The case illustrates the finding, not estimates its frequency |
| Table 1 | Model × benchmark × quantization coverage, task/block counts, scoring and fidelity; compressed main panel plus complete appendix |
| Figure 2 | Precision-axis outcome and consequence heatmaps/curves, including mild and damaging regimes |
| Figure 3 | Four-arm outcome patterns and current-action/suffix/interactions with intervals |
| Figure 4 | Stable heterogeneity and actual shared-state/continuation label transport |
| Figure 5 | Controlled pathway/patch/budget evidence for supported mechanisms; negative controls shown |
| Figure 6 or Table 2 | Application outcome versus actual resource budget, plus label-generation cost; use only if live evaluation completed |
| Appendix | All cells, priors/registration, corrected H3, retired stories, unsupported implementations, full annotations and replay details |

Do not fit every speculative interpretation into the abstract. At freeze, choose the two or three strongest independently supported findings from the prespecified broad portfolio and show their scope. The portfolio is fixed; headline strengths remain evidence-dependent.

## 12. Definition of complete

- [ ] All feasible minimum-panel axes and task types have a declared completed/unsupported/not-run status.
- [ ] Every displayed cell has checkpoint/config/task/block/score and integrity provenance.
- [ ] Four-arm, shared-state and process analyses use explicit populations and correct shared-block dependence.
- [ ] Viewed development findings and unseen confirmation are clearly separated.
- [ ] Complete action generation, tool typing and success naming are correct; top-k approximations are not called exact probabilities/KL.
- [ ] Closest prior work is accurately credited; no unsupported first/novelty claim.
- [ ] Mechanism statements distinguish association from controlled evidence.
- [ ] Prediction/label-transport applications use held-out branch outcomes and available information; policy/deployment claims additionally use fresh full closed-loop episodes. Training, label acquisition and inference costs are charged; competitive routing claims include complete-method comparisons.
- [ ] Fake numerical effects and native systems efficiency are reported separately.
- [ ] Negative, inconclusive, invalid and incomplete lanes remain visible.
- [ ] CLAIM_EVIDENCE.md maps every abstract/main-text assertion to a frozen result and its limitations.

This plan preserves breadth, protects depth and fixes the research problem without predetermining its answer.
