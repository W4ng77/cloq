# Amendment 1 to the CLOQ v1 protocol — CLOQ-MatchedRandom

Status: **frozen before any v1 closed-loop result existed.** See section 5 for the blindness record.

## 1. The defect this repairs

CLOQ-Novel currently differs from CLOQ-All along two axes at once:

- **novelty** — it takes the highest-novelty state per Q-half task;
- **trajectory depth** — as a consequence, its states concentrate in the deepest quartile
  (22–29 of 57 states, against 15 for CLOQ-All), and deep agent contexts are also the
  truncated ones (42–72% of contexts hit the 8192-token policy).

So if CLOQ-Novel wins, the result is confounded. The competing explanation is:

> Novelty did nothing. The arm simply calibrated on more late, deep, truncated contexts.

Nothing in the current four-arm design can separate those. This amendment adds the missing
control before any outcome is known.

## 2. The new arm

**CLOQ-MatchedRandom**: 28 FP states + 29 Q states per draw, same 64000 activation rows,
same task split, same three draws.

- The **FP half is bit-identical to CLOQ-Novel and CLOQ-All.** It is already produced by a
  fixed RNG stream (`[draw_seed, 0xF9]`) that does not depend on the arm, and the builder
  asserts equality against the frozen CLOQ-Novel manifest.
- The **Q half matches CLOQ-Novel's selection on every nuisance axis and differs only in the
  selection rule.** For each Q-half task, let the CLOQ-Novel pick have depth quartile `q`,
  truncation status `t`, and post-divergence flag `p`. Candidates are drawn from the same
  universe CLOQ-Novel drew from: states of that task which carry a stored novelty entry.
  Take the first non-empty tier and sample **uniformly at random** within it:

  | tier | requirement |
  |---|---|
  | 1 | post-divergence == `p` and depth quartile == `q` and truncated == `t` |
  | 2 | post-divergence == `p` and depth quartile == `q` |
  | 3 | post-divergence == `p` and depth quartile nearest to `q` |
  | 4 | depth quartile == `q` |
  | 5 | depth quartile nearest to `q` |

  Ties on "nearest quartile" break toward the lower quartile. The Q-half RNG stream is
  `[draw_seed, 0xA13]`, disjoint from CLOQ-All (`0xA11`) and CLOQ-Novel (`0xA12`).

**CLOQ-Novel's own pick stays in the candidate pool.** Excluding it would make the control
systematically lower-novelty than a true random draw within the stratum, which is a different
and weaker null. Keeping it makes the arm exactly "random within the matched stratum". The
cost is that a task with a small matched pool may hand both arms the same state, which costs
contrast power rather than validity, so the builder records the collision rate (section 4).

## 3. What the five arms then decompose

| arm | Q states | isolates |
|---|---|---|
| FP-Traj | none | nominal trajectory support |
| CLOQ-All | random on-policy | whether on-policy states help at all |
| CLOQ-MatchedRandom | post-divergence, depth- and truncation-matched | whether late / off-nominal states help |
| CLOQ-Novel | the same stratum, highest novelty | **whether the novelty score adds anything** |

The selector is only demonstrated by

> **CLOQ-Novel − CLOQ-MatchedRandom**

evaluated exactly like every other contrast: crossed bootstrap, draws resampled first, then
tasks stratified by domain, 10000 replicates, reported per draw and pooled, with the long-task
subset (BF16 horizon > 11) as the pre-specified primary stratum.

## 4. Mandatory audit, reported whether or not the arm wins

The builder records, per draw:

- `n_identical_to_novel` — Q-half tasks where the random draw returned CLOQ-Novel's own state;
- `mean_novelty_matched` against `mean_novelty_novel` — the novelty separation actually achieved;
- `matched_tier` histogram — how often exact matching was possible versus relaxed;
- the depth-quartile and truncation histograms of both arms, to confirm the match held.

**If mean novelty separation is small or the collision rate is high, the contrast is
underpowered and must be reported as inconclusive rather than as a null result.** This is
stated now, before the numbers exist, so that a small `Novel − MatchedRandom` difference
cannot later be presented as evidence that novelty does not matter when it is in fact evidence
that the control was too tight to test it.

## 5. Blindness record

At the moment this amendment was written, the v1 closed-loop evaluation had produced **no
completed run of any kind**. Stage 5 had been running for roughly 40 minutes on the BF16
baseline only:

```
runs/bf16_v1/retail    status = running
runs/bf16_v1/airline   does not exist
runs/*_dev             do not exist
```

No arm had been evaluated, so no v1 success rate, divergence statistic or open-loop number was
available to anyone. The amendment is therefore determined entirely by stage 1–4 artifacts
(calibration composition and novelty statistics), which are already reported in
`analysis/V1_STATUS_2026-09-16.md`.

## 6. Execution

The currently running stage 5–7 job over the twelve existing checkpoints is **not** interrupted.
The three CLOQ-MatchedRandom checkpoints are built and evaluated afterwards, on the same
evaluation tasks, with the same serving configuration and the same `VLLM_BATCH_INVARIANT=1`
determinism conditions.

## 7. What this amendment does not change

No existing arm, manifest, checkpoint, seed, task split, budget, decision rule or GO/Rethink
criterion is modified. Section 16 of the plan still selects between CLOQ-Novel and CLOQ-All for
the fresh test; CLOQ-MatchedRandom is a mechanism control and is not a fresh-test candidate.
