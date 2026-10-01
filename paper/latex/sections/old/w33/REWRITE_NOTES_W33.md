**TL;DR** W33 (2026-09-30): the LaTeX paper is rewritten as *Tracing the Consequences of Quantization in Closed-Loop Agents* (question: on identical histories, which task consequences do quantization-induced local action changes cause, and do they come from the current action, the continuation controller, or their interaction). The main text is 8 pages (Limitations begins on page 8); the PDF is 13 pages. It builds with no errors and no undefined references or citations. Every fork result is a `\pending{}` placeholder. Background numbers come only from the files listed below. The old "perturbation equivalence" sections are in `sections/old/`.

# Rewrite notes (W33)

Build: `cd paper/latex && /data/ziyangs/cloq_work/tools/tectonic main.tex`. Result: `main.pdf`, 13 pages.
- Main text: pages 1–8. §7 ends and Limitations begins in the right column of page 8.
- Ethics and References: page 9.
- Appendix: pages 10–13.
- No overfull boxes, no undefined references or citations.

## What changed

| Item | Old (sections/old/) | New |
|---|---|---|
| Title | Perturbation Equivalence in Closed-Loop Agents | Tracing the Consequences of Quantization in Closed-Loop Agents |
| Thesis | Judge a compressed agent against the reference's perturbation null; P1–P3 margin model | Same-state four-branch fork; estimands G = h − b, A/C/I, G_all; results pending |
| Structure | intro, related, framework, setup, results, diagnostics, recommendations, conclusion | 1 Intro, 2 Related work, 3 Run conditions and measurement definitions, 4 Same-state four-branch design (4.5 dev results, pending), 5 Consequence composition and mechanism annotation, 6 Independent confirmation, 7 Discussion (pending), Limitations, Ethics, Appendix A–G |
| Figure 1 | red placeholder box | TikZ schematic of one state forking into BB/BQ/QB/QQ, with the outcome categories. Captioned "not data"; it contains no numbers |
| `\pending` | red, small | `\textcolor{orange}{[PENDING: #1]}` as specified |
| Retired lines | main text | Appendix only: P0 audit (A), iter-4 prereg (B), random-perturbation fingerprint (C), turnover (D); summarised in Limitations |

Files:
- **New:** `sections/{abstract,introduction,related_work,conditions,fork_design,annotation,confirmation,discussion,limitations,ethics,appendix}.tex`.
- **Moved with `git mv`:** the old section files, to `sections/old/`.
- **Copied:** `sections/old/main_perturbation_equivalence.tex`, the old main file.
- **refs.bib:** 6 entries appended, copied verbatim from `analysis/insights/references_new.bib`: `wang2026agentprov`, `gao2025model`, `li2026dynamicmp`, `frantar2023gptq`, `lin2024awq`, `mustahsan2025stochasticity`. Each arXiv id's title was checked on arxiv.org/abs; the author lists of 2609.00052, 2602.02711, 2512.06710 and 2410.20247 were also checked against the arXiv citation_author metadata.
- **responsible_nlp_checklist.md:** updated A1–A3, B1, B5, B6, C2, C3 and D. D is now "yes, planned": the ~80-state blinded review, with TODOs for guidelines and reviewer identity.

Banned words ("lossless", "success-equivalent", "fingerprint confirmed", "absorbed", "cannot recover"): a grep over `sections/*.tex` finds none. `sections/old/` is excluded from this check.

## Source of every number

| Number in the paper | Where | Source |
|---|---|---|
| 85 dev tasks = 58 retail + 27 airline; 22 BF16-unstable excluded; 57 calibration tasks | §3 | `docs/REVIEW_PACKET.md` §2; RESEARCH_LOG W17 |
| telecom: 114 base tasks → 80 dev / 34 holdout; stratified hash split; 14 of 80 dev tasks ENV_ASSERTION+ACTION | §3, §6 | `manifests/telecom/dev_v1.json`; EXTERNAL_REVIEW Round 2/3 |
| official reward: retail DB×NL_ASSERTION 112/114, airline DB×COMMUNICATE 50/50 | §3 | METHODOLOGY_REVISION C8 |
| 257/257 (q4), 303/303 (q30a3) byte-identical cross-node decisions; 20/20 tasks and 113/113 decisions shifted before the fix; R0_BLOCK 2048 vs 4096 | §3, App. E | RESEARCH_LOG W3 |
| tool-type counts (retail 7/7/1/1, airline 6/6/1/1, telecom 6/6/1/0), the regex misses 5/6 telecom writes, 99.98% any_write agreement, 1.6% of episodes with an invalid call | Table 1, App. A, App. F | `analysis/insights/iter_4/out/tool_types.json`; METHODOLOGY_REVISION C5 |
| excess λ: RTN +0.19 [0.10, 0.30], GPTQ +0.15 [0.07, 0.24], AWQ +0.16 [0.07, 0.25]; per-model points; Holm 0.007/0.007/0.036; weak floors on q14/q30a3/q32; RTN CI excludes 0 only on q4, q32 | §3, Table 8 (App. D) | `docs/insights/iter_3_stats_R3.md` (Declared family table), `analysis/insights/iter_3/out/r10_turnover_stats_live_20260929T1937Z.json`; REVIEW_PACKET R1 |
| thresholds g_min 3 pp, ε 3 pp, TOST (−3, +3), 5 pp sensitivity only | §4.4, §6 | EXTERNAL_REVIEW §F; METHODOLOGY_REVISION B3 |
| ε rationale: ≈2.5 tasks per run; nonce SD 2.5 pp (q4), 2.9 pp (q8); q8 AWQ-W4 d3 +5.3 pp | §6 | METHODOLOGY_REVISION B3 (ε justification) |
| ~80 human-reviewed states, ~20 double-reviewed | §5, Ethics, checklist D | EXTERNAL_REVIEW Round 3 (Annotation) |
| task-clustered new-task width ≈ ±4 pp (dev mode, stand-in pairs, not a result) | Limitations | METHODOLOGY_REVISION §3 (B1 bullet); STORYLINE_v6 correction |
| H3 table: original / main / sensitivity F and p for 7 families; RAND 74% → 90% of F | Table 5 (App. A) | METHODOLOGY_REVISION B1 |
| H3 simulation: 0.364/0.331/0.417 vs 0.053/0.044/0.061; iid check 0.0405 vs 0.81; power 0.07/0.12/0.24/0.75 | App. A | METHODOLOGY_REVISION B1 (Simulation) |
| reproduction F 0.2602, p 0.0008, H1 p 0.74385 | App. A | METHODOLOGY_REVISION §0 |
| φ 0.396 / 0.469 / 0.327; p 0.744 / 0.744 / 0.721 | App. A | METHODOLOGY_REVISION B2 |
| crossed components q4 2.62/3.69/−0.86/−2.07, q8 2.61/1.24/1.26/0.30 | Table 6 (App. A) | METHODOLOGY_REVISION B2 (Variance components) |
| p_act missing flag 17–34% of q4 positions | App. A | METHODOLOGY_REVISION C1 |
| act/talk: 0.014 → 0.088 vs 0.080 null; unconditional ΔP(act) −0.10 to +0.005 | §1 (qualitative), App. A | METHODOLOGY_REVISION C9 |
| prereg H1 φ 0.40 (q4 −0.30, q8 0.94), p 0.74; H2 r 0.42 (q4 −0.52, q8 0.94), p_holm 0.42; H3 F 0.26, p_holm 0.0024; H4 −0.83 [−7.07, 4.22], p 0.70 | Table 7 (App. B) | `analysis/insights/iter_4/out/prereg_h1_h4_CONF_20260930T0044Z.json` (confirmatory_table, secondary.per_model); PREREG_iter4 sha16 a991e2e5ca2d6098 |
| 28 runs (40 miscount amended); q4 84 tasks | App. B | PREREG_iter4 §7 Amendment 1 |
| q4 d1 − d2 +9.6 pp [1.8, 17.4] (exploratory); new q4 recalibrations +1.5 to +3.9 pp (q4 only); q8 AWQ d3 +5.3 (+8.2 on q2) | App. B | STORYLINE_v6 Line A; EXTERNAL_REVIEW A.4; prereg JSON (nets 0.0149–0.0387) |
| RECAL F 0.025, p 0.30 (sens. 0.13, within 0.19); RAND 0.283, p 0.028; pooled p 0.013, RAND 90% | App. C | METHODOLOGY_REVISION B1 and §3 |
| Dutta flips up to 13.6%; Singh churn ≈5×; Flat Score (4 trials, TOST ±7.5, 2.5×, error budget); Replay Gap (>90% FP8, AWQ near-identical); tau2 #540 7–8 / 10–11 pt; Bjarnason 2.2–6.0 pp | §2 | `docs/insights/SURVEY.md` T1, T4, T5, T9a |

Wording taken from the binding sources:
- "exploratory results did not replicate in the pre-registered confirmation" (EXTERNAL_REVIEW A.3).
- The random-perturbation sentence (Round 2).
- "not recovered under the tested continuation controllers and the fixed remaining budget" (Round 2).
- Mechanics of the fork design (strict replay, prompt-id equality check, forced action consumes a step). These come from EXTERNAL_REVIEW §E and are consistent with `docs/insights/FORK_PROTOCOL.md` §1–§4. FORK_PROTOCOL was read for these mechanics only; none of its numbers are used.

## Open placeholders (`\pending{}`; 136 rendered instances)

| Key / location | What fills it |
|---|---|
| Abstract | findings sentence, from §4.5 and §6 only |
| §1 end | one-paragraph result summary |
| §3 Prompt nonces | stratified floor table for the reference controls. Identical-setting repeats and a BF16-vs-BF16 nonce control are not run yet (METHODOLOGY_REVISION B4) |
| §3 Background | paired Q−B success NI/TOST/difference: `analysis/insights/iter_4/success_ni.py` in real mode, once `a6k2_{q4,q8}_bfpair_q1..q5` are admitted |
| §4.3 | replay gate (a)–(e) outcome: `analysis/fork/gate/` (`gate.json`, `gate_same.json`) from `scripts/a6000/fork_driver.py`; FORK_PROTOCOL §8 |
| §4.4 | interval method and simulated coverage for sparse events (statistics deliverable, review §D); multiplicity rule (to be frozen in `docs/insights/PREREG_FORK_CONFIRM.md`) |
| Table 2 DEV-a | divergence coverage, from the frozen state files written by `fork_driver.py` |
| Table 2 DEV-b, DEV-c | composition, G_all (fixed pool and new tasks), conditional G, A/C/I. From the branch outcomes plus a paired-block analysis script to be added under `analysis/fork/` (**not yet written**) |
| Table 3 HOLD | telecom holdout, under the frozen PREREG_FORK_CONFIRM.md (**not yet written**) |
| Table 4 MECH, MECH-h | defect types × damage × recovered: `annotations.jsonl` from `cloq/fork_annotate.py` plus LLM labels. The labeller model and rules are not fixed yet. Human review agreement and confusion matrices |
| §5 end | which development outcome occurred; the frozen hypothesis |
| §7 | discussion (pending, apart from two design-level readings) |
| Ethics | reviewer identity and instructions |
| App. E | fork serving record (`logs/tasks/<fork task>.servers.json`) |
| App. G | per-domain and per-divergence-category split; stratified confusion matrices |

## Citations

- Every `\cite` key resolves in `refs.bib`.
- **Not cited because no verified bib entry exists yet** (TODO in the checklist, B1): Qwen3 technical report, vLLM (Kwon et al.).
- Survey-only papers were not added. The related-work set is the six required papers plus agent-evaluation noise work that is already in the bib.
- Flat Score details are cited from SURVEY [full]; AgentProv and Model Equality Testing from SURVEY [abs].

## Known gaps and caveats

- The simulator is named "Qwen3-30B-A3B", following REVIEW_PACKET. The old draft said "-Instruct-2507"; this should be confirmed from `scripts/a6000/noderunner.py` before submission.
- GPTQ/AWQ group size and symmetry are not stated; they are a TODO in checklist C2.
- The fork-analysis script, `PREREG_FORK_CONFIRM.md`, the LLM labeller and the annotation guidelines do not exist yet. The paper names them as future outputs, not as existing files.
- `\resizebox` shrinks the placeholder tables. Recheck legibility once they contain numbers.
