# exppilot: unattended experiment pilot (W100r)

**TL;DR** A login-node loop (default 12 h, one pass every 10 min) that releases the protocol's phase-2 tasks, runs the frozen analyses once when they are due, and keeps idle GPUs busy from `queue/deferred/`. It complements `autopilot.sh` (runner resubmission, infra retries, board and git sync) and does none of that work.

## Start, stop, inspect

```
setsid nohup scripts/a6000/exppilot.sh [hours] >/dev/null 2>&1 &     # default 12 h
touch /data/ziyangs/cloq_work/queue/EXPPILOT_STOP                    # stop within 30 s; delete the file before restarting
python3 scripts/a6000/exppilot.py --dry-run --once                   # print every action it would take, write nothing
```

- Log: `/data/ziyangs/cloq_work/logs/exppilot.log`. Each analysis also has its own log, `logs/exppilot_<key>_<UTC>.log`.
- State: `/data/ziyangs/cloq_work/exppilot_state.json`. It records phase-2 releases, analyses that succeeded or were committed, and rate-limit stamps. Deleting it does not re-queue anything, because every release first checks all five queue dirs. It does allow an analysis to run again.
- Only one instance can run at a time (flock on `cloq_work/exppilot.lock`).

## What it does

| | Step | Rule |
|---|---|---|
| A | Phase-2 release | Once `analysis/fork/newmethod/expansion_<m>.json` (q8, m24) has `expand: true`, it queues every missing f04–f06 `nmp_tau2_*` / `nmp_score_*` task of `phase2_cells`, plus the §2.4 gates of the q8 reference cells. Each cell family goes through its own generator: `make_tasks_m24.py panel --phase 2`, `make_tasks_rotpanel.py --panel --phase 2`, `make_tasks_kivi.py --phase 2 --gate-suffix _fx` and `make_tasks_bank_u.py --nmp-phase2`. Every generator refuses unless the record allows the cell. A q8 record that breaks the A5.3 KIVI pairing or leaves out the reference cells is refused. Priority tiers: m24 −30, rotation −27, KIVI −29, reference −27. Score tasks use the cell's phase-1 score tier. If `expand` is not true, nothing is queued. |
| B | Analyses (CPU, 30 min timeout, at most 3 attempts, run once) | `analyze_newmethod.py --model <m>` runs only after the model's record exists, and once every panel + score task of the admitted cells is done. That means phase 1 of `eligible` (with their BFCL forks), plus phase 2 of `phase2_cells` if the record expanded. After T_deadline (2026-10-04 12:00 PDT) it runs on whatever exists. `analyze_sameprec.py` and `analyze_sameprec_w3.py` each run once after the 2026-10-04 00:00 PDT freeze. Outputs and one line in `analysis/fork/out/EXPPILOT_LEDGER.md` are committed with explicit paths, followed by `pull --rebase --autostash` and `push`. |
| C | GPU fill | Idle GPU = a non-simulator card of a live `cloq-node` job, in idle state, not drained. Demand = the GPUs of todo tasks whose dependencies are done and that fit a live runner. If idle > demand on 2 consecutive loops, it moves deferred tasks into todo in (priority, age) order: priority −19, plus `requeue_note "exppilot fill <ts>"`, and a gate_same fork gets `fail_loud`. Per loop it releases at most (idle − demand) GPUs' worth, and only onto idle cards that can host the task (node pin, NVLink pairs). |
| D | Health | Logs `starved` once per hour when nothing is runnable and nothing can be released. Any task family (first three id tokens) with more than 3 failures in 2 h stops being released. |
| E | Status | Every 30 min it logs one paragraph: queue counts by family, idle GPUs vs demand, releases and analyses, and the actions taken since the last paragraph. |

**Never released from deferred:** the main-session stops (`pert_q4_rtn_w3_restore_early_q345`, `a6k2_q32_tel_rtn_w4`, `pert_q8_rtn_w3_restore_rand_attn_s3_q345`); any task whose `deferred_note`, `deferred_reason` or `defer_note` contains "stopped"; `ext_l8_`, smoke and l8 tasks; `kind: sim` tasks; g12 tasks (W100p gate FAIL); and tasks whose dependencies are not all done.

To keep one more task out of the fill, add "stopped …" to its `deferred_note`.

## What it never does

- It never runs sbatch, scancel or kill, and never touches `queue/running/`.
- It never opens `analysis/fork/holdout/` and never edits `configs/frozen_v*.json`, manifests or protocols.
- It never reads a panel outcome to decide what to queue. From the expansion record it reads only `expand`, `phase2_cells` and `eligible`.
- It writes no protocol note. §5.6 only requires the record to exist before phase 2 is queued. Editing the protocol would also break the `PROTOCOL_SHA256` guard in `analyze_newmethod.py`.
- It commits only its own analysis outputs and ledger lines.
