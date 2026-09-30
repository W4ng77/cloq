**TL;DR** Protocol `fork-v1` for the same-state 2×2 fork (EXTERNAL_REVIEW_GPT61_20260930.md §E). A fork state is
Q's full saved history before one of its decisions. tau2 rebuilds the DB, the telecom device state and the
user-simulator state from that history by strict replay. The current action is forced (a_B or a_Q), and the continuation
runs on a separate vLLM server per checkpoint, with the step and error budget restored. Code: `cloq/fork.py`,
`scripts/a6000/fork_driver.py`, worker kind `fork`. Gate status and numbers: §7–§9 (filled from `analysis/fork/gate/`).

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

## 8. Gate results

(pending)

## 9. Throughput and development cost

(pending)

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
