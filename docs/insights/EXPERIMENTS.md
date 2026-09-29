**TL;DR**
- Blocker: agent servers draw a numerics "flavour" at compile time (Inductor reduction autotune). Only q4 bf16 and its nulls are verified clean; q4/q8 cells are mixed. Do E1 (≈0.75 GPU-h) now, then E2 (flag + canary + rerun q4/q8, ≈22 GPU-h, ≈2 h wall) **before** q4 gptq/awq and q14/q30a3/q32 references start.
- E4 (0 GPU-h): fix s02 censoring (40/54 q8 k=1 tasks are censored raw-token divergences) and tag every run with its flavour.
- Then E5 (flavour null family, ≈6 GPU-h) and E3 (open-loop D, ≈26 GPU-h est.). Discussion: `docs/insights/iter_1_discussion.md#experiment-round-1`.

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

- 2026-09-28 (iter 1, round 1): E1–E6 and X1 proposed. Evidence scripts were added under `analysis/insights/iter_1/exp/` (read-only over logs, runs and the queue; `e_bestconfig.sh` reads the node-local caches over ssh).
