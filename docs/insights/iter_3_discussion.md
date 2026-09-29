**TL;DR**
- Iteration-3 discussion log (quantization-centred, `docs/insights/PLAN_iter4.md`). Round 1 proposes I5–I8. The full text is in `docs/insights/iter_3_candidates.md`.
- Survey: please answer S5-a…S8-b, with priority on S6-a/b (Hooker-style PIEs vs random noise and vs other architectures) and S5-b (the unit of Flat Score's ρ ≥ 0.94).
- Experiment: please cost and critique E17 (RTN-shaped Gaussian) and E20 (extra q8/q30a3 quantizer draws).

# Iteration 3 discussion

## Insight (round 1)

Four candidates, all computed on the iteration-2 gate. Two snapshots were used:
- frozen: `analysis/insights/iter_2/out/snapshot_20260929T0732Z.json`;
- live, provisional: `analysis/insights/iter_3/out/snapshot_live_20260929T1159Z.json`.

Scripts are `analysis/insights/iter_3/r01–r09`; re-run with `run_all.sh`.

- **I5, size-generic reallocation.** A fixed weight perturbation re-deals a fraction λ of robust tasks toward an attractor c, so Δ = λ(c − p̄) while λ = 0.07–0.48 at W4 (null SD 0.04–0.08).
  - Gaussian noise of equal weight norm re-deals *more* than every W4 quantizer: pooled +0.11 to +0.15, 4/4 models.
  - A null-scale fixed checkpoint re-deals nothing.
  - Among RTN, GPTQ and AWQ there is no pooled difference.
  - evidence: `analysis/insights/iter_3/out/r08_size_generic_{live,frozen}.json`, `r01_realloc_live.json`.
- **I6, fragility is latent and (model, task)-specific.** Breaks and fixes have four properties:
  - they repeat across nonces of one checkpoint (lift 2.2–5.1);
  - Gaussian-derived fragility predicts quantizer breaks (AUC 0.75–0.83; super-robust 0.68–0.81);
  - they do not transfer across models (AUC 0.51);
  - they are invisible to BF16 margins and to open-loop per-task flips (AUC 0.4–0.6).
  - evidence: `r03_fragility_live.json`, `r04_margin_predict_live.json`, `r05_openloop_task_live.json`, `r06_crossmodel_live.json`.
- **I7, open loop predicts how much, not which, and not net.** ρ(open-loop flip, λ) = 0.75–0.83. ρ with Δ is weak or null, and task-level AUC is about 0.5. This explains the iteration-2 C4 refutation through Δ = λ(c − p̄).
  - evidence: `r05_openloop_task_{live,frozen}.json` `cell_identity`.
- **I8 (hypothesis), damage is attractor collapse with loud control failures.** At W4, 5/137 breaks end abnormally. q8 RTN-W3 has 37% abnormal terminations and c = 0.06. ρ(p̄ − c, abnormal excess) = 0.48.
  - evidence: `r07_damage_live.json`.

Killed this round (R3-a…f in the candidates file):
- BF16 margins predict the fragile set;
- open-loop per-task flips predict it;
- fragility is a task property;
- "any fixed checkpoint has a profile" (at k = 0.03 on q14);
- "quantization error is worse than noise".

**The most important experiment** is E17, RTN-shaped Gaussian noise (per-group σ equal to that group's RTN error RMS). It decides whether the noise > quantizer gap is the error's energy distribution or its rounding structure. That makes "predict a quantizer's agentic effect from its error size" operational at the right granularity.
