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
