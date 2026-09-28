# COLING independent re-audit — results

CPU-only (`CUDA_VISIBLE_DEVICES=""`, `~/miniconda3/envs/cloq/bin/python`), read-only against
`runs/`. Nothing under `ckpts/`, `runs/`, `configs/`, `cloq/` was modified. All numbers below are
recomputed from raw `trajectory.jsonl` / `openloop.jsonl` files using `cloq.metrics.load_decisions`
and `cloq.metrics.resolved_db_match` (premature termination scored as `db_match=False`, per the
project's own convention — see `cloq/metrics.py`). Reproduce with `./make_all.sh`.

Scripts: `01_checkpoint_success.py`, `02_v0_gap.py`, `03_openloop_vs_closedloop.py`,
`04_loop_attribution.py`, `05_figures.py`. Raw output JSON in `out/`, figures in `figs/`.

---

## 1. Per-checkpoint success (18 GPTQ dev checkpoints, RTN, BF16)

BF16 horizon cutoff for "long" = 11 decisions (from the frozen `manifests/task_split_v0.json`,
verified: 25/58 retail + 12/27 airline = 37/85 dev tasks have horizon > 11 — matches
STRATEGY_v2's "85 dev tasks, 37 with BF16 horizon > 11" exactly).

| | pooled db_match | long db_match |
|---|---:|---:|
| BF16 (`bf16_v1`) | **0.376** | **0.297** |
| RTN (`rtn_eval`) | **0.271** (= min of the 18 GPTQ checkpoints) | **0.108** |
| 18 GPTQ checkpoints: min | 0.271 | 0.054 |
| 18 GPTQ checkpoints: max | 0.424 | 0.270 |
| 18 GPTQ checkpoints: mean | 0.332 | 0.176 |

Full per-checkpoint table in `out/01_checkpoint_success.json`.

**Match vs memo (A5):** exact. BF16 0.376/0.297, RTN pooled 0.271 exactly equal to the GPTQ
minimum, RTN long 0.108 — all reproduce STRATEGY_v2 A5 verbatim.

### Arm-label permutation test, conditional on tasks (A2)

Statistic: one-way ANOVA F on the 18 checkpoint-level db_match rates, grouped by arm (6 groups
of 3 draws); null = arm label carries no information (exchangeable). 20,000 permutations.

| | F | p |
|---|---:|---:|
| pooled | 0.634 | **0.683** |
| long | 1.219 | **0.368** |

**Match vs memo:** near-exact. STRATEGY_v2 A2 reports "arm 置换 p=0.68 pooled / 0.36 long" —
0.683 vs 0.68, 0.368 vs 0.36. This independently confirms the near-exchangeability claim.

### Draw-seed permutation test

Same F-statistic, grouping factor = calibration draw (c1/c2/c3) instead of arm.

| | F | p |
|---|---:|---:|
| pooled | 0.133 | **0.881** |
| long | 0.324 | **0.744** |

**Match vs memo:** near-exact. STRATEGY_v2 A2 reports "draw-seed p=0.90 / 0.74" — 0.881 vs
0.90, 0.744 vs 0.74. Confirmed.

*(Not requested but noted: the memo's third permutation number, "列置换 p=0.13 pooled /
0.08 long" (task/column-label permutation, a different null construction), was not
reproduced here since the task only asked for arm-label and draw-seed permutation tests.)*

---

## 2. v0 FP-Traj vs Static retail gap under an exchangeable null (A6)

`runs/static_eval` vs `runs/fp_traj_eval`, retail, 58 shared task ids. Exchangeable null: each
task's (static, fp_traj) outcome pair is independently swapped with probability 0.5 under H0;
statistic = mean(fp_traj) − mean(static); one-sided p = P(permuted diff ≥ observed), since the
pre-registered claim was FP-Traj > Static. 100,000 draws (this permutation test is provably
equivalent to the exact McNemar binomial test on discordant pairs, and was cross-checked against
`scipy.stats.binomtest` — both give p=0.01953 to full precision).

| | value |
|---|---:|
| mean(static) | 0.2414 |
| mean(fp_traj) | 0.3621 |
| observed diff | **+0.1207** (7-task swing, 8 fp-only wins vs 1 static-only win) |
| naive two-sided McNemar p | **0.0389** |
| exchangeable-null one-sided p | **0.0195** |

**Match vs memo — MISMATCH FLAGGED.** The point estimate (+0.121) and the naive two-sided
McNemar p (0.039) reproduce STRATEGY_v2 A6 exactly. But my exchangeable-null **one-sided** p
is 0.0195, not the memo's stated **0.035**. I verified my number is the exact one-sided McNemar
binomial p for 8 discordant wins vs 1 (`binomtest(8, 9, 0.5, alternative='greater')` = 0.01953),
so it is internally consistent and standard, but it does not match 0.035. Two-sided/2 also gives
0.0195, not 0.035, so the memo's 0.035 does not appear to come from halving its own two-sided
number either. I cannot determine from the repo which exact test construction produced 0.035
without the original audit script; flagging this as an open discrepancy. **This does not change
the qualitative finding** (single-draw "significant win" that reverses sign on replication,
A6/§2.2) — both my number and the memo's are comfortably inside "nominally significant at 0.05,
fragile."

Replication check (v1 c1 dev, retail only, single draw, same statistic): diff = **−0.0862**
(sign-reversed, consistent with A6's reported "复验为 −0.035" direction, though the full v1
replication number in the memo pools all 3 draws × both domains — that number is reproduced in
`out/01_checkpoint_success.json`'s per-checkpoint table, not repeated here).

---

## 3. Open-loop NLL vs closed-loop success (A4, A5)

Two pooling conventions were checked because they disagree on the correlation sign (see below):
- **mean-of-ratios**: mean over all per-decision `nll_per_token` values (matches the convention
  behind the cached `openloop.summary.json` field).
- **token-weighted**: sum(nll) / sum(action tokens) pooled over both domains.

| | mean-of-ratios | token-weighted |
|---|---:|---:|
| Static (mean of c1/c2/c3) | **0.0942** | 0.1278 |
| Other 5 trajectory arms (mean of 15 checkpoints) | **0.0757** | 0.1065 |
| RTN | **0.1574** | 0.2043 |
| RTN / Static ratio | **1.671×** | 1.598× |

**Match vs memo (A4/A5), mean-of-ratios column:** essentially exact. Static 0.0942 vs memo's
0.094; rest arms 0.0757 vs memo's "0.075–0.077"; RTN 0.1574 vs memo's 0.157; ratio 1.67× vs
memo's "1.7×". This confirms the mean-of-ratios convention is what STRATEGY_v2's headline NLL
table used.

### Static-vs-rest NLL permutation (A4)

Two-sample permutation test (statistic = mean(static) − mean(rest), 18 checkpoints: 3 static vs
15 other, 100,000 permutations):

| convention | diff | two-sided p |
|---|---:|---:|
| mean-of-ratios | 0.0186 | **0.0014** |
| token-weighted | 0.0213 | **0.0011** |

**Match vs memo — minor mismatch flagged.** Memo: p=0.0044. Mine: 0.0011–0.0014. Same order of
magnitude and same conclusion (Static is clearly separable from the other 5 arms in open-loop
NLL, p ≪ 0.01), but not numerically identical — likely a different permutation-test
implementation (e.g. exact enumeration over the C(18,3)=816 label assignments vs Monte Carlo, or
a different test statistic such as a t-statistic rather than a raw mean difference). Does not
change the qualitative finding.

### NLL vs closed-loop success correlation (A4) — SIGN DISCREPANCY FLAGGED

Spearman ρ over the 18 checkpoints, NLL/token vs pooled (resp. long) closed-loop db_match:

| convention | ρ (pooled) | ρ (long) |
|---|---:|---:|
| mean-of-ratios | **−0.124** | −0.088 |
| token-weighted | **+0.054** | +0.058 |

**Match vs memo:** the **token-weighted** convention reproduces STRATEGY_v2's "r=0.05
pooled / 0.04 long" almost exactly (0.054 vs 0.05, 0.058 vs 0.04). The mean-of-ratios convention
— the same one that reproduces the memo's headline Static/rest/RTN NLL *values* almost exactly —
gives the **opposite sign** and a larger magnitude (−0.124 / −0.088).

**This is a genuine internal-consistency issue worth resolving before the paper cites either
number.** It means STRATEGY_v2's own reported NLL statistics implicitly mix two different
pooling conventions across its own table (headline NLL values under mean-of-ratios, correlation
under token-weighted) without saying so. Practically: under **both** conventions, |ρ| ≤ 0.13,
so the substantive claim — "open-loop NLL does not predict closed-loop success" — is robust to
this choice; only the sign and exact magnitude are sensitive to it. Recommend the paper pick one
convention, state it explicitly, and report both the table values and the correlation from that
single convention (or report both openly, as done here).

---

## 4. Loop attribution (agent-side / simulator-side / mixed)

Classified every trajectory across the 18 GPTQ dev checkpoints + `bf16_v1` + `rtn_eval` whose
`termination_reason` is not in `cloq.metrics.NORMAL_TERMINATIONS` (`user_stop`, `agent_stop`) —
i.e. `max_steps`, `too_many_errors`, `infrastructure_error`. 150 such trajectories total.

**Rule (fixed mechanically, before any arm label was consulted):** for each trajectory, compute
the longest run of consecutive *exact*-duplicate user utterances (whitespace-normalised) and the
longest run of consecutive exact-duplicate agent actions (`cloq.metrics.normalize_action`,
content + tool calls). Threshold 3 (repeated ≥3 times consecutively):
- both runs ≥3 → **mixed** (lockstep call-and-response loop)
- only user run ≥3 → **simulator-side** (user stuck; agent content varies)
- only agent run ≥3 → **agent-side** (agent stuck; e.g. repeats a failing tool call)
- neither → **no_repetition** (e.g. `too_many_errors` from distinct, non-repeating errors —
  confirmed by inspection: several `too_many_errors` trajectories end on a run of *different*
  tool calls each producing a distinct error, not a loop at all)

### Counts

| label | n | share |
|---|---:|---:|
| agent-side | 55 | 36.7% |
| no_repetition | 53 | 35.3% |
| mixed | 30 | 20.0% |
| simulator-side | 12 | 8.0% |

By arm (of 150 premature trajectories, including 5 from `rtn`, 0 from `bf16_v1` — BF16 had zero
premature terminations in this set):

| arm | simulator-side | agent-side | mixed | no_repetition |
|---|---:|---:|---:|---:|
| static | 3 | 9 | 2 | 6 |
| fp_traj | 3 | 13 | 6 | 6 |
| cloq_all | 3 | 6 | 8 | 10 |
| cloq_novel | 2 | 5 | 4 | 9 |
| cloq_matched_random | 0 | 6 | 5 | 12 |
| cloq_matched_alt | 0 | 13 | 5 | 9 |
| rtn | 1 | 3 | 0 | 1 |

By termination reason:

| reason | simulator-side | agent-side | mixed | no_repetition |
|---|---:|---:|---:|---:|
| max_steps (n=125) | 5 | 53 | 30 | 37 |
| too_many_errors (n=14) | 7 | 2 | 0 | 5 |
| infrastructure_error (n=11) | 0 | 0 | 0 | 11 |

Note: all 11 `infrastructure_error` trajectories classify as `no_repetition` under this
mechanical rule — consistent with STRATEGY_v2 §2.3 item #7's separate finding (from message-step
counts) that 9 of these 11 are "actually 67–98-step loops"; the two classifications are not
contradictory since a step-count-based "this ran unusually long" observation and an
exact-text-repeat rule can disagree on borderline cases (e.g. slowly varying repeated phrasing
that never repeats *verbatim* three times in a row). This rule is deliberately conservative
(exact-match only) and likely undercounts near-duplicate loops; a looser near-duplicate
(edit-distance) rule would be a natural follow-up but was not built here since the task
specified fixing one rule before inspecting arm labels.

### Does an A8-style conclusion change after excluding simulator-side loops?

Sensitivity check: recompute each of the 18 checkpoints' pooled db_match with the 12
simulator-side dev-checkpoint premature trajectories **excluded from the denominator** (treated
as missing) instead of scored as failure (the project's current, and IMO correct, convention).

**Maximum shift in any checkpoint's pooled db_match: 0.0088** (less than one percentage point).
Full per-checkpoint before/after table in `out/04_loop_attribution.json`.

**Conclusion: no, A8/A2-style conclusions do not change.** Excluding simulator-side loops from
the failure count moves individual checkpoint success rates by less than 1 point, far smaller
than the arm-to-arm spread (pooled range 0.271–0.405) or the permutation-test null bands above.
This directly answers STRATEGY_v2 §2.3 item #13 ("simulator 造成的循环没有归因"): now attributed,
and the attribution turns out not to matter numerically for the arm-comparison conclusions,
though it *does* matter for interpretation — 8% of premature failures (12/150) are not the
quantized agent's fault, they are the user simulator failing to terminate, and 20% more (mixed)
have partial simulator involvement. Caveat: this proxy operates over *all* premature
trajectories, not the specific "BF16 succeeds, quantized fails" 234-pair subset that A8's
"46/234 max_steps loops" statistic was computed over; reproducing that exact paired taxonomy
(mechanism audit Q5) was out of scope here, so this is a reasonable but not identical check of
the same underlying question.

---

## 5. Figures

- `figs/fig_a_checkpoint_success.pdf` — per-checkpoint pooled & long db_match, 18 GPTQ
  checkpoints (colored by arm) + BF16 and RTN reference lines. Includes a placeholder hook
  (`load_null_bf16()` in `05_figures.py`) that overlays a 95% band from `runs/null_bf16_n*/`
  once that perturbation-null experiment exists and is `completed` in both domains — **no such
  directories exist yet**, so the hook is currently a no-op (confirmed: `ls runs | grep null`
  returns nothing).
- `figs/fig_b_nll_vs_success.pdf` — NLL/token vs pooled closed-loop success scatter, both
  pooling conventions side by side, annotated with their (opposite-sign) Spearman ρ.
- `figs/fig_c_8k_vs_32k.pdf` — 8k vs 32k pooled db_match. Only **BF16** has a completed pair
  (`bf16_v1` vs `ctx32k_bf16`, both domains, both `status: completed`): retail 0.362 → 0.414,
  airline 0.407 → 0.407 (unchanged), pooled 0.376 → 0.412 — **exact match** to STRATEGY_v2's
  "retail db_match 从 0.362 升到 0.414，airline 不变". `runs/ctx32k_static_c1` exists but is
  `status: running` for retail and has no `airline/` directory at all, so per instructions it
  was skipped; no other `ctx32k_*` arm directories exist, so figure (c) currently shows only the
  BF16 pair. Re-run `make_all.sh` once more `ctx32k_*` runs complete to fill it in.

---

## 6. Caveats (carried over from STRATEGY_v2 / COLING_PLAN, still true here)

One 4B model; τ²-bench retail+airline, 85 dev tasks total; user simulator is the same frozen 4B
model as the agent; greedy decoding throughout (temperature 0 for both agent and simulator, per
`configs/frozen_v0.json`); a single bit-width (W4); a custom 8192-token truncation harness that
is not τ²'s default (`cloq/context_policy.py`). RTN is a single deterministic implementation
(n=1) with no re-roll replicates, so none of its numbers have an associated uncertainty interval
here. The "37/85 long tasks" split and its BF16-horizon values come from the frozen v0 BF16 run
(`runs/bf16`), not from `bf16_v1`; I did not re-derive horizon from `bf16_v1` and cannot rule out
a small shift if it were recomputed there instead (this mirrors the project's own frozen-split
convention, not a new limitation I introduced).

## 7. Mismatch summary (quick reference)

| item | memo value | my value | verdict |
|---|---:|---:|---|
| BF16/RTN pooled & long db_match (A5) | 0.376/0.297, 0.271/0.108 | identical | match |
| Arm permutation p, pooled/long (A2) | 0.68 / 0.36 | 0.683 / 0.368 | match |
| Draw-seed permutation p, pooled/long (A2) | 0.90 / 0.74 | 0.881 / 0.744 | match |
| v0 retail gap, point estimate (A6) | +0.121 | +0.1207 | match |
| v0 naive McNemar two-sided p (A6) | 0.039 | 0.0389 | match |
| v0 exchangeable-null one-sided p (A6) | 0.035 | 0.0195 | **mismatch** |
| Static/rest/RTN NLL, mean-of-ratios (A4/A5) | 0.094 / 0.075–0.077 / 0.157 | 0.0942 / 0.0757 / 0.1574 | match |
| RTN/Static NLL ratio (A5) | 1.7x | 1.671x | match |
| Static-vs-rest NLL permutation p (A4) | 0.0044 | 0.0011–0.0014 | close, **minor mismatch** |
| NLL vs success Spearman r, pooled/long (A4) | +0.05 / +0.04 | token-weighted: +0.054/+0.058 (match); mean-of-ratios: −0.124/−0.088 (**sign mismatch**) | convention-dependent |
| 32k BF16 retail/airline/pooled (§ "harness 敏感性") | 0.362→0.414, unchanged | identical | match |
