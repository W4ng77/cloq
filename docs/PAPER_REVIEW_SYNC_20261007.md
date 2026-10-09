# Review follow-up and GitHub synchronization — 2026-10-07

Base: cloq c919dcc / cloq-paper 6db12c2. This is an editorial follow-up to the read-only review. No experiment, estimator, population, numerical result or protocol reading was changed.

## Changes
- Strengthen the contribution paragraph around the attribution gap between substitution sensitivity and a need for precision.
- Move the existing, selected exploratory RTN-W3 illustration to Result 1, where it explains the need for separate action and continuation contrasts. Retain its selection disclosure and scope table.
- Make the Q-only constraint specific to the tested selector rather than all deployable selectors.
- Clarify that the full QQ audit reproduced the baseline; distinguish two reference interventions from the direct common-state comparison.
- Remove repeated caveats and merge the discussion of conditional and deployment-distribution task values.
- Show trigger and matched-random values as discrete budget points without connecting lines. All source values and original numerical assertions are retained.

## Verification
- Local XeLaTeX preview: 36 pages, main text ends on page 8, Limitations starts on page 9; no overfull boxes or undefined references/citations.
- Visually checked revised first page, Result 1, trigger figure, scope table and final discussion/conclusion page.
- Numeric audit: 3611 occurrences; the same eight unverified metadata values and 31 absent source paths as before, zero new unverified values. Full check_numbers cannot pass in this local snapshot because run/queue/simulator metadata is absent; rerun on the cluster.
- Figure generation executes the existing source-value assertions. No data or analysis output changed.

The checked-in PDF is the local XeLaTeX preview for the changed source. Rebuild with production Tectonic and refresh the anonymous submission copy before submission. GitHub synchronization does not itself synchronize an Overleaf project.

## Table 1 visual follow-up

Replaced the dense three-column scope table with a two-column evidence overview, grouped by environments, model family and precision settings. Removed the redundant interpretation column, gave evidence more horizontal space, and separated configuration names from population metadata through font weight and neutral grey. All scientific numbers, intervals, sampling populations and the selected-stress disclosure are preserved. The main text still ends on page 8 and Limitations starts on page 9 (36 pages total). Revised pages 7 and 8 were rendered and inspected; there are no overfull boxes or undefined references. This remains a local XeLaTeX preview pending the production rebuild.

## Single-column redesign and prose pass — 2026-10-08

- Table 1 is now a single-column, five-group scope card. It communicates what each extension adds instead of repeating a dense numerical matrix. BFCL and ALFWorld share an environment group; the model-family, lower-bit, W/A and cache checks have separate groups. The selected RTN-W3 value keeps its exploratory qualifier.
- The complete former scope table, with all settings, samples, numbers, intervals and population qualifications, is retained as `sections/appendix_scope_overview.tex` and included in Appendix F. The main card points to it; the rows remain separate populations, not a ranking.
- Split long clauses in the motivation, related work, state restoration, calibration, replay audit and results. Use plain state-source descriptions in the main text. Essential timing disclosures, the negative holdout estimate and its protocol classification, simulated-quantization scope and the common-state extension disclosure remain.
- Consolidated repeated Discussion caveats into three short paragraphs: interpreting the references, evaluating a deployable intervention, and averaging over execution conditions. Kept a concise Conclusion. No experimental values, estimators or analysis rules changed.
- Removed a manual page break. The main text now ends naturally on page 7, with Limitations on page 8; no mostly empty eighth main-text page remains. Total preview: 36 pages. Standard ACL margins and body font sizes are unchanged.
- Rendered and inspected all main-text pages; Table 1 fits one column without clipping. No overfull boxes, undefined references/citations or duplicate-label warnings.
- Numeric audit: 3622 occurrences, the same eight unverified metadata values and 31 absent source paths as the previous local snapshot, zero new unverified values and zero missing required citations. The full metadata-dependent check still needs the cluster files.

The PDF is a local XeLaTeX preview. Rebuild with the production Tectonic toolchain and refresh the anonymous submission copy. GitHub updates do not directly update Overleaf.

## Eight-page main text and graphical Figure 2 — 2026-10-08

At the author's request, the main text uses the full eight-page allowance; Limitations begins on page 9. The new preview totals 37 pages.

- Replaced Figure 2's three text boxes with a full-width native TikZ schematic: Q-history until the first tool-structure mismatch, hash sampling without selecting disagreement, and three action sources on one saved sampled history. Each row connects the selection rule to the question it measures. Earlier agreement refers to tool structure, not exact wording. The illustrated paths are schematic, not new experimental trajectories.
- Kept exact sampling definitions in the method: action kind, tools and normalized arguments define first divergence; wording alone does not qualify. Ordinary indices use a fixed hash before action generation.
- Table 1 stays single-column and now uses the body font size. Full numerical scope details remain in the appendix.
- Expanded Discussion with short explanatory paragraphs on turnover versus net gain, the role of reference interventions, intervention-matched selector targets, oracle interpretation, deployment-distribution value and the purpose of the scope checks. This uses the additional page for interpretation, without restoring the experimental-list format or changing statistical claims.
- Conclusion stays in the main text. No margins or body font sizes were reduced to fit. No data, estimates, intervals, analysis rules or experiment status changed.
- Local XeLaTeX build is clean: no overfull boxes, undefined references/citations or duplicate labels. The final Figure 2 and pages 3, 4, 7, 8 and 9 were rendered and visually inspected; the full main-text preview was rendered.
- Numeric audit: 3622 occurrences, the same eight metadata values unverified due to absent local run files and the same 31 missing source paths. No new unverified values or missing required citations. The cluster is still needed for the full metadata-dependent check.

Rebuild with production Tectonic and regenerate the anonymous submission copy after pulling. This is a GitHub source/PDF synchronization, not a direct Overleaf update.
