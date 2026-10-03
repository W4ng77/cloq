**TL;DR** The one branch out of 774 that fails `prefix_and_env_ok` is in the **W3** same-precision analysis
(`sameprec_w3_20261003T023933Z`, q8 same: 773/774). It is not in the W4 analysis: every W4 count in
`sameprec_20261003T023857Z` is 1405/1405, and all the other cells there pass too. The failure comes from how the result
was recorded, not from a real mismatch. The branch ended in an agent-side context overflow. On that path `cloq/fork.py`
writes `prefix_ok: None` as a sentinel, because tau2 keeps no messages to compare. The env hash at init matches, and the
replayed prefix matches at the token level. The protocol rule is "exclusion only through quarantine", and context
overflow counts as a valid failure (W10/W70). `analyze_sameprec.py` already applies both rules, so **no reported number
changes**.

# Same-precision prefix/env acceptance check (2026-10-03 03:00 UTC)

## The failing branch

| field | value |
|---|---|
| analysis | W3 same-precision (protocol sameprec-w3-v1), `analysis/fork/out/sameprec_w3_20261003T023933Z.md` line 96 |
| cell / block | q8 (Qwen3-8B), GPTQ-W3 d1 vs d2, block q4 (`a6k2_q8_gptq_w3_q4`) |
| task | retail:111 |
| state | `01a4b3fe2dc5b158` (decision_idx 1, t* = 1, category tool_name: Q `get_user_details` vs Q′ `get_order_details`) |
| arm | BB = Q′Q′ (Q′ action, Q′ controller) |
| file | `analysis/fork/sameprec_w3/q8_gptq_w3_d1_vs_d2/q4/branches/01a4b3fe2dc5b158.json` |
| sub-check | **prefix**: `prefix_ok` is `None` (it is not `False`); `env_hash_init_ok` is `True` |
| termination | `infrastructure_error`, `infra_cause: context_overflow` (vLLM: 65 025 prompt + 512 output > 65 536) |

The other three arms at this state (BQ, QB, QQ) have `prefix_ok = True` and `env_hash_init_ok = True`.

## Recording problem or real mismatch: recording problem

- `cloq/fork.py` (the `ContextWindowExceeded` branch, around l. 586–600) returns a fixed record that hard-codes
  `"prefix_ok": None`, `"suffix": None` and `"n_messages": None`. tau2 raised before returning a simulation, so there
  are no messages to compare with the frozen history. `analyze_sameprec.acceptance()` counts
  `bool(None) and …` as a failure. The count therefore mixes a "not computable" sentinel with a real failure.
- Independent evidence that the prefix was replayed correctly:
  - The first recorded BB decision (decision_idx 1, forced) has prompt-ids sha `ce43719c…`. This equals the state's
    `q_decision.prompt_ids_sha` and the first-decision prompt sha of the other three arms. The prompt token ids are
    the rendered history prefix, so the prefix is bit-identical.
  - The BB and BQ completions at decision 1 are identical (same Q′ first action). Their decision-2 prompts are also
    identical, as they must be.
  - `env_hash_init` (db `b25c9cb2…`) equals the state's env hash, and is the same in all four arms.
- BB then ran 85 decisions with Q′ as controller before the conversation outgrew the window. This is the frozen
  policy's own looping. The episode is a valid failure outcome (Y_BB = 0), not a missing one.

## Rule applied

- **SAMEPREC_PROTOCOL.md §4**, inherited unchanged by SAMEPREC_W3 §4: "Acceptance counts are reported (QQ no-op sample
  pass rate, Q replay at state, prefix_ok and env_hash_init_ok of all branches) but, as in the precision analysis, they
  exclude units only through quarantine." Quarantine happens only when a QQ no-op mismatches. The W3 report has
  0 quarantined directories (no-op samples 31/31 and 39/39).
- **Amendment A1** changes no admission rule ("changes no estimate, interval, admission rule, block order or freeze
  date").
- **Context overflow is a valid failure** (W10; W70; `cloq/fork.py` comment "W10 / W70 … a valid failure outcome of the
  frozen policy: Y = 0 under every evaluator"; PREREG_FORK_CONFIRM "Agent-side context overflow … valid outcomes (W10),
  not misses"). `analyze_dev.load_dir` excludes only branches that carry an `error` key. This record has none, so the
  unit is admitted with Y_BB = 0, as the rule requires.
- `analyze_sameprec.py` already does exactly this. The unit is not excluded, the state and block are not quarantined,
  and K = 3 is unchanged. **The reported W3 (and W4) numbers are already correct. No script change, no re-run, no
  number changed.**

## Open question (not a rule change)

The acceptance count treats the context-overflow sentinel (`prefix_ok = None`) as a failure. A reader could take
"773/774" to mean that one replay mismatched. The protocols say nothing about how to *display* this case. One option is
a separate "not computable (context overflow)" count, which would be a reporting change only. It is not made here.
