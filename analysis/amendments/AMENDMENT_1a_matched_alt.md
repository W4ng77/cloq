# Amendment 1a — CLOQ-MatchedAlt, a power repair for Amendment 1

Status: **frozen before any v1 arm was evaluated.** At writing, only `runs/bf16_v1/retail`
had completed and `runs/bf16_v1/airline` was running. No quantized arm had produced a result,
so no v1 success rate existed. See Amendment 1 section 5 for the same record one step earlier.

## 1. What the build revealed

Amendment 1 committed, in its section 4, to declaring the contrast underpowered if the
matched-random draw collided too often with CLOQ-Novel's own pick. Building the three
manifests triggers exactly that clause.

The match itself is perfect. The depth-quartile histogram of CLOQ-MatchedRandom equals
CLOQ-Novel's in all three draws (c1 9/10/9/29, c2 8/10/17/22, c3 10/11/14/22), and every
selection landed in tier 1 or 2, so quartile and post-divergence status were always matchable.

The problem is pool size. A single task has few decisions inside one depth quartile, so the
matched stratum holds a median of only 2–3 candidate states:

| draw | collisions with CLOQ-Novel | novelty separation | share of the buffer identical to CLOQ-Novel |
|---|---:|---:|---:|
| c1 | 10 / 29 | 0.145 | 67% |
| c2 | 16 / 29 | 0.052 | 77% |
| c3 | 8 / 29 | 0.070 | 63% |

Pooled, 39% of Q-half states are the same state in both arms. Combined with the FP half, which
is identical by design, **63–77% of the two buffers coincide**. Any true novelty effect is
attenuated by roughly that factor, and c2 in particular separates the arms by only 0.052 in
mean novelty.

`CLOQ-Novel − CLOQ-MatchedRandom` therefore remains valid but is expected to be
underpowered, and a null there would not be interpretable.

## 2. The added arm

**CLOQ-MatchedAlt**: identical to CLOQ-MatchedRandom in every respect — same FP half, same
tier hierarchy, same matched stratum, same RNG discipline — with one change:

> the random draw is taken from the matched stratum **excluding CLOQ-Novel's own state**.
> Tiers are descended until a tier contains at least one state other than CLOQ-Novel's pick.
> If the task offers no alternative anywhere, CLOQ-Novel's state is kept and the manifest
> records it.

RNG stream `[draw_seed, 0xA14]`, disjoint from all existing arms.

The estimand changes and this is deliberate:

- `Novel − MatchedRandom` asks: is the top-novelty state better than a **typical** state of the
  same depth? Unbiased, pre-registered, attenuated by collisions.
- `Novel − MatchedAlt` asks: is the top-novelty state better than the **alternative you would
  otherwise have taken** at the same depth? Zero collisions by construction, strictly more
  power, and a direct statement of what the selector buys.

Both are reported. Neither replaces the other, and the pre-registered contrast keeps primacy:
if the two disagree, `Novel − MatchedRandom` is the headline and `Novel − MatchedAlt` is the
power-recovering companion.

## 3. Why this is not a post-hoc baseline

The collision rate is a property of the **calibration buffers**, computed from stage 1–4
artifacts. It is visible without any closed-loop evaluation, and it was surfaced by a check
Amendment 1 pre-committed to running. No arm had been evaluated when this was written.

## 4. Cost

Three additional W4 checkpoints and one additional development evaluation pass, queued behind
the running stage 5–7 job. No existing arm, manifest, checkpoint, seed or decision rule is
modified.
