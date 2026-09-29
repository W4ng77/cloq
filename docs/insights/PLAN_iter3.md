**TL;DR** Storyline v3 and the experiments behind it, for the ARR/NAACL deadline of 2026-10-12. Experiments freeze on
10-05. Compute is not the constraint (~38 GPUs ≈ 6k GPU-h/week against ~0.4k used). The weak points reviewers will
attack are generality (one benchmark, one model family, fake-quant only) and the statistics. The plan adds real
deployed formats, a second model family and a third τ² domain, and makes the statistics conformal + TOST.

# Plan, iteration 3 (2026-09-28, main session)

## 1. Storyline v3
Working title: *Every Checkpoint Is a Re-Roll: Perturbation Equivalence for Closed-Loop Agent Evaluation*.

One sentence: in closed-loop agents, *any* intervention above the model's own decision-tie floor re-rolls the
trajectory. So "is the compressed agent worse?" is well-posed only against the model's own perturbation null, and
divergence and damage are different thresholds with different predictors.

| # | Contribution | Status of evidence | Evidence |
|---|---|---|---|
| C1 | **Measurement floor.** The per-decision divergence hazard has a floor set by near-ties on the bf16 logit grid. It is reached by anything from k=0.001 weight noise to kernel reduction order. The floor is predictable from the model's own margin histogram, and serving numerics alone move the canonical score by about ±8 pp (~1/4 of outcomes). | strong on q4/q8/q14; E8 (fp32 head) decides the mechanism | `docs/insights/iter_2_prep.md` A2-3/A2-6, `iter_1_verdicts.md` I4a |
| C2 | **Criterion.** Conformal perturbation-equivalence test (exchangeability with a null family), an admission rule for null members, and a TOST/ε statement with honest power (per-family margins of 6.5–13 pp at 85 tasks, so pool families or add tasks). | analysis running | `docs/insights/iter_2_conformal.md` (pending) |
| C3 | **Two thresholds.** Divergence is predicted by open-loop flip rate (ρ 0.98–0.99). Damage comes later (free zone equivalent when pooled; RTN-W3 −19 pp q4, −15 pp q14). Whether damage depends on error *structure* beyond size is tested with real formats. | q4/q8/q14 clean; q30a3/q32 running | `iter_2_prep.md`, `analysis/openloop/` |
| C4 | **Protocol.** Open-loop probe → conformal interval for closed-loop risk → run closed loop only when the interval straddles the tolerance. Plus a reporting checklist. | depends on C2/C3 across ≥5 models | — |

What would change the story:
- If the fp32 head removes the floor, C1 becomes "bf16 logit ties are the source of evaluation non-reproducibility" (stronger and more actionable).
- If real formats damage at a matched flip rate where noise does not, C3 gains the "structure matters" result.
- If the second family has no free zone, the scope narrows to Qwen3, which is still publishable with a stated limit.

## 2. Additions, ranked by value per engineering hour (all to finish by 10-05)
| id | What | Why (which reviewer attack) | Cost |
|---|---|---|---|
| X1 | **Real deployed formats:** official Qwen3 AWQ-INT4 (8B/14B/32B), official FP8 (4B-2507/8B/14B/30B-A3B-2507/32B; weight-only Marlin on Ampere), KV-cache FP8, bitsandbytes NF4. Each gets canonical + 2 nonces + a cross-node det pair, plus E3 open-loop. | "fake-quant is not what is deployed"; Replay Gap's per-format floor; I3 structure-vs-size | ~60 GPU-h; config + det pairs |
| X2 | **Second family:** Mistral-Small-3.2-24B (already downloaded; smoke-test tool competence first), optionally GLM-4-9B-0414 (MIT). Slice: bf16, 5 nonces, gauss k∈{0.03,0.3,1,3}, RTN W8/W4/W3, E3. | "only Qwen3" | ~80 GPU-h |
| X3 | **τ² telecom domain** (dual-control; the user also acts with tools) on q4/q8/q14 core slice | "85 tasks, 2 domains"; more tasks = more TOST power; a different loop structure | harness work (worktree) + ~60 GPU-h |
| X4 | Wanda unstructured pruning at 3 sparsities on q8 (a non-quantization compression family) | universality of the criterion beyond quantization | ~0.5 day code + 15 GPU-h; only if X1–X3 land |
| X5 | Sampling T=0.7 (q8: bf16 vs RTN-W4, 5 seeds each) | "greedy only" | ~10 GPU-h, config only |
Not doing: a no-simulator benchmark (BFCL multi-turn / AppWorld). The integration risk is too high for 10-05; it is listed under Limitations and planned for the follow-up (ICML) paper.

## 3. Statistics
- Conformal equivalence + ε-TOST (C2); null-member admission rule; hierarchical task-random-effects model as a robustness check.
- Floor prediction from logged margins, validated across models (already within 7% for q8/q14 from q4).
- Report power / MDE per family; pool across families and domains.
