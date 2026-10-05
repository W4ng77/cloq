# Appendix revision: evidence for the argument

This editorial revision starts from CLOQ `84f1e16f80623f36255402857c5dc0fc2d852677` (paper sources unchanged from `5182066`). It changes the presentation of the existing evidence, without changing the protocols, admission rules, estimators, raw outcomes or primary decisions. The working research history remains in the repository.

## The argument readers should remember

The paper distinguishes three questions: how sensitive an outcome is to an action replacement, what signed task value a specific precision intervention provides, and what extra value higher precision adds over a same-precision replacement. These questions require different measurements.

The evidence connects them in three steps:

1. Paired action, continuation and joint replacements reveal rescues and damages that an average score hides. Joint rescues and rescues undone show why evaluating only one intervention misses part of its consequences.
2. A second checkpoint at the same bit width also produces substantial two-sided turnover. The common-state comparison then asks the sharper question of extra BF16 action value; its unresolved intervals remain visible.
3. Numerical fidelity is strongly associated with action differences. Its relationship to the consequences of a difference is weaker, and enriching changed outcomes has not yet established a net-beneficial upgrade rule.

This is the paper's contribution to evaluation. It does not require treating every completed engineering line as a separate finding, or interpreting an unresolved contrast as equivalence.

## Supplement structure

The compiled supplement now has seven evidence sections:

- **Evaluation contract and scope:** state restoration, endpoints, sampled replay acceptance, population coverage and the distinct end-to-end comparison.
- **Which upgrade changes the task?** Complete paired consequences, interval families and outcome-class interpretation.
- **What does higher precision add?** Same-precision references, their limits, and the common-state comparison.
- **From numerical fidelity to task value:** all primary method contrasts, complete ordinary-state upgrade intervals, the fidelity decomposition, controlled error dose and the frozen trigger.
- **Where do the consequences persist?** Ordinary state sources, alternative simulator controls, complete Mistral mode intervals, external environments and task-level replication scope.
- **Independent telecom confirmation:** frozen primary and secondary readings, all registered stratum families, replay audit and structural-missingness sensitivity.
- **Boundaries of a local-defect explanation:** compact injection results, manipulation failures and unsupported claims.

Nine existing full numeric tables retain their original entries. Two compact tables add all G/H/F intervals for the eleven q8 configurations and both Mistral configurations, so that statements about unresolved value have complete evidence. These are displays of existing outputs, not new experiments.

## What was removed from the compiled paper

Repeated G/H/F and off-diagonal forests, pooled 3-by-3 plots, repeated same-precision plots and the second-simulator interaction plot were removed. Existing main figures and the retained numeric evidence carry the argument.

The independent-state p-values and one-way ICC estimate were dropped. Text-regex associations, small token subgroups, naive co-flip references and the small Q0 exploratory panel were dropped. They did not support a central conclusion.

The long recovery and LLM annotation displays were removed. Recovery now has one compact error-minus-process table with its wide intervals and manipulation failures. Process annotations remain in the research release, but are not used as paper evidence for a mechanism.

The restoration matrix, old high-scale failure inventory and research-log-style unfinished-arm enumeration were removed from the paper. A brief restoration boundary and parser/budget-specific low-bit stress observations remain. Full analysis outputs and historical corrections are preserved.

Duplicate related-work details were removed from the supplement; the primary references and the methodological distinction remain in the main related-work section.

## Necessary main-text adjustments

Pointers to deleted figures now lead to the relevant evidence section. Mistral has its own population anchor. No effect estimate was changed.

The error-dose heading and discussion now describe trajectory divergence and end-to-end success, the quantities actually measured. The cross-cell paragraph that treated cache and weight configurations as a single decreasing-bit-width axis was removed; its numeric evidence remains in the consequence tables. The separate KIVI coverage sentence was removed from the KL diagnostic's reasoning chain.

## Checks and integration

- Active input/reference traversal finds no unresolved or duplicate labels, and no pending result placeholders.
- Nine retained table bodies match the starting manuscript exactly.
- All 78 newly displayed q8/Mistral G/H/F intervals match the two committed analysis reports, in source and column order.
- Two independent source reviews checked primary decisions, missing-data amendments, populations and scope. Visual review found float barriers producing half-empty pages; they were removed.
- The local XeLaTeX preview has 24 pages, compared with the retrieved 30-page source PDF. Main text ends on page 8 and Limitations begins on page 9. There are no undefined references/citations or overfull boxes.
- The local environment lacks `inconsolata.sty`; the preview loads the installed Inconsolata fonts through a temporary loader, while retaining the original Times font family. That loader is not a repository change. Rebuild with the normal Overleaf/cluster font package before final delivery.
- Full `check_numbers.py` must be run in the complete research checkout, which has the referenced result files and cluster-only metadata. The removed process-label table is no longer listed as a required paper source. No full-repository numeric PASS is claimed from this partial checkout.

The revision is isolated for review because other sessions are working on the new duration panel. Merge/cherry-pick only after checking concurrent paper changes. The duration panel is not touched here. If it supplies a resolved, interpretable result, place it under the existing question about the value of a specified intervention; avoid adding another independent storyline.
