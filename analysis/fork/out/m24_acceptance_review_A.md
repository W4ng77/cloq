# m24 (Mistral-Small-3.2-24B) new-method panel: acceptance review A (independent, effect-blind)

Reviewer A of 2. Written 2026-10-03 19:30 PDT. Repo HEAD `e30be4d`. Protocol sha256 `3bd7ef33...ba8f6` (A7.E1). Read-only: no effect, contrast, success rate or per-arm outcome aggregate was computed, printed or looked up. `analysis/fork/holdout/` was not opened. The only commands run were `analyze_newmethod.py --model m24 --dry`, `--selftest` and `make_newmethod_panel.py expansion --model m24` (no `--write`), plus CPU scans of non-outcome fields: error strings, `n_decisions`, budget counters, checks, provenance, mtimes and atimes. Y was read only as `is None`. No queue, protocol or code file was modified. Nothing was committed. This file is the only file written.

## TL;DR verdict

**CONDITIONAL GO. Nothing found in protocol integrity, admission, budgets, provenance or pre-registration hygiene blocks `queue/EXPPILOT_GO_newmethod_m24`.** Create it only when all three conditions below hold:
- **C1.** `nmp_score_m24_rtn_w4_f03` is in `queue/done/`. Its `token_scores/m24_rtn_w4/f03/score_summary.json` must be fresh: mtime after 2026-10-03 19:18 PDT, `n_ok` 84, `n_prompt_sha_ok` 84, and `bank_rows_sha256` equal to the current `tau2/m24_rtn_w4/f03/bank_rows.jsonl`. At 19:27 PDT the task was running: it prepared 85 rows (prompt sha ok 84/85; the one miss is the manifest-missing row) and regenerated a_B at 19:23. The file on disk now is the stale 03:29 failure, with `n_ok` 0.
- **C2.** Reviewer B's independent review is in.
- **C3.** At GO time, re-check: protocol sha still `3bd7ef33`, no `analysis/fork/newmethod/tau2_recovery/m24_*`, and `--dry` gives the admission in item 3.

**Blocking issues: none.** Eight non-blocking notes (N1 to N8, below) concern disclosure and hardening.

| # | Item | Result |
|---|---|---|
| 1 | Protocol integrity (sha, append-only chain) | **PASS** |
| 2 | Completeness (τ², score, BFCL) | **CONDITIONAL**: 35/36 m24 nmp tasks done; `nmp_score_m24_rtn_w4_f03` running |
| 3 | Admission (primary, strict, A6.E1 views; arm-error classes) | **PASS**: reproduced exactly; 7/7 arm errors classified identically |
| 4 | Budget and provenance spot-check | **PASS** |
| 5 | Pre-registration hygiene | **PASS with notes** (N2, N3, N4, N6) |
| 6 | GO acceptable once the last score task is done | **CONDITIONAL GO** (C1 to C3) |

---

## Part 1: Item-by-item findings

### 1. Protocol integrity: PASS

- `sha256(docs/insights/NEWMETHOD_PANEL_PROTOCOL.md)` = `3bd7ef3301b62a9a4688be8b10405ce1f58157ae2327324cd06dbc4ead5ba8f6`.
  - It equals `PROTOCOL_SHA256` in `analysis/fork/analyze_newmethod.py` (line 68).
  - The working copy is byte-identical to the committed version (861ebff). Neither file has uncommitted changes.
  - Re-checked at 19:27 PDT, after HEAD had moved to `e30be4d`: unchanged.
- **Append-only chain, checked on every committed version** (`git show <c>:<protocol>`):

| commit | amendment | bytes | sha256 (prefix) | script constant in the same commit | byte prefix of the previous version |
|---|---|---|---|---|---|
| 870d1ba | nmp-v1 | 23,928 | 9cd5c979 | = | n/a |
| 0af849b | A1 | 33,421 | 28b78509 | = | yes |
| 50fc648 | A2 | 38,303 | c6603f90 | = | yes |
| 9285afc | A3 | 43,015 | da8b69ba | = | yes |
| fae1fe3 | A4 | 48,080 | 0dc3143e | = | yes |
| 79b4ab4 | A5 | 56,161 | f9f8b3a5 | = | yes |
| fe6765e | A6 | 65,746 | 73bf5538 | = | yes |
| 2f06102 | A6.E1 | 76,745 | b306cc70 | = | yes |
| 10a5518 | A7 | 84,820 | ba743cee | = | yes |
| 861ebff | A7.E1 | 86,692 | 3bd7ef33 | = | yes |

- **A7's stated prefix.** `head -c 76745 <current file> | sha256sum` = `b306cc70ebfca526472e519baa32f5ed7f698e953711f88eb987a9bc6e61771c`. This is the full sha that A7 states in its text, so it verifies.
- **A6.E1's prefix.** The first 65,746 bytes hash to `73bf5538e9316c5c...`, the A6 version named in the A6.E1 commit message. A6.E1 does not state the prefix sha in the protocol text itself (N7).
- **Push times corroborate the commit times** (`refs/remotes/origin/master` reflog, "update by push"):
  - A6 fe6765e at 08:16:30;
  - A6.E1 2f06102 at 08:56:00;
  - A7 at 16:44:27;
  - A7.E1 at 17:45:01;
  - `expansion_m24` (9739a66) at 04:53:13.
  - Author date = committer date on every one of them.

### 2. Completeness: CONDITIONAL

Required for m24 (A2.2, A5, `expansion_m24.json` expand=true with `phase2_cells` [rtn_w4, gptq_w4_d1]); queue state at 19:27 PDT:

| family | required | done | not done |
|---|---|---|---|
| §2.4 gates | `nmp_gate_bank_m24_<cell>` ×2, `nmp_gate_same_m24_<cell>_r2` ×2 (r1 superseded, W100e-c) | 4/4; r2 verdicts `pass` true with `fail_loud`; bank `gate_pass` true, 10/10 no-op, 0 errors | none |
| τ² panel f01 to f06 | `nmp_tau2_m24_<cell>_f0{1..6}` ×12 | 12/12; one attempt each, no `error_history`/`autopilot_retry` | none |
| §9 score f01 to f06 | `nmp_score_m24_<cell>_f0{1..6}` ×12 | 11/12 | **`nmp_score_m24_rtn_w4_f03` running** (started 19:18; prepared 85 rows, prompt sha ok 84/85; a_B regenerated 19:23) |
| BFCL closed-loop | `ext_m24_{bf16,rtn_w4,gptq_w4_d1}_bfcl_nmp1` | 3/3 | none |
| BFCL forks | `nmp_bfcl_m24_<cell>_<cat>` ×8 | 8/8; `--dry`: 0 quarantined, 0 incomplete, replay guard 0 inconsistent in all 8 dirs, 200 items per cell, 0 excluded | none |

- **todo / failed / deferred / parked.** No `nmp_*_m24_*` task is in any of them.
- **Score outputs.** All 11 finished score summaries carry a `bank_rows_sha256` equal to the current `bank_rows.jsonl`.
- **Fidelity coverage note (N5).** rtn_w4 f01 has `n_ok` 82, i.e. 82/83 population states. The missing state is `b9663570026aa870` (retail:51), with `prep error InvalidFunctionCallException('Function name was YOU ARE BEING TRANSFERRED...`.
- **exppilot.** PID 3821923; `exppilot_state.json` `analyses` is `{}`. It logs `newmethod_m24: HELD until queue/EXPPILOT_GO_newmethod_m24` hourly. Once GO exists, `exppilot_analysis.required()` waits for all 32 tasks: phase 1 τ² + score, BFCL forks, phase 2 τ² + score. The one exception is T_deadline (10-04 12:00 PDT).
  - **Risk:** if the score task fails, the analysis runs at T_deadline on the stale f03 score file, with no flag, because `load_scores` skips silently. Hence C1.

### 3. Admission: PASS

**Primary and sensitivity views.** `--dry` at protocol `3bd7ef33`: guard OK (manifest `53295b64`, mask `b03a8a91`), `expansion_ok` true, `tau2_log` empty, population 83 (airline 13 and 44 masked).

| view | rtn_w4 admitted | gptq_w4_d1 admitted | M1 common blocks | k |
|---|---|---|---|---|
| primary (A6; A7 merge is a no-op for m24) | f01, f02, f03, f05, f06 (f04: `incomplete_tasks ["airline\|10"]`) | f01 to f06 | f01, f02, f03, f05, f06 | 5 |
| strict as preregistered | f03, f05, f06 (f01 retail:51, f02 retail:95, f04 airline:10) | f02 to f06 (f01 airline:2) | f03, f05, f06 | 3 |
| A6 prospective only | = strict | = strict | f03, f05, f06 | 3 |
| A6 + tool-call parse | f01 to f06 | f01 to f06 | f01 to f06 | 6 |
| pre-recovery (A7 view) | = primary | = primary | = primary | 5 |

- **Match with the phase-2 audit.** All five rows equal the §5 table of `m24_budget_audit_phase2_20261004T0017Z.md`. That audit ran at protocol `ba743cee` (A7). A7.E1 changed only q8 text and the constant, and the result is identical.
- **Admitted blocks and A6.** Every admitted block has rows 83 and complete 83. `complete_via_a6` = 1 only in rtn f01, rtn f02 and gptq f01; all three are phase 1 and were declared post hoc in A6.4 and E1.1.

**Arm-error classification.** I wrote my own scan of all 12 blocks, using my own regexes cross-checked against the frozen `a6_class` and `a6_producer`. It reads only `arm_source` strings, Y as `is None`, and the branch `error`, `n_decisions` and `infra_cause` fields.
- **Arms errored.** The arms flagged "error" in `arm_source` equal the arms with an `error` key in `branches/` in every block.
- **Gaps.** 0 row-level errors. 0 None arms without an error. 0 arms reused from an errored arm. 0 branch-file arm-set mismatches.
- **Missing rows.** The `missing_reason` rows are exactly the 14 manifest-missing rows.

| cell / block | task (pop) | state_key | arm | n_decisions | error (repr prefix) | A6 primary | A6.E1 plus | producer | matches protocol / audit |
|---|---|---|---|---|---|---|---|---|---|
| rtn f01 | retail:51 (in) | b9663570026aa870 | QB | 1 | `InvalidFunctionCallException('Function name was YOU ARE BEING TRANSFERRED…` | Y=0 (S1) | Y=0 | Q (forced a_Q) | A6.4, E1.4: yes |
| rtn f01 | retail:51 (in) | b9663570026aa870 | QQ | 1 | same | Y=0 (S1) | Y=0 | Q | yes |
| rtn f02 | retail:95 (in) | ca886db95ee998fe | QQ | 3 | same text | Y=0 (S1) | Y=0 | Q (controller) | yes |
| gptq f01 | airline:2 (in) | 09bfbba19c1e5efe | BQ | 7 | `InvalidFunctionCallException('Function name was  but must be…` (empty) | Y=0 (S1) | Y=0 | Q | yes |
| rtn f03 | airline:13 (**out**) | a05aae4744b0f026 | BQ | 2 | `JSONDecodeError('Unterminated string … (char 33)')` | missing | Y=0 | Q | yes |
| rtn f04 | airline:10 (in) | 5caebefd118b4169 | BQ | 25 | `JSONDecodeError('Unterminated string … (char 216)')` | **missing, block fails** | Y=0 | Q | phase-2 audit §4: yes |
| gptq f06 | airline:13 (**out**) | fc9daad0aa8e21ef | QQ | 57 | `InvalidFunctionCallException('Function name was  but must be…` | Y=0 (S1) | Y=0 | Q | yes |

- **Classifier agreement.** My regexes and the frozen classifier agree on all 7 arms.
- **S3, the A6 gate and B-produced arms.** No S3 arm exists. No arm has `infra_cause` together with `error`. No arm has `n_decisions` 0. No arm was produced by B, so E1.4 requires no B-produced Y = 0 to be named.
- **The one `infra_cause` branch.** It is gptq f02 airline:45 QQ, `context_overflow`, with no `error` key: the W10/W70 sentinel, already Y = 0 in the row and not an arm error.
- **JSONDecodeError arm in rtn f04.** The Q server log `logs/tasks/nmp_tau2_m24_rtn_w4_f04.Q.vllm.log` shows 1,173/1,173 `POST /v1/chat/completions` answered `200`. Its only two "Traceback" lines are import warnings at 13:40:40, before the block's first branch (13:46:14). So this error is not an outage, consistent with E1.2.

### 4. Budget and provenance: PASS

**Independent budget recount.** My counter follows tau2's `Orchestrator.step` (`third_party/tau2-bench/src/tau2/orchestrator/orchestrator.py` L895 `step_count += 1`, L327 `num_errors += 1` per error tool result). I wrote it as a different formulation from `cloq.fork.budget_used`: one step per agent/user message, plus one per tool-calling message whose results follow, plus one error per `error` tool result. The source trajectories were sha-checked against `manifest.tau2.sources` (all True), and only `task` and `messages` were kept (rewards dropped). Rows checked:
- rtn_w4 f04 airline:10, the required state, all arms;
- gptq_w4_d1 f06 airline:13;
- four hash-chosen phase-2 rows (`sha256("reviewA|cell|state_key")` minimum): rtn f06 retail:36, gptq f04 retail:113, gptq f05 retail:4, rtn f05 retail:40;
- the phase-1 sentinel gptq f02 airline:45.

Results:
- **Restored budget at the state.** It equals 200 − `steps_left` on 7/7 rows.
- **Completed arms.** On 18/18, my recount = stored `budget_recount` = live `[step_count_final, num_errors_final]`. Also `term_consistent` true, `counters_tau2_default` [0, 0], `prefix_ok` true and `env_hash_init_ok` true, and the stored `budget_ok` is true.
- **The rtn f04 airline:10 BQ arm (errored).** No counters are recorded; only `tag`, `branch`, `error`, `n_decisions` and `probe`, as the audit says. The restored budget is 3 (steps_left 197). The probe gives `counters_tau2` [0, 0] and `to_role` agent. With `n_decisions` 25, at least about 49 steps had run: well inside 200, so the error is not budget exhaustion.
- **The phase-1 overflow sentinel.** QQ has no suffix and `infra_cause context_overflow`. Its restored budget of 1 matches; the other arms recount exactly.

**Provenance, all 12 blocks:**
- summary `manifest_sha256` = `53295b64…`;
- the queue task `fork` spec equals the summary `spec`, which equals the expected panel spec (`bank_u`, one block, `subs ["U2B"]`, `noop_frac` 0.1, concurrency 8, out `tau2/m24_<cell>/<blk>`);
- `n_rows` 85; `n_missing` = the manifest-missing rows (f01: 2, otherwise 1); `n_errors` 0;
- no-op n = n_pass in every block (98/98 BB no-op checks);
- the bank row set equals the manifest's 85 rows per block;
- `Q_prompt_ok` true on 1,006/1,006 non-missing rows; no `checks` flag is false.

**Server identity, across f01 to f06, the gate outputs (bank, r2 same, r1 superseded) and all 8 BFCL fork tasks:**

| role | identity |
|---|---|
| B | `effective_config_sha` `bf306a565a30e0dd`, canary `2c2cdf5659344c4c`, `canary_ref_ok` true, `m24_textonly_v1`, `max_model_len` 33,792 |
| rtn Q | ckpt `745e96987cf3…`, config `c45539f5c5c7ccd9`, canary `66d2b463760d94e5` (RTN, W4, g128, asym) |
| gptq Q | ckpt `ed376dfb4c39…`, config `aabc19fedef1b0b6`, canary `9349e2e6f825381c` (GPTQ, W4, g128, calib c1) |

B and Q `numerics_env` are equal: batch-invariant, deterministic inductor. Q has no `canary_ref_ok`. Identity rests on the checkpoint sha plus canary equality across all tasks.

**Expansion record:**
- every `inputs.files_sha256` entry (10 files) is unchanged;
- every recorded queue task-file sha256 (10) equals the current file;
- the `expansion --model m24` dry recompute reproduces it: eligible [rtn_w4, gptq_w4_d1]; phase-1 GPU-h 11.47 and 17.98; projected 36.812 GPU-h; wall 4.602 h; expand true; the same `builder_sha256` `eb505f12…`;
- `expansion_m24.json` sha `58fdb68f…` is unchanged by the dry run.

**Reuse identity.** `analysis/fork/reuse_audit/REUSE_AUDIT.md` reports 431 m24 reuse rows, 0 flagged. Its 43 inconclusive m24 rows were render-identical in the scan.

### 5. Pre-registration hygiene: PASS with notes

**Timeline: the rules for phase 2 were fixed before phase-2 data existed, except one block, which is immaterial.**
- **Mask.** A3 and the mask (9285afc, 10-02 14:10) predate every m24 panel output: the first BFCL fork started at 19:55 and the first τ² branch was written at 23:50:45.
- **Expansion.** The record (04:53:03, pushed 04:53:13) predates the first phase-2 branch (07:47:21).
- **Branch write times (mtimes), per block:**

| block | first branch | last branch | relative to A6 (08:16:28) and A6.E1 (08:55:59) |
|---|---|---|---|
| gptq f04 | 07:47:21 | 08:24:17 | 64/84 before A6; all before A6.E1 |
| gptq f05 | 10:14 | 10:47 | after both |
| gptq f06 | 12:45 | 13:28 | after both |
| rtn f04 | 13:46 | 14:55 | after both |
| rtn f05 | 13:59 | 15:44 | after both |
| rtn f06 | 15:12 | 16:22 | after both |

- **Error arms.** The two phase-2 error arms were written at 13:19:16 (gptq f06) and 14:42:29 (rtn f04), both after A6.E1. Their classes were therefore fixed before they existed.
- **gptq f04 is the only block that straddles A6, and A6/A6.E1 cannot affect it.** It has no arm error, so every view admits it with identical rows.

**First-read forensics.** /data is ZFS with `relatime`, so atime records the first read after a write, within 24 h.
- **gptq f04 branch first reads:**
  - 30 at 08:01:18 and 9 at 08:03:47-48: matches E1.6;
  - 34 at 08:19:27: matches E1.6;
  - **2 at 08:21:22 and 9 at 08:24:24, not listed in E1.6** (N4). Each group is exactly the files created since the previous read, consistent with repeated recursive greps, not with a loader.
- **gptq f04 `bank_rows.jsonl`.** First read at 16:40:57.
- **Phase-2 `bank_rows.jsonl`, all blocks.** All six were first read together at 16:40:57. This matches A7's stated `--dry` (admission counts only) while A7 was drafted (A7 committed 16:44:25). Phase-2 branches were first read at 16:40:57 to 16:42:58, matching A7's stated error-field scan.
- **No phase-2 outcome analysis exists.**
  - No `analysis/fork/out/newmethod_m24_*` exists.
  - The only m24 outputs written after A6.E1 are the two budget-audit files.
  - A recursive search of analysis, docs, paper and scripts for files modified after 08:56 that reference m24 panel paths finds only the RESEARCH_LOG, the phase-2 audit and the reuse audit.
  - exppilot has run no analysis.

**Rules after A6.E1 do not touch m24.**
- `git diff 2f06102 HEAD -- analysis/fork/analyze_newmethod.py` adds A7: `a7_apply`, `a7_records`, `recovery=True`, the `prerecovery` view, `P3_K2V2_GATE_FAILED` and the constant.
- For m24 this is a no-op: there is no `tau2_recovery/m24_*`, so `--dry` primary = pre-recovery.
- A7's exclusion of m24 follows from E1.2 (JSONDecodeError is agent output), which was fixed at 08:55:59, before the rtn f04 arm existed. It was not a new discretionary choice.

**Post-hoc phase-1 component, disclosed (N1).** A6 re-admits rtn f01, rtn f02 and gptq f01. As a result, 2 of the 5 primary M1 blocks (f01, f02) exist only under a rule adopted after the phase-1 interim had been read. E1.1 and E1.8 disclose this, and the "A6 prospective only" view (k = 3) is computed and reported with its own Holm family.

**What the analysis script reads:**
- `bank_rows.jsonl` of all 12 blocks: needed for admission and for the preregistered complete-case and available-rows sensitivities (A3.3). That includes the refused rtn f04 rows and masked airline:13, in labelled sensitivities only.
- `branches/` lazily, only for rows with an undefined arm.
- `token_scores` only for blocks of admitted units.
- The 8 `newmethod/bfcl/bfcl_m24_*` dirs; no `ext/dev` reference dirs (`REF_BFCL` has no m24).
- Phase 2 only behind `expansion_ok` (true).
- `holdout` is guarded by `no_holdout`.
- **Gap (N6):** `a7_records` would also read `tau2_recovery/m24_*`, because recovery is not gated to q8. None exists.

### 6. Overall: CONDITIONAL GO

- **Acceptable** to create `queue/EXPPILOT_GO_newmethod_m24` once C1 to C3 hold.
- **Blocking issues:** none.
- **Non-blocking notes:** N1 to N8 below. None changes a τ² admission or the M1 block set. N1 to N5 must appear in the write-up.

---

## Part 2: Structured review

### Summary

The m24 panel runs two Q cells, rtn_w4 and gptq_w4_d1, against BF16 Mistral-Small-3.2-24B:
- **τ² panel (A).** U2B ordinary states from the BF16 trajectories, six nonce blocks, an 83-task population (A3 mask), four arms per state.
- **BFCL panel (B).** 200 items per cell.
- **Contrast.** The single primary contrast is M1 = gptq_w4_d1 − rtn_w4 on D_cc.
- **Rules.** Strict block completeness (A3.3) holds, modified by A6: agent-message validation errors (S1/S3) are scored Y = 0. A6.E1 adds two labelled sensitivities.
- **Phase 2.** f04 to f06 were released by an effect-blind expansion rule (§5/A5).

This review checks, without looking at outcomes, that:
- the frozen artifacts and amendment chain are intact;
- every required task ran once;
- the admission views and arm-error classes reproduce from raw records;
- budgets and server identities hold;
- no phase-2 outcome was read before its rules were fixed.

### Strengths

- **[S1] The amendment chain is mechanically verifiable.** Every committed protocol version is a byte prefix of its successor. Each commit updates the script constant in the same commit. Push times corroborate commit times (item 1 table).
- **[S2] Admission is reproducible from raw records.** My independent arm-error scan gives exactly the same 7 arms, classes and producers as the frozen code and both audits. `--dry` reproduces the phase-2 audit table in all five views (item 3).
- **[S3] Phase-2 rules predate phase-2 data.** A6/A6.E1 were fixed before 5 of 6 phase-2 blocks existed and before either phase-2 arm error existed. The sixth block (gptq f04) has no arm error, so no rule can move it (item 5).
- **[S4] Budgets and provenance are tight.**
  - An independent recount equals the stored and live counters on 18/18 sampled completed arms.
  - Server, checkpoint, canary and config identity hold across all τ² blocks, gates and BFCL forks.
  - The expansion inputs are unchanged since the decision (item 4).
- **[S5] Known costs were named in advance.** E1.2 named the rtn f04 loss under the primary before the arm existed: "a block with such an arm fails under the primary". The k = 6 "+ parse" view exists to show it.

### Weaknesses

- **[W1] MAJOR (reporting, N1).** 2 of the 5 primary M1 blocks (f01, f02) are admitted only through A6, which was adopted after the phase-1 interim had been read and was motivated by estimability (E1.1).
  - The prospective view (k = 3: f03, f05, f06) is the only view whose rule predates all of its data.
  - The disclosure exists (E1.1, E1.8). The write-up must give the prospective and strict rows equal prominence and say so where they disagree.
- **[W2] MINOR (N2).** `expansion_m24.json` attributes both `same` gates to the r1 tasks `nmp_gate_same_m24_<cell>`, whose own verdicts were `pass: false`. The `same_r1_superseded/gate_same.json` files confirm this.
  - The hashed `same/gate_same.json` files are the r2 outputs: sha `3495fca7…` and `01599893…`, `fail_loud` true, verdict pass.
  - The eligibility outcome is correct in substance. The record is write-once, and W100o flagged this as open, but no protocol note records it.
- **[W3] MINOR (N3).** §6 and A2.2 say "Every panel task depends on both gates of its cell". The m24 BFCL fork tasks depend only on the closed-loop runs (`make_tasks_m24.py` L194).
  - The gptq_w4_d1 BFCL forks ran on 10-02 from 19:55 to 23:46. That was before any gptq gate had passed: r1 same failed at 22:25, and r2 passed at 23:51:50.
  - Mitigation, verified:
    - the B and Q builds are identical to the gated ones (ckpt sha, config sha, canary);
    - the in-fork QQ no-op passes in all 8 dirs;
    - the replay guard shows 0 inconsistent.
- **[W4] MINOR (N4).** E1.6's first-read accounting of gptq f04 branch files is incomplete. 11 files were first read at 08:21:22 (2) and 08:24:24 (9), after A6 and before A6.E1, and are not listed. The pattern fits recursive filename greps. This is immaterial, because gptq f04 has no arm error.
- **[W5] MINOR (N5).** §9 fidelity coverage for rtn_w4 f01 is 82/83.
  - The unscored state is retail:51, the A6 state whose a_Q carries an invalid tool name: score prep raised `InvalidFunctionCallException`.
  - So the most extreme fidelity failure is absent from the KL strata and tertile cut points. This missingness is correlated with the outcome.
  - `load_scores` skips missing files and rows silently.
- **[W6] MINOR (hardening, N6).** `load_tau2(..., recovery=True)` applies `a7_records` to every model, but A7.1 scopes A7 to q8. Any future `tau2_recovery/m24_*` would be merged into the m24 primary without a protocol basis. None exists.
- **[W7] POLISH (N7).** Only A7 states its byte-prefix sha inside the protocol. A6.E1 and A7.E1 do not; they verify through git and commit messages.
  - Two statements in `m24_budget_audit_phase2_20261004T0017Z.md` are superseded:
    - its guard is `ba743cee` (now `3bd7ef33`);
    - its "E1.7: no confirmation found" was closed by W100ae (18:00).
  - The audit itself is not wrong for its time.
- **[W8] POLISH (N8).** The r2 re-run of gate_same after the r1 state-selection bug is documented in W100e-c but not in the protocol. Gates are engineering checks, not outcomes, so this needs a disclosure line, not an amendment.

### Questions for authors

- **[Q1]** What read gptq f04 branch files at 08:21:22 and 08:24:24? Was it the same reviewer grep as at 08:19:27?
- **[Q2]** If `nmp_score_m24_rtn_w4_f03` fails, will the main session refuse the T_deadline fallback, or label §9 as partial? Without action, exppilot would read the stale `n_ok 0` output.
- **[Q3]** Can `score_driver` score a_B (KLu over a_B tokens) for a row whose a_Q fails to render? The a_B quantities do not need a_Q. If it cannot, will the fidelity section name retail:51 as unscored?
- **[Q4]** Will the paper's m24 paragraph print the k = 3 prospective/strict result in the same table as the k = 5 primary and the k = 6 "+ parse" view?

### Verdict

- **Overall: conditional GO.** The evidence supports admission as computed. The remaining risks are disclosure and coverage of the descriptive fidelity section; none affects a τ² admission.
- **Revision priority:**
  1. C1 (score task done and fresh);
  2. C2 (reviewer B);
  3. C3 (GO-time re-check);
  4. N1 to N5 in the write-up.
- **Confidence by item:**
  - high on items 1, 3 and 4: direct recomputation;
  - medium-high on item 5: atime forensics see only the first read after a write within 24 h, and reads by processes that print nothing are invisible. For 5 of 6 phase-2 blocks the conclusion rests on write-time ordering, not on atimes.

### Revision plan

1. **C1.** After the task moves to `done/`, check `token_scores/m24_rtn_w4/f03/score_summary.json`: mtime > 19:18, `n_ok` 84, `n_prompt_sha_ok` 84, and `bank_rows_sha256` == sha256 of `tau2/m24_rtn_w4/f03/bank_rows.jsonl`. If it fails, decide before GO how §9 is labelled.
2. **C3.** At GO time, re-run the following and confirm the item-3 table and `tau2_log` {}:
   - `sha256sum docs/insights/NEWMETHOD_PANEL_PROTOCOL.md`;
   - `ls analysis/fork/newmethod/tau2_recovery | grep m24` (expect nothing);
   - `analyze_newmethod.py --model m24 --dry`.
3. **N1.** In the m24 results, show primary (k = 5), strict and prospective (k = 3) and "+ parse" (k = 6) side by side, with the E1.8 sentence verbatim.
4. **N2, N3, N8.** Add disclosure lines to the m24 methods and appendix:
   - the expansion record cites the r1 gate tasks, while the hashed verdict files are r2;
   - the gate_same r2 re-run and its reason;
   - the BFCL forks ran without gate dependencies, with gptq forks preceding the gate pass, plus the identity and no-op mitigation.
5. **N4.** Append the 08:21:22 and 08:24:24 reads to the E1.6 record (log or erratum); no rule change.
6. **N5.** In §9, report per-cell scored and population counts, and name retail:51 (rtn f01) as unscored because its a_Q fails validation.
7. **N6.** Optional, with a dated note: gate `recovery` on `model == "q8"`. Otherwise keep the GO-time check in C3.

---

## Part 3: Inline annotations

> "**m24 phase 2:** no `nmp_tau2_m24_*_f0{4,5,6}` task had finished. `gptq_w4_d1` f04 was running ... None of their outputs had been opened." (A6, status)

**[W4] MINOR:** E1.6 corrects this sentence. The corrected record is itself incomplete (next annotation).

> "both greps printed file names only. None of the 64 contained an arm error. No loader, `--dry` or content read touched them." (A6.E1 E1.6)

**[W4] MINOR:** This is verified for the 39 pre-A6 first reads and the 34 at 08:19:27. Not listed: 2 files first read at 08:21:22 and 9 at 08:24:24, all after A6 and before A6.E1. "None of the 64 contained an arm error" holds for all 84 gptq f04 records (0 error arms in my scan).

> "m24 has no arm error outside the A6/A6.E1 agent-output classes (InvalidFunctionCallException, and JSONDecodeError on the agent's own tool-call arguments). A7 does not apply to m24." (A7, what was known)

**Verified:** 7 arm errors over f01 to f06, 5 S1 and 2 JSONDecodeError, all with `n_decisions` ≥ 1, all Q-produced.
**[W6] MINOR:** the code does not enforce "A7 does not apply to m24": `load_tau2(recovery=True)` reads `tau2_recovery/<model>_*` for any model.

> "A gate counts only if its queue task is done, its spec `out` is the expected directory, and its verdict passes" (A5.1)

**[W2] MINOR:** For m24, the counted task is r1 (`nmp_gate_same_m24_<cell>`), whose own verdict was false (`same_r1_superseded/gate_same.json`). The verdict that passed is r2's, written to the same `out`. The decision is right in substance, but the attribution is wrong in the write-once record.

> "Dependencies: gates → panel tasks → score tasks. Every panel task depends on both gates of its cell." (§6); "Every panel task depends on both gates of its cell (§6)." (A2.2)

**[W3] MINOR:** The `nmp_bfcl_m24_*` tasks have deps `[ext_m24_<cell>_bfcl_nmp1, ext_m24_bf16_bfcl_nmp1]` only. The gptq_w4_d1 BFCL forks finished before its gate_same passed. Identity and no-op mitigation are verified (item 4); disclose the deviation.

> "A6 was proposed after the m24 phase-1 interim (`analysis/fork/out/m24_interim_20261003T141416Z.md`, 07:14 PDT) had been read." (A6.E1 E1.1)

**[W1] MAJOR (reporting):** `--dry` confirms that A6 alone admits rtn f01, rtn f02 and gptq f01, which puts f01 and f02 into M1 (2 of 5 primary blocks). The prospective view is the clean pre-registered reading and must sit beside the primary in every m24 table.

> "On that record A6 scores 4 arms in 3 population states as Y = 0, all S1" (A6.4); "All four m24 phase-1 A6 arms are Q-produced: retail:51 QB and QQ (forced a_Q, `n_decisions` 1); retail:95 QQ (3); airline:2 BQ (7)." (A6.E1 E1.4)

**Verified** from the branch records: the same arms, signatures, `n_decisions` and producers.

> "`load_scores` silently skips missing files, so an analysis run now would compute the phase-1 KL tertile cuts and strata from partial scores." (phase-2 audit §6.3)

**Still true for rtn_w4 f03** until the running task finishes (C1). **[W5]:** even when complete, rtn f01 lacks retail:51 (score prep `InvalidFunctionCallException`).

> "E1.7 (procedural, required by the protocol text) ... No confirmation was found in `docs/RESEARCH_LOG.md`" (phase-2 audit §6.1)

**[W7] POLISH:** This was superseded at 18:00 PDT by W100ae ("E1.7 is closed: S3 and the q8 scope of A6 are kept"). No m24 arm is S3, so the confirmation cannot change m24 admission.

> "Admission, from `analyze_newmethod.py --model m24 --dry`, guard: protocol `ba743cee…`" (phase-2 audit §5)

**[W7] POLISH:** At `3bd7ef33` (A7.E1), `--dry` reproduces every row of that table. A7.E1 touches q8 text and the constant only.

> "The text above this section is unchanged and is a byte-identical prefix (sha256 b306cc70ebfca526472e519baa32f5ed7f698e953711f88eb987a9bc6e61771c, the A6.E1 version)." (A7)

**Verified:** the first 76,745 bytes of the current file hash to exactly this value.

> "**Expected flag, not a fault:** template ids equal the recorded BF16 a_B completion ids on 35/84 rows." (W100o)

**[Q3]:** Teacher forcing on generated ids is fine. The separate issue is that a row whose a_Q cannot be rendered loses its a_B scores too (retail:51).

---

## Sources

Local evidence only; no web sources were used. All paths are relative to `/data/ziyangs/cloq` unless absolute.

- Protocol and history:
  - `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md`;
  - `git show <c>:docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` for 870d1ba, 0af849b, 50fc648, 9285afc, fae1fe3, 79b4ab4, fe6765e, 2f06102, 10a5518, 861ebff;
  - `git reflog refs/remotes/origin/master` (remote https://github.com/W4ng77/cloq).
- Code:
  - `analysis/fork/analyze_newmethod.py`, with `git diff 2f06102 HEAD`;
  - `scripts/a6000/make_newmethod_panel.py` (`expansion`);
  - `scripts/a6000/make_tasks_m24.py` (L154-194);
  - `scripts/a6000/exppilot_analysis.py`;
  - `cloq/fork.py` (L143-165);
  - `third_party/tau2-bench/src/tau2/orchestrator/orchestrator.py` (L313-329, L820-896).
- Frozen inputs:
  - `manifests/fork/newmethod_panel_v1_m24.json` (sha `53295b64…`);
  - `manifests/fork/newmethod_panel_v1_m24_mask_v1.json` (sha `b03a8a91…`);
  - `analysis/fork/newmethod/expansion_m24.json` (sha `58fdb68f…`).
- Data:
  - `analysis/fork/newmethod/tau2/m24_{rtn_w4,gptq_w4_d1}/f0{1..6}/{bank_summary.json, bank_rows.jsonl, branches/}`;
  - `analysis/fork/newmethod/token_scores/m24_*/f0*/score_summary.json`;
  - `analysis/fork/newmethod/gate/m24_*/{same,bank,same_r1_superseded}/`;
  - `analysis/fork/newmethod/bfcl/bfcl_m24_*/dev_summary.json` (fields `qq_noop_ok` only);
  - `runs/a6k2_m24_bfpair_f0{2,4,5,6}/{retail,airline}/trajectory.jsonl` (`task` and `messages` only).
- Audits:
  - `analysis/fork/out/m24_budget_audit_20261003T1354Z.md`;
  - `analysis/fork/out/m24_budget_audit_phase2_20261004T0017Z.{md,json}`;
  - `analysis/fork/reuse_audit/REUSE_AUDIT.md`, `reuse_flagged.json`.
- Queue and logs:
  - `/data/ziyangs/cloq_work/queue/{done,running}/nmp_*_m24_*.json`, `ext_m24_*_bfcl_nmp1.json`;
  - `/data/ziyangs/cloq_work/exppilot_state.json`;
  - `/data/ziyangs/cloq_work/logs/exppilot.log`;
  - `/data/ziyangs/cloq_work/logs/tasks/nmp_tau2_m24_rtn_w4_f04.Q.vllm.log` (HTTP status lines);
  - `/data/ziyangs/cloq_work/logs/tasks/nmp_score_m24_rtn_w4_f03.log`.
- Research log: `docs/RESEARCH_LOG.md` W100e-c, W100o, W100s, W100v, W100v-e, W100ab, W100ac, W100ad, W100ae, W100af.
- Reviewer scratch scripts (not repo artifacts):
  - `/tmp/claude-1064/-home-ziyangs/4a7ccb09-009e-4aee-b4c9-ef93691bb496/scratchpad/scan_errors.py`;
  - `/tmp/claude-1064/-home-ziyangs/4a7ccb09-009e-4aee-b4c9-ef93691bb496/scratchpad/spot_budget.py`;
  - `/tmp/claude-1064/-home-ziyangs/4a7ccb09-009e-4aee-b4c9-ef93691bb496/scratchpad/dry_m24.json`.
