# exppilot: unattended experiment pilot (W100r, review fixes W100r-b)

**TL;DR** A login-node loop (default 12 h, one pass every 10 min) that releases the protocol's phase-2 tasks, runs the frozen analyses once when they are due, and fills idle GPUs from `queue/deferred/` only with tasks the user approved. It complements `autopilot.sh` (runner resubmission, infra retries, board and git sync) and does none of that work. A 12 h run started in the morning of 10-03 ends before T_decide (20:00 PDT), the SAMEPREC freeze (10-04 00:00) and T_deadline (10-04 12:00). The start line of the log names every duty that falls after the end. Those duties need a relaunch with `--until` or a human.

## Start, stop, inspect

```
setsid nohup scripts/a6000/exppilot.sh [hours] [--until 2026-10-04T13:00-07:00] >/dev/null 2>&1 &   # default 12 h
touch /data/ziyangs/cloq_work/queue/EXPPILOT_STOP                    # stop within 30 s; delete the file before restarting
python3 scripts/a6000/exppilot.py --dry-run --once                   # print every action it would take, write nothing
```

- Log: `/data/ziyangs/cloq_work/logs/exppilot.log`. Each analysis also has its own log, `logs/exppilot_<key>_<UTC>.log`.
- State: `/data/ziyangs/cloq_work/exppilot_state.json`. It records phase-2 releases, analyses that succeeded or were committed, and rate-limit stamps. Deleting it does not re-queue anything, because every release first checks all five queue dirs. It does allow an analysis to run again.
- Only one instance can run at a time (flock on `cloq_work/exppilot.lock`).
- Control files in `queue/`, each written by a person or the main session, never by the pilot:
  - `EXPPILOT_STOP` stops the pilot.
  - `EXPPILOT_FILL_ALLOW` lists deferred task ids the user approved for the fill, one per line (`#` starts a comment).
  - `EXPPILOT_GO_newmethod_q8` releases the q8 analysis hold.

## What it does

| | Step | Rule |
|---|---|---|
| A | Phase-2 release | Starts once `analysis/fork/newmethod/expansion_<m>.json` (q8, m24) has `expand: true`. It queues every missing f04–f06 `nmp_tau2_*` / `nmp_score_*` task of `phase2_cells`, each through its cell family's generator: `make_tasks_m24.py panel --phase 2`, `make_tasks_rotpanel.py --panel --phase 2`, `make_tasks_kivi.py --phase 2 --gate-suffix _fx` and `make_tasks_bank_u.py --nmp-phase2`. **All or none:** every generator first runs without `--write` and must list every expected id. If any generator fails, nothing is written and the failure is logged hourly. A q8 record that breaks the A5.3 KIVI pairing or leaves out the reference cells is refused. **Reference cells** (`gptq_w4_d1`, `awq_w4`, `kvq_int8`) run f04–f06 with no gate dependency. §5.5 is unconditional, and the §5.3 cost has no gate time. `--ref-gates` adds the §2.4 gates, but only as recorded checks that nothing depends on. **Tiers:** m24 −30, and −29 for every q8 tau2 task (§5.5: never ranked). Score tasks keep their phase-1 score tier. If `expand` is not true, nothing is queued. |
| B | Analyses (CPU, 30 min timeout, at most 3 attempts, run once) | `analyze_newmethod.py --model <m>` runs only after the model's record exists, and once every panel and score task of the admitted cells is done. That covers phase 1 of `eligible` with their BFCL forks, plus phase 2 of `phase2_cells` if the record expanded. After T_deadline (2026-10-04 12:00 PDT) it runs on whatever exists. **q8 is held** until `queue/EXPPILOT_GO_newmethod_q8` exists. Per W100q F1a, the common-state amendment has to be hashed before the gptq_w4_d1 f04–f06 outputs are read. `analyze_sameprec.py` and `analyze_sameprec_w3.py` each run once after the 2026-10-04 00:00 PDT freeze. Each is skipped if a post-freeze output already exists, because the main session owns F0. Outputs are only the files the script prints as `wrote analysis/fork/out/<f>`, plus their `.md` siblings. They and one line in `analysis/fork/out/EXPPILOT_LEDGER.md` are committed with explicit paths, followed by `pull --rebase --autostash` and `push`. |
| C | GPU fill | Demand is counted per node: the GPUs of runnable todo tasks that the node's runner can host. Runnable means node pin, GPU count, dependencies done, and the W99p rule: runners started before 44527e1 (node001/005/007 now) never take tasks needing more than 2 GPUs. A node is filled only when no runnable todo task can use its idle cards. If such cards exist on 2 consecutive loops, the pilot moves deferred tasks listed in `EXPPILOT_FILL_ALLOW` into todo, in (priority, age) order. Each moved task gets priority −19, a `requeue_note`, and `autopilot_retry`, so a re-failure goes to a human. A gate_same fork also gets `fail_loud`. Tasks that pass every check but are not on the list are logged hourly for approval. The move is one rename from deferred/ to todo/. |
| D | Health | Logs `starved` once per hour when idle GPUs exist, no todo task is runnable and nothing is releasable. The line also counts the todo tasks blocked on dependencies. Any task family (first three id tokens) with more than 3 failures in 2 h stops being released. |
| E | Status | Every 30 min it logs one paragraph: queue counts by family, idle and fillable GPUs, demand by node, releases and analyses, and the actions since the last paragraph. |

**Never released from deferred, even when listed:**
- The main-session stops (`pert_q4_rtn_w3_restore_early_q345`, `a6k2_q32_tel_rtn_w4`, `pert_q8_rtn_w3_restore_rand_attn_s3_q345`), and any task whose `deferred_note`, `deferred_reason` or `defer_note` contains "stopped".
- `nmp_*` tasks.
- `ext_l8_`, smoke and l8 tasks.
- `kind: sim` tasks.
- g12 tasks (W100p gate FAIL).
- Tasks whose dependencies are not all done.
- Deterministic re-fails: an eval task with a `completed` run-domain whose `infra_causes.json` holds outage episodes (W100q §1.1).

## What it never does

- It never runs sbatch, scancel or kill, and never touches `queue/running/`.
- It never opens `analysis/fork/holdout/` and never edits `configs/frozen_v*.json`, manifests or protocols.
- It never reads a panel outcome to decide what to queue. From the expansion record it reads only `expand`, `phase2_cells` and `eligible`.
- It writes no protocol note. §5.6 only requires the record to exist before phase 2 is queued. Editing the protocol would also break the `PROTOCOL_SHA256` guard in `analyze_newmethod.py`.
- It commits only its own analysis outputs and ledger lines.
