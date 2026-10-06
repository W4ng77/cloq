**TL;DR** telecom HOLDOUT full QQ no-op audit (MIRROR self-check: QQ from original branches): 135 of 1202 eligible states pass every no-op check, 0 fail; QQ missing 1067, QQ error 0, excluded before the check 0. preconditions_all_done_and_equal **False**; complete_coverage **False**; all_checked_pass **True**; eval_rule_consistent **True**; env_hash_computed_for_all_checked **True**; state_ids_consistent **True**; classification_matches_loader **True**; input_dirs_eq_ref **True**.

# Holdout full QQ no-op audit (20261006T004420Z)

Script sha256 `dd9cab35d3b81503` (base holdout_noop_audit.py `020ceda094ab3d28`), git `7f6567390f`, protocol sha256 `e775f3eedb96c76a`, tau2 `2174a603f6d014ef94473ffa95957f6ce27100db`; state_id list digest `642e4f0a858e99d3`; 2515 inputs, digest `d7b5b4a95753a53d`.

## Preconditions (Q ckpt_sha256, effective_config_sha equal to the original fork)

- q4_gptq_w4_d1/g01: not done
- q4_gptq_w4_d1/g02: not done
- q4_gptq_w4_d1/g03: not done
- q4_gptq_w4_d1/g04: not done
- q4_gptq_w4_d1/g05: not done
- q4_gptq_w4_d1/g06: not done
- q8_gptq_w4_d1/g01: not done
- q8_gptq_w4_d1/g02: not done
- q8_gptq_w4_d1/g03: not done
- q8_gptq_w4_d1/g04: not done
- q8_gptq_w4_d1/g05: not done
- q8_gptq_w4_d1/g06: not done
- q8_awq_w4/g01: not done
- q8_awq_w4/g02: not done
- q8_awq_w4/g03: not done
- q8_awq_w4/g04: not done
- q8_awq_w4/g05: not done
- q8_awq_w4/g06: not done

## Failing or uncomputable checks (check: value: count)

{}

## Totals by category

- eligible: QQ result missing: 1067
- eligible: checked pass: 135
- no divergence: 20
- search-excluded: 2

Sub-reasons: {"X exclusion: decision/trajectory count mismatch": 2}

## Method

```
Holdout FULL QQ no-op audit (W100av; docs/insights/HOLDOUT_QQFULL_PROTOCOL.md; read-only, counts only).
Reuses holdout_noop_audit.py unchanged (categories, noop_ok + noop_check + budget_check, evaluation-rule booleans, leak guard) with two
substitutions: every divergent state is eligible (noop_frac 1.0), and a state's QQ arm is read from
analysis/fork/holdout_qqfull/<cell>/gNN/branches/<state_id>.json (BB/BQ/QB stay the original files; the original QQ, where sampled, is
ignored). A state without a QQ-full file counts as 'eligible: QQ result missing' (coverage). Preconditions (protocol §3): each done
qqfull_hold_* task's Q server ckpt_sha256 and effective_config_sha equal its fork_hold_* original's.
--mirror reads QQ from the ORIGINAL branches instead (end-to-end self-check: must reproduce holdout_noop_audit's 135 pass / 1067 missing).
usage: python analysis/fork/holdout_qqfull_audit.py --split holdout [--mirror] -> out/holdout_qqfull_audit_*.{json,md}
```
