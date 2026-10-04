# Reuse fix: measured cross arms of the one token-different reuse row (W100ae)

**TL;DR** Both arms that had been reused at q4_awq_w4 f01, airline:30, t = 6 (state_key 7411758182009c20) were measured once. Neither outcome changes: **BQ 0 → 0** (was reuse=QQ) and **QB 0 → 0** (was reuse=BB). No downstream number changes in analyze_bank_u or analyze_token_mech.

- **Task:** `reusefix_ru1_q4_awq_w4_f01`, mode `bank_u_arms` with `reuse_rerun`, concurrency 1, 27 s. Output in `analysis/fork/bank_u_reuse_fix/q4_awq_w4/f01/ru1/`; the originals are untouched.
- **Checks:**
  - the state is identical to the original row (state_id, history_sha, prompt_ids_sha, steps_left);
  - B and Q server identity (canary, ckpt sha, effective config sha) equals the original Bank U task;
  - budget ok;
  - the raw actions differ (key order), as the audit found.
- **Trajectories:**
  - The measured BQ suffix has the same suffix_sha as the original QQ branch (14c04247…).
  - The suffix hash compares canonical messages, so after the first prompt, which differs in key order, the continuation is canonically the same.
  - QB ends user_stop with db_match False (Y = 0), the same as the reused BB value.
- **Scope of the reuse rule after the audit:** 4,113 of 4,114 equality-based reuses are token-identical. The one exception is now measured and agrees.
