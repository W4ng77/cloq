**TL;DR** Outline for the COLING long paper draft (`paper/perturbation-equivalence-closed-loop.md`). Write
everything that current evidence supports; every multi-model A6000 result is a marked placeholder `[PENDING: …]`
naming the exact cells/script that will fill it. Deadline 2026-10-12.

# Outline: Perturbation Equivalence in Closed-Loop Agents

## Title
*Perturbation Equivalence in Closed-Loop Agents: When Is a Compressed Agent Actually Worse?*

## Thesis (one sentence)
In closed-loop agent evaluation any perturbation above the agent's near-tie floor re-rolls the trajectory, so a
compressed agent must be judged against the model's own perturbation distribution, not against one BF16 run.

## Sections, claims, sources

| § | Content | Claims (stable id → status) | Sources |
|---|---|---|---|
| Abstract | problem, criterion, first-order margin model, findings | — | all below |
| 1 Intro | v0 false positive (FP-Traj +0.121, p=0.0195 → −0.035 on replication) as opener; the serving-numerics result (I4a) as the second hook; 3 contributions | V1, I4a HELD | `analysis/coling/RESULTS.md`, `analysis/coling/02_v0_gap.py`, `docs/insights/iter_1_verdicts.md` |
| 2 Related work | compressed-agent eval (Flat Score 2607.27275, ACBench), eval noise (Noise Floor, Signal and Noise, AI Agents That Matter, pass^k, Replay Gap 2608.08239), per-step margin flip model (Du et al. 2026 TMLR 2609.26621 — inherited, credited), multi-turn degradation, open- vs closed-loop | positioning only | `analysis/coling/RELATED_WORK.md`, `docs/insights/SURVEY.md`, `docs/insights/survey_sweeps/*.md`, `analysis/insights/references_new.bib` |
| 3 Framework | definition of perturbation equivalence (task-level exchangeability with a null family: nonce, weight-only gauss k=0.03, serving-numerics flavour); first-order margin model P(flip_s)≈P(m_s<δ), divergence hazard; predictions P1 (tie floor then δ-ranked per-decision divergence), P2 (damage threshold later than divergence threshold), P3 (margin distribution predicts divergence curve) | I1 REVISE (rewritten form), I2 HYPOTHESIS, I3 HYPOTHESIS at risk | `docs/insights/iter_1_candidates.md`, `docs/COLING_PLAN.md` §2 |
| 4 Setup | τ²-bench retail+airline (85 dev tasks), 32k harness, Qwen3 4B/8B/14B/30B-A3B/32B, perturbation matrix (nonce×5, gauss k∈{0.03..3}×2, RTN W8/W4/W3, GPTQ W4×2 draws, AWQ W4, GPTQ W3, eager BF16), deterministic serving (batch invariance + deterministic Inductor + numerics canary; cross-node det pairs 257/257, 303/303), fixed Qwen3-30B-A3B simulator | setup facts | `scripts/a6000/make_tasks.py`, `scripts/a6000/models.json`, `docs/RESEARCH_LOG.md` W1–W4 |
| 5.1 P1 divergence | per-decision divergence floor 0.17–0.23 (q4) / 0.11–0.14 (q8), 0.42–0.45 at k=0.3, 0.77–0.99 at k=1; D≡0 → no divergence | tentative on q4/q8; `[PENDING: 5-model curve, E3 + a6k2 matrix]` | `analysis/insights/iter_1/verify/out/`, `iter_1_verdicts.md#I1` |
| 5.2 P2 free zone | q4 pooled: null-level success through k=1 & W4, −16 pp at k=3, −14 pp at W3; clean a6k2 W3 alone n.s. | HYPOTHESIS; `[PENDING: a6k2 q4/q8 nulls + damage cells, verify/v03, v04]` | `iter_1_verdicts.md#I2` |
| 5.3 P3 / D | E3 open-loop D: q4 RTN-W4 flip rate by BF16 margin 0.57 (<0.25) → 0.003 (≥8); BF16 self-replay D=0 sanity; q8 RTN-W4 −10.5 pp vs gauss k=1 0.0 at matched D | pilot facts; I3 at risk; `[PENDING: E3 all cells]` | `analysis/openloop/a6k2/q4/{bf16,rtn_w4}.json`, `scripts/a6000/openloop_d.py` |
| 5.4 Consequences (4B deep dive) | 18 GPTQ ckpts × 6 calibration arms indistinguishable (perm p=0.683/0.368); open-loop NLL unrelated to success (|r|≤0.13); flips state-determined (AUC 0.93); failures write-dominated; loops agent-side; serving numerics alone flips ~1/4 task outcomes (I4a) | HELD | `analysis/v1/FINDINGS_V1.md`, `analysis/coling/RESULTS.md`, `iter_1_verdicts.md#I4` |
| 6 Robustness | 8k vs 32k (ranking stable); simulator-side loops ≤0.009; determinism incident as a finding (Inductor autotune → kernel flavour re-rolls 95% of trajectories) | held / described | `docs/PROGRESS_2026-09-28.md` §2, `docs/RESEARCH_LOG.md` W3 |
| 7 Recommendations | checklist for evaluators | — | derived |
| Limitations | 2 domains, 85 tasks, greedy, fake-quant mostly, one simulator, one model family | — | — |
| Conclusion | — | — | — |

## Figures/tables (placeholders unless data exists)
- Fig 1 schematic (mermaid ok in draft). Fig 2 divergence vs δ (5 models) PENDING. Fig 3 success vs δ with null band PENDING.
- Fig 4 E3 flip-rate vs BF16 margin: q4 RTN-W4 pilot available now (`analysis/openloop/a6k2/q4/rtn_w4.json`).
- Tab 1 matrix; Tab 2 related-work comparison; Tab 3 8k vs 32k (`docs/PROGRESS_2026-09-28.md` §2).

## Verification log (critical claims)
| claim | check | status |
|---|---|---|
| v0 FP-Traj +0.121, McNemar p=0.0195, replication −0.035 | `analysis/coling/RESULTS.md` | to check by verifier |
| I4a q4 0.412→0.329, q8 0.316→0.380, 21/85 & 21/79 flips | `iter_1_verdicts.md`, `verify/v04_pooled_draws.py` out | recomputed by verify agent |
| det pairs 257/257, 303/303 | `docs/RESEARCH_LOG.md` W3 | recomputed in session |
| E3 pilot numbers | `analysis/openloop/a6k2/q4/*.json` | from file |
| v1 arm perm p 0.683/0.368 | `analysis/v1/FINDINGS_V1.md` | to check |
| every related-work citation | URLs | verifier subagent |
