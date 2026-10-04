# Reuse audit: canonical-equality arm reuse vs token identity

Written 2026-10-03 PDT (W100ae CPU scan; read-only, no GPU, holdout pruned and never opened). Repo HEAD when written: 43dcc37.
Machine-readable flagged list: `reuse_flagged.json` (same directory).

**TL;DR**
- **Checked:** every equality-based reused arm under `analysis/fork/`, 86 output directories:
  - 3,930 bank_u rows with `exact_agreement = true` (`QB`/`BB` reuse, `BQ = reuse=QQ`);
  - 184 bank_u_q0 rows (`c.Q0 = reuse=B.Q0`);
  - total 4,114 rows and 8,044 reused arms. Canonical equality re-verified on all of them (4,114/4,114).
- **Test:** each a_B/a_Q pair was rendered with the model's own chat template and tokenizer, the way it appears in the next prompt:
  - Qwen3-4B-Instruct-2507 and Qwen3-8B through the HF tokenizer;
  - m24 through `cloq.mistral_render.MistralChatRender` on the tekken.json under the models.json `src_path`. This renderer also prints tool-call ids.
  - An ordered, type-preserving JSON view of the arguments gave the same verdict on every row.
- **Flagged: 1 row, 2 reused arms**, in `analysis/fork/bank_u/q4_awq_w4/f01` (task `bank_u_q4_awq_w4_f01`):
  - state 7411758182009c20, airline:30, t = 6, U2B;
  - reused arms: `QB = reuse=BB` and `BQ = reuse=QQ`;
  - the difference is the key order inside `arguments.flights[0]`, which changes 24 token positions;
  - the decision-7 prompt is `600f0c14...` after a_Q and `211d510b...` after a_B (7,016 tokens each).
- **Flagged count by directory:** 1 in `bank_u/q4_awq_w4/f01`, 0 in each of the other 85 directories. The zeros cover:
  - every q8 and every m24 directory;
  - every gate directory;
  - every Q0 directory;
  - commonstate ref_d1;
  - every newmethod directory.
- **This confirms the E-2 statement for the GPTQ reference arms.** The reference rows had 0 flagged out of 776:
  - q4 gptq_w4_d1 f01-f03: 290;
  - q8 gptq_w4_d1 f01-f03: 349;
  - ref_d1 f04-f06: 137.
- **Independent cross-check (token scores):** 3,514 of the reuse rows have `score_driver` generated ids.
  - 3,470 have identical generated ids for a_B and a_Q, which is enough for an identical render.
  - 1 has differing ids where both actions' template ids equal their generated ids. It is the flagged row.
  - 43 are inconclusive, all render-identical in the scan:
    - 9 m24 rows whose tool-call ids were replaced after generation;
    - 34 m24_rtn_w4 f03 rows with no ids yet.
- **Validation coverage of the flagged row inside Bank U: none.**
  - It is not a noop sample, so BB = orig was not re-run. A noop re-run would not test a reuse anyway.
  - It is not in the Q0 subsample and not a simctrl unit.
  - No `reuse_rerun` task was in the queue at scan time.
  - One render-identical arm has been measured, for QB only: commonstate `q4/panel/d2_bf16/f01` arm QB (a_d2, BF16). Its Y = 0. BQ (a_BF16 then AWQ) has never been run.
- **Downstream consumers of the flagged row:**
  - `analyze_bank_u.py`, giving bank_u_f01 and bank_u_f01_f02_f03, which are cited at:
    - appendix.tex L278/282/301/317/330;
    - appendix_moved.tex L50/51/53/68;
    - results_r1.tex L27.
  - `analyze_token_mech.py` f01 development units, giving token_mech_20261001T185031Z and token_mech_20261002T003130Z, which are cited at:
    - appendix_moved.tex L73-77;
    - results_r3.tex L13.
  - Not consumed by Q0, simctrl, oracle_trigger, commonstate, newmethod or sameprec_split.

## 1. Flagged rows

| directory | bank task | state_key | sub | model | cell | block | task | t | reused arms | difference | noop / validation | Y (per arm, source) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `analysis/fork/bank_u/q4_awq_w4/f01` | `bank_u_q4_awq_w4_f01` | 7411758182009c20 | U2B | q4 | awq_w4 | f01 | airline:30 | 6 | QB=reuse=BB, BQ=reuse=QQ | key order in `tool_calls[0].arguments.flights[0]` (a_B: flight_number, date, origin, destination; a_Q: flight_number, origin, destination, date); no whitespace or number-format difference | noop_sample false; checks {Q_prompt_ok: true}; q0 false; not re-run | QQ 0 (run), BB 0 (orig), QB 0 (reuse=BB), BQ 0 (reuse=QQ) |

Token-level evidence for this row:
- **Minimal render** (user, action, tool result; Qwen3-4B-Instruct-2507 @ cdbee75f):
  - 119 vs 119 tokens; 24 positions differ, tokens 59-84;
  - a_B segment: `date": "2024-05-19", "origin": "LAS", "destination": "IAH`;
  - a_Q segment: `origin": "LAS", "destination": "IAH", "date": "2024-05-19`.
- **Full context, decision 7 prompt ids:**
  - after a_B: `211d510be400b5ed...` (7,016 tokens), from `runs/a6k2_q4_bfpair_f01/airline/decisions.jsonl` (orig BB);
  - after a_Q: `600f0c14030fd1ac...` (7,016 tokens), from `branches/7411758182009c20.json` QQ `decisions[1]`.
  - So the reused QB would have conditioned on `600f0c14`, not BB's `211d510b`. The reused BQ would have conditioned on `211d510b`, not QQ's `600f0c14`.
- **Token scores** (`analysis/fork/token_scores/q4_awq_w4/f01/scores.jsonl.gz`):
  - `same_ids = false`;
  - both `*_template_eq_generated = true`;
  - 96 ids each.
- **Same mechanism as the q4 f01 quarantine** (`analysis/fork/commonstate_replay_check/Q4_F01_IDENTITY.md`): a_Q (AWQ) has the same ordered arguments as a_d2.
  - The GPTQ d1 and KV8 rows at this state are render-identical to a_B, so they are not flagged.

## 2. Counts per directory

Rows = rows with outcomes. Reuse rows = rows with at least one `reuse=` arm, split into tool-call and text actions. Flagged = canonically equal but token-different.

| group | dirs | rows | reuse rows | tool-call / text | reused arms | flagged rows (arms) |
|---|---|---|---|---|---|---|
| bank_u gate | 6 | 180 | 120 | 100 / 20 | 240 | 0 (0) |
| bank_u native | 18 | 3420 | 2019 | 1655 / 364 | 4038 | 1 (2) |
| commonstate ref_d1 (bank_u) | 3 | 255 | 137 | 124 / 13 | 274 | 0 (0) |
| newmethod gate (bank_u) | 12 | 120 | 59 | 56 / 3 | 118 | 0 (0) |
| newmethod tau2 (bank_u) | 35 | 2961 | 1595 | 1272 / 323 | 3190 | 0 (0) |
| bank_u Q0 (bank_u_q0) | 12 | 292 | 184 | 148 / 36 | 184 | 0 (0) |
| **total** | 86 | 7228 | 4114 | 3355 / 759 | 8044 | 1 (2) |

By model:
- q4: 1085 reuse rows, 1 flagged;
- q8: 2598 reuse rows, 0 flagged;
- m24: 431 reuse rows, 0 flagged.

| directory | queue task (done) | mode | model | rows | reuse rows (tool-call / text) | reused arms | flagged rows (arms) |
|---|---|---|---|---|---|---|---|
| `analysis/fork/bank_u/gate/q4_awq_w4/f01` | `bank_u_gate_q4_awq_w4` | bank_u | q4 | 30 | 19 (15 / 4) | 38 | 0 (0) |
| `analysis/fork/bank_u/gate/q4_gptq_w4_d1/f01` | `bank_u_gate_q4_gptq_w4_d1` | bank_u | q4 | 30 | 17 (14 / 3) | 34 | 0 (0) |
| `analysis/fork/bank_u/gate/q4_kvq_int8/f01` | `bank_u_gate_q4_kvq_int8` | bank_u | q4 | 30 | 24 (16 / 8) | 48 | 0 (0) |
| `analysis/fork/bank_u/gate/q8_awq_w4/f01` | `bank_u_gate_q8_awq_w4` | bank_u | q8 | 30 | 16 (15 / 1) | 32 | 0 (0) |
| `analysis/fork/bank_u/gate/q8_gptq_w4_d1/f01` | `bank_u_gate_q8_gptq_w4_d1` | bank_u | q8 | 30 | 21 (19 / 2) | 42 | 0 (0) |
| `analysis/fork/bank_u/gate/q8_kvq_int8/f01` | `bank_u_gate_q8_kvq_int8` | bank_u | q8 | 30 | 23 (21 / 2) | 46 | 0 (0) |
| `analysis/fork/bank_u/q4_awq_w4/f01` | `bank_u_q4_awq_w4_f01` | bank_u | q4 | 190 | 89 (80 / 9) | 178 | 1 (2) |
| `analysis/fork/bank_u/q4_awq_w4/f02` | `bank_u_q4_awq_w4_f02` | bank_u | q4 | 190 | 82 (74 / 8) | 164 | 0 (0) |
| `analysis/fork/bank_u/q4_awq_w4/f03` | `bank_u_q4_awq_w4_f03` | bank_u | q4 | 190 | 83 (75 / 8) | 166 | 0 (0) |
| `analysis/fork/bank_u/q4_gptq_w4_d1/f01` | `bank_u_q4_gptq_w4_d1_f01` | bank_u | q4 | 190 | 93 (85 / 8) | 186 | 0 (0) |
| `analysis/fork/bank_u/q4_gptq_w4_d1/f02` | `bank_u_q4_gptq_w4_d1_f02` | bank_u | q4 | 190 | 102 (92 / 10) | 204 | 0 (0) |
| `analysis/fork/bank_u/q4_gptq_w4_d1/f03` | `bank_u_q4_gptq_w4_d1_f03` | bank_u | q4 | 190 | 95 (83 / 12) | 190 | 0 (0) |
| `analysis/fork/bank_u/q4_kvq_int8/f01` | `bank_u_q4_kvq_int8_f01` | bank_u | q4 | 190 | 134 (100 / 34) | 268 | 0 (0) |
| `analysis/fork/bank_u/q4_kvq_int8/f02` | `bank_u_q4_kvq_int8_f02` | bank_u | q4 | 190 | 130 (88 / 42) | 260 | 0 (0) |
| `analysis/fork/bank_u/q4_kvq_int8/f03` | `bank_u_q4_kvq_int8_f03` | bank_u | q4 | 190 | 129 (89 / 40) | 258 | 0 (0) |
| `analysis/fork/bank_u/q8_awq_w4/f01` | `bank_u_q8_awq_w4_f01` | bank_u | q8 | 190 | 109 (94 / 15) | 218 | 0 (0) |
| `analysis/fork/bank_u/q8_awq_w4/f02` | `bank_u_q8_awq_w4_f02` | bank_u | q8 | 190 | 90 (82 / 8) | 180 | 0 (0) |
| `analysis/fork/bank_u/q8_awq_w4/f03` | `bank_u_q8_awq_w4_f03` | bank_u | q8 | 190 | 90 (74 / 16) | 180 | 0 (0) |
| `analysis/fork/bank_u/q8_gptq_w4_d1/f01` | `bank_u_q8_gptq_w4_d1_f01` | bank_u | q8 | 190 | 134 (119 / 15) | 268 | 0 (0) |
| `analysis/fork/bank_u/q8_gptq_w4_d1/f02` | `bank_u_q8_gptq_w4_d1_f02` | bank_u | q8 | 190 | 107 (94 / 13) | 214 | 0 (0) |
| `analysis/fork/bank_u/q8_gptq_w4_d1/f03` | `bank_u_q8_gptq_w4_d1_f03` | bank_u | q8 | 190 | 108 (95 / 13) | 216 | 0 (0) |
| `analysis/fork/bank_u/q8_kvq_int8/f01` | `bank_u_q8_kvq_int8_f01` | bank_u | q8 | 190 | 152 (126 / 26) | 304 | 0 (0) |
| `analysis/fork/bank_u/q8_kvq_int8/f02` | `bank_u_q8_kvq_int8_f02` | bank_u | q8 | 190 | 143 (96 / 47) | 286 | 0 (0) |
| `analysis/fork/bank_u/q8_kvq_int8/f03` | `bank_u_q8_kvq_int8_f03` | bank_u | q8 | 190 | 149 (109 / 40) | 298 | 0 (0) |
| `analysis/fork/commonstate/q8/ref_d1/f04` | `cs_ref_q8_gptq_w4_d1_f04` | bank_u | q8 | 85 | 44 (41 / 3) | 88 | 0 (0) |
| `analysis/fork/commonstate/q8/ref_d1/f05` | `cs_ref_q8_gptq_w4_d1_f05` | bank_u | q8 | 85 | 47 (44 / 3) | 94 | 0 (0) |
| `analysis/fork/commonstate/q8/ref_d1/f06` | `cs_ref_q8_gptq_w4_d1_f06` | bank_u | q8 | 85 | 46 (39 / 7) | 92 | 0 (0) |
| `analysis/fork/newmethod/gate/m24_gptq_w4_d1/bank` | `nmp_gate_bank_m24_gptq_w4_d1` | bank_u | m24 | 10 | 4 (4 / 0) | 8 | 0 (0) |
| `analysis/fork/newmethod/gate/m24_rtn_w4/bank` | `nmp_gate_bank_m24_rtn_w4` | bank_u | m24 | 10 | 4 (4 / 0) | 8 | 0 (0) |
| `analysis/fork/newmethod/gate/q8_kivi_k16v16_fx/bank` | `nmp_gate_bank_q8_kivi_k16v16_fx` | bank_u | q8 | 10 | 6 (6 / 0) | 12 | 0 (0) |
| `analysis/fork/newmethod/gate/q8_kivi_k2v2/bank` | `nmp_gate_bank_q8_kivi_k2v2` | bank_u | q8 | 10 | 4 (4 / 0) | 8 | 0 (0) |
| `analysis/fork/newmethod/gate/q8_kivi_k2v2_fx/bank` | `nmp_gate_bank_q8_kivi_k2v2_fx` | bank_u | q8 | 10 | 4 (4 / 0) | 8 | 0 (0) |
| `analysis/fork/newmethod/gate/q8_kivi_k4v4/bank` | `nmp_gate_bank_q8_kivi_k4v4` | bank_u | q8 | 10 | 7 (6 / 1) | 14 | 0 (0) |
| `analysis/fork/newmethod/gate/q8_kivi_k4v4_fx/bank` | `nmp_gate_bank_q8_kivi_k4v4_fx` | bank_u | q8 | 10 | 7 (6 / 1) | 14 | 0 (0) |
| `analysis/fork/newmethod/gate/q8_quarot_w16/bank` | `nmp_gate_bank_q8_quarot_w16` | bank_u | q8 | 10 | 6 (6 / 0) | 12 | 0 (0) |
| `analysis/fork/newmethod/gate/q8_quarot_w4/bank` | `nmp_gate_bank_q8_quarot_w4` | bank_u | q8 | 10 | 5 (5 / 0) | 10 | 0 (0) |
| `analysis/fork/newmethod/gate/q8_quarot_w4a4/bank` | `nmp_gate_bank_q8_quarot_w4a4` | bank_u | q8 | 10 | 2 (2 / 0) | 4 | 0 (0) |
| `analysis/fork/newmethod/gate/q8_spinquant_w16/bank` | `nmp_gate_bank_q8_spinquant_w16` | bank_u | q8 | 10 | 7 (6 / 1) | 14 | 0 (0) |
| `analysis/fork/newmethod/gate/q8_spinquant_w4a4/bank` | `nmp_gate_bank_q8_spinquant_w4a4` | bank_u | q8 | 10 | 3 (3 / 0) | 6 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f01` | `nmp_tau2_m24_gptq_w4_d1_f01` | bank_u | m24 | 83 | 34 (31 / 3) | 68 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f02` | `nmp_tau2_m24_gptq_w4_d1_f02` | bank_u | m24 | 84 | 41 (38 / 3) | 82 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f03` | `nmp_tau2_m24_gptq_w4_d1_f03` | bank_u | m24 | 84 | 41 (37 / 4) | 82 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f04` | `nmp_tau2_m24_gptq_w4_d1_f04` | bank_u | m24 | 84 | 32 (28 / 4) | 64 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f05` | `nmp_tau2_m24_gptq_w4_d1_f05` | bank_u | m24 | 84 | 44 (39 / 5) | 88 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_gptq_w4_d1/f06` | `nmp_tau2_m24_gptq_w4_d1_f06` | bank_u | m24 | 84 | 43 (39 / 4) | 86 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_rtn_w4/f01` | `nmp_tau2_m24_rtn_w4_f01` | bank_u | m24 | 83 | 27 (24 / 3) | 54 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_rtn_w4/f02` | `nmp_tau2_m24_rtn_w4_f02` | bank_u | m24 | 84 | 32 (29 / 3) | 64 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_rtn_w4/f03` | `nmp_tau2_m24_rtn_w4_f03` | bank_u | m24 | 84 | 34 (30 / 4) | 68 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_rtn_w4/f04` | `nmp_tau2_m24_rtn_w4_f04` | bank_u | m24 | 84 | 24 (21 / 3) | 48 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_rtn_w4/f05` | `nmp_tau2_m24_rtn_w4_f05` | bank_u | m24 | 84 | 38 (34 / 4) | 76 | 0 (0) |
| `analysis/fork/newmethod/tau2/m24_rtn_w4/f06` | `nmp_tau2_m24_rtn_w4_f06` | bank_u | m24 | 84 | 33 (30 / 3) | 66 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_kivi_k16v16/f01` | `nmp_tau2_q8_kivi_k16v16_f01` | bank_u | q8 | 85 | 71 (57 / 14) | 142 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_kivi_k16v16/f02` | `nmp_tau2_q8_kivi_k16v16_f02` | bank_u | q8 | 85 | 74 (51 / 23) | 148 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_kivi_k16v16/f03` | `nmp_tau2_q8_kivi_k16v16_f03` | bank_u | q8 | 85 | 72 (42 / 30) | 144 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_kivi_k2v2/f01` | `nmp_tau2_q8_kivi_k2v2_f01` | bank_u | q8 | 85 | 34 (31 / 3) | 68 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_kivi_k2v2/f02` | `nmp_tau2_q8_kivi_k2v2_f02` | bank_u | q8 | 85 | 36 (34 / 2) | 72 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_kivi_k2v2/f03` | `nmp_tau2_q8_kivi_k2v2_f03` | bank_u | q8 | 85 | 31 (23 / 8) | 62 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_kivi_k4v4/f01` | `nmp_tau2_q8_kivi_k4v4_f01` | bank_u | q8 | 85 | 62 (52 / 10) | 124 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_kivi_k4v4/f02` | `nmp_tau2_q8_kivi_k4v4_f02` | bank_u | q8 | 85 | 63 (48 / 15) | 126 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_kivi_k4v4/f03` | `nmp_tau2_q8_kivi_k4v4_f03` | bank_u | q8 | 85 | 54 (36 / 18) | 108 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_quarot_w16/f01` | `nmp_tau2_q8_quarot_w16_f01` | bank_u | q8 | 85 | 72 (57 / 15) | 144 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_quarot_w16/f02` | `nmp_tau2_q8_quarot_w16_f02` | bank_u | q8 | 85 | 65 (47 / 18) | 130 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_quarot_w16/f03` | `nmp_tau2_q8_quarot_w16_f03` | bank_u | q8 | 85 | 71 (41 / 30) | 142 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_quarot_w4/f01` | `nmp_tau2_q8_quarot_w4_f01` | bank_u | q8 | 85 | 42 (38 / 4) | 84 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_quarot_w4/f02` | `nmp_tau2_q8_quarot_w4_f02` | bank_u | q8 | 85 | 34 (30 / 4) | 68 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_quarot_w4/f03` | `nmp_tau2_q8_quarot_w4_f03` | bank_u | q8 | 85 | 38 (30 / 8) | 76 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_quarot_w4a4/f01` | `nmp_tau2_q8_quarot_w4a4_f01` | bank_u | q8 | 85 | 27 (27 / 0) | 54 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_quarot_w4a4/f02` | `nmp_tau2_q8_quarot_w4a4_f02` | bank_u | q8 | 85 | 33 (31 / 2) | 66 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_quarot_w4a4/f03` | `nmp_tau2_q8_quarot_w4a4_f03` | bank_u | q8 | 85 | 24 (20 / 4) | 48 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_spinquant_w16/f01` | `nmp_tau2_q8_spinquant_w16_f01` | bank_u | q8 | 85 | 75 (58 / 17) | 150 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_spinquant_w16/f02` | `nmp_tau2_q8_spinquant_w16_f02` | bank_u | q8 | 85 | 69 (50 / 19) | 138 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_spinquant_w16/f03` | `nmp_tau2_q8_spinquant_w16_f03` | bank_u | q8 | 85 | 71 (41 / 30) | 142 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_spinquant_w4a4/f01` | `nmp_tau2_q8_spinquant_w4a4_f01` | bank_u | q8 | 85 | 25 (22 / 3) | 50 | 0 (0) |
| `analysis/fork/newmethod/tau2/q8_spinquant_w4a4/f02` | `nmp_tau2_q8_spinquant_w4a4_f02` | bank_u | q8 | 85 | 29 (26 / 3) | 58 | 0 (0) |
| `analysis/fork/bank_u/q0/q4_awq_w4/f01` | `bank_u_q0_q4_awq_w4_f01` | bank_u_q0 | q4 | 27 | 15 (13 / 2) | 15 | 0 (0) |
| `analysis/fork/bank_u/q0/q4_awq_w4/f02` | `bank_u_q0_q4_awq_w4_f02` | bank_u_q0 | q4 | 23 | 9 (8 / 1) | 9 | 0 (0) |
| `analysis/fork/bank_u/q0/q4_awq_w4/f03` | `bank_u_q0_q4_awq_w4_f03` | bank_u_q0 | q4 | 25 | 10 (8 / 2) | 10 | 0 (0) |
| `analysis/fork/bank_u/q0/q4_kvq_int8/f01` | `bank_u_q0_q4_kvq_int8_f01` | bank_u_q0 | q4 | 27 | 22 (16 / 6) | 22 | 0 (0) |
| `analysis/fork/bank_u/q0/q4_kvq_int8/f02` | `bank_u_q0_q4_kvq_int8_f02` | bank_u_q0 | q4 | 23 | 17 (12 / 5) | 17 | 0 (0) |
| `analysis/fork/bank_u/q0/q4_kvq_int8/f03` | `bank_u_q0_q4_kvq_int8_f03` | bank_u_q0 | q4 | 25 | 15 (10 / 5) | 15 | 0 (0) |
| `analysis/fork/bank_u/q0/q8_awq_w4/f01` | `bank_u_q0_q8_awq_w4_f01` | bank_u_q0 | q8 | 19 | 9 (8 / 1) | 9 | 0 (0) |
| `analysis/fork/bank_u/q0/q8_awq_w4/f02` | `bank_u_q0_q8_awq_w4_f02` | bank_u_q0 | q8 | 31 | 18 (18 / 0) | 18 | 0 (0) |
| `analysis/fork/bank_u/q0/q8_awq_w4/f03` | `bank_u_q0_q8_awq_w4_f03` | bank_u_q0 | q8 | 21 | 11 (10 / 1) | 11 | 0 (0) |
| `analysis/fork/bank_u/q0/q8_kvq_int8/f01` | `bank_u_q0_q8_kvq_int8_f01` | bank_u_q0 | q8 | 19 | 17 (14 / 3) | 17 | 0 (0) |
| `analysis/fork/bank_u/q0/q8_kvq_int8/f02` | `bank_u_q0_q8_kvq_int8_f02` | bank_u_q0 | q8 | 31 | 27 (22 / 5) | 27 | 0 (0) |
| `analysis/fork/bank_u/q0/q8_kvq_int8/f03` | `bank_u_q0_q8_kvq_int8_f03` | bank_u_q0 | q8 | 21 | 14 (9 / 5) | 14 | 0 (0) |

Not covered:
- `analysis/fork/newmethod/tau2/q8_spinquant_w4a4/f03` (task `nmp_tau2_q8_spinquant_w4a4_f03`, running at scan time). It has no bank_rows.jsonl yet, so re-run the scan when it lands.
- `analysis/fork/holdout/`, excluded by instruction and never opened.
- A7 recovery rows (`newmethod/tau2_recovery/*/rr1/recovery_rows.jsonl`) carry no reuse labels; `arm_source` there is `rerun` or an error. `analyze_newmethod.a7_apply` (L273) gives a reused arm XX's new value, so it uses the same pairs audited here.
- `kivi_recovery/failed_arms.json` and `FORENSICS.md` only mention reused arms of rows already in the table.

## 3. Method

**Enumeration.**
- `os.walk(analysis/fork)` with `analysis/fork/holdout` pruned at the top, so it is never entered. Every `bank_rows.jsonl` and `q0_rows.jsonl` was read.
- `arm_source` values over every `*.jsonl` that has the field:
  - bank_rows: run 14,102; orig 5,743; reuse=QQ 3,930; reuse=BB 2,727; reuse=QB 1,203; error 39;
  - q0_rows: run 400; reuse=B.Q0 184;
  - recovery_rows: rerun 1.
  - There are no other reuse labels. Every bank row with `exact_agreement = true` reuses exactly two arms, and `BQ = reuse=QQ` is always one of them.
- Code search for equality-based reuse:
  - **Found, and audited here:**
    - `fork_driver.bank_u` (`exact = canon_msg(a_b) == canon_msg(a_q)` at L729; reuse at L733-750);
    - `fork_driver.bank_u_q0` (L1258: `c.Q0 = reuse=B.Q0` when the native row is exact; a_B/a_Q are joined from the native row via `q0_summary.json spec.native_out`);
    - the analysis-level propagation in `analyze_newmethod.a6_resolve` (L210) and `a7_apply` (L282).
  - **Not equality-based reuse:**
    - `dev` / `branches` modes (dev, sameprec, sameprec_w3, kv, stress, telecom, ext, newmethod dev). Every requested arm runs, and QQ is the original episode, verified by noop samples.
    - `gate_same`: equality is a check (canonical + completion ids in foreign mode), not a reuse.
    - `commonstate`: every arm runs. The implicit identity is a check, and it is what exposed the q4 f01 case.
    - `score_driver`: it reuses scores only on identical generated ids (`same_ids`, L283), so token-exact.
    - `bank_u_arms` (A7, W100ae): it re-runs arms.
    - The bank_u `orig` arms: the recorded message itself is forced, which is identity, not equality. The noop samples passed 906/906 over the 74 bank directories.
    - `analyze_dev` enters units without a primary (semantic) divergence with all four arms equal to the original outcome. That is a design definition on semantic categories, not a canonical-equality reuse of a run arm, so it is not audited here.

**What reaches the next prompt.**
1. tau2 `to_litellm_messages` sends the content and, for each tool call, its id, its name and `json.dumps(arguments)`.
2. The arguments are then parsed back:
   - for HF templates, by `cloq.context_policy.template_view`, as vLLM does;
   - for m24, by mistral_common.
3. They are re-serialised in insertion order with JSON types:
   - by HF `tojson`, which is `json.dumps(..., ensure_ascii=False)` without `sort_keys`;
   - by mistral_common for m24.
4. Whitespace in the generated JSON therefore never reaches the next prompt, while key order and number or type formatting (1 vs 1.0 vs true) do.
5. `canon_msg` compares parsed dicts with Python `==`, which ignores key order and treats 1 == 1.0 == True.
6. Tool-call ids:
   - the Qwen3 templates do not render them;
   - Mistral renders them (`[CALL_ID]`, and in the tool result). m24 uses deterministic ids `d{t}c{k}` (`cloq/agent.py` L139/L195), and a_B/a_Q ids were equal on every m24 reuse row.

**Exact test per reuse row (cheapest conclusive first; all rows also got the tokenizer render).**
1. Recompute `F.canon_msg(a_B) == F.canon_msg(a_Q)`: 4,114/4,114.
2. Rendered view: `content`, plus for each tool call `name` and `json.dumps(arguments, ensure_ascii=False)` in stored order, plus the id for m24. bank_rows store a_B/a_Q with the dict order the agent used.
3. Tokenizer render:
   - The conversation is `[user 'x', action in tau2 litellm form, tool result 'r' per call (user 'y' after a text action)]`.
   - It is rendered with `add_generation_prompt=True` and the model's `chat_template_kwargs` (q8: `enable_thinking=False`):
     - Qwen: `template_view` + `AutoTokenizer(hf_id, revision).apply_chat_template`;
     - m24: `MistralChatRender(src_path).apply_chat_template`.
   - Each turn is delimited by special tokens and h_t and the tool output are common to both actions. So a difference in this segment is a difference in the real next prompt, and equality here is equality there.
   - Steps 2 and 3 agreed on all 4,114 rows.
4. Renderer sensitivity checks:
   - a key-order swap, 1 vs 1.0 and 1 vs true change the render for q4, q8 and m24;
   - a tool-call id change changes the Mistral render only.
5. Full-context confirmation for the flagged row: recorded decision-7 prompt ids (see §1).
6. Cross-check against `score_driver` generated ids (`token_scores/*/*/scores.jsonl.gz`, `newmethod/token_scores/*/*/scores.jsonl.gz`), see the TL;DR.

Reproduction (CPU, about 10 s): `source scripts/a6000/env.sh; export TMPDIR=<scratch>`, then for each reuse row:
```python
from cloq import fork as F; from cloq.context_policy import template_view
lm = lambda m: {'role': 'assistant', 'content': m.get('content'), 'tool_calls': [{'id': tc['id'], 'name': tc['name'], 'type': 'function',
      'function': {'name': tc['name'], 'arguments': json.dumps(tc['arguments'])}} for tc in m['tool_calls']] if m.get('tool_calls') else None}
conv = lambda m: [{'role': 'user', 'content': 'x'}, lm(m)] + ([{'role': 'tool', 'content': 'r', 'tool_call_id': tc['id']} for tc in m['tool_calls']]
      if m.get('tool_calls') else [{'role': 'user', 'content': 'y'}])
ids = lambda m: tok.apply_chat_template(template_view(conv(m)), add_generation_prompt=True, tokenize=True, **kwargs)  # m24: MistralChatRender(src_path)
flag = F.canon_msg(r['a_B']) == F.canon_msg(r['a_Q']) and ids(r['a_B']) != ids(r['a_Q'])
```

## 4. Downstream consumers of the flagged row

- **`analysis/fork/analyze_bank_u.py`**
  - reads: analysis/fork/bank_u/q4_awq_w4/f01/bank_rows.jsonl (native four arms, U2B);
  - use: row enters q4:awq_w4:U2B per-state contrasts (r, d, M, G, A, C, I, H, F), the exact-agreement rate (counted as exact), the class composition (counted as an identical action), and the cross-cell shared-state co-flip count (q4 U2B, f01);
  - outputs: `analysis/fork/out/bank_u_f01_20261001T134456Z.{json,md}`; `analysis/fork/out/bank_u_f01_f02_f03_20261002T003037Z.{json,md}`;
  - paper:
    - paper/latex/sections/appendix.tex L278 (exact agreement 0.43-0.83: counted as exact), L282 (native estimates table, q4 AWQ-W4 U2B), L301 and L317 (class composition: counted as an identical action without outcome change), L330 (shared fragility on the 255 shared q4 U2B states: its AWQ flip status is fixed by the reuse)
    - paper/latex/sections/appendix_moved.tex L50 (Bank U turnover), L51 ('Identical actions never change the outcome': the row is in the identical class and its BQ/QB are reused, not measured), L53 and L68 (differing-row and outcome-changing counts: it is counted as neither)
    - paper/latex/sections/results_r1.tex L27 (Bank U turnover, W4 cells, U1 and U2B)
    - paper/latex/check_numbers.py source list (bank_u_f01_20261001T134456Z.md, R3 Bank U)
    - not via §4 (appendix.tex L322, appendix_moved.tex L54): the content split covers class (ii) text differences only
- **`analysis/fork/analyze_token_mech.py`**
  - reads: analysis/fork/token_scores/q4_awq_w4/f01/scores.jsonl.gz (Y copied from the bank row; G = Y_BQ - Y_QQ at L99);
  - use: unit (q4, awq_w4, U2B, f01 development) with exact = same_ids = false and exact_canon = true: a 'differing' unit whose flip label G = Y_BQ - Y_QQ is fixed by BQ = reuse=QQ; listed in units[143] of both outputs (div_cls tool_arg, 'origin|date');
  - outputs: `analysis/fork/out/token_mech_20261001T185031Z.{json,md}`; `analysis/fork/out/token_mech_20261002T003130Z.{json,md} (f01 sections; the §3 validation is U1 f02/f03 and does not contain it)`;
  - paper:
    - paper/latex/sections/appendix_moved.tex L73 (1140 rows, 58 flips), L75, L77
    - paper/latex/sections/results_r3.tex L13
    - paper/latex/sections/appendix.tex L317 (token_mech flips: 58)
- **`analysis/fork/analyze_ghf.py`**
  - reads: bank_summary.json + bank_rows.jsonl (row counts only);
  - use: coverage matrix counts the row as ok; no outcome used;
  - outputs: `analysis/fork/out/ghf_20261001T211519Z.{json,md} (coverage section)`;
  - paper:
    - paper/latex/sections/appendix.tex L257 (coverage table; counts only)
- **Not consumed by:**
  - bank_u_q0 / Q0 analysis: the state is not in the Q0 subsample (q0 = false; absent from analysis/fork/bank_u/q0/q4_awq_w4/f01/q0_rows.jsonl)
  - simctrl (manifests/fork/simctrl_v1.json): state not among the units
  - oracle_trigger.py: U1 f02/f03 only
  - analyze_commonstate.py: q4 design reads the bank_u/q4_gptq_w4_d1 reference rows (render-identical at this state), never q4_awq_w4
  - analyze_newmethod.py: q8 reference cells and newmethod cells only
  - sameprec_split.py: links gptq_w4_d1 states only
  - noop counts cited at appendix.tex L23: the row is not a noop sample

No effect or contrast was computed here. The flagged row's per-arm Y values are listed in §1 and in the JSON.

## Evidence paths
- `analysis/fork/bank_u/q4_awq_w4/f01/{bank_rows.jsonl, bank_summary.json, branches/7411758182009c20.json}`, `/data/ziyangs/cloq_work/queue/done/bank_u_q4_awq_w4_f01.json`
- `runs/a6k2_q4_bfpair_f01/airline/decisions.jsonl` (task 30, decisions 6-7)
- `analysis/fork/token_scores/q4_awq_w4/f01/scores.jsonl.gz`
- `analysis/fork/commonstate/q4/panel/d2_bf16/f01/{cs_rows.jsonl, branches/7411758182009c20.json}`
- `analysis/fork/commonstate_replay_check/Q4_F01_IDENTITY.md`, `docs/insights/COMMONSTATE_ERRATA.md` E-2/E-3
- Code:
  - `scripts/a6000/fork_driver.py`: bank_u L673, bank_u_q0 L1223;
  - `cloq/fork.py`: canon_msg L68;
  - `cloq/context_policy.py`: template_view;
  - `cloq/mistral_render.py`;
  - `cloq/agent.py`: det_tool_call_id L195;
  - `scripts/a6000/score_driver.py`: same_ids L283.
- Task index: every directory maps to exactly one `queue/done/*.json` whose `fork.out` matches (table in §2).
