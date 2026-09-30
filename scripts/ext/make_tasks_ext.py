"""Queue tasks for the simulator-free external environments (worker.py eval tasks with an "env" field).

  dev   : q4 BF16 on the manifest dev items, two identical runs (r1, r2) in one task -> deterministic re-run check
  smoke : q4 BF16 and q4 GPTQ-W4 d1 (calibration c1, the a6k2 spec) on the fixed smoke subsets, priority -7
  eval  : q4 and q8 x {BF16, GPTQ-W4 d1, AWQ-W4 d1} (calibration c1, the a6k2 specs) on the full eval subsets, priority -9
          (simulator-free backlog behind the fork line; frozen served context, overflow scored as failure, W36-ext)

usage: python3 scripts/ext/make_tasks_ext.py {dev|smoke} [--dry-run]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

Q = Path("/data/ziyangs/cloq_work/queue")
CKPTS = {"bf16": {"kind": "bf16"},
         "gptq_w4_d1": {"kind": "gptq", "wbits": 4, "calib": "manifests/a6k2/{model}/calib_fp_traj_c1.json"},
         "awq_w4_d1": {"kind": "awq", "wbits": 4, "calib": "manifests/a6k2/{model}/calib_fp_traj_c1.json"}}
ENVS = {"bfcl": ("manifests/bfcl/bfcl_mt_v1.json", ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"]),
        "alfworld": ("manifests/alfworld/alfworld_text_v1.json", ["alfworld"])}


def task(model: str, arm: str, env: str, subset: str, reps: list[str], priority: int, tag: str = "") -> dict:
    man, domains = ENVS[env]
    tid = f"ext_{model}_{arm}_{env}_{subset}{tag}"
    ck = {k: (v.format(model=model) if isinstance(v, str) else v) for k, v in CKPTS[arm].items()}
    return {"id": tid, "kind": "eval", "env": env, "model": model, "arm": ck["kind"],
            "ckpt": ck, "domains": domains, "priority": priority,
            "runs": [{"run_id": f"{tid}{('_' + r) if r else ''}", "task_file": man, "subset": subset} for r in reps]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "smoke", "eval"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--env", default="", help="only this env")
    ap.add_argument("--tag", default="", help="task/run id suffix, e.g. _p2 for a prompt revision on dev")
    a = ap.parse_args()
    if a.mode == "dev":
        ts = [task("q4", "bf16", e, "dev", ["r1", "r2"], -8, a.tag) for e in ENVS if not a.env or e == a.env]
    elif a.mode == "smoke":
        ts = [task("q4", arm, e, "smoke", [""], -7, a.tag) for arm in ("bf16", "gptq_w4_d1") for e in ENVS if not a.env or e == a.env]
    else:
        ts = [task(m, arm, e, "eval", [""], -9, a.tag) for m in ("q4", "q8") for arm in CKPTS for e in ENVS
              if not a.env or e == a.env]
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
