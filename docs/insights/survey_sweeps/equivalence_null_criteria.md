# Survey sweep: equivalence / null criteria for compressed models (2026-09-28)

31 sources opened (abs pages); full text only for 2607.27275, 2608.15046, tau2-bench issue #540. Venues from arXiv comments.

## How close prior work gets (no one states our full criterion or P2)
1. **Jang 2026, Flat Score** (2607.27275) — closest: τ²-bench, 16/8/4-bit, task-paired bootstrap + **TOST at ±7.5 pt**,
   margin "≈1.3× the run-to-run noise floor" estimated from ONE repeated 456-episode run (1.5 pt, "coarse").
   Lacks: perturbation null (nonce/weight noise), task-level null distribution, divergence-vs-damage threshold.
   Reports the other side of P2: flat score while process errors rise ≤2.5×. → cite prominently; we generalise it.
2. **Kaplan 2026** (2609.18005) — "null condition, provably identical in distribution" (two ordinary runs) calibrating an
   LLM-judge instrument; 4-bit indistinguishable at ±0.3; single-turn, judge-scored, not agents.
3. **Chen 2026, Noise Floor Audit** (2608.22331) — BFCL: prompt-perturbation floor 11–58× the rerun floor;
   **the choice of null dominates** → report rerun and perturbation nulls, justify which defines "neutral".
4. **Singh 2026, Certifying Compressed LMs** (2608.15046) — paired TOST at a DECLARED ±2 pp margin, static benchmarks;
   churn ≈5× net delta; 0/16 equivalence claims in the literature state a margin; GPTQ-vs-AWQ ordering flips with
   calibration seed in 5/8 cells.
P2 direction (divergence ≫ damage) exists only as point observations: Dutta 2024, Singh 2026, Rababah 2026 (2607.08734,
"illusion of equivalency"), Patodiya 2026, Jang 2026. **No one measures divergence saturation vs damage threshold along
perturbation size, or a free compression zone.** Closest weight-noise dose–response: Tice 2024/NeurIPS 2025 (2412.01784,
sandbagging), accuracy only.

## Other entries (abstract level unless noted)
Kübler 2026 (2602.10144) per-sample McNemar for degradation, detects 0.3%; Gao 2024 Model Equality Testing (2410.20247,
ICLR 2025) MMD detects endpoints easily (distributional ≠ task damage); Cai 2025 (2504.04715) quantized substitution hidden by
nondeterminism; Zhu 2025 (2506.06975) rank-uniformity audit; **Acharyya 2025 (2509.10963) composite null of semantically
irrelevant query perturbations — closest statistical precedent for a perturbation null**; Bouthillier 2021 (2103.03098,
MLSys) variance accounting; Madaan 2024 (2406.10229) seed variance; Heineman 2025 (2508.13144) signal and noise;
Miller 2024 (2411.00640) error bars; Dror 2018 (ACL P18-1128) significance testing; Mustahsan 2025 (2512.06710) ICC for
agent stochasticity, 8–16 trials; Rabanser 2026 (2602.16666, ICML); Hariri 2025 (2510.04265, ICLR 2026) Bayesian pass@k;
Khanal 2026 (2603.29231) variance amplification factor; Kapoor 2024 (2407.01502) AI Agents That Matter; **Zhu 2025 ABC
(2507.02825): "TAU-bench counts empty responses as successful" — caveat for our success metric**; Atil 2024; Yuan 2025;
Fang 2025; Sclar 2023; **tau2-bench GitHub issue #540** (https://github.com/sierra-research/tau2-bench/issues/540): from
released trajectories, single runs must differ by 10–11 pt (airline) / 7–8 pt (retail) to exceed noise; 32–55% of tasks
reverse verdict across identical runs.
Lower priority: Bhojanapalli 2021 churn (2102.03349); Summers 2021 (2103.04514, ICML); Kurtic 2025 "Give Me BF16 or Give Me
Death" (2411.02355, ACL 2025); ACBench; HAL (2510.11977); Kurtskhalia 2026 (2609.07901); Double Measurement Confound (2609.09218).
Unopened lead: equivalence testing with data-dependent margins (2603.16213) — relevant for justifying a null-derived margin.

## Suggested positioning
Criterion novelty = margin/null band from the reference model's OWN perturbation distribution (nonce, Gaussian weight noise,
reruns) per task, for closed-loop agents — vs declared (Singh) or one-rerun-scaled (Jang). Acharyya = statistical precedent.
Threats: ABC (τ reward flaws), Jang (error budget masks damage → report process-error channels), Patodiya/Yuan (serving
nondeterminism → fix prefix-cache and batch settings when building the rerun null).
