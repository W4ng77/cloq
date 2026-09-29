"""Deterministic telecom dev split for X3 (docs/insights/PLAN_iter3.md).

Rule: start from tau2's official telecom `base` split (114 tasks, split_tasks.json), stratify by
issue type (mms_issue / mobile_data_issue / service_issue) x persona (None / Easy / Hard), rank the
tasks of every stratum by sha256("cloq-telecom-dev-v1|" + task_id) and keep the first
round(n_stratum * 80 / 114). The remaining base tasks are the holdout. `smoke` = the 5 dev tasks
with the smallest hash (any stratum). No model output is used, so the split is fixed before any run.

usage: python scripts/a6000/make_telecom_split.py [--out manifests/telecom/dev_v1.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from cloq import config as C

SALT = "cloq-telecom-dev-v1|"
TARGET = 80


def h(tid: str) -> str:
    return hashlib.sha256((SALT + tid).encode()).hexdigest()


def stratum(tid: str) -> tuple[str, str]:
    return tid.split("]")[0].lstrip("["), tid.split("[PERSONA:")[1].rstrip("]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(C.MANIFEST_DIR / "telecom" / "dev_v1.json"))
    args = ap.parse_args()
    ddir = C.TAU2_DIR / "data/tau2/domains/telecom"
    base = json.load(open(ddir / "split_tasks.json"))["base"]
    tasks = {t["id"]: t for t in json.load(open(ddir / "tasks.json"))}
    groups = defaultdict(list)
    for t in base:
        groups[stratum(t)].append(t)
    dev = []
    for k in sorted(groups):
        ids = sorted(groups[k], key=h)
        dev += ids[: round(len(ids) * TARGET / len(base))]
    dev = sorted(dev, key=h)
    hold = sorted(set(base) - set(dev), key=h)
    n_faults = lambda t: len(t.split("]")[1].split("[")[0].split("|"))
    out = {
        "telecom": dev,
        "rule": __doc__.strip().split("\n\n")[1],
        "source": "third_party/tau2-bench/data/tau2/domains/telecom/split_tasks.json:base",
        "salt": SALT, "n_base": len(base), "n_dev": len(dev),
        "holdout": hold, "smoke": dev[:5],
        "strata_dev": {"|".join(k): sum(stratum(t) == k for t in dev) for k in sorted(groups)},
        "reward_basis_dev": dict(Counter("+".join(tasks[t]["evaluation_criteria"]["reward_basis"]) for t in dev)),
        "n_faults_dev": dict(sorted(Counter(n_faults(t) for t in dev).items())),
        "tau2_commit": __import__("subprocess").check_output(["git", "-C", str(C.TAU2_DIR), "rev-parse", "HEAD"], text=True).strip(),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    Path(args.out).with_name("smoke_v1.json").write_text(json.dumps({"telecom": out["smoke"]}, indent=1))
    print(len(dev), len(hold), out["strata_dev"], out["reward_basis_dev"], out["n_faults_dev"])


if __name__ == "__main__":
    main()
