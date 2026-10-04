# q8 new-method panel (QuaRot / SpinQuant / KIVI, phase 1 f01-f03): acceptance review A (independent, effect-blind)

Reviewer A of 2. Written 2026-10-03 19:55 PDT. Repo HEAD `3681677`.
- **Code and protocol unchanged since 744f7c4:** `git diff 744f7c4 HEAD` is empty for the protocol, `analyze_newmethod.py`, `fork_driver.py`, `exppilot_analysis.py` and `cloq/fork.py`.
- **Protocol sha256:** `3bd7ef33...ba8f6` (A7.E1).

**What was and was not read.** The review was read-only.
- No effect, contrast, success rate or per-arm outcome aggregate was computed, printed or looked up.
- No `Y` was read from any bank row or recovery row. From branch and recovery records I read only these fields:
  - `arm_source`, `error`, `n_decisions`;
  - timing fields (`wall_seconds`, `generation_time_seconds`, `duration`), `finish_reason`, `n_completion_tokens`;
  - identity fields (`state_identical`, `shadow_identical`, `sim_seed`, `tag`, `prefix_ok`, `env_hash_init_ok`, forced-action equality);
  - server fingerprints.
- `analysis/fork/holdout/` was not opened. My one directory walk pruned it before descending.
- Reviewer B's file was not opened. Only the subject line of its commit (3de8d31) and of W100ah appeared in `git log` / `grep '^## W100ah'`.
- `analyze_newmethod.py` was run only with `--selftest` (PASS) and `--model q8 --dry` (rc 0), after `source scripts/a6000/env.sh`.

## TL;DR verdict

**CONDITIONAL GO.** I found no fatal issue, and nothing in the following blocks the read once the A7 re-runs have finished:
- protocol integrity;
- the finished phase-1 work;
- A7 compliance of the 18 terminal re-run arms;
- the analysis code;
- pre-registration hygiene.

**One blocking procedural condition remains.** Write `queue/EXPPILOT_GO_newmethod_q8` only after C1 holds, and after C3 and C4 have been checked:
- **C1 (blocking).** `a7_rr1_q8_kivi_k2v2_f03` and `a7_rr1_q8_kivi_k4v4_f01` are terminal (`done` or `failed`), with `recovery_summary.json` written.
  - The alternative is a cutoff time, plus a rule for unfinished arms, logged in RESEARCH_LOG before GO.
  - **Why this blocks:** `exppilot_analysis.required()` does not list `a7_rr1_*`, the q8 analysis runs once, and every other required task is now done. A GO written now would read the q8 panel immediately. It would leave out the kivi_k2v2 f03 and kivi_k4v4 f01 A7 merges, and recovering them later would need a second read (W1).
  - At 19:50 PDT: kivi_k2v2 f03 has f2b0916c7aa6d021 BQ+QQ still running (since 18:56). kivi_k4v4 f01 has 11 of 12 arms pending, with 3b1c207abdf8ef45 QQ running since 18:23.
- **C2 (was a condition, now SATISFIED).** `nmp_score_q8_spinquant_w4a4_f03` reached `done` at 19:39:33 PDT. Its `score_summary.json` shows `n_rows` 85, `n_ok` 85, `n_prompt_sha_ok` 85, and `bank_rows_sha256` equals the current `tau2/q8_spinquant_w4a4/f03/bank_rows.jsonl`. All 24/24 q8 score sets are bound to their current bank rows.
- **C3 (re-check at GO time).**
  - Protocol sha is still `3bd7ef33`.
  - `analyze_newmethod.py` is unchanged from 744f7c4 (or any change is logged).
  - `expansion_q8.json` is unchanged (expand false).
  - `--dry` gives:
    - primary: kivi_k2v2 {f01, f02}; kivi_k4v4 {f01, f02, f03} if all 12 f01 arms recovered, else {f02, f03}; every other cell f01-f03;
    - strict and pre-recovery: as today.
- **C4 (effect-blind acceptance of the 13 pending arms, before GO).** Repeat the A7.3 checks I ran on the 18 terminal arms (§3) for each new arm:
  - `state_identical`, `shadow_identical`, forced action = recorded action, `sim_seed`, `prefix_ok`/`env_hash_init_ok`, `-rr1` tag, server identity, budget recount.
  - **For timeout_cause_not_established arms:** check that no decision has `wall_seconds` ≥ 600 (A7.2's "any request times out again" clause, W3).
  - **For the two noop-sampled kivi_k4v4 f01 rows:** record how a recovered BB enters (W2) before the read.
- **C5 (procedural).** Reviewer B's review is in, per the exppilot GO rule ("budget audit + 2 independent reviews").

**The primary family is already final and cannot change by waiting:**
- P1 has k = 3.
- P2 has k = 3, its third block via A7.E1.
- P3 has k = 2 {f01, f02}, so its t has df 1. kivi_k2v2 f03 is lost to the persistent timeout whatever the pending arms do.

Waiting therefore costs nothing on the primary family. The pending tasks change only these: K2, A44_k4, the complete-case sensitivity and the A7 report.

| # | Item | Result |
|---|---|---|
| 1 | Protocol integrity, append-only chain (A7, A7.E1 prefixes), script constant | **PASS** |
| 2 | Completeness of phase-1 tasks; state of running A7 tasks | **CONDITIONAL**: τ² 24/24, score 24/24, BFCL 7 closed-loop + 28 forks, all gates done; 2 A7 tasks running (13 arms) |
| 3 | A7 compliance (A7.2/A7.E1 classes, A7.3 conditions, persistent timeout, merge logic) | **PASS** on the 18 terminal arms; **CONDITIONAL** on the 13 pending; minor gaps W2-W5 |
| 4 | Analysis code vs protocol (P1-P3 + Holm, P3 fallback, T1-T3, K2, A44, references, no holdout/un-admitted reads, `--dry` = audit) | **PASS with notes** (W2, W4, W6, W10) |
| 5 | Pre-registration hygiene (A6, A7, A7.E1, A4.4 code) | **PASS with disclosures** (W5, W7, W12) |
| 6 | GO conditions | **CONDITIONAL GO**: C1 blocking; C3-C5 at GO time; no other blocking issue |

---

# Part 1: Structured review

## Summary

The q8 new-method panel runs eight registered cells on the frozen U2B τ² bank (85 BF16-sourced states × 3 blocks) and on the 200-item BFCL panel:
- `quarot_w4`, `quarot_w4a4` and `quarot_w16`;
- `spinquant_w4a4` and `spinquant_w16`;
- `kivi_k2v2`, `kivi_k4v4` and `kivi_k16v16`.

The primary τ² family compares Q's action under the common BF16 continuation (D_cc) across methods:
- P1: quarot_w4 − gptq_w4_d1;
- P2: spinquant_w4a4 − quarot_w4a4;
- P3: kivi_k2v2 − kvq_int8.

Phase 2 was declined on cost (`expansion_q8.json`, expand false), so k ≤ 3. Thirty-one arms stopped on server or simulator errors. Amendments A7 and A7.E1 grant each one controlled re-run under fixed conditions, with the pre-recovery and strict views reported alongside. The analysis is held behind `queue/EXPPILOT_GO_newmethod_q8`.

**This review covers:**
- re-derivation of the protocol chain and of the admission;
- an independent check of the A7 re-run records;
- a reading of the analysis code paths that the read will exercise;
- a reconstruction, from git, file atimes and session transcripts, of who touched q8 panel outputs before each rule was fixed.

The acceptance audit (`q8_acceptance_audit_phase1_20261004T0226Z`) is accurate wherever I re-checked it. Its blocking item 3 (A4.4 contrasts missing) was resolved by 744f7c4, and its item 2 (score f03) has since resolved.

## Strengths

- **[S1] The protocol is append-only, byte for byte.** Every committed version (10 commits, 870d1ba to 861ebff) is a byte prefix of the next, and the working copy equals HEAD. A7 names its prefix sha (`b306cc70`, = 2f06102). A7.E1's prefix is the A7 version (`ba743cee`, = 10a5518). The script constant changes in the same commit as each amendment (§1).
- **[S2] Admission reproduces exactly.** `--dry` returns the audit's §6 table in all five views (primary, strict, pre-recovery, A6 prospective, A6 + tool-call parse). The tau2 log is empty, BFCL has none quarantined, none incomplete and 0 replay-inconsistent states, and every BFCL cell covers 200/200 items with 0 excluded.
- **[S3] The A7 scope is closed and consistent.** Four sets are identical at 31 arms:
  - the A7.1 list in the protocol;
  - `failed_arms.json`;
  - the arm lists of the 5 A7 queue tasks;
  - the panel arms whose `arm_source` starts with `error`.

  `bank_u_arms` refuses any arm that is not a recorded failed arm. No A7 task sets `reuse_rerun`. Reference U2B rows have 0 arm errors.
- **[S4] The A7 order of operations holds, to the second:**
  - A7 committed 16:44:25;
  - forensics committed 16:57:30 (e370e4b);
  - the 4 KIVI A7 tasks created 16:57:32;
  - A7.E1 committed 17:44:59;
  - the spinquant A7 task created 17:45:01.
- **[S5] Server identity is enforced and recorded.** For all 5 A7 tasks:
  - B and Q canary, `ckpt_sha256`, `effective_config_sha` and `hook_version` equal `a7_expect` and the original block's `bank_summary.servers`;
  - Q `hook_coverage.ok` and B `canary_ref_ok` are true;
  - the B and Q roles are verbatim copies of the original panel task.

  The KIVI panel blocks, their `_fx` gates and the KIVI BFCL fork tasks all run hook `30020b75`. The pre-fix gates ran `b82dfa5a`.
- **[S6] The KIVI and rotation gates are as A5.1/A4.3 require.**
  - All 10 gate directories pass (`gate_same.verdict.pass`, `gate_pass`).
  - kivi_k4v4 strict T1 (`T1_strict_codes_scale_mn_deq_bitwise`) is true.
  - The rotation release logs show `{"qr": true, "sp": true}` with all 5 cells released (`rot_release_panel_{qr,sp}_q8.log`, 10-02 20:35).
- **[S7] Panel outputs are not in git (untracked) and were never pushed.** Off-host exposure through the repository was therefore impossible.

## Weaknesses

- **[W1] MAJOR (blocking, procedural): the GO trigger does not wait for A7.** `exppilot_analysis.required()` builds its list from `nmp_{tau2,score}` and `nmp_bfcl` only. Once GO exists and those are done (true since 19:39:33), the once-only analysis fires.
  - `a7_records()` merges a block only if `recovery_summary.json` exists, and the two running tasks have none.
  - A GO now would therefore compute the primary with kivi_k4v4 f01 and kivi_k2v2 f03 pre-recovery.
  - That leaves out recovered arms from the complete-case sensitivity, K2 and A44_k4, and the A7 report. Correcting it would need a second read.
- **[W2] MAJOR for the secondary KIVI contrasts (not blocking for P1-P3): a recovered BB on a noop-sampled row enters without the no-op equality check.**
  - **The rows.** 9749f30f7ffd3c41 (exact; QB = reuse=BB) and 95d6b21e8fc7af2b (non-exact) in kivi_k4v4 f01 have `noop_sample` true, BB errored, and `checks` = {`Q_prompt_ok`} only. The `noop_BB` check was skipped because `bank_u` runs `noop_check` only when the BB run has no error.
  - **What the A7 code does.** `bank_u_arms` does not run `noop_check`. `a7_apply` writes the re-run BB `Y` into `Y_BB`.
  - **Why it matters.** The cross-method contrast is coded as `u["E"]["D_cc"] - v["E"]["D_cc"]`. That equals the protocol's ΔD_cc = Y_QB(m1) − Y_QB(m2) only if Y_BB is identical across cells at the state. The identity holds for orig rows and for rows whose no-op passed, and it is unverified at these two rows.
  - **Scope.** It affects K2 and A44_k4, and only if all 12 kivi_k4v4 f01 arms recover. At most 2 of 85 states in one block.
- **[W3] MINOR: A7.2's "any request times out again" clause is not enforced in code.**
  - `a7_apply` labels an arm "rerun" whenever `run_branch` returned no error. A request whose first 600 s attempt timed out but whose litellm retry succeeded would be merged, although A7.2 then says "the arm stays missing".
  - **Holds on the data so far.** The 8 recovered timeout_cause_not_established arms have a maximum decision `wall_seconds` of 524.7 s, so no attempt reached 600 s.
  - It must be checked on the pending f2b0916c7aa6d021 BQ/QQ arms (C4).
- **[W4] MINOR: the A7.4 report fields are missing.**
  - A7.4 requires per cell and block "their A7.2 class and `shadow_identical`". `a7rep` holds only counts: `rerun`, `failed again`, `states_completed`, `states_still_missing`.
  - The persistent timeout is labelled "failed again", not "persistent timeout".
  - A state refused for identity mismatch would not appear at all, because `a7_apply` returns an empty dict.
  - The write-up must take these fields from `failed_arms.json`, the `recovery_summary.json` files and the audit, or the report code must add them before the read (reporting only).
- **[W5] MINOR: A7's "What was known" statement is not fully accurate.** A7 says the errored arms were "read from `branches/<state_key>.json` error fields only". The forensics subagent printed more than that, before the A7 commit (16:44:25). Per the transcript `agent-aa1e0ae840e1c5150`:
  - **16:36:08 PDT:** `termination_reason` and suffix length of the non-errored arms in three KIVI branch files (kivi_k2v2 f01 1bdc433905484e8d; kivi_k4v4 f01 95d6b21e8fc7af2b, 9749f30f7ffd3c41);
  - **16:39:38 PDT:** the first 3 decisions and first 6 suffix messages (content truncated to 60 characters) of kivi_k2v2 f01 1bdc433905484e8d BQ.

  I did not look at the printed values. These are at most a few sibling arms of failed rows, not the failed arms. The A7 rule (re-run the listed arms) does not depend on them, so this is immaterial to the estimates. It belongs in an erratum line next to A7.7.
- **[W6] MINOR: the Holm family size is not stated in the protocol text.**
  - `tau2_contrasts` and `bfcl_stats` apply Holm over estimable members only (`if "D_cc" in con[lab]`). This has been in the frozen skeleton since 870d1ba (line 410), so it was pre-specified in code.
  - The protocol text names a three-member family. Under the strict and pre-recovery views P3 is not estimable, so m = 2 there; m = 3 under the primary and the A6.E1 views.
  - The report should state m per view.
  - Related, also pre-specified in 870d1ba: `t_pvalue` returns 1.0 when the block means have zero spread. That is conservative.
- **[W7] MINOR (disclosure): P2's third block and P3's block count rest on post-classification rules.**
  - **P2.** A7.2 as committed kept class `other` missing. A7.E1 (17:44, after the classification, before any re-run outcome) re-ran the 9 spinquant f01 arms, so P2 goes from k = 2 to k = 3.
  - **P3.** It has k = 2 (df 1), because the persistent-timeout rule keeps kivi_k2v2 f03 out. Recurrence depends on completion length, which is model behaviour (E1.5, A7.7).
  - **References.** The reference sides of P1 and P3 were not blind (A6.4), and kvq_int8 runs an older hook version (`ca3e42d2`).
  - **Requirement.** The strict and pre-recovery P2 (k = 2) and the k = 2 P3 must appear next to the primary with equal prominence.
  - **E1.5 is superseded.** Its sentence "They decide P3 (kivi_k2v2 has no admissible block under any view) and cost P2 one block" no longer describes the primary.
- **[W8] MINOR: the kivi_k2v2 panel and BFCL run were gated on the pre-fix gates.**
  - `nmp_tau2_q8_kivi_k2v2_f0{1,2,3}` and `ext_q8_kivi_k2v2_bfcl_nmp1` depend on the pre-fix gates.
  - f01 (17:34) and f02 (17:51) finished before `nmp_gate_same_q8_kivi_k2v2_fx` passed (18:02). A4.2 permits this.
  - The panel blocks run hook `30020b75`, the same as the `_fx` gates.
  - The BFCL closed-loop run records no hook version. It started 10-02 09:48, after the kernel fix f585ae3 (07:10), and its four fork directories have 0 replay-inconsistent states. State this next to P3.
- **[W9] MINOR (traceability): the committed rotation-gate record is stale.**
  - `analysis/fork/rot_gate/verdict.json` at its last commit (cf03f74, 10-02 04:11) shows `sp.pass` false ("missing validation outputs").
  - The passing verdict exists only in the working tree (uncommitted, together with `validate_sp_q8{,_ppl}.json`) and in the release logs.
  - Commit them, or cite the release logs as the gate evidence.
- **[W10] MINOR (labels): BFCL contrasts and kivi_k16v16's BFCL status are mislabelled.**
  - On BFCL, `bfcl_stats` iterates `SECONDARY`. K2 (kvq_int8 is not a BFCL reference) and A44_k2/A44_k4 (kivi_k16v16 has no BFCL, A4.1) will print "cell not admitted". They should print "not registered on BFCL".
  - kivi_k16v16's BFCL "not run" (A4.1) is not in `NOT_RUN`.
- **[W11] MINOR: the user-simulator replica is not fingerprinted in the A7 tasks.**
  - 4 of 5 A7 tasks used a different simulator endpoint from the original block (node-local vs node004/node005; node001 for spinquant by A7.E1).
  - A7.3 fixes the simulator seed (626729, verified on all 17 recovered arms) but not the replica's identity.
  - **Supporting evidence:** across the panel, no-ops pass on tasks that used different simulator replicas, and the shadow is identical 13/13 on the completed A7 states.
  - State this as an assumption.
- **[W12] MINOR (informational, outside the panel analysis): a recursive grep read holdout files.**
  - At 2026-10-03 06:42:35 PDT a workflow subagent (`agent-af50409cb071193fe`) ran `grep -rn 'W100[o-z]' docs/ analysis/ 2>/dev/null | grep -v '^analysis/fork/holdout' | head`.
  - The first grep reads the contents of every file under `analysis/`, including `analysis/fork/holdout/`; only its output is filtered.
  - `analyze_newmethod.py` itself never reads holdout (`no_holdout` guard). The main session may want to forbid unscoped recursive content greps over `analysis/`.

## Questions for the main session

- **[Q1] When is the GO written if kivi_k4v4 f01 is still running late on 10-04?**
  - A7.1 allows re-runs until 21:00 PDT, while §5's T_deadline (12:00 PDT) reserves analysis time.
  - Recommendation: fix the cutoff before GO. For example, "both A7 tasks terminal, or 2026-10-04 12:00 PDT, whichever is first; arms without a `recovery_summary.json` count as not re-run".
- **[Q2] How does a recovered BB enter on 9749f30f7ffd3c41 and 95d6b21e8fc7af2b?** Options:
  - (a) run `fork_driver.noop_check` on the re-run BB against the original. This is an equality check like every panel no-op. Apply §2.3 on a mismatch, and fix the consequence in advance.
  - (b) keep the re-run `Y_BB` and disclose that the no-op was not performed.
  - Either must be logged before the read.
- **[Q3] Should the A7 report add the A7.2 class and `shadow_identical` per arm, and the label "persistent timeout"?** This is a reporting-only code change before the read; the alternative is to take them from `failed_arms.json` and the recovery summaries in the write-up.
- **[Q4] Should a recovered timeout-class arm be checked against the strict reading of A7.2?** Confirm that an arm with any decision `wall_seconds` ≥ 600 would be treated as a persistent timeout. No such arm exists so far.
- **[Q5] Will the report state the Holm m per view (estimable members only)?**

## Verdict

**Overall: sound, conditional on one procedural step.** I found:
- no protocol-integrity defect;
- no admission discrepancy;
- no A7 condition violated on the terminal arms;
- no evidence that any q8 new-method outcome, contrast or effect was computed before A6, A7, A7.E1 or the A4.4 implementation was fixed.

**Revision priority:**
1. C1 (blocking).
2. C4 and Q2 (before the read; they affect only secondary contrasts).
3. W4, W5, W6, W7, W10 (reporting and disclosure).
4. W9, W11, W12 (traceability and hygiene).

**Confidence: high (0.85)** on items 1-4 and 6. Item 5 is **moderate-high (0.75)**: the evidence covers Claude sessions and login-node reads, but compute-node (NFS) reads do not update atime here, and actors outside these transcripts cannot be checked.

## Revision plan

1. **W1.** Do not write GO until both `a7_rr1_q8_*` tasks are in `done/` or `failed/` with a `recovery_summary.json`. Alternatively, log a cutoff rule (Q1) in RESEARCH_LOG first. Optionally add `a7_rr1_<m>_*` to `required()`.
2. **C4 / W3.** When the A7 tasks finish, run the same effect-blind checks as §3 below on the new arms:
   - state, shadow, forced action, seed, prefix, `-rr1` tag, server identity, budget recount;
   - max `wall_seconds` < 600 for kivi_k2v2 arms.
3. **W2 / Q2.** Decide and log the BB no-op handling for the two kivi_k4v4 f01 rows. A cheap guard is an assertion, or a reported count, that Y_BB is equal across cells per state in `tau2_contrast`.
4. **W4.** Add the A7.2 class, `shadow_identical` and the "persistent timeout" label to `a7rep`, or cite `failed_arms.json` and the recovery summaries in the write-up.
5. **W5, W7.** Append an erratum line (no rule change):
   - A7's "known" list also covered sibling-arm `termination_reason` and the suffix head of one BQ arm in 3 KIVI states;
   - E1.5's P2/P3 sentence is superseded by A7 and A7.E1.
6. **W6.** State "Holm over estimable members; m = 3 primary, m = 2 strict/pre-recovery".
7. **W10.** BFCL: "not registered" labels for K2 and A44; add the kivi_k16v16 BFCL row to `NOT_RUN`.
8. **W9.** Commit `analysis/fork/rot_gate/{verdict.json, validate_sp_q8.json, validate_sp_q8_ppl.json}`, or cite `rot_release_panel_{qr,sp}_q8.log`.
9. **W8, W11.** One sentence each in the KIVI method paragraph.

---

## Item-by-item findings

### 1. Protocol integrity and append-only chain: PASS

- **sha.** `sha256(docs/insights/NEWMETHOD_PANEL_PROTOCOL.md)` = `3bd7ef3301b62a9a4688be8b10405ce1f58157ae2327324cd06dbc4ead5ba8f6`.
  - It equals `PROTOCOL_SHA256` (`analyze_newmethod.py` line 68).
  - The working copy has no diff to HEAD and none since 744f7c4.
- **Chain.** Each version is a byte prefix of the next. Checked with `cmp -n <size(prev)>` on `git show <c>:<file>`:

| commit | PDT | amendment | bytes | sha256 prefix | script constant in the same commit |
|---|---|---|---|---|---|
| 870d1ba | 10-02 00:21 | nmp-v1 | 23,928 | 9cd5c979 | = |
| 0af849b | 10-02 06:26 | A1 | 33,421 | 28b78509 | = |
| 50fc648 | 10-02 13:25 | A2 | 38,303 | c6603f90 | = |
| 9285afc | 10-02 14:10 | A3 | 43,015 | da8b69ba | = |
| fae1fe3 | 10-02 14:21 | A4 | 48,080 | 0dc3143e | = |
| 79b4ab4 | 10-02 14:52 | A5 | 56,161 | f9f8b3a5 | = |
| fe6765e | 10-03 08:16 | A6 | 65,746 | 73bf5538 | = |
| 2f06102 | 10-03 08:55 | A6.E1 | 76,745 | b306cc70 | = |
| 10a5518 | 10-03 16:44 | A7 | 84,820 | ba743cee | = |
| 861ebff | 10-03 17:44 | A7.E1 | 86,692 | 3bd7ef33 | = |

- **Prefix shas named in the amendments.**
  - A7 states its prefix sha `b306cc70...` (the A6.E1 version); it matches 2f06102.
  - A7.E1 states none, but the A7 version (`ba743cee`) is an exact byte prefix of it.
- **Timing note.** A7's header says 16:50 PDT; the commit is 16:44:25. W100ab already records that the commit time is authoritative.

### 2. Completeness of phase 1 and the running A7 tasks: CONDITIONAL

**All finished:**
- **τ²:** `nmp_tau2_q8_<cell>_f0{1,2,3}`, 24/24 `done`.
  - Each log has exactly one start line and one `bank_u` completion line.
  - Every summary has the panel manifest sha, `n_rows` = `n_ok` = 85, `n_missing` = `n_errors` = 0, and every no-op passed (audit §2, consistent with the `--dry` reads).
- **Score:** `nmp_score_q8_<cell>_f0k`, 24/24 `done`; the last finished at 19:39:33 PDT.
  - Every `score_summary.json` has `n_rows` 85, `n_ok` 85, `n_missing` 0, `n_prompt_sha_ok` 85, `n_render_ok` 85.
  - Each `bank_rows_sha256` equals the sha of the current panel `bank_rows.jsonl`, and `bank_out` is the panel directory.
  - The reference token scores (`analysis/fork/token_scores/q8_{gptq_w4_d1,awq_w4,kvq_int8}/f0k`) are bound to the current Bank U rows (190 rows each).
- **BFCL:** `ext_q8_<cell>_bfcl_nmp1` for 7 cells, and 28 `nmp_bfcl_q8_<cell>_<cat>` forks, all `done`.
  - Every BFCL directory's QQ no-op passed (some W16 categories had 0 no-op items).
  - Replay guard: 0 inconsistent states.
  - kivi_k16v16 has no BFCL, as A4.1 specifies.
- **Gates (counted as A5.1 requires; also in `expansion_q8.json`):**
  - **Rotation cells:** `nmp_gate_{same,bank}_q8_<cell>` pass.
  - **KIVI cells:** only the `_fx` gates count, and all pass. The `_fx` gates run hook `30020b75`, the pre-fix gates `b82dfa5a`.
  - **kivi_k4v4 strict T1:** `gate_q8_toy4.json` `toy.verdict_strict.T1_strict_codes_scale_mn_deq_bitwise` = true. The original `verdict.T2_semantics` is false and `verdict_amended.T2_servingprec` true: this is the post-hoc revision disclosed in A4.3.
  - **Rotation gate:** `rot_release_gates_sp_q8.log` and `rot_release_panel_{qr,sp}_q8.log` show families `{"qr": true, "sp": true}` and all 5 cells released, with nothing held (W9 on the committed record).
- **Expansion record:**
  - written 2026-10-04 02:08:29Z (19:08 PDT), trigger "all phase-1 tasks finished", before T_decide;
  - 8/8 cells eligible;
  - projected 171.5 GPU-h, finishing after T_deadline, so `expand: false`.

**Running (at 19:50 PDT):**

| A7 task | node | arms | terminal so far | pending | in progress since |
|---|---|---|---|---|---|
| a7_rr1_q8_kivi_k2v2_f03 | node007 | 5 | b6a3454a4e6f976a QQ, dbdc689a3751d9dd QQ recovered; 01a17956873df0ef QQ failed again (persistent timeout) | f2b0916c7aa6d021 BQ, QQ | 18:56 |
| a7_rr1_q8_kivi_k4v4_f01 | node008 | 12 | 22e5640e91897669 QQ recovered | 11 | 18:23 (3b1c207abdf8ef45 QQ) |

- Both tasks have one start line in their logs. No `recovery_summary.json` exists yet, so nothing from these blocks is merged.
- KIVI decode at concurrency 1 runs at about 1 tok/s, so the 11 kivi_k4v4 arms may take many hours. This is why Q1 asks for a cutoff to be fixed in advance.

### 3. A7 compliance: PASS (terminal arms), CONDITIONAL (pending)

**Classification (A7.2, A7.E1).** `failed_arms.json` gives exactly one class per arm:
- 12 `service_failure_verified`: kivi_k4v4 f01, user simulator node004:8000 down 21:28:44-21:33:41;
- 10 `timeout_cause_not_established`: kivi_k2v2;
- 9 `other`: spinquant_w4a4 f01, user-simulator overload.

FORENSICS.md cites log lines for every arm. The classes follow A7.2's definitions as written:
- `other` was correctly kept out of the A7 re-run;
- the 9 `other` arms were re-run only after A7.E1 approved it.

**A7.3, checked independently on the 18 terminal arms** (`tau2_recovery/q8_*/f0*/rr1/{branches,recovery_rows.jsonl,recovery_summary.json}`, identity and timing fields only):

| check | result |
|---|---|
| state identical (state_id, history_sha, prompt_ids_sha, steps_left) | true on every completed state with a written row (14/14); `n_state_refused` 0 in the 3 summaries |
| forced first decision = recorded a_B / a_Q | 17/17 recovered arms |
| `shadow_identical` | 13/13 states in finished tasks (1 + 4 + 8) |
| `prefix_ok`, `env_hash_init_ok` | true, 17/17 |
| `sim_seed` | 626729 on 17/17, equal to the original arms' seed where one ran |
| tag suffix `-rr1` | 18/18 |
| concurrency | 1 in all 5 task specs; no `reuse_rerun` |
| single attempt | 1 start line per A7 task log; `autopilot_retry` "no" |
| server identity vs `a7_expect` and the original block | equal for all 5 tasks (recursive lookup of `canary`, `ckpt_sha256`, `effective_config_sha`, `hook_version`) |
| B/Q roles | verbatim JSON copies of the original `nmp_tau2_q8_<cell>_<blk>` task |
| original block untouched | the A7 outputs are a separate directory; `bank_u_arms` refuses `out == src_out` |

**Persistent timeout kept missing.**
- **The record.** `rr1/branches/01a17956873df0ef.json` QQ carries `error: litellm.Timeout ...` with `n_decisions` 31, the same decision as the original.
- **How the code handles it:**
  - `a7_apply` sets `Y_QQ` = None, marks QQ "failed again", and propagates None to BQ (`reuse=QQ`).
  - `a6_resolve` then classifies the new error from the re-run branch record. The class is missing, since Timeout is not an A6 signature.
  - The unit is excluded, so kivi_k2v2 f03 fails A3.3 under every view.

**Timing of the recovered timeout-class arms (A7.2 diagnosis).**
- Max decision `wall_seconds` per arm is 158.8 to 524.7 s. No attempt reached 600 s.
- `finish_reason` 'length' (1,024 tokens) occurs in 3 arms, all within 600 s.

**Merge logic (A7.4).**
- `a7_apply` overwrites only `rec["arms"]`, and `bank_u_arms` restricts those to recorded failed arms.
- A `reuse=XX` arm takes XX's new value.
- The `strict` and `prerecovery` views use the unmerged row from the same read. `plus` uses the merged row.
- `a6_prospective` derives from the merged primary, giving "A6.E1 sensitivities, with A7".
- `--selftest` covers a completed re-run, a failed re-run and reuse propagation (PASS).

**Gaps:** W2 (BB no-op), W3 (strict A7.2 clause), W4 (report fields), W11 (simulator replica).

### 4. Analysis code vs protocol: PASS with notes

| Element | Code (744f7c4) | Protocol | Status |
|---|---|---|---|
| Primary family | `PRIMARY` P1 quarot_w4 − gptq_w4_d1, P2 spinquant_w4a4 − quarot_w4a4, P3 kivi_k2v2 − kvq_int8; t over block-mean differences; Holm | A1.2 | match; Holm over estimable members (W6) |
| P3 fallback | `P3_K2V2_GATE_FAILED = False`; fires only on a gate failure | A7.5 (aligns the code with §1's gate-failure text; the skeleton fired on "no admitted τ² unit") | match; gates verified to pass |
| Secondary | T1, T2, T3, K2, A44_k2 (kivi_k2v2 − kivi_k16v16), A44_k4 (kivi_k4v4 − kivi_k16v16); no Holm | A1.2, A4.4 | match (744f7c4 adds only the two A44 tuples) |
| Kernel-path effect | per-cell D_cc of kivi_k16v16 in `tau2_cell` | A4.4 | present |
| KIVI pairing | A5.3 governs expansion only (expand false). A44 uses blocks complete in both cells (`tau2_contrast` common blocks): A44_k2 {f01, f02}; A44_k4 {f02, f03}, or f01-f03 if f01 recovers | A5.3, A4.4 | consistent |
| Reference cells | `take(..., "bank_u", BANK_U_SHA256)`: summary manifest sha must equal `e236ee64`; row `t, source_run, domain, task_id, block` must equal the panel row; U2B only; a no-op failure anywhere in the Bank U block quarantines | §2.5 | match (stricter on no-op) |
| Strict blocks | all 85 tasks with four arms, else the block is dropped; complete-case alongside | §7, A3.3 | match |
| Views | primary (A6+A7), strict (no A6/A7), pre-recovery (A6 as of b306cc70), A6 prospective (strict on Bank U rows), A6 + tool-call parse (with A7), each with its own Holm | A6, A6.E1, A7.4 | match |
| Phase 2 | refused unless `expansion_q8.json` has expand true | §11 | expand false; no f04-f06 directory exists |
| Holdout | `no_holdout()` asserts on every opened path; no glob reaches `holdout/` | §11 | match |
| Un-admitted inputs | no gate directory is read; `NM/tau2` holds only the 8 registered cells; BFCL loads `newmethod/bfcl/bfcl_q8_*` and `ext/dev` reference cells in `REF_BFCL` only | §1, A1.1, A4.1 | match |
| ΔD_cc | difference of per-cell D_cc | §4: Y_QB(m1) − Y_QB(m2) | equal iff Y_BB is identical per state; unverified only at the W2 rows |
| A7 report | counts only | A7.4: + class, `shadow_identical` | W4 |
| `--dry` admission | (below) | audit §6 | identical in all 5 views |

`--dry` (19:4x PDT), admitted blocks:
- **primary, A6 prospective, A6 + parse:** kivi_k2v2 {f01, f02} (f03 incomplete: airline 14, 19; retail 21, 99); kivi_k4v4 {f02, f03} (f01 incomplete: 8 tasks); every other cell, references included, f01-f03.
- **strict and pre-recovery:** kivi_k2v2 none; kivi_k4v4 {f02, f03}; spinquant_w4a4 {f02, f03}; every other cell f01-f03.
- **Other fields:** `tau2_log` empty, `expansion_ok` false, population 85.

**Fork-path stability between the Bank U references (finished 10-01 16:24) and phase 1 (from 10-02 12:49).**
- Commits touching `cloq/fork.py`, `fork_driver.py` or `context_policy.py` in that window are:
  - fb010bf: `search_task` and simctrl only;
  - 44527e1, 7009bec: Mistral-gated;
  - 87733f7: an additive mode;
  - d16f4ea: Gemma-gated.
- `run_branch` is unchanged since 44b0623 (09-30).
- So P1 and P3 compare the panel and the reference under the same Qwen `bank_u` path. `Q_prompt_ok` holds on every row.

### 5. Pre-registration hygiene: PASS with disclosures

**Evidence sources:**
- git commit times;
- ZFS `relatime` atimes on `analysis/fork/**` (holdout pruned);
- all Claude Code session transcripts on this host (`~/.claude/projects/**/*.jsonl`, main session and 327 subagents), scanned for tool calls that touch `tau2/q8_*`, `tau2_recovery`, `token_scores/q8_<new cell>`, `bfcl/bfcl_q8_*`, or run `analyze_newmethod.py --model q8` without `--dry` or `--selftest`.

**Findings:**
- **No q8 new-method analysis output exists.**
  - `analysis/fork/out/` contains no `newmethod_q8_*`.
  - The earlier outputs that mention the new cells (`q8ref_w4_nmp_20261003T140825Z`, `m24_interim_20261003T141416Z`) hold only "cell not admitted" placeholders for them.
  - The q8 interim loaded `--cells gptq_w4_d1,awq_w4,awq_w4_d1`, and `load_tau2` / `load_bfcl` skip other cells before opening any file.
- **No transcript tool call computed or printed a q8 new-method `Y`, effect or contrast** between phase-1 start (10-02 12:49) and now.
- **Before A6 (10-03 08:16), only recursive greps touched the q8 panel files.** The atime bursts match transcript commands:
  - 10-02 22:27:5x: `grep -rn "W100n" docs/ analysis/ scripts/` (05:27:28Z);
  - 10-03 06:43:40-06:44:20: `grep -rn 'W100[o-z]' docs/ analysis/` (06:42:35 PDT), which prints matching lines only (`| head`), and `grep -rln '...g12...' docs/ analysis/ scripts/` (06:44:05);
  - 10-03 07:18:50: `grep -rl "def _y" scripts/ analysis/ cloq/ | head -3` (07:18:49). It stopped early on SIGPIPE, which is why only 3 bank_rows, 1 scores file and 1 pyc changed atime.

  A6's status line ("The only fields read from them were effect-blind summary fields") is therefore slightly incomplete, but immaterial: these greps printed file names or lines matching unrelated strings.
- **Before A7 (16:44:25):**
  - the arm-error reads that A7 discloses;
  - the extra sibling-arm prints by the forensics agent at 16:36-16:39 (W5).
- **Before A7.E1 (17:44:59):** no read of any spinquant_w4a4 f01 arm's outcome fields was found.
- **Before the A4.4 implementation (19:33:21):**
  - the acceptance audit's disclosed print of one quarot_w4 f01 branch arm's outcome fields at 19:16:30 (transcript `agent-a9334f36d052fb020`). It is unrelated to the KIVI contrasts.
  - A4.4 itself has been in the protocol since 10-02 14:21, before any KIVI outcome existed, so 744f7c4 implements an existing rule.
- **Audit wording.** The audit's §2 "Endings" line reports termination-reason counts pooled over all 8 cells and 4 arms. That is an outcome-component aggregate, though not per arm or per cell, so it cannot inform any contrast. The audit's statement that it holds "no ... per-arm outcome aggregate" is literally true but should mention this line.
- **Limits of this evidence:**
  - compute-node reads via NFS do not update server-side atime here: score-task reads of `bank_rows.jsonl` left no atime trace;
  - processes outside Claude sessions on this host cannot be checked;
  - the outputs are untracked, so they were never on GitHub.

### 6. GO conditions: CONDITIONAL GO

- **Blocking:** C1 (W1).
- **At GO time:** C3 (guard and `--dry` re-check), C4 (pending-arm acceptance and the Q2 decision) and C5 (reviewer B).
- **Already satisfied:** C2 (score f03).
- **Non-blocking:** W2-W12 (disclosure, labels, traceability), of which W2 should be decided before the read.

---

# Part 2: Inline annotations

> "`exppilot_analysis.required()` lists no `a7_rr1_*` task, and the analysis runs once." (audit §TL;DR, Blocking GO 1)

**[W1] MAJOR: confirmed.**
- `required()` returns `nmp_{tau2,score}_q8_<cell>_f0k` plus `nmp_bfcl_q8_<cell>_*`; `step()` runs as soon as `left` is empty.
- All of these are `done` since 19:39:33 PDT, so a GO written now triggers the read at once, without the kivi_k2v2 f03 and kivi_k4v4 f01 A7 records.

> "3. **The A4.4 KIVI contrasts are missing from the analysis.**" (audit §8)

**Resolved** by 744f7c4 (19:33:21). `SECONDARY` now holds `("A44_k2", "kivi_k2v2", "kivi_k16v16"), ("A44_k4", "kivi_k4v4", "kivi_k16v16")` and nothing else changed. The commit precedes any q8 read, and W100ah logs it.

> "  - BB = the original BF16 continuation. It is re-run and checked for no-op equality on a 10% hash sample (`bank-u-noop-v1|state_key|cell`)." (§2.3)

**[W2] MAJOR (secondary contrasts):**
- For kivi_k4v4 f01 9749f30f7ffd3c41 and 95d6b21e8fc7af2b the no-op BB run errored, so `bank_u` skipped `noop_check` (`if noop and orig_arm and orig_arm in res and "error" not in res[orig_arm]`).
- `bank_u_arms` re-runs BB without `noop_check`, and `a7_apply` puts the re-run `Y` into `Y_BB`. The "original BF16 continuation" identity is therefore unverified at these two states.

> "- **Cross-method contrast on the same states** (τ², the headline): per state, ΔD_cc(m1, m2) = Y_QB(m1) − Y_QB(m2), averaged like the primary." (§4)

**[W2]:** `tau2_contrast` computes `u["E"][k] - v["E"][k]` with k = D_cc. That equals Y_QB(m1) − Y_QB(m2) only when Y_BB(m1) = Y_BB(m2) at the state. Add a per-state assertion or a reported count, or apply Q2(a), before the read.

> "  - any request times out again: the arm stays missing, labelled \"persistent timeout\", and its timing is reported." (A7.2)

**[W3] MINOR:**
- The code labels an arm "failed again" only on a `run_branch` error. A litellm retry that succeeds after a 600 s attempt would be merged.
- Verified absent for the 8 recovered kivi_k2v2 arms (max `wall_seconds` 524.7 s). Re-check f2b0916c7aa6d021 BQ/QQ when they land.

> "- The report lists, per cell and block, the arms re-run, completed and failed again, their A7.2 class and `shadow_identical`. Holm families, contrasts and margins are unchanged." (A7.4)

**[W4] MINOR:** `a7rep` has `rerun`, `failed again`, `states_completed` and `states_still_missing` only. There is no class, no `shadow_identical` and no "persistent timeout" label, and a refused state would be invisible.

> "- The errored arms, their error strings, `n_decisions` and blocks. These were read from `branches/<state_key>.json` error fields only. Block admission counts were also known (`analyze_newmethod.py --dry`)." (A7, "What was known")

**[W5] MINOR:**
- At 16:36:08 and 16:39:38 PDT, before the 16:44:25 commit, the forensics subagent also printed `termination_reason` and suffix length for the non-errored arms of three KIVI branch files, and the head of one kivi_k2v2 f01 BQ suffix.
- This is immaterial to the rule, but the sentence should be corrected by an erratum line.

> "The 31 q8 phase-1 τ² arms that stopped on a server-side error (kivi_k2v2 f01–f03: 10 `Timeout`; kivi_k4v4 f01: 12 `InternalServerError`; spinquant_w4a4 f01: 9 `Timeout`) get one controlled re-run each." (A7 TL;DR)

**[W7] MINOR:**
- As committed, A7.2 sent class `other` to "stays missing and is reported", so the TL;DR and A7.2 disagreed for the 9 spinquant arms until A7.E1.
- P2's third block exists only through A7.E1. Give the strict and pre-recovery P2 (k = 2) equal prominence.

> "- **The rule is unchanged:** they stay missing, labelled \"Q-server timeout, cause not established\". They decide P3 (kivi_k2v2 has no admissible block under any view) and cost P2 one block (spinquant_w4a4 f01)." (A6.E1, E1.5)

**[W7]:** Superseded by A7 and A7.E1. Under the primary, P3 has {f01, f02} and P2 has f01-f03. The write-up must not quote E1.5's consequence sentence as current.

> "- **Primary contrast family (Holm, two-sided α = .05, τ² D_cc, t over block-mean differences):**" (§7)

**[W6] MINOR:** In code the family is the estimable members (since 870d1ba). State m per view: 3 primary, 2 strict and pre-recovery.

> "- **`kivi_k2v2` phase 1** was released on the old gates. If its `_fx` gates fail, its panel output is reported as \"not admitted\", with the reason." (A4.2)

**[W8] MINOR, consistent with the data:**
- The `_fx` gates passed (gate_same at 18:02, after f01 and f02 had finished). The panel's hook `30020b75` equals the `_fx` gates'.
- The BFCL closed-loop run `ext_q8_kivi_k2v2_bfcl_nmp1` (deps: pre-fix gates) started 09:48, after f585ae3 (07:10). Its fork directories have 0 replay-inconsistent states.

> "- **Gates.** §2.4 applies to every cell, and phase-1 release is additionally conditional on the rotation gate (`rot_gate_check.py`), as already queued." (A1.1)

**[W9] MINOR:** The release did happen on a passing gate (`rot_release_panel_sp_q8.log`: `{"qr": true, "sp": true}`, released spinquant_w16 and spinquant_w4a4, held none). The committed `rot_gate/verdict.json` (cf03f74), however, still shows `sp.pass: false`. Commit the regenerated file.

> "- **BFCL panel B:** not registered for this cell. It is reported as \"not run\" unless it is amended in before any KIVI BFCL outcome is read." (A4.1)

**[W10] MINOR:** `NOT_RUN` lacks this row. `bfcl_stats` will print "cell not admitted" for A44_k2, A44_k4 and K2 on BFCL; the label should be "not registered on BFCL".

> "- **Servers.** The re-run task copies the original task's B and Q roles verbatim: checkpoint, serve_env, KIVI or rotation hook flags. The worker's canary and fingerprint checks apply. max_tokens, the 600 s request timeout, the step budget and the simulator seed are unchanged." (A7.3)

**Verified for B and Q (S5).** **[W11] MINOR:** The user-simulator endpoint differs from the original in 4 of 5 tasks, and the replica carries no fingerprint. The seed is equal (626729).

> "A7 was adopted after the arm errors and their counts per block had been seen (W100v, E1.5) and before any q8 new-method outcome or effect had been computed." (A7.7)

**Supported** by the transcript and atime evidence (§5). Add W5's sibling-arm prints for completeness.

> "  - **q8 new-method cells:** 22 `nmp_tau2_q8_*` phase-1 tasks were done, ... The only fields read from them were effect-blind summary fields: the expansion tool's (A5.2) and exppilot's `budget_ok` scan." (A6, status)

**Minor inaccuracy, immaterial:** Recursive greps also read these files at 06:43-06:44 and 07:18:50 on 10-03 (§5). They printed only names or lines matching unrelated patterns.

> "**No-op coverage gap (not a quarantine).** Two noop-sampled kivi_k4v4 f01 rows, 9749f30f7ffd3c41 and 95d6b21e8fc7af2b, have an errored BB, so their no-op check was never performed." (audit §4)

**Agreed on the facts; severity raised to W2.** Once the BB arms are re-run, this becomes a question about the baseline identity in K2 and A44_k4, not only about no-op coverage. Decide Q2 before the read.

> "P3_K2V2_GATE_FAILED = False" (`analyze_newmethod.py` line 98)

**Correct:** `nmp_gate_{same,bank}_q8_kivi_k2v2_fx` are `done` and pass, so the §1 fallback cannot fire (A7.5).

> `return con, holm({lab: con[lab].get("D_cc", {}).get("t_p_two_sided") for lab, _, _ in CT["primary"] if "D_cc" in con[lab]})` (`tau2_contrasts`)

**[W6]:** This is the estimable-members-only Holm rule, unchanged in substance since 870d1ba (where it was `R["tau2"]["holm_primary_D_cc"] = holm({... for lab, _, _ in PRIMARY if "D_cc" in con[lab]})`).

---

## Sources (local; no external URL was inspected)

**Protocol and code:**
- Protocol: `docs/insights/NEWMETHOD_PANEL_PROTOCOL.md` (all 10 committed versions via `git show`).
- Analysis: `analysis/fork/analyze_newmethod.py` (744f7c4), `analysis/fork/analyze_dev.py` (`Boot`, `summarise`, `t_interval`).
- Fork driver: `scripts/a6000/fork_driver.py` (`bank_u`, `bank_u_arms`, `noop_check`, `_y`).
- Analysis trigger: `scripts/a6000/exppilot_analysis.py` (`required`, `step`).
- Rotation gate: `scripts/a6000/rot_gate_check.py`, `scripts/a6000/make_tasks_rotpanel.py`.

**Audits and gate records:**
- Audit: `analysis/fork/out/q8_acceptance_audit_phase1_20261004T0226Z.md`.
- Expansion record: `analysis/fork/newmethod/expansion_q8.json`.
- Forensics: `analysis/fork/kivi_recovery/{FORENSICS.md,failed_arms.json}`.
- Reuse audit: `analysis/fork/reuse_audit/REUSE_AUDIT.md`.
- Gates: `analysis/fork/newmethod/gate/q8_*/{same/gate_same.json,bank/bank_summary.json}`, `analysis/fork/kivi_gate/gate_q8_toy4.json`, `analysis/fork/rot_gate/verdict.json` (working tree and cf03f74).

**Data and outputs (identity, timing and summary fields only):**
- Panel: `analysis/fork/newmethod/tau2/q8_*/f0{1,2,3}/{bank_summary.json,bank_rows.jsonl (arm_source/noop_sample/checks only)}`.
- Recovery: `analysis/fork/newmethod/tau2_recovery/q8_*/f0*/rr1/`.
- Token scores: `analysis/fork/newmethod/token_scores/q8_*/f0*/score_summary.json`, `analysis/fork/token_scores/q8_{gptq_w4_d1,awq_w4,kvq_int8}/f0*/score_summary.json`.
- BFCL: `analysis/fork/newmethod/bfcl/bfcl_q8_*/dev_summary.json` (no-op fields).
- Earlier outputs: `analysis/fork/out/{q8ref_w4_nmp_20261003T140825Z,m24_interim_20261003T141416Z,m24_interim_nmp_20261003T140821Z}.json` (cell lists only).

**Queue, logs and transcripts:**
- Queue: `/data/ziyangs/cloq_work/queue/{done,running}/{nmp_*_q8_*,a7_rr1_q8_*,ext_q8_*_bfcl_nmp1,rot_release_*}.json`.
- Logs: `/data/ziyangs/cloq_work/logs/tasks/{a7_rr1_q8_*,nmp_tau2_q8_*,nmp_score_q8_spinquant_w4a4_f03,rot_release_*,ext_q8_kivi_k2v2_bfcl_nmp1}.{log,servers.json,vllm.log}`.
- Research log: `docs/RESEARCH_LOG.md` (W100ab, W100ac, W100ae, W100ag; W100ah header only).
- Session transcripts: `/home/ziyangs/.claude/projects/-home-ziyangs/4a7ccb09-009e-4aee-b4c9-ef93691bb496{.jsonl,/subagents/*.jsonl}` (tool-call commands and timestamps only).
