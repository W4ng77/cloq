"""W100av holdout QQ-full preconditions, per task, as soon as its servers are up (HOLDOUT_QQFULL_PROTOCOL.md §3; GPT 10-05):
the Q server's ckpt_sha256, effective_config_sha and numerics canary (logs/tasks/<id>.servers.json, written at server start)
must equal the original fork_hold_* task's (queue/done result.servers.Q). On any mismatch the cell's not-yet-started tasks
are moved from todo/ to deferred/ (pausing that configuration) and the script exits 1. No outcome is read.
usage: python scripts/a6000/qqfull_precheck.py [--no-pause]"""
import argparse, json, shutil, sys
from pathlib import Path

W = Path("/data/ziyangs/cloq_work")
Q, KEYS = W / "queue", ("ckpt_sha256", "effective_config_sha", "canary")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pause", action="store_true")
    a = ap.parse_args()
    bad, rows = set(), []
    for t in sorted(p.stem for d in ("todo", "running", "done", "failed") for p in (Q / d).glob("qqfull_hold_*.json")):
        cell, g = t[len("qqfull_hold_"):].rsplit("_", 1)
        sj = W / "logs/tasks" / f"{t}.servers.json"
        if not sj.exists():
            rows.append((t, "servers not up yet"))
            continue
        new = json.load(open(sj))["Q"]
        old = json.load(open(Q / "done" / f"fork_hold_{cell}_{g}.json"))["result"]["servers"]["Q"]
        eq = {k: new.get(k) is not None and new.get(k) == old.get(k) for k in KEYS}
        rows.append((t, " ".join(f"{k}={'ok' if v else 'MISMATCH'}" for k, v in eq.items())))
        if not all(eq.values()):
            bad.add(cell)
    for t, s in rows:
        print(f"{t:36s} {s}")
    if bad and not a.no_pause:
        for p in sorted(Q.glob("todo/qqfull_hold_*.json")):
            if any(p.stem.startswith(f"qqfull_hold_{c}_") for c in bad):
                shutil.move(str(p), Q / "deferred" / p.name)
                print("paused (todo -> deferred):", p.name)
    print("PRECHECK", "FAIL " + ",".join(sorted(bad)) if bad else "OK (all started tasks)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
