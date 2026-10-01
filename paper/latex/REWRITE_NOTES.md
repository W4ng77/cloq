**TL;DR** W94 (2026-10-01): the paper is restructured after GPT-6.1 review 6 as *This Step or From Here On? Crossed Same-State Interventions for Evaluating Quantized Agents*: an interventional evaluation methodology plus a systematic study, with the W93 2×2 (G/H/F, (Δ_Q, Δ_B) 3×3) at the centre and the W91 simulator control (SIMCTRL) filled in.
- **Build:** tectonic, 14 pp; main text pp. 1–8 (Limitations starts p. 9); 0 overfull boxes, 0 undefined references.
- **Provenance:** `python3 paper/latex/check_numbers.py` → PASS (1773 number occurrences, 0 unverified, 0 missing source paths, all required sources cited; exit code 0).
- **Pending results** are `\todo{KEY: ...}` (red): HOLDOUT, TOKEN-VALIDATION, BANKU-F023 (main); RECOVERY-Q8, RESTORE (appendix). No number was invented.
- **Archive:** W89 draft in `sections/old/w89/`, W33 draft in `sections/old/w33/`.

# Rewrite notes (W94, review 6 structure)

Build: `cd paper/latex && /data/ziyangs/cloq_work/tools/tectonic main.tex`. Self-check: `python3 paper/latex/check_numbers.py` (exit 1 on any failure; `--report` to always exit 0).
Appendix tables `gen_ghf_crossed.tex` and `gen_patterns.tex` are generated verbatim from the W93 report by `tools/gen_w93_tables.py`; do not edit them by hand.

## Section and page map (compiled PDF)

| § | File | Content | Page |
|---|---|---|---|
| Abstract, 1 Intro | `abstract.tex`, `introduction.tex` | practical question (escalate? this step or from here on?); W93 Case 5 (q4 AWQ airline:31, 1/0/0/0); Fig. 1 crossed design | 1–2 |
| 2 Related work | `related_work.tex` | by identified quantity: Flat Score (process damage, 33/26 split, error budget, 55% recovery, repair prompt), Replay Gap (switch action + continuation together = our F; 0/359; no noise claim), DMR (router; we measure gains and proxy validity), 2407.09141, 2606.00206 | 2 |
| 3 Method | `method.tex` | setting; frozen state; Y_XY notation; G/H/F; paired differences; Δ_Q, Δ_B, 3×3, strict reversal; r/d/M; replay acceptance; Bank P (first tool-structure divergence, text-only skipped) and Bank U; three denominators; identified vs descriptive; fixed-pool vs new-task intervals | 3–4 |
| 4 R1 | `results_r1.tex` | Table 1: full-pool r/d/M/G_all (W4 M 15.5–20.9%, G_all −1.9…+2.9); "not end-to-end"; concentration (1 sentence → App. F) | 4–5 |
| 5 R2 (centre) | `results_r2.tex` | Table 2: G/H/F, G−H, F−G, F−H, off-diag, reversal, mean I per cell + pools; Fig. 2 TikZ 3×3 (W4 pool, KV8 pool); within-cell contrasts (q8 GPTQ/AWQ, q4 GPTQ, q8 RTN-W3, q4 KV8 H<0); action–controller fit = hypothesis; mean-I explanation | 5–6 |
| 6 R3 | `results_r3.tex` | Table 3: Bank U taxonomy with per-row and unique-row totals and flip rates; 39/56 composition share; **SIMCTRL** (text flips simulator-dependent); telecom holdout (TODO); BFCL/ALFWorld (ext_20261001T135106Z) | 6–7 |
| 7 R4 | `results_r4.tex` | token analysis: locates divergence, not consequence; frozen S_mm trigger; TOKEN-VALIDATION TODO | 7–8 |
| 8 Discussion | `discussion.tex` | when to escalate, which part, escalation can hurt (Case 6), not claimed | 8 |
| Limitations, Ethics | `limitations.tex`, `ethics.tex` | one family 4B/8B; simulated quantization (no latency/memory); relay simulator; LLM annotation; 34 holdout tasks; partial banks | 9 |
| App. A–I | `appendix.tex` | A setup; B end-to-end (TOST fails); C 16 patterns + new-task intervals; D coverage matrix (W93 §5, completed only); E Bank U per sub-bank, co-flip lead, Q0; F concentration; G injection + Table 4 v2; H prereg; I withdrawn (W×KV, restoration, equivalence, "absorbed", superseded A/C names) | 10–14 |

## W93 numbers in the main text

G/H/F and paired differences for all 11 cells and the W4/KV8 pools (Table 2); off-diagonal 26.9% [25.7, 28.1] (W4 pool), 15.3% [13.2, 17.3] (KV8 pool), 22.9–30.5% per W4 cell; strict reversal 3.2% (W4 pool), 1.2–4.2% per W4/KV8 cell, 8–14% of off-diagonal mass; P(I>0) 13.6% vs P(I<0) 13.4%, mean I +0.0 [−1.9, +2.0]; 3×3 pooled counts (Fig. 2); Case 5 (intro) and Case 6 (discussion).

## Checker changes (W94)

- `% nocheck` skips a line (TikZ coordinates, notation such as {−1,0,+1}, list labels).
- `% derived: X=expr; …` verifies X arithmetically; operands must be found in the line's sources. Used for the Bank U unique-row totals (310/46/60) and per-class rates (12.6/10.9/20.0%).
- Rounding: a source number with 1–2 more decimals that rounds to the printed one is accepted (e.g. 0.133 → 0.13, 0.449 → 0.45).
- Every `% src:` path must exist; `REQUIRED_SOURCES` (incl. the W93 `ghf_20261001T211519Z.md`, the SIMCTRL `simctrl_20261001T212742Z.md`, `ext_20261001T135106Z.md`) must exist and be cited.

## Deliberate wording decisions

- G_all (full pool) and G (divergent states) are different denominators; the text says G_all is G diluted by non-divergent units.
- Within-cell contrasts are "identified"; every cross-cell comparison is "descriptive" (each cell selects its own first divergences).
- The q4 GPTQ negative G and "action–controller fit" are a hypothesis (post-hoc divergence kinds; Δ_B also negative).
- SIMCTRL: worded as the coordinator required (text-only consequences at ordinary states are largely simulator-dependent, not a stable property of the action); scope = fixed histories, relay (Claude Code subagent) Sonnet 5.5, stochastic, f01 only; does not test Bank P.
- Token analysis: "does not reliably identify consequences among divergent states"; explicitly not "uncertainty is useless".
- External rows now use the committed `ext_20261001T135106Z` (BFCL q4 AWQ-W4 now 788 items: G −3.8 [−6.5, −1.3]); EXT-REFRESH resolved.
- User simulator = Qwen3-30B-A3B-Instruct-2507 (served model in `cloq_work/sims/*.json`, `docs/FINAL_EXPERIMENTS.md`). The `user_model_id` field in fork state files and the simctrl report's "Qwen3-4B-Instruct-2507" are a stale default label (`cloq/config.py` USER_MODEL_ID = agent hf_id), not the served simulator.
