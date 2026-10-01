# Quantization benchmark coverage and execution contract

**Status: forward execution plan, written 2026-09-30 America/Toronto (2026-10-01 UTC) against repository snapshot `2c68559`.** This documentation update performs no cluster mutation, authorizes no new result claim, and reports no live cluster inspection. It specifies how to maximize valid breadth and depth before the 2026-10-05 evidence freeze, with submission planned for 2026-10-12. Exact cutoff times and time zones must be recorded in the execution manifest.

The objective is a systematic empirical study of quantization in closed-loop agents, supported by a reusable measurement methodology. Coverage must not depend on whether any one attractive finding survives. Fill balanced method, model, and benchmark coverage first; then add repeated blocks, calibration replicates, controlled interventions, and explanation. A new routing algorithm is not a prerequisite for this plan.

## 1. Sources, precedence, and what is already known

Read this document with [METHOD_FIDELITY.md](METHOD_FIDELITY.md), [FORK_PROTOCOL.md](FORK_PROTOCOL.md), [WAKV_PREREG.md](WAKV_PREREG.md), [RESOURCE_PLAN.md](RESOURCE_PLAN.md), and [the execution plan](../EXECUTION_PLAN_20260930.md). [The night status](../STATUS_20260930_night.md) and [the result index](../../analysis/RESULTS_INDEX.md) locate existing evidence. A result becomes reusable only after its actual run/configuration hashes and admission status are checked; a narrative status entry is not a completed-cell manifest.

| Item | Evidence available in the inspected snapshot | Interpretation for this plan |
|---|---|---|
| Weight-only and numerical controls | Existing RTN/GPTQ/AWQ experiments, open-loop probes, and q4 format/rounding/rotation experiments are described in the execution plan and research log | Inventory and reuse compatible runs; do not rerun everything or assume every requested matrix cell is complete |
| Same-state forks | The night status reports W4, KV8, ALFWorld, and BFCL results; the fork protocol records replay acceptance | Retain the existing four-arm data and complete-block provenance; additional coverage remains planned until admitted outputs exist |
| A8/SmoothQuant/QuaRot | METHOD_FIDELITY records q4 acceptance and a q8 QuaRot validation suite | Acceptance is configuration- and architecture-specific, not a blanket approval of every bitwidth, model, or tensor-parallel layout |
| Matched rotation controls | q4 KV16-with-Q/K-rotation acceptance is documented; corrected factorial controls are identified | The unrotated KV16 cells cannot replace the matched controls in a factorial contrast |
| q8 W-by-KV confirmation | WAKV_PREREG fixes four A16 cells, six blocks, estimator, and two-sided contrast | Preserve this target even if a different interaction appears larger later |
| Static precision restoration | The night status reports the restoration line as dominated at matched storage and paused | Reuse it as mechanism evidence; it is not an established deployment improvement |
| Resources | The user provides 42 usable A6000s; the older RESOURCE_PLAN records 38 held cards and six simulator replicas at its measurement time | 42 is the planning ceiling. Live allocation, health, and registry records determine schedulable capacity; neither old count is silently treated as current |

The older execution plan's list of missing work is partly superseded. It must not be used to relabel documented acceptance as pending, nor to relabel planned evaluations as completed. The broadening below does not reopen the rejected checkpoint-lottery headline or turn exploratory task concentration into confirmation.

## 2. Design principles

1. **Breadth before extra repetitions in already deep cells.** Once a configuration is accepted, give it the same first complete task block as its comparison group before spending further blocks on favored cells. Existing 20-block cells need not be expanded while an accepted method or family has no baseline comparison.
2. **Balanced increments, not a full Cartesian product by default.** Complete a small, interpretable panel across methods first, then expand its blocks. Model-family and external-benchmark panels need representative coverage, not every format crossed with every backbone.
3. **No outcome-based admission.** A supported cell remains in the coverage table if it fails most tasks, generates invalid tool calls, loops, or shows no effect. Drop or defer configurations only for a documented engineering, hardware, availability, or resource reason fixed independently of favorable outcomes.
4. **Separate precision axes from algorithm bundles.** A plain W/A/KV cube and a QuaRot cube answer different questions. A SmoothQuant or QuaRot package is not an interchangeable corner of a plain RTN factorial.
5. **Use matched controls.** Match task, prompt block, checkpoint, calibration draw, rotation, parser, context policy, and serving settings whenever the estimand requires them. Record departures instead of hiding them behind a short method label.
6. **Keep evaluation levels distinct.** Teacher-forced shifts, autonomous closed-loop results, controlled same-state interventions, and a deployed routing policy measure different objects. Passing one level does not establish another.
7. **Generalization requires new tasks.** More nonces on the same tasks do not create more independent tasks. New domains, new backbones, new quantizers, new calibration draws, and new prompt blocks are separate transfer axes.
8. **Account for actual work.** A suffix is not automatically half an episode. Simulator calls, long prefixes, build/compile time, incomplete attempts, and long-tail failures enter the runtime ledger.

## 3. Coverage levels and admission ledger

Use the following levels for every model x quantizer x benchmark configuration. They describe evidence, not paper placement.

| Level | Required evidence | Permitted use |
|---|---|---|
| C0: specified | Exact model revision, method configuration, task manifest, seed/block assignment, and intended control | Queue planning only |
| C1: accepted | Required numerical/serving/replay gates pass; small integration pilot completes | Valid implementation; no benchmark-level performance conclusion |
| C2: breadth | One complete, paired evaluation block over the frozen task manifest | Descriptive coverage and runtime estimation; visibly low replication |
| C3: replicated breadth | Three complete paired blocks as the descriptive floor, five preferred where feasible; same task pool and configuration | Descriptive estimates with appropriately wide uncertainty; not a replacement for a preregistered design |
| C4: depth | Balanced additional blocks, controlled forks, calibration replicates, or common-state experiments with their own manifests | The specified deeper estimand; no automatic extrapolation to other configurations |
| C5: confirmation | Locked hypotheses, cells, exclusions, analysis, and untouched confirmation data | Confirmatory claims within that frozen scope |

The three-block target is a scheduling floor for broad descriptive comparisons, not a power guarantee. Existing preregistrations retain their declared block counts. Add repetitions in balanced groups using measured cost and prespecified precision targets; do not stop when a p-value crosses a threshold.

Each coverage row needs: `cell_id`, model ID/revision, tokenizer/template hash, quantizer version, W/A/K/V specification, calibration ID/hash, transformed-weight hash, hook/effective-config hash, benchmark version, task-manifest hash, expected task count, blocks expected/admitted, gate evidence, run IDs, source code commit, status, exclusion/defer reason, and measured cost. Store run-level status separately from aggregate analysis status.

Use explicit statuses: `planned`, `building`, `gate_failed`, `unsupported`, `pilot_complete`, `running`, `partial`, `complete_unverified`, `admitted`, `quarantined`, `deferred_budget`. A missing file, failed build, unsupported kernel, and zero task success are four different facts.

## 4. Weight-only panel

### 4.1 Core grid on q4 and q8

The primary weight-only axis is **BF16, W4, and W3**. Start with BF16 plus the following intended grid, with A16/K16/V16 and unchanged unquantized components. The method implementation must support the requested bitwidth before the cell is admitted.

| Family | W4 | W3 | Control and reporting requirement |
|---|---|---|---|
| RTN | core | core stress | Same grouping, scale convention, clipping, and deterministic rounding rule across widths, except documented necessities |
| GPTQ | core | core stress | Calibration manifest, token budget, damping, group size, activation ordering, sequential order, excluded modules, and solver version frozen |
| AWQ | core | planned core where implemented | Scale-search/clipping configuration and calibration frozen; W3 extensions must not inherit the credibility of a validated W4 implementation automatically |

This is **7 intended cells per model including BF16**, not a claim that all seven are already supported or completed. The first q4/q8 block over the 85-task retail/airline pool is at most `2 x 7 x 85 = 1,190` episodes before deduplication against reusable runs. Three blocks are at most 3,570 episodes; the preferred five-block expansion is at most 5,950. Count supported/admitted cells, valid failures, and unsupported cells separately in the final table.

**W8-only is outside both the minimum panel and the expanded weight grid.** A small, prespecified W8-only reference may be added only for an explicit mechanism contrast that needs a low-error anchor; name that contrast, its limited model/task scope, and incremental cost before execution. Do not repeat W8 across all quantizers, models, or benchmarks merely to complete a bitwidth ladder. Existing valid W8 results remain reusable and reportable; this scope change does not delete artifacts or interrupt running jobs. SmoothQuant W8A8 is retained as an activation-method comparator, and A8/KV8 remain independent required axes.

For native optimized kernels, W3 availability can differ from the fake-quant builder. Record `numerically_supported_fake` and `native_supported` separately. A W3 AWQ-like extension that cannot be checked against a declared recipe is labeled as that extension, not simply as canonical AWQ.

### 4.2 Format, rounding, and transformation panel

| Configuration | Minimum breadth assignment | Matched comparison | Interpretation |
|---|---|---|---|
| NF4 weight quantization | q4 and q8, first complete block then balanced repeats | BF16 and a declared INT4 reference at recorded effective storage | NF4 inference format; not a QLoRA finetuning result; record block size, codebook, scale storage, and whether double quantization is used |
| MXFP4 weight quantization | q4 and q8 where reference arithmetic passes | BF16 and declared W4 reference | Record element encoding, shared-scale encoding, block size, rounding, saturation/subnormals, and exceptions; distinguish spec-compliant MXFP4 from an approximate emulator |
| Stochastic-rounding RTN W4 | q4/q8 with a frozen first weight-rounding seed | Deterministic RTN W4 at the same grouping/scales | Separate checkpoint randomness from prompt-block randomness; later use several fixed rounding seeds crossed with blocks |
| Rotation-only floating control | q4/q8 for every rotation family used | Plain BF16, same serving settings | Estimates finite-precision transformation effects; mathematical invariance does not imply bit-identical BF16 execution |
| Rotated RTN W4 and rotated GPTQ W4 | q4/q8 | Their rotation-only control and unrotated method | Report transformation package and weight recipe; do not attribute every difference to rotation alone if calibration differs |

Reuse the existing q4 format probes after provenance checks; q8 completion is a breadth target. Add W3 stochastic rounding or multiple rotation draws after each family has a valid first comparison. Random parameter perturbations may remain diagnostic controls; they are not quantizers and must not increase the advertised number of quantization methods.

### 4.3 Calibration sensitivity without reviving a rejected headline

After core breadth, cross at least two independent calibration draws with the same prompt blocks on GPTQ/AWQ W4; expand to the available d1-d4 collection when compatible. Report calibration source, token count, and draw rule. Keep method-level deployment comparisons and controlled calibration-source comparisons distinct: forcing a shared recipe can change a named algorithm's intended configuration.

The questions are the size and transferability of calibration-induced variation, not whether a previously rejected lottery claim can be recovered in a selected subset. Analyze existing draws transparently, label post-hoc relations exploratory, and confirm only a newly frozen hypothesis on fresh data. No telecom holdout trajectory, hidden goal, reward, or state may enter calibration or hyperparameter selection.

### 4.4 Bounded W2 stress panel

W2 is an optional stress diagnostic, **outside the coverage floor and the seven-cell weight grid**. It tests the low-precision boundary without creating another full method x model x benchmark matrix. Keep A16/K16/V16 and use the following three intended cells:

| Stress cell | Admission requirement | Paired reference |
|---|---|---|
| q4 RTN W2 | Verified two-bit arithmetic, grouping/scales, finite outputs, and faithful serving | q4 BF16 under the identical new stress policy |
| q8 RTN W2 | Same numerical/serving requirements, with q8-specific acceptance | q8 BF16 under the identical new stress policy |
| q8 GPTQ W2 | Faithful supported two-bit GPTQ, pinned calibration and solver settings, and its own acceptance | The same q8 BF16 reference block |

If faithful GPTQ W2 is unsupported or fails its implementation gate, q8 AWQ W2 may replace the third cell only for that documented support reason and after its own two-bit fidelity gate. Record both the attempted GPTQ status and the replacement decision. Poor but valid GPTQ W2 task performance is not grounds for switching to AWQ. A named method must retain valid calibration and declared algorithm semantics at two bits; label an approximation as a distinct experimental variant, not as faithful GPTQ/AWQ.

Start with **one shared paired block on a frozen, stratified subset of about 24 of the canonical 85 retail/airline tasks**. Freeze the exact task IDs, domain strata, selection hash/seed, block, quantizer settings, and stress stopping-policy hash before seeing W2 outcomes. Select by task identity and prespecified metadata, not BF16 success, W2 loop incidence, or a preliminary effect. Use the same subset and block for every supported W2 cell and its model-matched BF16 reference. With exactly 24 tasks and all three cells supported, the initial closed-loop panel contains 72 W2 episodes plus 48 distinct BF16 reference episodes, or **120 episodes before valid reuse**; the q8 BF16 block is shared by its two comparisons. Builds, gates, retries, and any later forks are additional work.

Report each supported comparison on its frozen subset, with task/block counts, stopping reasons, and implementation status. This is not an 85-task benchmark estimate. W4/W3 results may be comparison anchors only when task, block, serving configuration, and stopping policy match; otherwise show them separately or budget a new matched control. Do not silently reuse uncapped BF16 or lower-bit episodes as capped-policy controls.

Follow **[the execution plan, §8.4](../EXECUTION_PLAN_20260930.md#84-loop-early-stopping-and-stress-run-caps)** for prospective early-stop rules; that section owns thresholds and policy details. Freeze the new stress policy before outcomes and apply the same rule to BF16, each compared quantized policy, and all branch arms if forks are added. An algorithmic loop stop is a valid policy failure with an explicit stop reason, not an infrastructure exclusion. A server outage or unresolved execution defect remains separate missing/infrastructure evidence. This lane does not modify existing primary, registered, or already-running experiment policies.

Expand to additional blocks, the full canonical pool, or a small fork sample only if measured runtime, tail behavior, support, and remaining budget permit. Freeze the expansion scope before its outcomes; use whole balanced groups. Do not expand only cells with favorable success, omit cells because they collapse, or select a few apparently recoverable loops. Preserve completed adverse outcomes and record any resource-based deferral.

## 5. Activation and joint weight/activation coverage

| Panel | Intended cells | Required controls and gate |
|---|---|---|
| Descriptive activation-only | W16A8 and W16A4, KV16 | A16 hook identity; plain BF16; per-token scale causality; fused qkv/o/gate-up/down coverage |
| Plain joint precision | RTN W4A8 and RTN W4A4 | Corresponding W4-only and A-only cells; same activation quantizer and clipping throughout the comparison |
| SmoothQuant | Smoothed W8A8 | Plain W8A8 comparator and transformed floating control where feasible; alpha chosen without benchmark outcome feedback; smoothed W8A16 only as a limited control for an explicit activation-mechanism contrast |
| QuaRot | Rotated W16A16, W16A8, W16A4, W4A16, W4A4; KV settings specified separately | Identical rotation draw and required online transforms; verified named recipe with documented deviations |
| Local activation diagnostic | A4 only at qkv, o, gate-up, or down | All-pass and full-A4 controls; same basis, clip, grouping, and module inventory |

METHOD_FIDELITY's q4 acceptance is a useful starting point; it does not establish q8 SmoothQuant acceptance or acceptance for another family. Record activation granularity, scale dtype, dynamic/static behavior, clip, scale floor, zero-row handling, group tails, tensor-parallel semantics, and excluded nonlinear/high-precision operations.

A16 pass-through must reproduce its appropriate reference; transformed floating controls may differ slightly from plain BF16 and require their own deterministic reference. Test single request versus batch, prefix-cache hit, chunked versus unchunked prefill, configuration-specific compile caches, and prefix/future-token scale independence. Quantization must be inside the inference engine at the actual activation sites; exporting dequantized weights alone does not implement A quantization.

The current documented hook refuses MoE experts and online-Hadamard TP>1. Do not count those configurations as covered through dense-only hooks or per-rank scales. Extend and validate the implementation explicitly or mark the cell unsupported.

## 6. KV coverage and fidelity

### 6.1 Core KV panel

Hold weights and activations at their declared floating baseline for isolated KV tests.

| Configuration family | Required cells | Purpose |
|---|---|---|
| Plain KV QDQ | K8V8, K4V4 | Mild and strong KV-only perturbations |
| K/V separation | K8V16, K16V8, K4V16, K16V4 | Attribute effects to key versus value quantization under the same recipe |
| Rotated KV | K8V8 and K4V4 where supported | Quantizer-plus-rotation package, with corresponding rotated KV16 controls |
| Stress extension | K3V3; W3+K4V4; W4A4+K4V4 | Boundary behavior under prespecified budgets; not selected because success is particularly low |
| KIVI extension | K4V4 and K2V2 after a dedicated gate | Named asymmetric key/value algorithm, distinct from naive RTN KV or QuaRot KV |

Cover q4 and q8 first. Run K-only/V-only at both 8 and 4 bits before spending many extra blocks on just K8V8. An asymmetric result is useful even if it does not improve a headline.

### 6.2 Required distinctions

- Record whether QDQ is applied to the tensors written into the attention cache, the quantized values used by attention, or a different representation. Record the precision in which the actual cache is stored.
- Online cache arithmetic must use only information available at insertion/update time. A scale computed across future tokens is invalid for a causal online claim.
- Test chunk boundaries, cache growth, cache reuse, prefill and decode, and repeated history restoration. A prompt-only logit check is insufficient for a KV-cache claim.
- A single floating-point cache storing previously dequantized K/V can support a numerical QDQ experiment, but does not demonstrate compressed cache memory, bandwidth, or native kernel performance.
- K-only and V-only cells retain the same rotation and all other settings as their joint comparator. Turning rotation off in the K16V16 control changes a second factor.
- KIVI must match its declared key/value granularity, streaming grouping, residual floating region, flushing behavior, and decode update rule. Naive per-token KV QDQ must not be relabeled KIVI.
- No model-switch branch may reuse another precision server's policy KV cache. Re-prefill the full correct history in the chosen controller and charge the associated work.

## 7. Two separate W x A x KV factorial families

### 7.1 Matched QuaRot cube: finish existing work first

The current corrected cube uses W in {16,4}, A in {16,4}, and KV in {16,4}, **all in the same QuaRot basis**. Every high-precision KV corner keeps the online Q/K rotation enabled (`KV16r`); every lower-precision corner uses the declared QuaRot KV recipe. Rotation, clipping conventions, excluded modules, model revision, and calibration recipe are held fixed.

| Corner | W | A | KV | Required label |
|---|---:|---:|---:|---|
| 000 | 16 | 16 | 16 | rotated floating, KV16r |
| 100 | 4 | 16 | 16 | QuaRot GPTQ W4, KV16r |
| 010 | 16 | 4 | 16 | rotated A4, KV16r |
| 001 | 16 | 16 | 4 | rotated KV4 |
| 110 | 4 | 4 | 16 | rotated W4A4, KV16r |
| 101 | 4 | 16 | 4 | rotated W4KV4 |
| 011 | 16 | 4 | 4 | rotated A4KV4 |
| 111 | 4 | 4 | 4 | QuaRot W4A4KV4 |

Within each W level, all A/KV corners must use the identical weight-checkpoint hash. Do not rebuild/calibrate W4 separately to favor each corner. Confirm that the KV16 configuration actually executes Q/K rotation rather than early-returning before it. METHOD_FIDELITY documents the q4 `bits=16, rot=qk` behavior; every newly used architecture still needs coverage evidence.

Complete the corrected q4 eight-corner table. Preserve q8's preregistered A16 four-corner, six-block W-by-KV test unchanged; complete the remaining q8 A4 corners as a separately declared broader factorial evaluation. Plain BF16 and the old unrotated KV16 runs are additional transformation controls, not replacements for these eight corners.

### 7.2 Plain cube: planned breadth expansion

Separately specify W in {16, RTN4}, A in {16, dynamic INT8}, and KV in {16, plain K4V4}, with **rotation off in all eight corners**. Its corners are BF16, W4, A8, KV4, W4A8, W4KV4, A8KV4, and W4A8KV4. Freeze one RTN W4 weight checkpoint and one activation/KV recipe across the relevant corners.

This cube answers whether simple precision perturbations interact without the QuaRot transformation package. It does not share a factorial denominator with the A4 QuaRot cube. If only isolated axes finish, report isolated axes; do not infer a three-way interaction from missing corners. Deduplicate truly identical existing endpoints by effective configuration hash, not by a similar display name.

### 7.3 Factorial analysis contract

Use complete matched task x block observations for each declared contrast. Every admitted block for the existing primary endpoint and registered W-by-KV contrast contains the full frozen task pool; do not drop difficult unfinished tasks by complete-case filtering. Defer or quarantine unresolved whole blocks under the existing protocol, and label any partial-block sensitivity as a different estimand. Report main effects, all three two-way interactions, and the three-way interaction with uncertainty and a declared multiplicity family. Report coverage lost through incomplete corners. Retain the preregistered q8 contrast as its own confirmatory test; the other interactions remain exploratory unless separately locked before seeing their data. Neither a nonsignificant main effect nor a large interaction establishes that harm requires a combination of axes.

## 8. Model coverage

| Model tier | Minimum intended panel | Depth after breadth | Support requirements |
|---|---|---|---|
| q4: Qwen3-4B-Instruct-2507 | Full weight core; format/rounding panel; A/SQ/QuaRot; KV separation; both declared cubes | Existing W4 forks plus balanced axis/format forks and calibration/rounding repeats | Exact revision and current non-thinking/tool settings pinned |
| q8: Qwen3-8B | Same numerical axes and weight core, using admitted architecture-specific implementations | Replicate q4 patterns, complete the fixed WAKV test, and maintain telecom dev coverage | Do not infer two q8 servers fit one card from q4 packing acceptance |
| q14 | BF16; RTN W4/W3; GPTQ W4; AWQ W4 where accepted | W4 forks and one mild KV configuration; expand supported GPTQ/AWQ W3 and calibration after the minimum panel | Use the registered revision below; pilot full context and suffix memory before bulk work |
| q32 dense | BF16; RTN W4; GPTQ W4; AWQ W4 where accepted | Selected W4 forks, a supported W3 configuration, and one precision-axis extension | Tensor-parallel and memory gate on available NVLink pairs; no unsupported online Hadamard path |
| q30a3 or another MoE | BF16 and verified weight-only W4 recipes | Expert/router coverage diagnostics, supported W3, and a supported KV-only extension | Record total and active parameters separately; dense-only activation hooks are currently insufficient |
| Second architecture/model family | Prefer registered l8: BF16, RTN W4/W3, GPTQ W4, AWQ W4 where supported; registered m24 is the access/serving fallback | KV8/KV4 and two W4 fork cells; supported GPTQ/AWQ W3 and activation/rotation after their own gates | Select by access, tool-interface support, and resource feasibility, not by favorable quantization outcomes; m24 changes scale as well as family |

q4 and q8 alone establish neither broad scale robustness nor cross-family robustness. q14 is the first scale extension; schedule q32 and MoE as separate coverage targets when their gates and measured cost permit. They must not be collapsed into one claim about scale, because architecture changes along with parameter count. Do not substitute MoE active parameter count for total checkpoint storage.

The inspected [model registry](../../scripts/a6000/models.json) pins the following identities. Its GPU declaration describes the registered serving layout; it is not a measured guarantee for a BF16/quantized pair, all context lengths, all kernels, or all fork branches.

| Registry ID | Exact model ID | Revision | Registered GPUs | Parser and explicit template options |
|---|---|---|---:|---|
| q4 | `Qwen/Qwen3-4B-Instruct-2507` | `cdbee75f17c01a7cc42f958dc650907174af0554` | 1 | `hermes`; no extra template options |
| q8 | `Qwen/Qwen3-8B` | `b968826d9c46dd6066d109eabc6255188de91218` | 1 | `hermes`; `enable_thinking=false` |
| q14 | `Qwen/Qwen3-14B` | `40c069824f4251a91eefaf281ebe4c544efd3e18` | 1 | `hermes`; `enable_thinking=false` |
| q32 | `Qwen/Qwen3-32B` | `9216db5781bf21249d130ec9da846c4624c16137` | 2 | `hermes`; `enable_thinking=false` |
| q30a3 | `Qwen/Qwen3-30B-A3B-Instruct-2507` | `0d7cf23991f47feeb3a57ecb4c9cee8ea4a17bfe` | 2 | `hermes`; no extra template options |
| l8 | `meta-llama/Llama-3.1-8B-Instruct` | `0e9e39f249a16976918f6564b8830bc894c89659` | 1 | `llama3_json`; `tools_in_user_message=false` |
| m24 | `mistralai/Mistral-Small-3.2-24B-Instruct-2506` | `95a6d26c4bfb886c58daf9d3f7332c857cb27b43` | 2 | `mistral`; no extra template options; dedicated serving path required |

Before queue generation, verify tokenizer/template hashes, actual access, serving compatibility, and supported quantizer paths. The registry documents l8 checkpoint identity checking and a past smoke run, but neither proves current access nor accepts every numerical hook. Preserve `tools_in_user_message=false`: the recorded tau2 greeting/template mismatch otherwise changes message roles. If l8 cannot be served faithfully, use m24 for a declared engineering reason and retain l8's status in the coverage ledger. Do not silently replace a weak l8 outcome with m24. The simulator's q30a3 identity is not by itself an accepted q30a3 agent configuration.

A family smoke test checks interface correctness on a fixed, outcome-independent set: schema rendering, tool-call parsing, stop behavior, context accounting, deterministic serving, and a no-op. Poor BF16 task success alone is not an engineering failure and cannot be used to remove the family from results. A new family with a valid but weak baseline remains informative, with limited headroom stated.

## 9. Benchmark populations and denominators

| Population | Frozen denominator / manifest requirement | Minimum numerical coverage | Expansion and interpretation |
|---|---|---|---|
| tau2 retail + airline development | **58 retail + 27 airline = 85 tasks** in the current fork/WAKV design | q4/q8 core weight grid; A/KV isolated axes and corrected cube | Primary common population for broad paired comparison; domain-specific rows accompany pooled results |
| tau2 telecom development | **80 tasks**, disjoint from holdout | q4/q8 BF16, GPTQ W4, AWQ W4, KV8; extend supported W4/W3 methods and KV4 as capacity permits | Fill both model panels; q8-only telecom coverage is not a model-balanced pool |
| tau2 telecom confirmation | **34 untouched tasks** | Only cells and analyses locked in the confirmation manifest | No broad exploratory fishing on holdout; expanding scope requires a recorded pre-outcome amendment and a fixed analysis family |
| BFCL multi-turn | Pin benchmark release and explicit task IDs for Base, Missing Parameter, Missing Function, Long Context; record counts per category | q4/q8 BF16, RTN/GPTQ/AWQ W4, one supported W3 and one KV cell | Complete categories before enlarging repetitions; distinguish episode success, turn-level errors, and evaluator-specific outcomes |
| ALFWorld text | Pin release, split, task files, environment variant, and task IDs; report seen/unseen split counts | Same representative q4/q8 panel as BFCL | Balance task types; freeze seeds and action parser; forks require environment-state equivalence |
| WebShop | Pin code/data/search-index snapshot, task sessions, reset/evaluator semantics, and success/partial-score definitions | After adapter acceptance: BF16 and two predefined W4 methods on q4/q8 | Optional engineering track; if accepted early and budget permits, grow to the common external panel |

BFCL/ALFWorld results exist according to the night status; their exact release, split, and counts must be read from admitted manifests before writing an external-coverage total. Do not invent a denominator from a benchmark's advertised size. For WebShop, “import succeeded” is not adapter acceptance: reset and replay, search determinism, persistent state, evaluator behavior, and dependency/data availability all need a pilot.

Every result table must report **tasks, blocks, task x block episodes, decision states, and branch completions separately**. In particular, 165 tasks for q8 W4 means 85 retail/airline plus 80 telecom dev, not a larger version of the same 85-task experiment. Use the 85-task intersection for model/method comparisons and report telecom separately; any combined statistic declares domain weights in advance.

[The split manifest](../../manifests/fork/splits_v1.json) explicitly states that **57 calibration tasks and 22 historical BF16-unstable exclusions are in no evaluation split**. Preserve that provenance: the 85-task headline population is conditional on the historical filtering, and the 57 calibration tasks are not untouched evaluation data. A separately frozen sensitivity manifest may reintroduce the 22 excluded tasks after their exact IDs and original exclusion rule are verified; report both the existing 85-task estimate and the enlarged population without silently changing the original preregistered target. Do not derive the population from the older README or remove new BF16/Q failures.

Use [the block manifest](../../manifests/fork/dev_blocks_v1.json) and the split manifest together. Their current dev allowlists are retail/airline `q1-q5` and `f01-f17`, and telecom `q1` and `f01-f06`; declare any additional blocks before executing or admitting them. The 34-task holdout requires the explicit holdout split and the frozen `PREREG_FORK_CONFIRM.md` hash matching `holdout.prereg_sha256`. The inspected manifest's hash is still null, with freezing planned for October 3. This plan does not itself unlock or authorize exploratory holdout analysis.

### 9.1 Valid failures versus missing evidence

- Invalid tool names/arguments, parse failures produced by the model, max-step endings, exhausted error budgets, wrong DB state, and policy-visible context failures remain outcomes under the frozen harness.
- For new stress experiments using a prospectively frozen early-stop policy, detected algorithmic loops remain valid policy failures with their stop reason. Apply the identical rule to the paired references and branch arms; keep infrastructure interruption distinct and retain the original endpoint definition for existing experiments.
- A context overflow caused by a valid configured policy is reported as a task failure with that reason. A harness serialization bug, wrong template, missing file, or server outage is infrastructure, requiring correction/replay and an audit entry.
- A quantizer's accepted numerics causing widespread invalid output is a valid adverse result. NaNs, a failed checkpoint build, or a hook not executing its advertised operation is an implementation/support result, not an admitted task-success estimate.
- Incomplete blocks and failed no-op groups are not silently completed with successes, zeros, or another configuration. Preserve attempted runs, quarantine reasons, corrected reruns, and the exact analysis admission decision.
- Report results on protocol-admitted complete blocks with the missingness ledger; separately label any partial complete-case sensitivity as a different estimand. If time prevents completion, show conservative success-rate bounds for unresolved intended episodes where useful; do not report a partial subset as the full benchmark.

## 10. Depth layers across the broad matrix

### 10.1 Closed-loop, open-loop, and outcome measurements

Every admitted C2/C3 cell records terminal success under its actual evaluator, attempts, termination reason, agent/user/tool turns, tool errors, context use, generated tokens, and time/cost components. Retail/airline DB success is named as such; telecom uses its official task-basis criterion. Report declared secondary policy/communication checks separately instead of changing success after seeing results.

Teacher-forced token/logprob probes provide a shared-context numerical view. Use one frozen reference bank plus a Q-visited bank when needed, with source-policy provenance. They do not demonstrate autonomous behavior, causal recovery, or useful online routing. Relate numerical distortion, semantic action changes, and terminal outcomes without treating any proxy as a monotone quality measure.

### 10.2 Same-state four-arm coverage

Maintain the existing W4 q4/q8 GPTQ/AWQ deep panel. Add a balanced mechanism panel spanning a mild KV cell, strong KV cell, W3 cell, and accepted A/joint cell rather than adding only whichever produced a large observed gain. Start with all 85 tasks in one block, using the declared state-selection rule, and then increment whole blocks. External benchmarks and a second family get a smaller preregistered common panel before additional within-q4 depth.

Do not require four-arm forks for every breadth cell before publishing its closed-loop result. For a cell that cannot support faithful forks, retain its autonomous evaluation and mark causal evidence unavailable. For an eligible fork unit, record the full immutable history, environment/device state, step/error budgets, exact current actions, role-specific serving configuration, and the separate continuation servers. No-op, ordering, and cache-isolation requirements remain those of FORK_PROTOCOL.

Use the four outcomes to report directional benefit and harm, current-action effects under each continuation, continuation effects under each current action, interactions, and all 16 binary outcome patterns. These are prespecified analytic views of the full table, not reasons to drop a cell. A nonzero interaction is not the same as strict action-ranking reversal.

### 10.3 Common-state cross-quantizer panel

Task x block equality does not guarantee equal histories or equal pivot times. Construct an outcome-independent, task-balanced bank of exact histories, with a declared mixture of source Q policies. Query each quantizer from those same histories, verify the appropriate identical prompt rendering within a model, and execute alternative current actions under a common suffix controller. Add a second suffix controller on a fixed subset to test continuation dependence.

This panel supports state-level transfer claims. Ordinary cross-quantizer task/block correlations support task-susceptibility claims only. Across model families, token IDs/templates need not match; preserve environment/history content and define the cross-model intervention explicitly rather than requiring impossible cross-tokenizer identity.

### 10.4 Mechanism diagnostics and restoration reuse

Retain existing layer/module restoration, random byte-matched restoration, RTN-versus-GPTQ comparisons, residual-dose curves, and local activation ablations as controlled diagnostics. Report their actual effective storage and transformation/calibration choices. A residual interpolation parameter alpha is not a bitwidth. Restoring part of a GPTQ checkpoint may interact with its original compensation; RTN is a useful separate control, not proof that the same interpretation holds for GPTQ.

Do not put the dominated restoration family back on the deployment critical path. New restoration runs are justified by an unresolved mechanism comparison with its matched control and explicit incremental cost, not by trying more subsets until one wins. A deployment claim would require a competitive matched-cost baseline and an actual end-to-end evaluation.

Preserve the existing paused restoration batches (56 and 22 queued items) and their provenance at low priority. A broadening of the research plan is not a reason to kill them, delete their queue records, or interrupt running episodes; a later scheduler may resume them within an explicit mechanism budget.

## 11. Breadth-first scheduling with measured costs

### 11.1 Runtime pilot and scheduler inputs

Use live allocation and health records before planning a wave. One worker owns its assigned GPUs; a validated q4 worker may own a B/Q server pair on one card. This does not authorize two unrelated workers to share a card or bypass worker cleanup ownership. Use existing registry/lease and drain mechanisms for simulator changes; do not interrupt running episodes merely to repack the cluster.

Measure at least 8-12 prespecified tasks for each new runtime class, spanning short/long prompts and domains; include actual telecom suffixes and stress loops. Keep pilot outcomes out of cell-selection decisions. Record cold and warm startup, build/compile time, prompt/decode tokens, p50/p90/max episode and suffix time, simulator turns, queue delay, throughput under intended concurrency, peak GPU memory, CPU/RAM use, and failed attempts.

Classify jobs separately: weight build, transformed-weight build, engine gate, closed-loop run, divergence search, each suffix controller branch, external benchmark, and CPU analysis. Estimate remaining GPU-hours from those classes and simulator demand from actual simulator requests. The historical 1,500 episodes/hour rate and half-episode suffix approximation are not a forecast for the expanded matrix.

Budget each wave as `build + gate + eval + search + suffixes + expected infrastructure reruns`, with an explicit uncommitted reserve. Start with a **20% reserve of schedulable time to the freeze** for completion, verification, and outages; update from live tail behavior, not from favorable outcomes. Stress jobs use a capped subset of current agent capacity, not an additional allocation on top of the cluster total.

### 11.2 Scheduling order

| Wave | Queue objective | Advance condition |
|---|---|---|
| 0: reconcile and prepare | Inventory existing runs; pin missing manifests; build checkpoints; run acceptance gates for unvalidated/new families and adapters; pilot distinct runtime classes | Coverage/cost ledger can distinguish reusable results from genuine gaps |
| 1: balanced minimum coverage | Fill first paired blocks of the q4/q8 BF16/W4/W3 weight grid, isolated A/KV/format panels, SmoothQuant W8A8 comparison, corrected QuaRot cube, model extensions, and external representative panels | Each feasible comparison group has a complete block; unsupported/deferred entries have explicit reasons |
| 2: replicated breadth | Fill three-block targets in balanced increments; complete the fixed q8 factorial confirmation and full plain cube when admitted | Enough complete blocks for transparent descriptive tables; no substitution for larger confirmatory requirements |
| 3: depth and transfer | Balanced additional blocks, calibration/rounding repeats, four-arm axis coverage, common-state cross-quantizer panel, second-family and scale forks | Each depth task addresses a declared question and fits measured remaining budget |
| 4: locked confirmation and freeze | Execute untouched holdout under frozen analysis; finish admitted blocks; validate provenance, artifacts, and figures | Evidence map and denominator audit complete before freeze |

Waves may run concurrently on different resource classes: external environments and open-loop/build work can fill slots while simulator-backed jobs wait. Existing deep-panel work need not be discarded. New work should primarily close breadth gaps until all technically feasible families have a defensible minimum comparison.

Do not reserve a W8-only sweep in any wave. A narrowly justified W8 diagnostic enters the mechanism queue after its contrast is specified; it does not displace missing W4/W3 coverage or the retained A8, KV8, and SmoothQuant comparisons.

The bounded W2 panel may use the capped stress lane after its task manifest, method gates, and prospective stopping policy pass. Its initial one-block subset is not part of the minimum coverage completion criterion. Charge BF16 controls and long-tail attempts to its budget; use measured runtime rather than observed success to decide further expansion.

Run q14, a second model family, q32/MoE, and WebShop engineering pilots early enough to discover constraints; do not leave every extension until the last day. Admission to bulk execution is based on a passed gate and measured completion forecast. A long engineering failure should not monopolize all cards or prevent already accepted breadth cells from finishing.

### 11.3 Calendar and stop conditions

- **10-01:** complete coverage reconciliation; freeze first breadth manifests; run new-family/large-model/WebShop pilots alongside missing q4/q8 blocks; record actual model/server capacities.
- **10-02:** advance accepted panels toward three complete blocks; finish corrected factorial groups; begin balanced axis forks and blinded annotation. Record which extensions are accepted, repairable, unsupported, or deferred.
- **10-03:** lock confirmation protocol before reading any holdout outcomes; reserve its measured cost; continue broad panels and selected depth with the remaining budget. Preserve pre-existing preregistrations.
- **10-04:** prioritize completing already admitted blocks, common-state comparisons, external/family replication, and the untouched holdout. New bulk jobs need a tail-aware completion forecast that leaves verification time.
- **10-05:** freeze evidence and publication artifacts at the recorded cutoff. Release unfinished cells as partial/deferred, never as zero effect or successful coverage. Subsequent experiments are a separately versioned extension.

A gate failure blocks that configuration's bulk execution. A task-quality collapse does not. If a stress configuration's measured runtime is excessive, reduce future blocks or defer a whole prespecified comparison group; keep completed/attempted outcomes and report the resource reason. New stress experiments may use the prospectively frozen common early-stop policy specified in the execution plan, §8.4. Do not lower a running experiment's step budget midway and combine it with earlier runs. If an emergency cap is necessary, the capped policy is a new, separately labeled experiment.

## 12. Cost and deployment interpretation

Maintain two separate cost tables:

1. **Numerical/emulation experiment cost:** actual BF16/QDQ server GPU-hours, build/compile cost, resident server count, simulator cost, replay/search overhead, prompt/decode tokens, and retries. These numbers support reproducibility and feasibility.
2. **Deployable representation/kernel cost:** packed weight bytes including scales/zeros/codebooks/padding/unquantized tensors, actual cache bytes, native-kernel peak memory, prefill/decode latency, and throughput under matched workload. Report only what is measured on the relevant backend/hardware.

An exported QDQ checkpoint stored in BF16 is not a four-bit resident checkpoint. Nominal W4 and theoretical packed bytes may be recorded as representation properties but must not be substituted for measured memory or speed. MXFP4, NF4, KIVI, and activation bit labels do not imply native support on A6000. A true low-bit backend comparison is a separate validated track, not a required rewrite of every emulation experiment.

Any precision-routing evaluation charges the Q proposal even when discarded, BF16 queries, re-prefill, continuation calls, router execution, and persistent model residency. A matched BF16-call rate is not necessarily a matched token or latency budget. BF16 is a reference policy, not a success ceiling. Static-restoration bytes and fake-quant runtime do not establish a deployment Pareto improvement.

## 13. Reporting obligations

Produce a release coverage table with rows for every intended cell and columns for implementation status, supported backends, task count, admitted blocks, closed-loop result, open-loop probes, fork coverage, and cost. Publish null, adverse, unsupported, and unfinished entries with their respective meanings.

Every pooled claim names its weighting and common population. Report task-generalization uncertainty alongside fixed-task block uncertainty; shared nonce blocks must be resampled together across tasks and paired cells. Non-inferiority and equivalence use a declared margin and matching checkpoint population; failure to reject a difference is not equivalence. The statistical analysis owner controls multiplicity families and confirmatory versus exploratory labels.

Preserve original result files, immutable input manifests, excluded/quarantined runs, and reproducible analysis commands. A figure's caption must distinguish a method's canonical name from the implementation variant actually run. Method coverage, parameter-scale coverage, architecture coverage, and task-domain coverage are separate counts.

The final paper can emphasize whichever robust conclusions emerge, but the complete empirical coverage remains visible. A weak or absent interaction, failure of signed-effect transfer, ineffective restoration, or lack of equivalence is a valid outcome of this study. The experiment plan must remain useful under those outcomes.

## 14. Primary method references and naming boundaries

These references identify the intended algorithms/formats; they do not certify an untested CLOQ implementation.

- GPTQ: Frantar et al., [GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers](https://arxiv.org/abs/2210.17323); [official implementation](https://github.com/IST-DASLab/gptq).
- AWQ: Lin et al., [AWQ: Activation-aware Weight Quantization for On-Device LLM Compression and Acceleration](https://proceedings.mlsys.org/paper_files/paper/2024/hash/42a452cbafa9dd64e9ba4aa95cc1ef21-Abstract-Conference.html).
- NF4 origin: Dettmers et al., [QLoRA: Efficient Finetuning of Quantized LLMs](https://arxiv.org/abs/2305.14314). CLOQ's NF4 inference cell does not reproduce QLoRA training.
- MXFP4: Open Compute Project, [Microscaling Formats (MX) Specification v1.0](https://www.opencompute.org/documents/ocp-microscaling-formats-mx-v1-0-spec-final-pdf). Pin the implemented specification and conversion rules.
- SmoothQuant: Xiao et al., [SmoothQuant](https://proceedings.mlr.press/v202/xiao23c.html); [official implementation](https://github.com/mit-han-lab/smoothquant). CLOQ's documented dynamic activation variant and chosen alpha remain explicit.
- QuaRot: Ashkboos et al., [QuaRot: Outlier-Free 4-Bit Inference in Rotated LLMs](https://arxiv.org/abs/2404.00456); implementation deviations and controls are recorded in METHOD_FIDELITY.
- KIVI: Liu et al., [KIVI: A Tuning-Free Asymmetric 2bit Quantization for KV Cache](https://proceedings.mlr.press/v235/liu24bz.html); [official implementation](https://github.com/jy-yuan/KIVI). KIVI coverage is planned until its own streaming fidelity gate passes.
