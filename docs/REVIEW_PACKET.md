# Review packet: tracing quantization consequences in closed-loop agents

Updated 2026-09-30 America/Toronto (2026-10-01 UTC), using repository snapshot [2c68559](https://github.com/W4ng77/cloq/tree/2c68559f619810dc82a2de008f2030656df1f420). This packet supersedes the old equivalence/fingerprint framing. Historical versions and original results remain in Git history and the research log.

## 1. What this project is now

**Working title:** *Tracing the Consequences of Quantization in Closed-Loop Agents*.

**Question:** how do weight, activation and KV precision change complete agent actions, how do those changes propagate under different continuation controllers, and which consequences generalize or support an actual precision decision?

The target is a methodology-driven empirical paper with broad measurements, controlled mechanisms and reusable evidence. The method is an identification/evaluation protocol, not a claim that factorial experiments or live forks are new. A useful learned policy would add an application contribution, but the entire paper does not depend on it or on finding a strict ranking reversal.

The contribution portfolio is:
1. A validated shared-state precision intervention protocol with explicit estimands, replay controls and task/block inference.
2. A broad account of rescue, damage, absorption and process costs across compression axes, model scale/family and interactive tasks.
3. Controlled evidence for pathways such as recovery, irreversible actions, context/budget effects and structured numerical error.
4. Tests of continuation-matched label transport and, if supported, a genuinely evaluated budgeted precision intervention.

The full matrix supplies generality. A distinctive, independently checked finding is still required; breadth alone does not guarantee venue acceptance.

## 2. Read these documents in order

| Document | Purpose |
|---|---|
| [Execution plan](EXECUTION_PLAN_20260930.md) | Authoritative current scope, contribution portfolio, resource allocation, schedule and completion rules |
| [Current storyline](insights/STORYLINE_v6.md) | Manuscript structure, hypotheses and allowed claim strength |
| [Coverage contract](insights/QUANT_BENCHMARK_COVERAGE.md) | Exact quantization/model/benchmark panels, admission gates and failure reporting |
| [Consequence analysis](insights/CONSEQUENCE_ANALYSIS_PLAN.md) | Full four-arm dictionary, 16 patterns, state banks, inference, mechanisms and application design |
| [Related-work positioning](insights/RELATED_WORK_POSITIONING.md) | Verified primary sources, closest overlap and concrete comparison obligations |
| [Night status](STATUS_20260930_night.md) | Historical latest-result snapshot; its W67 interpretations require audit |
| [Fork protocol](insights/FORK_PROTOCOL.md) / [W×KV preregistration](insights/WAKV_PREREG.md) | Existing implementation and frozen confirmation commitments |
| [Result index](../analysis/RESULTS_INDEX.md) / [research log](RESEARCH_LOG.md) | Numerical provenance and original outputs |

This planning update does not unlock the telecom holdout, change frozen endpoints, enqueue work or claim proposed implementations have passed their gates.

## 3. Current evidence and corrections

| Result | Current interpretation |
|---|---|
| W4 outcome turnover above the numerical noise floor | Supported in tested configurations; motivation for looking beyond average success |
| Checkpoint lottery | Did not replicate in preregistered testing; retain the negative record |
| Old H3 fingerprint statistic | Invalid preprocessing: real-pair scaling was reused during permutations; simulated false rejection was 33–42% at nominal 5% |
| Repaired H3 | Approximately 4.4% simulated false rejection; no detected persistent W4 fingerprint, p about 0.30; random-perturbation fingerprint is exploratory |
| Conditional act/talk channel | Largely reproduced by selection under a symmetric null; no established quantization-specific channel |
| W4 first-divergence action swaps | Initial pooled rescue 9.7%, damage 9.0%, turnover 18.7%, net gain +0.6 pp; crossed interval spans zero |
| Success-rate tests | Distinguish fixed-pool NI from new-task equivalence. Current task-resampled TOST does not establish global equivalence |
| W67 concentration/sign/overlap | Candidate associations, not yet validated state fragility: shared blocks, double-use and different state histories must be audited |
| Static precision restoration | Existing configurations are dominated by GPTQ-W4 on storage/outcomes; retain the deployment negative and reuse mechanism evidence |
| Replay, A/KV fidelity and external forks | Reuse only for actually validated configurations and benchmark scoring; new configurations need their own admission gates |

Do not quote this table without the checkpoint, task population, nonce blocks and evaluator from the source output. In particular, q8 summaries on 165 tasks and q4/KV summaries on 85 tasks are not directly comparable.

## 4. Identification design and statistical target

At one identical pre-action history, independently vary the current complete action source B/Q and continuation controller B/Q, obtaining Y_BB, Y_BQ, Y_QB and Y_QQ.

The current loss-oriented decomposition is
\[
A=Y_{BB}-Y_{QB},\quad C=Y_{BB}-Y_{BQ},\quad
I=Y_{BQ}+Y_{QB}-Y_{BB}-Y_{QQ}.
\]
The action-swap gain under Q continuation is G=Y_BQ-Y_QQ=A+I. Suffix replacement is H=Y_QB-Y_QQ=C+I; replacing both is F=Y_BB-Y_QQ=A+C+I. F and H are not cheap action-only gains.

Report all 16 binary patterns and rescue/damage/net effects. Nonzero interaction is not necessarily a strict action-ranking reversal.

Use two populations:
- **Bank P:** the existing first-semantic-divergence task design. Non-divergent task units receive its registered zero action-swap effect.
- **Bank U:** independently hash-sampled ordinary Q states, including agreement states, frozen before terminal outcomes. This supports actual shared-state comparisons and deployment-oriented prediction. Suffix effects are not zero merely because actions agree.

The protected telecom 34-task confirmation keeps G_all as its primary endpoint and its existing task-pool denominator. The q8 W×KV registration fixes four A16 corners and six blocks; the broader A4 factorial remains exploratory unless independently preregistered. Preserve the specified 3 pp margins and distinguish fixed-task block, crossed new-task and checkpoint-population uncertainty. Development splits of already viewed data are internal replication, not fresh confirmation.

## 5. Width and depth commitments

**Weight core:** BF16 plus RTN/GPTQ/AWQ W4 and W3 where faithful. No required W8-only sweep; an optional small low-error reference must justify its contrast and cost. Keep SmoothQuant W8A8 as an activation-method comparator, plus A8 and KV8 as independent axes.

**Joint precision:** finish the matched rotated W4/A4/KV4 cube and a separately identified plain W4/A8/KV4 family. Keep transformation controls matched and retain K-only/V-only diagnostics.

**W2/loop stress:** add a small frozen-subset W2 panel rather than a full grid. New stress contrasts use a validated common loop guard with complete-action/result/environment evidence, explicit algorithmic-failure accounting and an original-cap sensitivity. Existing frozen stop rules remain unchanged.

**Models/tasks:** q4/q8, q14 plus an audited larger model, an available second family; retail, airline, telecom dev, BFCL multi-turn and ALFWorld. WebShop is an adapter-gated extension. Protect telecom holdout. Record unsupported or incomplete cells visibly.

**Depth:** four-arm patterns, correct heterogeneity/transport tests, ordinary shared-state comparisons, blinded process labels, controlled recovery/budget/context interventions, residual-dose/matched-random contrasts, layer/module diagnostics, and fidelity-gated latent analysis plus bounded activation patching.

Start with one balanced paired block, use three as the descriptive breadth floor and five as the preferred expansion target; existing registered/core designs retain their replication rules. Replication count is not a power guarantee.

## 6. Closest-work boundary and impact

The positioning document examines Dynamic Mixed-Precision Routing, Flat Score, Amplified Failures, The Replay Gap, FutureBridge-OPD, COTA, Calibration Is Not Control, counterfactual/utility routing, and agent/task-aware quantization.

Avoid claiming novelty for flip measurements, live forks, standard factorial decomposition, signed outcome labels or a small router alone. The intended distinction is the precision-specific, shared-state separation of action and continuation, tested across compression axes and followed through real process consequences and transport. Its impact depends on what the experiments establish.

Prediction/label-transport comparisons use equal state pools, available features, learner capacity and budgets. A competitive routing claim additionally requires closest complete-method comparisons and fresh end-to-end evaluation with charged BF16 previews, labels, training and simulator cost. Fake quantization supports numerical-behavior conclusions; real efficiency requires native-format measurements.

Conformal is outside the core. The statistical contribution is correct estimands, crossed inference, rare contrasts, multiplicity and prospective confirmation.

## 7. Questions for an external reviewer

1. Which independently supported finding would best distinguish this protocol-driven study from the closest precision-routing and live-fork work?
2. Are Bank P and Bank U, their denominators and action/suffix estimands sufficient for the proposed claims?
3. Which recovery, budget/context or patching contrast would most decisively distinguish the competing mechanisms?
4. Does the coverage matrix support each proposed generalization, and where is an unsupported-format or benchmark-population confound still present?
5. Which baseline or cost omission would invalidate a label-transport or competitive-routing conclusion?
6. Which abstract claims survive if net gain is small, strict reversal is rare and a learned intervention does not outperform simpler signals?

The research question and portfolio are fixed. Results decide the strength and scope of the answers; they do not decide whether the other planned research questions are pursued.
