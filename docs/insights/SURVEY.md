# SURVEY — living literature map for the CLOQ COLING paper

Paper: *Perturbation Equivalence in Closed-Loop Agents: When Is a Compressed Agent Actually Worse?* (`docs/COLING_PLAN.md`).
Base map: `analysis/coling/RELATED_WORK.md` (26 verified entries, 2026-09-28). This file adds recent work and answers novelty questions.
Status 2026-09-28 (baseline sweep, parallel with iteration 1): **partial**. Entries marked [V-abs] had their arXiv abs/html page opened this pass;
[V-map] were verified in RELATED_WORK.md; [UNVERIFIED] = search snippet only. Three topic sweeps (margins/flips/nondeterminism; equivalence
and null baselines; compressed-agent 2025–26) were launched but had not returned when this pass closed. Their results still need to be merged.

## Literature map (by theme, newest first)

### 1. Compressed/quantized LLMs as agents
- **Flat Score, Amplified Failures**: Jang, Yang, Lim, Park, arXiv:2607.27275 (2026-07) [V-abs, full html read]. https://arxiv.org/abs/2607.27275
  Claims: on τ²-bench retail and telecom (114 tasks each; 4 trials/task, seed 300, agent T=0, user T=0.7), AWQ INT4 and FP8 (real Marlin kernels,
  A100) on Gemma-4 31B/26B-A4B and Qwen-3.6 27B/35B-A3B, Qwen-3.5 27B/9B leave the aggregate score unchanged. No cell survives multiple-comparison
  correction. Tool-name hallucination grows 2.5× (19.5%→38.3%, Gemma-4 telecom). BF16 vs INT4 failure distributions correlate at rank 0.97,
  and only 0.18% of INT4 events are new. One repeat run gives a ~1.5-pt variance baseline. The paper gives a **verbal logit-margin account**
  (m′ = m + η; quantization flips thin-margin argmax decisions). It does not measure logits, trajectory divergence, saturation, a
  perturbation null, or cross-model prediction.
  Relation: **competes** on framing and on the margin intuition. **We extend** it: we measure margins, give a quantitative flip/divergence
  model, add the perturbation null, and test cross-model prediction.
- **ACBench**: Dong et al., arXiv:2505.19433, ICML 2025 [V-abs, html read]. 15 models ≤8B; GPTQ/AWQ/SmoothQuant at 4/8-bit; SparseGPT/Wanda.
  Tool use drops 1–3% and real-world applications (AgentBoard) drop 10–15%. The paper also uses ERank, top-k ranking correlation (unstable as
  k→3) and an energy (logit-confidence) analysis. Everything is at T=0 with one run and no variance.
  Relation: competes/baseline. Its top-k/energy analyses are single-step logit diagnostics, not a divergence model.
- VLAQuantBench 2609.25376; Anatomy of a Closed-Loop Collapse 2609.23048; QuantVLA 2602.20309; Quantization Hurts Reasoning 2504.04823 [V-map].

### 2. Numerical perturbation → output divergence; margin-predicted flips
- **The Integer Alibi**: T.-R. Chen, arXiv:2608.13756 (2026-08) [V-abs]. https://arxiv.org/abs/2608.13756
  Claims: two INT8 GEMM kernels in vLLM (CUTLASS vs Triton) are each deterministic, yet they produce completely different sequences on
  1.7B and 8B models. Teacher-forced replay shows that flips concentrate at small logit margins. Margin predicts flip risk with **ROC-AUC 0.94
  over 16,384 positions**, and the flip rate falls from 34% in the lowest-margin decile to 0 above margin ≈9.
  Relation: **supports**. It is the closest prior for the per-step P(flip) ≈ P(m < δ). It is single-step and open-loop, with one perturbation type.
- **The Illusion of Equivalence**: Chodavarapu, Xu, arXiv:2604.15409 (2026-04) [V-abs]. https://arxiv.org/abs/2604.15409
  Claims: cache-ON vs cache-OFF FP16 inference diverges on 100% of sequences (LLaMA-2-7B, Mistral-7B, Gemma-2-2B, GSM8K). FP32 removes it.
  Accuracy differs systematically (cache-ON is higher in 8/9 conditions).
  Relation: **supports P1** in spirit: a tiny numerical δ already saturates sequence divergence. It is single-turn, and there is no margin model.
- **Grounded Scaling**: Ding, Wang, arXiv:2606.22495 (2026-06) [V-abs]. Position paper. k-step chain success decays as δ^k with per-step
  determinism δ<1. Relation: a loose analogue of our product formula. It is about environment determinism, not model perturbation.

### 3. Perturbation baselines / nulls and equivalence
- **Compared to What? Baselines and Metrics for Counterfactual Prompting**: Yang, Levy, Goldberg, Wallace, arXiv:2605.01048, COLM 2026
  [V-abs]. https://arxiv.org/abs/2605.01048
  Claims: counterfactual effects must be judged against meaning-preserving (paraphrase) modifications. Gender swaps flip 14.9% of MedQA
  predictions and paraphrase alone flips 14.1%, which is indistinguishable.
  Relation: **closest methodological precedent for the perturbation-equivalence criterion** (neutral-perturbation null), applied to
  input counterfactuals in single-turn QA. We apply it to model compression in closed-loop agents, with a success-level TOST.
- **Certifying Compressed Language Models**: Singh, arXiv:2608.15046 (2026-08) [V-abs, html read]. The paper proposes paired TOST at a
  **declared, fixed margin** (e.g. ±2 pp), with churn reported next to net delta (churn ≈5.4× net delta; 1,707 cells). It audits 16–17
  equivalence claims and finds that none declares a margin. The benchmarks are static (MMLU, GSM8K, …), and multi-turn/agent benchmarks are
  excluded. Its null is "true diff = 0 within declared margin", **not** the reference model's own perturbation distribution.
  Relation: competes on the "equivalence testing for compression" layer. We differ by deriving the margin/null from 𝒫_M in closed-loop tasks.
- **AgentDiff**: Zhang, Guo, arXiv:2605.25981 (2026-05) [V-abs]. Ten models, about 11,150 variants. Meaning-bearing rewrites cause +19.69 pp
  more inconsistency than presentation changes. First actions are preserved while later steps diverge ("stealth divergence"). There are no
  weight perturbations. Relation: supports the view that prompt perturbations re-roll agent trajectories. Its step-wise divergence measure is
  close to our divergence-vs-t.
- Noise Floor Audit 2608.22331 (prompt perturbation SD 11–58× the rerun SD; BFCL, single-turn); Signal and Noise 2508.13144; FormatSpread;
  multi-prompt eval; τ-bench pass^k [V-map].

### 4. Churn / flips with flat accuracy
- Accuracy is Not All You Need (Dutta et al. 2407.09141); Singh 2608.15046 (see §3); Flat Score (see §1) [V-map/V-abs].

### 5. Long-horizon compounding / multi-turn
- Sinha et al., *Illusion of Diminishing Returns*, 2509.09677 (ICLR 2026) [V-map]. Grounded Scaling (see §2). Anchors DAgger and exposure bias
  still need adding (the sweep is pending).

## Answers for iteration 1 (framing)

**Criterion (perturbation equivalence).** Closest prior work: *Compared to What?* (2605.01048). It uses a paraphrase null to judge counterfactual
flip effects. Singh (2608.15046) uses TOST for compressed LMs with a declared fixed margin. Noise Floor Audit (2608.22331) reports perturbation
SDs as a floor but does not use them to judge a model change. Flat Score has a single ~1.5-pt repeat-run baseline.
→ **(b) sharper/more general.** The "neutral-perturbation null" idea exists for input counterfactuals, and TOST exists for compression. The new
part is combining them: the equivalence margin comes from the reference model's own perturbation distribution, and the test is task-level and
paired on a closed-loop, state-mutating agent benchmark. We must cite all three and not claim the null idea itself.

**P1 (divergence saturates quickly with δ).** Closest prior work: Illusion of Equivalence (2604.15409), where FP16 accumulation order alone
diverges 100% of sequences, and Integer Alibi (2608.13756), where cross-kernel INT8 differences produce completely different sequences.
AgentDiff shows step-wise divergence under prompt rewrites. None of them measures a divergence-vs-δ curve, and none puts nonce, Gaussian
noise and RTN/GPTQ/AWQ on one axis in closed-loop agents.
→ **(b)**. "Tiny perturbations re-roll long generations" is known single-turn. Our addition is the saturation curve across perturbation
families in multi-turn agents. Risk: reviewers may call saturation obvious given these papers, so the emphasis should be on *where* it
saturates relative to P2.

**P2 (damage threshold later than divergence saturation, the "free compression zone").** Closest prior work: Flat Score (aggregate flat while
failures amplify), Dutta (flips with flat accuracy), Singh (churn 5.4× net delta), and Compared to What (flip rate equal to the paraphrase
null). All of these are consistent with divergence ≫ damage at a single perturbation size. None measures two thresholds along a δ sweep.
→ **(a)/(b)**: the two-threshold, dose-response statement appears to be new. Flat Score's amplified-failures result is the main counterpoint:
P2 must be shown at the success level *and* checked against failure-mode counts, or Flat Score's reviewers will object.

**P3 (cross-model divergence predictable from BF16 margins).** Closest prior work: Integer Alibi (margin → flip, AUC 0.94, single-step, one
perturbation) and Flat Score (verbal m′ = m + η account, no measurement). ACBench's energy/top-k analyses are descriptive.
→ **(b)**. The per-step margin→flip link is empirically established. The new parts are (i) composing it over closed-loop decision points
into P(diverged by t), (ii) predicting *across models* from BF16 margins alone, and (iii) one δ scale shared by prompt, noise and quantization
perturbations. Cite Integer Alibi as validating the per-step assumption. Flat Score is the direct precedent for the mechanism claim, so we
must present ours as its quantitative test.

## Ideas from recent work
1. **Integer Alibi (2608.13756)**: reproduce its margin-decile flip curve for our W4/nonce/Gaussian perturbations under teacher forcing on BF16
   τ² trajectories, and report the AUC. If each perturbation family has its own δ, the decile curves should collapse after rescaling by δ.
   This also calibrates δ per condition for P1/P3. (Matches `analysis/insights/iter_1/s01_token_flip_margin.py`.)
2. **Flat Score (2607.27275)**: test their "amplifies existing failures" claim against our null. Is the INT4 failure-mode mix inside the
   BF16-nonce null's failure-mode distribution? If it is, their amplification may partly be re-roll rather than damage.
3. **AgentDiff (2605.25981)**: report first-divergence step and whether the first action is preserved, per perturbation family. Prediction
   from the margin model: the first divergence lands on the lowest-margin decision point, whatever the family.
4. **Compared to What? (2605.01048)**: add a flip-rate-equivalence table in their format: task-level outcome-flip rate of each compressed
   config vs the nonce-null flip rate. This is cheap and directly comparable.
5. **Illusion of Equivalence (2604.15409)**: disclose the serving numerics (KV cache, batch invariance). A kernel-level δ is itself a point
   on the P1 curve and can be used as the smallest-δ condition.

## Open questions for survey
- Merge the pending sweeps: nondeterminism (FP32 reproducible reasoning, batch-invariance), forking/critical tokens, model-equality testing
  and quantized-substitution auditing, agent-eval variance 2025–26, multi-turn degradation (Lost in Multi-Turn), DAgger/exposure-bias anchors.
- Read Singh 2608.15046 in full to check whether any appendix derives the margin from reference variance (the html summary says no).
- The ACBench per-config table is still owed (bit-widths are known now: 4/8; runs = 1, T=0).
- ~~Flat Score per-config details~~ (done above: models, AWQ INT4/FP8, 4 trials, real kernels).
