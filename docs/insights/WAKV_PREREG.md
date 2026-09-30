# WAKV_PREREG — q8 replication of the q4 W×K interaction (pre-declared before any q8 result)

**TL;DR** The q8 target contrast is fixed as I_WK|A16, two-sided, t over block means as the primary interval. It is
written and committed before any q8 W×A×KV run exists (W66). Anything else from q8, or a different largest q4
interaction once the matched q4 kv16r cells finish, is exploratory.

Written 2026-09-30 by the activation-hook line (W65/W66). No `a6k2_q8_quarot_*` run existed when this note was committed.
The q4 kv16r cells were still queued; the q4 figure that motivated the target (I_WK|A16 = −14.9 pp) comes from the
confounded kv16 reference (W65).

## Target
- **Model:** q8 (Qwen3-8B, revision b968826d), QuaRot-rotated with the online Hadamards (validated: METHOD_FIDELITY §6,
  `analysis/ahook/validate_quarot_q8.json`).
- **Cells** (all A16, `make_tasks.py --only wakv`):

| cell | W | KV |
|---|---|---|
| `quarot_w16a16kv16r` | 16 (rotated BF16) | 16, Q/K rotation on, no KV quantization |
| `quarot_w4a16kv16r` | 4 (QuaRot GPTQ) | 16r |
| `quarot_w16a16kv4` | 16 | 4 (QuaRot KV4: asymmetric, group 128, clip 0.95, Q/K rotation) |
| `quarot_w4a16kv4` | 4 | 4 |

- **Blocks:** f01–f06 (nonces `manifests/fork/dev_blocks_v1.json` new_blocks), 1 run per cell per block. Paired with
  `a6k2_q8_bfpair_f01..f06`, which are admitted with matching nonces in snapshot 20260930T2311Z.
- **Unit:** task × block over retail (58) and airline (27). Y is DB success (analyze_dev.success). Infrastructure
  episodes are excluded.
- **Contrast:** I_WK|A16 = Y_W4K4 − Y_W4K16r − Y_W16K4 + Y_W16K16r, per unit, averaged within each block. It uses only
  units where all four cells exist.
- **Inference:** two-sided 95%.
  - **Primary:** t over the block means, k = 6 blocks, df 5 (analyze_dev.Boot, W63; t because k < 10).
  - **Secondary:** crossed task × block bootstrap (new-task generalisation). The block bootstrap is reported but not used.
- **Direction:** two-sided. q4 suggested a negative interaction. "Replicates" means the primary interval excludes 0 with
  the same sign as the matched q4 estimate. The q8 estimate and interval are reported whatever the outcome.
- **Analysis:** `python analysis/ahook/analyze_wakv.py --snapshot <snapshot> --models q8`, contrast `I_WK | A16` in the
  primary (kv16r) factorial. The script sha at the commit of this note is recorded in W66.

## Fixed now, not changed later
- Target, cells, blocks, estimator and interval rule above.
- If the matched q4 kv16r results show a different largest interaction, it is reported as exploratory on q8. The q8
  target stays I_WK|A16.
- Scope: effects among these QuaRot-rotated 4-bit axes. Not a claim that harm needs combinations (RTN-W3 alone is
  heavily damaging).
