> **DRY RUN ON DEV**: telecom dev blocks f01-f06 as a pseudo-holdout; proves the audit runs end to end; says nothing about the holdout.

**TL;DR** DRY RUN ON DEV (telecom dev f01-f06; proves execution only): of 104 eligible states (fixed hash rule, noop_frac [0.1]), 104 pass (0 with an uncomputable check) and 0 fail the no-op checks; unchecked: QQ missing 0, QQ error 0, excluded before the check 0 (of which 0 have a QQ, checked apart). analyze_dev counted 104 no-op records (fail 0) vs reference {'n': 104, 'n_fail': 0}; this audit 104 (0 on non-eligible states). all_eligible_checked **True**; all_checks_pass **True**; eval_rule_consistent **True**; env_hash_computed_for_all_checked **True**; no_qq_on_non_eligible **True**; noop_frac_consistent **True**; state_ids_consistent **True**; classification_matches_loader **True**; audit_records_eq_analyze_dev **True**; excluded_eligible_qq_checks_pass **True**; expected_cell_blocks_present **True**; n135_reconciles **True**; input_dirs_eq_ref **True**; input_files_digest_eq_ref **False**; all_fork_dirs_discovered **True**.

# QQ no-op acceptance audit, dev (20261004T151852Z)

Script `analysis/fork/holdout_noop_audit.py` sha256 `020ceda094ab3d28`, git `2276dc71bd`; snapshot `analysis/insights/iter_3/out/snapshot_auto_20261001T1411Z.json` (= reference's: True); reference `analysis/fork/out/holdout_confirm_DRYRUN_DEV_20261001T144457Z.json`; tau2 HEAD `2174a603f6d014ef94473ffa95957f6ce27100db`; rule fork_driver.py:1538 int(sha256('noop|' + state_id)[:8], 16) / 16**8 < noop_frac (recorded spec); repair log {'present': False, 'n_entries': 0}; dirs with search.json, states/ or branches/ outside the discovered set: 0. 1962 input files read, digest `09824eb3b9a89cef`; load_dir file digest `2083e8231dff9d15` (per-file sha256 in `analysis/fork/out/holdout_noop_audit_DRYRUN_DEV_20261004T151852Z.json`).

## Categories per (cell, block)

| cell, block | 0: no divergence | X: search-excluded | .: divergent, not eligible (not sampled) | M: eligible: QQ result missing | E: eligible: QQ error (noncomputable) | N: eligible: state excluded before the no-op check (noncomputable) | P: eligible: checked pass | F: eligible: checked fail | S: loader-excluded (Q block not admitted / trajectory changed; not eligible or no divergence) | q: QQ on a non-eligible state |
|---|---|---|---|---|---|---|---|---|---|---|
| q8:awq_w4 f01 | 0 | 0 | 72 | 0 | 0 | 0 | 8 | 0 | 0 | 0 |
| q8:awq_w4 f02 | 0 | 0 | 69 | 0 | 0 | 0 | 11 | 0 | 0 | 0 |
| q8:awq_w4 f03 | 0 | 0 | 76 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| q8:awq_w4 f04 | 0 | 0 | 68 | 0 | 0 | 0 | 12 | 0 | 0 | 0 |
| q8:awq_w4 f05 | 0 | 0 | 71 | 0 | 0 | 0 | 9 | 0 | 0 | 0 |
| q8:awq_w4 f06 | 0 | 0 | 74 | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| q8:gptq_w4_d1 f01 | 0 | 0 | 69 | 0 | 0 | 0 | 11 | 0 | 0 | 0 |
| q8:gptq_w4_d1 f02 | 1 | 0 | 71 | 0 | 0 | 0 | 8 | 0 | 0 | 0 |
| q8:gptq_w4_d1 f03 | 0 | 0 | 71 | 0 | 0 | 0 | 9 | 0 | 0 | 0 |
| q8:gptq_w4_d1 f04 | 1 | 0 | 65 | 0 | 0 | 0 | 14 | 0 | 0 | 0 |
| q8:gptq_w4_d1 f05 | 1 | 0 | 74 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| q8:gptq_w4_d1 f06 | 0 | 0 | 73 | 0 | 0 | 0 | 7 | 0 | 0 | 0 |
| total | 3 | 0 | 853 | 0 | 0 | 0 | 104 | 0 | 0 | 0 |

## No-op checks on every QQ record load_dir reaches (value: count)

| check | counts |
|---|---|
| budget_check | {'True': 104} |
| counters | {'True': 104} |
| db_match | {'True': 104} |
| env_hash_final_vs_orig_replay | {'True': 104} |
| env_hash_init | {'True': 104} |
| env_hash_replay_vs_live | {'True': 104} |
| history_prefix | {'True': 104} |
| official_reward | {'True': 104} |
| outcome | {'True': 104} |
| prompts | {'True': 104} |
| reward | {'True': 104} |
| suffix | {'True': 104} |
| termination | {'True': 104} |

## No-op checks on eligible states excluded before the check, QQ present (not in the 135) (value: count)

| check | counts |
|---|---|

## Evaluation rule on analysed divergent states (value: count)

| check | counts |
|---|---|
| n_states | 957 |
| arms_basis_formula_reproduces | {'True': 957} |
| arms_carry_basis_fields | {'True': 957} |
| orig_basis_formula_reproduces | {'True': 957} |
| orig_loop_guard_off | {'True': 957} |
| orig_row_eq_state | {'True': 957} |
| orig_run_eval_all_ignore_basis | {'True': 957} |
| orig_source_trajectory | {'True': 957} |
| orig_trajectory_record_eq_state | {'True': 957} |
| run_tau2_commit_eq_current_clean_head | {'True': 957} |

Other counts: {"state_id != sha([run, domain, task, t*])[:16]": 0, "driver-recorded no-op verdicts": 0, "driver-recorded verdicts = fork_driver.noop_check now": 0}. Sub-reasons: {}. Reconcile: {"n_records_analyze_dev": 104, "n_fail_analyze_dev": 0, "n_records_this_audit": 104, "n_units_analyze_dev": 960, "n_units_this_audit": 960, "n_unit_status_mismatches": 0, "n_excluded_eligible_qq_checked": 0, "n_pass_with_uncomputable_check": 0}.

## Per-task codes

One code per block, blocks in header order: 0 no divergence, X search-excluded, . divergent, not eligible (not sampled), M eligible: QQ result missing, E eligible: QQ error (noncomputable), N eligible: state excluded before the no-op check (noncomputable), P eligible: checked pass, F eligible: checked fail, S loader-excluded (Q block not admitted / trajectory changed; not eligible or no divergence), q QQ on a non-eligible state, - no record; '+' several rows.

| task | q8:awq_w4 (f01 f02 f03 f04 f05 f06) | q8:gptq_w4_d1 (f01 f02 f03 f04 f05 f06) |
|---|---|---|
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_apn_mms_setting/break_app_both_permissions/data_mode_off/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_disabled_off[PERSONA:Hard] | .P.... | P....P |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_apn_mms_setting/break_app_both_permissions/data_mode_off/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_disabled_on[PERSONA:Hard] | ...... | ...P.. |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_apn_mms_setting/break_app_both_permissions/unseat_sim_card/user_abroad_roaming_enabled_off[PERSONA:Hard] | .PP... | P..... |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_apn_mms_setting/break_app_sms_permission/data_mode_off/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_disabled_on[PERSONA:None] | ..P... | ...... |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_apn_mms_setting/break_app_sms_permission/data_mode_off/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_enabled_off[PERSONA:None] | ...P.. | ...... |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_apn_mms_setting/break_app_storage_permission/data_mode_off/data_usage_exceeded/unseat_sim_card[PERSONA:Easy] | ....P. | ...... |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_apn_mms_setting/break_app_storage_permission/data_mode_off/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_disabled_off[PERSONA:Easy] | ...... | ...... |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_apn_mms_setting/break_app_storage_permission/data_mode_off/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_disabled_on[PERSONA:Easy] | ...... | ...P.. |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_apn_mms_setting/break_app_storage_permission/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_disabled_off[PERSONA:Easy] | ...... | ...PPP |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_app_sms_permission/data_mode_off/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_disabled_off[PERSONA:None] | .P.... | .P.PPP |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/break_app_storage_permission/data_mode_off/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_enabled_off[PERSONA:Hard] | ...P.. | ...... |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/bad_wifi_calling/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_disabled_on[PERSONA:Easy] | ...... | ...P.. |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/break_apn_mms_setting/break_app_both_permissions/data_mode_off/data_usage_exceeded/user_abroad_roaming_enabled_off[PERSONA:None] | ...P.. | ...... |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/break_apn_mms_setting/break_app_storage_permission[PERSONA:None] | P...P. | ...... |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/break_apn_mms_setting/data_mode_off/unseat_sim_card/user_abroad_roaming_disabled_off[PERSONA:Easy] | P..... | ...P.. |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/break_apn_mms_setting/data_usage_exceeded[PERSONA:Hard] | ...... | ...... |
| telecom:[mms_issue]airplane_mode_on/bad_network_preference/break_app_both_permissions/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_disabled_on[PERSONA:Hard] | ...P.. | ....P. |
| telecom:[mms_issue]airplane_mode_on/break_app_both_permissions[PERSONA:Hard] | ...... | ..P... |
| telecom:[mms_issue]airplane_mode_on/break_app_both_permissions/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:None] | ...... | ...P.. |
| telecom:[mms_issue]bad_network_preference/bad_wifi_calling/break_apn_mms_setting/break_app_storage_permission/data_mode_off/data_usage_exceeded/unseat_sim_card[PERSONA:Easy] | ...... | ..P... |
| telecom:[mms_issue]bad_network_preference/bad_wifi_calling/break_app_both_permissions/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_disabled_off[PERSONA:None] | ...... | ..P... |
| telecom:[mms_issue]bad_network_preference/bad_wifi_calling/break_app_both_permissions/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:Hard] | .P.... | ...P.. |
| telecom:[mms_issue]bad_network_preference/bad_wifi_calling/break_app_sms_permission/data_mode_off/data_usage_exceeded/unseat_sim_card/user_abroad_roaming_enabled_off[PERSONA:Easy] | .P..P. | ...... |
| telecom:[mms_issue]bad_network_preference/break_app_sms_permission/data_mode_off/data_usage_exceeded/user_abroad_roaming_enabled_off[PERSONA:None] | ...... | ...... |
| telecom:[mms_issue]bad_network_preference/data_mode_off/user_abroad_roaming_disabled_on[PERSONA:None] | ...... | ...... |
| telecom:[mms_issue]bad_wifi_calling/break_apn_mms_setting/break_app_both_permissions/data_mode_off/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:None] | ...PPP | ...... |
| telecom:[mms_issue]bad_wifi_calling/break_apn_mms_setting/break_app_sms_permission/data_usage_exceeded[PERSONA:Hard] | ...... | P..... |
| telecom:[mms_issue]bad_wifi_calling/break_apn_mms_setting/unseat_sim_card/user_abroad_roaming_enabled_off[PERSONA:Easy] | ...... | ...... |
| telecom:[mms_issue]bad_wifi_calling/data_mode_off/data_usage_exceeded[PERSONA:Easy] | .P.... | .P.... |
| telecom:[mms_issue]break_apn_mms_setting/user_abroad_roaming_enabled_off[PERSONA:Hard] | ..P... | ...... |
| telecom:[mms_issue]break_app_both_permissions/data_usage_exceeded[PERSONA:Hard] | ...P.. | ...... |
| telecom:[mms_issue]break_app_both_permissions/unseat_sim_card/user_abroad_roaming_disabled_on[PERSONA:Hard] | ...... | .P.... |
| telecom:[mms_issue]break_app_sms_permission/data_mode_off[PERSONA:None] | ...... | P..... |
| telecom:[mms_issue]break_app_sms_permission/data_usage_exceeded/user_abroad_roaming_disabled_on[PERSONA:None] | ...... | ...P.. |
| telecom:[mms_issue]break_app_storage_permission/data_usage_exceeded[PERSONA:Easy] | ...P.. | ..PP.. |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference[PERSONA:Hard] | ...... | ...... |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/bad_vpn/data_mode_off/data_saver_mode_on/data_usage_exceeded/user_abroad_roaming_disabled_on[PERSONA:None] | ...... | ...... |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/bad_vpn/data_mode_off/data_saver_mode_on/user_abroad_roaming_disabled_off[PERSONA:Hard] | ....P. | ...... |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/bad_vpn/data_mode_off/data_usage_exceeded/user_abroad_roaming_enabled_off[PERSONA:Easy] | ...P.. | .0.P.. |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/bad_vpn/data_saver_mode_on/data_usage_exceeded/user_abroad_roaming_enabled_off[PERSONA:None] | ...... | ...... |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/bad_vpn/data_saver_mode_on/user_abroad_roaming_disabled_on[PERSONA:Easy] | ...... | ...P.. |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/data_mode_off/data_saver_mode_on[PERSONA:Hard] | .....P | P..... |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/data_mode_off/data_saver_mode_on/data_usage_exceeded/user_abroad_roaming_disabled_on[PERSONA:None] | ...P.. | ...... |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/data_saver_mode_on/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:None] | ...... | ..P... |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:Easy] | PP..P. | .....P |
| telecom:[mobile_data_issue]airplane_mode_on/bad_network_preference/user_abroad_roaming_enabled_off[PERSONA:Easy] | .P.... | ....P. |
| telecom:[mobile_data_issue]airplane_mode_on/data_mode_off[PERSONA:None] | .P.P.P | ..P... |
| telecom:[mobile_data_issue]airplane_mode_on/data_mode_off/data_saver_mode_on/data_usage_exceeded/user_abroad_roaming_enabled_off[PERSONA:Hard] | ...... | ...... |
| telecom:[mobile_data_issue]airplane_mode_on/data_saver_mode_on/user_abroad_roaming_disabled_on[PERSONA:None] | ....P. | .PPP.. |
| telecom:[mobile_data_issue]bad_network_preference/bad_vpn/data_mode_off/data_saver_mode_on[PERSONA:None] | .....P | P..... |
| telecom:[mobile_data_issue]bad_network_preference/bad_vpn/data_saver_mode_on/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:Easy] | .P.... | ...... |
| telecom:[mobile_data_issue]bad_network_preference/bad_vpn/user_abroad_roaming_disabled_off[PERSONA:Hard] | ...... | ...... |
| telecom:[mobile_data_issue]bad_network_preference/bad_vpn/user_abroad_roaming_enabled_off[PERSONA:Easy] | P..... | .P.... |
| telecom:[mobile_data_issue]bad_network_preference/data_mode_off/data_saver_mode_on/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:Easy] | P...P. | ...... |
| telecom:[mobile_data_issue]bad_network_preference/data_saver_mode_on/data_usage_exceeded[PERSONA:Hard] | ...... | P..... |
| telecom:[mobile_data_issue]bad_vpn/data_mode_off/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:None] | ...... | ...... |
| telecom:[mobile_data_issue]bad_vpn/data_saver_mode_on/user_abroad_roaming_disabled_on[PERSONA:None] | ...... | .....P |
| telecom:[mobile_data_issue]data_mode_off/data_usage_exceeded/user_abroad_roaming_disabled_off[PERSONA:Hard] | ...... | ....0. |
| telecom:[mobile_data_issue]data_saver_mode_on/user_abroad_roaming_enabled_off[PERSONA:Easy] | ...... | P..... |
| telecom:[mobile_data_issue]data_usage_exceeded/user_abroad_roaming_enabled_off[PERSONA:Easy] | ...... | ...... |
| telecom:[service_issue]airplane_mode_on/break_apn_settings/contract_end_suspension/lock_sim_card_pin[PERSONA:None] | ...... | ...P.. |
| telecom:[service_issue]airplane_mode_on/break_apn_settings/contract_end_suspension/unseat_sim_card[PERSONA:Easy] | ...... | P..0.. |
| telecom:[service_issue]airplane_mode_on/break_apn_settings/lock_sim_card_pin[PERSONA:None] | ...... | ...... |
| telecom:[service_issue]airplane_mode_on/break_apn_settings/lock_sim_card_pin/overdue_bill_suspension[PERSONA:Hard] | ...... | ...... |
| telecom:[service_issue]airplane_mode_on/break_apn_settings/lock_sim_card_pin/overdue_bill_suspension/unseat_sim_card[PERSONA:None] | ...... | ..P... |
| telecom:[service_issue]airplane_mode_on/break_apn_settings/lock_sim_card_pin/unseat_sim_card[PERSONA:None] | ...... | .....P |
| telecom:[service_issue]airplane_mode_on/break_apn_settings/overdue_bill_suspension/unseat_sim_card[PERSONA:None] | ...... | ...... |
| telecom:[service_issue]airplane_mode_on/break_apn_settings/unseat_sim_card[PERSONA:None] | ...... | .P...P |
| telecom:[service_issue]airplane_mode_on/lock_sim_card_pin/overdue_bill_suspension[PERSONA:Easy] | ...... | PP.... |
| telecom:[service_issue]airplane_mode_on/lock_sim_card_pin/unseat_sim_card[PERSONA:Hard] | ..P... | ...... |
| telecom:[service_issue]airplane_mode_on/overdue_bill_suspension/unseat_sim_card[PERSONA:Easy] | P..... | ...... |
| telecom:[service_issue]airplane_mode_on/unseat_sim_card[PERSONA:None] | P..PP. | ...... |
| telecom:[service_issue]break_apn_settings/contract_end_suspension/lock_sim_card_pin[PERSONA:Hard] | ...... | ...... |
| telecom:[service_issue]break_apn_settings/contract_end_suspension/lock_sim_card_pin/unseat_sim_card[PERSONA:Hard] | ...P.. | ..P... |
| telecom:[service_issue]break_apn_settings/lock_sim_card_pin/overdue_bill_suspension[PERSONA:Easy] | P..... | ...... |
| telecom:[service_issue]break_apn_settings/lock_sim_card_pin/overdue_bill_suspension/unseat_sim_card[PERSONA:Easy] | .....P | ....P. |
| telecom:[service_issue]break_apn_settings/overdue_bill_suspension/unseat_sim_card[PERSONA:Hard] | ...... | P..... |
| telecom:[service_issue]contract_end_suspension/lock_sim_card_pin[PERSONA:Hard] | ...... | ...... |
| telecom:[service_issue]lock_sim_card_pin/overdue_bill_suspension[PERSONA:Easy] | .P.... | ...... |
| telecom:[service_issue]overdue_bill_suspension/unseat_sim_card[PERSONA:Easy] | .....P | .P.... |

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
