# CLOQ v1 — findings

Qwen3-4B-Instruct-2507 @ `cdbee75f17c0`, τ²-bench retail+airline text mode, GPTQ W4 g128,
64000 activation rows per arm, 57 calibration states, three independent calibration draws,
85 development tasks (37 with BF16 horizon > 11). Protocol `docs/PLAN_v1.md`, frozen constants
`configs/frozen_v1.json`. Run 2026-09-16 15:36 → 2026-09-17 15:24 on 2×RTX 4080.

---

## 1. Headline

**The method does not work, and the control arm added before any result existed is what
established that.**

CLOQ-Novel — select the highest-novelty post-divergence states for calibration refresh — is the
**worst** quantized arm on long-horizon tasks. The two matched controls, which take a *random*
state from the same depth/truncation/post-divergence stratum, are the **best**.

Worse for the method, the proposed mechanism was achieved and did not deliver. CLOQ-Novel has
the **best support coverage of any arm** and the **smallest post-divergence support shift of any
arm**, and still ends up last. The chain's first three links replicate; the fourth is falsified
in the strong form, and the failure is not "we failed to move the representation" but "we moved
it exactly as intended and behaviour did not follow".

---

## 2. Primary endpoint: database end-state match

Mean over three draws. BF16 reference 0.376 pooled / 0.297 long.

| arm | long | pooled | long range across draws |
|---|---:|---:|---|
| CLOQ-MatchedAlt | **0.216** | **0.357** | 0.162 – 0.270 |
| CLOQ-MatchedRandom | **0.216** | 0.345 | 0.189 – 0.243 |
| Static | 0.189 | 0.341 | 0.162 – 0.243 |
| CLOQ-All | 0.171 | 0.337 | 0.081 – 0.243 |
| FP-Traj | 0.144 | 0.306 | 0.054 – 0.243 |
| **CLOQ-Novel** | **0.117** | 0.306 | 0.081 – 0.162 |

The pre-registered selection rule (plan §16) selected **CLOQ-All**, not CLOQ-Novel:
long-task means 0.171 vs 0.117, pooled 0.337 vs 0.306.

### Crossed bootstrap (resample draw, then tasks within domain; 10000 replicates)

| contrast | pooled | 95% CI | long | 95% CI |
|---|---:|---|---:|---|
| cloq_novel − cloq_matched_random | −0.039 | [−0.141, 0.082] | **−0.099** | [−0.243, 0.054] |
| cloq_novel − cloq_matched_alt | −0.051 | [−0.188, 0.094] | **−0.099** | [−0.243, 0.027] |
| cloq_novel − cloq_all | −0.031 | [−0.165, 0.094] | −0.054 | [−0.243, 0.135] |
| cloq_novel − static | −0.035 | [−0.141, 0.059] | −0.072 | [−0.216, 0.054] |
| cloq_matched_random − cloq_all | 0.008 | [−0.094, 0.118] | 0.045 | [−0.108, 0.243] |
| cloq_matched_alt − cloq_all | 0.020 | [−0.188, 0.176] | 0.045 | [−0.189, 0.243] |
| cloq_matched_random − fp_traj | 0.039 | [−0.129, 0.188] | 0.072 | [−0.162, 0.297] |
| fp_traj − static | −0.035 | [−0.176, 0.129] | −0.045 | [−0.297, 0.216] |
| bf16 − cloq_novel | 0.071 | [−0.035, 0.176] | **0.180** | **[0.027, 0.351]** |

**Every arm-versus-arm interval crosses zero.** The single interval excluding zero is BF16
beating CLOQ-Novel on long tasks. Nothing here is a significant method difference in either
direction; what follows is point estimates and their consistency, stated as such.

### The secondary endpoint agrees

The τ²-style language judge, which never sees the database, orders the arms the same way:
MatchedRandom 0.319, MatchedAlt 0.312, CLOQ-All 0.293, Static 0.287, FP-Traj 0.287,
**CLOQ-Novel 0.280**, BF16 0.340. The result is not an artifact of the primary endpoint.

---

## 3. The pre-committed caveat now argues against the method

Amendment 1 §4, frozen before any arm was evaluated, committed to this in writing:

> If mean novelty separation is small or the collision rate is high, the contrast is
> underpowered and must be reported as inconclusive rather than as a null result.

The collision rate *is* high. The matched stratum holds a median of 2–3 candidate states, so the
unbiased draw returns CLOQ-Novel's own state for 39% of Q-half tasks, and 63–77% of the two
buffers coincide.

**But the caveat does not rescue CLOQ-Novel, and applying it honestly makes the negative reading
stronger.** Two reasons:

1. We did not observe a null. We observed a **negative** point estimate, −0.099 on long tasks.
   Buffer overlap attenuates a difference *toward zero*, so the underlying difference is more
   likely to be more negative than −0.099, not less.
2. CLOQ-MatchedAlt was added precisely to remove the overlap. It collides on 0/2/2 of 29 tasks
   and roughly doubles the novelty separation, and it returns **the same −0.099**.

| arm | draw | same state as Novel | novelty (Novel) | novelty (control) | separation |
|---|---|---|---|---|---|
| MatchedRandom | c1 | 10/29 | 0.320 | 0.175 | 0.145 |
| MatchedRandom | c2 | 16/29 | 0.165 | 0.113 | 0.052 |
| MatchedRandom | c3 | 8/29 | 0.177 | 0.107 | 0.070 |
| MatchedAlt | c1 | 0/29 | 0.320 | 0.115 | 0.205 |
| MatchedAlt | c2 | 2/29 | 0.165 | 0.059 | 0.105 |
| MatchedAlt | c3 | 2/29 | 0.177 | 0.089 | 0.087 |

Both controls hold CLOQ-Novel's depth-quartile histogram exactly, in all three draws, so the
depth confound this amendment existed to remove is in fact removed.

---

## 4. The decisive result: the mechanism was achieved and did not transfer

Support distance from an arm's own visited states to its own calibration buffer, in the frozen
BF16 representation. Lower means the buffer covers where that policy actually goes.

| arm | self-coverage | pre-divergence | post-divergence | shift | MMD(FP,Q) | long SR |
|---|---:|---:|---:|---:|---:|---:|
| Static | 0.1898 | 0.0399 | 0.2079 | +0.1679 | 0.0766 | 0.189 |
| FP-Traj | 0.1261 | 0.0362 | 0.1392 | +0.1030 | 0.0956 | 0.144 |
| CLOQ-All | 0.0694 | 0.0364 | 0.0747 | +0.0383 | 0.0783 | 0.171 |
| **CLOQ-Novel** | **0.0597** | 0.0482 | 0.0615 | **+0.0133** | **0.0451** | **0.117** |
| MatchedRandom | 0.0687 | 0.0499 | 0.0718 | +0.0220 | 0.0898 | 0.216 |
| MatchedAlt | 0.0781 | 0.0480 | 0.0826 | +0.0346 | 0.1035 | 0.216 |

MMD empirical null (BF16 split-half) = −0.0003.

Read the CLOQ-Novel row against the last column. It has the **best** coverage, the **smallest**
post-divergence shift — the shift is nearly eliminated, 0.0133 against Static's 0.1679 — and the
**lowest** MMD, and it has the **worst** long-task success. The selector did its job at the
representation level. Success did not follow.

This is the cleanest possible refutation of the hypothesis as stated. It is not that occupancy
repair was attempted and failed to materialise; it is that occupancy repair **succeeded** and
carried no behavioural benefit. v0 already cautioned against reading lower global MMD as higher
success; v1 turns that caution into a demonstration, since MMD orders CLOQ-Novel best and
success orders it last.

---

## 5. v0's one significant method result did not replicate

v0 reported FP-Traj beating Static on retail by +0.121, 95% CI [+0.034, +0.224], on both the
database endpoint and the judge endpoint, and recorded it as continuation signal C.

Under three calibration draws that becomes **−0.035 pooled and −0.045 on long tasks**, with the
sign reversed and both intervals spanning zero, and it is not positive in all three draws.

v0's result was a single-draw artifact. This is exactly the failure mode the three-draw design
was built to detect, and detecting it is arguably the most transferable thing in this study.

---

## 6. Draw variance dominates method effect

Same W4 recipe, same row budget, same agent, same tasks. Only the calibration draw differs:

- FP-Traj long-task success: **0.054 → 0.243 across draws**, a 4.5× range.
- CLOQ-All long-task success: 0.081 → 0.243.
- MatchedAlt airline: 0.519 on c1 against 0.222 on c3.

Every between-arm point estimate in §2 is smaller than this within-arm spread. In ordinary LM
quantization, calibration-sample choice moves perplexity in the third decimal; in a long-horizon
agent the closed loop amplifies it into visibly different policies. **Any single-draw agent
quantization result should be treated as uninterpretable**, including v0's.

---

## 7. What did replicate

**Horizon amplification (link 1).** The quantization gap is concentrated in long tasks for every
arm. Short-task gaps run −0.028 to +0.007; long-task gaps run +0.081 to +0.180; amplification
+0.088 to +0.194.

**Open-loop fidelity overstates closed-loop reliability (link 2), more sharply than in v0.**

| arm | tool-name agr. | full tool-call agr. | NLL/token | long SR |
|---|---:|---:|---:|---:|
| Static | 0.889 | 0.814 | 0.0962 | 0.189 |
| FP-Traj | 0.905 | 0.843 | 0.0785 | 0.144 |
| CLOQ-All | 0.898 | 0.836 | 0.0772 | 0.171 |
| **CLOQ-Novel** | 0.901 | **0.840** | **0.0769** | **0.117** |
| MatchedRandom | 0.900 | 0.829 | 0.0783 | 0.216 |
| MatchedAlt | 0.900 | 0.828 | 0.0776 | 0.216 |

CLOQ-Novel has the best teacher-forced NLL and near-best tool-call agreement while having the
worst closed-loop long-task success. Open-loop fidelity spans 0.814–0.843 while long-task
success spans 0.117–0.216, and the two orderings are close to inverted.

**Post-divergence support shift (link 3).** Present for every arm (§4), with MMD far above the
BF16 split-half null.

**First divergence.** Essentially invariant across arms: 96.2–97.1% of tasks diverge, median
t*/H 0.291–0.302. Whatever the calibration buffer contains, the quantized policy leaves the
nominal path at the same point.

---

## 8. Decision rules

Evaluated against the criteria frozen in `docs/PLAN_v1.md` §19 before any v1 run.

- **Strong GO — not met.** CLOQ-Novel does not beat Static on long tasks; the point estimate is
  −0.072 and the interval spans zero.
- **Rethink clause 1 — FIRED.** "Three draws show no reproducible Static versus trajectory
  difference." FP-Traj − Static is −0.035 pooled with the sign reversed from v0.
- **Rethink clause 2 — not met.** CLOQ-Novel *does* improve support coverage over CLOQ-All
  (0.0597 vs 0.0694). The selector works; the benefit does not appear in behaviour.
- **Rethink clause 3 — not met.** Novelty-selected states are related to post-divergence
  behaviour by construction, and §4 shows they do reduce the post-divergence shift.

**Rethink has fired.** The recommendation is not to escalate to 7B in search of a positive
result, which §19 explicitly warns against.

---

## 9. What this study now says

The publishable claim is no longer "closed-loop support refresh repairs quantized agents". On
this evidence it is closer to:

> Long-horizon agents expose quantization failures that nominal and open-loop evaluation hide.
> The quantized policy leaves nominal calibration support almost immediately and stays outside
> it. But repairing that support does not repair behaviour: the arm that best covers its own
> post-divergence occupancy performs worst, and the dominant source of variation is not the
> calibration strategy at all but which calibration sample you happened to draw.

Three things that survive and are worth writing up:

1. **Token-matched is not support-matched.** A 64k-token budget buys ~10 agent contexts; state
   diversity is itself the scarce calibration resource for agent PTQ.
2. **Single-draw agent quantization results are not trustworthy.** Demonstrated by v0's signal C
   failing to replicate under three draws.
3. **Occupancy coverage is not a sufficient proxy for closed-loop success.** Demonstrated
   directly, with the coverage-best arm performing worst.

Worth testing next, in rough order: whether *any* calibration strategy beats draw variance at
this scale, which needs more draws before more arms; and the 16k/32k context control, since
42–72% of decisions truncate under the 8192-token policy and that is the most obvious
alternative explanation for the horizon effect. Both are better uses of a larger machine than a
bigger model. See `HANDOFF.md` §4.

---

## 10. Execution record

```
[2026-09-16 15:36:21] === stage5 starting        12 checkpoints x 2 domains, closed loop
[2026-09-17 02:08:05] === stage5 finished        10h32m
[2026-09-17 02:08:05] === stage6 starting        open-loop replay
[2026-09-17 05:20:51] === stage6 finished         3h13m
[2026-09-17 05:20:51] === stage7 starting        occupancy extraction + report
[2026-09-17 07:59:03] === stage7 finished         2h38m
[2026-09-17 07:59:03] PIPELINE V1 DONE: stage5 stage6 stage7

[2026-09-17 07:59:58] pipeline_v1.sh is no longer running; proceeding
[2026-09-17 08:00:07] === a1 starting            quantize 6 control checkpoints
[2026-09-17 08:00:16] === a1 finished            9 SECONDS - already built, see below
[2026-09-17 08:00:16] === a2 starting            control closed-loop evaluation
[2026-09-17 11:31:47] === a2 finished             3h31m
[2026-09-17 11:31:47] === a3 starting            control open-loop replay
[2026-09-17 13:42:49] === a3 finished             2h11m
[2026-09-17 13:42:49] === a4 starting            occupancy + report
[2026-09-17 14:57:04] === a4 finished             1h14m
[2026-09-17 14:57:04] AMENDMENT 1 PIPELINE DONE: a1 a2 a3 a4
[2026-09-17 15:24:01] REPAIR DONE
```

### Both GPUs, after the user simulator was found idling

Open-loop replay never calls the user simulator (`cloq/openloop.py` only uses `--agent-base`),
so during stage 6 GPU 0 held a 14.8 GB reservation and did nothing. Stopping it freed the card
for two jobs that were otherwise queued behind ~12 hours of work:

```
[2026-09-17 02:44:51] gpu0 building ckpts/v1/cloq_matched_random_c1_w4
[2026-09-17 03:19:41] gpu0 queue finished                 <- all 6 control checkpoints, 35 min
```

which is why `a1` above took 9 seconds instead of 35 minutes. GPU 0 then helped with stage 6
itself, working the queue backwards while the pipeline worked forwards:

```
[2026-09-17 03:19:43] GPU0 helper starting; stage6 currently at index 3
[2026-09-17 03:19:43] taking cloq_novel_c3 (index 11, stage6 at 3)
[2026-09-17 03:42:40] taking cloq_novel_c2 (index 10, stage6 at 4)
[2026-09-17 04:05:08] taking cloq_novel_c1 (index 9, stage6 at 5)
[2026-09-17 04:27:35] STOP: stage6 at index 6 is within 2 of target cloq_all_c3 (index 8); leaving the rest to it
```

The collision guard fired as designed and stopped rather than racing the pipeline for a
checkpoint. Three of twelve open-loop checkpoints were absorbed this way.

### Pre-registration

```
51c8dd8 Freeze Amendment 1: CLOQ-MatchedRandom control, before any v1 result exists
b4a6e37 Freeze Amendment 1a: CLOQ-MatchedAlt, before any v1 arm was evaluated
0a2c845 Build the Amendment 1/1a control arms: CLOQ-MatchedRandom and CLOQ-MatchedAlt
```

Amendment 1 was committed while only `runs/bf16_v1/retail` existed and was still running; no
quantized arm had produced a number. Amendment 1a was committed while only the BF16 baseline
existed. Both texts are in `analysis/amendments/`. All twelve pre-existing calibration manifests
were verified to rebuild bit-identically after the code changes, activation-row indices included,
so no pre-registered arm was disturbed.

---

## 11. Defects found during the run

**Variable scoping in `scripts/pipeline_v1.sh` stage 5.** `eval_ckpt` looped `for d in $DOMAINS`
without `local`. Bash functions share the caller's scope, so the draw variable was overwritten
with `airline` after every call, and the divergence and judge steps addressed run ids like
`static_airline_dev`:

```
[2026-09-17 ...] WARN divergence static_airline/retail
FileNotFoundError: [Errno 2] No such file or directory: 'runs/static_airline_dev/retail/trajectory.jsonl'
```

**Closed-loop results are unaffected** — the run id is expanded at the call site, before the
clobber — so no success rate in this report depends on it. Two post-hoc artifacts were lost and
both were regenerated: all 24 divergence files (CPU only, under two minutes) and all 36
`task_success.json` files. Fixed with `local` in commit `7381c5a`; `pipeline_v1.sh` itself was
deliberately not edited while running, because bash reads a script lazily by byte offset.

**Crash in `cloq/openloop.py` argument comparison.** One of 36 open-loop runs died with

```
AttributeError: 'str' object has no attribute 'items'
```

because the quantized model emitted a tool-call argument blob as a bare JSON string rather than
an object, and `arg_metrics` called `.items()` on it unconditionally. A malformed argument blob
now scores as a mismatch and is flagged, rather than destroying the domain's entire summary. The
helper is behaviour-identical on every input that did not previously crash, verified case by
case, so the other 35 summaries remain valid. `cloq_all_c3/airline` was regenerated;
all 36 open-loop summaries and all 36 judge files are now present.

---

## 12. Reproduction

```
analysis/v1/REPORT_V1.md          auto-generated tables and crossed bootstrap
analysis/v1/results_v1.json       machine-readable
analysis/v1/occupancy_{c1,c2,c3}.json   support distances, pre/post divergence, MMD
analysis/amendments/              the two frozen protocol amendments
manifests/v1/                     calibration + activation-row manifests for all 18 checkpoints
runs/<arm>_<draw>_dev/<domain>/   metrics, decisions, divergence, task_success, openloop, reps
docs/PLAN_v1.md                   protocol, §16 selection rule, §19 go/rethink criteria
```

Regenerate the tables with `python -m cloq.report_v1`. Determinism requires
`VLLM_BATCH_INVARIANT=1` and an unchanged serving configuration; v0 verified a zero noise floor
under those conditions via `scripts/bf16_replicate.sh`, which should be re-run before results
from a different machine are compared against these.
