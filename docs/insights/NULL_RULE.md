**TL;DR**
- Pre-declared null-admission rule (id **NR1**, v1), written 2026-09-29 ~07:15Z, *before* any analysis of the post-W8 frozen snapshot, the q4/q14 null redos, null_n6–n8 or the churn controls. Its sha256 is recorded in every snapshot manifest (`analysis/insights/iter_2/out/snapshot_<utc>.json` `null_rule`).
- Default: the **stratum-matched null S is primary**. The pooled null A becomes primary for a model only if an informative exact test finds no canonical-vs-nonce difference (p > 0.10 on both net and churn).
- Implemented by `analysis/insights/iter_2/n01_null_rule.py` → `out/n01_null_rule.json`. Evidence of the need: `paper/review_v2.md` W-C, `docs/insights/iter_2_conformal.md` §0.

# Null-admission rule NR1 (v1, frozen)

Scope: every run-level test of "cell/family C vs the perturbation null" for model M in iteration 2 and later: c01, k01 churn, n01, the paper's C2.

## NR1-1 Candidates

The null family N(M) consists of runs of the **unmodified reference BF16 checkpoint of M**, served by the a6k2 pipeline, that differ from the reference only by nuisance:
- `a6k2_<M>_bf16`: canonical prompt, compiled numerics;
- `a6k2_<M>_bf16_eager`: canonical prompt, eager numerics;
- `a6k2_<M>_null_n<k>`: nonce-k prompt, compiled numerics.

The following are never admitted:
- Gaussian cells of any k (k = 0.03 only in the labelled sensitivity set B);
- fp32-head runs (E8);
- det pairs (they cover a task subset);
- `*_cal` runs (different tasks);
- legacy `a6000_*` runs (a different numerics flavour, W3);
- fixed-checkpoint controls (`*_q<k>`);
- X1 runs.

## NR1-2 Eligibility

A run is eligible only if both of the following hold:
- It is in the frozen snapshot, i.e. it passes the integrity gate `analysis/insights/iter_2/integrity.py`.
- It has ≥ 77 of the 85 dev tasks scored. `infrastructure_error` episodes count as missing.

No draw is ever removed for its outcome. Only the gate removes draws.

## NR1-3 Strata and nonce disjointness

The null family has two strata:
- **Canonical stratum** K = {bf16, bf16_eager}.
- **Nonce stratum** U = {null_n*}.

For a family that uses nonce set S_C, any nonce null whose nonce is in S_C is removed from that family's reference in null set S. It is the nonce-mate of a family draw, so the pair is not exchangeable.

## NR1-4 Pre-declared exchangeability test (canonical vs nonce)

**Per model.** On the complete-case task set of the eligible null draws:
- **Statistic:** T_net = |mean rate(K) − mean rate(U)| and T_churn = mean_t |ȳ_K(t) − ȳ_U(t)|.
- **Test:** an exact permutation test over all C(n, |K|) relabellings.
- **p-value:** conservative, with ties counted against us.
- **Granularity:** p_min = 1/C(n, |K|).

**Pooled over models.** Stratified permutation, with labels permuted within each model and the statistic averaged over models. Monte Carlo B = 20,000, p = (1 + #)/(B + 1).

## NR1-5 Decision

Null set **A** (both strata pooled) may be primary for model M only if all three conditions hold:
- (a) the per-model test is informative: p_min ≤ 0.10;
- (b) conservative p_net > 0.10 **and** p_churn > 0.10;
- (c) the pooled test also gives p > 0.10 on both statistics.

Otherwise **S** (stratum-matched) is primary and A is reported only as a sensitivity analysis.

The level 0.10 deliberately leans toward rejecting A. Non-rejection is not proof of exchangeability, which is why the default is S.

## NR1-6 Reporting

Each null draw also gets a leave-one-out conformal p against the rest of the null draws, for net and churn. These are reported only and never used to drop draws.

## NR1-7 Versioning

This file is frozen. A change needs a new version (NR1 v2) with a dated rationale, and results under both versions must be reported.
