# q8 new-method panel, phase-1 acceptance audit: per-branch CPU check of f01 to f03, A7 recovery status, reuse scan of spinquant_w4a4 f03 (2026-10-04 02:26 UTC)

State as of 02:31 UTC. A7 and `--dry` were re-read after `a7_rr1_q8_spinquant_w4a4_f01` finished at 02:29 UTC.

**TL;DR**
- **No q8 branch fails `budget_check`.** `budget_ok` and `gate_pass` are true in all 24 panel summaries (8 cells x f01-f03) and in the 9 Bank U reference summaries. There are no context-overflow sentinels.
- **The independent recount matches everywhere: 0 mismatches.**
  - 3,892/3,892 completed panel branches;
  - 1,434/1,434 reference U2B branches;
  - 17/17 recovered A7 arms.
  - The recomputed `budget_check` equals the stored flag on every one of them. The restored budget equals 200 - `steps_left`, and `state_id` and `history_sha` recompute exactly, on 2,040/2,040 panel rows and 765/765 reference rows.
- **Provenance holds for every block:**
  - panel manifest sha `7534c690...`; the spec equals the panel spec and the queue spec;
  - `n_rows` 85, `n_ok` 85, `n_missing` 0, `n_errors` 0 (q8 has no mask: 85 tasks);
  - every no-op passed;
  - one attempt per task;
  - the source trajectory and decision shas equal the manifest;
  - B and Q canary, checkpoint sha, effective config and hook version are identical across f01-f03 in every cell.
- **31 arm errors (Y = None).** All are in `failed_arms.json`, and all are infrastructure errors, not A6/A6.E1 agent output:
  - kivi_k2v2: 10 `Timeout` (f01 1, f02 4, f03 5);
  - kivi_k4v4 f01: 12 `InternalServerError` (user simulator down);
  - spinquant_w4a4 f01: 9 `Timeout` (user simulator overload).
  - No S1, S3 or `JSONDecodeError` arm exists in any q8 panel block or reference U2B row. spinquant_w4a4 f03 has 0 arm errors, so A7.1 needs no new task.
- **A7 status now: 17 arms recovered, 1 failed again, 13 pending.**
  - **Done and fully recovered:** kivi_k2v2 f01 (1/1), kivi_k2v2 f02 (4/4) and spinquant_w4a4 f01 (9/9).
  - **kivi_k2v2 f03 (running):** 2 recovered and 2 pending. **01a17956873df0ef QQ (airline:14, t = 51) timed out again** at the same decision (`n_decisions` 31, as in the original). This is A7.2 "persistent timeout": the arm stays missing, so **kivi_k2v2 f03 cannot be admitted** whatever the 2 pending arms do.
  - **kivi_k4v4 f01 (running):** 1/12 recovered, 11 pending.
- **The persistent timeout is not load.** Over 4 attempts of 600 s (17:42:37 to 18:22:32 PDT), the KIVI Q server ran exactly 1 request, with 0 waiting. It decoded at a median of 1.1 tok/s, about 640 tokens per attempt, which is below `max_tokens` 1,024. At this context length, any completion longer than about 650 tokens times out at concurrency 1.
- **A7 server identity: all equal.** For every A7 task, the 3 finished and the 2 running, the B/Q canary, `ckpt_sha256`, `effective_config_sha` and `hook_version` in `servers.json` equal both `a7_expect` and the original block. The B and Q task roles are verbatim copies of the original task.
- **Admitted blocks (`--dry`).** q8 has no phase 2: `expansion_q8.json` has expand false, so k <= 3.
  - Primary (A6 + A7 as of now): every cell f01-f03, except kivi_k2v2 {f01, f02} and kivi_k4v4 {f02, f03}.
  - Pre-recovery and strict: spinquant_w4a4 {f02, f03}, kivi_k2v2 none, kivi_k4v4 {f02, f03}; every other cell f01-f03.
  - A6 prospective and A6 + tool-call parse: equal to the primary.
- **Primary contrasts:**
  - **P1**: k = 3 in every view (final).
  - **P2**: k = 3 under the primary (final), and k = 2 pre-recovery and strict.
  - **P3**: k = 2 under the primary, final ({f01, f02}). It is not estimable pre-recovery or strict.
  - At k = 2 the primary t has df 1.
  - Only K2 and the A4.4 k4v4 contrast can still change, through kivi_k4v4 f01.
- **Reuse scan, spinquant_w4a4 f03:** 28 reuse rows (56 reused arms) rendered with the Qwen3-8B template; **0 flagged**. The method reproduces REUSE_AUDIT's f01 and f02 counts exactly.
- **Blocking GO for q8:**
  1. **Two A7 tasks are still running, and exppilot would not wait for them.** These are kivi_k2v2 f03 and kivi_k4v4 f01, with 13 arms pending. `exppilot_analysis.required()` lists no `a7_rr1_*` task, and the analysis runs once. Write `EXPPILOT_GO_newmethod_q8` only after both tasks finish (A7 deadline 2026-10-04 21:00 PDT), or have the main session add them to `required()`.
  2. `nmp_score_q8_spinquant_w4a4_f03` is still running; exppilot already waits for it.
  3. The A4.4 contrasts kivi_k2v2 - kivi_k16v16 and kivi_k4v4 - kivi_k16v16 are not implemented in `analyze_newmethod.py`. Add them before the read, or record why they are omitted.
- This note contains no effect, contrast, success rate or per-arm outcome aggregate.

## 1. Method (same as the m24 audits; what was added)

- **Same per-row procedure as `m24_budget_audit_20261003T1354Z.md` §1/§8 and `m24_budget_audit_phase2_20261004T0017Z.md` §1:**
  1. Restore the budget from the BF16 source trajectory: `cloq.fork.prefix_len`, `agent_positions`, `budget_used(messages[:pos[t]])`.
  2. For every run arm, recount `budget_used(history + suffix)` independently and compare it with `budget_recount` and the live counters.
  3. Re-apply `fork_driver.budget_check` (live == recount, `term_consistent`, `counters_tau2_default == [0, 0]`) against the stored `budget_ok[arm]`.
  4. Classify arm errors with the frozen `analyze_newmethod.a6_class` (primary and A6.E1 plus) and `a6_producer`, then join them to the A7 classes in `analysis/fork/kivi_recovery/failed_arms.json`.
- **Scope:**
  - the 24 panel blocks `analysis/fork/newmethod/tau2/q8_<cell>/f0{1,2,3}`;
  - the 9 reference blocks `analysis/fork/bank_u/q8_{gptq_w4_d1,awq_w4,kvq_int8}/f0{1,2,3}`, U2B rows only, as `REF_TAU2` reads them;
  - the A7 outputs `analysis/fork/newmethod/tau2_recovery/q8_<cell>/<blk>/rr1/`.
- **Added checks:**
  - `state_id` and `history_sha` recomputed from the source;
  - the A7 re-run arms recounted the same way;
  - A7.3 conditions: forced action = recorded a_B/a_Q, `prefix_ok`, `env_hash_init_ok`, `sim_seed`, roles copied verbatim;
  - A7 server identity against `a7_expect` and against the original block;
  - Q-server timing of the arm that failed again;
  - exppilot's analysis trigger;
  - fork-path commits during phase 1.
- **Fields read:** budget, termination (for `term_consistent`), counters, error, `n_decisions`, checks, provenance and server fields. `Y` was read only as `is None`.
- **Disclosure:**
  - During schema inspection, one branch record's outcome fields were printed once: one arm of one quarot_w4 f01 state. They were not used.
  - The termination reasons of the 17 recovered A7 arms were read, for the consistency check only.
  - Nothing was aggregated.

## 2. Per cell x block

| cell / block | n_rows | n_ok | n_missing | n_errors | no-op n/pass | `budget_ok` | `gate_pass` | manifest sha | branches attempted / completed | arm errors | recount = stored = live | restored = 200 - steps_left | admitted, primary now |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| quarot_w4 / f01 | 85 | 85 | 0 | 0 | 6/6 | true | true | `7534c690` | 177 / 177 | 0 | 177/177 | 85/85 | yes |
| quarot_w4 / f02 | 85 | 85 | 0 | 0 | 7/7 | true | true | `7534c690` | 194 / 194 | 0 | 194/194 | 85/85 | yes |
| quarot_w4 / f03 | 85 | 85 | 0 | 0 | 7/7 | true | true | `7534c690` | 186 / 186 | 0 | 186/186 | 85/85 | yes |
| quarot_w4a4 / f01 | 85 | 85 | 0 | 0 | 7/7 | true | true | `7534c690` | 208 / 208 | 0 | 208/208 | 85/85 | yes |
| quarot_w4a4 / f02 | 85 | 85 | 0 | 0 | 11/11 | true | true | `7534c690` | 200 / 200 | 0 | 200/200 | 85/85 | yes |
| quarot_w4a4 / f03 | 85 | 85 | 0 | 0 | 13/13 | true | true | `7534c690` | 220 / 220 | 0 | 220/220 | 85/85 | yes |
| quarot_w16 / f01 | 85 | 85 | 0 | 0 | 7/7 | true | true | `7534c690` | 118 / 118 | 0 | 118/118 | 85/85 | yes |
| quarot_w16 / f02 | 85 | 85 | 0 | 0 | 8/8 | true | true | `7534c690` | 133 / 133 | 0 | 133/133 | 85/85 | yes |
| quarot_w16 / f03 | 85 | 85 | 0 | 0 | 9/9 | true | true | `7534c690` | 122 / 122 | 0 | 122/122 | 85/85 | yes |
| spinquant_w4a4 / f01 | 85 | 85 | 0 | 0 | 6/6 | true | true | `7534c690` | 211 / 202 | **9** | 202/202 | 85/85 | yes (A7 9/9 recovered) |
| spinquant_w4a4 / f02 | 85 | 85 | 0 | 0 | 10/10 | true | true | `7534c690` | 207 / 207 | 0 | 207/207 | 85/85 | yes |
| spinquant_w4a4 / f03 | 85 | 85 | 0 | 0 | 9/9 | true | true | `7534c690` | 208 / 208 | 0 | 208/208 | 85/85 | yes |
| spinquant_w16 / f01 | 85 | 85 | 0 | 0 | 6/6 | true | true | `7534c690` | 111 / 111 | 0 | 111/111 | 85/85 | yes |
| spinquant_w16 / f02 | 85 | 85 | 0 | 0 | 10/10 | true | true | `7534c690` | 127 / 127 | 0 | 127/127 | 85/85 | yes |
| spinquant_w16 / f03 | 85 | 85 | 0 | 0 | 9/9 | true | true | `7534c690` | 122 / 122 | 0 | 122/122 | 85/85 | yes |
| kivi_k2v2 / f01 | 85 | 85 | 0 | 0 | 15/15 | true | true | `7534c690` | 202 / 201 | **1** | 201/201 | 85/85 | yes (A7 1/1 recovered) |
| kivi_k2v2 / f02 | 85 | 85 | 0 | 0 | 9/9 | true | true | `7534c690` | 192 / 188 | **4** | 188/188 | 85/85 | yes (A7 4/4 recovered) |
| kivi_k2v2 / f03 | 85 | 85 | 0 | 0 | 8/8 | true | true | `7534c690` | 201 / 196 | **5** | 196/196 | 85/85 | **no (1 failed again; final)** |
| kivi_k4v4 / f01 | 85 | 85 | 0 | 0 | 7/7 | true | true | `7534c690` | 140 / 128 | **12** | 128/128 | 85/85 | **no (A7 pending, 1/12 recovered)** |
| kivi_k4v4 / f02 | 85 | 85 | 0 | 0 | 6/6 | true | true | `7534c690` | 135 / 135 | 0 | 135/135 | 85/85 | yes |
| kivi_k4v4 / f03 | 85 | 85 | 0 | 0 | 9/9 | true | true | `7534c690` | 156 / 156 | 0 | 156/156 | 85/85 | yes |
| kivi_k16v16 / f01 | 85 | 85 | 0 | 0 | 9/9 | true | true | `7534c690` | 122 / 122 | 0 | 122/122 | 85/85 | yes |
| kivi_k16v16 / f02 | 85 | 85 | 0 | 0 | 4/4 | true | true | `7534c690` | 111 / 111 | 0 | 111/111 | 85/85 | yes |
| kivi_k16v16 / f03 | 85 | 85 | 0 | 0 | 9/9 | true | true | `7534c690` | 120 / 120 | 0 | 120/120 | 85/85 | yes |
| ref gptq_w4_d1 / f01 | 190 (85 U2B) | 190 | 0 | 0 | 25/25 (U2B 18/18) | true | true | `e236ee64` (Bank U) | 159 / 159 (U2B) | 0 | 159/159 | 85/85 | yes |
| ref gptq_w4_d1 / f02 | 190 (85) | 190 | 0 | 0 | 17/17 (9/9) | true | true | `e236ee64` | 164 / 164 | 0 | 164/164 | 85/85 | yes |
| ref gptq_w4_d1 / f03 | 190 (85) | 190 | 0 | 0 | 16/16 (5/5) | true | true | `e236ee64` | 180 / 180 | 0 | 180/180 | 85/85 | yes |
| ref awq_w4 / f01 | 190 (85) | 190 | 0 | 0 | 16/16 (10/10) | true | true | `e236ee64` | 177 / 177 | 0 | 177/177 | 85/85 | yes |
| ref awq_w4 / f02 | 190 (85) | 190 | 0 | 0 | 17/17 (6/6) | true | true | `e236ee64` | 181 / 181 | 0 | 181/181 | 85/85 | yes |
| ref awq_w4 / f03 | 190 (85) | 190 | 0 | 0 | 19/19 (10/10) | true | true | `e236ee64` | 189 / 189 | 0 | 189/189 | 85/85 | yes |
| ref kvq_int8 / f01 | 190 (85) | 190 | 0 | 0 | 15/15 (5/5) | true | true | `e236ee64` | 118 / 118 | 0 | 118/118 | 85/85 | yes |
| ref kvq_int8 / f02 | 190 (85) | 190 | 0 | 0 | 18/18 (8/8) | true | true | `e236ee64` | 133 / 133 | 0 | 133/133 | 85/85 | yes |
| ref kvq_int8 / f03 | 190 (85) | 190 | 0 | 0 | 15/15 (8/8) | true | true | `e236ee64` | 133 / 133 | 0 | 133/133 | 85/85 | yes |

- "Completed" equals the panel summary's `n_branches_run`. "Attempted" adds the arms that errored.
- **Common to all 24 panel blocks:**
  - the summary and spec `manifest_sha256` equal the frozen `7534c690...`;
  - `spec` equals the §6 panel spec (`bank_u`, one block, `subs ["U2B"]`, `noop_frac` 0.1, `concurrency` 8, no `limit_per_sub`, `out` = `analysis/fork/newmethod/tau2/q8_<cell>/<blk>`) and equals the queue task's `fork` field;
  - the U2B row set equals the manifest's 85 rows of the block, and row fields (t, source_run, domain, task_id, block) equal the manifest on 2,040/2,040 rows;
  - `Q_prompt_ok` is true on 2,040/2,040;
  - there are 85 branch files per block, and each file's arm keys equal the row's run and errored arms.
- **The reference blocks** pass the same row checks on their U2B rows: 765/765 rows identical to the panel rows, under the Bank U manifest `e236ee64...` (§2.5).
- **`gate_pass` is true in every block.** Unlike m24, q8 has no manifest-missing rows, so `n_missing` = 0 satisfies the bank-gate formula. It is not a panel criterion.
- **Endings** (consistency only, pooled over all 8 cells and 4 arms):
  - panel: user_stop 3,546, max_steps 192, too_many_errors 154;
  - reference U2B: 1,343, 47 and 44.
  - Every max_steps and too_many_errors ending is consistent with the limits (200, 10).
  - `prefix_ok` is never false, `env_hash_init_ok` is true on all, and `counters_tau2_default` is [0, 0] on all.
- **Provenance and runs:**
  - The `trajectory.jsonl` and `decisions.jsonl` shas of `a6k2_q8_bfpair_f0{1,2,3}/{retail,airline}` equal the manifest's `tau2.sources`.
  - Each panel task has one queue record, in `done`, and one start line and one `bank_u` completion line in its log. The `requeue_note` fields are priority changes and node-pin changes only.
  - Phase 1 ran from 10-02 12:49 to 10-03 19:02 PDT.
- **Code on the fork path during phase 1.** No commit changed `bank_u`, `run_branch` or the Qwen render path:
  - d16f4ea `context_policy` is gated to `google/gemma-4-*` model ids;
  - 5c2f207 touches `worker.run_eval` (closed-loop eval) only;
  - 9ddb588 touches `gate_same` only;
  - 1adec78 and f0472f6 change the worker re-run gate and RAM-disk cleanup.
  - 607a132 (bank_u_arms `subs`/`reuse_rerun`) adds record fields and an opt-in path. Failed-arm re-runs behave the same before and after it.

### Server identity (identical across f01-f03 in every cell)

| cell | Q canary | Q `ckpt_sha256` | Q `effective_config_sha` | Q `hook_version` |
|---|---|---|---|---|
| quarot_w4 | `81ba3f64026092ba` | `47b31ea7...` | `b5540961c5364ba8` | `30020b7507a4fa7a` |
| quarot_w4a4 | `6cf36eeb857d100f` | `47b31ea7...` (same checkpoint as quarot_w4, A1.1) | `1394dbd2d2d212dd` | `30020b7507a4fa7a` |
| quarot_w16 | `03a0c46a81e17258` | `70ef8120...` | `51f39e04d46c8cb4` | `30020b7507a4fa7a` |
| spinquant_w4a4 | `66028ece4c06573c` | `b7223e20...` (rotations `1f1719b5...`) | `f32980982246866d` | `30020b7507a4fa7a` |
| spinquant_w16 | `0858c5d540ef4202` | `89e0b413...` (rotations `1f1719b5...`) | `98fab69714560be3` | `30020b7507a4fa7a` |
| kivi_k2v2 | `60cac990145b1cca` | null (BF16 weights) | `485c96e5d1e91943` | `30020b7507a4fa7a` |
| kivi_k4v4 | `27dfdf096d5093af` | null | `da5099eb5f25a262` | `30020b7507a4fa7a` |
| kivi_k16v16 | `e5487ba6b887d132` | null | `852b477acbf58b01` | `30020b7507a4fa7a` |
| ref gptq_w4_d1 | `a9f812fb17241b72` | `6ee628e6...` | `cd7c70f5e9fe40d4` | null |
| ref awq_w4 | `db76cab1da9700d1` | `9ce71e4a...` | `b8608c0732512633` | null |
| ref kvq_int8 | `18f22e1d2cfbc1f3` | null | `85d54c1985196e20` | `ca3e42d2ba543122` |

- B is the same in all 33 blocks: canary `e340c7991fa5bc08`, config `0d4bf272db1da1c5`, `canary_ref_ok` true.
- Every Q server ran at `max_model_len` 33,792, and `hook_coverage.ok` is true wherever a hook is used.

## 3. `budget_ok = false` branches: none; independent recount

| scope | completed branches | indep = stored = live | sentinel | mismatch | recomputed check = stored |
|---|---|---|---|---|---|
| panel f01-f03 (24 blocks) | 3,892 | 3,892 | 0 | 0 | 3,892 |
| reference U2B f01-f03 (9 blocks) | 1,434 | 1,434 | 0 | 0 | 1,434 |
| A7 re-run arms recovered so far | 17 | 17 | 0 | 0 | 17 |
| **total** | **5,343** | **5,343** | **0** | **0** | **5,343** |

- With 0 failures, there is nothing to classify as (i) known task issue, (ii) overflow sentinel, (iii) restoration anomaly, or other.

## 4. Arm errors (Y = None; invisible to `budget_ok`, `n_errors` and A5.2)

All 31 arms:
- each has `n_decisions` >= 1, no `infra_cause`, and probe `counters_tau2` [0, 0] with `to_role` agent;
- each restored budget equals 200 - `steps_left`;
- `a6_class` is "missing" for every one, in both the primary and the A6.E1 plus view, so no producer applies;
- each is listed in `failed_arms.json` with an A7 class, and every `failed_arms.json` entry was found.

"Row written" is the mtime of `branches/<state_key>.json`, i.e. when the row finished.

| cell / block | task | state_id / state_key | t | arm (reused by) | `n_decisions` | error | A6 / A6.E1 | A7 class (server) | A7 status now | row written (PDT) |
|---|---|---|---|---|---|---|---|---|---|---|
| kivi_k2v2 / f01 | airline:32 | `f86f175588c35058` / `1bdc433905484e8d` | 0 | QQ | 5 | `litellm.Timeout` | missing / missing | timeout_cause_not_established (Q) | **recovered** | 10-02 16:43 |
| kivi_k2v2 / f02 | retail:45 | `117c4af65b63c160` / `02dde73dfe90f6f6` | 1 | QQ | 12 | `Timeout` | missing | timeout_cause_not_established | **recovered** | 10-02 14:58 |
| kivi_k2v2 / f02 | retail:89 | `126227df20440fd0` / `21f3a2013895739f` | 4 | BQ | 3 | `Timeout` | missing | same | **recovered** | 10-02 15:36 |
| kivi_k2v2 / f02 | airline:13 | `c879a930acdf56a3` / `e553e7972e96416c` | 1 | BQ | 5 | `Timeout` | missing | same | **recovered** | 10-02 16:51 |
| kivi_k2v2 / f02 | airline:17 | `e4316db42ec85699` / `0f51e0c84a65cf7f` | 1 | BQ | 15 | `Timeout` | missing | same | **recovered** | 10-02 16:53 |
| kivi_k2v2 / f03 | airline:14 | `288d9e5ca142ebbf` / `01a17956873df0ef` | 51 | QQ (BQ = reuse=QQ) | 31 | `Timeout` | missing | same | **failed again** (persistent timeout) | 10-02 16:59 |
| kivi_k2v2 / f03 | airline:19 | `e556b95d4409db12` / `b6a3454a4e6f976a` | 0 | QQ | 11 | `Timeout` | missing | same | **recovered** | 10-02 17:15 |
| kivi_k2v2 / f03 | retail:21 | `3c8d26ee46be1777` / `dbdc689a3751d9dd` | 15 | QQ | 5 | `Timeout` | missing | same | **recovered** | 10-02 14:40 |
| kivi_k2v2 / f03 | retail:99 | `4d75cc34ced03e65` / `f2b0916c7aa6d021` | 2 | BQ | 26 | `Timeout` | missing | same | pending | 10-02 18:08 |
| kivi_k2v2 / f03 | retail:99 | same | 2 | QQ | 20 | `Timeout` | missing | same | pending | 10-02 18:08 |
| kivi_k4v4 / f01 | retail:27 | `a00bc87c213e2f45` / `3b1c207abdf8ef45` | 7 | QQ (BQ) | 68 | `InternalServerError [Errno 111] Connection refused` | missing | service_failure_verified (user sim node004:8000 down) | pending (running) | 10-02 21:29 |
| kivi_k4v4 / f01 | airline:14 | `ff2d571c8f3f4a33` / `22e5640e91897669` | 42 | QQ (BQ) | 25 | same | missing | same | **recovered** | 10-02 21:30 |
| kivi_k4v4 / f01 | airline:17 | `1331726099e2a98f` / `9a48c111a1211c17` | 3 | QQ (BQ) | 14 | same | missing | same | pending | 10-02 21:33 |
| kivi_k4v4 / f01 | airline:18 | `2c892c0b761ea21a` / `87c2005e50647c84` | 16 | QQ (BQ) | 10 | same | missing | same | pending | 10-02 21:29 |
| kivi_k4v4 / f01 | airline:2 | `cfcfc369835184e6` / `dcd3f47a56a2faba` | 9 | QQ (BQ) | 10 | same | missing | same | pending | 10-02 21:29 |
| kivi_k4v4 / f01 | airline:23 | `a685598be7e1adf8` / `9749f30f7ffd3c41` | 14 | BB (QB), QQ (BQ) | 2, 2 | same | missing | same | pending | 10-02 21:31 |
| kivi_k4v4 / f01 | airline:28 | `78718f7e53c790fa` / `961ad5dfd79a5dee` | 5 | QQ (BQ) | 1 | same | missing | same | pending | 10-02 21:31 |
| kivi_k4v4 / f01 | airline:3 | `9ac2b2e65295f4a7` / `95d6b21e8fc7af2b` | 3 | BB, BQ, QB, QQ | 1, 1, 2, 2 | same | missing | same | pending | 10-02 21:32 |
| spinquant_w4a4 / f01 | retail:7 | `eaee7db48334a362` / `a42e6f98f2baa960` | 10 | QQ (BQ) | 80 | `Timeout` | missing | other (user sim node005:8000 overload; A7.E1) | **recovered** | 10-03 08:13 |
| spinquant_w4a4 / f01 | airline:23 | `a685598be7e1adf8` / `9749f30f7ffd3c41` | 14 | BQ, QQ | 29, 11 | `Timeout` | missing | same | **recovered** (both) | 10-03 11:04 |
| spinquant_w4a4 / f01 | airline:32 | `f86f175588c35058` / `1bdc433905484e8d` | 0 | QQ | 21 | `Timeout` | missing | same | **recovered** | 10-03 10:02 |
| spinquant_w4a4 / f01 | airline:33 | `80354008b603149d` / `197f61e9d1573be3` | 9 | QB | 4 | `Timeout` | missing | same | **recovered** | 10-03 09:31 |
| spinquant_w4a4 / f01 | airline:4 | `594c3d42cba195d4` / `33b049d3a313a14f` | 7 | QQ | 3 | `Timeout` | missing | same | **recovered** | 10-03 08:22 |
| spinquant_w4a4 / f01 | airline:45 | `cbb0710ba23034f6` / `2b7e8183406b2144` | 9 | QB | 5 | `Timeout` | missing | same | **recovered** | 10-03 10:34 |
| spinquant_w4a4 / f01 | airline:47 | `e5057ccaebb0e3c4` / `27b52ac1d2cc9ec6` | 4 | QQ | 2 | `Timeout` | missing | same | **recovered** | 10-03 10:53 |
| spinquant_w4a4 / f01 | airline:8 | `1099d55256ce3e93` / `f01a1f21e0c452e7` | 17 | QQ | 3 | `Timeout` | missing | same | **recovered** | 10-03 11:25 |

- **Totals (31 arms):** 17 recovered, 1 failed again, 13 pending. Reused arms that inherit an error are 10, all `reuse=` of an errored arm (8 in kivi_k4v4 f01, 1 in kivi_k2v2 f03, 1 in spinquant f01). `a7_apply` gives them the re-run value.
- **The reference cells have no arm error on U2B rows.** So the A6 reclassification and the A6.E1 views change no q8 reference block.
- **No-op coverage gap (not a quarantine).** Two noop-sampled kivi_k4v4 f01 rows, 9749f30f7ffd3c41 and 95d6b21e8fc7af2b, have an errored BB, so their no-op check was never performed. The summary's 7/7 excludes them.
  - `bank_u_arms` re-runs BB but does not compare it with the original BB. If those BB arms recover, they enter without a no-op comparison.

## 5. A7 recovery and server identity

| A7 task | queue | started -> finished (PDT) | arms recovered / failed again / pending | `recovery_summary` | state identical | shadow identical |
|---|---|---|---|---|---|---|
| a7_rr1_q8_kivi_k2v2_f01 | done | 16:59 -> 17:15 | 1 / 0 / 0 | n_arms 1, refused 0, errors 0, `budget_ok` true | 1/1 | 1/1 |
| a7_rr1_q8_kivi_k2v2_f02 | done | 17:02 -> 17:54 | 4 / 0 / 0 | n_arms 4, refused 0, errors 0, `budget_ok` true | 4/4 | 4/4 |
| a7_rr1_q8_kivi_k2v2_f03 | running (node007) | 17:15 -> | 2 / **1** / 2 (f2b0916c7aa6d021 BQ, QQ) | not yet | (rows written at end) | |
| a7_rr1_q8_kivi_k4v4_f01 | running (node008) | 17:35 -> | 1 / 0 / 11 (3b1c207abdf8ef45 QQ in progress since 18:23) | not yet | | |
| a7_rr1_q8_spinquant_w4a4_f01 | done (node008, user sim node001:8000) | 17:45 -> 19:29 | 9 / 0 / 0 | n_arms 9, refused 0, errors 0, `budget_ok` true | 8/8 | 8/8 |

- **Every recovered arm satisfies the A7.3 conditions (17/17):**
  - the forced first message equals the recorded a_B or a_Q (canonical);
  - `prefix_ok` and `env_hash_init_ok` are true;
  - `sim_seed` equals the original arms' seed, or the source trajectory seed 626729 where no original arm ran (kivi_k4v4 22e5640e91897669, spinquant_w4a4 a42e6f98f2baa960);
  - tags end in `-rr1`;
  - concurrency is 1;
  - the budget recount matches and the recomputed check is true.
- **All 5 A7 tasks copy the original panel task's B and Q roles verbatim** (`gpus` 2), use manifest sha `7534c690...`, and set `autopilot_retry` "no".
- **The persistent timeout (A7.2), kivi_k2v2 f03 01a17956873df0ef QQ, airline:14, t = 51.** The restored budget is [103, 1], and BQ = reuse=QQ.
  - The original failed at `n_decisions` 31. The re-run failed at `n_decisions` 31 as well.
  - `a7_rr1_q8_kivi_k2v2_f03.Q.vllm.log` shows four attempts starting at 17:42:37, 17:52:37, 18:02:37 and 18:12:37 PDT, exactly 600 s apart; each later attempt is a prefix-cached re-prefill. The task log shows the final ERROR at 18:22:32.
  - Throughout, the server shows Running 1 and Waiting 0, generation at a median of 1.1 tok/s (range 0.2 to 2.2), and KV usage of 17.7%. That is about 640 tokens per attempt, and about 2,540 decoded over the four attempts.
  - So the failing call was the Q server's own, alone and unloaded. At this context, the per-request decode rate times the completion length exceeds 600 s. A completion that reached `max_tokens` 1,024 would need about 930 s.
  - **Rule:** under A7.2 the arm stays missing, labelled "persistent timeout". kivi_k2v2 f03 therefore fails A3.3 under the primary, whatever the pending f2b0916c7aa6d021 arms do.
  - **Disclosure (as E1.5):** whether a timeout recurs depends on completion length, which is the model's behaviour.
- **The pending KIVI arms face the same mechanism.** KIVI decode at concurrency 1 runs at 1.0 to 1.7 tok/s in these logs, so any of the pending KIVI arms whose completion runs past about 600 to 1,000 tokens will also time out.

**Server identity (item 5).** Compared: `logs/tasks/<id>.servers.json` vs the task's `a7_expect` vs the original block's `bank_summary.servers`.

| A7 task | B canary | B config | Q canary | Q `ckpt_sha256` | Q config | Q hook | all equal to `a7_expect` | all equal to the original block |
|---|---|---|---|---|---|---|---|---|
| kivi_k2v2_f01 (done) | `e340c7991fa5bc08` | `0d4bf272db1da1c5` | `60cac990145b1cca` | null | `485c96e5d1e91943` | `30020b7507a4fa7a` | yes | yes |
| kivi_k2v2_f02 (done) | same | same | `60cac990145b1cca` | null | `485c96e5d1e91943` | `30020b7507a4fa7a` | yes | yes |
| kivi_k2v2_f03 (running) | same | same | `60cac990145b1cca` | null | `485c96e5d1e91943` | `30020b7507a4fa7a` | yes | yes |
| kivi_k4v4_f01 (running) | same | same | `27dfdf096d5093af` | null | `da5099eb5f25a262` | `30020b7507a4fa7a` | yes | yes |
| spinquant_w4a4_f01 (done) | same | same | `66028ece4c06573c` | `b7223e20...` | `f32980982246866d` | `30020b7507a4fa7a` | yes | yes |

- In every task, B `canary_ref_ok` and Q `hook_coverage.ok` are true, and both servers run at `max_model_len` 33,792.
- The two KIVI checkpoints carry no sha because the weights are BF16. Their identity rests on the canary, the effective config and the hook version.

## 6. Admission (`analyze_newmethod.py --model q8 --dry`)

Guard: protocol `3bd7ef33...`, manifest `7534c690...`; `expansion_ok` false; `tau2_log` empty; population 85 tasks, no mask; BFCL log: none quarantined or incomplete, replay guard 0 inconsistent.

| view | quarot_w4 | quarot_w4a4 | quarot_w16 | spinquant_w4a4 | spinquant_w16 | kivi_k2v2 | kivi_k4v4 | kivi_k16v16 | gptq_w4_d1 / awq_w4 / kvq_int8 (ref) |
|---|---|---|---|---|---|---|---|---|---|
| **primary (A6 + A7 merged, as of now)** | f01-f03 | f01-f03 | f01-f03 | **f01-f03** | f01-f03 | **f01, f02** | f02, f03 | f01-f03 | f01-f03 each |
| pre-recovery (A6 before A7) | f01-f03 | f01-f03 | f01-f03 | f02, f03 | f01-f03 | none | f02, f03 | f01-f03 | f01-f03 |
| strict as preregistered (no A6, no A7) | same as pre-recovery | | | | | | | | |
| A6 prospective only (with A7) | same as primary | | | | | | | | |
| A6 + tool-call parse (with A7) | same as primary | | | | | | | | |

- Incomplete tasks under the primary: kivi_k4v4 f01 has 8 (airline 14, 17, 18, 2, 23, 28, 3; retail 27); kivi_k2v2 f03 has 4 (airline 14, 19; retail 21, 99). Pre-recovery and strict add:
  - kivi_k2v2 f01 (airline 32);
  - kivi_k2v2 f02 (airline 13, 17; retail 45, 89);
  - spinquant_w4a4 f01 (airline 23, 32, 33, 4, 45, 47, 8; retail 7).
- `a7_records` merges a block only once its `recovery_summary.json` exists, so the running tasks' finished arms are not yet in the primary.
- Because q8 has no A6-class arm, A6 changes nothing for q8. Primary = A6 prospective = A6 plus; strict = pre-recovery. The views differ only through A7.

**Common blocks per contrast** (`tau2_contrast` needs >= 2 common blocks; at k = 2 the primary t has df 1):

| contrast | primary now | after the pending A7 tasks | pre-recovery / strict |
|---|---|---|---|
| P1 quarot_w4 - gptq_w4_d1 | f01-f03 (k = 3) | f01-f03 (final) | f01-f03 |
| P2 spinquant_w4a4 - quarot_w4a4 | f01-f03 (k = 3) | f01-f03 (final) | f02, f03 |
| P3 kivi_k2v2 - kvq_int8 | f01, f02 (k = 2) | f01, f02 (final; f03 is lost) | not estimable (no kivi_k2v2 block) |
| T1 quarot_w4 - quarot_w16 | f01-f03 | f01-f03 | f01-f03 |
| T2 spinquant_w4a4 - spinquant_w16 | f01-f03 | f01-f03 (final) | f02, f03 |
| T3 quarot_w4a4 - quarot_w16 | f01-f03 | f01-f03 | f01-f03 |
| K2 kivi_k4v4 - kvq_int8 | f02, f03 | f01-f03 iff all 11 pending kivi_k4v4 f01 arms complete | f02, f03 |
| A4.4 kivi_k2v2 - kivi_k16v16 (**not implemented**) | f01, f02 | f01, f02 | none |
| A4.4 kivi_k4v4 - kivi_k16v16 (**not implemented**) | f02, f03 | as K2 | f02, f03 |

- P3's fallback cannot fire: `P3_K2V2_GATE_FAILED = False`, A7.5. The strict family is therefore Holm over P1 and P2 only.

## 7. Reuse scan of spinquant_w4a4 f03 (REUSE_AUDIT.md §3 method)

- **Method:**
  - For every row with a `reuse=` arm: `F.canon_msg(a_B) == F.canon_msg(a_Q)`.
  - The ordered rendered view (content, plus name and `json.dumps(arguments)` per tool call).
  - The tokenizer render of `[user, action, tool result(s) or user]` through `template_view` + `AutoTokenizer("Qwen/Qwen3-8B", b968826d...).apply_chat_template(add_generation_prompt=True, enable_thinking=False)` from `/data/ziyangs/cloq_work/hf`.
  - Sensitivity checks: a key-order swap and 1 vs 1.0 both change the render.
- **Result:** f03 has 85 rows, 28 reuse rows (22 tool-call, 6 text) and 56 reused arms (28 `reuse=BB`, 28 `reuse=QQ`). Canonical equality holds on 28/28, the rendered view on 28/28 and the token render on 28/28. **0 flagged.**
- **Validation:** the same script on f01 gives 25 reuse rows (22/3), 50 arms, 0 flagged. On f02 it gives 29 (26/3), 58, 0. Both match REUSE_AUDIT §2 exactly.
- With f03 scanned, every q8 newmethod τ² directory has been covered, with 0 flagged.

## 8. GO for q8: blocking and non-blocking items

**Blocking (procedure, not data):**
1. **A7 is not finished, and exppilot would not wait for it.**
   - Pending: 13 arms in 2 running tasks (kivi_k2v2 f03 2, kivi_k4v4 f01 11). a7_rr1_q8_spinquant_w4a4_f01 finished at 19:29 PDT (9/9).
   - `scripts/a6000/exppilot_analysis.py::required()` lists only the `nmp_tau2`, `nmp_score` and `nmp_bfcl` tasks. Once GO exists, the analysis runs once, as soon as those are done (now: only `nmp_score_q8_spinquant_w4a4_f03` is left). After T_deadline (2026-10-04 12:00 PDT) it runs regardless.
   - A GO written now would therefore compute the q8 primary with kivi_k4v4 f01 still pre-recovery (K2 and the A4.4 k4v4 contrast) and kivi_k2v2 f03's A7 record unmerged. Recovering them later would need a second read.
   - **Remedy:** write `EXPPILOT_GO_newmethod_q8` after both remaining `a7_rr1_*` tasks are in `done`, or have the main session add `a7_rr1_q8_*` to `required()`. The A7 deadline is 2026-10-04 21:00 PDT.
   - **Rate so far:** kivi_k4v4 took 45 min for its first arm (58 decisions). If KIVI arms keep that rate, both tasks may not finish before T_deadline.
2. **Local fidelity is incomplete.** `nmp_score_q8_spinquant_w4a4_f03` is running; 23/24 q8 score tasks are done. exppilot already waits for it.
3. **The A4.4 KIVI contrasts are missing from the analysis.** kivi_k2v2 - kivi_k16v16 and kivi_k4v4 - kivi_k16v16 on D_cc are prescribed by A4.4, but `SECONDARY` holds only T1, T2, T3 and K2, so they would not be reported. The per-cell kivi_k16v16 D_cc, i.e. the kernel-path effect, is reported.
   - Adding them implements an existing rule and needs no protocol amendment, but it must happen before the read.

**Not blocking:**
- **E1.7 is closed** (RESEARCH_LOG W100ae: S3 and the q8 scope of A6 kept). Either choice would leave q8 unchanged, because no q8 arm is in the A6 class.
- **kivi_k2v2 f03 is lost under the primary** by the persistent-timeout rule fixed in A7.2 before the re-run. P3 has k = 2 at most, and its t has df 1. Report the A7.2 timing (§5) with P3.
- **The no-op gap** on 2 noop-sampled kivi_k4v4 f01 rows (§4).
- **The reference kvq_int8 runs an older hook_version** (`ca3e42d2...`, from the Bank U era) than the KIVI cells (`30020b75...`). §2.5 admits reference rows on row identity and the Bank U manifest sha; hook identity is not a criterion. Name it next to P3.
- **`expansion_q8.json` has expand false** (written 02:08:29 UTC, trigger "all phase-1 tasks finished"), so q8 inference rests on k <= 3 blocks.

## 9. Rules applied (quoted; no new rule)

- **A3.3/§7 strict:** "a block enters a cell only if all 85 of its states have four arms … Cross-cell contrasts use the blocks complete in both cells."
- **A6.2:** "Everything else stays missing, … transport and server errors (for example litellm `APIConnectionError`, `Timeout`, `InternalServerError`)."
- **A7.2:** "the arm completes with no timeout: the original timeout is attributed to serving load and the outcome enters the repaired analysis; any request times out again: the arm stays missing, labelled 'persistent timeout', and its timing is reported."
- **A7.3:** "Each arm runs once, one state at a time (concurrency 1) … An arm that errors again stays missing."
- **A7.4:** the primary is "A6 with the A7 re-run arms merged". "before the A7 re-run", "strict as preregistered" and the A6.E1 sensitivities with A7 are reported next to it.
- **A7.1:** "The same rule applies to such an arm error in any q8 τ² panel block finished before the evidence freeze." spinquant_w4a4 f03 has none.
- **A4.4:** "`kivi_k2v2` - `kivi_k16v16`; `kivi_k4v4` - `kivi_k16v16`. Both are on D_cc … reported with intervals."
- **§5.5/A5:** expansion all or none; the record says expand false.

## 10. Reproduction and evidence

The audit was CPU-only, run with `source scripts/a6000/env.sh` and `TMPDIR` in the session scratchpad. HEAD was `e30be4d`. Code sha prefixes:
- `fork_driver.py` `740ff1b8`;
- `cloq/fork.py` `0a731c36`;
- `analyze_newmethod.py` `4deda9bb`;
- `exppilot_analysis.py` `2d31adb6`.

It read:
- the manifest;
- `runs/a6k2_q8_bfpair_f0{1,2,3}/{retail,airline}/{trajectory,decisions}.jsonl` and `config.json`;
- `analysis/fork/newmethod/tau2/q8_*/f0{1,2,3}/{bank_summary.json,bank_rows.jsonl,branches/}`;
- `analysis/fork/bank_u/q8_{gptq_w4_d1,awq_w4,kvq_int8}/f0{1,2,3}/` (U2B rows);
- `analysis/fork/newmethod/tau2_recovery/q8_*/*/rr1/`;
- `analysis/fork/kivi_recovery/failed_arms.json`;
- `analysis/fork/newmethod/expansion_q8.json`;
- queue records (metadata, roles, fork spec, `a7_expect`; never `result` contents beyond keys);
- `logs/tasks/{nmp_tau2_q8_*,a7_rr1_q8_*}.log`, `a7_rr1_q8_*.servers.json` and the `a7_rr1_q8_*.Q.vllm.log` throughput lines.

`analyze_newmethod.py --model q8 --dry` was run once; it prints admission blocks only. Nothing under `analysis/fork/holdout/` was opened, no queue file was touched, nothing was committed, and nothing was written except this note and its `.json` sibling.

```python
# per row with Y (same as the m24 audits), panel and reference U2B rows
x = traj[row.task_id]; n0 = F.prefix_len(x["task"]); pos = F.agent_positions(x["messages"], n0)
hist = x["messages"][:pos[row.t]]; restored = F.budget_used(hist, n0)          # == 200 - row.steps_left (2,040 + 765)
for arm, br in branches[row.state_key].items():
    if "error" in br: ANM.a6_class(br), ANM.a6_class(br, plus=True, domain=row.domain); continue   # 31 arms, all 'missing'
    indep = F.budget_used(hist + br["suffix"], n0)
    assert indep == br["budget_recount"] == [br["step_count_final"], br["num_errors_final"]]          # 5,343/5,343 incl. A7
    assert recomputed_budget_check(br) == row.budget_ok[arm]
```

**Evidence:**
- outputs: `analysis/fork/newmethod/tau2/q8_*/f0{1,2,3}/`, `analysis/fork/newmethod/tau2_recovery/q8_{kivi_k2v2,kivi_k4v4,spinquant_w4a4}/*/rr1/`;
- the failed-again record: `…/tau2_recovery/q8_kivi_k2v2/f03/rr1/branches/01a17956873df0ef.json` (arm QQ);
- its timing: `/data/ziyangs/cloq_work/logs/tasks/a7_rr1_q8_kivi_k2v2_f03{.log,.Q.vllm.log}`;
- A7 identity: `/data/ziyangs/cloq_work/logs/tasks/a7_rr1_q8_*.servers.json`, `/data/ziyangs/cloq_work/queue/{done,running}/a7_rr1_q8_*.json`;
- rules: `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (sha `3bd7ef33…`: §5, §7, A3.3, A4.4, A6, A6.E1, A7, A7.E1);
- templates: `analysis/fork/out/m24_budget_audit_20261003T1354Z.md`, `analysis/fork/out/m24_budget_audit_phase2_20261004T0017Z.md`;
- the reuse method: `analysis/fork/reuse_audit/REUSE_AUDIT.md`;
- the exppilot trigger: `scripts/a6000/exppilot_analysis.py` (`required`, `step`).
