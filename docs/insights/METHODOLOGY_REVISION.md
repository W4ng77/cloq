**TL;DR** Audit record of the P0 statistics and measurement fixes from the GPT-6.1 review (§B, §C, §F), done 2026-09-30 on snapshot 20260930T0044Z. All reported issues were confirmed in the code. The pre-registered H3 permutation test was invalid: with the true-pair scaling it rejects 33–42% of exchangeable null datasets at α = 0.05. The corrected test is calibrated: 4.4% ± 0.3% against a nominal ≤ 4%, B = 99. Corrected H3 still rejects when pooled (F 0.136, p 0.013), but the pooled signal is 90% from the random Gaussian checkpoints. RECAL (quantizer recalibrations) alone is not significant: F 0.025, p 0.30 (sensitivity p 0.13). The quantizer fingerprint claim (STORYLINE_v6 B3) is therefore withdrawn to "not shown". The crossed nonce model leaves the H1 p unchanged (0.744) and moves φ from 0.40 to 0.33–0.47, so the H1 verdict is unchanged. The measurement fixes do not change any W4 conclusion. The act/talk "blurring" (B5) is mostly a selection effect; its directional part is small and is not specific to quantizers. The success non-inferiority script is ready and waits for `bfpair`. ε = 3 pp was fixed before any `bfpair` outcome existed.

# Methodology revision: P0 statistics and measurement fixes (2026-09-30)

All results below that touch the 28 confirmatory runs are a **corrected (post-hoc) re-analysis**. Those runs were unblinded in W25. The pre-registered output `analysis/insights/iter_4/out/prereg_h1_h4_CONF_20260930T0044Z.json`, `PREREG_iter4.md` and `prereg_h1_h4.py` are unchanged and kept as history.

## 0. Audit record

| Item | Value |
|---|---|
| Repo HEAD at audit start | `af6b190` (W28). Committed on top of `66714f0` (fork pipeline commits by another session; no overlap with these files) |
| Snapshot | `analysis/insights/iter_3/out/snapshot_live_20260930T0044Z.json`, sha256 `244affdc277849beb45d242e1683bad4e7b087d7c71ac405cb777023ef9dc230`, utc 2026-09-30T00:44:19Z. Same gated snapshot as the confirmatory run; no fresher one needed (the `bfpair` runs are not done) |
| NULL_RULE | `docs/insights/NULL_RULE.md` sha256[:16] `65711ed7009fab90` (recorded in the snapshot) |
| PREREG | `docs/insights/PREREG_iter4.md` sha256[:16] `a991e2e5ca2d6098` (amendment 1; unchanged) |
| Pre-registered output | `prereg_h1_h4_CONF_20260930T0044Z.json` sha256[:16] `bf5f955c89ce82ba` (unchanged) |
| Code read (sha256[:16] at audit start) | `prereg_h1_h4.py` `5d08492a345cbefb`; `p1_overdispersion.py` `74246c6d2cc27256`; `common4.py` `d390e666cf9e3db3`; `iter_3/r_common.py` `8fa2cb438c5bed21`; `iter_2/common.py` `c8732108c93fa667`; `scripts/a6000/openloop_topk.py` `5115a33e12bf93b0` |

- `iter_2/common.py` changed after the confirmatory run. At that run its hash was `5a89d3574dbe7050`; W27 then added `agent_parse_error` to `AGENT_SIDE`.
- The re-analysis reproduces the pre-registered H3 exactly, F 0.2602 and p 0.0008 (`reproduction_of_prereg.match = true`), and the H1 p 0.74385 exactly. The W27 change therefore does not touch the q4/q8 confirmatory data.

### Analysis inputs

- **Confirmatory units.** 28 runs `a6k2_{q4,q8}_{gptq,awq}_w4_d{3,4}_q{1,2}` and `a6k2_{q4,q8}_gauss1_s{2,4,5}_q{1,2}`.
- **Null.** `a6k2_{m}_null_n1..n8`, with ≥ 77 tasks each (NR1-2).
- **Variance components.** GPTQ-W4 d1 (n1, n2, q3–q5), d2 (n1, n2), d3/d4 (q1, q2); AWQ-W4 d1 = `awq_w4` (n1, n2, q3–q5), d2 (q1–q3), d3/d4 (q1, q2); Gaussian k=1 s1–s5 (q1, q2, s2 also q3).
- **Success pairing.**
  - BF16 is `null_n<k>` on the n-nonces and `bfpair_q<k>` on q1–q5. The `bfpair` runs are queued (W28); dev mode stands in `null_n<k>`.
  - Secondary cells: RTN-W4, `rot_bf16`, Gaussian k=1 fixed.
- **E4-2 top-k.** All 50 cells under `analysis/openloop/a6k2/{q4,q8,q14,q32}/topk/*.npz`, each against the model's `bf16` top-k cell.
- **Generated-class cross-check.** BF16 closed loop `a6k2_{m}_bf16` and canonical Gaussian closed loop `a6k2_{m}_gauss1_s{1,2,4,5}`, the same checkpoint spec as the top-k cells: `{"kind": "gauss", "k": 1.0, "seed": s}` in both `config.json` files.
- **Tool definitions.** `third_party/tau2-bench` @ `2174a603`, `src/tau2/domains/{retail,airline,telecom}/tools.py`.

### Inclusion and exclusion rules (unchanged from prereg A5/A6 unless stated)

- Runs enter only through the integrity gate, and nonces are taken from the snapshot.
- An `infrastructure_error` episode is missing. Context overflow and `agent_parse_error` count as failure (W10, W27).
- y = `db_match` AND normal termination ("DB success", see C8).
- q4 airline 45 is removed.
- Primary task set = complete case over the null plus the confirmatory draws: q4 84 tasks, q8 85.
- The variance components use their own complete case.
- In `success_ni`, the task set is the complete case within each cell over its (Q, B) pairs, and dropped counts are reported.

## 1. Statistics issues (review §B)

### B1. H3 split-task fingerprint — **confirmed; fixed** (`analysis/insights/iter_4/h3_corrected.py`)

**Verified.** `prereg_h1_h4.split_cos` scales every feature by the differences of the *true* (q1-draw, q2-draw) pairs:
```python
sA = np.array([S[a] for a, _ in allu]); sB = np.array([S[b] for _, b in allu])
sd_w = np.sqrt(np.nanmean((sA - sB) ** 2, 0) / 2)
```
`fsplit_test` then permutes columns of a cosine matrix that was averaged over splits with that scale held fixed:
```python
Fs = np.array([F_from_C(Cs, ps) for ps in space])
```
The scale depends on the observed pairing. Features on which the true pairs happen to agree get up-weighted for the observed statistic only, so the permuted statistics are not exchangeable with the observed one.

**Fix** (all choices fixed before looking at the corrected numbers):
- **Main test.** Pairing-invariant, unpaired pooled scale, per split and feature: sd = sqrt((Σ_j (s_Aj − s̄_A)² + Σ_j (s_Bj − s̄_B)²)/(2(J_m − 1))) over all 7 units of the model. It depends only on the unordered sets {s_A} and {s_B}, so the column permutation is a valid permutation test.
- **Sensitivity test.** The original statistic, with the full preprocessing (true-pair sd_w, cosines, F) recomputed inside every permutation.
- **Fixed for every variant and every permutation:**
  - the 12 DISP features, in fixed order;
  - the same 100 split halves (the prereg stream `rng_for("split:primary:<m>")`);
  - one relabelling stream per family, shared by all variants;
  - NaN half-shifts set to 0 (none occurred);
  - a feature is dropped in a split when its scale is 0. The true-pair scale drops 18 of 1200 q4 feature×split cells; the pooled scale drops none.

**Observed data** (F / one-sided p). Exact enumeration where the number of relabellings is ≤ 5000.

| Family | Relabellings | Original (pre-registered method; invalid null) | **Main (corrected)** | Sensitivity (recompute per permutation) |
|---|---|---|---|---|
| Pooled, 4 model×set blocks (= H3) | 5000 MC | 0.260 / 0.0008 (prereg stream); 0.0004 (family stream) | **0.136 / 0.0134** | 0.260 / 0.0028 |
| RECAL only | 576 exact | 0.118 / 0.0052 | **0.025 / 0.304** | 0.118 / 0.130 |
| RAND only | 36 exact | 0.450 / 0.028 | **0.283 / 0.028** (p_min 1/36) | 0.450 / 0.028 |
| q4 | 144 exact | 0.193 / 0.021 | **0.088 / 0.125** | 0.193 / 0.069 |
| q8 | 144 exact | 0.328 / 0.0069 | **0.184 / 0.049** | 0.328 / 0.021 |
| Within model×method, all 6 blocks | 576 exact | 0.260 / 0.0017 | **0.158 / 0.0052** | 0.260 / 0.0035 |
| Within model×method, GPTQ/AWQ blocks only | 16 exact (p_min 0.0625) | 0.117 / 0.0625 | **0.064 / 0.1875** | 0.117 / 0.25 |
| q4 GPTQ d3 vs d4 | 2 (p ∈ {0.5, 1}) | 0.033 / 0.5 | −0.027 / 1.0 | 0.033 / 0.5 |
| q4 AWQ d3 vs d4 | 2 | 0.184 / 0.5 | 0.110 / 0.5 | 0.184 / 0.5 |
| q4 Gaussian s2, s4, s5 | 6 (p_min 1/6) | 0.323 / 0.167 | 0.200 / 0.167 | 0.323 / 0.167 |
| q8 GPTQ d3 vs d4 | 2 | 0.226 / 0.5 | 0.153 / 0.5 | 0.226 / 0.5 |
| q8 AWQ d3 vs d4 | 2 | 0.024 / 0.5 | 0.018 / 0.5 | 0.024 / 0.5 |
| q8 Gaussian s2, s4, s5 | 6 | 0.578 / 0.167 | 0.367 / 0.167 | 0.578 / 0.167 |

**Block composition of the pooled F** (same-checkpoint cos / different-checkpoint cos / share of F):

| Block | Original | Main |
|---|---|---|
| q4 RECAL | 0.317 / 0.222 / 10% | 0.075 / 0.072 / 1% |
| q4 RAND | 0.510 / 0.187 / 27% | 0.271 / 0.071 / 32% |
| q8 RECAL | 0.380 / 0.240 / 15% | 0.172 / 0.125 / 10% |
| q8 RAND | 0.774 / 0.196 / 48% | 0.604 / 0.237 / 58% |

RAND carries 74% of the original F, as the review stated, and 90% of the corrected F.

**Split-seed stability.** The main pooled F over 3 further split streams is 0.131, 0.131 and 0.138; RECAL-only is 0.016, 0.022 and 0.033.

**Simulation** (`--sim`). Synthetic datasets resample the real per-task shift rows within block, so draws are exchangeable within block while feature scales, missingness and task structure stay realistic. The planted signal adds δ·g_j·s_f to both draws of unit j. Entries are rejection rate at α = 0.05 ± Monte Carlo SE.

| Setting | Original | Main | Sensitivity |
|---|---|---|---|
| H0, 20 splits, B 199, n 2000 (nominal ≤ 0.045) | **0.364 ± 0.011** | 0.053 ± 0.005 | 0.052 ± 0.005 |
| H0, 20 splits, B 99, n 6000, independent seeds (nominal ≤ 0.040) | **0.331 ± 0.006** | 0.044 ± 0.003 | 0.044 ± 0.003 |
| H0, 100 splits, B 499, n 2000 (nominal ≤ 0.048) | **0.417 ± 0.011** | 0.061 ± 0.005 | 0.061 ± 0.005 |
| H0, 100 splits, B 999, n 500 (subset of the row above) | 0.434 ± 0.022 | 0.072 ± 0.012 | 0.074 ± 0.012 |
| Power, δ = 0.01 / 0.02 / 0.03 / 0.05 (20 splits, n 2000) | 0.38 / 0.52 / 0.72 / 0.97 (not interpretable: size 0.36) | 0.07 / 0.12 / 0.24 / 0.75 | 0.03 / 0.07 / 0.14 / 0.58 |

- **Exactness check.** On iid Gaussian synthetic shifts with 12 features of unequal scale (6000 datasets, 5 splits, B = 99), the main test rejects 0.0405 ± 0.0025 against a nominal ≤ 0.040. The original rejects 0.81.
- The main test is an exact permutation test by construction. The two 100-split rows share datasets with each other and with the first 20-split row. They sit 1.9–2.4 SE above nominal; the independent-seed row (1.5 SE) and the iid check are at nominal. Read them as a possible small excess of ≤ 0.01, not as a calibration failure.
- The main test has more power than the sensitivity test.

**Decision.**
- The pre-registered "H3 supported" label is removed. The old p is kept as history.
- The corrected pooled H3 (main p 0.0134) would pass Holm in the original family (3 × 0.0134 = 0.040), but this is post-hoc.
- It is carried by the random Gaussian checkpoints. The quantizer (RECAL) fingerprint is not detected: main p 0.30, sensitivity 0.13, within-method p 0.19.

### B2. p1 variance decomposition — **confirmed; fixed** (`analysis/insights/iter_4/p1_crossed.py`)

**Verified.** `p1_overdispersion.stats`:
```python
nonce = np.mean((yA.mean(1) - yB.mean(1)) ** 2) / 4
indep = np.sum(m.var(0, ddof=1) - np.mean((yA - yB) ** 2, 0) / 4) / N ** 2
```
With every checkpoint drawn under the same q1/q2 nonces, E[nonce] = σ²_e/2 + (b1 − b2)²/4. The shared nonce main effect cancels in between-checkpoint differences but is still subtracted, so sig_ck and φ are biased low. The same holds per task inside `indep`.

**Fix: crossed model.** Per model×set block:
- Model: m_jn = μ + a_j + b_n + e_jn.
- Design matrix X = [1 | J checkpoint indicators | 2 nonce indicators], rank J + 1, n = 2J.
- ANOVA without replication:

  | Term | df | E[MS] |
  |---|---|---|
  | MS_ck | J − 1 | σ²_e + 2σ²_a |
  | MS_nonce | 1 | — |
  | MS_res | J − 1 | σ²_e |

- σ̂²_a = (MS_ck − MS_res)/2.
- The unbiased shared-nonce term is (d̄² − s²_d/J)/4.
- The crossed independent-landing denominator uses the per-task interaction.
- Assumptions: additive checkpoint and nonce effects on run-level success; iid interaction plus run noise; fixed tasks.
- Negative moment estimates are kept, not truncated.

**H1 invariance (verified numerically).**
- The P1 null permutes checkpoint labels within task. d̄ (the mean over j and t of yA − yB) is invariant under that, so removing only the main-effect term shifts T and every permuted T* by the same constant, (J − 1)d̄²/4 = 0.000224.
- Checked on the pre-registered relabelling stream: **p = 0.74385 before and after** (`narrow_minus_p1_constant_under_permutation = true`).
- The fully crossed estimator (interaction divisor J − 1) is not a constant shift. Its p on the same relabellings is 0.721.

| Quantity (RECAL pooled, H1) | Pre-registered p1 | Main effect removed | Fully crossed |
|---|---|---|---|
| φ | 0.396 | 0.469 | 0.327 |
| Permutation p | 0.744 | 0.744 (identical) | 0.721 |

| Block | φ p1 | φ crossed | Unbiased shared nonce main effect | Checkpoint SD, signed pp (p1 → crossed) |
|---|---|---|---|---|
| q4 RECAL | −0.30 | −0.32 | −6e−6 | −1.17 → −1.19 |
| q4 RAND | 2.02 | 2.09 | −1.2e−5 | 3.38 → 3.37 |
| q8 RECAL | 0.94 | 0.81 | −5.8e−5 | 2.33 → 2.20 |
| q8 RAND | 0.36 | −0.00 | −1.9e−4 | 1.36 → −0.00 |

The q1–q2 main effect is estimated at about 0 (the unbiased estimate is slightly negative), so here the bias was small. The φ point estimate was nonetheless biased by construction. The H1 verdict (not supported) is unchanged, and the lottery line is not reopened.

**Variance components (replaces A13).**
- Model: Henderson method III for the unbalanced crossed design y_r = μ + M_method + C_ckpt(method) + N_nonce + e_r.
- Quadratic forms: SSE, R(C|μ,M,N), R(N|μ,M,C), R(M|μ,N).
- Degrees of freedom: 9, 6, 6, 1 for GPTQ/AWQ (23 runs, 8 checkpoints, 7 nonces), and 13, 9, 6, 2 with Gaussian added.
- Components are exact moment solutions. Table entries are signed SD in pp, sign(v)·sqrt(|v|):

| Model, set | Residual (nonce×ckpt + run) | Checkpoint | Nonce main | Method | A13 nested (pre-registered): method / ckpt / nonce |
|---|---|---|---|---|---|
| q4 GPTQ+AWQ | 2.62 | 3.69 | −0.86 | −2.07 | 0 (truncated from −0.000396) / 3.65 / 2.51 |
| q8 GPTQ+AWQ | 2.61 | 1.24 | 1.26 | 0.30 | 1.43 / 0.96 / 2.87 |
| q4 + Gaussian k=1 | 2.43 | 3.63 | −0.54 | −1.23 | — |
| q8 + Gaussian k=1 | 2.72 | 2.25 | 1.02 | 2.46 | — |

- Method has 1–2 df, so it is not estimable in any useful sense. A negative value is a moment estimate, not evidence that the component is 0.
- q4's checkpoint component is about 3.7 pp in both decompositions. It is driven by d1/d2 (GPTQ d1 +5.2, d2 −4.5 pp); the confirmatory d3/d4 are homogeneous.

### B3. Success non-inferiority, equivalence and ordinary difference — **new scaffold** (`analysis/insights/iter_4/success_ni.py`)

**Design.**
- Paired on the prompt nonce; the simulator configuration is shared. Run-level success is computed first, then the paired run difference D_jr = mean_t(y_Q − y_B). Task×run rows are never treated as independent.
- Cells are model × method (GPTQ/AWQ-W4) × checkpoint (d1–d4).
- Pre-declared equal-weight pools: model×method, model, method across models, and all.
- **Standard errors.** Pooled within-cell run variance, with df = Σ(R_j − 1) = 15 per model. Pools add the shared-BF16 covariance, σ²_u from Henderson III on D_jr = θ_j + u_ν + e, floored at 0 inside the SE only. Across models, Welch df.
- **Tests.**
  - Non-inferiority passes iff the one-sided 95% lower bound is > −ε.
  - TOST passes iff the 90% CI lies inside (−ε, ε).
  - The ordinary two-sided test is reported separately.
  - ε = 3 pp is primary and 5 pp a sensitivity analysis.
- **Task-level effect sizes** per cell:
  - Δ̂, and the U-statistic D̂ over independent replicate blocks. Only cross-block products enter, so the coupled same-nonce products are excluded by construction.
  - Δ²_U and V̂ = D̂ − Δ²_U. Negatives are kept.
  - Cross-check: the Hamming form D_H = H_QB − (H_QQ + H_BB)/2 over distinct blocks equals D̂ to machine precision in every dev cell (an algebraic identity, so this checks the implementation). An extended Hamming form uses all same-model BF16 draws.
- **Generalisation** (separate analysis). Task-id-clustered crossed resampling: tasks are resampled and shared across the model's cells; nonces get Poisson(1) weights, also shared. B = 2000.
- **Secondary cells** (outside the pools): RTN-W4, rotated BF16 (numerics control), and Gaussian k=1 fixed seeds. The Gaussian seeds are a control intervention, not a no-change null.

**Modes.**
- Real mode refuses until all 10 `a6k2_{q4,q8}_bfpair_q{1..5}` runs are admitted with their registered nonces. It was tested and refuses on the current snapshot.
- `--dev` substitutes `null_n<k>` for `bfpair_q<k>`. Those pairs are **not** nonce-paired. Output `out/success_ni_DEV_20260930T0044Z.json` is labelled "development only, NOT a result". No dev number is quoted as a finding.
- `--with-fdev` is a declared sensitivity analysis that adds the fork development blocks f01–f17 (W29a) where admitted.

**ε justification (written 2026-09-30, before any `bfpair` outcome exists).**
- The dev task set is about 85 tasks (q4: 84), so 3 pp is about 3 task outcomes out of 100: a change of about 2.5 tasks per run.
- The run-level nonce SD within a checkpoint (W25 A13) is 2.5 pp on q4 and 2.9 pp on q8. A margin below one nonce SD would be unreachable with 2–5 paired blocks per checkpoint. A 5 pp margin sits at the size of the largest observed W4 checkpoint effect (q8 AWQ-W4 d3: +5.3 pp on average, +8.2 pp on q2), so it could not flag such a checkpoint as non-negligible.
- The review fixed g_min = 3 pp for the fork study (§F). Using the same margin keeps "negligible" consistent across the paper.
- 5 pp is a looser sensitivity analysis only and never replaces 3 pp.
- A pooled pass implies nothing about individual models or methods (§F).

### B4. Reference controls — **partly addressed**

`success_ni` reports RTN-W4, rotated BF16 and the Gaussian k=1 fixed checkpoints as separate secondary cells, using the same paired machinery. Identical-setting repeats and a BF16-vs-BF16 nonce control with the same pairing, and a stratified floor table that flags single canonical-run floors, are **not done here**. They remain open for the fork protocol.

## 2. Measurement issues (review §C)

| # | Location | Verified | Fix (where) | Old vs corrected |
|---|---|---|---|---|
| C1 | `openloop_topk.p_act` | Yes: `sum(math.exp(l) for t, l in zip(ids, lps) if t in start ...)` counts a tool-start token outside the top-20 as 0 | `p_act_bounds` gives the lower bound, the upper bound (+p_k per missing start token) and a missing flag. Schema v2 adds mean bounds, the missing fraction and Δlogit bounds. The generated-class cross-check is under C9 (`scripts/a6000/openloop_topk.py`; `--schema 2` → `<cell>.v2.json`; schema-1 `.json` untouched, worker default stays 1) | Over all 50 cells, mean P(act) upper − lower < 0.001 (the 20th logprob is tiny), so no schema-1 mean moves in the 3rd decimal. The missing flag is frequent: 17–34% of q4 positions and 4–22% of q8/q14/q32 positions for W4/Gaussian cells, and 45–64% for RTN-W3. Mean Δlogit bounds widen, e.g. q4 RTN-W4 −0.90 → [−0.95, −0.81] and q4 RTN-W3 −7.77 → [−7.82, −5.98] |
| C2 | `topk_kl` | Yes: tokens missing on one side are imputed at that side's k-th logprob, then called KL | Kept unchanged as `approx_topk_kl_*` in v2. New `coarse_kl_*`: the exact KL over tokens known on both sides plus one residual category, a lower bound on the true KL (data processing) | Median coarse ≈ approx in every cell (q4 RTN-W4 0.0078 vs 0.0086; q32 RTN-W3 1.29 vs 1.49); means within 1–4%. Rankings unchanged |
| C3 | `name_mass` | Yes: prefix-tree estimate; alternatives outside the top-k are missing and completion is forced | Demoted to `name_mass_proxy_*` / `name_switch_rate_proxy`. Measured error terms: `name_mass_unassigned_mean` (1 − Σ est) and `name_switch_upper_bound` (P(BF16 name) < 0.5, where P(BF16 name) is exact by teacher forcing). The main tool metric is the fully generated and parsed name and arguments (fork study) | Unassigned mass ≤ 0.004 except RTN-W3 (q8 0.007, q4 0.025). Upper bound − proxy ≤ 0.021 for W4 cells (q4 RTN-W4 0.108 / 0.108; q8 RTN-W4 0.119 / 0.136) |
| C4 | `common4._feat_traj` `confirm_bw` | Yes: regex on the agent's own text (`'?' and confirm\|proceed\|yes\|...`); no user reply, policy or state check | Renamed `confirm_request_proxy` in DISP (same position and values). `confirm_bw` is still emitted as an alias; feature caches are versioned (`.traj.v2.pkl`) so stale pickles cannot silently return NaN (`analysis/insights/iter_4/common4.py`) | Values identical: `h3_corrected` re-run after the rename gives identical results; alias identity is checked on 17,996 episodes (`out/tool_types_features_20260930T0044Z.json`). Real authorisation or violation judgement is not implemented (it needs user reply, tool rules and state) |
| C5 | Write classification | Yes: `common4.WRITE_RE = ^(cancel\|modify\|return\|exchange\|book\|update\|send)`; `iter_2/common.WRITE_RE` adds `transfer` (a handoff counted as a write) | Explicit table from tau2 `@is_tool(ToolType.X)`: read / write / handoff / other (calculate) / invalid (not an agent tool of the domain; `think` is commented out in tau2, so a think call is invalid). `--check` re-derives it by AST and matches. New exploratory features `any_write_t`, `n_write_t`, `invalid_rate`, `read_rate`, `handoff` (`analysis/insights/iter_4/tool_types.py`, `out/tool_types.json`) | Retail/airline: the regex equals the table on valid names. Over q4/q8 episodes, `any_write` agrees 99.98% and `n_write` 99.73%; the differences are hallucinated write-like names. 1.6% of episodes contain an invalid call. **Telecom: the regex misses 5 of 6 write tools** (suspend/resume_line, enable/disable_roaming, refuel_data), so the table must be used for the telecom holdout |
| C6 | `divergence.analyze_task` | Yes: it compares two independent closed-loop trajectories. After the first prompt difference the two decisions no longer share a history (`t_context`), so it cannot serve as a same-state causal fork | Not changed here (fork protocol: both precisions queried on the same saved history; `cloq/fork.py`, other session) | — |
| C7 | `cloq/nl_judge.py` | Checked. It monkey-patches the module-global `tau2.evaluator.evaluator_nl_assertions.generate` inside a ThreadPoolExecutor (default concurrency 8), which is not thread-safe: the capture dict (`judge_raw`) and the expectedOutcome fallback can come from another thread; the judged messages are the right ones because they are passed as arguments | **Unused in scoring.** No a6k2/a6000 script calls it, no `nl_judge.jsonl` or `task_success.json` exists under `runs/` or `cloq_work/`, and every a6k2 analysis uses DB success. It is referenced only by the legacy 4080 shell pipelines (`scripts/pipeline*.sh`, `extras.sh`, `bf16_replicate.sh`) and `cloq/report.py`. Noted and left unchanged. If it is ever used, make it serial or inject the judge per call | — |
| C8 | `metrics.task_success` | Yes: named "success" but it is the DB end-state match for retail/airline. tau2's official rewards are retail DB×NL_ASSERTION (112 of 114 tasks) and airline DB×COMMUNICATE (50 of 50). Telecom uses `official_reward == 1`: the product over the task's own basis, ENV_ASSERTION (2253 of 2285 tasks) or ENV_ASSERTION×ACTION (32); deterministic, premature = 0 | This **is** tau2's official telecom success. `ENDPOINT_NAME`, `db_success()` and `official_basis_success()` added; behaviour of `task_success` unchanged (`cloq/metrics.py`) | Naming only. The paper must say "DB success" for retail/airline and report COMMUNICATE / official separately |

### C9. Selection effect in the act/talk shift conditional on BF16's choice — **confirmed** (`analysis/insights/iter_4/act_talk_selection.py`)

- **The problem.** P(act | BF16 acted) and P(act | BF16 talked) condition on BF16's own argmax. That selects positions where BF16's P(act) is near 1 or 0, so any perturbation, even a sign-symmetric one, pulls both means toward the middle.
- **The null.** Per decision, the script computes the expectation under a sign-symmetric perturbation of the cell's own |Δlogit|, over the first token of every BF16 decision (`first_all`).
- **Unconditional quantities.** It also reports ΔP(act), Δlogit and the argmax change.

| Cell (first_all) | P(act \| acted) / P(act \| talked) | Sign-symmetric expectation | Excess (directional part) | Unconditional ΔP(act) |
|---|---|---|---|---|
| q4 BF16 | 0.957 / 0.014 | — | — | 0 |
| q4 RTN-W4 | 0.844 / 0.088 | 0.894 / 0.080 | −0.050 / +0.008 | −0.028 |
| q4 GPTQ-W4 d1–d4 | 0.92–0.95 / 0.035–0.045 | 0.936–0.941 / 0.037–0.046 | −0.013 to +0.008 | −0.007 to +0.005 |
| q4 AWQ-W4 d1–d4 | 0.79–0.84 / 0.024–0.039 | 0.88–0.91 / 0.059–0.065 | −0.06 to −0.09 / −0.02 to −0.04 | −0.05 to −0.08 |
| q4 Gaussian k=1 (4 seeds), gshape, rtnsign | 0.67–0.87 / 0.02–0.19 | — | act −0.02 to −0.15 | −0.15 to +0.04 |
| q8 GPTQ / AWQ / RTN-W4 | 0.91–0.95 / 0.82–0.85 / 0.91 | — | small, toward talk | −0.04 to 0.00 / −0.07 to −0.10 / −0.02 |
| q8 Gaussian, gshape, rtnsign | — | — | — | −0.10 to +0.04 |

- **The "blurring" is mostly size.** The rise of P(act | talked) under RTN-W4 (0.014 → 0.088) is fully explained by the sign-symmetric null (0.080). The remaining directional component is a small net shift toward talk. That shift is larger under AWQ than under GPTQ, and size-matched random perturbations produce shifts of the same or larger size.
- **Cross-check against the generated action class.**
  - BF16: first-token class = generated class for 99.0% (q4), 99.8% (q14), 99.2% (q32) and 100% (q8) of decisions.
  - Gaussian cells on identical contexts (86–168 decisions each): top-k argmax class = generated class for 87–100%.
  - For quantizer cells no generated action on an identical context exists, so they need the fork study.

## 3. Claims in `docs/insights/STORYLINE_v6.md` affected

- **B3 "persistent behavioural fingerprint, confirmed (pre-registered)":** no longer valid as stated.
  - The pre-registered test was invalid, with a type-I error of about 0.33–0.42.
  - Corrected, the pooled fingerprint is post-hoc significant (p 0.013), and nearly all of it comes from the random Gaussian checkpoints.
  - For quantizer recalibrations the fingerprint is **not detected** (RECAL p 0.30; within-method p 0.19; J = 2 blocks cannot reach p < 0.5).
  - Suggested wording: "fixed random weight perturbations leave a persistent behavioural fingerprint (post-hoc corrected test); for W4 quantizer recalibrations a fingerprint was not detected".
- **B4 "fingerprint generic to fixed weight perturbations; random ≥ quantizers":** strengthened in direction (RAND is 90% of the corrected F), but it now rests on a post-hoc test.
- **B5 "act-vs-talk is blurred":** replace with the unconditional quantity. W4 quantizers shift the first-token act/talk propensity unconditionally by −0.10 to +0.005 on q4/q8, mostly toward talk; the other models differ in sign (q14 AWQ +0.09, q32 RTN-W4 −0.18). The conditional "blurring" is largely a selection effect of the perturbation's size, and random controls move it as much or more.
- **Line A (lottery):** unchanged. The crossed correction leaves the H1 p at 0.744, and φ stays 0.33–0.47.
- **Variance statement "checkpoint SD 3.65 pp vs nonce 2.51 pp, method ≈ 0":** in the crossed model, q4 residual (nonce×checkpoint + run) is 2.62 pp, checkpoint 3.69 pp, the nonce main effect −0.86 signed, and method not estimable (1 df; signed −2.07). The method "≈ 0" was a truncation; say "not estimable".
- **B1 "success-equivalence":** still untested. `success_ni` real mode waits for `bfpair`. The new-task generalisation interval (task-clustered) is much wider than the fixed-task one, about ±4 pp for the all-model pool in dev mode, so equivalence for new tasks at 3 pp is unlikely with the current task count.
- **"q4 range +1.5 to +3.9 pp":** q4 only, as the review says (not re-examined here).

## 4. Reproduce
```
source scripts/a6000/env.sh; cd analysis/insights/iter_4
S=/data/ziyangs/cloq/analysis/insights/iter_3/out/snapshot_live_20260930T0044Z.json
python h3_corrected.py --snapshot $S                                  # out/h3_corrected_20260930T0044Z.json
python h3_corrected.py --snapshot $S --sim --n-sim 2000 --deltas 0,0.01,0.02,0.03,0.05   # out/h3_corrected_sim_*.json
python h3_corrected.py --snapshot $S --sim --n-sim 2000 --deltas 0 --sim-split 100 --sim-B 499
python h3_corrected.py --snapshot $S --sim --n-sim 6000 --deltas 0 --sim-B 99 --sim-seed 777
python p1_crossed.py --snapshot $S                                    # out/p1_crossed_20260930T0044Z.json
python success_ni.py --dev --snapshot $S                              # out/success_ni_DEV_20260930T0044Z.json (NOT a result)
python success_ni.py --snapshot <fresh snapshot with bfpair>          # real mode (refuses until bfpair is admitted)
python act_talk_selection.py --snapshot $S                            # out/act_talk_selection_20260930T0044Z.json
python tool_types.py --check; python tool_types.py --feature-check $S
cd /data/ziyangs/cloq; for f in analysis/openloop/a6k2/*/topk/*.npz; do o=${f%.npz}; m=$(echo $f | cut -d/ -f4)
  python scripts/a6000/openloop_topk.py --resummarize $o --schema 2 --ref analysis/openloop/a6k2/$m/topk/bf16; done
```
