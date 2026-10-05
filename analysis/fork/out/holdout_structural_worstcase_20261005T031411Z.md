> **POST HOC SENSITIVITY (GPT-authorised, not a protocol repair)**

**TL;DR** Re-including the two structurally excluded tasks with any bounding unit G moves G_all between -6.68 [-10.35, -3.01] and -2.27 [-5.96, +1.43] pp (crossed 90%); readings: ['inconclusive']. Frozen: -4.57 [-7.17, -1.96], inconclusive.

# Holdout structural-exclusion sensitivity (2026-10-05T03:14:11Z)

JSON `analysis/fork/out/holdout_structural_worstcase_20261005T031411Z.json`. Inputs: script `{"path": "analysis/fork/holdout_structural_worstcase.py", "sha256": "1d51744a8c96ee76c8564c72f34f83f016891172bd6bcd92dbd37837eec3f1a4"}`; analyze_holdout_confirm_sha256 `2af1b6890defcf03a07040528d16e1ce2597d694e3a7cbacffc533fb0bb141db`; holdout_r2_posthoc_sha256 `009306b59e4a838a83922648ac5c396864ed671e87d7f0c837c3b2fb0de824ee`; git_head `414c559b25b6fa46bca2865fab5e646035ddb583`; prereg_sha256 `902892dd63e99e16ab9beefee9d39319d835eacdada3d4d92c4a1022d13fd622`; splits_sha256 `f7e805b88a5a4bc06b18840f444354ca7f83b24af08e088556e8ea867a127043`; cutpoints_sha256 `ab46abe91960f6c2cb1b228ffa7ada8128d4018f21be80ef017d1a95429d32de`; snapshot `{"path": "analysis/insights/iter_3/out/snapshot_holdout_20261002T0123Z.json", "sha256": "f5023c633f029395a8bad81429bb4f9d637bdf43a47e762eadb9c89fb7f70f84"}`; confirm_output `{"path": "analysis/fork/out/holdout_confirm_20261002T012353Z.json", "sha256": "f7451b9ee3d1ac58e8e36b3db7c4235c4875913affc53671875248046efe4d6f"}`; units_digest_sha256 `0fbcc42ac775b00c3740c77d7b80fe794b60e6061c4cae83316ee24fd90eaf9d`; input_files_digest_sha256 `548183437db10ed83258f689ef4d9928e7711e852a5d637cc792d5463cde04b4`

Cell weights {"q4:gptq_w4_d1": 0.5, "q8:gptq_w4_d1": 0.25, "q8:awq_w4": 0.25}; blocks ['h01', 'h02', 'h03', 'h04', 'h05', 'h06', 'h07', 'h08', 'h09', 'h10', 'h11', 'h12'].

## Excluded tasks

- q4:gptq_w4_d1: telecom:[mms_issue]bad_network_preference|break_app_sms_permission|user_abroad_roaming_disabled_on[PERSONA:Hard]; observed (structurally dropped) units in 11 blocks, 11 divergent, G {'h01': 0.0, 'h02': 0.0, 'h03': 0.0, 'h04': 0.0, 'h05': 0.0, 'h06': 0.0, 'h07': 0.0, 'h08': 0.0, 'h09': 0.0, 'h10': 0.0, 'h11': 0.0}; other reasons ['search: decision/trajectory count mismatch 61 vs 0']
- q8:awq_w4: telecom:[mobile_data_issue]airplane_mode_on|bad_network_preference|data_mode_off|user_abroad_roaming_disabled_on[PERSONA:Hard]; observed (structurally dropped) units in 11 blocks, 11 divergent, G {'h01': -1.0, 'h02': 0.0, 'h03': 0.0, 'h04': 0.0, 'h05': 0.0, 'h06': 0.0, 'h07': 0.0, 'h08': 0.0, 'h09': 0.0, 'h10': 0.0, 'h11': 0.0}; other reasons ['search: decision/trajectory count mismatch 94 vs 0']

## G_all (pp), crossed task x block 90% interval (decisional), block t alongside

| q4:gptq_w4_d1 | q8:awq_w4 | G_all | crossed 90% | block-t 90% | reading | +-5 pp small |
|---|---|---|---|---|---|---|
| excluded | excluded | -4.57 | [-7.17, -1.96] | [-6.08, -3.05] | inconclusive | False |
| excluded | -1 | -5.25 | [-8.28, -2.23] | [-6.77, -3.73] | inconclusive | False |
| excluded | 0 | -4.52 | [-7.11, -1.93] | [-6.04, -3.00] | inconclusive | False |
| excluded | +1 | -3.78 | [-6.46, -1.11] | [-5.30, -2.26] | inconclusive | False |
| excluded | obs/-1 | -4.64 | [-7.27, -2.01] | [-6.15, -3.13] | inconclusive | False |
| excluded | obs/+1 | -4.52 | [-7.11, -1.93] | [-5.94, -3.10] | inconclusive | False |
| -1 | excluded | -5.99 | [-9.35, -2.63] | [-7.47, -4.51] | inconclusive | False |
| -1 | -1 | -6.68 | [-10.35, -3.01] | [-8.16, -5.19] | inconclusive | False |
| -1 | 0 | -5.94 | [-9.29, -2.60] | [-7.43, -4.46] | inconclusive | False |
| -1 | +1 | -5.21 | [-8.65, -1.76] | [-6.69, -3.72] | inconclusive | False |
| -1 | obs/-1 | -6.07 | [-9.44, -2.69] | [-7.54, -4.59] | inconclusive | False |
| -1 | obs/+1 | -5.94 | [-9.29, -2.60] | [-7.33, -4.56] | inconclusive | False |
| 0 | excluded | -4.52 | [-7.08, -1.97] | [-6.00, -3.04] | inconclusive | False |
| 0 | -1 | -5.21 | [-8.19, -2.23] | [-6.69, -3.72] | inconclusive | False |
| 0 | 0 | -4.47 | [-7.01, -1.94] | [-5.96, -2.99] | inconclusive | False |
| 0 | +1 | -3.74 | [-6.37, -1.11] | [-5.22, -2.25] | inconclusive | False |
| 0 | obs/-1 | -4.60 | [-7.17, -2.02] | [-6.07, -3.12] | inconclusive | False |
| 0 | obs/+1 | -4.47 | [-7.01, -1.94] | [-5.86, -3.09] | inconclusive | False |
| +1 | excluded | -3.05 | [-6.72, +0.62] | [-4.53, -1.57] | inconclusive | False |
| +1 | -1 | -3.74 | [-7.73, +0.26] | [-5.22, -2.25] | inconclusive | False |
| +1 | 0 | -3.00 | [-6.66, +0.65] | [-4.49, -1.52] | inconclusive | False |
| +1 | +1 | -2.27 | [-5.96, +1.43] | [-3.75, -0.78] | inconclusive | False |
| +1 | obs/-1 | -3.12 | [-6.81, +0.56] | [-4.60, -1.65] | inconclusive | False |
| +1 | obs/+1 | -3.00 | [-6.66, +0.65] | [-4.39, -1.62] | inconclusive | False |
| obs/-1 | excluded | -4.64 | [-7.19, -2.10] | [-6.22, -3.06] | inconclusive | False |
| obs/-1 | -1 | -5.33 | [-8.30, -2.37] | [-6.92, -3.75] | inconclusive | False |
| obs/-1 | 0 | -4.60 | [-7.12, -2.07] | [-6.18, -3.01] | inconclusive | False |
| obs/-1 | +1 | -3.86 | [-6.49, -1.24] | [-5.45, -2.27] | inconclusive | False |
| obs/-1 | obs/-1 | -4.72 | [-7.28, -2.15] | [-6.31, -3.13] | inconclusive | False |
| obs/-1 | obs/+1 | -4.60 | [-7.12, -2.07] | [-6.07, -3.12] | inconclusive | False |
| obs/+1 | excluded | -4.40 | [-6.98, -1.82] | [-5.81, -2.99] | inconclusive | False |
| obs/+1 | -1 | -5.09 | [-8.09, -2.08] | [-6.50, -3.67] | inconclusive | False |
| obs/+1 | 0 | -4.35 | [-6.91, -1.79] | [-5.76, -2.94] | inconclusive | False |
| obs/+1 | +1 | -3.62 | [-6.27, -0.96] | [-5.03, -2.20] | inconclusive | False |
| obs/+1 | obs/-1 | -4.47 | [-7.07, -1.87] | [-5.86, -3.09] | inconclusive | False |
| obs/+1 | obs/+1 | -4.35 | [-6.91, -1.79] | [-5.68, -3.02] | inconclusive | False |
