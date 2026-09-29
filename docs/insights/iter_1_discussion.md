**TL;DR**
- Iteration-1 discussion between the insight, experiment and survey agents on I1–I4 (`docs/insights/iter_1_candidates.md`).
- Survey round 1: I2 new; I1, I3, I4 sharper versions; per-step margin model inherited (Du Eq. 14).
- Experiment round 1: the cross-server break is Inductor reduction autotuning, not scheduling. Fix: E2 (deterministic flag + canary + rerun q4/q8, ≈22 GPU-h). s02 KM is biased by censoring (E4a). Plan: `docs/insights/EXPERIMENTS.md`.

# Iteration 1 discussion

## Survey (round 1)

**TL;DR**
- I1 and I3 are sharper versions of prior work (b); I2 is new (a); I4 is (b). The per-step margin→flip model is inherited (c) from Du Eq. 14 and Integer Alibi.
- Change the experiments in three ways: (1) report the null width per serving path and per format (Replay Gap); (2) justify the choice of null, and test the canonical-prompt effect before P4c (Noise Floor Audit, Lunardi); (3) check our null SD against tau2 #540's 7–11 pt.

All novelty calls and the evidence behind them are in `docs/insights/SURVEY.md#answers-for-iteration-1`. Sweep tags (S-mfd, S-cae, S-enc) are defined in SURVEY.md §How to read the evidence tags.

### I1: divergence set by tie density

- **Call: (b) sharper/more general.** The per-step component is (c) inherited.
  - evidence: SURVEY.md I1-Q1 and I1-Q4.
- **Closest competitor:** Patodiya, *Same Request, Different Answer*, https://arxiv.org/abs/2609.04748.
  - Prefix caching changes 36% of 16-bit trajectories and 75% of 4-bit ones in multi-turn tool use.
  - It says, in words, that "amplification saturates at the coarsest settings".
  - evidence: S-mfd §CC-C.
- **Per-step model: inherited.** Du Eq. 14 (https://arxiv.org/abs/2609.26621) and Integer Alibi, AUC 0.942 (https://arxiv.org/abs/2608.13756).
  - evidence: S-mfd §CC-A, §CC-D.
- **What we add:**
  - the composition law against KM curves;
  - one δ axis from float noise to RTN-W4, with divergence flat across 1.5 decades;
  - the two-tier text/tool margin structure (no precedent found; I1-Q2).
- **Published results that should change experiments:**
  - **Replay Gap** (https://arxiv.org/abs/2608.08239, S-mfd §OE-22): FP8 control forks diverge > 90%, AWQ controls stay nearly identical.
    - P1c must be tested *per quantized format and per serving path*, not only BF16 a/b. Add same-node reruns of awq_w4 and gptq_w4.
    - Report the null width per arm.
  - **Integer Alibi** gives a calibrated margin→flip baseline (Brier 0.035, AUC 0.942). Report s01 against that calibration, not only as an AUC.
    - It also notes that the first teacher-forced flip is not the first free-running divergence. That caveat applies to P1d.
  - **AgentDiff** (https://arxiv.org/abs/2605.25981): meaning-bearing rewrites cause +19.7 pp more divergence than presentation changes.
    - Our nonce must stay presentation-only, and the paper should state this.

### I2: later damage threshold set by action-decision margins

- **Call: (a) new** as a two-threshold dose-response and as a margin-indexed cost of a flip. **(a)** for the action-turn flip rate as a fidelity metric.
  - evidence: SURVEY.md I2-Q1, I2-Q2, I2-Q4.
- **Closest competitor:** Flat Score, https://arxiv.org/abs/2607.27275. It shows the other side of P2:
  - the score stays flat while tool-name hallucination grows up to 2.5×;
  - the failure set is preserved;
  - the margin account is verbal and has no logprobs.
  - Point observations of divergence ≫ damage: Dutta 2407.09141, Singh 2608.15046, Rababah 2607.08734.
  - evidence: own [full]; S-enc §Close.
- **What we add:** two thresholds along one δ axis, and a mechanism for which flips cost success.
- **Published results that should change experiments:**
  - **Flat Score** measures damage through the *error budget*: tightening it from 10 to 2 re-exposes ≈ 17 pt.
    - P2a should also be reported under a strict budget, or on process-error channels (P2e), not only on db_match.
    - Otherwise a reviewer can say the "free zone" is an artifact of a lenient endpoint.
  - **ABC** (https://arxiv.org/abs/2507.02825, S-enc §OE): τ-bench counts empty responses as successes. **Benchmarking the Benchmarks** (https://arxiv.org/abs/2607.02577) reports brittle state matching.
    - Audit db_match in the damage cells (k = 3, W3) for empty or terminated episodes before placing the damage threshold.
  - **Quantization Inflates Reasoning** (https://arxiv.org/abs/2606.25519): token inflation is a hidden cost.
    - Add tokens and tool calls per episode as a secondary endpoint (S-cae §Tests-T2). It may move before db_match does.

### I3: D as a sufficient statistic, transferable across models

- **Call:**
  - (a) for D-sufficiency across perturbation families, and for the size-independent D(k);
  - (b) for margin-predicted robustness in principle (Fu 2601.06118; Du, in words);
  - (a) for pre-registered cross-model closed-loop curves.
  - evidence: SURVEY.md I3-Q1 through I3-Q4.
- **Closest competitor:** Fu, *Token Probabilities Expose Nondeterminism*, https://arxiv.org/abs/2601.06118.
  - Impact can be estimated from one run's token probabilities (single model, single perturbation).
  - evidence: S-mfd §OE-9.
- **What we add:** a matched-D comparison of structured vs random perturbations in closed loop, and cross-model prediction.
- **Published results that should change experiments:**
  - **YAQA** (https://arxiv.org/abs/2505.22988) and GPTQ/AWQ minimize *output* error, so they will have a smaller D than RTN at the same bits.
    - P3b must place quantizers by measured D (as drafted), never by bit-width or weight norm.
  - **Fang** (https://arxiv.org/abs/2506.22776, S-mfd §Optional): quantized weights respond differently to Gaussian noise.
    - Never stack the Gaussian ladder on quantized checkpoints.
  - **Qamar** (https://arxiv.org/abs/2609.07664): accuracy is non-monotone under progressive quantization.
    - P3b's Gaussian-ladder interpolation should allow non-monotone success at small D. Use a band, not a fitted monotone curve.

### I4: reference run = one draw; equivalence = exchangeability

- **Call: (b).**
  - Equivalence testing for compressed LMs exists: Singh uses a declared margin, and Flat Score uses a TOST margin taken from one rerun.
  - A perturbation null exists statistically (Acharyya 2509.10963) and for input counterfactuals (Compared to What? 2605.01048).
  - **(a)** for task-level exchangeability plus nestedness in closed-loop compressed agents.
  - evidence: SURVEY.md I4-Q2 and I4-Q4.
- **Closest competitor:** Singh, https://arxiv.org/abs/2608.15046 (own [full html]), and Flat Score's TOST (S-enc §Close-1).
- **Published results that should change experiments:**
  - **Noise Floor Audit** (https://arxiv.org/abs/2608.22331, S-enc §Close-3): the choice of null dominates; prompt-perturbation SDs are 11–58× rerun SDs.
    - Always report both nulls (rerun and nonce) side by side, and justify why the nonce is "neutral".
    - I1/P1c supplies the justification: reruns are 0 or saturated depending on D.
  - **Canonical-prompt advantage** (Lunardi https://arxiv.org/abs/2509.04013; Mizrahi https://arxiv.org/abs/2401.00595; Sun https://arxiv.org/abs/2306.11270).
    - Paraphrased prompts lower scores systematically on static benchmarks. P4c is a real risk: the s05 pilot already has canonical BF16 at the maximum (0.556 of 8 runs; evidence: `analysis/insights/iter_1/out/s05_pilot_success_q4_airline.json`).
    - Add a weight-only null (Gaussian k ≤ 0.03 on the canonical prompt, several seeds) next to the nonce null. The two can then be compared.
  - **tau2-bench issue #540** (https://github.com/sierra-research/tau2-bench/issues/540, S-enc §OE): single runs must differ by 10–11 pt (airline) or 7–8 pt (retail); 32–55% of tasks reverse across identical runs.
    - P4a should report our null SD next to this external estimate.
    - If our greedy null is much narrower, say why (greedy decoding vs their sampling settings).
  - **Intent Mismatch** (https://arxiv.org/abs/2602.07338, S-cae §Papers-10): user-simulator variance confounds multi-turn loss.
    - Fix the simulator seed and endpoint within each null. The node/endpoint issue in iter_1_candidates §design issue is the same confound.
  - **Koobs & Koning** (https://arxiv.org/abs/2603.16213): valid data-dependent equivalence margins.
    - A citable basis for "margin derived from the null", ahead of a reviewer's "post-hoc margin" objection.

### Response to the experiment agent

No experiment-agent turn was in this file when I posted. I will respond in round 2.

## Experiment (round 1)

**TL;DR**
- The cross-server break is **not scheduling and not hardware**. It comes from Inductor *autotuning* of the fused residual+RMSNorm reduction at compile time. On node005 it picked `R0_BLOCK=2048` for q4's hidden-2560 reduction; everywhere else it picked 4096. The result is a different summation order in every forward pass. Fix (E2): `TORCHINDUCTOR_DETERMINISTIC=1` plus a canary gate. Then rerun q4 and q8 (≈22 GPU-h, ≈2 h wall) and keep the legacy runs as a measured "numerics-flavour" null family.
- Only q4 bf16 and its 5 nulls are verified. Every other q4/q8 cell ran on a server whose flavour is unknown, and most q8 cells probably differ from `q8_bf16`. This contaminates D and divergence at k ≤ 0.1 and RTN-W8 (I1 P1a, I3 P3a/P3c). It does not contaminate k ≥ 0.3 or the outcome means.
- Separately, `s02` counts "same normalised action, different raw tokens" as *censoring*: 40 of 54 q8 k=1 tasks. So the KM divergence curves are biased low. Fix E4a costs 0 GPU-h.

### 0. Determinism: what the evidence says

| # | Finding | evidence |
|---|---|---|
| D1 | det_q4_a (node005) vs det_q4_b (node004): **113/113** identical-prompt decisions carry a margin shift or a first-token flip. 72/113 already differ at the first generated token. In shifted decisions a median 59% of tokens are shifted. The pattern is a fixed, server-wide numerics difference, not an intermittent effect (prefix-cache hits or chunk boundaries would hit only some decisions). | `analysis/insights/iter_1/exp/out/detshift.json` ← `exp/e_detshift.py` |
| D2 | det_q4_b (node004) vs q4_bf16 (node003): 245/245 identical, 0 shifted. This holds even though q4_bf16 served 4 run-domains at once (bf16 + null_n1) and det_b served 2, so batch composition and prefix-cache state differed. det_q30a3 a/b (node005/node004, including their node-local simulators): 254/254 identical. | same file; run environments `runs/a6000_q4_bf16/retail/environment.json`, `runs/a6000_det_q4_b/retail/environment.json` |
| D3 | The probe (node006 GPU5, which inherits node006's compile cache) gives: seq_cold, seq_warm, conc, nopc_seq, nopc_conc all **= B 30/30** and = A only on the 10 "same" items. Cold vs warm prefix cache, concurrency, and prefix caching on vs off change nothing. eager_seq = eager_conc (self-consistent), but they match neither: = A 14/30, = B 16/30. Eager is a third, deterministic flavour, which makes it a usable controlled floor perturbation (E5). | `/data/ziyangs/cloq_work/logs/tasks/probe_det_q4.log`; the final `analysis/determinism/probe_q4.json` will appear when it finishes |
| D4 | The vLLM configs of det_q4_a and det_q4_b are identical: same KV cache (225,904 tokens), same compile-cache hash `162509c25f`, same CUDA-graph capture sizes, no preemption. Both compiled fresh (35.4 s vs 36.4 s). | `/data/ziyangs/cloq_work/logs/tasks/det_q4_{a,b}.vllm.log` |
| D5 | **Mechanism.** Inductor benchmarks several reduction configs at the first compile on a node and stores the fastest in `*.best_config` in the node-local `/tmp/cloq_<job>/torchinductor_ziyangs`. For q4's hidden-2560 kernel `cjpkr2e73` it picked **R0_BLOCK=2048 on node005** (18:12:56, while 4 q4-architecture servers compiled at once) and **4096 on node003/004/006**. For q8's hidden-4096 kernels: `cxvticsdz` is 2048 on node004 and 4096 on node001/003/005/006; `ceqktfcyv` is 2048 on node006 and 4096 elsewhere. For q30a3's hidden-2048 kernel, only XBLOCK/num_warps differ; R0_BLOCK is 128 everywhere, which is consistent with q30a3 being identical across nodes (D2). `VLLM_BATCH_INVARIANT=1` fixes matmul and attention, but it does **not** set Inductor's `deterministic` flag (`TORCHINDUCTOR_DETERMINISTIC`, torch 2.13 `_inductor/config.py:1009`: "skips any on device benchmarking … if we know they affect numerics"). | `exp/out/bestconfig_node00{1,3,4,5,6}_job*.tsv` ← `exp/e_bestconfig.sh` (read-only ssh); `grep -n deterministic $(python -c 'import torch._inductor.config as c;print(c.__file__)')` |
| D6 | The simulator is not the source. All of s02's "context mismatch without agent flip" events are **agent-side**: the previous agent completion token ids differ while `action_key` is equal, and the first differing message is the assistant's. This holds for q4 (3–7 per config) and q8 (8–40 per config). The candidates' attribution to the simulator is wrong. | `exp/out/ctxmis.json` ← `exp/e_ctxmis.py` |

So each fresh compile draws a flavour. The draw is timing-dependent, so contention matters. Servers that compile later from the node cache (≈1.5 s compile) inherit the node's draw. A node restart (a new `/tmp/cloq_<job>`) draws again. **Pinning to a node does not fix this.**

### (a) What this means for every cell already run

Per-task table: `exp/out/server_flavour.json` ← `exp/e_server_flavour.py`, which joins the node logs `/data/ziyangs/cloq_work/logs/node_*.out`, the vLLM logs, the queue records and D5.

| model | reference server | other cells | status |
|---|---|---|---|
| q4 | `q4_bf16` + null_n1..n5, one server, node003 GPU2. **Verified** the same flavour as det_q4_b (D2). | gauss0.03/0.1 (node003) and gauss0.3/1/3 (node006) were fresh compiles 5–6 at a time, so each server's pick is unknown. The node disk says 4096, which is the likely canonical. rtn_w3/w4/w8 (node005) compiled fresh together with det_q4_a, which is off, on the node whose disk says 2048: **high risk of being off**. gptq/awq have not started. If they land on node005 (job 49596) they **inherit the off flavour for certain**. | nulls clean. Every other cell has an unknown flavour relative to the reference. |
| q8 | `q8_bf16` + nulls, node004 GPU5. Fresh compile, 3 at a time (with gauss0.03 s1/s2), and the node004 disk says `cxvticsdz`=2048. The reference's own pick is unknown. | awq_w4, gauss0.1 s1/s2, gauss0.3_s1, gauss3_s2, rtn_w3, rtn_w8 inherited node003/node005 caches (4096/4096). They differ from node004's disk in one kernel, so they are **probably off relative to the reference**. gauss0.3_s2 and gauss1 s1/s2 inherited node004's disk. gauss3_s1 and rtn_w4 (node006, `ceqktfcyv`=2048), gptq_w4 d1/d2 (node001) and gptq_w3 (node007) are unknown. | **Treat q8 as mixed-flavour throughout.** |
| q14 | Not run. `q14_bf16_cal` (node007; the cache is gone because job 49598 was cancelled at 18:42) only feeds calibration, where flavour is a harmless re-roll. | gptq/awq ×4 were claimed on the new node007 job at 18:47, before any fix. | These become legacy. |
| q30a3 | Not run. The det pair is identical across node004 and node005, including their simulators. | — | Apparently immune (D5). Still verify under the fix. |
| q32 | Not run (`bf16_cal` requeued). | — | Hidden 5120, so susceptible. |

**Impact by claim** (δ_flavour: median \|d\| 0.125, 59% of tokens shifted, KM≤4 0.50, tool-turn flip 0.015; evidence: `out/s04_node_floor.json` ← `s04_node_floor.py`; candidates I2 table):
- **I1.** The "node floor" datum is real, but it should be relabelled "compiled-kernel flavour", not node005 hardware. It still supports P1c. The small-δ dose-response in P1a (k=0.03 vs 0.1 vs W8) is **not testable on legacy q4/q8**, because the flavour δ is about the size of k=0.03 (median \|d\| 0.125 for both; `out/s03_margin_predictions.json` `shift_by_k`). Saturation itself is not threatened; if anything it is strengthened.
- **I2.** At the outcome level, flavour is a sub-threshold re-roll (tool-turn flip 0.015). Legacy runs remain valid *unpaired* free-zone draws. Paired statistics (P2b predictors at k ≤ 0.1, P2c pairing to BF16) must use clean cells.
- **I3.** D(k) at k ≤ 0.1, W8's placement, and "q4 and q8 share D(k)" at k=0.03/0.1 are **not evidence yet**: the flavour D equals k=0.03's D. At k ≥ 0.3, adding 0.125 to a median of 0.5–2.0 has no material effect. P3c at k=0.03 must be scored on clean cells only.
- **I4.** Nulls share their reference's server, so each null set is internally clean. P4b (exchangeability of cells with nulls) on legacy q8 mixes flavour. That is harmless under I4's own premise, but a reviewer will ask about it, so run it on clean cells.

### (b) Minimal fix under each probe outcome

The probe design only replays on node006, whose cache holds the canonical 4096. **Add E1a**, the same probe pinned to node005 (predicted = A 30/30), and **E1b**, a probe under `TORCHINDUCTOR_DETERMINISTIC=1` with a fresh cache on two nodes (predicted: identical on both).

| probe outcome | reading | minimal fix | cost |
|---|---|---|---|
| **O1 (observed):** default + nopc conditions = B 30/30; eager self-consistent but its own flavour | scheduling is exonerated; the per-compile kernel flavour (D5) is the cause | **E2**: `TORCHINDUCTOR_DETERMINISTIC=1` for agent servers, plus a canary gate at server start, plus a rerun of q4 and q8 (and the 4 q14 quant tasks started before the fix) under a new run-id prefix. Legacy runs become the numerics-flavour null family (E5). | ≈22 GPU-h, ≈2 h wall (below) |
| O1 + E1a ≠ A | the node005 disk config is not the whole story: per-instance draws | same fix (the flag removes the draw); rely on the canary | same |
| O2: default conditions disagree (cold≠warm or seq≠conc) but nopc agrees | prefix caching breaks batch invariance (already ruled out by D3) | add `--no-enable-prefix-caching` + E2 | rerun ≈22 GPU-h; remaining matrix ≈1.5–2.5× slower (≈95 → ≈200 GPU-h, still < 1 cluster-day) |
| O3: only eager is stable | compile ranges or CUDA graphs depend on batch shape | `--enforce-eager` for all agent servers + rerun | same order as O2 |
| E1b not identical across nodes | the flag is not honoured through vLLM's compile path | fallback F-freeze: seed one frozen Inductor + vLLM cache (copied from node004's `/tmp/cloq_49603/`, which is q4-canonical) into every job's `TMPDIR` at start; or `--enforce-eager` | ≈0 GPU-h + the same rerun |
| everything unstable, eager too | batch invariance is broken at kernel level | treat serving as its own perturbation family with measured δ; measure D only open-loop on one server (E3); use legacy data unpaired | 0 rerun; I1-P1a and I3 at small k downgraded to "not testable" |

Rejected alternatives:
- *Pin each model to one node.* The flavour is per compile, not per node, and node restarts redraw it; node007 was cancelled at 18:42 (`logs/node_node007_49598.out`).
- *Per-node rerun null.* It characterises the problem but fixes nothing.

### (c) Cost basis

Observed wall-clock per task, from `queue/done/<task>.json` `seconds`:
- q4 single-run tasks: 0.265 h (gauss0.03_s1, gauss0.3_s1) and 0.444 h (gauss1_s2).
- q4_rtn_w4 (2 runs): 0.384 h.
- det tasks (20 tasks): q4 0.10–0.13 h; q30a3 0.12–0.13 h on 2 GPUs.
- q8_bf16_cal (57 tasks): 0.271 h. q14_bf16_cal (57 tasks): 0.328 h.

The q8/q4 generation-time ratio on the eval set is ≈1.35 (`runs/a6000_q{4,8}_bf16/retail/decisions.jsonl`, `generation_seconds` summed: 1.63 h vs 2.20 h).

Estimates:
- per run: q4 ≈0.27, q8 ≈0.37, q14 ≈0.49 GPU-h;
- q30a3 ≈0.3 h × 2 GPUs; q32 ≈1 h × 2 GPUs (unmeasured guess);
- whole matrix ≈ 8 + 11 + 15 + 19 + 62 ≈ **115 GPU-h**.

Capacity is ≈26 agent GPUs, i.e. 6 nodes × 8 GPUs, minus 2 simulator GPUs per node, minus bad cards; see the `logs/node_*.out` headers. **Compute is not the constraint; correctness and queue order are.**

The long pole is the bf16 + 5-null task: 12 run-domains at RUN_PAR=4 on one GPU. `q4_bf16` was at 4/12 after ≈35 min (`/data/ziyangs/cloq_work/status/node003-g2.json`), so ≈1.7 h for q4 and ≈2.3 h for q8.

### Decisive tests for I1–I4 (all on clean cells after E2)

| insight | decisive test | in matrix? / when | design flaw → fix | cost |
|---|---|---|---|---|
| I1 | Per model, KM P(first div ≤4, ≤12) with a task-bootstrap CI (n=85) for {flavour null, nonce×5, k=0.03×2, k=0.1×2, W8×2}. **Flat** means all lie within ±0.15 at d=4. **Refuted** if d=4 rises > 0.3 from k=0.03 to 0.1. | yes, ≈2–4 h after the E2 restart for q4/q8; ≈+6 h for all models | (1) KM treats raw-token divergence as censoring (D6) → **E4a**; (2) the floor is uncontrolled → **E5** (legacy flavour + eager BF16) | 0 (E4a) + E5 ≈6 GPU-h |
| I2 | Per model, Δdb_match(config − mean of the 5 nulls) with a task-cluster bootstrap. Pooled free zone (k ≤ 0.1, W8: 6 runs/model): SE ≈ 0.027 per model and ≈0.012 over 5 models, so MDE ≈ 3.4 pp. Damage cells (k=3, W3) below the nulls. | yes | P2a as written ("inside the range of 5 nulls ± 1 SE") has a ≈1/3 false-alarm rate per run: an exchangeable draw falls outside the range of 5 others with probability 2/6. Replace it with the bootstrap Δ and P4b's permutation. P2d (cross-model ordering at k=1) is underpowered with 2 seeds (SE ≈ 0.037 per model) → optional **E6**. Survey: also report a strict error budget and tokens per episode, and audit empty or terminated episodes in the damage cells (E4c). | 0; E6 ≈15 GPU-h |
| I3 | P3a/P3b/P3c using D measured **open-loop on the BF16 reference contexts, on the same server as the cell** (`cloq/openloop.py`). This removes the flavour and removes the survivorship truncation the candidates admit (D only on pre-divergence, unflipped tokens). | no → **E3** | GPTQ/AWQ must be placed by measured D (survey: YAQA). Use a band, not a monotone fit (Qamar). | ≈26 GPU-h standalone (estimate; measure on the first q4 cell); less if run inside the eval task while the checkpoint is served |
| I4 | P4a pooled over 5 models (20 df; 5 nulls give only 4 df per model, so the per-model [0.5, 2] band is nearly unfalsifiable). P4b permutation on the task × run matrix. P4c canonical rank among {bf16, nulls, flavour null, k=0.03 s1–s5}. | mostly yes | The survey's canonical-prompt risk needs a null that changes neither prompt nor weights. **E5's flavour null is exactly that** (legacy BF16 vs new BF16, canonical prompt). | E5 |

### Ranked proposals (value per GPU-h)

| rank | id | what | GPU-h | why |
|---|---|---|---|---|
| 1 | **E4** | Analyses of existing runs: (a) count raw-token divergence as an event, typed "format", in s02; (b) join `server_flavour.json` into every s0x output and restrict paired stats to clean pairs; (c) db_match audit for empty or terminated episodes in k=3/W3, a strict error budget, and tokens per episode; (d) P4a SD next to tau2 #540 (7–11 pt) | 0 | un-biases every I1 curve now; the rest is required by the survey |
| 2 | **E1** | E1a probe on node005; E1b flag probe on node003 + node005 | ≈0.75 | confirms the mechanism and the fix before anything is rerun |
| 3 | **E2** | flag + canary gate + rerun q4/q8 (+ 4 q14 quant tasks) under a new run-id prefix | ≈22 | without it I1-P1a and I3 at small δ have no clean data |
| 4 | **E5** | numerics-flavour null family: legacy q4/q8 runs (free) + one eager BF16 run per model + gauss k=0.03 s3–s5 for q4/q8 | ≈6 | P1c, P4c and the survey's weight-only null in one family |
| 5 | **E3** | open-loop D per cell on its own server | ≈26 (est.) | a clean sufficient statistic for I3 and the P2b predictor |

Deferred:
- **E6**: seeds s3/s4 at k=0.3 and k=1, ≈15 GPU-h, only if P2d looks close.
- Drop `q32_gptq_w4_d2` if q32 GPTQ builds hit the known OOM (user memory: qwen32 fragmentation). No insight needs a second calibration draw at 32B, because the 4080 already showed the draws are exchangeable (candidates I3).

### Response to survey (round 1)

- **Replay Gap per-format null.** Agreed, and D5 supplies the mechanism: control-fork width is set by whether the serving path's compiled numerics are fixed, not by the format as such. All our fake-quant cells go through the BF16 path, so after E2 one det pair (E1b) covers them. Phase-4 real kernels (AWQ/GPTQ Marlin, FP8) each need their own det pair of ≈0.12 h × 2.
- **Weight-only and canonical-prompt null.** Adopted as E5. The legacy-flavour BF16 runs are canonical-prompt, untouched-weight nulls. The k=0.03 s3–s5 runs add the weight-only null the survey asked for.
- **Simulator endpoint (Intent Mismatch).** D2 and D6 show the node-local simulators agree (node004 = node005) and that no mismatch event is simulator-side. E2's canary should also fingerprint each simulator at node start.
- **Strict error budget, empty episodes, token inflation.** Adopted as E4c, at 0 GPU-h.

## Insight (round 2)

**TL;DR**
- All the survey and experiment points are accepted, except two partial rebuttals (R1, R2). I1 is strengthened: the Inductor kernel flavour is a real-world perturbation that re-rolls 95% of trajectories. I2 is weakened: P2c is demoted, P2a is restated as a bootstrap Δ, and P2e is added. I3 is strengthened on legacy q8, where GPTQ and AWQ fall where they were predicted to. I4's null moves to the weight-only / flavour family.
- s02's censoring bug is fixed (E4a done). Rewritten candidates: `docs/insights/iter_1_candidates.md`. Agreed ranking: E4 → E2 (a6k2 + canary + det pair) → E5 → E3 → E7 (new); E6 deferred; E1 superseded.
- Every A6000 number below is [legacy]. Snapshot: `analysis/insights/iter_1/out/s00_snapshot.json`, 2026-09-29T02:06Z. Numbers come from `analysis/insights/iter_1/out/*` ← `s0x_*.py`.

### Replies to the experiment agent

- **D1–D5 (kernel flavour): accepted.**
  - "node005 floor" is relabelled "compiled-kernel numerics flavour" throughout.
  - **Bearing on I1 (fact 1):** this is I1's best datum, not a confound of it. A reduction-order change inside one fused RMSNorm kernel does the following, with no weight or prompt change:
    - shifts 59% of tokens (median |d| = 0.125, ≈ gauss k = 0.03);
    - re-rolls 95% of trajectories by decision 12;
    - flips 4/20 task outcomes (db_match 0.45 vs 0.55).
    - evidence: `out/s04_node_floor.json`, `out/s07_flavour_outcome.json` ← `s04_node_floor.py`, `s07_flavour_outcome.py`.
  - q30a3, whose R0_BLOCK matched across nodes, is identical (same files). That is the D ≡ 0 arm of the new P1c.
  - The flavour family is therefore the smallest-δ point on I1's axis, and it is a null family for I4 (E5).
- **D6 (the simulator is not the source): accepted.** The round-1 simulator attribution is retracted.
  - After the E4a fix, the count of "context mismatch without agent flip" is 0 in every q4 and q8 config. evidence: `out/s02_trajectory_divergence_{q4,q8}.json`.
- **(a) Contamination by claim: accepted, with all legacy numbers labelled.**
  - Small-k D matching (q4 = q8 at k ≤ 0.1) and P1a's small-δ dose-response are reclassified as "not evidence until a6k2" (candidates I1 and I3).
  - Paired statistics are restricted to clean pairs (E4b).
- **(b) Fix: superseded by the main session's decision** to rerun the whole matrix as `a6k2_*` under `TORCHINDUCTOR_DETERMINISTIC=1`.
  - I still need the **canary gate and one cross-node det pair per model under the flag**. P1c's D ≡ 0 arm depends on it.
- **E4a (s02 censoring bug): accepted and done.**
  - The fix is in `analysis/insights/iter_1/s02_trajectory_divergence.py`. A raw-token difference on an identical context is now an event of type `format`.
  - The KM curves rose slightly. q4 k = 0.03 ≤ 4 went from 0.57–0.60 to 0.61–0.65. On q8 k = 1, the formerly censored tasks now appear as events: 39–40 of 83–85 are `format`.
  - `s05` was updated to keep `format` separate.
  - evidence: `out/s02_*`, `out/s05_*`.
- **P2a false-alarm rate (fact 3): accepted.**
  - P2a is now a per-model task-cluster bootstrap Δ against the null mean, with a pooled 5-model MDE of ±3.4 pp, plus the P4b φ permutation.
  - The pilot implementation is `s06_pilot_delta.py`. Retail: every cell's CI contains 0. Airline: 3 cells exclude 0. They are gauss 0.3 s1 (−0.167) and both null members, bf16 (+0.093) and null_n1 (−0.093).
  - With only 2 nulls, each null member is flagged against the null mean. That is why P4b is needed as well, and why P2a needs all 5 nulls. evidence: `out/s06_pilot_delta_q4_{retail,airline}.json`.
- **P2d underpowered: accepted.** Dropped from the main line; E6 stays deferred.
- **P4a per-model band nearly unfalsifiable: accepted.** Now pooled over 5 models (20 df).
- **E3 (open-loop D on the cell's own server): accepted, ranked 4.** It removes both the flavour and the survivorship truncation in s01's D.
  - That truncation is the source of the 0.1–0.15 under-prediction on q4 (candidates I3).
- **R1, a partial rebuttal on E2's scope.** The experiment agent put the flavour's impact on outcome means at "none" for k ≥ 0.3. I agree for unpaired means.
  - For I4 it is not negligible: the flavour alone flips 20% of task outcomes, the same rate as between null draws (0.185–0.195).
  - Legacy and a6k2 runs of the *same* config are therefore a second draw, not a duplicate. They should be kept and used (E5), not discarded.
  - evidence: `out/s07_flavour_outcome.json`, `out/s06_*` `null_pairwise_task_disagreement`.

### Replies to the survey agent

- **Per-step model inherited: accepted.** It is positioned as Du Eq. 14 plus Integer Alibi and MarginGate. s01 is called a replication.
- **Integer Alibi calibration (Brier): accepted as E4e.** One calibration curve fitted on the flavour pair, then applied to every family after δ-rescaling, is the token-level test of I3.
- **Teacher-forced vs free-running first flip: accepted.** P1d is scored on free-running divergence only.
- **Replay Gap per-format null: accepted, with a reinterpretation.**
  - P1c now says null width is bimodal in D: D ≡ 0 gives no divergence; D above the bf16 resolution gives saturation.
  - Our fake-quant cells all use the BF16 kernel path, so after a6k2 one det pair per model covers them.
  - For real kernels (Replay Gap's FP8/AWQ axis) I propose **E7**: Marlin det pairs for q8 awq_w4 and gptq_w4, ≈ 0.5 GPU-h.
- **AgentDiff (nonce must be presentation-only): accepted.** The nonce is a "Session ID" line appended to the system prompt (`cloq/agent.py` L93–96). The paper will say so.
- **Flat Score error budget (fact 4): accepted.** P2 is reported on db_match, on a strict-budget endpoint (≤ 2 tool errors, applied post hoc) and on process channels (P2e).
  - Pilot: the strict budget moves Δ by at most 0.017.
  - At k = 1 the process channels already move: decisions per episode 15.1–16.9 vs 12.0–12.3 for the nulls, premature rate 0.034–0.069 vs 0.
  - db_match has not yet moved significantly.
  - evidence: `out/s06_pilot_delta_q4_retail.json`.
- **ABC / Benchmarking-the-Benchmarks empty-episode audit: accepted.**
  - `s06` counts empty or premature episodes per cell: 0–1 in the free zone, and 1–4 at k = 1.
  - The damage cells (k = 3, W3) are to be audited once complete (E4c).
- **Token inflation: accepted as a process channel (P2e), not as an insight.**
- **YAQA (place quantizers by D): accepted, and partly confirmed on legacy q8.**
  - GPTQ W4: D 0.75, between k = 0.3 (0.5) and k = 1 (1.6–1.75). AWQ W4 (1.5) ≈ RTN W4 (1.5).
  - evidence: `out/s01_token_flip_margin_q8.json`.
- **Fang (no Gaussian noise on quantized weights) and Qamar (use a band): accepted.** Both are written into P3b.
- **Noise Floor Audit (report both nulls): accepted.** I4 reports nonce, weight-only and flavour nulls side by side. P1c supplies the reason rerun nulls are invalid.
- **Canonical-prompt advantage (fact 4): accepted as a live risk. P4c is recast.**
  - It is now a three-family comparison (weight-only gauss k = 0.03 s1–s5, flavour, nonce). E5 adds k = 0.03 s3–s5.
  - **R2, a partial rebuttal:** the pilot does not yet show a canonical advantage.
    - Airline: canonical 0.556 vs null_n1 0.370 (27 tasks).
    - Retail: canonical = null_n1 = null_n2 = 0.345 (58 tasks).
    - Pooled over 85 tasks this is one draw of ≈ +0.06, within 2 Bernoulli SD (≈ 2.6 pt each).
    - evidence: `out/s06_pilot_delta_q4_{retail,airline}.json`.
  - So the risk is not yet realised, but it is untested, which is why E5 is ranked 3.
- **tau2 #540 (null SD 7–11 pt): accepted as E4d.**
  - Our greedy Bernoulli SD is ≈ 2.6 pt pooled, with 19% task disagreement between null draws. #540's numbers are under sampling.
  - The narrower width is expected. Its being non-zero is the I4 point.
- **Intent Mismatch (simulator variance): accepted.** D6 shows the node-local simulators agree, and the a6k2 canary should also fingerprint the simulator.
- **Koobs & Koning / Acharyya: accepted as citations** for the null-derived margin. The formal basis is still an open survey question.

### Agreed experiment proposals, ranked

Details and costs are in `docs/insights/iter_1_candidates.md#experiments-agreed-and-ranked` and `docs/insights/EXPERIMENTS.md`.

1. **E4 (0 GPU-h).**
   - a: done.
   - b: flavour tags, clean pairs only.
   - c: strict budget, process channels and empty-episode audit on the damage cells.
   - d: SD next to #540.
   - e: Brier calibration.
   - f: P4b φ and P4e nestedness.
2. **E2 (a6k2, running).** Add a canary gate (agent + simulator) and one cross-node det pair per model under the flag.
3. **E5 (≈ 6 GPU-h).**
   - Legacy vs a6k2 BF16 flavour null (free).
   - gauss k = 0.03 s3–s5 on the canonical prompt for q4 and q8.
   - One eager BF16 run per model.
4. **E3 (≈ 26 GPU-h, est.).** Open-loop D per cell on its own server.
5. **E7 (new, ≈ 0.5 GPU-h).** Marlin real-kernel det pairs for q8 awq_w4 and gptq_w4.
- Deferred: E6 (P2d power).
- Superseded: E1 (root cause confirmed, `analysis/determinism/probe_q4.json`).
- Conditional: X1 (drop q32_gptq_w4_d2 on OOM).
