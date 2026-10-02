"""W99o: per-state comparison of a quarantined pre-fix fork directory with its fixed-code rerun (same state ids).

usage: python scripts/ext/w99o_state_compare.py NAME [NAME ...] -> prints JSON (states, outcome changes per arm)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def eff(d):
    return {json.loads(x)["state_id"]: json.loads(x) for x in (d / "effects.jsonl").read_text().splitlines() if x.strip()}


out = {}
for name in sys.argv[1:]:
    o, n = eff(ROOT / "analysis/fork/ext/quarantine/w99o" / name), eff(ROOT / "analysis/fork/ext/dev" / name)
    common = sorted(set(o) & set(n))
    ch = [s for s in common if o[s]["Y"] != n[s]["Y"]]
    out[name] = {"old_states": len(o), "new_states": len(n), "common": len(common), "only_old": len(set(o) - set(n)),
                 "only_new": len(set(n) - set(o)), "states_with_changed_Y": len(ch),
                 "changed_among_old_replay_false": sum(1 for s in ch if o[s].get("replay") is False),
                 "changed_among_old_replay_true": sum(1 for s in ch if o[s].get("replay") is True),
                 "arm_changes": {b: sum(1 for s in ch if o[s]["Y"][b] != n[s]["Y"][b]) for b in ("BB", "BQ", "QB", "QQ")},
                 "new_replay_false": sum(1 for s in n.values() if s.get("replay") is not True),
                 "changes": [{"state_id": s, "task_id": n[s]["task_id"], "old_replay": o[s].get("replay"), "old": o[s]["Y"], "new": n[s]["Y"]} for s in ch]}
print(json.dumps(out, indent=1))
