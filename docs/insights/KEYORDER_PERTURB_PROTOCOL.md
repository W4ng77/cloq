# Key-order perturbation: does a representation-only change of Q's action flip task outcomes? (protocol ko-v1)

**TL;DR** An exploratory follow-up, chosen after the fork results were known (GPT review, approved 2026-10-05), registered before any key-order suffix runs.
- **Question.** At Q's recorded tool call, reorder the keys of its arguments object and let Q continue. The parsed action, the tool returns, the database and the budget are unchanged; only the token sequence Q reads at its next decisions changes. How often does the task outcome flip, compared with replacing Q's action by BF16's action at the same states?
- **Panel.** q8 GPTQ-W4 d1 Bank P (first tool-structure divergence), all 20 complete blocks (q3, q4, q5, f01 to f17), 1,473 divergent states, full pool 1,700 units (85 tasks x 20 blocks). For this cell the paper's two-sided turnover is M = 17.9% [16.4, 19.5] on the full pool (analysis/fork/out/dev_all_20261001T070326Z.md).
- **Eligibility (frozen before any outcome).** 300 of 1,473 states are eligible (20.4% of divergent states, 17.6% of the 1,700 units; airline 187, retail 113; 41 tasks). Every rejected state fails at criterion (a): 767 are not tool calls and 406 have arguments with fewer than 2 keys. No state that reached criteria (b) to (d) failed them.
- **Arms.** KQ is new: 300 suffixes, plus 35 QQ no-op replays. QQ is the original episode and BQ is the existing Bank P branch; both are reused.
- **Key order survives rendering.** The Qwen3-8B template renders non-string arguments with `tojson`, and the transformers 5.17 `tojson` filter defaults to `sort_keys=False`. vLLM 0.29 `chat_utils` parses the arguments string with `json.loads`, which keeps order, and nothing on that path sorts keys. tau2 `to_litellm_messages` uses `json.dumps` without sorting. On all 300 states the transformed next prompt differs from the original next prompt; the first differing token is at position 4,924 or later. On all 300 states the locally rendered original next prompt reproduces Q's recorded next prompt ids (from the server).
- **Scope.** This covers validated tool-call states only. It is not a semantic null for all language actions. A flip under the deterministic server is a real consequence of this input intervention, not noise to subtract from the BF16 turnover.

PROTOCOL sha256: recorded by the lead at commit in docs/RESEARCH_LOG.md (ko-v1 entry). Later changes are dated amendments appended at the end.

| Frozen artifact | sha256 |
|---|---|
| `manifests/fork/keyorder_v1.json` (eligibility list: 1,473 rows, 300 eligible, per-state checks and predicted hashes) | `cbf12188ca485c03ae600f484af43f0bd22c29dcc19d8fda4436a1a1870d28ce` |
| Sorted eligible state ids (raw JSON) | `17307ad6d8a3122847eebf7932d3e8b81af06524ff47bd8141885024a3586d5b` |
| `scripts/a6000/keyorder_scan.py` (scanner that built the manifest; also recorded inside it) | `c6bedf229570dd3d636d770f835c69632d9276d0cbe9a383e5375791d98a790c` |

**Code.**
- `scripts/a6000/keyorder_scan.py`: transform and CPU eligibility scanner (`--selftest`).
- `scripts/a6000/keyorder_arm.py`: fork_driver mode `keyorder`. The dispatch is a single entry in `fork_driver.py`.
- `scripts/a6000/keyorder_selftest.py`: end-to-end KQ path through the real tau2 orchestrator, with a fake OpenAI-compatible server and no GPU.
- `scripts/a6000/make_tasks_keyorder.py`: task generator. `--write` refuses unless this file and the manifest are committed.
- `cloq/fork.py` is unchanged. `run_branch(st, "K", "Q", ...)` forces `st["a_K"]`.

---

## 1. Status and label

- **Exploratory.** The panel and the transform were chosen after the Bank P, SAMEPREC and COMMONSTATE results were known. Results are reported as an exploratory control and never as a confirmatory test.
- **Frozen readings unchanged.** No reading of Bank P, SAMEPREC, COMMONSTATE, NEWMETHOD, takeover window or holdout is amended. Nothing here reads `analysis/fork/holdout/`.
- **Priority.** The takeover-window panel (tw-v1, deadline 2026-10-05 21:00 PDT) keeps both simulator replicas, node005:8000 and node006:8000. Key-order tasks depend on the six tw-v1 panel tasks and run at a lower priority (-15 vs -21). The only alternative is a separate live replica (`--user-base`).

## 2. Transform (frozen, exactly one)

`reverse-top-level-keys`: for every tool call of Q's recorded action, the top-level keys of its arguments object are emitted in reverse order.
- **Kept unchanged:**
  - tool names;
  - argument values and their types;
  - nested objects, which keep their own key order (values are copied as they are);
  - arrays and their element order;
  - the number of calls and the call order;
  - tool-call ids and message content.
- **Always a change.** With at least 2 keys, reversal always changes the order.
- **Fixed rule.** The rule was fixed before scanning. It is never replaced by another rule (sorted, shuffled, nested) because of flips or coverage.
- **Coverage.** In this panel every eligible action has exactly one call, with 2, 3, 4, 5, 7 or 11 keys (97, 79, 91, 1, 19 and 13 states).

## 3. Eligibility (built first, without outcomes)

**Inputs.** The scanner reads `states/*.json` of `analysis/fork/dev/q8_gptq_w4_d1/g1..g4` (the directories `analyze_dev.discover` lists for this cell). It uses only these fields:
- the history;
- a_Q;
- the task and run config;
- the budget;
- recorded prompt-id hashes.

It never reads `branches/` or any reward, db_match or termination field.

A state is eligible iff all of the following hold, checked in this order (the first failing reason is recorded):

- **a.** Q's action is a tool call, every call has an arguments object, and at least one call has 2 or more keys.
- **b.** The parsed actions are identical:
  - dict equality of the canonical message;
  - `normalize_tool_call` per call;
  - `compare_actions` category `same`;
  - the raw (unsorted) JSON differs.
- **c.** Each action is executed on its own freshly restored environment, the same way `Orchestrator._execute_tool_calls` executes it. Identical results are required for:
  - the tool messages (content, error, requestor, id);
  - the DB and user-DB hashes;
  - the (steps, errors) recount.
- **d.** The next-prompt conditions hold:
  - The original episode has a next Q decision.
  - The locally rendered next prompt of the original action reproduces Q's recorded next prompt ids. This checks the render path.
  - The next prompt ids of the transformed action differ. If the template or serializer canonicalised key order, the tokens would be identical and the state would not be eligible.

**Results.** 300 eligible states. Rejections: `a:not_tool_call` 767, `a:lt2_keys` 406, none at b, c or d. Eligible states per block are 10 to 18.

## 4. Arms and run-time acceptance

**Continuation.** Q continues in every new arm. B continuation and the 510 common states are a separate later decision; neither is part of ko-v1.
- **KQ (new):** force a_K at h_t, then Q to the end. One suffix per eligible state.
- **QQ (reused):** the original Q episode. A 10% hash sample (`sha256("ko-v1-noop|state_id")`, 35 states) re-runs QQ, and every one must reproduce the original suffix: messages, prompt ids, termination, outcome, counters and final env hash (`fork_driver.noop_check`).
- **BQ (reused):** the existing Bank P branch from the same saved state.

**Servers.** Roles are copied verbatim from the Bank P tasks. The expected canaries, Q checkpoint sha and effective configs are those of `fork_dev_q8_gptq_w4_d1_g*`. A mismatch stops the task before any suffix runs.

**Per-state checks:**
- The state is rebuilt with `make_state` and must equal the saved Bank P state: id, history sha, prompt-id sha, env hash, budget and raw a_Q.
- a_K must equal the manifest's raw sha.
- Q regenerates a_Q at h_t (shadow): the completion ids are identical and the argument key order is the same.

**Per-KQ checks (outcome-blind; written to `keyorder_rows.jsonl`):**
- the forced first decision only;
- the reversed key order is present in the trajectory and in the forced decision record;
- the tool messages equal the scanner's;
- the first continuation prompt ids equal the scanner's prediction, come from the server and match the local rendering;
- history prefix, initial env hash and budget.

**Context overflow.** A context overflow is a valid failure (Y = 0), as in FORK_PROTOCOL W10/W70.

**Outputs.** Outcomes are written only to `analysis/fork/keyorder/q8_gptq_w4_d1/<g>/branches/`. They are read only by the analysis, after this protocol is committed.

**Quarantine.** As in Bank P protocol A, a fork task with any failed no-op or failed acceptance check is listed and excluded whole. Infrastructure errors leave the denominator and are counted.

## 5. Estimands

**Definitions.**
- **Unit and outcome.** The unit is task x block, as in Bank P. Y is retail/airline DB success: db_match and a user_stop/agent_stop ending (`fork_driver._y`). DB success does not include every official communication requirement.
- **Swap X in {K, B}** (key-order swap, BF16 swap):
  - rescue r_X = 1[Y_XQ = 1, Y_QQ = 0];
  - damage d_X = 1[Y_XQ = 0, Y_QQ = 1];
  - turnover M_X = r_X + d_X;
  - net G_X = r_X - d_X.
- **Paired differences.** M_K - M_B, G_K - G_B, r_K - r_B and d_K - d_B, all on the identical eligible states.

**Reported quantities.**
1. **Conditional (primary for the comparison).** The mean over eligible states of r, d, M and G for K and for B, and their paired differences.
2. **Coverage.** Eligible states out of 1,473 divergent states and out of 1,700 units, overall and per domain.
3. **Contribution to the full pool.** For each swap, the mean over the 20 blocks of the block mean over 85 tasks, with non-eligible units contributing 0. The share of the BF16 swap's full-pool M (17.9%) carried by eligible states is reported on the same pool. A conditional share is never compared with 17.9%.
4. **Joint flip table on eligible states.** Counts of K-only, B-only and both flips, split by direction.

## 6. Intervals

Every interval is paired: K and B share each draw, and differences are taken per draw.
- **Primary:** block bootstrap. The 20 blocks are resampled whole, B = 2000, seed 20261001, the same draws as `analyze_dev`. Conditional quantities are ratios within each draw.
- **Also reported:** t over block means (df = 19) and the crossed two-way bootstrap over tasks x blocks (41 tasks).
- **Disagreement.** When the intervals disagree, the conclusion uses the widest.

## 7. Reporting rules (fixed before outcomes)

- **K's turnover interval excludes 0.** Report that some consequences arise without changing the tool operation. Give the size relative to the BF16 swap with its paired interval.
- **M_K - M_B upper bound below 0.** Report that, on these states, the representation change moves outcomes less than the natural action replacement does.
- **Otherwise.** Report the bounds and state that the two are not distinguished. There is no equivalence margin, so equivalence is never claimed.
- **Never** subtract M_K from the BF16 turnover. K is a different intervention, not a noise floor.
- **Not identical to the reliability check.** The QQ no-op checks replay reliability on identical inputs. K checks the consequence of a representation change.
- **Every table states** the coverage, the units and the tasks x blocks.

## 8. Deadline and freeze

- **Sequence.** The protocol and the manifest are committed by the lead before `make_tasks_keyorder.py --write`. The generator enforces this.
- **Fixed design.** No change to the transform, the eligibility list, the arms or the estimands after any KQ outcome exists.
- **Completion.** The panel is completed within the submission window. If a group does not finish, the finished groups are reported as they are, with the missing blocks listed. There is no outcome-driven extension or rerun beyond infrastructure failures.

## 9. Build checks run (2026-10-05, CPU only)

- **`keyorder_scan.py --selftest`.** The transform rule invariants hold, including nested order kept and values unchanged. A 160-state sample gives 28 eligible, and the first differing token falls inside the transformed call.
- **Full scan.** 1,473 states in about 2 minutes; summary in §3.
- **`keyorder_selftest.py`.** Three g1 states (airline 2 keys, retail, retail 7+ keys) ran through the real orchestrator against a fake server that renders requests with the frozen template. Results:
  - all 9 KQ checks pass;
  - the prompt ids that crossed litellm equal the scanner prediction;
  - the QQ no-op correctly fails against the fake continuation.

  Real vLLM server-side rendering is checked at run time by `next_prompt_from_server`.

---

## Amendment 2026-10-05 (gate task, before the protocol commit)

- **What.** One gate task, `ko_gate_q8_gptq_w4_d1_f01` (`scripts/a6000/make_task_keyorder_gate.py`), requested by the lead. It runs mode `keyorder` on 8 eligible states of block f01 (Bank P group g1). Per domain, the states with the lowest `sha256("ko-v1-gate|<state_id>")` are taken: 4 airline and 4 retail. They were chosen from the frozen manifest only, before any key-order suffix existed. The 8 states are 77e2d66b7d581e2e, a167e44243032607, ec865088180437e3, fdb27b8002d28d3c, 791c2011eba41739, e34349b9202d441b, 51320550b2dce492 and 76b242d10491b9e5.
- **Checks.** The gate sets `noop_frac = 1.0`, so the untransformed Q -> Q re-run must reproduce QQ on all 8 states. The gate passes only if `keyorder_summary.json` reports `pass`. That requires the §4 per-state and per-KQ checks: identical tool messages, budget, prefix and initial env hash, and a next prompt that comes from the server and equals the scanner prediction. It also requires shadow identity and expected servers. Throughput is recorded.
- **Outcomes.** Gate outcomes are written only to `analysis/fork/keyorder/gate/q8_gptq_w4_d1_f01/branches/`. Nobody reads them before the protocol commit, and they are never pooled with the panel. The panel re-runs these states in its own directory. The transform, the eligibility list, the arms and the estimands are unchanged.
- **Scheduling.** The gate depends on the six tw-v1 panel tasks and runs at priority -15 (tw-v1 runs at -21). It therefore never competes with tw-v1 for a simulator replica.

## Amendment 2026-10-05b (analysis script, overflow acceptance fix, reference rates; before any KQ outcome)

TL;DR The §5-§7 analysis is fixed as code before any KQ outcome exists (no ko-v1 task has run; the gate is still in todo). A KQ context overflow before the first continuation decision now scores as a valid failure instead of quarantining its task. Bank P's own shadow and QQ no-op rates on these servers are recorded as the reference for the ko-v1 checks. The transform, the eligibility list, the arms and the estimands are unchanged.

- **Analysis script.** `analysis/fork/analyze_keyorder.py`, sha256 `779785c0a10ad683156dea4634e46764a6d4671ffd8cc15c1dae52b3fdcb9819`; synthetic selftest `analysis/fork/analyze_keyorder_selftest.py`, sha256 `dc0752c5132829fa70d695b2f91e5fa1360c695898c9c99ccfd05f26bd55b1fa` (`analyze_keyorder.py --selftest`; fake Bank P units with real split task ids and random Y, fake ko-v1 outputs; reads no fork output). Bank P units come from `analyze_dev.load_dir` on g1..g4 with snapshot `snapshot_auto_20261001T0600Z.json` (the snapshot of `dev_all_20261001T070326Z`), Bank P quarantine, `split_guard`, the strict W70 block rule and the W78 85-task panel rule. Output `analysis/fork/out/keyorder_<UTC>.{json,md}`.
- **Identical exclusions for both swaps.** A ko-v1 task with any failed QQ no-op (an errored QQ counts as failed, as in Bank P), KQ acceptance check, shadow, state identity, server expectation or manifest sha is quarantined whole: its eligible units leave for K and for B. A KQ infrastructure error or a missing KQ (including a ko-v1 task that never ran) removes that unit for both swaps. The strict block rule then drops each affected block for both swaps, and the dropped blocks are listed.
- **Full-pool contribution (85-task crossed rule).** For each swap and each of r, d, M, G: the mean over blocks of the block mean over all 85 panel tasks, with non-eligible units (non-divergent or ineligible) contributing 0. Intervals: block bootstrap over the 20 blocks, t over block means (df = 19), and the crossed bootstrap over all 85 tasks x 20 blocks (not over the 41 eligible tasks). The share of the BF16 swap's full-pool M carried by eligible states is the ratio of the two full-pool means on the same pool and the same draws (block and crossed). The conditional quantities use the ratio form over eligible units, with the crossed bootstrap over the eligible tasks only. A conditional share is never compared with 17.9.
- **Widest interval.** `widest` is the union of the block-bootstrap, t and crossed intervals. The §7 rules are evaluated on it. If the lower bound of M_K - M_B is above 0, which §7 does not name, the script reports the bounds and labels the reading as outside the §7 readings.
- **Overflow acceptance fix (`scripts/a6000/keyorder_arm.py`, sha256 `e7585644784009942146127643408224f48b4ae068b67a86427f17136e325bc8`).** Before the fix, every KQ context overflow failed acceptance and quarantined its task. `record_key_order` read `tool_calls` that the overflow record of `cloq/fork.py` does not keep. When the overflow came at the first continuation, no continuation decision existed, so `next_prompt_predicted` failed too. Now an overflow requires `forced_first` and `env_hash_init_ok`. It requires `record_key_order` and `next_prompt_predicted` only when their inputs exist. It records `overflow_at` (`before_first_continuation` or `continuation`) and the predicted next-prompt length `n_next_k`. Y_KQ = 0, as in FORK_PROTOCOL W10/W70. The summary counts overflows per category. The forced a_K is still checked before the run (`a_K_raw`). `scripts/a6000/keyorder_selftest.py` (sha256 `0c31f3fefe028e165870817c2fa5bdeee00cae8df14851229ece424935ee57a7`) adds a fake server that answers agent requests with vLLM's context-length 400. The KQ passes acceptance with `overflow_at = before_first_continuation`, Y_KQ = 0 and summary `pass`. The committed version of `kq_checks` fails the same record (`record_key_order` and `next_prompt_predicted` False).
- **Reference rates, Bank P on these servers (q8 GPTQ-W4 d1, g1..g4; the ko-v1 tasks copy their roles and expected canaries).**
  - **Shadow.** Q regenerated a_Q at t* with identical completion ids, prompt ids and action on 1,473 of 1,473 states (g1 365, g2 366, g3 369, g4 373). Source: the `q_replay` field of `search.json`. ko-v1's shadow additionally requires the same argument key order, which Bank P's `canon_msg` comparison did not check.
  - **QQ no-op.** 149 of 149 passed (g1 28, g2 37, g3 41, g4 43); no Bank P directory was quarantined. Source: `analyze_dev.load_dir` no-op records. All cells of `analysis/fork/out/dev_all_20261001T070326Z.md` give 924 of 924.
  - **The 17.9.** Same source: M = 17.941 on 1,700 units (85 x 20), with block bootstrap [16.353, 19.529], t [16.229, 19.653] and crossed [12.646, 24.296].
- **Locality of the perturbation (from the manifest, outcome-blind).** On the 300 eligible states the first differing token of the transformed next prompt lies 45 to 1,966 tokens before the end of the prompt (median 117, quartiles 46 and 389). In absolute position it is at 4,924 to 16,820. The prompts differ at 20 to 441 positions, and on 7 states the two prompts have different lengths. The token change therefore begins in the most recent tool call, near the end of the context. It does not begin in the system prompt or in earlier history.

## Amendment 2026-10-05c (overflow consistency check; before any KQ outcome)

TL;DR A KQ context overflow before the first continuation decision is now accepted only where the transformed next prompt is longer than the Q episode's. Any other such overflow fails acceptance and quarantines its task. The rule is enforced in the arm and again in the analysis. The transform, the eligibility list, the arms and the estimands are unchanged.

- **Outcome status.** No ko-v1 task has run: `analysis/fork/keyorder/` does not exist, and no `keyorder_*` output exists in `analysis/fork/out`. Nothing under `analysis/fork/keyorder/**/branches/`, `analysis/fork/takeover/q8_*/f0*/branches/` or `analysis/fork/holdout/` was opened. Tests used synthetic data, the frozen manifest and the Bank P states with a fake server. Not post hoc.
- **Wording fix (2026-10-05b).** That TL;DR says the fix applies to an overflow "before the first continuation decision". The body and the code cover every KQ context overflow, at either `overflow_at`. The body governs.
- **Mechanism.** Eligibility criterion d means the original Q episode sent this exact next request (`n_next_q` tokens) and it did not overflow. Under the deterministic server, an overflow at the first continuation after a_K is consistent only with a longer transformed prompt (`n_next_k > n_next_q`). In the manifest this holds on 1 of the 300 eligible states (`545d84908201887a`, 10,071 vs 10,070 tokens). The other 6 states whose prompt lengths differ have `n_next_k = n_next_q - 1`. Any other overflow at that point is a render, server or limit fault. Scoring it Y_KQ = 0 would add a K damage whenever Y_QQ = 1, which biases M_K upward.
- **Arm (`scripts/a6000/keyorder_arm.py`, sha256 `b256174719797987a4868660973af30fba42a562173afea4f409fb09661053b4`, supersedes `e7585644…`).** On a context overflow with no continuation decision, `kq_checks` adds `overflow_consistent = n_next_k > n_next_q` to the required checks. It records `n_next_q` next to `n_next_k`. The summary counts `overflow_consistent` failures in `kq_check_fail`. An overflow at a later continuation is unchanged: Y_KQ = 0, with `next_prompt_predicted` required. The overflow record of `cloq/fork.py` stores `prefix_ok` as None, so `prefix_ok` is not checkable there.
- **Analysis (`analysis/fork/analyze_keyorder.py`, sha256 `b0f306cd5e856c5f734189ec5190f9e8f312f8f3153e4c3ac88a4477af2d862a`, supersedes `779785c0…`).** `ko_group` applies the same rule from the manifest row, so an inconsistent before-first-continuation overflow quarantines the task even if a row reports `ok`. Rows are now parsed with `splitlines()`, skipping blank lines, so a missing trailing newline no longer drops the last row.
- **Selftests.** `scripts/a6000/keyorder_selftest.py` (sha256 `1c49210348d4075b43245ae748ed67ff2894586b80c02022756c2d9ab3956437`): the fake 400 server makes a g1 state with `n_next_k = n_next_q` overflow, and that KQ fails acceptance (`overflow_consistent` False, summary `pass` False). On `545d84908201887a` (g2) the same overflow passes with Y_KQ = 0 and `pass` true. The earlier 3-state checks pass unchanged. `analysis/fork/analyze_keyorder_selftest.py` (sha256 `99623867b3fe0289e9be3b066aca9b658e0a880452658f427a757c262dc334fa`) gives the synthetic overflow states `n_next_k > n_next_q`. It checks that the same states with `n_next_k = n_next_q` quarantine their task, and that a rows file without a trailing newline loses no row. Both passed 2026-10-05.
- **Open review items (not changed here).** A KQ agent-output error is still treated as an infrastructure error, with no A6 split or sensitivity. The analysis has no protocol self-guard and does not recompute `noop_sample` or cross-check summary `pass`. The reading gives no M_K / M_B ratio.

## Amendment 2026-10-05d (analysis script frozen; before any KQ outcome)

TL;DR The 2026-10-05c code is frozen as the §5-§7 analysis and the ko-v1 arm, frozen before any outcome of this experiment was read. No code, transform, eligibility list, arm or estimand changes.

- **Frozen files.** `analysis/fork/analyze_keyorder.py` sha256 `b0f306cd5e856c5f734189ec5190f9e8f312f8f3153e4c3ac88a4477af2d862a`; `analysis/fork/analyze_keyorder_selftest.py` sha256 `99623867b3fe0289e9be3b066aca9b658e0a880452658f427a757c262dc334fa`; `scripts/a6000/keyorder_arm.py` sha256 `b256174719797987a4868660973af30fba42a562173afea4f409fb09661053b4`; `scripts/a6000/keyorder_selftest.py` sha256 `1c49210348d4075b43245ae748ed67ff2894586b80c02022756c2d9ab3956437`. These equal the 2026-10-05c values.
- **Outcome status.** No ko-v1 task has run: `analysis/fork/keyorder/` holds only the eligibility files, and no `keyorder_*` output exists in `analysis/fork/out`. Nothing under `analysis/fork/keyorder/**/branches/`, `analysis/fork/takeover/q8_*/f0*/branches/` or `analysis/fork/holdout/` was opened. `analyze_keyorder.py --selftest` (synthetic Y) and `keyorder_selftest.py --manifest manifests/fork/keyorder_v1.json` (fake server, Bank P states) passed at 07:46 PDT 2026-10-05. Any later change to these files needs a further dated amendment with the new sha256 values.

## Amendment 2026-10-05e (GPT 10-05 review; before any KQ outcome)

TL;DR Three pre-outcome fixes that GPT requested: (1) the overflow record keeps its audit trail, and acceptance verifies it rather than skipping checks; (2) conditional readings use only intervals for the pooled-ratio estimand; (3) a sensitivity scores A6 agent-output errors as Y = 0. The transform, eligibility, arms and estimands are unchanged. Supersedes the 2026-10-05d frozen hashes.

- **Overflow audit (`cloq/fork.py` sha256 `7b4ef65e5067d025dd885b9832c572c61c0f3950d6e25070d987c1bc012213f5`).** The context-overflow record now carries:
  - `partial_suffix`, the messages executed before the overflow;
  - `partial_prefix_ok`;
  - `env_hash_at_overflow`;
  - per-decision `tool_calls`, `content`, `finish_reason` and `parser_error`.

  Y = 0 is unchanged (W10/W70). The change is additive. The takeover panel already ran under the previous file and does not read these fields.
- **Arm (`scripts/a6000/keyorder_arm.py` sha256 `06e219eb1516d7b85cc0988e03c4984bd1a17b21648b24081ce9e370d1874281`).** On an overflow, `kq_checks` now requires `record_key_order`, `trajectory_key_order`, `tool_messages` (all `n_calls` results) and `prefix_ok`, computed from the partial record. The 2026-10-05c rule still applies: `next_prompt_predicted` when a continuation decision exists, else `overflow_consistent`. No check is skipped for missing input.
- **CPU regression (`scripts/a6000/keyorder_selftest.py` sha256 `4e762c70d93d7df65ecc06f8040efb15c918807609472c2ec816d10bc43f3625`).** Through the real `run_branch`, a fake vLLM 400 overflow must pass with all four audit checks True and Y_KQ = 0. The same record with `partial_suffix` removed must fail acceptance. Passed 2026-10-05.
- **Estimand consistency (`analysis/fork/analyze_keyorder.py` sha256 `9b987e68c4ba0874fcf47020d9ae6e58b19d89b35c63e6b758da9bb1acbfa895`).**
  - **Conditional readings.** The point estimate is the pooled ratio over all eligible states. Its intervals are the block bootstrap and the crossed bootstrap, both of that ratio, and the §6 "widest" rule uses only these two.
  - **Auxiliary t.** The t interval is over per-block ratios, i.e. the mean of block proportions with 10 to 18 eligible states per block. That is a different estimand, so it is stored as `aux_t_mean_of_block_ratios` and never enters a reading.
  - **Full pool.** Every strict block holds all 85 tasks, so the block mean equals the pooled mean and t stays in the union.
- **A6 sensitivity (never primary).** A KQ branch error is classed with `analyze_newmethod.a6_class` (with `plus=True`). The primary is unchanged: the error leaves the denominator (§4). If any A6 agent-output error occurs, a second estimate scores those states Y_KQ = 0 and reports M_K, M_K − M_B and their rules. Error counts are reported by class.
- **Selftest (`analysis/fork/analyze_keyorder_selftest.py` sha256 `df2f628d8379ee810c00f8f265c6c5d8305a6aa580cd6b32ce9fe633c64ca086`).** It asserts:
  - with unequal eligible counts per block, the pooled ratio differs from the mean of block ratios;
  - conditional `widest` is the union of block and crossed only;
  - an A6 error enters only the sensitivity.

  Passed 2026-10-05.
- **Scope (reporting).**
  - The 300 eligible states cover 41 tasks: 187 airline and 113 retail.
  - Any K result is limited to these verified tool-call states. A null K turnover does not exclude effects of other representation changes or of free-text changes.
  - Before the panel is released, the gate is checked on its recorded counts, hashes and acceptance fields, not only on `pass`.
- **Outcome status.** No ko-v1 task has run (the gate is still queued). No keyorder, takeover-window or holdout branch was opened.

## Amendment 2026-10-05f (release order; before any KQ outcome)

TL;DR At the user's instruction, the four panel tasks (g1 to g4) were released at about 09:10 PDT, alongside the gate and the last takeover-window task. Previously the panel was to be released only after the gate's acceptance had been checked. Nothing else changes: transform, eligibility, arms, estimands, analysis code and acceptance rules are the same.

- **What still holds.**
  - Each panel task runs the full outcome-blind acceptance (shadow, QQ no-op, KQ checks, state, server, manifest), and a task that fails it is quarantined whole (§4).
  - The gate's counts, hashes and acceptance fields are checked, and recorded, before any panel outcome is read.
  - If the gate shows a systematic fault, the panel is not analysed until the fault is understood, and the decision is recorded in a further amendment.
- **Load.** The two simulator replicas (node005:8000, node006:8000) now carry up to two key-order tasks each, plus the gate and takeover-window f03. The QQ no-op check detects any loss of replay determinism under load.

## Amendment 2026-10-05g (g2 restart; before any KQ outcome is read)

TL;DR To speed things up, the user stopped g2 and four post-freeze tasks at 12:52 PDT. The four tasks are deferred and do not enter the paper. g2 was requeued with `resume: true`, concurrency 12 and a dedicated simulator replica (node005:8000). g4 continues unchanged and now has node006:8000 to itself.

- **What resume keeps.** A state whose branch file already holds every needed arm is not re-run. States that were in flight at the stop are re-run from the frozen state. Acceptance per state is unchanged.
- **Replica choice.** node005:8000 is the replica that g1 and g3 used, and it passed the identical-answer check against node006:8000 at startup. The QQ no-op checks on the noop sample still test replay on the new replica.
- **Scope of the change.** Transform, eligibility, arms, estimands and the frozen analysis code are unchanged.
