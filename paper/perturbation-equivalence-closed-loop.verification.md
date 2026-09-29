**TL;DR** Verification pass on `paper/perturbation-equivalence-closed-loop.md` (2026-09-28). There are 37 sources, all resolved, with no wrong IDs and no [UNVERIFIED] entries. Every prior-work claim now has an inline `[N]`. Six literature statements were corrected to match the papers. One internal number was wrong and is fixed (4B recovery rates). One range was mislabelled and is fixed (legacy q8 floor). The five requested conflict resolutions are applied, and all 17 `[PENDING: …]` placeholders are kept.

## 1. Citations and sources
- The Appendix C table was replaced by a numbered list, [1]–[37], in order of first citation. Every number is cited in the body, and every source in the list is cited.
- **Resolution check.** Each of the 35 arXiv IDs returned 200 on `arxiv.org/abs/<id>`. Title, first author and date were read from the `citation_*` meta tags and cross-checked against the Semantic Scholar batch API (`/graph/v1/paper/batch`); all matched. The arXiv export API was rate-limited, so the abs pages were used as the arXiv index.
- **Non-arXiv sources.**
  - tau2-bench #540 is live (GitHub API). Title: "Run-to-run noise floor…". Author: Universeyi. Opened 2026-09-12.
  - The Thinking Machines blog returned 200. Author: Horace He.
- **Venue labels.** Checked against arXiv Comments or the Semantic Scholar venue: Du → TMLR 2026; Replay Gap and Yang → COLM 2026; Sinha → ICLR 2026 (preprint 2025); ACBench → ICML; Signal and Noise → NeurIPS; Lunardi → ECAI; Mizrahi → TACL (preprint 2023); DAgger → AISTATS 2011 (preprint 2010).
- **Title and author fixes in the Sources list.**
  - "IFFC 2026" is Taheri et al., *Small Reasoning Models are Instruction Followers in Function Calling*.
  - "Agentic Benchmark Checklist" is Zhu et al., *Establishing Best Practices for Building Rigorous Agentic Benchmarks*.
  - The other entries now carry their full arXiv titles.
- **Literature statements corrected to match the papers** (checked in the arXiv HTML, the abstracts, or the Du PDF):
  - **Flat Score.** "±7.5-pt margin scaled from one repeat run" became "TOST at ±7.5 pt; noise floor (~1.5 pt) estimated from one repeat run". These are separate things in the paper. Changed in §2 and Table 2.
  - **Singh.** "Proposes paired TOST at declared ±2 pt" became "paired equivalence testing at a declared margin (±2 pt in its worked example)".
  - **Bjarnason.** "2.2–6.0 pp at T = 0" became "2.2–6.0 pp across runs, with SD > 1.5 pp even at T = 0". The abstract does not tie the range itself to T = 0.
  - **VLAQuantBench.** The claim "reports point estimates per configuration" was removed; the current abstract reports task-clustered intervals. The sentence now says only that the paper evaluates PTQ of VLA policies in closed-loop simulation.
  - **Patodiya.** "Per-turn divergence 3.5%" became "3.5% on a single-turn bridge vs 36.2% per episode". The 3.5% is from the single-turn bridge table.
  - **Canonical-template sentence (§3.4).** Reworded to what Lunardi [35] and Mizrahi [36] support: scores change under paraphrase and templates, and paraphrases often score lower.
  - Smaller wording fixes:
    - ACBench: "workflow and tool use 1–3%".
    - Integer Alibi: "reports" instead of "confirms".
    - Du Eq. 14 is now called a heuristic, which is how the paper describes it.
- **Claims checked and confirmed:**
  - ACBench: SmoothQuant and T = 0 (HTML).
  - Du Eq. 14 (PDF, line "P(flip at t) ≲ P(∆t < σz) (14)").
  - Integer Alibi AUC 0.942.
  - Flat Score: "token log-probabilities are not in our logs", 4 trials per task, 2.5×, 17 pt.
  - Noise Floor Audit: 11–58×, and multi-turn agent trajectories excluded.
  - Replay Gap: over 90% for FP8.
  - tau2 #540: 7–8 and 10–11 pt.
- **Not checked in full text:** ACBench's "one run, no variance". It is now worded as "our notes record…".

## 2. Internal numbers (repo `/data/ziyangs/cloq`)
- **Checked directly against the JSON or output files named in the provenance map, and all match the draft:**
  - `analysis/insights/iter_1/verify/out/v01_legacy_recompute{,_a6k2}.json`: every Table 3a hazard, CI and KM value; legacy q4 and q8 hazards; clean q8 k = 0.03 KM 0.84 [0.75, 0.93]; KM ≤ 4 0.54–0.69 → 0.78–0.79; text/tool ratios 5.8/5.7 and 6.4/11.3.
  - `v02_a6k2_det.json`: 257/257, 303/303, 0 flips, and the simulator first message differing on 11/20 tasks.
  - `v03_outcomes_pooled{,_a6k2}.json`: pooled free zone (−0.2, −0.7, +1.9, −3.5); eager 11/69; naive McNemar p = 0.021 and Δ −8.3; nested pass sets 0/10, 0/8, 0/4, 0/7; clean W3 −8.5 and −9.3 with 3v4 and 3v3; max_steps 7/33 and 8/32.
  - `v04_pooled_draws.json`: all of Table 4; q8 families; canonical 0.412→0.329 and 0.316→0.380; 21/85 and 21/79; p 0.19 and 0.38; null SD 2.9/3.2 and 3.75/3.26; canonical +1.8 and +1.9.
  - `out/s04_node_floor.json`: 113 decisions, 20/20 tasks, median 0.125, 59.1% of tokens non-zero, KM 0.50/0.95.
  - `out/s07_flavour_outcome.json`: 4/20, 0.45/0.55, p = 0.625.
  - `analysis/openloop/a6k2/q4/{rtn_w4,bf16}.json`: all of Table 5 and every E3 aggregate.
  - `analysis/coling/RESULTS.md`, `analysis/v1/FINDINGS_V1.md` and `docs/PROGRESS_2026-09-28.md` §2: the 4B numbers and Table 6.
- **Fixed.**
  - **4B recovery rates.** 0.68 (read) vs 0.21 (write) became 0.21–0.35 (write) vs 0.40–0.80 (read/lookup), among BF16-solved tasks. The source is `analysis/strategy_v2_workflow/mechanism/a567.out` Q7, table "recovery by (BF16 action, Q action)": write 0.214/0.300/0.346; read/lookup 0.398/0.677/0.800. The old 0.68 was one cell (text→read), and read→read is 0.398. Changed in §5.2 and Open questions; the provenance row was updated to match.
  - **Legacy q8 floor.** Legacy q8 at k = 0.03 is 0.12–0.14, not 0.11–0.14. The 0.11 value is from the clean seeds, and both are now stated.
  - **Tool-flip triple in §5.3.** Now labelled AWQ / RTN / k = 1. The unlabelled list could be misread as including GPTQ, whose rate is 0.23–0.30.
  - **Replication statement.** −0.035 pooled (−0.045 long); "both intervals" instead of "all intervals", matching FINDINGS_V1 §5.
  - **RTN-W3 max_steps counts.** Labelled "both domains".
- **Requested resolutions.**
  - v0 p = 0.0195: already correct in §1, §5.4 and App. A.
  - Replication −0.035 pooled: kept.
  - BF16 self-replay: now reads "no token flips, |Δlogprob| ≤ 5e-5 … the rounding of logged log-probabilities". The maximum |d| in `bf16.npz` is 4.9992e-5 and the p99 is 4.9e-5. The earlier phrase "which confirms … no measurable perturbation" was removed.
  - Autotune incident: contribution 3 now says 59% of tokens, and §6 already did. "Every token" does not appear anywhere.
  - Closed-loop vs E3 |d|: both definitions are introduced in §3.1 and §4. They are labelled as different quantities in the Table 3a caption, Table 5 caption, the §5.3 units paragraph (the side-by-side 1.75–2.0 vs 1.3e-6 contrast was removed), the q8 placement vs the pending E3 test, P3a, the Figure 2/3 notes and Limitations.

## 3. Not changed
- No results were added, and all 17 `[PENDING: …]` blocks are unchanged.
- The a6k2 numbers are live snapshots (2026-09-29T02:36Z) and must be re-run when the cells finish.
- The 4B numbers are still checked against analysis files only, not raw runs.
