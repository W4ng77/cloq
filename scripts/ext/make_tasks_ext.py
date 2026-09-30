"""Queue tasks for the simulator-free external environments (worker.py eval tasks with an "env" field).

  dev   : q4 BF16 on the manifest dev items, two identical runs (r1, r2) in one task -> deterministic re-run check
  smoke : q4 BF16 and q4 GPTQ-W4 d1 (calibration c1, the a6k2 spec) on the fixed smoke subsets, priority -7

usage: python3 scripts/ext/make_tasks_ext.py {dev|smoke} [--dry-run]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

Q = Path("/data/ziyangs/cloq_work/queue")
CKPTS = {"bf16": {"kind": "bf16"},
         "gptq_w4_d1": {"kind": "gptq", "wbits": 4, "calib": "manifests/a6k2/q4/calib_fp_traj_c1.json"}}
ENVS = {"bfcl": ("manifests/bfcl/bfcl_mt_v1.json", ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"]),
        "alfworld": ("manifests/alfworld/alfworld_text_v1.json", ["alfworld"])}


def task(model: str, arm: str, env: str, subset: str, reps: list[str], priority: int, tag: str = "") -> dict:
    man, domains = ENVS[env]
    tid = f"ext_{model}_{arm}_{env}_{subset}{tag}"
    return {"id": tid, "kind": "eval", "env": env, "model": model, "arm": "bf16" if arm == "bf16" else "gptq",
            "ckpt": CKPTS[arm], "domains": domains, "priority": priority,
            "runs": [{"run_id": f"{tid}{('_' + r) if r else ''}", "task_file": man, "subset": subset} for r in reps]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "smoke"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--env", default="", help="only this env")
    ap.add_argument("--tag", default="", help="task/run id suffix, e.g. _p2 for a prompt revision on dev")
    a = ap.parse_args()
    if a.mode == "dev":
        ts = [task("q4", "bf16", e, "dev", ["r1", "r2"], -8, a.tag) for e in ENVS if not a.env or e == a.env]
    else:
        ts = [task("q4", arm, e, "smoke", [""], -7, a.tag) for arm in CKPTS for e in ENVS if not a.env or e == a.env]
    for t in ts:
        p = Q / "todo" / f"{t['id']}.json"
        if any((Q / d / p.name).exists() for d in ("todo", "running", "done")):
            print(f"exists: {t['id']}")
            continue
        print(json.dumps(t) if a.dry_run else f"queued {t['id']}")
        if not a.dry_run:
            p.write_text(json.dumps(t, indent=1))


if __name__ == "__main__":
    main()
