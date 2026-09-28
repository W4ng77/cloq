"""Loop attribution for every run ending at max_steps / too_many_errors / infrastructure_error
across the 18 GPTQ dev checkpoints + BF16 v1 + RTN eval (STRATEGY_v2 open item #13).

Rule (fixed BEFORE looking at arm labels -- it is purely mechanical and never consults arm/draw
identity):
  1. Split a trajectory's messages into the ordered list of user utterances (content, whitespace-
     normalised) and the ordered list of agent actions (cloq.metrics.normalize_action of each
     assistant message's content + tool_calls).
  2. Compute the longest run of consecutive EXACT duplicates within each list separately
     (user_max_run, agent_max_run).
  3. Classify (threshold: a message/action repeated verbatim >=3 times consecutively):
       - both runs >= 3            -> "mixed"           (lockstep call-and-response loop)
       - only user_max_run  >= 3   -> "simulator-side"   (user stuck, agent content varies)
       - only agent_max_run >= 3   -> "agent-side"        (agent stuck, e.g. repeats failing tool call)
       - neither                  -> "no_repetition"      (e.g. too_many_errors from distinct errors)

This only classifies trajectories whose termination_reason is NOT in
cloq.metrics.NORMAL_TERMINATIONS (user_stop, agent_stop), i.e. max_steps / too_many_errors /
infrastructure_error, matching the project's own "premature" definition.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from common import ARMS, DRAWS, RUNS, save_json  # sets sys.path to repo root
from cloq.metrics import NORMAL_TERMINATIONS, normalize_action, read_jsonl, resolved_db_match

RUN_SPECS = []
for arm in ARMS:
    for draw in DRAWS:
        for dom in ("retail", "airline"):
            RUN_SPECS.append((f"{arm}_{draw}_dev/{dom}", arm, draw, dom))
for dom in ("retail", "airline"):
    RUN_SPECS.append((f"bf16_v1/{dom}", "bf16_v1", None, dom))
    RUN_SPECS.append((f"rtn_eval/{dom}", "rtn", None, dom))


def norm_text(s: str | None) -> str:
    return " ".join((s or "").strip().split())


def longest_run(seq: list) -> tuple[int, object]:
    best, best_val, cur, cur_val = 0, None, 0, object()
    for x in seq:
        if x == cur_val:
            cur += 1
        else:
            cur_val, cur = x, 1
        if cur > best:
            best, best_val = cur, cur_val
    return best, best_val


def classify(traj: dict) -> dict:
    msgs = traj["messages"]
    user_seq = [norm_text(m.get("content")) for m in msgs if m.get("role") == "user"]
    agent_seq = [
        normalize_action(m.get("content"), m.get("tool_calls"))
        for m in msgs if m.get("role") == "assistant"
    ]
    user_run, _ = longest_run(user_seq)
    agent_run, _ = longest_run(agent_seq)
    if user_run >= 3 and agent_run >= 3:
        label = "mixed"
    elif user_run >= 3:
        label = "simulator-side"
    elif agent_run >= 3:
        label = "agent-side"
    else:
        label = "no_repetition"
    return {"label": label, "user_max_run": user_run, "agent_max_run": agent_run, "n_messages": len(msgs)}


def main():
    rows = []
    for rel, arm, draw, dom in RUN_SPECS:
        trajs = read_jsonl(RUNS / rel / "trajectory.jsonl")
        for t in trajs:
            term = t.get("termination_reason")
            if term in NORMAL_TERMINATIONS:
                continue
            cls = classify(t)
            rows.append({
                "arm": arm, "draw": draw, "domain": dom, "task_id": t["task_id"],
                "termination_reason": term, **cls,
            })

    by_label = Counter(r["label"] for r in rows)
    by_arm_label = defaultdict(Counter)
    for r in rows:
        by_arm_label[r["arm"]][r["label"]] += 1
    by_term_label = defaultdict(Counter)
    for r in rows:
        by_term_label[r["termination_reason"]][r["label"]] += 1

    # A8-style sensitivity check: among the 18 dev checkpoints (excluding bf16_v1/rtn), what
    # fraction of premature failures are simulator-side, and how much does pooled/long db_match
    # per checkpoint shift if simulator-side premature trajectories are EXCLUDED from the
    # denominator (treated as missing) instead of scored as failure (the project's current
    # convention, cloq.metrics.resolved_db_match)?
    dev_rows = [r for r in rows if r["draw"] is not None]
    simulator_side_ids = {(r["arm"], r["draw"], r["domain"], r["task_id"]) for r in dev_rows if r["label"] == "simulator-side"}

    orig_by_ckpt = defaultdict(list)
    adj_by_ckpt = defaultdict(list)
    for arm in ARMS:
        for draw in DRAWS:
            for dom in ("retail", "airline"):
                trajs = read_jsonl(RUNS / f"{arm}_{draw}_dev/{dom}" / "trajectory.jsonl")
                for t in trajs:
                    v = resolved_db_match(t)
                    v = bool(v) if v is not None else False
                    key = f"{arm}_{draw}"
                    orig_by_ckpt[key].append(v)
                    if (arm, draw, dom, t["task_id"]) in simulator_side_ids:
                        continue  # excluded from adjusted denominator
                    adj_by_ckpt[key].append(v)

    import numpy as np
    sensitivity = {}
    for k in orig_by_ckpt:
        o = orig_by_ckpt[k]
        a = adj_by_ckpt[k]
        sensitivity[k] = {
            "orig_pooled_db_match": float(np.mean(o)), "orig_n": len(o),
            "adjusted_pooled_db_match": float(np.mean(a)) if a else None, "adjusted_n": len(a),
            "n_excluded_simulator_side": len(o) - len(a),
        }
    max_shift = max(abs(v["orig_pooled_db_match"] - (v["adjusted_pooled_db_match"] or v["orig_pooled_db_match"])) for v in sensitivity.values())

    result = {
        "n_premature_total": len(rows),
        "counts_by_label": dict(by_label),
        "counts_by_arm_label": {a: dict(c) for a, c in by_arm_label.items()},
        "counts_by_termination_reason_label": {t: dict(c) for t, c in by_term_label.items()},
        "n_dev_checkpoint_premature": len(dev_rows),
        "n_dev_simulator_side": sum(1 for r in dev_rows if r["label"] == "simulator-side"),
        "per_checkpoint_sensitivity_excluding_simulator_side": sensitivity,
        "max_pooled_db_match_shift_from_exclusion": max_shift,
        "rows": rows,
    }
    save_json("04_loop_attribution.json", result)
    print(f"n_premature_total={len(rows)}  by_label={dict(by_label)}")
    print("by arm:")
    for a, c in by_arm_label.items():
        print(" ", a, dict(c))
    print("by termination_reason:")
    for t, c in by_term_label.items():
        print(" ", t, dict(c))
    print(f"Max shift in pooled db_match from excluding simulator-side premature trajectories: {max_shift:.4f}")


if __name__ == "__main__":
    main()
