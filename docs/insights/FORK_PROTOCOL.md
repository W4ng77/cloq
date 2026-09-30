**TL;DR** Protocol `fork-v1` for the same-state 2×2 fork (EXTERNAL_REVIEW_GPT61_20260930.md §E). A fork state is
Q's full saved history before one of its decisions. tau2 rebuilds the DB, the telecom device state and the
user-simulator state from it by strict replay. The current action is forced (a_B or a_Q), and the continuation runs on a
separate vLLM server per checkpoint and serving config, with the step and error budget restored.
**Engineering gate: PASS (§8), deterministic protocol A.** It covers 20 Q→Q and 10 B→B bit-exact no-ops (retail, airline,
telecom), same-checkpoint four-branch agreement, order/concurrency isolation, budget accounting, re-prefill, and the
hooked KV config. Throughput and the development cost (≈ 260–320 GPU-h for q4/q8 × GPTQ/AWQ × 85 tasks × 20 blocks) are
in §9; the development plan (not queued) is in §11. Code: `cloq/fork.py`, `cloq/fork_annotate.py`,
`scripts/a6000/{fork_driver,fork_serve,make_tasks_fork_dev}.py`, worker kind `fork`.

# Fork protocol fork-v1

Scope: q4/q8 × GPTQ-W4/AWQ-W4 (development: 85 tasks; confirmation: telecom holdout, `manifests/telecom/dev_v1.json`).
Everything here was written before any fork outcome was inspected.

## 1. Objects

| Term | Definition | Code |
|---|---|---|
| block | One closed-loop run of a cell (Q = quantized agent) on one stated prompt nonce: `runs/<run_id>/<domain>/`. Existing `a6k2_<m>_<cell>_q<k>` runs are blocks; new blocks = new nonces (`manifests/fork/dev_blocks_v1.json`). | `fork.Block` |
| decision t | Q's t-th generated agent message (trajectory index `agent_positions[t]`, the greeting excluded) ↔ `decisions.jsonl` record t (last attempt, W8). Counts must agree, else the task is excluded. | `agent_positions` |
| h_t | All trajectory messages before decision t: agent, user and tool messages, both requestors. | `make_state` |
| a_Q | Q's recorded message at t (from trajectory.jsonl). | `state["a_Q"]` |
| a_B | B's full greedy action at h_t (§3). | `state["a_B"]` |
| branch XY | Force a_X at h_t, then controller Y to the end: BB, BQ, QB, QQ. QQ is the original; the fork QQ is the no-op check. | `run_branch` |
| primary state | First semantic action divergence along Q's history, at most one per task × model × checkpoint × block. It is frozen (state file written) before any branch runs. | `search_task` |

## 2. State restoration (why a state is complete)

tau2's half-duplex orchestrator (`third_party/tau2-bench/src/tau2/orchestrator/orchestrator.py::initialize`) accepts
`task.initial_state.message_history`. The fork gives it a task copy with `message_history = h_t`, and tau2 then does the following.
- **Environment.** A fresh environment is built with the task's `initialization_data` and
  `initialization_actions`. Every tool call in h_t (agent and user) is replayed with `strict=True`, which means a replayed
  mutating call must return exactly the recorded content (`environment.py::set_state`). This rebuilds the retail/airline DB and the
  telecom user device DB (dual control: user tool calls have `requestor="user"` and are replayed the same way).
  `sync_tools()` runs after every mutating call and at the end, as in live play.
- **Agent.** `agent.get_init_state(history)` takes the agent-visible messages (`is_valid_agent_history_message`: all assistant
  messages, user text, tool results with requestor assistant). The CLOQ agent re-applies the frozen context policy and
  renders the prompt from them, exactly as in the original run.
- **User simulator.** `UserSimulator.get_init_state(history)` takes the user-visible messages (`is_valid_user_history_message`:
  user messages including their tool calls, assistant text, tool results with requestor user). The simulator has no
  other state. Its system prompt is the global guidelines plus `str(task.user_scenario)`. The persona is None in text mode.
  Generation is greedy (T=0, top_k −1, seed = the original simulation seed via `set_seed`) on a batch-invariant server with
  a canary. Its next reply is therefore a function of (instructions, visible conversation). Nothing is unrecoverable.
- **Seed.** The orchestrator is built with the original `sim.seed` (trajectory.jsonl), so the agent and user `llm_args["seed"]` equal the original's.
- **Nonce.** The system prompt's `Session ID` line is set per agent instance from the block's `environment.json` `prompt_nonce`.
  The original CLOQ agent read it from the process env, which cannot hold several blocks in one process.
- **Timestamps.** tau2 rewrites history timestamps (`_add_timestamps`). No model sees them. Trajectory order is checked
  (`prefix_ok`).

Evidence, CPU only (no server):
- For every decision of the checked blocks, the prompt the restored agent renders equals Q's recorded server-side
  prompt ids (`analysis/fork/gate/cpucheck_{q4,q8}.json`).
- Every max_steps / too_many_errors episode is reproduced by the step/error recount (§4).
- Terminal states tested on the live simulator (the last decision forced, the real simulator replies): the final user reply, DB hash,
  budget and reward reproduce 6/6. That test came before the gate and is not gate evidence.

## 3. Divergence search

For t = 0, 1, … along Q's decisions (`fork_driver.search_task`):
1. Restore h_t. B's agent (same CLOQ agent code, same context policy, same llm_args including greedy, max_tokens 1024,
   top_logprobs 5, seed) sends the same chat request to the B server. The B server renders it with the same template and parses
   the output with the harness's own tool parser (vLLM hermes, server side). The server-returned prompt ids **must equal
   Q's recorded prompt ids** at t. Otherwise the task is excluded with that reason (never coded as "no divergence").
2. Compare a_Q and a_B semantically (`fork.compare_actions`). Classes: act (tool calls), talk (text), stop (`###STOP###`),
   parse_fail (tool-call markup the parser rejected), empty. Primary categories, first match: `class:<q>-><b>`,
   `invalid_tool` (a name outside the domain's tool list), `tool_count`, `multi_tool_order` (same calls, different order),
   `tool_name`, `invalid_args` (missing required or unknown keys), `tool_args`. Arguments are normalised by
   `cloq.metrics.normalize_tool_call`: key order and JSON whitespace ignored, string whitespace collapsed, integral floats
   become ints. Non-primary: `same`, `text_only` (same class, different text; recorded in `text_only_before`).
3. At the first primary divergence, stop and freeze the state: write `states/<state_id>.json` with a_B, then check the
   save/load round trip (§6). Also check Q replay: the Q server regenerates a_Q from h_t, and the completion ids must equal the recorded ones,
   which confirms checkpoint identity and state restoration at the fork point.
4. No primary divergence through the last decision means `no_divergence` (the task stays in the denominator with zero effect).

## 4. Branch execution and budget

`fork.run_branch(state, first, controller)`:
- **Forced action.** tau2's `set_state` cannot replay a history that ends in a tool call without results (it raises "Tool message
  expected"). So a_X is not appended to the history. Instead, `ForkAgent` returns a_X for the one agent step that follows h_t
  (h_t always ends with a message addressed to the agent) and logs the prompt it would have seen. a_X then passes through
  the orchestrator's normal step. Tool calls are executed by the real environment. Text is answered by the real user
  simulator, which never reuses observations from the old trajectory. The forced action consumes one step, and its tool errors
  count, as in live play.
- **Budget.** tau2 restarts `step_count` and `num_errors` at 0 when starting from a history. The fork restores them to
  `budget_used(h_t)`: one step per agent or user message plus one per tool-execution step; errors = tool results with
  `error=True` on either side. The remaining budget is therefore the original's, not reset. Recount check: on the checked blocks,
  every max_steps episode recounts to 200, or 201 when step 200 was a tool call (tau2 skips the check while
  a tool result is pending), and every too_many_errors episode recounts to 10 errors.
- **Continuation.** The controller server continues to the end with the original run's tau2 config (max_steps 200,
  max_errors 10, user llm_args, same simulator model).
- **Scoring.** `evaluate_simulation(sim, ORIGINAL task, ALL_IGNORE_BASIS)`: the gold environment must not replay h_t.
  `official_reward` is computed as in `cloq.run_arm.basis_reward` (retail/airline: DB success; telecom: official task-basis
  success, ENV_ASSERTION[+ACTION]).
- **Recorded per branch.** Suffix messages, per-decision prompt/completion id hashes (server ids for generated decisions,
  local render for the forced one), usage, api_base, final live DB hashes and DB hashes from replaying the full branch
  trajectory, counters, duration.

## 5. Serving

- B and Q run on two vLLM servers (worker kind `fork`, `scripts/a6000/worker.py::run_fork`).
  - `gpus: 2`: one server per GPU.
  - `gpus: 1`: both servers on one GPU with `GPU_UTIL=gpu_util` (0.44), started one after the other.
  - Ports are worker port + 100 (B) and + 200 (Q).
- The BF16 server must reproduce the model's canary reference (W3). The Q canary is recorded, and Q's identity is checked by
  regenerating recorded decisions (`idcheck`, completion ids by prompt ids) and by the Q replay at each state.
- Quantized checkpoints are rebuilt deterministically from their spec (the original run's weights were deleted after loading and
  never hashed). Identity is established by reproduction, not by hash. From now on, `ckpt_sha256` of every fork server's
  weights is recorded in `logs/tasks/<id>.servers.json` and the task result.
- A controller switch sends the whole context to the other server process, which prefills it itself. vLLM's prefix cache
  lives inside one engine process, so no KV or prefix cache is ever shared across weights. Per-server
  `vllm:prefix_cache_*` counters are recorded at the start and end.
- The simulator is the node's port 8000 or `queue/USER_BASE.<node>` (same model and canary on every node).
- **Per-role serving configuration** (fix of the W34 bug: before it, `run_fork` ignored `serve_env`/`serve_extra`, so
  a KV- or activation-quantized Q would have been served unquantized; no such fork had run). Code: `scripts/a6000/fork_serve.py`.
  - **Roles.** A task gives each role in full: `task["B"]`, `task["Q"]` = `{"ckpt", "serve_env", "serve_extra"}`. The legacy
    `q_ckpt`/`b_ckpt` map to empty serve_env/extra.
  - **Launch.** Each role's server gets the model env, then its serve_env on top, and serve_extra after the fixed vLLM
    args, as `run_eval` does.
  - **Canary.** The BF16 reference canary is checked only for the plain BF16 path; hooked or extra-arg servers are a
    different flavour by design, as in run_eval.
  - **Recorded per role** (`logs/tasks/<id>.servers.json` and the gate output `servers`): full launch args, serve_env,
    W/A/K/V bits, hook version (sha256 of `scripts/a6000/pyhooks/*.py`), compile-cache namespace (`kvq_b<b>_r<rot>_<which>`
    or default), hook coverage, weights identity, and `effective_config_sha` (the hash of all of these plus model,
    max_model_len and frozen numerics env; not GPU, port or gpu_util).
  - **Same configuration** means equal `effective_config_sha`, never the same weight path. Same config ⇒ canaries must be
    equal. A pure-KV Q shares B's weights (built once) but runs its own server with its own config hash.
    `expect_same_numerics` / `expect_distinct_numerics` assert canary equality or inequality.
  - **Hook coverage.** The KV hook prints one `hooked attention` line per Attention instance built in the engine
    process (added to `pyhooks/cloq_kvq.py`; model-construction time only, numerics unchanged). A hooked role fails at
    startup unless the patch is installed and every decoder layer (config `num_hidden_layers`) is hooked.
  - **Acceptance tasks (q4, 1 GPU).**
    - `fork_accept_kv16_bridge_q4`: KV16 through the hook must equal the plain BF16 path, with the same canary and four
      branches equal to the BF16 original.
    - `fork_accept_kvq_q4`: pure-KV Q (INT4 + Hadamard) vs plain BF16 B on distinct servers with distinct canaries; gate
      (a)(c)(d)(e) under the hooked config.
    - `fork_accept_kvq_same_q4`: both handles on the hooked config; four-branch no-intervention agreement.
- **Derived checkpoints (restore/resid, `scripts/a6000/derived.py`, W39-pert).** Per role, the same canary rules as
  run_eval, recorded in `servers.<role>.derived.canary`:
  - an equals-BF16 build must reproduce the BF16 reference;
  - an equals-Q build must reproduce the per-base reference `canary_agentq_<base>`;
  - every tag must reproduce its own `canary_derived_<tag>`.

  For restoration forks, the Q role is `resid` α=1 or `restore` arm `none`, so Q and every arm come from the same cached
  base (`ckpt_cache/base`).
- **Activation hook (`cloq_aq`).** A bits come from `CLOQ_AQ_BITS`. Coverage: with bits < 16 the number of quantized linear
  modules in the engine process must equal len(`CLOQ_AQ_ONLY`) × layers. The hook-reported compile-cache roots are recorded.
- **Activation, SmoothQuant and QuaRot roles (W46).**
  - Hook configs are read as the hooks read them (`CLOQ_AQ_*`; `CLOQ_KVQ_ROT` 0 / 1 / qk).
  - The compile-cache namespace is probed from the hooks' own sitecustomize and asserted against the cache roots they
    report. vLLM's compile hash does not see the hook env, so every hooked config gets its own directory.
  - `requires_serve_env` / `forbids_serve_env` are enforced per role.
  - A config with no original run is tested with `gate_same` `foreign_states`: cross-handle equality, not replay.
- **Allocation guard.** q8 needs one GPU per server; two 8B servers do not fit one A6000 at max_len 33792.
  `fork_gate_q8_telecom_iso` first failed this way on node006, whose runner (job 49642, pre-424df02) ignores
  `task["gpus"]`. `run_fork` now refuses a wrong allocation before building. The dev generator pins q8 tasks to
  node004/005/007.
- **GPU sharing.** Only one worker owns a GPU. With `gpus: 1` that single fork worker hosts both B and Q (GPU_UTIL 0.44
  each). Two independent workers must never share a card (`stop_server` kills every process on its GPUs, and the runner
  allocates whole cards). The 1-GPU B+Q layout ran the q4 gate at concurrency 8 (mean prompt 7.3k tokens) with no
  failure.
- **Counting.** Replicate blocks are complete shared-nonce blocks (existing q3–q5 + new f01–f17 = 20 per cell,
  `manifests/fork/dev_blocks_v1.json`), not queue jobs.

## 6. State manifest (machine-readable; one JSON file per state)

```json
{
 "protocol": "fork-v1",
 "state_id": "sha256([run_id, domain, task_id, t])[:16]",
 "run_id": "block run id", "domain": "retail|airline|telecom", "task_id": "tau2 task id", "decision_idx": "t",
 "n_decisions_orig": "Q decisions in the original episode",
 "nonce": "prompt nonce of the block (environment.json prompt_nonce)",
 "checkpoint": "Q checkpoint spec from the run config (kind, wbits, calib manifest)", "arm": "run arm",
 "model": {"hf_id": "...", "revision": "...", "chat_template_kwargs": {}},
 "simulator": {"user_model_id": "...", "sim_seed": "original simulation seed", "llm_user": "...", "llm_args_user": {}, "original_api_base": "..."},
 "agent_llm": {"llm_agent": "...", "llm_args_agent": "greedy args incl. max_tokens, top_logprobs, chat_template_kwargs"},
 "run_config": "the block's full tau2 TextRunConfig (max_steps, max_errors, seed, ...)",
 "max_prompt_tokens": 32768,
 "task": "full tau2 Task dump as run", "task_sha": "sha256 of the task dump", "n_prefix": "messages before step 0",
 "history": ["full h_t: every message dict (agent, user, tool; both requestors)"],
 "history_sha": "sha256 of the canonical history (ids/timestamps excluded)", "n_history": 0,
 "budget": {"steps_used": 0, "errors_used": 0, "max_steps": 200, "max_errors": 10, "steps_left": 0, "errors_left": 0},
 "env_hash": {"db": "agent DB hash after strict replay of h_t", "user_db": "user/device DB hash (telecom) or null"},
 "q_decision": {"prompt_ids_sha": "sha of Q's recorded prompt token ids at t", "n_prompt_tokens": 0, "prompt_sha256": "rendered prompt text sha",
                "completion_ids_sha": "...", "system_sha256": "...", "tools_sha256": "...", "parser_error": false, "finish_reason": "..."},
 "a_Q": {"message": "recorded Q message", "source": "trajectory"},
 "a_B": {"message": "B's parsed message", "prompt_ids_sha": "must equal q_decision.prompt_ids_sha", "completion_ids_sha": "...", "record": {}},
 "divergence": {"category": "primary category", "q_kind": "...", "b_kind": "...", "q_calls": [], "b_calls": [], "t_star": 0, "text_only_before": []},
 "q_replay": {"completion_ids_ok": true, "prompt_ids_ok": true, "action_ok": true},
 "io_check": {"history_sha_ok": true, "env_hash_ok": true, "task_sha_ok": true},
 "orig": {"termination_reason": "...", "reward": 0, "db_match": true, "official_reward": 0, "suffix_sha": "...",
          "suffix_prompt_ids_sha": ["Q's recorded prompt id hashes for t..end"], "budget_final": [0, 0]},
 "search": {"shadow_seconds_total": 0, "n_shadow": 0},
 "versions": {"tau2_commit": "...", "cloq_commit_run": "...", "packages": {}},
 "created": 0
}
```
The template and tokenizer versions are pinned by `model.revision`: the tokenizer and chat template come from that HF snapshot. They are also
checked, not assumed, by the equality of the prompt-id hashes (`q_decision.prompt_ids_sha` vs the local render and vs the B server).
The server side of each fork run is recorded in `logs/tasks/<fork task>.servers.json`: GPU, port, pid, checkpoint spec, `ckpt_sha256`,
canary per server, `canary_ref_ok` for BF16, and the simulator URL.

## 6b. Per-fork annotation (review round 2; `cloq/fork_annotate.py`, version fork-annot-v1)

The BF16 action is only a reference. A Q action is never labelled wrong because it differs from a_B. Three independent
fields are recorded per state × branch. a_Q and a_B are judged by the same checks.

| Field | Automatic content | Manual slot |
|---|---|---|
| 1. defect of the current action | invalid tool (tool-type table); invalid args (schema: missing required or unknown keys); execution error (the environment rejected the call: precondition or argument violation, with its text); ungrounded ids (an id-valued argument absent from every earlier message and tool output); `write_unconfirmed_proxy` (write tool with no explicit confirmation in the last user turn; a regex proxy, not an authorisation verdict); malformed (parse failure or empty); ends_episode, and premature_end = ends_episode and the branch fails | `defect.manual` |
| 2. later correction aimed at it | first later turn that calls the same tool without error (for an invalid tool: any valid tool); a same-tool call with grounded ids; for an unconfirmed write, the user objection turn and later writes (a write is not undone by a retry) | `correction.manual` |
| 3. requirements at the end | success under its name (retail/airline **DB success**; telecom **official task-basis success**, official_reward == 1); each env assertion, gold action check and communicate check; recursive DB paths that differ from the gold DB (agent and user/device DB) | none |

The remaining step and error budget at the state is attached. Recovery is claimed only for "defect → correction → satisfied".
Otherwise the result reads "not recovered under the tested continuation controllers and the fixed remaining budget".
Tool types come from `analysis/insights/iter_4/tool_types.py`. It is verified against the tau2 `@is_tool` decorators by `--check`;
the old write regex misses 5/6 telecom writes. Its sha256 is stored in every annotation (`tool_types_sha256`), so the table
is frozen by hash before confirmation. Annotation runs offline on the saved state and branch files:
`python -m cloq.fork_annotate --dir <fork out dir>` → `annotations.jsonl`.

Round-3 refinements (fork-annot-v1, `cloq/fork_annotate.py`). The automatic part and the record schema are implemented;
the LLM and human labels are separate tools, to come later.
- **Raw records.** Every judgement keeps the records behind it: the call and its arguments, the environment's result
  text, the schema, the id's presence in the DB at the state and in the conversation, the last user turn and earlier
  confirmation turns, `changed_by_action` (DB paths changed by the forced step), `env_changing`, `extra_steps_used`,
  `requirements_at_state` and `requirements.failing` at the end.
- **Statuses.**
  - `violation` only where the environment makes it verifiable: invalid tool, schema-invalid args, a call the environment
    rejected, or an id found neither in the DB nor in the conversation.
  - `needs_review` where a string rule is not enough:
    - an id present in only one of the two; a legitimate substitute is possible;
    - a write whose last user turn has no explicit confirmation; earlier confirmation turns are listed;
    - an episode-ending action in a failing branch. If the task was already complete at the state, this is
      `ok_task_already_complete` instead.
- **LLM and human slots.** Each record carries `manual` and `llm` slots (null for now).
- **Blinded review export.** `python -m cloq.fork_annotate --dir <out> --review-export` writes `review/packets.jsonl` and a
  separate `review/KEY_unblinding.jsonl`.
  - Packets are stripped of model, precision, checkpoint, nonce and branch source, and ordered by
    sha256(salt|state|branch).
  - Each packet holds the instructions, the history, the current action, the continuation, the end status and the
    automatic events.
  - Label slots `defect`, `correction` and `failed_requirements` each take `value`, `evidence_location` and `cannot_judge`.
- **Review sampling.** About 80 states, stratified by consequential / non-consequential, tool type and automatic label;
  about 20 double-reviewed. The stratified sample is drawn from `annotations.jsonl` with a fixed salt, not by hand.

## 6c. Deterministic forks (protocol A, primary) and stochastic forks (protocol B, fallback)

Both are fixed here before any development fork outcome.

**Protocol A: deterministic (primary).**
- **Condition.** No-op replay is exact: gate (a)–(e) pass, and the per-run QQ no-op sample in development stays exact.
- **Estimate.** Each branch is run once. Y_XY is a deterministic function of the fork state and the controllers.
- **Estimands.** G = E[Y_BQ − Y_QQ] and A/C/I (review §E), where the expectation runs over tasks, nonces (blocks) and
  checkpoints only.
- **Development checks.** A development QQ no-op that differs from the original is a protocol failure, not noise:
  - the affected block is quarantined;
  - the cause is found;
  - the rate is reported;
  - it is never subtracted from G.

**Protocol B: stochastic (only if A fails for an identified, repeatable source of randomness in the continuation).**
- **Preconditions (all verified).**
  - The start state is identical: history hash, DB/device hashes, budget, and simulator input (the prompt ids of the
    first user request are logged).
  - The residual difference comes from a describable, repeatable randomness in the subsequent execution, for example
    sampling with per-request seeds.
  - Hidden-state loss, branch contamination and systematic replay bias disqualify protocol B; repeats cannot fix them.
- **Estimand.** G = E[Y_BQ] − E[Y_QQ], the expectation over the declared continuation randomness (and over tasks, nonces
  and checkpoints). Each branch expectation is estimated by R repeats.
- **Repeats, seeds and failures.**
  - R = 4 per branch, including QQ; no adaptive stopping.
  - Seed of repeat r: sha256("fork-v1-B|state_id|branch|r")[:8] as an integer, sent per request (agent and simulator).
  - A repeat that fails for infrastructure reasons is retried once with the same seed. After that it is recorded as
    missing, never as failure. A state with any missing repeat is excluded from the estimate and counted in the
    exclusions.
- **Inference.**
  - Repeats are nested in task × nonce × state and are not independent samples.
  - Per state, the branch mean over its R repeats is the unit.
  - Intervals come from the crossed task/nonce resampling of the main analysis.
  - Same-configuration replays estimate only repeatability and run variance, reported separately. They are never
    subtracted from G.

**Current choice.** Protocol A, since the no-op replay is exact on every gate state (§8). Protocol B is not used.

**Decision points.**
- 10-01 evening: deterministic, stochastic or continued engineering (§8).
- 10-03: if state restoration still cannot be verified, the paper becomes measurement-only and the causal reading of
  action interventions is withdrawn.

## 7. Engineering gate (acceptance, evening of 10-01)

| Check | Definition | Where |
|---|---|---|
| (a) no-op Q→Q, B→B | Force the recorded action with its own controller. The following must equal the original suffix: every prompt token hash, messages (tool calls, arguments, tool results, user replies), final live DB hash and replay DB hash (= original full-trajectory replay hash), termination, reward, db_match, official_reward, final step and error counters. Q→Q runs at the gate states; B→B at mid-episode states of BF16 blocks. | `gate.json: states[].a_noop_QQ, a_noop_BB` |
| (b) same checkpoint | B and Q handles on two servers of the same Q checkpoint. The B-handle shadow must reproduce a_Q, and BB/BQ/QB/QQ must all be identical to each other and to the original. | `gate_same.json` |
| (c) isolation | The four branches run in reverse order and then all four concurrently must give identical signatures (suffix, prompt/completion hashes, outcomes, DB hash, counters). Save/load round trip: canonical history hash and DB hashes are recomputed from the reloaded state file. | `c_isolation`, `io_check` |
| (d) budget | In every branch the live counters equal the recount of the produced trajectory (they start from the restored values; tau2's default would be 0/0). max_steps/too_many_errors terminations are consistent with the limits. The no-op reproduces the original final counters. | `d_budget` |
| (e) re-prefill | QB: B's first request carries exactly the prompt Q saw at t+1 in the original (server-returned ids, equal to the local render). BQ: Q's first request equals BB's first continuation request. The two servers are separate processes (pid, GPU, port), with per-server prefix-cache counters. | `e_reprefill`, `servers` |

Gate tasks: `fork_gate_q4_gptq_w4_d1` (retail + airline, 1 GPU), `fork_gate_same_q4_gptq_w4_d1` (b),
`fork_gate_q8_awq_w4` (telecom + retail, 2 GPUs; waits for `a6k2_q8_tel_awq_w4`). Results: §8.

## 8. Gate results (2026-09-29/30, PDT)

**Verdict: PASS.** Every check passes on real divergence states in retail, airline and telecom, including the
hooked (KV-quantized) serving configuration. No stochastic replay floor remains: every no-op is bit-exact in prompts,
messages, DB hashes and outcomes. Decision for 10-01: **protocol A (deterministic forks)**; protocol B is not needed.

| Check | Result | Evidence (`analysis/fork/gate/`) |
|---|---|---|
| Checkpoint identity | Rebuilt Q regenerates recorded decisions: q4 GPTQ-W4 c1 16/16, q8 AWQ-W4 c1 16/16, q4 KVQ INT4+H 12/12. B (BF16) 16/16 each, and the BF16 canary matches its reference, including at GPU_UTIL 0.44. Q replay of a_Q at every fork state: 20/20. | `*/gate.json` idcheck_*, states[].q_replay |
| State restoration (CPU) | The prompt rendered from the restored history equals Q's recorded server prompt at every decision: 3,492/3,492 (q4: 1,880; q8 incl. telecom: 1,612). Step/error recount consistent with all 73 max_steps / too_many_errors episodes. | `cpucheck_q4.json`, `cpucheck_q8.json` |
| (a) Q→Q no-op | 20/20 states: q4 GPTQ 8 (retail 3, airline 5), q8 AWQ 8 (retail 5, telecom 3), q4 KVQ 4. Identical prompt-id hashes for every suffix decision, suffix messages (tool calls, args, results, user replies, telecom user device calls), live and replay DB hashes (= original replay), termination (incl. too_many_errors at 10 and max_steps), reward, db_match, official_reward, final counters. | `states[].a_noop_QQ` |
| (a) B→B no-op | 10/10: q4 retail 2 + airline 2, q8 retail 2 + telecom 2, KVQ gate 2. The q4 set first failed only on `official_reward`: `a6k2_q4_null_n1` predates that trajectory field (None vs 0.0). Now recomputed from reward_info (validated 335/335 on runs that store it) and re-verdicted offline from the saved files; the old verdict is kept in gate.json. | `a_noop_BB`, `reverdict` |
| (b) same checkpoint | 6/6 states (q4 GPTQ on two servers): the B-handle shadow reproduces a_Q, and all four branches are identical to each other and to the original. Also under the hooked config (KVQ INT4+H on both handles, 4/4) and the KV16 bridge (plain BF16 B vs hooked KV16 Q: same canary `c7343b60da095480`, 4/4 equal to the BF16 original). | `q4_same_ckpt/`, `q4_kvq_same/`, `q4_kv16_bridge/` `gate_same.json` |
| (c) isolation | Reversed order and all-four-concurrent give identical signatures: 10/10 states (q4 4 airline, q8 2 retail, KVQ 1 airline). Telecom (dual control): `fork_gate_q8_telecom_iso` 3/3 states. Reversed and concurrent are identical, and so are error-budget endings (too_many_errors at 10, max_steps). Rerunning the same 3 states and 2 B→B no-ops on a fresh server pair (node005 GPUs 4,5 vs 6,7) gave 14/14 identical branches. Save/load: history and DB/device hashes recomputed from the reloaded file match for all 30 states. | `c_isolation`, `io_check` |
| (d) budget | In all 80 gate branches (20 states × 4) the live counters equal the recount of the produced trajectory; tau2's default would have restarted at 0/0. No-op final counters equal the original (telecom no-ops end in too_many_errors at exactly 10, from restored counts). | `d_budget` |
| (e) re-prefill | 20/20 applicable states. QB: B's first request (server ids, equal to the local render) is exactly the prompt Q saw at t+1 in the original. BQ: Q's first request equals BB's. Servers are distinct processes (pid/port in `servers`). | `e_reprefill` |
| Per-role config (W34) | Hooked Q gets its own server and config hash (`c5003748f3f6679d` vs BF16 `efce043e33600dcc`), cache namespace `kvq_b4_r1_kv`, coverage 36/36 decoder layers, canary distinct from BF16 (`f4e319a296f618ea`). | `logs/tasks/fork_accept_*.servers.json` (cluster), `*/gate*.json` servers |

Divergence types covered by the gate states: class act→talk, talk→act, parse_fail→act, tool_name, tool_args,
tool_count, invalid_tool (telecom: the agent calls user-side device tools).

## 9. Throughput and development cost

Measured on the gate runs (real divergence states; concurrency 8; one node's shared simulator):

| | q4 GPTQ-W4 (1 GPU, B+Q) | q8 AWQ-W4 (2 GPUs) | q4 KVQ INT4+H (1 GPU) |
|---|---|---|---|
| Search: tasks with a primary divergence | 12/20 (60%) | retail 6/8, telecom 8/8 | 11/12 |
| t* (first divergence) | 1–7 (median 4) | retail 0–4, telecom 0 (6/8) or 6 | 0–10 |
| Shadow B cost per searched decision (median / p90) | 3.5 s / 12.4 s | 2.9 s / 4.5 s | 4.2 s / 19.1 s |
| Search wall per task | 8.6 s | 3.4 s | 14.3 s |
| Branch suffix duration (median / p90) | retail 104 / 196 s, airline 79 / 120 s | retail 118 / 162 s, telecom 209 / 425 s | 68 / 215 s |
| Effective wall per branch at concurrency 8 | 18.6 s | 60 s (retail ≈ 47 s, telecom ≈ 83 s) | 20 s |
| Simulator turns per branch | 3.9 | retail 9.7, telecom 20.2 | 4.6 |
| Agent generations per branch (mean prompt) | 6.3 (7.3k tokens) | retail 17.4 (9.4k), telecom 26.1 (11.1k) | 8 (8.6k) |

Simulator capacity (sampled 120 s, 2026-09-29 22:5x PDT): 14.7 req/s total over 5 replicas at partial load. One
replica sustained 6.5 req/s at 32 running requests, and node001/004 were nearly idle. A fork task at concurrency 8 uses about
0.2–0.25 simulator turns/s, so simulator throughput does not bind at the planned scale. GPU time does.

**Development estimate** (per block = 85 tasks retail+airline; 3 branches BB/BQ/QB per state + 10% QQ no-op; divergence
rate 60–90%):
- q4 per cell and block: search ≈ 12 min, 51–77 states × 3.1 branches × 18.6 s ≈ 49–74 min, so **≈ 1.0–1.5 GPU-h**.
- q8 per cell and block: search ≈ 5 min, 64–77 states × 3.1 × 47 s ≈ 2.6–3.1 h wall on 2 GPUs, so **≈ 5.4–6.4 GPU-h**.
  Concurrency 16 should roughly halve the wall time; it is not yet measured.
- Checkpoint build per task (once per group of blocks): GPTQ q4 ≈ 6 min, AWQ q8 ≈ 10 min.
- **Total, q4 and q8 × GPTQ-W4 and AWQ-W4 × 85 tasks × 20 blocks:**
  - q4: 2 × 20 × 1.0–1.5 = 40–60 GPU-h.
  - q8: 2 × 20 × 5.4–6.4 = 216–256 GPU-h.
  - Total **≈ 260–320 GPU-h**, about 13–16 h wall on 20 GPUs.
  - Simulator demand ≈ 25k (q4) + 80k (q8) turns, about 2–3 h of the currently measured simulator capacity.
- **Telecom development option** (80 dev tasks; never the 34 holdout), per cell and block:
  - a closed-loop Q block run (≈ 2.6 GPU-h, measured `a6k2_q8_tel_awq_w4_q1`), plus its paired BF16 run (≈ 2.6 GPU-h);
  - forks: ≈ 80 states × 3.1 × 83 s ≈ 5.7 h wall on 2 GPUs ≈ 11.4 GPU-h;
  - **≈ 17 GPU-h per q8 cell-block.** q8 × 2 methods × 5 blocks ≈ 170 GPU-h.
  - q4 telecom is not measured; it is expected to be cheaper.
  - Caveat: 6/8 q8 telecom divergences are at t=0, where both B and Q call user-side device tools (`invalid_tool`; the
    q8 BF16 telecom run ends in too_many_errors in 63/80 episodes). The telecom states are therefore dominated by one
    shared failure mode.
- **Priority (review round 3):**
  1. four-branch acceptance (done);
  2. all 85 dev tasks × the preset q4/q8 cells;
  3. complete balanced blocks;
  4. reserved capacity for the 34-task telecom holdout confirmation (≈ 34 × 3.1 × 83 s ≈ 2.4 h wall per q8 cell-block on 2 GPUs, plus its closed-loop runs);
  5. extras.

  The number of blocks is set from this throughput, and the fixed 20/40 is withdrawn: with ≈ 20 GPUs for ≈ 12 h, all four cells
  get ≈ 20 blocks on q4 but only ≈ 10–12 on q8 unless concurrency 16 is validated.

## 11. Proposed development fork generator (not queued)

`scripts/a6000/make_tasks_fork_dev.py` prints the tasks and writes nothing without `--write`.
- **Cells.** Fixed by `manifests/fork/dev_blocks_v1.json` (W29a), under its completeness rule, not by favourable results.
  - Rule: per model × method, the W4 checkpoint with the most existing fresh-nonce draws; ties go to the lowest calibration draw index.
  - Result: `gptq_w4_d1` and `awq_w4` (calibration c1) on q4 and q8.
- **Blocks.** q3–q5 plus f01–f17. The complete shared-nonce blocks are the replicate units.
- **Tasks.** One task per cell × group of 5 blocks, 16 tasks in total, mode `dev`:
  - search over all 85 tasks of each block;
  - freeze all states;
  - then BB/BQ/QB, plus the QQ no-op on a 10% hash sample.
  - q4 uses 1 GPU (B+Q, GPU_UTIL 0.44); q8 uses 2 GPUs. Deps: the eval tasks producing the blocks, plus the gate task of the model.
- **Proposed additions before `--write`:**
  - order the groups so every cell completes block groups in lockstep (balanced blocks);
  - set `concurrency` 16 on q4 after one validation task;
  - optionally add telecom dev blocks for q8 once their closed-loop Q/BF16 runs exist.
- **Stop rule.** Any development QQ no-op mismatch quarantines its task's output (protocol A, §6c).

## 10. Deviations from the design (and why)

1. **Forced action as the first agent step, not appended to the history.** tau2 cannot replay a trailing tool call without results.
   The effect is identical: the forced action takes the normal step, is executed by the real environment or answered by the real
   simulator, and costs one step.
2. **Counters restored by the fork.** tau2 starts from 0/0; the design requires the original remaining budget.
3. **Scoring with the original task.** Scoring with the fork's task copy would make the gold environment replay h_t.
4. **Shadow query through the chat endpoint.** B receives the same chat request as the harness would send, not a raw
   token-id prompt, so that the harness's server-side tool parser parses its output. Identity of the input is enforced, not
   assumed: the server-returned prompt ids must equal Q's recorded ids, otherwise the task is excluded.
5. **Checkpoints rebuilt, identity by reproduction.** The original Q weights were never hashed (`--no-sha`). A rebuilt Q counts as the
   block's checkpoint only if it regenerates recorded decisions (`idcheck`) and a_Q at every fork state (`q_replay`).
6. **Per-agent nonce.** See §2.
7. **Tool-call ids.** vLLM assigns random tool-call ids that no Qwen template renders. Message comparisons exclude ids. Prompt-token
   equality shows they never reach the model.
8. **B→B no-op on a different nonce.** The paired BF16 blocks on the Q nonces (`a6k2_*_bfpair*`) had not run yet. B→B is tested on
   BF16 null runs (`a6k2_q4_null_n1`, `a6k2_q8_null_n1`) and the telecom BF16 run `a6k2_tel_det_q8_a`. The no-op property does not
   depend on the nonce.
9. **Gate (b) uses two servers of the Q checkpoint.** This tests the handle plumbing across processes. With one server both handles
   would be the same object.
10. **Telecom error budget.** User-side tool errors count against max_errors, as in tau2 (`_execute_tool_calls`). The q8 BF16 telecom
    run ends in too_many_errors in 63 of 80 episodes, mostly from the agent calling user-side tools. The error budget is therefore often
    binding in telecom forks and is part of the restored state.

## 12. Difficulty moderators: exploratory on development, draft pre-registration for the telecom holdout (W52)

Development analysis: `analysis/fork/analyze_difficulty.py`. Everything in it is **exploratory**, because the moderators
were chosen after the development data was seen. Its effects, units and bootstrap are those of analyze_dev.py.

**Draft moderator list for the telecom holdout** (to be frozen in PREREG_FORK_CONFIRM.md before any holdout outcome, 10-03).
Cut points and bins are fixed on the telecom development data, never on the holdout.

| id | moderator | definition | test |
|---|---|---|---|
| M1 (primary moderator) | remaining horizon h | n_decisions(Q episode) − t* at the primary state | slope of C = L_BQ − L_BB on h (pp per 10 decisions, weighted LS under the hierarchical bootstrap). One-sided H1: slope > 0, i.e. harm from the Q continuation compounds with the remaining horizon. α = 0.05. |
| M2 | BF16 task difficulty | BF16 official success rate of the task over the holdout's paired BF16 blocks | G_all and C within bins {0}, (0, 0.5], (0.5, 1]; trend across bins |
| M3 | persona | PERSONA Hard / None / Easy from the task id | G_all per level; Hard vs None contrast |
| M4 | task length | mean agent decisions of the task's BF16 episodes | tertiles with cut points frozen from telecom dev |
| M5 | fault load | issue type (mms / mobile_data / service) and number of injected faults (from the task id) | G_all per level |

- M2–M5 are secondary, with Holm correction across them. All strata and point estimates are reported whatever their significance.
- Few holdout events mean limited evidence for a mechanism, not its absence (review round 3).
- The moderator analyses are nested within the primary G_all analysis. They do not replace it.

## 13. Pivot-time restoration (W55): arm selection rule, fixed before any pivot-arm outcome

**Step 2: which modules flip the action at the pivot.**
- **States:** 150 frozen primary states per cell, hash-sampled (`sha256("pivot-arms-v1"|state_id)`). Cells are q4
  GPTQ-W4 c1, q8 AWQ-W4 c1, q4 GPTQ-W3 c1 and q8 GPTQ-W3 c1.
- **Arms:** each serves as the Q handle and makes one decision from the identical prompt (prompt ids checked against Q's
  record):
  - controls `none` (= Q) and `all` (= BF16);
  - structured `early`, `middle`, `late`, `attn`, `mlp`;
  - byte-matched random `rand_third_s1`, `rand_attn_s1`, `rand_mlp_s1`;
  - `resid α=0.5`;
  - in the W3 cells, also the eight `restore_recal` arms (W54).
- **Endpoint:** the action reversion rate r_B(arm) = P(arm's full action semantically equals a_B). P(equals a_Q) and
  P(neither) are reported alongside. Comparison uses the same `compare_actions` as the search.

**Selection rule for step 3** (uses only step-2 action data, never outcomes):
- **Candidates:** the structured arms early, middle, late, attn and mlp, plain and recal. Each is paired with its byte-matched random
  control (seed 1): early/middle/late with rand_third_s1, attn with rand_attn_s1, mlp with rand_mlp_s1. Recal arms are paired
  with the recal random of the same set. resid α=0.5 is a dose reference, not a candidate.
- **Statistic:** Δ = r_B(arm) − r_B(matched random), paired on the same states. It is pooled over the two GPTQ-W3 cells
  (q4, q8) with equal weight, using the hierarchical bootstrap (tasks, then blocks within task; B = 2000; seed 20261001).
- **Eligible** if the one-sided 95% lower bound of Δ is > 0 **and** the point Δ ≥ 5 pp.
- **Chosen:** the eligible arm with the largest point Δ. A second eligible arm is added if its lower bound is also > 0,
  at most 2 in total. Ties go to fewer restored bytes. The byte-matched random control of each chosen arm is run with it.
- **If none is eligible,** step 3 is not queued, and the result is reported as "no module set flips the pivot action above
  its byte-matched control".

**Step 3 (queued only if step 2 selects an arm):** the branch "R at t*, then Q", on the GPTQ-W3 stress-fork states of q4 and q8.
It is compared with QQ (G_R = Y_RQ − Y_QQ) and with BQ (the share of the full-BF16-at-pivot effect it recovers).
