"""Regenerate metrics.json (and task_success.json's derived rate) for completed runs."""
import json, sys
from pathlib import Path
sys.path.insert(0, "/home/xinyu/cloq")
from cloq.metrics import summarize_run

for run_dir in sorted(Path("/home/xinyu/cloq/runs").glob("*/*")):
    if not (run_dir / "trajectory.jsonl").exists():
        continue
    m = summarize_run(run_dir)
    (run_dir / "metrics.json").write_text(json.dumps(m, indent=2))
    print(f"{run_dir.parent.name}/{run_dir.name}: n={m['n_tasks']} db_match={m['db_match_rate']} premature={m['premature_rate']}")
