# WP5 annotation protocol (frozen before unblinding)

**TL;DR** 80 τ² development fork states are reviewed blind in two passes. 20 of them get a second reviewer, the reviewers are the user and one collaborator, and the work is scheduled for 10-02/03. Pass 1 labels the two candidate current actions; pass 2 labels the four continuations.

The rubric is frozen by hash: `docs/insights/WP5_RUBRIC_v1.md`, sha256 `b97e0104…` (`manifests/annotation/wp5_rubric_freeze.json`). An LLM labeller and the automatic event extractor use the same rubric, and their labels are stored apart from the human ones. Disagreements are adjudicated by the rule in §5, and the unblinding key, kept outside the repository, is opened only after adjudication (§6).

## 1. Sample (frozen: `manifests/annotation/wp5_sample_v1.json`)

**Frame.** All 8,288 divergent τ² development units that passed the replay gate and have branch files.
- Source: `analysis/fork/out/consequence_units_20261001T0224Z.jsonl`.
- Cells: W4 (GPTQ-W4 d1, AWQ-W4), KV8 and stress (GPTQ-W3, KV4-rot), on q4 and q8, across retail, airline and telecom.

**Strata and allocation.**
- Strata are consequence sign × family × domain. The sign compares Y_BQ with Y_QQ: rescue, damage, both succeed, both fail.
- Each sign gets 20 states, spread over its strata in proportion to stratum size with at least one per stratum.
- Within a stratum, units are drawn in sha256 order. A task already in the sample is reused only if the stratum runs out; this happened for 2 states.

**Composition.**

| Cut | Counts |
|---|---|
| Sign | 20 per sign |
| Family | W4 58, KV8 12, stress 10 |
| Domain | retail 52, airline 24, telecom 4 |
| Model | q4 and q8 roughly equal |

**Weights.** Frequencies in this sample are sample composition, not prevalence. Each unit carries its stratum size and an approximate inclusion probability for weighting.

**Double review.** The first 5 states per sign in hash order (20 in total) are reviewed by both reviewers. Each of the other 60 states goes to R1 or R2 by hash; the assignment is in `analysis/annotation/wp5/packets_meta.json`.

## 2. What reviewers see and what is hidden

| | Shown | Hidden |
|---|---|---|
| Pass 1: current decision (`<id>_pass1.html`) | The user's hidden goal (task scenario), the full history up to the state, and the two candidate actions as **X** and **Y** in hashed order | Which action is the quantized or the BF16 model's; model, precision, quantizer, block; all G/H/F values; the outcome pattern; the future |
| Pass 2: process consequences (`<id>_pass2.html`) | The four continuations **S1–S4**, in hashed order, from the same state; each starts with that branch's current action; the remaining step/error budget | Branch role (which model took the action, which continued), precision, and the automated success label |

Packets: `analysis/annotation/wp5/packets/index.html`, plus a pass-1 and a pass-2 page per state.

Pass-1 labels for a state must be complete before its pass-2 page is opened.

## 3. Fields and values

The fields are those of WP5_RUBRIC_v1.md, verbatim; every field also allows "unknown" or "n/a".

**Pass 1, per action X and Y:**
- groundedness, tool_validity, argument_validity, permission_consent, goal_relevance, defensible;
- per state: state_ambiguity, both_defensible.

**Pass 2, per continuation S1–S4:**
- retries, defect_corrected, irreversible_change, user_clarification, loop, budget_exhaustion, requirements_satisfied.

**Evidence.** Every value other than unknown or n/a needs evidence: message indices `[i]` as printed on the page, or "action".

**Distinctions to keep separate:**
- A syntactically different action is not a defect.
- A tool error is a benchmark error, not a policy violation.
- A write without a recorded explicit "yes" is a consent problem only if the history shows no confirmation.
- An outcome-changing event is judged in pass 2 only.

## 4. Procedure

1. Read this protocol and the rubric, then label 2 calibration states (`calibration: true`). These are excluded from all analyses and are not in the sample: the first two frame units outside the sample in hash order, listed in packets_meta at release.
2. Label your assigned states. Write them to `labels_<reviewer>.jsonl`, one line per state and pass, following `labels_TEMPLATE.jsonl`: `{review_id, reviewer, pass, labels{field: {X|Y|S1..: {value, evidence, note}}}, notes, minutes}`.
3. Work independently. Do not discuss individual states before both reviewers have submitted the 20 double-review states.
4. Do not open the automatic events file (`events.jsonl`) or the LLM labels (`llm_labels.jsonl`) before submitting.

## 5. Agreement and adjudication rule (fixed now)

**Agreement** is computed per field on the 20 double-reviewed states:
- raw agreement and Cohen's κ, or Gwet's AC1 when a category is rare (prevalence < 10%);
- the number of disagreements;
- the share of unknown labels.

Results are reported per field, never as one global score.

**Adjudication.** Each disagreement is settled by a joint discussion of the two reviewers, citing evidence indices.
- Final value: the agreed value, or "unresolved" if no agreement is reached after discussion. Unresolved is reported as its own category, never coerced.
- The pre-adjudication labels of both reviewers are kept, and adjudication changes are counted.
- Single-reviewed states keep their one label.

**LLM and automatic labels.**
- LLM labels (`llm_labels.jsonl`, rubric hash recorded per line) and automatic events (`events.jsonl`: cloq.fork_annotate + WP5 events) are compared with the adjudicated human labels per field.
- They never override a human label.
- Their agreement with the humans is reported the same way.

**Wording and case selection.**
- A recovery claim needs defect → correction → requirement satisfied, all in human labels.
- Illustrative cases are chosen by frozen hash within declared patterns, with counterexamples and unresolved cases included.

## 6. Unblinding

The key (review id → state, X/Y role, S1–S4 branch) is at `/data/ziyangs/cloq_work/annotation/wp5_KEY_unblinding.jsonl`, outside the repository. Its sha256 (`packets_meta.json: key_sha256`) is committed. The key is opened only after:
1. all human labels are submitted;
2. adjudication is complete;
3. the labels file sha256 is committed.

Only then are labels joined to the branch roles, precision cells and consequence patterns.

## 7. Provenance

Recorded versions:
- sample manifest: sha in packets_meta;
- rubric: sha `b97e0104b274b33111fd9882b8a2cff9905375351b060559a65b1661fab6ffd7`;
- `cloq/wp5.py`: sha per output;
- fork_annotate version `fork-annot-v1` and the tool-types table sha (in `events.jsonl`).

LLM labeller:
- model: the served user-simulator model, Qwen3-30B-A3B-Instruct-2507 at the pinned revision, through an existing replica;
- decoding: greedy, seed 0;
- the URL and served snapshot are recorded per line.

The labeller model is also the τ² user simulator. Its labels are therefore not independent of the simulator's own judgements, and this is reported as a limitation.

## Amendment 1 — reviewers are independent Sonnet 5.5 instances (2026-10-01, before any reviewer label)

**TL;DR** The author decided that the two reviewers R1 and R2 are independent `claude-sonnet-5-5` instances, not humans. Their labels are reported as **independent strong-LLM annotation**. The paper makes no human-annotation claim for WP5.

- **Reviewers.**
  - R1 and R2 are separate Sonnet 5.5 agent contexts that share no conversation.
  - Each reviewer's assigned states are split into 4 chunks. Each chunk is a fresh instance that gets only:
    - this protocol;
    - the frozen rubric (`WP5_RUBRIC_v1.md`, sha unchanged);
    - copies of its assigned packet HTML files, in an isolated directory.
  - Each chunk starts with the same 2 calibration states, so calibration drift across chunks is measurable.
- **Blinding.**
  - The instances are told not to open the repository, the key, `events.jsonl`, `llm_labels.jsonl` or `packets_meta.json`, and to read only their chunk directory.
  - The packets themselves carry no model, precision, quantizer or outcome information (W71 leak check).
- **Distinction from the existing LLM labels.** The existing `llm_labels.jsonl` (Qwen3-30B-A3B, which is also the τ² simulator) stays a separate, weaker labeller. The Sonnet labels address the "labeller = simulator" limitation, but they are not human.
- **Adjudication (§5).** "Joint discussion of the two reviewers" is replaced by a third independent Sonnet 5.5 instance (R3). R3 sees only the two labels plus their evidence spans and the packet, and picks one value or "unresolved". Pre-adjudication labels are kept, and all of §5 otherwise applies.
- **Wording.**
  - Wherever §5 says "human labels", read "R1/R2 adjudicated labels".
  - A recovery claim still needs defect → correction → requirement, all in those labels.
  - Every table and sentence that uses them says "LLM-annotated (Sonnet 5.5, two independent instances)".
- **Unblinding (§6).** Unchanged: the key is opened only after both reviewers submit, adjudication is complete, and the labels' sha is committed.
