# New-method common panels (protocol nmp-v1, W99v)

**TL;DR** This protocol freezes two common panels that the new-method agents (QuaRot and SpinQuant W4 on q8, KIVI on q8) and the second-family (Mistral) agent run against. It also fixes the estimands, the inference, the expansion rule and the reporting before any panel task runs.
- **Panel A (τ²).** One ordinary state per task × block, sampled outcome-blind with the Bank U U2B rule.
  - The states come from the **BF16 trajectory** `a6k2_q8_bfpair_<blk>`, so they are the same for every method.
  - Six nonce blocks f01–f06 × the 85 retail/airline tasks = 510 states. Every configuration runs all four arms (BB, BQ, QB, QQ).
  - Phase 1 is f01–f03. Whether f04–f06 run is decided by a throughput/deadline rule that reads no effects (§5).
  - The f01–f03 rows are byte-identical to Bank U's U2B rows, so the existing q8 GPTQ-W4 d1, AWQ-W4 and KV8 four-arm results are reference cells on the same states at no GPU cost.
- **Panel B (BFCL multi-turn).** 200 items, 50 per category, chosen by a frozen hash rule from the eval pool. The pool excludes every adapter-development, smoke and gate sample (q4, q14 and l8 gates, plus the l8 probe). Four arms per item follow fork-ext-v1.
- **Headline comparison across methods.** The common-continuation action effect D_cc = Y_QB − Y_BB, compared across methods on the same τ² states. BB is the shared BF16 original, so the difference between two methods is exactly Y_QB(m1) − Y_QB(m2).
- **No new fork_driver mode is needed.** The manifest uses the Bank U row schema (`bank_u` mode, `subs ["U2B"]`) and the BFCL manifest schema (`bfcl_run` subset `nmp_v1`). Gates use the existing `gate_same` with `foreign_states` and the `bank_u` gate. KL uses the existing score driver.

| Frozen artifact | sha256 |
|---|---|
| `manifests/fork/newmethod_panel_v1.json` (q8; 510 τ² rows, 0 missing; 200 BFCL ids) | `7534c6907fa68bc8dab48061d7a2944a719e6e2fa123b639e7a0674c5a6ca201` |
| `scripts/a6000/make_newmethod_panel.py` (builder, as it built the manifest; also recorded inside it as `builder_sha256`) | `5fcc530872cd4d8dc77177607d31ae11668568a04c8933743cce852c35deb6cd` |
| Integrity snapshot used: `analysis/insights/iter_3/out/snapshot_auto_20261002T0631Z.json` | recorded in the manifest (`snapshot.sha256`) |
| Bank U manifest whose U2B rows f01–f03 equal ours (255/255 asserted by the builder) | `e236ee6483e723ffe8acd743ff2f5af8c1f92b49a39a7e721359c960ee12a907` |

`analysis/fork/analyze_newmethod.py` refuses to run if this file's sha256 differs from the value frozen in the script. Any amendment must therefore be appended here as a dated section, and the script's constant must be updated in the same commit, with a RESEARCH_LOG entry. `analysis/fork/holdout/` is never read by anything in this protocol.

---

## 1. Configurations

Model q8 = Qwen3-8B (`scripts/a6000/models.json`). B = BF16 everywhere. A configuration ("cell") is the Q role: one checkpoint plus its serving env. Cell names are fixed, and they are also the output directory names, because `analyze_ext.parse_dir` matches them by prefix and no name may be a prefix of another followed by `_`.

| Cell | Role | Status |
|---|---|---|
| `gptq_w4_d1`, `awq_w4`, `kvq_int8` | Reference cells (main study, calibration c1) | τ² f01–f03 already run in Bank U (U2B rows reused, §2.5); f04–f06 only under phase 2 |
| `gptq_w4_d1`, `awq_w4_d1`, `kvq_int4`, `gptq_w3` | BFCL reference cells | Existing q8 ext dev forks over all 788 eval items; restricted to the 200 panel items (all 4 × 50 present) |
| `quarot_w4` | QuaRot, controlled: random Hadamard R1 + online Hadamards, GPTQ-W4 weights, A16, KV16 (Q/K rotation on, KV unquantized). Same build as the existing closed-loop runs `a6k2_q8_quarot_w4a16kv16r_f0k` | new-method agent |
| `quarot_w16` | QuaRot **transform-path control**: the identical rotated model with W16 (`a6k2_q8_quarot_w16a16kv16r_*`) | new-method agent (required with `quarot_w4`) |
| `spinquant_w4` | SpinQuant, controlled: learned R1/R2 (Cayley optimisation) + the same online Hadamards R3/R4, then the same W4 quantizer as `quarot_w4` (§8) | new-method agent |
| `spinquant_w16` | SpinQuant transform-path control: the learned-rotation model at W16 | new-method agent (required with `spinquant_w4`) |
| `spinqoff_w4` | SpinQuant with the **official default pipeline** (its own calibration set, sample count, rotation-training and quantizer defaults), reported separately and never in a controlled contrast | optional |
| `kivi_k2v2` | KIVI-2: K per-channel, V per-token, 2-bit asymmetric, the paper's group size and full-precision residual window. Weights BF16 | new-method agent (primary KIVI cell) |
| `kivi_k4v4` | KIVI-4 (same settings at 4 bits) | optional, secondary |

The KIVI agent records the exact group size, residual length and hook env in its gate output, before phase 1. If `kivi_k2v2` fails its gate (§2.4), a non-effect criterion, `kivi_k4v4` becomes the primary KIVI cell. That fallback is part of this protocol.

## 2. Panel A: τ² ordinary-state bank on q8

### 2.1 Which sub-bank, and why U2B (BF16-sourced)

The states must be common to every method, so they cannot be defined on any one method's own trajectory.
- **U1 (own-trajectory) and Bank P (first divergence).** Each method selects its own states, so a cross-method difference mixes the action effect with state selection. analyze_ghf already flags every cross-cell Bank P comparison as "descriptive and confounded by state selection".
- **U2Q (Q-sourced).** This sub-bank uses the GPTQ-W4 d1 trajectories. It privileges one quantizer: those are the states GPTQ's errors lead to, GPTQ's own a_Q is the recorded action, and only GPTQ's QQ is the original continuation. It is not neutral between methods.
- **U2B (BF16-sourced) is method-independent.**
  - Every configuration is queried from the identical stored history. Prompt-id identity is checked per state: `Q_prompt_ok` in `bank_u`.
  - a_B is the recorded BF16 action, and **BB is the recorded BF16 continuation, the same for every configuration.** So for any two methods on the same state, D_cc(m1) − D_cc(m2) = Y_QB(m1) − Y_QB(m2). The baseline cancels exactly.
  - For q8 f01–f03 the rows equal Bank U's U2B rows. GPTQ/AWQ/KV8 results on these states already exist, so the new methods are compared with the main study's cells on the same states without new reference runs.
  - The same rule applies unchanged to Mistral's own BF16 trajectories (§9).
- **Limitation, stated with every result.** U2B is the BF16 policy's state distribution. It is not the distribution the quantized agent visits. The estimand is the effect at ordinary states that a BF16 agent reaches. Own-trajectory effects stay in Bank U U1 and Bank P.

### 2.2 Rows (frozen in the manifest)

- Blocks f01–f06: nonces `1d972ae1 d1613e2a 96da6c1a c8a4d627 66d0ff30 fd7b1cd1` (`manifests/fork/dev_blocks_v1.json`).
- Source runs `a6k2_q8_bfpair_<blk>`: all 12 run-domains are admitted in snapshot 20261002T0631Z with 58 + 27 tasks and no infra-missing episodes. The trajectory and decision sha256 are stored in the manifest under `tau2.sources`.
- Task pool: `splits_v1.json` dev, i.e. retail 58 + airline 27 = 85.
- One state per (block, domain, task): t = floor(u × n_decisions), with u = int(sha256("bank-u-v1|run|domain|task")[:12], 16) / 16¹².
  - The draw is uniform within the episode with no stratification. The selection probability 1/n_decisions is recorded.
  - A state whose source fails (missing, abnormal termination, count mismatch) stays as missing and is never replaced. There are 0 missing.
- `phase` = 1 for f01–f03 and 2 for f04–f06. `q0` = false: this panel has no Q0 controller.
- The builder reads only message structure, decision counts and termination reasons. It reads no reward and no fork output.

### 2.3 Arms

These are the `bank_u` mode semantics for U2B (FORK_PROTOCOL §15 amendment 1), unchanged.
- a_Q is generated by the cell's Q server at the stored prompt.
- **All four arms are defined for every state.**
  - BB = the original BF16 continuation. It is re-run and checked for no-op equality on a 10% hash sample (`bank-u-noop-v1|state_key|cell`).
  - When a_Q is token-identical to a_B: QB ≡ BB and BQ ≡ QQ under deterministic protocol A. The reuse is recorded per arm, and the suffix arm (QQ) is always run.
  - Otherwise BQ, QB and QQ are all run.
- Any no-op mismatch quarantines that task's output (§6c of FORK_PROTOCOL).
- An arm error leaves that state's row incomplete. It is never imputed.

### 2.4 Gates (before any panel task of a cell)

1. **`gate_same` with `foreign_states: true`.** B and Q are both this cell on two servers, run on `a6k2_q8_bfpair_f01` retail + airline, with 3 states per domain. Pass requires all of:
   - cross-handle completion ids identical on 8 foreign prompts;
   - the shadow equals a_Q;
   - all four arms identical;
   - budget ok.

   This establishes Q-side determinism and isolation. On U2B states the in-panel no-op only re-checks BB.
2. **`bank_u` gate:** 10 U2B rows of f01, `noop_frac 1.0`, `limit_per_sub 10`. It raises unless there are no errors, nothing missing and every no-op passes.
3. Transform-path controls (`quarot_w16`, `spinquant_w16`) pass the same two gates.

### 2.5 Reference cells

For q8 f01–f03, the analysis reads `analysis/fork/bank_u/q8_{gptq_w4_d1,awq_w4,kvq_int8}/f0k/bank_rows.jsonl`, U2B rows only. A row is admitted only if its `state_key`, `t`, `source_run`, `task_id` and `domain` equal the panel row and the summary's `manifest_sha256` equals the Bank U manifest sha above. If phase 2 runs, the reference cells run f04–f06 with the panel manifest like any other cell.

## 3. Panel B: BFCL multi-turn

- **Items.** For each of base / miss_param / miss_func / long_context, take the `bfcl_mt_v1` eval ids minus the exclusion set, sort by sha256("cloq-nmp-bfcl-v1:" + id), and keep the first 50. That gives 200 items, stratified by category before selection.
- **Exclusion set.** 214 unique ids, listed in the manifest under `bfcl_selection.excluded_ids`. It is the union of:
  - `bfcl_mt_v1` dev (12) and smoke (40; the q4 gate);
  - `bfcl_mt_l8gate_v1` smoke_l8g (20; the l8 gate);
  - `bfcl_mt_l8probe_v1` probe_l8 (100);
  - every BFCL id that appears in any file under `analysis/fork/{ext/gate,ext_q14_gate,ext_l8_gate}/` (116; the q14 gate and gate_same samples, BB no-op items, the l8 gate).

  Pool sizes after exclusion: 152 / 158 / 154 / 122.
- **Arms (fork-ext-v1, unchanged).** Per cell:
  1. One closed-loop Q run `ext_q8_<cell>_bfcl_nmp1` on the four domains with `task_file manifests/fork/newmethod_panel_v1.json`, `subset nmp_v1`.
  2. One `fork_ext` dev task per category (`q_blocks ["ext_q8_<cell>_bfcl_nmp1:bfcl_<cat>"]`, `noop_frac 0.1`). It searches each item for Q's first semantic divergence, runs BB/BQ/QB, and runs a 10% QQ no-op sample (a mismatch quarantines the directory).

  Output goes to `analysis/fork/newmethod/bfcl/bfcl_q8_<cell>_<cat>/`.
- **State selection.** On BFCL the states are each cell's own first-divergence states (fork-ext-v1 has no ordinary-state bank). Cross-method BFCL comparisons are therefore on the **same items** (item-level policy quantities, zero for no divergence), not the same states. They are labelled that way.
- **Admission (analyze_ext, imported).** A directory is quarantined whole if its QQ no-op sample mismatched. The W99o replay-consistency guard (`analyze_ext.replay_guard`) applies to every admitted BFCL directory, new or reference, and a failure stops the analysis.
- **BFCL reference cells.** These are the existing q8 dev forks, restricted to the panel items. Their BF16 closed-loop run `ext_q8_bf16_bfcl_eval` already covers the panel.

## 4. Estimands (frozen)

Y ∈ {0,1}: τ² retail/airline DB success with a normal stop (`fork_driver._y`); BFCL is valid under the official multi-turn checker. Per state, with all four arms present:

| Symbol | Definition | Reading |
|---|---|---|
| G | Y_BQ − Y_QQ (= Δ_Q) | replace only the current action; Q continues |
| H | Y_QB − Y_QQ | replace only the continuation |
| F | Y_BB − Y_QQ | replace both |
| **D_cc** | **Y_QB − Y_BB (= −Δ_B)** | **Q's action vs B's action under the common BF16 continuation** |
| I | Δ_Q − Δ_B = Y_BQ + Y_QB − Y_BB − Y_QQ | interaction (controller dependence of the action effect) |
| r, d, M | r = P(Y_BQ=1, Y_QQ=0), d = P(Y_BQ=0, Y_QQ=1), M = r + d | rescue, damage, outcome changed |
| damage_cc, gain_cc, M_cc | damage_cc = P(Y_BB=1, Y_QB=0), gain_cc = P(Y_BB=0, Y_QB=1), M_cc = damage_cc + gain_cc; D_cc = gain_cc − damage_cc | two-sided common-continuation consequences |

Also reported: the off-diagonal share P(Δ_Q ≠ Δ_B), strict reversals, and the 16 patterns (bit order BB, BQ, QB, QQ).

- **τ² unit = state** (one per task × block).
  - Primary: the task-equal mean over all panel states, i.e. the mean over the 85 tasks within a block, then the mean over blocks. Exact-agreement states enter with their identities (G = 0, D_cc = 0, H as run).
  - Secondary: the same quantities conditional on an action difference (ratio over non-exact states).
- **BFCL unit = item.** For G, r, d, M and D_cc: the all-item mean, with no-divergence items counted as 0. G, H, F, I and D_cc are also reported conditional on divergence.
- **Cross-method contrast on the same states** (τ², the headline): per state, ΔD_cc(m1, m2) = Y_QB(m1) − Y_QB(m2), averaged like the primary. The native-continuation contrast ΔG(m1, m2) = G(m1) − G(m2) is reported beside it. ΔG is labelled "each under its own continuation", so a ΔG that differs from ΔD_cc is attributed to the continuations.

## 5. Expansion rule (phase 2 = f04–f06), effect-blind

Implemented by `make_newmethod_panel.py expansion --model q8 --cells <registered new cells> --write`. It reads only queue status, the `gpus` of each task and these phase-1 summary fields: seconds, n_rows, n_ok, n_missing, n_errors, budget_ok and the no-op counts. It never opens `bank_rows.jsonl`, `branches/` or any analysis output.
1. **When.** Exactly once per model, at the earlier of (a) all phase-1 panel tasks of the registered cells finished, (b) T_decide = **2026-10-03 20:00 PDT** (Mistral: 2026-10-04 00:00 PDT).
2. **Eligible cells.** The gates passed (§2.4) and phase 1 is complete: f01–f03 done, n_errors 0, every no-op passed.
3. **Projected cost.** P = 1.25 × (Σ_eligible phase-1 GPU-h + the reference cells' U2B share of their Bank U f01–f03 task time). The projected wall time is P / 8 GPUs.
4. **Expand iff** now + wall ≤ T_deadline = **2026-10-04 12:00 PDT**. That is 9 h before the 2026-10-05 00:00 Toronto evidence freeze, kept for analysis.
5. **All or none.** If expanding, every eligible cell and the three reference cells run f04–f06. Otherwise no cell does. No cell is ever expanded alone, and cells are never ranked or chosen by preference.
6. The decision record `analysis/fork/newmethod/expansion_q8.json` is written before any phase-2 task is queued. Cells registered after the decision run f01–f03 only.

The BFCL panel has no expansion: 200 items, one run per cell.

## 6. What the method agents queue (existing modes only)

`python scripts/a6000/make_newmethod_panel.py spec --model q8 --cell <cell> [--phase 2]` prints the exact `fork` specs. The agent wraps each spec in a queue task with its own Q role (checkpoint + `serve_env`) and B = `{"ckpt": {"kind": "bf16"}}`.
- q8 forks use 2 GPUs.
- Task ids: `nmp_gate_same_q8_<cell>`, `nmp_gate_bank_q8_<cell>`, `nmp_tau2_q8_<cell>_<blk>` (the expansion rule looks these up by name), `nmp_score_q8_<cell>_<blk>`, `ext_q8_<cell>_bfcl_nmp1`, `nmp_bfcl_q8_<cell>_<cat>`.
- Dependencies: gates → panel tasks → score tasks. Every panel task depends on both gates of its cell.

| Purpose | fork_driver / driver | Key spec fields |
|---|---|---|
| Q determinism gate | `gate_same` | `foreign_states: true`, `q_blocks ["a6k2_q8_bfpair_f01:retail", "…:airline"]`, `n_per_block 3`, out `analysis/fork/newmethod/gate/q8_<cell>/same` |
| Bank gate | `bank_u` | manifest + `manifest_sha256` (above), `subs ["U2B"]`, `blocks ["f01"]`, `limit_per_sub 10`, `noop_frac 1.0`, out `…/gate/q8_<cell>/bank` |
| Panel A | `bank_u` | `subs ["U2B"]`, `blocks [<blk>]`, `noop_frac 0.1`, `concurrency 8`, out `analysis/fork/newmethod/tau2/q8_<cell>/<blk>` |
| Local fidelity (KL) | `driver: score`, `mode score_states` | `bank_out` = the panel output dir, out `analysis/fork/newmethod/token_scores/q8_<cell>/<blk>` |
| Panel B run | eval task, `env bfcl` | `task_file manifests/fork/newmethod_panel_v1.json`, `subset nmp_v1`, run id `ext_q8_<cell>_bfcl_nmp1` |
| Panel B forks | `scripts/ext/fork_ext.py` mode `dev` | `q_blocks ["ext_q8_<cell>_bfcl_nmp1:bfcl_<cat>"]`, `noop_frac 0.1`, out `analysis/fork/newmethod/bfcl/bfcl_q8_<cell>_<cat>` |

**fork_driver changes needed: none.** `bank_u` takes any manifest in the Bank U row schema. Its U2B branch does not depend on the cell name: the `src_cell` logic applies to U2Q only. `cell` is used only as a label and in the no-op hash. `score_driver` takes any `bank_out`. The worker must serve the Q role exactly as in closed loop; that is checked by gate 1 and by `Q_prompt_ok` on every state.

## 7. Inference, multiplicity, reporting

- **τ² intervals** (analyze_dev `Boot`, imported; B = 2000, seed 20261001):
  - **primary**: t over the k block means (df k − 1; k = 3 or 6 < 10 blocks, W63 rule);
  - the block bootstrap is reported alongside and flagged when it disagrees;
  - **secondary**: the crossed task × block bootstrap, for generalisation to new tasks.
  - Strict blocks (W70): a block enters a cell only if all 85 of its states have four arms. Otherwise the block is dropped for that cell with the reason recorded. A complete-case sensitivity is reported, labelled.
  - Cross-cell contrasts use the blocks complete in both cells.
- **BFCL intervals:** item bootstrap within category (`analyze_ext.StratBoot`, imported; B = 2000, seed 20261001). The draws are shared by all cells, so item-paired contrasts are valid. They describe item sampling only.
- **Primary contrast family (Holm, two-sided α = .05, τ² D_cc, t over block-mean differences):**
  - P1 quarot_w4 − gptq_w4_d1;
  - P2 spinquant_w4 − quarot_w4;
  - P3 kivi_k2v2 (or its gate fallback) − kvq_int8.

  The same three contrasts on BFCL item-level D_cc_all form a second Holm family, reported separately.
- **Everything else is reported per cell with intervals and no claim family:** G, H, F, D_cc, I, r, d, M, the conditional forms, the transform-adjusted contrasts (quarot_w4 − quarot_w16, spinquant_w4 − spinquant_w16), `spinqoff_w4`, and the KIVI secondary.
- **Equivalence wording.** "No difference" may be claimed only when the 95% interval lies within ±3 pp (g_min). Non-significance is never reported as equivalence.
- **Reporting.** Every registered cell is reported, whether the result is positive, negative or inconclusive, including gate failures (as "not admitted", with the reason). The expansion decision is reported with its inputs.

## 8. Controlled comparison: SpinQuant vs QuaRot

The controlled pair differs only in how R1/R2 are obtained (random Hadamard vs learned).
- **Calibration data.** One frozen set for both rotation learning and GPTQ: WikiText-2 raw train, 128 × 2048 tokens, `random.seed(0)`, the set the existing `quarot_w4` build uses (`cloq/quarot.py`; sha256 recorded in its build meta). SpinQuant's rotation optimisation uses this set, not its default 800 samples.
- **Weight grid and clipping.** GPTQ, per-channel symmetric W4, MSE clip search (norm 2.4, grid 100, maxshrink 0.8), percdamp 0.01, no act-order, the same sequential order. These are the existing QuaRot parameters (METHOD_FIDELITY §5).
- **Online transforms.** The same R3/R4 Hadamards (`CLOQ_AQ_HAD quarot`), the same fused norms.
- **KV.** Both run at KV16 with the same Q/K rotation flag (`CLOQ_KVQ_ROT qk`) and the same hook env as `a6k2_q8_quarot_w4a16kv16r_*`. Activations at 16 bits.
- **Transform-path controls.** `quarot_w16` and `spinquant_w16` (rotation applied, no quantization). They separate the effect of the rotation path, i.e. BF16 rounding through the rotated basis, from the effect of quantization. They run on the same panels with the same gates.
- **Official default pipeline.** `spinqoff_w4` (optional) uses SpinQuant's released defaults and is reported in its own row, labelled "official default, not controlled". QuaRot's official pipeline is already what `quarot_w4` uses (WikiText-2 128 × 2048).
- **Confounds named in the write-up.** quarot_w4 − gptq_w4_d1 (P1) differs in both the rotation and the calibration data: GPTQ-W4 d1 uses the τ² BF16 calibration trajectories (`calib_fp_traj_c1`). It is therefore read as "QuaRot pipeline vs the main study's GPTQ cell", not as the effect of rotation alone. The rotation-alone reading comes from the transform-adjusted contrast and the W16 control.

## 9. Local fidelity (measured alongside; not assumed to predict outcomes)

- **τ², per state.**
  - Exact token agreement of a_Q with a_B, and the semantic category (`agreement_category`).
  - From the score driver, teacher-forced on **a_B**, so every cell is scored on the same tokens:
    - KLu_0 (first action token) and KLu_mean (mean over a_B tokens) of KLu(B‖Q), the top-20-union KL with a tail bucket (not the full KL);
    - the fraction of a_B tokens that are Q's argmax;
    - the mean log-probability Q assigns to a_B.
- **BFCL.** Divergence rate, first-divergence position t*, divergence category. KL is not measured on BFCL: there is no ext score mode, and none is required.
- **Analysis (descriptive only).**
  - Per cell: the fidelity distribution.
  - M, M_cc and |D_cc| by agreement class and by KLu_mean tertile. The tertile cut points come from the KL values alone, pooled over all admitted cells' phase-1 states.
  - Across cells: the rank order of mean KLu next to the rank order of M_cc, with a Spearman ρ that is labelled descriptive (n = number of cells).

  No statement that fidelity predicts outcomes is made unless an interval excludes zero, and even then it is labelled exploratory.

## 10. Mistral (second family)

- The panel rules are model-agnostic. Mistral runs its BF16 closed-loop runs on the same six nonces with `manifests/eval_tasks_v0.json`, which gives the same 85-task retail/airline pool, under the run ids `a6k2_<m>_bfpair_f01…f06`. `<m>` is the models.json key; the expected key is `m24`, and another key is used as is.
- Once those runs are admitted in an integrity snapshot, the Mistral agent runs:

  ```
  make_newmethod_panel.py build --model <m> --snapshot <that snapshot>
  ```

  This writes `manifests/fork/newmethod_panel_v1_<m>.json`: the same row rule, the same BFCL ids, its own sha. The agent then records that sha in a dated amendment here before any Mistral panel task.
- Mistral cells are named by the Mistral agent and follow §2.4 (gates), §5 (its own expansion record, `expansion_<m>.json`, T_decide 2026-10-04 00:00 PDT, same deadline) and §7. They are never pooled with q8.
- BFCL applies only if Mistral's BF16 clears the capability floor that failed l8 (W99f). That is checked on the closed-loop BF16 panel run before any fork: BF16 success ≥ 10% on the 200 items. Otherwise BFCL is reported as "at floor; not forked". The criterion is an outcome of BF16 alone and makes no reference to Q or to any effect.

## 11. Guards

- Every panel task carries `manifest_sha256`, and `bank_u` refuses a mismatch.
- `analyze_newmethod.py` checks this protocol's sha and the manifest sha, and refuses to run on a mismatch.
- Phase-2 rows are analysed only if `expansion_q8.json` says `expand: true`. Otherwise their outputs are refused.
- Holdout data (`analysis/fork/holdout/`, the telecom split) is out of scope and never opened.
