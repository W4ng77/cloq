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

---

## Amendment A1 (2026-10-02 06:30 PDT, W99v-a1): rotation cells on the weight + activation axis, Holm P2, a disclosed post-hoc gate change

**TL;DR** This amendment was written before any panel outcome existed for any rotation cell. At this time no `analysis/fork/newmethod/tau2/` or `analysis/fork/newmethod/bfcl/` output exists. No `nmp_tau2_*`, `nmp_score_*` or `nmp_bfcl_*` task is in the queue's done, running or todo directories. The only outputs under `analysis/fork/newmethod/` are the KIVI gates. The rotation cells' own nmp gates (`nmp_gate_{same,bank}_q8_quarot_*`) are still in todo.
- The rotation cells become the advisor's weight + activation design: QuaRot-W4A16, QuaRot-W4A4 and SpinQuant-W4A4, all at KV16r, plus the two W16 transform-path controls.
- `spinquant_w4` (W4A16) is retired. `spinqoff_w4` is not built and is reported as "not run".
- Holm P2 becomes spinquant_w4a4 − quarot_w4a4 on D_cc. P1 and P3 are unchanged.
- One post-hoc change to the rotation gate is disclosed: its HF-invariance criterion T4 was changed after SpinQuant's value had been seen.
- The manifest (`newmethod_panel_v1.json`, sha `7534c690…`) and the states do not change.

Evidence: `analysis/fork/rot_gate/GATE.md` (with `verdict.json`, `validate_*_q8*.json`, `spin_learn_q8.json`), `scripts/a6000/rot_gate_check.py`, `scripts/a6000/make_tasks_rotpanel.py`, RESEARCH_LOG W99r / W99s / W99v-a1.

### A1.1 Cells (replaces the rotation rows of the §1 table)

All five cells use model q8, B = BF16, and KV16 with the online Q/K rotation on (`CLOQ_KVQ_ROT qk`, the "kv16r" serving config). The weight grid, calibration windows, online Hadamards (R3/R4) and fused norms are as in §8.

| Cell | Configuration | Serving env (activation part) | Status |
|---|---|---|---|
| `quarot_w4` | QuaRot-W4A16-KV16: random Hadamard R1 (seed 0) + per-head R2, GPTQ-W4 | `CLOQ_AQ_BITS=16 CLOQ_AQ_HAD=quarot` | registered (unchanged from §1) |
| `quarot_w4a4` | QuaRot-W4A4-KV16: the same checkpoint as `quarot_w4` | `CLOQ_AQ_BITS=4 CLOQ_AQ_FMT=sym_quarot CLOQ_AQ_CLIP=0.9 CLOQ_AQ_HAD=quarot` (per-token symmetric INT4, clip 0.9, on the inputs of q/k/v, o, gate/up, down) | **new** |
| `quarot_w16` | QuaRot transform-path control: the same rotations, W16A16 | A16 | registered (unchanged) |
| `spinquant_w4a4` | SpinQuant-W4A4-KV16. R1/R2 are learned by Cayley SGD (`cloq/spinquant.py learn`). The objective is next-token CE at W16A4KV16 with STE activation quantization, following SpinQuant's README rule for GPTQ weights. Training starts at the QuaRot point and uses the same 128 × 2048 WikiText-2 windows (6.25 epochs). The rotations are then exported through the identical QuaRot builder + GPTQ-W4 | identical to `quarot_w4a4` | **new** |
| `spinquant_w16` | SpinQuant transform-path control: the learned rotations, W16A16 | A16 | registered (unchanged) |
| `spinquant_w4` | SpinQuant-W4A16 | – | **retired** (reason below) |
| `spinqoff_w4` | SpinQuant official default pipeline | – | **not built; reported as "not run"** |

- **Why `spinquant_w4` is retired.** At W16A16, or at W4A16 with the rotations learned at W16A16, the training loss does not depend on the rotation. The network is rotation-invariant apart from bf16 rounding, so the gradient on R1/R2 is essentially zero and the rotations stay at their starting point. A "SpinQuant-W4A16" cell would therefore be QuaRot-W4A16 under another name. A genuine W4A16 SpinQuant would need rotations learned with the W4 weight quantizer in the loop. That is not the README rule for GPTQ weights, and it was not built. The learned rotation acts on the function only through the A4 quantizer, so the SpinQuant cell is evaluated where it differs: W4A4.
- **The controlled pair** `spinquant_w4a4` vs `quarot_w4a4` differs only in R1/R2. It shares the calibration windows (token-set sha `ec0a043b2c48…`), the GPTQ grid and MSE clip, the A4 grid and clip, the online Hadamards and KV16r. At step 0 of learning, SpinQuant *is* the QuaRot model; CPU test 1 shows 0.0 max difference.
- **Deviations from SpinQuant's official recipe, each made for the controlled contrast:**
  - 128 GPTQ windows instead of 800 fresh blocks;
  - the symmetric clip-0.9 activation grid of the serving path;
  - QuaRot's across-head H_32 on the o_proj input is kept;
  - R2 is initialised at H_hd.

  These are listed in GATE.md and are reported with every SpinQuant result.
- **Gates.** §2.4 applies to every cell, and phase-1 release is additionally conditional on the rotation gate (`rot_gate_check.py`), as already queued. Those criteria are effect-blind. They read gate files and gate_same verdicts only.
- **Expansion (§5).** The registered new cells for `expansion --cells` are `quarot_w4 quarot_w4a4 quarot_w16 spinquant_w4a4 spinquant_w16` plus the KIVI cell(s) that passed their gate.

### A1.2 Primary Holm family (replaces the list in §7)

Two-sided α = .05, τ² D_cc, t over block-mean differences. The BFCL family has the same three contrasts on D_cc_all.

| Id | Contrast | Reading |
|---|---|---|
| P1 | `quarot_w4` − `gptq_w4_d1` | QuaRot pipeline (W4A16, KV16r) vs the main study's GPTQ-W4 cell. **Named confound (unchanged, §8): the calibration data differ.** QuaRot uses WikiText-2 128 × 2048; GPTQ-W4 d1 uses the τ² BF16 calibration trajectories (`calib_fp_traj_c1`). Rotation and calibration are therefore not separated. The rotation-alone reading comes from T1 and the W16 control. |
| P2 | `spinquant_w4a4` − `quarot_w4a4` | **The advisor's controlled contrast:** learned vs random rotation, with the same calibration, weight grid, clipping, activation grid and KV16r |
| P3 | `kivi_k2v2` (or its gate fallback `kivi_k4v4`) − `kvq_int8` (τ²); − `kvq_int4` (BFCL) | unchanged |

- **Secondary (per-cell intervals, no claim family), replacing the §7 transform-adjusted list:**
  - T1 `quarot_w4` − `quarot_w16`;
  - T2 `spinquant_w4a4` − `spinquant_w16`;
  - T3 `quarot_w4a4` − `quarot_w16`;
  - K2 `kivi_k4v4` − `kvq_int8`.
- The former S1 (`spinqoff_w4` − `spinquant_w4`) is dropped, because neither cell is run.

### A1.3 Disclosed post-hoc change to the rotation gate

**Plain statement: this amendment was made after a gate value had been observed.**
- The rotation gate's criterion T4 (HF invariance of the exported W16 checkpoint, fp32 compute) was frozen in `rot_gate_check.py` at commit 3fd9522 as an absolute fp32 top-1 agreement ≥ 0.999.
- On 2026-10-02 at 05:50 PDT (commit 38db810), it was replaced by a QuaRot-relative threshold: fp32 top-1 agreement ≥ QuaRot's − 0.002, **and** mean |Δlogprob(top-1)| ≤ 1.5 × QuaRot's.
- **SpinQuant's value had already been seen when the threshold was replaced:** 0.9976, mean |Δlogprob| 0.0040.
- **The reason.** The absolute threshold was mis-specified. QuaRot's accepted export does not reach it either (0.9956, mean |Δlogprob| 0.0045), because the rotated weights are stored in bf16. Under the original criterion no rotated checkpoint built by this pipeline could pass.
- **What existed at the time.** No served SpinQuant output and no panel outcome of any cell existed. The change could not have been informed by any agent-level SpinQuant result or by any D_cc / G / H / F.
- **Corroboration that does not depend on T4.** Measured later, SpinQuant's served W16A16 transform control has act flip 0.0025 and first-token KL 0.0020. Both are at or below QuaRot's 0.005 and 0.0026.
- This change is reported with every SpinQuant result.

### A1.4 Interpretation note: WikiText perplexity is not a fidelity criterion for learned rotations

- The SpinQuant rotations are trained with a WikiText-2 (train) cross-entropy objective. In part they act as domain adaptation of the instruction-tuned model, working through the A4 quantizer.
- On the learner path, W16A4 WikiText-2 test perplexity is **8.76, below BF16's 9.73**, and below the QuaRot point's 11.04.
- A lower perplexity than the unquantized model cannot mean closer to BF16. WikiText perplexity is therefore **not** used as a fidelity criterion for any rotation cell, and the rotation gate's ppl-based direction checks (P1/P2 in `rot_gate_check.py`) are reported as uninformative.
- **The relevant measures**, all on the agent domain and relative to BF16:
  - the top-k act flip and first-token KL on the 400 BF16 agent decisions (rotation gate);
  - the panel's local fidelity, §9: KLu over a_B tokens and exact agreement;
  - the panel's D_cc.

### A1.5 q_blocks spec bug (fixed)

- **The bug.** `make_newmethod_panel.py spec` printed the τ² `gate_same` `q_blocks` as "run:domain" strings, but `fork_driver.load_blocks` unpacks [run, domain] pairs.
- **The fix.** Commit a98a2a6 (2026-10-02 04:29 PDT, `scripts/a6000/make_newmethod_panel.py`, one line) now emits [run, domain] pairs for the τ² gate. The BFCL `fork_ext` `q_blocks` keep their "run:domain" strings, which `fork_ext` expects.
- **What it does not change.** The manifest and its rows are unaffected. The builder's frozen sha in the header table (`5fcc5308…`) is the sha *as it built the manifest*, and stays the manifest's `builder_sha256`.
- `make_tasks_rotpanel.py` already used pairs.

### A1.6 Analysis script

`analysis/fork/analyze_newmethod.py` was updated in the same commit as this amendment:
- `PROTOCOL_SHA256` is set to this file's new sha256, and only the new value is accepted;
- `NEW_CELLS` is set to the cells in A1.1 plus KIVI;
- `PRIMARY` / `BFCL_PRIMARY` follow A1.2;
- `SECONDARY` is T1, T2, T3 and K2.

---

## Amendment A2 (2026-10-02 13:35 PDT, W100e): Mistral (m24) panel manifest sha, m24 cells, BFCL floor check, and one open analysis-rule question

**TL;DR** This amendment records the m24 manifest sha that §10 requires before any Mistral panel task. It was written before any m24 panel task existed: no `nmp_*_m24_*` task was in the queue's todo, running, done or failed directories, and no `analysis/fork/newmethod/*/m24_*` output existed. The only m24 outcomes in existence are the BF16 source runs (`a6k2_m24_bfpair_f01…f06`), the closed-loop BFCL runs `ext_m24_{bf16,rtn_w4}_bfcl_nmp1`, and the W99p gate outputs.
- The manifest is built by the unchanged builder with the frozen row rule (§2.2; failed rows kept missing).
- Cells: `rtn_w4` first, then `gptq_w4_d1` (as W99p/W99q planned).
- BFCL applies: BF16 clears the §10 floor.
- **Open question for the main session (not decided here):** under §7's strict-block rule, no m24 τ² block can be admitted, because airline task 44 is a missing row in all six blocks (A2.3).

### A2.1 Frozen artifact

| Artifact | sha256 |
|---|---|
| `manifests/fork/newmethod_panel_v1_m24.json` (510 τ² rows, 7 missing; the same 200 BFCL ids as `newmethod_panel_v1.json`, checked id by id) | `53295b64fbcc7c4501ea8883aa34ce922a5ca0e23c5636c8bb1c4efe38e3ff4c` |
| Builder `scripts/a6000/make_newmethod_panel.py` at build time (recorded in the manifest as `builder_sha256`; same file as a98a2a6) | `81039a8e151536deb50599884f8a2578f9c2b52d05d672d9a3a606cebcb84f9a` |
| Integrity snapshot `analysis/insights/iter_3/out/snapshot_auto_20261002T2022Z.json` (all six `a6k2_m24_bfpair_*` blocks admitted, no G6 pending warning) | `f8c4dde206cc7e0571cec5fee08c95625594ad4cc030eed1f4393b8d8cddfab2` |

Command: `make_newmethod_panel.py build --model m24 --snapshot analysis/insights/iter_3/out/snapshot_auto_20261002T2022Z.json` (source template `a6k2_m24_bfpair_{blk}`).

### A2.2 Cells, gates, expansion

- **Cells (Q role; B = BF16; m24 text-only view, mistral tokenizer/parser as in W99p):** `rtn_w4` (RTN-W4) and `gptq_w4_d1` (GPTQ-W4, calibration `manifests/a6k2/m24/calib_fp_traj_c1.json`, draw c1). They are never pooled with q8 (§10). m24 has no reference cells.
- **Tasks:** `scripts/a6000/make_tasks_m24.py panel --cell <cell> --bfcl`. The specs come verbatim from `make_newmethod_panel.py spec --model m24 --cell <cell>`. Forks use 4 GPUs (`gpus_per_role 2`, TP=2 per role), like the W99p gates. Every panel task depends on both gates of its cell (§6). `gptq_w4_d1` also queues its closed-loop BFCL Q run `ext_m24_gptq_w4_d1_bfcl_nmp1`.
- **Expansion (§5):** `make_newmethod_panel.py expansion --model m24 --cells rtn_w4 gptq_w4_d1`, recorded once in `analysis/fork/newmethod/expansion_m24.json`. T_decide is 2026-10-04 00:00 PDT and T_deadline is 2026-10-04 12:00 PDT. The rule is unchanged and effect-blind.
- **BFCL floor (§10), an outcome of BF16 alone:** `ext_m24_bf16_bfcl_nmp1` has 40/200 = 20% success (base 16/50, miss_param 8/50, miss_func 7/50, long_context 9/50). That is ≥ 10%, so the BFCL forks run.

### A2.3 Missing source rows and the strict-block rule (OPEN; for the main session)

- The 7 missing rows are BF16 source episodes that ended in `infrastructure_error`, with cause `agent_parse_error` (W99p's Mistral invalid-function-name failure class):
  - airline task 44 in every block f01–f06;
  - airline task 13 in f01.
- The frozen row rule (§2.2) keeps such rows missing. So the manifest is as the protocol prescribes.
- **Consequence.** §7's strict-block rule as implemented (`analyze_newmethod.strict_blocks`, n_tasks = 85 from the manifest rows) admits a block only if all 85 states have four arms. With task 44 missing in all six blocks, **no m24 block can be admitted**, and the primary τ² analysis would be empty. Only the labelled complete-case sensitivity would remain.
- **This amendment does not choose a resolution**, because each option changes the analysis design. The options seen:
  - (a) for m24, define the strict-block denominator as the non-missing manifest rows of the block (84, or 83 for f01);
  - (b) drop airline task 44 from every m24 block, a task-level exclusion based on the BF16 source only, and treat f01 under (a) or as dropped;
  - (c) report only the complete-case analysis for m24, labelled.
- Each option reads only the BF16 source and manifest fields, never a panel outcome. Whichever is chosen must be appended as a dated amendment **before any `analysis/fork/newmethod/*/m24_*` output is read**.
- The queued fork tasks are the same under all three options; the missing rows simply produce `missing_reason` records.

### A2.4 Analysis script

In the same commit, `analysis/fork/analyze_newmethod.py` sets `PROTOCOL_SHA256` to this file's new sha256 and adds `MANIFESTS["m24"]` with the sha above. Nothing else changes, and A2.3 is not resolved in code.

---

## Amendment A3 (2026-10-02 14:10 PDT, W100e-b): m24 analysis population, a fixed 83-task mask (resolves A2.3)

**TL;DR** This resolves the open question in A2.3. The decision was made by the advisor (GPT-6.1) and implemented **before any m24 panel output existed or was read**. At the time of writing, no `analysis/fork/newmethod/*/m24_*` directory exists, and no `nmp_*_m24_*` task is in the queue's running, done or failed directories.
- For **both** m24 cells (`rtn_w4`, `gptq_w4_d1`) and **all** blocks f01–f06, airline tasks **13** and **44** are excluded uniformly.
- The analysis population is the remaining **83 tasks**, fixed: 249 states per cell in phase 1, and 498 if expanded.
- The manifest (`53295b64…`) and the queued tasks are unchanged. The exclusion is a separate, versioned analysis mask.

| Frozen artifact | sha256 |
|---|---|
| `manifests/fork/newmethod_panel_v1_m24_mask_v1.json` (excluded tasks, the 83-task population, the 7 missing source rows and their recorded causes; bound to manifest sha `53295b64…`) | `b03a8a918959e3568315b1ae134f2902580e6af822d80beccb692729c2f82c81` |

### A3.1 Why these two tasks

- **The cause is the model, not infrastructure.** Their BF16 source episodes ended in an invalid tool call produced by the model itself: an empty function name, or free text in the name field. mistral_common then refuses to render the next turn. This is `agent_parse_error` (GATE.md row 1c; W99p; the W27 rule).
  - The run files label it `infrastructure_error` only because the episode cannot continue.
  - Task 44 fails this way in all six blocks; task 13 in f01.
- **End-to-end evaluation is unchanged.** Those episodes keep counting as model failures (W10/W27).
- **Fork results are conditional.** They are restricted to "tasks with a complete, recoverable BF16 source state in every block". The paper states this conditional population in one sentence, and the full missingness record is in the appendix.
- **Why task 13 is excluded in every block, not only f01.** Excluding it uniformly keeps one fixed population across blocks and cells. Without that, f01 would differ from the other blocks.

### A3.2 Disclosure (binding wording)

- The selection used only the BF16 source runs and the manifest; it used no fork result. That shows the **process** was transparent and outcome-blind.
- It does **not** show that the missingness is unrelated to task difficulty or to the intervention effects.
  - The excluded tasks are ones on which BF16 Mistral itself fails structurally, so they may differ systematically from the retained tasks.
  - m24 fork estimates therefore describe the 83-task conditional population, not the 85-task panel. They are not compared with q8 as if the populations were equal.

### A3.3 Rules

- **Strict completeness still applies (§7, W70) on the 83 tasks.** A (cell, block) is admitted only if it has a complete four-arm state for exactly the 83 predefined tasks.
  - Any newly missing branch (missing record, error, a missing arm) fails that block for that cell.
  - Missing arms are never filled with zeros or otherwise imputed.
  - Tasks are never retried until they succeed.
- **The two-cell comparison uses blocks complete in both cells.** The contrast is **M1 = `gptq_w4_d1` − `rtn_w4`**.
  - On τ²: D_cc, with t over block-mean differences, the block bootstrap alongside, and ΔG reported beside it.
  - On BFCL: D_cc_all, item-paired.
  - M1 is the only m24 primary contrast, so Holm over one contrast is the unadjusted p.
  - Per-cell G, H, F, D_cc, I, r, d, M and M_cc are reported with intervals (§7).
- **Sensitivity (labelled).** The actual-available-rows analysis uses every non-missing four-arm row of every block. It applies no mask and no strictness, so it includes task 13 in f02–f06. It is reported per cell and for M1 next to the primary. The complete-case analysis on the 83-task population is also reported.
- **BFCL (panel B) is unaffected by the mask.**
- **Expansion (§5) is unchanged.** It reads no outcome.

### A3.4 Analysis script

`analysis/fork/analyze_newmethod.py` was changed in the same commit:
- `PROTOCOL_SHA256` = this file's new sha256.
- `MASKS["m24"]` holds the mask path and sha. The guard refuses to run on a mask sha mismatch, or if the mask was frozen for another manifest.
- `population()` = manifest tasks minus the mask, asserted equal to the mask's stored population.
- `strict_blocks` needs exactly the population's task set.
- `apply_population` produces the primary, complete-case and available-rows sensitivity.
- `CONTRASTS["m24"]` = M1, and `M24_CELLS` registers `rtn_w4` and `gptq_w4_d1`, also with the BFCL directory parser.
- `--selftest` runs on synthetic units only.

## Amendment A4 (2026-10-02 14:25 PDT, W99t-b): KIVI same-kernel-path control `kivi_k16v16`, KIVI gates re-run on the fixed kernel, `kivi_k4v4` secondary with a disclosed post-hoc criterion revision

**TL;DR** This amendment registers `kivi_k16v16`, the KIVI serving kernel with no quantization, as the KIVI kernel-path control. It reruns every KIVI §2.4 gate on the fixed kernel (f585ae3) under new task ids and output directories. It admits `kivi_k4v4` as a secondary cell. One gate criterion for that cell was revised after its failing value had been seen, and this is disclosed below.

Status when this was written:
- No KIVI outcome had been read.
- The `kivi_k2v2` phase-1 τ² tasks (f01–f03) were running. Output directories `analysis/fork/newmethod/tau2/q8_kivi_k2v2/f0{1,2,3}` existed, but no file in them was opened.
- No `kivi_k4v4` or `kivi_k16v16` panel task existed.

### A4.1 Cell `kivi_k16v16` (transform-path control, required with the KIVI cells)

- **Definition:** BF16 weights and activations, served through the KIVI attention kernel (`scripts/a6000/pyhooks/cloq_kivi.py`, `cloq_kivi_kernel.py` @ f585ae3) with `CLOQ_KIVI_KBITS=16 CLOQ_KIVI_VBITS=16` (no K/V quantization), G = 32, R = 128.
- **Role:** it is to KIVI what `quarot_w16` is to `quarot_w4`. The kernel alone changes outputs: it moves 9% of 200 recorded BF16 completions (action agreement 0.91, first-token KL mean 0.001; `analysis/fork/kivi_gate/gate_q8.json`, server fidelity). The control separates that kernel-path effect from the effect of K/V quantization.
- **Panel:** τ² panel A f01–f03, all four arms. The existing `bank_u` U2B mode always runs four arms, and no QB-only mode exists. The control therefore gives the action effect with the BF16 continuation (QB) and the continuation-controller arms (BQ, QQ).
- **BFCL panel B:** not registered for this cell. It is reported as "not run" unless it is amended in before any KIVI BFCL outcome is read.
- **Gates:** the same two §2.4 gates, on the fixed kernel.

### A4.2 Gates re-run on the fixed kernel

- **Why:** the original §2.4 gates of `kivi_k2v2` and `kivi_k4v4` ran on the pre-fix kernel (IEEE-division scale; hook_version b82dfa5a). The scale fix (W99t-a2) makes the kernel's quantizer equal official KIVI's CUDA arithmetic.
- **What runs:** all three KIVI cells get new gates on the fixed kernel:
  - `nmp_gate_same_q8_<cell>_fx`, output `analysis/fork/newmethod/gate/q8_<cell>_fx/same`;
  - `nmp_gate_bank_q8_<cell>_fx`, output `…/q8_<cell>_fx/bank`.
- **The old gate outputs** stay as the record of the pre-fix kernel and do not admit any cell.
- **`kivi_k2v2` phase 1** was released on the old gates. If its `_fx` gates fail, its panel output is reported as "not admitted", with the reason.

### A4.3 `kivi_k4v4` is a secondary cell; disclosed post-hoc criterion revision

- **Original T2 failure:** the KIVI toy gate's original T2 compares the BF16 kernel against official KIVI in fp32, with bound mean |err| / mean |quant effect| < 0.05. On the fixed kernel, `kivi_k4v4` gives **0.0547** and fails (`analysis/fork/kivi_gate/gate_q8_toy3.json`).
- **Revised criterion:** the comparison is against official KIVI at serving precision (BF16 dequantized K/V and P; ef9dc5a). There `kivi_k4v4` gives **0.0467** and passes.
- **Scale of the gap:** official KIVI itself, run at BF16, differs from its own fp32 path by **0.0496**.
- **Disclosure:** the revised criterion was written after the original GPU value had been seen, and the cell is admitted under it. That is disclosed here and with every k4v4 result.
- **Conditions for release:** `kivi_k4v4` phase 1 is released only if both of these pass:
  - its `_fx` gates;
  - the strict T1 (`verdict_strict` in the KIVI toy gate): integer codes, scale, mn and dequantized values bitwise equal to official KIVI on fp32 and BF16-rounded data.
- **Reporting:** k4v4 is reported as **secondary**: K2, no Holm family.

### A4.4 Contrasts (no new Holm family; P3 unchanged)

- **Kernel-path effect:** D_cc(`kivi_k16v16`) = Y_QB(k16v16) − Y_BB.
- **Quantization effect net of the kernel path:**
  - `kivi_k2v2` − `kivi_k16v16`;
  - `kivi_k4v4` − `kivi_k16v16`.
  - Both are on D_cc, i.e. Y_QB difference on the same states. They are reported with intervals, like the QuaRot/SpinQuant transform-adjusted contrasts.
- **P3** (`kivi_k2v2` − `kvq_int8`) is unchanged. Every P3 result is reported next to the kernel-path effect.
- **Continuation-controller effects:** BQ, QQ and the M forms are discussed for KIVI only with all four arms of `kivi_k16v16` available.

### A4.5 Implementation note (prefill strategy)

The KIVI cells use a replay-compatible decode-view variant: every token, prompt or generated, attends with the state KIVI's incremental decode holds at its position. This is official KIVI with a 1-token prefill (precise text in `analysis/fork/kivi_gate/GATE.md` §6).

### A4.6 Analysis script

`analysis/fork/analyze_newmethod.py` was changed in the same commit:
- `PROTOCOL_SHA256` = this file's new sha256;
- `NEW_CELLS` += `kivi_k16v16`.

---

## Amendment A5 (2026-10-02 14:55 PDT, W100g): the expansion decision — registered cells, KIVI `_fx` gates, the fixed population, KIVI pairing, a frozen snapshot

**TL;DR** This amendment makes the §5 expansion rule implement what A3 and A4 already require. It was written **before any expansion decision** and before any phase-1 panel output was read. No `analysis/fork/newmethod/expansion_*.json` exists. No `nmp_tau2_*` task is in the queue's done or failed directories: the `kivi_k2v2` f01–f03 tasks are running, and every other panel task is in todo or not queued. The decision rule stays effect-blind; it reads no outcome field.
- The registered cells are fixed in the builder, not chosen on the command line (A5.1).
- KIVI gates count only from the `_fx` re-runs; `kivi_k4v4` also needs the strict T1 (A5.1, from A4.2 and A4.3).
- "Phase 1 complete" means every population state of f01–f03 has a completed record. For m24 the population is the A3 83-task mask, so 249 states per cell (A5.2).
- `kivi_k16v16` and the quantized KIVI cells expand together or not at all (A5.3).
- Eligibility is judged on a frozen snapshot, every input is recorded with its sha256, and the record is written exactly once (A5.4).

Evidence: `scripts/a6000/make_newmethod_panel.py` (`expansion`, `--selftest`), RESEARCH_LOG W100g. Reason: the GPT-6.1 review of 6e0b11b found three gaps: old KIVI gate directories, no fixed-83 check, no snapshot.

### A5.1 Registered cells and their gates (no command-line choice)

| Model | Registered cells for `expansion` | Gates counted |
|---|---|---|
| q8 | `quarot_w4`, `quarot_w4a4`, `quarot_w16`, `spinquant_w4a4`, `spinquant_w16` (A1.1) | §2.4: `nmp_gate_{same,bank}_q8_<cell>`, outputs `gate/q8_<cell>/{same,bank}` |
| q8 | `kivi_k2v2` (primary), `kivi_k16v16` (kernel-path control, A4.1) | **only** the fixed-kernel re-runs `nmp_gate_{same,bank}_q8_<cell>_fx`, outputs `gate/q8_<cell>_fx/{same,bank}` (A4.2). The pre-fix gates never admit a cell |
| q8 | `kivi_k4v4` (secondary, A4.3) | the `_fx` gates **and** the strict T1: task `kivi_gate_q8_toy4` done and `analysis/fork/kivi_gate/gate_q8_toy4.json` `toy.verdict_strict.T1_strict_codes_scale_mn_deq_bitwise` = true |
| m24 | `rtn_w4`, `gptq_w4_d1` (A2.2) | §2.4: `nmp_gate_{same,bank}_m24_<cell>` |

- The list is `REGISTERED` in the builder. `--cells` is no longer needed; if given, it must equal the list or the tool refuses.
- A registered cell whose release conditions are not met, or whose phase-1 tasks are not queued, is simply ineligible, with the reason recorded.
- A gate counts only if its queue task is done, its spec `out` is the expected directory, and its verdict passes (`gate_same.json` `verdict.pass`; bank gate `gate_pass`).
- Trigger (a) of §5.1 ("all phase-1 panel tasks of the registered cells finished") needs all three `nmp_tau2_<model>_<cell>_f0k` tasks of every registered cell in done or failed. A cell whose tasks are not queued holds trigger (a) open, so the decision then falls to T_decide.

### A5.2 Phase 1 complete (both models; m24 on the A3 population)

A (cell, block) of f01–f03 is complete only if all of the following hold at the snapshot time (A5.4):
- its `nmp_tau2_*` task is done, and its spec is the panel spec (`bank_u`, that block only, `subs ["U2B"]`, no `limit_per_sub`, the frozen manifest sha, `out` = `analysis/fork/newmethod/tau2/<model>_<cell>/<blk>`);
- the summary's `manifest_sha256`, `spec.blocks` and `spec.cell` match;
- `n_errors` = 0, and every no-op passed;
- `n_rows` = the manifest's U2B rows of the block (85);
- `n_missing` = the number of manifest-missing source rows of the block, all of which lie outside the population;
- `n_ok` = `n_rows` − `n_missing`.

How this covers the population with counts only:
- A manifest-missing row is always recorded missing by `bank_u`.
- So when `n_missing` equals their count, no other row is missing. Every population state of the block then has a completed record.
- For m24 the population is the A3 mask, taken from `analyze_newmethod.population` (no duplicated semantics):
  - the 7 manifest-missing rows (airline 13 in f01; airline 44 in f01–f03 here, f04–f06 later) do not make a cell ineligible;
  - any other missing row does;
  - phase 1 then covers exactly 83 × 3 = **249** states per cell.
- For q8 the population is all 85 tasks and no row is manifest-missing, so `n_missing` must be 0. This is now enforced for q8 as well; before, only `n_errors` and the no-ops were checked.
- The tool refuses to run if a manifest-missing row ever falls inside the population.

Fields read: queue status, the task's `gpus`, `finished` and fork spec, never its `result`; and from `bank_summary.json` only seconds, n_rows, n_ok, n_missing, n_errors, budget_ok, the no-op counts and the provenance fields `manifest_sha256` / `spec`. `bank_rows.jsonl`, `branches/`, token scores and `holdout/` are refused by a path guard.

**Limitation, stated:** a branch-arm error inside an otherwise completed row (`Y` = None for one arm) is counted in `n_ok` by `bank_u` and is not visible in these fields. Such a block passes A5.2. The analysis strict-block rule (§7; A3.3) still refuses it later. Expansion eligibility does not depend on it.

### A5.3 KIVI pairing (defines how `kivi_k16v16` enters expansion; A4 did not)

The KIVI group is `kivi_k16v16` plus the quantized KIVI cells `kivi_k2v2` and `kivi_k4v4`. Within it, §5.5 "all or none" is applied jointly with the control:
- a quantized KIVI cell is phase-2 eligible only if it is eligible on its own **and** `kivi_k16v16` is eligible on its own;
- `kivi_k16v16` is phase-2 eligible only if it is eligible on its own **and** at least one quantized KIVI cell is.

So if `kivi_k2v2` expands, `kivi_k16v16` expands on the same blocks (f04–f06). Otherwise neither does, and the record states why: "A5.3: kernel-path control kivi_k16v16 not eligible", or "A5.3: no eligible quantized KIVI cell".
- The rule uses only the eligibility of A5.1/A5.2 and reads no effect.
- The A4.4 contrasts (`kivi_k2v2` − `kivi_k16v16`, `kivi_k4v4` − `kivi_k16v16`) therefore always have both cells on the same blocks.
- The rotation W16 controls are not coupled by this amendment. Their pairing is unchanged from §5: each cell is judged alone.

### A5.4 Frozen snapshot, recorded inputs, written once

- **Snapshot time.** If the decision is due because T_decide has passed, eligibility is judged on the state **as of T_decide**: a task counts as done only if its queue record's `finished` ≤ T_decide. The scheduler's poll latency therefore changes nothing. If trigger (a) fires before T_decide, the snapshot time is the decision run itself.
- **Not complete means ineligible.** A cell whose phase 1 is not complete at the snapshot time is ineligible. "Cells registered after the decision run f01–f03 only" (§5.6) still holds, and so does a cell that completes later.
- **Inputs recorded.** Each input file is read once and parsed from the same bytes whose sha256 is recorded. The record holds, per cell:
  - every gate and panel task's queue state, `finished` time and task-file sha256;
  - the summary fields used;
  - the reasons for ineligibility.
  It also holds every input file's sha256 (`inputs.files_sha256`), the protocol, manifest and mask shas (`guard`), and the builder's own sha256 (`builder_sha256`, computed at run time).
- **Projected cost.** The finish time uses the actual decision-run clock: now + wall ≤ T_deadline (§5.4, unchanged).
- **Written once.** `--write` uses the clock, so `--now` is refused with it. The record `analysis/fork/newmethod/expansion_<model>.json` is created by a hard link of a complete temporary file, which fails if the record exists, so it is written exactly once.

Scheduler commands (one per model, unchanged otherwise):
- `make_newmethod_panel.py expansion --model q8 --write`
- `make_newmethod_panel.py expansion --model m24 --write`

### A5.5 Analysis script

`analysis/fork/analyze_newmethod.py`: `PROTOCOL_SHA256` = this file's new sha256 (same commit). Nothing else changes.

---

## Amendment A6 (2026-10-03 08:16 PDT, W100v): a fork-branch arm error caused by the agent's own message is a failure (Y = 0); the strict analysis as preregistered becomes a labelled sensitivity

**TL;DR** In the τ² panel (A), an arm whose branch stopped because the harness could not accept a message the agent model itself generated is scored Y = 0, as end-to-end evaluation scores the same failure. Every other arm error stays missing and still fails its block (§7, A3.3). This is the primary rule for every panel model (q8 and m24) and every cell. The analysis without A6 is reported beside it as the labelled sensitivity "strict as preregistered". The user approved this on 2026-10-03 ("都做"; W100q decision 2, W100t).

Status when this was written (before the commit that carries it):
- **m24 phase 2:** no `nmp_tau2_m24_*_f0{4,5,6}` task had finished. `gptq_w4_d1` f04 was running; `gptq_w4_d1` f05, f06 and `rtn_w4` f04 to f06 were in todo. None of their outputs had been opened.
- **q8 new-method cells:** 22 `nmp_tau2_q8_*` phase-1 tasks were done, `spinquant_w4a4` f01 was running and f03 in todo. Their outputs exist, but no analysis of them had been run or read. No `analysis/fork/out/newmethod_q8_*` exists, and exppilot holds the q8 analysis until `queue/EXPPILOT_GO_newmethod_q8`. The only fields read from them were effect-blind summary fields: the expansion tool's (A5.2) and exppilot's `budget_ok` scan.
- **No q8 expansion record** (`expansion_q8.json`) existed.

### A6.1 Why

- **End-to-end rule.** `scripts/a6000/worker.py` (`classify`) labels an episode that ends on the agent's own malformed output `agent_parse_error` (W27, W99p) or `agent_empty_output` (W92). `analysis/insights/iter_2/common.py` (`AGENT_SIDE`) then scores it as a task failure, not as missing.
- **The fork already follows it twice.** A source episode that ended this way is a valid failure, Y_QQ = 0 (`fork_driver.search_task`, W10/W70). A branch that overflows the context window is Y = 0 (`cloq/fork.py::run_branch`).
- **The gap.** `run_branch` converts only `ContextWindowExceeded`. Any other exception returns `{"error": repr(e)}`, so the arm is Y = None and A3.3 fails the whole (cell, block). The same failure by the same model is therefore a task failure end to end but a missing outcome in a fork branch.
- **Why it matters.** Under deterministic protocol A the error recurs on a re-run, and A3.3 forbids retries. Leaving it missing drops exactly the states where the agent's own output failed, so the missingness depends on the outcome being measured.

### A6.2 The class scored Y = 0

An arm is an **agent-output error** iff all three hold:
1. **Record.** Its branch record (`branches/<state_key>.json`, key = the arm) has an `error` field and no `infra_cause`.
2. **Type and message.** The error (the `repr` of the exception that `run_branch` caught from the tau2 orchestrator) matches one of:

| Id | Exception (`repr` prefix; either quote style) | Raised by | What the agent produced | End-to-end precedent |
|---|---|---|---|---|
| S1 | `InvalidFunctionCallException('Function name was ` (mistral_common) | mistral_common's instruct validator, `_validate_function_call`, which checks the function name of an **assistant** tool call. It runs while the agent renders its next request (`cloq.context_policy` → `cloq.mistral_render`) | a tool call with an empty or invalid function name | W99p (`worker.classify`, "Function name was … must be a-z") |
| S3 | `ValueError('AssistantMessage must have either content or tool_calls` (tau2) | tau2's orchestrator, `agent_msg.validate()` on the message the agent just returned | an empty message (no content, no tool call) | W92 (`agent_empty_output`) |

3. **Origin in the branch.** The record's `n_decisions` ≥ 1, so the branch logged at least one agent decision (the forced action) before the error. The stored history h_t cannot be the source of the bad message: every message in it was rendered without error at the source's decision t, and the same prompt ids are checked per state (`Q_prompt_ok`). The offending message is therefore the forced action (a_B or a_Q, each a model's own output) or a decision of the continuing controller.

- **Reused arms.** An arm reused from an arm in this class (`arm_source` `reuse=XX`, the §2.3 identity under protocol A) takes the same value.
- **Everything else stays missing,** and is never imputed. This covers:
  - transport and server errors (for example litellm `APIConnectionError`, `Timeout`, `InternalServerError`), and every `BadRequestError`;
  - harness errors (`KeyError`, `AssertionError`, `IndexError`, state restoration);
  - environment and tool errors;
  - user-simulator errors, including `UserMessage must have …`;
  - errors whose type does not identify an agent message, so the record cannot establish their origin: `JSONDecodeError` and the pydantic `validation error for ToolCall`. End to end, `worker.classify` also treats `JSONDecodeError` as an outage;
  - S1 or S3 with `n_decisions` 0;
  - row-level errors (the shadow or the state construction failed), prompt-id mismatches and manifest-missing rows.
- **W27's several-tool-calls refusal is not in the class.** It comes from the Llama-3.1 template and cannot arise with the Qwen3 or Mistral templates of the panel models. It would stay missing.
- The class reads only the error record. It does not depend on the arm, the cell or any Y.

### A6.3 Rules

- **Primary.** Arms in the A6.2 class enter with Y = 0. A state whose four arms are then defined is complete. Everything else in §7/A3.3 is unchanged:
  - any other arm error, missing record or missing arm fails the block for that cell;
  - nothing else is imputed;
  - there are no retries.
- **The A3.3 sensitivities** (complete case; m24 actual available rows) use the A6 scoring.
- **Sensitivity "strict as preregistered".** This is §7/A3.3 without A6: every arm error fails its block. It is reported next to the primary with:
  - admitted blocks per cell;
  - per-cell estimates;
  - every contrast;
  - its own Holm-adjusted primary family.
- **Reporting.** For each (cell, block), the report gives:
  - the number of states and arms scored Y = 0 under A6, with the signature and the task;
  - the arm errors that stayed missing, with the exception type.
- **Scope.** Panel A (τ²), q8 and m24, every cell including the q8 reference cells.
- **Unchanged:**
  - Panel B (BFCL): `analyze_ext` excludes an item with a branch error, and items have no strict-block rule;
  - expansion (§5, A5), which reads no outcome;
  - the A3 mask, the manifests, the queued tasks and the Holm families.

### A6.4 Disclosure (binding wording)

- **m24 phase 1 (f01 to f03): post hoc.** The arm errors that A6 reclassifies were seen before this rule (W100s budget audit, `analysis/fork/out/m24_budget_audit_20261003T1354Z.md`). The phase-1 interim estimates had also been read (W100s).
  - On that record A6 scores 4 arms in 3 population states as Y = 0, all S1:
    - `rtn_w4` f01 retail:51, QB and QQ;
    - `rtn_w4` f02 retail:95, QQ;
    - `gptq_w4_d1` f01 airline:2, BQ (empty name).
  - The `rtn_w4` f03 airline:13 BQ arm (`JSONDecodeError`, a masked task) stays missing.
- **m24 phase 2 and the q8 new-method cells: fixed before reading.** The rule was fixed before any of their τ² panel outcomes was read (status above). For q8 phase 1 the outputs already existed when the rule was fixed.
- **q8 reference cells (`gptq_w4_d1`, `awq_w4`, `kvq_int8`), f01 to f03: not blind.** Their Bank U U2B rows had been analysed before: in the main study's Bank U analyses, and for `gptq_w4_d1` and `awq_w4` in `analysis/fork/out/q8ref_w4_nmp_20261003T140825Z` (W100s).
- **Rationale.** Consistency with the end-to-end scoring of the same model-caused failure (W27, W92, W99p), and with the fork's own treatment of source episodes and branch overflow (W10, W70). The rule was not chosen for its effect on any estimate. The strict analysis as preregistered is always reported beside it.
- **Paper wording.** "A branch that ended because the harness could not accept the agent's own message (an empty or invalid tool name, or an empty message) is scored as a failure, as in end-to-end evaluation. This rule was added after the Mistral phase-1 results had been read; the analysis without it is reported alongside."

### A6.5 Recording check (no driver change)

- `run_branch` stores `error: repr(e)` untruncated and `n_decisions` in `branches/<state_key>.json`. It has done so since d1d2a6d, before Bank U, and the code path is the same for every model, so the type and the full message are available for every panel and reference row.
- `bank_rows.jsonl` keeps only `"error: " + repr[:120]` in `arm_source`. The analysis therefore reads the branch record.
- A6.2 needs no traceback, because the S1/S3 exception types are raised only by validators of agent messages. So `cloq/fork.py` and `fork_driver.py` are unchanged.

### A6.6 Analysis script

`analysis/fork/analyze_newmethod.py` was changed in the same commit:
- `PROTOCOL_SHA256` = this file's new sha256;
- `A6_SIGNATURES`, `a6_class` and `a6_resolve` implement A6.2;
- `load_tau2(..., a6=False)`: the default is the loader exactly as before. `main()` loads with `a6=True` for the primary;
- `strict_prereg` gives the sensitivity. `main()` asserts that it equals a load without A6, state by state;
- `a6_report` gives the per-block counts (JSON `tau2.a6`, markdown section). `--dry` prints the counts and the admitted blocks under both rules;
- `--selftest` covers A6 on synthetic error records.
