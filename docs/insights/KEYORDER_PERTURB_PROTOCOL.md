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
