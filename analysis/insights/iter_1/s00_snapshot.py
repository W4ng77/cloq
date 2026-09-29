"""Data snapshot for this iteration: status and decision counts of every A6000 run (read-only)."""
import datetime
from common import DOMAINS, RUNS, a6000_runs, dump, status

snap = {"taken_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "runs": {}}
for r in a6000_runs():
    snap["runs"][r] = {}
    for d in DOMAINS:
        p = RUNS / r / d / "decisions.jsonl"
        n = sum(1 for _ in open(p)) if p.exists() else 0
        snap["runs"][r][d] = {"status": status(r, d), "n_decisions": n}
done = sorted(f"{r}/{d}" for r, v in snap["runs"].items() for d, x in v.items() if x["status"] == "completed")
snap["completed"] = done
print(snap["taken_utc"], "runs:", len(snap["runs"]), "completed domains:", done)
dump("s00_snapshot.json", snap)
