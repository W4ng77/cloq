**TL;DR** Storyline v7, 2026-10-01, after GPT-6.1 reviews 3–4 and W76–W86.
- **Question:** quantization changes an agent's local actions. How do those changes become task consequences through the subsequent closed-loop execution?
- **Answer, in three evidence layers:**
  1. **Two-sided consequence atlas.** Same-state forks show that W4 turns 15–21% of task × block units into rescue or damage while net success stays flat. Consequential flips concentrate in fragile tasks whose direction replicates across nonces; the confirmation is pre-registered on a protected holdout.
  2. **Shared-state attribution.** On ordinary, outcome-independent states (Bank U), most consequential differences are full-message language differences, not tool or argument differences. Different quantizers flip the same states.
  3. **Controlled defect intervention plus a process audit.** Injected local defects produce heterogeneous two-sided turnover that is not separable from generic trajectory perturbation. Local defects and final failure do not correspond one-to-one.
- **Withdrawn:** W×KV interaction (pre-registered replication not supported), static precision restoration, success equivalence, and "defects are absorbed".

# Storyline v7: Tracing the Consequences of Quantization in Closed-Loop Agents

Supersedes `STORYLINE_v6.md`. Venue: ARR October → NAACL. Evidence freeze 10-05; submission 10-12.

## 1. Problem and gap

- **Accuracy-style evaluation of quantized LLM agents** reports end-task success. In τ²-bench, BFCL multi-turn and ALFWorld, W4/KV8 success is roughly flat (W4 G within ±3 pp), and that average looks like "safe to quantize".
- **Closest work: *Flat Score, Amplified Failures* (arXiv 2607.27275).** It shows flat scores hide failure amplification, with error-budget masking. It works at the episode level and does not separate the action from the continuation.
- **Our gap:** a flat average can hide (a) offsetting rescues and damages, and (b) a dependence of consequences on *which* state and *which* controller continues. Neither is visible without same-state counterfactuals.

## 2. Method: the same-state four-branch fork

- **Setup:** at the first semantic divergence between BF16 (B) and quantized (Q) agents, replay the identical state and swap {current action} × {continuation controller}, giving four branches: BB, BQ, QB and QQ.
- **Signed estimands:**
  - r = P(Y_BQ = 1, Y_QQ = 0) and d = P(Y_BQ = 0, Y_QQ = 1);
  - M = r + d (outcome turnover) and G = r − d (net);
  - A/C/I decomposition and 16 outcome patterns.
- **Inference:**
  - primary: fixed task pool, one statistic per complete shared block, block bootstrap or t over blocks;
  - secondary: crossed task × block bootstrap;
  - complete-block rule, a split guard, and replay gates with per-state no-op checks.

## 3. Evidence layer 1: the two-sided consequence atlas (main result)

**Coverage:**
- q4/q8 (Qwen3-4B/8B) × RTN/GPTQ/AWQ at W4/W3;
- QuaRot W4A4 and KV4, KV8, W2 stress;
- τ² retail/airline/telecom-dev, BFCL multi-turn and ALFWorld.

**Main numbers** (W70/W78, 85 tasks × 20 complete blocks):
- **W4:** M = 15.5–20.9%, while every G is within ±3 pp (q8 GPTQ +2.9 [+1.4, +4.4] on the fixed pool; it covers 0 when crossed).
- **KV8:** M = 6.5–8.1%.
- **External benchmarks:** M = 7–25%, with G covering 0 except BFCL q4 AWQ.

**Concentration** (W67 → W78, exploratory, dev):
- Flips concentrate in fragile tasks (dispersion 4–9× the binomial null).
- Per-task direction persists across independent nonce blocks.
- That holds as a retrospective conditional association beyond measured baselines (QQ propensity, BF16 success, trajectory length) in 6 configurations × 2 directions, carried by retail.
- Different quantizers flip the same tasks, but with near-random relative direction.

**Confirmation** (pre-registered, `PREREG_FORK_CONFIRM.md`, frozen before any holdout run): telecom holdout, 34 unseen tasks × 12 blocks × 3 cells.
- Primary: G_all with ±3 pp decision bounds.
- Secondaries: r/d/M, and cross-nonce repeatability of task fragility on the new tasks.

## 4. Evidence layer 2: shared-state attribution (second pillar, primary)

**Bank U** (W81/W84): ordinary Q states sampled independently of outcome. Sub-banks: U1 (Q's own history), U2B (BF16-sourced) and U2Q (Q-sourced), plus a common continuation controller Q0.
- **Consequence rates:**
  - per-state M is about 8–12% for q4 W4 and 0–5% for q8 and KV8;
  - G covers 0.
- **Which differences matter:**
  - About 71% of the outcome-changing differences are same-structure text differences (talk vs talk). Only 5 of 58 involve a different tool or arguments.
  - Simple content features (question, confirmation request, claimed action, new entity) are not associated with flips. A length difference is weakly associated in q4 only.
- **Cross-quantizer:** pairs of q4 cells flip on the same U2B state 7× vs ≈1.4 expected, 6 of 7 in the same direction, with different Q actions. That is state fragility, not shared action.
- **Q0 common continuation:** on the same states, under the same controller, the quantizers' actions are compared directly. Small n at f01; f02/f03 are queued.

**Claim to be tested at f01–f03:** the consequence of a local difference depends on the state source, on the full language action and on the continuation controller, and fragility transfers across quantizers at the state level.

## 5. Evidence layer 3: controlled intervention and process audit

**Recovery intervention** (W76/W83, q4; q8 running):
- **Design:** 30 frozen ordinary states. At each, inject {wrong_id, wrong_tool, premature_write} × {INVALID, VALID, process-perturbation} × {B, Q}. Every state passes the full replay audit (22 fields).
- **Turnover:** INV vs VAL is B 4 up / 3 down and Q 2/2. Process perturbation vs VAL is 3/2 under both controllers.
- **Net effects:** D = +0.03 [−0.17, +0.27]. INV − PP is about 0 under both controllers.
- **Reading:** heterogeneous two-sided turnover, no detected mean controller difference, and the error-specific effect is not separable from generic perturbation.
- **Manipulation checks:** wrong_tool mostly creates argument errors, and premature_write is mostly failure → failure.

**Process audit** (Table 4, W79/W82; LLM-annotated by Sonnet 5.5, labelled as such, mechanical fields verified programmatically):
- Local defects and final failure do not correspond one-to-one.
- Some successful continuations contain later corrections (damage group: 10/20).
- Failing branches differ by *wrong* changes (`unintended_or_unconsented_change`; it overlaps the DB outcome by construction) and by loops, not by executing more writes.

## 6. Contributions as they would appear in the paper

1. A same-state four-branch counterfactual protocol for closed-loop agents, with signed consequence estimands and block-level inference.
2. A multi-axis atlas: quantization causes large two-sided turnover hidden by flat success, concentrated in fragile, quantizer-shared tasks. This part is confirmed on a pre-registered holdout.
3. Shared-state evidence that consequences live mostly in full language actions and in the continuation, together with a controlled intervention and process audit that bound the "local defect → failure" story.

## 7. What is not claimed

Success equivalence (TOST fails); a W×KV interaction; static precision restoration as a method; "errors are absorbed"; human annotation (the labels are LLM); real speed or memory savings (quantization is simulated).

## 8. Open risks

- **The holdout may not confirm.** Then the atlas stays exploratory, and the paper still reports the protocol and the dev atlas honestly.
- **Bank U may stay small-n and underpowered** for controller attribution.
- **Model scale is limited:** Qwen3 4B/8B, plus q14 if it finishes. The second family is best effort.
- **Novelty vs Flat Score** rests on the same-state attribution and confirmation, not on "flat average hides failures" alone.
