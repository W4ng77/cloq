# SIMCTRL-P: Bank P four-arm simulator control (W97; GPT-6.1 review 7)

**TL;DR.** We re-run all four arms (BB, BQ, QB, QQ) of 80 frozen first-tool-structure-divergence states (Bank P), 20 in
each core W4 cell (q4/q8 × GPTQ-W4 d1/AWQ-W4). Each arm runs R = 5 times. The only change is the user simulator after
the fork state: it becomes Sonnet 5.5, answered by one clean headless `claude -p` call per user turn through the
integrity-checked file relay `simrelay-v2`. The states were frozen before any run, by an outcome-blind rule. That rule
uses stratified proportional allocation and sha256 order. The states come in two batches of 40; batch 2 is launched on
throughput or time grounds only.
- **What it shows.** Whether the W93 sign/size picture of G, H, F and G − H on these states survives a change of simulator.
- **What it cannot show.** It cannot confirm or refute few-pp effects (n = 80).
- **Not allowed.** The per-state four binary outcomes must not be summarised as an off-diagonal share comparable to 26.9%.
- **Status.** Built, frozen and validated (CPU dry run plus a real-CLI relay test). Nothing is queued yet; the main
  session queues the tasks after review.
- **Evidence:**
  - `manifests/fork/simctrl_p_v1.json` (sha256 `fa3dbf366b8584d837cc5231378e683f4a39615b024b662e5bbbb9d79e5a48a3`);
  - `scripts/a6000/make_tasks_simctrl_p.py`, `scripts/a6000/simrelay_cli.py`;
  - `scripts/a6000/fork_driver.py` (mode `simctrl_p`), `cloq/user_llm.py` (simrelay-v2);
  - `analysis/fork/simctrl_p/{dry/,validation/relay_test_20261001.json,estimate.json}`.

## 1. Design

| | |
|---|---|
| States | 80 Bank P states: the first tool-structure divergence of the dev-fork search (text-only differences are skipped by the search), frozen in `manifests/fork/simctrl_p_v1.json` |
| Cells | q4 GPTQ-W4 d1, q4 AWQ-W4, q8 GPTQ-W4 d1, q8 AWQ-W4 (20 states each) |
| Arms | XY = a_X forced at h_t, then controller Y from the next step (B = BF16, Q = the cell). a_B and a_Q are the actions recorded in the frozen dev state file. |
| Replicates | R = 5 independent runs per arm and state; keyed `<arm>#<r>`; all 20 branches of a state run concurrently |
| Simulator | Only the user simulator after h_t changes. The new one is Sonnet 5.5 via `scripts/a6000/simrelay_cli.py`. tau2's own UserSimulator still builds the system prompt (guidelines + task instructions), the flipped history and the stop logic. |
| State checks | Each check failure makes the state missing (never imputed). Checks: the frozen state file's sha; the state rebuilt from the trajectory has an equal state id, history sha and prompt-id sha; the a_B/a_Q canonical shas; and on GPU, B regenerates a_B and Q regenerates a_Q exactly from the identical prompt ids (greedy). |
| Y | retail/airline: `db_match` and termination ∈ {user_stop, agent_stop} (`fork_driver._y`) |
| Servers | B = BF16; Q = the cell's exact serving config (GPTQ/AWQ W4, calibration c1), as in the dev forks. q4: 1 GPU; q8: 2 GPUs pinned to node004/005/007; priority −14. |

## 2. Sampling rule (frozen; reads no outcomes)

**Eligible** units are the dev-split retail/airline panel units that `analyze_ghf`/`analyze_dev` admit:
- the same snapshot `snapshot_auto_20261001T0600Z`;
- the split guard (the telecom holdout is never opened);
- quarantine and dedupe;
- strict complete blocks (W70) and complete 85-task panel blocks (W78).

Of these, only divergent units count. The units digests equal the reference `dev_all_20261001T070326Z` in all 4 cells.
An eligible unit must also be **re-checkable**:
1. the Q pivot replay passed (`q_replay` all true);
2. the QQ no-op replay ran on the state (the hash-selected dev no-op sample) and reproduced:
   - the suffix;
   - every suffix prompt-id sha;
   - the termination reason;
   - the counters.

   `noop_ok`'s outcome key is not consulted.
3. BB, BQ and QB have `prefix_ok` and `env_hash_init_ok`.

This is the ghf CASE_RULE eligibility without its outcome categories.

| cell | admitted divergent | eligible | retail / airline eligible | sampled retail / airline | batch 1 retail / airline | blocks (all / batch 1) |
|---|---|---|---|---|---|---|
| q4 GPTQ-W4 d1 | 1102 | 116 | 76 / 40 | 13 / 7 | 6 / 4 | 16 / 10 |
| q4 AWQ-W4 | 1439 | 149 | 96 / 53 | 13 / 7 | 6 / 4 | 14 / 9 |
| q8 GPTQ-W4 d1 | 1473 | 149 | 106 / 43 | 14 / 6 | 7 / 3 | 16 / 9 |
| q8 AWQ-W4 | 1562 | 170 | 122 / 48 | 14 / 6 | 7 / 3 | 16 / 8 |

**Allocation** (per cell, n = 20). This is a two-level largest-remainder (Hamilton) proportional allocation:
- level 1 allocates over domains;
- level 2 allocates over the blocks within each domain.

Ties are broken by sha256(`simctrl-p-v1:alloc:…`). Within a (domain, block) stratum, states are ordered by
sha256(`'simctrl-p-v1:' + state_id`).

**Batches.** Batch 1 holds 10 per cell:
- each domain contributes ⌊k_d/2⌋ of its k_d selected states;
- the remaining slot goes to the domain with fewer selected states, so the batch is balanced by domain as far as possible;
- within a domain, the smallest sha keys go first.

Batch 2 holds the other 10 per cell.

**Launch rule.** Batch 1 runs first. Batch 2 may be launched only on throughput or time grounds, decided without
looking at any batch-1 outcome. Divergence types across the 80 are talk→act 32, tool_name 18, tool_args 14,
act→talk 12 and other 4.

## 3. Estimands (per-state arm means)

Ȳ_s,XY = mean over the 5 replicates of arm XY on state s. The estimands are equal-weight means over states. The sample is
proportionally stratified, so no reweighting is needed.
- G = mean_s(Ȳ_BQ − Ȳ_QQ): replace only the current action;
- H = mean_s(Ȳ_QB − Ȳ_QQ): replace only the continuation;
- F = mean_s(Ȳ_BB − Ȳ_QQ): replace both;
- G − H = mean_s(Ȳ_BQ − Ȳ_QB).

These are reported per cell, plus an equal-weight pool of the 4 cells. Intervals come from a bootstrap over states
within each cell (B = 2000).

**New vs original simulator on the same states.** The original per-state arm outcomes come from the frozen dev branch
files: one run each, and QQ is the recorded original continuation. They are compared with the new arm means. G/H/F/G − H
are reported under each simulator on the same 80 (or 40) states, together with their paired difference. Per arm, we
report how well the original Y agrees with the new replicate mean.

**Within-simulator variability.** Per arm: the share of states whose 5 replicates are not all equal.

**Not allowed.** The off-diagonal indicator (Δ_Q ≠ Δ_B) is not the same quantity under a stochastic simulator with R = 5
replicate means, because noise alone creates off-diagonal patterns. So the per-state four outcomes must NOT be
summarised as an off-diagonal share comparable to W93's 26.9%.

## 4. Unexposed branches

A branch can legitimately end before any user-simulator call. Examples: the step budget ends during tool calls, or an
agent-side context overflow. The CLOQ agent never stops by itself (`cloq/agent.py` `is_stop` only matches the opt-in
loop-guard marker), so such branches are rare. In the dev branches of the 80 states, 1.25% of branches had 0 user turns.
- Such a branch is recorded with `exposed: false` (`n_user_calls == 0`), and its Y is kept.
- It is **not missing** and does **not** fail the protocol check.
- The check variant `fork_driver._user_protocol_p` requires the relay checks only when `n_user_calls > 0`. For an
  unexposed branch it checks instead:
  - no user message in the suffix;
  - the termination is not user_stop;
  - `env_hash_init_ok`;
  - `prefix_ok`.
- `simctrl`'s `_user_protocol` is unchanged.
- Estimands are computed on all branches, and as a sensitivity on exposed branches only. Unexposed counts are reported
  per arm.

## 5. Relay simrelay-v2 (integrity)

`cloq/user_llm.py`. v2 is active only when the branch context sets `protocol: simrelay-v2`; v1 is unchanged. v2 has its
own root, `$CLOQ_SIMRELAY_DIR/v2` (default `/data/ziyangs/cloq_work/simrelay/v2`), so v1 claimers never see v2
requests.

**Request.** The request (`pending/<req_id>.json`) holds only these fields:
- `req_id`: `v2-` + a random uuid4 hex;
- `protocol`;
- `system_prompt`;
- `messages` (flipped history);
- `max_tokens`;
- `msg_sha256`;
- `stop_token_convention`.

There are no state, unit, arm, replicate or branch identifiers and no original outcomes. Bookkeeping goes to the sidecar
`meta/<req_id>.json`, which responders never read.

**Hash.** `msg_sha256` is the sha256 of the canonical JSON (sorted keys, separators `,` `:`, UTF-8) of the exact litellm
message list, system message first. The branch refuses to write a request it cannot reconstruct from
`system_prompt` + `messages`.

**Answer.** The answer (`done/<req_id>.json`) must echo `req_id`, `protocol` and `msg_sha256`. On any mismatch, or if
the content is empty, `relay_call` raises `RelayIntegrityError`. That is an infra error: the arm-replicate is missing,
never imputed. A daemon that finds a request whose hash does not verify answers *without* content, so the branch fails
at once instead of waiting for the 45 min timeout.

## 6. Responder isolation (`scripts/a6000/simrelay_cli.py`)

The daemon runs on the login node. It claims atomically (rename `pending/` → `claimed/cli-<n>/`), oldest first, and
only when one of its slots is free. The default concurrency is 12. Each request gets **one fresh headless call**:

```
claude -p --model claude-sonnet-5-5 --tools "" --strict-mcp-config --setting-sources "" --max-turns 1
       --no-session-persistence --system-prompt <request system_prompt> --output-format json
```

The call is configured as follows:
- cwd is the empty directory `/data/ziyangs/cloq_work/simrelay/cli_empty`, and the user message goes on stdin;
- `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` removes Claude Code's side model call;
- the binary is the newest `anthropic.claude-code-*`;
- there is no shared context, no session, no tools, no MCP, no settings and no CLAUDE.md.

**Residual.** These items are identical for every request and carry no experiment identifiers:
- Claude Code appends its environment block (cwd, platform, date, model name) and an account-context reminder to the
  user message;
- sampling uses Claude Code's defaults (adaptive thinking on; no temperature, no seed);
- max_tokens is advisory.

**Template** `simrelay-cli-template-v1`, sha256 `b4ac8a7e92f28537235dd9df56dddffa1450ed7c00410f90b74ffd3890e1927d`:
- a fixed header: "You are the customer described in the system prompt. Below is the conversation so far. Write ONLY
  the customer's next message.";
- then `Agent: …` for flipped role user and `Customer (you): …` for flipped role assistant;
- then a final `Customer (you):`.

Every answer records the template sha. The reply is cleaned only of an accidental role prefix, surrounding quotes or a
code fence around the whole message. Nothing else changes: `$` and stop tokens are preserved, and there is no shell.

**Per answer** the record holds: responder, model, models used, cost_usd, duration, template sha, raw result,
cleaning ops and attempts.

**Failures.** A CLI failure is retried up to 3 times with backoff. After that, the request goes back to `pending/`
(cool-down 60 s × failures). Garbage is never answered.

The log is `/data/ziyangs/cloq_work/logs/simrelay_cli.log`.

**Comparison with W95.** W95 used Claude Code subagents that answered many requests in one context (possible
carry-over) and saw bookkeeping fields. v2 removes both. It is still a different simulator from the original
Qwen3-30B-A3B (and from API Sonnet), and it is stochastic.

## 7. Validation (2026-10-01)

### (a) CPU dry run

Two q4 GPTQ units, be1b1f69 (airline talk→act) and 99a30007 (retail act→talk), with 4 arms × 5 replicates. The B
handle used the mock agent `tests/mock_anthropic.py`. The Q handle used the same mock with `--agent-stop`, which answers
the CLOQ agent stop marker at once. The relay was `simrelay_cli.py --mock` in a separate root.

Results:
- the manifest sha was verified;
- state checks passed 2/2 (state file sha, state id, history, prompt ids, a_B/a_Q shas; the local prompt-id render
  matches);
- 40 branches ran with no arm errors;
- 70 v2 user calls passed every integrity and protocol check;
- **10 unexposed branches** (BQ on be1b, whose a_B is a tool call; QQ on 99a3, whose a_Q is a tool call): 0 user calls,
  agent_stop, Y kept, `exposed: false`, protocol ok;
- `pass: true`.

Output: `analysis/fork/simctrl_p/dry/q4_gptq_w4_d1/` (with `dry_task.json`, `dry.sh`).

### (b) Relay end-to-end test (`tests/test_simrelay_v2.py`, temporary relay root)

**Phase A** sent three real tau2 retail requests (system prompt and flipped history from frozen dev states; one agent
message contains `$302.67`) through `relay_call`, and the real daemon answered them:
- 3/3 were answered (cli-0..2, 2.3–3.2 s, $0.0061–0.0083 each, model claude-sonnet-5-5 only);
- req_id, protocol and msg_sha256 were echoed and verified, and msg_sha256 equals the canonical sha;
- the template sha matched;
- the request held only the 7 v2 keys, with no identifiers;
- the meta sidecar was written;
- `$302.67` was preserved.

**Phase B** tested tampering:
- an answer with an altered msg_sha256 raised `RelayIntegrityError`;
- an answer with an altered req_id echo raised `RelayIntegrityError`;
- a request whose message was altered after hashing was rejected by the daemon (no content), and the branch then raised
  `RelayIntegrityError`;
- untampered answers (manual, and from the mock daemon) were accepted.

Output: `analysis/fork/simctrl_p/validation/relay_test_20261001.json`.

## 8. Throughput and cost (estimate; `make_tasks_simctrl_p.py --estimate` → `analysis/fork/simctrl_p/estimate.json`)

**Inputs.**
- In the dev branches of the 80 states, the mean was 6.07 user turns per branch (median 3; this counts turns, not
  outcomes). The expected user calls are therefore 4,805 (batch 1) and 9,710 (both).
- In the W95 relay run (468 branches), branches made 5.0 user calls on average, and the agent side took 12.2 s per user
  turn (median).
- The CLI takes about 4 s per call, plus a 1.8 s poll overhead.

The discrete-event FIFO model assumes 4 tasks at once and 5 units per task. It excludes checkpoint build and vLLM start
(~10–20 min per task).

| | daemon c = 12 | c = 24 |
|---|---|---|
| batch 1 (40 states, 800 branches) | 0.92 h (throughput bound 0.65 h) | 0.67 h (0.32 h) |
| both (80 states, 1,600 branches) | 1.41 h (1.30 h) | 0.89 h (0.65 h) |

**Cost** (sum of `total_cost_usd`). At the measured $0.0074 per call (W97 test, side call disabled), batch 1 costs about
$36 and both about $72. At $0.015–0.03 per call, batch 1 costs $72–144 and both $146–291.

## 9. What it can and cannot show

**Can.** It is a robustness check. It shows whether the sign/size picture of G, H, F and G − H, and the arm ordering on
these 80 (or 40) states, survives a change of user simulator, with the same states, the same forced actions and the same
controllers. It also measures within-simulator variability.

**Cannot.**
- It cannot confirm or refute few-pp G/H/F advantages (W93 intervals are a few pp; n = 80 states is far too small).
- It says nothing about rates under the new simulator beyond these states, and it is not a benchmark re-run.
- The histories before h_t still come from the original simulator.
- The four per-state binary outcomes must not be turned into an off-diagonal share comparable to 26.9% (§3).
