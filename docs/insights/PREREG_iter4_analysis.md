**TL;DR** This file documents `analysis/insights/iter_4/prereg_h1_h4.py`, the confirmatory analysis script for `docs/insights/PREREG_iter4.md` (sha256[:16] `0d5e8385c911824f`, checked by the script). It was written and debugged only on non-confirmatory stand-in checkpoints (`--dev`). No closed-loop outcome of a confirmatory run was computed, printed or opened. The PREREG left some points open; the script's resolutions are listed as A1–A18 below, and each should be logged as a §7 amendment **before** the confirmatory snapshot is taken. The dev output is `analysis/insights/iter_4/out/prereg_h1_h4_DEV.{json,log}`.

# Confirmatory analysis script for PREREG iter4

## How to run

Take the confirmatory run in this order, once:

1. Commit this script, plus any amendment commits (A16). Do this *before* the snapshot exists.
2. Build a fresh integrity snapshot: `python analysis/insights/iter_2/integrity.py --out analysis/insights/iter_3/out/snapshot_live_<utc>.json`.
3. Run the analysis:
   ```
   source scripts/a6000/env.sh
   cd analysis/insights/iter_4
   python prereg_h1_h4.py --snapshot /data/ziyangs/cloq/analysis/insights/iter_3/out/snapshot_live_<utc>.json
   ```
   Output: `out/prereg_h1_h4_CONF_<snapshot id>.json`. Only the final table goes to stdout.

**Refusal conditions.** Confirmatory mode (the default) refuses to run if any of the following holds:
- (a) The PREREG sha256 does not start with `0d5e8385c911824f`.
- (b) One of the 28 confirmatory runs (A1) is not admitted in the snapshot with both domains and its registered nonce (q1 = 6d1f0b3e, q2 = f07a5c21).
- (d) An earlier snapshot under `analysis/insights/*/out/` already admitted all 28 runs. The override is `--allow-later-snapshot`, and it is recorded in the output.
- (c) The script has uncommitted changes, or its last commit is not earlier than the snapshot's utc.
- (e) The output file already exists. The analysis runs once.
- The caller changes `--B` or `--n-split`.

**Deadline mode.** `--deadline-mode` (PREREG §5) is accepted only when both today's UTC date and the snapshot date are 2026-10-05 or later. In that mode the analysis uses every checkpoint that has both draws admitted, and it records which runs were excluded.

**Dev mode.** Dev mode runs on stand-ins:
```
python prereg_h1_h4.py --dev --snapshot /data/ziyangs/cloq/analysis/insights/iter_3/out/snapshot_live_20260929T1937Z.json
```
- RECAL stand-ins: `gptq_w4_d1` (n1, n2), `gptq_w4_d2` (n1, n2), `awq_w4` (n1, n2) and `awq_w4_d2` (q1, q2).
- RAND stand-ins: `gauss1_s1` fixed, `gshape_w4` and `rtnsign_w4` (q1, q2).
- Models: q4 and q8.
- The variance components leave out d3/d4 and gauss s2/s4/s5.

A guard raises an error if dev mode touches any confirmatory run id. The run takes about 10 s on the login node, and all RNG is seeded (`SEED = 20261005`, one named stream per analysis).

## What dev mode checked

- **Script completes and output is reproducible.** The script runs end to end. Two runs produce identical JSON apart from the timestamp.
- **Δ matches p2_dispositions.** The per-draw Δ of every stand-in draw equals `p2_dispositions_live_20260929T1937Z.json` `delta_A/B` to 4 decimals. The task sets are also the same: q4 84 tasks (airline 45 out), q8 85 tasks.
- **Null calibration on synthetic data.** Each test was run on 300 null simulations for H1–H3 and about 80–150 for H4.

  | Test | P(p < 0.05) |
  |---|---|
  | H1 | 0.050 |
  | H2 | 0.033 (exact test, discrete, slightly conservative) |
  | H3 | 0.050 |
  | H4 | 0.06–0.10 |

  The first H4 version was miscalibrated at 0.51 because relabellings with an undefined φ (E_indep ≤ 0) were compared as NaN. This is fixed as A10.
- **Refusal paths.** Tested on a synthetic empty snapshot: not admitted, deadline before 10-05, changed B, and an edited PREREG copy. None of these tests touches real data.

**Stand-in numbers (NOT confirmatory; illustration only).**

| Test | Estimate | p | p (Holm) |
|---|---|---|---|
| H1 | φ = 2.99 | 0.102 | 0.204 |
| H2 | r = 0.62 | 0.104 (exact, 576 relabellings) | 0.204 |
| H3 | F_split = 0.193 | 0.0014 | 0.0042 |
| H4 | φ_RECAL − φ_RAND = 4.49 | 0.238, 95% CI [−4.47, 17.91] | outside Holm |

Variance components on the stand-ins (d1/d2 only), in pp SD of Δ:

| Model | Method | Checkpoint | Nonce |
|---|---|---|---|
| q4 | 0 | 5.9 | 2.6 |
| q8 | 1.1 | 1.7 | 3.1 |

## Ambiguities resolved (log as §7 amendments)

**A1. Run count**
- §1 says "20 checkpoints × 2 draws = 40 runs", but the units it enumerates add up to 14 checkpoints: RECAL has 2 methods × d3/d4 × 2 models = 8, and RAND has 3 seeds × 2 models = 6. That is 28 runs.
- W19 also queued 16 + 12 = 28.
- The script requires exactly these 28 enumerated runs.

**A2. Run ids**
- §1 gives *queue task* ids. The run ids the script uses come from `scripts/a6000/make_tasks_iter4.py`:
  - RAND: `a6k2_{q4,q8}_churnctl_k1_s{2,4,5}` runs as `a6k2_<m>_gauss1_s<s>_q{1,2}`.
  - RECAL: `a6k2_<m>_{gptq,awq}_w4_d{3,4}_q{1,2}`.
- In confirmatory mode the nonces are checked against the snapshot.

**A3. φ null**
- §2 describes the null as "permutation of draw labels across checkpoints within (model, set)", and also says the P1 estimator is "applied unchanged".
- The script uses the P1 null unchanged (`p1_overdispersion.perm_T`): within each task, the checkpoint labels of the (y_q1, y_q2) pair are permuted, with B = 5000.
- It tests T = Σ(J−1)·sig_ck against its permutation distribution, which is the independent-landing expectation. This is P1's operationalisation of "φ > 1".

**A4. H1 pooling**
- "Sum of per-model numerators / sum of denominators" is implemented with P1's (J−1) weights.
- This is identical to the plain sum when both models have J = 4, so it matters only in deadline mode.

**A5. Task set**
- Tasks are the complete case over:
  - the eligible nonce null (null_n1–n8 with ≥ 77 tasks, NR1-2);
  - both draws of every confirmatory checkpoint of that model.
- q4 airline 45 is removed explicitly (W17).
- An infra-missing episode drops that task for the whole model, as P1 does.
- The variance components use their own complete case, which also includes the d1/d2 draws.

**A6. Δ reference**
- The reference is U minus the draw's nonce-mate (NR1-3).
- q1 and q2 are fresh nonces, so for confirmatory draws this is all of n1–n8.
- The outcome is iter_2 `common.outcomes`: db_match AND not premature. infrastructure_error counts as missing, and a context overflow counts as a failure (W10).

**A7. H2 permutation**
- The PREREG gives no B for H2. The script enumerates all within-model relabellings of q2 exactly (4!·4! = 576).
- The p-value includes the identity, so p_min = 1/576.
- The same rule applies throughout: exact enumeration whenever the number of relabellings is ≤ B = 5000, Monte Carlo B otherwise.

**A8. H3 details**
The PREREG leaves five parts of the H3 computation open. The script resolves them as follows:
- (i) **Scaling.** Scaling uses P2's sd_w, the pooled within-checkpoint nonce SD. It is computed *per split* from the split shift vectors (q1 on H, q2 on the complement Hᶜ) over all confirmatory units of the model, both sets. It is held fixed under permutation. Features with sd_w = 0 are zero-filled (P2).
- (ii) **Halves.** The halves are ⌊N/2⌋ and ⌈N/2⌉: q4 42/42, q8 42/43.
- (iii) **Split draws.** The 100 splits are drawn independently per model and shared by that model's two sets.
- (iv) **Averaging.** Each block's cosine matrix is averaged over the 100 splits. F is then the J-weighted mean, over the 4 (model, set) blocks, of same-checkpoint minus different-checkpoint cosine (P2 pooling). This equals the mean of per-split F whenever no cosine is undefined.
- (v) **Permutation.** The permutation shuffles the q2-side checkpoint labels within each block, applying the same permutation to all splits. It is Monte Carlo with B = 5000, because 4!·3!·4!·3! = 20,736 > B.

**A9. H4 test and CI**
- The test enumerates the RECAL/RAND labels exactly within each model: C(7,4)² = 1225 relabellings.
- p is two-sided: p = min(1, 2·min(one-sided p)).
- The PREREG gives no method for the CI. The script uses a percentile CI from a task bootstrap within model, with B = 2000.

**A10. Undefined φ**
- φ is undefined when E_indep ≤ 0. P1 returns NaN in that case.
- For H4, relabellings where either φ is undefined are excluded, which makes it a conditional permutation test. `n_defined` is reported.
- For H1 the P1 test is on T, so p stays defined even when φ is not.
- Secondary per-model φ_RAND can be undefined; it is reported as null.

**A11. §4 per model and per domain**
- "Per model" means both domains together; "per domain" means both models pooled. There are no model × domain cells.
- None of the secondary analyses is Holm-adjusted.

**A12. Sensitivity**
- "Exclude episodes ending in max_steps / context overflow" is implemented as follows:
  - For confirmatory draws, a task is dropped for the whole model if any confirmatory draw of that model ended that way. This is needed because φ and F need complete matrices.
  - For null draws, the affected episodes are left out of the null mean for Δ.
- This applies to H1–H4.

**A13. Variance components**
- The estimator is nested method-of-moments on Δ, computed per model and then averaged over models:
  - nonce = pooled within-checkpoint variance;
  - checkpoint = variance of checkpoint means within method, minus nonce·mean(1/n);
  - method = variance of method means, minus mean(raw checkpoint-mean variance / K).
- Draws: every admitted draw of GPTQ-W4 d1 (n1, n2, q3–q5), d2 (n1, n2), d3 and d4; and of AWQ-W4 d1 = `awq_w4` (n1, n2, q3–q5), d2 (q1–q3), d3 and d4.
- A variant adds Gaussian k=1 seeds s1–s5 as a third "method".
- With 2 methods, the method component has only 1 df per model.

**A14. Open-loop predictors**
- The §4 bullet on open-loop predictors (E3, E4-2) is **not** implemented in this script. It needs a separate analysis.
- Its inputs are predictors that were produced before the outcomes, so running it later does not break blinding.

**A15. "Analysis runs once on the first snapshot"**
- The script enforces this with refusal conditions (b)–(e) above. `--allow-later-snapshot` is the only override, and it is recorded.

**A16. Amendments and the PREREG hash**
- The hash guard is exact, so writing an amendment into §7 changes the hash and makes the script refuse.
- To log A1–A18, the main session should:
  1. add them to §7;
  2. update `PREREG_SHA16` in the script, in the same commit or a separate one, recording the new hash in RESEARCH_LOG;
  3. take the confirmatory snapshot only after that commit, so that guard (c) passes.

**A17. H3 blocks**
- "Within (model, set)" is read as 4 blocks: q4 RECAL, q4 RAND, q8 RECAL and q8 RAND.

**A18. H2 centring**
- Δ(q1) and Δ(q2) are each centred per model: the mean over that model's RECAL checkpoints is subtracted from each.
- The centred values are then pooled, and the Pearson r is computed on the pooled values.

## Evidence
- Script: `analysis/insights/iter_4/prereg_h1_h4.py`.
- Dev output: `analysis/insights/iter_4/out/prereg_h1_h4_DEV.{json,log}`.
- Stand-in cross-check: `analysis/insights/iter_4/out/p2_dispositions_live_20260929T1937Z.json`.
- Run ids: `scripts/a6000/make_tasks_iter4.py`.
