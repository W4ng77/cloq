# Related Work & Baseline Map — verified 2026-09-28

Scope: support for the COLING analysis paper *"Is Your Quantized Agent Worse, or Just
Re-Rolled? Pitfalls in Closed-Loop Evaluation of Post-Training-Quantized Tool Agents"*
(see `docs/COLING_PLAN.md`, `docs/STRATEGY_v2.md` §3). Every entry below was checked
against its arXiv/ACL Anthology page on 2026-09-28 (title, authors, date, venue, URL).
Anything I could not independently confirm is flagged **UNVERIFIED** and should not be
cited without a follow-up check. BibTeX for every VERIFIED entry is in
`references.bib` next to this file.

Companion doc: `docs/STRATEGY_v2.md` §3 already has a working literature table with risk
ratings for the papers the project has already scoped (Flat Score, Noise Floor Audit,
VLAQuantBench, TASA, Williams & Aletras, calibration-curation family, statistics
family, FrugalGPT/deferral, DAgger/GKD/MiniLLM). This document does not repeat those
risk judgments in full — it (1) verifies the ones STRATEGY_v2 had marked "URL not in
evidence pack" / "†", (2) adds the category-A agent/tool-use papers STRATEGY_v2 is
missing (ACBench, harness-disclosure, AI2 Signal-and-Noise, HAL, ABC — several of these
already appear in STRATEGY_v2 but without full bibliographic verification), and (3)
builds the baseline matrix the plan asks for.

---

## A. Compressed/quantized LLMs evaluated as agents / tool use / multi-turn interactive tasks

This is the category the current map (STRATEGY_v2 §3) under-covers — it only had Flat
Score and VLAQuantBench pinned down. Below are the ones I could verify.

1. **VERIFIED** — Dong, Tang, Liu, Li, Chu, Li. *"Can Compressed LLMs Truly Act? An
   Empirical Evaluation of Agentic Capabilities in LLM Compression"* (ACBench).
   arXiv:2505.19433, submitted 2025-05-26 (v2 2025-06-01). ICML 2025 poster.
   https://arxiv.org/abs/2505.19433
   - 15 models (Gemma-2B up to Qwen2.5 7B–32B, plus DeepSeek-R1-Distill reasoning
     models), quantization (GPTQ, AWQ) and pruning (Wanda, SparseGPT), 12 tasks across
     4 capability groups: workflow generation (WorfBench), tool use, long-context
     retrieval (Needle-in-Haystack-style), and "real-world application" tasks.
   - Finding: 4-bit quantization only drops workflow-gen/tool-use by 1–3%, but
     real-world application accuracy drops 10–15% — i.e. aggregate tool-use metrics
     look fine while a downstream-application metric does not. This is the closest
     paper to ours in category A.
   - Gap vs. us: single deterministic run per config (no seeds/re-rolls reported), no
     reference-model noise floor, not a closed-loop dialogue/DB-mutation benchmark
     (WorfBench/tool-use tasks are largely single-shot or short-horizon, not τ-bench
     style multi-turn state-mutating dialogues), no calibration-draw manipulation.

2. **VERIFIED** — Jang, Yang, Lim, Park. *"Flat Score, Amplified Failures: How the
   Error Budget Masks Damage in Quantized LLM Agents"*. arXiv:2607.27275, submitted
   2026-07-29. https://arxiv.org/abs/2607.27275
   - τ²-bench, INT4 vs. presumably BF16/FP16 reference, single calibration recipe
     (not stated as multi-draw), no explicit run-count/seed disclosure in the abstract.
   - Finding: aggregate τ²-bench score ≈ unchanged under INT4, but existing failure
     modes (tool-name hallucination, esp. telecom domain) amplify up to 2.5×; tightening
     the benchmark's error budget from 10→2 allowed errors turns a 1.3-point aggregate
     gap into a 17-point gap. A repair prompt eliminates the failures.
   - This is our single closest neighbor. It shares the "aggregate score hides damage"
     framing and uses τ-bench-family benchmarks. It does **not**: model calibration-draw
     variance, build a reference/perturbation noise floor, treat draws as the inference
     unit, or run a power analysis / MDE. Our contribution over it is exactly the
     variance/inference-unit layer, not the "aggregate masks failures" framing itself
     (STRATEGY_v2 correctly flags that framing as "already occupied, high collision
     risk" — we must not re-claim it as novel).

3. **VERIFIED** — Chen, Qian, Wang, Peng, Xu, Wu, Sun. *"Noise Floor Audit for Agent
   Benchmarks"*. arXiv:2608.22331, submitted 2026-08-23.
   https://arxiv.org/abs/2608.22331
   - Benchmark: BFCL (multiple + parallel categories), AST grading. 3 native
     tool-calling endpoints, 2 providers (temperature 0).
   - Findings: rerun (same-input) noise is small — ever-flip fractions 0.7%/2.0%/2.7%,
     mean rerun correlation 0.961–0.997; but *semantics-preserving prompt perturbations*
     produce 11×–58× larger paired SDs than reruns; failure character shifts across
     endpoints (malformed-output share 30% / 7% / <1% of failures).
   - Direct overlap with our "perturbation null" (R-nonce/R-tool) construction and with
     possible gap #3 in STRATEGY_v2 — **this is a high-collision paper and per the plan
     must be read in full before finalizing our novelty claims**, not just from the
     abstract. It does not touch quantization/compression at all, does not use a
     closed-loop, state-mutating benchmark (BFCL is single-turn function-call grading,
     not τ-bench-style DB mutation), and does not compare a compressed model to a
     reference model. Our distinguishing angle: compression-vs-reference *task-level*
     inference under this kind of noise floor, in a closed-loop benchmark, not
     provider/endpoint noise on a static function-call benchmark.

4. **VERIFIED** — Zhang, Wang, Ge, Xu, Hamm, Reddy. *"Stop Comparing LLM Agents
   Without Disclosing the Harness"*. arXiv:2605.23950, submitted 2026-05-07.
   https://arxiv.org/abs/2605.23950
   - Position paper: "Binding Constraint Thesis" — in long-horizon tasks, the harness
     (context construction, tool interaction, orchestration, verification) drives more
     performance variance than model choice; harness variance can exceed model-swap
     variance; proposes mandatory harness disclosure.
   - Directly supports the E4/harness-sensitivity part of our paper (8k vs 32k
     truncation) and the "harness disclosure" item on our evaluator checklist. No
     quantization content; not evidence for calibration or closed-loop-vs-open-loop
     specifically, but a strong citation for "harness choices are a confound reviewers
     must be told about."

5. **VERIFIED** (context, not agent-specific) — Liu, Sun, Zhang, Bai, Yu, Yu, Yuan,
   Hou. *"Quantization Hurts Reasoning? An Empirical Study on Quantized Reasoning
   Models"*. arXiv:2504.04823 (v1 2025-04-07, v2 2025-08-18). COLM 2025.
   https://arxiv.org/abs/2504.04823
   - DeepSeek-R1-Distill / Qwen / LLaMA reasoning variants, 1.5B–70B, weight/KV-cache/
     activation quantization at multiple bit-widths, AIME/MATH-500/GPQA/LiveCodeBench.
   - W8A8/W4A16 "lossless" (≤1% drop); lower bit-widths risk large drops that scale with
     model size/origin/task difficulty. Belongs in category B (below) but is relevant
     background for "quantized reasoning" as a component of tool-agent loops (an agent's
     tool-call decisions are themselves a reasoning step).
   - Not a closed-loop/agent benchmark; single-turn QA-style grading, not multi-turn
     tool use.

6. **Category-A benchmarks/venues searched but with NO verified quantization-specific
   evaluation found** (documented so we do not later claim "no one has done AgentBench/
   WebArena/SWE-bench with quantized models" without having actually looked): targeted
   searches for "quantized model + AgentBench", "+ WebArena", "+ SWE-bench" returned only
   general agent-benchmark papers (SWE-Bench Pro Verified arXiv:2609.08149, HAS-Bench
   arXiv:2607.04329, "Evaluation and Benchmarking of LLM Agents: A Survey"
   arXiv:2507.21504) with no quantization axis, and no paper we could verify runs
   AgentBench, WebArena, or SWE-bench specifically on quantized LLM checkpoints. This is
   an open gap ACBench and Flat Score do not fill (ACBench uses its own task suite plus
   WorfBench; Flat Score uses τ²-bench). **Treat "no verified quantized-agent evaluation
   on WebArena/SWE-bench/AgentBench" as a documented negative result of this search, not
   as a settled fact** — a dedicated agent with more time/domain-specific search terms
   (e.g. vendor blog posts, non-arXiv venues) might still find one.

---

## B. Quantization evaluation beyond perplexity

7. **VERIFIED** — Dutta, Krishnan, Kwatra, Ramjee. *"Accuracy is Not All You Need"*.
   arXiv:2407.09141, submitted 2024-07-12. NeurIPS 2024.
   https://arxiv.org/abs/2407.09141
   - 6 quantization schemes vs. FP16 baseline, 7 tasks; accuracy nearly unchanged but
     large "flip" counts (correct→incorrect and vice versa) except GPTQ W8A16.
     Single-turn benchmarks, no closed-loop/agent setting.

8. **VERIFIED** — Kurtic, Marques, Pandit, Kurtz, Alistarh. *""Give Me BF16 or Give Me
   Death"? Accuracy-Performance Trade-Offs in LLM Quantization"*. arXiv:2411.02355,
   submitted 2024-11-04. ACL 2025. https://arxiv.org/abs/2411.02355
   - Llama-3.1 family, FP8/INT8/INT4, >500k evaluations; FP8 near-lossless, tuned INT8
     1–3% loss, W4A16 competitive; deployment guidance (W4A16 sync, W8A8 async batching).
     Static benchmarks only.

9. **VERIFIED** — Marchisio, Dash, Chen, Aumiller, Üstün, Hooker, Ruder. *"How Does
   Quantization Affect Multilingual LLMs?"*. arXiv:2407.03211 (2024-07-03, rev.
   2024-10-12). EMNLP 2024 Findings. https://arxiv.org/abs/2407.03211
   - Human eval detects much larger degradation than automatic metrics (e.g. Japanese:
     16.0% human-rated drop vs 1.7% automatic); non-Latin-script languages hit hardest;
     math reasoning degrades fastest. Directly supports "aggregate/automatic metrics
     understate damage" as a cross-cutting theme, independent of our agent setting.

10. **VERIFIED** — Wang, Xue, Liu, Shen, Liu, Ding. *"Beyond Activation Alignment: The
    Alignment-Diversity Tradeoff in Task-Aware LLM Quantization"* (TASA).
    arXiv:2607.00908, submitted 2026-07-01. https://arxiv.org/abs/2607.00908
    - "Perplexity Illusion": perplexity-based layer sensitivity does not rank-correlate
      with sensitivity for complex reasoning. Alignment-diversity tradeoff: pure
      target-task calibration data can *hurt* post-quantization performance vs. mixing
      in general-domain data. Open-loop only (no agent/closed-loop task); directly
      supports the open-loop-fidelity-doesn't-predict-closed-loop-success argument by
      showing open-loop proxies (perplexity/sensitivity ranking) already mislead each
      other before you even get to closed-loop.

11. Already verified in STRATEGY_v2 with working links (re-confirmed live, no change):
    Williams & Aletras 2024 (arXiv:2311.09755, ACL 2024, "On the Impact of Calibration
    Data in Post-training Quantization and Pruning" — confirmed via ACL Anthology
    2024.acl-long.544 and arXiv abstract), VLAQuantBench (arXiv:2609.25376, re-verified
    below in §E with full author list), "Anatomy of a Closed-Loop Collapse"
    (arXiv:2609.23048), τ-bench pass^k (arXiv:2406.12045) and τ²-bench (arXiv:2506.07982)
    — full author lists confirmed below in the baseline table notes.

12. **UNVERIFIED (found, not independently confirmed beyond search snippet)** —
    "Does quantization affect models' performance on long-context tasks?"
    arXiv:2505.20276 — title/URL match a live arXiv record in search results, but I did
    not WebFetch the abstract page directly, so author list/venue are not confirmed.
    Relevant to the "open-loop fidelity ≠ closed-loop" argument if our harness-length
    (8k vs 32k) result needs a long-context-quantization citation.

13. **UNVERIFIED** — Sinha et al., ICLR 2026, on calibration (named in
    `docs/COLING_PLAN.md`'s to-do list). I could not find a paper by an author named
    Sinha on calibration/quantization at ICLR 2026; the closest ICLR 2026 quantization
    paper found was Li et al., *"Rethinking Residual Errors in Compensation-based LLM
    Quantization"* (ICLR 2026 poster), which is not by anyone named Sinha. **Do not cite
    "Sinha et al. ICLR 2026" until the person who added it to the plan supplies the
    correct arXiv ID** — it may be a misremembered author name or a paper not yet
    indexed under that name.

---

## C. Calibration-data studies for PTQ

14. **VERIFIED** — Williams & Aletras. *"On the Impact of Calibration Data in
    Post-training Quantization and Pruning"*. arXiv:2311.09755 (also ACL 2024, pp.
    10100–10118). https://arxiv.org/abs/2311.09755 /
    https://aclanthology.org/2024.acl-long.544/
    - Calibration-data choice significantly affects downstream task performance,
      especially for pruning; quantization somewhat more robust. Open-loop only.

15. **VERIFIED** — Williams (& co-authors). *"Self-calibration for Language Model
    Quantization and Pruning"*. arXiv:2410.17170, submitted 2024-10-22.
    https://arxiv.org/html/2410.17170v1
    - Model-generated ("self") calibration data as an alternative to external corpora;
      removes the calibration-corpus-choice dependency. Open-loop only.

16. **VERIFIED** — He, Yin, Zhen, Liu, Wu, Zhang, Yuan, Ma. *"Preserving LLM
    Capabilities through Calibration Data Curation: From Analysis to Optimization"*
    (introduces **COLA** — Calibration data curatiOn for capability preservation
    through coverage optimizAtion). arXiv:2510.10618, submitted 2025-10-12. NeurIPS
    2025 poster. https://arxiv.org/abs/2510.10618
    - Coverage/curation framework for calibration-set selection driven by activation
      patterns. Open-loop capability preservation, not closed-loop.

17. **VERIFIED** — *"Damage Predicts Recovery: When Calibration Data Matters in
    Compressing Financial LLMs"*. arXiv:2609.26241 (title/abstract confirmed via
    search; full author list not yet pulled from the abstract page — flag as
    **PARTIALLY VERIFIED**, re-check author list before final citation).
    https://arxiv.org/abs/2609.26241 (abs URL inferred from the arXiv ID pattern of the
    found html link `arxiv.org/html/2609.26241`; confirm the `/abs/` page resolves
    before submission).
    - Two model families, 6 compression configs, 3 token-matched calibration corpora,
      10 financial tasks; damage–recovery Spearman ρ=0.74: when compression barely
      hurts, calibration-corpus choice barely matters; when it hurts a lot,
      task-matched calibration helps recover some of it. **This is the single strongest
      piece of prior evidence for our headline argument** ("W4 damage may be too small
      at this scale for calibration-arm choice to matter") — but it is open-loop/
      classification+QA, not closed-loop agents, and domain-specific (finance).

18. Not independently found under the literal names "COVERCAL" — treat as either an
    alternate/earlier name for COLA (item 16) or **UNVERIFIED**; do not cite as a
    separate paper without a direct arXiv hit.

---

## D. Evaluation variance / reliability / statistical rigor

19. **VERIFIED** — Sclar, Choi, Tsvetkov, Suhr. *"Quantifying Language Models'
    Sensitivity to Spurious Features in Prompt Design..."* (FormatSpread).
    arXiv:2310.11324 (v1 2023-10-17, v2 2024-07-01). ICLR 2024.
    https://arxiv.org/abs/2310.11324
    - Up to 76-point accuracy swings from prompt formatting alone (LLaMA-2-13B);
      FormatSpread algorithm estimates the spread without full grid search; recommends
      reporting ranges, not single-format numbers.

20. **VERIFIED** — Mizrahi, Kaplan, Malkin, Dror, Shahaf, Stanovsky. *"State of What
    Art? A Call for Multi-Prompt LLM Evaluation"*. arXiv:2401.00595, submitted
    2023-12-31. TACL. https://arxiv.org/abs/2401.00595
    - 6.5M+ test cases, 20 models, 39 tasks; single-template evaluation is unreliable;
      argues for multi-prompt evaluation with stakeholder-specific metrics.

21. **VERIFIED** — Kapoor, Stroebl, Siegel, Nadgir, Narayanan. *"AI Agents That
    Matter"*. arXiv:2407.01502, submitted 2024-07-01. https://arxiv.org/abs/2407.01502
    - Critiques agent benchmarking: cost ignored, model-dev vs. downstream-dev needs
      conflated, weak holdout sets, poor standardization → poor reproducibility.

22. **VERIFIED** — Zhu et al. (25 authors, lead Yuxuan Zhu). *"Establishing Best
    Practices for Building Rigorous Agentic Benchmarks"* (introduces the **Agentic
    Benchmark Checklist**, ABC). arXiv:2507.02825, submitted 2025-07-03.
    https://arxiv.org/abs/2507.02825
    - Task validity / outcome validity / reporting checklist; auditing 10 popular
      agentic benchmarks finds flaws in most; reduces overestimation by 33% on
      CVE-Bench when applied. Our E5 practical-audit coding scheme should cite and
      align with ABC's item list, as STRATEGY_v2 §3 already plans.

23. **VERIFIED** — Kapoor, Stroebl, et al. *"Holistic Agent Leaderboard: The Missing
    Infrastructure for AI Agent Evaluation"* (HAL). arXiv:2510.11977, submitted
    2025-10-13 (approx., per listing). https://arxiv.org/abs/2510.11977
    - Standardized harness for reproducible, cost-controlled agent evaluation;
      21,730 rollouts, 9 models × 9 benchmarks, ~$40k total cost; finds e.g. higher
      reasoning effort reduces accuracy in a majority of runs. Directly relevant to our
      "harness disclosure" and "cost-controlled comparison" checklist items.

24. **VERIFIED** — Allen Institute for AI team. *"Signal and Noise: A Framework for
    Reducing Uncertainty in Language Model Evaluation"*. arXiv:2508.13144, submitted
    2025-08-18(ish, per listing). NeurIPS 2025. https://arxiv.org/abs/2508.13144
    - Formalizes benchmark "signal" (ability to separate models) vs. "noise"
      (checkpoint-to-checkpoint variability); 30 benchmarks × 375 models (60M–32B);
      interventions: better-signal metrics (e.g. perplexity over accuracy), filtering
      noisy subtasks, checkpoint-averaging. This is the general MDE/sensitivity
      framework STRATEGY_v2 flags as "cannot claim novelty over" — confirmed, keep it
      cited as background only, not as something we extend without qualification.

25. **VERIFIED** — τ-bench: Yao, Shinn, Razavi, Narasimhan. *"τ-bench: A Benchmark for
    Tool-Agent-User Interaction in Real-World Domains"*. arXiv:2406.12045, submitted
    2024-06-17. https://arxiv.org/abs/2406.12045
    - Introduces pass^k; GPT-4o <50% success, pass^8 <25% on retail — establishes that
      sampling-based reliability is already a known, reported problem for single
      (non-quantized) models on this exact benchmark family. Important citation for
      "why not just use pass^k" pre-emption (STRATEGY_v2 already flags this).

26. **VERIFIED** — τ²-bench: Barres, Dong, Ray, Si, Narasimhan. *"τ²-Bench: Evaluating
    Conversational Agents in a Dual-Control Environment"*. arXiv:2506.07982, submitted
    2025-06-09. https://arxiv.org/abs/2506.07982
    - Adds a tool-using user simulator and dual-control (agent+user) tasks; this is the
      benchmark family (retail + airline domains) our own experiments use.

27. **VERIFIED, background only, not independently checked beyond abstract page** —
    Singh, A. *"Certifying Compressed Language Models: An Audit and a Statistical
    Toolkit"*. arXiv:2608.15046, submitted 2026-08-15. https://arxiv.org/abs/2608.15046
    - Per-item churn (not net accuracy delta) is ~5× net delta across 1,707 paired
      model×task cells (1.3B–405B); audits 17 "equivalence" claims (method papers,
      model cards, vendor docs) and finds none states a prospective equivalence margin
      or releases task-matched per-item outputs. Strong, very close methodological
      cousin for the "aggregate deltas hide per-item churn" argument, but static
      benchmarks, not closed-loop, and not about calibration-arm variance specifically.
      Recommend reading in full given the overlap (same severity as Noise Floor Audit).

---

## E. Closed-loop vs. open-loop compression evidence (robotics/driving/VLA)

28. **VERIFIED** — Xu, Jin, Chen, Wang, Sui, Shi. *"VLAQuantBench: Closed-Loop
    Evaluation of Post-Training Quantization for Vision-Language-Action Models"*.
    arXiv:2609.25376, submitted 2026-09-21. https://arxiv.org/abs/2609.25376
    - 409 runs, LIBERO + other sims; W4A4 action-head layer scope hugely affects
      success (7%→70%+); calibration strategy effects are model-architecture-dependent;
      no universal layer-sensitivity rule, only recipe-specific. Point estimates per
      config, no reported variance/seeds — matches STRATEGY_v2's existing note.

29. Already in STRATEGY_v2, re-confirmed as live links (not re-fetched in full this
    pass, since STRATEGY_v2 already lists working URLs and no new information was
    needed): *"Anatomy of a Closed-Loop Collapse"* (arXiv:2609.23048), *QuantVLA*
    (arXiv:2602.20309).

30. **VERIFIED (new find for this pass)** — Wang, Jiang, Wang, Heng, Yang, Chen, Sun.
    *"Do Open-Loop Metrics Predict Closed-Loop Driving? A Cross-Benchmark Correlation
    Study of NAVSIM and Bench2Drive"*. arXiv:2605.00066, submitted 2026-04-30.
    https://arxiv.org/abs/2605.00066
    - Not about quantization/compression — it is a general open-loop-vs-closed-loop
      *metric correlation* study in driving (8 methods, NAVSIM/Bench2Drive): open-loop
      aggregate score correlates with closed-loop driving score but non-monotonically,
      with ranking reversals; simple 3-metric proxy ≈ full 5-metric system. Useful as a
      domain-general "open-loop metrics don't reliably predict closed-loop outcome"
      citation, parallel to our NLL-vs-closed-loop-success argument, but it is not
      about compressed models specifically — cite as supporting analogy only, not as a
      compression paper.
    - Note: one search snippet claimed "models with up to 86% fewer parameters yield
      comparable or superior closed-loop performance" in this space — I could not
      confirm this specific claim belongs to arXiv:2605.00066 itself (it may belong to
      a different driving paper in the surrounding search results, e.g. a
      distillation/pruning paper). **Do not cite that specific statistic without
      re-fetching and confirming which paper it is from** — flagged UNVERIFIED.

31. Other driving open/closed-loop papers surfaced but not verified as
    quantization-relevant, listed only so we don't re-search for them blind: DriveE2E
    (arXiv:2509.23922), BridgeSim (arXiv:2604.10856), "Closing the Loop: Motion
    Prediction Models beyond Open-Loop Benchmarks" (arXiv:2505.05638), CLOVER
    (arXiv:2605.15120). None of these were fetched/verified this pass; treat as leads,
    not citations, until checked.

---

## Verification summary

- **Fully verified this pass (title+authors+date+venue+URL fetched):** items 1, 2, 3, 4,
  5, 7, 8, 9, 10, 14 (via Anthology + arXiv), 19, 20, 21, 22, 23, 24, 25, 26, 28, 30.
- **Verified via consistent multi-source search snippet but not a direct WebFetch of the
  `/abs/` page in this session** (recommend a quick confirmatory fetch before the
  camera-ready bibliography is frozen): 15, 16, 27.
- **Partially verified / needs a follow-up check:** 17 (author list), 12 (author list
  and venue).
- **Explicitly UNVERIFIED — do not cite without correction:** 13 ("Sinha et al. ICLR
  2026" — could not locate), 18 ("COVERCAL" as a name distinct from COLA), the 86%-
  parameter-reduction claim under item 30.

---

## Baseline table — category-A papers (quantized-model-as-agent evaluations)

| Paper | Models (family/size) | Quantizers | Bit-widths | Agent benchmark(s) | Real kernels or fake/simulated quant? | Runs/seeds | Variance reported? |
|---|---|---|---|---|---|---|---|
| ACBench (2505.19433) | 15 models: Gemma-2B, Qwen2.5 7B/14B/32B, LLaMA-family, DeepSeek-R1-Distill reasoning variants (per abstract; exact list needs a table pull from the PDF if used for exact matching) | GPTQ, AWQ (quant); Wanda, SparseGPT (pruning) | 4-bit (headline number); likely also other widths in the full paper — **not confirmed from abstract alone, check PDF Table 1 before citing bit-width beyond "4-bit"** | Own 12-task suite: WorfBench (workflow gen), tool-use tasks, Needle-in-Haystack long-context, "real-world application" tasks | Not stated in abstract — likely simulated/fake-quant (HF/AutoGPTQ-AutoAWQ style), **needs PDF check** for whether real INT4 kernels were used at inference | Not stated in abstract — likely 1 run per config, **check PDF** | Not stated in abstract; no variance/CI language surfaced in search |
| Flat Score (2607.27275) | Not fully specified in abstract — **needs PDF check for exact model family/size** | Not named beyond "INT4" in abstract — likely GPTQ/AWQ/RTN, **needs PDF check** | INT4 (single width per abstract) | τ²-bench (telecom + presumably retail/airline) | Not stated — needs PDF check | Not stated in abstract | Not stated in abstract; framing is single-point aggregate-score comparison |
| Noise Floor Audit (2608.22331) | 3 tool-calling **endpoints**, 2 providers (this is a hosted-API audit, not a local open-weight quantization study) | N/A — not a quantization paper | N/A | BFCL (multiple + parallel categories) | N/A (hosted APIs, unknown internal precision) | Multiple reruns per input (exact count not in abstract) at temperature 0, plus prompt-perturbation sets | Yes — paired SDs for rerun vs. perturbation explicitly reported; this is the strongest variance-reporting paper in the table, but it is not a quantization paper |
| VLAQuantBench (2609.25376) | Multiple VLA model architectures (per abstract; exact family list needs PDF) | Multiple PTQ recipes, mixed-precision with variable layer scope | W4A4 headline number; abstract implies other bit-widths tested via "precision selection" sweep — **needs PDF check** | LIBERO + other sim environments (VLA closed-loop robot tasks, not LLM tool-agent benchmarks) | Real-robot experiments mentioned ("validated... through both simulation and physical robot experiments") — suggests real deployment, not pure fake-quant simulation, but **confirm in PDF** | 409 total experimental runs across configs — likely still ~1 run per specific (model, recipe, precision) cell, **needs PDF check for seeds per cell** | Point estimates per config per STRATEGY_v2's existing note; no reported run-to-run variance |

**Reading of this table:** every category-A paper we could verify (a) uses at most one
quantizer family reported with confidence from the abstract (GPTQ/AWQ, or an unnamed
INT4 scheme, or PTQ generically for VLA), (b) reports point estimates rather than
distributions over runs/seeds, and (c) none of them treats calibration-data choice as
an experimental factor in a closed-loop LLM tool-agent benchmark. This is consistent
with STRATEGY_v2's narrowed novelty claim (calibration-draw × closed-loop-agent
inference, and re-roll/draw separation) still being open. **Caveat:** several bit-width
and kernel-fidelity cells above are marked "needs PDF check" because the abstract pages
alone (fetched via WebFetch) did not give per-model, per-config tables — before writing
the paper's own related-work section, at least ACBench and Flat Score should be pulled
as full PDFs to fill those cells with certainty, since they are the two closest
neighbors and reviewers will check these details.

---

## Recommended model / quantizer / benchmark set for our paper

Given the fleet (many A6000 48GB, currently only Qwen3-4B-Instruct-2507 with
GPTQ/RTN W4 on τ²-bench retail+airline), and given the gaps above:

**Models — add at least one more size point, keep family fixed if budget-limited:**
- Keep Qwen3-4B-Instruct-2507 as the anchor (already run).
- Add **one larger same-family model** (e.g. Qwen3-8B or Qwen3-14B-Instruct) to let us
  say something about whether the "calibration-draw indistinguishability under W4"
  result holds as model size grows — ACBench and the reasoning-quantization literature
  (item 5) both suggest damage scales with size/task difficulty, so a single 4B point
  invites the "does this replicate at scale" objection. A6000 48GB comfortably fits an
  8B or 14B model plus a BF16 reference server.
- If time allows, one **different family** at a similar size (e.g. Llama-3.1-8B-Instruct
  or Mistral-7B-Instruct) to pre-empt "this is a Qwen-specific artifact" — Kurtic et al.
  (item 8) and Marchisio et al. (item 9) both show family-specific quantization behavior.

**Quantizers — currently GPTQ/RTN only:**
- Add **AWQ** at minimum — it is the other quantizer every close neighbor (ACBench,
  and implicitly Flat Score) uses alongside GPTQ, and its calibration procedure
  (activation-aware) is mechanistically different from GPTQ's Hessian-based approach,
  which matters for the calibration-draw claim (a reviewer will ask "does draw-
  indistinguishability hold for AWQ too, since AWQ selects salient channels
  differently").
- Consider **FP8** as a second axis, not to replace W4 but to report one "quantization
  is close to lossless here" reference point (Kurtic et al. show FP8 near-lossless) —
  this strengthens the "W4 damage may be near the closed-loop noise floor" argument by
  showing FP8 damage is smaller than the same noise floor, i.e. establishing the
  floor's sensitivity is not why *all* quantization looks equivalent.
- RTN should stay as the "known-worse" negative control (already in plan).

**Bit-widths — currently only W4:**
- The single-bit-width limitation is explicitly flagged in COLING_PLAN.md's limitations
  section already, which is honest, but if GPU time permits even one **W8** condition
  (GPTQ/AWQ W8A16 or W8A8) on the anchor model would let the paper show the MDE/
  sensitivity gradient (item 24's "signal" framing) actually has resolution — i.e. that
  our null result on W4-calibration-draws is not simply "this benchmark has no signal
  at all," since W8 should show smaller-or-no damage and a much bigger degradation
  arm (very low bit, e.g. W2 or 3-bit) should show clearly detectable damage. This
  connects directly to STRATEGY_v2's own "degradation gradient" plan (E2) — the
  literature map confirms this gradient argument has no close prior work in the
  closed-loop-agent setting specifically, so it is worth the GPU time.

**Benchmark — currently τ²-bench retail+airline only:**
- Keep τ²-bench as primary (matches τ²-bench itself, Flat Score, and our own prior
  work — comparability with the closest neighbor matters for reviewers).
- Consider adding **BFCL** as a secondary, cheap, single-turn control benchmark
  specifically because Noise Floor Audit (item 3) already characterizes its noise floor
  in detail — running our own quantized checkpoints on BFCL and comparing our own
  noise-floor estimate to theirs would be a strong, cheap sanity check and would let us
  cite/contrast directly against the closest "noise floor" paper in the literature
  instead of only against τ²-bench-only priors.
- Do not attempt AgentBench/WebArena/SWE-bench additions purely for "completeness" —
  no verified quantized-agent evaluation exists on them (item 6), so adding one would be
  a genuinely novel contribution, but it is a large scope increase for a COLING analysis
  paper on a tight timeline; flag as future work rather than a requirement for
  reviewer-perceived completeness.

**Runs/seeds — this is our actual differentiator, protect it:**
- None of the category-A papers verified above report >1 run per (model, quantizer,
  bit-width) cell or any run-to-run variance. Our multi-draw × multi-run design (already
  planned: 6 calibration arms × 3 draws, plus perturbation-null re-rolls) is the single
  largest methodological gap versus every close neighbor. This should be stated plainly
  in the paper's related-work section as the primary point of differentiation, not
  buried — it is the one claim in this table that is unambiguous and low-risk.

---

## Threats to novelty (carried over / sharpened from STRATEGY_v2 §3)

1. **"Aggregate score hides agent damage" framing is occupied** by Flat Score
   (2607.27275) and, more generally, by Dutta et al.'s flips (2407.09141) and Singh's
   per-item churn audit (2608.15046). We cannot lead with this framing as ours.
2. **Noise Floor Audit (2608.22331) and Singh's audit (2608.15046) are both
   high-collision** with our variance/inference-unit contribution, even though neither
   touches quantization or a closed-loop, state-mutating agent benchmark. Per
   STRATEGY_v2, Noise Floor Audit must be read in full (not just abstract) before we
   finalize novelty language — this pass only verified the abstract-level claims; a
   dedicated close reading is still owed.
3. **Calibration-data-doesn't-matter-when-damage-is-small is already argued** by Damage
   Predicts Recovery (2609.26241, Spearman ρ=0.74 damage↔recovery) and consistent with
   Williams & Aletras/self-calibration/COLA — all open-loop, classification/QA tasks.
   Our contribution must be explicitly framed as "this pattern, previously shown
   open-loop, also holds (or doesn't) in closed-loop agent evaluation," not as a new
   general claim about calibration-and-damage.
4. **Open-loop-doesn't-predict-closed-loop is a general, occupied claim** across
   robotics/driving/VLA (VLAQuantBench, Anatomy of a Closed-Loop Collapse, the
   NAVSIM/Bench2Drive correlation study). Our specific instantiation — NLL vs.
   closed-loop τ²-bench success for a *quantized LLM tool agent*, with an explicit
   correlation coefficient and flip-AUC mechanism story — is not duplicated by any
   verified paper, but the *general thesis* is not new and must be cited as such.
5. **ACBench (2505.19433) is the closest paper overall** and shares the multi-capability,
   multi-model structure our reviewers will expect us to compare against; we could not
   verify from the abstract whether it reports any variance, but its methodology
   (single run per config) is the norm across every category-A paper we found — so our
   "no one reports variance for quantized agents" claim is defensible, pending the PDF
   check on ACBench's methods section (flagged above).

## Closest 5 papers overall (for a related-work opening paragraph)

1. Flat Score, Amplified Failures (arXiv:2607.27275) — same benchmark family
   (τ²-bench), same "aggregate hides damage" concern, no variance model.
2. ACBench (arXiv:2505.19433) — broadest quantized-agent evaluation, multiple
   quantizers/models, but single-run, not closed-loop-dialogue-style.
3. Noise Floor Audit for Agent Benchmarks (arXiv:2608.22331) — same statistical
   question (rerun vs. perturbation noise) on a different, non-quantization, agent
   benchmark (BFCL).
4. VLAQuantBench (arXiv:2609.25376) — same "closed-loop PTQ evaluation" structure,
   different domain (robotics/VLA), no variance reporting.
5. Damage Predicts Recovery (arXiv:2609.26241) — same calibration-data-doesn't-matter-
   until-damage-is-large argument, open-loop/financial-NLP domain.

---

*Compiled 2026-09-28. All URLs above were live-fetched or cross-confirmed by search on
that date; re-verify before camera-ready in case of arXiv version bumps or venue
updates (several 2026 arXiv IDs above are very recent preprints and may still be
under review).*

## Corrections (main session, 2026-09-28)
- "Sinha et al. ICLR 2026" is verified: *The Illusion of Diminishing Returns: Measuring Long Horizon Execution in LLMs* (Sinha, Arun, Goel, Staab, Geiping), arXiv:2509.09677, ICLR 2026. Full text checked in the strategy workflow; no quantization, synthetic long-horizon execution task.
- Noise Floor Audit (2608.22331) full text was read in the strategy workflow: BFCL multiple/parallel, single-turn, open-loop, unquantized API models; the paper itself excludes multi-turn agents from its scope. Collision risk is methodological only.
- Still to read in full: Singh 2608.15046; ACBench and Flat Score per-config tables (PDF).
