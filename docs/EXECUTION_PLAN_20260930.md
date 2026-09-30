**TL;DR** Status and GPU plan as of 2026-09-30 evening, for *Tracing the Consequences of Quantization in Closed-Loop Agents* (experiment freeze 10-05, ARR 10-12).
- **Established:** W4 turnover above the numerics floor, and damage at W3 and at plain low-bit KV. The checkpoint lottery did not replicate. No W4 behavioural fingerprint was detected. The paper skeleton exists. The q4 replay gate passes.
- **Missing:** everything the paper's results depend on — the same-state four-branch results, their annotation, the telecom holdout confirmation, the local precision-restoration intervention, and A/KV coverage.
- **Resources:** 42 A6000s (not 48). Compute fits (~60–80 cluster-hours of work in ~100 hours). Engineering and validation time is the binding constraint, not GPUs.
- **Avoiding idle cards:**
  - simulator replicas sized to demand, with automatic load-aware routing;
  - small agents packed two per card;
  - a simulator-free backlog always queued;
  - stress configurations capped;
  - all checkpoints built ahead of their evals.

# Execution plan (2026-09-30)

## 1 What we have (evidence status)

| # | Result | Status | Evidence |
|---|---|---|---|
| 1 | W4 turnover exceeds the numerics floor. Pooled excess λ RTN +0.19 [0.10, 0.30], GPTQ +0.15, AWQ +0.16 (Holm); clearest on q4 and q32 | established; motivation, restricted to the verified conditions | `analysis/insights/iter_3/out/r10_turnover_stats_live_20260929T1937Z.json` |
| 2 | Damage anchors: RTN-W3 −16.7 pp (q8), −14.5 pp (q14); plain KV INT4/INT3 destroys q4 (79% / 90% of tokens flip); KV INT8 and INT4 with Hadamard are mild | established | RESEARCH_LOG W13–W14, iter_3 r07 |
| 3 | Checkpoint lottery (same method, new calibration draw): did not replicate in the pre-registered test (φ 0.40, p 0.74; r 0.42, p_holm 0.42) | refuted as a headline; kept as a transparent record | `analysis/insights/iter_4/out/prereg_h1_h4_CONF_20260930T0044Z.json` |
| 4 | Behavioural fingerprint: the original H3 test was invalid. Corrected: W4 quantizer recalibrations not detected (F 0.025, p 0.30); random fixed perturbations 0.283, p 0.028 (post-hoc) | exploratory | `docs/insights/METHODOLOGY_REVISION.md` |
| 5 | The act/talk shift conditional on BF16's choice is mostly a selection effect | corrected | `analysis/insights/iter_4/act_talk_selection.py` |
| 6 | Crossed variance components: checkpoint SD 3.7 pp (q4) / 1.2 pp (q8); method not estimable | descriptive | `analysis/insights/iter_4/p1_crossed.py` |
| 7 | Measurement infrastructure is verified: deterministic serving (cross-node 257/257, 303/303); tool-type table checked against τ² tool definitions (the telecom regex bug is fixed); DB success naming | done | W3, W29 |
| 8 | Replay gate on q4 GPTQ-W4 d1 passes: 8 states (retail/airline; act→talk, talk→act, tool name, tool args); no-op QQ 8/8, BB 4/4, same checkpoint 6/6, isolation and save/load, budget, re-prefill. q8 environment replay CPU check including telecom: 1612/1612 | preliminary pass; telecom fork states and q8 gate pending | `analysis/fork/gate/` |
| 9 | Paper skeleton: 8 pages, builds cleanly, 136 labelled placeholders | done | `paper/latex/main.pdf` |
| 10 | Open-loop probes E3 and E4-2 top-20 for about 50 cells; q4 new methods (NF4, MXFP4, rotation, stochastic rounding); fake KV hook | background measurements | W12–W20 |

## 2 What is missing (in the order the paper needs it)

| Priority | Result | Needs | Blocks |
|---|---|---|---|
| P1 | Replay gate: telecom fork states, q8, throughput pilot (p50/p90 suffix time, simulator load) | fork agent (running) | everything below with forks |
| P1 | Paired BF16 runs (`bfpair` q1–q5) → Q−B non-inferiority / TOST at 3 pp | 10 runs, 2 done, 6 running | §3 of the paper |
| P1 | Development blocks: Q runs for GPTQ-W4 d1 and AWQ-W4 d1 on q4/q8 plus BF16 on the same 17 new nonces | 36 tasks: 3 done, 11 running, 22 todo | development forks |
| P1 | Development forks: all 85 tasks × 4 cells × blocks. Coverage, rescue / damage / both succeed / both fail, G, A/C/I with intervals | fork tasks after the gate | Table 2, Figure 3 |
| P1 | Automatic event extraction, LLM labels, ~80 human-blinded states (~20 double) | annotation tools; **the author and the collaborator review on 10-02 and 10-03** | Table 4, Figure 5, case studies |
| P1 | Telecom holdout confirmation (34 tasks), frozen protocol `PREREG_FORK_CONFIRM.md` | freeze on 10-03 | Table 3 |
| P2 | KV axis in forks: K8V8 core, K4V4 stress, K-only / V-only | hook exists; add cells | Figure 2 |
| P2 | Local precision restoration: BF16 restored in early / middle / late layer thirds, attention vs MLP, budget-matched random modules; fork evaluation | mixed checkpoints (cheap with fake quantization) | Figure 4, deployment claim |
| P2 | Error dose curve Wα = W + α(W_Q − W), α ∈ {0, 0.25, 0.5, 1, 2} | weight-only; about half a day | Figure 2 |
| P2 | Static precision-allocation rule formed on development data, tested on the holdout | from the restoration results | deployment validation |
| P3 | A8 activation hook (covering fused QKV and merged MLP), then SmoothQuant W8A8, then QuaRot W4A4 (fake quantization; online Hadamard on the down_proj input and per-head Q/K; checked against the official configuration) | one engineering agent, about 2 days total, each step verified | W×A×KV 2³ matrix |
| P3 | BFCL multi-turn (Base, Missing Parameter, Missing Function, Long Context) and ALFWorld text | adapters about a day each; no LLM user simulator | external validity |
| P3 | Third model family: half-day tool-calling smoke test, dropped if it fails | — | coverage |
| deferred | Representation probes and activation patching (needs an HF engine plus a bridge), WebShop (search-index setup), KIVI (after A8) | — | Limitations / future work |

Anything in P3 not verified by the evening of 10-02 is excluded from the main text and listed in Limitations.

## 3 Cluster inventory and allocation

- **Inventory (measured 2026-09-30):**
  - node001: 4 A6000s
  - node003: 6
  - node004–node007: 8 each
  - **Total: 42 A6000s (48 GB each).** No fast cross-node interconnect; TP=2 only on NVLink pairs.
- **Current throughput:** about 1,500 closed-loop episodes/hour (6-hour average), with about 1,350 generated tok/s cluster-wide.

| Role | GPUs now | Plan | How |
|---|---|---|---|
| User simulator (Qwen3-30B-A3B, TP=2, same canary) | 10 (5 replicas) | 14 (7 replicas) | add a second replica on node004 and node005 at the next runner restart (resume-safe) |
| Closed-loop agents and fork branches (q4/q8) | ~26 | ~22 cards, packed 2 per card for q4 | q4 BF16 and fake-quant fit twice in 48 GB; the canary still has to pass per server |
| Simulator-free work: quant builds, mixed-precision checkpoints, open-loop probes, BFCL/ALFWorld, hook validation | ~4 | ~4–6, fills gaps | priority interleaving |
| Stress configurations (W3, Gaussian k≥2, KV4, q30a3/q32 remnants) | 6–8 | at most 1 per node | queue quota |

## 4 Keeping every card busy

1. **Load-aware simulator routing.** A balancer loop (`scripts/a6000/sim_balancer.py`) runs every 5 minutes.
   - It reads each simulator's running/waiting/KV load from `gpumon`.
   - It rewrites `queue/USER_BASE.<node>` so the next task on an overloaded node uses the least-loaded replica.
   - Hysteresis prevents flapping, and every change is logged.
   - Routing is per task start, so running episodes are never disturbed.
   - All replicas serve the same model and pass the same canary, so routing does not change outcomes.
2. **Replica count follows demand.** Target: simulator waiting ≤ 10 and KV ≤ 80% at steady state. If the cluster-wide wait stays above 30 for more than 30 minutes, add a replica at the next runner restart. If all replicas idle, convert one back to agent cards.
3. **Always keep a simulator-free backlog** at a priority just behind the core queue: open-loop probes, checkpoint builds, BFCL/ALFWorld runs. A card whose agent would only wait on a saturated simulator does useful work instead.
4. **Build ahead.** All calibration manifests, quantized and mixed-precision checkpoints are built at top priority before their eval tasks, so evals never wait on a build. They are tagged by content hash and reused.
5. **Granularity.** Tasks hold at most 3 runs, and fork tasks are split per task subset. Short tasks keep the queue fluid, and a failure loses little (resume-safe).
6. **Long-tail control.** Stress configurations loop to max_steps and hold a card and simulator slots for hours (W11). At most one stress task runs per node at a time, and stress cells run after the core matrix.
7. **Failures.** The monitor catches failed tasks. Context overflow and agent parse errors count as task failures; real outages are requeued and resumed (W10, W27).
8. **Dashboard and gputop.** Live utilisation, simulator waiting, GPU-hours per phase; a 30-minute heartbeat.

## 5 Schedule and compute budget

Estimates are in closed-loop episode-equivalents at the current rate (a fork suffix counts as about half an episode). They will be corrected by the throughput pilot.

| When | Work | Approx. episodes | Cluster hours |
|---|---|---|---|
| 09-30 night | Finish bfpair and dev block Q/BF16 runs; build KV / restoration / α checkpoints; start A8 hook, BFCL and ALFWorld adapters | ~9k | ~6 |
| 10-01 | Replay gate on telecom and q8, throughput pilot; **evening decision** (deterministic / stochastic / keep engineering); start development forks | ~6k | ~5 |
| 10-02 | Development forks on 85 tasks × {GPTQ-W4, AWQ-W4, KV8, W3/KV4 stress} × blocks; restoration and α forks; automatic events and LLM labels; **human review starts**; A8 / SmoothQuant / QuaRot verification; BFCL / ALFWorld runs | ~30k | ~20 |
| 10-03 | Freeze `PREREG_FORK_CONFIRM.md` (R from development variance and throughput, thresholds, analysis family, telecom mapping of mechanism categories); start the telecom holdout; W×A×KV matrix if the A hook passed | ~20k | ~13 |
| 10-04 | Holdout completes; static precision-allocation rule tested; simulator robustness if time allows | ~15k | ~10 |
| 10-05 | Evidence freeze: `CLAIM_EVIDENCE.md`, figures, reviewer packet | — | — |

- **Total:** about 80k episode-equivalents, roughly 55–60 cluster-hours at 1,500/h, or about 40 hours after the simulator expansion.
- **Available until the freeze:** about 100 hours.
- **Headroom:** the slack covers reruns and more blocks, where the development variance says they are needed.

## 6 Deliverables

`STUDY_PROTOCOL.md`, `QUANT_MATRIX.csv`, `OLD_RESULT_REUSE.csv`, `RESOURCE_PLAN.md` (this file's §3–4), `THROUGHPUT_PILOT.json`, `RUN_BUDGET.csv`, `FORK_PROTOCOL.md` / `REPLAY_ACCEPTANCE.md`, `METHOD_FIDELITY.md` (A8 / SmoothQuant / QuaRot), `ANNOTATION_PROTOCOL.md`, `PREREG_FORK_CONFIRM.md`, `CLAIM_EVIDENCE.md`, and the paper. The dashboard distinguishes run / verified / analysed / confirmed.
