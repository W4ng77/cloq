**TL;DR** Entry point for an external reviewer (updated 2026-09-30). This repo measures what weight quantization does
to closed-loop LLM agents (τ²-bench, Qwen3 4B–32B), judged against the model's own perturbation noise rather than a
single BF16 run. A pre-registered test on new checkpoints (W25) REFUTED the "checkpoint lottery" storyline (Line A),
and CONFIRMED that fixed checkpoints carry a persistent behavioural fingerprint. The evidence now supports Line B:
W4 quantization is success-equivalent but behaviourally distinct (turnover above a numerics floor, persistent
fingerprint), and the fingerprint is generic to fixed weight perturbations. We ask for critique and better ideas on
the storyline, methodology and statistics (§8). Target: ARR October 2026 (NAACL), 8 pages, experiments freeze
2026-10-05, submission 2026-10-12.

# Review packet: quantization and closed-loop LLM agents

Read this file first; every claim below points to the file that backs it. Numbers are from the integrity-gated
snapshot `analysis/insights/iter_3/out/snapshot_live_20260929T1937Z.json` unless marked otherwise. The project log,
newest first, is `docs/RESEARCH_LOG.md` (entries W1–W25, V*). The two storylines are in `docs/insights/STORYLINE_v6.md`.

## 1. Question and motivation

Quantization (W8/W4/W3, GPTQ, AWQ, FP8, NF4, …) is how LLM agents get deployed. Its evaluation practice comes from
single-turn benchmarks: compare one quantized run with one BF16 run on aggregate accuracy, and call it lossless if
they are within about 1 pp. That practice has no reference in closed-loop agents (multi-turn tool use against a
simulated user):

- Any perturbation above the decision-tie floor changes the trajectory. Even serving numerics alone (kernel
  reduction order) flip about 1/4 of task outcomes.
- One BF16 run is itself one draw. Our own v0 result shows the danger: quantized minus BF16 was +12 pp (p=0.02), and
  it became −3.5 pp on replication.
- "Unchanged success" can therefore hide large changes in which tasks succeed.

The paper asks what quantization actually does to an agent, measured against the model's own re-roll noise:

- How much does it re-roll outcomes?
- Is the change systematic (a different agent) or a re-rolled copy of the same agent?
- Can the effect be predicted cheaply, without running the closed loop?

## 2. Setup

| Item | Value | Where |
|---|---|---|
| Benchmark | τ²-bench retail + airline: 85 development tasks (58 retail + 27 airline, the `evaluation` split of `manifests/task_split_v0.json`). 22 BF16-unstable tasks excluded; 57 calibration tasks feed GPTQ/AWQ calibration | `manifests/task_split_v0.json`, `configs/frozen_v1.json` |
| Agent models | Qwen3-4B-Instruct-2507 (q4), Qwen3-8B (q8), Qwen3-14B (q14), Qwen3-30B-A3B-2507 (q30a3), Qwen3-32B (q32); Llama-3.1-8B-Instruct (l8) queued but weak on this benchmark | `scripts/a6000/models.json` |
| User simulator | Qwen3-30B-A3B, greedy, TP=2, one per node | `scripts/a6000/noderunner.py` |
| Decoding | greedy (T=0), 32k context | `configs/frozen_v0.json` generation_agent |
| Serving | vLLM 0.29 with batch-invariant kernels (`VLLM_BATCH_INVARIANT=1`), deterministic Inductor, pinned compile flags; a numerics canary hash is checked at every server start. Cross-node determinism: 257/257 and 303/303 identical episodes | `scripts/a6000/{env.sh,serve.sh,worker.py}`, RESEARCH_LOG W3 |
| Prompt nonce | a short random string inserted into the system prompt. A "nonce draw" is the same checkpoint re-run with a different nonce: a minimal, meaning-free perturbation that re-rolls trajectories | `cloq/run_arm.py`, `docs/insights/NULL_RULE.md` |
| Infrastructure | 6 nodes × 8 A6000, file-based task queue, one runner per node | `scripts/a6000/`, `docs/a6000/` |

Perturbation matrix (each cell = one fixed checkpoint, run on 2–8 nonce draws):

- **Null family:** BF16 on the canonical prompt, plus BF16 with nonces n1–n8.
  - The null family is stratified: canonical and nonce runs are not exchangeable (p=0.0099).
  - Test cells use fresh nonces (q1–q5), never the null nonces.
- **Quantizers** (fake-quant weights, BF16 compute):
  - RTN W8/W6/W5/W4/W3;
  - GPTQ W4/W3 with calibration draws d1–d4;
  - AWQ W4 with draws d1–d4;
  - NF4, MXFP4;
  - QuaRot-style Hadamard rotation plus RTN/GPTQ (with a rotated-BF16 control);
  - RTN with stochastic rounding (rtnsr).
- **Deployed formats:** official FP8 and AWQ checkpoints (X1).
- **KV cache:** fake quantization at INT8 and INT4 with Hadamard rotation. Plain INT4 and INT3 destroy the model (79% and 90% of tokens flip) and are reported open-loop only.
- **Size-matched random controls** (E17): Gaussian noise at RTN-W4's norm (gauss k=1), Gaussian noise at RTN's per-group RMS (gshape), and RTN magnitudes with random signs (rtnsign).
- **Gaussian dose ladder:** k = 0.001 … 3.

Code:
- `cloq/compress.py`, `cloq/quantize.py`, `cloq/rotate.py`;
- the KV hook `scripts/a6000/pyhooks/`;
- the matrix generators `scripts/a6000/make_tasks*.py`;
- the full experiment list `docs/FINAL_EXPERIMENTS.md`.

## 3. Methodology

### 3.1 Integrity and provenance
- `analysis/insights/iter_2/integrity.py` builds a frozen snapshot. It admits only runs whose episodes are complete and deduplicated, and whose infrastructure errors are resolved (W6, W8, W10); it hashes every admitted file.
- All analyses take `CLOQ_SNAPSHOT` and tag their outputs with it.
- Scripts are organised by insight iteration: `analysis/insights/iter_{1..4}/`, each with `run_all.sh`.

### 3.2 Turnover (λ) and landing (c): the two-parameter summary (iter_3 r01, r10)
- **Classification:** each task is classified from null nonce draws as always-ok, always-fail or coin.
- **Model:** a perturbed checkpoint maps a task's null success probability p_i to p_i' = (1−λ) p_i + λ c.
  - λ is the turnover intensity; c is where re-rolled tasks land.
  - The net effect is Δ = λ (c − p̄).
- **Estimation:** λ and c come from the break rate on always-ok tasks and the fix rate on always-fail tasks, corrected for misclassification using held-out null draws (b0, f0).
  - The coin stratum is predicted out of sample as a check.
  - Code and derivation: `analysis/insights/iter_3/r01_realloc.py` docstring.
- **R3 statistics** (`r10_turnover_stats.py`, `docs/insights/iter_3_stats_R3.md`):
  - λ is reported above a numerics floor (rotated BF16, canonical BF16, Gaussian k ≤ 0.003).
  - Hierarchical bootstrap over tasks, null draws, checkpoints and draws, with paired contrasts.
  - Equivalence tests at ±0.10.
  - c is suppressed when λ's lower 95% bound is ≤ 0.10.
  - Holm correction over a declared family.

### 3.3 Checkpoint-level tests (iter_4, `docs/insights/iter_4_disposition.md`)
- **P1 overdispersion φ:** between-checkpoint variance of net Δ, after removing within-checkpoint (nonce) variance, relative to what independent task landing predicts. A permutation null is also used. φ = 1 means independent landing.
- **P2 behavioural fingerprint F:**
  - Per trajectory, 12 behaviour features are computed: turns, tool calls, act-vs-talk share, write calls, transfers to a human, tool errors, max_steps hits, and others.
  - Shift vectors are taken against the null.
  - F compares the similarity of shift vectors from two draws of the same checkpoint with that of different checkpoints at the same dose, under a permutation null.
- **P3:** do fingerprints explain net Δ?
- **P4:** does an open-loop fork bias predict the closed-loop fingerprint?
- **Holm** over 5 declared tests: `analysis/insights/iter_4/out/h00_holm_live_20260929T1937Z.json`.

### 3.4 Open-loop probes (no simulator)
- **E3** (`scripts/a6000/openloop_d.py`): teacher-forces 400 decisions sampled from the BF16 closed-loop run through a served checkpoint. It records the log-probability shift of BF16's own tokens, the token flip rate, and the flip rate binned by BF16's logit margin.
- **E4-2** (`scripts/a6000/openloop_topk.py`): keeps the top-20 alternatives at every decision start and at tool-name tokens.
  - From these it gives P(act = `<tool_call>`) vs P(talk), KL(BF16‖cell), and tool-name switch rates, with BF16 served as its own cell.
  - q4 smoke: RTN-W4 lowers P(act) where BF16 acted (0.956 → 0.831) and raises it where BF16 talked (0.016 → 0.065); tool-name switch rate 0.4% → 10.8%.

### 3.5 Equivalence against the model's own null ("conformal" layer)
- **Test:** the exact permutation/conformal p-value of a quantized run's outcome vector among nonce-stratum null draws. Several statistics, Holm across them, ε-inversion (the largest shift not ruled out), and per-model e-values (no product across models).
- **Power / MDE:** 6.5–13 pp per family with 85 tasks.
- **Code:** `analysis/insights/iter_2/c01_conformal_equivalence.py`; docs `docs/insights/iter_2_conformal.md`, `NULL_RULE.md`.
- **Status:** the review says this layer is not yet load-bearing (§6).

## 4. Results so far (gated snapshot; provisional until the 10-05 freeze)

| # | Result | Strength | Evidence |
|---|---|---|---|
| R1 | W4 turnover exceeds the numerics floor. Pooled excess λ: RTN +0.19 [0.10, 0.30], GPTQ +0.15, AWQ +0.16 (Holm p ≤ 0.036). Per model, RTN's CI excludes 0 only on q4 and q32 | established | `iter_3/out/r10_turnover_stats_live_20260929T1937Z.json`, W17 |
| R2 | Relative to the floor, q4 RTN-W4 breaks 2.2× [0.9, 8.9] and fixes 1.2× [0.4, 3.7]. Earlier "5–10×" claims used the wrong denominator | established (small effect) | W17 |
| R3 | RTN re-rolls no more than random-sign error of its own magnitude (non-inferiority at 0.10, Holm p=0.038). Other matched random controls point the same way but are n.s. Isotropic Gaussian at RTN's norm re-rolls *more* than RTN (+0.14 [0.013, 0.276], r08) | partial | W15, W17, `iter_3/out/r08_*` |
| R4 | W4 methods (RTN/GPTQ/AWQ) have similar λ, but equivalence at ±0.10 is not established (p 0.12–0.63) | inconclusive | W17 |
| R5 | Landing c cannot be identified for RTN on any model (λ too small), so "c depends on method" is untestable | unidentified | W17 |
| R6 | A fixed checkpoint's behavioural fingerprint persists across nonce draws: F=0.44, perm p=0.001, 48 checkpoints. The review shows it halves (0.22, still p=0.0005) when draws are computed on disjoint task halves, and that fixed *random* checkpoints are as persistent as quantizers | established for any fixed perturbation | W18, `iter_4/out/p2_*`, `paper/review_storyline_v5.md` |
| R7 | Net effects are coherent across tasks on q4. W4 φ 5.6; q32 3.1 (3 checkpoints, p 0.155); q8/q30a3 about 1. Retail only (φ 3.81) vs airline 1.07. Same-method recalibration pairs φ 4.65 (p 0.013, df 7, exploratory); q4 GPTQ d1 vs d2 net +9.6 pp [1.8, 17.4] | exploratory; **not confirmed** by the pre-registered test (§4b) | W17, W18, W25 |
| R8 | Open-loop act-vs-talk contrast predicts the closed-loop act share on q4 (partial ρ 0.62 given flip rate, Holm p=0.012), but not net Δ. Open-loop flip rate predicts λ mostly through dose (partial ρ given dose 0.39 [−0.03, 0.73]) | q4 only | W18, W17 |
| R9 | Capability damage: RTN-W3 −16.7 pp on q8 and −14.5 pp on q14. Plain KV INT4/INT3 destroys the model; KV INT8 and INT4 with rotation are mild | established | W14, W13 |
| R10 | New methods on q4 (3 fresh-nonce draws each): NF4, MXFP4, rotation, stochastic rounding. Rotated BF16 has λ 0.12, at the serving floor | descriptive | W12, W15 |

## 4b. Pre-registered confirmation (2026-09-30)

- **Pre-registration:** `docs/insights/PREREG_iter4.md`, committed while the confirmatory runs were running (W22). Amendment 1 (W24) records 18 implementation clarifications made on stand-in data before any outcome was seen, including the correct unit count: 28 runs, not 40.
- **Units:** 14 new checkpoints × 2 fresh nonces on q4/q8.
  - RECAL: GPTQ/AWQ-W4 on new calibration draws d3/d4.
  - RAND: Gaussian k=1 fixed seeds s2/s4/s5.
- **Analysis:** `analysis/insights/iter_4/prereg_h1_h4.py`, run once on snapshot 20260930T0044Z. Output: `analysis/insights/iter_4/out/prereg_h1_h4_CONF_20260930T0044Z.json`.

| id | Hypothesis | Estimate | p (Holm) | Verdict |
|---|---|---|---|---|
| H1 | Recalibration lottery: φ_RECAL > 1 | φ 0.40 (q4 −0.30, q8 0.94) | 0.74 | not supported |
| H2 | Net Δ replicates across nonces | r 0.42 (q4 −0.52, q8 0.94) | 0.42 | not supported |
| H3 | Fingerprint persists on disjoint task halves | F_split 0.26 (q4 0.19, q8 0.33) | 0.0024 | supported |
| H4 | φ_RECAL − φ_RAND ≠ 0 (secondary) | −0.83 [−7.1, 4.2] | 0.70 (raw) | not detected (underpowered) |

Secondary results:
- New q4 recalibrations all land at net +1.5 to +3.9 pp.
- Pooling d1–d4, q4 checkpoint SD is 3.65 pp, nonce SD 2.51 pp and method SD 0.
- Random fixed checkpoints have fingerprints at least as persistent as quantizers: same-checkpoint cosine 0.51/0.77 vs 0.32/0.38.
- The exploratory q4 d1 vs d2 gap (+9.6 pp) did not replicate.

## 5. Storylines and reviews

- **v5** (`docs/insights/STORYLINE_v5.md`): "A quantized agent is a different agent". Quantized checkpoints are reproducible behavioural variants: a coherent net effect and a persistent fingerprint. Prompt nonces, Gaussian noise and sampling only re-roll outcomes. The conformal/exchangeability test is the instrument that separates the two.
- **Review of v4** (`paper/review_storyline_v4.md`): 2.5/5. It removed four v4 claims:
  - "c follows method";
  - "20–40% turnover / 5–10×";
  - "λ depends on size, not structure" stated as an equality;
  - the p̄ prediction.
- **Review of v5** (`paper/review_storyline_v5.md`): 2.5/5 as-is; 3.5 if the paper is reframed around the "checkpoint lottery" and new calibration draws confirm it. Main points:
  1. "Unlike random perturbations of the same size" is contradicted. Fixed random checkpoints are as persistent as quantizers, and the coherence contrast hinges on how stochastic-rounding RTN is classified. Prompt nonces are not size-matched (λ 0.02–0.12 vs ~0.25).
  2. F is partly mechanical: split-task F is 0.22. Behavioural distinguishability of quantized models is prior work (AgentProv, Stability Monitor, logit fingerprinting, model equality testing, Dutta 2024).
  3. F4 is overstated: it is driven by the W3 method gap, q8/q30a3 show nothing, and the effect is retail only.
  4. Conformal is not load-bearing: no F1–F7 claim uses a conformal p-value, and Level 2 as described is not what P1/P2 do.
  5. The queued sampling baseline was mis-designed. vLLM reseeds each request with the same seed, so a fixed seed acts as a fixed perturbation; it is now pulled from the queue. E4-4 is underpowered (df 6), and E4-3 mixes nonce strata.
  6. No held-out test set exists: the 85 tasks are development data, and the 57 calibration tasks feed GPTQ/AWQ.

  Suggested reframing: lead with the "checkpoint lottery" (same method, different calibration draw → different agent, different net effect), and present the fingerprint as generic to any fixed perturbation.
- **Line A, checkpoint lottery** (the v5-review recommendation): refuted by the pre-registered H1/H2 (§4b).
- **Line B, success-equivalent but behaviourally distinct** (current proposal; `docs/insights/STORYLINE_v6.md`). Six claims:
  - B1: success-equivalence (small, stable net Δ; confirmed null).
  - B2: turnover above the floor.
  - B3: a persistent fingerprint (confirmed).
  - B4: the fingerprint is generic to fixed weight perturbations.
  - B5: what changes — act-vs-talk blurring and tool-name switches.
  - B6: the damage regime (W3, plain KV INT4/INT3).

  Open problem B7: show that the behavioural change matters. Candidates: pass^k reliability, policy violations or extra writes, cost, a stricter grader.

  Conformal role in Line B: one exchangeability test, two outcome spaces. Success vectors are exchangeable with the null (accept ε-equivalence); behaviour vectors are not (reject).

## 6. Experiment record (iteration 4)

| id | What | Status |
|---|---|---|
| E4-1 | Open-loop E3 for existing checkpoints on q8/q14/q30a3/q32 | running |
| E4-2 | Top-20 open-loop (act vs talk, tool name) for 49 cells on q4/q8/q14/q32 | q4 smoke + d3/d4 done, rest running |
| E4-3 | New calibration draws c3/c4 → GPTQ/AWQ-W4 d3/d4 on q4/q8, 2 fresh nonces each | done; confirmatory units (§4b) |
| E4-4 | Fixed Gaussian k=1 seeds s2/s4/s5 on q4/q8, 2 fresh nonces each | done; confirmatory units (§4b) |
| S | Sampling baseline (BF16, T>0) | pulled (vLLM per-request seeding makes a fixed seed a fixed perturbation); not rerun |
| M-cells | q30a3/q32 core quantizer cells, Llama slice, telecom (third domain, dual control) | running / low priority |
| X1, KVQ, new methods | official FP8/AWQ checkpoints; fake KV-cache INT8, INT4+rotation; NF4, MXFP4, QuaRot rotation, stochastic rounding | q4 done, q8/q14 partly done (W12–W15) |

Full chronological record with evidence paths: `docs/RESEARCH_LOG.md`. Per-run results are the queue records under
`/data/ziyangs/cloq_work/queue/done/` (not in git) and the gated snapshots in `analysis/insights/iter_3/out/snapshot_live_*.json`.

Scale:
- Each closed-loop run (85 tasks) costs 1–10 GPU-hours; the user simulator is the bottleneck.
- About 40 GPUs are available until 10-05.
- Open-loop cells take about 10 minutes.

## 7. Repository map

- **Paper:**
  - `paper/latex/`: ACL template; still the older "perturbation equivalence" framing, not updated.
  - `paper/perturbation-equivalence-closed-loop.md`: older draft.
  - `paper/review*.md`: internal reviews.
- **Plans and insights:** `docs/insights/` (PLAN_iter3/4, STORYLINE_v4/v5/v6, PREREG_iter4, NULL_RULE, SURVEY, iter_*_*.md) and `docs/FINAL_EXPERIMENTS.md`.
- **Analysis:**
  - `analysis/insights/iter_{2,3,4}/`: scripts plus `out/`.
  - `analysis/openloop/`: E3 and E4-2 outputs.
  - `analysis/kvq/`, `analysis/rotation/`: validation of the KV-cache hook and the rotation code.
- **Code:** `cloq/` (harness, compression, calibration) and `scripts/a6000/` (serving, queue, worker, task generators).
- **Not in git:** raw runs (`runs/`, several GB: trajectories and per-decision logprobs), available on request.

## 8. What we would like from you

1. **Storyline.** Line A is refuted. Is Line B (success-equivalent, behaviourally distinct) strong enough for NAACL, or is there a better true story in this data? Is anything more important than we realise?
2. **B7: does the behavioural change matter?** Which consequence would convince reviewers? Candidates, all computable from existing runs:
   - pass^k reliability;
   - policy violations or unnecessary writes;
   - cost / conversation length;
   - a stricter grader;
   - user-visible errors.
3. **Statistics.**
   - Critique the λ–c estimator, the fingerprint F / F_split, the hierarchical bootstrap and the pre-registration.
   - How should success-equivalence be stated: ε-TOST, a conformal acceptance test, or a hierarchical model?
   - How can the "one test, two outcome spaces" conformal framing be made rigorous with 8 null draws, 2–5 checkpoints per method and 85 tasks?
4. **Experiments before 10-05.**
   - Which additions give the most evidence per GPU-hour?
   - A clean held-out test set (telecom? the 22 excluded tasks?).
   - A simulator swap.
   - A corrected sampling baseline.
   - Which queued items to drop.
5. **Positioning.** How to differentiate B3/B4 from flip, behaviour-fingerprinting and model-equality-testing work (Dutta 2024, AgentProv, Stability Monitor, logit fingerprinting) and from agent-evaluation noise papers.
6. **Title, abstract and Figure 1** for an 8-page NAACL paper.
