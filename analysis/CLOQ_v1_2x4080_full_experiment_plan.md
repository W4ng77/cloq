# CLOQ v1 — Two-RTX-4080 Saturation Plan
## Closed-Loop Support Refresh for Quantized LLM Agents

**Status:** freeze before starting v1  
**Model:** Qwen/Qwen3-4B-Instruct-2507, revision cdbee75f17c0  
**Environment:** tau2-bench text mode, retail + airline  
**Quantizer:** GPTQ W4 / group 128  
**Hardware:** 2× RTX 4080

## 0. v1 objective

v0 established three reproducible phenomena:
1. long-horizon amplification;
2. high open-loop fidelity can coexist with low closed-loop success;
3. support distance jumps after first behavioral divergence.

v0 did **not** establish a stable method win. The likely problem is calibration support: the 64k-token budget contained only ~10–13 contexts, and the CLOQ on-policy half contained only 5 Q0 contexts.

v1 therefore fixes both:
- number of independent agent states;
- number of GPTQ activation rows.

The method question becomes:

> Does refreshing calibration with **quantization-induced novel/post-divergence states** outperform nominal trajectory calibration and generic on-policy refresh?

---

## 1. Data policy

### Development set
The existing v0 evaluation set is now development data:
- retail: 58
- airline: 27
- pooled: 85

Use it for:
- 3-seed calibration variance;
- mechanism analysis;
- choosing between CLOQ-All and CLOQ-Novel.

Do **not** call these 85 tasks final untouched test data anymore.

### Final test
Before inspecting v1 results, freeze a fresh set from tau2 tasks never used for:
- calibration;
- v0 evaluation;
- debugging.

Target:
- >=40 retail;
- >=20 airline;
- otherwise all remaining eligible tasks.

If tau2 cannot provide a credible fresh set, final confirmation must use a second benchmark such as WorkArena/WebArena text mode.

---

## 2. Calibration task pool

Reuse the original frozen calibration task pool.

If the current manifest contains 40 tasks (20 retail + 20 airline), use:

N_state = 40

Otherwise set N_state equal to the exact number of calibration tasks and do not add tasks after seeing outcomes.

Every calibration arm contributes exactly **one independent state per calibration task**.

---

## 3. Matched calibration budget

Primary budget:

- 40 independent contexts;
- 1600 activation rows/context;
- exactly 64,000 GPTQ activation rows total.

For every selected context:

1. replay the exact deployment-format context;
2. apply the same 8192-token truncation rule;
3. collect valid non-padding token activations;
4. uniformly sample 1600 token positions without replacement using the calibration seed;
5. use those same token positions across all quantized layers.

If a context has fewer than 1600 valid positions:
- use all valid positions;
- deterministically fill the missing row budget from other contexts in that arm;
- never duplicate rows.

Report per arm:
- independent states;
- total activation rows;
- median input length;
- activation rows/state.

This replaces the v0 “64k raw input tokens” budget.

---

## 4. Calibration draws

Run exactly three draws:

- c1 = 20260729
- c2 = 20260730
- c3 = 20260731

Quantization seed stays fixed.

A draw controls:
- FP trajectory state selection;
- FP/Q task split for CLOQ;
- activation-row subsampling;
- novelty-selection tie breaking.

No draw may be dropped.

---

## 5. Main arms

### A. Static

For every calibration task use the initial decision state x0.

Exactly one state/task.

---

### B. FP-Traj

For every calibration task choose one BF16 trajectory state.

Balance normalized depth globally:
- 25% Q1;
- 25% Q2;
- 25% Q3;
- 25% Q4.

Keep success, failure, and partial trajectories.

Purpose:
test nominal deployment support.

---

### C. CLOQ-All

For each draw:

1. build the FP-Traj checkpoint Q0;
2. run Q0 closed-loop on all calibration tasks;
3. collect Q0 trajectories;
4. stratify tasks by domain and BF16 horizon quartile;
5. split tasks evenly into FP-half and Q-half.

Use the **same split** for CLOQ-All and CLOQ-Novel.

Calibration set:
- 20 FP states from FP-half tasks;
- 20 uniformly depth-sampled Q0 states from Q-half tasks.

Exactly one state/task.

Purpose:
generic on-policy refresh baseline.

---

### D. CLOQ-Novel

Use the same:
- calibration draw;
- FP/Q task split;
- FP-half states;
- activation-row budget

as CLOQ-All.

Only Q-state selection changes.

For every Q0 decision state x compute:

nu(x) = min_z [1 - cosine(phi(x), phi(z))]

where:
- phi is the frozen BF16 final-layer representation at the action boundary;
- z ranges over the draw-matched FP-Traj calibration support.

For each Q-half task:

1. if there are post-divergence Q0 states, choose the **highest-novelty post-divergence state**;
2. otherwise choose the highest-novelty Q0 state over the whole trajectory;
3. exactly one Q state/task.

Calibration set:
- 20 FP states;
- 20 task-diverse Q-novel states.

This is the proposed method: **closed-loop support refresh**.

---

## 6. Do not add these yet

Do not add:
- Fisher weighting;
- action-KL weighting;
- Q-only calibration;
- success-only trajectory filtering;
- extra bit widths;
- second model;
- second quantizer.

v1 tests one question only:

> Is *which on-policy state we add* more important than simply adding on-policy states?

---

## 7. Required checkpoints

3 draws × 4 arms:

- Static c1/c2/c3
- FP-Traj c1/c2/c3
- CLOQ-All c1/c2/c3
- CLOQ-Novel c1/c2/c3

**12 new checkpoints total.**

Reuse BF16 and RTN references after a small integrity replicate.

All checkpoints are quantized from the original BF16 checkpoint.

Never quantize an already quantized model.

---

## 8. Two-GPU execution schedule

### Stage 1 — FP-Traj / Q0

GPU 0:
- FP-Traj c1
- then FP-Traj c3

GPU 1:
- FP-Traj c2
- then first available Static job

Keep both GPUs occupied.

Also build:
- Static c1
- Static c2
- Static c3

whenever a GPU frees.

### Stage 2 — Q0 calibration rollouts

For each Q0 draw:
- split calibration tasks across GPU 0 and GPU 1;
- collect all Q0 trajectories;
- do not restart the user-simulator server inside a paired block.

### Stage 3 — novelty extraction

Replay FP/Q candidate states through frozen BF16.

Split calibration tasks 50/50 across GPUs.

Write immutable:
- novelty_manifest_c1.json
- novelty_manifest_c2.json
- novelty_manifest_c3.json

### Stage 4 — six refresh checkpoints

Queue continuously:
- CLOQ-All c1
- CLOQ-Novel c1
- CLOQ-All c2
- CLOQ-Novel c2
- CLOQ-All c3
- CLOQ-Novel c3

One single-GPU job per card.

### Stage 5 — development evaluation

Evaluate 12 checkpoints × 85 dev tasks.

Preferred:
- each GPU loads the same checkpoint and gets half the tasks.

If the harness cannot safely parallelize one checkpoint:
- GPU 0 evaluates one checkpoint;
- GPU 1 evaluates another checkpoint.

### Stage 6 — final untouched test

Only after dev analysis and method selection are frozen.

Evaluate:
- BF16
- Static
- FP-Traj
- selected CLOQ

on fresh unseen tasks.

---

## 9. Primary development table

Report every draw separately:

| arm | draw | retail SR | airline SR | pooled SR | long-task SR |
|---|---|---:|---:|---:|---:|

Primary contrasts:
1. FP-Traj - Static
2. CLOQ-All - FP-Traj
3. CLOQ-Novel - FP-Traj
4. CLOQ-Novel - CLOQ-All
5. CLOQ-Novel - Static

Use crossed bootstrap:
1. resample calibration draw;
2. within draw, resample tasks stratified by domain;
3. 10,000 replicates;
4. report mean and 95% CI.

Always report retail and airline separately as well.

---

## 10. Pre-specified long-horizon target

Freeze the v0 threshold:

H_BF16 > 11

as the **primary v1 long-horizon subgroup**.

Report:

| arm | short H<=11 | long H>11 | BF16 gap on long |
|---|---:|---:|---:|

Primary long-task contrasts:
- FP-Traj - Static
- CLOQ-All - FP-Traj
- CLOQ-Novel - FP-Traj
- CLOQ-Novel - Static

Secondary:
- BF16 horizon quartiles;
- continuous horizon/degradation correlation.

Do not move the threshold after seeing v1 results.

---

## 11. Behavioral stability

Keep as pre-specified secondary outcomes:

- premature termination;
- mean decisions;
- repeated tool calls;
- parser errors;
- tool errors;
- step-cap termination.

For each arm report deviation from BF16.

The v0 retail signature should be specifically checked:
Static caused more premature endings, more decisions, and more repeated calls; FP-Traj/CLOQ partially corrected them.

Behavior metrics remain secondary to task success.

---

## 12. Open-loop fidelity

Replay the exact stored BF16 dev contexts.

For every arm/draw compute:
- tool-name agreement;
- full normalized tool-call agreement;
- NLL/token of BF16 action;
- argument-field accuracy.

The paper claim is **not** that agreement predicts success.

The claim is:

> nominal-state fidelity can remain high while closed-loop task success degrades.

---

## 13. First divergence

For each paired BF16/quantized task:

t* = first normalized tool-call mismatch.

Report:
- divergence rate;
- median t*/H;
- success after early divergence;
- success after late divergence;
- success with no divergence.

After t*, contexts are not aligned; do not compare later actions step-by-step.

Primary question:

> Does CLOQ-Novel delay divergence or improve recovery after divergence?

---

## 14. Occupancy/support analysis

Use frozen BF16 representations.

For each visited state report support distance to:
- Static calibration support;
- FP-Traj support;
- CLOQ-All support;
- CLOQ-Novel support.

Key analyses:

### A. Divergence jump
pre-divergence vs post-divergence support distance.

### B. Coverage
Q-policy states to each calibration support.

### C. Success/failure
post-divergence distance in successful vs failed episodes.

### D. MMD
Keep MMD as a distribution-shift diagnostic only.

Do **not** claim lower global MMD implies higher success; v0 already falsified that monotonic interpretation.

---

## 15. CLOQ-Novel audit table

For every selected Q-novel state save:

- domain;
- task ID;
- BF16 horizon;
- Q0 horizon;
- divergence step;
- selected step;
- pre/post-divergence;
- novelty score;
- context length;
- truncation flag;
- repeated-tool region flag;
- near-failed-end flag;
- final Q0 task success.

Summarize:

| category | share of selected states |
|---|---:|
| post-divergence | |
| truncated | |
| near failed end | |
| repeated-tool region | |
| from failed Q0 episodes | |
| from successful Q0 episodes | |

This makes the method auditable.

---

## 16. Dev method-selection rule

Select CLOQ-Novel for the fresh test if:

1. mean **long-task** success across 3 draws is higher than CLOQ-All; and
2. pooled mean success is not worse than CLOQ-All by more than 2 absolute percentage points.

Tie:
- if long-task means differ by <1 pp, choose the simpler CLOQ-All.

Freeze this rule before running v1.

No third selector may be invented after seeing results.

---

## 17. Fresh-test protocol

After selecting the CLOQ variant, evaluate on fresh untouched tasks:

- BF16
- Static
- FP-Traj
- selected CLOQ

Preferred:
- all 3 calibration draws for every quantized method.

Primary final endpoint:
- success on tasks with BF16 horizon >11.

Secondary:
- pooled success;
- first divergence;
- behavioral stability;
- occupancy distance.

No parameter changes after fresh evaluation begins.

---

## 18. Integrity

Every run must assert:

- exact base checkpoint revision;
- exact tau2 revision;
- same system/domain policy;
- same tool schema;
- same user simulator/config;
- same generation settings;
- VLLM_BATCH_INVARIANT=1;
- no simulator restart inside paired block;
- exact calibration task IDs;
- exact dev/final task IDs;
- one state/task;
- exactly 64,000 activation rows/arm;
- same GPTQ settings;
- same quantization seed;
- no calibration/evaluation leakage.

Every run writes:

config.json
environment.json
task_manifest.json
calibration_manifest.json
row_manifest.json
quantization.json
trajectory.jsonl
openloop.summary.json
divergence.json
metrics.json
status.json

Only status=completed enters analysis.

---

## 19. Go / rethink criteria

### Strong GO
Continue to 7B/full paper if:
- CLOQ-Novel > Static on long tasks with crossed-draw 95% CI excluding 0; or
- CLOQ-Novel > FP-Traj on long tasks with positive sign in all 3 draws plus clear behavioral/coverage improvement.

### Moderate GO
Continue if:
- horizon amplification replicates;
- post-divergence support shift replicates;
- FP-Traj or CLOQ-Novel consistently improves a closed-loop metric;
- task-success CI remains wide because task count is small.

Then enlarge evaluation before changing method.

### Rethink
If:
- 3 draws show no reproducible Static vs trajectory difference;
- CLOQ-Novel does not improve support coverage over CLOQ-All;
- novelty-selected states do not relate to post-divergence behavior.

Do not jump to 7B solely to search for a positive result.

---

## 20. Immediate queue for 2×4080

### Quantization
12 checkpoints:
- 3 Static
- 3 FP-Traj
- 3 CLOQ-All
- 3 CLOQ-Novel

### Closed-loop dev evaluation
12 × 85 tasks

### Open-loop replay
all 12 checkpoints on stored BF16 contexts

### Occupancy extraction
- all calibration states
- all Q0 candidate states
- all dev trajectories

### Fresh test
after method selection only.

Keep both GPUs occupied continuously with independent single-GPU jobs.

---

## 21. Paper story v1 is testing

The target paper is **not**:

> trajectory calibration is always better.

It is:

### Phenomenon
Long-horizon agents expose quantization failures hidden by nominal/open-loop evaluation.

### Mechanism
The first action divergence pushes the quantized policy outside nominal calibration support.

### Diagnostic
Open-loop tool-call fidelity overstates closed-loop reliability.

### Method
Closed-loop support refresh adds the **quantization-induced novel states** missing from nominal calibration.

### Boundary
Not every on-policy state matters; novel/post-divergence support is the useful target.

If v1 supports this chain, the next stage is:
- 7B open agent model;
- second benchmark;
- second quantizer;
- no change to the core method.
