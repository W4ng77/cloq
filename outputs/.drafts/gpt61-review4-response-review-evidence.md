# Evidence notes: gpt61-review4-response (2026-10-01 07:40 PDT)

**E1. Recovery q4** (`analysis/recovery/inject_q4/inject.json`), recomputed:
- INV vs VAL with controller B: 4 states improve, 3 worsen (7/30 change). With Q: 2 improve, 2 worsen (4/30).
- 9/30 states change under at least one controller; D_i ≠ 0 in 8/30.
- Process-perturbation vs VAL changes 5/30 under B and 5/30 under Q.
- premature_write: VAL×Q fails in 7/10 states.

All exactly as GPT-6.1 stated. The report's "seldom change outcomes" is wrong.

**E2. Replay check** (`scripts/a6000/inject_driver.py` L248–250): `noop_VALQ` records reward_eq, termination_eq and suffix_eq (suffix sha) only. Prompt and initial-state hashes, budget and per-turn action equality are not separate artifacts. Suffix-sha equality implies the continuation transcript is identical, but the pre-state and budget are not audited. GPT-6.1 is correct.

**E3. Bank U f01 q4, outcome-changing records** (Y_BQ ≠ Y_QQ):

| cell | records | text_only | class talk↔act | tool_name | tool_args | same |
|---|---|---|---|---|---|---|
| AWQ | 18 | 11 | 5 | 1 | 1 | — |
| GPTQ | 20 | 14 | 4 | — | — | 2 |

- The 2 'same' records (c9f6129a9d3fb140, a372a9704ce920bc) have an identical tool call with different accompanying text. They are not nondeterminism; GPT-6.1's reading is correct.

**E4. Duplicates.** GPTQ U2Q ∩ U1 = 20 states (170 unique of 190); AWQ has 0 overlap. Confirmed.

**E5. Telecom cost** (runner logs and `analysis/fork/telecom/q8_gptq_w4_d1/g*`):
- A q8 telecom-dev fork group has 159 divergent states (about 2 blocks × 80 tasks).
- Branching it took 3 shards × median 8.6 GPU-h ≈ 26 GPU-h, plus closed-loop runs (q8 tel bfpair ≈ 2.1–2.2 GPU-h per block, Q ≈ 1.9–3.7).
- ⇒ About 15 GPU-h per 80-task block, or **about 6–8 GPU-h per 34-task holdout cell-block for q8**; q4 is cheaper.
- The "30 GPU-h per q8 holdout block" in report 2 §6 was a main-session overestimate. **K = 12 × 3 cells ≈ 200–300 GPU-h**, not 1,080.
- Inference, ±50%: the divergence rate per block varies.

**E6. W78** (`analysis/fork/out/w67_audit_v2_*.md`): "12/12" = 6 cells × 2 directions. The A→B adjustment conditions on B-half QQ propensity, so it is a retrospective conditional association. The null simulation drew task × block independently, with no shared nonce shocks. GPT-6.1 is correct.

**Sources:** the paths above; GPT-6.1 review 4 text (author relay).
