# Closed-Loop Calibration for Quantized LLM Agents
## 2×RTX 4080 Frozen Diagnostic Plan (v0)

**Working title:** *Compression Changes What Agents See: Closed-Loop Calibration for Quantized LLM Agents*

---

## 0. Core question

Standard PTQ assumes that a fixed calibration distribution is representative of deployment. A tool-using agent violates this assumption because its own actions determine future observations and conversation history.

For a full-precision agent \(\pi\) and quantized agent \(\hat\pi\),

\[
a_t \sim \pi(\cdot\mid x_t),\qquad
x_{t+1}=F(x_t,a_t,o_{t+1}).
\]

A small quantization-induced action change can therefore alter future context:

\[
\text{quantization}
\rightarrow
\text{action/tool-call drift}
\rightarrow
\text{future-context drift}
\rightarrow
\text{calibration mismatch}
\rightarrow
\text{further error}.
\]

The project tests whether PTQ should calibrate on the **state distribution induced by the deployed agent**, rather than on static prompts or only full-precision trajectories.

---

# 1. Research questions

### RQ1 — Horizon amplification
Does quantization degradation increase with task/trajectory length even when open-loop action fidelity remains high?

### RQ2 — Calibration distribution
At the same calibration budget, does calibration on full-precision agent trajectories outperform static/initial-state calibration?

### RQ3 — Compression-induced occupancy shift
After the first quantization-induced action divergence, does the quantized agent visit contexts farther from the original calibration support?

### RQ4 — Closed-loop refresh
Can one round of calibration on states visited by the quantized agent recover long-horizon task success?

### RQ5 — Generalization
Does the effect survive held-out tasks and, later, a second interactive-agent benchmark?

---

# 2. Why start with a pure LLM tool agent

The first diagnostic should remove vision/grounding as confounders. A state is purely textual/structured:

\[
x_t =
(\text{system policy},
\text{task/user history},
\text{tool schemas},
\text{previous tool calls},
\text{tool outputs}).
\]

Thus any closed-loop distribution shift comes from sequential agent decisions, not screenshot encoding or visual grounding.

The VLM/GUI extension comes only after this phenomenon is established.

---

# 3. Model and agent scaffold

## Primary model

**Qwen3-4B-Instruct-2507**

Freeze:
- exact Hugging Face revision/hash;
- tokenizer revision;
- Transformers/vLLM version;
- tool-calling template/parser;
- generation settings.

Primary generation:
- greedy / temperature 0;
- no sampling;
- fixed maximum action-generation tokens;
- exact same system prompt and tool schema across all precision arms.

## Agent scaffold

Use the benchmark's canonical tool-calling scaffold where possible.

Do **not** introduce:
- planning modules;
- reflection;
- retry heuristics unique to one arm;
- verifier models;
- memory compression;
- different tool parsers across precisions.

The only manipulated variable in the main experiment is **quantization calibration data**.

---

# 4. Benchmark choice

## Primary 2×4080 diagnostic: latest τ-bench/τ³ text-mode codebase

Use two non-RAG text domains first:
- retail;
- airline.

Why:
- pure LLM tool use;
- sequential database-changing actions;
- dynamic interaction;
- tool schemas and policy constraints;
- end-state evaluators;
- no visual confounder.

Avoid the knowledge/RAG domain in v0 because retrieval introduces another distribution-changing component.

## External validation after v0

If the signal is real:
1. WebArena/BrowserGym text observation, or
2. WorkArena/WorkArena++ text/AXTree observation.

This second benchmark removes the simulated-user component and tests a different interaction loop.

---

# 5. User simulator control

The user simulator is **never quantized**.

Freeze:
- simulator model/provider;
- simulator prompt;
- temperature = 0 if supported;
- benchmark version;
- task seed;
- initial database state.

For paired comparisons, every precision arm receives the same task specification, initial database state, and simulator configuration.

If a local simulator is used:
- GPU 0: fixed BF16 user simulator;
- GPU 1: agent model.

If an external fixed simulator is used:
- both 4080s can run independent agent workers.

Record every user turn so trajectories are auditable.

---

# 6. Task split

Do not choose tasks using quantized outcomes.

For each domain:

1. run a **BF16-only pilot**;
2. characterize each task by:
   - BF16 success;
   - number of agent turns/tool calls;
   - environment stability;
3. freeze the task pool before any PTQ comparison.

### Diagnostic target

Aim for approximately:
- 20 calibration tasks/domain;
- 30 held-out evaluation tasks/domain.

Total target:
- ~40 calibration tasks;
- ~60 held-out tasks.

If the exact benchmark version has fewer usable tasks, preserve a **40/60 calibration/evaluation ratio** and document the exact counts.

### Split rule

Task IDs are disjoint:

\[
T_{\rm cal}\cap T_{\rm test}=\varnothing.
\]

Stratify by BF16 trajectory length so the held-out set contains short, medium, and long tasks.

No evaluation task trajectory may enter quantization calibration.

---

# 7. What is a trajectory state?

At every agent decision point save the exact model input immediately before action generation:

\[
x_t =
(\text{policy/system},
\text{dialogue},
\text{tool definitions},
\text{past tool calls},
\text{tool outputs}).
\]

Store:

- domain / task ID / task seed;
- turn and tool-call index;
- exact serialized messages;
- exact tool schema;
- tokenized input IDs;
- attention mask;
- generated assistant/tool-call text;
- parsed tool name and arguments;
- tool result;
- user response;
- reward / end-state score;
- termination reason;
- parser/tool errors;
- context token count;
- model/scaffold/environment hashes.

Do **not** store hidden activations permanently.

Replay exact stored contexts when building calibration statistics or analysis embeddings.

---

# 8. Context policy

Long trajectories create a context-length confounder, so serialization/truncation must be identical across arms.

Freeze one context function:

1. always retain system/domain policy;
2. always retain full tool schema;
3. retain current user request;
4. retain the most recent interaction/tool history up to the token budget;
5. apply the same left-truncation rule to all arms.

Primary v0 maximum context:
- **8192 tokens**.

Record pre- and post-truncation lengths.

No arm may receive a different history-management strategy.

---

# 9. Quantization

## Primary setting

- weight-only GPTQ;
- W4;
- group size 128;
- activations BF16;
- embeddings BF16;
- LM head BF16;
- quantize decoder attention/MLP linear layers;
- same damping/order/grouping for all GPTQ arms.

All quantized checkpoints are created **from the same original BF16 checkpoint**.

Never quantize an already quantized checkpoint.

## Pre-specified stress setting

If W4 causes <1 percentage-point absolute task-success degradation relative to BF16 **and** no measurable first-divergence/occupancy effect, run exactly one stress replicate:

- W3, same group size and protocol.

Do not search additional bit widths after seeing outcomes.

---

# 10. Calibration-budget matching

This is critical.

Trajectory states are typically longer than initial/static states. Therefore matching only the number of sequences is insufficient.

## Primary budget

Match **total non-padding calibration tokens**:

\[
B_{\rm tok}=64{,}000
\]

per arm, within ±1%.

Use streaming layerwise GPTQ; batch size can be 1.

Also report:
- number of calibration contexts;
- median context length;
- total calibration tokens.

## Secondary control

If the primary result is positive, add a **state-count-matched** control with the same number of contexts per arm.

This separates:
- equal calibration compute/tokens;
- equal number of sampled states.

---

# 11. Main calibration arms

## A. Static-GPTQ

Calibration contexts contain:
- domain/system policy;
- tool schemas;
- initial user/task context;
- no executed tool trajectory.

Sample initial states from calibration tasks until the fixed token budget is reached.

This represents conventional static deployment-aware PTQ.

---

## B. FP-Traj-GPTQ

Run the BF16 agent on calibration tasks.

Uniformly sample intermediate decision states from the BF16 trajectories, stratified by normalized depth:

- 25% from quartile 1;
- 25% from quartile 2;
- 25% from quartile 3;
- 25% from quartile 4.

Continue sampling until the same \(64k\) token budget is reached.

All states use uniform calibration weight in v0.

This tests **trajectory support** without adding a new importance score.

---

## C. CLOQ — one-round closed-loop occupancy refresh

1. Quantize FP-Traj to obtain \(Q_0\).
2. Run \(Q_0\) closed-loop on the **calibration tasks only**.
3. Collect the states actually visited by \(Q_0\).
4. Build a new fixed-budget calibration buffer:

\[
\mu_{\rm CLOQ}
=
0.5\mu_{\rm FP}
+
0.5\mu_{Q_0}.
\]

At the token level:
- ~32k tokens from FP trajectory states;
- ~32k tokens from \(Q_0\)-trajectory states.

Use the same depth stratification when possible.

5. Re-quantize from the **original BF16 checkpoint**.

This is the core proposed method.

---

## D. Optional diagnostic: Q-only

Only if CLOQ works.

Use only \(Q_0\)-visited calibration states at the same token budget.

Purpose:
test whether preserving FP support is necessary or whether quantized occupancy alone suffices.

Not part of the first overnight run.

---

# 12. Reference/baselines

Required:
1. BF16;
2. Static-GPTQ;
3. FP-Traj-GPTQ;
4. CLOQ.

Cheap optional baseline:
5. RTN W4, no calibration.

Later full paper:
- demo/historical-trajectory calibration if exact benchmark-version trajectories are compatible;
- a second quantizer (e.g. AWQ) to test whether the occupancy effect is solver-independent.

Do not add these before the core phenomenon is established.

---

# 13. Evaluation protocol

Run all four required arms on exactly the same held-out tasks.

Primary endpoint:
- benchmark task success / end-state correctness.

Secondary:
- policy compliance/end-state components if provided;
- valid tool-call rate;
- parser error rate;
- number of tool calls;
- conversation turns;
- premature termination;
- repeated/looping tool calls.

Primary contrasts:
1. FP-Traj − Static;
2. CLOQ − FP-Traj;
3. CLOQ − Static.

Use paired task-level bootstrap:
- resample held-out task IDs;
- 10,000 replicates;
- report 95% CI.

Report both domains separately and pooled only if the metric is definitionally identical.

---

# 14. Horizon amplification

Define task horizon using the **BF16 trajectory**, never the quantized trajectory.

Preferred horizon variable:
- number of BF16 agent decision/tool-call steps.

Bucket held-out tasks by BF16 horizon quartile.

For method \(m\):

\[
\Delta_m(H)
=
SR_{\rm BF16}(H)-SR_m(H).
\]

Main figure:

- x-axis: BF16 horizon quartile;
- y-axis: success degradation from BF16;
- curves: Static, FP-Traj, CLOQ.

Key test:
does Static degradation increase more sharply with horizon than FP-Traj/CLOQ?

Also report continuous rank correlation between BF16 horizon and per-task quantization failure.

---

# 15. Open-loop fidelity

For every held-out BF16 trajectory state, replay the exact context into each quantized agent **without executing the predicted action**.

Measure:

### Tool-name agreement
\[
\Pr[\hat a^{\rm tool}=a_{\rm FP}^{\rm tool}]
\]

### Full normalized tool-call agreement
Exact match after canonicalizing:
- tool name;
- argument keys;
- whitespace/order;
- equivalent numeric/string formatting.

### Teacher-forced action NLL
\[
-\log p_Q(a_{\rm FP}\mid x_{\rm FP})
\]

### Argument-level accuracy
For matching tool names:
- exact argument-value match;
- field-level F1.

The key diagnostic is:

> high open-loop fidelity + much lower closed-loop success.

That pattern directly supports compounding distribution shift.

---

# 16. First-divergence analysis

For each paired BF16/quantized task from the same initial state, define

\[
t^\star =
\min\{t:\operatorname{Norm}(a_t^Q)\neq
\operatorname{Norm}(a_t^{FP})\}.
\]

Report:
- fraction with any divergence;
- median \(t^\star\);
- normalized divergence location \(t^\star/H_{\rm FP}\);
- task success conditional on early/late/no divergence.

Important:
after \(t^\star\), environments/history differ. Do **not** compare later action strings step-by-step as if states remained aligned.

Use occupancy metrics after divergence.

---

# 17. Measuring occupancy/context shift

Use the frozen BF16 Qwen model as the representation extractor.

For every stored context, replay it and extract a fixed representation:

Primary:
- final-layer hidden state at the assistant action-generation boundary.

Secondary:
- mean hidden state over the most recent tool/user observation tokens.

Freeze the representation rule before analysis.

For a visited quantized-policy state \(x\), define distance to calibration support:

\[
D_{\rm supp}(x;\mathcal C)
=
\min_{z\in\mathcal C}
[1-\cos(\phi(x),\phi(z))].
\]

Report:

1. FP states → Static calibration support;
2. FP states → FP-Traj support;
3. Q states → Static support;
4. Q states → FP-Traj support;
5. Q states → CLOQ support.

Most important comparison:

\[
D_{\rm supp}(x_{t>t^\star})
\quad\text{vs}\quad
D_{\rm supp}(x_{t<t^\star}).
\]

If quantization changes occupancy, support distance should increase after divergence.

Secondary two-sample metric:
- MMD between \(d_{\rm FP}\) and \(d_Q\) hidden representations.

Optional:
- logistic two-sample classifier AUC in appendix only.

---

# 18. What CLOQ is supposed to fix

CLOQ should not merely improve average reconstruction.

The mechanistic prediction is:

1. Static under-covers intermediate agent contexts.
2. FP-Traj covers nominal deployment trajectories better.
3. Quantization creates off-nominal states absent from FP trajectories.
4. CLOQ explicitly inserts those \(Q_0\)-visited states into calibration.
5. The refreshed quantizer should:
   - delay first divergence;
   - lower post-divergence support distance;
   - improve long-horizon task success.

This causal chain should be tested explicitly.

---

# 19. Failure-state analysis

Do not discard failed calibration trajectories.

For each \(Q_0\) state record whether it occurs:
- before any divergence;
- immediately after first divergence;
- in a parser/tool error;
- during repeated tool usage;
- near unsuccessful termination.

If CLOQ works, report what fraction of its Q-state budget comes from these categories.

Later method extension:
sample Q states by novelty/support distance.

Do **not** introduce this weighting in v0.

---

# 20. Two-GPU execution schedule

## Preferred mode: external/fixed user simulator

Both GPUs run agent workers.

### GPU 0
- BF16 calibration trajectories;
- half BF16 held-out evaluation;
- later half of quantized evaluations.

### GPU 1
- other half BF16 evaluation;
- GPTQ construction;
- later half quantized evaluations.

After FP-Traj is built:
- split \(Q_0\) calibration rollouts across GPUs;
- build CLOQ;
- split CLOQ held-out evaluation.

## Zero-API mode: local user simulator

### GPU 0
- fixed BF16 user-simulator server.

### GPU 1
- BF16 / Static / FP-Traj / CLOQ agent, sequentially.

This is slower but cleaner than quantizing/changing the simulator.

---

# 21. Overnight execution order

### Phase 0 — Pipeline sanity
- 3–5 benchmark tasks;
- BF16 agent;
- confirm tool parsing, task reset, deterministic logging;
- no paper conclusions.

### Phase 1 — BF16 pilot
- run candidate tasks;
- freeze calibration/test task IDs and horizon strata.

### Phase 2 — Collect BF16 calibration/test trajectories
- write immutable manifests.

### Phase 3 — Build Static and FP-Traj GPTQ
- verify exact token budgets;
- run unit tests on quantized checkpoints.

### Phase 4 — Held-out Static/FP-Traj evaluation
- compute success, open-loop fidelity, first divergence.

### Phase 5 — Collect \(Q_0\) calibration trajectories
- \(Q_0 =\) FP-Traj GPTQ.

### Phase 6 — Build CLOQ
- 50/50 FP/Q token budget;
- re-quantize from BF16.

### Phase 7 — CLOQ held-out evaluation
- same task IDs/seeds.

### Phase 8 — occupancy analysis
- replay stored contexts with BF16 representation extractor;
- produce support-distance plots.

---

# 22. Artifact schema

Every run writes:

```text
runs/<run_id>/
  config.json
  environment.json
  model.json
  task_manifest.json
  calibration_manifest.json
  quantization.json
  trajectory.jsonl
  predictions_or_actions.jsonl
  metrics.json
  status.json
```

`status.json` must be `completed` before a run enters analysis.

`calibration_manifest.json` records:
- exact task IDs;
- trajectory IDs;
- decision indices;
- token counts;
- source arm (static / FP / Q);
- SHA256 of serialized model input.

This prevents accidental calibration/test leakage.

---

# 23. Integrity checks

Before reporting any result assert:

- same original BF16 checkpoint;
- same tokenizer/tool template;
- same agent scaffold;
- same task version;
- same user-simulator configuration;
- same tool schemas;
- same generation settings;
- same evaluation task IDs;
- calibration/test task disjointness;
- same primary token budget ±1%;
- same quantizer settings;
- no failed/incomplete run;
- CLOQ quantized from BF16, not \(Q_0\).

Also report context-length distributions for each calibration arm.

---

# 24. Pre-specified continuation rules

Proceed to the full paper if at least **two of the following three** appear:

### Signal A — Horizon amplification
Long-horizon tasks show larger Static-GPTQ degradation than short tasks.

### Signal B — Occupancy shift
Support distance increases after first divergence and \(d_Q\) is measurably separated from \(d_{\rm FP}\).

### Signal C — Trajectory calibration
FP-Traj improves either:
- closed-loop success,
- first-divergence position,
- or post-divergence support coverage
over Static at matched token budget.

### Strong method signal
CLOQ improves over FP-Traj at the same calibration token budget.

---

# 25. Stop / rethink rules

Stop or substantially revise the project if:

1. W3 still produces negligible closed-loop degradation;
2. quantized and BF16 occupancies remain indistinguishable;
3. FP-Traj never improves any closed-loop/divergence metric;
4. CLOQ adds Q-policy states but does not improve coverage or behavior.

Do not move to 7B merely to search for a favorable result.

---

# 26. Full-paper expansion if v0 works

## Model scale
- Qwen/OpenCUA-class 7B model on A6000 48GB;
- second open agent checkpoint for model generality.

## Benchmarks
Primary:
- τ³ tool-agent benchmark.

External:
- WebArena/BrowserGym or WorkArena++.

## Additional baselines
- Demo/Historical-Traj calibration;
- RTN;
- second quantizer such as AWQ;
- Q-only calibration;
- success-only vs all-trajectory calibration.

## Method extension
Only after CLOQ works:

### CLOQ-Novel
Preferentially sample Q-policy states that are far from FP calibration support:

\[
w(x)\propto
\operatorname{clip}
(D_{\rm supp}(x;\mathcal C_{\rm FP})).
\]

This becomes the small “criticality/novelty” method on top of the core occupancy result.

---

# 27. Expected paper figures

### Fig. 1 — Concept
Static PTQ versus closed-loop agent calibration:
quantization changes action → changes future context → leaves calibration support.

### Fig. 2 — Horizon amplification
BF16-minus-quantized success vs BF16 horizon quartile.

### Fig. 3 — First divergence
Distribution of \(t^\star/H\) for Static, FP-Traj, CLOQ.

### Fig. 4 — Occupancy drift around divergence
Support distance aligned at \(t^\star=0\).

### Fig. 5 — Method result
Static → FP-Traj → CLOQ success at equal calibration token budget.

### Fig. 6 — Open-loop/closed-loop mismatch
Action fidelity on FP states vs actual closed-loop task success.

---

# 28. Desired paper-level claims

If supported, the paper should make five claims:

1. **Compression changes the state distribution that an agent subsequently observes.**
2. **The resulting closed-loop degradation grows with task horizon.**
3. **Static PTQ calibration under-covers intermediate deployment contexts.**
4. **Full-precision trajectory calibration improves robustness at matched calibration budget.**
5. **A single on-policy calibration refresh recovers part of the loss without training the policy or changing inference-time operators.**

The novelty is therefore not “another importance score.” It is a new PTQ setting:

\[
\boxed{\text{calibration distribution is policy-dependent}}
\]

and a minimal method:

\[
\boxed{\text{one-round on-policy calibration refresh}}
\]

---

# 29. Immediate 2×4080 deliverables

The first run should produce only these deliverables:

1. frozen task/calibration manifests;
2. BF16 trajectories;
3. Static-W4 checkpoint;
4. FP-Traj-W4 checkpoint;
5. paired held-out closed-loop results;
6. open-loop action agreement/NLL;
7. first-divergence statistics;
8. FP-vs-Q occupancy-distance analysis;
9. CLOQ-W4 checkpoint and evaluation if Signals A/B/C justify continuation.

No VLM experiment, no Fisher weighting, no additional bit search, and no second model in the first diagnostic.
