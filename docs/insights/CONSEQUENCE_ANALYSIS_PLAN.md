# Consequence analysis plan: identification, replication, and deployment

Status: development analysis and implementation specification, 2026-09-30 America/Toronto (2026-10-01 UTC).
Source snapshot: `2c68559` on `master`. Read together with `FORK_PROTOCOL.md`,
`METHOD_FIDELITY.md`, `WAKV_PREREG.md`, `../STATUS_20260930_night.md`, and
`../RESEARCH_LOG.md` (particularly W63–W67).

This document broadens the analysis without betting the paper on a particular
mechanism. It is not a retrospective preregistration of results already inspected.
It does not change the original primary endpoint, authorize opening the telecom
holdout, or establish any new statistical theorem. The implementation tasks below
are specifications, not statements that their outputs already exist.

## 1. Commitments and claim boundaries

1. **Keep `G_all` primary.** The existing primary is the full-pool effect of
   replacing Q's first semantically divergent action with B's action, followed by
   Q continuation. Preserve its target cells, denominator, sign, and inference
   rule from `FORK_PROTOCOL.md` §12. Do not promote a more favorable pattern,
   interaction, or routing result into its place.
2. **Protect all 34 telecom holdout tasks.** Development tools must reject their
   IDs before loading trajectories, outcomes, annotations, embeddings, or caches.
   A separate frozen confirmation manifest is required before any permitted
   confirmation access. Newly proposed tests are secondary only after their
   definitions, families, and analysis code have been frozen before unseen data.
3. **Treat the W67 patterns as hypotheses.** Concentration, directional stability,
   shared susceptibility, action-ranking reversals, and label transfer are useful
   candidates. The current analysis does not establish all of them. Do not infer
   a mechanism from a significant interaction or an attractive example.
4. **Distinguish targets.** A fixed task suite under a stated prompt-perturbation
   distribution, a population of unseen tasks, a population of calibration draws,
   and a different simulator are different targets. Extra nonces do not create
   extra independent tasks or checkpoints.
5. **Do not alter historical margins after seeing results.** The historical
   success NI margin is `epsilon = 0.03`; the existing gain threshold is
   `g_min = 0.03`. These are percentage-point differences in success probability,
   not margins for interactions, ranking reversals, harm rates, or prediction
   accuracy. Such additional margins require their own prospective justification.
6. **Keep multiple useful outcomes possible.** A well-supported measurement result,
   a validated mechanism result, and a successful deployable selector are different
   contribution levels. Failure of the latter two does not invalidate the first.
   Conversely, engineering correctness does not establish predictive usefulness.
7. **Preserve breadth without significance-driven scheduling.** Follow the main
   execution plan's six workstreams and their frozen resource priorities. Ranking
   reversal is one secondary diagnostic, not a gate for the project. Do not move
   compute toward a cell because an interim p-value is favorable or stop a valid
   workstream because its effect is null. Changes justified by engineering
   failures, coverage, or fixed resource limits require a logged reason and must
   preserve the planned result inventory.

## 2. Estimands and signs: one authoritative dictionary

At an immutable, fully restored state `h`, the first letter denotes the forced
current action and the second denotes the suffix controller. `B` is the matching
BF16 configuration and `Q` the stated quantized configuration. Let `Y_XY` be the
terminal success indicator under the benchmark's explicitly named evaluator.
Retail/airline DB success and telecom official task-basis success must retain
their separate names. Do not silently substitute one reward field for another.

| Symbol | Definition | Interpretation |
|---|---|---|
| `Y_BB` | B action, B suffix | BF16 from this saved state onward |
| `Y_BQ` | B action, Q suffix | Replace the current action only |
| `Y_QB` | Q action, B suffix | Keep the current action, upgrade its continuation |
| `Y_QQ` | Q action, Q suffix | Reference Q rollout from the same state |
| `L_XY` | `1 - Y_XY` | Failure loss used by the existing A/C/I convention |
| `A` | `L_QB-L_BB = Y_BB-Y_QB` | Cost of Q's current action under B continuation |
| `C` | `L_BQ-L_BB = Y_BB-Y_BQ` | Cost of Q continuation after B's action |
| `I` | `L_QQ-L_QB-L_BQ+L_BB` | Factorial interaction on failure loss |
| `G` | `Y_BQ-Y_QQ = A+I` | Current-action replacement benefit under Q continuation |
| `H` | `Y_QB-Y_QQ = C+I` | Suffix upgrade benefit after Q's current action |
| `F` | `Y_BB-Y_QQ = A+C+I` | Full upgrade benefit from the fork onward |
| `r` | `P(Y_BQ=1, Y_QQ=0)` | Rescue by current-action replacement |
| `d` | `P(Y_BQ=0, Y_QQ=1)` | Damage by current-action replacement |
| `M` | `r+d = E[abs(Y_BQ-Y_QQ)]` | Gross outcome change for this action intervention |

For unit gains as defined above, `E[G] = r-d`,
`I = Y_BQ+Y_QB-Y_BB-Y_QQ`, and `F = G+H-I`. Summary tables conventionally
label `E[G]` as `G`; only at that aggregate level is `G = r-d` literal. Unit-level
rescue/damage fields are binary indicators, whose weighted means are `r` and `d`.
Positive `G`, `H`, or `F` denotes a success improvement. Positive `A` or `C`
denotes a loss from replacing the relevant BF16 component with Q. Do not mix this
loss interaction with the opposite-sign interaction convention on success.

The linear A/C/I/G/H/F identities hold for unit outcomes and their weighted
expectations; r/d/M are aggregate probabilities/expectations. In a
stochastic continuation design, use expected returns for the causal contrasts.
The joint rescue/damage probabilities additionally depend on how branch randomness
is coupled. Report that coupling; do not present independently sampled binary
branches as observed individual treatment effects.

### 2.1 Denominators and non-divergent units

Maintain distinct estimand IDs:

- `primary_pivot_G_all`: the existing first-semantic-divergence policy over every
  admitted task/block. If there is no eligible divergence, this policy does
  nothing and its gain is zero.
- `pivot_G_conditional`: the same contrast conditional on an eligible divergence.
- `pivot_four_branch_conditional`: the observed four-branch outcomes at saved
  divergence states; the natural denominator for the 16-pattern analysis.
- `ordinary_state_*`: effects at the separately sampled ordinary Q-state bank.
- `deployed_policy_*`: outcomes of an actual complete routed episode.

**No divergence is not four observed equal outcomes.** A no-divergence unit has
no observed `Y_BB/Y_BQ/Y_QB` at an unspecified intervention time. Keep those raw
fields null. Record a zero primary policy gain with `effect_source=no_intervention`.
For the same primary policy, its unit rescue, damage, and gross-change indicators
are also zero, so their aggregate denominators remain identical to `G_all`.
Keep the raw four-branch pattern and raw `A/C/I` null for such units. Never let
null-filtering silently turn full-pool `r/d/M` into divergence-conditional rates.
For any full-pool `H` or `F`, first specify a policy that also does nothing when
there is no pivot; its zero is policy bookkeeping, not evidence that changing the
controller would have no effect. Otherwise report `H/F` on observed eligible
states only. Infrastructure failure, pending work, and replay failure are never
no-divergence units and never zero effects.

For binary deterministic forks, report `r`, `d`, `M`, and `G` together on the same
denominator, as well as the divergence-conditional versions. Low `G` alone does
not mean low consequence. A confidence interval covering zero is neither an
equivalence result nor evidence that gains and harms are random noise.

## 3. The complete 16-pattern table

Use the immutable bit order **`BB, BQ, QB, QQ`**. Generate the table from equations,
then assert it in the analysis so that plots cannot silently swap branch roles.
The values below are unit-level success differences, before multiplying by 100.

| Pattern | G | H | F | A | Strict action-ranking reversal? |
|---|---:|---:|---:|---:|---|
| 0000 | 0 | 0 | 0 | 0 | no |
| 0001 | -1 | -1 | -1 | 0 | no |
| 0010 | 0 | 1 | 0 | -1 | no |
| 0011 | -1 | 0 | -1 | -1 | no |
| 0100 | 1 | 0 | 0 | 0 | no |
| 0101 | 0 | -1 | -1 | 0 | no |
| 0110 | 1 | 1 | 0 | -1 | yes |
| 0111 | 0 | 0 | -1 | -1 | no |
| 1000 | 0 | 0 | 1 | 1 | no |
| 1001 | -1 | -1 | 0 | 1 | yes |
| 1010 | 0 | 1 | 1 | 0 | no |
| 1011 | -1 | 0 | 0 | 0 | no |
| 1100 | 1 | 0 | 1 | 1 | no |
| 1101 | 0 | -1 | 0 | 1 | no |
| 1110 | 1 | 1 | 1 | 0 | no |
| 1111 | 0 | 0 | 0 | 0 | no |

Deliver counts and fractions of **all 16 patterns**, by model, quantizer, domain,
draw, and declared state-bank population. Include zero-count patterns. Do not
select only interesting patterns for the main denominator. Individual 16-way
significance tests are not required; initial pattern tables are descriptive.

Action ranking under B continuation is `A = E[Y_BB-Y_QB | h]`; under Q continuation
it is `G = E[Y_BQ-Y_QQ | h]`. A strict reversal requires `A*G < 0`, with neither
contrast zero. `I != 0`, action disagreement, and a tie becoming a strict preference
are weaker and different findings. In deterministic protocol A, patterns `0110`
and `1001` establish a reversal at that particular admitted state and fixed
simulator configuration. They do not establish persistence under new nonces or
user behavior.

For stochastic or robustness runs, estimate the two expected action advantages
from independently repeated continuations at the **same saved state**. Declare a
robust reversal only under a prospectively specified joint uncertainty rule that
supports opposite signs, with multiplicity handled across searched states/families.
One noisy realization is insufficient. Any practical magnitude margin must be
chosen before those repeats are inspected; do not reuse the success NI margin by
analogy. If precision is inadequate, report the two intervals and label reversal
status unresolved. Interactions and reversals are not automatically literal error
recovery: that requires a content-defined recovery endpoint and evidence.

## 4. Unit registry, equal pools, and crossed inference

### 4.1 Freeze the observational unit before computing summaries

The registry key is `(suite, domain, task_id, model_id, quantizer_config,
calibration_draw_id, prompt_block_id, state_bank_id, state_id)` plus continuation
repeat IDs when used. A queue job, GPU, simulator replica, and identical
deterministic rerun are not new statistical replicates.

For each snapshot emit a coverage tensor before outcome summaries: expected and
observed task IDs by domain/cell/draw/block; divergence counts; completed branches;
no-divergence counts; missing and quarantined reasons; and whether the block is
complete under the frozen population. Apply the split guard first. Preserve the
historical admission rule and list any excluded BF16-abnormal tasks as defining
the target population; do not newly exclude difficult or unfavorable tasks.

Keep the 22 previously excluded BF16-unstable evaluation tasks in a separately
declared sensitivity tier if that tier is run. Freeze their IDs, repeats, and
analysis before collecting the additional outcomes; report why they were excluded
and what changes when they are included. They must not silently enter the
canonical denominator. The original 57 calibration tasks remain calibration
data and must never be repurposed as test tasks in any tier.

The current `85` and `165` pools are not interchangeable. The W67 q8 W4 output
combined 85 retail/airline tasks with many nonce blocks and 80 telecom development
tasks with only two blocks. Raw per-task flip counts, the number of never-flipping
tasks, and top-20%-of-tasks capture therefore mix exposure with susceptibility.
Twenty independent trials were not observed for every one of 165 tasks.

Required outputs:

1. A balanced, common 85-task retail/airline comparison on the shared admitted
   blocks for each declared cell comparison.
2. Telecom-development results separately, with their actual block counts.
3. A pooled result only with frozen domain/task weights, clearly defining whether
   the target is an equal-task or equal-domain average. Average domain means with
   those weights within each shared complete block; do not average blocks whose
   task composition changes without explicitly changing the estimand.
4. Pairwise comparisons on an explicit common task/block/draw intersection.
   Publish the intersection and excluded coverage. If balanced coverage cannot
   be completed, report separate strata rather than silently filling cells.

### 4.2 Primary and sensitivity uncertainty

For the fixed task suite, compute one paired weighted contrast per complete
shared nonce block. The existing primary interval resamples whole blocks when
there are at least 10 complete blocks; otherwise it uses a t interval over block
means, as amended in `FORK_PROTOCOL.md`. Preserve that rule for the existing
primary. With few blocks report its approximation and instability honestly; do
not manufacture precision by treating tasks within a block as independent runs.

For crossed task/block sensitivity, draw task multiplicities once within each
declared domain and draw global block multiplicities once; apply their product to
every matching branch and cell. Never resample blocks independently inside each
task. Shared BF16 outcomes and shared nonce perturbations remain shared across
quantizers and models. Resampling within a model followed by an independence
assumption across models is not a valid pooled interval.

Treat calibration draws as another factor only when multiple independently built
draws were actually sampled. Freeze whether the target is fixed d1 or a declared
draw distribution. If draws are shared across cells, use the same draw weights;
if draws are nested in model/method, retain that nesting. Use global nonce weights
and shared task weights across draws when those factors are crossed. With only a
few draws, report draw-specific results and sensitivity rather than claiming
precise draw-population inference. A d1 fork is not automatically explanatory of
d2–d4 success changes.

Continuation seeds, if added, form repeats within a restored state; they do not
replace task, block, or checkpoint units. Record whether common random numbers
were used across branches. Pure deterministic reruns are engineering checks with
zero additional sampling information.

For all intervals record the target, weights, cluster counts, method, random seed,
resampling count, and completeness rule. Crossed bootstrap results are sensitivity
to an assumed task-sampling target, not proof that 34 curated telecom tasks
represent every future task. A zero-event/zero-variance bootstrap distribution is
not evidence of perfect safety or a zero-width population effect; flag it and
report an appropriate prespecified bound or an unresolved inference statement.

### 4.3 Nonces and simulator randomness

Verify actual manifests and trajectories before naming a replication dimension.
Changing `CLOQ_PROMPT_NONCE` does not establish a changed user-simulator seed. The
frozen greedy simulator and seed can remain identical across blocks. Report
prompt perturbations, user seeds, sampling seeds, calibration draws, and serving
configurations as separate fields. If nonce strings were chosen deterministically,
describe the resulting finite perturbation panel and the assumed broader nonce
distribution; do not call deterministic repeats independent stochastic draws.

## 5. W67 audit and corrected development questions

Keep the original output and its script hash for provenance. Add an audit table
that distinguishes the reported statistic, its actual denominator/null, the
interpretation it supports, and the replacement analysis. Do not merely rename
the old p-values.

| W67 question | Current limitation | Required replacement |
|---|---|---|
| Do effects concentrate in tasks? | Pooled iid binomial null ignores block shocks, domain heterogeneity, and unequal exposure; raw flip-count rankings reward more repeats | Equal/common exposure; rates and coverage; independent-block directional/concentration replication; explicit crossed uncertainty |
| Are task signs persistent? | Rescue is possible only when QQ fails, damage only when QQ succeeds; redistributing signs at a pooled ratio can assign impossible labels | Report baseline opportunities, replicate signs on separate blocks, and compare with a QQ-outcome-risk baseline |
| Do rescues occur in net-rescue tasks? | Task sign and share are defined/scored on the same outcomes | Define sign/ranking on split A, evaluate all effects in split B, including reversals and ties |
| Do quantizers affect the same states? | `(task, nonce)` agreement does not imply identical history, pivot index, action, or environment state | First call it task/block co-susceptibility; use an identical immutable state bank for same-state claims |
| Is overlap above chance? | Permuting task labels independently within each block destroys persistent task propensity and overstates effective sample size | State the null; for task-identity association permute whole task vectors coherently across blocks, within domain; for nonce alignment preserve task propensity and permute whole nonce columns when exchangeable |
| Does early pivot timing cause consequence? | Position and realized remaining length correlate with difficulty, looping, and failure | Descriptive association first; use only fork-time variables for confirmation, or a separate controlled intervention |

Neither vector permutation is automatically valid. Require exchangeability within
its stated stratum; heterogeneous known task classes or nonexchangeable nonce
families require stratification or a model-based/descriptive alternative. Apply
the same permutation to all dependent observations involved in that test.
Report Monte Carlo p-values as `(1 + number at least as extreme)/(B + 1)`, never
zero. Do not use invalid exchangeability assumptions merely to obtain a p-value.

### 5.1 Directional replication and heterogeneity

Freeze a hash-based A/B nonce split on the common balanced development pool before
running the revised summaries. Because these development outcomes were already
inspected, this is internal replication, not fresh confirmation.

- On A, estimate each task's signed `G`, gross `M`, baseline QQ failure rate,
  rescue rate conditional on QQ failure, and damage rate conditional on QQ success.
  Keep zero-opportunity conditional rates missing, not zero. Freeze any ranking,
  selected fraction, sign rule, and shrinkage using A only.
- On B, report the mean signed `G` within the A-defined positive/negative/neutral
  groups; signed agreement including ties; capture of M by the A-defined ranking;
  and the full uncertainty of the validation statistic. Include every selected
  task even if it has no B events. No reranking or removal based on B.
- Compare with ranking based on QQ outcome propensity and simple observable task
  descriptors. Separate baseline opportunity from additional quantization-specific
  predictability. Do not condition the main result on “at least two flips” selected
  using both splits.
- A preregistered split-symmetrized statistic may use A-to-B and B-to-A together,
  but do not choose whichever direction looks stronger.

An optional exploratory effect-heterogeneity estimator avoids treating observed
task variance as entirely signal. On a fixed task panel with weights `w_i` summing
to one, let `g_ib` be the paired gain for task i and independent nonce block b,
and `bar_g_b = sum_i w_i g_ib`. Estimate stable task variation by

`mean_{b<c}[sum_i w_i g_ib*g_ic - bar_g_b*bar_g_c]`.

Under independent, identically targeted blocks this estimates weighted variation
of task-level expected gains. The analogous statistic can be used for `M`.
Retain negative estimates; do not clip before inference. Shared block shocks,
nonidentical perturbation distributions, and a near-degenerate null complicate
inference, so this is a development diagnostic, not a new theorem or an automatic
bootstrap significance test. Use directional replication as the easily auditable
companion result.

### 5.2 Task-held-out prediction is a different test

All states, nonces, draws, and branch outcomes of a task belong to the same outer
fold. Fit feature transforms, label aggregation, hyperparameters, and thresholds
inside training folds. Compare signed gain prediction with gross-flip prediction,
QQ failure prediction, and a constant/no-op model using the same folds and
available features. Assess selected-action value/net gain and calibration on the
held-out branch outcomes, not only AUROC or accuracy. This evaluates a decision
at the declared logged-state distribution; it is not a deployed-episode policy
value. Strong within-task nonce replication does not imply transfer
to new task IDs. A task-ID fragility lookup cannot predict untouched telecom
tasks; transfer requires features available there and an independently frozen
evaluation.

## 6. Immutable ordinary Q-state bank and matched-state transfer

The legacy first-divergence bank remains the population for the existing primary.
Create a **separate** bank for broader consequence learning and mechanism checks.
Do not select this bank on observed branch outcomes, high M, positive G, or a
favorable quantizer.

1. Freeze eligible task IDs, cells/draws, nonce blocks, decision eligibility, and
   sampling probabilities. Sample ordinary pre-decision states from completed Q
   trajectories using a recorded hash/random rule or prespecified observable
   strata. Include no-disagreement and low-risk states. Start with at most one
   sampled state per task/cell/block unless the additional within-trajectory
   dependence and weights are explicitly represented.
2. Save the complete history, environment/user-device reconstruction data, prompt
   and task hashes, used and remaining budgets, origin configuration, and selection
   metadata before computing candidate actions or branch outcomes. Freeze the
   manifest and do not replace failed or uninteresting sampled states silently.
3. State the target weighting. Uniform over tasks then uniform over eligible
   decisions differs from uniform over every logged decision, which overweights
   long/looping episodes. Record sampling probabilities and use the corresponding
   weighting when estimating a different target.
4. Query all compared configurations from the **same stored history and environment
   state**. Verify prompt IDs within tokenizer-compatible same-model comparisons.
   Across model sizes record the common text/history hash and each tokenizer's
   own prompt IDs; cross-model token-ID equality is not required or expected.
5. Freeze the shared candidate action definitions and the suffix controller for
   each transfer question. “B versus Q1's action under Q1” and “B versus Q2's action
   under Q2” change both action and continuation. To isolate controller dependence,
   hold candidate actions fixed and vary only the suffix. To study configuration
   transfer, explicitly report the distinct intervention being predicted.
6. Validate replay/no-op gates for every new configuration and simulator family.
   Run the full action through the normal tool parser/environment. A token-logit
   change is not a behavioral intervention outcome.

Deliver two distinct cross-quantizer tables: (a) legacy task/block co-susceptibility,
(b) common-state outcome/advantage agreement. Report the number of unique tasks,
states, nonces, and draws in each. Evaluate label transfer by training on source
cells and evaluating on prespecified target cells with outer task separation;
report within-state transfer separately from generalization to new tasks.

## 7. Content characterization and blinded review

The human study describes what the actions and trajectories do. BF16 is a
reference, not a correctness oracle. A disagreement or a tool error alone is not
a policy/authorization violation. An execution-error retry is not necessarily
recovery of the original defect or restoration of the desired state.

Prepare approximately 80 development states with approximately 20 independently
double-reviewed states, following the already planned workload. Freeze the sample
manifest and rubric before revealing labels to reviewers. A sample deliberately
stratified by rescue/damage or fragile/robust groups is appropriate for coverage,
but its raw label frequencies are not population prevalences; provide inclusion
weights or clearly label them as sample composition.

Use two blinded passes:

- **Pass 1, current decision:** task constraints, full available prefix, and the two
  anonymized actions in randomized order. Hide model/precision names, quantizer,
  G/H/F values, outcome pattern, task fragility ranking, and future suffixes. Label
  groundedness, tool validity, argument validity, permission/consent evidence,
  goal relevance, ambiguity, and whether both actions are defensible. Require
  exact evidence locations and allow unknown/not applicable.
- **Pass 2, process consequences:** anonymized suffixes with branch role and
  precision concealed; annotate retries, correction of the identified defect,
  irreversible changes, user clarification, loops, budget exhaustion, and final
  requirement satisfaction. Reviewers may see what the suffix actually contains
  but should not be shown the automated success label or selected hypothesis.

Run automatic event extraction and LLM-assisted labels using the same rubric and
evidence spans. Preserve their provenance separately from human labels. Double
reviewers work independently before adjudication; report agreement by field,
uncertainty, disagreement counts, and adjudication changes, not just one global
agreement score. Choose illustrative cases by a frozen hash or representative
sampling rule within declared patterns; include counterexamples and unresolved
cases. Do not cherry-pick cases that merely make the expected mechanism plausible.

## 8. Process costs and controlled consequence tests

Record per branch, and as paired contrasts: current-action and suffix tool calls,
tool failures, retries, user turns, agent generations, prompt/completion tokens,
steps/errors consumed, premature termination, unfulfilled requirements, and
irreversible writes where the environment exposes them. Keep event definitions
separate from value judgments. Normalize only with a stated denominator; do not
divide by observed successful episodes and call the result overall efficiency.

Report full-episode and suffix-only latency separately, with GPU time, simulator
time, device configuration, concurrency, switch/re-prefill cost, and the cost of
shadow BF16 searches. A cheaper or faster failed episode is not automatically a
better trade-off. Report joint success/cost and all termination categories.

Observational moderation by remaining budget, number of past errors, or task
length does not establish a budget/error mechanism. A controlled development
follow-up may randomize a **declared resource intervention** at a fixed state:

- retain actual used counters, vary the allowed remaining step/error budget using
  a prespecified schedule, and apply each level to all four branches;
- or inject a prespecified recoverable tool failure through a validated simulator
  interface, with a matched sham/no-error response and unchanged unrelated state.

Do not fabricate an inconsistent conversation/DB state, reset used counters, or
select an error type after observing its effect. Record both the original and
modified state signatures and the exact intervention. A budget intervention
changes the target environment; label it as such. Error type, budget levels,
controller contrasts, and control arms must be frozen before outcomes. Evaluate
literal recovery through predefined content/requirement endpoints as well as
success. Report null and opposite effects. These tests are optional mechanism
branches, not a reason to reinterpret the historical primary.

## 9. Internal representations and activation interventions

Linear probes, hidden-state distances, and layerwise prediction of outcome labels
are exploratory associations. Task, history length, action type, and label leakage
can make them predictive. Use task-held-out splits, fit preprocessing inside folds,
compare simple observable baselines, and report where candidate layers/tokens
were selected. A successful probe does not show a representation causes failure.

For a targeted activation-patching experiment:

1. Use an immutable fixed prefix, identical model/tokenizer where representation
   alignment is needed, a declared token/layer/site, and frozen candidate patches.
   Do not compare hidden states from histories that have already diverged and call
   their difference a same-state quantization mechanism.
2. Include no-op/sham patches; matched-norm random perturbations at matched sites;
   random-site controls; and a prespecified dose series. Match relevant layer/token
   coverage and norm, record patch scale and numerical precision, and retain
   clipping/normalization choices. Multiple random controls need declared seeds.
3. Measure logits and full semantic actions first, including unchanged, B-like,
   Q-like, and neither. If outcome relevance is claimed, execute the patched
   action with the explicitly fixed suffix controller and score real branches.
4. Verify re-prefill, cache isolation, hooks, and unchanged non-target computation.
   Patching must not inadvertently switch weights or serving configuration.
5. Interpret a successful patch as an effect of that implemented internal
   intervention. Off-manifold patches or transferred activations do not by
   themselves identify a unique natural causal pathway or a mediation percentage.

Mechanism experiments may explain cases without yielding a competitive deployment
method. Static bit restoration remains a diagnostic branch unless it beats valid
matched-storage/compute controls; the existing decision to stop presenting it as
the repair method is retained.

## 10. Simulator robustness, selection, and failure accounting

Replay validity remains a gate. Every new checkpoint, hook, simulator configuration,
and scheduling change must pass its applicable no-op and isolation checks.
Re-run sentinel states after serving updates. A failed gate quarantines affected
causal outputs; do not subtract a replay “noise floor” from the effect.

Freeze failure classes before summaries:

| Class | Treatment |
|---|---|
| Valid no divergence | Retain in the primary policy denominator with zero gain |
| Valid algorithmic failure under the frozen policy | Retain its benchmark failure outcome and termination reason |
| Pending/incomplete branches | Pending, never zero or no divergence |
| Infrastructure failure, wrong config, replay mismatch | Quarantine/missing; repair and rerun by a logged rule |
| Context overflow | Classify by cause: intended frozen context policy failure versus misprovisioned server; never silently alter the prompt |
| Retry | Preserve every attempt; exact-input infrastructure retry only under the frozen rule, with designated accepted-attempt logic unrelated to success |

Publish attrition by cell, domain, block, and pre-outcome state properties. A
complete-case cohort can become informative if difficult/long states are more
likely to fail. Restore the planned population when feasible; otherwise disclose
coverage and bound sensitivity to unresolved units rather than analyzing only
successful jobs as the original target.

Robustness to a different user simulator or genuinely new simulator seeds is a
separate experiment. Freeze the simulator version, prompt, seed distribution,
state-restoration semantics, and repetition scheme before it runs. Changing only
the agent prompt nonce is not this experiment. A different simulator may respond
differently to the same prefix, so define whether the claim concerns a local
continuation intervention or a fully regenerated episode. Non-LLM-user tasks
(such as the existing ALFWorld/BFCL extensions) provide triangulation, not proof
that every simulated user setting generalizes to real users.

## 11. From signed labels to a deployable policy

The relevant target is expected **net** benefit, not the chance of any change or
the chance of rescue alone. An action-only selector should learn
`tau_action(x) = E[Y_BQ-Y_QQ | x]`. Separate heads may learn
`tau_suffix(x) = E[Y_QB-Y_QQ | x]` and `tau_full(x) = E[Y_BB-Y_QQ | x]`.
Do not train an action-only deployment on the union of action-rescue and
suffix-rescue labels: these are different interventions. This explicitly refines
the draft deployment-target wording in `FORK_PROTOCOL.md` §14; it does not change
the existing fork primary or silently authorize that deployment experiment.

The four observed branch returns supply full-feedback supervision at admitted
states. Standard regression or cost-sensitive policy learning is sufficient to
start. Predicting expected gain, subtracting cost, and choosing the best option
are established decision principles, not a new theory contribution. Include
no-op as a candidate; a quantized action can be preferable to BF16's action.

For the first deployment experiment, prefer a **single intervention per episode**:
the frozen trigger follows Q until its first eligible trigger; then it executes
one explicitly chosen action/suffix scheme. Before that trigger, the history
distribution follows Q. With a history-measurable stopping time T and a fixed
post-trigger scheme m, its value difference is the expectation of that scheme's
conditional advantage at the selected Q state (zero if no trigger). This is a
useful identification restriction, not a new theorem or a justification for
evaluating arbitrary repeated switches from one-pivot data.

Training only on first oracle-divergence states does not provide general support
for an ordinary-state trigger. Use the separately frozen ordinary-state bank.
Compressed features can omit history that also determines first-trigger
selection, so an offline score alone is insufficient; the final evaluation must
run the frozen policy closed loop.

Allowed deployment features must exist before the chosen intervention: Q-visible
history, generated Q action if its computation is charged, Q uncertainty summaries,
schema/tool information, previous observed errors, and remaining budgets. Forbidden
features include future QQ success, realized remaining trajectory length, oracle
pivot time, task-ID fragility measured from test outcomes, and free BF16 shadow
queries. If BF16 is queried for features or action comparison, charge it even when
the router subsequently chooses Q.

Freeze policy, feature transformation, intervention semantics, thresholds/budget,
task and nonce splits, and analysis before evaluation. A deployable random baseline
must use a prospectively calibrated trigger schedule/budget cap; it cannot be
matched by looking ahead at how many calls the learned policy used on a test
episode. Report realized budgets and cost-quality curves on a prespecified grid.

Define whether the primary resource constraint is an expected/average episode
cost or a hard per-episode cap. Fixed `QB/BB` suffix labels assume B continues to
termination. A hard cap that switches back to Q, clips an action, or terminates
early defines a different intervention and is not evaluated by those labels.
Either retain the fixed suffix under a calibrated expected-cost constraint or
freeze the explicit budget-aware suffix controller and collect/evaluate its own
outcomes. No hidden fallback may change the intervention at deployment.

Label/prediction transport can be evaluated on independently collected held-out
branch outcomes without training an entire routing system. It requires controlled
supervision baselines and the declared state/task/transport split. Fresh full
closed-loop episodes are additionally required for a deployed-policy benefit claim.

Deployment baselines include always-Q and always-BF16 as reference anchors (not
assumed lower/upper bounds), random, simple tool/error rules, uncertainty/divergence
selection, and a comparable learned failure-risk/signed-gain baseline. Compare
budget-sensitive policies under the same frozen primary resource constraint;
always-Q/B anchors generally do not have the same cost as an intermediate policy.
For a competitive precision-routing claim, include the relevant existing approach, including
its terminal-reward refinement where feasible; do not compare only its KL warm
start and claim superiority over reward-trained routing. Charge training fork
compute as well as deployment cost. Compare action-only/suffix-only/multi-head
variants before attributing gains to the four-branch design.

Report actual episode success, net gain, rescue/damage under the stated pairing,
trigger frequency/timing, false/late triggers, cost, and failure modes. Oracle
value at the true pivot remains an oracle diagnostic, not policy value. Preserve
the declared primary deployment comparison independently of which baseline is
easiest to beat.

## 12. Confirmation, multiplicity, and interpretation

Before opening any untouched confirmation output, freeze and hash:

- task/split/cell/draw/block manifests and the target population;
- the original `G_all` primary and its existing decision rules;
- any new secondary endpoint definitions and their finite hypothesis families;
- task/domain/cell weights, eligible strata, and interaction contrasts;
- annotation rubric, sampling rules, and prediction/routing policy if applicable;
- interval/test method, missingness/retry rules, precision planning, and stopping
  schedule based on development variance and resource constraints;
- analysis code and a mock-data run verifying denominator and sign identities.

Group related secondaries (for example r/d/M, reversals, directional replication,
and predefined moderators) and specify multiplicity control such as Holm within
the declared confirmatory family. State whether conclusions are family-wise or
descriptive. Do not turn every cell in a 25-condition matrix into an independent
confirmatory headline. Use one prespecified pooled/factorial contrast or a small
set of explicitly corrected contrasts, with the full cell matrix descriptive.
The separate frozen W×A×KV preregistration retains its own scope and matched
rotation controls.

For the historical success comparison `Delta = success(Q)-success(B)`, NI at
epsilon = 0.03 requires the prespecified lower bound above -0.03; equivalence
requires the prespecified TOST/90% interval criterion inside [-0.03, 0.03]. A
non-significant difference is not either result. For existing `G_all`, distinguish
a positive benefit (one-sided lower bound above zero), a benefit exceeding g_min
(bound above 0.03), and a small effect (the existing 90% interval wholly inside
[-0.03, 0.03]). An interval overlapping the boundaries is inconclusive; do not
widen them retrospectively or interpret near-zero G as small M.

If a new result is discovered after confirmation data are inspected, record it as
exploratory. Another analysis of the same holdout is not another independent
confirmation. Fresh nonces on already exposed tasks can validate a perturbation
effect, but cannot restore task-level holdout status. All claims must identify
which dimension was unseen.

## 13. Deliverable schemas and implementation order

### 13.1 Unit-level output

Write an append-only `consequence_units_<snapshot>.jsonl` with at least:

```json
{
  "schema_version": "consequence-v1",
  "source_commit": "...",
  "analysis_commit": "...",
  "snapshot_id": "...",
  "split": "dev",
  "task_pool_manifest_sha": "...",
  "suite": "tau2",
  "domain": "retail",
  "task_id": "...",
  "model_id": "...",
  "quantizer_config_sha": "...",
  "calibration_draw_id": "d1",
  "prompt_block_id": "f01",
  "prompt_nonce_sha": "...",
  "simulator_config_sha": "...",
  "user_seed": 0,
  "continuation_repeat_id": null,
  "randomness_coupling": "deterministic-frozen",
  "state_bank_id": "legacy-first-semantic-divergence",
  "state_id": "...",
  "history_sha": "...",
  "env_sha": "...",
  "prompt_ids_sha": "...",
  "decision_idx": 2,
  "selection_probability": 1.0,
  "analysis_weight": 1.0,
  "eligibility_status": "divergent",
  "missing_reason": null,
  "replay_gate_pass": true,
  "evaluator_id": "retail-db-success",
  "Y": {"BB": 0, "BQ": 1, "QB": 1, "QQ": 0},
  "pattern_BB_BQ_QB_QQ": "0110",
  "effects": {"A": -1, "C": -1, "I": 2, "G": 1, "H": 1, "F": 0},
  "effect_source": "observed-deterministic-forks",
  "rescue": 1,
  "damage": 0,
  "gross_change": 1,
  "strict_reversal_observed": true,
  "branch_artifact_refs": {"BB": "...", "BQ": "...", "QB": "...", "QQ": "..."},
  "process_cost_refs": "...",
  "annotation_refs": "..."
}
```

No-divergence rows retain nullable branch outcomes and an explicit no-intervention
primary gain. Missing rows retain missing effects. Add calibration, serving,
tokenizer, simulator, and retry provenance through immutable linked manifests.
Store continuation-average contrasts separately from binary realized patterns.

### 13.2 Summary products

| Output | Required contents |
|---|---|
| `coverage_<snapshot>.json` | Expected/observed tensor, common intersections, denominators, attrition/retry/gate reasons |
| `consequence_estimands_<snapshot>.json` | G/H/F/A/C/I, r/d/M, raw/conditional/policy estimand IDs, weights, uncertainty metadata |
| `patterns16_<snapshot>.csv` | Every binary pattern and count, including zeros, by declared strata |
| `w67_audit_<snapshot>.md` | Original-versus-corrected interpretation, exposure/null issues, no silent replacement of history |
| `direction_replication_<snapshot>.json` | Frozen A/B membership/rankings, validation effects, opportunity baselines and uncertainty |
| `taskheldout_prediction_<snapshot>.json` | Grouped outer folds, training-only choices, out-of-fold scores, gain/cost/calibration |
| `matched_state_transfer_<snapshot>.json` | Shared-state manifest, exact intervention pairs, source/target split and transfer estimates |
| `annotation_review_<snapshot>.json` | Blinding/randomization manifests, evidence spans, independent labels, disagreement/adjudication |
| `mechanism_interventions_<snapshot>.json` | Fixed prefix/configuration, intervention and control definitions, doses, all measured effects |
| `closedloop_policy_<snapshot>.json` | Frozen policy ID, episode outcomes/costs, real triggers, matched-budget comparisons |

Each summary must link its input snapshot, code hash, manifest hashes, and unit
file. Do not overwrite old results. Register delivered artifacts in the results
index during implementation, with `exploratory`, `internal_replication`, or
`unseen_confirmation` stated explicitly.

### 13.3 Execution sequence and completion checks

**Stage A: inexpensive analysis audit, existing development data only.**

- [ ] Verify split guard before every load and publish coverage/common pools.
- [ ] Recompute the sign dictionary and all 16 patterns; assert aggregate G=r-d
  and M=r+d on the identical declared denominator.
- [ ] Preserve original G_all outputs and explain any difference caused by fixed
  bugs or denominator repair, rather than presenting it as a new hypothesis.
- [ ] Produce corrected W67 descriptive tables and nonce-split replication.
- [ ] Run task-held-out signed-gain versus opportunity/divergence baselines.
- [ ] Record whether action-ranking reversal and label transfer remain unresolved.

**Stage B: targeted evidence acquisition, frozen before each new branch.**

- [ ] Freeze ordinary-state and common-state manifests, controls, and target weights.
- [ ] Complete blinded content review and quantitative process-cost summaries.
- [ ] Choose a small, declared mechanism panel using development-only criteria;
  include sham/random/dose controls and unfavorable cases.
- [ ] Validate any stochastic simulator extension and preserve all replay failures.
- [ ] Use action-only/suffix-only contrasts to define the intervention semantics
  being compared in the fixed deployment panel. Neither a significant interaction
  nor a strict ranking reversal is required to continue the other workstreams.
  Lack of predictable benefit is reportable, not a reason to search indefinitely
  for a favorable cell or reallocate compute by interim significance.

**Stage C: independent validation.**

- [ ] Freeze the confirmation protocol and analysis before the telecom holdout.
- [ ] Run the original primary plus prespecified, multiplicity-controlled secondaries.
- [ ] Run any frozen deployment policy as complete fresh episodes; keep oracle
  diagnostics visibly separate.
- [ ] Publish all planned cells/endpoints, deviations, uncertainty, and null results.
- [ ] Match the final paper's claim level to what replicated: measurement,
  mechanism, prediction, and deployment are separate evidentiary steps.

No conformal test is needed for this plan. No thresholding, bootstrap correction,
factorial identity, or expected-gain routing equation should be presented as a new
statistical contribution without an independently established theoretical advance.
