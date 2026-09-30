**TL;DR** Status on 2026-09-30, 14:30 PDT, for *Tracing the Consequences of Quantization in Closed-Loop Agents* (ARR Oct → NAACL; evidence freeze 10-05). Written for external review (GPT-6.1).

**Established**
- **The fork instrument works.** The same-state 2×2 fork passes a bit-exact replay gate on τ², ALFWorld and BFCL. No-op samples are 752/752 on τ².
- **Success is equivalent at W4.** On retail and airline, pooled GPTQ-W4 minus BF16 success is 0.0 pp [−1.3, +1.3]; non-inferiority and TOST both pass at ε = 3 pp.
- **W4 divergence is not consequential.** 75–87% of tasks diverge from BF16, yet the fork effect G_all ≈ 0 on all three benchmarks.

**Emerging**
- Harm appears only when components are combined: KV4 together with A4 or W4 costs about 9–11 pp on q4.
- No evidence that harm compounds with the remaining horizon.

**Open**
- Whether real damage can be rescued. This was re-targeted today from GPTQ-W3, which turned out barely damaged, to RTN-W3 (−17 to −22 pp). Those results are expected overnight.

All numbers below are development-set and exploratory unless marked otherwise. The telecom holdout (34 tasks) is untouched; its pre-registration will be frozen on 10-03.

> **Revision 1 (2026-09-30 15:00 PDT, after the GPT-6.1 review of 7528f2e).** The wording below overstates three things.
> - **"Not consequential"** should read: a sizeable share of pivot actions change the outcome, in both directions. Rescue is about 9% and new damage about 9% of divergent units, so roughly 18% (about 15% of all units) flip outcome, and the average cancels them. New headline quantities r, d, M = r + d and G = r − d are being computed on a common denominator.
> - **"Success is equivalent"** holds only for the mixture of calibration draws d1–d4. The forks use d1, where q4 GPTQ is +5.7 pp. A checkpoint-aligned NI analysis is being added.
> - **"Harm needs combined axes"** is not identified. The KV16 cells had online Q/K rotation off, so the KV axis changed rotation and quantization together. Four matched rotated-KV16 cells are queued. Separately, RTN-W3 alone is heavily damaged.
>
> Also being fixed:
> - The fork bootstrap resampled blocks within tasks, which breaks the shared-nonce structure. It is moving to complete-block inference, plus crossed task × block inference for generalisation to new tasks.
> - The pivot "policy value" is an oracle proxy, not an end-to-end policy.
> - The +12.3 pp on q4 KV4 is Y_BB − Y_QQ, an oracle intervention.
> - ALFWorld's W4 interval [−9.7, +1.9] shows no detected net effect; it does not show an effect near zero.
>
> Result files are now committed (`analysis/RESULTS_INDEX.md`, 4f5cd63). The corrected numbers will appear in STATUS_20261001.

# CLOQ status for external review (2026-09-30 evening)

Repo: `W4ng77/cloq` (private). Earlier context: `docs/REVIEW_PACKET.md`, `docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md` (the plan agreed with GPT-6.1), `docs/EXECUTION_PLAN_20260930.md`. Every result in this file cites the file it comes from. The index of changes is `docs/RESEARCH_LOG.md`, entries W29–W61.

## 0. What changed since the last review round

| Item | Status | Where |
|---|---|---|
| Fork engineering gate (τ²) | **PASS**, deterministic protocol A chosen on 09-30, a day ahead of the 10-01 decision point | `docs/insights/FORK_PROTOCOL.md` §8, `analysis/fork/gate/`, W30/W42 |
| Development forks, W4 (q4/q8 × GPTQ/AWQ × 20 blocks × 85 tasks) | mostly done | `analysis/fork/out/dev_all_20260930T202228Z.md` |
| KV8 and stress forks (GPTQ-W3, KV4-rot) | done or running | same file |
| Forks on ALFWorld and BFCL multi-turn (no LLM user) | gate **PASS**; dev forks mostly done | `docs/insights/REPLAY_ACCEPTANCE_ext.md`, `analysis/fork/out/ext_20260930T202237Z.md`, W39-extfork/W51 |
| Activation line: A8 → SmoothQuant W8A8 → QuaRot W4A4KV4 (fake quantization, validated against official code) | all 6 acceptance checks pass on q4, and on q8 for QuaRot | `docs/insights/METHOD_FIDELITY.md`, W45/W47 |
| W×A×KV 2³ closed-loop matrix, q4 | 9 of 10 cells done | `analysis/ahook/out/wakv_*.md` |
| Restoration / residual-dose checkpoints (`restore`, `resid`, `restore_recal`) | built, unit-tested, running | `docs/insights/PERTURBATION_PROTOCOL.md`, W39-pert/W50/W54/W60 |
| Pivot detection and pivot-time module screening | detection done; screening running | `analysis/fork/out/pivot_*.md`, FORK_PROTOCOL §13, W55/W61 |
| Difficulty / horizon moderators | exploratory analysis done; M1–M5 drafted for the holdout prereg | `analysis/fork/out/difficulty_*.md`, FORK_PROTOCOL §12, W52 |
| External closed-loop evals (BFCL 788 items, ALFWorld 134 games; q4/q8/q14/q30a3/q32 × methods) | 77 done | W37/W38 |

Infrastructure incidents on 09-30 (none affects data validity):
- node003 rebooted unexpectedly (W56).
- Cluster-wide NFS stalls, 08:40–12:10, which caused server-start timeouts. Affected tasks were requeued and resumed (W56–W59).
- Several harness fixes, each logged in the research log:
  - user-simulator ToolCall errors are labelled `user_sim_error` rather than outage (W41);
  - the integrity snapshot now covers telecom (W44);
  - a sign convention error in the external fork A/C/I, found and fixed before use (W51).

## 1. Estimands (unchanged from the agreed plan)

For each task × block where the quantized agent Q first diverges semantically from BF16 (B) at decision t*, we replay the exact state and run four branches:

| branch | action at t* | continuation |
|---|---|---|
| BB | BF16 | BF16 |
| BQ | BF16 | Q |
| QB | Q | BF16 |
| QQ | Q | Q |

With L = 1 − Y on the loss scale:
- **G = Y_BQ − Y_QQ** (the effect of the pivot action itself)
- **A = L_QB − L_BB**
- **C = L_BQ − L_BB**
- **I = L_QQ − L_QB − L_BQ + L_BB**

**G_all is the primary endpoint.** It is taken over the full task pool, with non-divergent units counted as 0, and g_min = ε = 3 pp. Intervals come from a hierarchical bootstrap over tasks, then blocks within task (B = 2000, seed 20261001). A 10% QQ no-op replay sample runs in every task, and any mismatch quarantines that task's output.

Endpoints added today:
- the escalate-after-divergence value, Y_QB − Y_QQ = C + I;
- Y_BB − Y_QQ = A + C + I.

## 2. Results

### 2.1 Success equivalence (paper §3), confirmatory-style NI/TOST on development blocks

Source: `analysis/insights/iter_4/out/success_ni_REAL_20260930T0541Z.json`.
- Pooled across models:
  - GPTQ-W4 − BF16 = **0.0 pp [−1.3, +1.3]**, NI and TOST pass at 3 pp.
  - AWQ-W4 = +1.5 pp, pass.
- Per checkpoint, however, the difference swings with the calibration draw:
  - q4 GPTQ-W4: d1 = +5.7 [3.1, 8.4], d2 = −4.2 [−8.4, 0.0].
  - q4 AWQ-W4: d1 = +3.3, d2 = −4.0.
  - q8 is tighter: GPTQ-W4 d1 = −0.5, AWQ-W4 d1 = −0.9, both pass TOST.
- About 27% of task × block units flip outcome between Q and BF16.

### 2.2 τ² same-state forks (paper Table 2)

Source: `analysis/fork/out/dev_all_20260930T202228Z.md`. No-op sample 752/752; 0 quarantined.

| cell | divergent / units | G_all (pp, 95%) |
|---|---|---|
| q4 AWQ-W4 | 1438 / 1699 | −0.3 [−5.6, +4.9] |
| q4 GPTQ-W4 d1 | 1102 / 1700 | −1.9 [−6.7, +2.7] |
| q8 AWQ-W4 | 1627 / 1765 | +0.5 [−4.4, +5.8] |
| q8 GPTQ-W4 d1 | 1264 / 1491 | +3.0 [−2.8, +9.1] |
| **W4 pooled (equal weight)** | about 82% divergent | **+0.3 [−2.3, +2.9]** |
| q4 KV8 | 593 / 1870 | −0.3 [−3.1, +2.2] |
| q8 KV8 | 641 / 1552 | +0.2 [−2.3, +2.9] |
| q4 GPTQ-W3 (stress) | 232 / 255 | −1.2 [−10.8, +8.4] |
| q4 KV4 + Hadamard (stress) | 233 / 255 | +4.7 [−4.0, +13.6] |
| q8 KV4 + Hadamard (stress) | 238 / 254 | +3.1 [−6.1, +12.8] |

- **W4:** rescue and new damage are about 9% each among divergent units, so they cancel. A, C and I intervals all span 0; the pooled W4 A is −2.4 [−6.5, +1.6].
- **KV8 vs W4:** KV8 diverges in about 30–40% of units, versus 65–90% for W4. Rescue/damage for KV8 is about 2.7% / 2.8%.
- **Tentative mechanism lead:** on q4 GPTQ-W4, act→talk divergences are net harmful: 43 damage vs 20 rescue, G|type −14 pp [−35, +7]. Not significant yet.

### 2.3 Same forks without an LLM user simulator (external validity)

Source: `analysis/fork/out/ext_20260930T202237Z.md`. The gate passed on both environments (`REPLAY_ACCEPTANCE_ext.md`).

| env | W4 pooled G_all | W4 divergence rate |
|---|---|---|
| τ² | +0.3 [−2.3, +2.9] | 82% |
| ALFWorld (134 unseen games, q8) | −3.7 [−9.7, +1.9] | 87% |
| BFCL multi-turn (788 items) | −1.1 [−2.8, +0.7] | 75% |

Per-cell notes:
- BFCL q4 AWQ-W4 is the only W4 cell whose interval excludes 0: −3.6 [−6.6, −0.5].
- ALFWorld q8 AWQ-W4: A −0.7 [−9.0, +7.5], **C +7.5 [−0.7, +15.7]** (harm in the continuation, borderline), I −3.0.

### 2.4 W × A × KV (q4, QuaRot-rotated, dev blocks f01–f03, paired to BF16)

Source: `analysis/ahook/out/wakv_*.md`. BF16 = 33.7 on these blocks.

| cell | success − BF16 (pp) |
|---|---|
| W16 A16 KV16 (rotated control) | +2.7 |
| KV4 only | +3.9 |
| A4 only | −2.4 |
| W4 only (QuaRot-GPTQ) | +4.7 |
| **A4 + KV4** | **−10.6 [−26.6, +3.5]** |
| **W4 + KV4** | **−9.0 [−18.4, 0.0]** |
| A8 | +2.4 |
| SmoothQuant W8A8 | +3.1 |
| W4A4KV4 | running |

Reading: no single 4-bit axis hurts alone, but KV4 combined with another 4-bit axis does. The factorial interaction estimates follow once the last cell lands. Caveat: GPTQ-W4 d1 scores +10.2 on these same blocks, so absolute success on 3 blocks is noisy, and the paired differences are what matters.

### 2.5 Compounding / difficulty (exploratory)

Source: `analysis/fork/out/difficulty_*.md`.
- The slope of C on remaining horizon (pp per 10 decisions) is non-significant in all 8 cells, ranging from −3.7 to +0.2 (p ≥ 0.36).
- Difficulty and task-length strata all cover 0.
- On telecom dev, q8 AWQ-W4 Q − BF16 (official reward) is −2.7 pp overall (BF16 − Q = +2.7 [−2.9, +9.2]) and −7.3 pp on Hard persona (BF16 − Q = +7.3 [−2.6, +19.0]); both intervals cover 0. The whole gap sits in blocks f04–f06; f01–f03 show none.
- M1 (C-slope > 0, one-sided) through M5 are drafted for the holdout prereg (FORK_PROTOCOL §12).

### 2.6 Can the damage be rescued? (in progress; this is the open question)

**(a) Pivot detectability** (`analysis/fork/out/pivot_*.md`)
- AUROC of Q's own uncertainty (−first-token margin; min-margin and logprob variants 0.66–0.73) for "this decision is the first divergence" is **0.60–0.71**.
- Escalating 10% of decisions to BF16 catches 16–39% of pivots; escalating 20% catches 30–51%.
- The value of those policies covers 0 in every cell.
- One exception: q4 KV4-rot Y_BB − Y_QQ = **+12.3 pp [+3.4, +22.2]**. Switching fully to BF16 from the pivot rescues real damage there.

**(b) Static module restoration.** Closed-loop runs, arms paired with Q and BF16 on the same nonces (`analysis/fork/out/restore_eval_20260930T205529Z.md`). Arms:
- BF16 restored in the early / middle / late layer thirds, attention, MLP;
- byte-matched random controls, 3 seeds;
- residual dose W_α = W + α(W_Q − W).

| regime | finding |
|---|---|
| W4 (q4 GPTQ-W4 d1) | This is the equivalence regime; Q beats BF16 here (43.9 vs 33.7). Restoration moves outcomes toward BF16, not upward. At the action level, agreement with BF16 tracks the dose monotonically: prefix agreement 0.24 / 0.42 / 0.50 / 0.57 for α = 2 / 1 / 0.5 / 0.25. Outcome turnover is not closed by any arm. |
| GPTQ-W3 (q4, q8) | **Turned out barely damaged.** q4: Q 36.1 vs BF16 35.7. q8: Q 26.7 vs BF16 30.6 (BF16 − Q = +3.9 [−5.5, +13.7]). All 17 arms plus 8 `restore_recal` arms land within noise. **No rescue signal is possible here.** |
| **RTN-W3 (q4, q8)** | **The real damage regime**, re-targeted today: q4 13.5 vs 35.7, q8 13.3 vs 30.6. RTN has no inter-layer compensation, so plain restoration is exact (see (c)). 34 tasks are queued in two waves; the first wave (structured arms, seed-1 random controls, α = 0.5) runs at top priority. **Results expected overnight.** |

**(c) Inter-layer compensation (raised by the author).**
- GPTQ and AWQ in our pipeline are true-sequential: each layer is calibrated on inputs from the already-quantized upstream layers.
- A post-hoc swap of some modules back to BF16 therefore mis-matches downstream compensation.
- We added `restore_recal`: keep the modules in BF16 and **re-run the sequential calibration for all remaining modules**. Tests confirm keep = ∅ gives Q bit-exactly and keep = all gives BF16.
- On q4 GPTQ-W3, recal − plain differences are small and within noise, as expected in a regime with no damage.
- RTN-W3 avoids the issue entirely.

**(d) Pivot-time localisation (FORK_PROTOCOL §13; amendment 1 committed at 0f26f7d before any W3 selection statistic existed).**
- At about 150 frozen pivot states per cell, each restoration arm makes one decision. We measure the reversion-to-BF16 rate against the byte-matched random arm.
- Pre-declared selection rule: Δ ≥ 5 pp and a one-sided lower bound > 0, pooled over RTN-W3 q4 and q8. It picks at most 2 arms.
- The chosen arms are then run as forks "arm at t*, then Q", against QQ and BQ.
- Amendment 1 moved the selection population from GPTQ-W3 to RTN-W3, for the reason in (b). It is disclosed in the protocol, together with the fact that q4 GPTQ-W3 pivot output files existed on disk but were never opened.

## 3. Deviations and caveats to scrutinise

1. **The damage regime was chosen after seeing closed-loop success.** We moved from GPTQ-W3 to RTN-W3 because GPTQ-W3 showed no damage in success. This is outcome-dependent selection of where to test rescue, though not of the rescue result itself. We will report both regimes and state the order of events.
2. **Telecom restoration uses all 6 dev blocks** (f01–f06), not only the damaged f04–f06, to avoid selecting on the outcome.
3. **W4 success equivalence is population-level only.** Individual checkpoints swing by ±4–6 pp with the calibration draw.
4. **Small models.** Most results are Qwen3-4B/8B. q14/q30a3/q32 appear only in external closed-loop evals so far.
5. **Fake quantization throughout** (QDQ in BF16). The activation and QuaRot paths were checked against official code, with deviations listed in METHOD_FIDELITY.
6. **BFCL long_context overflow is scored as failure** in every arm, and the overflow rate is reported. The ALFWorld prompt went through 5 revisions on dev only; disclosed.

## 4. Remaining schedule

| when | what |
|---|---|
| overnight 09-30 → 10-01 | RTN-W3 restoration wave 1; RTN-W3 stress forks; pivot-arm screening; last W×A×KV cell; telecom dev forks |
| 10-01 | summary of the RTN-W3 rescue result; pivot-time fork (step 3) if the selection rule fires |
| 10-02 | automatic event extraction plus LLM labels; **human blinded review** (~80 states, ~20 double-coded) |
| 10-03 | freeze `PREREG_FORK_CONFIRM.md` (G_all primary; M1–M5 moderators; escalation value C + I as a pre-registered secondary); start the telecom holdout |
| 10-05 | evidence freeze |

## 5. Questions for the reviewer

1. **Framing.** At W4, divergence is frequent (75–87%) but its net effect G_all is about 0 on three benchmarks, and there is no compounding. Is "divergence is common but not consequential at W4; harm needs combined 4-bit axes (KV4 × A4/W4)" a strong enough main claim for NAACL main? Or should the paper lead with the W×A×KV interaction?
2. **Damage-regime choice.** Is moving the rescue test to RTN-W3 defensible, given that GPTQ-W3 shows no closed-loop damage? Should we also add AWQ-W3, which currently has no closed-loop runs and would cost about 20 GPU-h, as a second calibrated method in the damage regime?
3. **If static restoration fails on RTN-W3 but pivot-time full BF16 (Y_BB − Y_QQ) succeeds**, as the q4 KV4 +12.3 pp hints, is "escalate precision after the first divergence" a publishable deployment claim, given that pivot detection AUROC is only 0.60–0.71?
4. **The holdout prereg primary.** Should the telecom holdout primary stay G_all, or should the escalation value (C + I) or Y_BB − Y_QQ be co-primary in the stress cells?
5. **Anything in §3 that would sink the paper**, or that must be fixed before 10-05?
