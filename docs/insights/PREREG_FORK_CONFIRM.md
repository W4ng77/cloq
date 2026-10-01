# PREREG_FORK_CONFIRM — confirmatory protocol for the telecom holdout (same-state 2×2 forks)

> **DRAFT — not frozen; freezing = author approval + sha256 recorded in manifests/fork/splits_v1.json holdout.prereg_sha256 before any holdout unit is run.**
>
> Drafted 2026-10-01 (W85) by merging FORK_PROTOCOL §12, §12 amendment 1 (W80) and GPT-6.1 review 4's holdout points
> (`outputs/gpt61-review4-response-review.md`, point 6). No holdout unit has been run, and no holdout outcome, trajectory or
> task text was read in drafting it. The only holdout-adjacent input is the planning simulation on telecom **dev** data
> (`analysis/fork/out/holdout_k_planning_20261001T134838Z.{json,md}`). Items marked **[AUTHOR]** are open decisions (§14).
> Until frozen, this text may change; after freezing, changes are numbered amendments dated before the first holdout unit,
> or labelled deviations after it.

---

## 0. TL;DR

- **Population:** the 34 telecom holdout tasks (`manifests/fork/splits_v1.json` → `splits.holdout.tasks.telecom`).
  **Cells:** q4 GPTQ-W4 d1, q8 GPTQ-W4 d1 and q8 AWQ-W4 d1, with equal weights 1/3 **[AUTHOR]**.
  **Blocks:** K = 12 fresh nonce blocks h01–h12, shared by all cells and by the BF16 pair runs; halves are fixed by hash.
  The matrix is 34 × 12 × 3 = 1,224 units.
- **Primary:** G_all = E[Y_BQ − Y_QQ], task-equal. The interval is a t over the 12 block means (df 11). The EXTERNAL_REVIEW §F
  decision bounds are ±3 pp. G_all is the sole member of the primary family, at one-sided α = 0.05.
- **Secondaries** (each its own family at α = 0.05, never used to rescue the primary):
  - **S1:** two-sided consequence replication (r > 0 and d > 0; intersection–union).
  - **S2:** cross-half repeatability of task fragility. The statistic is ρ, the equal-weight mean over estimable cells of
    Spearman(m_A, m_B). It is tested one-sided by a persona-stratified permutation; there is **no** "≥ 10 flipping tasks" screen.
  - **Strata:** Holm within each strata family.
- **Planning (dev only):** at K = 12, the 90% CI width of G_all is ≈ 3.6 pp (t over blocks) and ≈ 3.7 pp (crossed). S2 has
  power ≈ 1.00 at the fitted dev task heterogeneity, and 0.76 with that heterogeneity halved, which is below its 95% profile
  lower bound. Size is 0.03–0.06. The K = 6 figures are 5.7 pp, 0.99 and 0.46.
- **Cost:** about 96 GPU-h (67–144), with a conservative estimate of 195 GPU-h.
- **Dev results are not retroactively confirmed (§13).**

## 1. Claims under test and their scope

1. **Primary (C1).** On new telecom tasks, the same-state replacement of a quantized model's first divergent action by BF16's
   action (the G policy) changes task success by G_all. The readings are those of §6.
2. **Secondary (C2).** Outcome-changing divergences on new tasks are two-sided: both rescues (r) and damages (d) occur.
3. **Secondary (C3).** Repeatability on new tasks: a holdout task that flips under quantization in one set of nonce blocks also
   tends to flip in an independent set of nonce blocks.
   - The honest description of the test is: *real task pairing is more consistent than persona-preserving random task pairing.*
   - It does **not** rule out all difficulty explanations. A task property correlated with flip propensity within persona,
     such as fault load, issue type or BF16 difficulty, would also produce ρ > 0.
   - C3 makes **no** "beyond difficulty" claim (cf. W78) and is not a transfer test of a dev-defined task score: dev task IDs do
     not occur in the holdout.
4. **Not claimed.**
   - No generalisation beyond telecom.
   - No generalisation beyond these three model × method cells.
   - No claim that holds over a new task distribution beyond the stratified telecom base split.
   - 34 tasks limit task-level generalisation, and more blocks do not substitute for more tasks.
   - Few events mean limited evidence, not absence of an effect.

## 2. Population, cells and weights

- **Tasks.**
  - The holdout consists of the 34 telecom base-split tasks not in `manifests/telecom/dev_v1.json` (stratified rule in that file).
  - The list is the one in `manifests/fork/splits_v1.json` and is not reproduced here.
  - Persona (Hard / None / Easy) is parsed from the task id (`PERSONA:<x>`).
  - The evaluator is the official telecom success (`official_reward == 1`), as on dev (FORK_PROTOCOL §4).
- **Cells.** Checkpoints follow the `primary_checkpoint_rule` of `manifests/fork/dev_blocks_v1.json` (calibration draw c1).
  **[AUTHOR]: confirm the 3 cells.**

  | id | model | method | checkpoint | weight | telecom dev forks? |
  |---|---|---|---|---|---|
  | c1 | q4 | GPTQ-W4 | d1 (c1) | 1/3 | **no** (closed-loop f01–f06 runs exist; no forks) |
  | c2 | q8 | GPTQ-W4 | d1 (c1) | 1/3 | yes (f01–f06, 80 tasks, complete) |
  | c3 | q8 | AWQ-W4 | d1 (c1) | 1/3 | yes (f01–f06, 80 tasks, complete) |

- **Why these three.**
  - They are the W4 primary cells of the dev design (dev_blocks_v1).
  - c2 and c3 are the only cells with a telecom dev fork history: the planning simulation and the stratum cut points rest on them.
  - c1 adds a second model, so C1–C3 are not a single-model statement.
  - Equal weights make G_all a cell-average estimand that does not depend on per-cell divergence counts.
- **Flags for the author.**
  - (a) c1 has no telecom dev fork data. Its planning parameters are borrowed from c2, and its first telecom forks would be
    holdout forks. The alternative is to replace c1 with q4 AWQ-W4. That changes nothing in the issue, since q4 AWQ has no
    telecom forks either, and its f01 closed-loop run had an outage.
  - (b) On dev, the task effects of c2 and c3 correlate at ρ_u = 0.80 (fitted). Two-thirds of G_all's weight is therefore one
    model, q8, and S2 is close to two looks at one task ordering for q8.
  - (c) An alternative weighting is 1/2 per model (q4: c1; q8: (c2 + c3)/2). Choose one before freezing.
- Per-cell G, r, d, M and ρ_c are reported for every cell as **descriptive** components. A pooled pass does not imply a per-cell
  pass (EXTERNAL_REVIEW §F).

## 3. Blocks, nonces and the split into halves

- **K = 12, fixed.**
  - The budget target is GPT-6.1 review 4's: 6 + 6 halves give 7 rate levels per task and half, against 4 for K = 6.
  - The dev planning simulation confirms adequacy (§11). K was not chosen from it.
- **Nonce rule.**
  - nonce(h_n) = sha256("cloq-fork-holdout-v1|" + str(k))[:8] for k = 0, 1, …, skipping any nonce already used by a run.
  - At drafting, the 30 `prompt_nonce` values in `runs/*/*/environment.json` were checked and none was skipped.
  - Re-check the rule at freeze **[AUTHOR]**.
  - Reserve blocks h13 and h14 are used only under §4.
- **Halves.** H_A is the first K/2 = 6 block ids in ascending order of sha256("holdout-split-v1|" + block_id); H_B is the rest.
  The rule is §12 amendment 1's.

| block | k | nonce | sha256("holdout-split-v1\|id")[:12] | half |
|---|---|---|---|---|
| h01 | 0 | 18bf2ee3 | 4a3108b69e2a | H_A |
| h02 | 1 | 66d4bb88 | 9cd294718b77 | H_B |
| h03 | 2 | 2e4fb169 | defe56b16729 | H_B |
| h04 | 3 | fadf7cf5 | 20e7cca605b8 | H_A |
| h05 | 4 | 2a5b0348 | 76e47e5eb901 | H_A |
| h06 | 5 | 5b3494c6 | cc54f75c8504 | H_B |
| h07 | 6 | 04b40ec0 | b68bceb4910d | H_B |
| h08 | 7 | 76ea129b | cc2a83bf4708 | H_B |
| h09 | 8 | 9537c607 | 68d9464fa8f5 | H_A |
| h10 | 9 | fb34253c | c267c361ed4d | H_B |
| h11 | 10 | a8daaa2a | 085986edce30 | H_A |
| h12 | 11 | 103c78cc | 5dbda182f71d | H_A |
| h13 (reserve) | 12 | computed at freeze, same rule | — | inherits the replaced block's half |
| h14 (reserve) | 13 | computed at freeze, same rule | — | inherits the replaced block's half |

- **Per block.**
  - Closed-loop runs: `a6k2_{q4,q8}_tel_bfpair_hNN` (BF16 pair), `a6k2_q4_tel_gptq_w4_d1_hNN`, `a6k2_q8_tel_gptq_w4_d1_hNN`
    and `a6k2_q8_tel_awq_w4_hNN`.
  - All use `task_file` holdout, the block's nonce, and the run configuration of the telecom dev blocks f01–f06
    (`scripts/a6000/make_tasks_fork_dev2.py`), with only the nonce and the task list changed.
  - Forks: fork-v1, deterministic protocol A (FORK_PROTOCOL §3–§6c), first primary semantic divergence, the same spec as
    `analysis/fork/telecom/*/search.json`.
  - Output goes to `analysis/fork/holdout/<model>_<cell>/<group>/`.
  - Block ids match `analyze_dev.RUN_RE` (`h\d+`).
- **Queue.** Nothing is queued before freezing. Freezing is the gate for both running and reading.

## 4. Completeness and repair (outcome-blind)

The analysis matrix is **complete by design**: 34 tasks × 12 blocks × 3 cells. The analysis is not run until the matrix is
complete or the repair budget below is exhausted.

1. **Unit statuses.**
   - `divergent` with Y_BB, Y_BQ, Y_QB and Y_QQ all present.
   - `no_divergence`, which counts with G = r = d = M = 0.
   - `missing`.
   - Agent-side context overflow and other deterministic in-episode failures are valid outcomes (W10), not misses.
2. **Infrastructure misses are repaired before any analysis.** These are server or simulator outage, a node kill, a branch
   error, branches pending, a closed-loop run-domain outage, and a QQ no-op mismatch traced to infrastructure.
   - The unit is re-executed with the same nonce and state: a fork `repair` task (W70) or a closed-loop re-run of the run-domain.
   - The limit is 3 attempts per unit.
   - The operator sees only status and missing reason, never Y.
   - Repairs are logged in `analysis/fork/holdout/REPAIR_LOG.jsonl`.
3. **Structural exclusions** cannot be repaired, because they are deterministic. Examples are a B-side prompt-id mismatch at
   the divergence search (§3.1 of FORK_PROTOCOL) and a reproducible QQ no-op mismatch.
   - The **task** is excluded from **that cell in all 12 blocks**, so blocks stay complete and shared, and this is reported.
   - The cell's denominator becomes 34 − n_excl.
   - If n_excl > 3 in a cell, the cell is reported as compromised. Its G is still in G_all, flagged **[AUTHOR: keep or drop]**.
4. **Unrepairable block.** If a (cell, block) is still incomplete after the repair budget, that block is replaced in **all** cells
   by the next reserve block (h13, then h14), which inherits the replaced block's half.
5. **Fallback.** If more than 2 blocks are unrepairable, the primary uses the complete shared blocks only (K' < 12).
   - Below K' = 8 the result is reported as **not estimable for the decision rules** (descriptive only).
   - S2 requires ≥ 3 complete blocks per half; otherwise it is not estimable.
6. **Sensitivity.** A complete-case run (`--complete-case`, the pre-W70 rule) is reported, labelled as a sensitivity.

## 5. Estimands and denominators

For cell c, task j and block b, Y_xy ∈ {0, 1} is the official success of the branch whose action is from x and suffix from y
(FORK_PROTOCOL §1; sign dictionary in CONSEQUENCE_ANALYSIS_PLAN §2).

- **Unit level.**
  - G = Y_BQ − Y_QQ.
  - r = 1[Y_BQ = 1, Y_QQ = 0], d = 1[Y_BQ = 0, Y_QQ = 1], M = r + d.
  - For no_divergence: G = r = d = M = 0.
- **Cell-block level.** G_{c,b} = (1/n_c) Σ_j G_{c,j,b}, with n_c = 34 − n_excl(c).
  - The estimand is **task-equal**: there is no n_decisions weighting, and no conditioning on divergence.
  - r_{c,b}, d_{c,b} and M_{c,b} are defined on the same denominator.
- **Block level.** G_all,b = Σ_c w_c G_{c,b} with w_c = 1/3. G_all = (1/K) Σ_b G_all,b; r, d and M are defined likewise.
- **Repeatability.** m_A(c, j) = (1/6) Σ_{b ∈ H_A} M_{c,j,b}, which takes 7 levels; m_B is the same over H_B.
- **Conditional-on-divergence quantities** (A, C, I, H, F, the 16 patterns) are descriptive only. They have a different
  denominator and are labelled as such.

## 6. Primary endpoint G_all (family P: {G_all}, one-sided α = 0.05)

- **Interval.**
  - Use the t over the K block means G_all,b, with df K − 1.
  - Report the 90% two-sided interval; its lower end is the one-sided 95% lower bound.
  - This replaces §12's "t only when < 10 blocks" switch. With 12 clusters, a percentile block bootstrap is anti-conservative,
    so the t is primary at any K.
- **Decision readings** (EXTERNAL_REVIEW §F; g_min = 3 pp):
  - **positive gain:** LB > 0.
  - **gain above 3 pp:** LB > +3 pp.
  - **small average effect:** the 90% CI lies inside (−3, +3) pp.
  - **otherwise inconclusive.**

  The three readings are nested statements about one interval, so no multiplicity adjustment applies within family P.
  The ±5 pp version is a labelled sensitivity only.
- **Interval scope.**
  - The t interval treats the 34 tasks as fixed: it is a statement about *these* tasks.
  - The planning simulation shows that it is slightly narrower than the new-task sampling spread. At true G = 3 pp,
    P(90% CI inside ±3 pp) = 0.09, against a nominal ≤ 0.05.
  - The **crossed task × block interval** (analyze_dev's crossed draws) is therefore reported next to it as the
    generalisation-to-new-tasks interval.
  - **[AUTHOR]:** keep the t as the decisional interval, as in §12, or make the crossed interval decisional. GPT-6.1 asked to
    keep G_all and the ±3 pp bounds; it did not ask for a specific interval.
- Per-cell G_c with its own t interval is descriptive (§2).

## 7. Secondary S1: two-sided consequences (family S1, α = 0.05)

- H1 is r > 0 **and** d > 0. Each is tested with a one-sided t over the K block means of r_b and d_b on the §5 denominator.
- S1 passes if both lower bounds are > 0. This is an intersection–union test, so no adjustment is needed.
- M > 0 is implied by S1 and is reported with its interval.
- The stress-cell endpoint C + I of §12 does **not** apply: the holdout has no stress cells. Y_BB − Y_QQ is reference only.

## 8. Secondary S2: cross-half repeatability of task fragility (family S2, one-sided α = 0.05)

This is §12 amendment 1, revised per GPT-6.1 review 4.

1. **Per cell.** ρ_c = Spearman(m_A(c, ·), m_B(c, ·)) over the cell's n_c tasks, with average ranks for ties.
2. **No outcome screen.**
   - The amendment-1 rule "cell not estimable if fewer than 10 tasks have m_A + m_B > 0" is **removed**.
   - The only estimability condition is mathematical: ρ_c is **not estimable** if m_A(c, ·) or m_B(c, ·) is constant.
     Spearman is undefined there.
   - That condition is invariant under any permutation of m_B's task labels. The estimable set is therefore identical in
     every permutation draw, and the screen sits inside the permutation by construction.
   - The implementation still recomputes the estimable set per draw and asserts that it does not change.
3. **Endpoint.** ρ = the equal-weight mean of ρ_c over the estimable cells.
   - If no cell is estimable, the endpoint is reported as **not estimable**, with no claim either way.
   - "Not estimable" is never coded as ρ = 0 and is never read as non-replication.
4. **Test.** One-sided, H1: ρ > 0.
   - Each draw takes one permutation π of task labels within persona stratum (Hard / None / Easy), applies it to m_B of
     **every** cell (the same π across cells), and recomputes ρ.
   - Use 10,000 draws, `numpy.random.default_rng(20261001)`, and p = (1 + #{ρ* ≥ ρ}) / (1 + 10,000).
   - If a task is excluded in only some cells, π acts on the full 34-task label set, and each cell uses its own included tasks.
5. **Reporting.** Report each ρ_c, n_c, the levels used, and the permutation null quantiles.
6. **Exploratory only.**
   - The sign consistency of per-task (r − d) across halves.
   - A within-stratum variant adjusted for fault load or issue type, which would be needed for any difficulty argument.
7. **Planning check (dev only, §11).** Power at K = 12 is ≈ 1.00 at the fitted dev heterogeneity and 0.76 with s_u halved.
   Size is 0.03–0.06.

## 9. Strata (pre-registered secondary families; Holm within each family)

- **Families.** These are the §12 strata known at the fork:
  - remaining step budget at t*;
  - persona (Hard / None / Easy);
  - BF16 task difficulty bin;
  - task length tertile;
  - fault load (issue type, number of injected faults).
- **What is computed.** For each stratum, G_all and r/d/M, with the same intervals as the primary.
- **Holm.** Holm applies within each family over its pre-specified levels. m is the number of pre-specified levels, **not**
  the number of estimable levels.
- **Not estimable.** A stratum with fewer than 2 complete blocks, or with zero variance, is reported as not estimable and
  keeps its place in m.
- **Cut points.**
  - They are fixed on telecom dev only, in `analysis/fork/holdout_cutpoints_v1.json`, which is **to be produced from dev before
    freezing [AUTHOR/TODO]**.
  - Its sha256 is to be recorded in this file.
  - The only cut points not taken from that file are persona and issue type, which are categorical.

## 10. Exploratory (never confirmatory)

- **M1:** the slope of C on the realised remaining horizon. It is confounded by Q's realised trajectory.
- Per-cell q4 versus q8 contrasts.
- Divergence-type breakdowns.
- Direction consistency.
- Bank U style action taxonomy.
- Any comparison of holdout and dev magnitudes.

## 11. Planning precision (telecom dev only; W85)

Source: `analysis/fork/holdout_k_planning.py` → `analysis/fork/out/holdout_k_planning_20261001T134838Z.{json,md}`.

**Model.**
- A logistic GLMM per q8 cell on the 80 × 6 complete dev matrix, with persona intercepts, block effects and a task random effect.
- The fitted task-effect SD s_u is 2.22 [1.73, 2.85] for GPTQ and 1.62 [1.27, 2.09] for AWQ.
- The block-shock SD is 0.57 (GPTQ) and 0.35 (AWQ).
- The task-effect correlation across cells is ρ_u = 0.80.
- The rescue share among consequential units has no detectable task-level heterogeneity: 0.59 for GPTQ, 0.47 for AWQ.

**Simulation.** 34 tasks (persona mix 11/11/12), with c1 borrowing c2's parameters. There were 1,000 replications per K
and 2,000 permutations each.

| K | 90% CI width of G_all, t over blocks | 90% width, crossed | S2 power (fitted s_u) | S2 power (s_u halved) | S2 size | P(LB > 0 \| G = 3 pp) | rate levels per half (mean used) |
|---|---|---|---|---|---|---|---|
| 6 | 5.7 pp | 5.4 pp | 0.99 | 0.46 | 0.06 | 0.54 | 3.6 |
| 8 | 4.7 pp | 4.6 pp | 1.00 | 0.57 | 0.06 | 0.64 | 4.2 |
| **12** | **3.6 pp** | **3.7 pp** | **1.00** | **0.76** | **0.03** | **0.83** | **5.3** |
| 16 | 3.1 pp | 3.3 pp | 1.00 | 0.86 | 0.05 | 0.91 | 6.2 |

**Reading.** K = 12 is adequate. It is the smallest of the four K values with S2 power ≥ 0.75 under the pessimistic
heterogeneity scenario, which lies below the dev 95% profile lower bound. It also gives ≥ 0.8 power for the §F planning
alternative G = 3 pp, and a 90% interval narrower than the 6 pp window the "small effect" reading needs.
K = 16 adds about 0.5 pp of precision for +33% cost.

This is a planning check and **not** a K search. K = 12 was fixed by the review before the simulation was run.

## 12. Analysis commands (run only after freezing; holdout analysis refuses to run otherwise)

```bash
# 0. freeze (author): record the hash, commit
sha256sum docs/insights/PREREG_FORK_CONFIRM.md     # -> manifests/fork/splits_v1.json splits.holdout.prereg_sha256
# 1. integrity snapshot covering the holdout runs (iter_2/integrity.py scans telecom; W44)
# 2. primary + S1 + strata (analyze_dev reports block-t, block bootstrap and crossed intervals; the t is read as primary)
python analysis/fork/analyze_dev.py --snapshot <SNAP> --split holdout --cells gptq_w4_d1 awq_w4
python analysis/fork/analyze_difficulty.py --snapshot <SNAP> --split holdout --cells gptq_w4_d1 awq_w4
# 3. confirmatory wrapper: equal-weight G_all over {q4:gptq_w4_d1, q8:gptq_w4_d1, q8:awq_w4}, decision readings, S1 IUT,
#    S2 permutation test, not-estimable handling, Holm per strata family
python analysis/fork/analyze_holdout_confirm.py --snapshot <SNAP> --split holdout
```

- `analysis/fork/analyze_holdout_confirm.py` **does not exist yet [TODO before freezing]**.
  - It must be written, dry-run on telecom dev with `--split dev`, using blocks f01–f06 and halves by the same hash rule
    (output labelled exploratory), and committed.
  - Its sha256 is to be recorded here at freezing.
  - It must refuse `--split holdout` unless `analyze_dev.split_guard` passes.
- `analyze_dev` already enforces the holdout guard (`split_guard`). It also accepts the `hNN` block ids and the
  `analysis/fork/holdout` root.

## 13. Relation to development results

- The dev results stay **exploratory**. These are the W52 difficulty moderators, the W67/W70/W78 fragility and
  direction analyses, the telecom dev G values and the dev split-half ρ (+0.63 GPTQ, +0.51 AWQ, descriptive, in the planning
  output).
- The holdout tests here **do not retroactively confirm** any dev result. A positive holdout result supports the holdout claim
  only. A dev number cited next to a holdout number is labelled "dev, exploratory".
- No holdout data will be used to revise the dev analyses, and no dev data will be pooled into a holdout endpoint.

## 14. Decisions the author must make before freezing

1. **Cells:** confirm c1 = q4 GPTQ-W4 d1 (no telecom dev forks), or swap it.
2. **Weights:** confirm equal per-cell weights 1/3 (q8 then carries 2/3), or use 1/2 per model.
3. **Decisional interval:** t over blocks (as in §12), or the crossed task × block interval.
4. **Structural exclusions:** keep or drop a cell with n_excl > 3 (§4.3).
5. **Prerequisites:** produce and hash `holdout_cutpoints_v1.json` from dev, and write and dry-run `analyze_holdout_confirm.py`.
6. **Blocks:** re-check the nonces against all runs at freeze, and compute h13 and h14.
7. **Budget:** approve about 96 GPU-h (67–144), conservative 195 (§15), and the queue priority.
8. **Freeze:** record the sha256 in `splits_v1.json` `holdout.prereg_sha256` and `blocks.telecom`. The freeze commit comes
   before any holdout unit is queued.

## 15. Cost (measured on telecom dev; `analysis/fork/out/holdout_k_planning_20261001T134838Z.json` → cost)

- **Measured per 80-task telecom block (means over the dev groups in `/data/ziyangs/cloq_work/logs/node_*.out`).**
  - Closed loop: q8 BF16 pair 0.7, q8 GPTQ 0.9, q8 AWQ 0.9, q4 BF16 pair 0.7 and q4 GPTQ 1.7 GPU-h.
  - Forks, successful attempts: q8 GPTQ 6.6 and q8 AWQ 5.1 GPU-h. A q8 fork group (2 blocks) took 7–22 GPU-h successful, and
    up to 33 GPU-h with failed attempts.
- **q4 telecom forks were never run.**
  - The q4/q8 fork ratio on retail/airline dev is 0.36, which gives 2.4 GPU-h.
  - The q4/q8 closed-loop ratio on telecom is 1.9.
- **Totals.** Scaled linearly to 34 tasks, this is ≈ 8 GPU-h per block, so K = 12 × 3 cells ≈ **96 GPU-h** (×0.7–×1.5: 67–144).
- **Conservative.** Counting failed attempts and using the larger q4 ratio gives ≈ **195 GPU-h**.
