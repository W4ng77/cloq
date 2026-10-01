**TL;DR** W89 (2026-10-01): the paper is rewritten to `docs/STORYLINE_v7.md` as *Same-State Counterfactual Forks: How Quantization-Induced Action Changes Become Task Consequences in Closed-Loop Agents*.
- **Build:** clean, with 0 overfull boxes and 0 undefined references or citations. The PDF has 12 pages: main text pp. 1–8, Limitations from p. 9.
- **Provenance:** every number has a `% src: <path>` comment.
- **Pending results** are `\todo{KEY: ...}` (red); no number was invented.
- **Archive:** the W33 draft is in `sections/old/w33/`.

# Rewrite notes (W89, storyline v7)

Build: `cd paper/latex && /data/ziyangs/cloq_work/tools/tectonic main.tex` (no latexmk/pdflatex on the cluster).
Self-check: `python3 paper/latex/check_numbers.py`, which lists every number not found in its `% src:` file.

## Structure (page estimate from the compiled PDF)

| § | File | Content | Pages |
|---|---|---|---|
| Abstract, 1 Intro | `abstract.tex`, `introduction.tex` | RQ; end-to-end comparison inconclusive (W64); 2×2 fork; three layers; Fig. 1 (TikZ) | ~1.6 |
| 2 Related work | `related_work.tex` | Flat Score, Replay Gap (no noise-floor claim), DMR, action-swap papers, 2407.09141, 2606.00206, simulators | ~0.7 |
| 3 Method | `method.tex` | setting; fork states; r/d/M/G and A/C/I; replay gate; block inference | ~1.2 |
| 4 L1 atlas | `atlas.tex` | Table 1 (r/d/M/G, A/C/I per cell); concentration (retrospective, 6 configs × 2 directions); holdout design + TODO | ~1.6 |
| 5 L2 Bank U | `bank_u.tex` | Table 2 (M per sub-bank), Table 3 (taxonomy with denominators); 39/56; co-flips = 5 states; Q0; pending controls | ~1.4 |
| 6 L3 bounding | `intervention.tex` | Table 4 (recovery per-state turnover); manipulation checks; process audit (LLM-annotated) | ~1.0 |
| 7 Discussion | `discussion.tex` | reading, implications, not claimed | ~0.5 |
| Limitations, Ethics | `limitations.tex`, `ethics.tex` | required items | p. 9 |
| App. A–F | `appendix.tex` | setup, composition, A/C/I CIs, end-to-end table (W64), Table 4 v2, prereg, withdrawn | pp. 10–12 |

## Placeholders (`\todo{}`)

| Key | Where | Fills from |
|---|---|---|
| HOLDOUT | abstract, §1, §4, App. D | `analysis/fork/analyze_holdout_confirm.py` under prereg sha 902892dd… |
| BANKU-F023 | §5 | `analysis/fork/analyze_bank_u.py` on f01–f03 |
| Q0 | §5 | Bank U Q0 at f01–f03 |
| RECOVERY-Q8 | §6 | `analysis/recovery/analyze_inject.py` on `inject_q8` |
| TOKEN | §5 | token-level diagnosis (REPORT_GPT61_20261001_0915 §3.4) |
| SIMCTRL | §5, Limitations | second user-simulator re-branch of class-(ii) flips |
| Q14 | §4, Limitations | q14 paired forks |
| EXT-REFRESH | Table 1 caption | newer external output `ext_20261001T135106Z` is untracked; the committed `ext_20260930T221613Z` lacks BFCL q4 GPTQ-W4 |
| RESTORE | App. F | the 70%/27% restoration numbers are only in the untracked `restore_eval_20261001T164337Z`; not printed |

## Numbers checked by hand (the script flags them because of rounding or structure)

- Recovery CIs are rounded from 3 decimals in `summary_v2.md`; all were checked.
- The crossed width of 4.1 pp rounds 4.09 in `holdout_k_planning_20261001T144122Z.md`.
- "0–54%" rounds .538.
- The remaining flags are section numbers, TikZ coordinates, {0,1}, "Sonnet 5.5" and "Instruct-2507".

## Deliberate wording decisions

- **G:** `G = Y_BQ − Y_QQ` is never called an end-to-end difference. Every "flat/similar" statement points to App. B (`success_ni_ALIGNED`). There, TOST at ±3 pp fails in every cell, so the paper claims neither a difference nor equivalence.
- **Interval exclusions:** two W4 cells have fixed-pool G intervals excluding 0 (q4 GPTQ −1.9 [−3.7, −0.1]; q8 GPTQ +2.9 [+1.4, +4.4]). The text says so; it never says "every G covers 0".
- **Replay Gap:** it is cited as an arXiv preprint. Its venue is disputed (COLM per the arXiv comment, workshop per `RELATED_WORK_POSITIONING.md`), so the bib entry was changed from `inproceedings`. No "zero vs 90% noise" claim is made.
- **2606.00206:** not in `storyline-v7-lit.md`. It was named by REPORT_GPT61_20261001_0915 §3.4, and its title and authors were checked on arxiv.org/abs on 2026-10-01.
- **External W4 M:** the range is 5.2–24.6% (committed file), not the storyline's "7–25%".
