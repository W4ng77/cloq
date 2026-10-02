**TL;DR** Same-precision role-swap gate (W99k; SAMEPREC_PROTOCOL.md §3): **PASS for q4 and q8.** With Q′ = GPTQ-W4 d2 in the driver's
B role, both checkpoints reproduce their own recorded decisions (16/16 each). All 12 search rows per cell pass the Q′ prompt-id check
(no exclusions), and the QQ no-ops (6/6) and Q′Q′ no-ops on Q′'s own trajectory (4/4) are bit-exact. Q replay, isolation, save/load,
budget and re-prefill all pass. The 12 formal tasks (f01–f17) were queued at −28 after both verdicts.

# Same-precision gate (Q = GPTQ-W4 d1, Q′ = GPTQ-W4 d2), 2026-10-02

Gate tasks `fork_sameprec_gate_{q4,q8}` (driver mode `gate`). Q blocks are `a6k2_<m>_gptq_w4_d1_q3` (retail and airline; not in the
analysis set). The Q′ own blocks are `a6k2_<m>_gptq_w4_d2_n1`. Settings: 6 search tasks per domain, 6 states, 2 isolation states,
4 Q′Q′ no-ops, 16 idcheck decisions.

| check | q4 | q8 |
|---|---|---|
| 1 identity: idcheck Q (d1 runs) / idcheck Q′ (d2_n1 runs) | 16/16, 16/16 | 16/16, 16/16 |
| 1 distinct numerics: canary Q′ / Q (`expect_distinct_numerics`) | a0fb6c52… / a72b3da0… | 15e5098c… / a9f812fb… |
| 2 B-role (Q′) prompt ids = Q's recorded prompt ids (search rows excluded for mismatch) | 0/12 excluded | 0/12 excluded |
| 3 divergence search: states / tasks (no divergence) | 9/12 (3) | 11/12 (1) |
| 3 categories among the 6 branched states | act→talk, talk→act, tool_name, tool_args | same four |
| 4 QQ no-op (all branched states) | 6/6 | 6/6 |
| 4 Q′Q′ no-op on Q′'s own trajectory (driver a_BB) | 4/4 | 4/4 |
| 5 Q replay at state / save-load / budget / re-prefill | pass | pass |
| 5 isolation (reversed order and concurrent) | 2/2 | 2/2 |
| driver verdict `pass` | **true** | **true** |
| wall time (gate) / shadow s per decision (median) / suffix s per branch (median) | 25 min / 3.5 / 97 | 53 min / 3.0 / 34 |

The gate states (block q3) are not part of any estimate (protocol §2).

Evidence: `analysis/fork/sameprec/gate/{q4,q8}/{gate.json,search.json,states/,branches/,states_bnoop/}`, queue
`done/fork_sameprec_gate_{q4,q8}.json`, logs `/data/ziyangs/cloq_work/logs/tasks/fork_sameprec_gate_{q4,q8}.{log,servers.json}`,
generator `scripts/a6000/make_tasks_sameprec.py --gate`.
