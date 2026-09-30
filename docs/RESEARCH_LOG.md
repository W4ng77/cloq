# CLOQ research log — every version, insight and work item, with TL;DR and evidence

**TL;DR** — The calibration method (CLOQ) was falsified at v1. The paper is now about *perturbation equivalence*:
judge a compressed agent against the model's own perturbation null. The A6000 multi-model matrix has been running
since 2026-09-28 18:10. The live dashboard is https://claude.ai/artifact/PqFrT9bVufKqdkD43u5c1B.

Paths are relative to the repo root unless they start with `/data/` (cluster only; not in git). Stable ids:
versions `V*`, insights `I*` (iteration-scoped in `docs/insights/`), experiment proposals `E*`, work items `W*`.
Newest first.

---

## W59 — NFS recovered; node001 back in service (2026-09-30 12:15 PDT)
**TL;DR** The W56/W57 NFS degradation has cleared:
- A fresh `import cloq.run_arm, vllm` takes 13–15 s on node001/004/006, down from >300 s at 11:25.
- The node001 latency probe was normal 3× in a row at 12:11.

Recovery steps:
- Removed `queue/DRAIN.node001`.
- Restarted the analysis daemon at `CLOQ_DAEMON_PERIOD=1200`, `CLOQ_DAEMON_PROCS=4`, a middle setting between the 600 s / 6 default and the throttled 3600 s / 2.
- The 90 min server-start timeout (W58) stays.

Still open:
- node003 remains down; the admin is working on it.
- The admin proposed reserving 8 CPUs per node for GPU jobs. Our runners use ≤32 CPUs, so they already comply.
- Rejected for now: re-running stalled tasks. A fresh start hit the same 5 min import, so it could not have helped.
- Proposed and not done: a node-local copy of the Python environment. It is not needed while NFS is healthy.

## W57 — Cluster-wide NFS degradation; analysis daemon throttled (2026-09-30 10:55 PDT)
**TL;DR** The NFS stalls from W56 are now on every node, not just node001. A metadata `ls` of the env takes 1.0–7.3 s, against 0.2–0.5 s in the morning. Processes sit in `rpc_wait_bit_killable` on node004, node005 and node006 (vLLM start, run_arm, fork_driver).
- **Impact:** at 10:49, 16 of 40 monitored GPUs were busy with 113 tasks queued. 13 tasks finished in the last hour.
- **Our own share of the load:** the analysis daemon built an integrity snapshot every 15–20 min, reading and hashing every run (about 10 min per cycle with 6 processes) and running the fork analyses on top of that. The daemon now takes `CLOQ_DAEMON_PERIOD` and `CLOQ_DAEMON_PROCS`. I restarted it with a 3600 s period and 2 integrity processes (pid 959917).
- **Undo:** restart the daemon without those environment variables once NFS latency is normal again.
- **Still open:** node003 is down (W56) and node001 is drained (W56). The storage server is the cluster admin's side.
Evidence: srun timings in this session, `ps` wchan on node004/005/006, `analysis/status/analysis_runs.jsonl`.

## W56 — node003 rebooted; node001 NFS stalls, drained (2026-09-30 09:45 PDT)
**TL;DR** Two infrastructure problems appeared within minutes of each other, around 08:40.

**node003 rebooted unexpectedly** (Slurm reason, 08:48; munge socket errors in the log).
- The runner got SIGTERM at 08:40. It requeued its running tasks, and other nodes picked them up. Nothing was orphaned.
- Job 49694 was requeued by Slurm and is now PENDING (ReqNodeNotAvail). It restarts by itself when node003 returns.
- The cluster is down 6 GPUs (40 usable).

**node001 NFS client stalls.**
- Processes are stuck in `rpc_wait_bit_killable`: vLLM startup, the GPTQ build, even the runner.
- Metadata access takes 2.1 s on node001, versus 0.2–0.5 s on the other nodes. Direct reads run at 173 MB/s, versus 421 MB/s on node004.
- Three fork/pivot tasks failed with "B server did not come up in 30 min", with an empty vLLM log. All were requeued.
- `queue/DRAIN.node001` = 2–7 stops new tasks there. Running tasks finish, and node001's simulator (GPUs 0,1) keeps serving.
- To undo: delete the file once node001's NFS latency is normal again.

**Monitor:** it now also reports job state changes. The old one missed RUNNING→PENDING because the job id stayed in squeue.

Evidence: `sinfo -N -n node003`, `logs/node_node003_49694.out`, `logs/node_node001_49727.out`, the srun/dd timings in this session, `logs/tasks/{fork_ext_dev_q8_gptq_w3_bfcl_miss_param,pivot_q4_gptq_w3_rand_attn_s1__rand_mlp_s1,pivot_q4_gptq_w4_d1_rand_attn_s1__rand_mlp_s1}.*`.

## W55 — Pivot-time restoration: detection (CPU), arm screening queued, step 3 gated by a pre-declared rule (2026-09-30)
**TL;DR** The pivot (the first semantic divergence) is only moderately detectable from Q's own uncertainty (AUROC 0.60–0.73), and no escalation value is distinguishable from zero yet. Pivot-arm screening (32 tasks, ≈ 26 GPU-h) is queued. Step 3 will run only if the rule fixed in FORK_PROTOCOL §13 selects an arm.
- **Step 1: `analysis/fork/analyze_pivot.py`** (EXPLORATORY; registrable as `python analysis/fork/analyze_pivot.py --snapshot {snapshot}`).
  - **Positives:** Q's decision at t*.
  - **Negatives:** Q's decisions before t*, and every decision of fully searched non-divergent units.
  - **Signals:** from Q's decisions.jsonl: first-token margin, minimum margin, mean and minimum token log-probability, and the number of low-margin tokens. Entropy was not logged.
  - **AUROC of −first_token_margin** (matched on domain × decision index):

    | Cell | AUROC (matched) |
    |---|---|
    | q4 AWQ-W4 | 0.65 (0.60) |
    | q4 GPTQ-W4 | 0.62 (0.62) |
    | q8 AWQ-W4 | 0.64 (0.67) |
    | q8 GPTQ-W4 | 0.69 (0.71) |
    | q4 KV8 | 0.71 (0.71) |
    | q4 GPTQ-W3 | 0.60 (0.64) |
    | q4 KV4-rot | 0.62 (0.62) |

    min_margin and the log-probability signals reach 0.66–0.73.
  - **Escalation policy** (escalate when the margin is below θ; escalating once at the pivot is branch BQ): escalating 10% of decisions catches 16–39% of pivots, and escalating 20% catches 30–51%. The policy value over the full pool has intervals covering 0 in every cell (e.g. q8 GPTQ-W4 at a 20% rate: +3.4 [−1.5, +8.6] pp).
  - **Full-pool values:** Y_BQ − Y_QQ, Y_QB − Y_QQ (= C + I, escalate after the divergence) and Y_BB − Y_QQ (= A + C + I) all cover 0, except q4 KV4-rot Y_BB − Y_QQ = +12.3 [+3.4, +22.2] pp.
  - analyze_dev.py now carries Y_QB − Y_QQ and Y_BB − Y_QQ as explicit endpoints.
- **Step 2: which modules flip the action at the pivot** (fork_driver mode `pivot_arms`, generator `scripts/a6000/make_tasks_pivot_arms.py`, analysis `analysis/fork/analyze_pivot_arms.py`).
  - **Design:** 150 hash-sampled frozen states per cell (q4 GPTQ-W4, q8 AWQ-W4, q4/q8 GPTQ-W3). Arms: none, all, early/middle/late/attn/mlp, byte-matched random rand_third/attn/mlp s1, and resid α 0.5; the W3 cells also get the 8 restore_recal arms. Each arm makes one decision per state at the identical prompt, two arms per task. 32 tasks at −14; the estimate is ≈ 26 GPU-h, revised from the measured control task.
  - **Pipeline control,** `pivot_q4_gptq_w4_d1_none__all` (run at −16, as the only priority exception): prompt ids 150/150; `none` reproduces a_Q exactly 150/150 and `all` reproduces a_B exactly 150/150.
- **Step 3 selection rule, fixed before any arm outcome** (FORK_PROTOCOL §13, commit 6c926c2).
  - **Statistic:** Δ = r_B(arm) − r_B(byte-matched random), paired, pooled over q4 and q8 GPTQ-W3 with the hierarchical bootstrap.
  - **Eligible:** one-sided LB > 0 and Δ ≥ 5 pp. The largest Δ is chosen, with a second arm if also eligible (max 2).
  - **If no arm is eligible,** step 3 is not run.
  - **Step 3 itself** ("R at t*, then Q" on the GPTQ-W3 stress states, vs QQ and BQ) is not implemented or queued. Estimate: ≈ 460 states × (1–2 arms + control) single branches, ≈ 12–25 GPU-h.
Evidence: `analysis/fork/out/pivot_20260930T135758Z.{json,md}`, `analysis/fork/pivot_arms/q4_gptq_w4_d1/{none,all}.jsonl`,
`analysis/fork/out/pivot_arms_20260930T145218Z.{json,md}`, `docs/insights/FORK_PROTOCOL.md` §13, `/data/ziyangs/cloq_work/queue/todo/pivot_*.json`.

## W54 — `restore_recal`: rebuilt mixed precision around the kept modules (fixes the sequential-compensation confound); 16 W3 tasks queued (2026-09-30)
**TL;DR** Plain `restore` arms swap BF16 modules into a finished true-sequential GPTQ/AWQ checkpoint. The downstream quantized modules were calibrated on quantized-upstream inputs, so the swap breaks their compensation, and the absolute recovery is confounded (the user caught this; confirmed in `cloq/quantize.py`).
- **New kind `restore_recal`:** the arm's modules stay BF16, and the base's sequential GPTQ/AWQ is re-run for all other modules (same c1 manifest, settings, seed).
- **Queued:** 16 tasks, 48 runs, on q4/q8 GPTQ-W3 × {early, middle, late, attn, mlp, rand_third_s1, rand_attn_s1, rand_mlp_s1}, blocks q3–q5, priority −14 (the same as the W3 plain arms). Estimated **~16 GPU-h** (range 10–25; W3 Q tasks with 3 runs took 0.9–1.0 GPU-h, and the recal build adds 7–11 min).
- **Reporting:** `analyze_restore_eval.py` reports the compensation effect `restore_recal` − `restore` per arm.

**Code**
- `cloq/quantize.py`: `quantize_model(keep=…)` and `--keep <arm manifest>`. With no keep set the code path is unchanged, and rtn with `--keep` is refused.
- `scripts/a6000/derived.py`: `build_recal`, built in node-local scratch and not cached, because the 16 arms would need ~190 GB. It has a per-tag registry on the files sha.
- `scripts/a6000/worker.py`: `--keep` is passed through (1 hunk).
- `scripts/a6000/make_tasks_perturb.py --recal`.

**Tests** (`tests/test_perturb.py`, CPU tiny Qwen3, W3, GPTQ and AWQ): ALL PASS.
- An empty keep set equals Q bit for bit, and two runs are deterministic.
- keep = all equals BF16.
- With layer 1 kept, layer 0 equals Q, and the downstream modules differ from the plain-restore arm: GPTQ 14/14; AWQ 13/14, where the unchanged module is one whose best AWQ exponent is 0, i.e. input-independent RTN.
- With a single k_proj kept, its q/v siblings equal Q and o_proj changes.
- Worker path: the base spec is re-run with `keep_manifest`, and the registry is written and re-checked.

**Analysis**
- New "restore vs restore_recal" table: success of each family, recal − plain, gap closed and turnover closed for both, and the T(BF16) difference.
- Pairing was verified with an aliased recal arm (= plain late): 255 units, difference 0.

**Interpretation rule:** plain-family structured vs random comparisons stay fair (same kind of mismatch). Absolute recovery is read from `restore_recal`.

**Evidence**
- `docs/insights/PERTURBATION_PROTOCOL.md` §3c.
- Queue: `/data/ziyangs/cloq_work/queue/todo/pert_q{4,8}_gptq_w3_restore_recal_*_q345.json`.

## W53 — Telecom W4-damage restoration cell (q8 AWQ-W4 c1): 9 arms queued on telecom dev f01–f06 (2026-09-30)
**TL;DR** This adds a second damage regime and the only one at W4 bits: q8 AWQ-W4 d1 on telecom dev blocks. 9 arms, cached AWQ base, priority −9, 18 tasks / 54 runs, estimated **~41 GPU-h (range 32–66)**; `analyze_restore_eval.py` reports the telecom cell separately, with a persona breakdown.
- **Arms:** early, middle, late, attn, mlp; `rand_{third,attn,mlp}_s1`; resid α 0.5.
- **Runs:** `a6k2_pert_q8_tel_awq_w4_<arm>_<blk>`, domain {telecom}, `manifests/telecom/dev_v1.json`. They pair with `a6k2_q8_tel_awq_w4_<blk>` and `a6k2_q8_tel_bfpair_<blk>`.
- **Holdout:** untouched.

**Block choice (a deviation from the f01–f03 request)**
- On f01–f03 there is no Q–BF16 gap at all: official success is 21/240 for both, and Hard persona 5/75 for both.
- The damage sits in f04–f06: 19/240 vs 32/240, Hard 1/75 vs 12/75. Restoration on f01–f03 alone would repeat the W4 equivalence problem (W50).
- I queued the full pre-existing dev set f01–f06 as two tasks per arm (`_f123`, `_f456`). This is the set the damage claim was made on.
- f04–f06 alone would be selected on outcome (regression to the mean), and that was rejected.
- The `_f456` half can be deleted from `todo` if f01–f03 only is preferred; that halves the cost to about 21 GPU-h.

**Caveat on the premise**
- With official task-basis success (the analysis definition) on f01–f06, BF16 − Q = +2.7 pp [−2.9, +9.2] overall (Q 8.3 %, BF16 11.0 %).
- For Hard it is +7.3 [−2.6, +19.0] (Q 4.0 %, BF16 11.3 %).
- Both intervals include 0, so the W4 damage is suggestive, not established.
- These numbers come from the pairing check, an aliased arm = Q.

**Cost estimate**
- Done q8 telecom 3-run tasks took 1.8–3.7 h each (median ~2.3 GPU-h, one GPU).
- The derived build takes about 1 min on the cached base `q8_awq_8a97d2f7b45b`.
- 18 × 2.3 ≈ 41 GPU-h is under the 60 GPU-h cut, so no arms were dropped. The cost also falls on the telecom simulator.

**Pairing verified before writing**
- Six Q runs were aliased as a fake arm (symlinked run dirs, temporary snapshot, output to scratch; all removed).
- `analyze_restore_eval` paired all 480 units on f01–f06, 0 skipped, with arm − Q = 0 and turnover 0 as expected.
- The run names contain `_tel_`, so the integrity snapshot expects the {telecom} domain set (W44).

**Analysis changes**
- The arm regex accepts `tel_<cell>`, and `pair_ids()` maps telecom cells to `*_tel_bfpair_*`.
- Telecom cells get their own bootstrap population.
- New "Telecom cell(s), by persona" table: Hard / Easy / None success, arm − Q, BF16 − Q, gap closed and turnover closed.

**Evidence**
- `scripts/a6000/make_tasks_perturb.py --tel`, `analysis/fork/analyze_restore_eval.py`.
- Queue: `/data/ziyangs/cloq_work/queue/todo/pert_q8_tel_awq_w4_*_{f123,f456}.json`.

## W52 — Difficulty moderators (exploratory) and telecom development forks queued (2026-09-30)
**TL;DR** The preliminary telecom signal is smaller under the official criterion, and none of the post hoc difficulty moderators is significant on the development forks.
- **Preliminary signal, recomputed with official telecom success** (official_reward == 1; the preliminary numbers used db_match/reward):
  - q8, f01–f06: BF16 11.0%, AWQ-W4 8.3% (−2.7 pp, not −4.8), GPTQ-W4 14.2%.
  - PERSONA:Hard: BF16 11.3%, AWQ 4.0%, GPTQ 20.7% (not 18% vs 4%).
  - q4: BF16 16.9%, GPTQ 16.7%.
- **`analysis/fork/analyze_difficulty.py`** (EXPLORATORY; registrable as `python analysis/fork/analyze_difficulty.py --snapshot {snapshot} --include-gate-telecom`). Moderators:
  - (a) remaining horizon h = n_decisions(Q) − t*, tertiles plus a bootstrap slope of C (and G, A, I) on h, the compounding test;
  - (b) BF16 task length, tertiles;
  - (c) BF16 difficulty, bins {0, (0, 0.5], (0.5, 1]};
  - (d) domain;
  - (e) telecom persona.

  It uses analyze_dev's units, exclusions and hierarchical bootstrap. It takes about 30 s on the current 4,810 fork states (7 cells, partial W4, KV8 and stress outputs, plus the telecom gate block).
- **First exploratory read.** No compounding signal: the slope of C on h is small and not significant in every cell (q4 GPTQ-W4 −0.8 pp per 10 decisions, p 0.36; q8 AWQ +0.5, p 0.73; the largest is q4 KV4-rot +3.3, p 0.15). The difficulty and length strata all have intervals covering 0.
- **Telecom development forks queued** at priority −12 by `scripts/a6000/make_tasks_fork_tel.py`:
  - q8 AWQ-W4 c1 and q8 GPTQ-W4 c1 on telecom dev blocks f01–f06, 2 blocks per task, 6 tasks.
  - All 18 Q and BF16 runs are admitted (snapshot 20260930T1319Z) with equal nonces, only dev tasks, and 0 of the 34 holdout tasks (asserted at generation).
  - 2 GPUs per task, pinned to node004/005/007, with the 10% no-op quarantine.
  - Estimate from the gate's telecom throughput: ≈ 11–12 GPU-h per cell × block, ≈ 135–145 GPU-h in total, below the 200 GPU-h budget. analyze_dev now reads `analysis/fork/telecom/`.
- **Draft pre-registration of moderators for the holdout** (FORK_PROTOCOL.md §12). M1, the primary moderator, is the one-sided slope of C on remaining horizon. M2–M5 (BF16 difficulty, persona, task length, fault load) are secondary under Holm. Cut points are fixed on telecom dev.
Evidence: `analysis/fork/analyze_difficulty.py`, `analysis/fork/out/difficulty_20260930T132741Z.{json,md}`, `scripts/a6000/make_tasks_fork_tel.py`,
`/data/ziyangs/cloq_work/queue/todo/fork_tel_q8_*.json`, `docs/insights/FORK_PROTOCOL.md` §12.

## W51 — External-fork analysis script (`analysis/fork/analyze_ext.py`) and the first ALFWorld estimate (2026-09-30)
**TL;DR** `analysis/fork/analyze_ext.py` (registry id `ext_forks`) reproduces the τ² fork analysis on ALFWorld/BFCL forks. On the first finished cell, q8 AWQ-W4 d1 ALFWorld (134 games), G_all is −3.7 [−11.9, +4.5] pp. The τ² W4 pool is +0.2 [−2.8, +3.2] pp, and BFCL is not in yet.
- **First cell, q8 AWQ-W4 d1 ALFWorld (134 games).** 119 divergent (89%): 14 rescues, 19 new damages, 30 both succeed, 56 both fail.
  - A −0.7 [−9.0, +7.5], C +7.5 [−0.7, +15.7], I −3.0 [−13.4, +6.7] pp.
  - Divergence types: command 102, talk→act 17.
  - QQ no-op 16/16.
- **Method.**
  - Imports `effects`, `summarise`, `pooled` and the constants from `analyze_dev.py`: B = 2000, seed 20261001, g_min = 3 pp; G = Y_BQ − Y_QQ; A/C/I on L = 1 − Y.
  - Unit = item; non-divergent items enter with zero effect.
  - Bootstrap: items with replacement within env × category, with draws shared across cells.
  - Pools use equal weights: W4 = GPTQ-W4 + AWQ-W4, stress = GPTQ-W3 + KV4, per environment and across environments. The two families are never mixed.
  - Quarantined dirs, incomplete dirs and exclusions by reason are listed.
  - Provenance: script sha, `analyze_dev` sha, git head, and the sha of every input (search.json, branches.json, effects.jsonl, dev_summary.json, per-state branch files, block trajectory.jsonl). It is idempotent on that fingerprint.
  - The `.md` has a τ² comparison line (W4 divergence rate and G_all per environment).
- **Hand check.** 3 states were recomputed from the raw state and branch files and the block trajectory:
  - talk→act: G −1, A 0, C +1, I −1;
  - command: G +1, A 0, C −1, I +1;
  - command: G 0, A +1, C +1, I −1.
  - In all three, Y_QQ equals the original success, and the controller URLs match the roles.
- **Sign convention fix.** `fork_ext.py` wrote A/C/I on the Y scale; it now uses the loss scale. `effects.jsonl` in dirs written before this commit (alfworld_q8_{awq_w4_d1,gptq_w3}) carry Y-scale A/C/I. `analyze_ext.py` recomputes everything from the branch files and never reads those values.

Evidence: `analysis/fork/analyze_ext.py`, `analysis/fork/out/ext_20260930T131312Z.{json,md}`, `analysis/fork/ext/dev/alfworld_q8_awq_w4_d1_all/`.

## W50 — Restoration moved to the damage regime (GPTQ-W3) and given a behavioural endpoint (2026-09-30)
**TL;DR** The first W40 results (q4 GPTQ-W4 d1, f01–f03) show a design problem. At W4, Q beats BF16 (43.9 vs 33.7; `success_ni` +5.7 pp), so every restoration arm "closes the gap" by losing success. W4 is an equivalence regime, and success recovery is not a meaningful endpoint there.

**Two fixes**
1. **Damage-regime cell.** GPTQ-W3 c1 is added as a restoration base for q4 and q8:
   - the same 17 arms (5 structured, 9 byte-matched random, resid α 0.25/0.5/2);
   - on stress blocks q3–q5, where W3 Q runs and BF16 pairs exist for both models (checked: all completed, nonces match);
   - 34 tasks / 102 runs queued at priority −8 (`pert_q{4,8}_gptq_w3_<arm>_q345`);
   - W3 byte budgets (`budget_w3`) recomputed in every manifest; module sets unchanged.
2. **Behavioural endpoint** in `analysis/fork/analyze_restore_eval.py`:
   - turnover to BF16, and turnover closed = 1 − T(arm, BF16)/T(Q, BF16), with the hierarchical bootstrap;
   - decision-level divergence from BF16, at token level and at action level;
   - the success columns are kept.

**First behavioural reading (q4 W4, 255 units per arm)**
- **Turnover to BF16 is not closed by any arm.** T(Q) = 26.7 %. Turnover closed ranges from −0.12 to +0.10, and every 95 % CI spans 0 (roughly ±0.4).
- **Action-level agreement with BF16 follows the residual dose.** Prefix agreement is:

  | α | 0.25 | 0.5 | 1 (Q) | 2 |
  |---|---|---|---|---|
  | prefix agreement | 0.57 | 0.50 | 0.42 | 0.24 |

  Action divergence closed at α = 0.25 is 0.10 [0.04, 0.19].
- **Layer restoration barely moves it.** Prefix agreement: early 0.42, late 0.45, middle 0.48, attn 0.49.
- **Token level saturates:** 99–100 % of episodes differ from BF16, first at decision ≈ 1.
- **Reading:** at W4, restoring precision delays the first action change but does not return outcomes to BF16's. This is consistent with outcome turnover at the perturbation floor. W3 will show whether restoration recovers success where there is damage.

**Tests:** `tests/test_perturb.py` now has W3 cases (hand count, exactness on an RTN-W3 base, `budget_w3` recorded by the build, random-arm W3 budgets within 0.5 %): ALL PASS.

**Evidence**
- Code and docs: `scripts/a6000/make_tasks_perturb.py --w3`, `cloq/perturb.py` (`wq_bytes`, `budget_w3`), `manifests/perturb/restore_v1/{q4,q8}/*.json`, `docs/insights/PERTURBATION_PROTOCOL.md` §3a/§4a.
- Outputs: `analysis/fork/out/restore_eval_20260930T125027Z.{md,json}`.
- Queue: `/data/ziyangs/cloq_work/queue/todo/pert_q*_gptq_w3_*_q345.json`.

## W39-extfork — Same-state 2×2 forks ported to ALFWorld and BFCL multi-turn; replay gate PASS; development forks queued (2026-09-30)
**TL;DR** Protocol fork-ext-v1 passes the fork-v1 engineering gate on both simulator-free environments (q4 GPTQ-W4 d1 vs BF16, smoke blocks). Neither environment has an LLM user, so these forks remove the user-simulator confound of the τ² forks.
- **ALFWorld:** Q→Q 12/12, B→B 4/4, same-checkpoint 4/4, isolation 4/4, save/load 12/12, re-prefill 12/12 + 12/12.
- **BFCL (r2):** the same counts.
- Every replayed step reproduces the recorded prompt and observations, and backend-state hashes are equal across branches.
- **BFCL r1** failed only on the stored BFCL result record: replayed text replies were rebuilt with `tool_calls []` instead of vLLM's `null`. Prompts and outcomes were identical. It was fixed and re-run before any development fork (r1 is kept).
- **Queued at −8, after the gate:** 36 development tasks.
  - ALFWorld q8 × {GPTQ-W4 d1, AWQ-W4 d1, GPTQ-W3, KV4} (2-GPU).
  - BFCL {q4 (1-GPU), q8 (2-GPU)} × the same 4 arms × 4 categories.
  - All run on the W37/W38 eval blocks; B = BF16; each task searches every item, then runs BB/BQ/QB plus a 10% QQ no-op sample (a mismatch quarantines the task).
  - About 90 GPU-h estimated.
- **Mechanism.**
  - State = the first semantic divergence along Q's trajectory: action class, tool count/name/arguments, or the ALFWorld `act` command after normalisation.
  - The environment is rebuilt by re-executing the recorded prefix through the adapters' own episode code, via a policy hook.
  - Branches BB/BQ/QB/QQ follow fork-v1. Y = the official evaluator: BFCL multi_turn_checker valid, ALFWorld won.
  - Output: G = Y_BQ − Y_QQ and A/C/I in `effects.jsonl`; `branches.json` rows follow the τ² schema.
- **Throughput (q4 gate, 1 GPU, concurrency 8).**
  - ALFWorld: divergence 100% (t* mostly 0); 26 s wall per branch (episodes run 186 s).
  - BFCL: divergence 65%; 6 s wall per branch; search 37 s per item.
- **First development result:** q8 AWQ-W4 d1, ALFWorld, 134 unseen games; 48 min on 2 GPUs; 5.2 s wall per branch at concurrency 12.
  - Coverage: 119 states, 15 without divergence, 0 excluded. QQ no-op 16/16 exact.
  - Summed effects: ΣG −5, ΣA −1, ΣC +10, ΣI −4 on the τ² loss scale L = 1 − Y (corrected in W51; first written on the Y scale as ΣA +1, ΣC −10, ΣI +4). That is 14 rescues vs 19 new damages; G_all −3.7 pp per game.
  - Branch cells mostly agree: 39 states all-fail and 24 all-succeed.
  - One block, no interval. The G/A/C/I reading is left to the main analysis.
- **Gate-state outcomes are not estimates** (12 smoke states each, q4):
  - ALFWorld: ΣG 0, ΣA +1, ΣC +1, ΣI −1.
  - BFCL: all four cells equal in every state.

Evidence: `docs/insights/REPLAY_ACCEPTANCE_ext.md`, `analysis/fork/ext/gate/{alfworld_q4_gptq_w4_d1,alfworld_q4_same_ckpt,bfcl_q4_gptq_w4_d1_r2,bfcl_q4_same_ckpt_r2,bfcl_q4_gptq_w4_d1,bfcl_q4_same_ckpt}/`, `scripts/ext/{fork_ext,make_tasks_extfork}.py`, `scripts/ext/{alfworld_run,bfcl_run}.py` (replay hooks), `scripts/a6000/worker.py::run_fork` (`env` dispatch), queue `todo/fork_ext_dev_*.json`.

## W47 — q4 W×A×KV 2³ closed-loop matrix queued (QuaRot-rotated), A8/SQ anchors; q8 QuaRot validated (2026-09-30 05:00 PDT)
**TL;DR** The three smoke evals finished with no errors and plausible success, so the matrix is queued.

Smoke results, db_match over 85 tasks, run `_q1` (nonce 6d1f0b3e):

| cell | db_match | notes |
|---|---|---|
| A8 | 0.341 | |
| SmoothQuant W8A8 | 0.412 | |
| QuaRot W4A4KV4 | 0.259 | 8/85 episodes hit max_steps; the task took 125 min |

For comparison, the W12 q* references are RTN-W4 0.306, GPTQ-W4 0.408 and the null 0.359.

Queued at priority −8, one task per cell with 3 runs on dev blocks f01–f03 (nonces from `manifests/fork/dev_blocks_v1.json`):
- `a6k2_q4_quarot_w{16,4}a{16,4}kv{16,4}_fdev`: every cell is the QuaRot-rotated model with the online Hadamards on.
  - W16 is the rotated BF16 model; W4 is QuaRot GPTQ.
  - A4 means clip 0.9.
  - KV4 means `CLOQ_KVQ_ROT=qk`, QuaRot format, clip 0.95. KV16 cells run without the KV hook, as in QuaRot, which rotates q/k only when K is quantized.
- Anchors: `a6k2_q4_{aq_a8,sq_w8a8}_fdev`.

Every run pairs with `a6k2_q4_bfpair_f0k` and `a6k2_q4_gptq_w4_d1_f0k` on the same nonces.
- **Rotated control:** W16A16KV16 is not canary-equal to BF16 by construction (rotated weights). Its open-loop floor on q4 is mean |Δlogprob| 0.0065, flip 0.55%. The closed-loop paired contrast "rotated control − BF16" is reported by the analysis.
- **Expect long tails in the A4 cells.** The W4A4KV4 smoke looped at the 32k context in one task for ~90 min.
- **Analysis:** `python analysis/ahook/analyze_wakv.py --snapshot {snapshot}` writes `analysis/ahook/out/wakv_<UTC>.{json,md}`. It is idempotent by input fingerprint and tested with synthetic cells. It reports:
  - per cell: success, cell − BF16 and turnover vs BF16 (fix/break);
  - the factorial main effects and interactions of W, A and KV (s = ±1, effect = ¼Σ s·Y);
  - the additivity gap and the rotated-control contrast;
  - intervals from the analyze_dev hierarchical bootstrap (B 2000, seed 20261001).
- **q8 QuaRot** (H_12 path) had never run on a GPU, so I queued `ahook_validate_quarot_q8` (priority −8.5). It passes; see METHOD_FIDELITY §6. q8 cells are unblocked but not queued.
Evidence: `/data/ziyangs/cloq_work/queue/done/a6k2_q4_{aq_a8,sq_w8a8,quarot_w4a4kv4}.json`, `scripts/a6000/make_tasks.py --only wakv`, `analysis/ahook/analyze_wakv.py`, `analysis/ahook/validate_quarot_q8.json`.

## W49 — P2 fork tasks queued: KV8 core and stress cells (2026-09-30)
**TL;DR** 14 fork tasks queued at priority −15 by `scripts/a6000/make_tasks_fork_p2.py`, estimated at ≈ 86–136 GPU-h in total (under the 150 GPU-h cut, so all stress cells are kept).
- **KV8 core.** q4 and q8 × kvq_int8 (BF16 weights with the KV INT8 hook, same serve_env as the closed-loop runs) on 22 blocks per model: q1–q5 plus f01–f17, every block with an admitted Q run and an admitted nonce-paired BF16 run. 5 tasks per model, groups of 5, 5, 5, 5 and 2 blocks.
- **Stress.** q4 and q8 × gptq_w3 (GPTQ-W3 c1, blocks q3–q5) and × kvq_int4_rot (KV INT4 + Hadamard, blocks q1–q3). Plain INT4 KV has no closed-loop runs, so it is not included. One task per cell, 85 tasks × 3 blocks.
- **Checks before queuing.** Snapshot 20260930T0911Z: all 56 Q blocks and their BF16 pairs admitted, nonces equal (0 mismatches), one checkpoint spec per cell. No new closed-loop Q runs are needed.
- **Settings.** B is plain BF16 and Q the cell's exact serving config (per-role config, W34/W46). Mode "dev": all states frozen before branches, with the 10% QQ no-op quarantine. q8 uses 2 GPUs, pinned to node004/005/007.
- **Estimate basis.** Measured on the running fork_dev tasks, per 5-block task:
  - q4: search ≈ 0.8 h; 266–372 states of 425 units; 60–110 states/h in branches; ≈ 1.0–1.2 GPU-h per block.
  - q8: search ≈ 0.4 h; ≈ 390 states; 57–94 states/h; ≈ 2.0–2.8 GPU-h per block.
  - KV8: q4 22–26 GPU-h and q8 44–62 GPU-h, likely less if INT8 KV diverges less.
  - Stress: 20–48 GPU-h, allowing up to 2× for looping at W3/KV4.
- **analyze_dev.py changes.**
  - It reads `analysis/fork/stress`.
  - It pools only within pre-declared families: W4 (gptq_w4_d1, awq_w4), KV8 (kvq_int8), stress (gptq_w3, kvq_int4_rot), per model and overall. Families are never pooled together.
  - `--cells kvq_int8 / gptq_w3 / kvq_int4_rot` are recognised; with no output yet they exit cleanly.
Evidence: `scripts/a6000/make_tasks_fork_p2.py`, `/data/ziyangs/cloq_work/queue/todo/fork_{kv,stress}_*.json`, `analysis/fork/analyze_dev.py`.

## W46 — Fork serving for activation / SmoothQuant / QuaRot roles (2026-09-30)
**TL;DR** `fork_serve` now matches the W45 hooks, and plain W and KV roles are unchanged.
- **Hook config read by the hooks' own rules.** `CLOQ_AQ_*` (bits, fmt, clip, group, only, had) and `CLOQ_KVQ_*` (ROT 0 / 1 / qk, where qk = QuaRot mode with V rotated offline; FMT; K and V clips).
- **Compile-cache namespace.** It is probed per role by running the hooks' own sitecustomize with that role's serve_env, and run_fork asserts that the cache roots the hooks report equal the recorded namespace. Resulting namespaces: A8 `aq_b8_…`, A4 `aq_b4_…`, SmoothQuant `aq_b8_sym_sq_…`, QuaRot `kvq_b4_rqk_…__aq_b4_…_hquarot_all`, plain `default`, legacy KV unchanged.
- **Per-role refusals.** run_fork applies the checkpoint's `requires_serve_env` / `forbids_serve_env` per role, as run_eval does.
- **W bits** come from the build metadata when the checkpoint spec lacks them.
- **gate_same `foreign_states` mode.** It tests a configuration that has no original run yet: handle cross-check, identical shadow actions, four-branch agreement and budget.
- **Validation.**
  - `fork_accept_quarot_same_q4`: both handles on quarot_w4a4kv4 (W4 A4 K4 V4, same config hash `28a766a57f9da170`, same canary `cc24839800f43b96`). KV coverage is 36/36 decoder layers and A coverage 144/144 linears. Cross-handle regeneration 6/6; 4/4 states have identical shadow actions, all four branches equal and budget consistent.
  - `fork_accept_noop_w_q4` (plain GPTQ, 3 gate states): every gate check passes, including the Q→Q no-op. Hashes are B `efce043e33600dcc` and Q `29ba0176bfc6a4e0`, identical to the running fork_dev tasks.
  - Recomputing the effective config for every recorded role reproduces every plain-W and BF16 hash. KV roles differ only in `hook_version`, because the pyhooks files were edited by W45; their namespaces are unchanged.
- **Found on the way.** My AQ rewrite of the KV coverage parser had dropped the `AttentionType.DECODER` spelling, and the first quarot run failed at startup (coverage 0). Fixed and requeued.
- **Rebuild reproducibility.** The q4 GPTQ checkpoint rebuilt by 4 fork_dev tasks on different nodes has the same sha (`e6c24bc…`).
Evidence: `scripts/a6000/{fork_serve,fork_driver,worker}.py`; `analysis/fork/gate/{q4_quarot_same/gate_same.json,q4_noop_w_w46/gate.json}`;
`/data/ziyangs/cloq_work/logs/tasks/fork_accept_{quarot_same,noop_w}_q4.servers.json`.

## W48 — node001 and node006 runners re-submitted with 8 GPUs (2026-09-30 02:52 PDT)
**TL;DR** The cluster has 48 A6000s (6 usable nodes × 8), not 42. node001 (job 49670) and node006 (job 49642) had been submitted with `--gres=gpu:A6000:4`, so GPUs 0–3 on both nodes were unallocated and idle. node003 GPUs 0 and 7 fail the NVML probe and stay excluded. With the user's approval I re-submitted both runners with 8 GPUs, submitting the new job before cancelling the old one: node001 → job 49727 (00:19), node006 → job 49731 (02:52).
- **Before the node006 restart:** its simulator was marked `draining` in simreg, so no new routes went to it, and I waited until it held no leases.
- **Interrupted tasks** (resume-requeued by the runner): `ext_q8_kvq_int4_alfworld_eval`, `ahook_validate_quarot_q8`.
- **Usable GPUs:** 38 → 46. node002/008/009 remain blocked: another user's CPU-only jobs hold all 48 CPUs on each.
- **Also fixed:** the old node006 runner code could hand a 2-GPU task a single card (see the fork agent's allocation guard).
Evidence: `logs/node_node001_49727.out`, `logs/node_node006_49731.out`, `logs/sim_balancer.log`, `sinfo -O gresused`.

## W45-ahook — Engineering line 1: A8, SmoothQuant W8A8, QuaRot W4A4KV4 fake-quant hooks accepted on q4 (2026-09-30 01:45 PDT)
**TL;DR** Activation fake quantization now runs inside the frozen BF16 vLLM path.
- **Hook** (`pyhooks/cloq_aq.py`): QDQ on the inputs of the fused QKVParallelLinear, MergedColumnParallelLinear gate_up and RowParallelLinear o/down layers, plus QuaRot's online Hadamards.
- **Builders**: SmoothQuant (`cloq/smoothquant.py`) and QuaRot (`cloq/quarot.py`: GPTQ W4, per-head V/O and down_proj Hadamards, H_76 Paley II for 9728).
- **KV**: QuaRot mode added to the KV hook (`CLOQ_KVQ_ROT=qk`, `CLOQ_KVQ_FMT=quarot`; defaults unchanged).

All six acceptance steps pass on q4:
- quantizers, GPTQ solver, smoothing and Hadamards are exact against the official code;
- the A16 hook reproduces the BF16 canary;
- coverage is 144/144 (36 per fused kind; each kind shown live by ablation) plus 36/36 KV layers;
- batch, prefix-cache and chunked-vs-unchunked outputs are identical, and compile-cache namespaces are separate (vLLM's own hash does not distinguish A8 from A4);
- open-loop shift is monotone in precision;
- causality: 4500/4500 prefix positions are unchanged by later tokens.

Mean |Δlogprob| and token flip rate on 150 BF16 decisions:

| config | mean \|Δlogprob\| | flip |
|---|---|---|
| A8 | 0.041 | 2.4% |
| A4, no rotation | 6.7 | 94% |
| SmoothQuant W8A8 (α 0.85 by Pile ppl) | 0.030 | 2.0% |
| W8A8 without smoothing | 0.043 | 2.5% |
| QuaRot W16A16 (floor) | 0.0065 | 0.55% |
| QuaRot W16A4 | 0.28 | 8.7% |
| QuaRot W4A16 | 0.13 | 5.1% |
| QuaRot W4A4KV4 | 0.43 | 11.6% |

Named methods (SmoothQuant, QuaRot) are checked item by item; the deviations are listed in METHOD_FIDELITY §4–5. "A8" is descriptive.
Smoke tasks are queued at priority −7: `a6k2_q4_{aq_a8,sq_w8a8,quarot_w4a4kv4}`, 1 fresh-nonce run each. The W×A×KV 2³ matrix is left to the main session.
- **fork_serve.py caveats:** it reads `CLOQ_ABITS` rather than `CLOQ_AQ_BITS`. Its cache namespace and KV `rot` fields also do not cover AQ or `CLOQ_KVQ_ROT=qk`. Fix these before any A/QuaRot fork.
Evidence: `docs/insights/METHOD_FIDELITY.md`, `analysis/ahook/{unit_tests,validate_a8_q4,validate_sq_q4,validate_quarot_q4}.json`, `analysis/ahook/ckpt_q4_*.quantization.json`, `tests/test_aq.py`, `scripts/a6000/aq_validate.py`; logs `/data/ziyangs/cloq_work/logs/ahook/`.

## W44 — Integrity snapshot covers telecom; restoration analysis registered (2026-09-30 01:10 PDT)
**TL;DR** `analyze_dev.py` (W43) reported that telecom fork units were "not admitted" because `iter_2/integrity.py` scanned only retail and airline, so no telecom run ever entered a snapshot. That would also have silently excluded the telecom holdout.
- **Change to integrity.py:**
  - It now scans telecom too.
  - The expected domain set is {telecom} for `*_tel_*` runs and {retail, airline} otherwise. Before, it only checked that a run had at least 2 domains.
  - Consumers (`common4`, `success_ni`, `prereg_h1_h4`) keep their own DOMS, so their inputs are unchanged.
- **Test snapshot:** 730 runs scanned, 639 frozen, 16 of them telecom. Every run admitted before is still admitted. The 2 domain-set exclusions (`a6000_q{4,8}_null_*`, retail only) were already excluded under the old rule.
- **Registry:** `restoration` now auto-runs `analysis/fork/analyze_restore_eval.py --snapshot {snapshot}` when new pert_* runs land.
Evidence: `analysis/insights/iter_2/integrity.py`, `docs/insights/EXPERIMENT_REGISTRY.json`, W43.

## W43 — Fork development analysis script and restoration-arm table (2026-09-30)
**TL;DR** `analysis/fork/analyze_dev.py` is the daemon's fork analysis. It is CPU-only and idempotent (it skips unchanged input fingerprints) and runs in about 15 s at full development scale.
- **Coverage.** States found per task × block, t* distribution, and the no-op sample pass rate. A fork task with any no-op mismatch is quarantined.
- **Outcomes.** The rescue / damage / both succeed / both fail table, G_all (primary, over the full task pool, with no-divergence units as zero effect), conditional G, and A/C/I exactly as in the review, where L_QQ − L_BB = A + C + I.
- **Intervals.** Hierarchical bootstrap: tasks, then blocks within task; B = 2000, seed 20261001. The draws are shared across cells, so the equal-weight pools per model and overall have valid intervals. g_min = ε = 3 pp flags are reported.
- **Breakdowns.** By divergence type (act→talk, talk→act, tool name, tool args, telecom user-device call, other), with each type's contribution to G_all, and by domain.
- **Exclusions.** Q blocks not admitted in the snapshot, or whose trajectory sha changed, are excluded and listed by reason.
- **Options.** `--cells` filters, and an unknown cell is a no-op with a message.
- **Provenance.** Script sha, git head and snapshot sha are recorded as in success_ni.py.
- **Checks.**
  - Run on the gate outputs (`--include-gate`, written as `dev_gatetest_*`, testing only).
  - 3 states checked by hand (airline 2: G −1, A 0, C +1, I −1; airline 19: 0, −1, 0, +1; retail 101: all 0) and G_all −1/16 = −6.25 pp.
  - The telecom gate block is correctly reported as not admitted (the snapshot does not scan the old `_tel_` runs).
  - No fork_dev task has finished yet.
- **Sibling `analysis/fork/analyze_restore_eval.py`** (W40 arms `a6k2_pert_<m>_<cell>_<arm>_<blk>` vs Q `a6k2_<m>_<cell>_<blk>` vs BF16 `a6k2_<m>_bfpair_<blk>`, nonce-checked):
  - Reports paired success, arm−Q, BF16−Q, arm−BF16, gap closed, and turnover (fix/break) with the same bootstrap.
  - Checked with a stand-in arm (q4 AWQ on f01–f03 as the "arm" of GPTQ): 255 units, success Q 43.9 / arm 37.3 / BF16 33.7 and turnover 20.8, each equal to a direct recount.
  - No arm is admitted yet, so it is a no-op for now.
Evidence: `analysis/fork/{analyze_dev,analyze_restore_eval}.py`, `analysis/fork/out/dev_gatetest_all_*.{json,md}`.

## W42 — Decision: deterministic forks (protocol A); development forks queued (2026-09-30 01:00 PDT)
**TL;DR** The fork engineering gate passed on real divergence states in retail, airline and telecom (W30, `docs/insights/FORK_PROTOCOL.md` §8):
- no-op QQ 20/20 and BB 10/10 bit-exact;
- same-checkpoint and KV16 bridge identical;
- isolation, reordering and a fresh server pair identical;
- budget counters 80/80;
- re-prefill 20/20.

The 10-01 evening decision is therefore taken early, about 1 day ahead: **protocol A (deterministic)**. Protocol B (stochastic) is not needed.
- **Queued:** 16 development fork tasks (`make_tasks_fork_dev.py --write`) at priority −20, ahead of every other science task.
  - q4 and q8 × GPTQ-W4 d1 and AWQ-W4 d1 × 20 shared-nonce blocks (q3–q5, f01–f17), over all 85 tasks.
  - A 10% Q→Q no-op sample; any mismatch quarantines the output.
  - q8 tasks pinned to node004/005/007.
- **Cost:** q4 about 40–60 GPU-h, q8 about 216–256 GPU-h. Expected q8 coverage in 12 h on about 20 GPUs is about 10–12 blocks.
- **Next:** development G/A/C/I and annotation (10-02), then PREREG_FORK_CONFIRM.md and the telecom holdout (10-03).
Evidence: `analysis/fork/gate/`, `docs/insights/FORK_PROTOCOL.md`, queue `todo/fork_dev_*.json`, commit 1cecec0.

## W41 — Telecom user-simulator ToolCall validation errors are not outages (2026-09-30 00:15 PDT)
**TL;DR** `a6k2_q4_tel_awq_w4_fdev1` failed on one "outage". The actual error was a tau2 pydantic `validation error for ToolCall` (arguments=`[]`, not a dict), repeated on both attempts. In telecom the user simulator has tools, and the agent's last decision in that episode was a clean `disable_roaming` call, so the malformed call came from the simulator in the state the AWQ agent led to. It is deterministic, so a plain requeue would fail again.
- **Worker change:** `worker.py` now labels such episodes in `infra_causes.json` via `toolcall_side()`:
  - `user_sim_error` if the agent's last decision parsed cleanly. It stays missing, like any infrastructure episode, in every arm. It does not abort the task.
  - `agent_parse_error` otherwise. That counts as a failure (W27).
- **Unchanged:** the vendored tau2 is not modified, so completed episodes are unaffected.
- **Reporting:** per-arm counts of user_sim_error are reported as a simulator-reliability row. Task resume-requeued.
Evidence: `runs/a6k2_q4_tel_awq_w4_f01/telecom/tau2_results.json` (task `[mobile_data_issue]bad_vpn|…[PERSONA:None]`), `decisions.jsonl` decision 4, `scripts/a6000/worker.py` `toolcall_side`, `logs/tasks/a6k2_q4_tel_awq_w4_fdev1.log` L956–1044.

## W40 — Closed-loop restoration and residual-dose arms on the development blocks (2026-09-30 00:40 PDT)
**TL;DR** After W39-pert verified the `restore` and `resid` checkpoint kinds (bit-exact endpoints, byte-matched random controls, cross-node reproducible cache), I queued 34 eval tasks (102 runs, about 8.7k episodes) at priority −8.
- **Cells:** q4 GPTQ-W4 d1 and q8 AWQ-W4 (the primary dev checkpoints).
- **Arms:** BF16 restored in early / middle / late thirds and in attention / MLP; byte-matched random thirds / attention / MLP, 3 seeds each; residual dose α ∈ {0.25, 0.5, 2}. α = 0 and 1 are the existing BF16 and Q runs.
- **Blocks:** dev blocks f01–f03, so every arm is paired with the Q and BF16 runs on the same nonces.
- **Purpose:** an early closed-loop recovery and dose curve (paper Fig. 2 and Fig. 4) while the fork gate is pending. The fork versions of the same arms follow the gate.
- **Open item:** `run_fork` does not yet apply `derived.canary_checks` (the equals-BF16 / equals-Q canary rules); this was sent to the fork agent. Registry `restoration` now matches `^pert_` / `_resid_`.
Evidence: queue `todo/pert_q{4,8}_*_fdev.json`, `docs/insights/PERTURBATION_PROTOCOL.md`, W39-pert.

## W39-pert — Engineering line 3: restoration and residual-dose checkpoint kinds (perturb-v1); smoke passes (2026-09-30)
**TL;DR** Two new worker ckpt kinds are derived from one cached W4 checkpoint Q:
- `restore`: BF16 restored in early / middle / late thirds, attention-only, MLP-only, or byte-matched random module sets (3 seeds per budget);
- `resid`: W_α = W + α(W_Q − W), α ∈ {0, 0.25, 0.5, 1, 2}, labelled as residual interventions, not bit widths.

**Exactness and reproducibility**
- α = 0 and `all` equal BF16 bit for bit, and α = 1 and `none` equal Q bit for bit: checked by CPU tests and again in every build. The endpoint rule is needed because the literal formula at α = 0 turns −0.0 into +0.0.
- Smoke on the cluster:
  - α = 0 served the BF16 reference canary `c7343b60…`;
  - α = 1 reproduced the files (`e6c24bc2…`) and canary (`a72b3da0…`) of the fork-gate GPTQ Q;
  - the cached q8 AWQ base equals the fork gate's Q (`9ce71e4a…`), which shows GPTQ/AWQ builds are bit-reproducible across nodes.

**Tasks**
- Only 5 smoke tasks were queued (priority −7). No matrices and no forks; forks belong to the main session.
- Manifests for q4/q8 were fixed before any outcome.
- Random arms match structured arms by BF16 parameter bytes within 0.14 % (q4) and exactly (q8); see `docs/insights/PERTURBATION_PROTOCOL.md` §3.

**Evidence**
- Code: `cloq/perturb.py`, `scripts/a6000/derived.py` (hooked into `scripts/a6000/worker.py::build_ckpt` / `run_eval`), `scripts/a6000/make_tasks_perturb.py`.
- Manifests: `manifests/perturb/restore_v1/{q4,q8}/*.json`.
- Tests: `tests/test_perturb.py` → `tests/out/test_perturb.json` (ALL PASS, CPU ~10 s).
- Protocol: `docs/insights/PERTURBATION_PROTOCOL.md`.
- Smoke records: `/data/ziyangs/cloq_work/queue/done/pert_smoke_*.json`, logs `/data/ziyangs/cloq_work/logs/tasks/pert_smoke_*.log`, `/data/ziyangs/cloq_work/ckpt_cache/{base/*/cache.json,registry/,registry.log}`, `analysis/determinism/canary_{derived_*,agentq_*}_*.json`.

**Smoke results**

| task | node | ckpt | equals | content sha | canary | episodes (20 det tasks) |
|---|---|---|---|---|---|---|
| `pert_smoke_q4_gptq_resid_a0` | node005 | resid α=0 on GPTQ-W4 d1 (base built 406 s, cached) | bf16 | 37749b09… | c7343b60 = BF16 reference ✓ | build+serve only |
| `pert_smoke_q4_gptq_resid_a1` | node007 | resid α=1 | q; files = cached Q = fork-gate Q e6c24bc2… | b22e0b7c… | a72b3da0 = fork-gate Q canary ✓ | build+serve only |
| `pert_smoke_q4_gptq_resid_a0.5` | node005 | resid α=0.5, eff_alpha 0.499996 | — | 33e473c3… | 144dd842 (tag ref) | retail 4/10, airline 2/10 |
| `pert_smoke_q4_gptq_restore_late` | node007 | restore late (84 linears) | — | 9c6f25ce… | fb88228c (tag ref) | retail 4/10 (1 max_steps), airline 5/10 |
| `pert_smoke_q8_awq_restore_rand_attn_s1` | node007 | restore rand_attn_s1 (61 linears) on AWQ-W4 d1 (base built 666 s, files = fork-gate q8 AWQ Q 9ce71e4a…) | — | f456d038… | 635eb383 (tag ref) | build+serve only |

**Derived build cost.** 8–24 s each on CPU (q4 / q8), plus serving. The base cache holds 7.5 GB (q4 GPTQ) + 16 GB (q8 AWQ).

**Open for the main session**
- `run_fork` builds these kinds unchanged, but does not yet apply `derived.canary_checks`.
- For restoration forks, use `resid_a1` / `restore_none` as the Q branch so Q and every arm share one cached base.
- KV-side K-only / V-only restoration is config-only via `CLOQ_KVQ_WHICH` (protocol §2.3).

## W38 — Simulator-free breadth on BFCL and ALFWorld (2026-09-30 00:10 PDT)
**TL;DR** The user asked for more cost-effective runs beyond τ². I queued 32 more external eval tasks at priority −10, behind W37's eval. None needs the user simulator.
- **Model scale and MoE:** q14 / q30a3 / q32 × {BF16, GPTQ-W4 d1, AWQ-W4 d1} × {BFCL, ALFWorld}.
- **Method, dose, recalibration and KV axis on q8:** {RTN-W4, GPTQ-W3, GPTQ-W4 d2, KV8, KV4} × both benchmarks.
- **q4:** the same four stress/KV arms, BFCL only.
- **Cost:** about 90 GPU-hours. It fills the gaps behind the fork line.
- **Why:** it tests whether the τ² picture (W4 small aggregate change but real turnover, damage at W3 and KV4, lottery absent) holds on two benchmarks with a deterministic, non-LLM environment. That removes the user-simulator confound reviewers will raise.
- **Next:** the same-state fork protocol on ALFWorld and BFCL (deterministic environments, no simulator), assigned to an engineering agent. It will be used only if it passes the same replay gate as τ².
Evidence: `scripts/ext/make_tasks_ext.py` (eval2), queue `todo/ext_*_eval.json`.

## W37 — External-benchmark full eval queued; long_context overflow decision (2026-09-29 23:50 PDT)
**TL;DR** After W36-ext passed dev and smoke, I queued the full eval split: 12 simulator-free tasks at priority −9, behind the fork line, covering q4 and q8 × {BF16, GPTQ-W4 d1, AWQ-W4 d1} × {BFCL multi-turn 788 items, ALFWorld unseen 134 games}.
- **Cost:** about 1.8 GPU-hours per checkpoint, or about 11 GPU-hours in total. It fills cards that would otherwise wait on the simulator.
- **Decision:** BFCL long_context keeps the frozen served context (33,792 tokens). An overflow is scored as a failure identically in every arm, and the overflow rate is reported per arm as its own column. Enlarging the context would change the served config shared with τ².
- **Caveat:** q4 ALFWorld is near the floor (10–15% on smoke). For ALFWorld, q8 is the primary comparison and q4 is reported only as a floor case.
- **Disclosure:** the ALFWorld prompt went through five versions on valid_seen dev games (W36-ext); this goes in the appendix.
Evidence: `scripts/ext/make_tasks_ext.py` (eval mode), queue `todo/ext_q{4,8}_*_eval.json`, W36-ext.
## W36-ext — Engineering line 2: BFCL multi-turn and ALFWorld adapters (no user simulator); dev validated, q4 smoke done (2026-09-30)
**TL;DR** Both benchmarks run through the queue on the same served agent as tau2 (worker.py eval task + `"env"` field; the checkpoint specs are unchanged, and the BF16 canary is checked). Deterministic re-run: 12/12 BFCL and 6/6 ALFWorld dev items are token-identical. q4 smoke pass counts, BF16 vs GPTQ-W4 d1 (keep categories separate; never average across benchmarks):
- BFCL: base 4/10 vs 3/10; miss_param 2/10 vs 2/10; miss_func 2/10 vs 2/10; long_context 2/10 vs 2/10.
- ALFWorld (valid_unseen smoke): 1/12 vs 2/12.

The smoke subsets are far too small for any comparison; this is a plumbing check only.
- **Versions.**
  - BFCL: bfcl-eval 2026.3.23 (wheel sha256 3bb6dfa5…). Its `BFCL_v4_multi_turn_*` files are the v3 multi-turn categories; per-file sha256 are in the manifest. Venv: `cloq_work/envs/bfcl` (+ soundfile, a missing qwen-agent import).
  - ALFWorld: alfworld 0.4.2 and textworld 1.7.0. Data: json_2.1.1 json/pddl plus the tw-pddl 2.1.2 zips; zip sha256 are in the manifest, and the MRCNN detector is not downloaded (591 MB on disk). Venv: `cloq_work/envs/alfworld`.
  - Frozen package lists: `env/ext_{bfcl,alfworld}.freeze.txt`.
- **Manifests (committed before any model run; selection by sha256(salt+id) only).**
  - `manifests/bfcl/bfcl_mt_v1.json`: 4 categories × 200 items. dev 3/category, smoke 10/category, eval = 197/category (smoke ⊂ eval).
  - `manifests/alfworld/alfworld_text_v1.json`: dev = 1 valid_seen game per task type. eval = the official eval_out_of_distribution split (valid_unseen, 134 games, same filter as AlfredTWEnv). smoke = 2 per task type (12).
- **BFCL adapter** (`scripts/ext/bfcl_run.py`).
  - Inference runs BFCL's own `inference_multi_turn_FC` loop: 20 steps/turn, then force-quit; miss_func holdout injection is done by the loop.
  - The handler is `OpenAICompletionsHandler` FC, with overrides for transport and logging only.
  - Scoring uses the official per-entry evaluator (`_evaluate_single_multi_turn_entry` → `multi_turn_checker`), unchanged.
  - Decoding is the frozen agent decoding from `frozen_v0` (greedy, seed 0, max_tokens 1024), with top-5 logprobs.
- **ALFWorld adapter** (`scripts/ext/alfworld_run.py`).
  - Environment: the official TW env, built as AlfredTWEnv.init_env builds it for eval.
  - Budget: 50 env actions and 50 decisions.
  - Scoring: `infos['won']`.
  - Interface: one native tool `act(command)`. Admissible commands are never shown to the agent; they are logged per action as the legal-action check.
  - **Prompt v5 frozen after 4 dev-only revisions** on valid_seen (disjoint from eval):
    - v1: commands were called as tools.
    - v2: the example `act(command=…)` was typed as text.
    - v3: the engine's locality rule was not stated.
    - v4: the raw-JSON example was typed as text.
  - Dev pass counts for v1–v5: 1, 0, 0, 1, and 3 of 6. The prompt-tuning history is part of the record.
- **Run layout.** `runs/<run_id>/<domain>/` has the run_arm file set. `decisions.jsonl` records, per decision: messages, tools, server prompt ids, completion ids, logprobs/margins, parsed actions, legality and the observations. `trajectory.jsonl` holds per item the full messages, the official evaluator output and the wall time. Domains are `bfcl_{base,miss_param,miss_func,long_context}` and `alfworld`, and run ids use the `ext_` prefix (not `a6k2_`).
- **Runtime** (q4, one A6000, 8 items concurrent × 4 categories in parallel).
  - BFCL: the 40-item smoke took about 150 s wall, i.e. ≈4 s/item amortised. Per-item latency averaged 50–73 s, with a max of 129 s.
  - ALFWorld: 12 games in 232–262 s wall, i.e. ≈20 s/game amortised. Per-game latency averaged 80–101 s, with a max of 186 s.
  - Task overhead: server start plus canary ≈1–2 min; a GPTQ build adds ≈6–8 min.
  - Full-eval estimate per checkpoint: BFCL 788 items ≈ 1 GPU-h; ALFWorld 134 games ≈ 0.8 GPU-h.
- **Caveats.**
  - BFCL long_context: 3/10 smoke items (and 1/3 dev) hit the served context (33,792 tokens; prompt > 32,768 with max_tokens 1024). These are recorded as `context_overflow` and scored as BFCL inference errors, identically for all arms. A larger `max_model_len` would change the served config, so that decision belongs to the main session.
  - ALFWorld q4 success is low (≈10–15% on unseen smoke), and about 30% of decisions carry no tool call.

Evidence: `scripts/ext/{common,bfcl_run,alfworld_run,make_manifests,make_tasks_ext,compare_runs}.py`, `scripts/a6000/worker.py` (`env` field), `manifests/{bfcl,alfworld}/`, `analysis/ext/rerun_*.json`, `analysis/ext/smoke_q4_summary.json`, `runs/ext_q4_*_{smoke,dev*}/`, queue `done/ext_q4_*.json`.

## W30 — Same-state fork pipeline built; engineering gate passed (deterministic forks) (2026-09-29/30)
**TL;DR** fork-v1 is implemented and passes every gate check, so development forks use deterministic protocol A.
- **Mechanism.** A fork state is Q's saved history before decision t. tau2 rebuilds the DB, the telecom device DB and the user-simulator
  state by strict replay; the simulator has no hidden state. The current action is forced through the normal orchestrator
  step. Step and error counters are restored (tau2 would reset them to 0). Each role gets its own vLLM server and
  effective serving config.
- **Evidence.**
  - Restored-history prompts equal recorded server prompts at 3,492/3,492 decisions.
  - Rebuilt GPTQ/AWQ checkpoints regenerate recorded decisions (16/16, 16/16).
  - 20/20 Q→Q and 10/10 B→B no-ops are bit-exact (prompts, messages, DB/device hashes, termination, rewards, counters), including telecom dual control and too_many_errors endings.
  - Same-checkpoint four-branch agreement holds 6/6, and 4/4 under the hooked KV config and the KV16 bridge.
  - Reversed and concurrent runs are identical (10/10, incl. 3 telecom; 14/14 branches identical across two server launches). Budget accounting holds in 80/80 branches. Re-prefill after a switch holds 20/20.
- **Fixes during the gate.**
  - The B→B comparator missed `official_reward` in old runs; it is now recomputed from reward_info (validated 335/335) and the verdict was recomputed offline, keeping the old one.
  - W34: run_fork ignored serve_env/serve_extra. Fixed with per-role configs, an effective-config hash, W/A/K/V bits, hook version, cache namespace and hook coverage (36/36 layers).
- **Annotation (review rounds 2–3).** `cloq/fork_annotate.py` records per-state events with raw records and ok/violation/needs_review statuses, correction evidence, per-assertion and per-DB-path requirements, and a blinded review export.
- **Throughput.**
  - q4 1-GPU B+Q: 18.6 s per branch at concurrency 8.
  - q8 2-GPU: ≈ 47 s per retail branch and ≈ 83 s per telecom branch.
  - The simulator is not binding (14.7 req/s observed over 5 replicas at partial load).
- **Development cost.** ≈ 260–320 GPU-h for q4/q8 × GPTQ-W4/AWQ-W4 × 85 tasks × 20 blocks, of which q8 is about 80%. The generator is proposed, not queued.
- **Follow-ups.** Per-role serving configs (W34), derived-checkpoint canaries, and an allocation guard (node006's old runner ignores task gpus) are done.
Evidence: `docs/insights/FORK_PROTOCOL.md` §8–§11; `analysis/fork/gate/{cpucheck_q4,cpucheck_q8}.json`,
`analysis/fork/gate/{q4_gptq_w4_d1,q8_awq_w4,q4_kvq_int4_rot}/gate.json`, `analysis/fork/gate/{q4_same_ckpt,q4_kvq_same,q4_kv16_bridge}/gate_same.json`,
`*/annotations.jsonl`; code `cloq/fork.py`, `cloq/fork_annotate.py`, `scripts/a6000/{fork_driver,fork_serve,make_tasks_fork_dev,worker}.py`;
logs `/data/ziyangs/cloq_work/logs/tasks/fork_*.{log,servers.json}`.

## W34-infra — Multi-replica user simulator: instance registry, drain-then-add, 6 replicas live (2026-09-30)
**TL;DR** The review finding on e72b93e was confirmed in code. The balancer read only port 8000 and keyed replicas by node name. The runner started exactly one simulator.
- **What changed:**
  - Every replica is now in a registry: `cloq_work/sims/<node>-<port>.json`, holding URL, GPUs, canary, no-op check, throughput, owner, state and health.
  - Routing is per instance URL, using per-instance waiting/running/KV load.
  - Routes still change only at run start. A route to a dead replica is moved at once; otherwise there is a 15-min hold per node, and the anti-herding rule and atomic replace are unchanged.
  - Leases keep a draining replica up until its clients finish.
  - `noderunner --sims N` starts N replicas on NVLink pairs at ports 8000+k, with a port-collision guard, heartbeat, and a `DRAIN.<node>` flag.
  - A queue task of kind `sim` adds a replica to a running runner without restarting it. That runner already keeps upper pairs for 2-GPU work, so the pair empties as its valid tasks finish.
- **node004-8007 is live (GPUs 6,7, job 49671, no restart):**
  - canary `9a594b881feb752a`, equal to the reference;
  - 4/4 identical answers to the same requests as node004-8000, both when idle and under 32-way concurrent load;
  - 377.6 and 618.4 generated tok/s at 16 and 32 concurrent requests;
  - 8 live run leases by 22:35.
- **Replicas now:** 6 (12 GPUs), all with the same canary.
- **7th replica (node005):** queued, then deferred by the main session. Simulator waiting is 0–6, below the add rule (waiting > 30 for 30 min).
- **Disruption:** no runner restart, no Slurm submit or cancel, and no interrupted episodes.

Evidence:
- Code: `scripts/a6000/{simreg,worker,noderunner,sim_balancer,gputop}.py`, `scripts/a6000/gpumon.sh` (commits d8a7d27, 51d5cc7, f7f4e9c).
- Dry run, 17/17 checks: `scripts/a6000/dryrun_simreg.py`, `/data/ziyangs/cloq_work/logs/w34_infra_dryrun.txt`.
- Registry: `/data/ziyangs/cloq_work/sims/`.
- Rollout logs, all under `/data/ziyangs/cloq_work/logs/`: `sim_instances.log`, `w34_node004-8007_{noop_underload,tp32}.json`, `sim_balancer.log`, `node_node004_49671.out`.
- Plan: `docs/insights/RESOURCE_PLAN.md` (inventory and rollout record).

## W35 — Old line stopped; experiment registry, automatic analysis daemon, board main-line view (2026-09-30)
**TL;DR**
- **Old line stopped.** 10 running old-line tasks (high-dose Gaussian redos, W3 on q32/l8, q30a3 k=3, old telecom BF16) were stopped through their run processes (clean server shutdown) and 51 queued old-line tasks moved to `queue/deferred/`. Finished episodes are kept and resumable.
- **New batch queued (priority −7/−6, 26 tasks, 74 runs).** KV8 Q blocks on the development nonces, plus telecom development blocks (80 dev tasks, holdout untouched) for BF16 / GPTQ-W4 d1 / AWQ-W4 d1 on 6 nonces.
- **Experiment registry.** `docs/insights/EXPERIMENT_REGISTRY.json` records each experiment's role (main / support / background / engineering / retired), its fit to the main line (critique), task patterns, and analysis.
- **Analysis daemon.** `scripts/a6000/analysis_daemon.py` runs on the login node, niced. Every 10 min it counts progress and runs CPU analyses when their data are complete, on a fresh gated snapshot; GPU analyses stay single-GPU queue tasks. It writes `analysis/status/board_feed.json` and `analysis_runs.jsonl`.
- **Board.** The new "Main line & experiments" tab groups experiments into running / waiting / not started / completed / retired, synced every 30 min.
Evidence: `docs/insights/EXPERIMENT_REGISTRY.json`, `scripts/a6000/analysis_daemon.py`, `scripts/a6000/make_tasks_fork_dev2.py`, `queue/deferred/`.

## W34 — Executor instructions (§20) adopted: fork config bug, simulator registry, three engineering lines (2026-09-30)
**TL;DR** External review of e72b93e, verified in code before acting:
- **Fork config bug.** `run_fork` launches B/Q servers with `env` + GPU_UTIL only and ignores the task's `serve_env`/`serve_extra`, so KV/A forks would silently run unquantized Q servers. No such fork has run yet. The fork agent will fix per-role configs, effective-config hashes, hook coverage counts and acceptance before any P2 fork.
- **Simulator routing.** `sim_balancer.py` route writes are now atomic. Multi-replica support (instance registry, runner N simulators, drain-then-add rollout, no all-node restart) is its own infrastructure line.
- **GPU sharing.** Two independent workers per GPU are unsafe (`stop_server` kills all GPU processes); only one fork worker hosting B+Q per card.
- **Counting.** Replicate blocks are complete shared-nonce sets (3 + 17 = 20), not the 36 queue jobs.
- **Engineering lines started:** (1) A8 → SmoothQuant → QuaRot fake-quant hooks with fidelity checks; (2) BFCL multi-turn + ALFWorld adapters (no user simulator); (3) layer/module restoration (byte-matched random controls) + α residual-dose checkpoints; (4) multi-simulator infrastructure.
- **Acceptance:** evening of 10-02; anything not accepted goes to Limitations.
Evidence: `scripts/a6000/worker.py` (run_fork), `scripts/a6000/sim_balancer.py`, `docs/EXECUTION_PLAN_20260930.md`.

## W33 — Paper rewritten as "Tracing the Consequences of Quantization in Closed-Loop Agents" (2026-09-30)
**TL;DR** `paper/latex/` is rewritten to the Round-3 target. The question: on identical interaction histories, which task consequences do quantization-induced local action changes cause, and do they come from the current action, the continuation controller, or their interaction?
- **Structure:** Intro; Related work (Dutta, Flat Score, AgentProv, Model Equality Testing, Replay Gap, Dynamic MP Routing, agent-eval noise); Run conditions and measurement definitions; the same-state four-branch design (G = h − b, A/C/I, G_all, replay gate, stochastic fallback, paired-block inference, fixed-pool vs new-task); Consequence composition and mechanism annotation; Telecom holdout confirmation (g_min = ε = 3 pp); Discussion (pending); Limitations.
- **Placeholders:** all fork results are `\pending{}` (136 rendered).
- **Figure 1:** a TikZ schematic, with no data in it.
- **Appendix:** the P0 audit (H3 original vs corrected, simulation, crossed variance components, measurement fixes); the iter-4 prereg record (non-replication); the random-perturbation fingerprint (exploratory, post-hoc); the turnover table; determinism.
- **Build:** 13 pages; main text 8 pages; no errors, undefined references or undefined citations.
- **Citations:** 6 bib entries added from `references_new.bib`, with arXiv ids checked.
- **Other files:** the old sections are moved to `sections/old/`, and the checklist is updated (A1–A3, B1, B5, B6, C2, C3, D).
Evidence: `paper/latex/REWRITE_NOTES.md` (source of every number, open placeholders), `paper/latex/main.tex`, `paper/latex/sections/*.tex`, `paper/latex/main.pdf`, `paper/latex/responsible_nlp_checklist.md`.

## W32 — Review round 3: paper fixed as "Tracing the Consequences of Quantization in Closed-Loop Agents" (2026-09-30)
**TL;DR** The goal is a complete, submittable paper; results set claim strength, not continuation. Decision points: 10-01 (deterministic vs stochastic forks vs engineering) and 10-03 (measurement-paper freeze if restoration is unverifiable). Stochastic estimand G = E[Y_BQ] − E[Y_QQ] with nested repeats, no no-op subtraction. Annotation: automatic events + LLM labels with evidence locations + ~80 human-blinded states (~20 double). Blocks sized by simulator throughput. Telecom holdout = independent cross-domain confirmation with a pre-mapped taxonomy. LaTeX rewrite starts now.
Evidence: `docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md` (Round 3).

## W31 — Review round 2: old main line retired; fork deliverables and annotation fields defined (2026-09-30)
**TL;DR** "Success-equivalent, behaviourally distinct" retired. The random-perturbation fingerprint is kept as an exploratory, post-hoc finding; no W4 fingerprint was detected. Main line: consequences and sources of quantized action substitutions on identical histories. The BF16 action is only a reference; defects are judged from tool preconditions, task requirements, authorisation and state. No research gate on the sign of G. The development evidence gate needs coverage, consequence composition, G and A/C/I with intervals, process evidence and precision. Per-fork annotation: defect, correction, requirements satisfied. Freeze the tool-type table. Report the fixed pool and new tasks separately. Our addition: telecom dev split (80 tasks) joins development forks.
Evidence: `docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md` (Round 2), `docs/insights/STORYLINE_v6.md`.

## W29 — P0 statistics and measurement fixes; corrected H3; audit record (2026-09-30)
**TL;DR** The review's §B/§C issues were all confirmed in the code; fixes were implemented as new scripts and outputs. The original results are kept as history, and everything below on the 28 runs is a corrected (post-hoc) re-analysis.
- **H3.** The pre-registered test was invalid: its true-pair scaling rejects 33–42% of exchangeable null datasets. The corrected test (pairing-invariant pooled scale) is calibrated: 4.4% ± 0.3% against a nominal ≤ 4%.
  - Corrected H3: pooled F 0.136, p 0.013 (was 0.260, 0.0008); RAND 0.283, p 0.028; q4 0.088, p 0.125; q8 0.184, p 0.049.
  - RECAL alone: F 0.025, p 0.30 (was 0.118, p 0.005). Random checkpoints carry 90% of the pooled F.
  - The quantizer fingerprint (STORYLINE_v6 B3) is not detected.
- **p1/H1 crossed nonce model.** H1 p is unchanged (0.744, exact invariance). φ is 0.33–0.47 against the pre-registered 0.40. Crossed variance components for q4: checkpoint 3.69 pp, residual 2.62 pp; method not estimable (1 df, negative moment estimate).
- **Success non-inferiority.** The scaffold is ready: ε = 3 pp (5 pp sensitivity), TOST, D/V U-statistics with the Hamming cross-check, and task-clustered generalisation. Real mode waits for `bfpair`; the dev mode uses stand-ins and is not a result.
- **Measurement.**
  - `p_act` bounds and a missing flag: means move < 0.001.
  - `topk_kl` renamed to `approx_topk_kl`; a coarse-grained exact-KL lower bound was added.
  - `name_mass` is now a proxy with measured error terms; `confirm_bw` is renamed `confirm_request_proxy` (values unchanged).
  - Tool-type table from the tau2 decorators: the write regex misses 5 of 6 telecom write tools.
  - Endpoint naming: DB success for retail/airline; tau2's official deterministic basis success for telecom.
  - `nl_judge` is unused in scoring and not thread-safe; left unchanged.
- **Act/talk "blurring" (B5).** Mostly a selection effect: the q4 RTN P(act|talked) rise 0.014 → 0.088 is matched by a sign-symmetric null (0.080). The directional part is small (unconditional ΔP(act) −0.10 to +0.005 on q4/q8) and random controls are as large or larger.

Evidence: `docs/insights/METHODOLOGY_REVISION.md`; `analysis/insights/iter_4/{h3_corrected,p1_crossed,success_ni,act_talk_selection,tool_types}.py`; `analysis/insights/iter_4/out/{h3_corrected,h3_corrected_sim*,p1_crossed,success_ni_DEV,act_talk_selection,tool_types_features}_20260930T0044Z.json`, `out/tool_types.json`; `analysis/openloop/a6k2/*/topk/*.v2.json`; `scripts/a6000/openloop_topk.py` (`--schema 2`), `analysis/insights/iter_4/common4.py`, `cloq/metrics.py`; snapshot `analysis/insights/iter_3/out/snapshot_live_20260930T0044Z.json`.

## W29a — Fork development blocks queued; Llama deprioritised (2026-09-30)
**TL;DR** Primary fork checkpoints fixed by a pre-stated completeness rule (most existing fresh-nonce draws; tie → lowest calibration draw): GPTQ-W4 d1 and AWQ-W4 d1 (calibration c1) on q4 and q8. Development blocks: existing q3–q5 + 17 new nonces f01–f17 (sha256-derived, disjoint from every used nonce) = 20 blocks; queued Q runs for the 4 cells and BF16 on the same nonces (36 tasks, 102 runs, priority −8), which also give paired Q−B success. 28 Llama (l8) tasks moved +40 per the external review's priorities. Workstreams launched: P0 statistics/measurement fixes (→ W29) and fork replay engineering with the 10-01 gate (→ W30).
Evidence: `manifests/fork/dev_blocks_v1.json`, `queue/todo/a6k2_{q4,q8}_{gptq_w4_d1,awq_w4,bfpair}_fdev*.json`.

## W28 — External review (GPT-6.1) adopted: fork mechanism study; P0 fixes; BF16 pairing (2026-09-30)
**TL;DR** New main line: same-state 2×2 fork (current action B/Q × continuation B/Q) to separate current-decision and subsequent-execution effects of quantization; mechanism/measurement paper, no repair method this round; conformal out of the core. Verified in code before adopting: H3 `split_cos` scales by true-pair differences (permutation invalid as implemented), p1 nonce term includes shared nonce main effect (H1 p-value unaffected, φ estimate biased), `p_act` treats tool-start outside top-20 as 0, q8 AWQ d3 +5.29 pp. Queued `a6k2_{q4,q8}_bfpair` (BF16 on the W4 fresh nonces q1–q5; nonces verified from environment.json) for paired non-inferiority. Thresholds 3 pp (g_min, ε, equivalence). Replay go/no-go 10-01 evening; telecom holdout (34 tasks, untouched) for confirmation.
Evidence: `docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md`, `queue/todo/a6k2_{q4,q8}_bfpair.json`.

## W28 — Simulator rebalance (2026-09-30 ~03:35 UTC)
**TL;DR** node004 and node006 simulators had 102 and 110 requests waiting (node004 served node005 via `USER_BASE.node005`; node006 served node003 via the runner's CLOQ_USER_BASE) while node001/005/007 simulators were idle. Removed `USER_BASE.node005` (node005 back to its own simulator) and set `USER_BASE.node003` → node007. Applies to newly started tasks; same model and canary on all simulators.
Evidence: `queue/USER_BASE.node003`, `gpumon/node00{4,6}.jsonl`.

## W27 — Llama multi-tool-call parse errors are agent failures, not outages (2026-09-30)
**TL;DR** `a6k2_l8_gauss0.03_s2` failed on 1 "outage": vLLM's llama3_json parser rejects a turn with several tool calls ("This model only supports single tool-calls at once!"). That is the agent's own output, so like context overflow (W10) it now counts as a task failure: worker labels it `agent_parse_error` in infra_causes.json (not an outage, no task abort) and `iter_2/common.py` relabels `AGENT_SIDE = {context_overflow, agent_parse_error}` as failures, keeping the true cause as the termination reason. Task resume-requeued.
Evidence: `scripts/a6000/worker.py` (W6/W10 guard), `analysis/insights/iter_2/common.py` (AGENT_SIDE), `runs/a6k2_l8_gauss0.03_s2/airline/tau2_results.json` task 14.

## W26 — Storyline v6 (two lines) and review packet update (2026-09-30)
**TL;DR** `docs/insights/STORYLINE_v6.md` records Line A (checkpoint lottery, refuted by the pre-registered H1/H2, W25) and Line B (success-equivalent but behaviourally distinct: B1 success equivalence, B2 turnover above the floor, B3 persistent fingerprint (confirmed), B4 fingerprint generic to fixed perturbations, B5 what changes, B6 damage regime; open B7 "does it matter"). `docs/REVIEW_PACKET.md` updated for the external reviewer (new §4b pre-registered result, both lines, experiment record, revised questions).
Evidence: `docs/insights/STORYLINE_v6.md`, `docs/REVIEW_PACKET.md`.

## W25 — Pre-registered confirmatory result (2026-09-30)
**TL;DR** Ran `prereg_h1_h4.py` once on snapshot 20260930T0044Z (all 28 confirmatory runs admitted). H1 recalibration lottery NOT supported (pooled φ 0.40, p 0.74; q4 φ −0.30, q8 0.94). H2 net effect replicating across nonces NOT supported (r 0.42, p_holm 0.42; q4 r −0.52, q8 0.94). H3 split-task behavioural fingerprint SUPPORTED (F_split 0.26, p_holm 0.0024; q4 0.19, q8 0.33). Random fixed checkpoints have fingerprints at least as persistent as quantizers (same-checkpoint cosine RAND 0.51/0.77 vs RECAL 0.32/0.38). H4 not detected (−0.83 [−7.1, 4.2]). Secondary: new q4 recalibrations d3/d4 all land at net +1.5 to +3.9 pp; including d1/d2, checkpoint SD 3.65 pp vs nonce 2.51 pp, method ≈ 0. Per PREREG §6: the checkpoint lottery is dropped as a headline (the exploratory q4 d1 vs d2 gap did not replicate on new checkpoints); the paper leads with turnover above the numerics floor plus a persistent behavioural fingerprint that is generic to fixed weight perturbations.
Evidence: `analysis/insights/iter_4/out/prereg_h1_h4_CONF_20260930T0044Z.json`, `analysis/insights/iter_3/out/snapshot_live_20260930T0044Z.json`, `docs/insights/PREREG_iter4.md`.

## W24 — Pre-registration amendment 1 (2026-09-30)
**TL;DR** PREREG_iter4 §7 amendment 1 records the 18 implementation clarifications (A1–A18) made while writing the confirmatory script on stand-in checkpoints, before any confirmatory outcome was computed or inspected. Most important: the confirmatory set is 14 checkpoints × 2 draws = 28 runs (the original text miscounted "40"). No hypothesis, statistic, unit, α or Holm family changed. New prereg sha256[:16] a991e2e5ca2d6098 (original 0d5e8385c911824f), updated in `prereg_h1_h4.py`.
Evidence: `docs/insights/PREREG_iter4.md` §7, `docs/insights/PREREG_iter4_analysis.md`, `analysis/insights/iter_4/prereg_h1_h4.py`.

## W23 — Confirmatory analysis script for PREREG iter4 (2026-09-29)
**TL;DR** `analysis/insights/iter_4/prereg_h1_h4.py` implements PREREG_iter4 §2–§4:
- **Primary.** H1 (φ, P1 estimator unchanged, B = 5000), H2 (r, exact within-model relabelling) and H3 (F_split, 100 task halves, 12 P2 features), with Holm over H1–H3.
- **Secondary.** H4 two-sided with a CI; per-model and per-domain versions; max_steps and overflow sensitivity; variance components.
- **Guards.** The script asserts PREREG sha16 0d5e8385c911824f. It refuses unless all 28 confirmatory runs are admitted with their registered nonces, the script was committed before the snapshot, no earlier snapshot already admitted them, and the analysis has not run before. `--deadline-mode` is accepted only on or after 10-05.
- **Development.** Built only on non-confirmatory stand-ins (`--dev`). No confirmatory outcome was opened. Stand-in Δ matches P2 exactly, and the permutation tests are calibrated on synthetic nulls.
- **Ambiguities.** A1–A18 need to be logged as §7 amendments. The most important is A1: §1 says 40 runs but enumerates 28. A16: amending §7 changes the hash, so `PREREG_SHA16` must be updated in a commit before the confirmatory snapshot.

Evidence: `docs/insights/PREREG_iter4_analysis.md`, `analysis/insights/iter_4/prereg_h1_h4.py`, `analysis/insights/iter_4/out/prereg_h1_h4_DEV.{json,log}`.

## W22 — Iteration-4 pre-registration (2026-09-29)
**TL;DR** Pre-registered H1 (recalibration lottery, φ>1), H2 (net effect replicates across nonces), H3 (split-task fingerprint), Holm over H1–H3; H4 (quantizer vs random coherence) secondary. Confirmatory units: GPTQ/AWQ-W4 d3/d4 and Gaussian k=1 seeds s2/s4/s5 on q4/q8 × nonces q1/q2 (40 runs). Written while these runs were running; no closed-loop outcome of them had been analysed (q4 churnctl_k1_s2 had finished, not opened). sha256[:16] of the registered file: 0d5e8385c911824f.
Evidence: `docs/insights/PREREG_iter4.md`.

## W21 — Review packet, v5 review, sampling baseline pulled (2026-09-29)
**TL;DR** Storyline v5 reviewed: 2.5/5 as-is, 3.5 if reframed around the checkpoint lottery with confirmatory recalibration draws (`paper/review_storyline_v5.md`). The review found the W19 sampling baseline mis-designed (vLLM re-seeds every request with the same seed, so a fixed seed acts as a fixed perturbation); `a6k2_q4_samp_T*` moved to `queue/deferred/` before any run started. All results, open-loop outputs, determinism canaries, calibration manifests and docs committed; analysis caches git-ignored. `docs/REVIEW_PACKET.md` is a self-contained entry point for external reviewers (methodology, results, reviews, open questions), linked from README.
Evidence: `docs/REVIEW_PACKET.md`, `paper/review_storyline_v5.md`, `queue/deferred/a6k2_q4_samp_T{0.2,0.5,0.8}.json`.

## W20 — E4-2 fork-alternative open loop implemented, smoke-tested and queued (2026-09-29 14:40 PDT)
**TL;DR** New `scripts/a6000/openloop_topk.py` records the served cell's top-20 alternatives (token id + logprob) at every BF16 decision start and at the tool-name tokens of BF16 tool calls. It uses the same 400-decision sample as E3, plus the first token of all BF16 decisions. BF16 is run as its own cell, so the contrasts are served-vs-served: Δlogit P(`<tool_call>`), KL(BF16‖cell), and the mass on each tool name.
- **Integrity.** The BF16 cell reproduces the closed-loop first-token logprobs within the log's 4-decimal rounding. `prompt_logprobs` and generation agree bit for bit.
- **Smoke, q4 RTN-W4 vs BF16.**
  - Mean P(act) at decision starts: 0.540 → 0.492.
  - Split by what BF16 did, it falls from 0.956 to 0.831 at tool starts and rises from 0.016 to 0.065 at text starts, so RTN blurs the fork rather than shifting it one way. Δlogit mean −0.90.
  - The act/talk argmax flips at 11.75% of starts.
  - First-token KL: median 0.009, q90 2.8.
  - P(BF16's tool name) falls from 0.991 to 0.896, and the tool-name switch rate rises from 0.4% to 10.8%.
- **Queued.** 50 tasks `a6k2_<m>_olk_<cell>` at priority −8: q4 19, q8 17, q14 6, q32 6 (cell list in the iter-4 doc).
- **Code changes.** `worker.py` passes `openloop.topk` / `positions` / `first_all` / `ref` through to the new script. Tasks without `topk` are unchanged, and `openloop_d.py` is untouched.

Evidence: `scripts/a6000/{openloop_topk,make_tasks_e42,worker}.py`; `analysis/openloop/a6k2/q4/topk/{bf16,rtn_w4}.{json,npz,names.json}`; `docs/insights/iter_4_disposition.md` ("E4-2 implementation"); `/data/ziyangs/cloq_work/queue/*/a6k2_*_olk_*.json`; logs `/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_olk_{bf16,rtn_w4}.log`.

## W19 — Iteration-4 experiments queued: checkpoint variant vs sampling (2026-09-29, user go-ahead)
**TL;DR** Tests whether a quantized checkpoint is a reproducible behavioural variant (coherent net effect, persistent fingerprint; W18) unlike nonce/Gaussian perturbations and sampling. Queued via `scripts/a6000/make_tasks_iter4.py`: E4-1 open-loop probes for existing checkpoints on q8/q14/q30a3/q32 (20 reprioritised to −8, 6 new); E4-3 calibration draws c3/c4 → GPTQ/AWQ-W4 d3/d4 on q4/q8 × 2 fresh nonces (8 cells, 16 runs, + open-loop); E4-4 fixed Gaussian k=1 seeds s2/s4/s5 on q4/q8 × 2 fresh nonces (12 runs); S sampling baseline q4 BF16 T∈{0.2,0.5,0.8} × seeds 1–3 on fresh nonces (9 runs). KV-cache quant and q8 new-method closed-loop cells moved +30 (telecom already at 40–60). Code: per-run `env` in worker.py; `CLOQ_AGENT_TEMPERATURE`/`CLOQ_AGENT_SEED` in cloq/config.py (frozen greedy stays the default; recorded in each run's config.json llm_args_agent); extra calibration draws c4/c5 in `configs/draws_extra.json` (frozen_v1 untouched; calib_v1 refuses to redefine a frozen draw). Pending: E4-2 (top-20 open-loop variant) and E4-5 (57 calibration-split tasks).
Evidence: `scripts/a6000/make_tasks_iter4.py`; `queue/todo/a6k2_{q4,q8}_{gptq,awq}_w4_d{3,4}.json`, `a6k2_{q4,q8}_churnctl_k1_s{2,4,5}.json`, `a6k2_q4_samp_T*.json`; `docs/insights/iter_4_disposition.md`.

## W18 — Iteration-4 disposition hypothesis: P1–P4, F1 (2026-09-29 13:30 PDT)
**TL;DR** Tests "quantization shifts dispositions at near-tied policy forks; a checkpoint's fixed bias makes the net effect a coherent lottery" on gated snapshot 20260929T1937Z, with Holm over 5 declared tests.
- **Supported.**
  - **P2** Each checkpoint has a reproducible behavioural fingerprint across nonce draws: F 0.44, p_holm 0.001. tool_share is the most checkpoint-specific feature.
  - **P1** Checkpoint net Δ is over-dispersed vs independent task landing: φ 4.6, p_holm 0.001. Excluding the W3 method gap: φ 2.3, p 0.017. Recalibration pairs: φ 4.7, p 0.013. The effect is carried by q4/q32; q8 and q30a3 show none. Prompt nonces are not coherent (φ_U 0.36–1.19).
  - **P4** On q4, an open-loop act-vs-talk logprob contrast predicts the closed-loop tool-call shift beyond dose: partial ρ 0.62, p_holm 0.012. q8/q30a3 do not replicate (they have no RTN/GPTQ E3 cells).
- **Not supported.**
  - **P3** The fingerprint does not predict the sign of Δ: ρ 0.12, p 0.32.
  - **F1** Near-tied BF16 first tokens do not mark fragile tasks: ρ −0.12.
- **Exploratory.** Shift size tracks λ (ρ 0.67). Gaussian seeds show no lottery at any k.
- **Proposed next (not queued).** E4-1 (E3 cells for existing checkpoints on the other models) and E4-2 (a fork-alternative open-loop spec with top-20 logprobs).

Evidence: `docs/insights/iter_4_disposition.md`; `analysis/insights/iter_4/{common4,p1_overdispersion,p2_dispositions,p4_openloop_forks,f1_fragile_forks,p5_dose_scaling,h00_holm}.py`, `run_all.sh`; `analysis/insights/iter_4/out/*_live_20260929T1937Z.{json,log}` (Holm: `out/h00_holm_live_20260929T1937Z.json`); `analysis/insights/iter_3/out/snapshot_live_20260929T1937Z.json`.

## W17 — R3/R4 statistics for λ–c turnover: floor, hierarchical bootstrap, TOST/NI, Holm (2026-09-29 12:55 PDT)
**TL;DR** Addresses review_storyline_v4 R3/R4 and W6/W7. Run on a fresh integrity-gated snapshot (20260929T1937Z) for q4/q8/q14/q30a3/q32 (l8: no runs), with a hierarchical paired bootstrap (tasks, null draws, checkpoints and draws resampled).
- **Survives Holm.**
  - W4 turnover above a numerics floor (rot_bf16/null_K/gauss0.001/0.003), pooled over 5 models: RTN +0.19 [0.10, 0.30], GPTQ +0.15 [0.07, 0.24], AWQ +0.16 [0.07, 0.25].
  - RTN re-rolls no more than random-sign error of RTN magnitude (NI, margin 0.10, p_holm 0.038).
- **Fails.** "20–40%" and "5–10×": against the floor, q4 RTN break is 2.2× [0.9, 8.9] and fix 1.2× [0.4, 3.7].
- **Not established.** λ-equivalence of W4 methods at ±0.10. The pooled Δλ vs RTN is only −0.05 to +0.13, but no TOST passes.
- **Unidentified.** "c follows method": RTN's c is unidentified (λ 2.5% bound ≤ 0.10) on every model, so none of the 14 Δc tests can be run.
- **Checkpoint lottery.** The same-method checkpoint gap exceeds the method gaps: q4 GPTQ d1−d2 ΔΔ +9.6 pp [1.8, 17.4], while every method-vs-RTN ΔΔ CI covers 0. The checkpoint variance of Δ exceeds the method variance on q4/q14/q32 (1–2 df; tests need R1).
- **Coin check.** Passes in 81/83 cells, but it is weak (median CI width 0.39).
- **Provenance.**
  - "Partial ρ 0.86" was flip vs per-decision *hazard* (A2-15). For λ it is 0.39 [−0.03, 0.73]: the probe is mostly a dose proxy.
  - The 85 tasks are the `evaluation` split of `manifests/task_split_v0.json` after 22 BF16-unstable exclusions; the 57 calibration tasks are unused.
  - `r01_realloc_unfrozen.json` (q4,q8 only, ungated) is left unchanged. The gated all-model r01 is `r01_realloc_live_20260929T1937Z.json`.
  - `r_common.py` gains a `CLOQ_TAG` output-tag override.

Evidence: `docs/insights/iter_3_stats_R3.md`; `analysis/insights/iter_3/r10_turnover_stats.py`; `analysis/insights/iter_3/out/{r10_turnover_stats,r01_realloc}_live_20260929T1937Z.json`, `out/snapshot_live_20260929T1937Z.json`, `out/integrity_live_20260929T1937Z.log`; `paper/review_storyline_v4.md`.

## W16 — Simulator rebalancing without runner restarts (2026-09-29 12:30 PDT)
**TL;DR** node005's simulator stayed KV-bound (4 running, 36–38 waiting) while node001/node004 simulators were idle. (1) Stopped `a6k2_q4_gauss3_s2_redo` (26/85 tasks after 13 h; k=3 loops to max_steps, W11) and moved it to `queue/deferred/` (finished episodes kept, resume-safe); `a6k2_q4_gauss3_s1_redo` (54/85) continues. (2) `worker.py` now reads `queue/USER_BASE.<node>` at task start, so a node's new tasks can use another node's simulator without restarting its runner; `USER_BASE.node005` → node004. All simulators are the same model with the same canary hash, so outcomes are unaffected. (3) `gputop.py` sums non-negative counter increments (server restarts gave negative cluster tok/s).
Evidence: `queue/deferred/a6k2_q4_gauss3_s2_redo.json`; `queue/USER_BASE.node005`; `scripts/a6000/{worker,gputop}.py`; `gpumon/node005.jsonl`.

## W15 — E17 size-vs-structure complete; r_common family regex fix (2026-09-29)
**TL;DR** `iter_3/r_common.QUANT_RE` recognised only rtn/awq/gptq, so r01–r09 silently dropped every E17 control and every new method (gshape, rtnsign, rtnsr, nf4, mxfp4, rot_*, kvq_*). Fixed. With all 3 draws per control on q4/q8/q14 (attractor-model λ, nonce null, task bootstrap, unfrozen):

| model | RTN W4 | gshape (RTN per-group RMS, Gaussian) | rtnsign (RTN magnitudes, random signs) | Gaussian k=1 (fixed ckpt) |
|---|---|---|---|---|
| q4 | 0.24 [0.09, 0.42] | 0.42 [0.22, 0.62] | 0.24 [0.12, 0.37] | 0.34 [0.16, 0.56] |
| q8 | 0.19 [0.01, 0.41] | 0.17 [0.02, 0.38] | 0.42 [0.17, 0.70] | 0.27 [0.07, 0.52] |
| q14 | 0.25 [0.06, 0.45] | 0.20 [−0.01, 0.41] | 0.35 [0.13, 0.58] | 0.30 [0.09, 0.49] |

No ordering holds across models and every CI overlaps: RTN's specific error structure reallocates no more than size-matched random error; the controls reallocate as much or more (3-model means: RTN 0.23, gshape 0.26, rtnsign 0.34). Supports "reallocation is set by error size, not quantizer structure" (M4). Provisional until the frozen-snapshot rerun. Earlier E17 numbers in chat (q8 gshape 0.049, q14 rtnsign 0.175) were a different metric (fate-change fraction) from an ad hoc script and are superseded.
Evidence: `analysis/insights/iter_3/out/r01_realloc_unfrozen.json`; `analysis/insights/iter_3/r_common.py` (QUANT_RE); runs `runs/a6k2_{q4,q8,q14}_{gshape,rtnsign}_w4_q{1,2,3}`.

**Addendum (AWQ calibration control, q4).** AWQ d2 (3 fresh-nonce runs) λ 0.23–0.26 vs d1 0.12–0.36 (mean 0.29): calibration draw does not matter. On q4, λ is method-independent (RTN 0.24, AWQ 0.25, GPTQ 0.25) while the attractor c differs (RTN 0.18, AWQ 0.36, GPTQ 0.45, p̄≈0.36), which by Δ = λ(c − p̄) is why RTN damages and GPTQ does not. Candidate insight: calibration-aware quantizers change *where* reallocated tasks land, not *how many* are reallocated. Caveat: q8 AWQ λ 0.39 vs RTN 0.19, so check across models on the frozen snapshot.

**Addendum (new methods, q4, 3 fresh-nonce runs each).** λ / c: rot_bf16 0.12 (≈ serving null_K 0.09); RTN 0.24/0.18; rot_rtn 0.23/0.37; GPTQ 0.25/0.45; rot_gptq 0.23/0.49; MXFP4 0.22/0.42; NF4 0.37/0.45; rtnsr (1.41× RTN error) 0.35/0.12. Rotation, like calibration, leaves λ unchanged and moves c above p̄ (≈0.36), which removes RTN's net damage; stochastic rounding raises λ and lowers c. q8/q14 queued. Evidence: `analysis/insights/iter_3/out/r01_realloc_unfrozen.json`.

## W14 — KV-quant scheduling (2026-09-29)
**TL;DR** Plain KV INT4/INT3 destroys q4 (token flip 79%/90% vs 4.3% with Hadamard rotation, 0.75% at INT8), so its closed-loop cells would loop to max_steps for hours (W11) and add nothing beyond gauss k=3. Deferred the 6 plain INT4/INT3 cells, added KV INT8 cells on q4/q8/q14 (fresh nonces q1–q3) as the free-zone deployed-analog point, and made the cross-node det pair INT4+rotation.
Evidence: `analysis/kvq/validate_q4.json`; `queue/deferred/a6k2_{q4,q8,q14}_kvq_{int4,int3}.json`; `queue/todo/a6k2_{q4,q8,q14}_kvq_{int8,int4_rot}.json`, `a6k2_det_q4_kvq_int4_rot_{a,b}.json`.

## W13 · Fake KV-cache quantization (KVQ) in the live pipeline (2026-09-29 12:30 PDT)
**TL;DR** Real FP8/INT KV caches cannot run on A6000 under our frozen numerics (W7), so KV quantization is faked:
a sitecustomize hook wraps vLLM 0.29's `Attention.forward` (used by Qwen3, Qwen3-MoE and Llama) before model
construction. It quantize-dequantizes K (after k_norm and RoPE) and V, i.e. exactly what is written to the paged cache.
The scheme is per token, per KV head, one asymmetric INT-b group over head_dim. An optional QuaRot-KV variant applies a
fixed Hadamard: q and k are rotated, V is quantized in the rotated basis and rotated back. Dynamo inlines the wrapper,
so the ops are compiled by Inductor and replayed inside the CUDA graphs. They are row-local, so they stay batch-invariant.
Validation on q4 (`analysis/kvq/validate_q4.json`):
(a) bits=16 through the hook reproduces the BF16 canary `c7343b60da095480` exactly.
(b)/(c) Open-loop |Δlogprob| on 150 BF16 reference decisions (12,288 tokens) is monotone in precision:

| cell | mean \|Δlogprob\| | token flip rate |
|---|---|---|
| INT8 | 0.010 | 0.75% |
| INT4 + Hadamard | 0.119 | 4.3% |
| INT4 | 5.00 | 79% |
| INT3 | 6.45 | 90% |

(d) Under every config, 8 real agent prompts gave identical token ids and logprobs in three settings: alone,
in one concurrent batch with 8 fillers, and again after a prefix-cache hit (8/8).
**Plain per-token INT4/INT3 destroys Qwen3-4B.** The cause is K outlier channels: one group spans them and zeroes the
rest. The Hadamard rotation largely rescues it, which is the QuaRot result. Expect `kvq_int4`/`kvq_int3` agents to loop
to max_steps. Those cells are likely GPU sinks (W11); defer them if the queue backs up.
- Code: `scripts/a6000/pyhooks/cloq_kvq.py` (the hook). `scripts/a6000/pyhooks/sitecustomize.py` installs it only when
  `CLOQ_PYHOOKS=1` and `CLOQ_KVQ_BITS` is set. Other env: `CLOQ_KVQ_ROT`, `CLOQ_KVQ_WHICH`.
- Compile-cache isolation: the hook moves `VLLM_CACHE_ROOT` to `<root>/kvq_b<b>_r<rot>_<which>`. vLLM keys its compile
  and AOT caches by config and traced source, not by env, so without this a KVQ server and a BF16 server could share a
  compiled graph.
- Worker changes (`scripts/a6000/worker.py`): the BF16 canary is skipped when `serve_env` enables KVQ, and
  `runs/<id>/quantization.json` records `kv_cache`.
- Generator: `scripts/a6000/make_tasks.py --only kvq`. Arm `kvq`, ckpt bf16.
- Validation: script `scripts/a6000/kvq_validate.py`; task `/data/ziyangs/cloq_work/queue/done/kvq_validate_q4.json`.
  Server logs are in `/data/ziyangs/cloq_work/logs/kvq/`, open-loop outputs in `analysis/kvq/openloop_q4_*.json`.
  The INT8 canary (`42f358a11e348a84`) differs from BF16, as intended.
- Queued (priority −2): `a6k2_{q4,q8,q14}_kvq_{int4,int3,int4_rot}`, each 3 runs `_q1.._q3` with fresh nonces
  6d1f0b3e/f07a5c21/4c8e1a7f. Det pair `a6k2_det_q4_kvq_int4_{a,b}` is pinned to node005/node004.

## W12 · More weight-only 4-bit formats: NF4, MXFP4, QuaRot rotation (+RTN/GPTQ), stochastic-rounding RTN (2026-09-29 12:00 PDT)
**TL;DR** Six new fake-quant cells go into the live pipeline, each dequantized back to bf16 and served through the
identical vLLM path. They are `nf4` (QLoRA NormalFloat-4, absmax block 64), `mxfp4` (OCP MX: E2M1 elements with a
shared E8M0 scale per 32), and the QuaRot-style `rot_bf16` (fused RMSNorm plus a seeded random-Hadamard residual
rotation, no quantization, a control). On top of that rotation come `rot_rtn_w4` and `rot_gptq_w4`. `rtnsr_w4` is
RTN's own grid with stochastic rounding: an on-grid, unbiased control, where `rtnsign` is off-grid. This adds the
method list of the COLM 2025 "Quantization Hurts Reasoning?" paper and extends E17 (error size vs structure).
- Unit tests pass on CPU (`tests/test_fp4_rotate.py`, run with `BNB_PATH=/data/ziyangs/cloq_work/tmp/bnbref`):
  - NF4 matches bitsandbytes 0.50.2 `quantize_4bit`/`dequantize_4bit` 100% (fp32 and bf16 inputs).
  - MXFP4 matches an ml_dtypes `float4_e2m1fn`/`float8_e8m0fnu` reference 100%, with hand-checked round-to-nearest-even ties and saturation to 6.
  - Hadamard: H H^T = dI for d = 2560, 4096 and 5120 (Paley order 20 ⊗ Sylvester).
  - A tiny tied Qwen3 stored in fp32 gives max |Δlogprob| 6.4e-7 after rotation.
  - rtnsr stays on the RTN grid, is unbiased (0.04 steps after 64 draws), and its error is 1.41× RTN's.
- q4 rotation check (`analysis/rotation/verify_q4.json`; task `a6k2_w12_verify_rot_q4`; `scripts/a6000/verify_rotation.py`).
  It uses 20 calibration contexts (40,960 positions) and compares rot_bf16 with the original:
  - fp32 compute: top-1 agreement 99.55%, mean |Δlp(top1)| 0.006. Here only the bf16 storage of the rotated weights differs.
  - bf16 compute: 98.4%, mean 0.018. This is the size of the bf16 numerics floor: the original model in bf16 vs fp32 compute agrees 98.7%, mean 0.013.
  - Max |Δlp| is 0.8–0.9 at near-tie positions (the numerics reference reaches 1.1). The last position agrees 20/20.
  - vLLM serves the untied checkpoint (`tie_word_embeddings=false`, explicit `lm_head.weight`). Greedy 48-token outputs are identical on 3/6 prompts; the other 3 diverge at a near-tie (token 0 or 13).
  - q_norm/k_norm act per head on the projection outputs, so the rotation leaves them unchanged.
- q4 smoke (task = production cell, fresh nonces q1–q3, overall db_match over 85 tasks). References:
  - fresh-nonce and n-nonce references: RTN-W4 q* 0.306, GPTQ-W4-d1 q* 0.408, AWQ-W4 q* 0.404, null n* 0.359.
  - new cells: nf4 0.341/0.365/0.376, mxfp4 0.341/0.353/0.329, rot_bf16 0.341/0.388/0.365, rot_rtn_w4 0.318/0.306/0.376,
    rot_gptq_w4 0.400/0.400/0.412, rtnsr_w4 0.212/0.235/0.294. Mean relative weight error: nf4 0.0086,
    mxfp4 0.0137, rot_rtn 0.0102 (RTN-W4 ≈ 0.0107), rtnsr 0.0212.
- Queued (priority −2; rtnsr −3): q8 and q14 × all 6 cells (runs `a6k2_<m>_<cell>_q1..q3`, nonces 6d1f0b3e/f07a5c21/4c8e1a7f).
  Also E3 open-loop tasks `a6k2_<m>_ol_<cell>` for q4/q8/q14 (ref `a6k2_<m>_bf16`, out `analysis/openloop/a6k2/<m>/<cell>`).
  q14's open-loop tasks wait on `a6k2_q14_bf16` (in todo), as the existing q14 E3 cells do.
- Code: `cloq/compress.py` (modes nf4, mxfp4, rtnsr), `cloq/rotate.py` (new), `cloq/quantize.py --src` (GPTQ on a local
  rotated checkpoint; records `pre_transform`), `scripts/a6000/worker.py` (kinds nf4, mxfp4, rtnsr, rot_bf16, rot_rtn, rot_gptq),
  `scripts/a6000/make_tasks.py --only w12`. Logs: `/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_{nf4,mxfp4,rot_*,rtnsr_w4}.log`.
- Caveats:
  - NF4 stores fp32 absmax with no double quantization. Double quantization of the scales is not modelled.
  - Rotation uses a single seed (0), and rot_* keeps embeddings and lm_head rotated in BF16. QuaRot additionally rotates
    per head in attention and applies online Hadamards for activations; neither matters for weight-only quantization.
    Only the residual rotation is applied.

## V6 · Insight loop, iteration 1 (2026-09-29, in discussion)
**TL;DR** Four candidates (I1–I4), repositioned against the literature. The per-step margin model is inherited
from Du et al. 2026. Our claims are the closed-loop composition, saturation along δ, a later damage threshold, and
cross-model transfer.
- Candidates: `docs/insights/iter_1_candidates.md`. Scripts: `analysis/insights/iter_1/s0*.py`.
  Outputs: `analysis/insights/iter_1/out/*.json` (snapshot `s00_snapshot.json`, 2026-09-29T01:26Z).
- Literature: `docs/insights/SURVEY.md`, `docs/insights/survey_sweeps/{margins_flips_divergence,compressed_agents_eval_noise,equivalence_null_criteria}.md`,
  `analysis/insights/references_new.bib`.
- Discussion (survey + experiment round 1): `docs/insights/iter_1_discussion.md`. Plan: `docs/insights/EXPERIMENTS.md`.
- Agent roles: `~/.claude/agents/cloq-{insight,survey,experiment,verify}.md` (on the cluster login node).
- **Verifier (iter 1, 2026-09-29 02:36Z):** I1 REVISE (v2: per-decision hazard floor), I2 HYPOTHESIS, I3 HYPOTHESIS (at risk: q8 RTN-W4), I4 HYPOTHESIS with I4a HELD (serving numerics move the canonical score ±8 pp). Also: legacy→a6k2 changed the user simulator (11/20 det tasks), so E5 needs the eager null. `docs/insights/iter_1_verdicts.md`, `docs/insights/LEDGER.md`, scripts `analysis/insights/iter_1/verify/v0{1..4}_*.py`.

## W9 · Llama-3.1-8B (l8) in the τ²-bench harness (2026-09-28 23:59 PDT)
**TL;DR** The l8 smoke run's 5 `infrastructure_error` episodes ("object of type 'NoneType' has no len()") were our
local prompt rendering, not the server. tau2's `to_litellm_messages` gives every assistant text turn `tool_calls: None`.
The Llama-3.1 template tests `'tool_calls' in message` and then takes `tool_calls|length`, so it crashed. The Qwen
template only tests truthiness. vLLM drops a None `tool_calls` and parses string `arguments` into dicts before it
renders, so it never crashed. Fix: `cloq/context_policy.template_view` applies the same normalisation before every
local render. Local prompt ids now equal the server's (smoke v1 17.5% → v2 100%). Qwen is byte-identical: 960 replayed
q4/q8/q30a3 decisions give the same text and match the server ids. l8 now uses the official meta repo, pinned. It also
sets `tools_in_user_message=false`, because by default the template relabels tau2's assistant greeting as a user turn
that carries the tool list. vLLM's `examples/tool_chat_template_llama3.1_json.jinja` is not in the wheel. We did not
adopt it: it has the same `tool_calls` test, and it stamps `strftime_now` (today's date) into the prompt. Smoke v2
(20 det tasks): no infra errors. airline db 0.2 / reward 0.2 / tool_err 0.22; retail db 0.2 / reward 0.0 /
tool_err 0.67 (q4: 0.04 / 0.16). The retail tool errors come from the model: it invents identifiers (21/38 "User not
found") and passes JSON arrays as strings (11/38). The template ablation gives the same retail rate (0.67).
- Code: `cloq/context_policy.py` (`template_view`, used by `render_prompt`/`render_prompt_ids`). Test:
  `tests/test_template_view.py` replays logged decisions (Qwen: identical text and 100% server-id match; l8: the raw path
  crashes on 165/165, `template_view` matches the server on 165/165). A synthetic case reproduces the crash.
- Model: `scripts/a6000/models.json` l8 = `meta-llama/Llama-3.1-8B-Instruct@0e9e39f249a16976918f6564b8830bc894c89659`.
  The 4 safetensors sha256 equal the unsloth mirror's (2b1879f3…, 09d433f6…, fc1cdddd…, 92ecfe1a…), and
  `hf cache verify` checked 14 files. The tokenizer encodes identically (57/57 prompts). The unsloth config/generation_config
  differ only in eos/pad metadata. The agent canary hash equals the unsloth one (`cbabe9a77c80c825`; old ref kept as
  `analysis/determinism/canary_agent_l8.unsloth.json`). The unsloth mirror was removed with `hf cache rm`. It freed only
  17 MB, because the shared blob store already deduplicated the weights with the meta repo.
- Runs: `/data/ziyangs/cloq/runs/a6k2_smoke_l8_v2/` (fix + `tools_in_user_message=false`) and
  `/data/ziyangs/cloq/runs/a6k2_smoke_l8tum/` (fix + default template, ablation: airline db 0.3 / tool_err 0.16 /
  16 tool calls per task with one max_steps; retail db 0.1 / tool_err 0.67). The ablation code `l8tum` was removed from
  models.json. Failed v1: `/data/ziyangs/cloq_work/queue/failed/a6k2_smoke_l8.json`, `/data/ziyangs/cloq_work/logs/tasks/a6k2_smoke_l8.log`.
- Consequence: l8's high retail tool-error rate belongs to the model, not to the harness. Treat l8 as a
  low-capability family (floor effects on db_match) when reading its perturbation nulls.

## W11 · Heavy-perturbation cells are GPU sinks; closed-loop k=3 deferred on q32/l8 (2026-09-29 04:55 PDT)
**TL;DR** From 01:22 to 04:53 only ~18 tasks finished. The reason: 7 slots were occupied for 5–6 h by k≥2 Gaussian and
redo cells, whose agents loop to max_steps with ~30k-token contexts. The batch-invariant kernels then run at ~50–80
generated tok/s and ~2k prefill tok/s per server. These were not hung (logs and metrics advance). Closed-loop gauss3 on
q32 and l8 (4 tasks) is moved to `/data/ziyangs/cloq_work/queue/deferred/`: it is a control under the
quantization-centred framing (PLAN_iter4) and costs roughly 6–10 GPU-h each. Their open-loop E3 cells stay queued (6 min each).
- Evidence: `/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_gauss3_s1_redo.log` (8 sims running 40–100 min each),
  `.vllm.log` throughput lines; status snapshot in session.

## W10 · Context-window overflow is a task failure, not an outage (2026-09-29 03:00 PDT)
**TL;DR** `a6k2_q8_gauss2_s2` failed the W6 guard with 2 infrastructure_error episodes. They were not outages: a
heavily perturbed agent looped until the dialogue exceeded the simulator's 65,536-token window. That is the agent's own
failure. The worker now classifies each infrastructure_error from tau2's `info.error` into
`runs/<run>/<dom>/infra_causes.json` (context_overflow vs outage) and fails the task only on outages. Analyses
(`analysis/insights/iter_2/common.py`) count context_overflow as failure. The task was re-queued.
- Evidence: `/data/ziyangs/cloq_work/logs/tasks/a6k2_q8_gauss2_s2.log` (ContextWindowExceededError); fix `scripts/a6000/worker.py`.

## W8 · Duplicate decision records from resumed runs; more infra-error runs (2026-09-28 23:45 PDT)
**TL;DR** tau2's `auto_resume` and retries re-run a simulation, but `cloq.agent` appends to decisions.jsonl. So an
interrupted or retried task kept the records of its abandoned attempt (6,724 records in 52 run-domains). Outcomes were
unaffected (trajectory.jsonl is rebuilt from the final results), but per-decision analyses were polluted. Fix:
`scripts/a6000/dedup_decisions.py` keeps the last attempt per task (applied to all a6k2 runs; the remaining count
mismatches are only infrastructure-error episodes), and `cloq/run_arm.py` now does the same at the end of every run.
The rescan found 6 more runs with simulator-outage episodes from before the W6 guard; they were deleted and re-queued
(`*_redo`). Also: the runners on node004/005/007 crashed on an unknown model code (l8) after my W5 change. Their tasks
were re-queued, the runners resubmitted (49671–49673), and the runner now re-reads models.json (unknown model = not
claimable).
- Evidence: dry-run log in session; `scripts/a6000/dedup_decisions.py`; `/data/ziyangs/cloq_work/logs/node_node004_49664.out` (KeyError 'l8').
- Consequence: iter_2 analyses (p0x, c01, c02) must be re-run after the redos finish.

## W7 · X1 real deployed formats in the live pipeline (2026-09-28 23:50 PDT)
**TL;DR** Official Qwen3 AWQ-INT4 (q8/q14/q32) and FP8 (q4/q8/q14/q30a3/q32) checkpoints are served with vLLM
0.29 kernels in the a6k2 pipeline. Each cell gets canonical + 2 nonces, a node005/node004 det pair and E3 open-loop:
32 tasks, `make_tasks.py --only x1`. **KV-FP8 and bitsandbytes cannot run here** and are not queued.
Under our frozen numerics (`VLLM_BATCH_INVARIANT=1`), vLLM swaps the "deployed" kernels for batch-invariant ones:
- FP8 uses the Humming FP8 kernel (not FP8 Marlin, which vLLM rejects in batch-invariant mode).
- AWQ uses `awq_dequantize` + matmul (not awq_marlin), and it must run with FP16 activations.
The weights are the real deployed ones; the GEMM kernels are not. Smokes passed for both formats; q30a3 FP8 det pair
275/275 decisions identical so far.
- Checkpoints (HF cache `/data/ziyangs/cloq_work/hf`, pinned in `scripts/a6000/make_tasks.py::X1_HF`):
  Qwen3-8B-AWQ `4da05a8e`, 14B-AWQ `31c69efc`, 32B-AWQ `0499c3ac`, 4B-Instruct-2507-FP8 `85918040`, 8B-FP8 `220b46e3`,
  14B-FP8 `9a283b4a`, 30B-A3B-Instruct-2507-FP8 `5a5a7763`, 32B-FP8 `aa55da1e`. There is no official AWQ for the 2507
  models (q4/q30a3), so they have no AWQ cell.
- Same model variant: `analysis/x1/verify_checkpoints.py` → `analysis/x1/checkpoint_verification.json`. For all 8, the
  model card's `base_model` is exactly our BF16 repo. tokenizer.json, vocab, added/special tokens, chat_template and
  generation_config are hash-identical to our BF16 snapshot; config.json differs only in `torch_dtype` (AWQ: float16).
  The same `chat_template_kwargs` are passed: worker `model_env` is keyed by task model, so enable_thinking=false
  applies for q8/q14/q32. Smoke check: server-side prompt ids equal local BF16-tokenizer ids, 312/312 decisions; no
  thinking content.
- Code: `worker.py` ckpt kind `hf` (serve `hf_id@revision`; `runs/<id>/quantization.json` records the repo, revision
  and quantization_config) plus per-task `serve_env`; `make_tasks.py::x1` (priority 30+model; det −6; E3 ref `a6k2_<m>_bf16`,
  out `analysis/openloop/a6k2/<m>/<fmt>`); arms `x1_awq` / `x1_fp8`.
- Fix 1, FP8: Humming reads NVML device index 0 regardless of CUDA_VISIBLE_DEVICES. On node003 index 0 is the faulty card,
  so the server died with `NVMLError_Unknown`. `scripts/a6000/pyhooks/sitecustomize.py`, enabled only by
  `CLOQ_PYHOOKS=1` (FP8 tasks' `serve_env`; `env.sh` adds the dir to PYTHONPATH), remaps index i → CUDA_VISIBLE_DEVICES[i]
  inside humming only. Log: `/data/ziyangs/cloq_work/logs/x1/smoke1_failed_nvml.json`.
- Fix 2, AWQ: with BF16 activations the batch-invariant path crashes (`awq_dequantize` expects Half,
  `/data/ziyangs/cloq_work/logs/tasks/a6k2_det_q14_x1_awq_b.vllm.log`). AWQ cells therefore add `--dtype float16`, which is the
  checkpoints' config dtype and vLLM's default. This is a second difference from BF16 besides the weights. FP8 stays BF16.
- Dropped formats:
  - kv_fp8: on SM86, Triton attention refuses an FP8 KV cache ("native FP8 requires SM89+",
    `/data/ziyangs/cloq_work/logs/x1/withdrawn_kv_fp8/`). FA2 has FP8 KV only on SM90+, FlexAttention has none, and
    FlashInfer is not batch-invariant, so it is excluded under our protocol (vllm `v1/attention/backend.py:321`).
  - bnb: `--quantization bitsandbytes` was removed in vLLM 0.29 (not in `QUANTIZATION_METHODS`), and bitsandbytes is
    not installed.
- Smokes: `runs/a6k2_smoke_x1_q8_fp8` (det tasks, node005; retail 0.30, airline 0.10) and `runs/a6k2_smoke_x1_q8_awq`
  (node003; retail 0.20, airline 0.10; 1226 s vs 251 s for FP8, because the dequant path is slow). Downloads: `/data/ziyangs/cloq_work/logs/x1/download.{py,log}`.
- Open: an X1 variant with `CLOQ_BATCH_INVARIANT=0` would run the actual Marlin kernels, at the cost of batch-dependent
  numerics. `serve_env` supports it. A BF16 + TRITON_ATTN control would matter only if KV-FP8 ever becomes possible.

## W6 · Simulator outages scored as agent failures (2026-09-28 23:10 PDT)
**TL;DR** node003 uses node004's user simulator. When I restarted node004 (19:43 and ~21:50), node003 episodes ended in
`infrastructure_error`, yet the tasks exited rc=0. 11 run-families had ≥2 such episodes (q4 nulls n3–n5 were 100%).
Scored as failures, they would have fabricated +8–16 pp "gains" and a −23 pp q8 W3 "loss". Fix: those runs were
deleted and re-queued as `*_redo`, pinned to nodes with their own simulator. The worker now fails any run with an
infrastructure_error. Analyses treat such episodes as missing (`analysis/insights/iter_2/common.py` INFRA).
- Evidence: `docs/insights/iter_2_prep.md` §0 F1; `/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_bf16.log` ("Connection
  refused"); fix `scripts/a6000/worker.py` (termination_reasons check).
- Also queued: E8 FP32-head control (`a6k2_*fp32h*`, spec in `docs/insights/iter_2_prep.md` §E8).

## W5 · TP=2 starvation fix (2026-09-28 22:00 PDT)
**TL;DR** A freed card was always taken by a 1-GPU task, so no NVLink pair ever became free. At 21:49, q30a3 and q32
main cells stood at 5 and 3 done with 0 running. Fix: while a runnable 2-GPU task waits, the upper agent pairs
(4,5)(6,7) take only 2-GPU tasks. Runners on node004/005/007 were restarted (jobs 49664/49665/49666).
- Evidence: queue counts at 21:49 in this entry. Fix: `scripts/a6000/noderunner.py` (`tp2_wait`, `reserved`).

## W4 · TP=2 on NVLink pairs only (2026-09-28 20:45 PDT)
**TL;DR** `a6k2_q32_bf16_cal` hung in NCCL init on node005 GPUs 5,6, a cross-switch pair with no NVLink. The runner now
gives 2-GPU tasks only NVLink pairs (0,1)(2,3)(4,5)(6,7), and single-GPU tasks prefer broken pairs. This likely also
explains the earlier node007 TP=2 hangs. Runners on node004–007 were restarted (jobs 49638/49639/49641/49642; node006
is down to 4 GPUs because mg546924 took 4).
- Evidence: `/data/ziyangs/cloq_work/logs/tasks/a6k2_q32_bf16_cal.vllm.log` (stops after `pynccl.py:113`), topology
  from `nvidia-smi topo -m` (NV4 within pairs, NODE/SYS across). Fix: `scripts/a6000/noderunner.py` (allocation).

## W3 · Cross-node determinism incident (2026-09-29, root cause found, fix deployed)
**TL;DR** torch Inductor picked the reduction config for the fused residual+RMSNorm kernel by timing it at compile
time: R0_BLOCK 2048 on node005 vs 4096 elsewhere. The summation order changed, so every token shifted, and vLLM batch
invariance does not cover this. Fix: `TORCHINDUCTOR_DETERMINISTIC=1` plus a numerics canary at every server start.
The whole matrix is re-run as `a6k2_*`; old `a6000_*` runs are kept as a legacy "numerics flavour" null (E5).
- Symptom: `runs/a6000_det_q4_a` (node005) vs `runs/a6000_det_q4_b` (node004): 20/20 tasks and 113/113
  identical-prompt decisions shift; `analysis/insights/iter_1/out/s04_node_floor.json`,
  `analysis/insights/iter_1/exp/e_detshift.py`.
- Kernels are identical across nodes: `/data/ziyangs/cloq_work/numtest.py` (hash `932e7dab8e342639` on node004–007).
- Runtime is not the cause: `analysis/determinism/probe_q4.json`. On node006, cold / warm / concurrent / no-prefix-cache
  all match node004 30/30; eager is a third flavour (A 14/30, B 16/30). Script `scripts/a6000/det_probe.py`.
- Root cause (experiment agent): `analysis/insights/iter_1/exp/e_bestconfig.sh`, `e_server_flavour.py`;
  discussion `docs/insights/iter_1_discussion.md` (Experiment round 1), plan E1–E6 `docs/insights/EXPERIMENTS.md`.
- Fix: `scripts/a6000/env.sh` (flag), `scripts/a6000/worker.py::check_canary`; references in
  `analysis/determinism/canary_{agent,sim}_<model>.json`; per-start log `/data/ziyangs/cloq_work/logs/canary.log`.
- **Fix verified (2026-09-28 20:00 PDT):** `runs/a6k2_det_q4_a` (node005) vs `runs/a6k2_det_q4_b` (node004): 257/257 decisions
  byte-identical (prompt + completion), identical metrics. q30a3 pair 303/303 identical. Canary log
  `/data/ziyangs/cloq_work/logs/canary.log`: sim + q4/q8/q30a3 agents match on every node so far.
- Rerun: `scripts/a6000/make_tasks.py --prefix a6k2`. Old unfinished tasks archived in
  `/data/ziyangs/cloq_work/queue/legacy_v1/`.

## W2 · A6000 matrix running (2026-09-28 18:10 →)
**TL;DR** 5 models × 30 configs + determinism pairs; 110 tasks on node003–007 (38 GPUs). Checkpoints live only in
node RAM disk.
- Plan: `docs/A6000_PLAN.md` §3. Generator: `scripts/a6000/make_tasks.py`. Runner/worker: `scripts/a6000/{noderunner,worker}.py`.
- Live queue: `docs/a6000/QUEUE.md` (snapshot pushed every 30 min); `/data/ziyangs/cloq_work/queue/{todo,running,done,failed}/`.
- Logs: `/data/ziyangs/cloq_work/logs/node_<node>_<job>.out` (runner), `.../logs/tasks/<task>.log` (worker + run_arm),
  `.../logs/tasks/<task>.vllm.log`, `.../logs/sim_<node>_<job>.log` (user simulator).
- Per-run artifacts: `runs/a6000_<model>_<config>/<domain>/{metrics,status,config,environment,model}.json`
  (in git), `decisions.jsonl` / `trajectory.jsonl` (cluster only).

## W1 · Phase 0 + environment (2026-09-28)
**TL;DR** Driver 550 cannot run the pinned cu130 stack, so we built the cu129 builds of the same versions. Code is
model-generic with per-token margins. RTN is bit-identical to v1. Smoke test passed.
- Commits `3313d01`, `724b3dc` (and later). Env notes: `env/README_A6000.md`.
- Smoke test: `/data/ziyangs/cloq_work/logs/smoke/49592.out` (3 retail tasks, 83 s, 35/35 decisions with margins,
  server/local prompt ids identical).
- RTN equivalence check (vectorized vs `cloq/gptq.rtn_quantize_linear`, W8/W4/W3 on q4 layer 0): identical — command
  in session log; code `cloq/compress.py`.
- Node GPU faults: node003 PCI 01:00.0 and E1:00.0 (probe in `scripts/a6000/node.sbatch`; log
  `/data/ziyangs/cloq_work/logs/node_node003_49601.out`).

## V5 · Perturbation null on 4B (4080, 2026-09-28 → 09-29)
**TL;DR** BF16 × 5 nonces; Static / FP-Traj / RTN × 3 nonces; 8k harness. Results arrive with release `data-4080`.
- Script: `scripts/null_rerolls.sh`. Handoff: `docs/HANDOFF_4080_FINAL.md` (when pushed).

## V4 · E4 8k vs 32k context control (4080, 2026-09-28)
**TL;DR** Removing truncation lifts every model by 0.01–0.04 and leaves the ranking almost unchanged, so the main
harness moved to 32k. A W4 checkpoint beats BF16 under both harnesses, which is a live example of re-roll noise.
- Evidence: `docs/PROGRESS_2026-09-28.md` §2 (table); script `scripts/ctx_control.sh`; runs `runs/ctx32k_*`
  (4080; in `data-4080`).

## V3 · Strategy pivot to evaluation science (2026-09-28)
**TL;DR** A 48-agent strategy workflow plus an independent recompute. Flips are decided by the state (AUC 0.93).
Open-loop NLL does not track closed-loop success (|r| ≤ 0.13). Failures are write-dominated. Loops are mostly
agent-side.
- Strategy: `docs/STRATEGY_v2.md`. Recompute: `analysis/coling/RESULTS.md` + `analysis/coling/0[1-5]_*.py`.
- Workflow analyses: `analysis/strategy_v2_workflow/{mechanism,truncation,variance}/` (e.g. `mechanism/res_churn.json`).
- Loop attribution: `analysis/coling/04_loop_attribution.py`. Retired claims / reporting conventions: `docs/PROGRESS_2026-09-28.md` §3.

## V2 · v1: 3 draws × 6 arms (4080, 2026-09-16 → 09-27)
**TL;DR** The six calibration arms cannot be told apart in closed loop (arm permutation p = 0.683 pooled / 0.368
long). The CLOQ method claim is falsified. Draw variance is amplified by the closed loop.
- Evidence: `analysis/v1/FINDINGS_V1.md`, `analysis/v1/REPORT_V1.md`, `analysis/v1/results_v1.json`,
  `analysis/V1_STATUS_2026-09-16.md`, amendments `analysis/amendments/`. Protocol: `docs/PLAN_v1.md`, `configs/frozen_v1.json`.

## V1 · v0: single draw, 4 arms (4080, ≤ 2026-09-16)
**TL;DR** Horizon amplification (short 0.000 vs long 0.189, p = 0.039). Open-loop fidelity does not predict
closed-loop success. Support shifts after the first divergence. FP-Traj +0.121 later proved a false positive
(McNemar p = 0.0195; replication −0.035).
- Evidence: `analysis/FINDINGS.md`, `analysis/REPORT.md`, `analysis/results.json`, `analysis/occupancy_obs.json`,
  figures `analysis/fig2_horizon.png`, `analysis/fig6_openloop_vs_closedloop.png`; false-positive recompute
  `analysis/coling/02_v0_gap.py` → `analysis/coling/RESULTS.md`. Protocol: `docs/PLAN_v0.md`, `configs/frozen_v0.json`.
