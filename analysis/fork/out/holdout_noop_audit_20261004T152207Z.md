**TL;DR** telecom HOLDOUT QQ no-op acceptance audit: of 135 eligible states (fixed hash rule, noop_frac [0.1]), 135 pass (0 with an uncomputable check) and 0 fail the no-op checks; unchecked: QQ missing 0, QQ error 0, excluded before the check 0 (of which 0 have a QQ, checked apart). analyze_dev counted 135 no-op records (fail 0) vs reference {'n': 135, 'n_fail': 0}; this audit 135 (0 on non-eligible states). all_eligible_checked **True**; all_checks_pass **True**; eval_rule_consistent **True**; env_hash_computed_for_all_checked **True**; no_qq_on_non_eligible **True**; noop_frac_consistent **True**; state_ids_consistent **True**; classification_matches_loader **True**; audit_records_eq_analyze_dev **True**; excluded_eligible_qq_checks_pass **True**; expected_cell_blocks_present **True**; n135_reconciles **True**; input_dirs_eq_ref **True**; input_files_digest_eq_ref **True**; all_fork_dirs_discovered **True**.

# QQ no-op acceptance audit, holdout (20261004T152207Z)

Script `analysis/fork/holdout_noop_audit.py` sha256 `020ceda094ab3d28`, git `d2b170a758`; snapshot `analysis/insights/iter_3/out/snapshot_holdout_20261002T0123Z.json` (= reference's: True); reference `analysis/fork/out/holdout_confirm_20261002T012353Z.json`; tau2 HEAD `2174a603f6d014ef94473ffa95957f6ce27100db`; rule fork_driver.py:1538 int(sha256('noop|' + state_id)[:8], 16) / 16**8 < noop_frac (recorded spec); repair log {'present': False, 'n_entries': 0}; dirs with search.json, states/ or branches/ outside the discovered set: 0. 2516 input files read, digest `704121b838762f9c`; load_dir file digest `548183437db10ed8` (per-file sha256 in `analysis/fork/out/holdout_noop_audit_20261004T152207Z.json`).

## Categories per (cell, block)

| cell, block | 0: no divergence | X: search-excluded | .: divergent, not eligible (not sampled) | M: eligible: QQ result missing | E: eligible: QQ error (noncomputable) | N: eligible: state excluded before the no-op check (noncomputable) | P: eligible: checked pass | F: eligible: checked fail | S: loader-excluded (Q block not admitted / trajectory changed; not eligible or no divergence) | q: QQ on a non-eligible state |
|---|---|---|---|---|---|---|---|---|---|---|
| q4:gptq_w4_d1 h01 | 0 | 0 | 30 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h02 | 1 | 0 | 28 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h03 | 1 | 0 | 32 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h04 | 2 | 0 | 29 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h05 | 1 | 0 | 28 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h06 | 0 | 0 | 29 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h07 | 3 | 0 | 25 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h08 | 2 | 0 | 28 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h09 | 1 | 0 | 28 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h10 | 0 | 0 | 31 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h11 | 0 | 0 | 32 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| q4:gptq_w4_d1 h12 | 0 | 1 | 31 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| q8:awq_w4 h01 | 0 | 0 | 32 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| q8:awq_w4 h02 | 0 | 0 | 32 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| q8:awq_w4 h03 | 0 | 0 | 31 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| q8:awq_w4 h04 | 0 | 0 | 31 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| q8:awq_w4 h05 | 0 | 0 | 30 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| q8:awq_w4 h06 | 0 | 0 | 31 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| q8:awq_w4 h07 | 0 | 0 | 28 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| q8:awq_w4 h08 | 0 | 0 | 30 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| q8:awq_w4 h09 | 0 | 0 | 27 | 0 | 0 | 0 | 7 | 0 | 0 | 0 |
| q8:awq_w4 h10 | 0 | 0 | 28 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| q8:awq_w4 h11 | 0 | 0 | 30 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| q8:awq_w4 h12 | 0 | 1 | 30 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h01 | 0 | 0 | 29 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h02 | 0 | 0 | 30 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h03 | 0 | 0 | 29 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h04 | 0 | 0 | 31 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h05 | 0 | 0 | 32 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h06 | 4 | 0 | 28 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h07 | 0 | 0 | 32 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h08 | 0 | 0 | 31 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h09 | 2 | 0 | 29 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h10 | 2 | 0 | 27 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h11 | 0 | 0 | 31 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| q8:gptq_w4_d1 h12 | 1 | 0 | 27 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| total | 20 | 2 | 1067 | 0 | 0 | 0 | 135 | 0 | 0 | 0 |

## No-op checks on every QQ record load_dir reaches (value: count)

| check | counts |
|---|---|
| budget_check | {'True': 135} |
| counters | {'True': 135} |
| db_match | {'True': 135} |
| env_hash_final_vs_orig_replay | {'True': 135} |
| env_hash_init | {'True': 135} |
| env_hash_replay_vs_live | {'True': 135} |
| history_prefix | {'True': 135} |
| official_reward | {'True': 135} |
| outcome | {'True': 135} |
| prompts | {'True': 135} |
| reward | {'True': 135} |
| suffix | {'True': 135} |
| termination | {'True': 135} |

## No-op checks on eligible states excluded before the check, QQ present (not in the 135) (value: count)

| check | counts |
|---|---|

## Evaluation rule on analysed divergent states (value: count)

| check | counts |
|---|---|
| n_states | 1202 |
| arms_basis_formula_reproduces | {'True': 1202} |
| arms_carry_basis_fields | {'True': 1202} |
| orig_basis_formula_reproduces | {'True': 1202} |
| orig_loop_guard_off | {'True': 1202} |
| orig_row_eq_state | {'True': 1202} |
| orig_run_eval_all_ignore_basis | {'True': 1202} |
| orig_source_trajectory | {'True': 1202} |
| orig_trajectory_record_eq_state | {'True': 1202} |
| run_tau2_commit_eq_current_clean_head | {'True': 1202} |

Other counts: {"state_id != sha([run, domain, task, t*])[:16]": 0, "driver-recorded no-op verdicts": 0, "driver-recorded verdicts = fork_driver.noop_check now": 0}. Sub-reasons: {"X exclusion: decision/trajectory count mismatch": 2}. Reconcile: {"n_records_analyze_dev": 135, "n_fail_analyze_dev": 0, "n_records_this_audit": 135, "n_units_analyze_dev": 1224, "n_units_this_audit": 1224, "n_unit_status_mismatches": 0, "n_excluded_eligible_qq_checked": 0, "n_pass_with_uncomputable_check": 0}.

## Per-task codes

One code per block, blocks in header order: 0 no divergence, X search-excluded, . divergent, not eligible (not sampled), M eligible: QQ result missing, E eligible: QQ error (noncomputable), N eligible: state excluded before the no-op check (noncomputable), P eligible: checked pass, F eligible: checked fail, S loader-excluded (Q block not admitted / trajectory changed; not eligible or no divergence), q QQ on a non-eligible state, - no record; '+' several rows.

| task | q4:gptq_w4_d1 (h01 h02 h03 h04 h05 h06 h07 h08 h09 h10 h11 h12) | q8:awq_w4 (h01 h02 h03 h04 h05 h06 h07 h08 h09 h10 h11 h12) | q8:gptq_w4_d1 (h01 h02 h03 h04 h05 h06 h07 h08 h09 h10 h11 h12) |
|---|---|---|---|
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_app_storage_permission/unseat_sim_card[PERSONA:Hard] | .P.........P | .........P.. | ..P.......PP |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/break_app_storage_permission/data_mode_off/user_abroad_roaming_enabled_off[PERSONA:Easy] | .........P.. | ............ | .........PP. |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/data_usage_exceeded[PERSONA:None] | ............ | ............ | ..P...P..... |
| telecom:[mms_issue]airplane_mode_on/bad_wifi_calling/break_app_both_permissions/data_mode_off/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_enabled_off[PERSONA:None] | P........... | .PP......... | ...........P |
| telecom:[mms_issue]airplane_mode_on/bad_wifi_calling/user_abroad_roaming_enabled_off[PERSONA:Easy] | .....P...... | ........P.P. | ............ |
| telecom:[mms_issue]bad_network_preference/bad_wifi_calling/break_app_sms_permission/data_mode_off/unseat_sim_card/user_abroad_roaming_enabled_off[PERSONA:Hard] | ............ | ............ | .PP......... |
| telecom:[mms_issue]bad_network_preference/break_app_both_permissions[PERSONA:Easy] | .......P.... | ......P.P... | ....P....P.. |
| telecom:[mms_issue]bad_network_preference/break_app_sms_permission/user_abroad_roaming_disabled_on[PERSONA:Hard] | ..........PX | ........P... | .P...P...P.. |
| telecom:[mms_issue]bad_network_preference/user_abroad_roaming_disabled_off[PERSONA:None] | ......P..... | .......PP.P. | ...........P |
| telecom:[mms_issue]bad_network_preference/user_abroad_roaming_disabled_on[PERSONA:None] | ..0..PP..... | ...........P | ............ |
| telecom:[mms_issue]bad_wifi_calling/break_apn_mms_setting/data_mode_off/data_usage_exceeded/unseat_sim_card[PERSONA:None] | ....PP...... | ............ | P.......PP.. |
| telecom:[mms_issue]break_apn_mms_setting/data_mode_off/data_usage_exceeded/user_abroad_roaming_disabled_on[PERSONA:Hard] | P..0...0P... | ..........P. | P........... |
| telecom:[mms_issue]break_apn_mms_setting/data_mode_off/user_abroad_roaming_disabled_on[PERSONA:Hard] | ...0...0.... | ..P......... | ............ |
| telecom:[mms_issue]break_app_storage_permission/unseat_sim_card/user_abroad_roaming_disabled_on[PERSONA:Easy] | ......P..... | ............ | ............ |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/bad_vpn/data_mode_off/data_saver_mode_on/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:Hard] | ............ | .......PP.P. | ....P..P.... |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/bad_vpn/data_mode_off/data_saver_mode_on/data_usage_exceeded/user_abroad_roaming_enabled_off[PERSONA:Easy] | P........... | ...P........ | ...P.0..0..P |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/data_mode_off/data_usage_exceeded/user_abroad_roaming_disabled_on[PERSONA:None] | .0.......... | ......PP.... | ...P........ |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/data_mode_off/user_abroad_roaming_disabled_on[PERSONA:Hard] | ...PP....... | ....PP...P.X | .P.......... |
| telecom:[mobile_data_issue]airplane_mode_on/user_abroad_roaming_enabled_off[PERSONA:None] | ...P..0..... | ....P...P... | ............ |
| telecom:[mobile_data_issue]bad_network_preference/bad_vpn/data_mode_off/data_saver_mode_on/data_usage_exceeded/user_abroad_roaming_enabled_off[PERSONA:Easy] | .P..PPPP.... | .P.......... | P..........P |
| telecom:[mobile_data_issue]bad_network_preference/bad_vpn/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:Easy] | ......PP.... | .....P..P... | ........PP.. |
| telecom:[mobile_data_issue]bad_network_preference/bad_vpn/user_abroad_roaming_disabled_on[PERSONA:None] | ............ | P.P......P.. | ..P......... |
| telecom:[mobile_data_issue]bad_network_preference/user_abroad_roaming_enabled_off[PERSONA:Hard] | ........PP.. | ......P..... | ...P........ |
| telecom:[mobile_data_issue]data_mode_off/data_usage_exceeded[PERSONA:None] | ............ | ............ | P........... |
| telecom:[mobile_data_issue]data_saver_mode_on/data_usage_exceeded[PERSONA:Easy] | ........P... | ...P..P....P | ........P.P. |
| telecom:[service_issue]airplane_mode_on/break_apn_settings[PERSONA:Hard] | .P....PP.... | ............ | .....0...... |
| telecom:[service_issue]airplane_mode_on/break_apn_settings/contract_end_suspension/lock_sim_card_pin/unseat_sim_card[PERSONA:Easy] | ........0... | ....P.PP.P.P | ..P....P...0 |
| telecom:[service_issue]airplane_mode_on/break_apn_settings/overdue_bill_suspension[PERSONA:None] | ..P......... | ............ | .........0.P |
| telecom:[service_issue]airplane_mode_on/contract_end_suspension/lock_sim_card_pin/unseat_sim_card[PERSONA:Hard] | ....PP...... | ....P....... | .....0..0... |
| telecom:[service_issue]airplane_mode_on/lock_sim_card_pin[PERSONA:Easy] | .P..0...PP.. | P........... | ......P..... |
| telecom:[service_issue]airplane_mode_on/lock_sim_card_pin/overdue_bill_suspension/unseat_sim_card[PERSONA:Easy] | .P..P......P | .........P.. | ............ |
| telecom:[service_issue]airplane_mode_on/overdue_bill_suspension[PERSONA:None] | ......0..... | ...P.P...... | .........0.. |
| telecom:[service_issue]break_apn_settings/lock_sim_card_pin[PERSONA:None] | P..P..0...P. | .........P.. | .P...P...... |
| telecom:[service_issue]contract_end_suspension/unseat_sim_card[PERSONA:Hard] | ........P... | ......P..... | P....0.P.... |

## Method

```
Holdout QQ no-op acceptance audit (GPT review 2026-10-04; read-only): does the no-op sample analyze_holdout_confirm counted (provenance.noop_sample; holdout n 135, n_fail 0) cover every state the driver's
fixed rule made eligible (incl. noncomputable ones), and are all checks consistent? Rule = scripts/a6000/fork_driver.py:1538 (QQ queued at L1552/L1558): sampled iff int(sha256('noop|' + state_id)[:8], 16) / 16**8 <
noop_frac as recorded (branches*.json spec, else search.json spec of mode dev, else driver default 0.1). Each search row (task x cell x block; a split task, or an expected cell x block of the reference, without a row:
'no search row'; state file without a row: orphan) gets one of CATS in analyze_dev.load_dir's order (L270-338): Q block not admitted / trajectory changed = S unless the state is eligible (then N); search exclusions map
to a closed vocabulary (driver exclusion prefix or exception class). Per counted QQ: analyze_dev.noop_ok (L242) + fork_driver.noop_check (L272; final env hash vs orig_final_hash L264, a strict tau2 replay of the
original episode) + budget_check (L296); the same checks run, reported apart from the 135, on eligible states excluded before the no-op check whose QQ exists. Per analysed divergent state: Y_QQ (original) and the
BB/BQ/QB/QQ-rerun official_reward come from cloq.run_arm.basis_reward (source 'trajectory'; row = state = trajectory record; the basis formula over stored reward_info reproduces every side; run config all_ignore_basis,
loop guard off; run tau2 commit = current clean HEAD; the fork's own is not stored). Input identity: discovered dirs and load_dir's file digest equal the reference's. Outputs only counts, categories, booleans, input
sha256, git head, script sha256 (leak guard; no outcome, no outcome-derived count). --split holdout: split_guard first. usage: python analysis/fork/holdout_noop_audit.py (--split holdout | --dry-run-dev |
--selftest) [--snapshot S] [--ref R] -> out/holdout_noop_audit_*.{json,md}
```
