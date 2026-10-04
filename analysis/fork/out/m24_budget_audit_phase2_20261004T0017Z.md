# m24 phase-2 `budget_ok` and arm-error audit: per-branch CPU check of f04, f05, f06 (2026-10-04 00:17 UTC)

**TL;DR**
- **No phase-2 branch fails `budget_check`.** `budget_ok` is true in all six phase-2 summaries (rtn_w4 and gptq_w4_d1, f04 to f06). There are no context-overflow sentinels and no restoration anomalies.
- **The independent recount matches everywhere.** For all 1,130 completed phase-2 branches, the recount from the BF16 source history plus the saved suffix equals both the stored `budget_recount` and the live counters: 0 mismatches and 0 sentinels.
  - The recomputed `budget_check` equals the stored flag on 1,130/1,130 branches.
  - The restored budget equals 200 − `steps_left` on 504/504 rows.
- **Every block passes the provenance and A5.2-type checks:**
  - the summary and spec manifest sha is `53295b64…`, and the spec equals the panel spec;
  - `n_rows` 85, `n_ok` 84, `n_missing` 1, `n_errors` 0;
  - every no-op passed: 11/11, 8/8, 9/9 (rtn) and 8/8, 7/7, 5/5 (gptq);
  - the only missing row is airline:44, which is manifest-missing and outside the population;
  - the source trajectory shas match the manifest, and the B and Q server configs are identical across all six blocks of each cell.
- **Phase 2 has two arm errors (Y = None).** Both come from the agent's own output, and Q produced both:
  - **rtn_w4 f04, airline:10 (in the 83-task population), BQ:** `JSONDecodeError('Unterminated string …')`, `n_decisions` 25. Q produced it as controller, at decision 26.
    - Under A6 and A6.E1 this **stays missing in the primary**, so **rtn_w4 f04 is not admitted**.
    - The labelled sensitivity "A6 + agent tool-call parse failures" scores it Y = 0.
    - The E1.2 rule was committed at 08:55:59 PDT. The arm was written at 14:42:29 PDT, so the rule was **fixed before this arm existed**.
  - **gptq_w4_d1 f06, airline:13 (masked, outside the population), QQ:** `InvalidFunctionCallException('Function name was  but must be …')` (S1, empty name), `n_decisions` 57. Q produced it as controller.
    - **A6 scores it Y = 0.** It affects only the unmasked available-rows sensitivity.
  - Neither arm was produced by B, so E1.4 requires no B-produced Y = 0 to be named.
- **Admission, from `analyze_newmethod.py --model m24 --dry`:**
  - **Primary (A6, with A7 merged; A7 does not apply to m24):**
    - rtn_w4: {f01, f02, f03, f05, f06};
    - gptq_w4_d1: {f01, …, f06};
    - **M1 uses {f01, f02, f03, f05, f06}, so k = 5** (df 4, so §7's primary t is computable).
  - **Strict as preregistered:**
    - rtn_w4: {f03, f05, f06};
    - gptq_w4_d1: {f02, …, f06};
    - **M1 uses {f03, f05, f06}, so k = 3.**
  - **"A6 prospective only"** gives the same blocks as strict here (k = 3).
  - **"A6 + tool-call parse"** admits all six blocks in both cells (k = 6).
- **GO-blocking anomalies: none in the budget, counter, termination, provenance or server data.** Open items before `EXPPILOT_GO_newmethod_m24` (§6):
  - E1.7: the main session must confirm or revert S3. No m24 arm is S3, so this cannot change any m24 admission.
  - 7 of the 12 m24 local-fidelity score tasks (§9) are not done. τ² admission does not depend on them.
  - The rtn_w4 f04 loss is the "known cost" stated in E1.2. Moving `JSONDecodeError` into the primary now would be post hoc.
- This note contains no effect, contrast, success rate or per-arm outcome aggregate.

## 1. Method (same as W100s; what changed)

- **The method is unchanged from `analysis/fork/out/m24_budget_audit_20261003T1354Z.md` §1 and §8.** For each row that has `Y`:
  1. Restore the budget at the state from the BF16 source trajectory: `cloq.fork.prefix_len`, `agent_positions`, `budget_used` on `messages[:pos[t]]`.
  2. For each run arm, recount `budget_used(history + suffix)` independently. Compare it with `budget_recount` and with the live `[step_count_final, num_errors_final]`.
  3. Re-apply `fork_driver.budget_check` (`live == recount`, `term_consistent`, `counters_tau2_default == [0, 0]`) and compare the result with the stored `budget_ok[arm]`.
  4. List arm errors from `branches/<state_key>.json` and classify them with the frozen `analyze_newmethod.a6_class` and `a6_producer`.
- **Validation.** The same script was run first on phase 1 (f01 to f03). It reproduced W100s exactly:
  - 1,133 completed branches;
  - endings user_stop 1,118, max_steps 10, too_many_errors 4, overflow 1;
  - one sentinel (gptq_w4_d1 f02, airline:45 QQ);
  - the same 5 arm errors;
  - 0 recount mismatches.
- **Fields read:** budget, termination, counters, error, `n_decisions`, checks, provenance and server fields. `Y` was read only as `is None`, to locate arm errors. No outcome was aggregated.
- **Added checks** (not in W100s):
  - per-block server and checkpoint identity across phases;
  - code changes on the fork path between phases;
  - one attempt per task;
  - the timing of each arm error against the A6.E1 commit;
  - the Q-server HTTP statuses of the task that produced the JSONDecodeError.

## 2. Per block (phase 2)

| cell / block | n_rows | n_ok | n_missing (task) | n_errors | no-op n/pass | `budget_ok` | `gate_pass` | manifest sha | branches attempted / completed | arm errors | overflow | recount = stored = live | restored = 200 − steps_left | strict A3.3 (83 tasks) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rtn_w4 / f04 | 85 | 84 | 1 (airline:44, manifest-missing, out) | 0 | 11/11 | true | false | match | 215 / 214 | **1 (airline:10 BQ, in)** | 0 | 214/214 | 84/84 | **not admitted** (primary and strict) |
| rtn_w4 / f05 | 85 | 84 | 1 (same) | 0 | 8/8 | true | false | match | 184 / 184 | 0 | 0 | 184/184 | 84/84 | admitted |
| rtn_w4 / f06 | 85 | 84 | 1 (same) | 0 | 9/9 | true | false | match | 195 / 195 | 0 | 0 | 195/195 | 84/84 | admitted |
| gptq_w4_d1 / f04 | 85 | 84 | 1 (same) | 0 | 8/8 | true | false | match | 196 / 196 | 0 | 0 | 196/196 | 84/84 | admitted |
| gptq_w4_d1 / f05 | 85 | 84 | 1 (same) | 0 | 7/7 | true | false | match | 171 / 171 | 0 | 0 | 171/171 | 84/84 | admitted |
| gptq_w4_d1 / f06 | 85 | 84 | 1 (same) | 0 | 5/5 | true | false | match | 171 / 170 | 1 (airline:13 QQ, **out**) | 0 | 170/170 | 84/84 | admitted |

- "Completed" equals the summary's `n_branches_run`. "Attempted" adds the arms that errored.
- **`gate_pass` is false in all six blocks for the same reason as in phase 1.** It is the bank-gate verdict and needs `n_missing == 0`, and panel blocks carry manifest-missing rows by construction (A2.3). It is not a panel criterion.
- **Common to all six blocks:**
  - the summary and `spec.manifest_sha256` equal the frozen `53295b64…`;
  - `spec` equals the panel spec: `bank_u`, one block, `subs ["U2B"]`, no `limit_per_sub`, `out` = `analysis/fork/newmethod/tau2/m24_<cell>/<blk>`;
  - the bank row set equals the manifest's 85 U2B rows of the block;
  - row fields (t, source_run, domain, task_id, block) equal the manifest on 504/504 rows;
  - `Q_prompt_ok` is true on 504/504;
  - there are 84 branch files per block, and each file's arm keys equal the row's run and errored arms;
  - no arm was reused from an errored arm.
- **Endings over the 1,130 completed branches** (pooled over cells and arms): user_stop 1,117; max_steps 11; too_many_errors 2.
  - Every max_steps and too_many_errors ending is consistent with the limits (200, 10).
  - `prefix_ok` is never false, `env_hash_init_ok` is true on all, and `counters_tau2_default` is [0, 0] on all.
- **Provenance:**
  - The source `trajectory.jsonl` shas of `a6k2_m24_bfpair_f0{4,5,6}/{retail,airline}` equal the manifest's frozen `tau2.sources` shas.
  - Each phase-2 task was attempted once: one queue record in `done`, and one `bank_u` completion line per task log.
  - `expansion_m24.json` (expand true, both cells eligible) was written at 2026-10-03 11:53 UTC, before the first phase-2 branch (14:47 UTC).

## 3. `budget_ok = false` branches: none

- No phase-2 branch has a stored or recomputed `budget_check` failure.
- No branch carries `infra_cause: context_overflow`, so no sentinel occurs.
- With 0 failures there is nothing to classify as cause (i) known task issue, (ii) overflow sentinel, (iii) restoration anomaly, or other.
- **Independent recount over all run branches:**

| scope | completed branches | indep = stored = live | sentinel | mismatch | recomputed check = stored |
|---|---|---|---|---|---|
| phase 2 (this note) | 1,130 | 1,130 | 0 | 0 | 1,130 |
| phase 1 (W100s, re-run by this script) | 1,133 | 1,132 | 1 (gptq f02 airline:45 QQ) | 0 | 1,133 |

## 4. Arm errors in phase 2 (Y = None; invisible to `budget_ok`, `n_errors` and A5.2)

| cell / block | task (A3 population) | state_id / state_key | t | restored budget | arm | `n_decisions` | error (repr prefix) | A6 primary | A6.E1 "+ tool-call parse" | strict | producer | written (PDT) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rtn_w4 / f04 | airline:10 (**in**) | `23c8a1921873e8c4` / `5caebefd118b4169` | 1 | [3, 0] (steps_left 197) | BQ | 25 | `JSONDecodeError('Unterminated string starting at: line 1 column 217 (char 216)')` | **missing** (not S1/S3), so the block fails | Y = 0 (`toolcall_args_json`) | missing | Q (controller, decision 26) | 14:42:29 |
| gptq_w4_d1 / f06 | airline:13 (**out**, masked) | `130b51acd597fdbe` / `fc9daad0aa8e21ef` | 2 | [5, 0] (steps_left 195) | QQ | 57 | `InvalidFunctionCallException('Function name was  but must be a-z, A-Z, 0-9, or contain underscores and dashes, with a maximum length of 64.')` | Y = 0 (S1 `invalid_function_name`) | Y = 0 | missing | Q (controller; `n_decisions` ≥ 2) | 13:19:16 |

- **What the records hold.** Each errored arm records only `tag`, `branch`, `error`, `n_decisions` and `probe`. There are no counters, so the arm cannot be recounted.
  - The probe shows `counters_tau2` [0, 0] and `to_role` agent for both.
  - The restored budgets equal 200 − `steps_left`.
- **Where the JSONDecodeError comes from (rtn_w4 f04, airline:10 BQ).** The mechanism is the one in A6.E1 E1.2.
  - `third_party/tau2-bench/src/tau2/utils/llm_utils.py:440` is `arguments=json.loads(tool_call.function.arguments)` inside `generate`. It runs before that decision is logged, so the offending message is the controller's decision 25 + 1, i.e. Q's.
  - Airline offers no user tools (`domains/airline/environment.py` builds only `AirlineTools`).
  - The Q server of this task (`/data/ziyangs/cloq_work/logs/tasks/nmp_tau2_m24_rtn_w4_f04.Q.vllm.log`) answered **1,173/1,173 chat completions with 200 OK**. It showed no restart or crash before the end-of-task shutdown. The malformed arguments therefore came from a successful response, not from an outage.
  - Whether that completion hit `max_tokens` 1,024 cannot be established: the decision record is written only after a parsed response.
- **Timing against the rules.** A6 was committed at fe6765e, 08:16 PDT, and A6.E1 at 2f06102, 2026-10-03 08:55:59 PDT. Both arm errors were produced later: 13:19 and 14:42 PDT.
  - So their classification (S1 → Y = 0; `JSONDecodeError` → missing in the primary and Y = 0 only in the labelled sensitivity) was fixed before they existed. Neither is post hoc.
  - The whole rtn_w4 f04 block ran 13:46 to 14:55 PDT.
- **A7 header claim checked.** A7 states that "m24 has no arm error outside the A6/A6.E1 agent-output classes". That holds on the finished phase 2: one S1 arm and one tool-call `JSONDecodeError` arm. It was committed at 16:44 PDT, after the last phase-2 block finished at 16:22 PDT.
- **Phase 1, unchanged and for completeness** (W100s §4): rtn_w4 f01 retail:51 QB and QQ (S1); rtn_w4 f02 retail:95 QQ (S1); gptq_w4_d1 f01 airline:2 BQ (S1); rtn_w4 f03 airline:13 BQ (`JSONDecodeError`, masked).
- **Over f01 to f06**, the masked task airline:13 produced agent-output arm errors twice (rtn f03 BQ, gptq f06 QQ). This is consistent with A3.1's reason for masking it.

## 5. Admission per cell (`analyze_newmethod.py --model m24 --dry`, guard: protocol `ba743cee…`, manifest `53295b64…`, mask `b03a8a91…`; `expansion_ok` true; `tau2_log` empty)

| view | rtn_w4 admitted | gptq_w4_d1 admitted | M1 common blocks (phase 1+2) | k | M1 phase-2 blocks |
|---|---|---|---|---|---|
| **primary: A6 (with A7 merged; A7 does not apply to m24)** | f01, f02, f03, f05, f06 (f04 refused: airline:10 BQ `JSONDecodeError`) | f01–f06 | **f01, f02, f03, f05, f06** | **5** | f05, f06 |
| strict as preregistered (no A6) | f03, f05, f06 (f01 retail:51; f02 retail:95; f04 airline:10) | f02–f06 (f01 airline:2) | f03, f05, f06 | 3 | f05, f06 |
| A6 prospective only (A6.E1) | f03, f05, f06 | f02–f06 | f03, f05, f06 | 3 | f05, f06 |
| A6 + agent tool-call parse failures (A6.E1) | f01–f06 | f01–f06 | f01–f06 | 6 | f04, f05, f06 |
| pre-recovery (A7 view) | as primary | as primary | as primary | 5 | f05, f06 |

- **A6 changes admission only on phase 1.** The A6-completed blocks are rtn f01, rtn f02 and gptq f01, and E1.1 flags them as post hoc.
  - In phase 2 the only in-population arm error is the `JSONDecodeError`, which A6 leaves missing. So the phase-2 admissions are the same under the primary, strict and prospective views.
- **The A6 report (`--dry`) lists two phase-2 entries:**
  - gptq_w4_d1 f06: "airline:13 Y=0 QQ[Q] (outside population)";
  - rtn_w4 f04: "airline:10 missing BQ", reason `JSONDecodeError`.
- The available-rows sensitivity (A3.3) has no mask and no strictness, so it includes the gptq f06 airline:13 row. Under A6 that row has Y = 0 in QQ, and it is excluded in the strict view.

## 6. Anomalies and the GO decision

- **The audit found nothing that should block GO** in the budget, counter, termination, restoration, provenance, server-identity or code-path data:
  - 0 `budget_ok` failures, 0 sentinels and 0 recount mismatches;
  - 0 restoration mismatches;
  - consistent endings;
  - identical B/Q effective configs, canaries and checkpoint shas across f01 to f06 per cell:
    - B: `bf306a565a30e0dd`, canary `2c2cdf56…`, `canary_ref_ok` true;
    - rtn Q: ckpt `745e9698…`, config `c45539f5…`;
    - gptq Q: ckpt `ed376dfb…`, config `aabc19fe…`;
    - all at `max_model_len` 33,792;
  - no change to `run_branch`, `bank_u` or the Mistral agent render path between phase 1 and phase 2:
    - 248b0c5 only adds `MistralChatRender.render_turn`, which only `score_driver` uses;
    - 1adec78 and f0472f6 touch worker eval re-runs and RAM-disk cleanup;
    - 10a5518 (`bank_u_arms`) landed after the last phase-2 block.
- **Items for the main session before writing `EXPPILOT_GO_newmethod_m24`.** None of them changes a τ² admission.
  1. **E1.7 (procedural, required by the protocol text).** "The main session confirms or reverts S3 and the q8 scope before writing `EXPPILOT_GO_newmethod_q8` or `_m24`."
     - No confirmation was found in `docs/RESEARCH_LOG.md`; the latest mention is the W100v-e to-do list.
     - No m24 arm in f01 to f06 is S3, so either choice leaves every m24 view unchanged.
  2. **rtn_w4 f04 is lost under the primary.** This is the outcome-dependent loss that E1.2 named in advance ("a block with such an arm fails under the primary"), under a rule fixed before the arm existed.
     - Reclassifying `JSONDecodeError` into the primary now would be a post-hoc change: phase-2 arm-error records have been read, here and in A7.
     - The prespecified remedy is to report the "A6 + tool-call parse" sensitivity (k = 6) beside the primary (k = 5).
  3. **Local fidelity (§9) is incomplete.** These m24 `nmp_score` tasks are not done:
     - running: gptq f05, rtn f02, rtn f05;
     - todo: gptq f06, rtn f03, rtn f04, rtn f06.

     `load_scores` silently skips missing files, so an analysis run now would compute the phase-1 KL tertile cuts and strata from partial scores. τ² admission and M1 do not depend on this. Either wait for these tasks so that one read is complete, or label the fidelity section partial.
- **Not anomalies:**
  - `gate_pass` false (by construction, §2);
  - the gptq f06 airline:13 S1 arm (masked task; it affects only the labelled available-rows sensitivity);
  - the Q-produced arm errors (no B-produced Y = 0 needs naming under E1.4).

## 7. Rules applied (quoted; no new rule)

- **A3.3:** "A (cell, block) is admitted only if it has a complete four-arm state for exactly the 83 predefined tasks. Any newly missing branch (missing record, error, a missing arm) fails that block for that cell. … The two-cell comparison uses blocks complete in both cells."
- **A5.2 limitation:** "a branch-arm error inside an otherwise completed row … is counted in `n_ok` … Such a block passes A5.2. The analysis strict-block rule (§7; A3.3) still refuses it later."
- **A6.2 / A6.3:** "Arms in the A6.2 class enter with Y = 0", where the class is S1 `InvalidFunctionCallException('Function name was ` or S3 `ValueError('AssistantMessage must have either content or tool_calls`, with `n_decisions` ≥ 1 and no `infra_cause`. Everything else stays missing, including "`JSONDecodeError` …".
- **A6.E1 E1.2:** "`JSONDecodeError` … stays missing in the primary … The known cost is that a block with such an arm fails under the primary … New labelled sensitivity 'A6 + agent tool-call parse failures' … `JSONDecodeError` arms with `n_decisions` ≥ 1 in retail or airline, scored Y = 0."
- **A6.E1 E1.4 (producer):** "`n_decisions` = 1 is the forced action (the arm's first letter) and ≥ 2 the controller (its second letter). A tool-call parse failure is always the controller's."
- **A7:** "m24 has no arm error outside the A6/A6.E1 agent-output classes … A7 does not apply to m24."
- **Budget checks are gate criteria, not panel admission criteria** (W100s §5): FORK_PROTOCOL §7 (d), NEWMETHOD §2.4.1 and the bank gate's `gate_pass`.

## 8. Reproduction and evidence

The audit was CPU-only, run with `source scripts/a6000/env.sh` and `python`. It read only:
- the manifest and mask;
- `runs/a6k2_m24_bfpair_f0{4,5,6}/{retail,airline}/{trajectory.jsonl,config.json}`;
- `analysis/fork/newmethod/tau2/m24_{rtn_w4,gptq_w4_d1}/f0{4,5,6}/{bank_summary.json,bank_rows.jsonl,branches/*.json}`, plus f01 to f03 for the validation run;
- `analysis/fork/newmethod/expansion_m24.json`;
- the queue `done` records (metadata, spec and `result.out` only);
- the task logs and the Q/user-sim vLLM access logs (HTTP status lines only).

`analyze_newmethod.py --model m24 --dry` was run once; it prints admission blocks only.

Nothing under `analysis/fork/holdout/` was opened, no queue file was touched, nothing was committed, and nothing was written except this note and its `.json` sibling.

```python
# per row with Y (same as W100s §8)
x = traj[row.task_id]; n0 = F.prefix_len(x["task"]); pos = F.agent_positions(x["messages"], n0)
hist = x["messages"][:pos[row.t]]; restored = F.budget_used(hist, n0)            # == 200 - row.steps_left (504/504)
for arm, br in branches[row.state_key].items():
    if "error" in br: ANM.a6_class(br), ANM.a6_class(br, plus=True, domain=row.domain), ANM.a6_producer(arm, br, sig); continue
    indep = F.budget_used(hist + br["suffix"], n0) if br["suffix"] is not None else None
    assert indep == br["budget_recount"] == [br["step_count_final"], br["num_errors_final"]]   # 1,130/1,130
    assert recomputed_budget_check(br) == row.budget_ok[arm]                                   # 1,130/1,130
```

**Evidence:**
- outputs: `analysis/fork/newmethod/tau2/m24_{rtn_w4,gptq_w4_d1}/f0{4,5,6}/`;
- the two arm errors: `…/m24_rtn_w4/f04/branches/5caebefd118b4169.json` (arm `BQ`) and `…/m24_gptq_w4_d1/f06/branches/fc9daad0aa8e21ef.json` (arm `QQ`);
- the expansion record: `analysis/fork/newmethod/expansion_m24.json`;
- queue records: `/data/ziyangs/cloq_work/queue/done/nmp_tau2_m24_*_f0{4,5,6}.json`;
- logs: `/data/ziyangs/cloq_work/logs/tasks/nmp_tau2_m24_rtn_w4_f04{.log,.Q.vllm.log}`;
- code:
  - `scripts/a6000/fork_driver.py` (296 `budget_check`, 673–797 `bank_u`; sha `fe1e6dd1…`);
  - `cloq/fork.py` (143–175, 539–640; sha `0a731c36…`);
  - `analysis/fork/analyze_newmethod.py` (156 `population`, 174 `a6_class`, 189 `a6_producer`, 299 `load_tau2`, 403 `strict_blocks`; sha `5dbf02a9…`);
  - `third_party/tau2-bench/src/tau2/utils/llm_utils.py:440`;
- rules: `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (sha `ba743cee…`: §5, §7, A3.3, A5.2, A6, A6.E1, A7);
- the phase-1 template: `analysis/fork/out/m24_budget_audit_20261003T1354Z.md`;
- the repo was at HEAD `5c00a6d`.
