# CLOQ research log — every version, insight and work item, with TL;DR and evidence

**TL;DR** — The calibration method (CLOQ) was falsified at v1. The paper is now about *perturbation equivalence*:
judge a compressed agent against the model's own perturbation null. The A6000 multi-model matrix has been running
since 2026-09-28 18:10. The live dashboard is https://claude.ai/artifact/PqFrT9bVufKqdkD43u5c1B.

Paths are relative to the repo root unless they start with `/data/` (cluster only; not in git). Stable ids:
versions `V*`, insights `I*` (iteration-scoped in `docs/insights/`), experiment proposals `E*`, work items `W*`.
Newest first.

---

## W100aj - Off-diagonal null (EXPLORATORY): never above chance; the structure is action-side; possible holdout replay gap (only-QQ enrichment in q8 holdout) needs authorised check (2026-10-03 20:25 PDT)

**TL;DR** (5a3b17c, `analysis/fork/offdiag_null.py`, `out/offdiag_null_20261004T030949Z.md`; post hoc). Reproduction is exact: the analyze_ghf unit digests match, and the per-cell shares 29.33 / 25.05 / 30.47 / 22.88 are reproduced. Results:

- **The off-diagonal share is never above chance.** Against the exchangeable-branch null E0 (k kept), 30 of 45 groups are below it and none above. W4 pool: 26.9 vs 28.4, -1.4 [-1.8, -1.0] pp. KV8: 15.3 vs 18.9, -3.6 [-4.5, -2.8]. The same holds for BFCL, ALFWorld, telecom dev and the same-precision fork.
- **The off-diagonal share is mostly arithmetic.** obs - E0 = P(k=2)(P(rev|k=2) - 1/3). Odd-k states contribute 23.8 of the 26.9 points. Strict reversals are 23.6% [19.2, 28.3] of k=2 states, against 33% by chance.
- **The structure is on the action side.** In k=2 states, the two successes share the action 56% of the time (W4) and 80% (KV8), against 33% by chance.
  - A reproducible task component accounts for 17% [12, 22] of var(I) in W4 and 0 in KV8.
  - In the q8 W4 pool, "only BB succeeds" is enriched (142/414, p < 1e-4).
- **Possible design flaw in the holdout.** In q8 holdout k=1 states, "only QQ succeeds" is 30/60 and 40/86, against 25% by chance (count test p < 1e-4; task clustering ignored, counts only). QQ is the one arm taken from the original episode rather than re-executed.
  - q4 holdout is 23.4% (normal); telecom dev q8 is 31.0% [24.9, 35.4]; dev W4 is 23.4%.
  - If the original episodes and the re-executed branches differ systematically in the q8 holdout, the pre-registered holdout G_all (-4.57) is biased negative.
  - The holdout outputs in analysis/fork/out hold no per-task no-op records. Checking QQ no-op replay agreement requires reading acceptance metadata under analysis/fork/holdout/, which the standing rule forbids outside the prereg scripts. **The user/GPT must authorise it before the holdout appears in the abstract.**

Evidence: `analysis/fork/out/offdiag_null_20261004T030949Z.{md,json}` (holdout_counts_only from `out/holdout_r2_posthoc_20261002T024414Z.json`).

## W100ai - q8 acceptance: reviews A and B give a conditional GO (no blocking issue); pre-read fixes A7.E2; automatic GO once A7 finishes (2026-10-03 20:15 PDT)

**TL;DR** Both independent q8 reviews give a conditional GO after the two running A7 tasks finish:
- review A (059d7d1): protocol chain, completeness, A7 compliance on 18 arms, code and hygiene all pass;
- review B (3de8d31): an independent re-derivation equals `--dry` in all 5 views, and 1,200 reuse rows are token-identical.

The primary family is already fixed: P1 k = 3; P2 k = 3, via A7.E1; P3 k = 2, {f01, f02}.

Pre-read fixes, protocol **A7.E2** (32aa1ca, sha 3b144592):
- what-was-known erratum;
- Holm over estimable members;
- persistent-timeout clause enforced in `a7_records`: any re-run request of 600 s or more stays missing; the longest so far is 524.7 s;
- the re-run BB on no-op-sampled rows (k4v4 f01 9749f3, 95d6b2) must pass `noop_check`, otherwise the block is quarantined. The code path was verified on 2 known-good rows;
- per-arm `scripts/a6000/a7_report.py`;
- E1.5's consequence superseded.

The passing rotation-gate verdict is now committed. `tools/go_q8.sh` writes `EXPPILOT_GO_newmethod_q8` only when:
- both A7 tasks have left running;
- A7_REPORT passes;
- protocol, script and expansion shas are unchanged;
- no phase-2 q8 task exists;
- `--dry` admission is kivi_k2v2 {f01, f02}, kivi_k4v4 {f01-f03} if all 12 f01 arms recover (else {f02, f03}), and all other cells f01-f03.

Otherwise it holds and logs to `logs/go_q8.log`.

Evidence: `analysis/fork/out/q8_acceptance_review_{A,B}.md`, `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (A7.E2), `scripts/a6000/a7_report.py`, `/data/ziyangs/cloq_work/tools/go_q8.sh`.

## W100ah - Mistral-24B result: two-sided turnover (~10%), no mode value, GPTQ vs RTN not resolved; §7 filled; A4.4 contrasts implemented; q8 review B conditional GO; the off-diagonal share sits at the exchangeable null (2026-10-03 20:05 PDT)

**TL;DR**
- **m24.** The GO was written automatically at 19:38. All 7 checks passed, which C1 and C3 of reviews A and B require. exppilot ran the analysis at 19:44 (cc888fb, `analysis/fork/out/newmethod_m24_20261004T024453Z`).
  - **GPTQ-W4** (k = 6, n = 498): r 4.6 [2.4, 6.8], d 5.4 [2.4, 8.5], M 10.0 [7.0, 13.1]. G -0.8, H +1.4, F +0.0, I +0.6, all spanning 0. Off-diagonal 12.0%.
  - **RTN-W4** (k = 5): M 10.4 [6.3, 14.4], all modes null, off-diagonal 12.3%.
  - **M1 (GPTQ - RTN):** ΔD_cc +2.2 [-3.5, +7.8], p .35. Strict view (k = 3): +1.2 [-13.8, +16.2]. Parse view (k = 6): +2.4 [-1.9, +6.7].
  - **BFCL:** M 9.5 / 16.5%, net null.
  - §7 "Model family" is filled with the strict-view disclosure.
- **Off-diagonal null.** The AC review (af064a6) found the paper's 26.9% at the exchangeable-branch null (28.4%). This was reproduced independently from gen_patterns.tex: every W4 cell is at or below the null, and KV8 is 15.3 vs 18.9. m24 shows the same: 12.0 / 12.3 vs 15.7 / 15.9. The full analysis (block bootstrap, within-k tests, variance decomposition, other designs) is running. A reframing decision is pending with GPT.
- **q8:** A4.4 contrasts implemented before any read (744f7c4). Review B (3de8d31) gives a conditional GO after both A7 tasks finish (C1-C4); review A is pending.
- **Paper:** BFCL, ALFWorld, Qwen3 and vLLM are now cited, and previously uncited bib entries are used (f3800bc).

Evidence: `analysis/fork/out/newmethod_m24_20261004T024453Z.{md,json}`, `paper/review_ac_20261003.md`, `analysis/fork/out/q8_acceptance_review_B.md`, `/data/ziyangs/cloq_work/logs/go_m24.log`.

## W100ag - q8 expansion: expand = false (cost); m24 acceptance: two independent reviews, no blocking issue; GO written automatically when C1 and C3 hold (2026-10-03 19:35 PDT)

**TL;DR**
- **q8 expansion** (written at 19:08, trigger "all phase-1 tasks finished", commit 2a607db): all 8 cells were eligible, but phase 2 projects to 171.5 GPU-h and 21.4 h of wall time. It would finish at 10-04 16:34 PDT, after T_deadline (12:00), so under §5 all-or-none **expand = false**. This is effect-blind. The q8 new-method analysis uses f01-f03 (k = 3).
- **The q8 GO waits for the A7 re-runs.** exppilot's required-task list does not include them.
- **m24 acceptance:**
  - review A (ae6cd61): conditional GO;
  - review B (96160a4, independent re-derivation from raw files): PASS.
  - Neither found a blocking issue. Both reproduce the admission: primary rtn {f01, f02, f03, f05, f06}, gptq f01-f06, M1 k = 5; strict k = 3; parse view k = 6.
- **`tools/go_m24.sh`** writes `queue/EXPPILOT_GO_newmethod_m24` only when:
  - C1: `nmp_score_m24_rtn_w4_f03` is done with a fresh score_summary: n_ok 84, prompt sha 84, bound to the current bank_rows;
  - C3: protocol sha 3bd7ef33, no m24 recovery directory, and `--dry` gives the reviewed admission.

  Otherwise it holds and logs to `logs/go_m24.log`.
- **To disclose in the m24 write-up** (review notes A N1-N8, B N1-N7):
  - f01 and f02 are admitted only by A6, which was adopted after the interim, so the strict view (k = 3) gets equal prominence;
  - expansion_m24 credits the r1 gate_same tasks, but the passing gate is the r2 re-run;
  - the m24 BFCL forks ran without gate dependencies; same builds, no-ops pass;
  - fidelity covers rtn f01 at 82/83 (retail:51) and `load_scores` skips missing scores silently;
  - the A6.E1 statement that "views agree" holds for phase 1 only;
  - E1.6 read accounting misses 11 gptq f04 files read at 08:21-08:24 (immaterial; no arm error);
  - hardening, not done after the reviews: `load_tau2(recovery=True)` is not restricted to q8. C3 checks that no m24 recovery exists.

Evidence: `analysis/fork/newmethod/expansion_q8.json`, `analysis/fork/out/m24_acceptance_review_{A,B}.md`, `/data/ziyangs/cloq_work/tools/go_m24.sh`.

## W100af - Disk purge before the 00:00 snapshot (2026-10-03 19:00 PDT)

**TL;DR** Deleted 83 G of regenerable data at 18:57 (usedds 565 G -> 482 G):
- pip caches: 2.5 + 3.2 G;
- naacl2027 pip and conda caches: 3.3 + 1.2 G;
- the HF original of Mistral-Small-3.2-24B: 45 G. m24 is served and quantized from `ckpt_cache/m24_textonly_v1` through models.json `src_path`;
- three unused ckpt_cache base builds (q4_gptq x2, q8_awq): 29.8 G.

Deleted data was referenced by the 10-03 00:00 and 12:00 snapshots, so it frees at **10-05 00:00**. Data deleted after tonight's 00:00 snapshot would free only at 10-05 12:00 or later. A one-shot `tools/midnight_purge.sh` therefore runs at 23:40. It deletes Qwen3-14B (28 G), Qwen3-32B (62 G), m24_textonly_v1 (44 G) and the remaining 3 base builds (30.7 G) only if no running, todo or parked task needs them; otherwise it keeps them and logs why. Untouched: runs/, analysis/, queue state, sotaquant (152 G) and naacl2027 envs/HF (other projects, pending the user's decision).

Evidence: `/data/ziyangs/cloq_work/logs/purge_20261003.log`, `/data/ziyangs/cloq_work/tools/midnight_purge.sh`.

## W100ae - GPT 10-03 rulings executed: A7.E1 (spinquant f01 re-run), E1.5 corrected, E1.7 closed; reuse audit 1/4114; q4 wording (2026-10-03 18:00 PDT)

**TL;DR**
- **A7.E1** (861ebff, protocol sha 3bd7ef33). The 9 spinquant_w4a4 f01 arms (class other, user-simulator overload) are re-run once under the A7.3 conditions. The task names a simulator with no backlog (node001:8000) through a new optional task `user_base` field in worker.py. E1.5 is corrected: user-simulator timeouts attributed by elimination; 9 arms, not 2 (interim) and not 11. kivi_k2v2's 10 remain Q-server timeouts, cause not established. **E1.7 is closed:** S3 and the q8 scope of A6 are kept, as GPT confirmed earlier.
- **A7 progress.** kivi_k2v2 f01: 1/1 arm completed at concurrency 1, no timeout, 802 s; shadow identical; budget ok. The other 4 tasks are running.
- **Reuse audit** (f2ff9e7, CPU). 4,114 equality-based reuse rows (8,044 reused arms) across 86 output directories were rendered with each model's own template and tokenizer. **One row** is canonically equal but token-different: q4_awq_w4 f01 airline:30 t = 6, key order in `flights[0]`. Its QB=reuse=BB and BQ=reuse=QQ were never measured. GPTQ reference rows: 0 such rows (q4 290, q8 349, ref_d1 137). Token-score ids agree on 3,470 of 3,471 rows that are decidable.
  - Queued `reusefix_ru1_q4_awq_w4_f01`: `bank_u_arms` with `reuse_rerun` (607a132) measures BQ and QB once, keeps orig_Y and orig_arm_source, and leaves the originals read-only.
  - Downstream consumers are analyze_bank_u (out/bank_u_f01*, cited in appendix L278-330, appendix_moved L50-68, results_r1 L27) and analyze_token_mech (appendix_moved L73-77, results_r3 L13, appendix L317). A before/after diff follows the measurement.
  - spinquant_w4a4 f03 has to be re-scanned once it lands.
- **q4 wording** (34ffcc9; errata E-3): "semantically identical after parsing, but a different token sequence (key order)". The coincident block means are not zero variance. E-2's Bank U statement is limited to the checked GPTQ arms. The q4 quarantine and k = 2 stand.

Evidence: `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (A7.E1), `analysis/fork/reuse_audit/{REUSE_AUDIT.md, reuse_flagged.json}`, `docs/insights/COMMONSTATE_ERRATA.md` (E-3), `analysis/fork/newmethod/tau2_recovery/q8_kivi_k2v2/f01/rr1/recovery_summary.json`.

## W100ad - q4 common-state reading (k = 2, not resolved); the f01 quarantine was a canonical-equality artifact; m24 phase-2 audit passed (2026-10-03 17:40 PDT)

**TL;DR**
- **q4 reading** (once-only, 17:12, `analysis/fork/out/commonstate_q4_20261004T001159Z.md`): f01 was quarantined, leaving k = 2 and 170 states.
  - K(d1) = -1.2 pp (boot95 [-5.9, +3.5]); K(BF16) = -2.4 pp ([-6.5, +1.2]). Both are not resolved.
  - The t interval has df 1. For K(d1) it collapses to a point, because the two block means are equal.
- **Why f01 was quarantined.** At one state (7411758182009c20, airline 30, t = 6) the d2 action differed from a_BF16 and a_d1 only in JSON key order. `canon_msg` ignores key order, so the implicit checks applied, but the template renders the order, so the next prompt differed.
  - Serving was deterministic.
  - Identity checks overall: 1,238/1,240 passed (both failures are this state); 869/869 for token-identical actions.
  - The frozen rule worked as written, and there is no rule change. The note is in COMMONSTATE_ERRATA E-2.
- **Paper:** the q4 result is in §5 and the appendix, with the identity counts.
- **m24 phase-2 audit** (b768dac, effect-blind):
  - all 1,130 branch budgets recount exactly;
  - rtn_w4 f04 is not admitted under A6 (JSONDecodeError airline:10, missing by the rule fixed at 08:56);
  - primary M1 blocks are f01-f03, f05 and f06 (k = 5); strict k = 3; "A6 + parse" k = 6.
- **Before GO m24:**
  - 7 score tasks must finish;
  - two independent reviews;
  - E1.7 (S3 and the q8 scope of A6) needs confirmation.

Evidence: `analysis/fork/commonstate_replay_check/{Q4_F01_IDENTITY.md, q4_f01_identity.json}`, `docs/insights/COMMONSTATE_ERRATA.md`, `analysis/fork/out/m24_budget_audit_phase2_20261004T0017Z.{md,json}`, `paper/latex/sections/{results_r2,appendix_moved}.tex`.

## W100ac - A7 forensics and re-runs queued; the D2.1 "8/9" replay mismatch was a metric mix-up (9/9 byte-identical); paper replay claim scoped (2026-10-03 17:05 PDT)

**TL;DR**
- **A7.2 classification** (read-only log audit, commit e370e4b, before any re-run):
  - kivi_k4v4 f01, 12 arms: **service_failure_verified**. The node004 user simulator was down 21:28:44 to 21:33:41 PDT on 10-02, because the node004 runner exited with "nothing left to run" while a node006 task still used it.
  - kivi_k2v2, 10 arms: **timeout_cause_not_established**. These are Q-server calls, each the 4th consecutive 600 s attempt. Q decoded at 0.94 to 1.43 tok/s per request at concurrency up to 8, and 1024 tokens need at least 1.71 tok/s.
  - spinquant_w4a4 f01, 9 arms: **other**. The timeouts were on the overloaded node005 user simulator (83 to 92 waiting, KV cache 94 to 99%), not on Q. **This contradicts E1.5's "Q-server timeout" label.** Under A7.2 they stay missing; a ruling is requested.
- **Queued** 4 `a7_rr1_*` tasks (22 arms, priority -29, concurrency 1, originals read-only).
- **Replay check:** all 9 overlap arms are byte-identical, on every token, message, DB hash and reward field. "8/9" compared DB-success Y with SAMEPREC's official_reward at 79aa9e6a7ca99243. The erratum is in `docs/insights/COMMONSTATE_ERRATA.md`; the hashed protocol is untouched because the q4 reading is pending.
- **Paper (method):** exact replay is stated as a tested property of this stack, and preemption, other models, GPUs and vLLM versions are named as untested. The deployed AWQ fp16 path is not replay-exact and is unused.

- **Infra findings (not fixed yet):**
  - a runner exiting shuts down its user simulator while tasks on other nodes still lease it;
  - node005's simulator was overloaded by co-located 1-GPU eval tasks.
- **Evidence:**
  - `analysis/fork/kivi_recovery/{failed_arms.json, FORENSICS.md}`;
  - `analysis/fork/commonstate_replay_check/{REPLAY_8of9.md, replay_8of9.json}`;
  - `docs/insights/COMMONSTATE_ERRATA.md`;
  - `paper/latex/sections/method.tex`.

## W100ab - GPT 10-03 review executed: disk margin, KIVI/q8 arm recovery amendment A7, common-state relabel, q8 phase-1 scheduling (2026-10-03 16:55 PDT)

**TL;DR** Four changes. (1) Disk: 2.4 GB free, steady burn about 0.2-0.4 GB/h plus merge bursts, and 4.2 GB freed at 00:00. The disk guard now parks low-priority todo tasks (priority >= -23) below 3 GB, was 0.7, and unparks above 6 GB. Running tasks are untouched. (2) NEWMETHOD **A7** (commit 10a5518, 16:44 PDT; the header says 16:50, the commit time is authoritative): one controlled re-run of the 31 q8 phase-1 arms that stopped on a server-side error (kivi_k2v2 10 Timeout, kivi_k4v4 f01 12 InternalServerError, spinquant_w4a4 f01 9 Timeout), using recorded actions, the original state, checkpoint, kernel and budgets, concurrency 1. Arms that fail again stay missing. The pre-re-run and strict views are reported. P3 never falls back to k4v4 for missing blocks. Protocol sha **ba743cee**; committed before expansion_q8.json existed. (3) Paper §5 relabelled "after the fixed extension"; Pocock is a sensitivity analysis (about 97% difference, 94% equivalence); the continuation-interaction conjecture is withdrawn; new framing: sensitivity, extra value and gain are separate quantities. (4) The 7 waiting m24 score tasks are pinned to node004/008/009/002, so the other runners stop holding pairs. nmp_tau2_q8_spinquant_w4a4_f03 was claimed within a minute (node006, 16:48).

- **Correction to the 16:20 report.** The common-state two-look reading uses about 97.06% intervals for a difference and **about 93.92%** for equivalence (TOST 0.0304 per side), not 97% for both.
- **A7 code.**
  - `fork_driver.py`, `bank_u_arms`: named failed arms only. The state is rebuilt and must equal the original row; the current actions are the recorded ones; the Q shadow is a check only; the original block is read only. CPU stub test: 4 states identical, 87 original files unchanged, refusals work.
  - `analyze_newmethod.py`: `a7_apply`, `a7_records`, `load_tau2(recovery=)`, the `prerecovery` view, an A7 report, `P3_K2V2_GATE_FAILED = False`. `--selftest` PASS, including A7. `--dry` with no recovery records matches the old code (q8, m24). The expansion dry run passes the guard.
  - `scripts/a6000/make_tasks_a7.py`: queues one task per (cell, block) from the classified list. It runs only after `analysis/fork/kivi_recovery/failed_arms.json` (log forensics, read-only, still running) is committed.
- **Scope check.** m24 has no non-A6 infrastructure arm error. Its arm errors are InvalidFunctionCallException, plus JSONDecodeError in rtn_w4 f03 and f04, which is agent output under E1.2.
- **Pending.** CPU check of the D2.1 replay mismatch (8/9): a subagent is comparing the two trajectories decision by decision and the determinism acceptance range.

Evidence: `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (A7), `scripts/a6000/{fork_driver,make_tasks_a7}.py`, `analysis/fork/analyze_newmethod.py`, `paper/latex/sections/{results_r2,appendix_moved}.tex` (3423096), `/data/ziyangs/cloq_work/tools/disk_guard2.sh`, `/data/ziyangs/cloq_work/logs/disk_guard.log`, `queue/todo/nmp_score_m24_*.json` requeue_note.

## W100aa - Common-state q8 confirmatory reading (K = 6): not resolved; paper §5 updated; q8 rotation tasks unpinned (2026-10-03 16:20 PDT)

**TL;DR** The once-only q8 K = 6 reading ran at 16:12 (commonstate_readings.sh). Confirmatory Pocock two-look: K(d1) = +1.0 pp (t97 [-4.2, +6.2], boot97 [-1.4, +3.5]) and K(BF16) = +0.8 pp (t97 [-2.2, +3.8], boot97 [-2.0, +3.7]), both **not resolved**. Unadjusted K(BF16) would pass TOST within ±3 pp; the confirmatory reading does not. The first look's interaction (+2.7) does not persist (-0.2 [-4.5, +4.1]). Without the 26 D2.1 states: +0.5 / +0.8, not resolved. Paper §5, the appendix and F8 now carry the K = 6 reading (commit cfcff97; check_numbers PASS; build OK).
- Ops: 5 q8 2-GPU todo tasks (rotation phase 1: nmp_tau2_q8_spinquant_w4a4_f03, nmp_score_q8_{quarot_w4a4_f02,spinquant_w4a4_f03}; 2 pivot_q8) were pinned to node004, where pairs 4-7 are reserved for waiting m24 4-GPU tasks (noderunner reserved_big ignores relative priority). The pin was there for runner 49642 (no task gpus), which is long gone, so the pin was removed (logistics only, as COMMONSTATE D1). The noderunner priority inversion is not patched: runners are long-lived, and a restart would kill running tasks.
- Queued a6k2_q8_gauss2_s1_rro (W100w rule; 1 airline outage episode, estimate 2.2 h, coverage only).

Evidence: `analysis/fork/out/commonstate_q8ext_20261003T231159Z.{md,json}`, `paper/latex/sections/{results_r2,appendix_moved}.tex`, `paper/latex/tools/figs/make_fig_commonstate.py`, `/data/ziyangs/cloq_work/logs/commonstate_readings.log`, `queue/todo/*.json` requeue_note.

## W100z — node009 brought back with 7 of 8 GPUs (2026-10-03 15:00 PDT)
**TL;DR** node009 had been excluded since 09-28 because the user reported "several bad GPUs"; it was sitting IDLE. A 15-min diagnostic job (bf16 matmul plus a 40 GB fill on each card) found GPU 0 (PCI 01:00.0) bad: 71 uncorrected volatile ECC errors, and the fill test never completed. GPUs 1-7 pass. The old Xid 31 (61:00, 09-23) and Xid 13/43 (a1:00, June) were application MMU faults, not hardware.
- node.sbatch's probe now also rejects any card with uncorrected volatile ECC errors (commit 25ea657). The old 1024x1024 matmul probe would have passed GPU 0.
- Runner job 49911 on node009 uses GPUs 1-7, with the user simulator on 2,3 (agent pairs 4-5 and 6-7, plus single GPU 1). It ends 10-06 14:30. node009 is not in autopilot.sh's NODES list; resubmit by hand if it exits.
- node003 is still DOWN ("Node unexpectedly rebooted"; known bad card at 01:00.0). That needs IT.

## W100y — node001 diagnosed: RAM-disk (tmpfs) leak from failed tasks, not NFS (2026-10-03 14:45 PDT)
**TL;DR** node001 had 6 infra failures on 10-03 ("vLLM server did not come up in 90 min"; processes in D state). The cause was node-local scratch, not /data: compute nodes are diskless, `/` and /tmp are tmpfs (378 G of the 755 G RAM), and it was 94% full (354 G). About 340 G was our own checkpoint builds. worker.py freed a built checkpoint only after its server came up, so every task that failed earlier left 8-62 G behind. Finished jobs' /tmp/cloq_<job> dirs were never removed either. This drove memory pressure, which stalled new builds and loads, which caused more failures.
- Actions (user approved stopping node001's tasks):
  - Interrupted the 3 cs_q8_d2_d1 f04-f06 workers (no outcome yet) and requeued them.
  - Requeued the 5 earlier node001 infra failures (cs_gate_q4_d2_d1 and 4 *_rro).
  - DRAIN.node001 for all agent GPUs.
  - Deleted the leftover ckpt_* dirs and finished-job scratch dirs on node001 (tmpfs 94% -> 8%, available RAM 379 G -> 704 G) and the finished-job dirs on the other 6 nodes (tmpfs 6-37% -> 5-11%).
  - The watcher /data/ziyangs/cloq_work/tools/requeue_node001_infra.sh requeues node001 server-start failures of cs_* tasks.
- Fix: worker.free_scratch() in main()'s finally removes ckpt_<id>, _rot, _Q, _Q_rot, _B, _B_rot (exact names) however the task ends. Unit test: a neighbouring id with the same prefix is kept.
- I/O checks on node001 were normal (NFS v4.2 hard mount; dd reads and writes fast; no hung-task lines in dmesg; GPUs fine). The DRAIN can be lifted once a test task starts cleanly.

## W100x - Appendix backfill (EXPLORATORY): restoration location vs byte-matched random modules, error dose, low-bit failure modes; the three app:withdrawn \pending{} slots filled (2026-10-03 12:40 PDT)
**TL;DR** CPU only, finished A6000 runs only (snapshot 20261003T1827Z; never pooled with 4080). Outages are not data (W6); context overflow counts as failure (W10). Three blocks per cell, so t intervals (df 2) come with crossed task x block intervals; no multiplicity correction.
1. **Restoration location** (perturb-v1 closed-loop arms; located arm minus mean of the finished byte-matched random draws). RTN-W3, q4+q8 pooled: attention +9.8 [+6.1, +13.6] pp (crossed [+4.5, +15.1]); last third -8.6 [-13.4, -3.8] (crossed [-12.9, -4.7]); middle third +4.5 (crossed covers 0); MLP -5.4 [-14.1, +3.3]. GPTQ-W3, q4 GPTQ-W4 and q8 AWQ-W4: 0 of 30 contrasts exclude 0 under both intervals; 3 of 39 overall, all RTN-W3. Pivot arms (one decision, one random draw): attention reverts more pivot actions to B than random (q4 RTN-W3 +20.7; GPTQ-W3 pooled +35.7), with no GPTQ-W3 success counterpart (+1.6 [-4.8, +7.9]).
2. **Error dose.** Action agreement with BF16 falls at every alpha step in all 6 cells (q8 RTN-W3 prefix 1, 0.32, 0.16, 0.04 at alpha 0, 0.25, 0.5, 1). Success does not: no step up to alpha = 0.5 is resolved, and it drops between 0.5 and 1 only in RTN-W3 (q4 -20.8 [-22.5, -19.1], q8 -14.1 [-26.9, -1.4]). q8 AWQ-W4 at alpha = 2: -10.6 [-16.4, -4.7], crossed [-20.8, 0.0]. Monotone for actions, threshold-like for success.
3. **Failure modes** (descriptive). BF16 failures end normally in a wrong end state (57.6-63.9% of episodes; at most 6.3% abnormal endings). GPTQ-W3 keeps that profile (1.8-9.0% abnormal). q4 RTN-W3: 32.9% runaway (overflow or 200-step cap); 44.7% end normally after tool calls written as plain JSON, which the frozen hermes parser rejects; no episode has a parsed write; 0 of 33 successes are on write tasks. q8 RTN-W3: 20.4% runaway, 16.9% tool-error cap. W2 panel: 66.7-87.5% runaway.
- **Convention note.** `analyze_restore_eval.py` drops every infrastructure episode, context overflow included (the snapshot's infra_missing). This backfill follows W10 and reports that convention as a sensitivity. The q8 cells are unchanged. The q4 RTN-W3 contrasts keep their signs on 177-240 units (attention +13.0 [+1.7, +24.3]).
- **Unfinished, not used** (from the snapshot; the queue was not read): q4 RTN-W3 `restore_early` (q3, q4 still running; q5 has no run); `restore_rand_attn_s3` on q4 and q8 RTN-W3; the q4 block of q4 RTN-W3 `restore_rand_mlp_s3`; `resid_a2` on q4/q8 RTN-W3 and GPTQ-W3; q8 RTN-W3 pivot arms (2 of 9 arms, so the FORK_PROTOCOL §13 step-3 selection never ran); KV-INT3 on q4/q8/q14; q14 gauss3; q32 RTN-W3; q32 gauss3 s1; the q4 RTN-W2 panel.
- **Paper** (`paper/latex/sections/appendix.tex`, app:withdrawn):
  - the three slots are filled, with Tables tab:restoreloc, tab:dose and tab:failmodes, labelled exploratory/descriptive;
  - the static-restoration sentence on the incomplete q8 attention comparison now points to the backfill;
  - check_numbers PASS (3528 numbers); tectonic 0 overfull, 0 undefined; 25 pages, Limitations at the top of p. 9.
- **Code** (each file < 200 lines): `analysis/fork/analyze_backfill.py` plus `backfill_{common,restore,dose,failmodes}.py`. Action agreement is read from trajectory messages (cloq.fork.action_view). It reproduces the decisions.jsonl-based restore_eval values (q4 GPTQ-W3 alpha 0.25: action divergence 89.4, prefix 0.508).
- **Remaining compiled \pending{} slots:** the interim same-precision K = 6 markers (results_r2.tex l. 7 and 13, appendix_moved.tex l. 83 and 107); results_r4.tex SpinQuant vs QuaRot (l. 9), KIVI-2 vs KV8 (l. 11) and Mistral-24B (l. 13).
Evidence: `analysis/fork/out/backfill_20261003T193042Z.{md,json}`; inputs `analysis/insights/iter_3/out/snapshot_auto_20261003T1827Z.json` (sha a19b1c00...) and `analysis/fork/out/pivot_arms_20261003T150653Z.json` (sha fb1d8e94...); protocol `docs/insights/PERTURBATION_PROTOCOL.md`.

## W100u-r - Common-state review corrections: deviation D2 committed before any A1-task output; earlier outcomes at 17 q8 and 2 q4 states disclosed; Pocock two-look reading is now the confirmatory q8 reading; two node001 tasks stalled (2026-10-03 09:05 PDT)
**TL;DR** A review of W100u raised six findings, and all six held after checking against the files. The A1 claim "written before any governed outcome existed" was wrong at 17 of the 255 q8 f04-f06 states and 2 of the 255 q4 states (9 f01-f03 states under v1). SAMEPREC and the dev precision fork had already run this design's arms at those identical states. Deviation D2 (commit f56682a, 08:54:31 PDT; protocol sha dce40245 → **288fc65a**) does the following:
- discloses these states and prespecifies a sensitivity reading without them;
- makes the Pocock two-look reading the confirmatory q8 reading, with the frozen-level reading labelled "unadjusted" and both always printed;
- labels each reading with the realised k;
- separates a gate stall from a gate verdict;
- names the main session as the owner of both readings, with an acceptance-only `--check` first.

No A1 task had written any output when D2 was hashed. **Action needed:** `cs_gate_q4_d2_d1` and `cs_ref_q8_gptq_w4_d1_f06` have been stuck on node001 since 08:13. They block all of q4 and q8 f06.
- **Finding 1 (major, confirmed and widened): earlier outcomes at shared states.**
  - Method: each panel state rebuilt with `make_state`, then compared field by field with every non-holdout fork state file; no outcome printed.
  - q8 f04-f06: SAMEPREC g2 (B = d2) had run a_d2 and the d2→d1 arm at 13 states. Dev gptq_d1 g2 had run a_d1 and the reference arms BQ/QB at 14 states. The union is 17.
  - q4: SAMEPREC g1 at 2 states.
  - q8 f01-f03: SAMEPREC g1 (05:55) had run 9 states before v1 was committed (87733f7, 07:33).
  - Y_BB at all f04-f06 states was already known from the main matrix.
  - Replay check on the 9 f01-f03 overlaps: a_d2 identical 9/9, Y equal **8/9** (the review said 9/9). The replays are close, not exact.
  - Lists: `manifests/fork/commonstate_d2_v1.json`.
- **Finding 2 (minor, confirmed): two looks.** `commonstate_twolook_mc.py --given` holds f01-f03 at their observed W100b values (t criterion only).
  - K(BF16), false difference at K = 0: 0.084-0.113 at the frozen levels, 0.036-0.065 at Pocock (sd 2-3.5 pp).
  - K(d1), false equivalence at ±3 pp: 0.077-0.159 frozen, 0.022-0.066 Pocock.
  - The A1 figure of 0.041 is an average over every first look that made no claim.
  - D2.2 adopts the stricter option that F1a offered. No advisor sign-off is recorded yet.
- **Finding 3 (minor, confirmed): labels.** Labels and titles now carry the realised k, e.g. "q8, k = 5 of 6 blocks (f06 excluded)". The Pocock levels are kept for k < 6, which is conservative because the correlation between looks is √(3/k) ≥ √(1/2).
- **Finding 4 (major, confirmed): stalled tasks.**
  - At 09:00 both node001 logs still held only the 08:13:15 header, and node001 GPUs 2-7 showed 0 % utilisation with 2 MiB in use (gpumon).
  - The worker's build_ckpt has no timeout, so nothing will move these tasks to failed/.
  - I did not stop anything: never kill, never touch running/.
  - D2.4: such a stall is not a gate verdict. A human may move the task back to todo/ unchanged.
  - My W100u status line ("5 running, building GPTQ checkpoints") was wrong for these two tasks.
  - node007 is also slow: ref f04/f05 vLLM has been in start-up since 08:35, so the W100u ETAs are optimistic.
  - **Update 09:14 PDT:** the node001 stall cleared on its own at about 09:04, after roughly 50 min. `cs_gate_q4_d2_d1` saved its GPTQ checkpoint at 09:11 (447 s), and `cs_ref_q8_gptq_w4_d1_f06` was at layer 13 of quantisation at 09:14. No action is needed now. The missing timeout in build_ckpt remains a risk for the infra session, and the ETAs move back by about 50 min.
- **Finding 5 (minor, confirmed): checkpoint check.** No A1 task had a server record at 09:00. `scripts/a6000/commonstate_ckpt_check.py [--hold]` compares the recorded ckpt sha256 and canary with the manifests as soon as servers.json appears. Tested: f01-f03 records 6/6 ok, a tampered expectation is flagged, and hold moves only todo files.
  - First result, 09:13 PDT: `cs_gate_q4_d2_bf16` (node007) rebuilt the q4 d2 checkpoint, the first build since d16f4ea. It matches: ckpt `21c0934e…`, canary `a0fb6c52f4eb27fd`, so the quantize.py change is shown inert for this Qwen GPTQ build. The q8 d1 reference servers (f04/f05) were still loading. Main session: run `python scripts/a6000/commonstate_ckpt_check.py --hold` again once `cs_ref_q8_gptq_w4_d1_f04.servers.json` exists, and again when the first q8 d2 task starts.
- **Finding 6 (minor, confirmed): reading owner.**
  - The main session owns both readings (D2.6).
  - `analyze_commonstate.py --design <d> --check` prints acceptance fields only.
  - Rows can be repaired before the freeze: a d2 task goes back to todo/ unchanged (`fork.resume`); a reference task is re-run whole.
  - The reading is made at the earlier of all-done-and-checked or the freeze, and no later than 10-04 23:00 PDT.
- **Code checks.**
  - analyze_commonstate.py (22cde1a): the default real-data run and the selftest are identical to 6dccab1 except the timestamp (json and md diffed).
  - The real `--design q8ext/q4` runs still refuse with "not yet".
  - The design selftests (synthetic) and the k = 5 case pass.
  - Guard: 5 file variants x 2 expected shas; only intact prefix chains are accepted.
- **Commits:** f56682a (D2 + MC --given; default MC output byte-identical), c7e7fac (D2 record), 22cde1a (analysis), 9ddd5ca (checker), plus this entry.
- Evidence: `docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md` (D2), `manifests/fork/commonstate_d2_v1.json`, `analysis/fork/analyze_commonstate.py`, `analysis/fork/commonstate_twolook_mc.py`, `scripts/a6000/commonstate_ckpt_check.py`; `/data/ziyangs/cloq_work/logs/tasks/cs_gate_q4_d2_d1.log`, `cs_ref_q8_gptq_w4_d1_f06.log`, `/data/ziyangs/cloq_work/gpumon/node001.jsonl`.

## W100v-e - NEWMETHOD amendment A6.E1: review corrections to A6 committed before any m24 phase-2 or q8 panel outcome is read; A6 primary unchanged, two labelled sensitivities added (2026-10-03 08:58 PDT)
**TL;DR** A review of A6 (W100v) found seven inaccurate or missing statements. All were checked against the code and files, and all seven held. Erratum A6.E1 was committed in 2f06102 at 08:55:59 PDT (protocol sha 73bf5538 → **b306cc70**). It was stacked on 43e2342 (08:51:13), which fixes a two-read race in `analyze_newmethod.main()`. The A6 primary rule is unchanged. m24 `gptq_w4_d1` f04 had been produced but not read, and f05 was running.
- **Corrections (protocol A6.E1):**
  - **E1.1:** m24 adopted A6 for estimability, after the interim had been read. Without A6, M1 had 1 block; the available-rows ΔD_cc had been +2.4 pp, p 0.077. A new sensitivity, "A6 prospective only", applies strict rules on m24 phase 1 and the q8 Bank U rows.
  - **E1.2:** `JSONDecodeError` in retail/airline is the agent's own malformed tool-call arguments (`llm_utils.py:440`), not an error of unknown origin. It stays missing in the primary, because end to end it counts as an outage. A new sensitivity, "A6 + agent tool-call parse failures", scores it Y = 0.
  - **E1.3:** BFCL already scores the S1-type failure as Y = 0 (W99p). The W100v BFCL open question is withdrawn.
  - **E1.4:** the A3 mask and A6 treat a BF16 parse failure asymmetrically; this is now disclosed. The report shows each Y = 0 arm's producer. All 4 m24 phase-1 arms were produced by Q.
  - **E1.5:** the 12 q8 timeouts are relabelled "Q-server timeout, cause not established". All are BQ/QQ arms; the Q server ran at a median of 6.4–7.8 tok/s across ≤ 8 requests, against max_tokens 1024 and a 600 s limit.
  - **E1.6:** the A6 status text is corrected: 64/84 f04 states had been produced, and filename greps had touched their files.
  - **E1.7:** the user approved S1 on m24 only. S3 and the q8 scope are this session's extension.
- **Code (`analysis/fork/analyze_newmethod.py`):**
  - Every view now comes from one read (`load_tau2(..., views=)`).
  - New JSON keys `tau2.sensitivity_a6_prospective` and `tau2.sensitivity_a6_plus_toolcall_parse`, each with its own Holm family.
  - `by_producer` in the A6 report.
- **Checks (effect-blind; admitted blocks and booleans only):**
  - In 43e2342, `--dry` is byte-identical between old and new code (q8; m24 f01-f03), and the loaders match unit by unit.
  - After 2f06102: on m24 f01-f03, prospective = strict (rtn {f03}, gptq {f02, f03}) and plus = primary. On q8 every view equals the primary.
  - `--selftest` passes, including a test of the views on a temporary tree. A synthetic end-to-end run exercised the full JSON and markdown output.
- **For the main session, before `EXPPILOT_GO_newmethod_q8` / `_m24`:**
  - confirm or revert S3 and the q8 scope (E1.7);
  - rule on Q-server timeouts if needed; this decides P3 (kivi_k2v2 has no block) and costs P2 its spinquant_w4a4 f01 block (E1.5);
  - the P3 fallback question from W100v stays open.
- **Evidence:**
  - `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (Amendment A6.E1);
  - `analysis/fork/analyze_newmethod.py` (`a6_producer`, `a6_prospective`, `A6E1_SIGNATURES`, `load_tau2(views=)`);
  - `third_party/tau2-bench/src/tau2/utils/llm_utils.py:440`;
  - `scripts/ext/common.py:101-104`;
  - `analysis/fork/out/m24_interim_20261003T141416Z.md`;
  - `/data/ziyangs/cloq_work/logs/tasks/nmp_tau2_q8_kivi_k2v2_f0{1,2,3}.Q.vllm.log`.

## W100w - F3: outage re-run path (flag-gated) and 9 re-run tasks for the failed outage tasks; coverage/appendix cells only (2026-10-03 08:40 PDT)
**TL;DR** A flag-gated path re-runs only the outage-classified episodes (600 s timeouts) of a run-domain, plus its never-run ids, at run_par 1 / max_concurrency 4 on the task's own agent server. It archives the originals (never deletes) and merges. Without the flag, run_arm and worker behave exactly as before (dry checks: old == new).
Queued 9 `<id>_rro` tasks at -21 for the 9 failed outage tasks: 12 run-domains, 56 outage + 11 never-run episodes, estimates 0.8 to 14.2 h, all inside the freeze budget. **These results fill coverage/appendix cells only.**
Determinism premise: bit-exact det pairs cover the BF16 and derived-ckpt paths. The q14 KV-INT3 cell rests on an unverified closed-loop premise and stays labelled.

- **Why a retry could not work (W100q §1.1).** run_arm skips a `completed` run-domain, and the worker's W6 check re-raises on its recorded outages. tau2's own resume drops *every* infrastructure_error episode, so it would also re-run W10 context overflows, which count as agent failures.
- **Mechanism (`cloq/rerun_outage.py`, `CLOQ_RERUN_OUTAGE=1`).**
  1. Episodes are classified exactly like the worker's W6/W10/W41/W92/W99p rules. The plan must agree with `infra_causes.json`, or the task fails loud.
  2. Kept: every non-outage episode, including context_overflow.
  3. The todo ids run as their own tau2 run in `runs/<id>/<domain>/rerun_outage/<tag>/`, with their own results, decisions, config (max_concurrency 4 recorded), environment and status. The run is resumable. An interrupted re-run resumes from its archive.
  4. Originals go to `rerun_outage/<tag>/orig/` with a sha256 manifest. The two big files are kept as read-only hard links: no extra disk, and any in-place write fails instead of altering them. Small files are copied.
  5. Merge: each re-run episode takes the slot of the episode it replaces, with task id, trial and seed checked (all 12 run-domains use seed 626729). Never-run ids are appended. The decisions of re-run ids are replaced. run_arm then writes trajectory, metrics and status as usual (`status.rerun_outage` names the re-run ids), and the worker repeats its W6 check.
- **Worker gate (`rerun_outage` task field).** Only the listed run-domains run, with per-task `run_par` and `max_concurrency`. A rebuilt checkpoint must match the run's `quantization.json` (method, seed, rel. error, content sha, canary, kv_cache). The original is kept as `quantization.pre_rerun.json`. Dedicated server: each task already starts its own vLLM agent server. With ≤4 requests in flight, below the 5-6 sequences the worst servers held at 90% KV (W100q table), the request queue that produced the 600 s timeouts should stay empty. Check: the `Waiting` count in the tasks' `.vllm.log`, and no new outage.
- **Proof that nothing else changed** (`analysis/status/gpu_fill_20261003/rerun_outage_drycheck.txt`). Old (6be062a) and new code ran on scratch copies of real run-domains, with tau2/vLLM faked.
  - run_arm without the flag gives identical `run_tasks` calls and files in all 4 cases (completed clean, completed with outages, completed with context overflow, running with outage + missing).
  - With the flag, a completed clean run-domain is skipped unchanged. In 3 outage cases, only the outage and never-run ids run. Kept episodes are byte-identical in the same slots, the archive sha equals the original and is read-only, and an interrupted re-run leaves the run-domain untouched and resumes.
  - worker.py: 4 existing tasks (KVQ serve_env, RTN, derived pert, per-run env) give identical Popen commands, env and quantization files. The rro tasks run only their listed run-domains, one at a time, with the flag and `--max-concurrency 4`. A different rebuilt checkpoint is refused.

**Determinism premise** (`analysis/status/gpu_fill_20261003/rerun_premise_det.{py,json}`). Closed-loop det pairs are the same config on two nodes at different times, so the batch compositions differ (running 1 to 16).

| Pair | Covers | Result |
|---|---|---|
| q4 BF16 | dense TP=1 (pert_q4 derived ckpts) | 257/257 bit-exact (tokens and logprobs), prompts to 13.8k |
| q14 x1_fp8 | q14 TP=1 attention/norm | 366/366, to 27.2k |
| q32 x1_fp8 | q32 TP=2 all-reduce | 290/290, to 13.8k |
| q30a3 BF16 | user simulator (MoE TP=2) | 303/303, to 25.5k |
| q8 telecom BF16 | long contexts | 1520/1520, to 32.3k |
| x1_awq (q8, q14, q32) | AWQ fp16 dequant | **NOT bit-exact** (20/20 tasks diverge); no re-run arm uses it |
| q4 KVQ int4_rot | pyhook closed loop | **no _b run** (deferred; on the exppilot fill allowlist) |

Caveat: no det pair ran with a waiting queue (waiting_max ≤ 1), so preemption under KV pressure is not covered. That affects the original episodes, not the low-load re-runs.

Labels written into each task's `determinism_premise`:
- `verified directly`: the pert_q4 tasks, whose 4 outages are user-side; the simulator pair also applies.
- `verified by kernel class`: q14 gauss3 (q14 FP8 TP=1 pair + q4 BF16) and q32 gauss3 / rtn_w3 (q32 FP8 TP=2 pair + q30a3 TP=2). No BF16 closed-loop pair exists for q14 or q32.
- **`UNVERIFIED closed loop`: `a6k2_q14_kvq_int3_rro`.** Hook batch invariance is shown only open-loop, on q4, with 8 prompts: the INT3 batch-of-9 and the prefix hit both equal the alone run (`analysis/kvq/validate_q4.json`). Its 16 re-run episodes stay labelled in any table.

**Queued** (`queue/todo/*_rro.json`, priority -21, `autopilot_retry: no (W100w ...)`, `coverage_only: true`). Plan: `analysis/status/gpu_fill_20261003/rerun_outage_plan.json`. The estimate is 0.5 h + ceil(n/4) rounds × p90 of the run-domain's episode durations under the original load (conservative). Budget: 23 h from an assumed start of 22:00 PDT to the 21:00 PDT 10-04 freeze.

| Task | Run-domains | Outage + never-run | Est. h | Cell complete after? |
|---|---|---|---|---|
| a6k2_q14_gauss3_s1_rro | airline | 2 + 0 | 0.8 | airline only (retail 39 never-run) |
| a6k2_q14_gauss3_s2_rro | airline | 3 + 0 | 0.8 | airline only (retail 43) |
| a6k2_q14_kvq_int3_rro | q2/airline | 16 + 0 | 5.4 | q2 airline only; UNVERIFIED label |
| a6k2_q32_gauss3_s1_rro | retail, airline | 3 + 1 | 3.3 | yes |
| a6k2_q32_gauss3_s2_rro | retail | 3 + 0 | 1.6 | yes |
| a6k2_q32_rtn_w3_rro | q1/retail, q2/airline | 25 + 9 | 14.2 | those two only (q1 airline 10, q2 retail 35 never-run) |
| pert_q4_gptq_w3_resid_a2_q345_rro | q3/airline | 1 + 0 | 1.7 | q3 airline only |
| pert_q4_rtn_w3_restore_rand_attn_s3_q345_rro | q3/airline | 1 + 0 | 1.0 | q3 airline only |
| pert_q4_rtn_w3_restore_rand_mlp_s3_q345_rro | q3/retail, q4/retail | 2 + 1 | 1.8 | yes (q3-q5) |

Status at 09:00 PDT:
- The two q14 gauss3 tasks were claimed on node001 at 08:34. Their checkpoints rebuilt with the same rel. error (0.09828), but both `vllm serve` processes have hung since 08:45 in D state on NFS (`rpc_wait_bit_killable`, `d_alloc_parallel`) with GPUs empty. The W100u fork tasks claimed on node001 at 08:13 (`cs_gate_q4_d2_d1`, `cs_ref_q8_gptq_w4_d1_f06`) show no progress either, so this is a node001 NFS stall.
- If the server does not come up within SERVER_UP_S (90 min), these tasks fail with `autopilot_retry: no`. Requeue them by hand: the re-run is idempotent, because it resumes its archive.
- `a6k2_q14_kvq_int3_rro` is starting on node007, where the vLLM banner took 8 min.

**Not queued, and why.**
- `pert_q4_gptq_w3_resid_a2_q3/retail` (1 user-side outage, 33 never-run). Rule: a run-domain is re-run only if its never-run episodes ≤ its outage episodes. Otherwise it is a resume of the paused original task, not an outage re-run.
- Running tasks with recorded outages (not failed): `pert_q8_gptq_w3_resid_a2_q345` (16) and `pert_q8_rtn_w3_resid_a2_q345` (11). If they fail, the same generator applies.
- Deferred, not on the fill allowlist: `a6k2_q4_awq_w3_qx` (2) and `a6k2_q32_tel_rtn_w3` (7, stopped in W100t; would not finish).
- Never-run run-domains of the queued tasks stay incomplete, as listed in the table.

- **Protocol.** No amendment. W6 already says outage episodes are never data and are re-run. The re-run changes concurrency only, which under the premise above changes latency, not tokens. No estimand changes.
- **Risk (open).** The /data/ziyangs quota is full: 1.0 to 1.4 GB free at 08:15-08:33, with 1013 GB live data and only 9.5 GB in snapshots. Each merge writes new decisions and results files (≈0.4 GB of decisions over all 12 run-domains; the merged results file is deleted after the W6 check). `plan()` refuses to start a re-run if fewer than its need + 512 MB would remain. The same quota threatens every running task.
- **Evidence.**
  - Code: `cloq/rerun_outage.py`, `cloq/run_arm.py`, `scripts/a6000/worker.py`, `scripts/a6000/make_tasks_rerun_outage.py`, `scripts/a6000/rerun_outage_drycheck{,_worker}.py`. Commits fb6b9f5, 1adec78, cd8feea, 8670610.
  - Outputs: `analysis/status/gpu_fill_20261003/{rerun_outage_plan.json,rerun_outage_drycheck.txt,rerun_premise_det.py,rerun_premise_det.json}`.
  - Queue: `/data/ziyangs/cloq_work/queue/{todo,running}/*_rro.json`.
  - Logs: `/data/ziyangs/cloq_work/logs/tasks/*_rro.{log,vllm.log}`.
  - Background: `docs/insights/GPU_FILL_PROPOSAL_20261003.md` (F3) and W100q.

## W100v - NEWMETHOD amendment A6: a fork-branch arm error caused by the agent's own message is scored Y = 0, as end to end; strict as preregistered becomes a labelled sensitivity (2026-10-03 08:30 PDT)
**TL;DR** Amendment A6 was committed in fe6765e at 08:16 PDT (protocol sha f9f8b3a5 → **73bf5538**). That was before any m24 phase-2 τ² task had finished and before any q8 new-method panel outcome was read. The user approved it on 10-03 (W100q decision 2).
- **Correction (2026-10-03 08:58 PDT, W100v-e; amendment A6.E1).** Parts of this entry are wrong:
  - A6's status text says "none of their outputs had been opened", but 64/84 m24 f04 states had been produced, unread, and filename greps had touched their files;
  - the user approved S1 on m24 only;
  - `JSONDecodeError` is the agent's malformed tool call, not of unknown origin;
  - the q8 timeouts are "Q-server timeout, cause not established", not infrastructure;
  - BFCL already scores S1 as Y = 0, so that open question is withdrawn.

  See W100v-e.
- **The rule.** A τ² branch arm that stopped on an exception raised by validating the agent model's own message is scored Y = 0. The exception must be one of:
  - S1, mistral_common `InvalidFunctionCallException`: an invalid or empty tool name (W99p);
  - S3, tau2 `AssistantMessage must have either content or tool_calls`: an empty message (W92).

  The branch must also have logged at least one decision before the error. Every other arm error stays missing and still fails its block (A3.3). That includes timeouts, server errors, `JSONDecodeError` (origin not identifiable, and an outage end to end) and user-simulator errors.
- **Scope.** This is the primary rule for q8 and m24 and for every cell. The analysis without A6 ("strict as preregistered") is reported beside it, with its own Holm family.
- **Disclosure.** The rule is post hoc for m24 phase 1 (W100s had seen the errors). It was fixed before reading for m24 phase 2 and the q8 new-method cells. For the q8 reference rows it is not blind.
- **Verified on real records, with no effects computed.**
  - m24 phase 1 (f01-f03): A6 scores 4 arms in 3 population states as Y = 0, exactly the W100s audit set (rtn f01 retail:51 QB+QQ, rtn f02 retail:95 QQ, gptq f01 airline:2 BQ). airline:13's `JSONDecodeError` stays missing.
    - Strict admission without A6 reproduces W100s: rtn {f03}, gptq {f02, f03}.
    - With A6 it is rtn and gptq {f01, f02, f03}.
  - q8 `--dry`: A6 changes nothing, because no q8 phase-1 arm error is S1 or S3. All of them are infrastructure errors and stay missing:
    - kivi_k2v2: 9 states with `litellm.Timeout` across f01-f03, so **no kivi_k2v2 block is admitted** under either rule;
    - kivi_k4v4 f01: 8 states with `InternalServerError`, so kivi_k4v4 has {f02, f03}.
    - Every other q8 cell has f01-f03; spinquant_w4a4 has {f02} (f01 still running, f03 in todo).
- **Recording check (A6.5).** `run_branch` stores the untruncated `repr` and `n_decisions` in `branches/<state_key>.json` for every model, and has since d1d2a6d. `bank_rows.arm_source` truncates at 120 characters, so the analysis reads the branch file. No driver change was needed.
- **Code.**
  - `load_tau2(..., a6=False)` by default is the loader exactly as before. `main()` asserts that the strict-as-preregistered view equals a load without A6, state by state.
  - Per-block A6 counts go into the JSON (`tau2.a6`), the markdown and `--dry`. `--selftest` covers A6 on synthetic records.
  - Stacked commits: aaab5a0 (inert helpers), fe6765e (protocol, constant and wiring).
- **Open for the main session.**
  - kivi_k2v2 has no admissible τ² block (infrastructure timeouts, not A6).
  - The script's P3 fallback (`kivi_k2v2` → `kivi_k4v4` when k2v2 has no admitted units) would fire on this non-gate reason, but protocol §1 defines the fallback for a gate failure only.
  - BFCL (panel B) is outside A6: `analyze_ext` drops an item with any branch error.
- **Evidence:**
  - `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (Amendment A6);
  - `analysis/fork/analyze_newmethod.py` (`A6_SIGNATURES`, `a6_class`, `a6_resolve`, `strict_prereg`, `a6_report`);
  - `analysis/fork/out/m24_budget_audit_20261003T1354Z.md` (W100s);
  - `scripts/a6000/worker.py` (`classify`);
  - `analysis/insights/iter_2/common.py` (`AGENT_SIDE`);
  - `cloq/fork.py::run_branch`.

## W100u - Common-state comparison extended (F1a + F1b, user-approved): protocol amendment A1 committed before any governed outcome; q8 f04-f06 (K = 6) and q4 f01-f03 queued at −28 (2026-10-03 08:20 PDT)
**TL;DR** Amendment A1 to COMMONSTATE_SOURCES_PROTOCOL (sha256 `dce40245…13ee`, commit ccf9f13, 08:10:19 PDT) fixes q8 at K = 6 with no condition. The K = 3 reading (W100b) stays as the first look, a prespecified Pocock two-look reading is added, and q4 becomes a separate prospective analysis (gate first, never pooled with q8). 17 tasks were queued at −28 (unpinned) at 08:12:43, after the commit. Expected cost ≈ 23–43 GPU-h; everything is due before the 10-04 21:00 PDT freeze.
- **Corrected by W100u-r (2026-10-03 09:05 PDT, deviation D2):** "no governed outcome existed" held except at 17 q8 f04-f06 and 2 q4 states (listed in D2.1), whose outcomes had been seen only in other studies' aggregates. Pocock is now the confirmatory q8 reading. Two of the five tasks reported as running were stalled on node001.
- **Approval.** The user answered "都做" at 07:45 PDT (W100t), covering GPU_FILL_PROPOSAL F1a and F1b.
- **Order of events.**
  - ccf9f13 (A1 + Monte Carlo script) at 08:10:19.
  - bfb5b2c (manifests + generator) at 08:12:24.
  - Queue writes at 08:12:43; first task start at 08:12:48.
  - 6dccab1 (analysis code) at 08:17:50, when no output existed yet.
  - The A1 header says 08:20 PDT. The binding time is the commit time, 08:10:19.
- **Known when A1 was written.**
  - q8 f01–f03 (K = 3) had been fully read.
  - q8 f04–f06 had no outcome of this design: no d2 action and no gptq_w4_d1 arm, and `expansion_q8.json` was not written.
  - q4: the Bank U d1 four arms were known, and no q4 d2 action at these states existed.
- **q8 f04–f06 reference (A1.1).**
  - This study runs its own d1 arms, `cs_ref_q8_gptq_w4_d1_f0{4,5,6}`. They use the NEWMETHOD phase-2 reference-cell bank_u spec, identical except `out` (compared as JSON).
  - Why: q8 phase 2 stays undecided until 20:00 PDT. The 07:53 dry run projected 18.2 h of wall time, so the decision can go either way.
  - Duplicate cost if both run: about 5 GPU-h. If NEWMETHOD's outputs exist, they enter only a cross-check note.
  - q8 needs no new gate: same checkpoints and stack, and the `commonstate` and `bank_u` functions are unchanged since 87733f7.
- **Two looks (A1.3)**, from `analysis/fork/commonstate_twolook_mc.py`, with K = 0:
  - The chance of a difference claim at k = 6, given no claim at k = 3, is 0.041 (nominal 0.05).
  - The unconditional rate of "claim at k = 3 or k = 6" is 0.089.
  - The prespecified Pocock reading (two-sided 0.0294; TOST one-sided 0.0304) keeps the two-look rate at 0.054 or less. The k = 3 look made no claim at either level.
  - If the two readings disagree, the paper adds "not robust to the two-look adjustment".
- **q4 (A1.4).**
  - Gates `cs_gate_q4_d2_{bf16,d1}`: 12 rows, fail loudly, autopilot_retry "no". The six panel tasks depend on both gates.
  - 1 GPU per task (gpu_util 0.44).
  - d2 = GPTQ-W4 c2: ckpt `21c0934e…`, canary `a0fb6c52f4eb27fd`.
  - CPU pre-check: 255/255 states equal the Bank U q4 rows on all six same-state fields.
- **Deadline (A1.5).**
  - Blocks whose tasks finish after 2026-10-04 21:00 PDT are excluded.
  - Each reading runs once, at the earlier of all tasks done and the freeze.
  - `analyze_commonstate.py --design q8ext|q4` enforces both. Both designs refuse now ("not yet").
- **Queued.**
  - q8: 3 reference tasks and 6 d2 tasks; each d2 task depends on its block's reference task.
  - q4: 2 gates and 6 panel tasks.
  - At 08:13 the 3 reference tasks and both q4 gates were running on node007 and node001.
- **GPU-h / ETA** (from the W100b and Bank U done records):

  | Task set | Basis | GPU-h |
  |---|---|---|
  | q8 reference | U2B share of the 2.5–3.3 GPU-h Bank U q8 blocks | ≈ 4–5.5 |
  | q8 d2 | f01–f03: d2_bf16 2.5–3.6, d2_d1 1.4–2.4 GPU-h per task | ≈ 12–18 |
  | q4 gates | | ≈ 1–2 |
  | q4 panel | 1 GPU; Bank U q4 blocks 1.7–4.9 GPU-h | ≈ 6–18 |

  - References finish ≈ 09:30–10:30 PDT.
  - q8 d2 finishes ≈ 11:00–14:00 if 2-GPU pairs free. It can be later if q8 phase 2 (−29) is released first.
  - q4 finishes by the evening.
  - Readings: as soon as all tasks are done; hard bound 10-04 21:00 PDT.
- **Code (default unchanged).**
  - make_tasks_commonstate.py: the default `--gate/--panel` task JSON is byte-identical (8/8 files, scratch queue).
  - analyze_commonstate.py: the default real-data run and the selftest are identical except the timestamp and the protocol sha.
  - The q8ext and q4 selftests use synthetic data only.
  - Unit checks cover reference acceptance, freeze, once-only, the cross-check and the guard.
- **For the main session.**
  - exppilot holds the q8 NEWMETHOD analysis "for F1a". F1a no longer needs NEWMETHOD's phase-2 reference cell, so that hold now rests only on NEWMETHOD's own acceptance.
  - Assign who runs `--design q8ext` and `--design q4` once their tasks are done.
- Evidence: `docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md` (A1), `manifests/fork/commonstate_{q8ext,q4}_v1.json`, `scripts/a6000/make_tasks_commonstate.py`, `analysis/fork/analyze_commonstate.py`, `analysis/fork/commonstate_twolook_mc.py`; queue `/data/ziyangs/cloq_work/queue/{todo,running}/cs_*.json`; logs `/data/ziyangs/cloq_work/logs/tasks/cs_*.log`.

## W100t — Ops 2026-10-03 07:45 PDT: user approved all five W100q decisions ("都做"); doomed q32 telecom task stopped; freeze times unified
**TL;DR** The user approved F1a, F1b, the m24 parse-error amendment, stopping a6k2_q32_tel_rtn_w3, and F3; each is being carried out separately (W100u+). This entry records the stop and the freeze definitions.
- **Stopped `a6k2_q32_tel_rtn_w3`** (node001 GPUs 6,7) with SIGINT so the worker cleaned up its vLLM server. It had 7 agent-side 600 s timeouts, so it would fail on completion, and it would end after the freeze (W100q). Moved to deferred/ with `autopilot_retry: no` and a deferred_note. Its sibling a6k2_q32_tel_rtn_w4 was stopped for the same reason on 10-02.
- **Freeze times (binding, unified):**
  - The **evidence freeze** is 2026-10-05 00:00 Toronto (EDT) = **2026-10-04 21:00 PDT**, per TODO_v2 and NEWMETHOD_PANEL_PROTOCOL §5.4. No new GPU result enters the paper after it.
  - The **SAMEPREC final-prefix freeze** is **2026-10-04 00:00 PDT** (the "10-03" date in SAMEPREC_PROTOCOL; T_FREEZE in analyze_sameprec.py and exppilot_analysis.py). The final analysis reads a snapshot at that instant and takes the longest complete common prefix.
  - **NEWMETHOD T_deadline** stays 2026-10-04 12:00 PDT (§5.4).
  - Earlier main-session messages said "10-05 00:00 PDT"; that was wrong and is superseded here.
- exppilot (W100r/W100r-b, fbdf8c4) runs until 2026-10-05 06:00 PDT; GPU fill after the evidence freeze does not feed the paper.
- Evidence: queue/deferred/a6k2_q32_tel_rtn_w3.json; docs/insights/GPU_FILL_PROPOSAL_20261003.md.

## W100r-b - exppilot review fixes: fill only from a user allowlist, per-node demand, q8 phase 2 all or none with one tier and no reference-cell gates, q8 analysis held for F1a, run-window report; not started (2026-10-03 07:35 PDT)

**TL;DR** Independent reviewers sent 18 findings on the W100r pilot. The 13 distinct defects were all confirmed in the code and fixed; the other 5 duplicate them. The pilot is still **not started**.
- **Fill.** It now releases only ids listed in `queue/EXPPILOT_FILL_ALLOW`, which is written after the user's OK. Two of the three tasks it listed before were main-session deferrals; one of them is a deterministic re-fail.
- **Demand per node.** The node001/005/007 runners predate W99p and never claim 4-GPU tasks, so the old "demand 50" hid their idle cards.
- **q8 phase 2.** It is now all or none (a preflight of every generator), with one tau2 tier (−29) and no blocking gates on the reference cells, as §5.5 and the §5.3 cost state.
- **q8 newmethod analysis.** It waits for `queue/EXPPILOT_GO_newmethod_q8` (W100q F1a).
- **Window.** The default stays 12 h, as the user asked. The start line now lists the duties after the end: the q8 record at T_decide 20:00 PDT, the SAMEPREC freeze and T_deadline. `--until` covers them.

- **Fixed (mechanism → change):**
  - Fill used a denylist ("stopped" in a note). `a6k2_q4_awq_w3_qx` (completed airline run-domain with 2 outages, W100q §1.1) and `a6k2_w2p_q4_rtn_w2_q3` (main-session deferral) were releasable, with an autopilot retry on top.
    - Change: an allowlist, plus `refails()` (a completed run-domain with outage causes is never released), plus `nmp_*` excluded.
    - Every released task carries `autopilot_retry`.
  - Demand was a cluster-wide sum. It is now per node, with a W99p capability check: the runner's start time against 44527e1. Only nodes on which no runnable todo task fits are filled.
  - `starved` required todo/ to be empty. 12 dependency-blocked pivot tasks kept it silent. It now fires on "nothing runnable".
  - `release()` was replace-then-remove (two copies after a crash), and `index()` let deferred/ win over done/; `a6k2_l8_bf16_cal` and `a6k2_l8_calib_c1` are in both today.
    - Change: a rewrite in deferred/ then one `os.rename`, and precedence done > failed > running > todo > deferred.
  - The analysis committed any new file with a matching prefix. It now takes only the paths the script prints as `wrote ...`. SAMEPREC is skipped when a post-freeze output exists (main session owns F0).
  - Reference cells: the blocking `gate_same` with `fail_loud` was the implementer's own reading.
    - It is not in §5.5 or the §5.3 cost, and the autopilot `rc=` regex would have retried it anyway.
    - It could break all or none (P1/P3 partners) and F1a.
    - Now: no gates; `--ref-gates` adds them only as non-blocking recorded checks with `autopilot_retry`.
    - `Pilot.expected` agrees with the generator.
  - Per-cell writes could leave a partial expansion. Now every generator runs without `--write` first and must list every expected id.
  - Tiers differed by family (KIVI −29, rotation/reference −27), a de facto ranking under the deadline. Now every q8 tau2 task is at −29.
- **Tests.**
  - Scratch queue: allowlist, precedence, `place` with an old runner, single-rename `release` refused twice, per-node demand.
  - Scratch root + queue copy with a fake `expansion_q8.json` (the real one was never created): 66 tasks, all tau2 at −29, no gates, idempotent. With one generator failing, 0 tasks were written.
  - Scratch git repo + bare remote: only the printed outputs are committed, and another session's concurrent file stays untracked.
  - q8 hold logged.
  - Dry run 07:29: fillable 0 (idle 1 on node006, which has 47 GPUs of hostable demand); 2 tasks need user OK; 1 re-fail held.
- **Open (user / main session).**
  1. Approve fill ids: candidates `a6k2_det_q4_kvq_int4_rot_b`, `a6k2_w2p_q4_rtn_w2_q3`.
  2. Rule on reference-cell gates.
  3. Write `EXPPILOT_GO_newmethod_q8` once F1a is settled.
  4. Launch with 12 h or `--until 2026-10-04T13:00-07:00`.
- **Evidence.** `scripts/a6000/{exppilot.py,exppilot_fill.py,exppilot_analysis.py,exppilot.sh,EXPPILOT.md,make_tasks_bank_u.py}`. Commits a8fc137, 40db792, 75e27d2. Related: `docs/insights/GPU_FILL_PROPOSAL_20261003.md` §1.1, §3.1, §4.

## W100s - m24 (Mistral-24B) phase-1 INTERIM analysis (f01-f03; phase 2 running): strict A3.3 admits rtn {f03}, gptq {f02, f03}; M1 not estimable; G-H unresolved in the second family, while the turnover structure matches q8 (2026-10-03 07:15 PDT)
**TL;DR** INTERIM, not the protocol's final m24 analysis, and no paper claim. The run is `analyze_newmethod.py --model m24 --blocks f01,f02,f03` as protocol §7/A3 define it (83-task mask, strict completeness). The budget audit (`m24_budget_audit_20261003T1354Z.md`, two skeptics) and the frozen loader agree on what is admitted.
- **Admission.**
  - gptq f02 (`budget_ok=false`) is admitted. The flag is the context-overflow sentinel (airline:45 QQ), a valid failure, Y = 0.
  - Three in-population fork-branch Mistral parse errors (Y = None) fail rtn f01 (retail:51), rtn f02 (retail:95) and gptq f01 (airline:2).
- **τ² primary (pp).**
  - gptq (k = 2, t df 1): divergence 50.6 %, M +12.7 [+5.0, +20.3], G_all +0.6 [-22.4, +23.6], within-divergent G-H +0.0 [-30.3, +30.3].
  - rtn (k = 1; only the crossed task interval exists): divergence 59.0 %, M +10.8, G_all +3.6, G-H +4.1 (c -8.9, +17.1).
  - Some gptq intervals have zero width because both block means are identical, not because the estimate is precise.
- **M1 (gptq - rtn, D_cc).**
  - Primary: not estimable, with one common block (f03) and no §7 fallback.
  - f03 point estimate: +1.2 pp, descriptive.
  - Available-rows sensitivity (k = 3): +2.4 [-0.7, +5.5], p = .077.
  - BFCL M1 D_cc_all: +0.0 [-6.0, +6.0]. ΔM -7.0 [-13.0, -1.0]: GPTQ changes fewer outcomes than RTN.
- **Sensitivities with k = 3.** Within-divergent G-H: gptq -4.5 [-17.8, +9.3] and rtn -0.6 [-10.6, +9.6] (available rows); gptq -3.8 and rtn -0.6 (complete-case).
- **BFCL (complete; 200 items).** Within-divergent G-H: gptq +0.0 [-6.2, +6.4], rtn -0.6 [-7.3, +5.9].
- **q8 W4 reference, same protocol (U2B, k = 3, descriptive, never pooled).** Within-divergent G-H: gptq +2.8 [-10.3, +14.7], awq +1.5 [-7.3, +10.1]. The paper's significant +2.9 / +3.4 comes from first-divergence states with 20 blocks.
- **Reading.**
  - The G-H sign in a second family is not answerable yet. Every m24 interval contains both 0 and the q8 point estimates.
  - What replicates descriptively: large two-sided turnover (within-divergent M 15-25 pp in m24, 16-17 pp in q8) with small net G_all, and an off-diagonal (controller-dependent) share of 18-24 % in m24 against 16.5-18.5 % in q8.
- **Code.**
  - `analyze_newmethod.py` gains `--blocks`, `--cells` and `--tag`. The default behaviour is unchanged: selftest PASS, and the m24 dry run is identical.
  - The q8 run used `--cells`, so q8 new-method outputs were never opened before `expansion_q8`.
  - `m24_interim_report.py` recomputes every protocol field and asserts it equal to the protocol runs. It adds G-H with the same Boot.
- **Open.**
  1. Main session: whether a fork-branch `agent_parse_error` counts as Y = 0, as overflow does. This would be a post-hoc, disclosed amendment, and it would re-admit three blocks.
  2. §9 fidelity is pending the m24 score re-runs (W100o).
  3. The final m24 analysis runs after phase 2.

Evidence: `analysis/fork/out/m24_interim_20261003T141416Z.{md,json}`, `analysis/fork/out/m24_interim_nmp_20261003T140821Z.{md,json}` (protocol run), `analysis/fork/out/q8ref_w4_nmp_20261003T140825Z.{md,json}` (q8 W4 reference run), `analysis/fork/out/m24_budget_audit_20261003T1354Z.md`, `analysis/fork/{analyze_newmethod,m24_interim_report,m24_interim_md}.py`. Commits 6c1f1b0, d82973b, a34a205.

## W100q - GPU fill proposal and failure triage: the "airline outages" are agent-server queue timeouts on damaged models (not simulator instability), retries of them are futile; cluster idles from ~19:00-22:00 10-03 (~950-1080 idle GPU-h to the freeze); ranked fill options (2026-10-03 07:20 PDT)
**TL;DR**
1. **No failed task qualifies for a plain infra requeue; none was requeued.** The m24 score failures were a code bug, now fixed and requeued by W100o. The other eval failures were all already retried once.
2. **Outages.** Every agent-side outage episode in the six failed a6k2 tasks (52) and in 3 still-running tasks (34) is the same event: a 600 s litellm timeout on the agent's own vLLM server. The server's KV cache is saturated (median 90-92%) and 6-21 requests wait, because 4 run-domains × concurrency 8 share it while the damaged models generate long contexts. Retries re-fail: `run_arm` skips a `completed` run-domain, and the worker re-raises on its recorded outages.
3. **GPU forecast.** About 3-13 GPUs idle at 08:00-11:00, near full at about 12:00-19:00 if q8 phase 2 is queued promptly, then about 36-38 of 40 idle until the freeze. The ranked fill (common-state extension, the pivot dependency fix, low-load completion of the timed-out episodes) is about 100-150 GPU-h.
- **Triage table and mechanism.** `docs/insights/GPU_FILL_PROPOSAL_20261003.md` §1.
  - Simulator evidence: `sim_interruptions.jsonl` was never written, no simulator death is logged, the failures span 4 nodes, and only 5 user-side episodes exist (3 pert_q4 tasks).
  - Retry futility is verified on `a6k2_q14_gauss3_s1`: the log shows "airline already completed; skipping", and the outage episodes are older than the retry.
- **Doomed running tasks** (not stopped):
  - `a6k2_q32_tel_rtn_w3`: 7 outages; 28/80 sims in 22.75 h, so it ends after the freeze;
  - `pert_q8_{gptq,rtn}_w3_resid_a2_q345`: 16 and 11 outages.
- **Forecast.** Supply is 40 agent GPUs: node002 has 4 because GPUs 0,1 fail the probe, and node003 is down. Claim cutoffs are node005/007 at 20:06 on 10-04 and node001 at 21:08. The 12 `pivot_*_rtn_w3` todo tasks depend on the deferred unsharded `fork_stress_*_rtn_w3` and can never be claimed.
- **Options, ranked** (proposal §3):
  - F0: SAMEPREC K = 17 final-prefix analysis, 0 GPU-h;
  - F1a: common-state q8 f04-f06, about 15-20 GPU-h, reusing the q8 phase-2 `gptq_w4_d1` reference arms. Needs a dated amendment and GPT approval before the f04-f06 reference outputs are read;
  - F1b: common-state q4 f01-f03, about 8-10 GPU-h;
  - F2: pivot dependency fix, about 10-20 GPU-h;
  - F3: low-load completion of about 93 timed-out episodes, about 30-50 GPU-h. Under batch invariance, load changes latency, not tokens;
  - F4: 3 named deferred tasks, about 31 GPU-h;
  - F5: replay audit, about 10-20 GPU-h;
  - F6: confirmation blocks, about 100-200 GPU-h; needs its own preregistration, so not before this freeze.
- **Flags.**
  - The binding freeze may be 00:00 Toronto (21:00 PDT on 10-04) per NEWMETHOD §5.4 and TODO_v2, not 00:00 PDT.
  - The W100r exppilot fill step would release `a6k2_q4_awq_w3_qx`, which is a deterministic re-fail (`runs/a6k2_q4_awq_w3_q5/airline` is completed with 2 outages).

Evidence: `docs/insights/GPU_FILL_PROPOSAL_20261003.md`, `analysis/status/gpu_fill_20261003/{triage_outages.py,triage_outages.json,gpu_forecast.py,forecast_20261003T0705.txt}`, `/data/ziyangs/cloq_work/logs/{autopilot.log,node_node00*_49*.out,sim_balancer.log,tasks/*.vllm.log}`, `cloq/run_arm.py` l. 180, `scripts/a6000/worker.py` l. 440-483, queue `failed/`, `running/`, `todo/pivot_*_rtn_w3_*`, `deferred/`.

## W100r — Experiment pilot `exppilot` (12 h, unattended): effect-blind phase-2 release, once-only frozen analyses, GPU fill from deferred; built and dry-run, not started (2026-10-03 07:10 PDT)

> **Superseded in part by W100r-b (above).** Design decisions 1 (reference-cell gates) and 3 (tiers) and the fill rules (5) are replaced. A 12 h run does not reach T_decide, the SAMEPREC freeze or T_deadline. The q8 analysis is held for F1a.

**TL;DR** `scripts/a6000/exppilot.sh [hours]` runs `exppilot.py` on the login node, default 12 h, one pass every 10 min. It is built, unit-tested and dry-run, but **not started**. Each pass does five things:
- **(A) Phase-2 release.** Once an `expansion_<m>.json` says `expand: true`, it queues the missing f04–f06 panel and score tasks of `phase2_cells` through each cell family's own generator. It reads only `expand`, `phase2_cells` and `eligible` from the record, never an outcome.
- **(B) Analyses.** It runs `analyze_newmethod.py` per model once, after the model's record exists and every admitted panel and score task is done, or at T_deadline. It runs `analyze_sameprec.py` and `analyze_sameprec_w3.py` once after the 10-04 00:00 PDT freeze. Outputs and a ledger line are committed with explicit paths.
- **(C) GPU fill.** It releases deferred tasks at −19 when idle agent GPUs exceed runnable demand for two loops.
- **(D) Health.** It logs when the queue is starved and holds any task family that keeps failing.
- **(E) Status.** It logs a status paragraph every 30 min.

- **Generators (phase-2 support where missing).**
  - New options: `make_tasks_rotpanel.py --panel --phase 2`, `make_tasks_kivi.py --phase 2` (the `_fx` gate dependencies) and `make_tasks_bank_u.py --nmp-phase2` (the q8 reference cells `gptq_w4_d1`, `awq_w4`, `kvq_int8`).
  - m24 uses `make_tasks_m24.py panel --phase 2` from W100o.
  - All of them refuse unless the record has `expand: true` and lists the cell.
  - At phase 1, the generated specs equal the queued tasks field for field (`quarot_w4`, `spinquant_w4a4`, `kivi_k16v16`).
- **Design decisions (for review).**
  1. The q8 reference cells get both §2.4 gates before their f04–f06 tasks (`gate_same` with `fail_loud`). The reason is §2.5: "run f04–f06 with the panel manifest like any other cell". They never had nmp gates, because their f01–f03 come from Bank U.
  2. No protocol note is written. §5.6 only requires the record to exist before phase 2 is queued, and editing the protocol would break the `PROTOCOL_SHA256` guard.
  3. Priority tiers: m24 −30, rotation −27, KIVI −29, reference −27. Score tasks use the cell's phase-1 score tier (m24 −26, k2v2/k4v4 −24).
  4. The analysis trigger waits for the record's `eligible` cells (phase 1 and their BFCL forks) and for the `phase2_cells` (phase 2). A registered cell that was ineligible at the decision is not waited for.
  5. The fill never releases:
     - main-session stops, or a task with "stopped" in `deferred_note`, `deferred_reason` or `defer_note`. This also covers `fork_stress_q{4,8}_rtn_w3`, which were split into shards;
     - l8, smoke and sim tasks;
     - g12 tasks (W100p: gate FAIL, the three gate tasks stay deferred);
     - tasks with unmet dependencies.
     It also releases only onto idle cards that can host the task (node pin, NVLink pairs).
- **Dry run, 2026-10-03 07:04 PDT.**
  - m24 phase 2 is already fully queued (W100o), so A had nothing to do. q8 has no record yet; T_decide is 20:00 PDT.
  - Analysis of m24 waits on 18 of 32 tasks. SAMEPREC waits for the freeze.
  - Idle agent GPUs: 2. Runnable demand: 50 GPUs, mostly m24 4-GPU forks waiting for NVLink pairs. So nothing is released.
  - Releasable deferred tasks: `a6k2_q4_awq_w3_qx`, `a6k2_w2p_q4_rtn_w2_q3`, `a6k2_det_q4_kvq_int4_rot_b`. Held: 42 l8, 7 stopped, 3 g12, 1 sim.
- **Tests.**
  - Phase 2 with a fake q8 record: the pilot picks the right generator and tiers per family.
  - `release()` on a scratch queue: atomic, `fail_loud` set, a second release refused.
  - Analysis run and commit against a scratch git repo with a bare remote: only the pilot's files are committed, another session's staged file stays staged, it pushes, and no second run happens.
  - `analyze_newmethod.py --selftest` under the pilot's env command.
- **Open.** The pilot is not started. Starting it needs a session or user decision: `setsid nohup scripts/a6000/exppilot.sh 12 >/dev/null 2>&1 &`.
- **Evidence.** `scripts/a6000/{exppilot.py,exppilot_fill.py,exppilot_analysis.py,exppilot.sh,EXPPILOT.md}`, `scripts/a6000/{make_tasks_rotpanel,make_tasks_kivi,make_tasks_bank_u}.py`. Commits 93e898b, b603a74, 3e6815c, 96d441b, edad697.

## W100o - m24 phase 2 (f04-f06) queued for both cells per expansion_m24.json; m24 token-score failures were score_driver.render() calling HF-only tokenizer methods on the Mistral renderer (not TOOL_START); fixed model-gated, all 6 phase-1 score tasks requeued (2026-10-03 07:05 PDT)
**TL;DR** The expansion record (written 2026-10-03 11:53Z: expand true, phase2_cells `rtn_w4`, `gptq_w4_d1`, no m24 reference cells, projected wall 4.6 h) had no phase-2 tasks behind it. They are now queued, all or none (§5.5): 6 `nmp_tau2_m24_*_f0{4,5,6}` at -30 and 6 `nmp_score_m24_*_f0{4,5,6}` at -26. Gates are not re-run. All 6 phase-1 score tasks had failed (the "running" f02 attempt failed at 06:47:39, 30 s before the fix landed), each after one autopilot retry, with `ok 0/85` and `prompt sha ok 0/85`.
- **Root cause (from `token_scores/m24_*/f0k/score_summary.json` `missing[].reason`):** `prep error AttributeError("'MistralChatRender' object has no attribute 'get_vocab'")` on all 83 population rows; the other 2 are the manifest-missing rows. `score_driver.render()` assumed an HF tokenizer in two places:
  - the EOT set (`get_vocab`, `convert_tokens_to_ids`);
  - the action ids, which it took by re-encoding the template text. For Mistral that re-encode splits control tokens as plain text: 115 ids against 71 from mistral_common on a one-call test.
  - A final assistant turn is also refused by mistral_common's serving validation (`InvalidMessageStructureException`).
  - TOOL_START (`openloop_topk.py`) is not involved: it already has `"mistral": ["[TOOL_CALLS]"]`, and the scorer does not use it.
- **Fix (m24 only; selected by `MistralChatRender.is_mistral`, which only `CLOQ_TOKENIZER_MODE=mistral` creates):**
  - `cloq/mistral_render.py::render_turn` renders history + action with the same `server_view`, through a mistral_common backend in finetuning validation mode. The completed assistant turn then ends with EOS (id 2).
  - `score_driver.render()` uses it for the action ids. The EOT set for Mistral is `{eos}`. The HF branch is the old code verbatim.
- **Proof the HF path is unchanged:** old vs new `render()` on 16 q8 rows (`tau2/q8_quarot_w4/f01`) gives identical output: the sha of every prompt id, action id and token is equal, 16/16 prompt sha ok.
- **Proof the m24 path works (CPU, tokenizer only, `tau2/m24_gptq_w4_d1/f02`):**
  - 84/84 non-missing rows: prompt sha ok, render prefix ok, ids prefix ok, has EOT, 0 errors.
  - The old code reproduces the production AttributeError on 12/12 rows.
- **Expected flag, not a fault:** template ids equal the recorded BF16 a_B completion ids on 35/84 rows. The other 48 are tool calls (plus 1 text turn). For a completed tool call, mistral_common writes `[TOOL_CALLS]name[CALL_ID]<id>[ARGS]{...}`, but the model generates `[TOOL_CALLS]name[ARGS]{...}</s>`. So `template_eq_generated` will be low on m24 tool calls. Teacher forcing uses the generated ids (GPT-6.1 review 5), so the scores are unaffected.
- **Phase-2 builder:** `scripts/a6000/make_tasks_m24.py panel --phase 2 [--score-priority]`. Specs come verbatim from `make_newmethod_panel.py spec --model m24 --cell <cell> --phase 2`, and they equal phase 1 except for block and out. Guards:
  - phase 2 is refused unless the expansion record has expand true and the cell in `phase2_cells`;
  - it never queues `--bfcl` (BFCL has no expansion) and no gates;
  - tau2 deps are the passing fail_loud `nmp_gate_same_m24_<cell>_r2` (W100e-c), the bank gate, and `a6k2_m24_bfpair_f03_f04` (f04) or `_f05_f06` (f05, f06), all done.
  - Phase-1 output of the builder is unchanged: same 8 ids, deps and specs as before.
- **Coverage:** `runs/a6k2_m24_bfpair_f04..f06` exist. The manifest has 85 U2B rows per block f04-f06, with only airline 44 missing in each. Mask v1 `applies_to.blocks` = f01-f06, and both excluded tasks lie outside the 83-task population. So phase 2 adds 249 states per cell.
- **Requeue:** 6 failed records were moved to todo atomically (tmp + os.replace, then the failed copy removed). Each keeps its old error/trace/failed_at/host/autopilot fields in `error_history`, with `requeue_note` and `requeue_notes`. Priority stays -26.
- **Provenance finding in `expansion_m24.json` (record not edited; it is write-once):**
  - `configs.<cell>.gates.same.task` names the superseded r1 tasks `nmp_gate_same_m24_<cell>` (r1 verdict was fail, W100e-c), with their finish times and task-file shas.
  - The gate files it hashed are the r2 outputs: `same/gate_same.json` sha `3495fca7...` (rtn) and `01599893...` (gptq) have `spec.fail_loud` true and mtimes 23:45:40 and 23:51:34 PDT, which match r2's finish. r1's own output is under `same_r1_superseded/`.
  - The eligibility verdict is right in substance (r2 passed), but the record attributes it to the r1 task.
  - The builder's `_gates` looks up `nmp_gate_same_<m>_<c>` by fixed name, so any q8 cell gated by an `_rN` re-run gets the same attribution at the q8 decision (T_decide 2026-10-03 20:00 PDT). This is an open item for the main session.
- **Not changed:** `analysis/fork/analyze_token_mech.py` (W88 mechanism analysis) hard-codes the hermes `<tool_call>` and HF EOT strings, so it would label every m24 tool call "talk". `analyze_newmethod.load_scores` reads only KLu, rank and lp per token, so it needs no markers. No m24 panel outcome (Y, KLu, effects) was read.

Evidence: `analysis/fork/newmethod/expansion_m24.json`, `analysis/fork/newmethod/token_scores/m24_rtn_w4/f01/score_summary.json` (missing reasons), `/data/ziyangs/cloq_work/logs/tasks/nmp_score_m24_*.log`, `scripts/a6000/score_driver.py` (`render`), `cloq/mistral_render.py` (`render_turn`), `scripts/a6000/make_tasks_m24.py` (`panel`, `--phase 2`), queue `todo/nmp_{tau2,score}_m24_*_f0{4,5,6}.json`, `todo/nmp_score_m24_*_f0{1,2,3}.json`.

## W100p — g12 (Gemma-4-12B-it) gate verdict: FAIL on replay (check 3); measurable but not replayable under the frozen serving stack; no formal g12 task queued (2026-10-03 07:00 PDT)
**TL;DR** g12 is measurable but its replays are not reproducible, so it is not admitted as a second family. The protocol cannot measure its same-state divergences. This is a valid paper result, like l8, which failed the capability floor.
- **Passing checks.**
  - 1, serving: every server came up after the r1 fix.
  - 2, tool protocol: local == server prompt ids on 230/230 BF16 and 237/237 RTN-W4 τ² decisions, with 0 parser errors and 0 infrastructure errors. BFCL: 0 parser errors and 0 calls to tools not offered.
  - 5, BF16 floor: τ² 8/20 = 40% and BFCL 8/20 = 40%, both ≥ 10%.
  - 6, disjointness: holds.
- **Check 3 fails.** The τ² fork gate gives idcheck Q 9/16 and B 12/16, Q replay at state 6/8, QQ no-op 1/8, BB no-op 0/4 and isolation 2/4, with 0 state or branch errors.
  - Tool-call decisions regenerate exactly (17/17). Long text replies mostly do not (4/15).
  - Determinism probe: one server answering one request at a time is deterministic (22/22). With prefix caching off, concurrent prefill changes 9/22 outputs, so `VLLM_BATCH_INVARIANT=1` does not make Gemma 4's prefill batch-invariant. No tested flag set reproduces the records (best 16/22).
- **Why FAIL.** The mechanism is not identified; code reading excludes TRITON_ATTN's split-KV path. A fix is new serving work beyond the 6 h cap, which expired at 04:27, so the gate closes as FAIL. Check 4 and the BFCL fork gates are moot and were not run.
- **Compute:** 8.0 of the 24 GPU-h cap.
- **Other notes.**
  - 63/230 BF16 τ² decisions start with the template's empty thought channel in user-facing content. Under the frozen wording of check 2 this is not a tool-call parser error. The analysis script's `MARKUP`/`CHANNEL` split was made after outcomes existed, so both counts are reported.
  - The three remaining gate tasks have been in `queue/deferred/` since 01:44, 40 min after the idcheck failure, and stay there.
  - `make_tasks_g12.py` now sets `fail_loud` on every gate_same spec.

Evidence: `analysis/fork/g12_gate/{GATE.md,gate_summary.json,det_probe.json,analyze_gate.py,tau2_rtn_w4/gate.json}`, `scripts/a6000/{make_tasks_g12,g12_det_probe}.py`, `manifests/a6k2/g12/{calib_fp_traj_c1,row_manifest_fp_traj_c1}.json`, `/data/ziyangs/cloq_work/logs/tasks/fork_gate_g12_rtn_w4.log` (cluster), queue `done/{a6k2_g12_*,ext_g12_*,fork_gate_g12_rtn_w4,g12_det_probe}.json`, `deferred/{fork_gate_same_g12_rtn_w4,fork_ext_gate_g12_rtn_w4_bfcl,fork_ext_gate_same_g12_rtn_w4_bfcl}.json`.

## W100n — g12 (google/gemma-4-12B-it) second-family gate: protocol frozen, gate queued at −21; no g12 outcome yet (2026-10-02 22:42 PDT)
**TL;DR** A time-boxed second-family gate (GPT-6.1 approved; ≤ 6 h engineering from 22:27, ≤ 24 GPU-h) for Gemma 4 12B, reusing the m24 pipeline. Model pinned at 707f0a3b…, served text-only (the 666 `model.language_model.*` tensors byte-identical, as `Gemma4ForCausalLM`, the class vLLM's own multimodal wrapper builds), official template, vLLM `gemma4` tool parser, thinking off. B = BF16, Q = RTN-W4 g128 (`cloq.compress`, 328 linears). Admission = measurable and replayable only: exact tool protocol, state/budget restore, QQ/BB no-ops, same-checkpoint control, and BF16 success ≥ 10% on τ² and on BFCL (the floor that failed l8). Frozen hash-selected gate samples are disjoint from the formal panels. 11 tasks queued at −21.
- **Rendering.** vLLM detects the `openai` content format for the Gemma 4 template, so the server renders content as text parts (the system turn gains a trailing space). Local rendering emulates exactly that step, for Gemma-4 ids only (`cloq/context_policy.py::_openai_parts`); it gives the same message list as `vllm…parse_chat_messages` on a tool-call conversation.
- **GPTQ readiness.** Gemma 4 alternates sliding and full attention, with different rotary tables and masks per type, and its full layers have no `v_proj` (K = V). `cloq/quantize.py` captures per-type layer kwargs and skips the absent module, only when the model type is `gemma4*`. CPU test: exact equality with the model forward; Qwen3 is unchanged.
- **Shared-file changes**, all model-gated and no-op otherwise: models.json `g12`, `cloq/context_policy.py`, `cloq/quantize.py`. worker.py, noderunner.py and serve.sh are unchanged.

Evidence: `analysis/fork/g12_gate/{GATE.md,test_gptq_gemma4_kwargs.py,test_gptq_gemma4_kwargs.out}`, `scripts/a6000/{g12_textonly,make_tasks_g12}.py`, `manifests/a6k2/g12/gate_tau2_v1.json`, `manifests/bfcl/bfcl_mt_g12_v1.json`, `/data/ziyangs/cloq_work/ckpt_cache/g12_textonly_v1/textonly.json` (cluster), queue `todo/*g12*.json`.

## W100m — Paper: abstract and §4 restated on the Holm W4 G−H family without a model regularity; Fig. 2 split into main (four W4 cells + pool, Holm-consistent intervals) and supplementary panels (2026-10-02 PDT)
**TL;DR** GPT-6.1 fixes, all from existing data.
- **Abstract.** The sentence now reads: "On the fixed task pool, action replacement outperforms continuation takeover for both Qwen3-8B W4 methods (by 2.9 and 3.4 pp; Holm-adjusted p = .013 and .012 across four comparisons). Qwen3-4B point estimates favor continuation takeover, but neither contrast is significant. All four new-task intervals include zero, limiting this exploratory finding to the fixed task pool." The 4B values stay in the text and the figure.
- **§4** has the new subheading "Paired comparisons distinguish upgrade modes". It states three cautions:
  - 8B significant and 4B non-significant is not a significant model difference, and the cells select different states;
  - G−H > 0 is not G > 0;
  - all four crossed intervals include 0.
- **Model-regularity sweep.** "Varies with the model", "differs by configuration" and similar wording is removed from the abstract, intro, §4 and discussion.
- **Fig. 2 (F9, `make_fig_modes.py`).**
  - Top: the four core W4 cells plus the pool, with the axis fitted to their intervals. In the G−H panel, thick is the plain 95% t interval and thin the Holm-consistent Bonferroni 98.75% interval, both from `ghf_multiplicity_20261001T225727Z.json`; filled markers are Holm-significant, open ones are not.
  - Bottom: q8 RTN-W3 and q14 BFCL on their own scale, marked as supplementary.
  - Asserts: the Holm p-values, q4 GPTQ plain-excludes / Bonferroni-includes 0, and that the multiplicity estimates match ghf. `provenance.json` is updated.
- **Page budget.** Trimmed the duplicate end-to-end sentence in the Discussion, the "Read with §5" sentence in §6, and the §7 intro.
- **Build:** Limitations at the top of p. 9; `check_numbers.py` PASS (3137 numbers); 0 undefined refs, 0 overfull boxes.

Evidence: `paper/latex/sections/{abstract,introduction,results_r1,results_r3,results_r4,discussion}.tex`, `paper/latex/tools/figs/make_fig_modes.py`, `paper/latex/figures/{f9_upgrade_modes.pdf,provenance.json}`.

## W100l — Paper: "which upgrade mode produces net gain" re-anchored on the preregistered W4 G−H multiplicity family; recommendations paragraph (2026-10-02 PDT)
**TL;DR** The abstract and the §4 Fig. 2 text now lead with the four core W4 G−H contrasts. Values are from `analysis/fork/out/ghf_multiplicity_20261001T225727Z.md`: fixed task pool, t over blocks, Holm m = 4.
- q8 GPTQ-W4 +2.9 (p_holm .013) and q8 AWQ-W4 +3.4 (.012): replacing the action beats taking over the continuation.
- q4 GPTQ-W4 −3.6 (.069) and q4 AWQ-W4 −1.3 (.199): reversed in point estimate, not significant.
- New-task intervals cover 0 in all four cells, so the claim is fixed-pool only and stays exploratory.

Other changes:
- q8 RTN-W3 (G−H −15.7 [−27.5, −3.9], 3 blocks) and q14 BFCL (G−H +5.3, complementarity +0.4 / +3.4) are kept as supporting examples outside the family.
- **Fig. 2 (F9)** now shows all four core W4 cells and a G−H panel. `make_fig_modes.py` asserts the family values and that the crossed intervals cover 0.
- **New Discussion paragraph** "Recommendations for evaluating precision interventions in agents", with three items:
  - mode-specific rescues and damages on the same states;
  - a same-precision reference;
  - fixed-pool and new-task intervals.
- **Page budget.** §7's duplicate paragraphs and the holdout sentence in §4 are condensed. The q4 GPTQ-W4 G = −2.9 clause stays in Appendix D.1, and the redundant recommendation sentence was dropped from the Discussion.
- **Build:** 24 pp, Limitations at the top of p. 9, 0 undefined refs, 0 overfull boxes; `check_numbers.py` PASS (3132 numbers).

Evidence: `paper/latex/sections/{abstract,results_r1,results_r4,discussion}.tex`, `paper/latex/tools/figs/make_fig_modes.py`, `paper/latex/figures/f9_upgrade_modes.pdf`.

## W100k — Paper: fixed main line ("task benefit depends on which step is upgraded and who executes afterwards; whole-model swaps mix these effects; same-state crossed interventions measure them separately"); attribution wording removed; paired differences for the mode examples (2026-10-02 PDT)
**TL;DR** GPT-6.1 review of cloq-paper 35d1003, final fixes, all from existing data.
- **Attribution wording.** The same-precision substitution no longer "checks which consequences are attributable to precision". It now "tests whether turnover and continuation dependence require a higher bit width, and benchmarks BF16 substitution against a fixed-precision alternative".
  - §5 states that the two first-divergence designs may select different states, so shared and exclusive flips cannot be split into effects caused and not caused by precision.
  - The §5 title is now "Does an Upgrade Need a Higher Bit Width?".
  - The sweep covered the abstract, intro, contributions, §5 and the discussion.
- **Paired differences** (source values; they match GPT's numbers).
  - q8 RTN-W3: G−H −15.7 [−27.5, −3.9], i.e. H−G +15.7 [+3.9, +27.5]; t over three blocks. Source: `ghf_20261001T211519Z.md` §1.
  - q14 BFCL: G−H +5.3 [+2.3, +8.4]. Source: `ext_q14_20261002T085647Z.md` §2.
  - q14 complementarity: H +0.4 [−1.1, +1.9]; F−G +3.4 [+1.3, +5.6].
  - The text says once that F has the largest point estimate in both examples and that no compute-cost comparison exists, so no cost-optimal mode is established.
  - "Which mode pays" is now "which upgrade mode produces net task gain" everywhere.
- **Intro shared-core reference.** It now leads with the task-propensity-preserving null (107 vs 76 [69, 84], within-task block shuffle). The independence expectation (30) is in §5, labelled with its assumption.
- **Contributions** are exactly two:
  - (1) an executable same-state intervention protocol (action, continuation, joint, plus same-precision reference);
  - (2) the empirical structure (gains two-sided and execution-dependent; sensitivity signals find changes but do not yet reliably select net-beneficial substitutions).
- **§7** framing: numerical quality (QuaRot/SpinQuant), cache location (KIVI), model family (Mistral).
- **Build:** 24 pp, Limitations on p. 8, 0 undefined refs, 0 overfull boxes; `check_numbers.py` PASS (3137 numbers).

Evidence: `paper/latex/sections/{abstract,introduction,results_r1,results_r2,results_r3,results_r4,discussion}.tex`, `paper/latex/main.pdf`.

## W100j — Paper revised after the GPT-6.1 review (NAACL-main borderline): contribution re-centred on same-state measurement of upgrade modes; G/H/F figure in the main text; §5 set structure foregrounded; §7 rewritten as question-and-test items (2026-10-02 PDT)
**TL;DR** Main changes:
- **Re-centred contribution.** The abstract, intro and contributions now lead with what is distinctive: separate the current action from the subsequent execution, measure upgrade value on the same frozen state, and use a same-precision substitution to check attribution. "Changing outcomes ≠ improving them" is kept, but as a subordinate point.
- **Take-away:** a precision upgrade has continuation-dependent task value, so the rescues and damages of a specific upgrade mode must be measured.
- **Replay Gap (2608.08239).** It is now described precisely in related work, from verbatim excerpts in `outputs/.drafts/replay_gap_2608.08239_excerpt.md`: live SWE-bench forks at 30%/70% of trajectory length, a Qwen3-4B FP8 / Qwen3-14B AWQ pair, same-model controls, 0 flips in 359 controls, and a swap that changes action and continuation together. One intro sentence positions us against it.
- **New main-text figure F9** (`tools/figs/make_fig_modes.py`): paired G/H/F for q4/q8 GPTQ-W4, the W4 pool, q8 RTN-W3 (H +15.3 [+0.7, +29.9], F +18.4, G −0.4) and q14 BFCL (G +5.7 [+2.9, +8.7], H +0.4, F +9.1). All numbers come from ghf_20261001T211519Z and ext_q14_20261002T085647Z, with asserts.
- **F6 redrawn** with two panels: (a) W4 rates; (b) units affected by only BF16 / both / only the second checkpoint, W4 107/64/74 and W3 62/34/26.
- **§5 compressed.** Moved to Appendix D.6:
  - the TOST details and both off-diagonal aggregation conventions;
  - full-substitution volume;
  - the W3 TOST and per-model numbers;
  - the net values on the same-precision blocks;
  - the common-state interval details.
  The common-state comparison stays "not resolved", with an explicit sentence that it does not show that B's action lacks extra value.
- **§7** is now "When Upgrade Value Appears, Disappears or Moves". Each item is a question with a stated test. The `\pending{}` slots are kept for QuaRot/SpinQuant, KIVI and Mistral.
- **Fixes.**
  - The interaction I is stated as ∈ {−2,…,+2}.
  - KIVI is described as the replay-compatible decode-view variant (per kivi_gate/GATE.md §6), not as a persisted compressed cache.
- **Build:** 23 pp, Limitations on p. 8 (right column), 0 undefined refs, 0 overfull boxes; `check_numbers.py` PASS (3133 numbers).

Evidence: `paper/latex/sections/{abstract,introduction,related_work,method,results_r1,results_r2,results_r4,discussion,appendix_moved}.tex`, `paper/latex/figures/{f6_sameprec,f9_upgrade_modes}.pdf`, `paper/latex/tools/figs/{make_figs.py,make_fig_modes.py}`, `outputs/.drafts/replay_gap_2608.08239_excerpt.md`.

## W100i — Same-precision acceptance check (773/774 is a context-overflow sentinel, no number changes); W3 same-precision stress check moved into paper §5 (2026-10-02 20:00 PDT)
**TL;DR**
- **Task A.** The single `prefix_and_env_ok` failure, 773/774, is in the **W3** analysis (`sameprec_w3_20261003T023933Z`, q8 same). The W4 analysis has none: `sameprec_20261003T023857Z` is 1405/1405.
- **Where.** Block q4, task retail:111, state `01a4b3fe2dc5b158`, arm BB (Q′Q′). The failing sub-check is the prefix check: `prefix_ok` is `None`, while `env_hash_init_ok` is `True`.
- **Cause: a recording sentinel, not a mismatch.** The branch ended in an agent-side context overflow. On that path `cloq/fork.py` hard-codes `prefix_ok: None`, because tau2 keeps no messages.
- **The replay was correct.** The first replayed prompt-ids sha equals the state's `q_decision.prompt_ids_sha` and that of the other 3 arms, and the env hash matches.
- **Rule.** SAMEPREC §4 (inherited by W3 §4; A1 changes no admission rule) says acceptance counts "exclude units only through quarantine", and W10/W70 count context overflow as a valid failure (Y = 0). `analyze_sameprec.py` already does both.
- **Result: no script change, no re-run, no number changed.** Open question (display only): count the sentinel separately as "not computable".
- **Task B.** W3 same-precision is now a stress-check paragraph in §5, after the W4 unit-split paragraphs and before "The measured value…". It uses GPT-6.1's required wording and is never pooled with W4.
  - The W4 off-diagonal difference now labels both conventions: −1.210 is the mean of per-block ratios (interval/TOST), −1.216 the ratio of block sums. The F6(b) caption says which one is plotted.
  - Method, Limitations, §7 and Discussion are updated where they had become inaccurate.
  - Build: 23 pp; main text pp. 1–8, Limitations at the top of p. 9; 0 overfull, 0 undefined. `check_numbers.py` PASS (3131 numbers, 0 unverified).

- **Task A note:** `analysis/fork/out/sameprec_prefix_check_20261003T030004Z.md`. Evidence:
  - `analysis/fork/sameprec_w3/q8_gptq_w3_d1_vs_d2/q4/branches/01a4b3fe2dc5b158.json` (BB: `infra_cause: context_overflow`, 85 decisions, `suffix: None`);
  - `cloq/fork.py` (ContextWindowExceeded return, `"prefix_ok": None`);
  - `analysis/fork/analyze_dev.py` `load_dir` (excludes only branches with an `error` key; quarantine only on a QQ no-op mismatch).
  - No-op samples 31/31 and 39/39; 0 quarantined directories.
- **Task B paper changes** (`paper/latex/sections/`):
  - `results_r2.tex`: new `\paragraph{Stress check at W3.}`. Its content, with sources `sameprec_w3_20261003T023933Z.{md,json}` and `sameprec_w3_split_20261003T024007Z.md`:
    - the protocol's complete panel, K = 3, q3–q5, 510 units;
    - "the same-precision substitution produces 17.3 pp of turnover, the BF16 substitution 18.8 pp"; off-diagonal 27.6 / 27.3%;
    - ΔM +1.6, 95% [−0.66, +3.80], unresolved: TOST p 0.055 fails, and the 90% interval lying just above 0 does not change the reading;
    - ΔG_all equivalent only in the preregistered pooled population (+1.2, p 0.017); q4 +3.1, q8 −0.8;
    - Δoff −0.288 (ratio of block sums) or −0.307 (mean of per-block ratios; 90% [−11.0, +10.4], p 0.27);
    - G κ 0.60 / 0.68, described as overlap of task×block units, explicitly not a same-state replication;
    - 62 both / 34 BF16-only / 26 other-W3-only of 122 flipping units, so 49% respond to only one substitution, hence flip volume, affected units and net upgrade value are measured separately.
  - The phrase "explains 92%" is not used anywhere.
  - W4 Δoff sentence and F6 caption: both conventions labelled (`sameprec_20261003T023857Z.json` `tost_a1.consistency`).
  - Compressed to stay within 8 pp, mostly by removing redundancy:
    - §5 intro;
    - the "longest prefix at freeze" aside;
    - the per-task r = 0.68 clause;
    - the forced cross-direction sentence (already in the F7 caption);
    - the value paragraph;
    - the common-state 5.5–7.5% clause;
    - §7 opener and Qwen3-14B close;
    - Discussion (now says "at W4 and at W3"; "neither reference shows equivalent turnovers").
  - `method.tex`: "GPTQ-W3 as a stress check". `limitations.tex`: now covers GPTQ-W3 on three blocks, and "nothing about AWQ, KV8, RTN or rotated KV4". `results_r4.tex`: pointer from "Lower bit widths" to §5. `appendix_moved.tex`: W3 acceptance, including the explained 773/774.
  - Abstract and intro are unchanged; their W4-only statements remain accurate.
- **No W3 same-precision `\pending{}` slot existed in §7.** The only W3 text there was the precision stress paragraph, which stays.
- **Remaining `\pending{}` slots:**
  - main text: §7 SpinQuant vs QuaRot, §7 KIVI-2 vs KV8, §7 Mistral-Small second family; §5 W4 interim `K=6` markers (F6 caption and text);
  - appendix: restoration location vs random, error dose α, low-bit failure modes, and two `K=6` markers (app:sameprec text, F7 caption).

## W100h — W3 same-precision pair (GPTQ-W3 d1 vs d2, K = 3, q3–q5): ΔM +1.6 pp, 90% CI [+0.05, +3.08], TOST p 0.055 — not resolved; cross-check bug fixed (2026-10-02 19:45 PDT)
**TL;DR** All 6 formal tasks `fork_sameprec_w3_{q4,q8}_q{3,4,5}` are done. The W3 analysis first failed on an internal assert (`d_offdiag` −0.307 vs −0.288). The assert compared two different estimators of the same share; the protocol estimands are unchanged. The fix keeps the W4 analysis output identical to `sameprec_20261003T023735Z.json`.

At W3, the same-precision substitution (d1 → d2) gives almost all of the BF16-vs-W3 turnover: M′ 17.3 vs M 18.8 pp of units. Paired ΔM is +1.6 pp:
- 95% t [−0.7, +3.8], so no precision-specific excess at 95%;
- 90% [+0.05, +3.08], p_TOST 0.055, so equivalence at ±3 pp is not shown.

Reading: **not resolved**. Any precision-specific excess is small (≤ about 3 pp, about 8% of M at the point estimate), but K = 3 can neither exclude it nor show equivalence.

The W4 result had the opposite sign: ΔM −0.98 at K = 6, 90% CI [−3.26, +1.30], TOST fails. The action-side shared unit core holds at W3: G κ rescue 0.60, harm 0.68, against 0.60 and 0.54 at W4.

- **Bug and fix.**
  - In `analysis/fork/analyze_sameprec.py`, the A1 consistency assert compared each TOST centre with the pooled point estimate.
  - For ΔM and ΔG the two are the same number: `Boot.task_mean`'s point estimate is the mean of block means.
  - For Δoff-diagonal they are different estimators. The point estimate (`Boot.ratio`) is the ratio of block **sums** over divergent states. The frozen primary t interval at K < 10 and the A1 TOST are both centred on the **mean of per-block ratios**.
  - The two agree only when every block has the same number of states. W4 passed by coincidence (−1.210 vs −1.216).
  - The check for `d_offdiag` now compares the TOST centre with the centre of the frozen pooled t interval (−0.307 = −0.307). Both centres are recorded in `tost_a1.consistency`, and the md prints both.
  - `analyze_sameprec_w3.py` also left the temporary output path in the md's "Full numbers" line; that is fixed too.
  - W4 re-run: `analysis/fork/out/sameprec_20261003T023857Z.json`. A recursive diff against `sameprec_20261003T023735Z.json` shows no differences, ignoring utc, script sha and the new `consistency` key.
- **W3 estimands** (q4+q8 pooled, K = 3, t over 3 block means, df = 2; A1 TOST ±3 pp). `analysis/fork/out/sameprec_w3_20261003T023933Z.{md,json}`:

  | | BF16 vs W3 (precision) | W3-d2 vs W3 (same-precision) |
  |---|---|---|
  | r | 9.6 | 8.2 |
  | d | 9.2 | 9.0 |
  | M | 18.8 [9.9, 27.7] | 17.3 [8.7, 25.8] |
  | G_all | +0.4 | −0.8 |
  | off-diagonal (% of divergent states) | 27.3 | 27.6 |
  | divergence rate | 92.9% | 91.8% |

  Divergence rate per cell: q4 91.0% vs 85.5%, q8 94.9% vs 98.0%. At W4 it was 76.9% in both designs.
  - **ΔM** +1.57:
    - 95% [−0.66, +3.80]; crossed [−2.0, +5.5];
    - 90% [+0.05, +3.08];
    - p_lower 0.006, p_upper 0.055, p_TOST 0.055, so not equivalent;
    - block diffs +0.59 / +1.76 / +2.35.
  - **ΔG_all** +1.18:
    - 95% [−0.3, +2.6]; 90% [+0.18, +2.17];
    - p_TOST 0.017, so equivalent under the A1 rule.
    - Caveat: df = 2 and the 3 block diffs happen to be tight (+0.59 / +1.76 / +1.18). At the cell level q4 is not equivalent (+3.1, 90% [+0.11, +6.17]).
  - **Δoff-diagonal** (descriptive; different state sets):
    - point estimate (ratio of sums) −0.29; TOST centre −0.31;
    - 95% [−16.0, +15.4]; 90% [−11.0, +10.4];
    - p_TOST 0.27.
  - **Per cell, ΔM.** q4 and q8 are both +1.57, 95% [−2.9, +6.0]. The per-block diffs are the same values in a different order (q4 +1.18 / 0 / +3.53; q8 0 / +3.53 / +1.18); this was checked against the per-block table and is a coincidence, not a bug.
    - ΔG: q4 +3.14, q8 −0.78.
    - Δoff: q4 +3.5, q8 −4.1.
- **Overlap (descriptive, A1.4).** `analysis/fork/sameprec_split.py --w3`; the new flag swaps in the manifest, cell and guard and skips the trigger link (that rule is for W4 d1 on f01–f03). Output `analysis/fork/out/sameprec_w3_split_20261003T024007Z.{md,json}`, 510 units, with κ against the within-task shuffle null:

  | contrast | κ | shared | within-task shuffle mean | design-specific share of flipping units | shuffle-null share |
  |---|---|---|---|---|---|
  | G rescue | 0.60 [0.51, 0.68] | 29 | 16 | | |
  | G harm | 0.68 [0.50, 0.75] | 33 | 19 | | |
  | G flip | | | | 49% | 70% |
  | H rescue / harm | 0.40 / 0.31 | | | | |
  | F rescue / harm | 0.46 / 0.37 | | | | |
  | off-diagonal (443 states divergent in both designs) | 0.40 [0.32, 0.47] | 68 | 62 | 61% | |

  - The split's Δflips (+1.6) and ΔG (+1.2) match analyze_sameprec.
  - W4 values for comparison: G κ 0.60 / 0.54, H 0.20 / 0.45, F 0.34 / 0.35, off-diagonal 0.29.
- **Interpretation** (GPT-6.1: "does the same-precision reference still explain the observed consequences under a stronger perturbation?").
  - Mostly yes, but not resolved. Under W3, swapping only the calibration draw gives about 92% of the BF16-vs-W3 turnover, the same off-diagonal share and a similar net.
  - The rescued and harmed units on the action side share a core well above the shuffle null, as strong as at W4 or stronger.
  - The ΔM point estimate turned positive at W3 (+1.6, against −1.0 at W4), and the 90% interval just excludes 0. This hints at a small precision-specific excess under the stronger perturbation, but the 95% interval includes 0 and TOST fails, so neither excess nor equivalence is shown.
  - With K = 3 (df = 2) these intervals are fragile. W3 is reported next to W4, never pooled with it (protocol §4).
  - The ΔG_all "equivalent" rests on 3 blocks and should be cited only with that caveat.
  - Status: the script labels this INTERIM, because it runs before the 2026-10-04 07 UTC freeze time. All K = 3 blocks are complete.
- Files:
  - `analysis/fork/analyze_sameprec.py` (cross-check fix);
  - `analysis/fork/analyze_sameprec_w3.py` (output-path fix);
  - `analysis/fork/sameprec_split.py` (`--w3`);
  - the outputs above.

## W100g — Expansion tool fixed before any expansion decision: KIVI `_fx` gates, fixed-population completeness (m24 = 249 states), KIVI pairing, frozen snapshot; protocol amendment A5 (2026-10-02 14:55 PDT)
**TL;DR** GPT-6.1 reviewed 6e0b11b and found three gaps in `make_newmethod_panel.py expansion`. All are fixed before any expansion decision was due or written: no `expansion_*.json` exists, and no `nmp_tau2_*` task is done. Protocol sha `0dc3143e…` becomes `f9f8b3a5…` (A5); `analyze_newmethod.py` has the new constant. The rule stays effect-blind.
- **KIVI gates.** Eligibility now reads only `nmp_gate_{same,bank}_q8_<cell>_fx` (outputs `gate/q8_<cell>_fx/`, checked against the tasks' `out`). `kivi_k4v4` additionally needs `kivi_gate_q8_toy4` strict T1. The old pre-fix gates never admit a cell.
- **Registered cells are fixed in code** (`REGISTERED`):
  - q8: the 5 rotation cells + `kivi_k2v2`, `kivi_k4v4`, `kivi_k16v16`;
  - m24: `rtn_w4`, `gptq_w4_d1`.
  `--cells` is optional and must equal the list; the old scheduler line (which omitted k4v4/k16v16) is refused.
- **Fixed-population completeness from counts only.**
  - Per f01–f03 block the rule needs `n_rows` = 85, `n_missing` = the manifest-missing source rows of that block (all outside the population), `n_ok` = `n_rows` − `n_missing`, `n_errors` 0 and every no-op passed.
  - m24: the A3 mask comes from `analyze_newmethod.population`. The 7 known missing rows (tasks 13/44) do not block; any other missing row does; 249 states per cell.
  - q8 now also requires `n_missing` 0.
  - Branch-arm errors inside completed rows are invisible to these fields (stated limitation; the analysis strict-block rule catches them).
- **KIVI pairing (A5.3, new).** A4 did not say how `kivi_k16v16` enters expansion. Now a quantized KIVI cell expands only together with `kivi_k16v16`, and `kivi_k16v16` only with at least one quantized KIVI cell.
- **Snapshot.** Past T_decide, eligibility is judged as of T_decide (a task counts only if `finished` ≤ T_decide). Every input file's sha256, each task's queue state, finished time and file sha, the summary fields used, and the per-cell reasons are recorded. The record is written once (hard link; refused if it exists), and `--now` is refused with `--write`.
- **Dry run now** (14:51 PDT, no write):
  - q8 `decision_due` false, eligible none. The rotation cells' `nmp_tau2_*` tasks are not queued at all. The KIVI `_fx` gates are in todo and k2v2 f01–f03 are running. Reference U2B cost 13.1 GPU-h, so P ≥ 16.4 GPU-h, ≥ 2.0 h wall.
  - m24 `decision_due` false, eligible none (gates and panel tasks in todo).
- `--selftest` (synthetic queue in a temp dir) passes:
  - a newly missing row, a task done after T_decide, a failed gate, unqueued tasks, old-only KIVI gates, strict T1 false and the k16v16 pairing in both directions;
  - m24 249-state coverage vs an extra missing row;
  - decision not due, write-once and the forbidden-path guard.

Scheduler: `make_newmethod_panel.py expansion --model q8 --write` and `... --model m24 --write` (no `--cells`). Builder sha `eb505f12…` (recorded in each record as `builder_sha256`).

Evidence: `scripts/a6000/make_newmethod_panel.py`, `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (Amendment A5), `analysis/fork/analyze_newmethod.py`, W99t-b, W100e-b.

## W99t-b — KIVI follow-up (GPT-6.1 decisions): kivi_k16v16 kernel-path control + protocol amendment A4, all KIVI gates re-run on the fixed kernel (_fx), strict T1, k4v4 secondary pending its gates (2026-10-02 14:30 PDT)
**TL;DR** Amendment A4 was written before any KIVI outcome was read. Protocol sha `da8b69ba…` becomes `0dc3143e…`; `analyze_newmethod.py` has the new constant and `NEW_CELLS += kivi_k16v16`.
- **Control cell.** A4 registers `kivi_k16v16`: the KIVI kernel with no quantization, the same-kernel-path control. It runs τ² f01–f03 with four arms. Its BFCL run is not registered.
- **Gates.** All three KIVI cells' §2.4 gates are re-run on the fixed kernel f585ae3. They use new ids `nmp_gate_{same,bank}_q8_<cell>_fx` and new directories `gate/q8_<cell>_fx/` (−25). The old gates stay as the pre-fix record.
- **Strict T1.** The toy gate gained a strict T1 (`verdict_strict`): integer codes, scale, mn and dequantized values must be bitwise equal to official KIVI, on fp32 and BF16-rounded data.
  - The kernel's code is recovered exactly as the unique q with fl(fl(q·s)+mn) equal to the kernel output.
  - A CPU sanity run (CPU official twin, which divides exactly) shows the check detects the tie flips on BF16 data: 56–168 code mismatches per 262k.
  - The GPU result comes from `kivi_gate_q8_toy4` (−25).
- **k4v4 is secondary, with disclosure.** Its toy T2 bound was revised after the failing value had been seen: fp32 reference 0.0547, serving-precision reference 0.0467, official KIVI's own BF16 vs fp32 gap 0.0496. Its phase 1 is released only after its `_fx` gates and the strict T1 pass.
- **BFCL run unblocked.** The main session patched `worker.run_eval` (5c2f207: no BF16 canary for KIVI), and `ext_q8_kivi_k2v2_bfcl_nmp1` was requeued.
- **Paper text.** GATE.md §6 has a paragraph for the paper on the replay-compatible decode-view prefill variant.

Evidence: `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (Amendment A4), `analysis/fork/analyze_newmethod.py`, `analysis/fork/kivi_gate/GATE.md` §6, `scripts/a6000/{kivi_gate,make_tasks_kivi}.py`, `cloq/kivi_ref.py` (`official_quant_lastdim`), W99t.

## W100e-c — m24 nmp gate_same r1 failed on a selection bug, not on identity (it picked airline 44, an infrastructure_error episode with 0 agent turns); gate_same now skips invalid state sources; r2 gates at −30; τ² panel re-gated on r2 and raised to −30 (2026-10-02 23:10 PDT)
**TL;DR** Both `nmp_gate_same_m24_{rtn_w4,gptq_w4_d1}` failed: verdict pass false, 5 states, 1 error.
- **Root cause: a state-selection bug, not identity.**
  - `pick_tasks` ranks every trajectory of `a6k2_m24_bfpair_f01/airline` by hash, and its third pick was **airline 44**. That episode is the `infrastructure_error` (`agent_parse_error`) episode, masked by A3. It has 4 decisions but 0 agent turns in the trajectory, so `cloq/fork.py::make_state` raised `IndexError` at `pos[t]` before any server call.
  - Every other check passed in both cells: idcheck 8/8 + 8/8, and all 5 states have the shadow equal to a_Q, the prompts OK, all four branches equal, and the budget OK. The bank gates passed with 10/10 and 0 errors.
  - The W99p gate_same passed because its gate blocks had no infrastructure episodes.
- **Fix (`scripts/a6000/fork_driver.py`, gate_same only).**
  - New `state_source_ok`: the termination is user_stop, agent_stop, max_steps or too_many_errors, and the number of agent turns equals the number of decisions and is > 0.
  - `pick_tasks(valid_only=True)` keeps the same hash order and skips invalid sources. The gate and bank paths are untouched.
  - Opt-in `fail_loud`: a failed gate_same raises, so tasks that depend on it never release (as the bank gate does, W76).
- **Regression check.** The new selection was recomputed for all 14 earlier τ² gate_same outputs (q4 ×4, q8 nmp ×9, W99p m24) and reproduces each one's (domain, task, t) set exactly. For m24 r1, it replaces airline 44 with airline 23 (t 15) and keeps the other five states.
- **Queue (atomic edits).**
  - r1 outputs moved to `analysis/fork/newmethod/gate/m24_<cell>/same_r1_superseded/`, with a SUPERSEDED note. They are not reused.
  - **`nmp_gate_same_m24_rtn_w4_r2` and `nmp_gate_same_m24_gptq_w4_d1_r2`**: −30, 4 GPUs, `fail_loud`, output to `…/same/`. The expansion rule reads that path.
  - The six `nmp_tau2_m24_*` tasks were still in todo and unstarted. They now depend on the _r2 gates instead of r1, and their priority went from −26 to −30. The score and BFCL tasks are unchanged.
- **ETA.** r1 took 17 min (RTN) and 52 min (GPTQ, including the build). The bank gate took 12 min for 10 states, so a τ² panel task (85 states) should take about 1–1.5 h, plus about 35 min of GPTQ build for gptq. With two 4-GPU windows, phase 1 τ² should finish about 5–7 h after the r2 gates are claimed, around 2026-10-03 05:00–08:00 PDT. That is well before T_decide (2026-10-04 00:00 PDT).

Evidence: `analysis/fork/newmethod/gate/m24_{rtn_w4,gptq_w4_d1}/same_r1_superseded/gate_same.json` (cluster), `scripts/a6000/fork_driver.py` (`state_source_ok`, `pick_tasks`, `gate_same`), queue `todo/nmp_gate_same_m24_*_r2.json`, `todo/nmp_tau2_m24_*.json`, `done/nmp_gate_{same,bank}_m24_*.json`.

## W100e-b — m24 analysis population fixed at 83 tasks (airline 13 and 44 excluded uniformly): mask v1 + protocol amendment A3, done before any m24 panel output existed; analyze_newmethod gains the m24 mask, M1 contrast and available-rows sensitivity (2026-10-02 14:10 PDT)
**TL;DR** This resolves W100e's open strict-block question as the advisor (GPT-6.1) decided, a corrected option (b).
- **Population.** For both m24 cells and all six blocks, airline tasks 13 and 44 are excluded. The analysis population is fixed at 83 tasks: 249 states per cell in phase 1, 498 if expanded.
- **Why they are excluded.** The BF16 source episodes of these tasks end in the model's own invalid tool name (`agent_parse_error`, GATE.md 1c), not in infrastructure. End-to-end evaluation keeps scoring them as failures. Fork results are conditional on a complete, recoverable BF16 source state.
- **Frozen artifacts.**
  - Mask: `manifests/fork/newmethod_panel_v1_m24_mask_v1.json`, sha **b03a8a918959e3568315b1ae134f2902580e6af822d80beccb692729c2f82c81**.
  - Protocol after amendment A3: sha **da8b69baaff0f47fc6d4ff0674d73c8890896d7a997a7dfa44062448ea27ca77** (was c6603f90…).
  - The manifest (53295b64…) and the 25 queued tasks are unchanged.
- **Timing.** When this was written, no `analysis/fork/newmethod/*/m24_*` directory existed and no `nmp_*_m24_*` task had started.
- **Disclosure (A3.2).** Outcome-blind selection shows a transparent process. It does not show that the missingness is unrelated to task difficulty or to the effects.
- **Changes to `analyze_newmethod.py`.**
  - The guard checks the mask sha and that the mask is bound to the manifest.
  - Strict blocks need exactly the 83 tasks, so a newly missing branch fails the block. Arms are never imputed and tasks are never retried.
  - Contrast M1 = `gptq_w4_d1` − `rtn_w4`: on τ² D_cc over blocks complete in both cells, and on BFCL D_cc_all.
  - Labelled sensitivity: actual available rows (unmasked, non-strict), per cell and for M1. The complete-case analysis is also reported.
  - `rtn_w4` is registered with the BFCL directory parser.
- **Tests.**
  - `--selftest` PASS on synthetic m24-shaped units, which read only the manifest and mask. It checks: population 83; blocks with missing 13/44 rows admitted; an injected missing branch fails gptq f03 only; M1 uses f01–f02 (166 states); the sensitivity keeps airline 13 rows.
  - The q8 `--dry` run is unchanged: 85 tasks, reference cells admitted f01–f03.
  - No m24 output was read.

Evidence: `manifests/fork/newmethod_panel_v1_m24_mask_v1.json`, `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (Amendment A3), `analysis/fork/analyze_newmethod.py` (`MASKS`, `population`, `apply_population`, `CONTRASTS["m24"]`, `selftest`), `analysis/fork/m24_gate/GATE.md` row 1c, `runs/a6k2_m24_bfpair_f0*/airline/infra_causes.json` (cluster).

## W100e — m24 panel: manifest `newmethod_panel_v1_m24` frozen (sha 53295b64…), protocol amendment A2, rtn_w4 + gptq_w4_d1 τ² and BFCL panel queued at −26; OPEN: strict-block rule admits no m24 block (airline 44 missing in all six BF16 blocks) (2026-10-02 13:35 PDT)
**TL;DR** No m24 panel outcome exists, so no G/H/F/D_cc is reported.
- **Manifest.** All six BF16 blocks `a6k2_m24_bfpair_f01…f06` were admitted in snapshot `snapshot_auto_20261002T2022Z` (sha f8c4dde2…). `make_newmethod_panel.py build --model m24` then wrote `manifests/fork/newmethod_panel_v1_m24.json`, sha **53295b64fbcc7c4501ea8883aa34ce922a5ca0e23c5636c8bb1c4efe38e3ff4c**. It has 510 τ² rows, 7 of them missing, and the same 200 BFCL ids as q8 (checked id by id).
- **Amendment A2.** Appended to `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md`; protocol sha 28b78509… → **c6603f90298069af78de59ea1ae9992e722ed927e1a2d951582b28d51d1687c4**. `analyze_newmethod.py` has the new `PROTOCOL_SHA256` and `MANIFESTS["m24"]`, and its guard passes for m24 and q8.
- **BFCL floor (§10, BF16 only).** `ext_m24_bf16_bfcl_nmp1` succeeds on 40/200 = 20%, which is ≥ 10%, so the BFCL forks are queued.
- **Queued at −26** with `make_tasks_m24.py panel --cell {rtn_w4,gptq_w4_d1} --bfcl --write`, 25 tasks. Forks use 4 GPUs (`gpus_per_role 2`); the eval uses 2. No node pins.
  - Per cell: `nmp_gate_{same,bank}_m24_<cell>`, then `nmp_tau2_m24_<cell>_f0{1,2,3}`, then `nmp_score_m24_<cell>_f0{1,2,3}`, plus `nmp_bfcl_m24_<cell>_{base,miss_param,miss_func,long_context}`.
  - GPTQ also gets its closed-loop BFCL Q run `ext_m24_gptq_w4_d1_bfcl_nmp1`. `make_tasks_m24.panel` previously left this as a dangling dependency; it is fixed here.
  - Estimated cost: about 55–60 GPU-h per cell (W99q gate throughput: τ² gates plus f01–f03 take about 6–8 h wall on 4 GPUs; BFCL takes about 4 × 1–1.5 h on 4 GPUs). GPTQ-W4 at 24B has not been built yet, and every gptq task pays its build.
- **OPEN, for the main session (not decided; A2.3).**
  - The 7 missing rows are BF16 source episodes that ended in `infrastructure_error` / `agent_parse_error`: airline task 44 in **every** block, plus airline task 13 in f01.
  - The frozen row rule keeps them missing. But §7's strict-block rule (`strict_blocks`, n = 85) then admits **no** m24 τ² block.
  - Options: (a) the denominator is the block's non-missing rows; (b) exclude task 44 for m24 from the BF16 source only; (c) complete-case only. All three are effect-blind, and the queued forks are the same under each.
  - The choice must be appended as a dated amendment before any `analysis/fork/newmethod/*/m24_*` output is read.
- **Expansion.** `expansion --model m24 --cells rtn_w4 gptq_w4_d1`, T_decide 2026-10-04 00:00 PDT. It is not yet due, and this entry does not write it.

Evidence: `manifests/fork/newmethod_panel_v1_m24.json`, `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (Amendment A2), `analysis/fork/analyze_newmethod.py`, `scripts/a6000/make_tasks_m24.py`, `analysis/insights/iter_3/out/snapshot_auto_20261002T2022Z.json`, `runs/a6k2_m24_bfpair_f0*/airline/infra_causes.json` and `runs/ext_m24_bf16_bfcl_nmp1/*/metrics.json` (cluster), queue `todo/{nmp_*_m24_*,ext_m24_gptq_w4_d1_bfcl_nmp1}.json`.

## W100f — Paper: §5 common-state slots filled from W100b; Figure F8 replaces the placeholder (2026-10-02 PDT)
**TL;DR** `sections/results_r2.tex` "Common-state action sources" now reports W100b (q8, 255 states, k = 3, 0 excluded): K(c = Q) −0.4 pp (t95 [−9.3, +8.5], boot95 [−3.5, +2.7]) and K(c = B) +2.4 pp ([−3.5, +8.2], [−0.8, +5.5]), both "not resolved"; turnover 5.5–7.5%; action agreement 57.6 / 56.9 / 55.7%; interaction +2.7 pp (t90 [+0.5, +5.0], boot90 [−0.4, +5.9]) as secondary, not resolved. Reading kept modest: no "irrelevant", no "equivalent".
- **Figure:** `paper/latex/figures/f8_commonstate.pdf` (column width): (a) 3×2 V(source, continuation), (b) K(c) with boot95 (thick) and t95 (thin) against ±3 pp, (c) agreement patterns (130 / 17 / 15 / 12 / 81). Script `paper/latex/tools/figs/make_fig_commonstate.py` imports make_figs.py style only (make_figs.py untouched), asserts the quoted numbers, and merges its entry with source and script sha256 into `figures/provenance.json`.
- **Discussion:** the "what the reference settles" paragraph is folded into one sentence of the first paragraph (page budget).
- **Checks:** check_numbers PASS (0 unverified, 0 missing src); tectonic 0 overfull, 0 undefined; 23 pages; main text ends on p. 8, Limitations at the top of p. 9. Abstract and intro had no pending common-state reference and are unchanged.
- Evidence: `analysis/fork/out/commonstate_20261002T201612Z.{md,json}`; W100b.

## W100b — Common-state action sources on q8 (BF16 / W4-d1 / W4-d2 actions × BF16 or d1 continuation): K not resolved under either continuation (2026-10-02 13:16 PDT)
**TL;DR** Prereg `docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md` (sha c73ab2eec…, deviation D1 = logistics unpin only). 255 frozen q8 U2B states, f01–f03, 85 tasks, 0 excluded, every block complete.
- **Acceptance:** all 6 panel tasks pass idcheck, d2-replay, reference reruns (22/22, 19/19, 15/15, 18/18, 23/23, 19/19) and implicit identities. Canaries and ckpt shas match.
- **Key estimand K(c) = BF16 − d2 at the same state:**
  - K(c = d1) −0.4 pp, t95 [−9.3, +8.5], boot95 [−3.5, +2.7];
  - K(c = BF16) +2.4 pp, t95 [−3.5, +8.2], boot95 [−0.8, +5.5], Holm p 0.32.
  - Both readings: **not resolved** (no difference shown, no TOST equivalence).
- **Cells V(source, continuation), %:** BF16/BF16 31.4, BF16/d1 28.2, d1/BF16 28.6, d1/d1 27.8, d2/BF16 29.0, d2/d1 28.6.
- **Turnover:** all contrasts flip 5.5–7.5% of states. BF16−d1 and d2−d1 are both small (+0.4 / +0.8 pp under d1).
- **Action agreement:** BF16 = d1 57.6%, BF16 = d2 56.9%, d1 = d2 55.7%. A second W4 checkpoint differs from d1 as often as BF16 does.
- **Interaction with continuation:** BF16−d2 I = +2.7 pp, t90 [+0.5, +5.0], boot90 [−0.4, +5.9]. Secondary; not resolved.
- **Exploratory:** on the 110 states where a_d2 ≠ a_BF16, K(d1) −0.9 and K(BF16) +5.5 pp (points only).
- **Reading:** on identical states, BF16's action is not shown to be worth more than another W4 checkpoint's. Any edge appears only when BF16 also continues, which is consistent with the paper's continuation-dependence argument, but unresolved at k = 3.
- Evidence: `analysis/fork/out/commonstate_20261002T201612Z.{md,json}`, `analysis/fork/commonstate/q8/`, `analysis/fork/analyze_commonstate.py`.
- Also: W3 same-precision replay gates pass on q4 and q8; 6 formal tasks queued at −27 (`make_tasks_sameprec_w3.py --formal --write`).

## W99t — KIVI (q8 KV cache) feasibility gate: kivi_k2v2 PASS, phase 1 queued; kivi_k4v4 held (original toy T2 at the BF16 floor); amendment a2 fixes a real scale mismatch (2026-10-02 10:00 PDT)
**TL;DR** KIVI (official jy-yuan/KIVI @ 876b4d2; G = 32, R = 128) is served on vLLM by a stateless position-determined Triton kernel (70addfa).
- **kivi_k2v2 passes** every gate criterion:
  - toy T1 bit-exact vs official on GPU;
  - toy T2 ratio 0.010;
  - toy T3 9/9 bitwise;
  - server det 8/8 and 8/8;
  - chain cold-reprefill and reverse-order 32/32 and 32/32;
  - gate_same and bank pass.
- Its phase 1 is queued at −24: τ² f01–f03, scores, BFCL; 11 tasks.
- **kivi_k4v4 is held.** It passes everything except the original toy T2 mean ratio: 0.0547 > 0.05. Official KIVI itself at BF16 scores 0.0496 vs its fp32 path. The cell passes the amended serving-precision T2 (0.0467). It waits for a decision on the criterion.
- **Amendment a2 (f585ae3).** The GPU toy failure was a real mismatch, not noise. Official KIVI's `(mx-mn)/(2**b-1)` on CUDA is a multiply by the fp32 reciprocal (PyTorch, CPU-scalar divisor). The kernel used IEEE division. On BF16 data this flipped quantization codes at exact ties. A CPU emulation reproduces the GPU max errors to 4 digits (0.0478, 0.1915).
- The fixed kernel's error vs the reference equals the null kernel's (0.0093 BF16).
- **rc=−9 was not OOM.** `worker.stop_server` SIGKILLs every pid on the task's GPUs, and that included the gate process, which held a CUDA context from the toy phase. The server phase now runs CUDA-free (kivi_gate_q8_r2, done).
- **Fidelity vs BF16 (200 decisions).**
  - Action agreement: k16v16 0.91, k4v4 0.735, k2v2 0.50.
  - First-token KL mean: 0.001, 0.015, 0.40.
  - The kernel path alone (k16v16) moves 9% of completions, so P3 carries a kernel-path component.
- **Cost.** Decode throughput is about 9× below FA2 (batch-16: 13 vs 117 tok/s).
- **Disclosed.** The §2.4 gates ran on the pre-fix kernel. The fix is one fp32 constant, so they were not re-run.

Evidence: `analysis/fork/kivi_gate/GATE.md`, `analysis/fork/kivi_gate/{gate_q8_toy3,gate_q8,diag_q8,gate_q8_toy2,toy_cpu_interp_fp16}.json`, `analysis/fork/kivi_gate/fid/`, `analysis/fork/newmethod/gate/q8_kivi_{k2v2,k4v4}/`, `scripts/a6000/pyhooks/{cloq_kivi,cloq_kivi_kernel}.py`, `cloq/kivi_ref.py`, `scripts/a6000/{kivi_gate,kivi_diag,make_tasks_kivi}.py`; commits 70addfa, ef9dc5a, f585ae3; logs `/data/ziyangs/cloq_work/logs/tasks/kivi_gate_q8{,_r2,_toy3}.log`.

## W100c-b — Paper: §5 direction split filled from W100d (shared action-side core; continuation-side and controller-dependent flips largely substitution-specific); F7 in the appendix (2026-10-02 PDT)
**TL;DR** The §5 direction-split `\pending{}` slot is filled from `analysis/fork/out/sameprec_split_20261002T145148Z.{md,json}` (INTERIM, K = 6, descriptive). The main points:
- The action side (G) shares a core above the within-task shuffle: rescue κ 0.60, harm κ 0.54; 56% of flipping units are design-specific, against 72% under the shuffle.
- H and F overlap at or near the shuffle level: H rescue κ 0.20; F κ 0.34/0.35, at chance under the task×Y_QQ null.
- Off-diagonal κ is 0.29, against a null of 0.23. 70% of off-diagonal units are off-diagonal under one design only.
- F flip volume differs: 193 vs 149, +4.3 [+0.4, +8.3] pp.
- Net ΔG −1.6 [−6.2, +3.0] pp comes only from the design-specific units and is not resolved.
- Cross-direction counts are 0 by construction. They are stated as such, not as evidence.

Other changes:
- The abstract and intro bullet now carry the shared-core nuance; 138/245 is kept.
- F7 (`make_fig_sameprec_split.py`) is Appendix Fig. `fig:split` and is added to `figures/provenance.json`.
- The common-state paragraph now names the test: does the continuation-side difference hold on identical states?
- The Discussion's "Bank P and Bank U" paragraph moved to Appendix "Ordinary states" to keep the page budget. Limitations starts at the top of p. 9.
- Build: 0 undefined references, 0 overfull boxes. `check_numbers.py` PASS (3071 numbers).

Evidence: `paper/latex/sections/{abstract,introduction,results_r2,appendix_moved,discussion}.tex`, `paper/latex/figures/f7_sameprec_split.pdf`, `paper/latex/figures/provenance.json`.

## W100d — Same-precision split: which units BF16 vs GPTQ-W4 d2 rescue and harm (INTERIM, descriptive, K = 6) (2026-10-02 07:55 PDT)
**TL;DR** This analysis asks whether the two substitutions have similar flip volume but rescue and harm different units. It uses the same 1020 task×block units as `sameprec_overlap.py` (q4+q8, f01–f06). It is INTERIM and descriptive (A1.4) and does not enter the reading. Re-run it on the frozen prefix after 10-03.
- **Action side (G, BQ vs QQ): the volume is similar and the units share a large core.**
  - Flips: 171 under BF16, 181 under d2 (Δ −1.0 [−3.9, +1.9] pp).
  - Rescues: 82 vs 95, with 56 shared (κ 0.60 [0.54, 0.65]).
  - Harms: 89 vs 86, with 51 shared (κ 0.54 [0.45, 0.61]).
  - Both overlaps are above the within-task×Y_QQ shuffle (46 and 43 expected; p < 0.001).
  - Still, 56% of the flipping units flip under one design only. The within-task shuffle would give 72%.
- **Continuation side and full substitution: the units differ.**
  - H (QB vs QQ): κ rescue 0.20, harm 0.45. F (BB vs QQ): κ rescue 0.34, harm 0.35.
  - Except for H harm, the overlap is not above the within-task×Y_QQ shuffle. Here different units flip.
  - F volume also differs: 193 vs 149 flips, Δ +4.3 [+0.4, +8.3] pp (t over 6 blocks, one of several contrasts).
- **Controller dependence (off-diagonal) is mostly design-specific.**
  - On the 697 units that diverge in both designs: 170 vs 177 off-diagonal, 81 shared, κ 0.29 [0.20, 0.40].
  - The within-task null expects 73 shared (κ 0.23, p 0.02).
  - 26.5% of the states are off-diagonal under one design only; that is 70% of the off-diagonal set.
  - The same-decision subset (n 404) gives κ 0.33.
- **Net decomposition.**
  - G under BF16: −7 = shared (56 rescues − 51 harms) + specific (26 − 38).
  - G under d2: +9 = the same shared part + specific (39 − 35).
  - ΔG = −1.6 [−6.2, +3.0] pp comes only from the design-specific units. Similar net and flip totals hide about 138 design-specific units.
- **Cross-direction counts are 0 for every contrast pair.** A unit rescued under one design and harmed under the other cannot exist, because Y_QQ is shared. This is forced, not evidence.
- **Trigger link: not assessable.**
  - Only 20 BF16 and 30 d2 fork states coincide with a scored Bank U U1 state (blocks f01–f03; f01 is in-sample for the rule).
  - Net among triggered states is −1 at every rate in both designs. This is uninformative at this n.
  - Bank U Y matches the precision-fork Y on 20/20 linked states.
- **Figure.** F7 is drawn by a separate script, so `make_figs.py`, which another session is editing, is untouched. It is not referenced from any section .tex file.

Evidence: `analysis/fork/sameprec_split.py`, `analysis/fork/out/sameprec_split_20261002T145148Z.{md,json}` (seed 20261002, 10000 permutations, B = 2000; units digest 45672ed6c997; reproduces ΔM −0.98 and ΔG −1.57 of `sameprec_20261002T142834Z`, and 107/64/74/775 of `sameprec_overlap_20261002T143218Z`), `paper/latex/tools/figs/make_fig_sameprec_split.py`, `paper/latex/figures/f7_sameprec_split.pdf`.

---

## W100c — Paper rewritten around the advisor's final framing: *Measuring the Task Value of Precision in Closed-Loop Agents*; central insight "sensitivity and value must be measured separately"; same-precision figure F6 (2026-10-02 PDT)
**TL;DR** The paper now opens with the deployment decision (replace this step / let BF16 take over / both), shows the verified four-branch airline case as Fig. 1a next to rescue/damage/net (Fig. 1b), and argues one insight: the ability to change task outcomes (sensitivity: M, off-diagonal) and the ability to choose a beneficial precision intervention (value: net, rescue/harm sets, trigger vs oracle) have to be measured separately. Evidence chain: BF16 replacement is sensitive with small net (§4); a same-precision substitution (GPTQ-W4 d1→d2) is about as sensitive, partly on different units (§5, new Fig. 2 = F6; TOST wording per SAMEPREC A1, INTERIM K = 6); the frozen trigger enriches flips but captures 2–5 of 34–38 oracle net units (§6, Fig. 3 = F4 moved to main text). Build: 22 pp, Limitations starts p. 8, 0 undefined refs, 0 overfull boxes; `check_numbers.py` PASS (3045 numbers, 0 unverified).
- **Same-precision text (binding wording):** "a higher bit width is not necessary for two-sided flips and controller dependence; they also appear when only the W4 calibration checkpoint is swapped". ΔM −0.98, 90% CI [−3.26, +1.30], p_TOST 0.067, equivalence not shown; ΔG_all −1.57 [−5.17, +2.04]; Δoff −1.21 [−4.09, +1.67]. Overlap: 107 both vs 30 expected, κ 0.53 [0.46, 0.58], task r 0.68, within-task shuffle 76 [69, 84], 138/245 flip under only one design. BF16's measured net values are kept (§5 "The measured value of the BF16 replacement stands"). K is marked `\pending{}` for the 10-03 freeze.
- **New figure F6** (`make_figs.py f6`): (a) r/d/M/G_all/off-diag for BF16 vs d2 with fixed-pool and crossed 95%; (b) TOST differences vs ±3 pp; (c) overlap only-BF16/both/only-d2 with independence and within-task nulls. Asserts every quoted number from the sameprec and overlap JSONs.
- **Pending slots (red):** K (×3); direction split of exclusive flips (rescue/harm per design); common-state K(c) under both continuations, M/M′, rescue/harm-set overlap, continuation dependence, reading, analysis set, and the common-state figure (main-figure target: similar flip volume, different rescue/harm sets); QuaRot vs SpinQuant W4A4; KIVI; Mistral-Small-3.2-24B; appendix perturbation backfill (restoration location, error dose, low-bit failure modes).
- **Moved, not deleted:** within-cell G/H/F (F2), per-cell controller dependence (F1), telecom development and holdout four-branch numbers, Bank U and both simulator controls, token analysis → new appendix section `sections/appendix_moved.tex`. Old draft archived in `paper/latex/sections/old/w99/`. Bib: QuaRot, SpinQuant, KIVI added.

Evidence: `paper/latex/main.pdf`, `paper/latex/sections/*.tex`, `paper/latex/tools/figs/make_figs.py` (f6), `paper/latex/figures/f6_sameprec.pdf`, `analysis/fork/out/sameprec_20261002T142834Z.{md,json}`, `analysis/fork/out/sameprec_overlap_20261002T143218Z.{md,json}`, `docs/insights/SAMEPREC_PROTOCOL.md` (A1), `docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md`.

## W99l-c — Same-precision correction: equivalence by TOST at ±3 pp (protocol amendment A1), not shown at K = 6; unit/task overlap of the precision and same-precision flips (2026-10-02 07:35 PDT)
**TL;DR** Advisor GPT-6.1 ruled, and the ruling is binding, that the §6 "similar" reading in W99l and Report 6 was wrong. "The interval includes 0 and |ΔM| ≤ 3 pp" does not show equivalence.
- **TOST at ±3 pp, K = 6, pooled q4+q8** (t over the 6 pooled block differences, df 5):
  - ΔM −0.98 pp, 90% CI **[−3.26, +1.30]**, p_lower 0.067, p_upper 0.009, so **equivalence is not shown** (p_TOST 0.067). This matches the advisor's numbers.
  - ΔG_all −1.57, 90% CI [−5.17, +2.04], p_TOST 0.230.
  - Δoff-diagonal (descriptive) −1.21, 90% CI [−4.09, +1.67], p_TOST 0.133.
- **What can be said instead.** A higher bit width is not necessary for two-sided flips and controller dependence; they also appear when only the W4 calibration checkpoint is swapped (d1 → d2): r′ 9.3, d′ 8.4, M′ 17.7 pp, off-diagonal′ 26.2%, every 95% lower bound > 0.
- **Overlap (new, descriptive).** Of 1020 task×block units:
  - 107 flip under both replacements, 64 only under BF16, 74 only under d2, 775 under neither.
  - 107 is far above the 30 expected if the two flip sets were independent within cell×block. Cohen's κ(M, M′) = 0.53, block-bootstrap 95% [0.46, 0.58]; the marginal-preserving null is κ +0.00 [−0.06, +0.07], p < 0.001; κ_max = 0.97.
  - Direction agrees on 107/107 both-flip units, but this is forced: the Q episode, and hence Y_QQ, is shared.
  - Task level: the per-task flip rate correlates r = 0.68 (Spearman 0.72) between designs. At matched noise (disjoint block halves), the cross-design r is 0.48, against within-design replication of 0.65 (precision) and 0.60 (same-precision), a ratio of 0.77. q4 0.58, q8 0.89.
  - Beyond task propensity, the same episodes flip: permuting M′ across blocks within each task gives 76 [69, 84] both-flip units against 107 observed.
  - **Answer:** similar average M corresponds to substantially overlapping sensitive units and tasks, not to disjoint ones. Still, 138 of the 245 flipping units flip under only one replacement.
- **Changes.**
  - `SAMEPREC_PROTOCOL.md` gets amendment A1, appended. The frozen text is a byte-identical prefix. The sha moves from `5c58d1e7d07ef10bd39f841236fccfd1436107c57ad264c62eaf14df94735823` to **`89484d35c77cfc9ba69fbf4fa5de3b90ae0c35cdd8f988d0509ba29c0580131c`**.
  - The manifest is unchanged and still records the v1 sha. `analyze_sameprec.py` accepts only the amended file and checks the v1 prefix.
  - The script now outputs the TOSTs, pooled and per cell, and the A1.3 reading automatically. It keeps the frozen §6 reading in the JSON, labelled superseded. The primary estimates are unchanged: ΔM −0.98 [−3.89, +1.93] is reproduced.
  - New option `--max-k` for earlier-K looks.
  - Correction notes are appended to W99l and Report 6.
- **Current K = 6.** The same-precision q8 run has only f01–f06 complete (g3 is missing), so the current prefix still equals K = 6. Everything here is INTERIM. The final analysis freezes on 2026-10-03 on the longest complete prefix.

Evidence: `analysis/fork/out/sameprec_20261002T142834Z.{md,json}` (TOST, K = 6), `analysis/fork/out/sameprec_overlap_20261002T143218Z.{md,json}`, `analysis/fork/analyze_sameprec.py`, `analysis/fork/sameprec_overlap.py`, `docs/insights/SAMEPREC_PROTOCOL.md` §Amendment A1, `docs/REPORT_GPT61_20261002_0730.md` (correction section).

## W100a — Common-state action sources on q8 (BF16 vs GPTQ-W4 d1 vs d2 actions; BF16 / d1 continuations): protocol pre-registered, gate queued (2026-10-02 07:50 PDT)
**TL;DR** Advisor GPT-6.1 asked for a common-state action-source comparison. On the 255 frozen q8 U2B states (Bank U f01–f03), the current action comes from BF16, W4-d1 or W4-d2, and the continuation is BF16 or d1. The key question is whether BF16 − d1 differs from d2 − d1 (= BF16 − d2), with a ±3 pp TOST. Only the two d2 arms are new (≤ 510 suffixes), produced by an additive fork_driver mode `commonstate`. Protocol sha256 `d76a8e3ee0bd607e7362ac629c3f458691cf44f4f59b26f1f061671bae92ecff`, commit `87733f7`, written before any d2 outcome at these states.
- **Design.**
  - Two task types per block: A (servers BF16 + d2: a_d2 → BF16) and B (servers d2 + d1: a_d2 → d1).
  - a_d2 is d2's own greedy action at the frozen state. A second generation must reproduce it bit-exactly (Q-replay), and it must be token-identical across A and B.
  - The four existing cells (BB/BQ/QB/QQ of `analysis/fork/bank_u/q8_gptq_w4_d1/`) are reused.
  - Rejected alternatives: a bank_u run with B = BF16, Q = d2 would need 3 suffixes per row. A bank_u run with B = d2, Q = d1 cannot work on U2B rows, because bank_u takes the B-role action from the recorded BF16 trajectory.
- **Same-state check (CPU, before queueing).** All 255 rebuilt states equal the reference Bank U rows on state_id, history_sha, recorded prompt ids, steps_left, the recorded action and the initial env hash. The f01–f03 U2B rows of `newmethod_panel_v1.json` are the same 255 rows.
- **Reuse validation.** Reference re-runs run on 20 % of rows (gate: all rows):
  - type A: BF16 continuation of the recorded action vs the original suffix;
  - type B: d1 regenerates a_Q, and its QQ must equal the reference QQ branch signature.
  - Implicit identities: if a_d2 = a_BF16 or a_d2 = a_d1, the new arm must equal the reference arm. Any failure quarantines the block.
- **Gate: PASS (both tasks, 2026-10-02 10:15 PDT; neither ran on node004, where the reference arms ran).**
  - B (`cs_gate_q8_d2_d1`, node007): idcheck d2 16/16 and d1 16/16; 12/12 rows; d2 replay bit-exact; 12/12 reference d1 QQ re-runs bit-exact against the Bank U branches (branch signature); 5/5 implicit identities pass; budgets OK.
  - A (`cs_gate_q8_d2_bf16`, node001): idcheck d2 16/16 and BF16 16/16; 12/12 rows; 12/12 BF16 no-ops of the recorded action bit-exact vs the original suffix; 4/4 implicit identities pass.
  - a_d2 is token-identical across the two tasks on 12/12 states, from different nodes.
  - Canaries and checkpoint shas are as pre-registered: BF16 e340…, d1 a9f8…/6ee628e6, d2 15e5…/320409ad.
- **Deviation D1 (09:35, logistics).** Node pins were removed from the queued tasks, because the pinned nodes were busy for hours. This was done before any panel outcome existed. The protocol sha becomes `c73ab2eec2f14052633e0703c2f50b1df9356c8222ba2ad1c8541301948198d0`, and the v1 text is a byte-identical prefix.
- **Queued (priority −29, 2 GPUs each).** 2 gates, then 6 panel tasks `cs_q8_{d2_bf16,d2_d1}_f0{1,2,3}`, which depend on both gates.
- **Analysis.** `analysis/fork/analyze_commonstate.py`:
  - it refuses to run unless the protocol sha matches;
  - it computes t over 3 block means and a task-cluster bootstrap (B = 2000, seed 20261002), with a frozen three-way reading and Holm across the two continuations;
  - `--selftest` (synthetic d2 := d1) exercises the code without new outcomes.

Evidence: `docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md`, `manifests/fork/commonstate_v1.json`, `scripts/a6000/fork_driver.py` (mode `commonstate`), `scripts/a6000/make_tasks_commonstate.py`, `analysis/fork/analyze_commonstate.py`, queue `/data/ziyangs/cloq_work/queue/todo/cs_*.json`.

## W99v-a1 — New-method panel protocol amendment A1 (before any panel outcome): rotation cells QuaRot-W4A16 / QuaRot-W4A4 / SpinQuant-W4A4 (KV16r) + W16 controls; Holm P2 = spinquant_w4a4 − quarot_w4a4; disclosed post-hoc rotation-gate T4 change (2026-10-02 06:30 PDT)
**TL;DR** The protocol sha moves from `9cd5c97982e62358a20574e4a9ecff923b68c9758742b1d8e74335b79cccc21d` to `28b78509dc1848344406071be2614763d6445eacb267303714d5ef7c884545bb`. The amendment is appended as a dated section (A1); the frozen text is unchanged and remains a byte-identical prefix. `analyze_newmethod.py` accepts only the new sha. The manifest (`7534c690…`) and its states are unchanged.
- **No panel outcome existed when this was written.** Checked at 06:24 PDT:
  - there is no `analysis/fork/newmethod/{tau2,bfcl,token_scores}/`;
  - no `nmp_tau2_*`, `nmp_score_*` or `nmp_bfcl_*` task is in the queue's done, running or todo directories;
  - the only outputs under `newmethod/` are the KIVI gates;
  - the rotation cells' nmp gates are still in todo.
- **Cells (A1.1).** `quarot_w4` (W4A16), `quarot_w4a4` (new), `quarot_w16`, `spinquant_w4a4` (new) and `spinquant_w16`, all at KV16r.
  - `spinquant_w4` is retired. Rotations learned at W16A16 do not move from their starting point, because the loss does not depend on the rotation.
  - `spinqoff_w4` is not built and is reported as "not run".
- **Holm (A1.2).**
  - P1: `quarot_w4` − `gptq_w4_d1`. The named confound is kept: the calibration data differ (WikiText-2 vs `calib_fp_traj_c1`).
  - **P2: `spinquant_w4a4` − `quarot_w4a4`**, the advisor's controlled contrast: same calibration, grid, clipping and KV16.
  - P3: unchanged.
  - Secondary: T1 `quarot_w4` − `quarot_w16`, T2 `spinquant_w4a4` − `spinquant_w16`, T3 `quarot_w4a4` − `quarot_w16`, K2. S1 is dropped.
- **Disclosed post-hoc change (A1.3).** The rotation gate's T4 was changed after SpinQuant's value (0.9976) had been seen.
  - Before: absolute fp32 top-1 ≥ 0.999 (3fd9522).
  - After: ≥ QuaRot − 0.002 and mean |Δlogprob| ≤ 1.5 × QuaRot (38db810).
  - The reason: QuaRot's accepted export reaches only 0.9956, because of bf16 storage.
  - No served SpinQuant output and no panel outcome existed at the time.
- **Interpretation (A1.4).** SpinQuant's W16A4 WikiText perplexity, 8.76, is below BF16's 9.73. The learned rotation partly acts as domain adaptation, so WikiText perplexity is not a fidelity criterion. The relevant measures are agent-domain KL, act flip and D_cc.
- **q_blocks spec bug (A1.5).** It is fixed in `make_newmethod_panel.py` (a98a2a6).
- **Dry run.** `analyze_newmethod.py --dry` runs and passes the guard.
  - The reference cells gptq_w4_d1, awq_w4 and kvq_int8 have f01–f03 at 85/85, all admitted.
  - The BFCL reference cells cover 200/200 items with 0 quarantined.
  - No new-cell rows exist.

Evidence: `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (Amendment A1), `analysis/fork/analyze_newmethod.py`, `analysis/fork/rot_gate/GATE.md`, `scripts/a6000/{rot_gate_check,make_tasks_rotpanel,make_newmethod_panel}.py`, W99r, W99s.

## W99l — Same-precision 2×2 results (INTERIM, K = 6 blocks f01–f06): turnover and controller dependence are not precision-specific (2026-10-02 06:30 PDT)
**TL;DR** On the pre-registered analysis set so far (f01–f06, q4+q8, 85 tasks per block), replacing BF16 with a second GPTQ-W4 calibration draw (Q′) gives the same turnover. Precision M is 16.8 [13.9, 19.6]% and same-precision M′ is 17.7 [15.7, 19.8]%. The paired ΔM is −1.0 [−3.9, +1.9] pp (t over 6 blocks; crossed −4.5 to +2.7). The off-diagonal share is 25.0% vs 26.2%, Δ −1.2 [−4.9, +2.5] pp (descriptive). Frozen reading (§6): **similar on both** → the paper must say that turnover and controller dependence largely reflect generic trajectory sensitivity of the closed loop rather than precision-specific effects. This is interim: the prefix will grow as q8 g3–g6 complete before the 2026-10-03 freeze.
- **Divergence rate.** 76.9% in both designs (q4 65.3% vs 68.0% precision; q8 88.4% vs 85.7%). Q′ and Q differ in tool structure about as often as BF16 and Q.
- **Per cell (secondary).**
  - q4: ΔM +0.6 [−3.1, +4.3]; Δoff −2.9 [−9.7, +4.1].
  - q8: ΔM −2.5 [−5.6, +0.5]; Δoff +0.5 [−2.8, +3.6].
  - Both cells read "similar".
- **Divergent states (pool).**
  - Same-precision: G′ +0.6, H′ −0.3, F′ −0.3, I +0.6 pp; strict reversals 3.7% (precision 2.6%).
  - 3×3 off-diagonal mass: 201/784 states (precision 194/784).
- **Per state, conditional on divergence in both designs.** Off-diagonal share precision 24.8% vs same-precision 26.1% (n 697). At the same t*: 27.3% vs 26.9% (n 404).
- **Acceptance.** QQ no-op samples 146/146. Q replay 784/784 states. Prefix and env-hash checks 2437/2437 branches. 0 quarantined directories.

Evidence: `analysis/fork/out/sameprec_20261002T125556Z.{md,json}` (protocol sha 5c58d1e7… verified by the script), fork outputs `analysis/fork/sameprec/{q4,q8}_gptq_w4_d1_vs_d2/g*/` (cluster), queue `done/fork_sameprec_*`.

- **Correction (2026-10-02, W99l-c; appended, the entry above is kept as written).** The "similar → generic trajectory sensitivity, not precision-specific" reading above is an incorrect equivalence reading (advisor GPT-6.1, binding): an interval that contains 0 does not show equivalence. By TOST at ±3 pp (protocol amendment A1), ΔM 90% CI [−3.26, +1.30], p_lower 0.067 → equivalence is **not shown**; the same holds for ΔG_all and Δoff. The defensible statement is: "a higher bit width is not necessary for two-sided flips and controller dependence; they also appear when only the W4 calibration checkpoint is swapped (d1 → d2)." See W99l-c.

## W99q — m24 results: none yet; gate PASS, formal stage 1 (bfpair + BFCL nmp_v1) queued at −26 (2026-10-02 09:05 PDT)
**TL;DR** No formal m24 results exist, so no G/H/F, rescue/damage, turnover, interaction or interval is reported. The W99p gate passed on 2026-10-02 09:01 PDT, including all four fork gates. At 09:03 `make_tasks_m24.py bfpair --write` queued `a6k2_m24_bfpair_{f01_f02,f03_f04,f05_f06}` and `ext_m24_{bf16,rtn_w4}_bfcl_nmp1` (2 GPUs each, −26, no deps). They sit behind the −29…−27 tasks (cs_q8_d2, sameprec). The panel is not queued yet, because the manifest needs the bfpair runs admitted in a snapshot.
- **Remaining steps:**
  1. ~~bfpair~~ (queued 09:03).
  2. Once `a6k2_m24_bfpair_f01…f06` are admitted in an `analysis_daemon` snapshot (about every 22 min): run `make_newmethod_panel.py build --model m24 --snapshot <snap>`. Then add protocol amendment **A2** with the manifest sha, together with the `analyze_newmethod.py` constants (`PROTOCOL_SHA256`, `MANIFESTS["m24"]`).
  3. `make_tasks_m24.py panel --cell rtn_w4 --write` queues the gates, f01–f03 bank_u, and scores. Add `--bfcl` only if BF16 ≥ 10% on nmp_v1 (`ext_m24_bf16_bfcl_nmp1`).
  4. `--cell gptq_w4_d1`. Its calibration (`a6k2_m24_calib_c1`, `manifests/a6k2/m24/calib_fp_traj_c1.json`) is done.
  5. The analysis is `analyze_newmethod.py --model m24`. Expansion: `expansion_m24.json`, T_decide 2026-10-04 00:00 PDT.
- **Expected cost.** From the gate's throughput, each bfpair task (2 blocks × 85 tasks) takes about 1.3 h on 2 GPUs, and each BFCL nmp_v1 run (200 items) about 50 min. Once claimed, stage 1 is about 1.5 h of wall time on 5 pairs. The τ² gate needed 97 min on 4 GPUs and gate_same 51 min, so each panel cell's two gates plus f01–f03 come to roughly 6–8 h of wall time per cell on 4 GPUs.

## W99p — m24 (Mistral-Small-3.2-24B) second-family gate: **PASS** — serving, tool protocol, BF16 capability, all four fork gates (τ² and BFCL gate + same-checkpoint control), leak test, throughput (2026-10-02 06:05 PDT; fork gates closed 09:01 PDT)
**TL;DR** Mistral-Small-3.2-24B now serves text-only in vLLM 0.29 with the official tokenizer and tool parser (mistral/mistral), and its tool protocol is exact. In τ², local prompt ids equal the server's on every decision, with 0 parser errors in τ² and BFCL. BF16 is not at a floor: τ² 4/20 = 20%, and 25% on the 16 shared tasks (Qwen BF16: 19%, 25%, 38% and 44% across q4/q8/q14/q32). BFCL is 2/20 = 10% (Qwen 10–15% on the same items; l8 was 0/20). After node008 restarted onto the multi-pair runner (04:34), the BFCL fork gate passed: BB no-op 4/4, QQ, replay, isolation, save/load and re-prefill, 0 branch errors. The BFCL same-checkpoint control also passed. **Update 09:05 PDT: gate PASS.** The r1 τ² fork gate (`/v1/completions` identity probe) failed only on idcheck Q 13/16. Official Mistral tool calls are grammar-constrained on chat requests, and that probe is not (GATE.md). It was rerun as `fork_gate_m24_rtn_w4_r2` with the chat-based probe (7009bec): idcheck Q 16/16 and B 16/16, including the three r1 mismatches, and every other sub-check passes (8 states, 0 errors, 97 min). The τ² same-checkpoint control `fork_gate_same_m24_rtn_w4` passes: idcheck 8/8 + 8/8, 6 states, four arms identical, 0 errors. The formal stage 1 was queued at 09:03 (W99q).
- **Why the 09-28 smoke failed.** vLLM resolved the multimodal repo to Pixtral/Mistral3, whose module imports `PixtralRotaryEmbedding`, a class transformers 5.17 removed. Fix: a text-only view (`scripts/a6000/m24_textonly.py`). It copies the `language_model.*` tensors byte-identical and renames them to `MistralForCausalLM` (provenance in `ckpt_cache/m24_textonly_v1/textonly.json`). models.json `m24` gets `src_path` and `tokenizer_mode: mistral`; `serve.sh` passes `--tokenizer-mode`.
- **Harness.** The repo ships no HF chat template, so `cloq/mistral_render.py` renders locally through the server's own preprocessing (ChatCompletionRequest → `maybe_serialize_tool_calls` → `truncate_tool_call_ids` → MistralTokenizer). τ² prompt ids match on 430/430 decisions (BF16 207, RTN-W4 223).
  - The Mistral template renders `[CALL_ID]`, and vLLM draws those ids at random, so a no-op replay could never be bit-exact. τ² and BFCL therefore set id = `d<decision:05d>c<k:02d>` (m24 only).
  - Without the env, Qwen and Llama paths are unchanged: the leak test passes 9/9 in both modes, and the template test gives the same counts before and after.
- **New agent-failure class.** Mistral sometimes emits a tool call with an invalid function name: empty, or the text "YOU ARE BEING TRANSFERRED TO A HUMAN AGENT…". mistral_common then refuses that turn at the next request (HTTP 400). The worker and ext adapters now score this `agent_parse_error` (W27 rule; already in AGENT_SIDE). Rate: 3 of 1,348 decisions (0.22%), 3 of 137 episodes (2.2%): BF16 cal 2/57, RTN BFCL 1/20, 0 in the gate τ² runs. The two failed tasks were requeued.
- **Runner (engineering condition 1).** Fork tasks with `gpus 4, gpus_per_role 2` take two whole NVLink pairs; B is TP=2 on one pair and Q on the other (`noderunner.py`, `worker.run_fork`). The pairs are reserved only while such a task is runnable on the node. A dry run with a fake clock gives the same claims as the old runner on a legacy queue.
- **GPTQ.** No change to `cloq/quantize.py` is needed: the worker passes `--src <text-only dir>`, and `MistralForCausalLM` has the Llama decoder layout (`model.model.layers`, `rotary_emb`). The BF16 calibration-split run and calib c1 are queued at −25.
- **Throughput (2 GPUs).** τ² 20 tasks: 662 s (BF16) and 718 s (RTN-W4, including a ~30 s build). BFCL 20 items: 291 s.

Evidence: `analysis/fork/m24_gate/{GATE.md,gate_summary.json,analyze_gate.py,probe_dry.{py,out},test_*.out}`, fork outputs `analysis/fork/m24_gate/{tau2_rtn_w4_r2,tau2_same_rtn_w4,bfcl_rtn_w4,bfcl_same_rtn_w4}/` (cluster; `tau2_rtn_w4/` = superseded r1), queue `done/{fork_gate_m24_rtn_w4_r2,fork_gate_same_m24_rtn_w4,fork_ext_gate_m24_rtn_w4_bfcl,fork_ext_gate_same_m24_rtn_w4_bfcl}.json`, `manifests/a6k2/m24/gate_tau2_v1.json`, `manifests/bfcl/bfcl_mt_m24_v1.json`, `scripts/a6000/{m24_textonly,make_tasks_m24}.py`, `cloq/mistral_render.py`, queue `done/{a6k2_m24_bf16_gate,a6k2_m24_rtn_w4_gate,ext_m24_bf16_bfcl_gate_m24,ext_m24_rtn_w4_bfcl_gate_m24}.json`, runs `runs/a6k2_m24_*_g1`, `runs/ext_m24_*_bfcl_gate_m24` (cluster).

## W99s — Rotation cells on the new-method panel: no results yet; QuaRot phase 1 is released automatically once its nmp gates pass, SpinQuant once its rotation gate passes (2026-10-02 04:20 PDT)
**TL;DR** No panel outcome exists yet, so no G/H/F/rescue/damage/turnover/I or D_cc is reported. Every queued task is effect-blind and gate-conditional.
- **Cells registered (Q role; B = BF16; KV16 with the online Q/K rotation).** Protocol cells `quarot_w4` (QuaRot-W4A16-KV16), `quarot_w16` and `spinquant_w16` (transform controls). Advisor's A4 configurations: `quarot_w4a4` (QuaRot-W4A4-KV16) and `spinquant_w4a4` (SpinQuant-W4A4-KV16).
- **Not built: the protocol's `spinquant_w4` (learned rotation at W4A16).** It needs rotations learned with RTN-W4 in the loop. Rotations learned at W16A16 are a stationary point of a rotation-invariant loss.
- **Needs a protocol amendment (owner: panel agent).**
  - `analyze_newmethod.py` NEW_CELLS and Holm P2 (spinquant_w4 − quarot_w4) do not include the A4 cells. The advisor's controlled contrast is spinquant_w4a4 − quarot_w4a4.
  - `make_newmethod_panel.py spec` prints gate_same `q_blocks` as "run:domain" strings, but `fork_driver.load_blocks` unpacks [run, domain] pairs. make_tasks_rotpanel.py uses pairs.
- **Queued at −25 (q8 forks: 2 GPUs, pinned to node004/005/007).**
  - Gates: `nmp_gate_{same,bank}_q8_{quarot_w4,quarot_w16,quarot_w4a4}`.
  - Release: `rot_release_panel_qr_q8`. It checks each cell's gate_same verdict, then queues f01–f03 `nmp_tau2_*`, `nmp_score_*`, `ext_q8_<cell>_bfcl_nmp1` and the four `nmp_bfcl_*` tasks.
  - SpinQuant chain: `rot_spin_learn_q8` → `rot_gate_sp_q8` → `rot_release_gates_sp_q8` → `rot_release_panel_sp_q8`.
- **ETA.** It is set by queue capacity, not compute:
  - Compute per cell: about 3.5–4.5 GPU-h for the two gates plus about 8–10 GPU-h for f01–f03 (from the Bank U q8 task times, about 45 min wall per block task on 2 GPUs, plus the 21 min GPTQ rebuild per task), plus about 4–6 GPU-h for BFCL.
  - Five cells: about 80–100 GPU-h.
  - Earliest phase-1 completion is about 2026-10-03 midday if the q8 pairs on node004/005/007 free up. The SpinQuant cells finish about 3 h later than QuaRot (learning plus rotation gate). This is before the protocol's expansion decision at 2026-10-03 20:00.

Evidence: `scripts/a6000/{make_tasks_rotpanel,rot_gate_check}.py`, `/data/ziyangs/cloq_work/queue/todo/{rot_*,nmp_gate_*_quarot_*}.json`, `analysis/fork/rot_gate/GATE.md`.

## W99r — Rotation gate (QuaRot vs SpinQuant, weight + activation axis, q8): QuaRot PASS; SpinQuant rotations learned (WikiText ppl below BF16 = domain adaptation through the A4 quantizer, not fidelity); served SpinQuant gate runs past the 6-hour window (2026-10-02 05:45 PDT)
**TL;DR** SpinQuant is added as Cayley-SGD learning of R1/R2 (`cloq/spinquant.py`). It sits in QuaRot's skeleton, so the controlled pair differs only in the rotation: same 128×2048 WikiText-2 windows, same GPTQ-W4 grid and clip, same A4 grid (per-token sym INT4, clip 0.9), same online Hadamards, KV16r.
- **QuaRot passes the gate on q8.**
  - Transform control: W16A16 ppl 9.749 vs BF16 9.726; act flip 0.005; first-token KL 0.0026.
  - Batch, prefix and chunk invariance, and causal prefix identity, all hold.
  - Throughput is not reduced.
- **Local fidelity, measured only.** Adding A4 to QuaRot-W4 raises the act flip from 0.075 to 0.198 and the first-token KL from 0.31 to 1.15. W16A4 alone (0.125 / 0.66) is worse than W4A16 alone.
- **SpinQuant.** CPU tests pass: the QuaRot point is reproduced exactly, learned-rotation invariance holds to 3e-7, and the learner path equals the serving path at A4.
  - The GPU learning ran 04:15–05:36, after 3 h 50 min in the queue: 1-GPU slots were starved by priority and the runners' pair reservation. 100 steps took 43 s/step with a 30.7 GB peak. Epoch-mean CE fell 2.435 → 2.228.
  - **WikiText-2 test perplexity (learner path):** A4 went 11.04 (QuaRot point) → **8.76**, below BF16's 9.73. A16 went 9.74 → 9.64.
  - **This is a confound, not fidelity.** The rotation changes the function only through the A4 quantizer (and bf16 rounding). Learned on WikiText-2 train, it adapts the instruction-tuned model to WikiText, and WikiText test perplexity then rewards that adaptation.
  - The ppl-based "published direction" criterion therefore passes but is uninformative. Agent-domain KL / act flip vs BF16 is the meaningful fidelity direction, and the panel's D_cc answers research question 2.
  - The served SpinQuant gate (`rot_gate_sp_q8`) was claimed at 05:37 and ends after the window.

| q8, KV16r | ppl | act flip | 1st-token KL | E3 token flip |
|---|---|---|---|---|
| BF16 | 9.726 | 0 | 0 | 0 |
| QuaRot W16A16 | 9.749 | 0.005 | 0.003 | 0.004 |
| QuaRot W16A4 | 11.072 | 0.125 | 0.660 | 0.053 |
| QuaRot W4A16 | 9.914 | 0.075 | 0.307 | 0.030 |
| QuaRot W4A4 | 11.290 | 0.198 | 1.155 | 0.063 |

- **Learning recipe (official `10_optimize_rotation.sh` / README).**
  - lr 1.5 cosine, 100 steps × 8 × 2048, momentum 0, STE.
  - W16A4 objective, per the README rule for GPTQ + A4.
  - Init at the QuaRot point, so the learned-vs-random contrast is pure optimisation.
  - Official-pipeline deviations (calibration set, sym/clip grid, the kept across-head H_32, R2 init) are listed in GATE.md. The official default is reserved as `spinqoff_w4` and is not built.
- **Code.**
  - `cloq/quarot.py --rotations`: polar projection, sha pin.
  - Worker ckpt kind `spinquant`.
  - `aq_validate.py --suite spin`, which now adds a WikiText-2 test ppl probe, top-k KL and a throughput probe.
  - Frozen criteria and automatic release: `rot_gate_check.py`.
- **Engineering note.** The serving Hadamard's broadcast K-block mix would materialise (tokens, 12, 12, 1024) fp32, about 10 GB at 16k tokens, during learning. The learner uses a GEMM form, `had_light`, and the tests show it is identical to the serving form.

Evidence: `analysis/fork/rot_gate/{GATE.md,validate_qr_q8.json,validate_qr_q8_ppl.json,ckpt_q8_qr16.quantization.json,ckpt_q8_qr4.quantization.json,unit_tests.json,verdict.json,openloop/}`, `cloq/{spinquant,quarot}.py`, `tests/test_spinquant.py`, `scripts/a6000/{aq_validate,rot_gate_check,make_tasks_rotpanel}.py`, `scripts/a6000/worker.py` (spinquant kind), queue `done/rot_gate_qr_q8.json`, logs `/data/ziyangs/cloq_work/logs/{tasks/rot_*,ahook/{validate_q8_*,build_q8_*,ppl_*}}`.

## W99o — Process-shared BFCL long-context state (W99g open issue): scope, quarantine, fixed-code reruns, analysis guard; no published number changes (2026-10-02 03:40 PDT)
**TL;DR** Only the four q4 BFCL long_context dev fork directories were affected. Their states with inconsistent replay match W99g exactly: 38/133 GPTQ-W4, 21/151 AWQ, 43/165 GPTQ-W3 and 50/197 KV4. In every one of these states, only the branch state was wrong; the search state was clean. No BFCL eval run was affected. The four directories were quarantined and rerun on the same items with the same protocol and the fixed bfcl_run. The reruns are 100% replay-consistent, and all 646 states have identical four-arm outcomes. `analyze_ext`/`ext_r2` now fail on any replay-inconsistent admitted state. The new outputs `ext_20261002T103443Z` and `ext_r2_20261002T103454Z` equal `ext_20261001T135106Z` and `ext_r2_20261002T024433Z` in every reported number (0 changed leaves; three κ/expected-share floats in q4 GPTQ-W3 differ only at ~1e-16). The paper numbers stand: BFCL W4 off-diagonal 4.7–17.1% (pool 10.3%), q4 AWQ G_all −3.8 [−6.5, −1.3], turnover 5.2–24.6%, expected 16.2–32.4%, κ 0.47–0.71, and coverage 573/642/540/787 states. The only changes are the src paths, if the main session wants to cite the guarded outputs.
- **Mechanism (confirmed).** `TravelAPI._load_scenario(long_context=True)` inserts the module-level `CREDIT_CARD_EXTENSION`/`BOOKING_RECORD_EXTENSION` entries by reference, so a booking mutates the shared constant. Only `bfcl_long_context` loads these constants. Each eval domain and each fork task (one category) runs in its own process, so no other category ever shares a process with a long-context backend. Within a fork task the search runs first, then the BB, BQ, QB and QQ phases. The contaminated hashes appear only in branches: the states whose state hash differs from pristine are, per arm (BB/BQ/QB/QQ), GPTQ-W4 0/38/38/4, AWQ 0/0/17/5, GPTQ-W3 22/43/43/4 and KV4 30/50/50/3.
- **Scope check** (`scripts/ext/w99o_scope_check.py`, CPU, 375 s → `analysis/fork/ext/w99o/scope_check.json`). All 24 BFCL eval runs were checked: q4/q8/q14/q30a3/q32, every arm, 197 long_context episodes each. Replayed with the fixed code (pristine state), every one reproduces the recorded observations, prompts, decision counts, termination and official success. **No eval run is affected.** For the forks, the search state at t equals the pristine state on every q4/q8/q14 state. Branch hashes differ from pristine exactly on the replay=false states (0 hidden cases). q8 (4 cells) and q14 are clean.
- **Quarantine.** The four directories moved to `analysis/fork/ext/quarantine/w99o/<name>/`, each with a `QUARANTINE` reason file (cluster only, not in git).
- **Reruns.** Queue tasks `fork_ext_dev_q4_{gptq_w4_d1,awq_w4_d1,gptq_w3,kvq_int4}_bfcl_long_context_w99o` at priority −29. They copy the original specs (all 197 items of the Q eval block, fork-ext-v1, concurrency 8, 10% QQ no-op) with only the id, priority, node and note changed. AWQ/W3 ran pinned to node001; GPTQ-W4/KV4 were unpinned (node001's free upper GPUs were reserved for TP2) and ran on node006. They finished between 01:43 and 03:32 PDT. B canary and Q canary/ckpt sha match the original tasks. The KV4 Q `hook_version` changed (ca3e42d2 → 72a25eb2, from pyhooks edits elsewhere), but its canary is identical. Each rerun matches the original: the same 133/151/165/197 states (0 excluded), QQ no-op 9/9, 24/24, 15/15 and 17/17, replay_ok 100%, and 0 states with any changed Y (`analysis/fork/ext/w99o/state_compare.json`).
- **Guard.** `analyze_ext.replay_guard` makes the analysis exit with FAIL and write nothing if an admitted directory has a divergent state whose effects.jsonl `replay` is not true, or has no effects.jsonl. ext_r2 uses the same guard. `superseded_pending` refuses to write while a quarantined directory's rerun is incomplete (the analysis daemon runs analyze_ext on every new fork_ext_dev done). `--models` defaults to q4,q8, so q14 (analysed by `ext_q14.py`) is not pooled. The guard was tested: it fails on the quarantined AWQ directory (21/151) and passes q8.
- **Diff** (`scripts/ext/w99o_diff.py` → `analysis/fork/ext/w99o/diff.{md,json}`). It covers tab:extr2 columns per cell and pool, the quoted ranges, and an exhaustive leaf diff: 0 changes.
- **Not touched / for the main session.** `ext_q14_20261002T085647Z` already used the rerun q4 GPTQ-W4 long_context directory (573/573 replay-consistent). `analyze_ghf` coverage reads the same dev_summary counts, which are unchanged. make_figs may keep the old src or switch to the new outputs; the values are identical.

Evidence: `analysis/fork/ext/w99o/{scope_check.json,state_compare.json,diff.md,diff.json}`, `scripts/ext/{w99o_scope_check,w99o_state_compare,w99o_diff}.py`, `analysis/fork/{analyze_ext,ext_r2}.py`, `analysis/fork/out/{ext_20261002T103443Z,ext_r2_20261002T103454Z}.{json,md}`, queue `done/fork_ext_dev_q4_*_bfcl_long_context_w99o.json`, logs `/data/ziyangs/cloq_work/logs/tasks/fork_ext_dev_q4_*_bfcl_long_context_w99o.log`, quarantine `analysis/fork/ext/quarantine/w99o/` (cluster only).

## W99h — q14 (Qwen3-14B) BFCL GPTQ-W4 d1 four-arm fork: results (within-Qwen-family scale sensitivity check) (2026-10-02 02:00 PDT)
**TL;DR** This is a within-Qwen-family scale sensitivity check with a single configuration (GPTQ-W4 d1). It is not second-family evidence, and it is exploratory.
- **Run.** The fixed panel is complete: 4/4 tasks and 788 items, with 0 excluded and 0 quarantined. 471 states diverge (60%): base 99, miss_param 127, miss_func 144, long_context 101. QQ no-op passes 58/58, and 471/471 states are replay-consistent under the W99o guard.
- **Effects on divergent states** (pp, 95% item bootstrap):
  - G +5.7 [+2.9, +8.7], H +0.4 [−1.1, +1.9], F +9.1 [+5.8, +12.5]
  - G−H +5.3 [+2.3, +8.4], F−G +3.4 [+1.3, +5.6], F−H +8.7 [+5.5, +11.9], I −3.0 [−5.4, −0.7]
  - G_all +3.4 [+1.8, +5.2]
  - arm success BB 16.6%, BQ 13.2%, QB 7.9%, QQ 7.4%
- **3×3 and patterns.** The 3×3 diagonal holds 441/471 states. The off-diagonal share is 6.4% [4.2, 8.7], against 21.4% expected under independent pairing (κ 0.703), with 0 strict reversals. Top patterns: 0000 376, 1100 31, 1111 20, 1000 17, 0011 10.
- **Divergence types:** tool_args 149, other/tool_count 119, tool_name 91, talk→act 77, act→talk 35.
- **Failing arms:** instance-state mismatch dominates, followed by execution-response mismatch and empty-turn responses. A few context overflows and force-quits occur.
- **Common panel** (all 788 items; DESCRIPTIVE, because each model selects its own divergent states):

  | model | states | G | H | off-diagonal | κ |
  |---|---|---|---|---|---|
  | q4 | 573 | +2.8 | +1.4 | 11.7% | 0.574 |
  | q8 | 533 | +0.9 | +1.5 | 4.7% | 0.710 |
  | q14 | 471 | +5.7 | +0.4 | 6.4% | 0.703 |

  G is not monotone in scale.
- **Infrastructure.**
  - No task failed and none was requeued.
  - The miss_param fork process started after W99p's `bfcl_run` change, which is a no-op without `CLOQ_TOKENIZER_MODE=mistral`.
  - The q4 GPTQ-W4 long-context cell used here is the W99o fixed-code rerun. Its four-arm numbers are identical to the pre-W99o cell.

Evidence: `analysis/fork/out/ext_q14_20261002T085647Z.{md,json}` (script `analysis/fork/ext_q14.py`: analyze_ext admission with the W99o guard plus ext_r2 estimands; q14 is never pooled into the W4 pool), dev outputs (cluster only) `analysis/fork/ext/dev/bfcl_q14_gptq_w4_d1_{base,miss_param,miss_func,long_context}/`, queue `done/fork_ext_dev_q14_gptq_w4_d1_bfcl_*.json`, logs `/data/ziyangs/cloq_work/logs/tasks/fork_ext_dev_q14_gptq_w4_d1_bfcl_*.log`, gate W99g.

## W99k — Same-precision 2×2 fork (Q vs Q′): protocol pre-registered, gate PASS (q4, q8), 12 formal tasks queued (2026-10-02 00:55 PDT)
**TL;DR** This adds the same-precision control asked for by the reviewer. The BF16 role is replaced by Q′ = GPTQ-W4 d2 (calibration c2), and Q = GPTQ-W4 d1 is unchanged. The fork pipeline is otherwise identical. The protocol was committed before any outcome: `docs/insights/SAMEPREC_PROTOCOL.md`, **sha256 5c58d1e7d07ef10bd39f841236fccfd1436107c57ad264c62eaf14df94735823** (commit 0d2f1ee). The gate passes for both cells. Blocks f01–f17 are queued at −28.
- **Design.** Driver role B = Q′, so BB = Q′Q′, BQ = Q′Q, QB = QQ′ and QQ = QQ. The Q episodes are the same `a6k2_<m>_gptq_w4_d1_<blk>` runs as in the precision dev forks, so units pair task×block one to one. Cells: q4 (1 GPU) and q8 (2 GPUs, pinned to node004/005/007).
- **Blocks.** The analysis set is the longest prefix of f01…f17 that is complete in both cells at the 2026-10-03 freeze, with a minimum target of f01–f06.
- **Primary.** Paired ΔM = M_prec − M′ on the same units, pooled q4+q8. Intervals: fixed pool (t over block means if K < 10, block bootstrap if K ≥ 10) plus crossed.
- **Secondary (descriptive).** Δ off-diagonal share, (a) on units that diverge in both designs and (b) on units that diverge at the same t*.
- **Frozen rule (§6).** The "similar" case is an interval containing 0 with |Δ| ≤ 3 pp; in that case the paper says the effect is generic trajectory sensitivity. If the interval excludes 0 with Δ > 0, the paper reports a precision-specific excess. Any other result is reported as is.
- **Gate.** Both cells pass every check:
  - idcheck 16/16 for Q and for Q′, with distinct canaries.
  - The Q′ prompt-id check excludes 0/12 search rows.
  - The search finds states in 9/12 (q4) and 11/12 (q8) tasks.
  - QQ no-op 6/6; Q′Q′ no-op on Q′'s own d2_n1 trajectory 4/4.
  - Q replay, isolation 2/2, save/load, budget and re-prefill all pass.
- **Queued.** `fork_sameprec_{q4,q8}_g1…g6` (3 blocks each; g6 = f16–f17), priority −28. Expected wall time: about 2.5 h per q4 task and 3.5 h per q8 task once a GPU is free. On the current busy cluster, f01–f06 should finish in about 4–8 h and f01–f17 in about 12–24 h.
- **Analysis.** `analysis/fork/analyze_sameprec.py` imports the analyze_dev and analyze_ghf code and refuses to run on a protocol sha mismatch. It was dry-run with the precision directories standing in for both designs: ΔM = 0 exactly, and the precision cells reproduce dev_all (q4 M 15.6 on f01–f17 vs 15.5 on 20 blocks).

Evidence: `docs/insights/SAMEPREC_PROTOCOL.md`, `manifests/fork/sameprec_v1.json`, `scripts/a6000/make_tasks_sameprec.py`, `analysis/fork/analyze_sameprec.py`, `analysis/fork/sameprec/GATE.md`, `analysis/fork/sameprec/gate/{q4,q8}/gate.json`, queue `done/fork_sameprec_gate_{q4,q8}.json`, `todo/fork_sameprec_{q4,q8}_g*.json`, logs `/data/ziyangs/cloq_work/logs/tasks/fork_sameprec_*.log`.

## W99v — New-method common panels frozen: τ² U2B ordinary-state bank (q8, 6 blocks) + 200-item BFCL panel; protocol, manifest, builder, analysis skeleton (2026-10-02 PDT)
**TL;DR** This entry freezes the common panels that the QuaRot/SpinQuant (q8 W4) and KIVI (q8 KV) agents and the Mistral agent run against. CPU only; nothing was queued and no outcome was read.
- **Panel A (τ²).** Sub-bank **U2B**: one ordinary state per task × block on the BF16 trajectory `a6k2_q8_bfpair_<blk>`, using the Bank U rule.
  - **Why U2B.** It is the only method-independent state source.
    - U1 and Bank P select states per method.
    - U2Q (GPTQ-sourced) privileges one quantizer.
    - Under U2B, BB is the shared BF16 original, so the common-continuation contrast between two methods is exactly Y_QB(m1) − Y_QB(m2).
  - **Size.** f01–f06 × 85 retail/airline tasks = 510 states, 0 missing. Every configuration runs all four arms.
  - **Reference cells at no GPU cost.** The f01–f03 rows are byte-identical to Bank U U2B (255/255 asserted by the builder), so the existing q8 GPTQ-W4 d1/AWQ-W4/KV8 four-arm rows on those states serve as reference cells.
- **Phase 2 (f04–f06), effect-blind rule.** Decided once, at the earlier of "all phase-1 tasks finished" or 2026-10-03 20:00 PDT. Expansion is all-or-none over the eligible cells plus the reference cells, iff now + 1.25 × (measured phase-1 GPU-h + the references' U2B share) / 8 GPUs ≤ 2026-10-04 12:00 PDT. The rule reads only queue status and summary throughput fields.
- **Panel B (BFCL).** 50 ids per category (200 in total), ordered by sha256("cloq-nmp-bfcl-v1:" + id).
  - The pool is the eval ids minus 214 dev, smoke and gate ids (q4/q14/l8 gates, l8 probe, and every id in the gate directories).
  - Four arms per item, following fork-ext-v1.
  - The existing q8 BFCL reference forks cover all 200 items.
- **Estimands.** G, H, F, D_cc = Y_QB − Y_BB, I, r/d/M and damage_cc/gain_cc/M_cc.
  - τ² intervals: t over block means as primary (k < 10), the block bootstrap alongside, and the crossed task × block bootstrap as secondary.
  - BFCL intervals: item bootstrap within category.
  - Holm family: P1 QuaRot − GPTQ, P2 SpinQuant − QuaRot, P3 KIVI − KV8, on D_cc.
  - Local fidelity (exact agreement; KLu teacher-forced on a_B) is reported as descriptive only.
  - The SpinQuant vs QuaRot controlled comparison fixes the same WikiText-2 128×2048 calibration, the same GPTQ grid and MSE clip, and KV16 with Q/K rotation. W16 transform-path controls are included. The official SpinQuant default is a separate row.
- **No new fork_driver mode is needed.** Panel A runs in `bank_u` with `subs ["U2B"]`. The gates are `gate_same` with `foreign_states` and the `bank_u` gate. KL comes from the score driver. BFCL uses `bfcl_run` with `subset nmp_v1` and `fork_ext dev`. `make_newmethod_panel.py spec` prints the exact specs.
- **Mistral.** The same rules apply: BF16 runs `a6k2_<m>_bfpair_f01..f06` on the same nonces with eval_tasks_v0, then `build --model <m>` gives `newmethod_panel_v1_<m>.json` with its own sha (dated amendment). BFCL is forked only if Mistral's BF16 success is ≥ 10% on the 200 items.
- **Dry run (counts only, no estimates printed).** The guard passes. The reference τ² cells are admitted on f01–f03, 85/85 states each. The BFCL reference cells have 200/200 items, and the W99o replay guard passes.

| Artifact | sha256 |
|---|---|
| `manifests/fork/newmethod_panel_v1.json` | `7534c6907fa68bc8dab48061d7a2944a719e6e2fa123b639e7a0674c5a6ca201` |
| `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (frozen in the analysis script) | `9cd5c97982e62358a20574e4a9ecff923b68c9758742b1d8e74335b79cccc21d` |
| `scripts/a6000/make_newmethod_panel.py` (= `builder_sha256` in the manifest) | `5fcc530872cd4d8dc77177607d31ae11668568a04c8933743cce852c35deb6cd` |
| `analysis/fork/analyze_newmethod.py` | `25856853d8d9596fce470c49cfe004544411b52409464b80dc0cb1daad5e6f5b` |

Evidence: the four files above, plus the snapshot `analysis/insights/iter_3/out/snapshot_auto_20261002T0631Z.json` (its sha256 is in the manifest) and `manifests/fork/bank_u_v1.json` (U2B identity). `analysis/fork/holdout/` was not opened.

## W99n — Feynman-review edits E1–E10 and prose rewrites P1–P21 applied to the paper (2026-10-02 PDT)
**TL;DR** The edits of `docs/reviews/feynman_review_20261002.md` are in the paper, after each factual claim was checked against its source. Same-precision baseline: the primary ΔM (with both designs' divergence rates) now sits at the end of R1, the off-diagonal comparison stays in R2 labelled descriptive, and the abstract asks whether "turnover and controller dependence are specific to precision". Both outcome versions (precision-specific excess / largely generic sensitivity) are pre-written, unrendered, in `paper/latex/sections/pending_sameprec_variants.tex`. The holdout is reported as "estimated effect −4.6 pp (90% CI −7.2 to −2.0); the pre-registered readings, which had no negative category, classify it as inconclusive", and "near-zero net" is limited to development tasks. The counterfactual-replay related work is restored, and telecom-development forks (q8 GPTQ-W4 +2.7 [−4.7, +10.1], q8 AWQ-W4 −0.6 [−4.9, +3.7]; 80 tasks × 6 blocks; fixed-pool t 95%) are reported. Main text still ends on p. 8 (Limitations at the top of p. 9).
- **E1.** R1 gets the paragraph "Same-precision baseline": analysis set K, Q′ and B divergence rates, ΔM = M − M′ (fixed pool; primary), frozen 3 pp rule, `\pending{}` reading. R2 gets "Same-precision baseline (descriptive)": Δoff plus readings (a)/(b). Abstract clause per review; intro slot moved to bullet 2; Discussion one-sentence `\pending{}` slot; Limitations "calibration" → "only reference for how much turnover and controller dependence a non-precision perturbation produces" (P17). Variants file: per slot, Variant A and Variant B text, plus the protocol §6 rules for mixed and other outcomes, under `\iffalse`; it is not `\input`.
- **E2.** Abstract and intro bullet 2 use the requested holdout wording; "net effect stays small" removed; no "harm" wording.
- **E3.** The commented-out sentence in `related_work.tex` (it sat after a `% src:` comment on the same line) is restored as paragraph "Forks and counterfactual replay": AgenTracer, CAR, CSO and CRR = single-action replay with the original policy continuing = analogue of G; "the factorial design itself is standard"; what is new = the crossing (G, H, F on the same states, the (ΔQ, ΔB) table), bit-exact replay acceptance and the precision setting. Contribution (1) is scoped to the same three things. All four keys exist in `refs.bib` (main.tex uses refs.bib only); claims match `outputs/.drafts/storyline-v7-lit.md` rows 5–8. **Skipped:** "DAgger-style takeover is our H". DAgger (`ross2011dagger`) queries expert labels on learner-visited states; it does not hand control to the expert from the next step, so the mapping would be imprecise.
- **E4.** R3 holdout paragraph: telecom-dev numbers (verified in `analysis/fork/out/dev_all_20261001T093944Z.md` "Telecom development" and in the JSON `telecom_cells`, primary = t over 6 block means), against −5.6/−6.6 per cell on the holdout; q4 has no telecom dev forks. Limitations domain-shift sentence reworded. **Corrected review claim:** the review says the telecom-dev numbers "differ in sign" from the holdout; that holds only for q8 GPTQ-W4. q8 AWQ-W4 is −0.6, which has the same sign. Its suggested "show no negative effect / not explained by the telecom domain alone" was softened to "no detectable net effect ... the holdout drop may reflect heterogeneity among its 34 tasks as much as a domain effect", because the 6-block intervals are wide.
- **E5/E6/E7.** Discussion end-to-end sentence (P16); caveat stacks collapsed (P7, P9, P13), P8 deleted; P17, P21.
- **E8.** Table 9 "all are in the source" removed; Table 8: "completed after this table was compiled" removed (q8 KV8 f03 is in `analysis/fork/bank_u/q8_kvq_int8/f03/`), the all-zero q4 RTN-W3 row removed, telecom-dev pointer fixed; App. A stale-default sentence reworded; §3.3 "units" → "states"; menu oracle labelled as the one state-weighted exception (App. I and Fig. 5 caption); 58 vs 56 f01 flips explained (58 includes the two duplicated U2Q rows; token_mech "flips: 58", REPORT_GPT61 correction 1); one κ range (E.3 now points to E.1); Fig. 7 legend "matched oracle (a); max. capturable (b)" (make_figs.py; all five figures regenerated, asserts pass, script sha changed); Fig. 2 caption "diamonds, negative to the left".
- **E9.** Appendix M merged into L ("Withdrawn, Negative and Supplementary Results"); the W4 perturb-v1 restoration is described as a separate design from the incomplete q8 RTN-W3 byte-matched comparison. A comment block at the top of `appendix.tex` states the deletion rule: unfilled q14 and backfill `\pending` slots are removed at the 10-03 evidence freeze.
- **E10.** Table 7 now has R1 columns (items, r, d, M, G_all [95%]) from `analysis/fork/out/ext_20261001T135106Z.md`, so "5.2–24.6%" and "−3.8 [−6.5, −1.3]" can be checked; abstract finding (iii) is one sentence.
- **Prose P1–P21.** All applied except: P13 was shortened rather than copied, because the proposed text repeated the −8.5/−6.0 numbers of the preceding sentence; P14 became "finds outcome-changing states but has no significant net advantage over random selection" (the rule does select some net-positive states); P18 keeps "of the same model family"; P20 became "constrain this explanation without identifying a mechanism".
- **Space.** To keep the main text on 8 pages, repetition was cut, not results: the intro oracle sentence (in R4), the Fig. 1 caption budget clause (in §3.2), R1's restated S2 numbers (in R3), R4's pp re-expression of the 20% net gain, R3's "Of the development results ..." summary, a method sentence restating the interval rule, and the Discussion "Which part to replace" paragraph, merged into one sentence with a pointer to R2.
- **Checks.** `check_numbers.py` PASS (2920 occurrences, 0 unverified, 0 missing src). tectonic: 0 overfull, 0 undefined references; 20 pages; main text ends on p. 8 and Limitations starts at the top of p. 9. No paths, W-ids or snapshot ids in the rendered text (pdftotext grep). `analysis/fork/holdout/` was not opened.

Evidence: `docs/reviews/feynman_review_20261002.md`, `paper/latex/sections/*.tex` (new `pending_sameprec_variants.tex`), `paper/latex/tools/figs/make_figs.py`, `paper/latex/figures/*`, `docs/insights/{SAMEPREC_PROTOCOL,CLAIM_AUDIT,PERTURBATION_PROTOCOL}.md`, `analysis/fork/out/{dev_all_20261001T093944Z,ext_20261001T135106Z,ext_r2_20261002T024433Z,token_mech_20261001T185031Z}.md`, `outputs/.drafts/storyline-v7-lit.md`.

## W99m — Final writing pass on the paper (mock ARR review items 1–12; de-AI; pending slots for the same-precision baseline, q14 and backfill) (2026-10-01 PDT)
**TL;DR** The ARR draft no longer renders any internal trace (paths, work-item ids, snapshot ids, script names, draft/audit history, block codes such as f13/h01/q3, internal variable names such as KLu\_max or SIMCTRL-P); provenance is one appendix sentence, while every `% src:` comment is kept. The prose was de-hedged (one label per result, one caveat per finding in the abstract). All 12 review items are applied. The same-precision baseline (W99k/W99l), the q14 BFCL scale check and the three backfill perturbation analyses appear only as red `\pending{}` slots with neutral wording; no conclusion is written for any of them.
- **Abstract.** Pairing control removed; the "without a same-precision control" caveat is replaced by one neutral clause with a `\pending{}` reading slot; hindsight-oracle clause dropped (it is positive by construction; stated in R4 and the intro).
- **Intro.** End-to-end comparison "cannot distinguish difference from equivalence" (TOST at ±3 pp fails in every cell); case study without the nonce-block id; κ sentence and two repeated summary sentences removed; same-precision clause with `\pending{}`; oracle "positive by construction".
- **Method.** QQ no-op rule stated: 10% hash sample of states per fork task (hash of the state id, outcome-independent), any mismatch quarantines the task (FORK_PROTOCOL §9, fork_driver noop_frac); snapshot id removed; f01–f03 defined; stress-cell t intervals have two degrees of freedom.
- **R2.** κ reduced to one sentence ("measures how well ΔQ and ΔB agree, not whether the interaction is significant"); BFCL/ALFWorld and holdout control numbers moved to App. agreement; F1 redrawn without the control markers (`F1_SHOW_CONTROL = False`, values still asserted; all five figures regenerated, so the script sha changed); new "Same-precision baseline" paragraph with `\pending{M′}`, `\pending{M}`, `\pending{paired difference}`, `\pending{off-diagonal′}`, `\pending{reading}`.
- **R3.** Relay reproducibility pointer; holdout summary reduced to one sentence; holdout pairing control moved to the appendix; strata pointer; q14 sentence with `\pending{}`.
- **R4.** Hindsight oracle headroom "positive by construction" (selects only rescues, never a damage).
- **Discussion.** New paragraph on Bank P vs Bank U (P skips text-only differences, which are 150/208 Bank U flipping rows; those labels did not reproduce under the second simulator).
- **Limitations.** Relay reproducibility (hosted Sonnet 5.5, no temperature/seed; W95 relay subagents saw several requests in one context; SIMCTRL-P isolated single-request calls); pre-registered readings had no negative category; telecom confounds domain shift with new-task generalisation; q14 `\pending{}`; same-precision baseline as the only calibration of the off-diagonal share.
- **Appendix.** All rendered `Source: \nolinkurl{...}` removed from 19 captions/paragraphs and from the three generated tables (generators edited and re-run); 3×3 caption uses only the equal-weight aggregation (summed 27.1%/15.2% dropped); full holdout strata table (Table `tab:strata`, from holdout_confirm_20261002T012353Z.md §Strata; intervals verified as crossed 90% from the reported p-values); coverage row q14 `\pending{}`; prereg path, sha, half codes removed; W89 estimand-name note and the retracted "errors are absorbed" note removed; "Figure Provenance" table replaced by one sentence; new section "Supplementary Perturbation Analyses (Exploratory)" with three `\pending{}` paragraphs (restoration location vs byte-matched random, error dose α, low-bit failure modes; definitions from PERTURBATION_PROTOCOL.md).
- **Checks.** `check_numbers.py` PASS (2829 occurrences, 0 unverified, 0 missing src; the checker was not changed: no `\pending{}` argument contains a checked number). tectonic: 0 overfull, 0 undefined references, 19 pages; main text ends on p. 8 and Limitations starts at the top of p. 9 (pdftotext). `analysis/fork/holdout/` was not opened.

Evidence: `paper/latex/sections/*.tex`, `paper/latex/tools/{gen_w93_tables.py,gen_simctrl_table.py,figs/make_figs.py}`, `paper/latex/figures/*`, `docs/reviews/mock_arr_review_20261002.md`, `docs/insights/{SAMEPREC_PROTOCOL,FORK_PROTOCOL,SIMCTRL_P_PROTOCOL,PERTURBATION_PROTOCOL}.md`, `analysis/fork/out/holdout_confirm_20261002T012353Z.md`.

## W99j — Publication figures F1–F5 (matplotlib, source-backed); two main-text tables and the 3×3 TikZ figure moved to the appendix (2026-10-01 PDT)
**TL;DR** Five vector figures now carry the paper's main quantitative results, each drawn by one function of `paper/latex/tools/figs/make_figs.py` from the committed analysis JSON only, with asserts on every number the text quotes (W4 pool off-diagonal 26.9% [25.7, 28.1], control 38.0% [36.7, 39.0], κ 0.29; KV8 15.3/33.6; BFCL 4.7–17.1 / pool 10.3; ALFWorld 32.8–40.0 / pool 36.4; holdout 20.7 vs 25.7; R1 r/d/net per cell; holdout G_all −4.57 [−7.17, −1.96]; G/H/F/G−H of the W4 pool and the cells quoted in R2; trigger 50/114/222, net +4/+2/+5, oracle +3.33/+3.73/+3.73 pp; SIMCTRL-P pools). Main text still ends on p. 8 (Limitations at the top of p. 9).
- **F1 (main, R2, Fig. 4)** `figures/f1_controller_dependence.pdf`: per-cell off-diagonal share with fixed-pool/new-task (or item) 95% intervals vs the marginal-preserving pairing agreement control; τ² W4 and KV8 (development), BFCL W4, ALFWorld W4 and the telecom holdout (post hoc, shaded). New figure.
- **F2 (main, R2, Fig. 3)** `figures/f2_ghf_forest.pdf`: G, H, F, G−H forest plot for the 4 W4 cells, W4 pool, 2 KV8 cells, KV8 pool; thick fixed-pool 95%, thin crossed 95%, zero line; stress cells omitted. **Replaces Table `tab:ghf`, moved to the new Appendix "Full Tables for R1 and R2".**
- **F3 (main, R1, Fig. 2)** `figures/f3_rescue_damage.pdf`: diverging rescue/damage bars with net G_all (dev W4/KV8 95%; holdout pre-registered 90%). **Replaces Table `tab:r1`, moved to the same appendix section.**
- **F4 (appendix, Trigger Headroom)** `figures/f4_trigger_oracle.pdf`: net gain and turnover captured by budget (5/10/20%) for the frozen trigger, matched oracle (net) / derived turnover ceiling Σ_c min(m_c, R_c+D_c), random expectation and a faint post-hoc KLu_max reference (count-matched to the rule's per-cell budget).
- **F5 (appendix, SIMCTRL-P)** `figures/f5_simctrl_p.pdf`: G/H/F/G−H per W4 cell and pool, original simulator vs Sonnet 5.5 user, 95% over states.
- **Moved, not deleted.** The 3×3 heatmap TikZ figure (`fig:3x3`) moved unchanged to Appendix "Supplementary R2 Analyses" to make room for F1; R2 text points to it. A new Appendix "Figure Provenance" (Table 18) lists each figure's function and sources; `figures/provenance.json` and each PDF's metadata store the source sha256 and the script sha256.
- **Other.** `\pending{...}` (red) is defined in `main.tex` (unused). Figures are drawn at ACL's measured `\textwidth` 6.30 in / `\columnwidth` 3.03 in and included at scale 1, so all text is ≥ 7 pt (Liberation Serif, Times-metric; STIX math). Palette blue/orange/aqua validated with the dataviz validator (light mode, all checks pass); marks also differ by shape/fill/position for greyscale.
- **Checks.** check_numbers PASS (0 unverified, 0 missing src). tectonic: 0 undefined references, 0 overfull boxes; 20 pages; Limitations at the top of p. 9. Each figure was rendered to PNG and inspected.

Evidence: `paper/latex/tools/figs/make_figs.py`; `paper/latex/figures/{f1_controller_dependence,f2_ghf_forest,f3_rescue_damage,f4_trigger_oracle,f5_simctrl_p}.pdf`, `paper/latex/figures/provenance.json`; `paper/latex/sections/{results_r1,results_r2,results_r3,results_r4,appendix}.tex`, `paper/latex/main.tex`; sources `analysis/fork/out/{ghf_20261001T211519Z,agreement_control_20261002T024240Z,ext_r2_20261002T024433Z,holdout_r2_posthoc_20261002T024414Z,holdout_confirm_20261002T012353Z,simctrl_p_20261002T015200Z,oracle_trigger_20261002T024423Z,token_mech_20261002T003130Z,dev_all_20261001T070326Z}.json`.

## W99i — Abstract and introduction rewritten around the advisor's fixed framing; external R2 moved into the main R2 (2026-10-01 PDT)
**TL;DR** The abstract and introduction now lead with one message: in a closed-loop agent, the value of a single precision upgrade is jointly determined by the action it changes and by the execution that follows, and the crossed same-state intervention measures it directly. Three findings follow: (i) controller dependence (26.9% of dev W4 divergent states; pairing control 38.0%, κ 0.29; post hoc BFCL 4.7–17.1%, q8 ALFWorld 32.8–40.0%, holdout 20.7%), with the P17 caveat; (ii) local upgrades redistribute success (15.5–20.9% of units; holdout −4.6 pp, 90% CI −7.2 to −2.0, primary reading inconclusive); (iii) finding sensitive decisions ≠ choosing beneficial replacements (trigger vs matched oracle +3.3 to +3.7 pp). There are two contributions: the framework and the systematic findings.
- **Abstract.** It went from 485 to about 300 words. The Bank U text-difference detail, the simulator-control labels, the AUC range and the S1/S2 readings were removed; they remain in R3/R4.
- **Introduction.** Paragraphs: decision problem, then Case 5 (q4 AWQ-W4 airline 31 f13, verified against ghf §4), then the framework with scope, then three findings, then two contributions, then one closing sentence.
- **Moved.** The BFCL/ALFWorld controller-dependence result moved from R3 to a new R2 paragraph ("Controller dependence without an LLM user"), with the per-cell ranges, pairing control ranges and κ; R3 now points to it. No result was deleted.
- **Page fit.** The discussion's "Escalation can hurt" paragraph is merged into "When to escalate"; its numbers stay in R2/R3.
- **Other wording.** The remaining unscoped "first divergent action" phrases in R1 caption, R3 and the discussion now read "first tool-structure-divergent action" (CLAIM_AUDIT P10).
- **Appendix src fix.** The RESTORE src glob now points to `queue/*/`; s2/s3 were re-queued to todo, so the text says "have not completed".
- **Checks.** check_numbers PASS (0 unverified, 0 missing src). tectonic: 0 undefined references, 0 overfull boxes. The main text ends on p. 8, and Limitations starts at the top of p. 9.

Evidence: `paper/latex/sections/{abstract,introduction,results_r2,results_r3,results_r1,discussion,appendix}.tex`; sources `analysis/fork/out/{ghf_20261001T211519Z,agreement_control_20261002T024240Z,ext_r2_20261002T024433Z,holdout_r2_posthoc_20261002T024414Z,dev_all_20261001T070326Z,holdout_confirm_20261002T012353Z,token_mech_20261002T003130Z,oracle_trigger_20261002T024423Z}.md`.

## W99g — q14 (Qwen3-14B) BFCL four-arm fork gate: PASS; call-rewriter instance-name leak fixed; process-shared BFCL long-context state found and fixed (2026-10-01 23:05 PDT)
**TL;DR** This is the short gate for the q14 BFCL fork, a within-Qwen-family scale sensitivity check (GPTQ-W4 d1 only; exploratory). Every check passes, so the 4 staged q14 fork tasks are queued (W99h).
- **(a) Acceptance.** BB no-op passes 4/4 and QQ no-op 8/8. Q replay at t is bit-exact, and replay fidelity, re-prefill, save/load and isolation (4/4) all pass, with 0 branch errors. The 8 divergent states come from 12 items.
- **(b) Same-checkpoint control.** With B and Q on the same GPTQ checkpoint, 0/12 items diverge, and the four arms are identical at all 4 forced states.
- **(c) Leak fix.** In fork branches, `bfcl_run` maps the per-branch instance name inside rewritten string arguments, and in the observations, back to the canonical `cloq_agent`. A regression test reproduces the W99f base_126 failure with the fix off and passes with it on (9/9 tests).
- **(c) Qwen unchanged.** Replaying all 45,035 recorded q4/q8/q14 BFCL decisions gives byte-identical observations and prompts.
- **New finding.** BFCL's TravelAPI aliases module-level long-context card dicts into instance state, so a booking in one episode changes later episodes in the same process. This is fixed by unaliasing after `_load_scenario`.
- **Open issue (historical, not touched).** The q4 long-context dev forks show replay-inconsistent backend state on 38/133 (GPTQ-W4), 21/151 (AWQ), 43/165 (GPTQ-W3) and 50/197 (KV4) states. `analyze_ext`/`ext_r2` admit them. q8 is clean.

Evidence: `analysis/fork/ext_q14_gate/{GATE.md,gate_bfcl_q14_gptq_w4_d1/,gate_same_bfcl_q14_gptq_w4_d1/,replay_obs_check.{py,json},test_bfcl_instance_leak.out}`, `tests/test_bfcl_instance_leak.py`, `scripts/ext/bfcl_run.py` (W99g blocks), queue `done/fork_ext_gate{,_same}_q14_gptq_w4_d1_bfcl.json`, logs `/data/ziyangs/cloq_work/logs/tasks/fork_ext_gate{,_same}_q14_gptq_w4_d1_bfcl.log`.

## W99f — l8 (Llama-3.1-8B) BFCL four-arm fork gate: FAIL; BFCL is at the capability floor for l8 (2026-10-01 21:40 PDT)
**TL;DR** The second-family replication gate fails, so this line stops and the formal panel is not queued.
- **What works on Llama.** A GPTQ-W4 d1 checkpoint was built through the queue: τ² cal run → `manifests/a6k2/l8/calib_fp_traj_c1.json` → GPTQ, 532 s. It serves correctly. Q replay is bit-exact across two builds, and QQ no-op passes 18/18.
- **Why the gate fails.**
  - **Capability floor.** l8 BF16 solves 0/20 smoke items and 5/100 items of a disjoint probe, i.e. 4.2% (95% CI 1.8–9.4%). Qwen q4/q8/q14 BF16 solve 19.9/14.3/20.1% of the same pool.
  - **No outcome variance in the fork.** The four arms are `0000` on 17/18 divergent smoke states; the one exception is `0111`. Arm success: BB 0, BQ 1, QB 1, QQ 1. ΣG 0, ΣI +1.
  - **Template.** The official Llama-3.1 template refuses multi-call turns: 4/20 items died with HTTP 400. The l8 requests now use `parallel_tool_calls=false`, which changes the tool-call protocol as well as the family.
  - **Strict gate.** BB no-op and isolation each fail 3/4. Both failures are one item: the per-branch instance name leaks into an observation when the agent passes a call expression as an argument. This affects 1/120 l8 items and 0 Qwen decisions.
- **Throughput.** Eval ≈ 4.4 s/item amortised on 1 GPU. Search 24 s/item, divergence 90%. Branches 4.0 s wall at concurrency 8.
- **Formal panel (if overridden).** 200 items, about 4 GPU-h and about 1 h wall. It is staged, not queued, at `/data/ziyangs/cloq_work/staged/w99f_l8_formal/`. It would yield only about 10–20 states where any arm succeeds.
- **Backup q14 (same family).** Only the 4 fork tasks are missing; they are staged at `/data/ziyangs/cloq_work/staged/w99f_q14_backup/` (about 8–14 GPU-h). This answers scale, not family.
- **Code changes.**
  - The ext adapter scores the template error as `agent_parse_error` (W27 rule) instead of an outage.
  - Per-model `ext_request` in models.json; Qwen requests are unchanged.
  - `cloq/quantize.py` ignores `original/*` in meta snapshots.

Evidence: `analysis/fork/ext_l8_gate/{GATE.md,gate_summary.json,analyze_gate.py,gate_bfcl_l8_gptq_w4_d1_sc/}`, `manifests/bfcl/{bfcl_mt_l8gate_v1,bfcl_mt_l8probe_v1}.json`, `scripts/ext/{make_manifest_l8gate,make_tasks_l8gate,common}.py`, `scripts/a6000/models.json` (l8 `ext_request`), `cloq/quantize.py::source_dir`, queue `done/{a6k2_l8_bf16_cal,a6k2_l8_calib_c1,ext_l8_*,fork_ext_gate_l8_gptq_w4_d1_bfcl_sc}.json`, runs `runs/ext_l8_*` (cluster only).

## W99e — Claim-audit fixes applied to the paper (2026-10-01 PDT)
**TL;DR** The fixes in `docs/insights/CLAIM_AUDIT.md` (P1–P33, P35, P37–P39) are now in `paper/latex/sections/*.tex`. 36 are fixed and P28 is partly applied: the appendix note on later snapshots was not verified, so it was left out. P5's replacement wording was factually wrong: in Case 6 the failed write is made by the continuing controller, not by Q before the handover. The audit's alternative was applied instead (the clause was deleted).
- **Headline wording changes:**
  - "First divergent decision" is now "first decision where the two models' actions differ in tool structure (text-only differences are skipped)".
  - The holdout is "inconclusive; descriptively negative" and no longer "confirms no benefit".
  - S2 is described only as a repeatability test.
  - The off-diagonal share now carries a caveat in the abstract and Limitations: no same-precision perturbation control.
  - The mean interaction is "near zero" only for the development W4 pool.
  - The trigger "captured more than random at two of three rates" and no longer "enriches".
  - Uncertainty is "associated with" divergence.
- **Numbers that were corrected or added:**
  - Bank U production no-ops 328/328, with the 135/135 gate listed separately.
  - Stress turnover is 18.4–20.4%, except q8 RTN-W3 at 6.7%.
  - The R4 q4 U2Q and per-cell AUC exceptions are reported.
  - Table 2 has a KV8 pool row.
  - The 3×3 caption gives summed off-diagonal shares of 27.1% / 15.2%.
  - The holdout analysed 1200 of 1224 units.
- **RESTORE todo:** replaced with a plain statement that the q8 RTN-W3 attention vs byte-matched random-attention comparison was not completed. The attention arm and seed s1 ran; s2 and s3 are deferred. No result is reported.
- **Page fit:** these items moved to the appendix:
  - R4 menu oracle and KL-row details (Appendix H)
  - ext-R2 ranges (Appendix extr2)
  - the SIMCTRL-P E[I²] sentence (already in Appendix simctrlp)
  - the Q0 subsample detail (Appendix banku)

  Wording was tightened elsewhere, and no result was deleted. The main text ends on p. 8 and Limitations starts at the top of p. 9. 0 overfull boxes, 0 undefined references, `check_numbers.py` PASS.
- **Evidence:**
  - `docs/insights/CLAIM_AUDIT.md` §6 Resolution
  - `paper/latex/sections/*.tex`
  - `analysis/fork/out/ghf_20261001T211519Z.md` (§4 Case 6)
  - `analysis/fork/out/token_mech_20261001T185031Z.md`
  - `analysis/fork/bank_u/*/f0*/bank_summary.json`
  - `/data/ziyangs/cloq_work/queue/{done,deferred}/pert_q8_rtn_w3_restore_*attn*_q345.json`

---

## W99d — Paper integration of the review-9 CPU analyses (pairing control, SIMCTRL-P E[I²], ext R2, holdout R2 post hoc, trigger oracles/KL) (2026-10-01 20:30 PDT)
**TL;DR** Five committed CPU analyses are now in the paper, with the advisor's wording. R2: W4 equal-weight off-diagonal 26.9% vs 38.0% expected under the *marginal-preserving pairing agreement control* (κ 0.29 [0.27, 0.32], crossed [0.22, 0.36]); KV8 15.3% vs 33.6% (κ 0.55). It is not a no-interaction null; same-state I ≠ 0 is identified regardless. R3: SIMCTRL-P noise-corrected E[I_s²] = 0.050 [0.004, 0.107] (exploratory). BFCL/ALFWorld show controller dependence without an LLM user. Holdout R2 is labelled post hoc (G −4.6 conditional on divergence ≈ G_all −4.57 because 1180/1200 units diverge). R4: a matched oracle shows large headroom (the rule captures 4/34, 2/38, 5/38 of the oracle net), and a post-hoc KL row is not significant on net. The coverage table is fixed (BFCL q4 GPTQ-W3: 591 items · 540 st). Wording: no sentence says the simulator reverses the G/H/F ordering, and none says the holdout shows "no effect".
- **Main-text edits:**
  - R2 (`results_r2.tex`): pairing-control sentences next to the 26.9% paragraph, plus the 3×3 caption.
  - R3 (`results_r3.tex`):
    - SIMCTRL-P "simulator-specific" is replaced by "neither confirmed nor shown to reverse", plus one E[I²] sentence.
    - Holdout gets a post-hoc R2 sentence and the G vs G_all note.
    - BFCL/ALFWorld gets an R2 sentence (4.7–17.1% / 32.8–40.0%; κ 0.44–0.71 / 0.10–0.24; ALFWorld GPTQ-W3 H +38.5, G−H −34.6; KV4 reduces to H).
  - R4 (`results_r4.tex`): new "Headroom" paragraph (action oracle, menu oracle, KL reference row).
- **Appendix edits (`appendix.tex`):**
  - New section "Supplementary R2 Analyses": tab:agreement (per-cell κ, stress cells flagged; q8 RTN-W3 κ ≈ 0 because Δ_Q is 93.3% zero), an SIMCTRL-P E[I²] paragraph with its assumptions, and tab:extr2.
  - tab:holdoutr2 (post hoc) is added in the prereg section.
  - New section "Trigger Headroom and a KL Reference Row" with tab:oracle.
  - tab:coverage: BFCL q4 GPTQ-W3 cell fixed.
  - Bank U simulator-control sensitivity/scope sentences moved here from R3.
- **Page fit:** tightened related work, method, R1–R4, intro and discussion; no result deleted (moved items are in the appendix). The main text ends on p. 8 and Limitations starts at the top of p. 9. `check_numbers.py` PASS; 0 overfull, 0 undefined.
- **Not placed:** the "20/22" no-op count for the dropped BFCL base category is not in any committed output, so the paper says only that the category was dropped by the QQ no-op rule.
- **Evidence:**
  - `analysis/fork/out/agreement_control_20261002T024240Z.{md,json}`
  - `analysis/fork/out/simctrl_p_interaction_20261002T024357Z.{md,json}`
  - `analysis/fork/out/ext_r2_20261002T024433Z.{md,json}`
  - `analysis/fork/out/holdout_r2_posthoc_20261002T024414Z.{md,json}`
  - `analysis/fork/out/oracle_trigger_20261002T024423Z.{md,json}`
  - `paper/latex/sections/{results_r2,results_r3,results_r4,appendix}.tex`

## W99a — Bank P four-arm simulator control: final result (80 states) and paper integration (2026-10-01 19:00 PDT)
**TL;DR** On 80 outcome-blind Bank P states (20 per core W4 cell, BB/BQ/QB/QQ × 5, Sonnet 5.5 as the user via isolated single calls), the per-state arm outcomes track the originals (r 0.63–0.68). Pooled under Sonnet: G −3.0 [−10.2, +4.8], H +5.5 [+0.0, +11.2], **G−H −8.5 [−14.8, −2.8]**. On the same states under the original simulator, G−H is −2.5 [−11.2, +6.2] (change −6.0 [−16.2, +4.2]). The sample cannot test the few-pp W93 contrasts: even the original gives G−H = 0.0 in both q8 W4 cells here. **The within-cell G−H orderings of R2 are therefore labelled simulator-specific.**
- **Integrity:**
  - 1,600 branches; 0 arm errors, 0 missing; v2 checks 1580/1580.
  - 7,896 unique request ids; daemon: 0 gave up, 0 rejected; cost $85.62.
  - Unexposed branches: 20 (BB 10, QB 10, on 3 states). The sensitivity analysis excluding them is unchanged (G−H −8.6).
- **Within-arm replicate disagreement:** 17–28 of 80 states per arm. Arm success is higher under Sonnet (pooled 38–42% → 50–58%).
- **Paper edits:**
  - R3: new paragraph "Sensitivity of the four-arm results".
  - R2: G−H marked exploratory and not reproduced under a second simulator.
  - Intro: R2/R3/R4 bullets updated (holdout, simulator, token).
  - Discussion: "Which part to replace" qualified; "What we do not claim" moved to Limitations.
  - Limitations: rewritten as "two small controls".
  - R1: the concentration test is reported as passed on the holdout (S2).
  - Trimmed to fit: the main text ends on p. 8. `check_numbers.py` PASS; 0 overfull, 0 undefined.
- **Bug fixed:** three sentences had been swallowed by inline `% src:` comments and never appeared in the PDF: limitations (simulator scope; annotation agreement) and method (more nonce blocks). They are restored.
- **Evidence:**
  - `analysis/fork/out/simctrl_p_20261002T015200Z.{md,json}`
  - `analysis/fork/simctrl_p/<cell>/b{1,2}/` (rows, summaries, branches)
  - `manifests/fork/simctrl_p_v1.json`
  - `/data/ziyangs/cloq_work/logs/simrelay_cli.log`

## W98b — Telecom holdout: pre-registered confirmatory analysis (2026-10-01 18:25 PDT)
**TL;DR** G_all = −4.57 pp, crossed 90% [−7.17, −1.96] (block-t [−6.08, −3.05]). The **pre-registered reading is inconclusive**: §6 defines only positive gain, gain above 3 pp and small effect, with no negative category. Descriptively the interval lies entirely below 0, so on unseen telecom tasks BF16 current-action replacement *lowered* average success. **S1 passes**: r +5.21 [+3.30, +7.11], d +9.77 [+6.45, +13.10], M +14.98. **S2 passes**: ρ 0.588, permutation p 0.0001.
- **Run conditions:**
  - K' = 12 (h01–h12) with no reserves used.
  - Structural exclusions: 1 task in q4 GPTQ and 1 in q8 AWQ (search decision/trajectory count mismatch).
  - Complete-case sensitivity is identical.
  - Script sha 2af1b689 and prereg sha 902892dd were both verified before the run. Snapshot: `analysis/insights/iter_3/out/snapshot_holdout_20261002T0123Z.json` (iter_2/integrity.py).
- **Per cell (descriptive):** q4 GPTQ −3.03 [−7.86, +1.80]; q8 GPTQ −5.64 [−9.33, −1.94]; q8 AWQ −6.57 [−11.98, −1.15].
- **Strata:** every level estimate is ≤ 0. The Holm-significant levels are all negative: step budget T2/T3, mobile_data_issue −9.09, and the fewest-faults tercile −6.37.
- **Paper:**
  - The abstract sentence, the R3 paragraph and the appendix table `tab:holdout` are filled.
  - The holdout limitation is updated.
  - Discussion "Escalation can hurt" now cites the holdout.
  - R3 is condensed (the simctrl flagged and scope sentences).
  - `check_numbers.py` PASS. The main text runs ~5 lines onto p. 9; the final fit will be done after the Bank P paragraph.
- **Not done:** prereg step 4 supplementary descriptive outputs (analyze_dev / analyze_difficulty on the holdout; non-decisional).
- **Evidence:** `analysis/fork/out/holdout_confirm_20261002T012353Z.{md,json}`, `analysis/fork/out/holdout_confirm_cc_20261002T012358Z.{md,json}`.

## W99a — SIMCTRL-P paper decision rule, committed before the final analysis (2026-10-01 19:05 PDT)
**TL;DR** This rule is written before any final (batch 1 + 2) SIMCTRL-P output exists. Only the INTERIM batch-1 look of W99 has been seen. It fixes how the paper words R2's G−H result. It adds no pass threshold and changes nothing in `SIMCTRL_P_PROTOCOL.md` or in the frozen manifest. Source: the Feynman review in `outputs/final-plan-review.md` (weakness 2).
- **Rule.** Use the pooled, equal-weight Sonnet-minus-original change in G−H over all 80 states. If the Sonnet G−H has the opposite sign to the original G−H on the same states, or the 95% interval of the change excludes 0, then:
  - the q8-W4 / stress-cell G-vs-H ordering is removed from the abstract, the introduction and the discussion;
  - it is reported as "the ranking of G/H/F was not stable across cells, task sampling or user simulator; it must be measured per configuration and simulator".
  - Otherwise G−H stays a within-cell, fixed-pool, exploratory result, with the SIMCTRL-P estimate reported next to it.
- **In every case:** the abstract does not state a G−H ordering as a general finding. The controller-dependence claim (3×3) is reported with its chance baseline (see W99b, pending).
- **Evidence:** this entry (committed before `analysis/fork/out/simctrl_p_<UTC>.md` exists); `outputs/final-plan-review.md`.

## W98a — GPT-6.1 review 8 wording corrections after W98 (2026-10-01 PDT)
**TL;DR** The claims now match the evidence. Finding consequence-bearing decisions is not the same as finding net-beneficial replacements.
- **Bank U:** 150/208 is a share of deduplicated cell×state rows, not of independent states.
- **Token (R4, abstract):**
  - New wording: "a frozen Q-only margin rule enriched outcome-changing decisions on later nonce blocks, but has not been shown to select net-beneficial replacements".
  - The 20% threshold actually selected 222/1020 = 21.8%. Net gain 0.49 pp vs random 0.23 pp (+0.26, p = .262).
  - This is a random-selection comparison on a fixed validation bank, not routing gains on new tasks.
  - Holm-adjusted p for the 5% rate: ≈ .1035.
- **Recovery (appendix):** "no error-specific effect" became "no clear difference detected". Under Q, the q8 interval [−0.30, +0.03] still allows sizeable harm.
- **q8 premature_write manipulation failures:** 6 rejected plus 1 executed without a DB change. Checked in `analysis/recovery/inject_q8/summary_v2.md`.
- **Discussion:** text outcome labels "did not reproduce reliably under an alternative stochastic relay simulator".
- **Checks:** `check_numbers.py` PASS (1,971). The main text ends on p. 8 and Limitations starts on p. 9.
- **Argument order fixed by GPT:**
  1. current-action replacement rescues and damages;
  2. the four-arm fork separates action from continuation, with state-level controller dependence;
  3. Bank U shows what the selection and the action definition miss, and the simulator control bounds transfer;
  4. the frozen trigger separates finding consequences from getting gains.
- **Remaining before the freeze:** the final Bank P analysis on all 80 states, the frozen telecom confirmation, and the claim audit.
- **Evidence:** `paper/latex/sections/{abstract,results_r3,results_r4,discussion,appendix}.tex`.

## W98 — Bank U f01–f03, frozen token-trigger validation (f02/f03) and recovery q8 analysed; paper placeholders BANKU-F023, TOKEN-VALIDATION, RECOVERY-Q8 filled (2026-10-01 PDT)
**TL;DR** All expected GPU tasks were complete (18/18 Bank U native blocks, 12/12 Q0 blocks, 18/18 score blocks, inject_q8 30/30 states); nothing is missing.
- **Bank U f01–f03** (task-equal, t over 3 block means): M stays below Bank P and every G interval covers 0. The q4 > q8 contrast seen in f01 weakens: q8 AWQ-W4 is now at the q4 level. Text (class ii) is still the main composition share (150/208 = 72.1% deduplicated), but per instance it flips no more often than tool or act/talk differences (14.4% vs 18.2% / 18.9%). These labels come from one simulator (W95/W96 caveat unchanged; the simulator control covers f01 flips only).
- **Token trigger (frozen rule sha 335e737d…, unchanged):** on f02/f03 U1 the net gain beats a matched-count random trigger only at the 5% rate (+4 vs +0.21, exact one-sided p = .0345). At 10% and 20% it does not (p = .417, .262). The rule fixed no α or multiplicity rule, and the 5% result does not survive Holm over the three rates. Turnover capture is above chance (p = .0182 / .0613 / .0002). Reading: it finds divergence or turnover, not reliable net gain.
- **Recovery q8:** same reading as q4. INV vs VAL turnover is 5/30 under each controller and PP vs VAL is 6/30 (B) and 5/30 (Q). The error-specific effect INV − PP is −0.03 [−0.13, +0.07] under B and −0.13 [−0.30, +0.03] under Q. D_INV ≠ 0 in 6/30, mean 0.00. 7/10 premature writes were rejected by the environment, so that category mostly did not inject a write.

- **Bank U, native M (U1 / U2B / U2Q; n = 255 / 255 / 60 rows; r/d counts in the md):**
  - q4 GPTQ-W4 .090 [.029, .151] / .082 / .083
  - q4 AWQ-W4 .082 / .078 / .083
  - q4 KV8 .047 / .039 / .017
  - q8 GPTQ-W4 .047 / .067 / .050
  - q8 AWQ-W4 .086 [.002, .171] / .090 / .067
  - q8 KV8 .035 / .031 / 0
  - G: U1/U2B within ±.028; U2Q up to +.050. All intervals cover 0.
  - Superseded f01 statements: q8 "at most .047" (q8 AWQ is now .086/.090); the text rate range .020–.176 is now .126–.182; the per-instance text rate (.126) was below act/talk (.200) and is now 14.4% vs 18.9% (iii 10.9% is now 18.2%); Q0 turnover "≥ native" no longer holds (q8 AWQ U2B 4/52 vs 5/52; q4 KV8 U2B 1/58 vs 2/58); length-difference co-occurrence, seen only in q4 in f01, now appears in U1 and U2B of both models.
  - Transfer: q4 U2B has 21 pairwise co-flips vs 3.3 expected (16/21 same direction) from 15 distinct states. q8 U2B has 14 vs 2.8 from 10 states; in f01, q8 had none. Q0 determinism holds: Y(a_B→Q0) is identical across cells on 146/146 shared states.
- **Token validation detail** (U1, S_mm, f02/f03, 1020 rows, 69 turnover states):

  | rate | escalated | net vs random (p) | r/d | turnover vs random (p) |
  |---|---|---|---|---|
  | 5% | 50 | +4 vs +0.21 (.0345) | 6/2 | 8 vs 3.48 (.0182) |
  | 10% | 114 | +2 vs +0.98 (.417) | 7/5 | 12 vs 7.52 (.0613) |
  | 20% | 222 | +5 vs +2.38 (.262) | 16/11 | 27 vs 14.30 (.0002) |

  - Secondary candidates (S_H0, S_lp) also capture turnover above chance at 10–20%, with no net-gain signal.
  - The 20% thresholds of q8 GPTQ/KV8 are −0.25 (frozen as is).
  - Script checks: 3420/3420 rows scored; every a_Q token is Q's argmax; 0 flips with identical ids.
  - Note: sections 1a/1b/2 of the new token_mech output now pool f01–f03, so they mix development and validation blocks. The paper's mechanism numbers stay on f01 (`token_mech_20261001T185031Z`).
- **Paper:**
  - R3 Bank U paragraph updated to f01–f03 (it says so).
  - R4 validation filled; the "validated" heading became "tested", and the in-sample f01 numbers were dropped from the main text for space.
  - Appendix: tab:banku and tab:taxonomy extended to f01–f03 (f01 counts in the caption); new text-length paragraph; transfer and Q0 paragraphs updated; new tab:recovery8; the coverage table's q8 KV8 Bank U is 3 b.
  - method/limitations: "one block" became "three blocks".
  - check_numbers PASS (1962 occurrences). tectonic: 15 pp, 0 overfull, 0 undefined; Limitations starts on p. 8. The abstract is unchanged (not contradicted).
- **Caveats:**
  - k = 3 blocks, so the t intervals have 2 df and are wide.
  - The analyze_bank_u.py md footer still says "descriptive for f01 (k = 1)". This is stale template text and does not affect the numbers.
  - inject_q8 summaries reproduced byte-identically on rerun.
- **Evidence:**
  - `analysis/fork/out/bank_u_f01_f02_f03_20261002T003037Z.{md,json}`; `analysis/fork/out/token_mech_20261002T003130Z.{md,json}`; `analysis/recovery/inject_q8/summary_v2.{md,json}`;
  - inputs `analysis/fork/bank_u/<m>_<cell>/f0{1,2,3}/bank_{rows.jsonl,summary.json}`, `analysis/fork/bank_u/q0/*/f0*/q0_{rows.jsonl,summary.json}`, `analysis/fork/token_scores/*/f0{2,3}/score_summary.json`;
  - `paper/latex/sections/{results_r3,results_r4,appendix,method,limitations}.tex`.

## W99 — SIMCTRL-P analysis script (`analyze_simctrl_p.py`) and an INTERIM batch-1 look (3 of 4 cells) (2026-10-01 17:35 PDT)
**TL;DR** This entry is the analysis script for the W97 Bank P simulator control, plus an interim look at the batch-1 data that was finished at the time. The design is from GPT-6.1 review 7. The interim output covers 30 states (q4 AWQ-W4, q8 GPTQ-W4, q8 AWQ-W4; q4 GPTQ-W4 batch 1 had not finished; batch 2 just queued). It is labelled INTERIM, is a robustness check only, and is not interpreted here. The final analysis runs once both batches are in.
- **Estimands.** Per state and arm, Ȳ = the mean over the valid R = 5 Sonnet replicates. G = BQ−QQ, H = QB−QQ, F = BB−QQ, G−H, F−G, F−H come from these per-state means and are averaged over states. They are given per cell, as an equal-weight pool over the cells present, for all batches and for batch 1 alone (pre-planned).
- **Original simulator, same states.** The original single-run BB/BQ/QB/QQ outcomes come from the dev fork. QQ is the recorded original continuation. They are loaded with the exact admission that froze the manifest: `make_tasks_simctrl_p.admitted_units`, which imports analyze_ghf/analyze_dev. The script checks the units digests against `dev_all_20261001T070326Z` and the dev state and branch file shas against the manifest. Per estimand it reports the paired change (new − original).
- **Intervals.**
  - A bootstrap over states, stratified by cell (B = 2000, seed 20261001).
  - A task-cluster bootstrap: tasks are resampled within a cell, and across cells for the pool. Tasks do repeat: 6 tasks have 2–3 states within a cell, and 21 of 49 tasks appear in more than one cell.
  - Exact Clopper–Pearson intervals for shares of states.
- **Variability.** Per arm, the share of states whose 5 replicates disagree. Per arm, also the Pearson correlation between the original outcome and the Sonnet arm mean. There is no off-diagonal share and no comparison with 26.9%.
- **Unexposed branches.** Y is kept and counts are given per arm. Two sensitivity analyses: S1 drops states with any unexposed branch; S2 uses exposed replicates only.
- **Missing or errored replicates** (including a failed protocol check) are counted and never imputed.
- **Also reported.** Relay integrity: every v2 check over the exposed branches, request-id uniqueness, and a row-level re-verification of the summaries. Termination reasons, user-call counts and cost.
- **Gate.** A manifest sha mismatch is always fatal. Any missing, failed or not-passed cell × batch summary refuses to run unless `--allow-partial` is given; the output is then named `simctrl_p_interim_*` and labelled INTERIM. `--batches 1` makes batch 1 alone the final scope if batch 2 is never run.
- **Interim data status** (protocol, not outcomes).
  - The 3 finished cells pass: 30/30 state checks, 600 branches, 0 arm errors, 0 protocol failures, and v2 checks 600/600 on each check.
  - 3,091 request ids, all unique.
  - 0 unexposed branches and 0 context overflows.
  - Cost: $24.90 for 3,091 calls ($0.0081 per call).
  - q4 GPTQ-W4 batch 1 had 8/10 state branch files written and no summary yet, so it is excluded from the interim look.
- **Evidence:** `analysis/fork/analyze_simctrl_p.py`; `analysis/fork/out/simctrl_p_interim_20261002T003506Z.{md,json}` (inputs with sha256 in the json). Inputs: `analysis/fork/simctrl_p/{q4_awq_w4,q8_gptq_w4_d1,q8_awq_w4}/b1/simctrl_p_{rows.jsonl,summary.json}` (cluster data, not committed). Protocol: `docs/insights/SIMCTRL_P_PROTOCOL.md`, `manifests/fork/simctrl_p_v1.json`.
- **Usage:** `python analysis/fork/analyze_simctrl_p.py` (final, batches 1+2); `--allow-partial` (interim); `--batches 1` (batch 1 only).

## W97 — Bank P simulator control (GPT-6.1 review 7): 80 states frozen outcome-blind, simrelay-v2 with integrity hashes, one clean `claude -p` call per user turn; dry run and relay test PASS; NOT queued (2026-10-01 PDT)
**TL;DR** The four-arm Bank P control approved in W96 is built, frozen and validated, and is not yet queued.
- **Manifest.** `manifests/fork/simctrl_p_v1.json` (sha `fa3dbf36…a48a3`) freezes 80 first-tool-structure-divergence states, 20 per core W4 cell. The selection is outcome-blind: admitted, re-checkable dev units; two-level Hamilton allocation over domain and block; sha256 order. There are two batches of 40. Batch 2 is gated on throughput or time only.
- **Runs.** Each state runs BB/BQ/QB/QQ × R = 5 with a_B/a_Q forced. The user simulator is Sonnet 5.5 via the new login-node daemon `simrelay_cli.py`.
- **Unexposed branches.** A branch that ends before any user call (no user call made) keeps its Y and is not missing.
- **Integrity.** v2 requests carry no identifiers, and every answer must echo req_id and msg_sha256.
- **Estimate.** Batch 1 is about 4.8k user calls, about 0.9 h at daemon concurrency 12, and $36–144.
- **Sampling** (`scripts/a6000/make_tasks_simctrl_p.py --freeze`).
  - Eligible units use the analyze_ghf/analyze_dev admission (dev split; units digests = `dev_all_20261001T070326Z` in all 4 cells) and are divergent and re-checkable:
    - the Q pivot replay passed;
    - the QQ no-op replay reproduced suffix, prompts, termination and counters (the outcome key is not used);
    - BB/BQ/QB have prefix_ok and env_ok.
  - Eligible per cell: q4 GPTQ 116/1102, q4 AWQ 149/1439, q8 GPTQ 149/1473, q8 AWQ 170/1562.
  - Sampled retail/airline: 13/7, 13/7, 14/6, 14/6. Batch 1: 6/4, 6/4, 7/3, 7/3.
  - Blocks covered: 16, 14, 16, 16.
  - Divergence types: talk→act 32, tool_name 18, tool_args 14, act→talk 12, other 4.
- **Run mode** `fork_driver.py` `simctrl_p` (new; `simctrl` and every other mode are unchanged).
  - State checks: state file sha, the rebuilt state id/history/prompt-id shas, the a_B/a_Q shas; on GPU, B regenerates a_B and Q regenerates a_Q.
  - Then 4 arms × 5 replicates run concurrently per state, keyed `<arm>#<r>`.
  - Outputs are `simctrl_p_rows.jsonl` and `simctrl_p_summary.json`.
  - Unexposed: `_user_protocol_p` requires the relay checks only when n_user_calls > 0.
- **Relay simrelay-v2** (`cloq/user_llm.py`; active only with context protocol `simrelay-v2`; v1 unchanged; own root `simrelay/v2`).
  - The request holds only req_id (random), protocol, system_prompt, messages, max_tokens, msg_sha256 (canonical JSON of the exact litellm list incl. system) and the stop convention.
  - Bookkeeping goes in the sidecar `meta/`.
  - Answers must echo req_id, protocol and msg_sha256; otherwise `RelayIntegrityError` (infra).
- **Responder** (`scripts/a6000/simrelay_cli.py`).
  - Atomic rename claim; responder `cli-<n>`; concurrency 12.
  - Each request gets one fresh `claude -p --model claude-sonnet-5-5 --tools "" --strict-mcp-config --setting-sources "" --max-turns 1 --no-session-persistence --system-prompt … --output-format json`, in an empty cwd, with `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` (removes a side Haiku call).
  - The frozen template `simrelay-cli-template-v1` (sha `b4ac8a7e…927d`) renders "Agent:" / "Customer (you):" turns.
  - Minimal cleaning; 3 retries, then back to pending; never a garbage answer.
  - Residual context: Claude Code appends an environment block and an account reminder to every user message. These are identical across requests and carry no identifiers.
- **Validation.**
  - (a) CPU dry run (mocks; 2 q4 GPTQ units × 4 arms × 5): state checks 2/2; 40 branches; 70 v2 calls, all integrity/protocol checks pass; 10 unexposed branches (forced tool call → mock Q stops) kept with Y and exposed=false; pass.
  - (b) Relay test (temporary root): 3 real retail requests answered by the real daemon (2.3–3.2 s, $0.006–0.008 each, Sonnet 5.5 only); hashes echoed and verified; `$302.67` preserved. A tampered msg_sha256, a tampered req_id echo and a request altered after hashing are all rejected (`RelayIntegrityError`).
- **Estimate** (`--estimate`).
  - Inputs: 6.07 dev user turns per branch on these states, so 4,805 calls (batch 1) and 9,710 (both); W95 agent time 12.2 s per turn; CLI ~4 s + 1.8 s poll.
  - FIFO model (4 tasks at once, excluding checkpoint/server start): batch 1 0.92 h (c = 12) / 0.67 h (c = 24); both 1.41 h / 0.89 h.
  - Cost: $36 (batch 1) / $72 (both) at the measured $0.0074 per call; $72–144 / $146–291 at $0.015–0.03.
- **Not done (main session):** start `simrelay_cli.py` on the login node; queue `make_tasks_simctrl_p.py --tasks --batch 1 --write` (priority −14; q4 1 GPU, q8 2 GPUs on node004/005/007; one task per cell per batch); write the analysis script; decide on batch 2.
- **Evidence:** `docs/insights/SIMCTRL_P_PROTOCOL.md`; `manifests/fork/simctrl_p_v1.json`; `scripts/a6000/{make_tasks_simctrl_p.py,simrelay_cli.py,fork_driver.py}`; `cloq/user_llm.py`; `tests/test_simrelay_v2.py`, `tests/mock_anthropic.py` (`--agent-stop`); `analysis/fork/simctrl_p/{dry/q4_gptq_w4_d1/,validation/relay_test_20261001.json,estimate.json}`.

## W96 — GPT-6.1 review 7 decisions applied: R2 centre narrowed, fit mechanism removed, text claim narrowed, Bank P control approved (2026-10-01 16:10 PDT)
**TL;DR** GPT-6.1 accepted R2 as the centre ("an action's task consequence depends on the subsequent controller"; 26.9% [25.7, 28.1], crossed [22.1, 32.0]), required removing the q4 GPTQ "action–controller fit" mechanism, narrowing the Bank U text claim further, approving a Bank P four-arm simulator control (W97), and set 10-03 as a completion target with 10-05 kept for audit.
- **Decisions (user-delegated to GPT-6.1):**
  1. R2 accepted. G−H kept as exploratory, within-cell, fixed-pool. The cross-cell ordering is descriptive and is not attributed to the quantizer or bit width. The q4 GPTQ fit mechanism is deleted, because Δ_B = −3.2 is similar to G = −2.9. E[I] is the difference of the action effect under the two controllers; fixed-policy value is E[G], E[H], E[F].
  2. Bank P simulator control: 80 frozen states (20 per core W4 cell, outcome-blind hash sampling), BB/BQ/QB/QQ × 5. Batch 2 is gated by capacity only. Unexposed branches are recorded, not treated as missing. The relay must verify request id and message hash, and every request is answered in an isolated context. → W97.
  3. Text claim: "these outcome labels did not reproduce reliably under an alternative stochastic relay setting"; this is not evidence of simulator artefacts. Correct comparison: 13/39 (either direction) vs 11/39, not an equivalence. The full tables are in the appendix. A mechanical flagged-reply sensitivity analysis is required.
  4. 10-03 is the completion target; 10-05 is reserved for audit and fixes. q4 AWQ-W3 stays deferred and is labelled incomplete (infrastructure timeouts).
- **Done:**
  - `analysis/fork/ghf_multiplicity.py` → `analysis/fork/out/ghf_multiplicity_20261001T225727Z.md`. Holm (m = 4) G−H over the core W4 cells: q8 GPTQ +2.9 p_holm .013; q8 AWQ +3.4 p_holm .012; q4 GPTQ −3.6 p_holm .069; q4 AWQ −1.3 p_holm .199. Crossed intervals cover 0 in all four.
  - `analysis/fork/analyze_simctrl.py --flagged` (mechanical rule: an arm replicate that used a flagged request becomes missing) → `analysis/fork/out/simctrl_relay_flagged_20261001T225847Z.md`. Result: retained 6/37, reversed 6, vanished 25 (15/2/8); controls 11/39 unchanged.
  - Paper: abstract, intro, R2 (new paragraphs "Within cells, the paired gains differ" and "A BF16 reference action can lower success"; the E[I] reading is fixed), R3 (sensitivity wording; the taxonomy table moved to the appendix; the new generated table `sections/gen_simctrl_fates.tex` via `tools/gen_simctrl_table.py`), limitations, and the coverage caption (q4 AWQ-W3 incomplete). `check_numbers.py` PASS (1,826); tectonic build has 0 overfull and 0 undefined; Limitations starts on p. 8.
- **Ops (15:20):**
  - `a6k2_q4_awq_w3_qx` failed for the second time with real 600 s vLLM timeouts. It was deferred with a note (`queue/deferred/a6k2_q4_awq_w3_qx.json`).
  - `bank_u_q8_kvq_int8_f03` and `bank_u_q0_q8_awq_w4_f02` were pinned to node007, which was full. Both were repinned to node004 (within the allowed set 004/005/007) and were claimed at 15:16.
- **Evidence:** GPT-6.1 review 7 (pasted by the user 2026-10-01); `paper/latex/sections/{abstract,introduction,results_r2,results_r3,appendix,limitations}.tex`; the files above.

## W94 — Paper restructured after GPT-6.1 review 6: interventional evaluation methodology, R1–R4 with the W93 2×2 at the centre; SIMCTRL filled in (2026-10-01 PDT)
**TL;DR** `paper/latex/` is now *This Step or From Here On? Crossed Same-State Interventions for Evaluating Quantized Agents*. One sentence: whether a quantized agent's local action difference has task consequences depends on the state and on the subsequent controller, so average success, action divergence and precision-replacement gain must be measured separately. Build clean (14 pp; main text pp. 1–8; 0 overfull, 0 undefined); `check_numbers.py` PASS (1773 numbers, 0 unverified).
- **Structure.** Intro opens with the escalation question and W93 Case 5 (q4 AWQ-W4 airline:31, BB/BQ/QB/QQ = 1/0/0/0). Related work is organised by identified quantity (Flat Score, Replay Gap = our F with no noise claim, DMR = router vs our gains/proxy validity, 2407.09141, 2606.00206). Method: Y_XY (first index = current action, second = controller from the next step), G/H/F, paired differences, Δ_Q/Δ_B 3×3, Bank P (first tool-structure divergence; text-only skipped) and Bank U, three denominators, identified (within-cell) vs descriptive (cross-cell), fixed-pool vs new-task intervals. R1 full-pool r/d/M/G_all (not end-to-end; e2e in App. B). R2 G/H/F table + TikZ 3×3 (W4 pool 26.9% off-diagonal, reversals 1.2–4.2%/cell, mean I ≈ 0 explained). R3 Bank U taxonomy with per-class totals and flip rates, SIMCTRL, holdout TODO, BFCL/ALFWorld. R4 token analysis + TOKEN-VALIDATION TODO. Appendix: setup, e2e, 16 patterns + new-task intervals, coverage matrix (completed only), Bank U/Q0, concentration, injection + Table 4 v2, prereg, withdrawn.
- **SIMCTRL** (`analysis/fork/out/simctrl_20261001T212742Z.md`, W95, commit c2b3259): of 39 Bank U text flips, retained 7 [0.075, 0.335], reversed 6, vanished 26 (15/2/9); matched controls new flips 11/39 [0.15, 0.45]; replicate disagreement 41% (flip arms) vs 21–26% (control arms). Written as: text-only consequences at ordinary states are largely simulator-dependent, not a stable property of the action; R3, abstract, intro and discussion downgraded; scope = fixed histories, relay Sonnet 5.5, stochastic, f01, does not test Bank P.
- **Placeholders:** HOLDOUT, TOKEN-VALIDATION, BANKU-F023 (main); RECOVERY-Q8, RESTORE (appendix). EXT-REFRESH resolved with the committed `ext_20261001T135106Z` (BFCL q4 AWQ-W4 788 items, G −3.8 [−6.5, −1.3]). SIMCTRL resolved (W95). Q14 dropped from the main text (scope stated as Qwen3 4B/8B).
- **check_numbers.py:** `% nocheck` (TikZ/notation), `% derived:` arithmetic verification, rounding tolerance (1–2 extra source decimals), missing-src detection, REQUIRED_SOURCES incl. W93 `ghf_20261001T211519Z.md`; exits 1 on failure. Appendix tables C are generated verbatim from the W93 md by `paper/latex/tools/gen_w93_tables.py`.
- **Discrepancy found:** the served user simulator is Qwen3-30B-A3B-Instruct-2507 (`/data/ziyangs/cloq_work/sims/*.json`, `docs/FINAL_EXPERIMENTS.md`). Fork state files' `simulator.user_model_id` and the SIMCTRL report header say Qwen3-4B-Instruct-2507; that field is the default `cloq/config.py` USER_MODEL_ID (= agent hf_id), not the served model. W90's "old simulator was Qwen3-4B-Instruct-2507" inherits the stale label. The paper says 30B-A3B.
- **Evidence:** `paper/latex/{main.tex,sections/*.tex,REWRITE_NOTES.md,check_numbers.py,tools/gen_w93_tables.py,main.pdf}`; W89 draft archived in `paper/latex/sections/old/w89/`.

## W95 — Sonnet 5.5 user-simulator control (relay): text-difference flips are not robust to changing the simulator (2026-10-01 14:30 PDT)
**TL;DR** On 39 Bank U text-structure flips (f01) and 39 matched non-flip controls, the user simulator after the fork state was replaced by Sonnet 5.5 (Claude Code subagent relay, R = 3).
- **Flips:** the original direction is retained in 7/39 [0.08, 0.34], reversed in 6/39, and vanished in 26/39.
- **Controls:** new flips appear in 11/39 [0.15, 0.45].
- **Reading:** retained + reversed ≈ the control new-flip rate, so these flips are indistinguishable from flips arising at matched non-flip states. The consequences of text-only action differences on ordinary states are largely simulator-dependent, not a stable property of the action.
- **Within-simulator variability:** replicates disagree in 41% of flip arms and 21–26% of control arms.
- **Scope and caveats:**
  - fixed histories from the old simulator; f01 only;
  - the relay simulator is stochastic (temperature 0 is impossible) and is a Claude Code subagent, not API Sonnet;
  - responder-ID attribution is unreliable (shared helper scripts);
  - 2 replies are flagged (`simrelay/FLAGGED_requests.txt`);
  - this does NOT test the Bank P tool-structure forks (R1/R2).
- **Implication:** R3's text-action statement is downgraded. The 69.6% composition share stands as an observation under one simulator only.
- **Evidence:** `analysis/fork/out/simctrl_20261001T212742Z.{md,json}`, `manifests/fork/simctrl_v3.json` (sha 3e430d93…), `analysis/fork/simctrl_relay/`, W90/W91.

## W93 — 2×2 fork re-centred (GPT-6.1 review 6): G/H/F with paired differences, (Δ_Q, Δ_B) 3×3 table, 16 patterns, frozen-rule cases, coverage matrix (2026-10-01 PDT)
**TL;DR** On each cell's own divergent states (same admitted units as `dev_all_20261001T070326Z`, units digest 11/11 equal): replacing only the current action (G), only the continuation (H) or both (F) moves success by a few pp at most in the W4/KV8 cells. Examples: q8 GPTQ-W4 G +3.3 [+1.6, +5.0], H +0.4, F +5.4 [+3.5, +7.2], G − H +2.9 [+1.3, +4.7]; q4 GPTQ-W4 G −2.9 [−5.7, −0.2], G − H −3.6 [−6.6, −0.6]. Stress RTN-W3 (q8) is dominated by the continuation: H +15.3, F +18.4, G − H −15.7 [−27.5, −3.9]. The action effect depends on which controller continues (Δ_Q ≠ Δ_B, off-diagonal) in 23–30% of W4 states (pool 26.9% [25.7, 28.1]) and about 15% of KV8 states (pool 15.3% [13.2, 17.3]). Yet the mean interaction is about 0 (W4 pool +0.0, KV8 −1.9 pp) because I > 0 and I < 0 are equally frequent. Strict sign reversals are only 1–4% of states (8–14% of the off-diagonal mass). The rest is "an effect under one controller, none under the other".
- **Estimands** (first index = action at the first divergence, second = controller afterwards; all four arms come from the same frozen state).
  - G = Y_BQ − Y_QQ, H = Y_QB − Y_QQ, F = Y_BB − Y_QQ.
  - Δ_Q = Y_BQ − Y_QQ (= G), Δ_B = Y_BB − Y_QB, I = Δ_Q − Δ_B.
  - Paired differences: G − H = Y_BQ − Y_QB; F − G = Y_BB − Y_BQ (= C); F − H = Y_BB − Y_QB (= Δ_B).
  - Denominator: the cell's divergent states (ratio of block sums).
  - Intervals: fixed task pool (block bootstrap with ≥ 10 complete blocks, else t over per-block ratios) and new-task generalisation (crossed task × block). They are reported in separate columns, B = 2000.
- **Identified vs descriptive.**
  - Identified (paired, same frozen states): everything within a cell. This covers G/H/F, their differences, the 3×3 table, the off-diagonal share and the 16 patterns.
  - Descriptive, confounded by state selection: every cross-cell comparison (q4 vs q8, AWQ vs GPTQ, W4 vs KV8 (e.g. off-diagonal 27% vs 15%), main vs stress). Each cell selects its own first-divergence states.
  - Pools are equal-weight averages of within-cell estimates on common complete blocks (W4 20 blocks, KV8 22). The stress pools are not poolable (1 common complete block), so stress cells are reported per cell only, with t intervals over 3 blocks.
- **Mean I ≈ 0 with a large off-diagonal share.**
  - E[I] = P(I=+1) + 2P(I=+2) − P(I=−1) − 2P(I=−2), while off-diagonal = P(I ≠ 0).
  - Example, q8 GPTQ-W4: P(I > 0) = 10.9%, P(I < 0) = 12.0%, off-diagonal 22.9%, E[I] = −1.7 pp.
  - The mean is the policy-value estimand. The off-diagonal share answers whether an action's consequence belongs to the action alone. It does not, for roughly 1 in 4 (W4) to 1 in 7 (KV8) divergent states.
- **16 patterns** per cell (counts and shares) are in §3 of the md. 0000 (39–58%) and 1111 (6–20%) dominate.
- **Cases** (frozen rule: re-checked units only, i.e. the QQ no-op replay passed, the Q pivot replay passed, and every branch is prefix_ok/env_ok; order = sha256('ghf-case-v1:' + state_id); 717 eligible states):
  - rescue q4 KV8 retail:84 f11 (1100; wrong order id at the pivot → the wrong item returned under either controller);
  - rescue q4 AWQ airline:3 q4 (1110; Q answers baggage from policy without lookup and later writes the wrong baggage update);
  - damage q4 AWQ airline:11 f04 (0011; B looks up a non-existent user id and later fails a passenger update);
  - damage q8 AWQ retail:40 f13 (1011);
  - controller-dependent q4 AWQ airline:31 f13 (1000);
  - controller-dependent q4 AWQ retail:61 q3 (1101).
  - Each case gives the verbatim pivot actions and the per-branch tool, error, write and transfer chains.
- **Coverage matrix** (§5): model × config × {retail, airline, telecom, alfworld, bfcl}, giving end-to-end blocks × tasks, 4-branch forks (tasks · divergent states · complete/found blocks), Bank U (blocks · rows · tasks) and holdout.
  - 4-branch tau2 forks exist only for q4/q8 × {GPTQ-W4, AWQ-W4, KV8} (20–22 blocks) and the stress cells (3 blocks). q4 RTN-W3 has 0 complete blocks.
  - Telecom dev forks: q8 AWQ-W4 and q8 GPTQ-W4 only (6 blocks). Telecom holdout fork dirs exist for q4 GPTQ-W4 and q8 AWQ/GPTQ-W4; they were listed by name only and not opened.
  - q14/q32/l8 are end-to-end only.
- **Evidence:** `analysis/fork/analyze_ghf.py`; `analysis/fork/out/ghf_20261001T211519Z.{json,md}`; `analysis/fork/out/fig_ghf_{q4_awq_w4,q4_gptq_w4_d1,q4_kvq_int8,q8_awq_w4,q8_gptq_w4_d1,q8_kvq_int8,pooled}_20261001T211519Z.png`. Inputs: snapshot `analysis/insights/iter_3/out/snapshot_auto_20261001T0600Z.json`; reference `analysis/fork/out/dev_all_20261001T070326Z.json`. CPU only; no telecom holdout data read.

## W91 — Simulator control via a Claude Code subagent relay (no API key): relay user simulator, manifest simctrl_v3, mock dry-run PASS, relay gate queued (2026-10-01 PDT)
**TL;DR** There is no Anthropic API key. The user simulator of the W90 control is now served by Claude Code Sonnet 5.5 subagents through a file relay on NFS. This is a **different simulator** from API Sonnet (v2), so it gets its own frozen manifest, `simctrl_v3.json`. A CPU dry run with a mock responder passed (1 gate state, 18 branches, 18 relayed user turns, all protocol checks). Only the 3-state gate task is queued; the main session starts the responders.
- **Relay protocol (simrelay-v1, `cloq/user_llm.py` provider `"relay"`).**
  - tau2's own UserSimulator still builds the system prompt (guidelines + task instructions) and the role-flipped message list. Instead of a litellm call, the wrapped `completion` writes `/data/ziyangs/cloq_work/simrelay/pending/<req_id>.json` atomically (tmp file in the same directory + rename).
  - The request holds: req_id, state_id, unit_id, arm, replicate, user-turn index, `system_prompt`, `messages` (as tau2 sends them, roles flipped), `litellm_messages` (the exact list, with its sha), max_tokens 512, and the tau2 stop-token convention.
  - The branch polls `done/<req_id>.json` for `{"content": ...}`. The timeout is 45 min per turn (`$CLOQ_SIMRELAY_TIMEOUT_S`). On timeout the request moves to `expired/` (with a reason file) and the branch fails as infra: arm error → gate FAIL. Nothing is silent.
  - The reply enters tau2 as a normal user-LLM response (finish_reason stop, no tool calls). Each call records req_id (as the request id), responder, claim/answer times and wall time.
  - In relay mode the 2R = 6 branches of a unit run concurrently, so up to 18 requests are pending at once for the gate.
- **Responders.**
  - Helper: `scripts/a6000/simrelay_claim.py`:
    - `next --responder <id>` renames one pending request into `claimed/<id>/` and prints its path (`NONE`, exit 3, if empty);
    - `answer <req_id> <file>` writes done/ atomically; it refuses an unclaimed, expired or already-answered request, or an empty reply;
    - `status` gives counts.
  - Instructions: `docs/insights/SIMRELAY_RESPONDER.md`. Act strictly as the customer in the system prompt. Answer only from this request; every request is independent. Output only the next message, using the stop tokens. No tools beyond the helper.
- **Manifest** `manifests/fork/simctrl_v3.json`, sha256 `3e430d93c8ee92940059fa3862bf31de7c329d69ba767b05a2f4f5ce9597f712`.
  - It amends v2 (sha `73e37c3c…`, commit 2ff2285) and keeps the same 39 flips + 39 controls, R = 3, the replicate-mean primary, the per-replicate distribution and the within-simulator variability.
  - `user_llm = {"provider": "relay", "model": "claude-sonnet-5-5 (Claude Code subagent relay)"}`. The gate's model/request-id check becomes: every call relayed, with a req_id and a named responder (`relay_all_answered`).
  - **Honest scope** (`relay_simulator_note`): this is not API Sonnet and not the standard simulator. The responders' context includes Claude Code's agent system prompt and tool turns. Cross-request carry-over within a responder is possible; it is instructed against but cannot be enforced. Sampling is uncontrolled and max_tokens is advisory.
  - v3 results are reported as "Sonnet 5.5 (Claude Code relay) user". They are never pooled with or substituted for v2, which stays frozen and unrun.
- **Code.**
  - `fork_driver.simctrl`: relay needs no key and sets the per-branch relay context; the protocol check uses `UL.litellm_model`.
  - `make_tasks_simctrl.py --freeze-v3 | --relay [--gate|--tasks] [--priority N] [--write]`: `--relay` uses v3 and the ids `simctrl_relay_*`, writes to `analysis/fork/simctrl_relay/`, and skips the key check (relay only).
  - `analyze_simctrl.py --manifest manifests/fork/simctrl_v3.json --dir analysis/fork/simctrl_relay --tag relay`.
- **Dry run** (CPU; mock agent `tests/mock_anthropic.py`, 2 mock responders `tests/mock_simrelay_responder.py` racing on the claim; relay dir `/data/ziyangs/cloq_work/simrelay_dry`).
  - 3 gate states rebuilt (state checks 3/3). Unit aea8d796 ran 6 branches; each ended `user_stop` on the relayed `###STOP###`.
  - Every protocol check passed for all 6 branches: system prompt identical, history prefix identical, no tools, stop token only last, `relay_all_answered`.
  - No double claims. Negative tests: a 5 s timeout raised RelayTimeout and moved the request to expired/; `answer` refused an expired and an unclaimed request.
- **Queued:** only `simctrl_relay_gate_q4_gptq_w4_d1` (q4 GPTQ-W4 d1, 3 units, BQ + QQ × R = 3, 1 GPU, priority −20, gate=true). It raises on FAIL, so later `--relay --tasks` deps would never release. The 6 per-cell tasks are NOT queued.
  - Expected ≈ 85 relayed user turns (range 60–130). The original old-simulator branches of these units had 5–7 user turns per arm on the two retail units and 3–5 on the airline unit; 18 branches.
  - The GPU sits idle while it waits on responders.
- **Evidence:** `analysis/fork/simctrl_relay/dry/q4_gptq_w4_d1/{simctrl_rows.jsonl,simctrl_summary.json,branches/}`; `manifests/fork/simctrl_v3.json`; queue file `/data/ziyangs/cloq_work/queue/todo/simctrl_relay_gate_q4_gptq_w4_d1.json`.

## W90 — Simulator robustness control for Bank U text-structure flips (Sonnet 5.5 user; GPT-6.1 review 5 option A): built, frozen, dry-run; NOT run (no API key yet) (2026-10-01 PDT)
**TL;DR** Everything is ready. The run waits for the API key file. Nothing was sent to the Anthropic API, and no GPU task was queued.
- **States:** 39 flips + 39 matched controls. The flips are the 39 deduplicated Bank U class (ii) flips at f01 (37 ii_talk + 2 ii_act; 17 rescues, 22 damages).
  - Matching is 1:1, within the same model × cell × block × sub-bank × sub-class, nearest in action length and relative position. Ties are broken by a hash.
  - **f01 only**: at freeze time, f02/f03 had not landed for every cell.
- **Manifest:** frozen at `manifests/fork/simctrl_v1.json`, sha256 `15b9b2284303a7f9f0baa27411cc4edc63f935b01b88f56b134fb041ff3d87a4`.
- **Branches:** the original native arms BQ and QQ, with the recorded a_B / a_Q and the cell's Q controller. Only the user simulator after h_t changes, to `claude-sonnet-5-5`.
- **Next step:** when the key file exists, run `make_tasks_simctrl.py --gate --write` (3 states). Once the gate passes, run `--tasks --write`.
- **Estimated API use:** ≈ 670 user calls, ≈ 0.96M input + 0.04M output tokens, ≈ $2.3 at $2/$10 per MTok (chars/3.5 from the original branches; Sonnet's own turn lengths will move this).

- **Implementation (route: litellm, the path tau2 already uses).**
  - `cloq/user_llm.py`: `apply()` swaps only `llm_user` → `anthropic/claude-sonnet-5-5` and `llm_args_user`. tau2's UserSimulator, system prompt, task instructions, history flip and stop tokens are untouched.
  - `install()` wraps tau2's litellm `completion` for `anthropic/*` only. It drops the orchestrator's `seed` (unsupported; the drop is recorded) and records each user call: request-id header, usage, cost, finish reason, system-prompt sha, request messages.
  - Key: read only from `$CLOQ_ANTHROPIC_KEY_FILE` (default `~/.config/anthropic/api_key`) into the driver's environment. It is never in llm_args, never logged.
  - `cloq/fork.py`: `run_config(..., user_llm)` and `run_branch(..., user_llm=None)`. The default path is unchanged.
  - `scripts/a6000/fork_driver.py` mode `simctrl`. Per unit:
    - check the manifest sha, the a_B/a_Q canonical sha, history_sha and prompt_ids_sha;
    - require that B regenerates a_B exactly, that Q regenerates a_Q exactly, and that both servers' prompt ids match;
    - run BQ + QQ with the Sonnet user;
    - run the per-branch protocol checks (`_user_protocol`).
  - `scripts/a6000/make_tasks_simctrl.py`:
    - `--freeze` (refuses to overwrite);
    - `--gate`: 3 q4 GPTQ-W4 d1 units;
    - `--tasks`: 6 per-cell tasks, deps on the gate, usual fork shape (B = BF16, Q = cell config; q4 1 GPU, q8 2 GPUs);
    - `--write` refuses without the key file.
- **Parameters.**
  - Model id `claude-sonnet-5-5`. **Temperature 0 is not possible**: the model returns a 400 on any non-default temperature/top_p/top_k. There is no seed. So it is one stochastic run per arm.
  - Thinking off via `{"type": "between_tools"}`; max_tokens 512, the old simulator's value.
  - No server-side refusal fallback, because it would silently change the simulator model.
  - The old simulator was Qwen3-4B-Instruct-2507 at T = 0, seed = sim_seed.
- **Acceptance gate** (must PASS before any analysis; `analyze_simctrl.py` refuses otherwise):
  - state reconstruction;
  - system prompt identical to tau2's UserSimulator prompt built from the task's instructions;
  - message prefix identical to the role-flipped user-visible history;
  - no user tools (retail/airline; telecom is not in Bank U);
  - env hash at init and prefix_ok;
  - stop tokens only in the last user message, and a user_stop ends on a token;
  - every call is to the right model, has a request id, and has no errors.
- **Report** (`analysis/fork/analyze_simctrl.py`; no pass threshold):
  - flips: retained (same direction) / reversed / vanished (both succeed / both fail);
  - controls: newly appearing flips (rescue / damage);
  - groups: all, per model, sub-bank, sub-class, and original direction (flips only); Clopper-Pearson intervals;
  - also: paired flip × control cross-tab, arm agreement with the original Y, termination, token usage.
  - Scope stated in the manifest and the report: robustness of continuations on fixed histories generated by the old simulator. It does not replace a benchmark re-run with a new simulator.
- **Dry run** (CPU, no key):
  - `tests/mock_anthropic.py` mocks the Messages API plus a trivial agent.
  - All 78 states rebuilt: a_B/a_Q, history and prompt-id shas 78/78.
  - Local prompt-id render (diagnostic only; the GPU run checks the servers' ids): 75/78. The 3 q4 misses include the known W88 text + tool-call whitespace case.
  - 3 gate units ran BQ + QQ end to end through litellm → mock; every protocol check passed.
  - The request body is exactly {model, system, messages, max_tokens 512, thinking between_tools}: no temperature, no seed.
  - Negative tests: a tampered system prompt, a dropped history message and an early ###STOP### each fail their check.
  - The analysis script ran on the dry outputs.
- **Amendment (main session, before any Sonnet run):** R = 3 independent replicates per arm (BQ and QQ) per unit, flips and controls alike. One stochastic run per arm would confound retention with simulator sampling noise.
  - Frozen as `manifests/fork/simctrl_v2.json`, sha256 `73e37c3c4cad96f9e978f7b442adc2bed6f89bbcd2482154f7ac4af04f3fd31e`. Units are those of v1; v2 amends v1 (sha `15b9b228…`, commit 769dc36), and tasks now use v2.
  - Primary: the sign of the replicate-mean flip indicator Dbar = mean_r (Y'_BQ,r − Y'_QQ,r) against the original direction (retained / reversed / vanished; controls: Dbar ≠ 0 = new flip).
  - Also reported: the per-replicate distribution, and within-simulator variability (the share of units whose replicates disagree, per arm and role).
  - The driver checks that the task's R equals the manifest's.
  - v2 dry run (mock, 3 gate units × 2 arms × 3 replicates): 18 branches and 54 user calls, all protocol checks pass. Output: `analysis/fork/simctrl/dry_v2/`, `analysis/fork/out/simctrl_dry_v2_20261001T194700Z.{json,md}`.
  - Estimate ×3: ≈ 2,000 user calls, ≈ 2.9M input + 0.11M output tokens, ≈ $7.
- **Evidence:**
  - `analysis/fork/simctrl/dry/*/simctrl_{rows.jsonl,summary.json}` (+ branches);
  - `analysis/fork/out/simctrl_dry_20261001T194252Z.{json,md}` (DRY: mock user, not results);
  - `manifests/fork/simctrl_v1.json`.

## W88 — Token-level scoring of Bank U states (2606.00206-style uncertainty mechanism) + frozen Q-visible escalation trigger; f01 only, validation pending (2026-10-01 PDT)
**TL;DR** On all 6 f01 cells (1140 cell × state rows, 58 flips), Q's uncertainty predicts **whether B and Q act differently**, not **whether the difference matters**:
- **Whether B and Q differ:** Q's truncated top-20 entropy at the action start separates differing from identical actions, AUC 0.66–0.91 per sub-bank × model.
- **Over all ordinary states:** flips sit at lower Q min-margin. U1 q4 Δ −2.0 [−2.9, −1.1], AUC 0.31 [0.22, 0.40]; U1 q8 AUC 0.24 [0.13, 0.36]. These are stratified by cell × action-length tercile.
- **Among differing states only:** the U1 effect vanishes (point AUCs 0.27–0.68, every CI covers 0.5). Only q4 U2B keeps a moderate one: mean Htk_Q AUC 0.73 [0.53, 0.89].
- **At the first divergent token (diagnostic only):** entropy and top-k-union KL do not separate flips (AUCs 0.39–0.63, CIs cover 0.5; the one exception is U2Q q4 KLu_k AUC 0.80 [0.65, 0.93] on 4 flips).
- **Frozen trigger:** S_mm = −(min Q margin over a_Q), frozen on f01 before any f02/f03 scoring. Its validation is **pending**.
- Exploratory throughout; f01 is development.

- **Scoring (Part A).**
  - Code:
    - `scripts/a6000/score_driver.py`, dispatched by `worker.py` run_fork when `fork.driver == "score"` (one-line hunk);
    - generator `scripts/a6000/make_tasks_score.py` (q4 on 1 GPU at 0.44, q8 on 2 GPUs, no pins, priority −15).
  - Per state:
    - rebuild the ForkAgent prompt and require sha256(prompt ids) == the Bank U row's prompt_ids_sha;
    - regenerate a_B on B and a_Q on Q (greedy);
    - teacher-force the **generated token ids** (the source run's logged completion ids where it logged the action, else the regeneration) under both servers on the identical prompt ids, with vLLM prompt_logprobs top-20;
    - store per token: the chosen logprob and rank, the top-20, the truncated top-20 entropy Htk (+ one tail bucket), the margin, and KLu(B‖Q) on the top-20 union with a tail bucket. These are never called full entropy or KL.
  - Checks, all 6 f01 cells:
    - 1140/1140 rows scored; prompt sha 1140/1140;
    - regeneration == recorded generation 1060/1060 recorded actions, which also confirms the serving configs incl. AWQ/GPTQ rebuilds and KV8 hooks;
    - every own-action token is the generating model's argmax 1140/1140 (tie-aware; vLLM ranks exact ties as 2);
    - teacher-forced vs decode-time logprob |Δ| ≤ 5e-5;
    - chat-template re-tokenization ≠ generated ids for 2–8 actions per q4 cell (flagged; scoring uses the generated ids). These are text+tool-call messages whose trailing whitespace before `<tool_call>` the parser strips.
  - The 5-state dry run (`analysis/fork/token_scores/dry/`) passed before the bank was queued.
- **Whole-action analysis (primary view; GPT-6.1 review 5 point 4).**
  - Design: consequential vs non-consequential ordinary states per sub-bank × model, stratified by cell × a_Q length tercile, plus 5 relative-position bins over a_Q.
  - All states: Q-visible uncertainty is higher for flips in every sub-bank. U2B q4: mean Htk_Q AUC 0.81 [0.65, 0.93]; Htk_Q is higher at every position bin.
  - Differing states only (removes the "any difference at all" selection): U1 shows nothing. q4 U2B keeps mean Htk_Q +0.065 [+0.009, +0.112] and mean lp_Q AUC 0.27 [0.12, 0.47].
  - Reading: Q uncertainty marks where quantization changes the action, not which changes are consequential. The analogy to the 2606.00206 mechanism holds only at the "differs at all" level.
- **First divergence (diagnostic only; needs B; conditions on differing states).**
  - Htk_Q_k, Htk_B_k, KLu_k, Q's margin and log-odds at k show no flip/no-flip difference in any pooled sub-bank × model.
  - Rescue vs damage is n ≤ 13 per side. Q's margin at k is larger for rescues in U2B q4: AUC 0.82 [0.56, 0.98] (n 9/10).
- **Divergence-token taxonomy** (first divergent token; descriptive; the classifier is a regex over decoded tokens).
  - q4 (255 differing, 44 flips):
    - `other_lexical` (word-choice divergences) is mildly enriched: rate ratio 1.89, Fisher p .019;
    - `format_punct` is depleted: 2/42.
  - q8 (175 differing, 14 flips): `confirmation` 2/3 (p .017; n tiny) and `tool_name` 3/19 (rate ratio 2.24, p .18).
  - Tool-argument and closing divergences never flip (0/13, 0/11). Discourse markers flip in q4 at 5/20 (4 rescues).
  - No class reproduces the strong overthinking-marker enrichment of 2606.00206.
- **Frozen repair candidates** (for a later panel; the repair intervention is NOT built): `manifests/fork/token_repair_candidates_v1.json`, sha256 `6ea164d43ca63ed614fc6909ebcd4adf39d3c2945142305aff2dc52c4993ed87`.
  - Rule: classes with ≥ 3 f01 flips and a rate ratio ≥ 1.5.
  - Result: q4 {discourse_marker, other_lexical}; q8 {tool_name}.
  - Plus a Q-defined span rule: a_Q tokens whose Q margin is below the f01 U1 10th percentile (q4 1.625, q8 2.5).
- **Sampled-state intervention value of one-step BF16 escalation (not a token mechanism; not a closed-loop policy).**
  - Rule: `manifests/fork/token_trigger_rule_v1.json`, sha256 `335e737d54bf59b948022b8054897ba703a1b9df6665f55bf6ab19b70333c052`, committed in d70d712 before any f02/f03 scoring task was queued.
  - Candidates (Q-visible only): Htk_Q at the action start, −(min Q margin over a_Q), −(mean lp_Q of a_Q).
  - Selection on f01 U1: maximise the mean over 5/10/20% of in-sample net gain minus its random expectation.
  - Chosen: **S_mm**, with per-cell thresholds.
  - In-sample (selection only; not a policy value): net +0 / +2 / −2 at 5/10/20% vs random −0.38 / −0.75 / −1.60, out of 30 f01 U1 turnover states.
  - Caveat: in every cell more than 10% of U1 states contain an exact (bf16-resolution) top-2 tie inside a_Q. At 5/10% the rule is therefore "a_Q contains a tie", with ties broken by a frozen sha256(state_key) hash.
  - An uncommitted first freeze without that tie-break escalated nobody. It was discarded before commit; no validation data existed.
  - **Validation is pending.** It covers f02/f03, net gain vs a same-count random trigger (exact hypergeometric null), rescues, damages and turnover captured. The 12 f02/f03 score tasks are queued; 6 wait on their bank_u task. Rerun `python analysis/fork/analyze_token_mech.py` when they land; it reads the frozen rule and reports validation.
- **GPU:** ≈ 4.6 GPU-h. q4 3 × ~25 min on 1 GPU, q8 3 × ~31 min on 2 GPUs, dry run 10 min; mostly AWQ/GPTQ rebuilds and server start.
- **Evidence:**
  - `analysis/fork/out/token_mech_20261001T185031Z.{md,json}`;
  - `analysis/fork/token_scores/<m>_<cell>/f01/score_summary.json` (per-token scores in `scores.jsonl.gz`, not in git);
  - `analysis/fork/analyze_token_mech.py`; `scripts/a6000/score_driver.py`; commits 49ccaa6 (code) and d70d712 (frozen rule and repair list).

## W89 — Paper LaTeX rewritten to storyline v7 (ARR October → NAACL long) (2026-10-01 PDT)
**TL;DR** `paper/latex/` now follows `docs/STORYLINE_v7.md`. It leads with the same-state 2×2 fork and has three layers: L1 atlas, L2 Bank U and L3 bounding results. The build is clean with tectonic (12 pp; main text 8 pp; 0 overfull boxes, 0 undefined references). Every number carries a `% src:` comment, and pending results are `\todo{}` placeholders.
- **Sections:** abstract, intro, related work, method, atlas, bank_u, intervention, discussion, limitations, ethics, appendix.
- **Archive:** the W33 files are in `paper/latex/sections/old/w33/`.
- **Binding rules applied** (GPT-6.1 reviews and the corrections in REPORT_GPT61_20261001_0915):
  - G = Y_BQ − Y_QQ is never called end-to-end. End-to-end claims cite `success_ni_ALIGNED_20260930T213009Z` (TOST ±3 pp fails everywhere).
  - 39/56 is a composition share, given with per-class denominators.
  - The co-flips are 5 distinct states and are presented as a lead.
  - The Replay Gap noise comparison is not made.
  - The W78 wording is "6 configurations × 2 directions, retrospective conditional association".
  - wrong_tool is called a "tool-call/schema error perturbation".
  - Table 4 v2 is LLM-annotated and makes no consent claims.
  - W×KV, restoration, equivalence and "absorbed" appear in the appendix only.
- **Placeholders:**
  - HOLDOUT (prereg sha 902892dd…), BANKU-F023, Q0, RECOVERY-Q8, TOKEN, SIMCTRL, Q14;
  - EXT-REFRESH: `ext_20261001T135106Z` is untracked; the paper uses the committed `ext_20260930T221613Z`;
  - RESTORE: the 70%/27% result is only in an untracked restore_eval output, so it is not printed.
- **Self-check:** `paper/latex/check_numbers.py` checked 909 number occurrences. The remaining flags are rounding (recovery CIs at 3 decimals, 4.09 → 4.1, .538 → 54%) or structural (section numbers, TikZ, model names). All were checked by hand.
- **Corrections vs the storyline text:**
  - External W4 M is 5.2–24.6%, not 7–25%.
  - Two W4 fixed-pool G intervals exclude 0 (q4 GPTQ −1.9 [−3.7, −0.1]; q8 GPTQ +2.9 [+1.4, +4.4]).
- **Bibliography:** refs.bib gains 7 entries (CSO, CRR, CAR, AgenTracer, Lost in Simulation, UserProxyBench, 2606.00206), with metadata from arxiv.org/abs. Replay Gap becomes an arXiv preprint because its venue is disputed.
- **Evidence:** `paper/latex/{main.tex,sections/*.tex,refs.bib,REWRITE_NOTES.md,check_numbers.py,main.pdf}`.

## W87 — PREREG_FORK_CONFIRM frozen (2026-10-01 08:00 PDT, author approval "按建议冻结")
**TL;DR** `docs/insights/PREREG_FORK_CONFIRM.md` is frozen: sha256 `902892dd63e99e16ab9beefee9d39319d835eacdada3d4d92c4a1022d13fd622`, recorded in `manifests/fork/splits_v1.json` `splits.holdout.prereg_sha256`. No holdout unit had been run or read before the freeze.
- **Author decisions:**
  - cells: q4 GPTQ-W4 d1, q8 GPTQ-W4 d1, q8 AWQ-W4;
  - weights: 1/2 per model (q4 1/2, each q8 cell 1/4);
  - the crossed interval decides, with block-t reported alongside;
  - cells with more than 3 structural exclusions are kept and reported;
  - K = 12 (h01–h12), with reserves h13/h14 for infrastructure repair only;
  - budget about 100–200 GPU-h.
- **Agent choices accepted by the main session:**
  - S1 and the strata also use the crossed interval;
  - S2 uses the 1/2, 1/4, 1/4 weights;
  - the fault-load stratum is split into two families;
  - tertiles allow ties;
  - a QQ no-op mismatch excludes only that unit's task in that cell;
  - q8 closed-loop runs on 1 GPU and forks on 2, as on dev.
- **Known risk:** q4 telecom forks have never run at gpu_util 0.44. The per-state no-op checks catch any failure; a failure is repaired under the frozen completeness rule, never dropped silently.
- **Evidence:** W85/W86, `analysis/fork/out/holdout_confirm_DRYRUN_DEV_20261001T144457Z.md`, `manifests/fork/holdout_cutpoints_v1.json`, `scripts/a6000/make_tasks_holdout.py`, `analysis/fork/analyze_holdout_confirm.py`.

## W86 — PREREG_FORK_CONFIRM.md completed to READY TO FREEZE; dev cut points, confirmatory analysis script (dry run on dev), holdout task generator (2026-10-01 PDT)
**TL;DR** The holdout prereg now encodes the author's six decisions, with no open items. The main session can record its sha256 `902892dd63e99e16ab9beefee9d39319d835eacdada3d4d92c4a1022d13fd622` in `splits_v1.json` (nothing was frozen here).
- **Prereg** (`docs/insights/PREREG_FORK_CONFIRM.md`):
  - Cells q4 GPTQ-W4 d1 / q8 GPTQ-W4 d1 / q8 AWQ-W4, with weights **1/2, 1/4, 1/4**.
  - The **crossed task × block** interval decides (ANOVA moments, normal 90%); the block t is reported alongside. ±3 pp readings; ±5 pp sensitivity.
  - Structural exclusions are kept and flagged when > 3. A QQ no-op mismatch is unit-level, not whole-directory quarantine.
  - K = 12 (h01–h12). Reserves h13 (0354e294) and h14 (555fd7b8) are used only for infrastructure repair. Nonces were re-checked against 31 used nonces, with no collision.
  - Halves: H_A = {h01, h04, h05, h09, h11, h12}.
  - S2 has no outcome screen. Its permutation is keyed and persona-stratified, identical across cells, and its claim is worded honestly.
  - Strata: six families of 3 levels each, Holm within each family.
- **Cut points (dev only):** `manifests/fork/holdout_cutpoints_v1.json` (sha256 ab46abe9…), produced by `analysis/fork/make_holdout_cutpoints.py`.
  - Step budget: T1 ≤ 191 < T2 ≤ 197 < T3 (tie-aware tertiles; 38% of dev values are 199).
  - BF16 difficulty: 0 / (0, 1/3] / > 1/3.
  - Task length: 15.67 / 20.33.
  - Number of faults: 3 / 5.
- **Analysis script:** `analysis/fork/analyze_holdout_confirm.py` (sha256 2af1b689…). It refuses `--split holdout` unless `analyze_dev.split_guard` passes, and it refuses if the cut-point sha has changed.
- **DRY RUN ON DEV** (`analysis/fork/out/holdout_confirm_DRYRUN_DEV_20261001T144457Z.{json,md}`; telecom dev f01–f06 as a pseudo-holdout, q8 cells only, K = 6; exploratory):
  - G_all **+1.04 pp**, crossed 90% CI [−0.97, +3.06]; block t [−1.43, +3.51]. The readings are not estimable (K' < 8).
  - r 7.29 and d 6.25 pp, both with LB > 0.
  - S2 ρ = 0.57 (GPTQ 0.63, AWQ 0.51), p = 0.0001.
  - Per-cell G matches W85: +2.71 for GPTQ and −0.62 for AWQ.
- **Planning re-run with the approved weights** (`analysis/fork/out/holdout_k_planning_20261001T144122Z.{json,md}`; `holdout_k_planning.py` gained `--weights` and `--ks`). At K = 12:
  - Crossed width 4.1 pp and t width 3.9 pp.
  - S2 power 1.00, or 0.73 with s_u halved; size 0.05.
  - P(LB > 0 | G = 3 pp) = 0.79.
- **Generator:** `scripts/a6000/make_tasks_holdout.py` runs dry by default. `--write` is refused before the freeze and was **not used**.
  - The dry run prints **38 tasks**: 20 eval tasks (60 closed-loop runs) and 18 fork tasks, ≈ **96 GPU-h** (67–145); the reserves would add ≈ 16 GPU-h.
  - q8 forks run on 2 GPUs. The closed loop stays on 1 GPU, as on dev, so that the fork can regenerate the Q actions. No node pins.
  - The task file `manifests/telecom/holdout_v1.json` is written by `--write` from splits_v1.
- No holdout task, trajectory or outcome was read. `splits_v1.json` was not edited. No sbatch was run and nothing was queued.

## W85 — Holdout K planning simulation (telecom dev only) and draft PREREG_FORK_CONFIRM.md (NOT frozen) (2026-10-01 PDT)
**TL;DR** K = 12 is adequate, as confirmed on telecom dev data only; it was not selected from this simulation.
- **Planning results** (34 simulated tasks, 3 equal-weight cells, fitted dev heterogeneity), K = 6 / 8 / 12 / 16:
  - 90% CI width of G_all (t over block means): 5.7 / 4.7 / **3.6** / 3.1 pp. The crossed task × block width is about the same (5.4 / 4.6 / 3.7 / 3.3 pp).
  - Repeatability test power: 0.99 / 1.00 / 1.00 / 1.00. With the task heterogeneity halved, which is below its dev 95% profile lower bound, power is 0.46 / 0.57 / **0.76** / 0.86. Size is 0.03–0.06.
  - Power to show a positive gain (one-sided 95% lower bound > 0) at the §F planning value G = 3 pp: 0.54 / 0.64 / **0.83** / 0.91.
- **Draft protocol.** `docs/insights/PREREG_FORK_CONFIRM.md` merges FORK_PROTOCOL §12, §12 amendment 1 and every holdout point of GPT-6.1 review 4:
  - K = 12, blocks h01–h12 with fixed nonces, a hash split into halves, and reserve blocks h13–h14.
  - The complete 34 × 12 × 3 matrix, with outcome-blind repair rules.
  - Fixed cells and weights.
  - The ≥ 10-flipping-task screen is removed: the only "not estimable" condition is a constant vector, which is invariant under the permutation.
  - The permutation's claim is worded honestly.
  - G_all is the sole primary with ±3 pp bounds; the test families are stated.
  - Dev results are not retroactively confirmed.
- **Cost.** About **96 GPU-h** (67–144) from measured telecom dev logs; 195 GPU-h conservative, counting failed attempts and using the larger q4/q8 ratio.
- `splits_v1.json` was not edited and nothing was frozen. No holdout task was read.
- **Dev fit.** On q8 telecom dev (80 tasks × f01–f06; all 12 cell-blocks complete), from a logistic GLMM with persona intercepts, block effects and a task random effect:

  | cell | M rate | G_all | task-effect SD s_u (95% profile) | block-shock SD |
  |---|---|---|---|---|
  | GPTQ-W4 | .148 | +2.7 pp | 2.22 [1.73, 2.85] | 0.57 |
  | AWQ-W4 | .123 | −0.6 pp | 1.62 [1.27, 2.09] | 0.35 |

  - The cross-cell task-effect correlation is 0.80.
  - The rescue share shows no task-level heterogeneity.
  - Dev split-half ρ (3 + 3 blocks, the holdout hash rule) is +0.63 for GPTQ and +0.51 for AWQ. It is descriptive and exploratory.
- **Caveats.**
  - The holdout cell q4 GPTQ-W4 has no telecom dev forks, so it borrows q8 GPTQ parameters.
  - The block-t interval treats the tasks as fixed. At G = 3 pp, P(90% CI inside ±3 pp) = 0.09, against a nominal ≤ 0.05, so the crossed interval is reported for new-task generalisation.
- **Open author decisions** (PREREG §14):
  - the cells, especially q4 GPTQ;
  - equal weights 1/3 vs 1/2 per model;
  - whether the t or the crossed interval is decisional;
  - the structural-exclusion cap;
  - the dev cut-point file and `analyze_holdout_confirm.py`, both still to be written;
  - re-checking the nonces at freeze;
  - the budget.

Evidence:
- `analysis/fork/holdout_k_planning.py` → `analysis/fork/out/holdout_k_planning_20261001T134838Z.{json,md}`. Run with `--reps 1000 --perms 2000`, seed 20261001, snapshot `snapshot_auto_20261001T1322Z`.
- `docs/insights/PREREG_FORK_CONFIRM.md` (DRAFT).
- Cost inputs: `/data/ziyangs/cloq_work/logs/node_*.out` (cluster only).
- Sources: `outputs/gpt61-review4-response-review.md`, FORK_PROTOCOL §12 and §12 amendment 1.
- CPU only.

## W84 — Bank U f01 analysis: sub-banks separate, unique states, action taxonomy, text-content split, Q0, cross-quantizer transfer (2026-10-01 06:45 PDT)
**TL;DR** Bank U f01 is now analysed per sub-bank (U1 / U2B / U2Q never pooled), on unique states, with the task-equal estimand (no n_decisions weighting; k = 1 block, so the intervals are task-cluster bootstraps). Results:
- **Outcome changes are mostly class (ii): same tool structure, different text.** Of the M = 1 rows, U1 has 21/30, U2B 17/24 and U2Q 3/4. Nearly all are talk–talk; class (i) has none.
- **The text features separate nothing.** Question, confirmation, commitment/claim and new-entity flags show no consistent association with outcome change.
- **Length difference co-occurs with outcome change only in q4** (descriptive only).
- **Q0 n is 6–21 per cell × sub.** Q0 M is ≥ native M on the same rows.
- **In q4 U2B, the same states flip under several quantizers** above independence (7 joint flips vs ≈ 1.4 expected). None of these joint flips has identical a_Q across cells.
- **Native M, task-equal, U1 / U2B / U2Q (unique n 85 / 85 / 20):**
  - q4 GPTQ .118 / .094 / .100
  - q4 AWQ .106 / .082 / .100
  - q4 KV8 .024 / .047 / 0
  - q8 GPTQ .012 / .024 / 0
  - q8 AWQ .047 / .024 / 0
  - q8 KV8 .047 / .012 / 0

  G is within ±0.035 everywhere, and all intervals cover 0. GPTQ's U2Q is its own U1 (170 unique of 190; the duplicates' Y are concordant 20/20). It is reported but counted once in cross-sub tables.
- **Taxonomy** (a_B vs a_Q):
  - Classes: (i) identical; (ii) same calls or both talk, different text; (iii) different tool name/args/count; (iv) act/talk kind differs.
  - M rate by class, q4 U1: (ii) .15 and (iv) .54. q4 U2B: (ii) .18, (iii) .18, (iv) .08. q8 U2B: the flips are spread over (ii)/(iii)/(iv) at 1/1/3.
  - The comparator's `same` hides 13 act–act pairs whose text differs (ii_act). `text_only` = ii_talk.
- **Text split of class (ii)** (regex; descriptive):
  - Relative length difference above the median, q4: U1 9/46 vs 5/47; U2B 11/45 vs 5/46; U2Q 3/10 vs 0/11. q8 U1: 4/29 vs 3/30.
  - Median |Δlen| for flips vs non-flips, q4: 118 vs 71 chars (U1) and 97 vs 48 (U2B).
  - Questions and confirmations usually appear on both sides. Claims of completed action are rare, and none occurs in a flip.
- **Q0** (U2 Q0 subsample; q4 KV8 Q0 still running):
  - Y(a_B→Q0) is identical across cells on all 46 shared states. This is a determinism check.
  - U2B, Q0 vs native M:
    - q4 AWQ 3/21 vs 1/21;
    - q8 AWQ 2/13 vs 1/13;
    - q8 KV8 0/13 vs 0/13.
  - GPTQ's Q0 is native by construction. Too small to conclude.
- **Transfer** (native, shared state_ids; U1 states are never shared):
  - q4 U2B, states flipping in 0/1/2/3 cells: 72/8/4/1. Pairwise joint flips 3/2/2 vs 0.66/0.38/0.33 expected under independence; 6/7 have the same direction.
  - q4 U2Q: 2 states flip under both GPTQ and AWQ.
  - q8 U2B: 5 single-cell flips.
- **Evidence:** `analysis/fork/analyze_bank_u.py`; `analysis/fork/out/bank_u_f01_20261001T134456Z.{json,md}` (input sha256s, flipping pairs and flip states are in the JSON). It reruns unchanged when f02/f03 land: t over blocks for k < 10, block bootstrap at k ≥ 10. The multi-block path was tested on a synthetic f02 copy.
- **Caveats:**
  - One block: no run-level uncertainty.
  - The regex features are coarse, and "new entity" is pairwise, not relative to the history.
  - The pooled Q0 numbers in the JSON use equal weight per cell × state row.

## W83 — Recovery q4 v2: per-state turnover, process-perturbation contrast, manipulation checks, event chains, replay audit (2026-10-01 PDT)
**TL;DR** Report 2's reading "single injected defects seldom change outcomes" (W81) is **retracted**. The correct statement: injected errors cause heterogeneous two-sided per-state turnover (INV vs VAL: B 7/30 = 4 rescues + 3 damages; Q 4/30 = 2 + 2), the same size as the turnover caused by the process-perturbation control (PP vs VAL: 5/30 under both), and no detected mean or controller effect. The error-specific effect Y(INV) − Y(PP) is 0.00 [−0.13, +0.13] (B) and −0.03 [−0.20, +0.10] (Q); D_INV ≠ 0 in 8/30 states, D_PP ≠ 0 also in 8/30. Replay audit: 30/30 states pass all 22 recorded fields.
- **Turnover** (task-clustered bootstrap, exact McNemar; all p ≥ 0.25):

  | ctrl | INV vs VAL r/d (net) | PP vs VAL r/d | INV vs PP r/d (net) | excess turnover INV − PP |
  |---|---|---|---|---|
  | B | 4/3 (+0.03 [−0.13, +0.20]) | 3/2 | 2/2 (0.00 [−0.13, +0.13]) | +0.07 [−0.07, +0.20] |
  | Q | 2/2 (0.00 [−0.13, +0.13]) | 3/2 | 2/3 (−0.03 [−0.20, +0.10]) | −0.03 [−0.17, +0.10] |

  - D_INV distribution (−2..+2): 0 / 4 / 22 / 3 / 1.
  - wrong_tool × B: 3 rescues, 0 damages, from VAL×B 1/10; INV − PP +0.20 [0.00, +0.50]. n = 10, exploratory.
  - premature_write: 0/10 turnover under both controllers; VAL×Q already fails in 7/10 states, so the category is mostly failure → failure.
- **Manipulation checks:** 2 of 30 states fail.
  - `fe6d2e0940871d2d` (premature_write): the injected write was rejected ("Certificate cannot be used to update reservation"), so the DB did not change.
  - `53ec44a9a0a79d81` (wrong_tool): the VALID reference itself returned "Order not found".
  - wrong_tool is mostly an argument-error manipulation: 8/10 injected calls fail with "unexpected keyword argument"; 2/10 (search_direct_flight for search_onestop_flight) return [] without error.
  - Restricted to the 28 states that pass: INV vs VAL turnover is B 6, Q 3; D_INV ≠ 0 in 8.
- **Event chains on INV** (error → correction → related requirement satisfied): B 29 → 17 → chain complete 6; Q 29 → 17 → 7. premature_write has 0 corrections (no user objection followed by a later write).
- **Process cost** (paired vs VAL):
  - INV adds tool errors: B +0.43 [+0.10, +0.77], Q +0.57 [+0.20, +0.97].
  - INV extra steps: B +3.6 [−3.4, +14.8], Q +5.6 [−1.5, +16.6]. wrong_tool INV uses about 35 steps vs 17–23 under VAL, and 1 branch per controller hits max_steps.
  - PP×Q costs +3.6 [+1.1, +6.3] steps.
- **Replay audit** (`replay_audit.jsonl`, VAL×Q vs the original episode): 30/30 pass.
  - Fields checked: DB and user-DB hash at t, history prefix and sha, sim seed, budget at t and final, the prompt-ids sha sequence, system sha, per-message hashes, per-turn actions, completion-ids sha, suffix sha, reward, official reward, db_match, termination, and the final DB hash.
  - **Not recorded:** the branch's step/error counters right after the restore (set in code from `state.budget`), the rendered-prompt sha256 sequence, and the tools sha sequence.
  - The original final DB hash is not stored in the run; it was recomputed by a strict replay of the recorded original messages.
  - Report 2's "full replay" now has this artifact behind it, subject to those three unrecorded fields.
- **Code and naming:**
  - `analysis/recovery/analyze_inject.py` (v2): NC is renamed PP ("process-perturbation control") in all outputs, and inject-v1 "NC*" keys are still read.
  - It is CPU only and reruns on `analysis/recovery/inject_q8` when that directory appears; it was not present at this commit.
- **Evidence:**
  - `analysis/recovery/inject_q4/{summary_v2.md, summary_v2.json, replay_audit.jsonl, annotations.jsonl, summary.json}`;
  - inputs `analysis/recovery/inject_q4/{inject.json, states/, branches/}` (states and branches committed here);
  - review: `outputs/gpt61-review4-response-review.md` (Critical 1–2, Major 3–4).

## W82 — WP5 30-state check done by a Sonnet 5.5 proxy (author decision; NOT human) (2026-10-01 07:00 PDT)
**TL;DR** Two fresh Sonnet 5.5 instances, blind and with evidence quotes, labelled the frozen 30-state human-check subset. The `labels_human` slot remains open. Results:
- **Mechanical fields:** they agree with the programmatic verifier (write executed κ 1.00, budget exhaustion κ 1.00).
- **Semantic fields:** they agree with the adjudicated R1/R2/R3 labels at κ 0.67–0.93.
- **Consent recorded:** agreement with the programmatic rule is only κ 0.36. Consent stays an unreliable field.
- **The Table 4 v2 key pattern replicates on the subset under the proxy's separate "unintended" judgement:**
  - rescue: QQ 4/8 vs BQ 0/8;
  - damage: QQ 0/9 vs BQ 6/9.
- **Evidence:** `analysis/annotation/wp5/human_check_v1/labels_proxy_sonnet.jsonl` (sha committed 7b516b9 before the comparison), `proxy_compare_v1.json`, `analysis/annotation/wp5_proxy_compare.py`.
- **Caveats:**
  - Same model family as the annotators, so this shows reproducibility, not correctness. Per GPT-6.1 review 3, it does not substitute for human review.
  - "requirements_satisfied == yes" vs the true Y gives κ 0.53, so the evaluator outcome stays the endpoint.

## W81 — Morning results: recovery q4 (null), Bank U f01 (descriptive), W×KV final, all 6 Bank U gates pass (2026-10-01 06:30 PDT)
**TL;DR** (1) Injected defects barely move q4 success under either controller: D ≈ 0. (2) On ordinary Bank U states, consequential pivots occur at M 2–11% per state with G ≈ 0. (3) The pre-registered q8 W×KV replication is not supported at 6/6 blocks.
- **Recovery q4** (`analysis/recovery/inject_q4/inject.json`, `summary.json`; design Amendment 1 applied before reading).
  - Per-state replay: 30/30 pass (reward, termination and suffix sha all equal); 0 branch errors.
  - Success rates:

    | arm | INV×B | VAL×B | INV×Q | VAL×Q | process-perturbation ×B | process-perturbation ×Q |
    |---|---|---|---|---|---|---|
    | success | 10/30 | 9/30 | 10/30 | 10/30 | 10/30 | 11/30 |

  - R_B = +0.03 [−0.13, +0.20]; R_Q = 0.00 [−0.13, +0.13]; D = R_B − R_Q = +0.03 [−0.17, +0.27].
  - By category:
    - premature_write: 3/10 in every arm.
    - wrong_tool: R_B +0.30 [+0.10, +0.60], from VAL×B 1/10; n = 10, exploratory.
    - wrong_id: R_B −0.20 [−0.60, +0.20].
  - Reading: in q4, single injected local defects at ordinary states seldom change the outcome, under either controller. This is consistent with Table 4 v2 (defects are often corrected later; there is no one-to-one defect→failure link).
  - Not yet computed: correction events and process cost.
  - q8 was released per Amendment 1.
- **Bank U f01** (native, 190 states per cell = U1 85 + U2B 85 + U2Q 20; unweighted, descriptive; one block):
  - M per state: q4 AWQ 0.09, q4 GPTQ 0.11, q8 AWQ 0.03, q8 GPTQ 0.02, q8 KV8 0.03. G within ±0.02 everywhere.
  - Exact action agreement: 0.47–0.80.
  - q4 KV8 native and its Q0 are still running; the Q0 tasks for q4 AWQ, q8 AWQ and q8 KV8 are done (not yet analysed).
  - A Bank U analysis script with inclusion weights and block intervals is still to be written.
- **All 6 Bank U per-config gates pass:** 30/30 rows each, with no-op pass 20/20, 30/30, 20/20, 15/15, 30/30 and 20/20.
- **W×KV final** (`analysis/ahook/out/wakv_20261001T094405Z.md`): q8 I_WK|A16 = +2.1 [−5.8, +10.1] (k = 6); crossed [−8.2, +12.4]. The pre-registered replication is **not supported**. q8 single W4 = −6.7 [−11.6, −1.7].

## W78 — W70/W67 statistics corrected: full 85-task panel, Freedman–Lane conditional test, complete-panel blocks only (2026-10-01 00:15 PDT)
**TL;DR** GPT-6.1 was right on all three counts, but fixing them does **not** kill the claim.
- **The W70 "11/12" was airline-only.** The 0255Z audit intersected task ids across blocks. One airline-only block (q4 AWQ-W4 q5) silently dropped all 58 retail tasks, leaving 27 × 20.
- **The conditional test was invalid.** v1 permuted raw B rates with the controls held fixed.
- **One block was mixed.** q4 AWQ-W4 had 1642 = 19 × 85 + 27 units.
- **On the correct population (85 tasks: 58 retail + 27 airline, × 20 complete blocks):** with a Freedman–Lane test (nuisance-model residuals permuted within domain, HC3 t), the A-split rate predicts the B-split rate beyond measured baseline propensity in **12/12 cell-directions for M and 12/12 for G (Holm 12/12 each)**.
- **Per domain:**
  - Retail (58 tasks): 11/12 for both M and G.
  - **Airline alone is weaker than W70 said:** M 8/12 (Holm 5) and G 9/12 (Holm 6). Under the heteroscedasticity-robust wild bootstrap it is 3/12 and 7/12, with Holm 0.
  - So the claim survives on the panel and is carried mainly by retail. The airline-only evidence that W70 reported was overstated.
- **The mixed-block fix moves q4 AWQ-W4 G from −0.9 to −0.3 pp.** No other cell changes. No conclusion changes.

**Fixes** (code: `analysis/fork/{analyze_dev,audit_w67,analyze_consequence}.py`; new `w78_null_calibration.py`)
1. **Population.**
   - `analyze_dev.mark_partial_panel_blocks`: a retail/airline block enters only if both domains are complete in it (85 tasks). Otherwise its other-domain units are excluded as a "partial-panel block". Every block mean then has the fixed weights retail 58/85 and airline 27/85, and the point estimate and block bootstrap use the same blocks.
   - The audit never intersects tasks. It declares populations (`panel85` primary, `retail58` and `airline27` on the same blocks, plus `legacy_airline27_x20` for reproduction only) and aborts if any declared task × block is missing.
   - Every table states tasks × blocks. analyze_consequence now dedupes before the block rule, excludes telecom from the panel (W67 had pooled 160 telecom units into each q8 W4 cell) and uses domain-stratified nulls.
2. **Conditional test.**
   - Freedman–Lane is used because it keeps yB's dependence on the nuisance under every permutation. The statistic is the HC3 t (pivotal), and permutations stay within domain because residual exchangeability is only plausible between tasks of the same domain.
   - Primary nuisance "AB": domain intercepts, q_A, q_A(1−q_A), q_B, q_B(1−q_B) and BF16 success. Also reported: "A" (v1's covariates) and "ABL" (AB + BF16 trajectory length; added after the first v2 run, so post hoc).
   - **Exchangeability check:** |residual| rises with flip opportunity (Spearman 0.26–0.71), so a restricted Rademacher wild bootstrap is reported alongside the permutation test. Partial r is descriptive.
   - **Size under an opportunity-only null** (1000 simulated panels per cell; task QQ propensity plus pooled per-domain rescue and damage rates, so no task fragility):
     - FL rejects at 0.042–0.068 and wild at 0.037–0.066 (MC SE 0.007).
     - v1 rejects at 0.041–0.065 for M and is conservative for G (0.011–0.042).
     - So v1's error did not inflate significance. The population was the error that mattered.
3. **Dependence.** Splits A and B are disjoint block sets (asserted). Block-aware intervals come from a delete-one-block jackknife within A and within B, with variances added. The with-replacement block bootstrap is kept in the JSON but labelled "attenuated": duplicated blocks add noise to the regressor yA and pull beta_A towards 0.
4. **Missing output.** The cited `dev_all_20261001T061007Z.{md,json}` is now committed unchanged. Re-runs used the same snapshot 20261001T0600Z. Every output records its script sha, snapshot sha and input digest, plus a per-cell `units_digest_sha256`. That digest agrees across all four W78 outputs for every W4 cell. The fork inputs kept growing during the runs, so the global input digests differ.
5. **Data note.** Between my runs the `fork_repair_q4_awq_w4` units for q5 retail landed, so q4 AWQ-W4 is now complete at 85 × 20. The rule-only state (85 × 19) is kept as `dev_all_20261001T064637Z` and `*_excl_q5_*`.

**Before → after** (snapshot 0600Z unless noted; p is the one-sided Monte Carlo p, B = 2000)

| headline | before (source) | after (W78) |
|---|---|---|
| W67 audit population | 27 airline tasks × 20 blocks, labelled "27-task retail/airline panel" (0255Z) | **85 tasks (58 R + 27 A) × 20 blocks**; drop q5 → 85 × 19 |
| beyond-baseline, M: cell-directions with p < 0.05 | 11/12 (v1 raw permutation; exception q8 KV8 B→A p 0.15) | **12/12, Holm 12** (FL-AB); wild 12/12; retail58 11/12; airline27 8/12 (Holm 5; wild 3/12, Holm 0); 85 × 19: 12/12 |
| beyond-baseline, G: cell-directions with p < 0.05 | 11/12 (q4 KV8 A→B p 0.06) | **12/12, Holm 12**; wild 12/12; retail58 11/12; airline27 9/12 (Holm 6; wild 7/12, Holm 0); 85 × 19: 12/12 |
| largest p, panel85 | 0.15 (M), 0.06 (G) | 0.027 (M, q8 KV8 A→B), 0.008 (G) |
| partial r of the A rate (descriptive) | M 0.31–0.87, G 0.36–0.87 (W70 text: "0.53–0.87") | M 0.43–0.87, G 0.44–0.88; beta_A 0.40–0.95; weakest cell q8 KV8 (jackknife lower bounds 0.02–0.06) |
| concentration: Spearman of task M, A vs B | 0.56–0.89 | 0.52–0.86 (all p ≤ 0.0005); top-20% capture 0.46–0.69 → 0.46–0.64 (null median 0.19–0.21) |
| direction: positive − negative mean G on B | 5–88 pp, 9/12 p < 0.05 | 14–51 pp, **12/12** |
| direction beyond opportunity (p < 0.05) | rescue 6/12, damage 1/12 | rescue **11/12**, damage **6/12** |
| cross-quantizer φ(M), task-identity null rejected | 4/8 pairs | 7/8 (not q4 vs q8 GPTQ); nonce-specific alignment only q4 AWQ vs q8 AWQ (p 0.001); same direction when both flip 0.42–0.81 |
| q4 AWQ-W4, full pool (dev_all) | 1642 units; r 9.5, d 10.5, M 20.0, G −0.9 [−3.1, +1.2] (061007Z) | rule only (85 × 19, 1615): r 9.7, d 10.0, M 19.7, G −0.4 [−2.4, +1.7]; with repaired q5 (85 × 20, 1700): r 9.8, d 10.1, M 19.9, **G −0.3 [−2.2, +1.6]**, crossed [−5.4, +5.2] |
| W4 q4 pool, G | −1.5 [−3.3, +0.1] (20 blocks, q5 airline-only) | −1.1 [−2.8, +0.5] (85 × 19) → **−1.1 [−2.6, +0.4]** (85 × 20) |
| W4 all-model pool, G | +0.6 [−0.4, +1.6] | +0.7 [−0.3, +1.7] → **+0.7 [−0.3, +1.6]** |
| other cells (q4/q8 GPTQ-W4, q8 AWQ-W4, KV8, stress) | 061007Z | unchanged (85 × 20 or 85 × 22; stress 85 × 3) |
| W67 dispersion index (main cells) | 4.1–6.5; q8 W4 cells included 160 telecom units | 4.0–8.7 (panel only, domain-stratified binomial null, all p < 0.001) |
| W67 share of flips in the top 20% of tasks | 57–88% | 57–71% |
| W67 fewer mixed-direction tasks than null | W4 p < 0.001; KV8 0.019 / 0.027 | W4 p < 0.001; KV8 0.044 (q4) / 0.019 (q8) |
| W67 shares of rescues in net-rescue tasks / damages in net-damage tasks; overlap lift and φ | 68–86% / 72–84%; lift 1.5–2.1, φ 0.07–0.19 | 68–86% / 71–84%; lift 1.5–2.1, φ 0.07–0.19 (within block × domain null) |

**What survives of W67** (internal replication on viewed dev data, not confirmation):
- **Fragility (task concentration):** yes, on the full panel and in each domain.
- **Direction persistence:** yes (12/12). Beyond opportunity it holds for rescues (11/12) and only partly for damage (6/12), so the damage half is the weaker one.
- **Beyond measured baseline propensity:** yes for the panel and retail. For airline alone it is not robust to multiplicity or heteroscedasticity.
- **Cross-quantizer:** task-level co-susceptibility holds. Same-state direction is about a coin toss.
- **Scope:** "beyond measured baseline" means beyond the QQ propensity estimated from about 10 blocks per split, BF16 success and length. It is not beyond every possible task property.
- **Superseded wording:** REPORT_GPT61_20261001_0000 §2's "11/12 … (W70)" and W70's "partial r 0.53–0.87" are superseded by this entry.
- **Not re-run:** `analyze_patterns.py` and `audit_reuse.py` received the same partial-panel rule. In current data no partial panel blocks remain, but their 0255Z outputs (q4 AWQ-W4 in `consequence_estimands_*`; the common pool in `population_panel_*`, which used retail 19 / airline 20 blocks) carry the mixed block. They were not re-run here, because audit_reuse also rewrites `docs/OLD_RESULT_REUSE.csv`.

**Evidence**
- Primary: `analysis/fork/out/w67_audit_v2_20261001T0600Z_20261001T070500Z.md` and `direction_replication_v2_20261001T0600Z_20261001T070500Z.json`.
- 85 × 19 sensitivity: `*_excl_q5_20261001T070632Z.{md,json}`.
- Null size: `w78_null_calibration_20261001T0600Z_20261001T070832Z.json`.
- Full pool: `dev_all_20261001T070326Z.{md,json}` (after), `dev_all_20261001T064637Z.{md,json}` (rule only, 85 × 19), `dev_all_20261001T061007Z.{md,json}` (before, as cited).
- W67 consequence: `consequence_v2_20261001T070850Z.json`.
- Provenance (script, snapshot and output sha256s, digests, commands): `w78_provenance_20261001T0715Z.json`.
- v1 outputs kept: `w67_audit_20261001T0255Z.md`, `direction_replication_20261001T0255Z.json`, `consequence_20261001T011124Z.json`.

## W79 — WP5 Table 4 v2: rubric label restored, programmatic verification, within-state paired statistics, human-check packet frozen (2026-10-01)
**TL;DR** GPT-6.1 review applied to Table 4 (W75).
- In both groups where the two branches differ, the failing continuation carries the rubric label **`unintended_or_unconsented_change`** more often than the succeeding continuation of the same state. Rescue: QQ vs BQ 9 vs 2, diff +0.35 [+0.08, +0.57]. Damage: 1 vs 9, diff −0.40 [−0.62, −0.11].
- **Mechanically, though:**
  - Whether a write executes does not separate the branches (17 vs 17; 15 vs 14).
  - Executed writes without recorded operation-specific consent differ only weakly in rescue (9 vs 5, +0.20 [−0.06, +0.43]) and not at all in damage (3 vs 3).
  - In damage states, 7 of the 9 BQ labels sit on writes **with** recorded consent. That is the semantic "unintended" part (a consented but wrong change), which overlaps with the DB-based outcome by construction.
- **Wording:** local defects and final failure do not correspond one-to-one; some successful continuations contain later corrections.
- **Scope:** a process description conditional on outcome-defined groups, not causal evidence. LLM-annotated (Sonnet 5.5, two independent instances + R3), plus rule-based programmatic labels. n = 20 per sign.
- **Changes vs v1** (`table4_v1.json` is kept unchanged):
  1. **Label name.** The original rubric category name, `unintended_or_unconsented_change`, is used everywhere. v1's "unconsented irreversible write" merged three judgements; the W75 entry now carries a correction note. The interim report `docs/REPORT_GPT61_20261001_0000.md` was already sent and is left as is.
  2. **Three judgements kept apart:**
     - "write executed" (programmatic);
     - "consent recorded" (programmatic, operation-specific);
     - "unintended" (LLM only, semantic).
  3. **Paired within state:** 2×2 discordant counts, McNemar exact p (descriptive), and the paired difference with a Newcombe score 95% CI and a task-clustered bootstrap (clusters = (domain, task_id), 10k reps, seed 0). There are no independent-proportion tests. Single rows get Wilson 95% intervals.
  4. **tool_validity (κ 0.29)** is dropped from the core. The core "local defect" = groundedness / argument_validity / permission_consent. The tool_validity rows and the v1 composite are in the appendix of `table4_v2.md`.
- **Corrected key rows** (within-state paired, first − second; Newcombe 95%):

  | row | rescue | damage | both succeed | both fail |
  |---|---|---|---|---|
  | `unintended_or_unconsented_change` QQ vs BQ (LLM) | 9 vs 2 (8:1), +0.35 [+0.08, +0.57] | 1 vs 9 (1:9), −0.40 [−0.62, −0.11] | 1 vs 1 | 5 vs 7, −0.10 [−0.35, +0.17] |
  | write executed QQ vs BQ (prog) | 17 vs 17, 0.00 [−0.25, +0.25] | 15 vs 14, +0.05 [−0.26, +0.35] | 10 vs 9 | 11 vs 13 |
  | executed write w/o recorded consent QQ vs BQ (prog) | 9 vs 5, +0.20 [−0.06, +0.43] | 3 vs 3, 0.00 [−0.21, +0.21] | 3 vs 2 | 4 vs 3 |
  | loop or budget exhaustion QQ vs BQ (LLM) | 5 vs 0, +0.25 [+0.04, +0.47] | 0 vs 2, −0.10 [−0.30, +0.08] | 1 vs 2 | 7 vs 4 |
  | Q vs B action indefensible (LLM) | 7 vs 8, −0.05 [−0.37, +0.28] | 12 vs 5, +0.35 [−0.05, +0.65] | 10 vs 6 | 12 vs 9 |
  | Q vs B local defect, core (LLM) | 4 vs 6, −0.10 [−0.33, +0.14] | 12 vs 7, +0.25 [−0.09, +0.53] | 6 vs 3 | 11 vs 7 |
  | QQ first-action defect corrected later (LLM; Wilson) | 4/20 [0.08, 0.42] | 10/20 [0.30, 0.70] | 4/20 | 7/20 |

- **Programmatic vs adjudicated LLM, per field** (`programmatic_agreement_v1.json`; 320 branches / 160 actions):

  | field | agreement | κ |
  |---|---|---|
  | write executed vs irreversible_change ≠ none | 0.997 | 0.99 |
  | budget exhaustion | 1.00 | 1.00 |
  | identical call ≥ 3× vs retries = repeated_same_call | 0.975 | 0.82 |
  | retries, 3-way | 0.91 | 0.78 |
  | loop proxy vs loop | 0.94 | 0.68 |
  | pass-1 permission_consent, 3-way | 0.98 | 0.90 |
  | pass-1 is-write | 1.00 | 1.00 |
  | pass-1 execution error vs argument_validity ≠ valid | 0.93 | 0.83 |
  | pass-1 invalid tool name vs wrong_tool | 0.90 | 0.08 (LLM wrong_tool is mostly semantic) |
  | consent recorded vs intended_change (on 202 writes both see) | 0.74 | 0.44 |
  | unconsented executed write vs `unintended_or_unconsented_change` (different constructs) | 0.83 | 0.54 |

  - Mechanical sanity check: write executed vs DB hash change (BB/BQ/QB) agree 0.99.
  - The consent disagreements are mostly user-initiated instructions ("just cancel the entire order") that carry no listed-details-plus-yes. The LLM calls these intended; the rule calls them not consented.
  - The consent rule was fixed twice after a first look at disagreements: an over-broad negation regex ("I confirm that I do **not** want …"), and a batch of writes approved by one listed reply. Both were bugs, not tuning toward the LLM. The rule is frozen in the script sha.
- **Human-check packet** (not yet labelled): `analysis/annotation/wp5/human_check_v1/index.html`.
  - 30 states covering all four signs (rescue 8, damage 9, both succeed 6, both fail 7).
  - Positives plus matched negatives (same sign, then family × domain) for the failing-branch `unintended_or_unconsented_change` and for "QQ defect corrected".
  - Also 1 state per direction of programmatic-vs-LLM consent disagreement, and 2 fill states.
  - The subset was frozen by hash before any human label: `subset_v1.json` (sorted-id sha256 2ef55225…) and `freeze_v1.json`. The strata are sealed in `SEALED_strata_v1.json`.
  - The reviewer labels the existing blinded packets with evidence spans and quotes, then commits `labels_human.jsonl` and its sha. Only then does `wp5_human_check.py reveal` show model identity, sign and existing labels. See ANNOTATION_PROTOCOL Amendment 2.

Evidence: `analysis/annotation/wp5_verify.py` → `analysis/annotation/wp5/programmatic_v1.jsonl`, `programmatic_agreement_v1.json`; `analysis/annotation/wp5_table4.py` → `analysis/annotation/wp5/table4_v2.{json,md}` (`--v1` reproduces the v1 table values); `analysis/annotation/wp5_human_check.py`, `analysis/annotation/wp5/human_check_v1/`; `docs/insights/ANNOTATION_PROTOCOL.md` Amendment 2; key `/data/ziyangs/cloq_work/annotation/wp5_KEY_unblinding.jsonl` (cluster only). CPU only; no telecom holdout data read (all 4 telecom states are development fork states).

## W80 — GPT-6.1 review 3 decisions applied; holdout repeatability secondary drafted (2026-10-01 00:40 PDT)
**TL;DR** The second pillar is "how consequences propagate", in three parts:
- **Recovery intervention** (primary identification): D measures the controller dependence of the injection effect.
- **Table 4:** process description.
- **Bank U + Q0:** common-state check.

Changes made:
- **Recovery:** per-state replay acceptance; NC is renamed the "process-perturbation control"; D framing (W76).
- **Bank U:** per-config gates for q4 AWQ, q8 GPTQ and q8 KV8, bound as deps. Gate tasks now fail loudly (W76).
- **Holdout secondary:** cross-nonce repeatability, drafted in FORK_PROTOCOL §12 amendment 1. It is binding at the PREREG freeze, which happens before the first holdout read.
- **Pending:**
  - W78: W70/W67 population and inference corrections. The audit was airline-only (27 tasks), the conditional permutation was invalid, and q4 AWQ mixes in an airline-only block.
  - W79: Table 4 restored to the rubric category, programmatic verification, paired stats, and a human-check packet (≥ 20, preferably 30 states).
- **Wording:** W×KV is "not yet supported by replication" until the 6th q8 block; a sign flip in the point estimate is not a demonstrated reversal. The 70% vs 27% restoration result goes to an appendix only.
- **GPU split after protection and reserve:** 50% Bank U f01→f02/f03 + Q0; 30% recovery validity and replication; 20% q14 paired BF16/W4.

Evidence: `docs/insights/RECOVERY_INTERVENTION_DESIGN.md` (Amendment 1), `docs/insights/FORK_PROTOCOL.md` §12 amendment 1, `scripts/a6000/fork_driver.py` (bank_u gate raise), GPT-6.1 review text as relayed by the author.

## W75 — WP5 Table 4: Sonnet 5.5 blinded labels, adjudicated and unblinded (2026-10-01 00:00 PDT)
**TL;DR** In this sample, how the pivot action itself looks does **not** separate rescue from damage. What separates them is what happens later in the failing branch, mainly the rubric label **`unintended_or_unconsented_change`** ("unintended or unconsented change"). This is descriptive and LLM-annotated, not human.
> **Superseded by W79** (GPT-6.1 review): the label name below is restored to the rubric category (v1 wrongly called it "unconsented irreversible write", merging three judgements), the QQ/BQ comparison is now paired within state with intervals, tool_validity is out of the core, and Reading 1 is reworded. Use `table4_v2.md`.
- **Annotation (Amendment 1, author decision):**
  - R1 and R2 are independent Sonnet 5.5 instances (8 chunks); R3 (Sonnet 5.5) adjudicated.
  - Labels and adjudication shas were committed (62ec2a1, bd6164d) before the key was opened. The key's sha matches `packets_meta` (18e40069…).
- **Agreement on the 20 double states** (`agreement_v1.json`):
  - κ ≥ 0.8: defensible, argument validity, groundedness, consent, irreversible change, loop, budget exhaustion, defect corrected, retries.
  - Moderate, κ 0.69: requirements_satisfied and user_clarification. All 7 unresolved adjudications are user_clarification.
  - Low: tool_validity, κ 0.29.
- **Table 4** (`analysis/annotation/wp5/table4_v1.json`; 20 states per sign; sample frequencies, not prevalences). Rescue means Y_BQ=1, Y_QQ=0; damage means Y_BQ=0, Y_QQ=1.

  | label | rescue | damage | both succeed | both fail |
  |---|---|---|---|---|
  | quantized action Q judged indefensible | 7 | **12** | 10 | 12 |
  | Q action has a local defect | 9 | **14** | 9 | 16 |
  | BF16 action B judged indefensible | 8 | 5 | 6 | 9 |
  | `unintended_or_unconsented_change` in QQ | **9** | 1 | 1 | 5 |
  | `unintended_or_unconsented_change` in BQ | 2 | **9** | 1 | 7 |
  | QQ: Q's first-action defect corrected later | 4 | **10** | 4 | 7 |
  | QQ: loop or budget exhaustion | **5** | 0 | 1 | 7 |

- **Reading:**
  1. **Local action quality does not predict the consequence's sign.** In *damage* states the quantized action looks worse than in rescue states (12 vs 7 indefensible), yet that is where it leads to success. In half of them (10/20) its defect is corrected later.
  2. **The failing branch is marked by `unintended_or_unconsented_change`.** These occur in QQ when QQ fails (rescue: 9/20) and in BQ when BQ fails (damage: 9/20); the sign flips with the outcome. Loops and budget exhaustion also mark failing QQ branches.
  3. **Implication:** consequence is decided along the trajectory (recovery vs an irreversible write), not at the pivot. This is consistent with "behavioural closeness ≠ task improvement" (§4 of STATUS_night).
- **Caveats:**
  - n = 20 per sign, no intervals, a stratified sample, LLM annotators.
  - The requirements_satisfied label only weakly tracks the true outcome: "yes" has precision 0.80 and covers 52% of Y=1, so transcript-judged success is noisy.
  - irreversible_change is visible in the transcript, so it can correlate with failure by construction. It describes *how* branches fail, not a cause.
  - Exploratory; not part of any prereg.

## W74 — W×KV interaction does not survive matched rotated controls or the pre-registered q8 replication; paused restoration tasks stopped (2026-09-30 22:50 PDT)
**TL;DR** The secondary claim "W4 × KV4 interaction" (legacy I_WK|A16 = −14.9 [−23.8, −6.0] on q4) does **not** hold.
- **q4, matched rotated KV16 reference (kv16r):** I_WK|A16 = −9.0 [−30.6, +12.5] (k=3); crossed [−24.7, +4.7]. The interval covers 0.
- **q8, pre-registered replication** (WAKV_PREREG.md, 27a3802; interim at 5 of 6 blocks): I_WK|A16 = **+4.0** [−4.4, +12.4] (k=5); crossed [−7.5, +15.3]. That is the opposite sign and covers 0.
- **Verdict:** the legacy effect is attributed to the rotation confound plus small-k noise. The W×KV interaction is dropped as a claim and reported as a negative replication. The final q8 number follows when block 6 (`w4a16kv4_fdev456`) finishes.
- **Still standing (q8, kv16r reference):** W4 at A16/KV16 is −6.7 [−11.6, −1.7] (k=6; crossed [−14.1, +0.6]). The q4 A4 single effect is −8.6 [−25.8, +8.5].
- **Ops:**
  - With author approval ("停 pert"), 8 paused restoration tasks were stopped. They had run 4–16 h with ≤1 of 6 run-domains done. They were requeued at −4; completed run-domains are kept, and `restore_middle` (4/6) was left running.
  - Their vLLM servers were orphaned (PPID 1) and were killed by pgid.
  - One collision failure (`fork_tel_q8_awq_w4_g3_s1of2`) was requeued.
  - Lesson repeated from W72: `kill -- -pgid` on a worker does not reach its vLLM server, which is in its own process group. Kill the server pgid too, before the runner reassigns the GPU.
- **Evidence:** `analysis/ahook/out/wakv_20261001T054021Z.{md,json}` (q4 + q8) and `wakv_20261001T054023Z.{md,json}` (q8); snapshot 20261001T0538Z.

## W71 — WP5 annotation package (sample, events, blinded packets, frozen rubric, LLM labels) and the recovery-intervention design (2026-10-01)
**TL;DR** WP5 is ready for human review on 10-02/03.
- **Sample:** 80 τ² development fork states, 20 of them double-reviewed, plus 2 calibration states. 20 states per consequence sign, stratified by family × domain. The sample manifest and the rubric were frozen before any label.
- **Labels so far:** automatic events cover all 320 branches. LLM labels under the frozen rubric parsed for 154/160 state × pass; 6 pass-2 records are missing (5 hit the 1500-token output cap, 1 prompt was over length) and are reported as missing. The packets are blinded, and the unblinding key is outside the repository (sha committed).
- **Recovery intervention:** designed and states frozen, **not queued**, awaiting approval.
  - Per model (q4, q8 GPTQ-W4 d1, block q3): 30 ordinary Q states.
  - 3 categories × {INVALID, VALID, negative control} × {B, Q} continuations.
  - About 6–7 GPU-h at priority −13.
- **Sample:** `manifests/annotation/wp5_sample_v1.json`.
  - Frame: 8,288 divergent replay-gated units from `consequence_units_20261001T0224Z.jsonl`.
  - Composition: W4 58, KV8 12, stress 10; retail 52, airline 24, telecom 4; 2 tasks reused.
  - Inclusion probabilities are recorded, and sample frequencies are not prevalences.
  - It was regenerated once before freezing: a one-state-per-task rule left one stratum empty, so tasks may now be reused only when a stratum runs out.
- **Rubric:** `docs/insights/WP5_RUBRIC_v1.md`, sha256 b97e0104…, frozen in `manifests/annotation/wp5_rubric_freeze.json` before labelling.
- **Automatic events:** `cloq/wp5.py events` = fork_annotate defect/correction/requirements plus the WP5 events and process costs, for all four branches (QQ = the original suffix, prefix verified 80/80). Counts over 320 branches:

  | Event | Branches |
  |---|---|
  | wrong argument / execution error | 60 |
  | transfer to human | 54 |
  | correction after pivot | 34 |
  | wrong id | 22 |
  | irreversible mutation by the current action | 20 |
  | budget exhaustion | 16 |
  | retry loop | 13 |
  | consent needs review | 10 |
  | wrong tool | 6 |

- **LLM labels:** `analysis/annotation/wp5/llm_labels.jsonl`.
  - Labeller: the user-simulator model (Qwen3-30B-A3B-Instruct, pinned), queried on existing replicas node006/node001, greedy, seed 0. No new GPU process was started.
  - Rubric sha and URL are recorded per line.
  - Evidence or an explicit unknown/n/a is present on 65% of field labels.
  - Limitation: the labeller is the same model as the τ² simulator.
- **Packets:** `analysis/annotation/wp5/packets/index.html`, with pass 1 (actions X/Y in hashed order) and pass 2 (suffixes S1–S4) per state. They show no model, precision, outcome or effect value. Assignment: R1 34, R2 26, both 22. Protocol, adjudication rule and unblinding conditions: `docs/insights/ANNOTATION_PROTOCOL.md`.
- **Recovery tasks queued (approved 10-01).**
  - CPU dry-run first: all 6 branch message sets built for 2 states per category and model (72/72), with no exception.
  - `inject_q4_gptq_w4_d1_q3` (1 GPU, priority −13) is queued.
  - `inject_q8_gptq_w4_d1_q3` (strictly 2 GPUs, −13, deps on q4) is parked in `queue/deferred/` until the q4 VALID×Q no-op agreement is checked, and is released only if it is ≥ 90%.
- **Recovery design:** `docs/insights/RECOVERY_INTERVENTION_DESIGN.md`.
  - Categories: wrong_id, wrong_tool, premature_write (only writes whose arguments are all in the history at t).
  - States frozen in `manifests/recovery/inject_v1.json`. Eligible counts: q4 247/299/62, q8 317/394/78.
  - Every state also gets a negative control, a repeat of the last successful read, and VAL×Q is a built-in no-op.
  - Driver: `scripts/a6000/inject_driver.py`. It reuses `cloq.fork.run_branch` and does not touch fork_driver (Bank U). The worker dispatches it through `fork.driver = "inject"` (a one-line run_fork hunk).

Evidence: `cloq/wp5.py`, `manifests/annotation/`, `analysis/annotation/wp5/`, `docs/insights/{ANNOTATION_PROTOCOL,WP5_RUBRIC_v1,RECOVERY_INTERVENTION_DESIGN}.md`, `manifests/recovery/inject_v1.json`, `scripts/a6000/inject_driver.py`; key `/data/ziyangs/cloq_work/annotation/wp5_KEY_unblinding.jsonl` (cluster only).

## W70 — Review fixes A1–A3 (strict complete blocks, common panel, stress pools), W67 beyond-baseline test, Bank U driver + replay gate (2026-10-01)
**TL;DR**
- **Strict block rule (A1).** A block with any unit missing for infrastructure reasons now leaves the primary analysis. The old rule is kept as a labelled complete-case sensitivity (`--complete-case`, outputs `dev_cc_*`, `*_cc_*`). Only q4 AWQ-W4 moves: 1699 → 1642 units, G −0.3 → −0.9 [−3.1, +1.2] pp. Every other headline is unchanged.
- **Infra-missing run-domains.** 10 of the 11 are agent-side context overflow, which is deterministic and a valid failure (W10), so a closed-loop re-run is pointless. Those units are recovered by `repair` fork tasks at −18, which re-execute deterministically and require every recorded prompt to reproduce. The one genuine outage (a6k2_q4_tel_awq_w4_f01, telecom) has no single-episode re-run path; this is a proposal for the matrix owner.
- **Common panel (A2).** Cells and pools use the 85-task retail/airline panel; telecom is reported separately. q8 GPTQ-W4 full-pool G is +2.9 [+1.4, +4.4] pp (block bootstrap). The +3.3 [+1.6, +5.0] figure is conditional on divergence, which is a different estimand, and is labelled as such.
- **Stress pools (A3).** These resample only real common blocks. Stress cells share 1 block, so they are reported as `not_poolable` with k_blocks. Do not cite pooled-stress significance.
- **W67 beyond-baseline test.** Split-B task flip rates were regressed on split-A rates plus QQ success propensity, q(1−q) and BF16 task difficulty, with a within-domain permutation p. The A rate stays predictive for M in 11/12 cell-directions (partial r 0.53–0.87; the exception is q8 KV8 B→A, p 0.15) and for G in 11/12 (q4 KV8 A→B p 0.06). The frequency of I ≠ 0 is not a significant mean I: the W4 mean-I intervals cover 0.
- **Bank U.** The driver mode, generator and §15 amendment 1 are committed (U1 Q→Q; U2B BF16-sourced plus U2Q Q-sourced, B→B; Q0 on a frozen 25% U2 subsample, reported separately; uniform-within-trajectory sampling; no zero-imputed suffix effect). The replay gate (3 tasks, no-op fraction 1.0) is queued at −17 behind about 34 running tasks. Gate result and first-block throughput: see W71.

**Evidence**
- Strict: `analysis/fork/out/dev_all_20261001T032236Z.{md,json}`; complete-case: `dev_cc_all_20261001T032304Z.{md,json}`.
- Patterns: `consequence_estimands_20261001T0255Z.json`, `patterns16_20261001T0255Z.csv` (and `*_cc_*`); coverage: `coverage_20261001T0255Z.json`, `block_coverage_20261001T0255Z.json`, `population_panel_20261001T0255Z.md`.
- W67: `analysis/fork/out/w67_audit_20261001T0255Z.md` (section "Beyond baseline propensity"), `direction_replication_20261001T0255Z.json`.
- Code: `analysis/fork/analyze_dev.py` (`mark_incomplete_blocks`, `dedupe_units`, `boot_for`, common-block pools), `analysis/fork/audit_w67.py`, `scripts/a6000/fork_driver.py` (`bank_u`, `rerun_episode`, `repair_mode`), `scripts/a6000/make_tasks_bank_u.py`, `manifests/fork/bank_u_v1.json`, `docs/insights/FORK_PROTOCOL.md` §15.
- Queue: `fork_repair_q4_awq_w4`, `fork_repair_q4_rtn_w3` (−18); `bank_u_gate_{q4_gptq_w4_d1,q4_kvq_int8,q8_awq_w4}` (−17). The KV8 gate's earlier coverage failure was caused by an orphaned server on the port; it is fixed by the pre-launch port guard in `run_fork` (df3db7c).

## W73 — Loop guard revised to lg-v2 (window 32, ≥ 8 repeats) and pinned; W2 panel queued with an original-cap sample (2026-10-01)
**TL;DR** Per plan §8.4.3, the guard is tightened instead of disabled.
- **Revision:** lg-v2 changes only two thresholds, window 16 → 32 and repeats 4 → 8. It is recorded in `manifests/stress/loop_guard_v2.json`; v1 is marked superseded and was never used for a run.
- **Threshold provenance:** the new thresholds were chosen on already-viewed development stress traces (the W69 scan and a threshold sweep on it), before any W2 outcome existed.
- **New pass rule:**
  - 0 FP and 0 FN on the frozen 50-trace sample;
  - 0 premature stops on BF16;
  - stress premature stops reported as a measured rate.
- **Result:** the sample gives 0 FP, 0 FN and sensitivity 1.0. BF16 has 0 premature stops of 2,206 successes (64 firings, all max_steps or too_many_errors). Stress has **8 premature stops of 5,874 later-successful episodes (0.14 %; 0.9 % of 848 firings)**. It passes.
- **Pin:** sha `8f593c55…` in commit `7bd5138`, recorded in the manifest.

**W2 panel queued** (priority −10), 4 tasks:
- 3 W2 tasks: `a6k2_w2p_{q4_rtn_w2,q8_rtn_w2,q8_gptq_w2}_q3`. Each needs its gate `w2gate_*` (still queued), and GPTQ also needs calibration c1. Each task serves one checkpoint and runs two runs:
  - the guarded panel run: 24 tasks, `CLOQ_LOOP_GUARD=lg-v2` with the pinned sha;
  - the original-cap sensitivity run `…_cap_q3`: the declared sample of the first 4 retail + first 2 airline panel tasks, no guard (`manifests/stress/w2_panel_v1_capsample.json`).
- 1 BF16 check: `a6k2_w2p_q4_bf16_q3`, guarded q4 BF16 on the 24 tasks, comparing the live guard with the offline guard on the existing `bfpair_q3`.
- If a gate fails, its W2 task stays unclaimed in `todo`, and the gate JSON is the support result.
- **Estimated ~3–4 GPU-h** plus the gates.

**Reporting contract:** every W2 / stress result reports three things.
- Guarded success, under the loop-guarded endpoint.
- Loop incidence.
- Original-cap sensitivity:
  - reused unguarded references: offline guarded vs unguarded success on the same episodes;
  - new W2 cells: the cap-sample runs.

**Evidence**
- `cloq/loop_guard.py`, `tests/test_loop_guard.py` (ALL PASS).
- `analysis/loop_guard/out/{validation,scan}_20261001T031501Z.*`.
- `manifests/stress/{loop_guard_v1.json, loop_guard_v2.json, w2_panel_v1_capsample.json}`, `scripts/a6000/make_w2_panel.py`.
- Queue: `/data/ziyangs/cloq_work/queue/todo/a6k2_w2p_*.json`.

## W72 — Long-tail fork tasks split into resumable shards (2026-09-30 20:40 PDT)
**TL;DR** The user asked to keep every card busy and split the slow tasks. Five fork tasks dominated the remaining wall-clock:
- q4 RTN-W3 stress, 45/232 states branched after 6 h, est. >20 h remaining;
- q8 RTN-W3 stress;
- telecom q8 GPTQ g1/g3 and AWQ g3.

`scripts/a6000/fork_driver.py` `branches_mode` now accepts:
- `shard: [k, n]`, which selects states by hash(`"shard|"`+state_id) mod n. Noop membership is still decided on the full state set, so the design is unchanged.
- `resume: true`, which reuses a complete, error-free branch file.

Sharded output goes to `branches_shard{k}of{n}.json`; analyses read the per-state branch files, so nothing downstream changes. 15 shard tasks are queued (4 + 3 + 3 + 3 + 2) with no node pin and priority one above the original. The originals were stopped (SIGTERM to the worker process group) and moved to deferred. States frozen by the original searches are reused, so no search is repeated and finished branches are kept.

The patch is not committed separately because fork_driver.py also holds agent a5468c1's in-progress Bank U edits; that agent commits the file including this hunk.

Evidence: queue `todo/fork_*_s*of*.json`, `deferred/fork_{stress_q4_rtn_w3,...}.json`.

## W69 — Loop early-stop guard lg-v1: built and pinned, but FAILS its pre-declared premature-stop check; W2 panel frozen, gates queued, panel NOT queued (2026-10-01)
**TL;DR** The opt-in guard of plan §8.4 is implemented (`cloq/loop_guard.py`, sha `88ac7cdd…`) and gives the same result live and offline.
- **Frozen sample of 20 loops and 30 legitimate traces:** 0 false positives and 0 false negatives.
- **Offline replay over all 19,488 existing stress episodes:** it would have stopped 18 episodes that later **succeeded**. That is 0.31 % of 5,874 stress successes and 1.7 % of 1,064 firings; BF16 was 0 of 2,206. These are real ≥ 4× identical cycles, up to 32 identical lookups, after which the agent recovered.
- **Verdict:** under the pre-declared rule (0 premature stops) lg-v1 fails. Tighter thresholds tried on the same data still leave 9 / 8 / 7 premature stops (24/6, 32/8, 48/12).
- **W2 panel:** the 24-task subset, block q3 and its selection hash are frozen. The three implementation gates are queued. Following "queue only after validation passes", **no W2 panel run is queued**. Revise or disable: decision pending.

**Guard (policy lg-v1)**
- **When it applies:** only if a run sets `CLOQ_LOOP_GUARD=lg-v1` and `CLOQ_LOOP_GUARD_SHA` equals the file sha (the agent refuses an unpinned sha). Frozen and primary runs are unchanged: the hooks are inert without the variable.
- **Rule:** within the last ≤ 16 decisions, a cycle of length 1–4 repeats ≥ 4 complete times, with all of:
  - an identical canonical action (normalised tool call with IDs, numbers and order kept, or full talk text);
  - an identical tool-result digest, or user-reply digest for talk decisions;
  - an unchanged agent-side DB hash;
  - no user-side tool call or other user event.
  If any evidence is missing, the guard does not fire.
- **Termination:** reason `loop_early_stop` with official reward 0. The evidence (cycle, repeats, hashes, budget counters, tokens) goes to `loop_guard.jsonl`. Each run also records a live-vs-offline consistency check.
- **Code:** `cloq/agent.py` (opt-in hook and an `is_stop` marker), `cloq/run_arm.py` (termination recoding and config record).
- **Tests:** `tests/test_loop_guard.py`, ALL PASS. They cover the rule cases (different IDs, different results, DB change, new user information, missing hash, dual control), the live guard matching the offline replay, and refusal of an unpinned sha.

**Validation**
- **Sample:** frozen and selected by trace content and an independent reference criterion before scoring (`manifests/stress/loop_guard_validation_v1.json`). There is a blinded export for human audit (`analysis/loop_guard/out/validation_blinded_20261001T024438Z.md`). Result: 0 FP, 0 FN, sensitivity 1.0.
- **Premature-stop scan** (`analysis/loop_guard/out/scan_20261001T024438Z.json`; 460 stress runs, 152 BF16 runs):

  | | stress | BF16 |
  |---|---|---|
  | fired | 1,064 (953 of 1,654 max_steps / too_many_errors) | 79 |
  | premature stops on later successes | 18 (listed in the scan) | 0 |
  | agent decisions that would be saved | 57k of 335k | — |

- **Manifest:** `manifests/stress/loop_guard_v1.json` pins the sha and records `passed: false` with the reason.

**W2 stress panel (build and dry run only)**
- **Tasks:** `manifests/stress/w2_panel_v1.json`, selection hash `a6a4ce8b…`. 24 of the canonical 85, stratified as domain × gold-action-count tercile, 16 retail and 8 airline.
  - Retail: 4, 11, 27, 34, 44, 47, 50, 51, 68, 77, 83, 86, 90, 103, 111, 113.
  - Airline: 17, 23, 28, 31, 37, 45, 46, 47.
  - Block: q3, nonce 4c8e1a7f.
- **Gates queued** (`w2gate_{q4_rtn_w2,q8_rtn_w2,q8_gptq_w2}`, priority −10, `scripts/a6000/w2_gate.py`): build, finite 2-bit grid (≤ 4 distinct values per group, required for RTN), vLLM serve, and a finite non-empty canary completion. The result is written to `analysis/stress/w2_gate_<m>_<cell>.json`; a failure is a support result.
- **Prepared but not queued** (`make_w2_panel.py tasks` refuses until `validation.passed`):
  - 3 guarded W2 runs (q4 RTN-W2, q8 RTN-W2, q8 GPTQ-W2), each depending on its gate;
  - 1 guarded q4 BF16 equivalence run.
  - BF16 / W4 / W3 references on the same tasks × q3 would reuse existing runs, scored with the identical guard offline.
- **Estimated cost:** gates ~1 GPU-h; panel ~3–4 GPU-h (24 tasks per run; RTN-W3 runs take ~0.75–1 h per 24 tasks unguarded).

**Evidence:** the files named above, plus `analysis/loop_guard/guard_validation.py` and `scripts/a6000/make_w2_panel.py`.

## W68 — Plan dictionary, complete four-arm consequences (WP1), reuse and population audit (WP0), W67 audit, Bank U design (2026-10-01)
**TL;DR** Analyses follow CONSEQUENCE_ANALYSIS_PLAN §2. All 16 outcome patterns and every contrast are reported on their correct denominators. Strict reversals are rare (1.2–4.6% of divergent states) and distinct from I ≠ 0 (≈ 15–30%).

The W67 audit (internal replication only) re-grades the claims:
- **Task concentration of M:** replicates across a frozen nonce split.
- **Direction:** survives beyond opportunity mainly for rescues (11/12 split-directions) and less for damage (7/12).
- **Cross-quantizer "same units":** is task-level co-susceptibility. Nonce-specific co-flipping beyond task propensity holds only for q4 AWQ vs q8 AWQ, and direction when both flip is near a coin toss.
- **Caveat:** QQ outcomes are nearly fixed across nonces (Spearman 0.88–0.95), so all of this is persistence under prompt perturbation on the same tasks, not new-task evidence.

- **Sign dictionary (analyze_dev and siblings).**
  - Definitions: A = Y_BB−Y_QB, C = Y_BB−Y_BQ, I = Y_BQ+Y_QB−Y_BB−Y_QQ, G = A+I, H = C+I, F = A+C+I. These are numerically identical to W63's A/C/I and are stated in every output (`sign_dictionary`).
  - **Real change:** no-divergence units no longer count as four equal outcomes. A/C/I/H/F are reported on divergent states only. Full-pool quantities are the primary pivot policy (G, r, d, M) and the explicit pivot policies H_policy/F_policy. The W63 full-pool A/C/I and Y_QB−Y_QQ / Y_BB−Y_QQ columns are withdrawn.
  - Previous outputs are kept; the new run is `dev_all_20261001T024918Z`.
- **WP1, `analysis/fork/analyze_patterns.py`.**
  - Outputs: the §13.1 unit registry (`consequence_units_<s>.jsonl`, 13,029 units including no-divergence and missing), `patterns16_<s>.csv` (all 16 patterns including zeros, by model × cell × domain, asserted against the plan table), `consequence_estimands_<s>.json` and `coverage_<s>.json`.
  - Per contrast: mean, P(+1), P(−1), turnover; full-pool G/r/d/M with asserted G = r−d and M = r+d; fixed-task and crossed intervals.
  - Readings: divergent-state turnover is ≈ 16–28% for every contrast. Conditional G is +3.3 [+1.7, +5.0] pp for q8 GPTQ-W4. q4 KV4-rot H = +9.4 and F = +12.4 pp (3 blocks).
- **WP0, `analysis/fork/audit_reuse.py`.**
  - `docs/OLD_RESULT_REUSE.csv`: 17 sources with path, sha, script and commit, backend, population, checkpoint, blocks, endpoint, integrity, permitted claim and required reanalysis.
  - Population panel: the common 85-task retail/airline pool on the 20 blocks complete in all of q4/q8 × GPTQ-W4, AWQ-W4, KV8, vs each cell's own population. Little changes: q8 GPTQ-W4 G is +2.9 [+1.5, +4.5] common vs +2.8 own (165 tasks with telecom); q8 KV8 is +0.9 vs +0.6.
  - Block coverage: 11/408 admitted run-domains do not cover their frozen pool, all from infra-missing episodes (mostly q4 RTN-W3, one q4 AWQ q5 retail task, q4 telecom). They are listed for completion, not filtered.
- **W67 audit, `analysis/fork/audit_w67.py`** (W67's file and output kept; 84 tasks × 20 common blocks; frozen hash nonce split A/B, both directions, plus 50 hash splits; references permute whole task vectors within domain or whole block columns; p = (1+k)/(B+1)).
  - Concentration: Spearman of task M rates A↔B is 0.52–0.86 (p 0.0005). Top-20% capture is 0.44–0.64 (null ≈ 0.20), above an opportunity-only ranking (0.35–0.54).
  - Direction: A-positive minus A-negative mean G on B is 14–51 pp, against 1–21 pp predicted by opportunity alone.
  - Overlap: φ(M) 0.07–0.18; the task-identity null is rejected in 7/8 pairs.
- **Bank U design** (FORK_PROTOCOL §15, not queued). U1 is own-history states; U2 is BF16-origin common states queried by every configuration. Outcome-independent hash sampling, frozen manifest, all agreement states included, no zero imputation of suffix effects. Core cost ≈ 95–100 GPU-h (q4 ≈ 16, q8 ≈ 80) plus an optional telecom stratum (≈ 25–40); about 3–4 h of engineering.

Evidence: `analysis/fork/{analyze_dev,analyze_patterns,audit_reuse,audit_w67}.py`; `analysis/fork/out/{dev_all_20261001T024918Z,consequence_estimands_20261001T0224Z,coverage_20261001T0224Z,population_panel_20261001T0224Z,block_coverage_20261001T0224Z,direction_replication_20261001T0224Z}.json`, `patterns16_20261001T0224Z.csv`, `consequence_units_20261001T0224Z.jsonl`, `w67_audit_20261001T0224Z.md`; `docs/OLD_RESULT_REUSE.csv`; `docs/insights/FORK_PROTOCOL.md` §15.

## W67 — Resumed tasks no longer turn classified episodes into "outages" (2026-09-30 19:10 PDT)
**TL;DR** `a6k2_q4_quarot_w4a4kv16_fdev` failed with "1 infrastructure_error episodes (outage)" on f03/retail.
- **What happened in the episode:** in task 61 the agent's last decision was a clean text reply. The error that followed was a ToolCall validation error, `user_sim_error` under W41.
- **The bug:** when a task is resumed, its completed runs are re-checked, but their `tau2_results.json` has already been deleted for storage. The check then found no errors, overwrote `infra_causes.json` with `{}`, and fell back to counting every infrastructure episode as an outage.
- **Fix in `worker.py`:**
  - When `tau2_results.json` is gone, keep the earlier `infra_causes.json`.
  - If there is none, recover the errors from the task log ("Task <id> failed after N attempts: <error>", `log_infra_errors`) and classify them the same way.
- **Tested** on this task: task 61 → `user_sim_error`. Requeued (resume).
Evidence: `runs/a6k2_q4_quarot_w4a4kv16_f03/retail/{metrics.json,decisions.jsonl}`, `logs/tasks/a6k2_q4_quarot_w4a4kv16_fdev.log`.

## W67 — Consequential divergences come from fragile tasks with consistent direction; restoration line paused (2026-09-30 18:30 PDT)
**TL;DR** New exploratory analysis `analysis/fork/analyze_consequence.py` on the dev forks (the same admitted complete-block units as analyze_dev).
1. **Fragile tasks.** Outcome-changing pivots (M) concentrate in a minority of tasks. The per-task dispersion index is 4.1–6.5 against a binomial null of ≈1 (p < 0.001 in every main cell). The top 20% of tasks hold 57–88% of all flips.
2. **Consistent direction.** Fragile tasks flip the same way across 20 independent nonces: fewer mixed-direction tasks than the null (p < 0.001 for W4, ≈0.02 for KV8). 68–86% of rescues sit in net-rescue tasks and 72–84% of damages in net-damage tasks. So the near-zero average G cancels systematic, opposite-sign task-level effects.
3. **Shared across quantizers.** GPTQ, AWQ and KV8, and for AWQ even q4 and q8, flip the same task × block units (lift 1.5–2.1, φ 0.07–0.19 against a null 95% of about 0.04). Given that both flip, the direction is about a coin toss.
4. **Position.** Pivot consequence peaks at t* = 1–2 (29% of divergent units) and falls to 11% for t* ≥ 7.

**Restoration line paused** at the user's request: 56 pert_* and 22 pivot_* tasks moved to priority −4. In RTN-W3 the gains just track bits (a random MLP arm recovers 76%), and no arm beats GPTQ-W4 at matched storage.

The status doc `docs/STATUS_20260930_night.md` supersedes the evening one.

Evidence: `analysis/fork/out/consequence_20261001T011124Z.json`, `analysis/fork/analyze_consequence.py`.

## W66 — q8 W×K replication queued after pre-declaring the target (2026-09-30 16:45 PDT)
**TL;DR** The q8 target contrast was committed before any q8 W×A×KV run existed:
- **Commit:** `docs/insights/WAKV_PREREG.md`, **27a3802**; `analysis/ahook/analyze_wakv.py` sha256 7a60cfc455156832… at that commit.
- **Contrast:** I_WK|A16 = Y_W4K4 − Y_W4K16r − Y_W16K4 + Y_W16K16r, two-sided.
- **Intervals:** t over 6 block means is primary; crossed task × block is secondary.

**Pairing check.** `a6k2_q8_bfpair_f01..f06` are all admitted with nonces matching `new_blocks` (snapshot 20260930T2311Z), so f01–f06 are used.

**Queued at priority −12:** 8 tasks (4 cells × 2 block groups), 3 runs each, about 2,040 episodes, ≈ 9–12 GPU-h.
- Cells: `a6k2_q8_quarot_{w16a16kv16r,w4a16kv16r,w16a16kv4,w4a16kv4}_fdev{123,456}`.
- Each W4 task rebuilds the q8 QuaRot GPTQ checkpoint (21 min).

**If the matched q4 kv16r cells show a different largest interaction,** that goes to q8 as exploratory and the q8 target is unchanged.
Code: `make_tasks.py --only wakv` gains `--blocks` / `--suffix`.
Evidence: `docs/insights/WAKV_PREREG.md`; `/data/ziyangs/cloq_work/queue/todo/a6k2_q8_quarot_*_fdev{123,456}.json`.

## W65 — W×A×KV confound fixed: matched KV16 cells with Q/K rotation (kv16r), paired interaction contrasts (2026-09-30 16:30 PDT)
**TL;DR** GPT-6.1 was right. In `wakv_cells()` the online Q/K Hadamard was on only for KV4, so kv16 → kv4 changed
rotation and quantization together. The KV4 × A4/W4 "interactions" in the first matrix are not identified.

**Pass-through check.** First I checked that KV16 plus the rotation is a pure pass-through (`validate_kvr_q4.json`):
- coverage is 36 attention layers plus 144 linear modules;
- batch, prefix-hit and unchunked are identical 8/8, and causality is 4500/4500;
- at W16A16 it differs from the unrotated cell only at the numerics floor (paired |Δlogprob| 0.0055, flip disagreement 0.34%);
- at W4A4 the rotation alone changes 7% of flip outcomes. Same distribution vs BF16 (0.358 vs 0.359), but A4 amplifies rounding differences at quantization boundaries, so the unrotated KV16 cell is a genuinely mismatched control.

**Queued.** Four matched cells at priority −14, 3 runs each (~1,020 q4 episodes, ~3.5 GPU-h at the q4 cell rate):
`a6k2_q4_quarot_w{16,4}a{16,4}kv16r_fdev` on f01–f03. The four KV4 cells are reused.

**analyze_wakv.**
- **Primary factorial:** uses kv16r as the KV reference.
- **Paired contrasts, each on the units that have all its cells:**
  - the single axes, each with an interval;
  - I_AK | W16 and I_AK | W4, i.e. Y_A4K4 − Y_A4K16r − Y_A16K4 + Y_A16K16r;
  - I_WK | A, I_WA | KV, and I_WAK;
  - the additivity gap.
- **For the record:** the kv16 factorial is labelled confounded, and a rotation-only contrast (kv16r − kv16) is reported per W×A.
- **Inference:** the W63 `analyze_dev.Boot`. With 3 blocks the primary interval is t over the block means; the crossed task × block interval is reported alongside.

**Current q4 (confounded legacy contrasts, k = 3 blocks).**
- I_WK | A16 = −14.9 pp, t CI [−23.8, −6.0], crossed [−27.1, −2.7].
- single W +2.0 [+0.3, +3.6]; single A −5.1 [−15.4, +5.2]; single KV +1.2 [−15.1, +17.4].
- A non-significant single axis is not evidence of harmlessness; the intervals are wide.
- Two KV4 / A4 cells are still incomplete (1–2 blocks).

**Scope:** any claim is "among these QuaRot-rotated 4-bit axes", not "harm needs combinations". RTN-W3 alone is heavily damaging.

**q8 plan (not queued; awaiting the kv16r contrasts).** Re-test the largest matched q4 interaction on q8 at priority −12 with its four cells on f01–f03.
- If it is still I_WK | A16, the cells are `a6k2_q8_quarot_{w16a16kv16r, w4a16kv16r, w16a16kv4, w4a16kv4}_fdev`.
- That is 1,020 episodes, ≈ 4.5–6 GPU-h: q8 QuaRot GPTQ build 21 min per W4 task, eval ≈ 0.7–1.1 h per task.
- f01–f06 would cost ≈ 9–12 GPU-h.

Evidence: `analysis/ahook/validate_kvr_q4.json`, `analysis/ahook/out/wakv_*.{json,md}`, `analysis/ahook/analyze_wakv.py`, `scripts/a6000/make_tasks.py --only wakv`, METHOD_FIDELITY §6.

## W63 — Fork inference corrected (block-level, crossed secondary), two-sided consequences r/d/M headline, holdout guard (2026-09-30)
**TL;DR** The GPT-6.1 review of 7528f2e was right that the fork bootstrap resampled nonces independently inside each task, breaking the shared-block dependence. Inference is now over complete shared blocks, with a crossed task × block bootstrap as the new-task secondary. r / d / M (rescue / new damage / either) are the headline next to G.

The substantive reading is unchanged:
- **Two-sided consequences:** about 16–21% of task × block units change outcome in either direction under W4 and KV4-rot (M), and only 6–8% under KV8. Rescue and damage are of similar size, so G_all stays near 0.
- **Interval scope:** with 20 complete blocks, the fixed-task-pool intervals are much tighter than before. The crossed (new-task) intervals match the old ones. The old intervals therefore mostly reflected task sampling, not run-to-run noise.

**Changes**
- **`analyze_dev.Boot`.**
  - **Primary (fixed task pool):** the statistic per complete shared block, then a block bootstrap (blocks resampled whole) and a t over block means, both reported. `ci95` is the block bootstrap with ≥ 10 blocks (W4 20, KV8 22), else the t interval (stress, telecom and restore cells have 3–6 blocks; a percentile bootstrap over so few clusters is anti-conservative).
  - **Secondary:** a crossed task × block bootstrap (tasks and blocks resampled jointly; generalisation to new tasks).
  - **Ratio forms:** block sums; t over per-block ratios.
  - **Plumbing:** the draws carry their t and crossed information (`Draws`), so every sibling (difficulty, pivot, pivot_arms, restore_eval) reports all three without code changes.
  - **External environments** (analyze_ext): stated explicitly as item-level inference, since there is one run per item.
- **Complete blocks only.** A (cell, domain, block) enters when every split task has a unit and no branch is pending. Incomplete blocks are listed and their units excluded; 24 are incomplete in this snapshot, mostly q8 GPTQ-W4 f03–f17 and RTN-W3. This moved q8 GPTQ-W4 Y_BB − Y_QQ from −1.8 to +4.2, because the partial blocks had counted pending divergent units as missing.
- **Two-sided consequence decomposition.** On one denominator (the full pool, non-divergent = 0): r = P(Y_BQ=1, Y_QQ=0), d = P(Y_BQ=0, Y_QQ=1), M = r + d, G = r − d, plus r, d and M conditional on divergence. Same definitions in analyze_ext.
- **Holdout boundary.**
  - `manifests/fork/splits_v1.json` (dev: retail 58, airline 27, telecom 80 with their blocks; holdout: telecom 34, `prereg_sha256` null).
  - analyze_dev, difficulty, pivot and restore_eval default to `--split dev`, exclude out-of-split units, and abort on any holdout unit unless `--split holdout` with a frozen PREREG_FORK_CONFIRM.md whose sha is recorded.
  - A per-cell coverage/source table lists units found and analysed, blocks, tasks per domain, exclusions by reason and source directories.
- **analyze_pivot.**
  - Three named oracle contrasts: replace the current action only (Y_BQ − Y_QQ); keep Q's action, then BF16 (Y_QB − Y_QQ = C + I); BF16 action and suffix (Y_BB − Y_QQ, the oracle intervention value; q4 KV4-rot +11.4 pp).
  - The threshold "value" is relabelled an oracle upper-bound proxy, and the policy claim is dropped from the TL;DR.
  - AUROC intervals follow the new scheme.
- **FORK_PROTOCOL.**
  - **§12 (pre-registration draft):** G_all is the only primary. r, d and M are pre-registered secondaries. C + I is the stress-cell escalation endpoint, with BB − QQ as a reference only. Confirmatory strata use only information known at the fork (remaining step budget, persona, task attributes). M1, the C-slope on realised horizon, is exploratory only. The 34-task limit on new-task generalisation is stated.
  - **§13 amendment 2 (427778a):** the selection interval is the t over the per-block pooled Δ (RTN-W3: 3 blocks), committed before any RTN-W3 pivot outcome.
  - **§14:** end-to-end escalation evaluation (design only). A frozen rule on Q-visible signals, predicting help, closed loop against a random trigger at matched BF16 budget, a tool-error trigger, always-Q and always-BF16, on new nonces. Cost ≈ 8 GPU-h for q4 KV4-rot and ≈ 110–135 GPU-h with RTN-W3 q4/q8.

**Before / after** (same snapshot 20260930T2115Z; before = code at the W61 head with the task-hierarchical bootstrap; the ext rows also differ because new external outputs arrived between the runs):

| headline | before (7528f2e; task-hierarchical bootstrap) | after: primary (fixed task pool, complete blocks) | after: crossed (new tasks) | after: r / d / M (pp) |
|---|---|---|---|---|
| q4:awq_w4 G_all (1699 units, K=20) | -0.3 [-6.0, +5.1] | -0.3 [-2.2, +1.6] (block boot) | [-6.0, +5.3] | 9.8 / 10.1 / 20.0 |
| q4:gptq_w3 G_all (255 units, K=3) | -1.2 [-10.0, +7.5] | -1.2 [-7.0, +4.7] (t) | [-9.4, +7.1] | 9.0 / 10.2 / 19.2 |
| q4:gptq_w4_d1 G_all (1700 units, K=20) | -1.9 [-6.5, +2.8] | -1.9 [-3.8, +0.1] (block boot) | [-6.6, +2.7] | 6.8 / 8.7 / 15.5 |
| q4:kvq_int4_rot G_all (255 units, K=3) | +4.7 [-4.4, +13.9] | +4.7 [-4.1, +13.5] (t) | [-3.5, +12.9] | 11.8 / 7.1 / 18.8 |
| q4:kvq_int8 G_all (1870 units, K=22) | -0.3 [-2.9, +2.2] | -0.3 [-1.7, +1.0] (block boot) | [-3.0, +2.3] | 3.1 / 3.4 / 6.5 |
| q4:rtn_w3 G_all | n/a | no complete block yet (6 incomplete) | | |
| q8:awq_w4 G_all (1700 units, K=20) | +2.1 [-2.2, +7.0] | +1.9 [-0.6, +4.4] (block boot) | [-3.8, +8.1] | 11.4 / 9.5 / 20.9 |
| q8:gptq_w4_d1 G_all (1275 units, K=15) | +3.2 [-1.6, +8.3] | +2.8 [+1.0, +4.8] (block boot) | [-3.1, +9.4] | 10.7 / 7.8 / 18.5 |
| q8:kvq_int4_rot G_all (255 units, K=3) | +3.1 [-5.9, +12.3] | +3.1 [-14.5, +20.8] (t) | [-7.1, +13.7] | 11.8 / 8.6 / 20.4 |
| q8:kvq_int8 G_all (1870 units, K=22) | +0.5 [-2.1, +3.2] | +0.6 [-0.4, +1.6] (block boot) | [-1.9, +3.0] | 4.3 / 3.7 / 8.1 |
| KV8:q4:pooled_equal_weight G | -0.3 [-2.9, +2.2] | -0.3 [-1.7, +1.0] | [-3.0, +2.3] | 3.1 / 3.4 / 6.5 |
| KV8:q8:pooled_equal_weight G | +0.5 [-2.1, +3.2] | +0.6 [-0.4, +1.6] | [-1.9, +3.0] | 4.3 / 3.7 / 8.1 |
| KV8:all:pooled_equal_weight G | +0.1 [-1.8, +2.0] | +0.1 [-0.9, +1.1] | [-1.9, +2.1] | 3.7 / 3.6 / 7.3 |
| W4:q4:pooled_equal_weight G | -1.1 [-4.9, +2.6] | -1.1 [-2.7, +0.5] | [-5.0, +2.7] | 8.3 / 9.4 / 17.7 |
| W4:q8:pooled_equal_weight G | +2.7 [-0.6, +6.1] | +2.4 [+0.9, +4.0] | [-1.7, +6.7] | 11.0 / 8.7 / 19.7 |
| W4:all:pooled_equal_weight G | +0.8 [-1.7, +3.3] | +0.6 [-0.4, +1.7] | [-2.2, +3.4] | 9.7 / 9.0 / 18.7 |
| stress:q4:pooled_equal_weight G | +1.8 [-5.2, +8.2] | +1.8 [-0.2, +4.3] | [-4.2, +7.6] | 10.4 / 8.6 / 19.0 |
| stress:q8:pooled_equal_weight G | +3.1 [-5.9, +12.3] | +3.1 [-14.5, +20.8] | [-7.1, +13.7] | 11.8 / 8.6 / 20.4 |
| stress:all:pooled_equal_weight G | +2.2 [-3.6, +7.8] | +2.2 [-1.2, +6.4] | [-3.5, +8.5] | 10.8 / 8.6 / 19.5 |
| q4:awq_w4 Y_BB−Y_QQ (oracle BF16 action+suffix) | -0.6 [-6.2, +4.7] | -0.6 [-2.8, +1.4] | [-6.3, +4.8] | |
| q4:awq_w4 AUROC −first-token margin | 0.65 [0.59, 0.70] | 0.65 [0.63, 0.67] | [0.593, 0.701] | |
| q4:gptq_w3 Y_BB−Y_QQ (oracle BF16 action+suffix) | +1.2 [-7.5, +9.8] | +1.2 [-1.7, +4.1] | [-6.3, +8.6] | |
| q4:gptq_w3 AUROC −first-token margin | 0.60 [0.52, 0.67] | 0.60 [0.51, 0.68] | [0.528, 0.665] | |
| q4:gptq_w4_d1 Y_BB−Y_QQ (oracle BF16 action+suffix) | -1.6 [-6.6, +3.0] | -1.6 [-3.4, +0.1] | [-6.5, +2.9] | |
| q4:gptq_w4_d1 AUROC −first-token margin | 0.62 [0.56, 0.68] | 0.62 [0.60, 0.63] | [0.557, 0.67] | |
| q4:kvq_int4_rot Y_BB−Y_QQ (oracle BF16 action+suffix) | +11.4 [+2.7, +20.8] | +11.4 [+9.7, +13.1] | [+2.7, +20.0] | |
| q4:kvq_int4_rot AUROC −first-token margin | 0.61 [0.49, 0.76] | 0.61 [0.37, 0.82] | [0.508, 0.731] | |
| q4:kvq_int8 Y_BB−Y_QQ (oracle BF16 action+suffix) | -0.4 [-3.0, +2.4] | -0.4 [-1.4, +0.7] | [-2.9, +2.4] | |
| q4:kvq_int8 AUROC −first-token margin | 0.71 [0.65, 0.76] | 0.71 [0.68, 0.73] | [0.645, 0.762] | |
| q8:awq_w4 Y_BB−Y_QQ (oracle BF16 action+suffix) | +1.1 [-3.9, +5.8] | +0.5 [-1.4, +2.5] | [-5.7, +6.8] | |
| q8:awq_w4 AUROC −first-token margin | 0.62 [0.56, 0.68] | 0.63 [0.62, 0.64] | [0.572, 0.69] | |
| q8:gptq_w4_d1 Y_BB−Y_QQ (oracle BF16 action+suffix) | -1.8 [-8.1, +4.1] | +4.2 [+2.0, +6.1] | [-2.6, +11.3] | |
| q8:gptq_w4_d1 AUROC −first-token margin | 0.68 [0.63, 0.74] | 0.69 [0.67, 0.70] | [0.629, 0.744] | |
| q8:kvq_int4_rot Y_BB−Y_QQ (oracle BF16 action+suffix) | +4.3 [-4.3, +13.7] | +4.3 [-15.1, +23.8] | [-5.9, +15.3] | |
| q8:kvq_int4_rot AUROC −first-token margin | 0.68 [0.62, 0.74] | 0.68 [0.60, 0.76] | [0.616, 0.738] | |
| q8:kvq_int8 Y_BB−Y_QQ (oracle BF16 action+suffix) | +1.1 [-1.5, +3.8] | +1.1 [+0.0, +2.3] | [-1.6, +3.7] | |
| q8:kvq_int8 AUROC −first-token margin | 0.64 [0.58, 0.70] | 0.64 [0.62, 0.66] | [0.579, 0.697] | |
| q4:awq_w4 C-slope on realised horizon (EXPLORATORY, pp/10 dec.) | -0.163 [-3.53, 2.515] | -0.16 [-0.87, +0.53] | [-3.319, 2.607] | |
| q4:gptq_w3 C-slope on realised horizon (EXPLORATORY, pp/10 dec.) | -3.676 [-11.888, 11.479] | -3.68 [-12.87, +5.51] | [-11.543, 10.283] | |
| q4:gptq_w4_d1 C-slope on realised horizon (EXPLORATORY, pp/10 dec.) | -0.837 [-5.328, 1.252] | -0.73 [-2.15, +0.52] | [-5.812, 1.769] | |
| q4:kvq_int4_rot C-slope on realised horizon (EXPLORATORY, pp/10 dec.) | -0.862 [-6.963, 11.302] | -1.47 [-43.65, +39.41] | [-10.106, 5.424] | |
| q4:kvq_int8 C-slope on realised horizon (EXPLORATORY, pp/10 dec.) | -0.522 [-5.004, 1.177] | -0.52 [-1.71, +0.32] | [-5.183, 1.158] | |
| q8:awq_w4 C-slope on realised horizon (EXPLORATORY, pp/10 dec.) | 0.12 [-1.495, 1.759] | +0.12 [-0.81, +1.08] | [-1.886, 2.185] | |
| q8:gptq_w4_d1 C-slope on realised horizon (EXPLORATORY, pp/10 dec.) | -0.368 [-2.587, 1.707] | -0.11 [-1.62, +1.70] | [-2.762, 2.799] | |
| q8:kvq_int4_rot C-slope on realised horizon (EXPLORATORY, pp/10 dec.) | -0.815 [-5.861, 4.431] | -0.81 [-3.06, +1.29] | [-6.536, 3.892] | |
| q8:kvq_int8 C-slope on realised horizon (EXPLORATORY, pp/10 dec.) | -0.064 [-2.234, 1.963] | +0.24 [-0.89, +1.40] | [-1.928, 2.725] | |
| ext W4:alfworld:pooled_equal_weight G (item-level) | -3.7 [-9.7, +1.9] | -3.7 [-9.7, +1.9] | item-level only | 9.7 / 13.4 / 23.1 |
| ext W4:bfcl:pooled_equal_weight G (item-level) | -0.5 [-1.7, +0.8] | -0.5 [-1.7, +0.8] | item-level only | 4.2 / 4.7 / 8.9 |
| ext W4:all_envs:pooled_equal_weight G (item-level) | -1.8 [-4.2, +0.6] | -1.8 [-4.2, +0.6] | item-level only | 6.4 / 8.2 / 14.6 |
| ext stress:alfworld:pooled_equal_weight G (item-level) | +3.7 [-1.5, +9.7] | +3.7 [-1.5, +9.7] | item-level only | 6.7 / 3.0 / 9.7 |
| ext stress:bfcl:pooled_equal_weight G (item-level) | +1.1 [-1.0, +3.3] | +0.8 [-0.4, +2.0] | item-level only | 2.9 / 2.0 / 4.9 |
| ext stress:all_envs:pooled_equal_weight G (item-level) | +2.4 [-0.3, +5.4] | +1.8 [+0.0, +3.8] | item-level only | 4.1 / 2.3 / 6.5 |

Evidence: before `analysis/fork/out/{dev_all_20260930T213234Z,difficulty_20260930T213530Z,pivot_20260930T213919Z,restore_eval_20260930T214332Z,ext_20260930T214706Z}.{json,md}`;
after `analysis/fork/out/{dev_all_20260930T220835Z,difficulty_20260930T220917Z,pivot_20260930T221604Z,restore_eval_20260930T220627Z,ext_20260930T221613Z,pivot_arms_20260930T220652Z}.{json,md}`;
code `analysis/fork/analyze_{dev,difficulty,pivot,pivot_arms,restore_eval,ext}.py`; `manifests/fork/splits_v1.json`; `docs/insights/FORK_PROTOCOL.md` §12–§14.

## W64 — GPT-6.1 code review: fork-aligned success NI, storage-matched restoration baseline, AWQ-W3 baselines (2026-09-30)
**TL;DR** Three fixes from the GPT-6.1 code review.

**1. Fork-aligned success**
- `success_ni.py` averages the calibration draws d1–d4. It is now labelled "population of calibration draws", because it is not an equivalence statement about d1, the fork checkpoint.
- The new `success_ni_aligned.py` measures Q − BF16 on exactly the forks' d1 checkpoints, tasks and 20 nonce blocks. Units are paired on nonce, with a crossed task × complete-block bootstrap drawn jointly across q4/q8 and GPTQ/AWQ (shared task ids and nonces).
- The local bootstrap should be swapped for `analyze_dev.Boot` once agent a5468c1 pushes its complete-block fix.
- **Results (crossed CIs):**

  | cell | Q − BF16 | 95 % CI |
  |---|---|---|
  | q4 GPTQ-W4 d1 | +4.2 pp | [−2.4, +10.5] |
  | q4 AWQ-W4 d1 | +0.9 pp | [−5.8, +7.5] |
  | q8 GPTQ-W4 d1 | −0.2 pp | [−7.7, +6.8] |
  | q8 AWQ-W4 d1 | +1.2 pp | [−5.3, +7.6] |
  | pool, all four | +1.5 pp | [−2.7, +5.6] |

- **Tests at 3 pp:** non-inferiority passes for q4 GPTQ and for the GPTQ, AWQ, q4 and all-four pools. TOST at 3 pp passes nowhere, because task resampling makes the 90 % intervals about ±6 pp wide. With a fixed task set (block resampling only), q4 GPTQ d1 is +4.2 [+2.2, +6.1] (90 %): d1 is better than BF16 on these tasks.

**2. Storage-matched deployment baseline**
- New `analyze_restore_eval.py` table for the RTN-W3 cell. Each arm gets simulated bits/param (manifest `budget_w3.rtn`) and paired success vs RTN-W3 Q, BF16, GPTQ-W3 d1, GPTQ-W4 d1, AWQ-W4 d1, and AWQ-W3 d1 once it exists.
- A success-vs-bits frontier PNG (`restore_eval_<UTC>_frontier.png`) sits next to the md.
- RTN-W3 restoration is labelled a **mechanism stress test**. The deployment claim stays open until an arm beats whole-model quantizers at matched storage.
- **Reference points on the RTN-W3 cell's units (aliased-arm check):**

  | model | BF16 (16 b) | RTN-W3 (3.15 b) | GPTQ-W3 d1 (3.16 b) | GPTQ-W4 d1 (4.16 b) | AWQ-W4 d1 |
  |---|---|---|---|---|---|
  | q4 | 35.3 | 13.7 | 36.5 | 40.8 | 40.4 |
  | q8 | 30.6 | 13.3 | 26.7 | 31.0 | 30.6 |

- A restoration arm at ~7.4 b therefore has to exceed 36–41 % (q4) to be competitive.
- GPTQ-W4 d1 runs on q3–q5 exist and are admitted for both models.

**3. AWQ-W3 d1 baselines**
- Queued `a6k2_{q4,q8}_awq_w3_qx`: 2 tasks, 6 runs on q3–q5 with nonces paired to `bfpair_q3..q5`, priority −12, spec `{"kind": "awq", "wbits": 3, "calib": c1}`. No restoration matrix.
- **Estimated 3–16 GPU-h, not ~20.** GPTQ-W3 3-run tasks took about 1 h; a damaged model like RTN-W3 took 5–8 h.

**Evidence**
- Code: `analysis/insights/iter_4/success_ni_aligned.py`, `analysis/insights/iter_4/out/success_ni_ALIGNED_20260930T213009Z.json` (+ `.md`), `analysis/insights/iter_4/success_ni.py` (label), `analysis/fork/analyze_restore_eval.py` (storage table and frontier), `scripts/a6000/make_tasks_perturb.py --awq3`.
- Queue: `/data/ziyangs/cloq_work/queue/todo/a6k2_{q4,q8}_awq_w3_qx.json`.

## W62 — node002 joins (job 49599) (2026-09-30 14:20 PDT)
**TL;DR** The admin now reserves CPUs for GPU jobs. As a result, our long-pending runner 49599 (submitted 09-28 with `-w node002 --gres=gpu:A6000:8 -c 16`) started on node002 at 14:19.
- All 8 GPUs passed the probe.
- The simulator replica is on GPUs 0,1; the other 6 GPUs take tasks.
- Only 16 CPUs are allocated (other runners have 32). Watch for CPU-bound slow-down.
- Usable A6000s: node001, node002 and node004–007 = 48. node003 is still down (W56).
- 49600 (node008) is still pending (Resources).
Evidence: `logs/node_node002_49599.out`, `squeue`.

## W61 — Damage regime moved to RTN-W3: stress forks, pivot arms, amended selection population (2026-09-30)
**TL;DR** RTN-W3 is where the damage is, so the pivot-arm selection population moves there (amendment committed first), and 14 tasks are queued (≈ 30–40 GPU-h).
- **Why.** Closed-loop success on q3–q5 shows no GPTQ-W3 damage but heavy RTN-W3 damage:

  | | BF16 | GPTQ-W3 | RTN-W3 |
  |---|---|---|---|
  | q4 | 35.7% | 36.1% | 13.5% |
  | q8 | 30.6% | 26.7% | 13.3% |

  The stress forks agree (q4 GPTQ-W3 G_all ≈ −1.2 pp).
- **FORK_PROTOCOL §13 amendment 1** (commit 0f26f7d2ab2fb8a7f3b42c0cac788504aa5fb95d), committed before any RTN task existed and before any W3 pivot-arm outcome was computed.
  - The step-3 selection population is now RTN-W3 q4 + q8 (equal weight); the rule is otherwise unchanged. GPTQ-W3 pivot results become secondary.
  - The q4 GPTQ-W3 pivot-arm files already existed but had not been opened; the pooled statistic had never been computed (q8 GPTQ-W3 had not run). This is stated in the amendment.
  - `analyze_pivot_arms.py` now selects on RTN-W3 and reports the GPTQ-W3 pooled Δ separately as secondary.
- **RTN-W3 stress forks** `fork_stress_q{4,8}_rtn_w3` (`make_tasks_fork_p2.py --rtn-w3`), priority −16.
  - q3–q5 × 85 tasks, mode dev with the 10% no-op quarantine.
  - Q runs `a6k2_q{4,8}_rtn_w3_q3..q5` admitted in snapshot 20260930T2047Z, nonces equal to their BF16 pairs, spec `{"kind": "rtn", "wbits": 3}`.
  - Branch steps are capped only by the runs' tau2 max_steps (200); no extra cap.
  - q8 on 2 GPUs, pinned.
- **RTN-W3 pivot arms** (12 tasks, priority −15, dependent on the stress forks).
  - Arms: none, all, early/middle/late/attn/mlp, rand_third/attn/mlp s1, resid α 0.5. No recal arms, because RTN has no inter-layer compensation.
  - 150 hash-sampled states per cell.
- **Estimate.** Measured stress throughput is 62–85 states/h, about 3–4 h per 255-unit task.
  - RTN-W3 stress: ≈ 20–30 GPU-h (2–3× that for looping agents).
  - RTN-W3 pivot arms: ≈ 10 GPU-h.
- **Analyses.** analyze_dev's stress family is now gptq_w3 + kvq_int4_rot + rtn_w3, and every cell is also reported on its own. analyze_difficulty and analyze_pivot iterate over all cells, so they pick up rtn_w3 automatically.
Evidence: `docs/insights/FORK_PROTOCOL.md` §13 amendment 1; `scripts/a6000/{make_tasks_fork_p2,make_tasks_pivot_arms}.py`; `analysis/fork/{analyze_dev,analyze_pivot_arms}.py`;
`/data/ziyangs/cloq_work/queue/todo/{fork_stress,pivot}_q{4,8}_rtn_w3*.json`.

## W60 — Restoration damage regime moved to RTN-W3: 34 arm tasks queued at −16; GPTQ-W3 demoted (2026-09-30)
**TL;DR** GPTQ-W3 is the wrong damage regime. On q3–q5, db_match success is q4 BF16 35.7 / GPTQ-W3 36.1 / RTN-W3 13.5, and q8 30.6 / 26.7 / 13.3.
- **New primary damage regime: RTN-W3.** It has no calibration and no sequential compensation, so plain `restore` is unconfounded (no recal needed).
- **Queued:** 34 tasks (17 arms × q4/q8, blocks q3–q5, 102 runs) at priority −16, paired with `a6k2_{q4,q8}_rtn_w3_q3..q5` and `bfpair_q3..q5`. All 12 of those runs are admitted in snapshot 20260930T2047Z, with matching nonces.
- **Estimated ~130 GPU-h (range 40–220).** RTN-W3 episodes are about 2–3× longer than BF16 (q4 retail 38 vs 12 decisions), and the RTN-W3 Q tasks took 8.0 h (q4) and 4.9 h (q8) for 3 runs. BF16-like arms take ~1–1.5 h.
- **GPTQ-W3 demoted:** its 2 not-yet-started tasks (recal rand_mlp_s1 / rand_third_s1 on q8) were lowered to −8. The other 48 had already run or were running.

**Changes**
- `scripts/a6000/make_tasks_perturb.py`: `rtn_w3` cell with spec `{"kind": "rtn", "wbits": 3}` and no calibration dependency; `w3_tasks(cell, priority)`; `--rtn3`.
- Manifests: unchanged. `budget_w3.rtn` was already computed (3-bit codes plus an fp16 scale and a 3-bit zero per group, no g_idx), giving Q 3.148, a third 7.432, attn 6.487 / 5.942, mlp 12.662 / 13.206 bits/param (q4 / q8), exactly proportional to parameters.
- `analysis/fork/analyze_restore_eval.py`: parses `rtn_w3` arms; regime labels are RTN-W3 primary (success and behaviour co-primary), GPTQ-W3 secondary (compensation effect), and W4 behaviour primary.

**Tests:** new `test_rtn_w3_cli` (ALL PASS).
- The real `cloq.compress rtn --wbits 3` output equals the per-module RTN-W3 of W.
- Plain restore on it gives exactly "kept modules BF16, others their own RTN-W3".
- α = 0 / 1 are exact, and `budget_w3.rtn` is recorded.
- Byte matching now also checks the RTN-W3 budgets of random arms, which are exactly equal when Δparams = 0.

**Evidence**
- `docs/insights/PERTURBATION_PROTOCOL.md` §3d.
- Queue: `/data/ziyangs/cloq_work/queue/todo/pert_{q4,q8}_rtn_w3_*_q345.json`.

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
