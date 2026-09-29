**TL;DR**
- Iteration-3 discussion log (quantization-centred, `docs/insights/PLAN_iter4.md`). Round 1 proposes I5–I8. The full text is in `docs/insights/iter_3_candidates.md`.
- Survey (round 1, below): I5 and I7 are sharper versions of known flip/churn and open-vs-closed-loop results; I6 is new at task level and contradicts the margin account of which items flip; I8 is partly anticipated by Flat Score's budget-exhaustion count. Kennedy 2026 (https://arxiv.org/abs/2609.33923) predicts gshape ≈ RTN < isotropic, so cite it as the mechanism.
- Experiment: please cost and critique E17 (RTN-shaped Gaussian) and E20 (extra q8/q30a3 quantizer draws).

# Iteration 3 discussion

## Insight (round 1)

Four candidates, all computed on the iteration-2 gate. Two snapshots were used:
- frozen: `analysis/insights/iter_2/out/snapshot_20260929T0732Z.json`;
- live, provisional: `analysis/insights/iter_3/out/snapshot_live_20260929T1159Z.json`.

Scripts are `analysis/insights/iter_3/r01–r09`; re-run with `run_all.sh`.

- **I5, size-generic reallocation.** A fixed weight perturbation re-deals a fraction λ of robust tasks toward an attractor c, so Δ = λ(c − p̄) while λ = 0.07–0.48 at W4 (null SD 0.04–0.08).
  - Gaussian noise of equal weight norm re-deals *more* than every W4 quantizer: pooled +0.11 to +0.15, 4/4 models.
  - A null-scale fixed checkpoint re-deals nothing.
  - Among RTN, GPTQ and AWQ there is no pooled difference.
  - evidence: `analysis/insights/iter_3/out/r08_size_generic_{live,frozen}.json`, `r01_realloc_live.json`.
- **I6, fragility is latent and (model, task)-specific.** Breaks and fixes have four properties:
  - they repeat across nonces of one checkpoint (lift 2.2–5.1);
  - Gaussian-derived fragility predicts quantizer breaks (AUC 0.75–0.83; super-robust 0.68–0.81);
  - they do not transfer across models (AUC 0.51);
  - they are invisible to BF16 margins and to open-loop per-task flips (AUC 0.4–0.6).
  - evidence: `r03_fragility_live.json`, `r04_margin_predict_live.json`, `r05_openloop_task_live.json`, `r06_crossmodel_live.json`.
- **I7, open loop predicts how much, not which, and not net.** ρ(open-loop flip, λ) = 0.75–0.83. ρ with Δ is weak or null, and task-level AUC is about 0.5. This explains the iteration-2 C4 refutation through Δ = λ(c − p̄).
  - evidence: `r05_openloop_task_{live,frozen}.json` `cell_identity`.
- **I8 (hypothesis), damage is attractor collapse with loud control failures.** At W4, 5/137 breaks end abnormally. q8 RTN-W3 has 37% abnormal terminations and c = 0.06. ρ(p̄ − c, abnormal excess) = 0.48.
  - evidence: `r07_damage_live.json`.

Killed this round (R3-a…f in the candidates file):
- BF16 margins predict the fragile set;
- open-loop per-task flips predict it;
- fragility is a task property;
- "any fixed checkpoint has a profile" (at k = 0.03 on q14);
- "quantization error is worse than noise".

**The most important experiment** is E17, RTN-shaped Gaussian noise (per-group σ equal to that group's RTN error RMS). It decides whether the noise > quantizer gap is the error's energy distribution or its rounding structure. That makes "predict a quantizer's agentic effect from its error size" operational at the right granularity.

## Survey (round 1)

Owner: cloq-survey, 2026-09-29. Every URL below was opened in this pass. Detailed map: `docs/insights/SURVEY.md#t9-quantization-reallocation-error-size-vs-structure-fragile-sets-iter-3`; BibTeX: `analysis/insights/references_new.bib` (block "iteration 3 round 1").
The main session's provisional E17 facts are treated as unfrozen. They are the gshape/rtnsign λ values, isotropic λ 0.13–0.15, AWQ > RTN, and W3 damage. Their only pointers so far are the queue records `/data/ziyangs/cloq_work/queue/done/a6k2_q8_gshape_w4.json` and `/data/ziyangs/cloq_work/queue/done/a6k2_q14_rtnsign_w4.json`, and the λ values come from the main-session message (09:30 PDT). No analysis json exists yet.

### Novelty calls

| id | call | closest prior work (URL) | what it shows | what we add |
|---|---|---|---|---|
| I5 reallocation toward an attractor, size-generic | **(b) sharper / more general** | Dutta et al., NeurIPS 2024, https://arxiv.org/abs/2407.09141 | Static MCQ. At similar accuracy, W4 GPTQ/AWQ flip 4–8% of answers, and flips are balanced (wrong→right ≈ right→wrong). Low top-margin answers flip. KL vs flips ρ = 0.981. | Closed loop. A re-roll-null-referenced robust-task decomposition with misclassification correction (λ, c). The attractor model Δ = λ(c − p̄): Dutta's balance is the special case c ≈ p̄, and the model also predicts *when* flips stop being balanced (W3: c ≪ p̄). Size-vs-structure controls (isotropic, gshape, rtnsign, null-scale fixed ckpt). |
| | | Singh 2026, https://arxiv.org/abs/2608.15046 | Churn ≈ 5.4× the net delta over 1,707 static cells. GPTQ vs AWQ on GSM8K: 9.1% right→wrong, 8.5% wrong→right. | Theirs is a churn ratio with no null and no model of the net. |
| | | Hooker et al. 2019, https://arxiv.org/abs/1911.05248 | "Compression cannibalizes performance on a small subset of classes to preserve a similar overall top-line accuracy". Uses a population-of-30-models (init) null with modal labels. | The null idea (population modal label) is Hooker's in spirit and must be cited. We add the agent loop, weight-noise controls and the attractor. |
| | | Vallecillos-Ruiz et al., ICSME 2026, https://arxiv.org/abs/2606.27205 | Program repair: Llama-8B quanto4 solves 58 vs 61 problems with only 29 overlapping (Jaccard Consistency Rate). One seed, T = 0.1, no null. | Nearest *agent-adjacent* precedent of solved-set drift. It lacks a null, so part of its drift is re-roll noise. |
| I6 fragile set is latent, (model, task)-specific, perturbation-agnostic, invisible to BF16 margins | **(a) new at task level in agents**; (b) relative to PIEs | Hooker 2019 (above) | PIEs are shared across pruning levels and are *atypical/hard* examples, i.e. a data property. No random-weight-noise control and no cross-architecture test (read in full; `evidence:` pdftotext of 1911.05248 §3). | Noise↔quantizer transfer (AUC 0.75–0.83); no cross-model transfer (AUC 0.51), which *contradicts* the "task property" reading of PIEs; repeatability across re-rolls. |
| | | Duan 2026, https://arxiv.org/abs/2606.03002 | SAE *features*: RTN and matched-perplexity pruning damage overlapping sets (Jaccard 0.79–0.86, Spearman 0.98). Damage is predictable from FP statistics (AUC 0.92–0.97). | Same "shared vulnerability" at feature level, but there it is FP-predictable. Our task-level fate is **not** FP-predictable (margin AUC 0.43–0.60). Cite as the contrast. |
| | | Dutta 2024 (above); Integer Alibi https://arxiv.org/abs/2608.13756 | Low margin predicts which answer or token flips (AUC 0.94 token-level). | We contradict the extension of this to *task fate* in closed loop (R3-a). |
| | | Lee et al., IJCAI 2025, https://www.ijcai.org/proceedings/2025/0902.pdf | "Quantization magnifies a model's inherent weaknesses rather than simply correlating with task difficulty". | Dataset-level support for model-specificity (I6 c). |
| | | Baldock et al. 2021, https://arxiv.org/abs/2106.09647 | Example difficulty (prediction depth) is consistent across architectures. | Counterpoint to I6 c: say why agent task fate differs (the decision is reached in closed loop). |
| I7 open loop predicts how much, not which, not net | **(b)** | Dutta 2024: KL ↔ flips ρ = 0.981 (static) | A distance metric predicts the *amount* of flips. | Extension to closed-loop λ (ρ = 0.75–0.83), plus the explicit failure for identity (AUC ≈ 0.5) and for Δ (via λ(c − p̄)). |
| | | Codevilla et al., ECCV 2018, https://arxiv.org/abs/1809.04843; Wang et al. 2026, https://arxiv.org/abs/2605.00066 | Offline error "is not necessarily correlated with driving quality". NAVSIM→Bench2Drive ρ = 0.90 in aggregate, with ranking inversions and a "snowball effect". | These are the driving analogue. Ours is the first amount/identity/net split. |
| I8 net damage = attractor collapse with loud control failures | **(b)**, partly anticipated | Flat Score, https://arxiv.org/abs/2607.27275 (html read) | Gemma-4-31B telecom: error-budget exhaustions 5 (BF16) → 46 (INT4); "no episode in any arm reaches either cap" (max_steps); tool-name hallucination up to 2.5×. | They have no rerun baseline for termination reasons and no link to a net-effect parameter. We tie loud failures to c and measure the silent-break share against the null. |
| | | Advani 2026, https://arxiv.org/abs/2606.09863 | 45–48% of single-control τ² successes are false (silent failure). | The silent/loud split exists in agent-reliability work, but not under perturbation. |

### Direct answers to the lead's five questions

1. **"Aggregate preserved, but *which* items are solved changes" is known for static tasks.**
   - Prior work: Dutta 2407.09141, Singh 2608.15046, Rababah 2607.08734 ("a shift in behavior even when accuracy and perplexity are preserved") and Hooker 1911.05248. Also Vallecillos-Ruiz 2606.27205 (program repair, low solved-set overlap) and Saha 2609.06922 (VLM: only 265/9,000 answers change at 4-bit while score gaps move).
   - No paper does this for closed-loop agents against a re-roll null.
   - **Flat Score does not report per-task churn.** Its ρ ≥ 0.94 / 0.97 is the rank correlation of *per-tool-name hallucination frequencies* (Gemma-4-31B telecom; 3 of 1,646 INT4 hallucinations are novel tool names). Per task it reports only "4-bit worse on 33, better on 26, tied on 55" (4 trials each, no rerun null). This answers S5-b: their "failure set preserved" is at the level of failure types and does not conflict with λ = 0.05–0.5.
   - We add:
     - (i) closed loop;
     - (ii) null-referenced robust-task decomposition (always-ok / always-fail from nonce nulls, with LOO misclassification correction);
     - (iii) the attractor model, which explains Dutta-style balance (c ≈ p̄) and predicts its breakdown (W3: q8 −17 pp, q14 −15 pp; provisional, main session);
     - (iv) the size-vs-structure controls, which no flip paper has.
2. **Size vs structure of the error.**
   - Classical: uniform quantization ≈ additive, uncorrelated, white noise under Widrow's conditions (Widrow, Kollár, Liu 1996, https://isl.stanford.edu/~widrow/papers/j1996statisticaltheory.pdf). DiffQ (https://arxiv.org/abs/2104.09987) uses exactly this as a training proxy.
   - LLM-specific and new, **Kennedy & Kennedy 2026 (https://arxiv.org/abs/2609.33923)**:
     - RTN error is spectrally flat: effective dimensionality is 0.93–0.96× the i.i.d. value over 1,683 tensors, and invariant from 2 to 8 bits.
     - Isotropic Gaussian probes **over-excite the few high-energy residual channels** (29% vs 17% of energy on Qwen3-8B). They therefore overestimate absolute output damage while preserving the ranking.
     - This is the published mechanism for our "isotropic (λ 0.13–0.15) > RTN, gshape (0.049) ≈ RTN (0.052) on q8". Structure *within* a group barely matters, while the per-group energy distribution does.
   - Hu & Ramachandran 2026 (https://arxiv.org/abs/2609.01587): per-group granularity is worth +0.095 CORE, while GPTQ/AWQ add only +0.020/+0.017 on top. Scale granularity dominates the algorithm, consistent with "per-group RMS is the sufficient statistic".
   - **Rounding correlation (signs) does matter:**
     - AdaRound (https://arxiv.org/abs/2004.10568, full text): the diagonal-Hessian terms see only magnitude, and the *off-diagonal* terms see sign. On ResNet18 layer 1 at 4-bit, 100 stochastic roundings give 52.06 ± 5.52% vs nearest 52.29% (best 63.06%; all-up/all-down 0.10%).
     - That matches our q14 rtnsign (0.175) > RTN (0.098): RTN's signs are not random-bad; they are on average at least as good as random.
     - Hessian-weighted error: GPTQ https://arxiv.org/abs/2210.17323, HAWQ https://arxiv.org/abs/1905.03696, QuIP incoherence https://arxiv.org/abs/2307.13304.
     - Adversarial bound on "size-generic": Egashira 2024 (https://arxiv.org/abs/2405.18137) and AGENTQ (EMNLP 2026, https://arxiv.org/abs/2609.14060, up to 100% post-quantization attack success on agents). Rounding structure *can* carry arbitrary behaviour when optimised. Scope I5 to "non-adversarial checkpoints".
3. **AWQ/GPTQ vs RTN: flips and consistency, not perplexity.**
   - Dutta: at W4, AWQ flips 4.05–7.66% and GPTQ 4.26–8.26%, which is not separable. Only GPTQ-W8 is near zero (0.26–1.40%). Perplexity is insufficient because "lower probabilities for some tokens … may be cancelled by higher probabilities of other tokens".
   - Singh: the calibration draw alone reverses the GPTQ–AWQ ranking in 5/8 cells.
   - Hu & Ramachandran, App. F: AWQ is calibration-seed-stable (spread 0–2%), GPTQ is not (4–24%).
   - Shafique & Marchisio 2026 (https://arxiv.org/abs/2608.08447): consistency "improve[s] or degrade[s] … independently of its effect on accuracy". GPTQ/AWQ beat AutoRound there.
   - Jaiswal 2024 (https://arxiv.org/abs/2310.01382): perplexity misses knowledge loss.
   - Williams & Aletras, ACL 2024 (https://arxiv.org/abs/2311.09755): "substantial variations in downstream task performance" from the calibration data alone.
   - **Nobody reports AWQ churning *more* than RTN at lower perplexity.** Our provisional q4/q8 result (AWQ 0.12–0.15 vs RTN 0.05–0.09) is new. It is plausible through AWQ's activation-derived per-channel scaling: that moves error energy across channels, which is exactly the variable Kennedy shows matters. It needs the calibration-seed control below.
4. **Quantized agent / tool-use evaluations, 2025–2026.**
   - ACBench (https://arxiv.org/abs/2505.19433): single run, no per-task analysis.
   - Flat Score: per-task paired counts only, no null.
   - Mix-Quant https://arxiv.org/abs/2605.20315 and QuantClaw https://arxiv.org/abs/2604.22577: aggregate.
   - Dynamic mixed-precision routing (https://arxiv.org/abs/2602.02711): step sensitivities differ and are learned via KL.
   - Vallecillos-Ruiz (program repair): solved-set drift, no null.
   - AGENTQ: adversarial.
   - Rath https://arxiv.org/abs/2605.15208: new failures vs seed flips, on bias.
   - **None reports robust/fragile task sets against a re-roll null.**
5. **A model-specific fragile set that transfers across perturbations.**
   - Nearest are feature-level (Duan: quant ↔ pruning, same model) and class/exemplar-level within one architecture (Hooker PIEs/CIEs).
   - Flat Score's "quantization amplifies the failure the model already exhibits at full precision" is the failure-*type* analogue.
   - No task-level noise↔quantizer transfer and no cross-model test was found. Baldock's cross-architecture consistency of difficulty is the counter-expectation that I6 c overturns for agents.

### Results that should change an experiment

- **E17 follow-up (Kennedy 2609.33923).** Add a **channel-energy-share** statistic per perturbation: the fraction of the propagated output perturbation in the top-k energy residual channels. It is computed from one forward pass with the checkpoint delta (0 GPU-h beyond E3). Prediction: it orders λ as isotropic > rtnsign > gshape ≈ RTN on q8/q14, and explains AWQ > RTN. If it does not, the energy-distribution reading is wrong.
- **Valid random rounding (AdaRound Table 1).** rtnsign is off-grid. A *stochastic-rounding* W4 checkpoint keeps RTN's grid and scales and randomises only the up/down choice. AdaRound predicts the mean ≈ RTN with a large spread. Run 2 seeds × q14, 2 nonces each (≈ 4–6 GPU-h, the E17 cost scale from `docs/insights/iter_3_candidates.md` E17). This separates "sign correlation" from "off-grid".
- **Calibration-seed control for AWQ > RTN (Singh; Hu & Ramachandran App. F; Williams & Aletras).** Run AWQ-W4 with a second calibration seed on q4/q8. If λ(AWQ) varies by more than the null pair SD (0.024–0.050, `analysis/insights/iter_3/out/r08_size_generic_live.json` `null_pair_lam_sd`), the "AWQ reallocates more" claim is a calibration draw, not a method property.
- **Baseline we must match.** Report Dutta-style flips (pairwise, BF16 canonical vs quantized) *next to* λ. This shows how much of the raw flip count is re-roll noise, using the tau2 issue #540 scale (32–55% of tasks reverse across identical runs; https://github.com/sierra-research/tau2-bench/issues/540).
- **Scope line for I5.** "Non-adversarial PTQ". AGENTQ and Egashira show that structure can dominate size when rounding is optimised against a behaviour.
