# PREREG_FORK_CONFIRM — confirmatory protocol for the telecom holdout (same-state 2×2 forks)

> **READY TO FREEZE — sha256 to be recorded in splits_v1.json holdout.prereg_sha256 by the main session.**
>
> Drafted 2026-10-01 (W85) from FORK_PROTOCOL §12, §12 amendment 1 (W80) and GPT-6.1 review 4's holdout points
> (`outputs/gpt61-review4-response-review.md`, point 6). Completed 2026-10-01 (W86) with the author's six decisions
> (cells; weights 1/2 per model; crossed interval decisional; structural exclusions kept; K = 12 + reserves h13–h14;
> budget ≈ 100–200 GPU-h). No holdout unit has been run, and no holdout outcome, trajectory or task text was read in
> drafting it. The holdout-adjacent inputs are the planning simulation and the strata cut points, both computed on telecom
> **dev** data only. After freezing, changes are numbered amendments dated before the first holdout unit, or labelled
> deviations after it.

---

## 0. TL;DR

- **Population:** the 34 telecom holdout tasks (`manifests/fork/splits_v1.json` → `splits.holdout.tasks.telecom`).
- **Cells and weights:** q4 GPTQ-W4 d1 (weight 1/2), q8 GPTQ-W4 d1 (1/4), q8 AWQ-W4 (1/4), i.e. 1/2 per model.
- **Blocks:** K = 12 fresh nonce blocks h01–h12, shared by all cells and by the BF16 pair runs. Halves are fixed by hash:
  H_A = {h01, h04, h05, h09, h11, h12}, H_B = {h02, h03, h06, h07, h08, h10}. Reserve blocks h13 and h14 are used only for
  infrastructure repair under §4. The matrix is 34 × 12 × 3 = 1,224 units.
- **Primary:** G_all = E[Y_BQ − Y_QQ], task-equal and weighted over cells. The **crossed task × block** 90% interval decides
  (§6). The t over block means is reported alongside. The decision bounds are ±3 pp (EXTERNAL_REVIEW §F). G_all is the
  sole member of the primary family, at one-sided α = 0.05.
- **Secondaries** (each its own family at α = 0.05, never used to rescue the primary):
  - **S1:** two-sided consequence replication, r > 0 and d > 0 (intersection–union), on the crossed interval.
  - **S2:** cross-half repeatability of task fragility. ρ is the weighted mean over estimable cells of Spearman(m_A, m_B).
    It is tested one-sided by a persona-stratified permutation. There is **no** outcome screen of cells.
  - **Strata:** six families, Holm within each family.
- **Structural exclusions** are kept and reported, never dropped. A cell with more than 3 is flagged.
- **Planning (dev only, approved weights):** at K = 12, the 90% CI width of G_all is ≈ 4.1 pp (crossed) and 3.9 pp (block t).
  S2 has power ≈ 1.00 at the fitted dev heterogeneity and 0.73 with that heterogeneity halved; its size is 0.05.
- **Cost:** 38 queue tasks, ≈ 96 GPU-h (67–145). The conservative estimate is ≈ 195 GPU-h, inside the approved 100–200 GPU-h.
- **Dev results are not retroactively confirmed (§13).**

## 1. Claims under test and their scope

1. **Primary (C1).** On new telecom tasks, the same-state replacement of a quantized model's first divergent action by BF16's
   action (the G policy) changes task success by G_all. The readings are those of §6.
2. **Secondary (C2).** Outcome-changing divergences on new tasks are two-sided: both rescues (r) and damages (d) occur.
3. **Secondary (C3).** Repeatability on new tasks: a holdout task that flips under quantization in one set of nonce blocks also
   tends to flip in an independent set of nonce blocks.
   - The honest description of the test is: *real task pairing across the two halves is more consistent than
     persona-preserving random task pairing.*
   - It does **not** rule out difficulty explanations. A task property correlated with flip propensity within persona, such as
     fault load, issue type or BF16 difficulty, would also produce ρ > 0.
   - C3 makes **no** "beyond difficulty" claim (cf. W78). It is not a transfer test of a dev-defined task score: dev task IDs do
     not occur in the holdout.
4. **Not claimed.**
   - No generalisation beyond telecom.
   - No generalisation beyond these three model × method cells.
   - No claim that holds over a new task distribution beyond the stratified telecom base split.
   - 34 tasks limit task-level generalisation, and more blocks do not substitute for more tasks. The decisional crossed
     interval includes task-sampling variance for this reason.
   - Few events mean limited evidence, not absence of an effect.

## 2. Population, cells and weights

- **Tasks.**
  - The holdout consists of the 34 telecom base-split tasks not in `manifests/telecom/dev_v1.json` (stratified rule in that file).
  - The list is the one in `manifests/fork/splits_v1.json` and is not reproduced here.
  - The runs use the task file `manifests/telecom/holdout_v1.json` = `{"telecom": <that list, same order>}`. It is written
    by `scripts/a6000/make_tasks_holdout.py --write` after the freeze, and the generator asserts equality with splits_v1.
  - Persona (Hard / None / Easy) is parsed from the task id (`PERSONA:<x>`). Issue type is the `[<issue>]` prefix.
  - The evaluator is the official telecom success (`official_reward == 1`), as on dev (FORK_PROTOCOL §4).
- **Cells.** Checkpoints follow the `primary_checkpoint_rule` of `manifests/fork/dev_blocks_v1.json` (calibration draw c1).
  The ckpt specs are copied from the done tasks `a6k2_<model>_<cell>.json`.

  | id | model | method | checkpoint | weight w_c | telecom dev forks? |
  |---|---|---|---|---|---|
  | c1 | q4 | GPTQ-W4 | d1 (c1) | **1/2** | no (closed-loop f01–f06 runs exist; no forks) |
  | c2 | q8 | GPTQ-W4 | d1 (c1) | **1/4** | yes (f01–f06, 80 tasks, complete) |
  | c3 | q8 | AWQ-W4 | d1 (c1) | **1/4** | yes (f01–f06, 80 tasks, complete) |

- **Why these weights.**
  - On dev, the task effects of c2 and c3 correlate at ρ_u = 0.80 (fitted).
  - Equal per-cell weights would give q8 two-thirds of G_all, so the weights are 1/2 per model.
  - G_all is a weighted cell-average estimand. It does not depend on per-cell divergence counts.
- **c1 has no telecom dev fork history.** Its planning parameters are borrowed from c2, and its first telecom forks are the
  holdout forks. Reported as a limitation.
- **Per-cell components.** G, r, d, M and ρ_c are reported for every cell as **descriptive** components. A pooled pass does
  not imply a per-cell pass (EXTERNAL_REVIEW §F).

## 3. Blocks, nonces and the split into halves

- **K = 12, fixed.**
  - The budget target is GPT-6.1 review 4's: 6 + 6 halves give 7 rate levels per task and half, against 4 for K = 6.
  - The dev planning simulation confirms adequacy (§11). K was not chosen from it.
- **Nonce rule.**
  - nonce(block with index k) = sha256("cloq-fork-holdout-v1|" + str(k))[:8], for k = 0, 1, …, 13 (h01 is k = 0).
  - A nonce already used by any run (`prompt_nonce` in `runs/*/*/environment.json`) or queued task (`runs[].nonce` in
    every queue directory), or listed in `manifests/fork/dev_blocks_v1.json`, would be skipped, and the block would take
    the next k.
  - **Check at completion (W86):** 31 distinct used nonces were checked (30 run nonces, plus queue and dev_blocks). None of the
    14 holdout nonces collides, so no k is skipped. The table below is therefore final.
  - `make_tasks_holdout.py` re-derives every nonce, asserts that it equals this table, and aborts if any non-holdout run or
    task has started using one.
- **Halves.** H_A is the first K/2 = 6 block ids in ascending order of sha256("holdout-split-v1|" + block_id); H_B is the rest
  (§12 amendment 1's rule). A reserve block that replaces a primary block inherits that block's half.

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
| h13 (reserve) | 12 | 0354e294 | e6f6af899fcf | inherits the replaced block's half |
| h14 (reserve) | 13 | 555fd7b8 | 755aa463a852 | inherits the replaced block's half |

- **Per block: tasks generated by `scripts/a6000/make_tasks_holdout.py`, which runs dry by default.**
  - **Closed loop:** `a6k2_{q4,q8}_tel_bfpair_hNN` (BF16 pair), `a6k2_q4_tel_gptq_w4_d1_hNN`, `a6k2_q8_tel_gptq_w4_d1_hNN` and
    `a6k2_q8_tel_awq_w4_hNN`. All use the holdout task file and the block's nonce.
    - The run configuration is that of the telecom dev blocks f01–f06 (`make_tasks_fork_dev2.py`), with only the nonce and
      the task file changed.
    - There are 3 blocks per eval task, so the closed loop is 20 eval tasks.
    - GPUs are the models.json default (1). The closed loop is not run tensor-parallel, because the fork's Q server has to
      regenerate the closed-loop Q actions.
  - **Forks:** fork-v1, deterministic protocol A (FORK_PROTOCOL §3–§6c), mode `dev`.
    - Each fork follows the first primary semantic divergence, with BB/BQ/QB branches and a 10% QQ no-op sample, the same
      spec as `analysis/fork/telecom/*/search.json`.
    - There are 2 blocks per fork task, so the forks are 18 tasks, each depending on its Q eval task(s).
    - q4 runs on 1 GPU (`gpu_util` 0.44); q8 runs on 2 GPUs, one per B/Q server. There are no node pins.
  - **Output:** `analysis/fork/holdout/<model>_<cell>/gNN/`. Repairs go to `analysis/fork/holdout/repair/…`.
  - Block ids match `analyze_dev.RUN_RE` (`h\d+`).
- **Queue.** Nothing is queued before freezing. `--write` refuses unless the prereg sha256 is recorded in splits_v1.

## 4. Completeness and repair (outcome-blind)

The analysis matrix is **complete by design**: 34 tasks × 12 blocks × 3 cells. The analysis is not run until the matrix is
complete or the repair budget below is exhausted.

1. **Unit statuses.**
   - `divergent` with Y_BB, Y_BQ, Y_QB and Y_QQ all present.
   - `no_divergence`, which counts with G = r = d = M = 0.
   - `missing`.
   - Agent-side context overflow and other deterministic in-episode failures are valid outcomes (W10), not misses.
2. **Infrastructure misses are repaired before any analysis.** An infrastructure miss is any missing unit that is not
   structural (item 3). Examples are server or simulator outage, a node kill, a branch error, branches pending, an
   infrastructure termination at search, a Q block not admitted in the snapshot, and a QQ no-op mismatch.
   - The unit is re-executed with the same nonce and state: a fork `repair` task (W70) or a closed-loop re-run of the run-domain.
   - The limit is 3 attempts per unit.
   - The operator sees only status and missing reason, never Y.
   - Repairs are logged in `analysis/fork/holdout/REPAIR_LOG.jsonl`.
3. **Structural exclusions** cannot be repaired, because they are deterministic. The analysis classifies these missing
   reasons as structural:
   - (a) the search exclusion "B prompt ids differ from Q's recorded prompt" (FORK_PROTOCOL §3.1);
   - (b) the search exclusion "decision/trajectory count mismatch";
   - (c) a QQ no-op mismatch on the unit's state that still exists when the analysis runs, i.e. after the repair budget.

   How they are handled:
   - The **task** is excluded from **that cell in all blocks**, so blocks stay complete and shared, and this is reported.
     The cell's denominator becomes n_c = 34 − n_excl(c).
   - A no-op mismatch is handled at **unit** level. This replaces analyze_dev's whole-directory quarantine, which would
     delete two complete blocks.
   - If n_excl > 3 in a cell, the cell is **kept** in G_all with its prereg weight, and is reported and flagged
     ("> 3 structural exclusions, kept"). It is never dropped.
4. **Unrepairable block.** A (cell, block) is incomplete if any of the cell's included tasks lacks a valid unit after the
   repair budget.
   - Each incomplete primary block, in ascending id order, is replaced in **all** cells by the next reserve block that is
     complete in all cells (h13, then h14). The reserve inherits the replaced block's half.
   - Reserve blocks are generated (`make_tasks_holdout.py --reserve h13 [h14]`) only when a primary block is unrepairable.
5. **Fallback.** If more than 2 blocks are unrepairable, the analysis uses the complete shared blocks only (K' < 12).
   - Below K' = 8 the decision readings of §6 are reported as **not estimable** (descriptive only).
   - S2 needs ≥ 3 complete blocks per half; otherwise it is not estimable.
6. **Sensitivity.** A complete-case run (`--complete-case`: infrastructure-missing units do not make a block incomplete) is
   reported, labelled as a sensitivity. Denominators are then per (cell, block); see §5.

## 5. Estimands and denominators

For cell c, task j and block b, Y_xy ∈ {0, 1} is the official success of the branch whose action is from x and suffix from y
(FORK_PROTOCOL §1; sign dictionary in CONSEQUENCE_ANALYSIS_PLAN §2).

- **Unit level.**
  - G = Y_BQ − Y_QQ.
  - r = 1[Y_BQ = 1, Y_QQ = 0], d = 1[Y_BQ = 0, Y_QQ = 1], M = r + d.
  - For no_divergence: G = r = d = M = 0.
- **Cell-block level.** G_{c,b} = (1/n_{c,b}) Σ_{j ∈ A_{c,b}} G_{c,j,b}.
  - A_{c,b} is the set of the cell's included tasks with a valid unit in b. In the primary analysis it holds all n_c tasks.
  - The estimand is **task-equal**: there is no n_decisions weighting, and no conditioning on divergence.
  - r, d and M are defined on the same denominator.
- **Combined matrix.** Z_{j,b} = Σ_c w_c (J / n_{c,b}) G_{c,j,b} 1[j ∈ A_{c,b}], with J = 34 and w = (1/2, 1/4, 1/4).
  - Its block mean is G_all,b = (1/J) Σ_j Z_{j,b} = Σ_c w_c G_{c,b}.
  - G_all = (1/K') Σ_b G_all,b.
  - r, d and M are combined likewise.
- **Repeatability.** m_A(c, j) = (1/|H_A|) Σ_{b ∈ H_A} M_{c,j,b}. With 6 blocks per half it takes 7 levels; m_B is the same over H_B.
- **Conditional-on-divergence quantities** (A, C, I, H, F, the 16 patterns) are descriptive only. They have a different
  denominator and are labelled as such.

## 6. Primary endpoint G_all (family P: {G_all}, one-sided α = 0.05)

- **Decisional interval: crossed task × block** (author decision 3).
  - The estimator is a two-way random-effects decomposition of the J × K' matrix Z without replication (ANOVA moments):
    - MS_T = K' Σ_j (Z̄_j· − Z̄)² / (J − 1);
    - MS_B = J Σ_b (Z̄_·b − Z̄)² / (K' − 1);
    - MS_E = the residual mean square, with (J − 1)(K' − 1) df.
  - Var(G_all) = [MS_E + max(MS_T − MS_E, 0) + max(MS_B − MS_E, 0)] / (J K'). Negative components are truncated at 0.
  - The interval is G_all ± 1.645 √Var (normal), i.e. 90% two-sided. Its lower end L is the one-sided 95% lower bound.
  - This interval includes task-sampling variance, so it is a statement about new tasks from the same distribution, not only
    about these 34.
- **Reported alongside, not decisional:** the t over the K' block means G_all,b (df K' − 1, 90%). It treats the 34 tasks as
  fixed.
- **Decision readings** (EXTERNAL_REVIEW §F; g_min = 3 pp; [L, U] = the crossed 90% interval):
  - **positive gain:** L > 0.
  - **gain above 3 pp:** L > +3 pp.
  - **small average effect:** −3 pp < L and U < +3 pp.
  - **otherwise inconclusive.**

  The readings are nested statements about one interval, so no multiplicity adjustment applies within family P. The ±5 pp
  version is a labelled sensitivity only. If K' < 8, the readings are not estimable (§4.5).
- Per-cell G_c, with both intervals, is descriptive (§2).

## 7. Secondary S1: two-sided consequences (family S1, α = 0.05)

- H1 is r > 0 **and** d > 0. Each is tested by its crossed one-sided 95% lower bound (as §6, on the matrix of r and of d).
- S1 passes if both lower bounds are > 0. This is an intersection–union test, so no adjustment is needed. The block-t bounds
  are reported alongside.
- M > 0 is implied by S1 and is reported with its interval.
- The stress-cell endpoint C + I of FORK_PROTOCOL §12 does **not** apply: the holdout has no stress cells. Y_BB − Y_QQ is
  reference only.

## 8. Secondary S2: cross-half repeatability of task fragility (family S2, one-sided α = 0.05)

This is §12 amendment 1, as revised per GPT-6.1 review 4. It **replaces** the amendment's "not estimable" rule.

1. **Per cell.** ρ_c = Spearman(m_A(c, ·), m_B(c, ·)) over the cell's included tasks, with average ranks for ties.
2. **No outcome screen.**
   - The amendment-1 rule "cell not estimable if fewer than 10 tasks have m_A + m_B > 0" is **removed**. No cell is screened
     on its outcomes.
   - The only estimability condition is mathematical: ρ_c is **not estimable** if m_A(c, ·) or m_B(c, ·) is constant (Spearman
     is undefined there) or if the cell has fewer than 3 included tasks.
   - Constancy is invariant under any permutation of m_B's task labels. The estimable set is therefore identical in every
     permutation draw, and the condition sits inside the permutation by construction. The implementation asserts this in
     every draw.
3. **Endpoint.** ρ = Σ_{c estimable} w̃_c ρ_c, where w̃ is the §2 weights renormalised over the estimable cells.
   - If no cell is estimable, the endpoint is reported as **not estimable**, with no claim either way.
   - "Not estimable" is never coded as ρ = 0 and is never read as non-replication.
4. **Test.** One-sided, H1: ρ > 0.
   - Draw keys U = `numpy.random.default_rng(20261001).random((10000, J))` over the task ids in sorted order.
   - In draw r, within each persona stratum, a cell's included tasks (in task-id order) receive the m_B values of the same
     tasks re-ordered by ascending key U[r, ·].
   - With no exclusions this is one permutation π per draw, the same for every cell. With exclusions it is the same keyed
     permutation restricted to each cell's included tasks.
   - ρ* is recomputed in each draw, and p = (1 + #{ρ* ≥ ρ}) / (1 + 10,000).
5. **What the test shows.** Real task pairing is more consistent than persona-preserving random pairing. It does not
   separate repeatability from within-persona task properties (§1.3).
6. **Reporting.** Report each ρ_c, n_c, the levels used per half, the number of tasks with m_A + m_B > 0 (descriptive), and the
   permutation null quantiles.
7. **Exploratory only.**
   - The sign consistency of per-task (r − d) across halves.
   - A within-stratum variant adjusted for fault load or issue type, which would be needed for any difficulty argument.
8. **Planning check (dev only, §11).** Power at K = 12 is ≈ 1.00 at the fitted dev heterogeneity and 0.73 with s_u halved.
   Size is 0.05.

## 9. Strata (pre-registered secondary families; Holm within each family)

- **Cut points.** These are fixed on telecom dev only, in `manifests/fork/holdout_cutpoints_v1.json`, with sha256
  **ab46abe91960f6c2cb1b228ffa7ada8128d4018f21be80ef017d1a95429d32de**.
  - They were produced by `analysis/fork/make_holdout_cutpoints.py` (sha256 43f5538b3001…; snapshot 20261001T1411Z).
  - The analysis refuses to run if the file's sha differs.
  - Tertile labels are T1: v ≤ c1, T2: c1 < v ≤ c2, T3: v > c2. The cuts (c1, c2) are the pair of observed dev values
    minimising Σ_k (share_k − 1/3)², which is a tie-aware tertile.
- **Families.** The m = 3 levels of each family are pre-specified:

  | family | variable | levels (dev cut points) | unit |
  |---|---|---|---|
  | step_budget | remaining step budget at t* (max_steps − steps used) | T1 ≤ 191 < T2 ≤ 197 < T3 | unit-level (divergent units) |
  | persona | PERSONA in the task id | Hard, None, Easy | task |
  | bf16_difficulty | task BF16 success rate, pooled over the q4 and q8 BF16 pair episodes of the analysis blocks | "0" (= 0), "low" (0, 1/3], "high" > 1/3 | task |
  | task_length | task mean agent decisions over the same BF16 pair episodes | T1 ≤ 15.67 < T2 ≤ 20.33 < T3 | task |
  | issue_type | `[<issue>]` prefix of the task id | mms_issue, mobile_data_issue, service_issue | task |
  | n_faults | number of injected faults (‘\|’-separated items in the task id) | T1 ≤ 3 < T2 ≤ 5 < T3 | task |

  - FORK_PROTOCOL §12's "fault load (issue type, number of injected faults)" is split into the two families issue_type and
    n_faults.
  - The BF16 statistics use 24 episodes per holdout task (2 models × 12 blocks); the dev cut points used 12.
- **What is computed per level.**
  - Task-level families: G_all of the tasks in the level. This is §5 restricted to them, with J = number of tasks in the
    level and n_{c,b} counted within the level.
  - step_budget: the level's **contribution** to G_all, i.e. §5 over all tasks with every unit outside the level set to 0.
    The three levels plus the zero contribution of non-divergent units sum to G_all.
- **Test.** Two-sided, H0: G_level = 0, with p = 2Φ(−|est| / se_crossed), where se_crossed is the §6 crossed SE of the level.
  - Holm applies within each family over its m = 3 pre-specified levels, at α = 0.05.
  - The block-t interval is reported alongside.
  - r, d and M per level are descriptive (crossed intervals, not tested).
- **Not estimable.** A level with fewer than 2 tasks, a cell with no available task in some block, or zero crossed variance
  is reported as not estimable. It keeps its place in m with p = 1.

## 10. Exploratory (never confirmatory)

- **M1:** the slope of C on the realised remaining horizon. It is confounded by Q's realised trajectory.
- Per-cell q4 versus q8 contrasts.
- Divergence-type breakdowns.
- Direction consistency.
- Bank U style action taxonomy.
- Any comparison of holdout and dev magnitudes.
- The analyze_dev / analyze_difficulty holdout outputs (§12, steps 2 and 3). Their equal-weight W4 pools and whole-directory
  quarantine differ from §4–§6.

## 11. Planning precision (telecom dev only; W85, re-run with the approved weights in W86)

Sources:
- `analysis/fork/holdout_k_planning.py` → `analysis/fork/out/holdout_k_planning_20261001T134838Z.{json,md}` (W85, equal weights,
  K = 6/8/12/16);
- `analysis/fork/out/holdout_k_planning_20261001T144122Z.{json,md}` (W86, `--weights 0.5,0.25,0.25 --ks 12`).

**Model.**
- A logistic GLMM per q8 cell on the 80 × 6 complete dev matrix, with persona intercepts, block effects and a task random effect.
- The fitted task-effect SD s_u is 2.22 [1.73, 2.85] for GPTQ and 1.62 [1.27, 2.09] for AWQ.
- The block-shock SD is 0.57 (GPTQ) and 0.35 (AWQ).
- The task-effect correlation across cells is ρ_u = 0.80.
- c1 borrows c2's parameters.
- The simulation uses 34 tasks (persona mix 11/11/12), 1,000 replications and 2,000 permutations each.

| K = 12 scenario | weights | 90% width, crossed | 90% width, t over blocks | S2 power (size under null) | P(t-LB > 0) |
|---|---|---|---|---|---|
| fitted s_u | 1/2, 1/4, 1/4 | 4.1 pp | 3.9 pp | 1.00 | 0.46 |
| s_u halved | 1/2, 1/4, 1/4 | 3.0 pp | 3.0 pp | 0.73 | 0.25 |
| no task heterogeneity (null) | 1/2, 1/4, 1/4 | 2.4 pp | 2.4 pp | 0.05 (size) | — |
| true G_all = +3 pp | 1/2, 1/4, 1/4 | 4.3 pp | 3.9 pp | 1.00 | 0.79 |
| fitted s_u | 1/3 each (W85) | 3.7 pp | 3.6 pp | 1.00 | 0.40 |

- The planning crossed width used Var = max(MS_T + MS_B − MS_E, MS_E) / (JK). §6 truncates each component separately, which
  is never narrower.
- **Reading.** K = 12 stays adequate under the approved weights: S2 power is ≥ 0.7 in the pessimistic scenario, and the 90%
  width is below the 6 pp window that the "small effect" reading needs. Putting weight 1/2 on one cell widens G_all by
  about 0.3 pp, against equal weights.
- This is a planning check and **not** a K search. K = 12 was fixed by the review before the simulation was run.

## 12. Analysis commands (run only after freezing; holdout analysis refuses to run otherwise)

```bash
# 0. freeze (main session): record the hash, commit
sha256sum docs/insights/PREREG_FORK_CONFIRM.md     # -> manifests/fork/splits_v1.json splits.holdout.prereg_sha256
# 1. queue (after the freeze; dry run first, then --write)
python scripts/a6000/make_tasks_holdout.py            # prints 38 tasks, ~96 GPU-h; writes nothing
python scripts/a6000/make_tasks_holdout.py --write    # refuses unless step 0 is done
# 2. after completion/repair (§4): integrity snapshot covering the holdout runs (iter_2/integrity.py scans telecom; W44)
# 3. confirmatory analysis (this prereg, exactly)
python analysis/fork/analyze_holdout_confirm.py --snapshot <SNAP> --split holdout
python analysis/fork/analyze_holdout_confirm.py --snapshot <SNAP> --split holdout --complete-case   # §4.6 sensitivity
# 4. supplementary descriptive outputs (not decisional; §10)
python analysis/fork/analyze_dev.py --snapshot <SNAP> --split holdout --cells gptq_w4_d1 awq_w4
python analysis/fork/analyze_difficulty.py --snapshot <SNAP> --split holdout --cells gptq_w4_d1 awq_w4
```

- `analysis/fork/analyze_holdout_confirm.py` (sha256 **2af1b6890defcf03a07040528d16e1ce2597d694e3a7cbacffc533fb0bb141db**)
  implements §4–§9.
  - It calls `analyze_dev.split_guard` for the holdout before opening any holdout file, so it refuses `--split holdout` unless
    this file's sha256 equals splits_v1 `holdout.prereg_sha256`.
  - It refuses if the cut-point sha differs from §9.
  - It fixes 10,000 permutations for the holdout.
- **Dry run on dev.** `--dry-run-dev` runs the identical pipeline on telecom dev blocks f01–f06, relabelled as a
  pseudo-holdout: K = 6, 80 tasks, and q4 absent with weights renormalised.
  - It was run and committed in W86 as `analysis/fork/out/holdout_confirm_DRYRUN_DEV_*.{json,md}`, labelled **DRY RUN ON DEV**
    (exploratory).
  - Dev results: G_all +1.04 pp, crossed 90% [−0.97, +3.06]; S1 r 7.3 and d 6.3 pp, both LB > 0; S2 ρ = 0.57, p = 0.0001.
    The readings were not estimable, since K' = 6 < 8.
- **Script hashes.** Any later change to the analysis script before the first holdout unit is a numbered amendment with its
  new sha256. `analyze_dev.py` (imported) has sha256 5851a57b1a7b… at W86.

## 13. Relation to development results

- The dev results stay **exploratory**. These are the W52 difficulty moderators, the W67/W70/W78 fragility and
  direction analyses, the telecom dev G values, the dev split-half ρ (+0.63 GPTQ, +0.51 AWQ) and the W86 dry run.
- The holdout tests here **do not retroactively confirm** any dev result. A positive holdout result supports the holdout claim
  only. A dev number cited next to a holdout number is labelled "dev, exploratory".
- No holdout data will be used to revise the dev analyses, and no dev data will be pooled into a holdout endpoint.

## 14. Author decisions (recorded 2026-10-01, W86)

1. **Cells:** q4 GPTQ-W4 d1, q8 GPTQ-W4 d1 and q8 AWQ-W4 (calibration c1).
2. **Weights:** 1/2 per model. The q4 cell gets 1/2 and each q8 cell 1/4 (§2). S2 uses the same weights, renormalised over
   estimable cells (§8).
3. **Decisional interval:** crossed task × block (§6). The block t is reported alongside.
4. **Structural exclusions:** a cell with more than 3 is kept and the exclusions are reported, never dropped (§4.3).
5. **Blocks:** K = 12 (h01–h12). The reserves h13–h14 are used only for infrastructure repair under §4.4. Nonces were checked
   at W86 (§3).
6. **Budget:** about 100–200 GPU-h approved (§15).
7. **Freeze (main session):** record this file's sha256 in `splits_v1.json` → `splits.holdout.prereg_sha256` and the block
   list in `blocks.telecom`. The freeze commit comes before any holdout unit is queued.

## 15. Cost (measured on telecom dev; `analysis/fork/out/holdout_k_planning_20261001T134838Z.json` → cost)

- **Measured per 80-task telecom block (means over the dev groups in `/data/ziyangs/cloq_work/logs/node_*.out`).**
  - Closed loop: q8 BF16 pair 0.7, q8 GPTQ 0.9, q8 AWQ 0.9, q4 BF16 pair 0.7 and q4 GPTQ 1.7 GPU-h.
  - Forks, successful attempts: q8 GPTQ 6.6 and q8 AWQ 5.1 GPU-h.
- **q4 telecom forks were never run.** The q4/q8 fork ratio on retail/airline dev is 0.36, which gives 2.4 GPU-h. The q4/q8
  closed-loop ratio on telecom is 1.9.
- **Totals.** Scaled linearly to 34 tasks, this is ≈ 8 GPU-h per block.
  - `make_tasks_holdout.py` (dry run) prints 38 tasks: 20 eval tasks (60 closed-loop runs) and 18 fork tasks, ≈ **96 GPU-h**
    (×0.7–×1.5: 67–145).
  - The conservative estimate, counting failed attempts and using the larger q4 ratio, is ≈ **195 GPU-h**.
  - The reserves h13 + h14, if needed, add ≈ 16 GPU-h.
