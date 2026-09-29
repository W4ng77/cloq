**TL;DR** The "disposition" hypothesis is half supported (snapshot 20260929T1937Z, Holm over 5 declared tests).
Three parts survive. (1) Each quantized checkpoint has a reproducible behavioural fingerprint across nonce draws (P2, p_holm 0.001). (2) Checkpoint net effects are over-dispersed relative to independent task landing (P1, p_holm 0.001; W4-only φ 2.5, p 0.017, driven by q4). (3) On q4 an open-loop act-vs-talk logprob contrast predicts the closed-loop tool-call shift beyond dose (P4, partial ρ 0.62, p_holm 0.012; q8/q30a3 do not replicate).
Two parts fail. The fingerprint does not predict which way net success moves (P3, ρ 0.12, p 0.32). Near-tied BF16 fork tokens do not mark fragile tasks (F1, ρ −0.12). So "a fixed fork bias sets the lottery's sign" is not shown.

# Iteration 4: does quantization shift an agent's dispositions? (P1–P4, F1)

Date 2026-09-29. 0 GPU-h. Stable ids: tests **P1, P2, P3, P4, F1** (confirmatory, Holm) and **X1–X6** (exploratory). Proposals are **E4-1 … E4-5**.

Scripts are in `analysis/insights/iter_4/`: `common4.py`, `p1_overdispersion.py`, `p2_dispositions.py`, `p4_openloop_forks.py`, `f1_fragile_forks.py`, `p5_dose_scaling.py` and `h00_holm.py`, driven by `run_all.sh`. Outputs go to `analysis/insights/iter_4/out/<name>_live_20260929T1937Z.{json,log}`.

Snapshot: the gated manifest `analysis/insights/iter_3/out/snapshot_live_20260929T1937Z.json` (same gate as W17). Models: q4, q8, q14, q30a3, q32 (l8 has no runs). Every `trajectory.jsonl` is checked against the manifest's size and mtime.

## Hypothesis under test

The hypothesis has four parts:
- Quantization shifts policy-level dispositions (act vs ask, transfer, which tool) at forks where BF16 is near-tied.
- A checkpoint adds a fixed small bias at these forks. The bias size scales with error size (so it drives λ), and its direction is checkpoint-specific (so the net effect is a lottery, coherent across tasks).
- Fragile tasks are the ones whose trajectories pass near-tied forks.
- Stated falsifiably: P1 is coherence of net effects; P2 is persistence of the behaviour shift; P3 is that the behaviour shift explains the net effect; P4 is that an open-loop fork bias predicts the closed-loop behaviour shift; F1 is that fork near-ties predict fragility.

## Declared family and design

The family is `analysis/insights/iter_4/common4.py` `DECLARED`, and is copied into every output JSON under `_declared`. It was written before any iter-4 statistic was computed.
- P4 was amended once, before any P4 number existed, from a raw Spearman to a partial Spearman given the open-loop flip rate (the dose proxy). That makes it stricter. P1–P3 had already been computed at the time.
- The family is not a pre-registration: the team had seen the W17 numbers.

Design:
- **Units.** Nonce-stratum checkpoints with at least 2 nonce draws: fixed quantizers, E17 controls, NF4/MXFP4/rotations, and Gaussian fixed controls. That gives 20/12/14/7/6 units on q4/q8/q14/q30a3/q32, and 48 units in 10 model × dose-group blocks enter P2/P3.
- **Draws.** Draws A and B are the first two run names in sorted order. The last two are used as a sensitivity check.
- **Dose groups.** floor, small, mid (W5/W8, Gaussian 0.3), W4 (all W4 methods, E17 controls, Gaussian 1), and W3. Checkpoints are compared only within a model × dose group, so dose effects do not count as checkpoint-specific.
- **Null.** NR1 stratum-matched: the nonce null U minus the draw's nonce-mate (`docs/insights/NULL_RULE.md`). Canonical Gaussian cells are compared with K (bf16, bf16_eager).
- **Disposition features.** 12 per trajectory, from `trajectory.jsonl` (`common4.py` docstring): tool_share (the act-vs-talk rate), turns, any/n writes, transfer_to_human, tool-error rate, "not found" error rate (a hallucinated-ID proxy), confirm-before-write, ask rate, first-write position, max_steps and too_many_errors endings. No episode in these runs ends by agent stop, so "premature end" is represented by the two termination features.
- **Tasks are the cluster.** Every permutation null permutes within task (P1), within block (P2/P3), across checkpoints (P4) or across tasks within model (F1).

## Verdicts

| id | prediction | estimate | p (one-sided) | p Holm | verdict |
|---|---|---|---|---|---|
| P1 | checkpoint net Δ is over-dispersed vs independent task landing (pooled, all dose groups) | φ = 4.61 (perm 95% quantile 1.92; 10 blocks, df 38) | 0.0002 | 0.001 | **supported**, but the pooled φ is inflated by the W3 RTN-vs-GPTQ method gap; see X1 |
| P2 | a checkpoint's disposition shift persists across nonce draws and differs from same-dose checkpoints | fingerprint F = 0.44 (perm mean 0.00, q95 0.10; 48 units) | 0.0002 | 0.001 | **supported** |
| P3 | disposition shift (draw A) predicts dose-centred net Δ (draw B), leave-one-block-out ridge | ρ = 0.12 (A→B 0.05, B→A 0.19; perm q95 0.35) | 0.32 | 0.63 | **not supported** |
| P4 | q4: open-loop act-vs-talk contrast s_act predicts the closed-loop tool_share shift, beyond the flip rate | partial ρ = 0.62 (19 cells) | 0.004 | 0.012 | **supported on q4 only** (X5) |
| F1 | tasks with more near-tied BF16 first tokens are more fragile (partial on n decisions) | pooled ρ = −0.12 (per model: q4 −0.21, q8 −0.76, q14 −0.13, q30a3 −0.08, q32 +0.40) | 0.84 | 0.84 | **not supported** (wrong sign on 4 of 5 models) |

evidence: `analysis/insights/iter_4/out/h00_holm_live_20260929T1937Z.json` (written by `h00_holm.py`); sources are listed per row in that file.

## P1: the checkpoint lottery (coherent net effects)

evidence: `analysis/insights/iter_4/out/p1_overdispersion_live_20260929T1937Z.{json,log}` (written by `p1_overdispersion.py`).

Statistic:
- φ = (between-checkpoint variance of net success − nonce variance) / (the same variance expected if every task landed independently, given each task's spread across checkpoints).
- The null permutes checkpoint labels within each task. This keeps each task's turnover and nonce noise and removes cross-task coherence.
- This is the task-level test the brief asked for. A positive cross-task correlation of a checkpoint's break/fix events is exactly what raises φ above 1, so a logistic GLMM was not needed.

| subset (exploratory except "all") | φ | perm q95 | p | df |
|---|---|---|---|---|
| all groups (P1 primary) | 4.61 | 1.92 | 0.0002 | 38 |
| **X1** all except W3 (W3 = RTN vs GPTQ, a method gap) | 2.29 | 1.98 | 0.017 | 35 |
| W4 group | 2.46 | 2.09 | 0.017 | 30 |
| W4 production quantizers only (no E17 controls) | 2.14 | 2.32 | 0.080 | 20 |
| same-method recalibration pairs (GPTQ d1/d2 ×5 models, AWQ d1/d2 ×2) | 4.65 | 3.59 | 0.013 | 7 |
| last-two-draw sensitivity (all groups) | 4.82 | 1.98 | 0.0002 | 38 |

Per model, W4 group (`groups.w4`: J, φ, true between-checkpoint SD vs independent-landing SD):
- q4: J 13, φ 5.59, SD 4.6 pp vs 2.0 pp.
- q8: J 8, φ −0.14, SD 0.
- q14: J 7, φ 1.42, SD 2.7 vs 2.3 pp.
- q30a3: J 4, φ −0.84, SD 0.
- q32: J 3, φ 3.05, SD 3.7 vs 2.1 pp.

On q4 each checkpoint's net Δ reproduces across nonce draws (`models.q4.units`, draw A / draw B): GPTQ-d1 +5.6/+6.8 pp, rot-GPTQ +4.5/+4.5, MXFP4 −1.5/−0.3, GPTQ-d2 −4.0/−5.2, RTN −2.8/−6.4, stochastic-rounding RTN −14.6/−12.2.

Leaving any one W4 checkpoint out keeps the pooled W4 φ in the range 1.60–2.62 (`w4_leave_one_ckpt_out_phi`; the lowest is without q4 rtnsr_w4).

Nonce-null baseline (`models.<m>.null_U_baseline`): prompt nonces are **not** coherent. φ_U is 1.19/0.62/0.63/0.36/0.80 and no p is below 0.31. The coherence is a property of the weights, not of the prompt perturbation.

Reading: a real checkpoint lottery exists, carried by q4 and q32 (q14 weakly). q8 and q30a3 show none at W4. The W3 blocks show large between-checkpoint gaps, but those are RTN vs GPTQ (a method effect), not a lottery.

## P2: dispositions persist per checkpoint

evidence: `analysis/insights/iter_4/out/p2_dispositions_live_20260929T1937Z.{json,log}` (written by `p2_dispositions.py`).

The fingerprint F is the cosine similarity of a checkpoint's two draws' standardised 12-feature shift vectors, minus the cosine with same-block other checkpoints.
- Per model F: q4 0.65, q8 0.27, q14 0.38, q30a3 0.43, q32 0.17.
- Same-checkpoint raw cosine: 0.77/0.69/0.72/0.63/0.45.
- Nonce-null analogue (two U draws' leave-one-out shifts): −0.13 to −0.23.
- W4 production quantizers only: F = 0.53, p = 0.001 (25 units).
- Leaving out any one feature keeps F in the range 0.42–0.51 (`P2.leave_one_feature_out_F`), so no single feature drives it.

**X2** per-feature reliability (`models.<m>.reliability_per_feature`) is the between-checkpoint variance over the variance of one nonce draw. The act-vs-talk rate is the most checkpoint-specific feature: tool_share 17.9 (q4), 7.4 (q8), 55 (q14), 232 (q30a3), 0.7 (q32). Error and not-found rates are also high on q4/q8 (7–64). transfer_to_human is low on q4 (0.08) but 2–4 on q8/q14.

## P3: the fingerprint does not predict the sign of the net effect

evidence: `p2_dispositions_live_20260929T1937Z.json` → `P3`.

- **Declared test.** Cross-fitted ridge, leave-one-block-out: ρ 0.12 (p 0.32). Ridge α 0.1/10/100 gives 0.10/0.15/0.26 (point estimates only). Without dose centring ρ = 0.07.
- **X3, exploratory.** Per feature, centred draw-A shift vs centred draw-B Δ, n = 48, parametric p, ignoring blocks. Turns (ρ −0.53, p 0.0001) and max_steps (−0.48, p 0.0006) track Δ, as do transfer (+0.43, p 0.003), tool_share (+0.38, p 0.009) and confirm-before-write (−0.36, p 0.013). Turns and max_steps are near-restatements of failure (looping), so they are not evidence of a fork bias. That the multivariate model does not transfer across blocks says the link is not a single model-independent direction.
- **Task level.** On null-robust tasks, a task broken in draw B moves along its checkpoint's draw-A direction (over the other tasks) only a little more than along another checkpoint's direction: AUC 0.59 vs 0.54, p 0.12 over 45 units. Fixes: 0.47 vs 0.42, p 0.08.

## P4: open-loop fork bias predicts behaviour on q4

evidence: `analysis/insights/iter_4/out/p4_openloop_forks_live_20260929T1937Z.{json,log}` (written by `p4_openloop_forks.py`).

How it is measured:
- E3 stores only the BF16 token's logprob shift d, not the alternatives' shifts. The fork bias is therefore a contrast: s_act = mean d at first tokens where BF16 started a tool call minus mean d where BF16 started text.
- The E3 decision sample was reconstructed exactly (seed 0, n 400) and verified token by token against the stored margins (`reconstruction_verified`).
- Each .npz input is pinned by its sha256 (`ol_npz_sha256_16`). E3 is not gated, and q30a3 cells were still being written during this run.

Results:
- **q4, 19 cells.** Partial ρ(s_act, closed-loop tool_share shift | flip rate) 0.62 (p 0.004); raw 0.51. Leave-one-cell-out range 0.57–0.67. Restricted to flip ≥ 0.02 (11 cells): 0.82, p 0.002. The flip rate alone correlates negatively with the tool_share shift (ρ −0.56): bigger perturbations talk more, but the direction beyond dose is carried by s_act.
- **X5, q8 (12 cells, only AWQ plus Gaussian; 8 of them have flip < 0.01).** Partial ρ 0.00.
- **X5, q30a3 (7 cells).** Partial ρ 0.15.
- **X5, pooled over the 3 models.** ρ 0.34, p 0.028.
- **Beyond tool_share.** s_act does not predict net Δ (q4 partial 0.29, p 0.12). s_write (write vs read tool-name tokens) does not predict write shifts (q4 −0.25). s_transfer rests on 4 BF16 transfer decisions per sample and is uninformative.

## F1: BF16 near-tied forks do not mark fragile tasks

evidence: `analysis/insights/iter_4/out/f1_fragile_forks_live_20260929T1937Z.{json,log}` (written by `f1_fragile_forks.py`).

- Near-ties are common. BF16 first-token margins below 1 logprob occur in 8–17% of decisions and in 56–93% of tasks (per model, averaged over the null draws; `bf16_fork_ties`). They are 3–6× more frequent at text decisions (13–34%) than at tool-call decisions (3–5%).
- The declared test fails: pooled partial ρ −0.12.
- It is under-powered. Only 11–20 null-robust tasks per model, and selecting on "every nonce draw succeeds" also selects tasks whose ties do not matter.
- **X4 selection check over all tasks.** tie_rate vs nonce-null coin-ness pU(1−pU): pooled ρ 0.05 (p 0.14). tie_rate vs perturbed turnover: −0.04 (p 0.79). Cross-model transfer: mean partial ρ 0.06.
- Neither first-token margin nor all-token tie rate identifies which tasks re-roll. This agrees with W17 / r05: open-loop quantities predict how much, not which tasks.

## X6: how the effect scales with size (exploratory)

evidence: `analysis/insights/iter_4/out/p5_dose_scaling_live_20260929T1937Z.{json,log}` (written by `p5_dose_scaling.py`).

- **Disposition-shift norm vs λ** (λ from W17 r10, same snapshot): Spearman q4 0.64, q8 0.69, q14 0.74, q30a3 0.54, q32 0.70; pooled 0.67. The size of the behaviour shift tracks turnover. That part of the hypothesis is consistent, but both quantities measure "how much changed".
- **Gaussian seeds show no lottery** (canonical cells, one draw per seed, noise included in both terms). Pooled φ by k: 0.001 → 0.22, 0.003 → 0.45, 0.01 → 0.71, 0.03 → 0.62, 0.1 → 1.94 (p 0.08), 0.3 → 2.03 (p 0.07), 1 → 0.43 (p 0.87). At the W4-matched size k = 1, 4 q4 seeds give φ 1.02.
- So the coherent net effect is seen for quantizer checkpoints (W4 φ 2.5, recalibration pairs 4.7) but not for isotropic Gaussian checkpoints of matched size. Two things make this contrast descriptive: the Gaussian cells have 1 draw each and 1–4 df per k, and the difference was not tested.

## What this does to the storyline

- **Adds (C2/C3 reframing).** A quantized checkpoint is a reproducible behavioural variant of the model, not noise. Its behaviour fingerprint persists across prompt nonces (P2), its net effect is a coherent draw rather than a sum of independent task flips on q4/q32 (P1, recalibration pairs φ 4.7), and prompt nonces are not coherent. This supports the "checkpoint lottery" reading of W17 with a test that does not need c to be identified.
- **Does not add.** The mechanism "fixed bias at a few policy forks sets the sign" is not shown. Behaviour fingerprints do not predict the sign of Δ across blocks (P3). Fork near-ties do not predict fragility (F1). The open-loop act-vs-talk bias predicts the act-vs-talk behaviour on q4 (P4) but not Δ.
- **Scope.** P1 is heterogeneous: q8 and q30a3 have no W4 checkpoint variance. P4 rests on q4, because q8/q30a3 lack E3 cells for RTN/GPTQ. All tests have few checkpoints (df 7–38). Features are heuristic (the confirm regex, and "not found" as a hallucinated-ID proxy).
- **Related work.** Quantization-induced behaviour change as reproducible per-checkpoint "flips" and a per-step margin model are already published: Dutta et al. 2024 "Accuracy is not all you need" (https://arxiv.org/abs/2407.09141) and Du et al. 2026 (TMLR, arXiv 2609.26621). New here would be: closed-loop agent coherence (φ vs an independent-landing null), a behavioural fingerprint reproducible across prompt nonces, and the contrast with nonce and Gaussian perturbations. Novelty needs the survey agent's check.

## Cheap data that would decide the inconclusive parts (not queued)

| id | what | decides | cost |
|---|---|---|---|
| E4-1 | E3 open-loop cells for existing checkpoints on q8/q14/q30a3/q32: rtn_w4, gptq_w4_d1/d2, awq_w4(_d2), rtn_w3, gptq_w3, gshape_w4, rtnsign_w4, nf4 (400 decisions, `scripts/a6000/openloop_d.py` unchanged) | P4 beyond q4 (currently q8 has one quantized cell) | no simulator; ~10 min per cell |
| E4-2 | **Fork-alternative open loop**: `openloop_d.py` variant with `prompt_logprobs=20` for the BF16 reference and each cell. Store the top-20 (id, logprob) at the first completion token and at the tool-name token, plus logP(`<tool_call>`) at every decision start of all BF16 decisions (not a 400 sample). Gives the direct act propensity shift Δlogit P(act), and the transfer/write name-token shifts, without the BF16-branch contrast. | P4 with a direct fork measure; P3 (does Δlogit P(act) predict Δ?); per-task fork bias for F1 | no simulator; one prefill per decision |
| E4-3 | R1 recalibration checkpoints GPTQ-W4 d3/d4, AWQ-W4 d3 on q4/q8/q14, 2 nonce draws each (q1/q2) | P1 lottery on the purest contrast (now df 7) | ~2 closed-loop runs per checkpoint |
| E4-4 | Gaussian k=1 fixed controls for seeds s2/s4/s5 on q4/q8 (2 nonce draws each) | quantizer-vs-Gaussian coherence contrast (X6) with the nonce correction | ~6 runs per model |
| E4-5 | R2: the 57 unused calibration tasks for 6–8 existing W4 checkpoints × 2 draws | confirmatory replication of P1/P2 on new tasks | ~16 runs per model |

## Caveats

- The P1 primary pools W3 blocks (a method gap); the lottery claim rests on the exploratory W4 / no-W3 / recalibration rows (p 0.013–0.08).
- Draw A of all checkpoints shares nonces (n1 or q1) and draw B likewise. This cannot create same-checkpoint similarity, but it does share nonce effects across checkpoints.
- P3's per-feature correlations use parametric p and ignore block structure.
- E3 outputs are ungated. q30a3 results changed between two runs of this analysis because a cell was added (7 cells in the final run).

## E4-2 implementation (2026-09-29, W20)

- **Script.** `scripts/a6000/openloop_topk.py` is a sibling of `openloop_d.py`, which is unchanged, so the E3 outputs stay byte-identical. It uses the same decision sample (seed 0, n 400, sorted) and sends one request per decision: prompt + BF16 completion, truncated after the last needed token, with `prompt_logprobs=20`. vLLM 0.29 returns one dict {token_id: {logprob, rank, decoded_token}} per prompt position. It holds the top-20, plus the actual token when that token falls outside them (checked on a live server). `--first-all` also scores the first token of all BF16 decisions (942 on q4) with a `max_tokens=1, logprobs=20` generation.
- **Positions.**
  - *Decision start.* The first completion token. On Qwen3 (hermes), P(act) = P(`<tool_call>`, id 151657) and P(talk) = 1 − P(act). For Llama the script uses `<|python_tag|>` / `{` / `{"`, and for Mistral `[TOOL_CALLS]`.
  - *Tool name.* The tokens that overlap `"name": "<tool>"`, found from tokenizer character spans. This is validated on all 724 q14 BF16 tool calls: the extracted name equals the parsed tool name every time.
- **Contrast.** Served-vs-served. BF16 is its own cell (`topk/bf16`), and every other cell depends on it and is scored against it with `--ref`. The per-cell summary gives:
  - Δlogit P(act), overall and split by BF16 decision type.
  - Binary act KL.
  - Top-k KL(BF16‖cell) and total variation at decision starts and at tool-name tokens.
  - The exact P_cell(BF16's tool name).
  - A prefix-tree estimate of the mass on every tool name, its Δ against BF16, and the name-switch rate.

  The docstring defines each of these, including the approximations.
- **Integrity.**
  - The BF16 cell reproduces the closed-loop first-token logprob of every decision within the 4-decimal rounding of `decisions.jsonl` (max |Δ| 5.0e-5, 400/400 prompt-logprobs, 942/942 generation).
  - `prompt_logprobs` and generation give bit-identical first-token top-20 on all 400 sampled decisions.
  - RTN-W4's first-token flip rate (0.1925) equals its E3 value.
- **Smoke, q4 BF16 vs RTN-W4** (`analysis/openloop/a6k2/q4/topk/{bf16,rtn_w4}.json`):
  - **P(act) at decision starts.** BF16 0.540 and RTN 0.492 (all 942 decisions: Δ −0.028). Where BF16 acts, P(act) falls from 0.956 to 0.831. Where BF16 talks, it rises from 0.016 to 0.065. So RTN mostly blurs act vs talk; it does not simply push toward talk.
  - **Δlogit P(act).** Mean −0.90 (median −0.52): −2.33 at BF16 tool starts and +0.89 at BF16 text starts.
  - **Flips.** The argmax act/talk flips at 11.75% of starts (12.1% of all 942).
  - **KL at starts.** Median 0.009, q90 2.8, mean 0.91 (heavy tail).
  - **Tool names.** Median KL 1e-6, mean 0.19. P(BF16's name) falls from 0.991 to 0.896, and the name-switch rate rises from 0.4% to 10.8%. For example, `modify_pending_order_items` goes to `get…`/`exchange…`, and `find_user_id_by_name_zip` goes to `…_email`.
- **Queue.** 50 tasks `a6k2_<m>_olk_<cell>` at priority −8 (the two smoke tasks ran at −9), generated by `scripts/a6000/make_tasks_e42.py`:

  | model | cells | tasks |
  |---|---|---|
  | q4 | BF16 + 18 | 19 |
  | q8 | BF16 + 16 (no nf4/mxfp4/rot_*: those q8 checkpoints are not built yet) | 17 |
  | q14 | BF16 + rtn_w4, gptq_w4_d1/d2, awq_w4, rtn_w3 | 6 |
  | q32 | BF16 + rtn_w4, gptq_w4_d1/d2, awq_w4, rtn_w3 | 6 |

  To recompute a summary offline: `openloop_topk.py --resummarize <out> --ref <m>/topk/bf16 --model <m>`.
- **Caveats.**
  - Tool-name mass is estimated only down to the level of a tool family. An alternative token such as `update` is split evenly across the `update_*` tools.
  - Alternatives outside the top-20 are invisible.
  - P(act) excludes tool calls that start with text (about 1% of BF16 tool decisions start with a text token).
