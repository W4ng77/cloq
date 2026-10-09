# Readability revision, 2026-10-09

## Editorial aim

Explain the value of a precision fallback through one evidence chain: measure rescues and damages, test precision attribution with references, and test whether selection produces task benefit. Keep the experiment results and their strength unchanged.

## Changes

- The abstract and introduction begin with the fallback decision and its task consequences. The introduction distinguishes running a model from the start from inserting it into another model's history.
- Contributions now distinguish the measurement protocol from the empirical reference tests. The findings are shorter and point directly to the three result sections.
- The method explains BQ, QB and BB as complete executions, so the continuation's role is understandable before the results.
- Result 1 puts rescues and damages first. The negative telecom estimate is stated directly, alongside the missing negative category in the registered interpretation. The potential hybrid-trajectory explanation remains explicitly untested.
- Result 2 gives the checkpoint and representation references distinct roles, then asks about extra BF16 value at identical states. Two overlapping concluding paragraphs are replaced by one.
- Result 3 explains what the same selected decisions show under capture and net-benefit objectives. The conclusion remains confined to one frozen margin rule on later blocks of the same tasks.
- Discussion is organised into three themes: BF16 is a reference rather than an oracle; selection must target the executed upgrade; controlled realised outcomes differ from expected deployment benefit. Repeated summaries of the three result sections are removed.
- Figure 2's caption is shortened while preserving its denominators, confidence levels, registration status and AWQ-style qualification. Figure assets and numerical table bodies are unchanged.
- The final layout pass removes an awkward cross-column split and a one-line continuation at the top of the final column, by shortening prose rather than adjusting fonts, margins or spacing.

## Evidence boundaries preserved

No experimental estimate, interval endpoint, scoring rule, or statistical interpretation is changed. In particular:

- The main W4 net estimate remains unresolved on new tasks.
- The holdout has a negative observed estimate and an inconclusive registered classification because the protocol omitted a negative category.
- Q-prime and key-order turnover do not establish equivalence and are not subtracted as a noise floor.
- The shared-state estimates leave a useful BF16 advantage possible.
- The RTN-W3 example remains an exploratory configuration selected from five stress settings.
- The selector result does not establish failure of learned routers or of uncertainty-based routing generally.
- No mechanism is attributed to the negative holdout or to representation sensitivity.

## Verification

- Fresh pdfLaTeX/latexmk build completed successfully with the actual edited wording verified in the resulting PDF.
- Main text occupies 8 pages; Conclusion is on page 8; Limitations begins on page 9. Total PDF: 32 pages.
- Abstract: 195 whitespace-delimited words in extracted PDF text, excluding line numbers.
- All eight main pages were rendered and inspected. No clipped figures, overlapping text, or table overflow was observed.
- The final log has no overfull boxes, undefined references, undefined citations, or multiply defined labels.
- Static reference check: 21 active source files; no missing citation keys, missing reference targets, or duplicate labels.
- Main prose contains none of the internal names Bank P, Bank U, Pocock, Amendment, f01, or revision-history labels.
- Numerical-token differences were compared against the pre-edit source. Changes concern repetitions of BF16 and expansion of model aliases, not experimental quantities.
- The local numerical checker scans 3196 occurrences, with 7 unverified pre-existing metadata quantities and 28 missing source paths. Those paths refer to cluster checkpoint, queue, calibration and simulator metadata not present in this snapshot. It reports zero missing required source annotations. This is not a full numerical-check PASS; the full check still requires the cluster metadata.

Final PDF SHA256: `05109924d01c2a1f287d946d96283e10f1dc49afa0ddf1561f866bb107091024`.

## Publication scope

Update the source and compiled PDF in CLOQ and its GitHub paper mirror. The mirror PDF is named `main_local_build.pdf`. Direct Overleaf pull/compile is not performed in this environment.
