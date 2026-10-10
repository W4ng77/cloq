# Findings-oriented paper revision, 2026-10-10

## Scope

This revision uses existing experimental results only. It introduces no runs, estimators, power calculations, decision rules, or new claims of equivalence. The contribution remains a paired measurement protocol and reference interventions for interpreting the task benefit of precision fallback.

## Main changes

- Present all five existing lower-bit stress settings together in the single-column main-text Table 1. The joint-fallback new-task intervals exclude zero in two settings; the other three remain unresolved. These are exploratory, three-block, unadjusted contrasts, not a monotonic bit-width dose-response or a newly registered positive control.
- Distinguish the roles of the references. Calibration resampling and unchanged-operation key reordering show that outcome changes do not by themselves diagnose a precision deficit. The shared-state comparison directly measures BF16's additional action value and remains unresolved, with equivalence unestablished.
- State the measured object clearly: realised paired task consequences conditional on the recorded state and execution conditions. Individual rescue/damage labels are not claimed to be invariant to prompt, user or serving changes. A repeatedly triggered router has a different policy value.
- Keep the negative telecom estimate, the frozen protocol's inconclusive classification, the passed registered secondary checks, and the full QQ replay audit distinct.
- Narrow the selection result to the tested frozen margin rule. Its capture advantage does not establish a net-benefit advantage or the failure of learned routers generally.
- Add an appendix table summarising the design and amendment timeline. Add existing interval bounds as an estimation-precision summary, explicitly distinguished from minimum detectable effects and retrospective power.
- Explain the exact random-selection test using the joint rescue/damage distribution, sampling without replacement and the signed net-gain statistic. Existing p-values are unchanged.
- Shorten sentences and headings, remove duplicated discussion, define the pooled population and weighting, and maintain the main-text/appendix pointers.

## Verification

- Fresh local PDF build: 35 pages total; main text ends on page 8; Limitations begins on page 9; extracted abstract has 190 words.
- No undefined or multiply defined references, missing citation keys, or overfull boxes in the release build. Main pages were rendered and inspected, including paragraph/column endings and the new single-column table.
- All five promoted stress-setting G/H/F estimates and joint-fallback interval endpoints were checked against `analysis/fork/out/ghf_20261001T211519Z.json`. No estimates were recomputed.
- The local numeric checker cannot complete its full verification: it reports seven pre-existing metadata quantities and 28 unavailable cluster metadata paths. It reports no missing required source annotations. Run the full checker on the cluster before submission; this note does not claim a full numeric-check PASS.
- Release PDF SHA-256: `cd325b9b2ef5a9cbf88452bab90dc44ed291c41126364a46b6123c269c387965`.

The revision improves the argument and its scope; it does not guarantee conference acceptance. The GitHub paper mirror is updated separately from the Overleaf workspace, which must pull the source changes and compile them in the submission toolchain.
