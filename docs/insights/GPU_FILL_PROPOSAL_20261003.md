**TL;DR** (W100q, 2026-10-03 07:15 PDT, infra session; proposal only, nothing queued or edited)
1. Failed queue: no task qualifies for a plain infra requeue. Every eval failure was already retried once, and the "airline outage" failures are not caused by an unstable user simulator. They are 600 s timeouts on the **agent** vLLM server of damaged models: the KV cache stays saturated and 6 to 21 requests wait. A retry cannot fix them, because the run-domain is already marked `completed`.
2. GPUs start idling now. There is a partial dip (about 3 to 13 idle) from 08:00 to 11:00. The cluster is near full from about 12:00 to 19:00 if q8 phase 2 is queued promptly. From about 19:00 to 22:00 on 10-03 until the freeze, about 36 to 38 of 40 agent GPUs sit idle, roughly 950 to 1080 GPU-h.
3. The meaningful fill totals about 100 to 150 GPU-h. Ranked: the common-state extension (q8 f04 to f06, then q4), unblocking 12 stale-dependency pivot tasks, and completing the timed-out episodes at low load. Most of the late idle capacity has no paper use under the current protocols.

# GPU fill proposal, 2026-10-03 to the evidence freeze

Scope:
- **Owner:** infra session (failure triage, GPU utilization).
- **Rules applied:** nothing was requeued from `deferred/`, no m24, g12, KIVI or rotation task was touched, `queue/running/` was not touched, and nothing was killed.
- **Evidence directory:** `analysis/status/gpu_fill_20261003/`, which holds `triage_outages.py` and `.json` plus `gpu_forecast.py` and `forecast_20261003T0705.txt`.

## 1. Failure triage

`failed/` held 19 files at 06:48. At 07:05, W100o moved the 6 `nmp_score_m24_*_f0{1,2,3}` tasks back to todo, which leaves 13.

| Task(s) | Class | Evidence | Action |
|---|---|---|---|
| `nmp_score_m24_{rtn_w4,gptq_w4_d1}_f0{1,2,3}` (6) | **Code bug.** `score_driver.render()` called HF-only `get_vocab` on `MistralChatRender`, so 83/85 rows failed with a prep error and 0/85 passed the prompt-sha check. | `analysis/fork/newmethod/token_scores/m24_rtn_w4/f01/scores.jsonl.gz` `missing_reason`; log `nmp_score_m24_rtn_w4_f01.log` | Fixed and requeued by the m24 owner (W100o, commit 248b0c5). The f02 retry burned about 1.5 h × 4 GPUs (29 min GPTQ build) before the fix landed. |
| `a6k2_q14_gauss3_s1`, `_s2`, `a6k2_q14_kvq_int3`, `a6k2_q32_gauss3_s1`, `_s2`, `a6k2_q32_rtn_w3` | **Agent-server timeout** (classified "outage"). Already retried once; the retry re-failed deterministically. | §1.1 | Leave. A fix needs a decision (F3). |
| `pert_q4_gptq_w3_resid_a2_q345`, `pert_q4_rtn_w3_restore_rand_{attn,mlp}_s3_q345` | User-simulator side: 3 timeouts and 2 connection-refused episodes in total. Already retried once. | `triage_outages.json` | Leave (pert line is user-paused; F3/F4). |
| `kivi_gate_q8` | rc = −9 twice; superseded by `kivi_gate_q8_r2` and `_toy2/3/4` (done) | `done/kivi_gate_q8_r2.json` | Leave (KIVI-owned, obsolete). |
| `a6k2_smoke_l8`, `a6k2_smoke_m24` | Expected 09-28 smoke failures, superseded by `a6k2_smoke_l8_v2` and the m24 gate tasks (done) | `done/` | Leave. |
| `ext_l8_gptq_w4_d1_bfcl_smoke_l8g_sc` | A stale duplicate: a done record with the same id exists (resubmitted after the `quantize.py` fix). The l8 line is closed (W99f). | `done/ext_l8_gptq_w4_d1_bfcl_smoke_l8g_sc.json` | Leave. |

### 1.1 The "airline outage" failures are agent-side queue timeouts, not simulator instability

Mechanism. Every outage episode behind the six a6k2 failures has the same error: `litellm.Timeout ... Connection timed out after 600.0 seconds`, after 2 attempts. The traceback runs through `tau2/agent/llm_agent.py` → `cloq/agent.py`, so it is the agent's own vLLM server (the quantized model under test), not the Qwen3-30B-A3B user simulator.
- **Counts:** 52 episodes over the six tasks: q14 kvq_int3 16, q32 rtn_w3 25 (12 in the failing q2 airline run-domain), q14 gauss3 2 + 3, q32 gauss3 3 + 3.
- **Server load:** one agent server takes `RUN_PAR` = 4 run-domains × `max_concurrency` 8 = up to 32 concurrent requests. The damaged models produce long, looping contexts, so the KV cache holds only a few sequences.

  | Server | Running (median) | Waiting (median) | KV use (median) | Lines with a queue |
  |---|---|---|---|---|
  | q14 kvq_int3 | 5 | 20 | 90.5% | 100% |
  | q32 rtn_w3 | 6 | 20 | 91.9% | 99% |
  | q14/q32 gauss3 | 2 | 6–8 | 68–86% | 86–97% |
  | Healthy q14 BF16 | 12 | 4 | n/a | n/a |
  | Healthy q32 BF16 | 12 | 8 | n/a | n/a |
  | Healthy q14 RTN-W4 | 14.5 | 4 | n/a | n/a |

  A request that waits in the queue and then decodes 1024 tokens can exceed 600 s.
- **The run times match this pathology.** q14 kvq_int3_q2 airline took 65 774 s (18.3 h) for 27 tasks; q14 gauss3_s1 airline took 45 780 s.

Evidence against simulator instability:
- `logs/sim_interruptions.jsonl` was never created (no simulator ever died with an active lease).
- `logs/sim_instances.log` has no death event.
- The failures sit on four nodes (001, 005, 006, 008).
- The simulator queues around the 3 user-side events were short: node001 at 15:10 to 15:15 on 10-02 had wait 0 to 1; at 12:00 to 12:05 it had wait 0 to 10.

The user-side events are only 5 episodes (3 timeouts, 2 connection refused) in the 3 failed pert_q4 tasks.

**Why the autopilot retry cannot help.** `cloq/run_arm.py` l. 180 skips a run-domain whose `status.json` is `completed`, and outage episodes are recorded inside a completed run-domain. `worker.py` l. 454 to 483 then re-reads `metrics.json` and raises the same error.
- **Verified on `a6k2_q14_gauss3_s1`.** It was retried at 12:00:02 and failed at 12:20. The log shows `airline already completed; skipping`, and the outage episodes ended at 04:09 and 04:12 PDT, before the retry.
- **Cost of the futile retry.** The retail run-domain had resumed with 39 runs left and was killed by the re-raise. Each futile retry costs one server start plus that lost progress.

**Running tasks that are already doomed** (agent-side 600 s timeouts recorded; each will raise when its run-domain completes):

| Task | Outage episodes | Progress | GPUs |
|---|---|---|---|
| `a6k2_q32_tel_rtn_w3` | 7 | 28/80 telecom sims in 22.75 h (1.2 per h), so it ends after the freeze | 2 |
| `pert_q8_gptq_w3_resid_a2_q345` | 16 | n/a | 1 |
| `pert_q8_rtn_w3_resid_a2_q345` | 11 | n/a | 1 |

The q32 telecom task matches its sibling `a6k2_q32_tel_rtn_w4`, which was stopped with user approval on 10-02 as stuck. The two pert tasks are the q8 "error dose α" appendix backfill. Their non-outage episodes are valid data that F3 could complete, so stopping them is not proposed. Stopping the q32 telecom task is proposed (open question).

## 2. Demand vs supply, 07:00 10-03 → 00:00 10-05 PDT

**Supply: 40 agent GPUs.**
- 6 each on node001, 004, 005, 006, 007 and 008; 4 on node002, whose GPUs 0,1 fail the probe.
- GPUs 0,1 of each node run the user simulator. node003 is down (job 49694 pending, `ReqNodeNotAvail`).
- Runners stop claiming 3 h before their job end (`--min-left 10800`): node005 and node007 at **20:06 on 10-04** (job end 23:06), node001 at **21:08 on 10-04**. The other jobs outlive the horizon.
- Autopilot runs until 01:37 on 10-05 and resubmits runners only while todo is non-empty.

**Demand.** Point estimates come from the `seconds` field in done/ records and from claim times in `logs/node_*.out`.
- **Running tasks (39 GPUs at 06:50).** Most finish by 10:00 to 13:00. The kvq int3/int4 evals (6 run-domains each) and pert_q4 have about 6 to 10 h left. q32 telecom runs past the freeze.
- **todo (07:05, 35 files).**
  - m24 phase 2: 6 tau2 at −30 plus 12 scores at −26, all 4-GPU. About 75 GPU-h (tau2 median 1.08 h, max 3.96 h; score about 0.8 h including the 29 min GPTQ build).
  - q8 rotation: 1 tau2 and 4 scores, all 2-GPU and pinned to node004/005/007.
  - 12 pivot tasks that can never be claimed (F2).
- **q8 phase 2.**
  - **When:** the decision fires when `nmp_tau2_q8_spinquant_w4a4_f03` finishes. That task waits for a node004 pair, and scores sort ahead of it alphabetically. Expected decision about 11:30 to 13:00.
  - **Projected cost:** the dry run at 07:00 (builder without `--write`) projects 127 GPU-h, using 5 of the 8 cells as eligible now. With all 8 cells eligible plus the reference-cell gates, it is about 130 to 190 GPU-h.
  - **Wall time:** bounded by the KIVI tau2 tasks (4 to 8 h each).
- **g12 formal: none** (W100p gate FAIL).

Indicative hourly table (`analysis/status/gpu_fill_20261003/forecast_20261003T0705.txt`; greedy list scheduler with q8 node pins). "Known" = running + todo + m24 phase 2 + q8 phase 2.

| Window (PDT) | Idle GPUs, running + todo only | Idle GPUs, known work | Idle GPUs, known + all fill below |
|---|---|---|---|
| 07:00 10-03 | 1 | 1 | 1 |
| 08:00 to 11:00 | 15–33 | 3–13 | 0–5 |
| 12:00 to 18:00 | 33–38 | 0–2 | 0 |
| 19:00 to 22:00 | 38 | 26–38 | 5–24 |
| 23:00 10-03 to 20:00 10-04 | 38 | 38 | 38 |
| 21:00 to 24:00 10-04 | 20–26 (claim cutoffs) | 20–26 | 20–26 |
| **Idle GPU-h total** | **≈ 1400** | **≈ 1080** | **≈ 950** |

When idling starts:
- **Now.** node006 GPU 7 has been free since 06:47.
- **A real dip from about 08:00.** The q8 telecom and rotation tasks finish, while the m24 4-GPU tasks need two free NVLink pairs on one node and the q8 tasks may only use node004/005/007.
- **Steady idling from about 19:00 to 22:00 on 10-03**, as q8 phase 2 drains. The two remaining busy GPUs are the q32 telecom task.

Side effect: the 12 unclaimable pivot tasks keep `todo/` non-empty. Once whole nodes are idle, the autopilot will keep resubmitting runners that idle-exit after 30 min, in a loop of about 35 min per node.

Caveat on the horizon. The task brief uses 00:00 PDT on 10-05. `NEWMETHOD_PANEL_PROTOCOL.md` §5.4 ("9 h before the 2026-10-05 00:00 Toronto evidence freeze", T_deadline 12:00 PDT) and TODO_v2 ("October 5 Toronto") put the freeze at **21:00 PDT on 10-04**. That is 3 h earlier (open question).

## 3. Fill options, ranked by paper value per GPU-h

| # | Option | GPU-h | Paper value | Protocol implications |
|---|---|---|---|---|
| F0 | SAMEPREC final-prefix analysis (K = 17: all `fork_sameprec_{q4,q8}_g1..g6` are done) | **0** | High. The main-text §5 and F6/F7 still carry interim K = 6 markers (W100h). | Already fixed by SAMEPREC §2 ("longest complete prefix at the evidence freeze"). No amendment. Owned by the main session. |
| F1a | Common-state comparison, q8 f04–f06 (K = 3 → 6 blocks) | ≈ 15–20 | High. It is a main-text pending slot (common-state K(c)). At K = 3 both K(c) are "not resolved" (t95 half-widths 8.9 and 5.9 pp). If the between-block SD stays the same, the K = 6 t95 half-width is about 3.8 and 2.5 pp, and the bootstrap half-width shrinks by about 1/√2. | The cost is low because the q8 phase-2 reference cell `gptq_w4_d1` runs the existing d1 arms (BB, BQ, QB, QQ) on exactly these 255 frozen U2B rows (`newmethod_panel_v1.json` f04–f06, phase 2; NEWMETHOD §2.5). Only the 6 d2 tasks are new (`cs_q8_d2_{bf16,d1}_f0{4,5,6}`, 2 GPUs, about 1.2 h; f01–f03 took 0.7–1.8 h). Add about 5 GPU-h of d1 arms if `expansion_q8` says false. **Needs a dated amendment to `COMMONSTATE_SOURCES_PROTOCOL.md` (§6 says so) and GPT-6.1 approval before any f04–f06 d2 outcome exists.** The K = 3 outcomes are known (K(d1) −0.4, K(BF16) +2.4), so the amendment must also fix K = 6 unconditionally, keep the K = 3 reading, and state how the two looks are handled (e.g. the K = 6 reading at a split α, or labelled exploratory). The f04–f06 reference outputs come from q8 phase 2 (queued about 12:00 to 13:00), so **the amendment has to be hashed before those outputs are read, preferably before they exist.** |
| F1b | Common-state comparison, q4 f01–f03 (new model, same design) | ≈ 8–10 (+1–2 h engineering in `make_tasks_commonstate.py`) | Medium-high. It adds model breadth, and in the Holm W4 G−H family q4 reverses q8's sign. No q4 outcome of this design exists. | Inputs exist: Bank U `q4_gptq_w4_d1/f01–f03` and the q4 d2 checkpoint (`a6k2_q4_gptq_w4_d2`, used by sameprec). q4 is 1 GPU per task (B and Q at gpu_util 0.44). Needs the same dated amendment and approval. q8 is known, so the amendment states that q4 was added after q8 was read. |
| F2 | Unblock the 12 `pivot_{q4,q8}_rtn_w3_*` tasks in todo | ≈ 10–20 | Medium. Appendix restoration location vs random in the RTN-W3 damage regime. The pivot arms are done for gptq_w3, awq_w4 and gptq_w4_d1. | No design change. The tasks were requeued with user approval (option 1, 10-01 23:05) at tier −23. They depend on `fork_stress_{q4,q8}_rtn_w3`, which was split into the shards `fork_stress_*_rtn_w3_s*of*` (all done; W72) and parked in `deferred/`, so the dependency can never resolve. Fix: replace the dependency with the shard ids (a one-field edit, tmp + os.replace). The states exist (`analysis/fork/stress/q{4,8}_rtn_w3/states`, 232 and 255). This also stops the runner-resubmit loop. Needs the main session's OK, since it edits todo records it created. |
| F3 | Complete the agent-timeout episodes at low load | ≈ 30–50 | Medium. It completes coverage cells now reported missing: q14/q32 Gaussian k = 3 (B2 dose ladder), q14 KV-INT3 (M5), q32 RTN-W3 (M2), `a6k2_q4_awq_w3_qx` (2 timeouts, deferred), and the q8 error-dose α arms (`pert_q8_*_resid_a2`, appendix). That is about 93 episodes: 88 agent-side (52 in the failed a6k2 tasks, 34 in the 3 doomed running tasks, 2 in `a6k2_q4_awq_w3_qx`) and 5 user-side. | Mechanism claim: under `VLLM_BATCH_INVARIANT=1` + `TORCHINDUCTOR_DETERMINISTIC=1`, tokens do not depend on batch composition for Qwen3 (B8 determinism pairs 257/257 and 303/303; fork no-op re-runs bit-exact). So a timed-out episode re-run alone yields the episode that load prevented. This is not established for Gemma 4 (W100p), which is not involved. W6 already says such episodes are never data and are re-run. What is missing is a resume path, because run_arm skips completed run-domains: drop the outage-classified sims from `tau2_results.json` and set the run-domain back to running. A per-task `run_par` (worker `CLOQ_RUN_PAR` is global today) of 1 for damaged cells would also stop new timeouts. Both are code and data changes on shared files, so they need the main session's and the user's OK. Infrastructure only: no estimand changes. |
| F4 | `deferred/`: only `pert_q4_rtn_w3_restore_early_q345`, `pert_q8_rtn_w3_restore_rand_attn_s3_q345` and `a6k2_det_q4_kvq_int4_rot_b` | ≈ 30 (pert, 12–15 h each) + 1 | Low-medium. The two pert tasks complete the RTN-W3 restoration-location set (q4 `early` is the only missing location; q8 `rand_attn` lacks seed s3). det_b completes a B8 determinism pair (`_a` done). | The pert tasks fall under the user's "停 pert" (pause pert) and were not covered by the 10-01 23:05 option-1 requeue. They risk the same agent timeouts unless F3's `run_par` fix lands first. Bulk requeue is not allowed; requeueing these 3 needs explicit user OK. |
| F5 | Cross-node replay audit of a hash sample of reported fork branches | ≈ 10–20 | Low-medium. A reproducibility artifact for the checklist: a bit-exact re-run on a different node. | No outcome is read, so no preregistration is needed beyond a frozen sample rule. Any mismatch is reported. |
| F6 | Independent confirmation blocks for the Holm W4 G−H family (e.g. q4 GPTQ-W4, p_holm 0.069) | ≈ 100–200 | Potentially high, but late | Needs its own preregistration and approval. If it is decided after seeing p = 0.069, it is an outcome-dependent extension, so it must be framed and analysed as a separate confirmation. **Not recommended before this freeze.** |

`deferred/` inventory (56 files). Only F4's three are candidates.

| Category | Count | Note |
|---|---|---|
| l8 line | 43 | 22 open-loop `a6k2_l8_ol_*` and 21 closed-loop or calibration. The line is closed (Llama gated, W99f capability floor). |
| Stopped as stuck | 3 | `a6k2_q32_tel_rtn_w4` ("0/1 run-domain after 10.6 h", stopped with user approval on 10-02; "requeue later", but it would not finish before the freeze), `a6k2_q4_awq_w3_qx` (2 real 600 s timeouts), `a6k2_w2p_q4_rtn_w2_q3` (degenerate W2, truncated-result JSONDecodeError) |
| g12 gates | 3 | Owner g12; gate FAIL (W100p) |
| Superseded originals `fork_stress_{q4,q8}_rtn_w3` | 2 | Never requeue |
| pert paused ("停 pert") | 2 | Candidates under F4 |
| Determinism pair `a6k2_det_q4_kvq_int4_rot_b` | 1 | Candidate under F4 |
| Old telecom line `a6k2_q8_tel_bf16` (W35) | 1 | n/a |
| Extra simulator replica `sim_node005_r2` | 1 | Not needed; simulator queues are short |

Reading. F0 to F3 total about 65 to 100 GPU-h, plus 0 for F0, and give the best value; F4 and F5 add about 40 to 50. Even with all of them, about 950 GPU-h of the late window stays idle. Turning that into main-text evidence would need new preregistered designs (F6-scale) approved before the freeze. Otherwise the honest options are to accept idle capacity or to let runners idle-exit and release the nodes (which F2 also enables).

### 3.1 Interaction with the experiment pilot (W100r `exppilot`, built, not started)

- **Phase 2 and F0.** Pilot step (A) would queue q8 phase 2 as soon as `expansion_q8.json` exists, which removes the human queueing delay assumed in §2. Step (B) would run the SAMEPREC analyses after the freeze, which covers F0.
- **Fill step (C) would release two deterministic re-failures.** Its dry run lists `a6k2_q4_awq_w3_qx`, `a6k2_w2p_q4_rtn_w2_q3` and `a6k2_det_q4_kvq_int4_rot_b` as releasable.
  - `runs/a6k2_q4_awq_w3_q5/airline` is `completed` and holds 2 outage episodes (`infra_causes.json`), so the task re-fails a few minutes after its server starts, as described in §1.1.
  - `a6k2_w2p_q4_rtn_w2_q3` was deferred after a second failure from a truncated result. Its retail run-domain is still `running`, with a 44 MB `tau2_results.json`, so a re-fail is likely.
  - Both were deferred by the main session as stuck. An automated release from `deferred/` also conflicts with the rule that a requeue from `deferred/` needs explicit user OK.
  - **Proposed:** exclude a task from (C) whenever one of its run-domains is `completed` with outage-classified episodes, i.e. apply the §1.1 check before release. Release from `deferred/` only after the user approves the pilot's fill step.

## 4. Decisions requested

1. F1a/F1b: write the common-state amendment (K = 6 on q8, and/or q4) and get GPT-6.1 approval before about 12:00 PDT, when the q8 phase-2 reference outputs start to exist? Who writes it: the main session or this session?
2. F2: may the infra session rewrite the dependencies of the 12 pivot rtn_w3 todo tasks to the done shard ids?
3. F3: approve a resume path for outage-classified episodes (plus a per-task `run_par`) for the damaged coverage cells? Or should these cells stay reported as incomplete?
4. Stop `a6k2_q32_tel_rtn_w3`? It holds 2 GPUs, has 7 agent timeouts already, and runs past the freeze. Its owner is the main session, and the user approved the same stop for its sibling.
5. Which freeze binds: 00:00 PDT or 00:00 Toronto (= 21:00 PDT on 10-04)?
6. F4: requeue the 3 named deferred tasks? (No bulk requeue.)
7. Exppilot (W100r) fill step: approve it, and should it skip tasks whose completed run-domains hold outage episodes (§3.1)?

Evidence:
- **This proposal's files:** `analysis/status/gpu_fill_20261003/{triage_outages.py,triage_outages.json,gpu_forecast.py,forecast_20261003T0705.txt}`.
- **Code:** `scripts/a6000/{worker.py,noderunner.py,autopilot.sh}`, `cloq/run_arm.py`.
- **Protocols:** `docs/insights/{COMMONSTATE_SOURCES_PROTOCOL,NEWMETHOD_PANEL_PROTOCOL,SAMEPREC_PROTOCOL}.md`.
- **Outputs:** `analysis/fork/out/commonstate_20261002T201612Z.md`.
- **Cluster logs:** `/data/ziyangs/cloq_work/logs/{autopilot.log,node_node00*_49*.out,sim_node00*_49*.log,sim_balancer.log,expansion_sched.log,tasks/<task>.{log,vllm.log}}`.
- **Run data:** `/data/ziyangs/cloq/runs/<run>/<domain>/{status.json,tau2_results.json,infra_causes.json}`.
- **Queue:** `/data/ziyangs/cloq_work/queue/{failed,running,todo,deferred}/`.
