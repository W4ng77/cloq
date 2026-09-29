**TL;DR** Storyline v5 (2026-09-29), after the Feynman review of v4 (`paper/review_storyline_v4.md`, 2.5/5), the R3
statistics (`docs/insights/iter_3_stats_R3.md`, W17) and the disposition analysis (`docs/insights/iter_4_disposition.md`,
W18). Claim: a quantized LLM agent is not the original agent plus noise, it is a *different, reproducible agent*.
Random perturbations of the same size (prompt nonces, Gaussian weight noise) and sampling re-roll task outcomes
independently; a quantized checkpoint shifts them coherently, with a persistent behavioural fingerprint. The
conformal/permutation test against the model's own perturbation null is the instrument that separates the two.
Status: parts established (marked), the decisive tests are queued (W19, W20).

# Storyline v5

Working title: *A Quantized Agent Is a Different Agent: Separating Re-Roll Noise from Behavioural Change in Closed-Loop LLM Agents*

## Motivation
- Quantization is how agents get deployed (W4/W8, AWQ/GPTQ/FP8/NF4). Its evaluation practice is inherited from
  single-turn benchmarks: one quantized run vs one BF16 run, aggregate accuracy, "within 1 pp = lossless".
- In closed-loop agents this practice has no reference: any perturbation above the decision-tie floor re-rolls
  trajectories, and one BF16 run is itself one draw (v0 false positive: +12 pp, p=0.02 → −3.5 pp on replication).
- So two questions are conflated: (a) how much does quantization re-roll outcomes, and (b) does it make the agent a
  different agent (systematic, reproducible change) or only a re-rolled copy of the same agent? Aggregate success
  cannot tell them apart; "unchanged success" is compatible with both.

## Findings chain
| # | Finding | Status | Evidence |
|---|---|---|---|
| F1 | W4 turnover exceeds the numerics floor (rot_bf16, canonical BF16, k≤0.003): pooled excess RTN +0.19 [0.10, 0.30], GPTQ +0.15, AWQ +0.16 (Holm p ≤ 0.036); largest on small models | established (5 models) | W17, `r10_turnover_stats_live_20260929T1937Z.json` |
| F2 | RTN re-rolls no more than random-sign error of its own magnitude (non-inferiority, Holm p=0.038); other matched-random controls point the same way but n.s. | partly established | W17 |
| F3 | A checkpoint's behavioural fingerprint (act-vs-talk share, turns, transfers, tool errors…) persists across prompt nonces and differs between same-dose checkpoints: F=0.44, perm p=0.001, 48 checkpoints | established | W18, `iter_4/out/p2_*` |
| F4 | A checkpoint's net effect is coherent (overdispersed vs independent task landing): W4 φ 5.6 on q4, 3.1 on q32, ~1 on q8/q30a3; prompt nonces φ 0.36–1.19 (not coherent); same-method recalibration pairs φ 4.65 (df 7); q4 GPTQ d1 vs d2 net +9.6 pp [1.8, 17.4] | established on q4/q32, model-dependent | W17, W18 |
| F5 | Matched-size Gaussian seeds show no coherence (φ 0.43 at k=1) → structure decides *coherence*, size decides *turnover* | hypothesis (1 draw per seed) | W18; decisive test E4-4 queued |
| F6 | Sampling (BF16, T>0) behaves like nonce re-rolls, not like a checkpoint: independent landing, no fingerprint | hypothesis | sampling baseline S queued (W19) |
| F7 | The open-loop act-vs-talk logit contrast predicts a checkpoint's closed-loop fingerprint (q4 partial ρ 0.62, Holm p=0.012), but not its net Δ | q4 only | W18; E4-1/E4-2 queued for q8/q14/q30a3/q32 |
| — | Dropped from v4: "c follows method" (unidentified), "20–40% / 5–10×" (wrong denominator), "λ follows size, not structure" as equality (r08 contradicts), p̄-prediction (no leverage), open-loop predicts λ beyond dose (partial ρ 0.39) | dropped | W17, review |

## Contributions
| # | Contribution | Rests on |
|---|---|---|
| C1 | **Protocol**: evaluate a quantized agent against the model's own perturbation null with a stratified permutation/conformal test at two levels: task outcomes (is this checkpoint's outcome vector exchangeable with null draws? ε-equivalence) and checkpoint identity (are repeated draws of a checkpoint exchangeable with draws of other checkpoints and of the null?). Includes power/MDE and a reporting checklist | F1, F3, F4 |
| C2 | **Finding**: a quantized agent is a distinct, reproducible behavioural variant, not noise: coherent net effect and persistent fingerprint, unlike prompt nonces (and, if E4-4/S confirm, unlike matched Gaussian noise and sampling) | F3–F6 |
| C3 | **Consequence**: single-checkpoint quantizer comparisons conflate method with checkpoint identity (recalibration moves net success by ~10 pp on q4); report checkpoints × nonces, not one run | F4 |
| C4 | **Cheap diagnostic**: an open-loop act-vs-talk probe on BF16 contexts predicts the direction of a checkpoint's behavioural shift without the simulator (if E4-1/E4-2 extend beyond q4) | F7 |

## Role of conformal inference
Not branding; it is the formal instrument for the paper's central distinction.
1. Level 1 (task outcomes): conformal p-value of a quantized run's outcome vector among the nonce-stratum null draws
   (canonical vs nonce not exchangeable, p=0.0099, so the test is stratified); ε-inversion gives the largest shift the
   data cannot rule out; Holm across statistics; per-model e-values. Finite-sample valid with 6–9 null draws.
2. Level 2 (checkpoint identity): "noise" = draws of a checkpoint are exchangeable with draws from the model's own
   perturbation distribution (nonce, Gaussian seed, sampling seed); "variant" = within-checkpoint draws are
   exchangeable with each other but not with the null. F3/F4 are permutation tests of exactly this hypothesis;
   stating them as conformal/exchangeability tests gives validity with few checkpoints and draws.
3. Theory asked of the collaborator: validity under stratified/weighted exchangeability (nonce stratum), a
   hierarchical (checkpoint → nonce draw → task) exchangeability test with few units per level, and power with
   85 tasks.

## Risks and fallbacks
- F5/F6 fail (Gaussian or sampling also coherent) → C2 becomes "any fixed weight perturbation is a variant; prompt
  nonces and sampling are not", still new but weaker on "structure".
- Coherence only on q4/q32 → report as model-dependent with the φ table; C2 scoped.
- Llama unusable → Qwen3-only, stated in Limitations.
- Held-out confirmation: the 57 calibration-split tasks are contaminated for calibrated methods (their trajectories
  feed GPTQ/AWQ calibration); a clean confirmatory split is still open.
