# q8 new-method panel, phase 1 (f01-f03): acceptance review B, independent re-derivation from raw files

Reviewer B of 2. Review A (`q8_acceptance_review_A.md`) was not read. State as of 2026-10-04 02:47 UTC (2026-10-03 19:47 PDT). Repo HEAD f3800bc; the files under review are unchanged since 744f7c4:
- `analyze_newmethod.py`, sha `dbc133b3...`;
- the protocol, sha `3bd7ef33...` (A7.E1);
- the manifest, sha `7534c690...`;
- the builder, sha `eb505f12...`.

Effect-blind. No effect, contrast, success rate or outcome aggregate was computed or printed. Y was read only as "defined (0/1) or not".
- `analyze_newmethod.py` ran only with `--dry` and `--selftest`.
- In one extra check, the script was imported in-process to compare per-unit arm vectors with this re-derivation by equality only, with `unit_effects` stubbed to return nothing. That check printed only mismatch counts.
- `analysis/fork/holdout/` was never opened. Nothing in the repo was modified; this file is the only write.

## TL;DR

- **Verdict: CONDITIONAL GO. There is no blocking issue and no disagreement, but `queue/EXPPILOT_GO_newmethod_q8` must not be written yet.**
  - Two A7 re-runs are still running: `a7_rr1_q8_kivi_k2v2_f03` and `a7_rr1_q8_kivi_k4v4_f01`.
  - `exppilot_analysis.required()` does not list `a7_rr1_*` tasks. Every task it does list is now done, so a GO written now would start the once-only analysis at once, without these two blocks' re-run arms. That contradicts A7.1 and A7.4.
- **Item 1 (admission). The raw re-derivation equals `--dry` in every view, with 0 disagreements:**
  - 24 panel blocks and 9 Bank U reference blocks;
  - views: primary, pre-recovery, strict as preregistered, A6 prospective, A6 + parse.
  - An in-process equality check of the script's per-unit arm vectors against this re-derivation gave 0 mismatches over 2,805 units in each of 4 views.
  - **Primary now:** every cell is admitted for f01-f03, except kivi_k2v2 {f01, f02} and kivi_k4v4 {f02, f03}.
  - **Pre-recovery = strict:** spinquant_w4a4 {f02, f03}, kivi_k2v2 none, kivi_k4v4 {f02, f03}, every other cell f01-f03.
- **Item 2 (A7 merge).** The 31 named arms are equal in three sources: the protocol's A7.1 list, `failed_arms.json` and the five task specs (`fork.arms`).
  - The finished re-runs merge exactly their spec arms (1 + 4 + 9 = 14 arms, all completed). Every state identity check is true.
  - B/Q canary, `ckpt_sha256`, `effective_config_sha` and `hook_version` equal `a7_expect` and the original block, for all 5 tasks. Each task started once.
  - **kivi_k2v2 f03 is already settled.** Its re-run of airline:14 QQ (`01a17956873df0ef`) failed again with `litellm.Timeout` at `n_decisions` 31. So **kivi_k2v2 f03 cannot be admitted under any view**, whatever the remaining state does.
- **Item 3 (expansion).** `expansion_q8.json` was written once, at 19:08:29 PDT, by trigger (a). All 8 cells were eligible.
  - Projection: 1.25 x (124.079 + 13.105) GPU-h / 8 GPUs = 21.435 h of wall time. The run would finish at 10-04 16:34 PDT, after T_deadline 12:00 PDT, so expand = false (§5.5 all-or-none). The recomputation matches the record.
  - The decision does not depend on SAFETY: even at 1.0 the wall time (17.15 h) exceeds the 16.86 h available.
  - All 50 recorded input files are unchanged. No phase-2 q8 task exists in any queue state.
- **Item 4 (contrasts).**
  - P1, P2 and P3 are final now. Primary k = 3, 3 and 2. Pre-recovery and strict: P1 k = 3, P2 k = 2, P3 not estimable.
  - Only K2 and A44_k4 can still change: they reach k = 3 under the primary only if all 11 pending kivi_k4v4 f01 arms complete.
  - P3 and A44_k2 have k = 2 (df 1).
- **Item 5 (score and BFCL tasks).**
  - Score: all 24 `nmp_score_q8_*` tasks are done. Each `score_summary.json` `bank_rows_sha256` equals the current `bank_rows.jsonl`. Each has n_ok 85, prompt sha 85/85 and the same B/Q servers as its panel block.
  - BFCL: all 7 registered q8 BFCL cells are done (1 closed-loop run + 4 forks each). kivi_k16v16 has no BFCL by A4.1 ("not run"). `--dry` shows no quarantined or incomplete BFCL directory, and replay-inconsistent is 0 over 44 directories.

## 1. Admission re-derived from raw rows (item 1)

### Method

The re-derivation is my own code (`derive.py`, `compare.py` in this session's scratchpad). It does not import `analyze_newmethod`.
- **Panel rows.** For each of the 8 cells x f01-f03, `bank_summary.json` is checked:
  - `manifest_sha256` = `7534c690...`;
  - `spec.cell` and `spec.blocks`;
  - no-op `n_pass` = `n`.
- **Identity.** Every `bank_rows.jsonl` row must have `sub` U2B and `model` q8. `state_key`, `t`, `source_run`, `domain`, `task_id` and `block` must equal the manifest row, and `checks.Q_prompt_ok` must be true.
- **Undefined arms.** An undefined arm is Y not in {0, 1}. Each one is classified from its `arm_source` (`error: ...` or `reuse=XX`) and, for errors, from the branch record (`branches/<state_key>.json`: `error` prefix, `n_decisions`, `infra_cause`).
- **A6.2.** My own regexes: S1 `InvalidFunctionCallException('Function name was`, S3 `ValueError('AssistantMessage must have either content or tool_calls`, with `n_decisions` >= 1 and no `infra_cause`. The A6.E1 "plus" view adds `JSONDecodeError(` in retail and airline.
- **A7.4 merge.** Only finished recoveries count (`rr1/recovery_summary.json` present). Only records with `Y`, every `state_identical` field true, and arms named in the queue task's `fork.arms` are used.
  - Each named arm takes the re-run value, `arm_source` and branch record.
  - A reused arm `reuse=XX` whose XX was re-run takes XX's new value. A6 is applied afterwards.
- **Strict block rule (§7, A3.3).** A block is admitted iff 85 complete four-arm rows cover the 85-task population exactly. q8 has no mask.
- **Reference cells.** `analysis/fork/bank_u/q8_{gptq_w4_d1,awq_w4,kvq_int8}/f0k`, U2B rows only. The summary `manifest_sha256` must be `e236ee64...` (the Bank U sha in `BANK_U_SHA256`), with the same identity test and whole-block no-op as `take()`.

### Result per block

Cells and blocks not listed below have 0 undefined arms.

| cell / block | U2B rows, identity ok | no-op | rows with an undefined arm before merge (error arms + reuse-dependent arms) | after the A7 merge now | admitted: primary / pre-recovery / strict |
|---|---|---|---|---|---|
| quarot_w4 f01, f02, f03 | 85, 85, 85 | 6/6, 7/7, 7/7 | 0 | 0 | yes / yes / yes |
| quarot_w4a4 f01, f02, f03 | 85 each | 7/7, 11/11, 13/13 | 0 | 0 | yes / yes / yes |
| quarot_w16 f01, f02, f03 | 85 each | 7/7, 8/8, 9/9 | 0 | 0 | yes / yes / yes |
| spinquant_w4a4 f01 | 85 | 6/6 | **8** (9 + 1) | 0 (8 rows completed by A7) | **yes / no / no** |
| spinquant_w4a4 f02, f03 | 85 each | 10/10, 9/9 | 0 | 0 | yes / yes / yes |
| spinquant_w16 f01, f02, f03 | 85 each | 6/6, 10/10, 9/9 | 0 | 0 | yes / yes / yes |
| kivi_k2v2 f01 | 85 | 15/15 | **1** (1 + 0) | 0 | **yes / no / no** |
| kivi_k2v2 f02 | 85 | 9/9 | **4** (4 + 0) | 0 | **yes / no / no** |
| kivi_k2v2 f03 | 85 | 8/8 | **4** (5 + 1) | 4 (A7 running) | no / no / no |
| kivi_k4v4 f01 | 85 | 7/7 | **8** (12 + 8) | 8 (A7 running) | no / no / no |
| kivi_k4v4 f02, f03 | 85 each | 6/6, 9/9 | 0 | 0 | yes / yes / yes |
| kivi_k16v16 f01, f02, f03 | 85 each | 9/9, 4/4, 9/9 | 0 | 0 | yes / yes / yes |
| gptq_w4_d1 f01, f02, f03 (Bank U, 85 of 190 rows) | 85 each | 25/25, 17/17, 16/16 | 0 | n/a | yes / yes / yes |
| awq_w4 f01, f02, f03 (Bank U) | 85 each | 16/16, 17/17, 19/19 | 0 | n/a | yes / yes / yes |
| kvq_int8 f01, f02, f03 (Bank U) | 85 each | 15/15, 18/18, 15/15 | 0 | n/a | yes / yes / yes |

The undefined rows, by state, all have arm errors of server-side type:
- **spinquant_w4a4 f01** (`litellm.Timeout`, the user simulator):
  - retail:7 QQ (BQ=reuse=QQ);
  - airline:23 BQ and QQ;
  - airline:32 QQ, airline:33 QB, airline:4 QQ, airline:45 QB, airline:47 QQ, airline:8 QQ.
  - All 9 re-run arms completed.
- **kivi_k2v2 f01** (`litellm.Timeout`): airline:32 QQ, completed.
- **kivi_k2v2 f02** (`litellm.Timeout`): retail:45 QQ, retail:89 BQ, airline:13 BQ and airline:17 BQ, all completed.
- **kivi_k2v2 f03** (`litellm.Timeout`):
  - airline:14 QQ (BQ=reuse=QQ): **re-run failed again** (`Timeout`, `n_decisions` 31);
  - airline:19 QQ and retail:21 QQ: re-run branch records written without an error;
  - retail:99 BQ and QQ: pending. The task has no `recovery_summary.json` yet, so nothing is merged.
- **kivi_k4v4 f01** (`litellm.InternalServerError`):
  - retail:27, airline:14, :17, :18, :2 and :28 QQ, each with BQ=reuse=QQ;
  - airline:23 BB and QQ (QB=reuse=BB, BQ=reuse=QQ);
  - airline:3 BB, BQ, QB and QQ;
  - re-run status: airline:14 QQ written without an error, 11 arms pending.
- **A6 changes nothing on q8.** No q8 panel or reference arm matches S1, S3 or the E1 `JSONDecodeError` class. So for q8, pre-recovery = strict, and A6 prospective = A6 + parse = primary.

### Comparison with the script

**Comparison with `--dry`** (`analyze_newmethod.py --model q8 --dry`, run 02:39 UTC, rc 0):
- `tau2_blocks`, `tau2_blocks_pre_recovery`, `tau2_blocks_strict_prereg`, `tau2_blocks_a6_prospective` and `tau2_blocks_a6_plus_toolcall_parse` give, for every cell and block, the same admitted flag, the same complete count (85, 84, 81 or 77) and the same incomplete-task list as above.
- `tau2_log` is empty (no refusal, quarantine or identity failure).
- guard: protocol `3bd7ef33...`, manifest `7534c690...`; population 85 with no mask; `expansion_ok` false.

`--selftest`: PASS, including A6 and A7.

**In-process equality check.** `load_tau2(q8, a6=True, views, recovery=True)` was run with effects stubbed. Its per-unit four-arm vector (or exclusion) equals this re-derivation:
- on all 2,805 units (24 x 85 panel + 9 x 85 reference);
- in each of primary, prerecovery, strict and plus;
- with 0 mismatches.

So the A7 merge, including reuse propagation (spinquant_w4a4 f01 retail:7 BQ follows the re-run QQ), is computed identically. The script's A7 report covers exactly kivi_k2v2 f01 (1) and f02 (4) and spinquant_w4a4 f01 (9), all "rerun".

## 2. A7 merge provenance (item 2)

- **Named arms.** The protocol A7.1 list (parsed from the text), `analysis/fork/kivi_recovery/failed_arms.json` (committed e370e4b at 16:57:30, 2 s before the first A7 task was created) and the union of `queue/*/a7_rr1_q8_*.json` `fork.arms` are the same 31 (cell, block, state_key, arm) tuples:
  - kivi_k4v4 f01: 12, service_failure_verified;
  - kivi_k2v2: 10, timeout_cause_not_established;
  - spinquant_w4a4 f01: 9, other, re-run by A7.E1.
- **Finished tasks** (kivi_k2v2 f01 and f02, spinquant_w4a4 f01):
  - `recovery_summary.json` `spec` equals the queue task's `fork` byte for byte; manifest sha `7534c690...`;
  - `n_arms` 1, 4 and 9, all recovered; 0 failed again, 0 refused, 0 errors; `shadow_identical` 1/1, 4/4 and 8/8; `budget_ok` true;
  - the rr1 arm set equals the spec arm set; every record has all 4 `state_identical` fields true (state_id, history_sha, prompt_ids_sha, steps_left);
  - each task log shows one start (`=== ...` lines), and no rr2 directory exists.
- **Servers.** For all 5 tasks, `logs/tasks/<id>.servers.json` B and Q, plus `recovery_summary.servers` for the 3 finished tasks, equal `a7_expect` in `canary`, `ckpt_sha256`, `effective_config_sha` and `hook_version`. They also equal the original `nmp_tau2_q8_<cell>_<blk>.servers.json`.
  - B: `e340c799` / `0d4bf272` / null / null, with `canary_ref_ok` true.
  - Q: k2v2 `60cac990` / `485c96e5` / null / `30020b75`; k4v4 `27dfdf09` / `da5099eb` / null / `30020b75`; spinquant `66028ece` / `f3298098` / `b7223e20...` / `30020b75`.
  - The B and Q task roles are verbatim copies of the original tasks. Only spinquant f01 names `user_base` `node001:8000`, as A7.E1 approved.
- **How the script guards this (hardening note, not blocking).** `a7_records` and `a7_apply` do not themselves check rr1 arms against the queue spec, nor `state_identical`, the summary sha or `a7_expect`.
  - They rely on `fork_driver.bank_u_arms`, which refuses unnamed or non-failed arms, writes no `Y` when the state differs, and merges only records with `Y`.
  - This is verified externally above for the 3 finished tasks, and must be repeated for the 2 running ones (C1).

## 3. Expansion decision (item 3)

- **Written once.**
  - The file has one link (nlink 1) and mtime 19:08:29.18 PDT, which equals its `now`.
  - `expansion_sched.log` has a single write event, and no stray `.tmp` file exists.
  - It was committed once, in 2a607db, and its sha `e63dd997...` equals the HEAD blob.
  - `builder_sha256` `eb505f12...` equals the current committed builder. A7 (10a5518, 16:44) and A7.E1 (861ebff, 17:44) predate it (A7.6).
- **Trigger.** "all phase-1 tasks finished": all 24 `nmp_tau2_q8_*` tasks were done before T_decide 20:00 PDT, and the snapshot is the decision run itself (A5.4).
- **Eligibility.** All 8 registered cells (A5.1):
  - gates pass (KIVI on the `_fx` gates; kivi_k4v4 also `kivi_gate_q8_toy4` T1 strict = true; the gate files were re-read here);
  - every block complete under A5.2 (n_rows 85, n_ok 85, n_missing 0, n_errors 0, every no-op passed, `finished` <= now);
  - so there is no A5.3 pairing exclusion.
- **Cost.** The recomputation equals the record:
  - phase-1 GPU-h summed from summary seconds x gpus: 124.079;
  - reference U2B share (85/190 x 2 GPUs over the 9 Bank U blocks): 13.105;
  - P = 171.48 GPU-h; wall time 21.435 h; finish 2026-10-04 23:34:35 UTC, which is after T_deadline 19:00 UTC;
  - expand = false and `phase2_cells` = [].
- **Inputs.** All 50 entries of `inputs.files_sha256` match the current files.
- **No phase 2 queued.** No `nmp_{tau2,score}_q8_*_f0{4,5,6}` task exists in todo, running, done, failed, deferred, parked or legacy. exppilot logged "phase 2 q8: record says expand=False; nothing queued (§5.5)" at 19:14:44.
  - The `analyze_newmethod` glob finds only f01-f03 directories for q8, so W100q F1a (the gptq f04-f06 reference outputs) is moot for this analysis.

## 4. Common admitted blocks per contrast (item 4)

"After A7" means once both running tasks finish.
- kivi_k2v2 f03 stays out in every view, because of the airline:14 persistent timeout.
- kivi_k4v4 f01 enters the primary (and therefore the prospective and plus views) only if all 11 pending arms complete.
- Pre-recovery and strict cannot change.
- The A6 prospective and A6 + parse views equal the primary throughout.

| id | cells | primary now | primary after A7 | pre-recovery | strict as preregistered |
|---|---|---|---|---|---|
| P1 | quarot_w4 - gptq_w4_d1 | f01-f03 (k 3) | same | k 3 | k 3 |
| P2 | spinquant_w4a4 - quarot_w4a4 | f01-f03 (k 3) | same | f02, f03 (k 2) | f02, f03 (k 2) |
| P3 | kivi_k2v2 - kvq_int8 | f01, f02 (k 2) | f01, f02 (k 2, final) | not estimable (0) | not estimable (0) |
| T1 | quarot_w4 - quarot_w16 | k 3 | same | k 3 | k 3 |
| T2 | spinquant_w4a4 - spinquant_w16 | k 3 | same | f02, f03 | f02, f03 |
| T3 | quarot_w4a4 - quarot_w16 | k 3 | same | k 3 | k 3 |
| K2 | kivi_k4v4 - kvq_int8 | f02, f03 (k 2) | f01-f03 iff all 11 pending arms complete, else f02, f03 | f02, f03 | f02, f03 |
| A44_k2 | kivi_k2v2 - kivi_k16v16 | f01, f02 | f01, f02 (final) | not estimable | not estimable |
| A44_k4 | kivi_k4v4 - kivi_k16v16 | f02, f03 | as K2 | f02, f03 | f02, f03 |

- **Holm primary family.** Primary: {P1, P2, P3}. Pre-recovery and strict: {P1, P2}, with P3 not estimable.
- **P3 fallback.** `P3_K2V2_GATE_FAILED` = False, and kivi_k2v2 passed its `_fx` gates, so P3 never falls back to k4v4 (A7.5).

## 5. Score and BFCL tasks (item 5)

- **Score.** All 24 `nmp_score_q8_<cell>_f0{1,2,3}` are in done. Each `score_summary.json`:
  - has `bank_rows_sha256` equal to the sha256 of the current `analysis/fork/newmethod/tau2/q8_<cell>/<blk>/bank_rows.jsonl`;
  - was written after it;
  - has `spec.bank_out`, `cell` and `blocks` matching; n_rows 85, n_ok 85, n_missing 0; prompt sha 85, render 85, start-same 85;
  - has B and Q canary, `effective_config_sha` and `ckpt_sha256` equal to its panel block;
  - has 85 lines in `scores.jsonl.gz`.
- **Reference token scores** (`analysis/fork/token_scores/q8_<ref>/f0k`): 85/85 U2B rows are scored, bound to the current Bank U `bank_rows`.
- **BFCL.** `ext_q8_<cell>_bfcl_nmp1` and `nmp_bfcl_q8_<cell>_{base,miss_param,miss_func,long_context}` are done for quarot_w4, quarot_w4a4, quarot_w16, spinquant_w4a4, spinquant_w16, kivi_k2v2 and kivi_k4v4. kivi_k16v16 BFCL is not registered (A4.1) and is reported "not run".
- No `nmp_*_q8_*` task is outside done.

## 6. Additional checks

- **Reuse scan (W100ae open item: spinquant_w4a4 f03 landed after `REUSE_AUDIT.md`, see its L182).**
  - Method: every `exact_agreement` row with a `reuse=` arm in all 24 q8 panel blocks, with a_B and a_Q rendered through the Qwen3-8B chat template (b968826d, `enable_thinking` false; tool-call id not rendered) and compared token by token.
  - Result: 1,200 reuse rows, **0 token-different**. spinquant_w4a4 f03 has 28 rows and 0 flagged. The per-directory counts for the other 23 blocks equal REUSE_AUDIT's table.
  - The test has power: a swapped argument key order is detected, and an id-only change is ignored.
- **Budget.** `budget_ok` is true in all 24 panel summaries, in every row's per-arm `budget_ok` (2,040 rows) and in all rr1 records. No arm-level recount was done here; that is the audit's scope.
- **E1.7.** S3 and the q8 scope of A6 were confirmed (W100ae), and they change nothing on q8.
- **No q8 read yet.** No `analysis/fork/out/newmethod_q8_*` exists.

## 7. Verdict and conditions for writing `queue/EXPPILOT_GO_newmethod_q8`

**Verdict: CONDITIONAL GO, no blocking issue.** The raw re-derivation agrees with `--dry` and with the script's in-process merge in every view. Expansion, gates, the A7 provenance of the finished re-runs, the score bindings and the BFCL tasks all check out. GO is withheld only because of C1.

**C1 (required).** Both `a7_rr1_q8_kivi_k2v2_f03` and `a7_rr1_q8_kivi_k4v4_f01` have left running/. For each one that is done:
- `recovery_summary.json` exists, its `spec` equals the queue task's `fork`, and its manifest sha is `7534c690...`;
- the rr1 arm set equals the spec arms (5 and 12);
- every record with `Y` has all 4 `state_identical` fields true;
- `servers.json` and `recovery_summary.servers` B/Q (`canary`, `ckpt_sha256`, `effective_config_sha`, `hook_version`) equal `a7_expect`;
- the task log shows one start, and no rr2 exists.

A task that ends in failed/ merges nothing and is reported as such.

Deadline: A7.1 allows re-runs until 2026-10-04 21:00 PDT, and exppilot's T_deadline is 12:00 PDT. If kivi_k4v4 f01 is still running at a cutoff the main session sets for the read, the main session records that cutoff in a dated note before writing GO. Its unfinished arms then stay missing, which affects only K2 and A44_k4. Alternatively, it re-runs the analysis once the task finishes and labels the later output primary.

**C2 (required).** Re-run `--dry` after C1 and confirm:
- the primary admits every cell f01-f03 except kivi_k2v2 {f01, f02} and kivi_k4v4 {f02, f03}, or {f01, f02, f03} only if its recovery summary shows 12 recovered, 0 failed again and 0 refused;
- pre-recovery = strict = spinquant_w4a4 {f02, f03}, kivi_k2v2 none, kivi_k4v4 {f02, f03}, the rest f01-f03;
- A6 prospective = A6 + parse = primary;
- `tau2_log` is empty, there are no BFCL quarantines, and replay-inconsistent is 0;
- protocol sha `3bd7ef33...`, manifest `7534c690...`, `expansion_ok` false; `analyze_newmethod.py` sha is unchanged from `dbc133b3...`, or any change is reviewed.

**C3 (recommended; affects only K2 and A44_k4).** Two kivi_k4v4 f01 no-op-sample rows (airline:23 `9749f30f7ffd3c41`, airline:3 `95d6b21e8fc7af2b`) have an errored BB, so their no-op check never ran; the block's 7/7 excludes them. `bank_u_arms` re-runs BB without comparing it with the original.
- If those BB arms recover, compare the rr1 BB branch with the source original on the identity fields of `fork_driver.noop_check` (suffix_sha, suffix prompt-id shas, termination, `env_hash_final` against the original replay), by equality only.
- A mismatch is a §2.3 no-op mismatch and needs a dated ruling before the read. Otherwise, report the coverage gap.

**C4 (required, procedural).** `expansion_q8.json` is unchanged (sha `e63dd997...`) and no q8 phase-2 task is queued.

**Blocking issues: none.**

## 8. Notes for the write-up (non-blocking)

1. **kivi_k2v2 f03.** airline:14 QQ timed out again on the concurrency-1 re-run, so A7.2 labels it "persistent timeout" and its timing must be reported.
   - Completion length can depend on model behaviour (E1.5), so this missingness may be outcome-related, as A6.1 discusses.
   - It removes f03 from kivi_k2v2 in every view, so P3 and A44_k2 rest on k = 2, where the primary t interval has df 1.
2. **P2 and T2.** They reach k = 3 only through the A7.E1 re-run of 9 spinquant_w4a4 f01 user-simulator-overload arms (class "other", approved after classification). Pre-recovery and strict have k = 2. Report both, with the A7.7 wording.
3. **Simulator identity.** The A7.E1 re-run used another user-simulator replica (node001:8000). `servers.json` fingerprints B and Q but records only the simulator's URL, so simulator-replica identity is assumed, not checked. The same holds for any original task whose node routed through `USER_BASE.<node>`.
4. **BFCL secondaries.**
   - K2 is not estimable on BFCL, because `kvq_int8` is not a BFCL reference cell (`REF_BFCL` has `kvq_int4`).
   - A44_k2 and A44_k4 are not estimable on BFCL, because kivi_k16v16 has no BFCL (A4.1).
   - The script reports these as "cell not admitted". That label should read "not run / not a BFCL reference cell".
5. **Disclosure.** The in-process `load_tau2` comparison in §1 goes beyond the literal "--dry/--selftest only" instruction. It loads exactly what `--dry` loads, with effects stubbed, and printed only equality counts.

## Evidence

- Panel: `analysis/fork/newmethod/tau2/q8_<cell>/f0{1,2,3}/{bank_summary.json,bank_rows.jsonl,branches/}`.
- Reference: `analysis/fork/bank_u/q8_{gptq_w4_d1,awq_w4,kvq_int8}/f0{1,2,3}/`.
- A7:
  - `analysis/fork/newmethod/tau2_recovery/q8_*/f0*/rr1/`;
  - `/data/ziyangs/cloq_work/queue/{done,running}/a7_rr1_q8_*.json`;
  - `/data/ziyangs/cloq_work/logs/tasks/{a7_rr1_q8_*,nmp_tau2_q8_*}.servers.json`;
  - `analysis/fork/kivi_recovery/failed_arms.json`.
- Expansion: `analysis/fork/newmethod/expansion_q8.json`, `/data/ziyangs/cloq_work/logs/expansion_sched.log`, `/data/ziyangs/cloq_work/logs/exppilot.log`.
- Score: `analysis/fork/newmethod/token_scores/q8_*/f0*/score_summary.json`.
- Gates: `analysis/fork/newmethod/gate/q8_*/{same,bank}/`, `analysis/fork/kivi_gate/gate_q8_toy4.json`.
- Scripts and specs: `scripts/a6000/{fork_driver.py (bank_u, bank_u_arms), make_tasks_a7.py, make_newmethod_panel.py (decide), exppilot_analysis.py (required)}`, `analysis/fork/analyze_newmethod.py`, `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (§2.3, §5, §7, A3.3, A5, A6, A6.E1, A7, A7.E1).
