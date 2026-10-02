**TL;DR** Pre-registered same-precision control for the 2×2 fork (reviewer's top weakness: no same-precision
perturbation baseline). The BF16 role B is replaced by Q′ = the same model's GPTQ-W4 checkpoint from a different
calibration draw (d2, calibration c2). Q stays the fork checkpoint (GPTQ-W4 d1, c1). Everything else is the Bank P dev
fork pipeline, unchanged. Cells q4 and q8; blocks f01, f02, … f17 in that order; the analysis set is the longest
complete prefix (minimum f01–f06). Primary comparison: the paired difference in turnover M (precision 2×2 minus
same-precision 2×2) on the same task×block units. The interpretation rule in §6 is frozen. This file was written and
committed before any same-precision fork outcome (gate or formal) existed.

# Same-precision 2×2 fork ("Q vs Q′") — protocol sameprec-v1

Written 2026-10-01 23:40 PDT. Work item W99k (docs/RESEARCH_LOG.md). The sha256 of this file is recorded in
`manifests/fork/sameprec_v1.json` and in the W99k log entry. `analysis/fork/analyze_sameprec.py` refuses to run unless
the file's sha256 equals that value.

## 1. Question

In a deterministic greedy closed loop, any plausible change of action or controller can flip the outcome. The precision
2×2 (B = BF16, Q = GPTQ-W4/AWQ-W4) shows turnover M = 15.5–20.9% of task×block units (W4 cells, W63/W78 dev_all) and a
controller-dependent action effect (Δ_Q ≠ Δ_B) on 26.9% of divergent states (W4 pool, W93 ghf). This study asks how much
of that is precision-specific and how much is generic trajectory sensitivity. To test this, the BF16 partner is replaced by
a partner of the same precision and method that differs only in its calibration draw.

## 2. Design

- **Pipeline.** Exactly the Bank P dev fork: `scripts/a6000/fork_driver.py` mode `dev` (divergence search over every
  task of each block, all states frozen before any branch runs, then three branches on every state plus the QQ no-op on
  the 10% hash sample), FORK_PROTOCOL fork-v1 §§1–6, worker kind `fork`. Same tau2 config, simulator, context policy,
  greedy args, budget restoration, scoring and nonce handling. No code path of the driver is changed.
- **Role swap.** Task JSON `b_ckpt` = `{"kind": "gptq", "wbits": 4, "calib": "manifests/a6k2/<m>/calib_fp_traj_c2.json"}`
  (Q′, the checkpoint behind runs `a6k2_<m>_gptq_w4_d2_n*`). `q_ckpt` = `{"kind": "gptq", "wbits": 4, "calib":
  "manifests/a6k2/<m>/calib_fp_traj_c1.json"}` (Q, the checkpoint behind the Q blocks `a6k2_<m>_gptq_w4_d1_<blk>`, the
  same Q episodes as the precision dev forks). `expect_distinct_numerics: true` (the two servers must have different
  canaries).
- **Arm mapping.** The driver's role "B" is Q′. Driver branch BB = Q′Q′, BQ = Q′Q, QB = QQ′, QQ = QQ. First index =
  action at the first divergence, second = controller from the next step on.
- **Divergence.** Along Q's recorded trajectory, Q′ generates its full greedy action at each decision from the identical
  prompt. Its server-returned prompt ids must equal Q's recorded prompt ids, otherwise the unit is excluded with that
  reason. The first tool-structure divergence (`fork.compare_actions` primary categories; text-only differences are
  skipped) is frozen as the unit's state. Q replay at the state is checked as in dev.
- **Cells.** q4 (Qwen3-4B) and q8 (Qwen3-8B), GPTQ-W4, Q = d1, Q′ = d2. q4: 1 GPU, B and Q servers at gpu_util 0.44.
  q8: 2 GPUs (one per server), pinned to node004/005/007 in rotation (existing convention).
- **Blocks (fixed by order, not by outcome).** Ordered list f01, f02, …, f17 (nonces from
  `manifests/fork/dev_blocks_v1.json`), each = retail (58) + airline (27) = the 85 dev panel tasks
  (`manifests/fork/splits_v1.json`). Queued as tasks of 3 consecutive blocks (g1 f01–f03, g2 f04–f06, g3 f07–f09,
  g4 f10–f12, g5 f13–f15, g6 f16–f17) per cell, priority −28. The existing blocks q3–q5 are not used (q3 is used by the
  gate only).
- **Analysis set.** The longest prefix f01…f_K of the ordered list such that every block in it is a complete 85-task
  block (strict rule below) in the same-precision fork of BOTH cells at the evidence freeze (2026-10-03). The precision
  side uses the same K blocks (all 20 precision blocks are complete). Target minimum K = 6 (f01–f06). If K < 3, no
  reading is made and only per-block numbers are reported. Completed blocks beyond the prefix are reported per block
  only and do not enter the estimates.
- **Infrastructure failures** are requeued unchanged (with `fork.resume: true`, which reuses complete branch files); the
  search is deterministic, so a rerun reproduces the frozen states.

## 3. Gate (before any formal task is queued)

One gate task per cell (fork_driver mode `gate`, output `analysis/fork/sameprec/gate/<m>/`), Q blocks
`a6k2_<m>_gptq_w4_d1_q3` (retail, airline; not in the analysis set), Q′ own blocks `a6k2_<m>_gptq_w4_d2_n1`
(retail, airline). Checks, all required:
1. **Identity.** idcheck Q (16 recorded d1 decisions regenerated bit-exactly) and idcheck Q′ (16 recorded d2_n1 decisions
   regenerated bit-exactly), distinct canaries.
2. **B-role prompt ids.** Every search row's Q′ prompt ids equal Q's recorded prompt ids (no exclusion with reason "B
   prompt ids differ").
3. **Divergence search.** Runs without errors and finds states (reported: divergence rate, categories).
4. **No-ops.** QQ no-op on every gate state, and Q′Q′ no-op on Q′'s own trajectory (driver a_BB): suffix, prompt ids,
   termination, outcome, counters and env hashes bit-exact.
5. **Replay / restoration.** Q replay at each state bit-exact; save/load (history and env hash); budget accounting;
   re-prefill; order and concurrency isolation.
The gate passes iff the driver verdict `pass` is true and check 2 holds. If it fails, nothing formal is queued and the
failure is reported. Result: `analysis/fork/sameprec/GATE.md`.

## 4. Admission (identical to the precision analysis)

`analysis/fork/analyze_dev.py` loaders and rules, imported, not copied: snapshot gate (Q block admitted in
`analysis/insights/iter_3/out/snapshot_auto_20261001T0600Z.json`, trajectory sha unchanged), quarantine of a whole fork
task directory on any QQ no-op mismatch, dedupe, strict complete-block rule (W70: a block with any missing unit for
any reason is incomplete and leaves), complete 85-task retail/airline panel blocks only (W78), split guard dev. Units
without a divergence enter with zero effect. Same-precision fork outputs live under `analysis/fork/sameprec/`, which no
other analysis script reads. Acceptance counts are reported (QQ no-op sample pass rate, Q replay at state, prefix_ok and
env_hash_init_ok of all branches) but, as in the precision analysis, they exclude units only through quarantine.

## 5. Estimands

Notation with Q′ in place of B: Y_Q′Q′, Y_Q′Q, Y_QQ′, Y_QQ (success = DB success with a normal stop; analyze_dev.success).
Unit = task × block.

**Same-precision 2×2 (per cell q4, q8 and the equal-weight pool q4+q8), on the analysis set:**
- Full pool (every admitted unit; no divergence = 0): r′ = P(Y_Q′Q = 1, Y_QQ = 0), d′ = P(Y_Q′Q = 0, Y_QQ = 1),
  M′ = r′ + d′, G_all′ = r′ − d′. Mean of block means.
- Divergence rate = divergent units / admitted units.
- On divergent states (ratio of block sums): G′ = Y_Q′Q − Y_QQ, H′ = Y_QQ′ − Y_QQ, F′ = Y_Q′Q′ − Y_QQ;
  Δ_Q = Y_Q′Q − Y_QQ, Δ_Q′ = Y_Q′Q′ − Y_QQ′, I = Δ_Q − Δ_Q′; the 3×3 table of (Δ_Q, Δ_Q′); off-diagonal share
  P(Δ_Q ≠ Δ_Q′); strict reversals P(Δ_Q · Δ_Q′ < 0) and their share of the off-diagonal mass; the 16 patterns.
- The same quantities for the precision 2×2 (B = BF16) of the same cells, recomputed on the same K blocks from
  `analysis/fork/dev/<m>_gptq_w4_d1/` with the same code.

**Primary comparison (paired, identified):** ΔM = M_prec − M′ on the same task×block units (the same Q episode is the
QQ arm of both designs). Per unit: M_prec(u) − M′(u), on units admitted in both designs; per cell and the equal-weight
pool q4+q8.
- Fixed-pool interval (primary): over the K complete blocks. t over the K per-block mean differences when K < 10 and
  the block bootstrap when K ≥ 10 (analyze_dev.summarise rule); both are always reported.
- Crossed task × block bootstrap (secondary: generalisation to new tasks).
- B = 2000, seed 20261001 (analyze_dev.Boot), draws shared by both cells so the pool is valid.
- Also reported: Δr, Δd, ΔG_all with the same intervals.

**Secondary comparison (descriptive):** Δoff = offdiag_prec − offdiag′. The two shares are on different state sets (each
design selects its own first divergences), so this is descriptive and confounded by state selection. Interval: shared
block-bootstrap draws of the two ratios (t over per-block ratio differences when K < 10), plus crossed. Reported
alongside, per state and conditional on divergence:
- (a) the off-diagonal share on the units that diverge in BOTH designs, each design on its own state of that unit;
- (b) the subset of (a) where both designs diverge at the same decision index t* (same history h_t; only the alternative
  action and the partner controller differ).
Also descriptive: ΔG′/H′/F′ means, Δ strict-reversal share, Δ divergence rate.

## 6. Frozen interpretation rule

Applied to the pooled q4+q8 estimate with its primary fixed-pool interval. Per-cell readings use the same rule and are
secondary. "A few pp" = 3 pp (the project's ε = g_min).

- **Turnover (M).**
  - If the ΔM interval includes 0 and |ΔM| ≤ 3 pp: the paper must say that the turnover largely reflects generic
    trajectory sensitivity of the closed loop rather than a precision-specific effect.
  - If the interval excludes 0 with ΔM > 0: the paper reports the precision-specific excess ΔM (with its interval) and
    its share ΔM / M_prec.
  - Any other result (the interval includes 0 but |ΔM| > 3 pp, or ΔM < 0 with the interval excluding 0) is reported as
    is: "not resolved by this control" or "same-precision turnover at least as large", with the numbers.
- **Controller dependence (off-diagonal share).** The same three-way rule on Δoff, always labelled descriptive (different
  state sets), stated together with readings (a) and (b).
- If both M and the off-diagonal share fall in the "similar" case, the paper must say that turnover and controller
  dependence largely reflect generic trajectory sensitivity rather than precision-specific effects.
- Either outcome is reported. No other thresholds, subsets, or re-analyses enter the reading. Anything else is labelled
  exploratory.

## 7. Outputs

`analysis/fork/analyze_sameprec.py` → `analysis/fork/out/sameprec_<UTC>.{md,json}`, TL;DR first: analysis set K, per-cell
and pooled estimates for both designs, ΔM and Δoff with intervals, the frozen reading, acceptance counts, and per-block
numbers (r, d, M, G_all, states, divergence rate per block and cell, for every completed block including blocks outside
the prefix) so that partial completion can be reported.
