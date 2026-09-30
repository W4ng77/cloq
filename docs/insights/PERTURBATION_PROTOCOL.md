**TL;DR** Protocol `perturb-v1` (fixed 2026-09-30, before any restoration or dose outcome): two derived checkpoint kinds built from one cached fake-quant checkpoint Q and its BF16 source W.
- `restore` copies BF16 weights back into early / middle / late layer thirds, into attention-only or MLP-only linears, or into byte-matched random module sets (3 seeds per budget).
- `resid` is the residual intervention W_α = W + α(W_Q − W), α ∈ {0, 0.25, 0.5, 1, 2}. It is not a bit width.
- α = 0 and the `all` arm equal BF16 bit for bit; α = 1 and the `none` arm equal Q bit for bit. CPU tests check this, and each build re-checks it.
- Evidence: `cloq/perturb.py`, `scripts/a6000/derived.py`, `tests/test_perturb.py` (→ `tests/out/test_perturb.json`), `manifests/perturb/restore_v1/{q4,q8}/*.json`, smoke tasks `pert_smoke_*` (queue `/data/ziyangs/cloq_work/queue/{done,failed}`).

# Perturbation protocol: local precision restoration and residual dose (perturb-v1)

Execution plan P2 (`docs/EXECUTION_PLAN_20260930.md` §2): Figure 4 (local restoration, deployment claim) and Figure 2 (error dose). Primary checkpoints follow `manifests/fork/dev_blocks_v1.json`:
- models: q4 = Qwen3-4B-Instruct-2507 and q8 = Qwen3-8B;
- Q: GPTQ-W4 d1 and AWQ-W4 d1;
- calibration: draw c1 (`manifests/a6k2/<model>/calib_fp_traj_c1.json`).

## 1. Objects

- **W** is the pinned BF16 snapshot (`scripts/a6000/models.json`).
- **Q** is the fake-quant checkpoint built by `cloq.quantize`. It is BF16 storage, and only the 252 decoder linears differ from W (q, k, v, o, gate, up, down × 36 layers). The builder checks that embeddings, norms and the lm_head of Q are bit-identical to W, and refuses to build otherwise. Rotated (QuaRot) Q checkpoints are refused.
- **Derived checkpoint**: each decoder linear comes from W, from Q, or from W + α(Q − W). Every other tensor comes from W. The shard layout and non-weight files are those of W, so vLLM serves it through the same BF16 path as W and Q.

## 2. Arms

### 2.1 Restoration (`restore`, manifest-driven)

| Arm | Linears restored to BF16 | Seeds |
|---|---|---|
| `early` / `middle` / `late` | all 7 linears of layers 0–11 / 12–23 / 24–35. Thirds are equal size; if the layer count is not divisible by 3, the earlier thirds get the extra layer | — |
| `attn` | q, k, v, o of all 36 layers | — |
| `mlp` | gate, up, down of all 36 layers | — |
| `rand_third_s{1,2,3}` | random linears whose BF16 parameter bytes match one third | 1, 2, 3 |
| `rand_attn_s{1,2,3}` | random linears matched to `attn` | 1, 2, 3 |
| `rand_mlp_s{1,2,3}` | random linears matched to `mlp` | 1, 2, 3 |
| `none` / `all` (controls) | nothing (= Q) / everything (= W) | — |

**Random draws**
- The three thirds have identical byte budgets on q4 and q8 (36 layers). One random family therefore serves all three thirds. If the layer count were not divisible by 3, the generator would create one family per third.
- Draw: `random.Random("cloq-perturb-v1|restore|<model>|<revision>|<budget>|<seed>|<try>")`.
  - Python seeds it through SHA-512 of the string, so it does not depend on the process or `PYTHONHASHSEED` (tested).
  - The draw shuffles all 252 linears, then fills greedily with every linear that still fits under the target.
  - The first try that lands within the pre-declared tolerance wins: `RAND_TOL` = 0.5 % of the matched arm's restored parameters, never above target.
  - Draws depend only on the model, never on the method or on any outcome. GPTQ and AWQ bases therefore get the same random module sets.

**Matching is by bytes, not by module count.** Random arms restore 55–204 linears against 84 / 144 / 108 in the structured arms.

### 2.2 Residual dose (`resid`)

- **Formula:** W_α = W + α(W_Q − W) per decoder linear. It is computed with three separate fp32 CPU ops (subtract, scale, add), then one round-to-nearest-even cast to BF16.
- **Endpoints:** α = 0 and α = 1 are the endpoint tensors themselves, copied bit for bit.
  - This rule is needed. Evaluating the literal formula at α = 0 turns every −0.0 weight into +0.0. The tiny test model has one such weight per linear, and the test measures 42 bit differences over 42 linears.
  - At α = 1 the literal formula happens to be exact in the test (0 differences). The copy rule still makes α = 1 exact by construction.
- **Rounding at interior α:** BF16 rounding moves the realised dose slightly. Every build records the realised dose `eff_alpha` = ⟨W_α − W, Q − W⟩ / ‖Q − W‖². The tiny test gives 0.25002 / 0.49998 / 1.99990.
- **Labelling:** these are residual interventions, labelled `resid_a<α>`. α = 0.5 is not "W5/W6" and α = 2 is not "W3". W_2 extrapolates beyond Q along the quantizer's own error direction, and nothing guarantees it lies on any quantization grid.

### 2.3 KV-side restoration: configuration only

KV restoration uses the existing fake KV hook (`scripts/a6000/pyhooks/cloq_kvq.py`, RESEARCH_LOG W13) through `serve_env`. Nothing is reimplemented:

| Intent | serve_env |
|---|---|
| KV INT-b on both K and V | `{"CLOQ_PYHOOKS": "1", "CLOQ_KVQ_BITS": "b"}` (`CLOQ_KVQ_WHICH` defaults to `kv`) |
| **K kept high precision** (quantize V only) | `... "CLOQ_KVQ_WHICH": "v"` |
| **V kept high precision** (quantize K only) | `... "CLOQ_KVQ_WHICH": "k"` |
| Hadamard-rotated variant | add `"CLOQ_KVQ_ROT": "1"` |
| hook installed, pass-through (flavour control) | `"CLOQ_KVQ_BITS": "16"` |

- **Where the config goes:**
  - eval tasks: the task's `serve_env`;
  - forks: the per-role `{"B": {"ckpt": …, "serve_env": {…}}, "Q": {…}}` config (e.g. `fork_accept_kvq_q4`).
- **Combining with weights:** KV and weight restoration combine freely, e.g. a `restore_late` ckpt with `CLOQ_KVQ_WHICH=v`.
- **Canary:** a KV-hooked server is a different numerics flavour, so the derived-ckpt canary rules below are skipped under the hook, as for BF16 + hook.

## 3. Budgets (pre-declared accounting)

**What each arm records.** Every manifest records:
- `restored_params` and `restored_bf16_bytes` (= 2 × params);
- a simulated storage budget for a real packed deployment:
  - kept W4 linears: 4-bit codes, plus per (row, 128-column group) one fp16 scale and one 4-bit zero point, plus method side information. For GPTQ with act-order this is the `g_idx` (int32 per input column). For AWQ it is a per-input-channel fp16 scale; `cloq.quantize` folds it into the weight, but the budget counts it.
  - restored linears: BF16.

**What is excluded.** Embeddings, norms and the lm_head are BF16 in every arm and in Q, and are left out of the linear budget. Their bytes are constant across arms.

**Byte matching** (q4 = Qwen3-4B-Instruct-2507, 3.633 B linear params; generated from the safetensors headers by `python -m cloq.perturb manifests`):

| arm | family | n linears | restored params | BF16 GB | frac | Δ vs matched | sim bits/param GPTQ | AWQ |
|---|---|---|---|---|---|---|---|---|
| none | control | 0 | 0 | 0.000 | 0.0000 | — | 4.165 | 4.160 |
| early / middle / late | structured | 84 each | 1,211,105,280 | 2.422 | 0.3333 | — | 8.110 | 8.107 |
| attn | structured | 144 | 943,718,400 | 1.887 | 0.2597 | — | 7.237 | 7.235 |
| mlp | structured | 108 | 2,689,597,440 | 5.379 | 0.7403 | — | 12.927 | 12.926 |
| all | control | 252 | 3,633,315,840 | 7.267 | 1.0000 | — | 16.000 | 16.000 |
| rand_third_s1/s2/s3 | random | 84 / 87 / 89 | 1,209,794,560 / 1,211,105,280 / 1,209,794,560 | 2.420–2.422 | 0.3330–0.3333 | −0.108 % / 0 / −0.108 % | 8.105–8.110 | 8.103–8.107 |
| rand_attn_s1/s2/s3 | random | 66 / 68 / 81 | 943,718,400 / 942,407,680 / 942,407,680 | 1.885–1.887 | 0.2594–0.2597 | 0 / −0.139 % / −0.139 % | 7.234–7.239 | 7.231–7.236 |
| rand_mlp_s1/s2/s3 | random | 187 each | 2,689,597,440 / 2,688,286,720 / 2,689,597,440 | 5.377–5.379 | 0.7399–0.7403 | 0 / −0.049 % / 0 | 12.922–12.926 | 12.920–12.925 |

q8 = Qwen3-8B, 6.946 B linear params. All nine random arms match exactly (Δ = 0):

| arm | n linears | restored params | BF16 GB | frac | sim bits/param GPTQ / AWQ |
|---|---|---|---|---|---|
| none | 0 | 0 | 0 | 0 | 4.162 / 4.159 |
| early / middle / late | 84 each | 2,315,255,808 | 4.631 | 0.3333 | 8.108 / 8.106 |
| attn | 144 | 1,509,949,440 | 3.020 | 0.2174 | 6.734 / 6.733 |
| mlp | 108 | 5,435,817,984 | 10.872 | 0.7826 | 13.428 / 13.427 |
| rand_third_s1/s2/s3 | 90 / 96 / 82 | 2,315,255,808 | 4.631 | 0.3333 | 8.108 / 8.106 |
| rand_attn_s1/s2/s3 | 61 / 66 / 55 | 1,509,949,440 | 3.020 | 0.2174 | 6.736 / 6.733 |
| rand_mlp_s1/s2/s3 | 204 / 200 / 196 | 5,435,817,984 | 10.872 | 0.7826 | 13.426 / 13.426 |

Because parameter bytes match, the simulated budgets also match to within 0.005 bits/param. The small remainder is side information that scales with input columns, not with parameters.

## 3a. Damage-regime base (W50): GPTQ-W3 c1

**Why a second base.** On the development blocks, q4 GPTQ-W4 d1 does not lose success relative to BF16 (Q 43.9 vs BF16 33.7 on f01–f03; `analysis/fork/out/restore_eval_20260930T122705Z.md`). Every restoration arm therefore moves success *down* toward BF16. In that regime, "gap closed" measures reversion toward BF16, not recovery of lost performance. W4 is in the equivalence regime, so there the behavioural endpoint (§4a) is primary.

**The W3 arms**
- Base: GPTQ-W3 with calibration c1 (`{"kind": "gptq", "wbits": 3, "calib": …c1}`), cell `gptq_w3`, for q4 and q8.
- Arms, the same 17: early, middle, late, attn, mlp; `rand_{third,attn,mlp}_s{1,2,3}`; resid α ∈ {0.25, 0.5, 2}.
- Blocks: q3–q5 (nonces 4c8e1a7f, b9d2e605, e1a47c3d). Both models already have W3 Q runs `a6k2_<m>_gptq_w3_<blk>` and BF16 pairs `a6k2_<m>_bfpair_<blk>` on these blocks, and the generator checks that before writing.

**Budgets**
- The module sets are unchanged. They are matched on BF16 parameter bytes, which do not depend on the base's bit width.
- The simulated storage is recomputed as `budget_w3` in every manifest: 3-bit codes, plus one fp16 scale and one 3-bit zero per (row, 128 columns), plus the same side information as for W4.
- Q alone: q4 3.157 and q8 3.155 simulated bits/param (GPTQ).

| model | arm | W3 sim bits/param, structured | W3 sim bits/param, random s1 / s2 / s3 |
|---|---|---|---|
| q4 | third | 7.438 | 7.433 / 7.438 / 7.433 |
| q4 | attn | 6.491 | 6.493 / 6.488 / 6.488 |
| q4 | mlp | 12.666 | 12.664 / 12.659 / 12.664 |
| q8 | third | 7.436 | 7.436 / 7.436 / 7.436 |
| q8 | attn | 5.946 | 5.947 / 5.947 / 5.947 |
| q8 | mlp | 13.209 | 13.207 / 13.207 / 13.208 |

`tests/test_perturb.py` checks:
- the W3 hand count;
- W3 exactness (resid and restore on an RTN-W3 base);
- that a W3 build records `budget_w3`;
- that every random arm's W3 simulated budget is within 0.5 % of its structured arm.

## 4a. Endpoints by regime (W50)

`analysis/fork/analyze_restore_eval.py` reports two groups of columns.

**Success** (kept): Q, arm and BF16 success, and "gap closed" = (arm − Q)/(BF16 − Q).

**Behavioural**, where the reference is BF16 rather than success:
- Turnover to BF16: T(X) = P(outcome of X ≠ outcome of BF16). Turnover closed = 1 − T(arm)/T(Q), computed per bootstrap draw with the same hierarchical bootstrap.
- Decision level, from `decisions.jsonl`:
  - token level: the first decision whose prompt or completion tokens differ from BF16. At W4 this saturates, since almost every episode differs from BF16 within one or two decisions.
  - action level: the first decision whose action signature (kind plus normalised tool calls, wording ignored) differs.
  - Both levels give the divergence rate, divergence closed, prefix agreement (first-divergence index / BF16 decisions), and later / earlier than Q.

**Which is primary**
- W4 (equivalence): the behavioural endpoint is primary.
- W3 (damage): success and behaviour are co-primary.

The action level is not a same-state comparison once the wording has diverged; same-state claims remain the fork protocol's.

## 3b. Telecom W4-damage cell (W53): q8 AWQ-W4 c1 on telecom dev

- **Base:** the same cached base as W40 (`q8_awq_8a97d2f7b45b`, W4 budgets of §3).
- **Arms (9):** early, middle, late, attn, mlp; `rand_{third,attn,mlp}_s1`; resid α 0.5.
- **Blocks:** telecom dev f01–f06 (`manifests/telecom/dev_v1.json`); the holdout is never used.
- **Pairing:** arms pair with `a6k2_q8_tel_awq_w4_<blk>` and `a6k2_q8_tel_bfpair_<blk>`.
- **Reporting:** `analyze_restore_eval.py` gives this cell its own bootstrap population and a persona breakdown (Hard / Easy / None). Success and behaviour are co-primary here.
- **Caveat:** on f01–f06 the Q–BF16 gap itself is not significant (+2.7 pp [−2.9, +9.2]; Hard +7.3 [−2.6, +19.0]), and on f01–f03 it is exactly 0.

## 3c. Plain restore vs `restore_recal` (W54)

**Plain `restore` is a post-hoc swap.** It takes the finished Q and copies the chosen modules back to BF16. GPTQ and AWQ in `cloq/quantize.py` run true-sequential: every module is calibrated on inputs produced by the already-quantized upstream modules, so part of each module's quantization error is compensated downstream.

**Why that matters.** After a swap, the downstream quantized modules see BF16-upstream inputs they were not calibrated for. Their compensation no longer matches, and the absolute recovery of a plain restore arm is confounded by this mismatch. It penalises early and middle arms most, since they have the most downstream modules. The byte-matched random arms carry the same kind of mismatch, so the structured vs random comparison within the plain family stays fair. The absolute "gap closed" does not.

**`restore_recal` is the rebuilt mixed-precision checkpoint** a practitioner would build.
- The chosen modules stay BF16.
- The base's sequential GPTQ/AWQ is re-run for every remaining module: same calibration manifest (c1), same settings, same seed (`cloq.quantize --keep <arm manifest>`).
- Downstream modules are therefore calibrated on the mixed-precision upstream.
- Bits accounting is identical to the plain arm (`budget` / `budget_w3`).
- Exactness (CPU tests on a tiny Qwen3):
  - an empty keep set equals Q bit for bit;
  - keep = all equals BF16;
  - modules before the first kept module, and its same-group siblings, equal Q;
  - GPTQ re-calibrates every downstream module (14/14 in the test). AWQ re-calibrates most: a module whose best scale exponent is 0 is plain RTN and legitimately does not change (13/14).
- Cost: one GPTQ/AWQ run per arm (q4 ~7 min, q8 ~11 min).
- Storage: built per task in node-local scratch. They are not added to the persistent base cache, where the 16 W3 arms would need ~190 GB. Reproducibility is enforced by the per-tag registry (files sha).

**Compensation effect.** `analyze_restore_eval.py` reports `restore_recal_<X>` − `restore_<X>` on paired units, for success and for turnover to BF16.

## 3d. RTN-W3: the primary damage regime (W60)

**Why RTN-W3 is primary.** On blocks q3–q5, closed-loop db_match success is:

| model | BF16 | GPTQ-W3 | RTN-W3 |
|---|---|---|---|
| q4 | 35.7 | 36.1 | 13.5 |
| q8 | 30.6 | 26.7 | 13.3 |

GPTQ-W3 barely damages q4 and costs q8 about 4 pp. RTN-W3 costs 17–22 pp, so it is the primary damage regime, with success and behaviour co-primary.

**No confound.** RTN quantizes every linear independently and has no calibration and no sequential compensation. A plain `restore` on an RTN-W3 base is therefore exactly "these modules BF16, every other linear its own RTN-W3". The compensation confound of §3c does not arise, and no `restore_recal` variant is needed.

**Arms**
- Base: `{"kind": "rtn", "wbits": 3}`, the same spec as the `a6k2_<m>_rtn_w3_*` Q runs.
- Arms: the 17 W3 arms (5 structured, 9 random, resid α 0.25/0.5/2) for q4 and q8 on q3–q5.
- Pairing: `a6k2_<m>_rtn_w3_<blk>` and `a6k2_<m>_bfpair_<blk>`.

**Budget:** `budget_w3.rtn` is 3-bit codes plus one fp16 scale and one 3-bit zero per (row, 128 columns), with no g_idx. Storage is therefore exactly proportional to parameters:
- Q: 3.148 bits/param;
- a third: 7.432;
- attn: 6.487 (q4) / 5.942 (q8);
- mlp: 12.662 (q4) / 13.206 (q8).

Random arms with Δ = 0 match their structured arm exactly.

**GPTQ-W3 is secondary.** Its plain and recal arms now measure only the compensation effect.

## 3e. Storage-matched deployment baseline (W64)

**What an arm must beat.** An RTN-W3 restoration arm is a *mechanism stress test*. It becomes a candidate precision-allocation method only if it beats whole-model quantizers at the same or lower simulated storage: GPTQ-W3 d1 (3.16 b), AWQ-W3 d1, GPTQ-W4 d1 and AWQ-W4 d1 (4.16 b).

**How it is compared.** Arms are compared on the same tasks × q3–q5 blocks, paired. The table and the frontier plot come from `analyze_restore_eval.py`. For example, a third of the linears in BF16 costs 7.43 b/param and must exceed GPTQ-W4 d1's success to support a deployment claim.

**Residual-dose arms** are not storage configurations and have no bits.

## 4. What each arm can and cannot show

| Arm | Can show | Cannot show |
|---|---|---|
| early / middle / late vs `rand_third` | Whether where the quantization error sits in depth matters beyond how much is removed. If one third's rescue exceeds the random spread (3 seeds) at an equal byte budget, depth location matters for that model × method | Why. Thirds differ in weight statistics, relative error norms (see the `per_linear` stats in quantization.json) and downstream amplification, and the arm cannot separate these. A third that helps is not proof that its layers "decide" actions. With 3 seeds, the random spread is a coarse reference, not a null distribution |
| attn vs mlp | Whether attention or MLP error dominates the closed-loop effect, *given unequal budgets* (q4: 26 % vs 74 % of linear params) | A per-byte comparison between attn and mlp directly. Each must be compared with its own random family (`rand_attn`, `rand_mlp`) |
| `rand_*` | Budget-only baseline: the effect of removing that fraction of the error at random | A uniform-over-bytes null. Greedy filling over-represents small modules; q4 `rand_attn_s1` restores 14 k_proj vs 5 q_proj. `rand_mlp` restores 74 % / 78 % of all linears, so it overlaps heavily with `mlp` and with every other arm, and differences there have little power |
| none / all | Pipeline controls: the derived path reproduces Q and BF16 exactly, both in bits and in the served canary | — |
| resid α ∈ {0, 0.25, 0.5, 1, 2} | The dose–response shape along the quantizer's own error direction: monotone, threshold or non-monotone. α = 2 tests whether doubling the same structured error behaves like a harder quantizer | Bit-width equivalence. W_0.5 is not W5, and W_2 is not W3 (not on any grid; its norm doubles but its structure is copied). Errors of other quantizers point elsewhere, so the curve says nothing about them. Interior α values carry BF16 rounding noise of order 2⁻⁹ relative; use the recorded `eff_alpha` |
| KV `WHICH=k` / `v` | Which cache side carries the KV-quantization effect at equal bits | Byte equivalence to weight restoration (activation memory vs parameters are different budgets). Rotated and non-rotated KV are different interventions |

**General limits**
- Fake quantization: the served kernels are BF16 GEMMs, so latency and memory claims come only from the declared budget, never from measurement.
- Each arm is one fixed checkpoint. Checkpoint-to-checkpoint variation is covered only by the two methods × two models, not by recalibration draws.
- Outcomes are read through the fork protocol (`docs/insights/FORK_PROTOCOL.md`: G, rescue/damage, coverage), with the thresholds fixed there. This document fixes arms and budgets only.

## 5. Engineering: kinds, tags, exactness, canary

**Checkpoint specs** (full lists: `scripts/a6000/make_tasks_perturb.py::specs(model, cell)`; 21 per primary checkpoint):

```
{"kind": "restore", "base": {"kind": "gptq", "wbits": 4, "calib": "manifests/a6k2/q4/calib_fp_traj_c1.json"},
 "arm": "late", "manifest": "manifests/perturb/restore_v1/q4/late.json"}
{"kind": "resid", "base": {...}, "alpha": 0.5}
```

**Build path** (`scripts/a6000/worker.py::build_ckpt` → `scripts/a6000/derived.py`):
1. **Base Q.** Built once per (model, base spec) into `/data/ziyangs/cloq_work/ckpt_cache/base/<model>_<kind>_<tag>/`.
   - A cross-node O_EXCL lock prevents duplicate builds; a lock older than 3 h counts as stale.
   - `cache.json` holds the spec, the files SHA-256 (same definition as `worker.ckpt_sha`) and the host.
   - Every later task on any node reuses these files, so all 21 arms of a base come from bit-identical Q weights.
   - q4 base ≈ 8 GB and q8 ≈ 16 GB, so all four primary bases ≈ 50 GB.
   - The builder refuses to add a base while the cache holds more than `CLOQ_CKPT_CACHE_MAX_GB` (default 100).
2. **Derived checkpoint.** `python -m cloq.perturb restore|resid` runs on CPU (`CUDA_VISIBLE_DEVICES=""`) into node-local scratch. The worker deletes it once vLLM has loaded it, as for every built kind.
3. **Tags.**
   - spec tag = sha256(protocol, model, revision, spec, manifest module sha)[:12];
   - content hash = sha256 over (name, dtype, shape, bytes) of every tensor.
   - The first build of a tag writes `ckpt_cache/registry/<model>_<tag>.json`. Every later build on any node must reproduce it, or the task fails. All builds are also logged to `ckpt_cache/registry.log`.
4. **Exactness in every build.**
   - `equals` is computed tensor by tensor. α = 0 and `all` must give `bf16`; α = 1 and `none` must give `q`; otherwise the build fails.
   - An `equals = q` build must also give safetensors files byte-identical to the cached Q.

**Canary rules after serving** (`derived.canary_checks`; plain path only, no `serve_extra`, no KV hook):

| Checkpoint | Canary must reproduce |
|---|---|
| `equals = bf16` | the BF16 agent reference `analysis/determinism/canary_agent_<model>.json` |
| `equals = q` | the per-base reference `canary_agentq_<base key>_<model>.json` (the first server writes it) |
| every tag | `canary_derived_<tag>_<model>.json`, so re-serving a tag on another node must reproduce its numerics |

**Recording.** The task result gets a `_ckpt` record: tag, content and files SHA, `equals`, `eff_alpha` and canary.

**Tests.** `python tests/test_perturb.py` runs on CPU in about 10 s and covers:
- exactness: α = 0 / 1 bitwise, including file-level identity for α = 1; interior α against an independent numpy evaluation; every restoration arm checked tensor by tensor;
- byte accounting against a hand count;
- determinism: two builds, and cross-process RNG under a different `PYTHONHASHSEED`;
- the non-linear-tensor guard;
- the worker path: base built once and reused; registry written, and a tampered registry detected;
- the committed q4 / q8 manifests reproduce exactly from the model headers.

## 6. Disk and cleanup

- **Derived checkpoints** live only in node-local scratch during a task.
- **Base cache:** about 50 GB for the four primary bases, under the 1 TB user quota (218 GB free on 09-30). Delete a base with `rm -rf /data/ziyangs/cloq_work/ckpt_cache/base/<key>` when no queued task references it; `cache.json`'s mtime is the last use.
- **After a delete:** a later task rebuilds the base. If GPTQ/AWQ is not bit-reproducible across nodes, the registry check then fails loudly instead of silently mixing Q versions. Delete the matching `registry/*.json` records deliberately in that case.

## 7. Open items for the main session

- **Fork integration.** `run_fork` builds `restore` / `resid` specs through `build_ckpt` unchanged. It does not yet call `derived.canary_checks`: the per-role canary is recorded, but the equals-bf16 / equals-q rules are enforced only in eval tasks.
- **Fork Q branch.** For restoration forks, the Q branch should be `resid_a1` (or `restore_none`) rather than a fresh `gptq` build, so that Q and every arm share one cached base.
- **Gate cross-check (verified by the smoke, RESEARCH_LOG W39-pert).** The cached q4 GPTQ base reproduced the fork gate's Q files sha `e6c24bc2…` (built on another node), and `resid_a1` reproduced its canary `a72b3da0…`. The cached q8 AWQ base equals the gate's `9ce71e4a…`. `resid_a0` served the BF16 reference canary `c7343b60…`.
