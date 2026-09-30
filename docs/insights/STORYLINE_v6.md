**TL;DR** Two candidate storylines after the pre-registered confirmation (W25, 2026-09-30). Line A, the "checkpoint
lottery", was the v5-review recommendation: same quantization method, different calibration draw, different net
success. The pre-registered test on new checkpoints refuted it (H1, H2 not supported). Line B, "success-equivalent,
behaviourally distinct", is what the confirmed evidence supports. W4 quantization is equivalent to BF16 in task
success within nonce noise, but it re-rolls which tasks succeed above a numerics floor and leaves a persistent
behavioural fingerprint (H3 confirmed). The fingerprint is generic to fixed weight perturbations, not specific to
quantizers. Line B is the current proposal. Its open problem is showing that the behavioural change matters.

> **Status 2026-09-30: both lines retired as main lines.** Line A was refuted by pre-registration; Line B lost both ends after W29 (success equivalence untested, no W4 fingerprint detected). Current main line: consequences and sources of quantized action divergence on identical histories; see `docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md` (Round 2).

# Storyline v6: two lines

## Line A: checkpoint lottery (refuted, kept for the record)
- **Claim:** net success depends on the calibration draw more than on the method, so single-checkpoint quantizer comparisons are a lottery.
- **Exploratory basis:** q4 GPTQ-W4 d1 vs d2 differed by +9.6 pp [1.8, 17.4]. Recalibration-pair overdispersion φ was 4.65 (df 7). Checkpoint SD exceeded method SD in net Δ (W17, W18).
- **Pre-registered test** (`docs/insights/PREREG_iter4.md`, 14 new checkpoints × 2 nonces on q4/q8, run once on snapshot 20260930T0044Z):
  - **H1** (φ_RECAL > 1): φ 0.40, p 0.74. Not supported.
  - **H2** (net Δ replicates across nonces): r 0.42, p_holm 0.42. Not supported.
  - The new q4 recalibrations d3/d4 all land at net +1.5 to +3.9 pp.
  - With d1–d4 pooled, q4 checkpoint SD is 3.65 pp, nonce SD 2.51 pp and method SD 0.
- **Verdict:** the d1 vs d2 gap did not replicate; the pre-registration stopped us from publishing it.

## Line B: success-equivalent, behaviourally distinct (proposed)
One sentence: *W4 quantization of an LLM agent passes every success-based equivalence check, yet it is a different
agent. It re-rolls which tasks succeed and shifts how the agent acts, and aggregate success cannot see this.*

| Claim | Evidence | Status |
|---|---|---|
| B1 Success-equivalence: GPTQ/AWQ-W4 net Δ is small and stable (q4 ≈ +2 pp, q8 ≈ 0); method and checkpoint effects are not distinguishable from nonce noise on new checkpoints | W25 (prereg H1/H2 null + estimates), W17 R4 | confirmed null / estimates; ε-equivalence test to be run |
| B2 Turnover above the numerics floor: W4 re-rolls outcomes beyond rotation/serving/tiny-noise floors (pooled excess λ RTN +0.19, GPTQ +0.15, AWQ +0.16) | W17 (`r10_turnover_stats`) | established (Holm) |
| B3 Persistent behavioural fingerprint: a fixed checkpoint's behaviour shift replicates on disjoint task halves under a different nonce (F_split 0.26, p_holm 0.0024; q4 0.19, q8 0.33) | W25 H3 | confirmed (pre-registered) |
| B4 The fingerprint is generic to fixed weight perturbations: size-matched random checkpoints are at least as persistent (same-checkpoint cosine RAND 0.51/0.77 vs quantizers 0.32/0.38) | W25 secondary, W18 | descriptive |
| B5 What changes: act-vs-talk propensity is blurred (q4 RTN-W4: P(act | BF16 acted) 0.956 → 0.831, P(act | BF16 talked) 0.016 → 0.065); tool-name switches 0.4% → 10.8%; breaks concentrate on writes, argument errors and hallucinated IDs | W20 (E4-2 smoke), iter_3 r03/r07 | q4 smoke; E4-2 across 49 cells queued/running |
| B6 Damage regime: W3 and plain KV INT4/INT3 lose success (RTN-W3 −16.7 pp q8, −14.5 pp q14) | W13/W14, iter_3 r07 | established |
| B7 (open) Does the behavioural change matter? Candidates computable from existing data: pass^k reliability across nonce draws, policy violations and extra/unsafe write calls, conversation length and cost, a stricter grader (all assertions, not db_match) | — | to do (no GPU) |

Role of conformal/exchangeability testing in Line B (load-bearing): one instrument, two outcome spaces, opposite
verdicts.
- **Success vector vs the nonce-stratum null:** exchangeable, so accept ε-equivalence with a finite-sample guarantee.
- **Behaviour vector vs the null:** not exchangeable, so reject.

That contrast is the thesis. Theory needed: stratified/weighted exchangeability, and a hierarchical checkpoint → nonce → task structure.

Contributions (Line B):
- **C1 Protocol:** evaluate a quantized agent against its own perturbation null on both success and behaviour. Includes the two-level exchangeability test, power, and a reporting checklist.
- **C2 Finding:** success equivalence coexists with turnover above the floor and a persistent behavioural fingerprint (B1–B4). The null on success is confirmed by pre-registration.
- **C3 Characterisation:** what changes (B5), when it becomes damage (B6), and whether it matters (B7).
- **C4 Diagnostic:** the open-loop act-vs-talk and tool-name probe (E4-2) measures the fingerprint without the simulator. Needs cross-model confirmation.

Risks:
- Reviewers may call B1 "quantization is fine, known".
- B3/B4 may read as "any perturbation changes behaviour, obvious".
- B7 may show the behavioural change is harmless.

Mitigation:
- Make B7 the deciding analysis.
- Position against flip / behaviour-fingerprinting / model-equality work (Dutta 2024, AgentProv, Stability Monitor, model equality testing) by being closed-loop, null-referenced and pre-registered.

## Correction (2026-09-30, W29; `docs/insights/METHODOLOGY_REVISION.md`)
- **B3 withdrawn as worded.** The pre-registered H3 permutation used pairing-dependent scaling; under exchangeable data it rejects 33–42% at α = 0.05. Corrected (pairing-invariant scale, calibrated about 0.044):
  - pooled F 0.136, p 0.013 (post-hoc);
  - quantizer recalibrations (RECAL) only 0.025, p 0.30 (not detected);
  - random checkpoints (RAND) only 0.283, p 0.028 (the minimum attainable).

  Wording now: fixed random weight perturbations leave a persistent behavioural fingerprint (post-hoc corrected test); for W4 quantizer recalibrations a fingerprint was not detected.
- **B4:** random ≥ quantizer persistence, post-hoc.
- **B5 largely a selection effect.** The conditional act/talk shift is matched by a sign-symmetric null (q4 RTN-W4 P(act | BF16 talked) 0.014 → 0.088 vs null 0.080). Unconditional ΔP(act) runs from −0.10 to +0.005 on q4/q8, and random controls move it as much or more.
- **Variance:** "method ≈ 0" becomes "method not estimable" (1 df). Crossed components in signed SD, pp:

  | Model | Checkpoint | Residual | Nonce |
  |---|---|---|---|
  | q4 | 3.69 | 2.62 | −0.86 |
  | q8 | 1.24 | 2.61 | 1.26 |

  The H1 p-value is unchanged (0.744) because the nonce term is invariant under relabelling.
- **B1 still untested** (paired BF16 runs pending). The new-task interval is about ±4 pp, so 3 pp equivalence for new tasks is unlikely with 85 tasks.
