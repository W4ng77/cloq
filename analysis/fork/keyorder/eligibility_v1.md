# Key-order eligibility v1 (ko-v1), q8 GPTQ-W4 d1 Bank P

TL;DR: 300 of 1,473 divergent states are eligible (20.4% of divergent states, 17.6% of the 1,700-unit pool). Every rejection is at criterion (a): 767 not a tool call, 406 fewer than 2 argument keys. No state failed (b) parsed-action identity, (c) execution identity, or (d) next-prompt token difference. Outcome-blind: only `states/*.json` read, no branch file and no reward, db_match or termination field.

- Transform (frozen): reverse the top-level keys of each tool call's arguments object; nested values copied unchanged (their own key order kept), arrays, tool names, call count and order untouched.
- Scanner: `scripts/a6000/keyorder_scan.py`, sha256 `c6bedf22...a790c` (same as the manifest's `scanner_sha256`).
- Inputs: `analysis/fork/dev/q8_gptq_w4_d1/g1..g4` (blocks q3, q4, q5, f01-f17).
- Eligible ids sha256 (sorted state_id list, raw JSON): `17307ad6d8a3122847eebf7932d3e8b81af06524ff47bd8141885024a3586d5b`.
- Independent re-run: this file's rows are identical to `manifests/fork/keyorder_v1.json` (sha `cbf12188...28ce`); the file hashes differ only by the `created` timestamp.

| reason | airline | retail | total |
|---|---|---|---|
| eligible | 187 | 113 | 300 |
| a:not_tool_call | 130 | 637 | 767 |
| a:lt2_keys | 139 | 267 | 406 |

- Eligible: 41 tasks, 10-18 per block (q3 has the fewest, 10), one call per action; keys 2 (97), 3 (79), 4 (91), 5 (1), 7 (19), 11 (13).
- Divergence category of eligible states: tool_name 174, tool_args 110, act->talk 14, invalid_tool 2.
- First differing next-prompt token lies 45 to 1,966 tokens before the end of the prompt. The local render of the original action reproduces Q's recorded next prompt on all 300.
- Retail coverage is low (113 of 1,017 retail states), so retail is under-represented relative to the full pool.
- Scope: covers only validated tool-call states. It is not a semantic null for all language actions. Under a deterministic server, a flip is a real consequence of the input intervention, not noise to subtract. Server-side rendering of the reversed order is checked only at run time (`next_prompt_from_server`).
