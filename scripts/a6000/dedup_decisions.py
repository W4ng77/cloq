"""W8: keep, per task, only the decision records of the final attempt.

tau2 auto_resume + max_retries re-run an interrupted or failed simulation, and cloq.agent appends to decisions.jsonl,
so a task can carry records from an abandoned attempt (a different trajectory_id). The final attempt is the one
whose records appear last in the file. Checks: the kept decision count per task equals the number of assistant turns
in trajectory.jsonl. Rewrites decisions.jsonl atomically; prints per-run stats.
usage: python scripts/a6000/dedup_decisions.py runs/a6k2_*/*/  [--dry]
"""
import json
import os
import sys
from collections import OrderedDict


def n_assistant(rec):
    return sum(1 for m in rec["messages"] if m.get("role") == "assistant")


def main(paths, dry):
    tot_drop = tot_bad = 0
    for r in paths:
        dp, tp = os.path.join(r, "decisions.jsonl"), os.path.join(r, "trajectory.jsonl")
        if not (os.path.exists(dp) and os.path.exists(tp)):
            continue
        lines = open(dp).read().splitlines()
        last = OrderedDict()
        for ln in lines:
            x = json.loads(ln)
            last[x["task_id"]] = x["trajectory_id"]
        keep = [ln for ln in lines if (lambda x: last[x["task_id"]] == x["trajectory_id"])(json.loads(ln))]
        cnt = {}
        for ln in keep:
            t = json.loads(ln)["task_id"]
            cnt[t] = cnt.get(t, 0) + 1
        mism = 0
        for ln in open(tp):
            rec = json.loads(ln)
            na = n_assistant(rec)
            if cnt.get(str(rec["task_id"]), 0) not in (na, na - 1):  # the greeting turn is not a model decision
                mism += 1
        drop = len(lines) - len(keep)
        tot_drop += drop
        tot_bad += mism
        if drop or mism:
            print(f"{r}: drop {drop}/{len(lines)} records, {mism} tasks with count mismatch")
        if drop and not dry:
            tmp = dp + ".tmp"
            open(tmp, "w").write("\n".join(keep) + "\n")
            os.replace(tmp, dp)
    print(f"total dropped {tot_drop}, tasks with mismatch {tot_bad}")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--dry"]
    main(a, "--dry" in sys.argv)
