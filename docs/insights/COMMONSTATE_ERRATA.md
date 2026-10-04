# Common-state protocol: errata (kept outside the hashed protocol file)

`docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md` is hashed and guarded by `analysis/fork/analyze_commonstate.py`, so factual corrections that change no rule, estimate or reading are recorded here.

## E-1 (2026-10-03 17:05 PDT, W100ac): the D2.1 replay check is 9/9, not 8/9

**TL;DR** On the 9 f01–f03 overlap states, the (d2 action, d1 continuation) arms of SAMEPREC q8 g1 and of this design are byte-identical replays:
- the a_d2 completion ids (9/9);
- the prompt and completion token ids of every d1 decision (148 decisions, 6,370 completion tokens);
- every user-simulator and tool message;
- the final DB hash and all reward fields.

The earlier "8/9" compared this design's Y, the DB success, with SAMEPREC's τ² official_reward. At 79aa9e6a7ca99243 (airline 3, t = 0) these two metrics differ by definition: both runs have db_match = True, user_stop, official_reward = 0 and suffix_sha 5d4d49aa…. The runs themselves do not differ.

- **Replaces:** "a_d2 is identical 9/9 and the (d2 action, d1 continuation) outcome is equal 8/9. The replays are close but not exact" (D2.1), the "8/9 Y" in D2.7, and RESEARCH_LOG W100u-r.
- **Unchanged:** every rule and reading. The D2.1 sensitivity reading excludes these states anyway.
- **Serving.** Both runs used vLLM 0.29.0, VLLM_BATCH_INVARIANT=1, TORCHINDUCTOR_DETERMINISTIC=1, TP=1, and identical checkpoints and configs. They differed in node and in load: up to 8 running and 4 waiting requests on the d1 server, which is past the det-pair envelope (waiting ≤ 1). The tokens were identical anyway.
- **Evidence:**
  - `analysis/fork/commonstate_replay_check/{REPLAY_8of9.md, replay_8of9.json}`;
  - `analysis/fork/commonstate/q8/panel/d2_d1/f03/branches/79aa9e6a7ca99243.json`;
  - `analysis/fork/sameprec/q8_gptq_w4_d1_vs_d2/g1/branches/5859e02aecc11d39.json`.

## E-2 (2026-10-03 17:35 PDT, W100ad): why q4 f01 was quarantined: a canonical-equality artifact, not non-determinism (no rule change)

**TL;DR** One state removed q4 f01 under the frozen §4 block quarantine: 7411758182009c20 (airline 30, t = 6). It failed one implicit identity check in each panel task. Its d2 action has the same tokens as a_BF16 and a_d1 except for the key order inside `arguments.flights[0]`. `canon_msg` compares parsed arguments as dicts and ignores key order, so the implicit checks applied. The chat template renders the keys in their original order, so the next prompt differs: 24 permuted positions out of 7,016. The continuation therefore could not be a replay.

- **Serving was deterministic.** No-op re-runs passed 15/15 and QQ re-runs 18/18. The d2 actions were identical on two GPUs at 85/85 states. Up to decision 7, every prompt, tool output and environment hash matched. A CPU tokenizer check reproduces both recorded hashes from the key swap.
- **Acceptance across all common-state tasks (q4 + q8, gate + panel):**
  - implicit + reference identity checks: 1,238/1,240 passed (99.84%, Wilson 95% [99.41, 99.96]). Both failures are this state, one per task;
  - every implicit check with a token-identical action passed (869/869);
  - d2 replay 1,578/1,578; cross-task a_d2 789/789.
- **The rule worked as written.** §2 states the precondition as canonical equality, and §4 quarantines on any failure, so removing f01 was correct. The q4 reading (k = 2) stands as produced. Bank U reuse uses the same equality, but no canonically-equal yet token-different pair occurs there (0 of 776), so no reference reuse is affected.
- **Evidence:** `analysis/fork/commonstate_replay_check/{Q4_F01_IDENTITY.md, q4_f01_identity.json}`; `analysis/fork/out/commonstate_q4_20261004T001159Z.md`.
