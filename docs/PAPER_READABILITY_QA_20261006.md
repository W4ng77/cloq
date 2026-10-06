# Readability and argument revision, 2026-10-06

Base: CLOQ `939c7b85f96817ee99338ab8976f5c8c291c7f1d`.
This is a writing and presentation revision. It changes no estimator, analysis population, admission rule, frozen reading, checkpoint, or experimental output.

## Argument

The main text follows three questions: what a specified precision intervention changes; what reference interventions establish about those changes; and whether one frozen selector turns sensitivity into net benefit. The motivation is the task benefit of a concrete BF16 fallback, rather than model drift in isolation. Factorial step valuation is credited to prior work.

The abstract has 177 words in the rendered PDF. Long findings cards and protocol-like paragraph headings were replaced with a short three-question introduction. Timeline and inference detail remain in the supplement. The direct common-state comparison remains unresolved and does not establish equivalence. The holdout's negative estimate and the omission in its frozen categories both remain explicit. The trigger finding remains specific to one frozen rule.

The Discussion distinguishes a realised effect under the fixed execution stack from an expected value over a defined deployment distribution. It does not infer that all labels are arbitrary, call the system chaotic, or claim a new average-over-perturbations experiment. The selected RTN-W3 example remains exploratory and is identified as selected from the stress panel.

## Presentation

- Main consequences: two large panels replace the four narrow panels. Development and holdout retain their distinct intervals and populations. The complete former figure remains in the appendix.
- Main references: the same-precision substitution, key-order reference and direct common-state value comparison form a three-panel argument. The main common-state panel shows the two-look 97% reading intervals; the original complete figure, including unadjusted intervals and W3/continuation details, remains in the appendix.
- Selection: removed the broken axis. The hindsight oracle is a separate numerical strip. Trigger and random net gains share one axis, and markers no longer highlight the uncorrected 5% result. All exact p-values and actual selected counts are retained.
- State-source schematic: larger text and three plain-language state definitions replace a crowded interval/protocol diagram. Replay counts remain in Method.
- Scope table: a plain three-column booktabs table replaces the glyph-and-colour matrix. Scope populations, selection caveats, estimates and intervals are retained.
- Closing argument uses the available space for interpretation and a Conclusion. No margin, body-font, or ACL-style modification was used.

## Inconsistencies corrected

1. Method now distinguishes weight-only W4 with BF16 KV from the separate KV8 configuration with BF16 weights.
2. The initial 135-state holdout audit is explicitly initial, resolving the obsolete statement that no other state was replayed before the later 1202-state full replay.
3. The general output-failure description now points to the amended Mistral missing-data exception.
4. The continuation-only overlap description no longer says that B "also" takes over, which could be read as joint replacement.
5. Ethics identifies the actual task-success endpoints, including database-only retail/airline scoring.
6. An underpowered telecom-development result is no longer used to rule out a domain effect.
7. Updated all retained panel pointers after the figure reorganisation.

## Supplement selection

The compiled paper omits the historical injection/restoration/withdrawn-interaction appendix and the label-transfer/takeover-duration follow-up appendix, which no main-text claim uses. Their source files and research records remain in the repository. Primary results, unresolved primary contrasts, sampling/scoring rules, audits and dated amendments remain disclosed. A short provenance section replaces the unrelated historical appendix in the compiled supplement.

## Validation

- Clean XeLaTeX build: 36 pages, Conclusion on page 8, Limitations beginning on page 9; no overfull boxes or undefined references/citations. The original committed Tectonic PDF and an unchanged XeLaTeX baseline both had 36 pages and the same main-text boundary. Tectonic itself is unavailable here; repeat the production build on the cluster before submission.
- Visually inspected all eight main-text pages and each changed figure, checking labels, legends, cropping and the ending columns.
- Original figure data-loading/assertion routines are reused. New plots consume the same committed JSON outputs; metadata records source hashes and renderer hashes. No outcome values were edited.
- Fifteen detailed result tables have identical numerical row sequences before and after. All scope-table estimates/intervals match; two duplicate bit labels were removed by the redesign.
- PDF text/metadata have no identifying usernames, project account links or local cluster paths.
- Local `check_numbers.py` has no new unmatched values relative to the unchanged baseline. A full PASS cannot be claimed here: eight pre-existing metadata-dependent numbers and 31 source paths require the cluster's run/checkpoint/simulator metadata. Run the full check there and regenerate the anonymous submission copy from this revision.

Renderers: `paper/latex/tools/figs/make_readable_main.py` and `make_trigger_readable.py`. The complete old numerical displays are retained as supplementary figures; no discarded research branch is used to strengthen a main claim.
