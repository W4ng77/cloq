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

## Deliver the mode-comparison promise and simplify the reference display — 2026-10-09

This revision follows the author's storyline → figures → tables review. It changes presentation, not the frozen experimental analyses. Local preview: main text ends on page 8, Limitations starts on page 9; 36 pages total.

- Figure 3 now has a separate panel for W4 and KV8 divergent-state pooled G/H/F, with new-task 95% intervals. The development/holdout panels retain full-pool G_all and their original intervals. The caption and method explicitly distinguish the denominators. Main text reports W4 G/H/F (+0.5/+0.2/+0.7 pp) and the observed 4.0% joint-rescue / 4.8% rescue-undone shares, without claiming enrichment.
- Figure 3 uses blue rescues and hatched orange damages. Both action-only panels have turnover columns. The holdout panel prominently labels its 90% interval; all diamonds are visible solid marks, with primary/pooled rows bold.
- Figure 4 paired turnover differences consistently mean BF16 minus reference. The key-order contrast is displayed as +2.3 [-2.9, +8.4] pp, exactly the sign reversal of the original -2.3 [-8.4, +2.9]; the analysis output itself is untouched. Rate rows and difference rows have a separator.
- Figure 4 common-state panel shows the two-look block-t 97% component only. Companion bootstrap and unadjusted intervals remain in the supplement, as does the rule requiring both interval families. Neither the joint reading nor its timing limitations were changed. All descriptions now identify the 510 states as ordinary BF16-sourced Qwen3-8B histories, with GPTQ-W4 substitutes.
- Figure 2 is shorter and points to the sections each sampling design serves. Figure 5 corrects the negative damage tick. No random-selection interval was invented from p-values: it continues to display the matched-count expectation and exact tests.
- Removed the two repetitive opening Discussion paragraphs, renamed the mode paragraph, shortened the abstract and aligned result headings with the three introduction questions. The holdout consistently has a negative estimate in this tested setting, an inconclusive frozen category because the negative category was omitted, and no identified cause or general domain-transfer mechanism.
- Table 1 is a true one-column booktabs table: setting, state population, action-only turnover and task-value reading. F is called joint replacement, not continuation takeover. The duplicated appendix scope-overview table is removed; full scope evidence remains in its per-setting subsections.
- Fixed-pool and new-task G/H/F intervals now share two-line cells. All old point estimates, state counts, pattern summaries and both interval sets were mechanically compared and preserved. A JSON-backed generator makes the tables reproducible. The coverage matrix uses controlled line breaks; the detailed reference table no longer embeds its full timeline inside cells.
- Appendix figures now complement the main figures: Figure 6 shows permutation-reference contrasts only; Figure 7 retains W3, continuation-dependent shares and the complete common-state interval display. Removed revision-history titles and the repeated development/holdout and main reference panels. Appendix float queues are flushed between claim-specific sections, so tables stay with their evidence.

Validation: all figure-source assertions pass; no overfull boxes, undefined references/citations or duplicate labels in the final local XeLaTeX build. Rendered and inspected revised main figures, relevant main pages and supplementary tables/figures. Numeric audit: 3688 occurrences; the same eight pre-existing metadata values remain locally unverified, with 31 absent source paths and no missing required citations. There are no added unverified values. The complete metadata-dependent check still requires the cluster.

After pulling, rebuild with production Tectonic, run the complete numeric check and regenerate the anonymous submission copy. The source/PDF mirror is synchronized to GitHub; this is not a direct Overleaf update.

## 2026-10-09: combined overview and final opinion audit

Figure 1 and the former Figure 2 are now one full-width figure: the left panel retains the action-by-continuation matrix and verified airline example; the right panel condenses first-divergence, ordinary sampling, and common-state comparisons. The independent sampling float was removed and all figure references renumber automatically. The state-selection source remains as an input to Figure 1.

Reviewed every main figure at rendered page size. Retained the previous revision's G/H/F main-text panel, distinct full-pool and divergent-state denominators, prominent holdout 90% label, consistent BF16-minus-reference contrasts, separate difference rows, and a single displayed two-look interval. The trigger retains two parallel panels because capture and net value are different quantities; no random reference interval was invented from p-values. Oracle counts remain separate from the net-gain axis. No experimental estimate, test or inference rule changed.

Readability edits remove repeated qualifications in Discussion and clarify that the own-first-divergence selection limitation belongs to the same-precision panel, not to the adjacent key-order experiment. Essential scope and adaptive-analysis disclosures are retained.

Local XeLaTeX preview: main text ends on page 8; Limitations begins on page 9. Rendered overview, all main results figures and final main page checked for overlap and clipping. No overfull boxes or undefined references. The production Tectonic build must still be run on the submission environment. Numeric audit is compared with the existing missing-metadata baseline; this workspace cannot certify the cluster-only metadata.

## 2026-10-09: substantive eighth-page fill and claim-linked supplement

Promoted two findings from the supplement to strengthen the main argument. Result 1 now distinguishes repeatable task fragility from signed benefit: the top 20% of tasks selected on one prompt half carry 41.0% of turnover on the other half, while neither group has a resolved new-task net gain. Discussion explains the fidelity diagnostic through action-change frequency and consequences conditional on a change; it reports the exploratory KL association and conditional AUCs without claiming a causal mechanism. Result 3 links to this explanation. The Conclusion stays complete on page 8. No margin, font or spacing tricks were used to create the fill.

The supplement has six claim-specific sections: measurement/replay; consequences/patterns/fragility; holdout/full replay; precision references/common states; selection/fidelity; scope. A short guide maps each section to its main-text purpose. Evidence provenance is part of measurement setup rather than a separate final section. Removed an unused action-taxonomy table, redundant text-composition reporting, duplicated rate/interval prose, and repeated audit chronology. Complete primary comparison families, null results, simulator-control limitations, conditional populations and adaptive-analysis timelines remain available.

Local XeLaTeX preview is 34 pages (previous preview: 36), with main text ending on page 8 and Limitations beginning on page 9. Revised main pages and appendix layouts were rendered for visual checks; the build has no overfull boxes or undefined references. Numeric audit: 3569 occurrences, seven pre-existing metadata-dependent values locally unverified, 28 absent source paths, and zero uncited/missing required sources. Newly promoted numbers are checked against the committed fragility and KL reports. The full checker still requires cluster metadata, and the submission must be rebuilt with production Tectonic and the anonymous copy regenerated.

## 2026-10-09: story-first revision and scope pruning

This revision responds to the request to make the five-minute argument clear: an outcome flip does not establish a need for precision; fallback must be evaluated by its signed task benefit.

The main evidence chain is now (1) paired rescues and damages, including the negative telecom holdout; (2) same-bit and operation-preserving references, followed by the direct common-state value comparison; (3) the frozen margin rule tested on both capture and net gain. Results sections open with the finding rather than protocol status. The holdout's negative estimate is prominent in the abstract and Result 1, while its frozen inconclusive classification and missing negative category are retained. The replay and pre-registration rationale is one measurement paragraph; detailed checks remain in the claim-linked appendices. Main-text model aliases are replaced by model names.

The main figures display new-task 95% intervals and the registered holdout 90% intervals. The key-order reference retains its original conservative 95% interval (the wider of block and crossed intervals); its definition is explicit in the caption. Fixed-pool intervals and the common-state two-look 97% intervals remain in the supplement, with their original decisions unchanged. The direct common-state comparison stays in the argument as unresolved, with no equivalence claim.

Scope is selected by research question, not by favourable outcomes. The detailed KL decomposition, auxiliary KL selector comparison, extended outcome-class taxonomy, and the independent quantizer-ranking comparison family are removed from the compiled submission as whole analyses. Their original records remain in repository history and the analysis outputs. All four main W4 configurations, all three upgrade modes, both reference interventions, the direct common-state comparison, every tested frozen-trigger rate, holdout secondaries and sensitivity checks remain. The scope appendix retains every admitted ordinary-state mode effect, including nulls and path controls, and the external-environment and Mistral comparisons. It retains simulator-control limitations and adaptive-analysis timelines. The main scope table now focuses on environments, a second family and the selected lower-bit illustration rather than method ranking.

The Discussion explains the evaluation target, how references constrain attribution, why a selector must predict signed benefit, and the distinction between realised conditional outcomes and expected deployment benefit. It does not claim that precision has no value or that the reference interventions estimate a universal noise floor. The selected RTN-W3 example retains its selection disclosure.

Verification: local XeLaTeX preview, 32 pages total; Conclusion ends on page 8 and Limitations starts on page 9. All eight main pages were rendered and inspected, as were the affected supplementary figures/tables. No overfull boxes or undefined references/citations. Figure generators executed their existing source-value assertions. Numeric audit: 3196 occurrences, the same seven metadata-dependent unverified values and 28 missing paths as the pre-edit snapshot, zero missing required sources. This local snapshot cannot provide a complete metadata-dependent PASS; rerun the unchanged checker on the cluster. No outcome values, estimators, admission rules or frozen readings were modified. The Replay Gap bibliography venue was corrected to its stated COLM Efficient Reasoning Workshop acceptance.

The checked PDF is a local XeLaTeX preview. Rebuild with production Tectonic and refresh the anonymous submission copy before upload. Publishing to the paper GitHub mirror does not directly update Overleaf.

## 2026-10-09: match the actual Overleaf compiler and fill the eighth page

The author supplied the Overleaf-compiled PDF. Its producer is pdfTeX, not the XeLaTeX preview previously used here. The main text did end on page 8, but the right column ended well above the bottom; the previous claim did not establish that the page was filled. A local pdfLaTeX build reproduced the uploaded PDF's line count and final-page layout before editing.

Expanded the argument, without adding experiments or numerical claims: the negative single-action estimate concerns a hybrid policy; the reference interventions test attribution rather than provide a subtractable noise floor; and turnover versus net gain assigns different signs to damaging interventions. The final pdfLaTeX preview has 32 pages, with the Conclusion complete near the bottom of page 8's right column and Limitations starting on page 9. No font-size, margin or line-spacing changes. No overfull boxes or undefined references. All eight main pages were rendered for inspection. No estimates, populations or test decisions changed; the pre-existing metadata-dependent numeric gate remains a cluster task.

Use the Overleaf/pdfLaTeX build as the pagination reference for this revision. The checked-in local PDF is now built with pdfLaTeX. GitHub mirror publication still does not directly pull changes into Overleaf.
