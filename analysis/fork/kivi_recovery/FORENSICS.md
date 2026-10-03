# q8 new-method panel: forensics of errored fork-branch arms (kivi_k2v2, kivi_k4v4, spinquant_w4a4 f01)

Read-only forensics, 2026-10-03. No queue entry, run directory or existing file was changed, and no GPU work was run. Machine-readable record: `analysis/fork/kivi_recovery/failed_arms.json` (31 arms; evidence lines quoted with path and line, all 114 re-checked against the files with `sed -n`).

## TL;DR

| cell | block(s) | errored arms | service_failure_verified | timeout_cause_not_established | other | server the failing call went to |
|---|---|---|---|---|---|---|
| kivi_k2v2 | f01 (1), f02 (4), f03 (5) | 10 | 0 | **10** | 0 | agent Q server (inferred by elimination) |
| kivi_k4v4 | f01 | 12 | **12** | 0 | 0 | user simulator node004:8000 (verified down) |
| spinquant_w4a4 | f01 | 9 | 0 | 0 | **9** | user simulator node005:8000 (inferred by elimination; queue backlog verified) |
| **total** | | **31** | 12 | 10 | 9 | |

- **kivi_k4v4 f01 (12 arms, `[Errno 111] Connection refused`).** The failing calls went to the user simulator at node004:8000, which was not listening from 21:28:44 to 21:33:41 PDT on 10-02.
  - The node004 runner (job 49862) found nothing left in its queue and exited at 21:28:43, and that shut its simulator down.
  - The node006 fork task was still using that simulator.
  - All 12 refusals fall between 21:29:18 and 21:33:40.
  - The agent servers on node006 (B :8105, Q :8205) served requests throughout the outage.
- **kivi_k2v2 (10 arms, `litellm.Timeout`).** By elimination, the failing call was on the KIVI Q agent server. The cause of the timeout is not established.
  - The Q server never crashed, restarted or refused: one API pid per task, no ERROR, OOM, CUDA or Preemptions lines before the end-of-task shutdown (the only ERROR lines are the teardown's EngineDeadError after the task finished), and 0 non-200 responses.
  - Each final error is the 4th consecutive 600 s timeout of one call.
  - In 9 of 10 arms, the user simulator had 0 running and 0 waiting requests inside the final attempt's window.
  - Measured on the Q server: the per-request decode rate of successful Q calls was a median of 0.94 to 1.43 tok/s. With up to 8 requests running, aggregate generation was 3 to 10 tok/s.
  - In the same tasks, 9 successful Q calls (k2v2 and k4v4) needed at least one timed-out attempt before they succeeded. Their completions were 123 to 1016 tokens long.
  - The timed-out completion's length is not recorded.
- **spinquant_w4a4 f01 (9 arms, `litellm.Timeout`, including 2 QB arms).** The failing calls were on the node005 user simulator, not on Q or B.
  - In every arm, the agent server the arm uses (Q for BQ/QQ, B for QB) was idle while the call was in flight. Meanwhile the simulator had a median of 83 to 92 requests waiting, with KV usage peaking at 94 to 99%.
  - In the same task, 8 successful user-sim calls took 1124 to 2333 s. No successful Q or B call took more than 88 s.
  - The simulator neither crashed nor refused connections, so the class is `other` (user-simulator overload).
  - **This contradicts protocol E1.5**, which labels spinquant_w4a4 f01's timeouts "Q-server timeout, cause not established" and says all such arms are BQ/QQ.
- **The timeout error text does not say whether it was a connect or a read timeout.** "Connection timed out after 600.0 seconds." is litellm's fixed message for any `httpx.TimeoutException`: connect, read, write or pool (`litellm/llms/custom_httpx/http_handler.py:1031-1036`). The 600 s value applies to all four phases (`httpx.Timeout(timeout=600.0)`).
  - Inference: a 600 s connect timeout to a listening local port is implausible, so these are most likely read timeouts.

## Method (what each claim rests on)

1. **Arm-to-error mapping.** `run_branch` returns `{tag, branch, error, n_decisions, probe}` on exception (`cloq/fork.py:585`, `:602`). The arms of one state run sequentially in the order BB, BQ, QB, QQ (`fork_driver.bank_u`, `scripts/a6000/fork_driver.py:751-755`).
   - Each tau2 `ERROR` line in the task log was matched to exactly one arm by bracketing:
     - from the end of the previous arm (last suffix timestamp);
     - to the start of the next arm (first suffix timestamp), or to the branch file's mtime.
   - All 31 matches are unique. The error stamp is within 1.3 s of the next arm's start or of the file mtime (0.25 s or less for 30 of the 31 arms; 1.22 s for k2v2 f02 e553 BQ).
2. **Four attempts per error.** tau2 `generate` sets `num_retries=3` (`third_party/tau2-bench/src/tau2/config.py:40`, `llm_utils.py:379-380`). litellm retries a Timeout, APIError or APIConnectionError through `completion_with_retries` with `stop_after_attempt(3)` and no wait (`litellm/utils.py:1711-1720`, `litellm/main.py:4420-4449`). That gives 1 + 3 attempts to the same `api_base`.
   - litellm prints one "Give Feedback" banner per failed attempt. The banner count in each task log reconciles exactly (residual 0) for every kivi task:
     - 4 × (errored calls), plus
     - ⌊duration/600⌋ for each successful call whose `generation_time_seconds` (tau2 measures across retries) exceeds 600 s.
   - spinquant_w4a4 f01 has a residual of 4 unattributed failed attempts (see open questions).
   - A timeout error therefore marks a call that was in flight for at least 2,400 s before T. The final attempt [T−600 s, T] is certainly a 600 s timeout.
3. **Server attribution by elimination.** After the forced first action, an arm XY calls only server Y and the user simulator. vLLM logs a stats line every 10 s while not idle; each line gives Running and Waiting.
   - A snapshot with `Running: 0 reqs, Waiting: 0 reqs` on server S during a call's lifetime means the call was not queued or running in S's engine at that moment. The same call goes to the same server on every retry.
   - Inference caveat: this assumes the request was not held outside the engine, for example in the HTTP layer.
   - The evidence used is preferably inside the final attempt. Three arms rely on an earlier attempt, flagged in the table:
     - k2v2 f02 e553 BQ;
     - spinquant 9749 QQ and f01a QQ. For these two, the final attempt has zero Q throughput (no stats lines) and Q's GPU at 0% in gpumon.
4. **Times.** All logs are in America/Los_Angeles (PDT, UTC−7). `window_utc` is [T−2400 s, T] for timeouts (estimated start of the first attempt; true start ≤ this). For refusals it is [T−1 s, T], because refusals are immediate.

## Per-arm table

The server column notes whether the elimination evidence lies in the final attempt or only in an earlier one.

| cell block | state_key | arm | n_dec | error | error time PDT (UTC) | server | class | key evidence (path:line) |
|---|---|---|---|---|---|---|---|---|
| kivi_k2v2 f01 | 1bdc433905484e8d | QQ | 5 | Timeout | 10-02 16:43:09 (23:43:09Z) | agent Q (inferred) (final attempt) | timeout_cause_not_established | tasks/nmp_tau2_q8_kivi_k2v2_f01.log:19; sim idle logs/sim_node004_49862.log:51186; Q busy tasks/nmp_tau2_q8_kivi_k2v2_f01.Q.vllm.log:3203 |
| kivi_k2v2 f02 | 02dde73dfe90f6f6 | QQ | 12 | Timeout | 10-02 14:58:46 (21:58:46Z) | agent Q (inferred) (final attempt) | timeout_cause_not_established | tasks/nmp_tau2_q8_kivi_k2v2_f02.log:19; sim idle logs/sim_node005_49863.log:33301; Q busy tasks/nmp_tau2_q8_kivi_k2v2_f02.Q.vllm.log:1671 |
| kivi_k2v2 f02 | 21f3a2013895739f | BQ | 3 | Timeout | 10-02 15:29:27 (22:29:27Z) | agent Q (inferred) (final attempt) | timeout_cause_not_established | tasks/nmp_tau2_q8_kivi_k2v2_f02.log:36; sim idle logs/sim_node005_49863.log:34318; Q busy tasks/nmp_tau2_q8_kivi_k2v2_f02.Q.vllm.log:2016 |
| kivi_k2v2 f02 | e553e7972e96416c | BQ | 5 | Timeout | 10-02 16:02:38 (23:02:38Z) | agent Q (inferred) (earlier attempt only) | timeout_cause_not_established | tasks/nmp_tau2_q8_kivi_k2v2_f02.log:53; sim idle logs/sim_node005_49863.log:36294; Q busy tasks/nmp_tau2_q8_kivi_k2v2_f02.Q.vllm.log:2373 |
| kivi_k2v2 f02 | 0f51e0c84a65cf7f | BQ | 15 | Timeout | 10-02 16:37:45 (23:37:45Z) | agent Q (inferred) (final attempt) | timeout_cause_not_established | tasks/nmp_tau2_q8_kivi_k2v2_f02.log:74; sim idle logs/sim_node005_49863.log:39112; Q busy tasks/nmp_tau2_q8_kivi_k2v2_f02.Q.vllm.log:2727 |
| kivi_k2v2 f03 | dbdc689a3751d9dd | QQ | 5 | Timeout | 10-02 14:40:08 (21:40:08Z) | agent Q (inferred) (final attempt) | timeout_cause_not_established | tasks/nmp_tau2_q8_kivi_k2v2_f03.log:19; sim idle logs/sim_node005_49863.log:32588; Q busy tasks/nmp_tau2_q8_kivi_k2v2_f03.Q.vllm.log:1174 |
| kivi_k2v2 f03 | f2b0916c7aa6d021 | BQ | 26 | Timeout | 10-02 16:44:11 (23:44:11Z) | agent Q (inferred) (final attempt) | timeout_cause_not_established | tasks/nmp_tau2_q8_kivi_k2v2_f03.log:44; sim idle logs/sim_node005_49863.log:39261; Q busy tasks/nmp_tau2_q8_kivi_k2v2_f03.Q.vllm.log:2809 |
| kivi_k2v2 f03 | 01a17956873df0ef | QQ | 31 | Timeout | 10-02 16:59:50 (23:59:50Z) | agent Q (inferred) (final attempt) | timeout_cause_not_established | tasks/nmp_tau2_q8_kivi_k2v2_f03.log:61; sim idle logs/sim_node005_49863.log:40353; Q busy tasks/nmp_tau2_q8_kivi_k2v2_f03.Q.vllm.log:2967 |
| kivi_k2v2 f03 | b6a3454a4e6f976a | QQ | 11 | Timeout | 10-02 17:15:31 (00:15:31Z) | agent Q (inferred) (final attempt) | timeout_cause_not_established | tasks/nmp_tau2_q8_kivi_k2v2_f03.log:78; sim idle logs/sim_node005_49863.log:41778; Q busy tasks/nmp_tau2_q8_kivi_k2v2_f03.Q.vllm.log:3116 |
| kivi_k2v2 f03 | f2b0916c7aa6d021 | QQ | 20 | Timeout | 10-02 18:08:17 (01:08:17Z) | agent Q (inferred) (final attempt) | timeout_cause_not_established | tasks/nmp_tau2_q8_kivi_k2v2_f03.log:95; sim idle logs/sim_node005_49863.log:44709; Q busy tasks/nmp_tau2_q8_kivi_k2v2_f03.Q.vllm.log:3639 |
| kivi_k4v4 f01 | 3b1c207abdf8ef45 | QQ | 68 | ConnRefused | 10-02 21:29:18 (04:29:18Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:19; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | 87c2005e50647c84 | QQ | 10 | ConnRefused | 10-02 21:29:26 (04:29:26Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:36; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | dcd3f47a56a2faba | QQ | 10 | ConnRefused | 10-02 21:29:40 (04:29:40Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:53; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | 9749f30f7ffd3c41 | BB | 2 | ConnRefused | 10-02 21:30:19 (04:30:19Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:70; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | 22e5640e91897669 | QQ | 25 | ConnRefused | 10-02 21:30:36 (04:30:36Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:87; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | 961ad5dfd79a5dee | QQ | 1 | ConnRefused | 10-02 21:31:00 (04:31:00Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:104; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | 9749f30f7ffd3c41 | QQ | 2 | ConnRefused | 10-02 21:31:13 (04:31:13Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:121; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | 95d6b21e8fc7af2b | BB | 1 | ConnRefused | 10-02 21:31:29 (04:31:29Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:138; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | 95d6b21e8fc7af2b | BQ | 1 | ConnRefused | 10-02 21:31:29 (04:31:29Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:155; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | 95d6b21e8fc7af2b | QB | 2 | ConnRefused | 10-02 21:31:32 (04:31:32Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:172; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | 95d6b21e8fc7af2b | QQ | 2 | ConnRefused | 10-02 21:32:27 (04:32:27Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:189; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| kivi_k4v4 f01 | 9a48c111a1211c17 | QQ | 14 | ConnRefused | 10-02 21:33:40 (04:33:40Z) | user sim node004:8000 | service_failure_verified | tasks/nmp_tau2_q8_kivi_k4v4_f01.log:206; logs/sim_node004_49862.log:63116 (shutdown 21:28:44); logs/sim_node004_49885.log:167 (listening 21:33:41) |
| spinquant_w4a4 f01 | 9749f30f7ffd3c41 | BQ | 29 | Timeout | 10-03 08:06:44 (15:06:44Z) | user sim node005:8000 (inferred) (final attempt) | other | tasks/nmp_tau2_q8_spinquant_w4a4_f01.log:120; Q idle tasks/nmp_tau2_q8_spinquant_w4a4_f01.Q.vllm.log:2845; sim backlog logs/sim_node005_49863.log:69439 |
| spinquant_w4a4 f01 | 197f61e9d1573be3 | QB | 4 | Timeout | 10-03 08:07:11 (15:07:11Z) | user sim node005:8000 (inferred) (final attempt) | other | tasks/nmp_tau2_q8_spinquant_w4a4_f01.log:125; B idle tasks/nmp_tau2_q8_spinquant_w4a4_f01.B.vllm.log:1098; sim backlog logs/sim_node005_49863.log:69443 |
| spinquant_w4a4 f01 | a42e6f98f2baa960 | QQ | 80 | Timeout | 10-03 08:13:02 (15:13:02Z) | user sim node005:8000 (inferred) (final attempt) | other | tasks/nmp_tau2_q8_spinquant_w4a4_f01.log:138; Q idle tasks/nmp_tau2_q8_spinquant_w4a4_f01.Q.vllm.log:2845; sim backlog logs/sim_node005_49863.log:69520 |
| spinquant_w4a4 f01 | 33b049d3a313a14f | QQ | 3 | Timeout | 10-03 08:22:53 (15:22:53Z) | user sim node005:8000 (inferred) (final attempt) | other | tasks/nmp_tau2_q8_spinquant_w4a4_f01.log:155; Q idle tasks/nmp_tau2_q8_spinquant_w4a4_f01.Q.vllm.log:2850; sim backlog logs/sim_node005_49863.log:69655 |
| spinquant_w4a4 f01 | 2b7e8183406b2144 | QB | 5 | Timeout | 10-03 09:30:48 (16:30:48Z) | user sim node005:8000 (inferred) (final attempt) | other | tasks/nmp_tau2_q8_spinquant_w4a4_f01.log:196; B idle tasks/nmp_tau2_q8_spinquant_w4a4_f01.B.vllm.log:1176; sim backlog logs/sim_node005_49863.log:70784 |
| spinquant_w4a4 f01 | 1bdc433905484e8d | QQ | 21 | Timeout | 10-03 10:02:02 (17:02:02Z) | user sim node005:8000 (inferred) (final attempt) | other | tasks/nmp_tau2_q8_spinquant_w4a4_f01.log:225; Q idle tasks/nmp_tau2_q8_spinquant_w4a4_f01.Q.vllm.log:3057; sim backlog logs/sim_node005_49863.log:71297 |
| spinquant_w4a4 f01 | 27b52ac1d2cc9ec6 | QQ | 2 | Timeout | 10-03 10:53:37 (17:53:37Z) | user sim node005:8000 (inferred) (final attempt) | other | tasks/nmp_tau2_q8_spinquant_w4a4_f01.log:250; Q idle tasks/nmp_tau2_q8_spinquant_w4a4_f01.Q.vllm.log:3106; sim backlog logs/sim_node005_49863.log:72089 |
| spinquant_w4a4 f01 | 9749f30f7ffd3c41 | QQ | 11 | Timeout | 10-03 11:04:14 (18:04:14Z) | user sim node005:8000 (inferred) (earlier attempt only) | other | tasks/nmp_tau2_q8_spinquant_w4a4_f01.log:263; Q idle tasks/nmp_tau2_q8_spinquant_w4a4_f01.Q.vllm.log:3106; sim backlog logs/sim_node005_49863.log:72096; GPU5 0% gpumon/node005.jsonl:212847 |
| spinquant_w4a4 f01 | f01a1f21e0c452e7 | QQ | 3 | Timeout | 10-03 11:25:02 (18:25:02Z) | user sim node005:8000 (inferred) (earlier attempt only) | other | tasks/nmp_tau2_q8_spinquant_w4a4_f01.log:276; Q idle tasks/nmp_tau2_q8_spinquant_w4a4_f01.Q.vllm.log:3107; sim backlog logs/sim_node005_49863.log:72110; GPU5 0% gpumon/node005.jsonl:212888 |

Notes on specific arms:
- **Reused arms inherit the missing value** (`arm_source` `reuse=XX`):
  - kivi_k4v4 f01: BQ of 22e5, 3b1c, 87c2, 961a, 9749, 9a48 and dcd3; QB of 9749;
  - kivi_k2v2 f03: BQ of 01a1;
  - spinquant f01: BQ of a42e.
- **kivi_k4v4 f01 95d6 BB/BQ and 961a QQ** have `n_decisions` = 1 and a text forced action (a_B or a_Q). In tau2 a text agent message is followed by a user turn, so the refused call was the user-simulator call. This is direct, not by elimination.
- **kivi_k4v4 f01 user simulator.** `nmp_tau2_q8_kivi_k4v4_f01.servers.json:139` sets `user_base` to `http://node004:8000/v1`. In gpumon, node004 has no port 8000 and GPU0 at 2 MiB at 21:31:43 and 21:32:13 (`gpumon/node004.jsonl:217774-217775`). The next runner (job 49885) reports the simulator up at 21:33:44 (`logs/node_node004_49885.out:11`).
- **kivi_k2v2 e553 BQ.** The user simulator has an idle snapshot only in attempt 3 (15:50:27). During its final attempt, 93 user calls recorded by k2v2 f02 and f03 (same node005 simulator) completed in ≤ 17 s each.

## Serving configuration relevant to timeouts

The same for all tasks below:
- **Driver:** `bank_u` with `concurrency` 8, so up to 8 states run in parallel and each state runs its arms sequentially. That gives at most 8 concurrent agent calls (split across B and Q) and at most 8 concurrent user calls per task.
- **Agent requests:** `max_tokens` 1024, `timeout` 600, temperature 0.
- **User requests:** `max_tokens` 512, `timeout` 600.
  - Source: `runs/a6k2_q8_bfpair_f0{1,2,3}/{airline,retail}/config.json`.
- **Retries:** `num_retries` 3 (tau2 default), so 4 attempts and up to about 2,400 s per call.
- **vLLM:** 0.29.0, `max_model_len` 33792, `gpu_memory_utilization` 0.90, chunked prefill and prefix caching on, `VLLM_BATCH_INVARIANT=1`.
- **`max_num_seqs` / `max_num_batched_tokens`:** not passed (`scripts/a6000/serve.sh:12-17`), so vLLM defaults apply. On a 48 GB A6000 those are 256 / 2048 (`vllm/engine/arg_utils.py:2718-2727`), consistent with `compile_ranges_endpoints [2048]` in each Q log's engine-config line.
  - The binding limit is the driver's concurrency of 8; the max_num_seqs default (256) is not binding.
- **Preemptions:** no `Preemptions` lines in any Q, B or user-simulator log examined.

| task | host / job | Q server (GPU:port) | Q method | KV cache (tokens) | user_base | task seconds |
|---|---|---|---|---|---|---|
| kivi_k2v2 f01 | node008 / 49869 | 5:8205 | Qwen3-8B BF16 + KIVI K2V2 g32 r128 (python hooks) | 173,760 | node004:8000 (remote) | 16,967 |
| kivi_k2v2 f02 | node001 / 49866 | 5:8205 | same | 173,760 | node005:8000 (remote) | 17,592 |
| kivi_k2v2 f03 | node005 / 49863 | 7:8207 | same | 193,312 | 127.0.0.1:8000 (node005) | 26,370 |
| kivi_k4v4 f01 | node006 / 49731 | 5:8205 | Qwen3-8B BF16 + KIVI K4V4 g32 r128 | 193,312 | node004:8000 (remote) | 7,259 |
| spinquant_w4a4 f01 | node005 / 49863 | 5:8205 | SpinQuant W4 (GPTQ, fake-quant bf16) + A4 hooks | 172,000 | 127.0.0.1:8000 (node005) | 25,832 |

## Throughput around the failing calls versus the rest of the task

"In" means successful requests (other arms of the same task) whose completion timestamp falls inside some failing call's [T−2400 s, T] window. "Out" means the rest of the task.
- Per-request tok/s = completion tokens / tau2 `generation_time_seconds`. That time includes queueing and prefill, and spans retries.
- User-call seconds = user-message timestamp minus the previous message's timestamp. This is an approximation.
- Aggregate Q generation = median of the non-zero "Avg generation throughput" over the 10 s vLLM stats lines.
- kivi_k4v4 f01 has no "in" columns: its refusals were immediate.

| task | Q tok/s per request, in: med/p90/max (n) | Q tok/s, out | Q call s, in: med/p90/max | Q call s, out | Q aggregate gen tok/s in / out | Q running (median) in / out | user call s, in | user call s, out | B tok/s per request (out) |
|---|---|---|---|---|---|---|---|---|---|
| kivi_k2v2 f01 | 1.36/1.68/2.35 (283) | 1.43/2.06/4.02 (1595) | 33/90/497 | 36/82/1177 | 9.6 / 7.4 | 7 / 6 | 9.0/37.9/71.6 (140) | 7.8/33.3/84.9 | 13.9/15.4/15.9 |
| kivi_k2v2 f02 | 0.94/1.12/1.26 (582) | 1.40/1.86/2.19 (887) | 55/172/499 | 45/123/1200 | 7.2 / 8.5 | 8 / 7 | 3.3/8.4/17.0 (430) | 2.0/6.2/25.2 | 13.6/15.5/15.8 |
| kivi_k2v2 f03 | 0.95/1.53/1.90 (613) | 1.21/2.00/2.45 (1036) | 52/150/917 | 41/139/395 | 7.0 / 3.4 | 7 / 5 | 2.7/7.3/17.9 (462) | 2.8/7.3/103.7 | 13.9/15.4/15.9 |
| kivi_k4v4 f01 | - | 1.37/2.08/3.33 (785) | - | 35/88/1004 | - / 8.0 | - / 7 | - | 3.3/8.2/26.6 | 14.0/15.0/15.7 |
| spinquant_w4a4 f01 | 13.4/13.8/14.0 (52) | 11.5/13.1/14.0 (1609) | 5.6/13.1/32.8 | 4.1/11.1/88.2 | 8.7 / 13.4 | 0 / 1 | **561/597/2328 (53)** | 4.5/201/2333 | 13.9/15.3/16.0 |

Facts drawn from these numbers:
- **kivi Q server.** Per-request decode on Q is roughly 10× slower than B (about 1 to 1.4 tok/s versus about 14 tok/s).
  - A 1024-token completion needs ≥ 1.71 tok/s to finish within 600 s. At the median in-window rate (0.94 to 1.36 tok/s) the limit is reached at roughly 560 to 820 completion tokens. Prefill and queueing count against the same 600 s.
  - In-window per-request rate was lower than out-of-window in f02 (0.94 vs 1.40) and f03 (0.95 vs 1.21), and similar in f01 (1.36 vs 1.43).
- **Successful Q calls with at least one timed-out attempt.** There are 9 across the kivi tasks:

  | task | state | arm | total s | completion tokens | prompt tokens |
  |---|---|---|---|---|---|
  | k2v2 f01 | 4bba | QQ | 1177 | 1016 | 8516 |
  | k2v2 f02 | e553 | QQ | 1200 | 369 | 7606 |
  | k2v2 f03 | 8e15 | QQ | 917 | 294 | 6927 |
  | k2v2 f03 | a2d1 | QQ | 895 | 269 | 14422 |
  | k4v4 f01 | 4bba | QQ | 1004 | 799 | 7037 |
  | k4v4 f03 | 2d24 | QQ | 1687 | 740 | 8696 |
  | k4v4 f03 | 54f5 | QQ | 938 | 247 | 7387 |
  | k4v4 f03 | a2d1 | QQ | 809 | 133 | 8898 |
  | k4v4 f03 | f2b0 | QQ | 770 | 123 | 14817 |

  - Six of the nine had ≤ 369 completion tokens. So a 600 s Q timeout occurs for completions far below max_tokens; a near-max_tokens completion is not required.
  - No user-simulator call in any kivi task exceeded 600 s. The maximum was 530 s, in k4v4 f03.
- **spinquant_w4a4 f01.** Per-request rate on Q and B was 11 to 14 tok/s with calls ≤ 88 s. User calls inside the windows took a median of 561 s.
  - The node005 simulator's hourly median Waiting rose from 0 to 1 on 10-02 afternoon to 38 at 05:00, then 59, 83, 86, 87, 84 and 80 from 06:00 to 11:00 on 10-03.
  - Over the same period KV usage was 97.7 to 99.7% (hourly max). Aggregate generation was 22 and 16 tok/s in the 05:00 and 06:00 hours, then 8 to 11 tok/s from 07:00 to 11:00, against 28 to 77 tok/s (hourly means) between 12:00 and 18:00 on 10-02.

## Open questions

1. **kivi_k2v2: length of the timed-out Q completions.** The decision record is written only after a response, so it is unknown.
   - With batch-invariant temperature-0 decoding, each retry recomputes the same completion. Retries succeeded for 9 calls once load dropped (above); in the 10 errored calls, all 4 attempts timed out.
   - A deterministic replay of the 10 arm prefixes with streaming would measure the completion length and per-token timing. That requires GPU work and was not run.
2. **Does vLLM abort the server-side request when litellm's client times out?** If not, abandoned requests keep decoding on Q and the retries compete with them. With request logging off, the vLLM logs cannot show this.
3. **spinquant_w4a4 f01: what saturated the node005 simulator?** Every client in the backlog window was local: 1,857 POSTs from 127.0.0.1 between 07:00 and 11:30 (`logs/sim_node005_49863.log:68537-72803`), of which 40 got `400 Bad Request`.
   - node005 then ran:
     - the spinquant fork;
     - `pert_q8_gptq_w3_resid_a2_q345` and `pert_q8_rtn_w3_resid_a2_q345`, running since 10-02;
     - `a6k2_q4_gauss3_s1_redo` and `a6k2_q4_gauss3_s2_redo`, claimed 04:40:13 on 10-03 (`logs/node_node005_49863.out:131-132`).
   - The backlog onset at about 05:00 follows the two redo tasks. Stats lines such as `logs/sim_node005_49863.log:72110` show prompt throughput of 6,777 tok/s at a 1.0% prefix-cache hit rate, which suggests long uncached prompts. Both points are inference; per-client load was not measured.
4. **spinquant_w4a4 f01: 4 failed attempts are not attributed** (55 banners = 36 for 9 errored calls + 15 from successful user calls > 600 s + 4). They may be earlier calls inside the errored arms, whose messages are not stored.
5. **kivi_k4v4 f01: was anyone else using node004:8000?** The node004 runner tears its simulator down when its own queue is empty, even while another node's task uses it as `user_base`.
   - In the last minutes before the shutdown (`logs/sim_node004_49862.log:62900-63116`), the node004 simulator's only remote client was 10.141.0.6 (node006): 5 POSTs, against 199 local ones.
   - No other task's logs were checked for refusals in 21:28:44-21:33:41.
6. **Protocol text to revisit (main session).**
   - E1.5 says "12 `Timeout` arms (kivi_k2v2 f01 to f03: 10; spinquant_w4a4 f01: 2) ... All 12 are Q-controller arms". spinquant_w4a4 f01 now has 9 timeout arms, 2 of them QB, and the evidence places them on the user simulator, not on Q.
   - W100v calls the kivi_k4v4 f01 arms infrastructure. The evidence verifies that: the user simulator was down.

## Evidence index

- **Branch records:** `analysis/fork/newmethod/tau2/q8_{kivi_k2v2,kivi_k4v4,spinquant_w4a4}/f0x/branches/<state_key>.json` and `bank_rows.jsonl`.
- **Task logs:** `/data/ziyangs/cloq_work/logs/tasks/nmp_tau2_q8_{kivi_k2v2_f01,kivi_k2v2_f02,kivi_k2v2_f03,kivi_k4v4_f01,spinquant_w4a4_f01}.{log,Q.vllm.log,B.vllm.log,servers.json}`. The `.worker.log` files are empty.
- **User simulators:** `/data/ziyangs/cloq_work/logs/sim_node004_49862.log`, `sim_node004_49885.log`, `sim_node005_49863.log`.
- **Node runners:** `/data/ziyangs/cloq_work/logs/node_node004_49862.out`, `node_node004_49885.out`, `node_node005_49863.out`.
- **gpumon:** `/data/ziyangs/cloq_work/gpumon/node004.jsonl`, `node005.jsonl`. These scrape ports 8000-8010 only, so the fork B/Q servers on 81xx/82xx appear only as GPU util and memory.
- **Queue records:** `/data/ziyangs/cloq_work/queue/done/nmp_tau2_q8_{kivi_k2v2_f0[1-3],kivi_k4v4_f01,spinquant_w4a4_f01}.json`.
- **Code read:**
  - `cloq/fork.py` (`run_branch`, `ForkAgent`);
  - `cloq/agent.py:107-190`;
  - `scripts/a6000/fork_driver.py` (`bank_u`);
  - `third_party/tau2-bench/src/tau2/utils/llm_utils.py:355-430`;
  - litellm 1.82.6 (`utils.py`, `main.py`, `llms/custom_httpx/http_handler.py`);
  - vLLM 0.29.0 (`v1/metrics/loggers.py:241-311`, `engine/arg_utils.py:2670-2760`).
