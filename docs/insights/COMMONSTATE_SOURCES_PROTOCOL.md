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
