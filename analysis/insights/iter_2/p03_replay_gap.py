"""Review item 5 (W5 / Q4): reconcile our 16-27% outcome flips under numerics-only changes with Replay Gap's
0 outcome flips in 359 same-model control forks (arXiv 2608.08239).

For every clean cell (a6k2) against the canonical BF16 run of the same model, paired on the conversation excluding
the system prompt (so nonce cells are comparable), per task: did the agent diverge, at which decision (i*), how long
is the reference episode (L), who diverged first (agent = completion differs on identical context; ctx = the
conversation differed first, i.e. the user simulator or environment), and did the database outcome flip.
Tasks with infrastructure_error in either run are dropped.

Outputs per model, for agent-only perturbations (eager, nonces, k <= 0.03, W8; the simulator is canary-gated and
deterministic in a6k2) and for all cells:
  * outcome-flip rate overall, among never-diverged tasks, and by divergence depth (absolute i*, relative i*/L);
  * share of first divergences that are simulator/environment-first;
  * P(0 flips in 359 forks) if every fork flipped at our rate for late forks (i*/L >= 0.5);
  * the legacy -> clean canonical pair (agent + simulator numerics changed) for comparison.
Usage: python p03_replay_gap.py -> out/p03_replay_gap.json
"""
import re
from collections import defaultdict

import numpy as np

from common import dump, first_div, infra_tasks, load_many, now, outcomes_both, runs_for, RUNS

AGENT_ONLY = re.compile(r"_(bf16_eager|gauss0\.00[13]_s\d|gauss0\.01_s\d|gauss0\.03_s\d|rtn_w8_n\d|null_n\d)$")
ABS = [(0, 0, "0"), (1, 3, "1-3"), (4, 7, "4-7"), (8, 10 ** 6, "8+")]
REL = [(0, .25, "[0,.25)"), (.25, .5, "[.25,.5)"), (.5, .75, "[.5,.75)"), (.75, 1.01, "[.75,1]")]


def rate(xs):
    return {"n": len(xs), "flip_rate": round(float(np.mean(xs)), 4) if xs else None}


def summarise(recs):
    out = {"n_task_pairs": len(recs), "overall": rate([r["flip"] for r in recs]),
           "never_diverged": rate([r["flip"] for r in recs if r["why"] == "end"]),
           "diverged_agent_first": rate([r["flip"] for r in recs if r["why"] == "agent"]),
           "diverged_ctx_first": rate([r["flip"] for r in recs if r["why"] == "ctx"]),
           "by_abs_depth": {}, "by_rel_depth": {}}
    ag = [r for r in recs if r["why"] in ("agent", "ctx")]
    for lo, hi, name in ABS:
        out["by_abs_depth"][name] = rate([r["flip"] for r in ag if lo <= r["i"] <= hi])
    for lo, hi, name in REL:
        out["by_rel_depth"][name] = rate([r["flip"] for r in ag if r["L"] and lo <= r["i"] / r["L"] < hi])
    late = [r["flip"] for r in ag if r["L"] and r["i"] / r["L"] >= .5]
    if late:
        p = float(np.mean(late))
        out["late_fork_flip_rate"] = round(p, 4)
        out["P_zero_flips_in_359_at_late_rate"] = float((1 - p) ** 359)
    return out


def pairs_for(model, prefix="a6k2"):
    runs = runs_for(model, prefix)
    ref = f"{prefix}_{model}_bf16"
    D = load_many(sorted(set(runs)))
    Yr = outcomes_both(ref)
    recs = defaultdict(list)
    for run in runs:
        if run == ref:
            continue
        drop = infra_tasks(run) | infra_tasks(ref)
        Y = outcomes_both(run)
        for dom, t, i, e, kind, L, why in first_div(D[ref], D[run], "ctx"):
            if (dom, t) in drop or (dom, t) not in Y or (dom, t) not in Yr:
                continue
            recs[run].append({"i": i, "L": L, "why": why, "flip": int(Y[(dom, t)] != Yr[(dom, t)])})
    return recs


def main():
    res = {"snapshot_utc": now(), "models": {}}
    for model in ("q4", "q8", "q14"):
        recs = pairs_for(model)
        ao = [x for r, xs in recs.items() if AGENT_ONLY.search(r) for x in xs]
        al = [x for xs in recs.values() for x in xs]
        m = {"agent_only_cells": sorted(r for r in recs if AGENT_ONLY.search(r)),
             "agent_only": summarise(ao), "all_cells": summarise(al),
             "per_cell_flip_rate": {r: round(float(np.mean([x["flip"] for x in xs])), 4) for r, xs in recs.items() if xs}}
        # legacy -> clean canonical (agent + simulator numerics)
        a, b = f"a6000_{model}_bf16", f"a6k2_{model}_bf16"
        if (RUNS / a).exists():
            D = load_many([a, b])
            Ya, Yb = outcomes_both(a), outcomes_both(b)
            lr = [{"i": i, "L": L, "why": why, "flip": int(Ya[(d, t)] != Yb[(d, t)])}
                  for d, t, i, e, kind, L, why in first_div(D[b], D[a], "ctx") if (d, t) in Ya and (d, t) in Yb]
            m["legacy_vs_clean_canonical"] = summarise(lr)
            m["legacy_vs_clean_canonical"]["share_ctx_first"] = round(np.mean([r["why"] == "ctx" for r in lr]), 4)
            m["legacy_vs_clean_canonical"]["share_ctx_first_at_decision0"] = round(np.mean([r["why"] == "ctx" and r["i"] == 0 for r in lr]), 4)
        res["models"][model] = m
        print(model, "agent-only", m["agent_only"]["overall"], m["agent_only"]["never_diverged"], m["agent_only"]["by_rel_depth"],
              m["agent_only"].get("late_fork_flip_rate"), "ctx-first", m["agent_only"]["diverged_ctx_first"])
        if "legacy_vs_clean_canonical" in m:
            print("   legacy->clean", m["legacy_vs_clean_canonical"]["overall"], m["legacy_vs_clean_canonical"]["share_ctx_first"])
    dump("p03_replay_gap.json", res)


if __name__ == "__main__":
    main()
