# Evidence freeze 2026-10-04 21:00 PDT (2026-10-05 00:00 Toronto)

**TL;DR** Snapshot taken 2026-10-04 21:00:17 PDT. No GPU result finished after this time enters the paper (TODO_v2; NEWMETHOD_PANEL_PROTOCOL §5.4; GPT 10-04: no extension). Tasks still running are reported as incomplete.

## Running at the freeze (incomplete; excluded from the paper)
- `a6k2_q4_gauss3_s2_redo`
- `a6k2_q4_kvq_int3`
- `a6k2_q4_kvq_int4`
- `pert_q8_rtn_w3_resid_a2_q345`

## Finished in the last 24 h before the freeze (done/, by mtime)
- `a6k2_q14_gauss3_s2_rro` 2026-10-03 21:52
- `a7_rr1_q8_kivi_k4v4_f01` 2026-10-03 22:05
- `a6k2_q32_gauss3_s2_rro` 2026-10-03 23:32
- `a6k2_q32_gauss3_s1_rro` 2026-10-04 04:13
- `fork_repair_q4_rtn_w3` 2026-10-04 06:45
- `a6k2_q14_kvq_int3_rro` 2026-10-04 07:33
- `a6k2_q4_gauss2_s1_redo_rro` 2026-10-04 09:44
- `pivot_q8_rtn_w3_early__middle` 2026-10-04 12:22
- `pivot_q8_rtn_w3_rand_attn_s1__rand_mlp_s1` 2026-10-04 12:22
- `a6k2_q8_kvq_int4_rro` 2026-10-04 14:46
- `a6k2_q8_gauss3_s1` 2026-10-04 15:03

Total done: 1351; git HEAD at freeze: 0119322.

## Amendment 2026-10-04 21:05 PDT
After the snapshot script was written, GPT (20:45 PDT) opened one separately registered exploratory window: the takeover-duration panel (docs/insights/TAKEOVER_WINDOW_PROTOCOL.md), with a deadline of 2026-10-05 21:00 PDT. This snapshot still freezes everything else. The SAMEPREC, COMMONSTATE, NEWMETHOD and holdout readings and the four tasks listed above as incomplete are unchanged.
