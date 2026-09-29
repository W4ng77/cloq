**TL;DR**
- Iter-2 prep (2026-09-29T05:06Z): 20 a6k2 run-domains (≥10% of episodes; 27 with any) are silently broken by `infrastructure_error` (node003's remote simulator); re-queue them (E9, ≈4.5 GPU-h) and add a worker guard (E11). Evidence: `docs/insights/iter_2_prep.md#0-data-flags-fix-before-any-number-goes-into-the-paper`.
- Queue the FP32-head control (E8, ≈1.6 GPU-h, one vLLM flag). It is the only open test for W2 / Du et al. Next is E10 (E3 for the sub-grid cells, ≈0.8 GPU-h).
- The no-GPU items A2-1…A2-11 are done. A2-10/11 are the conformal layer: `analysis/insights/iter_2/out/c0*.json` ← `c0*.py`, explained in `docs/insights/iter_2_conformal.md`. E12 (≈2.4 GPU-h, 3 extra nonce nulls per model) makes the exact within-prompt test usable.

# Experiment plan (running)

Status values: proposed / accepted by main / queued / done / dropped. Owner of status changes: main session.
Cost basis: `queue/done/<task>.json` `seconds`:
- q4 run 0.265–0.444 h;
- det tasks 0.10–0.13 h;
- q8_bf16_cal 0.271 h and q14_bf16_cal 0.328 h (57 tasks each);
- q8/q4 generation-time ratio 1.35 (`runs/a6000_q{4,8}_bf16/retail/decisions.jsonl`).

The matrix totals ≈115 GPU-h. Capacity is ≈26 agent GPUs (`/data/ziyangs/cloq_work/logs/node_*.out`), so compute is not binding.

| id | status | proposal | serves | GPU-h | evidence |
|---|---|---|---|---|---|
| E1 | proposed (iter 1) | determinism mechanism + fix check: E1a probe pinned to node005; E1b probe with `TORCHINDUCTOR_DETERMINISTIC=1` + fresh cache on node003 and node005 | all | ≈0.75 | `analysis/insights/iter_1/exp/out/bestconfig_*.tsv` ← `exp/e_bestconfig.sh`; `logs/tasks/probe_det_q4.log` |
| E2 | proposed (iter 1) | `TORCHINDUCTOR_DETERMINISTIC=1` for agent servers + canary gate + rerun q4, q8 and the 4 q14 quant tasks started pre-fix, under a new run-id prefix; legacy runs kept | I1-P1a, I3-P3a/c, I2-P2b, I4-P4b | ≈22 | `exp/out/server_flavour.json` ← `exp/e_server_flavour.py`; `exp/out/detshift.json` ← `exp/e_detshift.py` |
| E3 | proposed (iter 1) | open-loop D per cell on the BF16 reference contexts, on the cell's own server (`cloq/openloop.py`) | I3, I2-P2b | ≈26 (est.; measure on the first q4 cell) | truncation bias stated in `docs/insights/iter_1_candidates.md` I3 evidence |
| E4 | proposed (iter 1) | analyses: (a) s02 counts raw-token divergence as an event ("format"); (b) flavour tags joined into s0x, paired stats on clean pairs only; (c) k=3/W3 audit for empty or terminated episodes, strict error budget, tokens per episode; (d) P4a SD vs tau2 #540 | I1, I2, I4 | 0 | `exp/out/ctxmis.json` ← `exp/e_ctxmis.py`; survey turn in `iter_1_discussion.md` |
| E5 | proposed (iter 1) | numerics-flavour null family: legacy q4/q8 runs (free) + 1 `--enforce-eager` BF16 run per model + gauss k=0.03 s3–s5 for q4/q8 | I1-P1c, I4-P4c, survey weight-only null | ≈6 | `out/s04_node_floor.json` ← `s04_node_floor.py` |
| E6 | deferred | seeds s3/s4 at k=0.3 and k=1, all models (P2d power: SE ≈0.037 per model with 2 seeds) | I2-P2d | ≈15 | power arithmetic in the discussion §Decisive tests |
| X1 | proposed drop (conditional) | `q32_gptq_w4_d2`, if q32 GPTQ builds OOM; no insight needs a 2nd calibration draw at 32B | — | −4 to −8 | candidates I3 (4080 draws exchangeable) |
| E8 | proposed (iter 2) | FP32 lm_head control on q4: det pair + bf16, eager, k = 0.001 s1, k = 0.03 s1, all with `--hf-overrides '{"head_dtype": "float32"}'`; pre-registered predictions (a)–(d) | I1/W2, novelty vs Du et al. | ≈1.6 | spec and predictions: `docs/insights/iter_2_prep.md#e8-fp32-head-control-the-reviews-item-11-essential-for-w2-and-for-positioning-against-du-et-al`; tie share `analysis/insights/iter_2/out/p02_ties.json` `tie_density` |
| E9 | proposed (iter 2) | re-queue the F1-broken runs away from node003: new task `a6k2_q4_null_fix` (n3–n5) plus 7 done tasks unchanged (q8 gauss1_s1, q8 rtn_w3, q4 gauss0.003_s1, gauss1_s4, gauss2_s2, gauss3_s1, q8 gauss0.001_s2), after moving the broken run dirs aside | all outcome claims | ≈4.5 | `analysis/insights/iter_2/out/p00_snapshot.json` `infra_error_runs`; `/data/ziyangs/cloq_work/logs/tasks/a6k2_q4_bf16.log` L1257 |
| E10 | proposed (iter 2) | E3 open-loop D for k ∈ {0.001, 0.003, 0.01, 2} × s1/s2 (`make_tasks.py --only e3`) | W11 / Fig. 2 x-axis | ≈0.8 (q4), ≈1.6 (q4 + q8) | `analysis/insights/iter_2/out/p05_e3_axis.json` |
| E11 | proposed (iter 2) | worker guard: fail or retry a task whose run has any `infrastructure_error`, and probe the simulator between runs; iter-1 verify scripts drop those episodes | data integrity | 0 (code) | `docs/insights/iter_2_prep.md#f1-infrastructure_error-episodes-are-silently-scored-as-failures` |
| A2-1 | done (iter 2) | declared-margin TOST per family, per cell and pooled free zone; M80 per family | W1 | 0 | `analysis/insights/iter_2/out/p01_equivalence.json` ← `p01_equivalence.py` |
| A2-2 | done (iter 2) | within-pass stratified Δ (IVW), null sets A–D, leave-one-family-out | W3, W4 | 0 | same, `stratified`, `nullsets`, `lofo_nullset_A` |
| A2-3 | done (iter 2) | exact-tie floor: tie density (5 models), flat sub-grid hazard, tie share of flips, cross-model floor prediction | W2 | 0 | `out/p02_ties.json` ← `p02_ties.py`; `out/p06_weight_ulp.json` ← `p06_weight_ulp.py` |
| A2-4 | done (iter 2) | Flat-Score / Singh / McNemar vs the null-referenced TOST | W5 | 0 | `out/p07_protocol_tally.json` ← `p07_protocol_tally.py` |
| A2-5 | done (iter 2) | Replay Gap reconciliation (agent-first flips, depth) | W5, Q4 | 0 | `out/p03_replay_gap.json` ← `p03_replay_gap.py` |
| A2-6 | done (iter 2) | text vs tool hazard | W2 | 0 | `out/p02_ties.json` `closed_loop.*.hazard_{text,tool}` |
| A2-7 | done (iter 2) | write/read/text first divergence, write-set change, Spearman vs Δ (P2b predictor not supported) | P2b | 0 | `out/p04_write_flips.json` ← `p04_write_flips.py` |
| A2-8 | done (iter 2) | null width: non-degenerate p_t fraction, SD ratio with chi-square CI | W9 | 0 | `out/p01_equivalence.json` `null_width_A` |
| A2-9 | done (iter 2) | E3 axis choice: token flip rate | W11 | 0 | `out/p05_e3_axis.json` ← `p05_e3_axis.py` |
| X2 | dropped (iter 2) | extra per-family draws aimed at ±5 pp equivalence | W1 | — | M80 ≥ 6.5 pp even at 5 draws: `out/p01_equivalence.json` `families.*.m80_tost` |
| A2-10 | done (iter 2, conformal) | conformal/permutation equivalence per draw, family and pooled (null sets A/S/B); ε-TOST by test inversion; e-values; power and granularity | C2, W1 | 0 | `analysis/insights/iter_2/out/c01_conformal_equivalence.json` ← `c01_conformal_equivalence.py`; `docs/insights/iter_2_conformal.md#1-conformal-equivalence-test-a2-10` |
| A2-11 | done (iter 2, conformal) | open-loop → closed-loop conformal intervals (jackknife+, leave-one-model-out), hazard and success Δ; re-runnable as E3 for q14/q30a3/q32 lands | C3, C4 | 0 | `analysis/insights/iter_2/out/c02_openloop_conformal.json` ← `c02_openloop_conformal.py`; `docs/insights/iter_2_conformal.md#2-open-loop--closed-loop-conformal-prediction-a2-11` |
| E12 | proposed (iter 2, conformal) | 3 extra nonce nulls n6–n8 (new nonces) for q4, q8, q14, so the prompt-stratum-matched exact test S has n = 6 (p_min 1/28 at 2 draws) | C2 (F-C1: pooled ±5 pp rests on the mixed-prompt null) | ≈2.4 | spec: `docs/insights/iter_2_conformal.md#5-design-flaws-and-proposals`; basis `queue/done/a6k2_q8_bf16.json` (2,680 s for 6 runs), `a6k2_q14_gauss0.1_s1.json` (1,968 s) |
| E13 | proposed (iter 2, conformal) | rule: new nonce'd cells (PLAN_iter3 X1/X2) use nonces disjoint from the null nonces | C2 | 0 | `c01…json` `note_S`; `scripts/a6000/make_tasks.py` L44/L53 reuse `NONCES[0:2]` |
| A2-12 | done (iter 2, review v2) | integrity gate G1–G7 + frozen snapshot manifest; run_all.sh reads it; headline diff | W-A | 0 | `analysis/insights/iter_2/out/snapshot_20260929T0732Z.json` ← `integrity.py`; `out/diff_20260929T0732Z.md` ← `diff_outputs.py`; `docs/insights/iter_2_integrity.md#1-integrity-gate-a2-12-review-w-a` |
| A2-13 | done, provisional (iter 2, review v2) | churn: stratum-matched, excess churn with CI, negative controls, null-vs-null, Flat-Score r; fixed-checkpoint control auto-included | W-B, Q1/Q2/Q5 | 0 | `out/k01_churn.json` ← `k01_churn.py`; `iter_2_integrity.md#2-churn-checks-a2-13-review-w-b-q1-q2-q5` |
| A2-14 | done (iter 2, review v2) | Holm across all family×statistic tests; e-product dropped (per-model + mean); NR1 null rule (S primary) | W-C, W-G | 0 | `docs/insights/NULL_RULE.md`; `out/n01_null_rule.json` ← `n01_null_rule.py`; `out/c01_conformal_equivalence.json` |
| A2-15 | done, provisional (iter 2, review v2) | C3 matched dose: partial rho(flip, hazard given dose) 0.86 [0.67, 0.96] | W-D | 0 | `out/d01_matched_dose.json` ← `d01_matched_dose.py` |
| A2-16 | done, provisional (iter 2, review v2) | floor by pairing stratum; stratum-matched cross-model prediction (5–29% error) | Q4, C1 | 0 | `out/f01_floor_strata.json` ← `f01_floor_strata.py` |
| E14 | proposed (iter 2, review v2) | dedup the 4 completed runs that still have abandoned attempts (`scripts/a6000/dedup_decisions.py`), then re-run the gate | F-I3 | 0 | `iter_2_integrity.md#7-proposals-for-main-costs-from-queuedonejson-seconds` |
| E15 | proposed (iter 2, review v2) | fixed Gaussian k=1 s1 checkpoint × churnctl nonces (6d1f0b3e/f07a5c21) on q4/q8/q14: stratum-S Gaussian damage test and dose-matched churn control | F-I1, F-I2 (churn headline, k=1 harm) | ≈3.5–6 | spec in `iter_2_integrity.md#7-proposals-for-main-costs-from-queuedonejson-seconds`; basis `queue/done/a6k2_q4_gauss1_s4_redo.json` (1,724 s), `a6k2_q8_gauss1_s2.json` (3,498 s), `a6k2_q14_gauss1_s1.json` (1,848 s) |
| E16 | proposed (iter 2, review v2) | re-run `bash analysis/insights/iter_2/run_all.sh` after redos, null_extra and churnctl land; replace the provisional numbers | all | ≈3 min CPU | `analysis/insights/iter_2/run_all.sh` |

## Ready-to-queue specs

The main session reviews and enqueues these. Every task needs its node's job to still be alive, because the node-local caches live in `/tmp/cloq_<job>`.

E1a (inherits node005's compile cache, which holds R0_BLOCK=2048; predicted = A 30/30):
```json
{"id": "probe_det_q4_n005", "kind": "cmd", "model": "q4", "priority": -20, "deps": [], "node": "node005",
 "title": "determinism probe q4 on node005 cache",
 "cmd": "source scripts/a6000/env.sh && python scripts/a6000/det_probe.py --model q4 --run-a a6000_det_q4_a --run-b a6000_det_q4_b --out analysis/determinism/probe_q4_node005.json"}
```

E1b: two copies, `node` = node003 and node005, with ids `probe_det_q4_detflag_n003` / `_n005`. Predicted: both summaries are identical, whether they equal A or B:
```json
{"id": "probe_det_q4_detflag_n003", "kind": "cmd", "model": "q4", "priority": -20, "deps": [], "node": "node003",
 "title": "determinism probe q4, Inductor deterministic, fresh cache",
 "cmd": "source scripts/a6000/env.sh && export TORCHINDUCTOR_DETERMINISTIC=1 TORCHINDUCTOR_CACHE_DIR=$TMPDIR/ind_det_$$ VLLM_CACHE_ROOT=$TMPDIR/vllm_det_$$ && python scripts/a6000/det_probe.py --model q4 --run-a a6000_det_q4_a --run-b a6000_det_q4_b --out analysis/determinism/probe_q4_detflag_node003.json"}
```
`det_probe.py` drops the raw completions (`res.pop("conditions")`). To compare the two nodes token by token, and not only by the A/B counts, keep that field. That needs a code change, which is for main.

E2 steps:
1. Touch `queue/STOP` and let the running tasks finish. Their output becomes legacy-flavour data.
2. Add `export TORCHINDUCTOR_DETERMINISTIC=1` to the agent-server environment (`scripts/a6000/env.sh` or `serve.sh`).
3. Add a canary to `worker.py`. After the server is healthy, send the 3 decision-0 prompts of `manifests/a6000/det_tasks.json` and hash the completion ids and top-5 logprobs. Compare against `configs/canary/<model>.json`: the first server under the flag writes it, and every later server must match it or the task fails. Apply the same check to the simulator at node start.
4. Regenerate the q4 and q8 matrices with `R = a6000v2_{m}`, so legacy run dirs are never overwritten (`make_tasks.py` needs a prefix option).
5. Confirm with a det pair under the flag on 2 nodes (`determinism(m, "c"/"d", node)`), ≈0.25 GPU-h.

E4a: patch `analysis/insights/iter_1/s02_trajectory_divergence.py`. Where `b[key] != p[key]` follows equal `action`, record an event of type `format` at i−1, not a censoring. Rerun with `bash analysis/insights/iter_1/run_all.sh`.

E5: add `eval_task(f"{m}_bf16_eager", m, "bf16", {"kind": "bf16"}, [run(f"{R}_bf16_eager")], p)`, served with the extra vLLM arg `--enforce-eager`. The worker needs a `serve_extra` field for this. Also add gauss `{"kind": "gauss", "k": 0.03, "seed": s}` for s = 3, 4, 5.

## History

- 2026-09-29 (iter 2, review v2 must-do 2–5): A2-12…A2-16 done on frozen snapshot `20260929T0732Z` (provisional). E14–E16 proposed. Flags: F-I1 (canonical stratum capped at n = 2, so Gaussian cells are untestable under the NR1-primary null S), F-I2 (dose-matched Gaussian k=1 churns at least as much as the quantizers), F-I3 (4 completed runs not deduplicated). See `docs/insights/iter_2_integrity.md`.

- 2026-09-28 (iter 1, round 1): E1–E6 and X1 proposed. Evidence scripts were added under `analysis/insights/iter_1/exp/` (read-only over logs, runs and the queue; `e_bestconfig.sh` reads the node-local caches over ssh).
- 2026-09-29 (iter 2 conformal): A2-10/A2-11 done (0 GPU-h, snapshot 05:45Z). E12 (≈2.4 GPU-h) and E13 (rule) proposed. Flags: F-C1, where the pooled ±5 pp equivalence rests on the mixed-prompt null A, and F-C2, where open-loop features do not predict success Δ, so the C4 gate cannot certify damage. See `docs/insights/iter_2_conformal.md`.
- 2026-09-29 (iter 2 prep): A2-1…A2-9 done (0 GPU-h). E8–E11 proposed and X2 dropped. Flags F1 (`infrastructure_error` scored as failure; 20 run-domains ≥10%, 27 with any) and F2 (iter-1 `action_key` ignores top-level tau2 tool calls). The E8 specs are in `docs/insights/iter_2_prep.md#3-proposals-gpu-and-code-for-main`.
