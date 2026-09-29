"""Snapshot of the a6k2 (clean) and a6000 (legacy) runs used by iteration-2 prep: per run-domain status, tasks with an
outcome, and termination reasons (infrastructure_error counted separately; see common.INFRA).
Usage: python p00_snapshot.py -> out/p00_snapshot.json
"""
import json
from collections import Counter

from common import DOMS, RUNS, dump, now, outcomes


def main():
    res = {"snapshot_utc": now(), "runs": {}, "infra_error_runs": {}}
    for p in sorted(RUNS.iterdir()):
        if not p.is_dir() or not p.name.startswith(("a6k2_", "a6000_")):
            continue
        r = {}
        for d in DOMS:
            st = p / d / "status.json"
            if not (p / d).exists():
                continue
            o = outcomes(p.name, d, with_reason=True)
            tr = Counter(v[1] for v in o.values())
            r[d] = {"status": json.load(open(st)).get("status") if st.exists() else None, "n_outcomes": len(o),
                    "terminations": dict(tr)}
            if tr.get("infrastructure_error"):
                res["infra_error_runs"][f"{p.name}/{d}"] = f"{tr['infrastructure_error']}/{len(o)}"
        res["runs"][p.name] = r
    dump("p00_snapshot.json", res)
    print(res["infra_error_runs"])


if __name__ == "__main__":
    main()
