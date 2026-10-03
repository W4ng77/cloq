**TL;DR** Pre-registered common-state action-source comparison on q8 (Qwen3-8B), advisor GPT-6.1 (binding). On the 255
frozen U2B ordinary states of Bank U (f01–f03; the U2B rows of `manifests/fork/newmethod_panel_v1.json` f01–f03), the
current action comes from three sources (BF16, GPTQ-W4 d1, GPTQ-W4 d2) and the continuation is fixed to BF16 or d1.
Four of the six source × continuation cells already exist (Bank U q8 gptq_w4_d1); this study adds d2 → BF16 and
d2 → d1 (≤ 510 suffixes) with a new additive fork_driver mode `commonstate`. Key question: is BF16 − d1 different from
d2 − d1 (equivalently, BF16 − d2 ≠ 0)? Equivalence margin ±3 pp by TOST; "interval includes 0" is never read as
equivalence. Written and committed before any d2 outcome at these states existed.

# Common-state action sources (BF16 vs W4-d1 vs W4-d2) on q8 — protocol commonstate-v1

Written 2026-10-02 07:45 PDT. Work item W100a (docs/RESEARCH_LOG.md). The sha256 of this file is recorded in
`manifests/fork/commonstate_v1.json` and in the W100a log entry; `analysis/fork/analyze_commonstate.py` refuses to run
unless the file's sha256 equals that value.

## 1. Question

The Bank U precision 2×2 on ordinary states shows that, with the history and continuation held fixed, replacing the W4
model's current action by the BF16 model's action changes the outcome (G = Y_BQ − Y_QQ, rescue/damage). The
same-precision control (W99l) suggests that much of the fork turnover is generic trajectory sensitivity. This study asks
the action-level version directly: **with the same history and the same continuation, what does choosing BF16's action
bring compared with choosing another W4 action (a second GPTQ-W4 calibration draw)?** If BF16 − d1 ≈ d2 − d1, the
BF16 action has no value beyond "a different plausible action"; if BF16 − d1 > d2 − d1, the BF16 action carries
precision-specific value.

## 2. Design

- **States.** The frozen q8 U2B rows of `manifests/fork/bank_u_v1.json` (sha256 `e236ee64…a907`), blocks f01, f02,
  f03 (85 each: retail 58 + airline 27; 255 states, none missing). These are the same rows (same state_key, source run
  `a6k2_q8_bfpair_<blk>`, task, t) as the f01–f03 U2B rows of `manifests/fork/newmethod_panel_v1.json` (checked:
  255/255 identical). The state is h_t of the BF16 source trajectory at the sampled decision t.
- **Sources.** BF16 (Qwen3-8B @ b968826d; the recorded action of the source trajectory, a_BF16), W4-d1 (GPTQ-W4,
  calibration `manifests/a6k2/q8/calib_fp_traj_c1.json`, ckpt sha256 `6ee628e6…`, canary `a9f812fb17241b72`; its action
  a_d1 is the Bank U row's a_Q), W4-d2 (GPTQ-W4, calibration `calib_fp_traj_c2.json`, ckpt sha256 `320409ad…`, canary
  `15e5098c08c412da`; the checkpoint of runs `a6k2_q8_gptq_w4_d2_n*` and of the same-precision fork).
- **Continuations.** BF16 or d1, from the next decision to the end, with the same simulator (node-local Qwen3-30B-A3B
  user simulator, the state's simulation seed), the restored step/error budget, tau2 config, scoring and nonce.
- **Cells V(s, c).**

  | source \ continuation | BF16 | d1 |
  |---|---|---|
  | BF16 | Y_BB (existing, = original suffix unless run) | Y_BQ (existing) |
  | d1   | Y_QB (existing) | Y_QQ (existing) |
  | d2   | **new arm A** | **new arm B** |

  Existing = `analysis/fork/bank_u/q8_gptq_w4_d1/f0{1,2,3}/bank_rows.jsonl` (outcomes as recorded there, including the
  Bank U reuse rule for token-identical actions; FORK_PROTOCOL §15 amendment 1).
- **Mechanism (cheapest correct).** New fork_driver mode `commonstate` (additive; no other mode changes):
  - Task type A, servers B = BF16, Q = d2: d2 generates a_d2 at h_t from the identical prompt (prompt ids must equal the
    recorded BF16 prompt ids), a second generation on the same server must reproduce it bit-exactly (Q-replay
    acceptance), then arm QB = a_d2 forced, BF16 continuation (new arm A).
  - Task type B, servers B = d2, Q = d1: same a_d2 generation and replay on the d2 server, then arm BQ = a_d2 forced,
    d1 continuation (new arm B).
  - a_d2 is regenerated in both tasks; the analysis requires the two to be token-identical (completion-id sha and
    canonical message), which also checks cross-node d2 determinism.
  - New arms are always run (no reuse), even when a_d2 equals a_BF16 or a_d1. Those rows give free identity checks.
  - Rejected alternatives: a bank_u run with B = BF16, Q = d2 would also run the unneeded BQ (BF16 → d2) and QQ
    (d2 → d2) arms (3 suffixes per row instead of 1). A bank_u run with B = d2, Q = d1 does not work on U2B rows,
    because bank_u takes the B-role action of a U2B row from the recorded BF16 trajectory, not from the B server.
- **Same-state guarantee.** Each row rebuilds the state with `cloq.fork.make_state` and requires equality with the
  reference Bank U row for state_id, history_sha, recorded prompt-id sha, steps_left, the recorded action, and the
  initial env hash of the reference branches. CPU pre-check on 2026-10-02: 255/255 equal on all six.
- **Reference re-runs (reuse validation).** On a hash sample (`sha256('commonstate-noop-v1|' + state_key + '|' + kind)`,
  fraction 0.2; gate: every row):
  - task A: the recorded BF16 action continued by BF16 must reproduce the original suffix (noop_check: suffix,
    prompt ids, termination, reward, db_match, budget, env hashes);
  - task B: d1 regenerates a_d1 (must equal the reference row's a_Q), and its d1 continuation must reproduce the
    reference QQ branch (`branch_signature`: suffix sha, prompt and completion ids, termination, reward, env hash, budget).
  - Implicit identity (every row where it applies): if a_d2 = a_BF16 (canonical), arm A must equal the original
    suffix; if a_d2 = a_d1, arm B must equal the reference QQ branch.
- **Tasks.** Two gate tasks, then six panel tasks (one per block × task type), priority −29, 2 GPUs each (one per
  server), q8 nodes node004/005/007 in rotation, `fork.resume: true`; panel tasks depend on both gates. Generator
  `scripts/a6000/make_tasks_commonstate.py`, outputs `analysis/fork/commonstate/q8/{gate,panel}/<type>/…`.

## 3. Gate (before the panel; the panel depends on it)

Gate tasks `cs_gate_q8_d2_bf16` (type A, node005) and `cs_gate_q8_d2_d1` (type B, node007), mode `commonstate`
with `gate: true`, 12 hash-selected rows of the 255 (`sha256('commonstate-gate|' + state_key)`), reference re-run on
every row. Both run on nodes other than node004 (where the reference Bank U arms ran), so a pass also shows cross-node
reproducibility. Required, all:
1. **Identity.** idcheck of 16 recorded decisions, bit-exact: d2 on `a6k2_q8_gptq_w4_d2_n1` (both tasks), BF16 on
   `a6k2_q8_bfpair_f01` (A), d1 on `a6k2_q8_gptq_w4_d1_f01` (B); server canaries as listed in §2 (checked by the
   analysis from the queue records).
2. **d2 determinism at foreign states.** For every row: prompt ids equal; the second d2 generation reproduces the first
   (completion ids and canonical message).
3. **No-ops.** All reference re-runs and all applicable implicit identity checks pass.
4. **Same state / budget.** All same-state checks pass; budget accounting holds on every run branch.
5. No row errors or missing rows.
The driver verdict `pass` encodes 1–5 (canary values are checked offline). On failure the gate task fails, the panel is
never released, and the failure is reported (no redesign without a new dated protocol section).

## 4. Admission

A state u enters the analysis set iff all of:
- the reference Bank U row has all four outcomes;
- both new arms have an outcome (a branch that ends in a context-window overflow is a valid failure, Y = 0, as in
  W10/W70; any other error makes the row missing);
- all same-state checks pass and d2's replay passes in both tasks;
- a_d2 is identical across tasks A and B (completion-id sha and canonical message).
**Block quarantine.** If any reference re-run or implicit identity check of a block fails in either task, the whole
block leaves the analysis set (both tasks, all six cells), as with the QQ no-op quarantine of the dev analysis. Missing
units for infrastructure reasons are requeued unchanged (resume). The analysis set is the blocks among f01–f03 that are
complete (85/85 admitted) and not quarantined at the analysis time; if fewer than 2 blocks qualify, no reading is made
and only per-block numbers are reported. Server canaries must match §2, else the task's rows are missing.

## 5. Estimands

Unit = state u (task × block). Y ∈ {0, 1} = DB success with a normal stop (retail/airline; `fork_driver._y`).
V(s, c) = mean of Y over the analysis set for source s ∈ {BF16, d1, d2} and continuation c ∈ {BF16, d1}.
Primary target as Bank U: equal weight per task within a block, then the mean over blocks (not n_decisions-weighted).

- **Contrasts.** For each pair (s1, s2) ∈ {(BF16, d1), (BF16, d2), (d2, d1)} and each c:
  Δ_{s1−s2}(c) = V(s1, c) − V(s2, c); rescue r = P(Y_s1 = 1, Y_s2 = 0), damage d = P(Y_s1 = 0, Y_s2 = 1),
  turnover M = r + d.
- **Interaction with the continuation.** I_{s1−s2} = Δ_{s1−s2}(BF16) − Δ_{s1−s2}(d1).
- **Key estimand.** K(c) = Δ_{BF16−d1}(c) − Δ_{d2−d1}(c), which equals Δ_{BF16−d2}(c) unit by unit. Co-primary for
  c = d1 (the W4 deployment controller; matches Bank U's G) and c = BF16. Secondary: the continuation average
  K̄ = (K(BF16) + K(d1)) / 2.
- **Action agreement.** Pairwise exact canonical agreement among a_BF16, a_d1, a_d2 and the `compare_actions`
  category (same / text_only / primary); the five three-way patterns (all equal; BF16 = d1 ≠ d2; BF16 = d2 ≠ d1;
  d1 = d2 ≠ BF16; all different). Also the descriptive key question on the subset where a_d2 ≠ a_BF16.

## 6. Inference

- Two intervals for every estimand: **t over the k block means** (df = k − 1; run-level), and the **task-cluster
  bootstrap** (resample the 85 tasks with replacement, each task bringing its rows in every block; B = 2000,
  seed 20261002, the same draws for every estimand). Both at 95 % (two-sided) and 90 % (for TOST).
- **Frozen reading for K(c), applied to each continuation separately:**
  - **"BF16 action adds value beyond a W4 swap"** (K > 0) or **"another W4 action does better"** (K < 0): only if
    BOTH 95 % intervals exclude 0 on the same side. Across the two co-primary continuations the bootstrap two-sided
    p-values (2·min(P*(K ≤ 0), P*(K ≥ 0))) are Holm-adjusted at α = 0.05, and the claim also needs the Holm-adjusted
    p < 0.05.
  - **"Equivalent within ±3 pp"** (TOST, α = 0.05 each side): only if BOTH 90 % intervals lie inside (−3, +3) pp.
    Equivalence across both continuations needs it under each (intersection–union, no adjustment).
  - Otherwise: **"not resolved"**, reported with the numbers. An interval that includes 0 is never called
    equivalence or "no effect".
  - Expected precision: with ~255 units and a paired turnover of roughly 10–20 %, the 90 % half-width is ~3–5 pp, so
    "not resolved" is a likely outcome. This is stated before the data. An extension to f04–f06 would need new d1 BQ/QQ
    arms and a new dated protocol section.
- The same three-way rule is applied, as secondary readings, to the interactions I_{s1−s2}: "continuation-dependent",
  "equivalent within ±3 pp", or "not resolved". All other quantities (V, Δ, r, d, M, agreement) are descriptive with
  both intervals.
- No other subsets, thresholds or re-analyses enter the reading; anything else is labelled exploratory.

## 7. Outputs

`analysis/fork/analyze_commonstate.py` → `analysis/fork/out/commonstate_<UTC>.{md,json}`, TL;DR first: analysis set,
admission and acceptance counts (gate, reference re-runs, implicit identities, cross-task a_d2 identity, canaries), the
3 × 2 table V(s, c), all contrasts with r/d/M and both intervals, interactions, K(c) with the frozen reading and TOST,
the agreement tables, and per-block numbers. The script refuses to run unless the protocol sha256 equals the manifest's.

---

## Deviation D1 (2026-10-02 09:35 PDT, logistics only; no outcome-dependent change)

The node pins of §2/§3 (gate A on node005; panel tasks on node004/005/007 in rotation) were removed from the queued
tasks, because the pinned nodes were occupied for hours by priority −28 tasks. Gate B had already passed on node007:
12/12 reference d1 QQ re-runs were bit-exact against the node004 Bank U branches, and the canaries matched. No panel
outcome existed. Nothing else changes. Cross-node identity is still checked on every task by the reference re-runs and
the implicit identities (§2), and on every unit by the cross-task a_d2 identity (§4). The text above this section is
unchanged and is a byte-identical prefix (sha256 d76a8e3ee0bd607e7362ac629c3f458691cf44f4f59b26f1f061671bae92ecff).

---

## Amendment A1 (2026-10-03 08:20 PDT, W100u): q8 extended to f04–f06 (K = 6), and q4 as a separate prospective analysis

**TL;DR** q8 runs six blocks: f04–f06 are added unconditionally, with this study's own d1 reference arms. The K = 6
reading is the confirmatory q8 reading under the unchanged §4–§6 rules. The K = 3 reading (W100b) stays in the record
as the first look, and a prespecified Pocock two-look reading is reported next to the K = 6 reading. q4 (f01–f03) is a
separate prospective analysis with the same estimands. It runs its own gate first and is never pooled with q8. Blocks
not complete by 2026-10-04 21:00 PDT are excluded. Written and committed before any outcome it governs existed.

**Why, and approval.** GPU fill proposals F1a and F1b (`docs/insights/GPU_FILL_PROPOSAL_20261003.md`). The user
approved both on 2026-10-03 07:45 PDT (W100t). §6 requires a new dated section for any extension. The text above
this section is unchanged and is a byte-identical prefix: 12,813 bytes, sha256
c73ab2eec2f14052633e0703c2f50b1df9356c8222ba2ad1c8541301948198d0 (the D1 version).

**What was known when this section was written.**
- **q8 f01–f03 (read).** The K = 3 reading (W100b, `analysis/fork/out/commonstate_20261002T201612Z.md`) was produced,
  read and reported in paper §5 (W100f): K(d1) −0.4 pp and K(BF16) +2.4 pp, both "not resolved". Every f01–f03 cell,
  contrast, block mean and agreement table has been seen. The extension was proposed because both readings were
  unresolved, so the decision to extend depends on those outcomes. A1.3 deals with this.
- **q8 f04–f06 (none).** No outcome of this design exists at these states. No d2 action has been generated there.
  No gptq_w4_d1 arm (BQ, QB or QQ) has been run there: `analysis/fork/newmethod/tau2/q8_gptq_w4_d1/` does not exist
  and `expansion_q8.json` has not been written. The BF16 source episodes `a6k2_q8_bfpair_f04`–`f06` exist. They supply
  the states and the reused BB suffixes, and their whole-episode outcomes are part of the main matrix.
- **q4.** The Bank U q4 gptq_w4_d1 four-arm outcomes on f01–f03 exist and have been read (W70 onward). No q4 d2
  action at these states exists. The q4 d2 checkpoint has been used only by the same-precision fork (SAMEPREC), at
  d1-sourced states, which are different states. q4 is added after the q8 K = 3 reading was known.
- **CPU pre-check (2026-10-03 08:07 PDT, `cloq.fork.make_state`, no GPU).** q4: all 255 rebuilt states equal the
  Bank U q4 reference rows on the six same-state fields of §2. q8 f04–f06: all 255 states build, with recorded prompt
  ids and steps_left > 0. There are no reference rows to compare with yet.

### A1.1 q8: six blocks, fixed now
- The q8 design is f01–f06 (K = 6). f04–f06 run whatever any outcome shows: no stopping, no further extension and
  no other look.
- **States f04–f06.** The 255 q8 U2B rows of `manifests/fork/newmethod_panel_v1.json` (sha256 `7534c690…ca201`),
  blocks f04, f05 and f06: phase 2, 85 rows each (retail 58 + airline 27), sources `a6k2_q8_bfpair_f04`–`f06`, none
  missing. Bank U v1 has no f04–f06 rows. The panel manifest uses the same sampling rule, and its f01–f03 rows equal
  Bank U's (255/255, `bank_u_identity`). The same 85 tasks appear in all six blocks, so the task-cluster bootstrap
  resamples 85 tasks, each bringing its six rows.
- **Reference d1 arms at f04–f06 (BB, BQ, QB, QQ).** This study runs them itself:
  - tasks `cs_ref_q8_gptq_w4_d1_f04`, `_f05` and `_f06`;
  - fork mode `bank_u` on the panel manifest, cell gptq_w4_d1, U2B only, noop_frac 0.1;
  - B = BF16, Q = GPTQ-W4 d1 (calib c1);
  - output `analysis/fork/commonstate/q8/ref_d1/<blk>`.

  This is the NEWMETHOD phase-2 reference-cell spec with a different output directory. That cell runs only if
  `expansion_q8.json` says expand. The decision is effect-blind but stays open until 20:00 PDT today, and the 07:50
  dry run projected 18.2 h of phase-2 wall time, so it can go either way. Reusing that cell would make this design
  depend on another study's decision. If both run, the duplicate cost is about 5 GPU-h. These reference rows belong
  to this study and never enter a NEWMETHOD analysis.
- **Cross-check (acceptance note only).** If NEWMETHOD's `nmp_tau2_q8_gptq_w4_d1_<blk>` outputs also exist at
  the reading, the analysis reports per block how many rows agree with this study's reference on a_Q (canonical) and
  on Y in each of BB, BQ, QB and QQ. The result never changes admission.
- **New d2 arms at f04–f06.**
  - Task types A and B of §2, ids `cs_q8_d2_bf16_<blk>` and `cs_q8_d2_d1_<blk>`.
  - The panel manifest, `ref_dir` = `analysis/fork/commonstate/q8/ref_d1`, noop_frac 0.2.
  - Outputs `analysis/fork/commonstate/q8/panel/<type>/<blk>`, beside f01–f03.
  - Each task depends on its block's reference task.
- **No new q8 gate.** The §3 gates passed on 2026-10-02 (W100a) with the same model, checkpoints and serving stack.
  The fork_driver functions `commonstate` and `bank_u` have not changed since 87733f7.
- **Acceptance.** The per-block checks of §2 and §4 are unchanged: reference re-runs, implicit identities, d2 replay,
  cross-task a_d2 identity, canaries and checkpoint sha256. They also cover any change in quantization or serving code.
  In addition, an f04–f06 block is complete only if:
  - its `bank_summary.json` has 85/85 rows ok, 0 errors, 0 missing and the panel manifest's sha;
  - every BB no-op sample of the reference task passed;
  - the reference task's server canaries and d1 checkpoint sha256 match §2.
- **Queue.** Priority −28, 2 GPUs per task, no node pin.

### A1.2 q8 reading at K = 6
- §4–§6 apply unchanged:
  - admission and block quarantine;
  - the estimands;
  - both intervals: t over the k block means (df = k − 1) and the task-cluster bootstrap (B = 2000, seed 20261002);
  - the frozen three-way reading of K(BF16) and K(d1), with Holm over the two continuations and TOST at ±3 pp;
  - the secondary readings and the descriptives.
- The analysis set is the complete, non-quarantined blocks among f01–f06 (§4, at least 2).
- **The primary q8 reading is this K = 6 reading.** It is the confirmatory reading of the extended design.

### A1.3 Two looks
- The K = 3 reading (W100b) stays in the record unchanged. It is reported next to the K = 6 reading as "first look,
  k = 3", and it is never relabelled or replaced. The K = 6 reading is the second and last look, computed once (A1.5).
- **Error rates.** Source: `analysis/fork/commonstate_twolook_mc.py`, a Monte Carlo over iid normal block effects
  with a between-block SD of 2–6 pp, t criterion only. The frozen rule also needs the bootstrap, so its rates are at
  most these.
  - At K = 0, the chance of a difference claim at k = 6, given no claim at k = 3, is 0.041 (nominal 0.05).
  - At K = 0, the procedure "claim at k = 3, otherwise at k = 6" has an unconditional rate of 0.089.
  - At the ±3 pp equivalence boundary the same two rates are 0.010–0.037 and 0.024–0.084.
- **Prespecified two-look reading (sensitivity).** The same three-way rule at the Pocock levels for two equally
  spaced looks:
  - difference: nominal two-sided 0.0294, so both 97.06 % intervals must exclude 0 and the Holm-adjusted bootstrap
    p must be < 0.0294;
  - equivalence: nominal one-sided 0.0304 per TOST side, so both 93.92 % intervals must lie inside ±3 pp;
  - t quantiles at these levels with df = k − 1.

  The k = 3 look made no claim at 0.05, so it made none at these stricter levels either. The observed path is
  therefore a path of this two-look design, whose two-look rate is 0.054 or less for a difference and for
  equivalence (t criterion, Monte Carlo).
- **Reporting rule.** The paper states the K = 6 reading at the frozen levels. If the two-look reading does not
  support a claim that the frozen levels make, the paper reports both readings and adds "not robust to the two-look
  adjustment".

### A1.4 q4: a separate prospective analysis (K = 3)
- **Model and states.** The same design on q4 (Qwen3-4B-Instruct-2507 @ cdbee75f). The states are the 255 q4 U2B
  rows of `manifests/fork/bank_u_v1.json`, blocks f01–f03: sources `a6k2_q4_bfpair_f0{1,2,3}`, 85 rows each
  (retail 58 + airline 27), none missing.
- **Reference.** `analysis/fork/bank_u/q4_gptq_w4_d1/f0{1,2,3}`, which already exists.
- **Sources.**
  - BF16: canary `c7343b60da095480`.
  - d1: GPTQ-W4, calib `manifests/a6k2/q4/calib_fp_traj_c1.json`, ckpt `e6c24bc2…`, canary `a72b3da03409576e`.
  - d2: calib `calib_fp_traj_c2.json`, ckpt `21c0934e…`, canary `a0fb6c52f4eb27fd`. This is the d2 of SAMEPREC q4.
- **Tasks.** 1 GPU each (B and Q at gpu_util 0.44, as in Bank U q4), priority −28, no pin.
- **Gate first.** The five conditions of §3 apply.
  - Tasks `cs_gate_q4_d2_bf16` and `cs_gate_q4_d2_d1`: 12 hash-selected rows, with the reference re-run on every row.
  - idcheck of 16 decisions: d2 on `a6k2_q4_gptq_w4_d2_n1`, BF16 on `a6k2_q4_bfpair_f01` (A), d1 on
    `a6k2_q4_gptq_w4_d1_f01` (B).
  - The gate fails loudly and is never retried automatically (`autopilot_retry` "no").
  - The six panel tasks `cs_q4_d2_{bf16,d1}_f0{1,2,3}` depend on both gates.
  - If a gate fails, q4 is reported as "not admitted" with the reason. There is no redesign without a new dated
    section.
- **Analysis.** §4–§6 apply unchanged to q4 alone:
  - K(BF16) and K(d1) are co-primary, with Holm over the two continuations within q4 (a family separate from q8);
  - TOST at ±3 pp, both intervals, k = 3 (t df = 2);
  - one look only.
- **No pooling.** q4 and q8 are never pooled into one reading. Their signs can differ, as they do in the W4 G−H
  family, and a pooled number would then mix opposite effects. Any cross-model number is labelled exploratory.
- **Disclosure.** q4 was added after the q8 K = 3 reading was read. It is reported whatever its direction.

### A1.5 Deadline and once-only readings
- **Evidence freeze: 2026-10-04 21:00 PDT** (W100t). A block enters a reading only if both of these hold:
  - every task that supplies it has a done record finished no later than the freeze (q8 f04–f06: the reference
    task and both d2 tasks; q4: both d2 tasks);
  - it is complete and not quarantined (§4, A1.1).

  Other blocks are excluded and never added later. If the q8 analysis set has k < 6, the reading is made with that k
  and labelled with it. If fewer than 2 blocks qualify, there is no reading, only per-block numbers (§4).
- **Once only.** Each reading (q8 K = 6; q4) is computed once, at the earlier of (a) all of its tasks done and
  (b) the freeze. `analyze_commonstate.py` refuses a non-selftest run before that point, and a second run.

### A1.6 Files
- **New manifests.** `manifests/fork/commonstate_q8ext_v1.json` (q8 f04–f06) and
  `manifests/fork/commonstate_q4_v1.json`, created with this amendment. `commonstate_v1.json` is not edited.
- **Hash records.** Each new manifest records the sha256 of this file, and so does `analyze_commonstate.py`. Its
  guard also checks that the first 12,813 bytes hash to c73ab2ee…98d0.
- **Generator.** `scripts/a6000/make_tasks_commonstate.py --design q8ext|q4`. The default `--gate` / `--panel` output
  is unchanged.
- **Analysis.** `analysis/fork/analyze_commonstate.py --design q8ext|q4` writes
  `analysis/fork/out/commonstate_<design>_<UTC>.{md,json}`. Without `--design` it gives the unchanged K = 3 q8
  analysis.
