# Storyline v6: tracing precision changes to agent consequences

Updated 2026-09-30 America/Toronto (2026-10-01 UTC). This is a substantial revision of the earlier v6. Its superseded fingerprint/equivalence framing remains in Git history. Current authority: [execution plan](../EXECUTION_PLAN_20260930.md), with [coverage](QUANT_BENCHMARK_COVERAGE.md), [analysis](CONSEQUENCE_ANALYSIS_PLAN.md) and [positioning](RELATED_WORK_POSITIONING.md).

## 1. Fixed question, evidence-dependent answer

**Working title:** *Tracing the Consequences of Quantization in Closed-Loop Agents*.

An agent's complete action matters through the environment and the controller that follows it. We study how changing weight, activation and KV precision changes that action, how subsequent execution absorbs or amplifies the difference, and whether the resulting information transfers to new tasks or useful precision decisions.

The paper is a methodology-driven empirical investigation. It needs a distinctive validated finding, broad scope and controlled evidence; it does not require inventing a new quantizer or winning with a router. Existing live forks and factorial designs are credited rather than presented as new mathematical constructions.

The central argument has four parts:
1. Aggregate success is an incomplete description: separate rescue, new damage and process cost.
2. Current action and subsequent execution are separately intervenable precision decisions: measure all four branches on identical states.
3. Consequences may depend on semantic errors, recovery opportunities, budget/context and structured numerical error: test these competing explanations rather than name a mechanism from correlation.
4. Action-value information may or may not transport across continuation precision and quantizers: evaluate it, then test a practical intervention only if warranted.

“May” is intentional. Ranking reversal, stable state fragility and deployment benefit remain hypotheses.

## 2. Breadth supports the argument

The required weight axis is BF16/W4/W3 across supported RTN, GPTQ and AWQ implementations. W8-only is an optional small reference, not a full required sweep. SmoothQuant W8A8 remains a distinct activation-method comparison; dynamic A8, QuaRot W4A4, KV8/rotated KV4 and K-only/V-only are retained.

Add a bounded W2 subset to characterize destructive and looping regimes. Early stopping is a shared, validated evaluation rule for new stress comparisons, with explicit failure reasons and original-cap sensitivity; it is neither a hidden sample filter nor a claimed repair intervention. Existing registered stop rules remain fixed.

Two W×A×KV families stay separate: the matched rotated W4/A4/KV4 cube and the planned plain W4/A8/KV4 family. q8's existing confirmation is only the fixed-A16 W×KV four-corner test with six blocks.

Coverage spans q4/q8, model scale, an available second family, and retail/airline/telecom/BFCL/ALFWorld. WebShop is a gated extension. Show common-population contrasts and cell-specific coverage separately. Keep unsupported methods and incomplete lanes visible.

Breadth is a contribution to scope, not an automatic novelty claim. At freeze, the main text develops the two or three strongest independently checked findings from this prespecified portfolio; the appendix presents the complete matrix.

## 3. Depth and the strongest possible storyline

| Finding, if established | Appropriate paper statement | Additional evidence needed |
|---|---|---|
| Large rescue and damage with a small aggregate mean | Quantization changes which trajectories succeed, with offsetting effects | Paired population, numerical floor, replicated uncertainty and correct scoring |
| Current-action and suffix effects interact | Local precision decisions depend on the declared continuation | Matched four arms, all patterns, distinction from strict ranking reversal |
| Differences are mostly absorbed | Many local deviations are corrected within the tested budgets | Adequately estimated branch/process effects and actual correction traces; an inconclusive mean is insufficient |
| Damage concentrates in identifiable pathways | Specific operations or recovery conditions mediate harmful consequences | Independent label replication, blinded annotation and controlled injection/budget contrast |
| Structure matters beyond perturbation magnitude | Quantization and matched random error produce different consequences | Matched norms/shapes/engine plus independent error seeds and dose analysis |
| Consequence labels transfer poorly or well | Action-value supervision depends on continuation/configuration to a measured extent | Ordinary immutable states, task-grouped held-out outcomes, matched features and budgets |
| A precision intervention improves live outcomes | Consequence information supports a practical decision under the declared constraint | Full episodes, complete-method baselines, no oracle features and charged total acquisition/inference cost |

A near-zero G can support only the claim justified by its interval. It does not establish equality or successful recovery by itself. Negative application results can delimit intervention strategies when evaluated fairly.

## 4. Identification backbone

At a frozen shared state, B/Q current actions crossed with B/Q continuations produce BB, BQ, QB and QQ. The loss-oriented dictionary is:
\[
A=Y_{BB}-Y_{QB},\ C=Y_{BB}-Y_{BQ},\
I=Y_{BQ}+Y_{QB}-Y_{BB}-Y_{QQ}.
\]
The action-only replacement gain is G=A+I; suffix-only gain H=C+I; replacement of both F=A+C+I. Include rescue/damage and all 16 outcomes. Interaction alone is not strict reversal.

Bank P estimates the task-pool effect at the first semantic divergence, preserving zero action effect for non-divergent tasks. Bank U samples ordinary Q states before outcomes and includes agreement states. It supports actual state transfer and policy-relevant information; agreement does not imply zero suffix effect.

The protected telecom 34-task confirmation keeps its G_all primary endpoint. More mechanism hypotheses do not replace it. Fixed-task, new-task and new-checkpoint inference are reported separately.

## 5. Mechanism portfolio

- Trace complete tools/arguments, consent, state mutation, termination, retries and actual corrections.
- Use checkable automatic labels, a blinded frozen LLM rubric and about 80 human-reviewed states, about 20 independently double-reviewed. These are planned workloads, not completed annotation claims.
- Inject matched valid/invalid actions and vary fixed recovery budgets or context conditions.
- Reuse residual dose and restoration as diagnostics, with same-size random/module controls. Dominated restoration remains a deployment negative.
- Analyze same-input residual/attention/MLP representations only after engine parity; use task-grouped probes.
- Patch bounded modules with sham/random/magnitude controls and rerun the full tail. Latent similarity or a probe alone is not causal evidence.

These lanes proceed in parallel; no single positive mechanism is the project's go/no-go.

## 6. Closest work and application boundaries

Credit precision routing, flat-score behavior, live-fork evaluation, counterfactual utility/credit assignment and agent-aware calibration. Explain exact differences using the [primary-source comparison table](RELATED_WORK_POSITIONING.md).

The first application is continuation-matched label transport on unseen declared state/task populations. A second, optional application is a one-trigger live precision intervention under a prospectively fixed resource constraint. Prediction value and deployed-policy benefit are different claims. Competitive routing requires closest full methods as well as equal-capacity signal controls.

Fake quantization is appropriate for numerical consequences. Speed/memory gains need actual native-format end-to-end measurements. Conformal is outside the title, abstract and core method.

## 7. Retired headline claims and reusable evidence

| Prior storyline | Current role |
|---|---|
| Checkpoint lottery | Negative preregistered result and transparency record |
| Persistent W4 fingerprint | Not detected after H3 correction; original statistic invalid |
| Random fixed-perturbation fingerprint | Exploratory comparison; does not establish W4 fingerprint |
| Quantization-specific act/talk blurring | Selection-null warning; no established unique channel |
| Success-rate equivalence | Unsupported as a general claim; preserve declared NI/TOST analyses |
| Static restoration as a competitive deployment method | Existing negative frontier; reuse only as controlled diagnostics |
| W67 stable state fragility | Candidate task associations pending shared-block/double-use and actual-state tests |

Previous work remains valuable as motivation, infrastructure, controls, matched runs and audit data. [The result index](../../analysis/RESULTS_INDEX.md) and source hashes identify what is reused.

## 8. Figures and abstract rule

Use the [main plan's figure inventory](../EXECUTION_PLAN_20260930.md#11-manuscript-storyline-and-figures): one reviewed four-arm example; broad outcome/consequence map; four-arm decomposition; actual transport/heterogeneity; controlled mechanisms; optional measured application.

Write the abstract after the October 5 evidence freeze. Every numerical or mechanistic claim must link to a frozen output, population, evaluator, interval and limitation. Do not put pending hypotheses in the abstract as results.
