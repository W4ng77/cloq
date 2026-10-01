**TL;DR** Status on 2026-09-30, 18:30 PDT. It supersedes `STATUS_20260930_evening.md` and incorporates the GPT-6.1 review of 7528f2e. A new analysis (W67) explains *why* W4's average effect on task success is about zero. About 15–21% of task × block units have a pivot action that flips the outcome. Those flips sit in a small set of **fragile tasks**, and each fragile task flips **in a consistent direction** across 20 independent nonces. The average cancels **systematic, opposite-sign task-level effects**, not random noise. GPTQ, AWQ and KV8 all flip the same units, so fragility belongs to the state; the direction is specific to the quantizer.
- **Dropped:** the static precision-restoration line. Restoring bits trivially helps, and no arm is competitive with GPTQ-W4 at matched storage.
- **Corrected:** statistics, checkpoint alignment, the holdout guard, and the W×A×KV rotation confound.

# CLOQ status (2026-09-30 night)

Branch `master`. The result files are listed in `analysis/RESULTS_INDEX.md`. Change log: `docs/RESEARCH_LOG.md`, W56–W67.

## 1. What the paper claims now

**Title:** *Tracing the Consequences of Quantization in Closed-Loop Agents.*

1. **Two-sided consequences** (fork, primary). At the first point where the quantized agent Q's action diverges from BF16 (B), we replay the identical state and swap the action. Let r = P(B's action rescues the episode) and d = P(it newly damages it), over all units.
   - **W4 pooled:** r 9.7%, d 9.0%. So M = r + d = **18.7%** of all units have an outcome-changing pivot action, while G = r − d = +0.6 pp [−0.4, +1.7] (fixed task pool; crossed [−2.2, +3.4]).
   - **KV8:** M = 7.3%.
   - **ALFWorld and BFCL** (no LLM user): M = 7–25%, and every G interval covers 0 except BFCL q4 AWQ, which is −3.6 [−6.6, −0.5].
2. **The cancellation is between tasks, not noise (new, W67; §2).** That explains why "aggregate success is unchanged" coexists with frequent consequential divergence.
3. **Success under W4 shows no detected loss but is not equivalent.** Checkpoint-aligned d1:
   - q4 GPTQ +4.2, q4 AWQ +0.9, q8 GPTQ −0.2, q8 AWQ +1.2;
   - the pool is +1.5 [−2.7, +5.6] (crossed);
   - NI at 3 pp passes in several cells and pools, but TOST fails everywhere under task resampling (`success_ni_ALIGNED_20260930T213009Z`).
4. **Secondary, pending: a W × KV interaction among QuaRot-rotated 4-bit axes.** The q4 matched rotated-KV16 controls are running. The q8 replication is pre-registered (`docs/insights/WAKV_PREREG.md`, 27a3802).

## 2. New analysis (W67): where consequential divergences come from

Script: `analysis/fork/analyze_consequence.py` (exploratory, dev split, the same admitted complete-block units as analyze_dev). Output: `analysis/fork/out/consequence_20261001T011124Z.json`. The permutation and binomial nulls use B = 2000.

### 2.1 Consequences concentrate in fragile tasks

Per-task M across blocks against a binomial null at the pooled rate:

| cell | M | dispersion index (null ≈ 1) | p | share of flips in the top 20% of tasks | tasks never flipping |
|---|---|---|---|---|---|
| q4 AWQ-W4 | 20.0% | 6.5 | <0.001 | 57% | 32 / 85 |
| q4 GPTQ-W4 | 15.5% | 6.4 | <0.001 | 65% | 37 / 85 |
| q8 AWQ-W4 | 20.0% | 4.5 | <0.001 | 87% | 97 / 165 |
| q8 GPTQ-W4 | 17.2% | 5.1 | <0.001 | 88% | 100 / 165 |
| q4 KV8 | 6.5% | 4.1 | <0.001 | 71% | 47 / 85 |
| q8 KV8 | 8.1% | 4.1 | <0.001 | 66% | 38 / 85 |

### 2.2 Fragile tasks flip in a consistent direction

Among tasks with at least 2 flips over the 20 blocks:
- **Fewer tasks show both directions than a null that redistributes rescue/damage labels at the pooled ratio**: 22–27 observed versus 32–41 expected; p < 0.001 in all four W4 cells, p ≈ 0.02 for KV8.
- 68–86% of all rescues occur in net-rescue tasks, and 72–84% of all damages in net-damage tasks.
- Each block uses a different nonce, so a different BF16 run, user-simulator seed and Q run. This is reproducibility across 20 independent replications of the same task.
- **Implication:** the near-zero average is a sum of task-level effects of opposite sign. The measured "quantization effect on success" therefore depends on benchmark composition: which fragile tasks are included. That is also a candidate explanation for the ±4–6 pp checkpoint-to-checkpoint swings seen earlier: different calibration draws may flip different fragile tasks. This is to be tested next (§4).

### 2.3 Different quantizers flip the same states, in different directions

Same task × block (same nonce and same BF16 run), comparing whether two cells both have an outcome-changing pivot. The null permutes tasks within blocks.

| pair | P(flip in b \| flip in a) | P(flip in b) | lift | φ (null 95%) | same direction given both |
|---|---|---|---|---|---|
| q4 GPTQ-W4 ~ AWQ-W4 | 0.33 | 0.20 | 1.6 | 0.14 (0.05) | 0.61 |
| q8 GPTQ-W4 ~ AWQ-W4 | 0.34 | 0.20 | 1.7 | 0.16 (0.04) | 0.47 |
| q4 GPTQ-W4 ~ KV8 | 0.14 | 0.07 | 2.1 | 0.12 (0.04) | 0.81 |
| q8 AWQ-W4 ~ KV8 | 0.14 | 0.08 | 1.7 | 0.11 (0.04) | 0.42 |
| q4 ~ q8, AWQ-W4 (different models!) | 0.36 | 0.21 | 1.7 | 0.19 (0.04) | 0.53 |
| q4 ~ q8, GPTQ-W4 | 0.20 | 0.18 | 1.1 | 0.02 (0.04) | — |

- **Where** a consequential pivot happens is shared across quantizers: weight vs KV, GPTQ vs AWQ, and for AWQ even across model sizes. So fragility is a property of the state.
- **The direction** given that both cells flip is close to a coin toss (0.42–0.61; 0.81 for q4 GPTQ ~ KV8 on 36 units).

### 2.4 Position

Pooled over the four W4 cells, the share of divergent units whose pivot changes the outcome is:

| t* (decision index of the first divergence) | 0 | 1–2 | 3–6 | ≥7 |
|---|---|---|---|---|
| M given divergence | 21% | **29%** | 21% | 11% |

Early pivots matter most. Very late pivots rarely change the outcome.

### 2.5 What this does *not* show yet

- No **content** description of the fragile states yet. Next step: automatic event extraction plus LLM labels plus the human blinded review of about 80 states, stratified into fragile/robust tasks and rescue/damage. This becomes Table 4 of the paper.
- Task-level direction consistency is shown within a quantizer cell. Whether the *same* fragile tasks drive the checkpoint lottery across calibration draws (d1–d4) is untested.
- All of this is exploratory on the dev split. The telecom holdout prereg will include r, d and M plus a pre-registered fragility test (§4).

## 3. What was corrected after the GPT-6.1 review

| issue | fix | commit / log |
|---|---|---|
| The bootstrap resampled blocks inside tasks, breaking the shared-nonce structure | Primary: per complete block, then infer over blocks (block bootstrap with ≥10 blocks, otherwise t). Secondary: crossed task × block. Every analysis recomputed. | 00ffdb5, W63 |
| Headline was G only | r, d, M and G on one denominator, plus conditional versions | W63 |
| NI averaged the d1–d4 checkpoints while the forks use d1 | Checkpoint-aligned NI on the fork units, with joint resampling across models | 51cc6d2, W64 |
| Holdout could leak into dev analyses | `manifests/fork/splits_v1.json`; dev mode aborts on holdout units unless the prereg is frozen; coverage table per cell | W63 |
| W×A×KV: KV16 cells had rotation off | 4 matched rotated-KV16 cells (running); proper paired interaction contrasts; q8 replication pre-registered | W65, W66, 27a3802 |
| +12.3 pp on q4 KV4 was called an escalation effect | Relabelled as the oracle intervention Y_BB − Y_QQ; the threshold "policy value" is an oracle proxy only; an end-to-end design is written (FORK_PROTOCOL §14), not run | W63 |
| Prereg scope | G_all is the only primary; r/d/M secondary; C + I is the stress escalation endpoint; M1 is exploratory; confirmatory strata use fork-time information only | FORK_PROTOCOL §12, b8519e6 |
| Result files missing on GitHub (404) | Committed; index in `analysis/RESULTS_INDEX.md` | 4f5cd63 |

## 4. Dropped, and why

**Static precision restoration** (BF16 in layer thirds / attention / MLP, byte-matched random controls, residual dose α, the `restore_recal` variant). The line is paused: 56 + 22 queued tasks were moved to the lowest priority.
- In the only damaged regime (RTN-W3), the gains are just "more bits": α = 0.5 recovers 92% of the gap and a *random* MLP subset recovers 76%.
- No arm is competitive at matched storage. A restored RTN-W3 arm sits at 7–13 bits/param and is still below GPTQ-W4 at 4.2 bits/param.
- At W4 there is nothing to recover. GPTQ-W3 turned out barely damaged.
- One sentence stays in the paper because it bears on the main claim: at W4, moving behaviour toward BF16 (action-prefix agreement rises monotonically as α shrinks: 0.24 → 0.42 → 0.50 → 0.57) does not move task success toward BF16. Behavioural closeness to the reference is not task improvement.

## 5. Next steps

| priority | work | why |
|---|---|---|
| 1 | Characterise fragile states: event extraction, LLM labels, ~80 human-blinded states stratified fragile/robust × rescue/damage | What makes a decision point consequential is the mechanism contribution (Table 4) |
| 2 | Does task fragility explain the checkpoint lottery? Relate per-task flips under d1 to the success differences across d1–d4 on the closed-loop runs (CPU) | Could unify the earlier "lottery" observation with the fork finding |
| 3 | Pre-register a fragility/direction test for the telecom holdout: the dev-defined fragile-task score predicts holdout flips; tasks keep their direction across blocks | Converts §2 from exploratory to confirmatory |
| 4 | W×A×KV q4 matched contrasts, then the pre-registered q8 replication | Secondary claim |
| 5 | Model scale: W4 forks on q14 (needs q14 dev blocks first) | Reviewers will ask about model size |
