# Controlled recovery intervention (W71; EXECUTION_PLAN §5.5, CONSEQUENCE_ANALYSIS_PLAN §8): design for approval

**TL;DR** Per model (q4 and q8, GPTQ-W4 d1, block q3), take 30 frozen ordinary Q states, 10 for each of 3 error categories: wrong ID, wrong tool, premature write without consent. At each state, three actions are injected — a matched INVALID action, its VALID counterpart, and a negative control (NC) — and each is continued under B and under Q with the restored step/error budget.
- That is 180 branches per model and 360 in total.
- Estimated cost is about 6–7 GPU-h, about 2.5 h of wall time on 3 GPUs.
- The states are already frozen (`manifests/recovery/inject_v1.json`), before any branch has run. Nothing is queued: the tasks will be queued at −13 once approved.

## Design

**States.** Ordinary Q decision states (Bank-U-like, but selected only by the action's eligibility, never by outcome).
- Blocks: `a6k2_q4_gptq_w4_d1_q3` and `a6k2_q8_gptq_w4_d1_q3`, retail and airline.
- Eligibility, all conditions required:
  - t ≥ 1;
  - at least 20 steps left;
  - at least one earlier successful read call (needed for the negative control);
  - at most one state per task.
- Draw: 10 per category in sha256(salt|run|domain|task|t) order.
- Rebuilt with `cloq.fork.make_state`, the same strict replay as the forks.

Eligible states per category:

| Model | wrong_id | wrong_tool | premature_write | Selected (retail / airline) |
|---|---|---|---|---|
| q4 | 247 | 299 | 62 | 30 (22 / 8) |
| q8 | 317 | 394 | 78 | 30 (20 / 10) |

**Categories.** These were frozen from the most frequent automatically checkable defect types in development. In the WP5 events (80 states × 4 branches): wrong argument 60, wrong ID 22, consent needs review 10, wrong tool 6.

| Category | When eligible | INVALID injection | VALID (matched) |
|---|---|---|---|
| wrong_id | Q's action is one read call with an id argument grounded in the history | Same call, with that id replaced by a well-formed id absent from the DB (deterministic rotation, checked absent) | Q's recorded call |
| wrong_tool | Q's action is one read call | A plausible wrong read tool of the domain (fixed map in `inject_driver.py`), same arguments | Q's recorded call |
| premature_write | Q's action is a confirmation request, and Q's next action after the user's reply is a write whose argument values all already appear in the history (no future information) | That write issued now, before the user replies (no consent) | Q's recorded confirmation request |

**Negative control (every state).** A repeat of the most recent successful read call. It changes no requirement and no DB state, so any outcome difference against VALID measures how sensitive the continuation is to an irrelevant extra turn.

**Branches.** Each of {INV, VAL, NC} is crossed with {B, Q}, giving 6 branches per state.
- Every branch uses `cloq.fork.run_branch` unchanged: forced current action, restored step/error counters, same simulator seed, B on BF16 and Q on GPTQ-W4 d1, each on its own server.
- **VAL×Q is the original episode**, so it serves as a built-in no-op check. A mismatch quarantines the state.
- `scripts/a6000/fork_driver.py` is not touched, because Bank U (agent a5468c1) edits it. The new driver is `scripts/a6000/inject_driver.py`, dispatched by the worker through `fork.driver = "inject"` (a one-line hunk in `run_fork`).

**Endpoints, frozen now.**
1. **Task success Y**, with the official name per domain (retail/airline DB success).
2. **Recovery under controller c:** R_c = Y(INV, c) − Y(VAL, c). The controller contrast is R_B − R_Q: does B recover from the injected error better than Q?
3. **Literal recovery events** from `cloq.fork_annotate` on the INV branch:
   - wrong_id: the same tool is later called with a grounded id and no error (`regrounded`);
   - wrong_tool: the correct tool is later called without error;
   - premature_write: a user objection turn, later writes, and whether the final DB matches the gold paths touched by the write.
4. **Negative control:** Y(NC, c) − Y(VAL, c), reported next to R_c. A recovery effect is interpretable only where the NC difference is small.
5. **Process cost** (WP5 event extractor): extra steps, tool errors, turns and termination.

**Analysis.**
- Paired by state, clustered by task; an exact sign/McNemar test on discordant pairs, plus a state bootstrap.
- Reported per category and model.
- These are development data from one block: a failure to reproduce an injected error's effect is reported, and synthetic interventions are reported as a population separate from natural divergences.

## Cost

| | Branches | Wall per branch (τ² gate, concurrency 8) | GPU layout | GPU-h |
|---|---|---|---|---|
| q4 | 180 | 18.6 s → about 56 min, plus GPTQ build 6 min | 1 GPU (B+Q) | about 1.1 |
| q8 | 180 | about 47–60 s → 2.4–3.0 h, plus GPTQ build 10 min | 2 GPUs (strict) | about 5–6 |
| **Total** | 360 | | | **about 6–7 GPU-h** |

Simulator demand is about 360 × 4–10 turns, roughly 2–4k turns, which is negligible against the measured capacity.

**Tasks to queue on approval** (priority −13):
- `inject_q4_gptq_w4_d1_q3`: kind `fork`, `fork.driver = "inject"`, 1 GPU, `gpu_util` 0.44;
- `inject_q8_gptq_w4_d1_q3`: 2 GPUs.

Each task runs B = BF16 and Q = GPTQ-W4 d1 c1, with output in `analysis/recovery/inject_<model>/`.
