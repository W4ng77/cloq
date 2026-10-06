# Paper visual revision, 2026-10-06

Base: `573afc26e663e7a1d13ae90fb6de2943a30ed16c`. This revision changes presentation and a few scope clarifications; it does not change any estimate, confidence interval, outcome, or analysis decision.

## Presentation

- Figure 1: readable action-source by continuation matrix, retaining the audited joint-rescue example.
- Figure 2: full-width development and holdout panels with separate populations and interval conventions; signed rescue/damage bars and net diamonds.
- Figure 3: two aligned panels for capture and net gain; hindsight oracle values in a separate numerical strip. Actual selected counts remain visible.
- Main reference table: three population groups, right-sized numerical columns, one primary paired contrast per group, complete inference details in the appendix.
- Scope table: existing RTN-W3 continuation/full gains promoted as an exploratory stress example, not a prospective positive control or a bit-width dose-response result.
- Appendix: wide tables split into stacked panels with literal data cells preserved. Numerical tables use an explicit 8.5-point font rather than whole-table shrinking. Coverage and quantization-setting tables wrap prose in ragged-right columns; floats align at the top of appendix pages.
- Conclusion retained. Main text ends on page 8; Limitations starts on page 9. The full PDF is 32 pages, reflecting more readable appendix tables.

## Review clarifications

- Fixed greedy-stack branch outcomes are distinct from per-state expectation over nuisance perturbations or alternative simulators.
- Trigger budgets are target quantiles on the development block, not exact selection quotas on subsequent states; random selection matches the actual selected counts.
- The Mistral 83-task conditional population points to its appendix description.

## Verification

- Compiled successfully; no overfull boxes, undefined references, or oversized-float warnings.
- Inspected all rendered pages and the main figures and wide tables at full resolution.
- Original numerical-token multisets were compared against 24 retained table blocks: no original numerical data tokens were lost. Stacked panels repeat identifying columns but do not recompute data cells.
- Figure generation uses the original data and retained source-value assertions; interval values and significance are unchanged.
- `check_numbers.py` was run on both the base sections and revised sections against the same available sources. Base: 3675 occurrences; revision: 3669 occurrences. Both have the same eight unverified metadata values and the same 31 unavailable source paths, with zero uncited/missing required sources. There are no new numeric-check failures.
- This environment cannot honestly claim a full `check_numbers` PASS: uncommitted cluster quantization/calibration metadata and adjacent `cloq_work` files are unavailable. Run the existing checker in the complete cluster checkout before submission. The checker and source data were not altered to suppress these failures.
- The pending full-QQ holdout replay is not replaced by this presentation revision; its new evidence must be incorporated only after the registered audit completes.

## Cluster build check (lead, 2026-10-05 PDT, on top of 2addfca)

- With the submission toolchain (tectonic on the cluster), 2addfca as pushed builds to 37 pages and the Conclusion runs about 16 lines onto page 9 (Limitations on page 10); the 8-page / 32-page figures above came from a different build environment. Fixed by: Figure 3 height 2.05 -> 1.8 in; one redundant oracle-count clause (the counts are in Figure 3 and Appendix Table 15) and one duplicated simulator sentence (in Limitations) removed; the fixed-stack sentence in Discussion shortened; three scope-table rows tightened. Result: 36 pages, main text ends on page 8, Limitations on page 9.
- Full `check_numbers.py` on the cluster checkout: PASS (no unverified values, no missing sources).
- Palette: same semantic roles, muted hues (B #3B75AF, rescue #4C9A7A, damage #C4553A, Q #A0647D, Q' #B08A3E, KV8/KL #7FA9D4) in make_figs.py and main.tex \definecolor; oracle strip boxes neutral grey. Label overlaps fixed in Figure 3 (legends, +2 label) and the clipped panel titles of Figure 2.
- Scope table: the RTN-W3 row now says it is one of five stress configurations (exploratory), and its interval type (crossed 95%) is stated in the caption.
