# m24 (Mistral-Small-3.2-24B) new-method panel: acceptance review B (independent re-derivation)

Reviewer B of 2. Written 2026-10-03 ~19:30 PDT at repo HEAD e30be4d. I did not read reviewer A's output or the existing m24 budget audits or interim reports. Every admission result below was re-derived from the raw `bank_rows.jsonl`, `branches/` and `bank_summary.json` files, the manifest, the mask and the protocol text. I compared it with `--dry` only after that.

## TL;DR verdict

**Acceptable to unblock (write `queue/EXPPILOT_GO_newmethod_m24`) once `nmp_score_m24_rtn_w4_f03` is done and its output is valid. No blocking issue found.**

- **Admission re-derivation agrees with `analyze_newmethod.py --model m24 --dry`** in every view: primary A6, strict as preregistered, A6 prospective, A6 + tool-call parse, and pre-recovery. Each admitted block, incomplete task, A6 signature, producer and missing reason matches.
  - **Primary A6.** rtn_w4 admits {f01, f02, f03, f05, f06}. gptq_w4_d1 admits f01 through f06. M1 therefore uses 5 common blocks, {f01, f02, f03, f05, f06}.
  - **Strict as preregistered.** rtn_w4 admits {f03, f05, f06}. gptq_w4_d1 admits {f02, ..., f06}. M1 uses k = 3, {f03, f05, f06}.
  - **A6 + tool-call parse.** Both cells admit all 6 blocks, so M1 uses k = 6.
  - **A6 prospective** gives the same blocks as strict. **Pre-recovery** gives the same blocks as the primary, because m24 has no A7 records.
- **Expansion record: valid.**
  - `expansion_m24.json` was created once, at 04:53:03 PDT. Its file birth, mtime and ctime are all 04:53:03.22. It has one git commit (9739a66, 04:53:03) and 1 link.
  - It came after all 6 phase-1 τ² tasks had finished (the last at 04:43:19).
  - The phase-2 tasks first appear in the queue snapshot at 07:08:22, and they are absent at 06:38:18. The first phase-2 worker claim was at 07:12:59 and the first phase-2 output at 07:47:21.
  - It records expand = true with both cells eligible, and the 6 phase-2 tasks match `phase2_cells`.
- **Score tasks: 11 of 12 are done, and all 11 are bound to the current bank rows. `nmp_score_m24_rtn_w4_f03` is running.**
  - Its directory still holds the stale pre-fix output (n_ok 0/85, 0 usable rows).
  - The loader would read that file silently, which gives no KL for the 83 admitted rtn f03 states.
  - Exppilot waits for the task to be done, but only until T_deadline (2026-10-04 12:00 PDT).
- **Script checks.** The protocol, manifest and mask guards pass and `--selftest` passes. An audit-hooked `--dry` opened or listed no `holdout` path. Primary statistics read only admitted blocks.

**Blocking:** none.

**Precondition for GO (not a defect):**
- `nmp_score_m24_rtn_w4_f03` is done.
- Its `score_summary.json` has `bank_rows_sha256` = `f7a8c307d754...`, the current rtn f03 `bank_rows.jsonl`.
- Its `n_ok` covers the population: 84 is expected, with 83 population rows plus masked airline:13.

**Non-blocking items:** N1 to N7 below.

---

## 1. Undefined arms and admitted blocks, re-derived from raw files

**Method** (script reproduced in the Appendix; read-only; it prints no Y value):
- **Population.** I took the population from the protocol text alone: A3 excludes airline 13 and 44, uniformly. That leaves 83 tasks. I then asserted that it equals the frozen mask's `excluded_tasks` / `population`, and it does.
- **Rows.** For each of the 12 (cell, block) directories:
  - every row's identity (t, source_run, domain, task_id, block, sub, model) is asserted equal to its manifest row;
  - there are no duplicate tasks;
  - every defined Y is asserted to be in {0, 1} and is not otherwise read;
  - an arm is undefined iff `Y[arm] is None`.
- **Classification.** Each undefined arm was classified from its `branches/<state_key>.json` record using the protocol text:
  - A6.2: S1 = `InvalidFunctionCallException('Function name was ` and S3 = `ValueError('AssistantMessage must have either content or tool_calls`, in either quote style, with no `infra_cause` and `n_decisions` ≥ 1, are scored Y = 0;
  - A6.E1 E1.2: `JSONDecodeError` with `n_decisions` ≥ 1 in retail or airline stays missing in the primary and is Y = 0 only in the "plus" view;
  - everything else is missing;
  - reused arms follow their source arm.
- **Producer** (E1.4): `n_decisions` = 1 means the forced action (first letter of the arm); otherwise the controller (second letter). A JSON parse failure is always the controller's.
- **Consistency checks.** For every errored arm, the bank row's `arm_source` equals `"error: " + branch.error[:120]`.
  - No undefined arm has a source other than `error` or `reuse=`.
  - No branch file is missing.
  - All per-row `checks` (Q_prompt_ok and the no-op checks) pass.
  - No row-level `error` exists. The only row-level `missing_reason` values are the 7 manifest-missing source rows: airline 44 in f01–f06 and airline 13 in f01, all masked.

### 1a. Every undefined arm in the m24 panel (12 directories, 1020 rows)

| cell | block | task | in population | arm | branch error (prefix) | n_decisions | class (my reading) | producer |
|---|---|---|---|---|---|---|---|---|
| rtn_w4 | f01 | retail:51 | yes | QB | `InvalidFunctionCallException('Function name was YOU ARE BEING TRANSFERRED ...` | 1 | S1, Y = 0 | Q (forced a_Q) |
| rtn_w4 | f01 | retail:51 | yes | QQ | same | 1 | S1, Y = 0 | Q (forced a_Q) |
| rtn_w4 | f02 | retail:95 | yes | QQ | `InvalidFunctionCallException('Function name was YOU ARE BEING TRANSFERRED ...` | 3 | S1, Y = 0 | Q (controller) |
| gptq_w4_d1 | f01 | airline:2 | yes | BQ | `InvalidFunctionCallException('Function name was  but must be a-z ...` (empty name) | 7 | S1, Y = 0 | Q (controller) |
| rtn_w4 | f04 | **airline:10** | **yes** | BQ | `JSONDecodeError('Unterminated string starting at: line 1 column 217 ...')` | 25 | **missing in primary** (E1.2); Y = 0 in "plus" only | Q (controller) |
| rtn_w4 | f03 | airline:13 | no (masked) | BQ | `JSONDecodeError('Unterminated string ... column 34 ...')` | 2 | missing (E1.2); plus Y = 0 | Q |
| gptq_w4_d1 | f06 | airline:13 | no (masked) | QQ | `InvalidFunctionCallException('Function name was  but must be ...` | 57 | S1, Y = 0 (outside population) | Q |

- No S3 arm, no `infra_cause`, and no other exception type appears anywhere in the m24 panel.
- No arm is B-produced. So E1.4's "any B-produced Y = 0 in phase 2 is named" has nothing to name.
- The phase-1 rows agree with A6.4 and E1.4 exactly: retail:51 QB/QQ, retail:95 QQ, airline:2 BQ, and airline:13 BQ JSONDecodeError, with the stated `n_decisions` of 1, 3, 7 and 2.

### 1b. Admitted blocks (strict 83-task completeness, A3.3); mine vs `--dry`

Phase-2 blocks are allowed because `expansion_m24.json` has `expand: true`.

| cell / block | phase | primary A6 | strict prereg | A6 prospective (strict on phase 1) | A6 + tool-call parse | `--dry` agrees |
|---|---|---|---|---|---|---|
| rtn_w4 f01 | 1 | admitted (via A6: retail:51) | **no** (retail:51) | no | admitted | yes |
| rtn_w4 f02 | 1 | admitted (via A6: retail:95) | **no** (retail:95) | no | admitted | yes |
| rtn_w4 f03 | 1 | admitted | admitted | admitted | admitted | yes |
| rtn_w4 f04 | 2 | **no** (airline:10, JSONDecodeError) | no | no | admitted | yes |
| rtn_w4 f05 | 2 | admitted | admitted | admitted | admitted | yes |
| rtn_w4 f06 | 2 | admitted | admitted | admitted | admitted | yes |
| gptq_w4_d1 f01 | 1 | admitted (via A6: airline:2) | **no** (airline:2) | no | admitted | yes |
| gptq_w4_d1 f02–f06 | 1, 2 | admitted | admitted | admitted | admitted | yes |

- **M1 = gptq_w4_d1 − rtn_w4, blocks complete in both cells:**
  - primary {f01, f02, f03, f05, f06}, k = 5;
  - strict and prospective {f03, f05, f06}, k = 3;
  - plus all six, k = 6;
  - pre-recovery equals the primary.
- `--dry` gives `tau2_log` = {} (nothing refused or quarantined) and `expansion_ok` = true.
- Its `a6` report lists exactly the 7 arms of table 1a, with the same signatures, producers and missing reasons. `complete_via_a6` = 1 in rtn f01, rtn f02 and gptq f01.
- **Disagreements: none.**

### 1c. Other row-level checks (effect-blind)

- **Summaries.** All 12 `bank_summary.json` have manifest sha `53295b64...`, the right `spec.blocks` and `spec.cell`, `subs` ["U2B"] and no `limit_per_sub`. They also have:
  - n_rows 85, n_errors 0;
  - n_missing = the manifest-missing rows of the block (f01: 2; others: 1), and n_ok = n_rows − n_missing;
  - every no-op passed (5/5, 8/8, 9/9, 11/11, 8/8, 9/9 for rtn; 5/5, 11/11, 12/12, 8/8, 7/7, 5/5 for gptq).
- **No change after finish.** In every block, no file under the directory has an mtime or ctime later than its queue task's `finished`.
- **Equality reuse is valid** (§2.3; checked independently of the W100ae reuse audit). In the 12 panel blocks, 423 rows carry `reuse=` arms, and all are `exact_agreement` true.
  - In all 423, a_B and a_Q are identical in content, tool-call ids, names and argument JSON (stored key order), with 0 differences.
  - The branch history is rendered from these messages, so the reused QB ≡ BB and BQ ≡ QQ are the same continuation.

## 2. Expansion record `analysis/fork/newmethod/expansion_m24.json` (sha256 `58fdb68f...`)

- **Written once.**
  - The file's birth, mtime and ctime are all 2026-10-03 04:53:03.22 PDT, so it has not been rewritten since creation. It has 1 link.
  - The record's own `now` is 11:53:02.49Z (04:53:02 PDT).
  - Exactly one git commit touches it: 9739a66 at 04:53:03 PDT, "expansion_m24 decision". The working copy is clean.
- **Inputs unchanged since the decision.** All 10 `inputs.files_sha256` entries (4 gate files and 6 phase-1 `bank_summary.json`) equal the current files byte for byte.
- **Tool version.**
  - `builder_sha256` `eb505f12...` equals `make_newmethod_panel.py` at 79b4ab4 (A5), which is also the current file.
  - `guard.protocol_sha256` `f9f8b3a5...` is the A5 protocol, the version in force at 04:53.
- **Trigger (a), all phase-1 tasks finished, is correct.** The six `nmp_tau2_m24_*_f0{1,2,3}` tasks finished between 00:45:28 and 04:43:19 PDT, all before 04:53:02. T_decide (2026-10-04 00:00 PDT) had not been reached.
- **Eligibility (A5.1/A5.2), re-checked from the summary fields:**
  - both cells pass their bank gates (`gate_pass` true; 10/10 no-ops, 0 errors, 0 missing);
  - both pass gate_same (verdict.pass true, n_errors 0);
  - all 3 phase-1 blocks of each cell are complete as defined in 1c.
  - `eligible` = [rtn_w4, gptq_w4_d1] and `ineligible` = {}.
- **Projected cost.**
  - Phase-1 seconds × 4 GPUs: rtn 10323.0 s → 11.470 GPU-h; gptq 16182.2 s → 17.980 GPU-h.
  - P = 1.25 × 29.450 = 36.813 (the record has 36.812); wall = P / 8 = 4.602 h.
  - Projected finish 16:29:08Z (09:29 PDT on 10-03) ≤ T_deadline 2026-10-04 12:00 PDT, so expand = true. That is correct.
- **Phase-2 tasks queued after the record.** Independent evidence comes from the committed queue snapshots `docs/a6000/QUEUE.md`:
  - 924e02a (04:38), ea18f7c (05:08), e832765 (05:38), e4e2510 (06:08) and 69a201f (06:38:18; todo 21) contain no `nmp_tau2_m24_*_f0{4,5,6}` id in any section;
  - 0b1b206 (07:08:22; todo 34) lists all six in todo.
  - This matches W100o's "queued 07:05".
- **Phase-2 outputs came after the record.** The earliest phase-2 worker claim was gptq f04 at 07:12:59 PDT (`worker.log` birth), and the earliest phase-2 file was gptq f04 at 07:47:21. That is 2 h 54 min after the record. The rtn phase-2 directories were created at 13:45, 13:58 and 15:10.
- **Phase-2 tasks match `phase2_cells`.**
  - Tasks: `nmp_tau2_m24_{rtn_w4,gptq_w4_d1}_f0{4,5,6}`, all done, finished 08:24:35 to 16:23:04 PDT.
  - Each spec equals the cell's phase-1 spec except `blocks` and `out`: mode bank_u, manifest sha, subs U2B, noop_frac 0.1, concurrency 8.
  - The Q and B roles are identical to phase 1, with gpus 4 and gpus_per_role 2.
  - The deps are the passing `_r2` gate_same, the bank gate and the bfpair source task.

**N1 (non-blocking, provenance).** `configs.<cell>.gates.same` names the r1 tasks `nmp_gate_same_m24_<cell>`, with their task sha and finish time (21:57 and 22:25 PDT). Those tasks' own `result.verdict.pass` is **false**. The `gate_same.json` that the record hashed and judged is the **r2** output:
- `spec.fail_loud` true;
- mtime 23:45:40 (rtn) and 23:51:34 (gptq), equal to the r2 finish times;
- r1's output is in `same_r1_superseded/`, verdict false; its `SUPERSEDED` note says the failure was 1 row error from selecting airline 44, with idcheck 8/8.

The eligibility verdict is right in substance, because r2 passed and every panel task depends on r2. The record's task attribution is wrong. W100o already notes this. The paper's "expansion decision with its inputs" (§7) should state it. It does not affect the analysis, which reads only `expand`.

## 3. Score tasks `nmp_score_m24_*` and the loader

| cell | f01 | f02 | f03 | f04 | f05 | f06 |
|---|---|---|---|---|---|---|
| rtn_w4 | done; n_ok 82/85 (see N3) | done; 84/85 | **running** (rows prepared 19:19:15 PDT, prompt sha ok 84/85); directory holds the **stale pre-fix output**, 03:29:53, n_ok 0/85, 0 rows with a_B tokens | done; 84/85 | done; 84/85 | done; 84/85 |
| gptq_w4_d1 | done; 83/85 | done; 84/85 | done; 84/85 | done; 84/85 | done; 84/85 | done; 84/85 |

- **All 11 finished summaries are bound and post-fix.**
  - Each has `bank_rows_sha256` equal to the sha256 of the current `tau2/m24_<cell>/<blk>/bank_rows.jsonl`.
  - `spec.bank_out` is the panel directory and `spec.out` = `analysis/fork/newmethod/token_scores/m24_<cell>/<blk>`, which is exactly where the loader reads.
  - All were written between 15:56 and 18:40 PDT, after the W100o render fix. The missing rows are the manifest-missing source rows, plus N3.
- **Loader.** `analyze_newmethod.load_scores` (L435–452) reads `NM/token_scores/<model>_<cell>/<blk>/scores.jsonl.gz`, with `ref` False for m24. `main()` calls it only in the full run (L730–736), and only for blocks admitted in the primary.
  - It returns `{}` without warning if the file is absent.
  - It skips every row without `acts.a_B.tok`.
  - It never checks `score_summary.json` (n_ok, `bank_rows_sha256`).
- **Consequence of a missing or stale file.** Those states carry no KL. `fidelity()` then computes:
  - the KLu_mean tertile cut points (pooled over admitted phase-1 states);
  - the per-cell KL summaries;
  - the M / M_cc / |D_cc| by KL tertile;
  - the Spearman across cells.

  All of these are computed without those states, with no error. Only `n_scored` / `n_scored_phase1` in the JSON reveal it; the markdown does not show it.
  - **The primary τ² (D_cc, G, ..., M1) and BFCL estimates are unaffected**, because fidelity is §9, descriptive only.
  - With today's files, a run would score 0 of the 83 rtn f03 states and shift the phase-1 tertile cuts.
- **Exppilot guard.** `exppilot_analysis.required()` includes all 12 `nmp_score_m24_*` tasks. After GO, the analysis waits until they are `done`, but only until T_deadline 2026-10-04 12:00 PDT. After that it runs on whatever exists, and with the stale file that silently means 0 rtn f03 scores. If the running task fails, the GO alone does not prevent this.

## 4. Script checks

- **Guard** (`guard("m24")`, exercised by `--dry` and `--selftest`):
  - protocol sha256 `3bd7ef33...` = `PROTOCOL_SHA256` (A7.E1);
  - manifest `53295b64...` = `MANIFESTS["m24"]`;
  - mask `b03a8a91...` = `MASKS["m24"]`, and `applies_to.manifest_sha256` equals the manifest sha.
  - `analyze_newmethod.py` is committed and clean: sha256 `4deda9bb...`, last commit 861ebff.
- **`--selftest`: PASS** (`selftest`, `a6` and `a7` all "PASS").
- **`--dry` exits with rc 0 and writes nothing.** No `newmethod_m24_*` file exists in `analysis/fork/out`.
- **Holdout and un-admitted blocks.** I ran `--dry` under a Python audit hook that logs every `open`, `os.listdir` and `os.scandir`.
  - It shows 0 paths containing `holdout`.
  - It shows no `tau2_recovery` or `analysis/fork/bank_u` access (m24 has no A7 records and no reference cells).
  - τ² files opened: each block's `bank_summary.json` and `bank_rows.jsonl`, plus `branches/<sk>.json` only for the rows of table 1a.
  - The full-run-only readers (`load_scores`, `a7_records`) use fixed non-holdout roots through `no_holdout`.
  - The primary statistics (`tau2_cell`, `tau2_contrasts`, `fidelity`, score loading) take only `cells` from `strict_blocks`, which are admitted blocks. The complete-case, available-rows and four labelled views are separate, labelled outputs with their own Holm families.
- **Changes since A6.E1 (2f06102, 08:55 PDT).** The script diff to HEAD adds only A7 (`a7_apply`, `a7_records`, the `prerecovery` view) and the P3 flag. For m24 there are no A7 records, so `prerecovery` equals the primary, as confirmed in `--dry`.

## 5. Non-blocking items

- **N1.** The expansion record attributes gate_same to the failed r1 tasks while it hashed the passing r2 files (§2). This is a provenance wording fix for the report. The record must not be edited, because it is write-once.
- **N2.** `load_scores` misses data silently (§3). Before writing GO, check the rtn f03 `score_summary.json`: the `bank_rows_sha256` and `n_ok` stated in the TL;DR. If the task fails, hold the GO, or have the analysis note that rtn f03 has no KL.
- **N3.** In rtn_w4 f01, retail:51 has no token score. The score prep raised `InvalidFunctionCallException` on a_Q, the same invalid-name action that A6 scores Y = 0. So in rtn f01, 82 of 83 population states are scored, and the KL-stratified §9 tables exclude exactly this one Q-failure state. State this with the fidelity results.
- **N4.** gptq_w4_d1 f02 has `budget_ok` false at summary level. It comes from one arm, airline:45 QQ, which is in `context_overflow_arms`.
  - For overflow records `budget_recount` is None by construction (`cloq/fork.py::run_branch`), so `budget_check` cannot pass.
  - That arm is Y = 0 by the W10/W70 rule and is defined.
  - It is not an admission issue, and A5.2 does not condition on it.
- **N5.** The primary and the "plus" sensitivity now differ (k = 5 vs 6), because of rtn f04 airline:10 (JSONDecodeError, n_decisions 25).
  - This is the prespecified E1.2 cost.
  - The E1.2 rule was committed at 08:55:59 PDT, before rtn f04 existed (directory created 13:45:16), so this loss is prospective, not post hoc.
  - E1.9's "the plus view equals the primary" was a phase-1 statement and no longer holds for six blocks. The write-up should say so.
  - A7 (16:44 PDT) states that "A7 does not apply to m24". That sentence was written after the rtn f04 error record existed. Its basis is the error class (agent tool-call parse), not an outcome, and it follows E1.2.
- **N6.** `expansion_ok()` checks only `expand is True`, not that the cell is in `phase2_cells`. There is no consequence for m24, where both cells are listed and both ran phase 2, but it would matter for a model with a cell outside `phase2_cells`.
- **N7.** The E1.7 precondition (confirm or revert S3 and the q8 scope before any GO) is recorded as closed in RESEARCH_LOG W100ae ("S3 and the q8 scope of A6 are kept"). In any case S3 matches no m24 arm (table 1a), so either ruling leaves m24 unchanged.

## 6. Effect-blindness of this review

Read:
- `bank_rows.jsonl`: identity fields, `arm_source`, which arms have Y = None, `exact_agreement`, `checks`, `budget_ok`, `context_overflow_arms`, and a_B / a_Q of the reuse rows;
- `branches/<sk>.json`: only the 7 errored arms (`error`, `n_decisions`, `infra_cause`);
- `bank_summary.json` count fields;
- `score_summary.json` count and sha fields;
- in the stale rtn f03 `scores.jsonl.gz`, only the presence of `acts.a_B.tok`;
- queue task metadata, but not `result`, except the gate tasks' `verdict.pass`;
- the `--dry` and `--selftest` output.

Defined Y values were only asserted to be in {0, 1}. No Y, effect, contrast, success rate or per-arm aggregate was computed or printed.

**One disclosed deviation.** While tracing the gptq f02 `budget_ok` flag, I printed `termination_reason` and the step counters of the three run arms of one state (gptq_w4_d1 f02 airline:45). That is per-arm termination information for a single state, part of Y's definition. It was not aggregated, and it does not enter any conclusion here other than N4.

I did not open `analysis/fork/holdout/`. I modified no existing file or queue entry and made no commit.

## Reproduce

```
cd /data/ziyangs/cloq && source scripts/a6000/env.sh
python analysis/fork/analyze_newmethod.py --model m24 --dry      # compare with tables 1a/1b
python analysis/fork/analyze_newmethod.py --selftest
python3 <appendix script>                                         # independent derivation, prints no Y
```

Evidence paths:
- `manifests/fork/newmethod_panel_v1_m24.json` and `newmethod_panel_v1_m24_mask_v1.json`;
- `analysis/fork/newmethod/tau2/m24_{rtn_w4,gptq_w4_d1}/f0{1..6}/` and `analysis/fork/newmethod/token_scores/m24_*/f0*/score_summary.json`;
- `analysis/fork/newmethod/expansion_m24.json` and `analysis/fork/newmethod/gate/m24_*/{same,same_r1_superseded,bank}/`;
- `/data/ziyangs/cloq_work/queue/{done,running}/nmp_*_m24_*.json` and `/data/ziyangs/cloq_work/logs/tasks/nmp_tau2_m24_*.worker.log` (claim times);
- git `docs/a6000/QUEUE.md` at 69a201f and 0b1b206;
- `scripts/a6000/exppilot_analysis.py` (`required`, `step`).

## Appendix: independent derivation script (read-only; prints no Y)

This is a condensed form of the script I ran; the full version also printed the summary and row-check fields of §1c. I extracted this exact text from this file and re-ran it. It reproduces the admitted blocks of table 1b in every view, and it lists 20 undefined entries: the 6 rows (7 arms) of table 1a plus the 14 manifest-missing row records (7 per cell).

```python
import json, re, sys
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
MAN = json.loads((ROOT / "manifests/fork/newmethod_panel_v1_m24.json").read_text())
MASK = json.loads((ROOT / "manifests/fork/newmethod_panel_v1_m24_mask_v1.json").read_text())
EXP = json.loads((ROOT / "analysis/fork/newmethod/expansion_m24.json").read_text())
ARMS = ("BB", "BQ", "QB", "QQ")
EXCL = {"airline|13", "airline|44"}                       # protocol A3 text
tasks = {f"{r['domain']}|{r['task_id']}" for r in MAN["rows"]}
POP = tasks - EXCL
assert len(tasks) == 85 and len(POP) == 83
assert set(MASK["excluded_tasks"]) == EXCL and set(MASK["population"]) == POP
rows = {r["state_key"]: r for r in MAN["rows"]}

def classify(rec, domain):                               # A6.2 / A6.E1 from the protocol text
    if not isinstance(rec, dict) or "error" not in rec:
        return "missing", "missing", "no branch error record"
    if rec.get("infra_cause"):
        return "missing", "missing", f"infra_cause {rec['infra_cause']}"
    e, nd = str(rec["error"]), int(rec.get("n_decisions") or 0)
    s1 = e.startswith("InvalidFunctionCallException('Function name was ") or e.startswith('InvalidFunctionCallException("Function name was ')
    s3 = e.startswith("ValueError('AssistantMessage must have either content or tool_calls") or e.startswith('ValueError("AssistantMessage must have either content or tool_calls')
    jd = e.startswith("JSONDecodeError(")
    if (s1 or s3) and nd >= 1:
        return "Y0", "Y0", "S1" if s1 else "S3"
    if s1 or s3:
        return "missing", "missing", ("S1" if s1 else "S3") + " n_decisions 0"
    if jd and nd >= 1 and domain in ("retail", "airline"):
        return "missing", "Y0", "JSONDecodeError (E1.2)"
    return "missing", "missing", e[:60]

out = {"undefined": [], "blocks": {}}
for cell in ("rtn_w4", "gptq_w4_d1"):
    for blk in ("f01", "f02", "f03", "f04", "f05", "f06"):
        d = ROOT / "analysis/fork/newmethod/tau2" / f"m24_{cell}" / blk
        seen, comp = {}, {"strict": set(), "a6": set(), "plus": set()}
        for x in [json.loads(l) for l in (d / "bank_rows.jsonl").read_text().splitlines() if l.strip()]:
            r = rows[x["state_key"]]
            assert all(x[k] == r[k] for k in ("t", "source_run", "domain", "task_id", "block", "sub", "model"))
            task = f"{x['domain']}|{x['task_id']}"
            assert task not in seen; seen[task] = x["state_key"]
            if "missing_reason" in x or "error" in x:
                out["undefined"].append((cell, blk, task, task in POP, "row", str(x.get("missing_reason") or x.get("error"))[:80])); continue
            Y, src = x["Y"], x["arm_source"]
            und = [a for a in ARMS if Y[a] is None]
            assert all(Y[a] in (0, 1) for a in ARMS if Y[a] is not None)
            if not und:
                for v in comp: comp[v].add(task)
                continue
            br = json.loads((d / "branches" / f"{x['state_key']}.json").read_text())
            cls = {}
            for a in und:
                sa = str(src[a])
                if sa.startswith("error"):
                    assert sa == "error: " + br[a]["error"][:120]
                    cp, cplus, lab = classify(br.get(a), x["domain"])
                    nd = int(br[a].get("n_decisions") or 0)
                    prod = a[1] if lab.startswith("JSON") or nd >= 2 else a[0]
                    cls[a] = {"primary": cp, "plus": cplus, "label": lab, "n_decisions": nd, "producer": prod}
                elif sa.startswith("reuse="):
                    cls[a] = {"src": sa}
                else:
                    cls[a] = {"primary": "missing", "plus": "missing", "label": "undefined, not error/reuse"}
            for a, c in cls.items():
                if "src" in c:
                    b_ = cls.get(c["src"][6:]) or {"primary": "missing", "plus": "missing"}
                    c.update(primary=b_["primary"], plus=b_["plus"], label="reuse")
            if all(c["primary"] == "Y0" for c in cls.values()): comp["a6"].add(task)
            if all(c["plus"] == "Y0" for c in cls.values()): comp["plus"].add(task)
            out["undefined"].append((cell, blk, task, task in POP, cls))
        phase = MAN["tau2"]["phase"][blk]
        ok = phase == 1 or EXP.get("expand") is True
        out["blocks"][f"{cell}/{blk}"] = {v: ok and POP <= comp[v] for v in comp} | {
            "prospective": ok and POP <= (comp["strict"] if phase == 1 else comp["a6"])}
print(json.dumps(out, indent=1, default=str))
```
