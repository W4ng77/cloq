"""LiveCodeBench problem store and the deterministic benchmark selection rule.

Source: HF dataset livecodebench/code_generation_lite (license field "cc"; problems from LeetCode/AtCoder/Codeforces
with LCB's public examples and hidden tests), pinned revision below. Only the release_v5 and release_v6 increments
(test5.jsonl, test6.jsonl) are downloaded.

Selection rule (recorded in the manifest): every problem whose difficulty is in the chosen set in the v5 and v6
increments, i.e. contest dates 2024-09-22 .. 2025-04-06 (release_v6 minus release_v4). Main set (decided 2026-09-29
after the hard-only smoke gave q4 pass@end 1/20): difficulty in {medium, hard} -> manifests/code/lcb_mh_v5v6.json;
the earlier hard-only set (154 problems) stays as manifests/code/lcb_hard_v5v6.json. No filtering on model
behaviour. Order = sha256 of
question_id (a fixed pseudo-random order, so a prefix of the manifest is an unbiased subsample, e.g. the 20-problem
smoke set). Problems are stored one JSON file per problem (hidden tests stay in LCB's compressed encoding) under
CLOQ_CODE_DATA (default /data/ziyangs/cloq_work/data/lcb_code).

usage: python -m cloq_code.data build --src <dir with test5.jsonl test6.jsonl> --manifest manifests/code/lcb_mh_v5v6.json [--difficulties medium hard]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pickle
import zlib
from functools import lru_cache
from pathlib import Path

HF_REPO = "livecodebench/code_generation_lite"
HF_REVISION = "0fe84c3912ea0c4d4a78037083943e8f0c4dd505"
SOURCE_FILES = ["test5.jsonl", "test6.jsonl"]  # release_v5 \ v4 and release_v6 \ v5
DATA_DIR = Path(os.environ.get("CLOQ_CODE_DATA", "/data/ziyangs/cloq_work/data/lcb_code"))
RULE = ("all problems with difficulty in {diffs} in LiveCodeBench code_generation_lite release_v5 and release_v6 "
        "increments (test5.jsonl + test6.jsonl at revision %s); order = sha256(question_id) ascending; no filtering "
        "on any model's behaviour").replace("%s", HF_REVISION)


# Pre-registered deviation from configs/frozen_v0.json generation_agent (decided 2026-09-29, before any main run):
GEN_DEVIATION = {"max_tokens": 4096, "frozen_max_tokens": 1024,
                 "reason": "hard-only smoke (q4): 45% of replies hit 1024 tokens and 14/20 first replies had no closed "
                           "code block; every other generation setting is the frozen greedy one"}


def order_key(qid: str) -> str:
    return hashlib.sha256(qid.encode()).hexdigest()


def decode_private(s: str) -> list[dict]:
    try:
        return json.loads(s)
    except Exception:
        return json.loads(pickle.loads(zlib.decompress(base64.b64decode(s.encode("utf-8")))))


def build(src: Path, manifest: Path, difficulties: list[str]) -> dict:
    out_dir = DATA_DIR / "problems"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for fn in SOURCE_FILES:
        with open(src / fn) as f:
            for line in f:
                d = json.loads(line)
                if d["difficulty"] not in difficulties:
                    continue
                qid = d["question_id"]
                (out_dir / f"{qid}.json").write_text(line)
                pub = json.loads(d["public_test_cases"])
                priv = decode_private(d["private_test_cases"])
                rows.append({
                    "task_id": qid, "difficulty": d["difficulty"], "platform": d["platform"], "contest_id": d["contest_id"],
                    "contest_date": d["contest_date"], "title": d["question_title"],
                    "testtype": pub[0]["testtype"] if pub else None,
                    "n_public": len(pub), "n_hidden": len(priv),
                    "sha256": hashlib.sha256(line.encode()).hexdigest(), "source_file": fn,
                })
    rows.sort(key=lambda r: order_key(r["task_id"]))
    man = {
        "benchmark": "cloq_code / LiveCodeBench %s (v5+v6 increments)" % "+".join(difficulties),
        "difficulties": difficulties,
        "n_by_difficulty": {x: sum(r["difficulty"] == x for r in rows) for x in difficulties},
        "hf_repo": HF_REPO, "hf_revision": HF_REVISION, "source_files": SOURCE_FILES,
        "selection_rule": RULE.replace("{diffs}", "{" + ", ".join(difficulties) + "}"),
        "generation_deviation": GEN_DEVIATION,
        "n_tasks": len(rows), "task_ids": [r["task_id"] for r in rows], "problems": rows,
        "date_range": [min(r["contest_date"] for r in rows), max(r["contest_date"] for r in rows)],
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(man, indent=1))
    return man


@lru_cache(maxsize=256)
def _raw(qid: str) -> dict:
    return json.loads((DATA_DIR / "problems" / f"{qid}.json").read_text())


def load_problem(qid: str, with_hidden: bool = False) -> dict:
    d = _raw(qid)
    meta = json.loads(d.get("metadata") or "{}")
    p = {
        "task_id": qid, "title": d["question_title"], "content": d["question_content"], "platform": d["platform"],
        "contest_date": d["contest_date"], "difficulty": d["difficulty"], "starter_code": d.get("starter_code") or "",
        "func_name": meta.get("func_name"), "public_tests": json.loads(d["public_test_cases"]),
    }
    p["testtype"] = "functional" if p["starter_code"].strip() else "stdin"
    if with_hidden:
        p["hidden_tests"] = decode_private(d["private_test_cases"])
    return p


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--src", required=True)
    b.add_argument("--manifest", required=True)
    b.add_argument("--difficulties", nargs="+", default=["medium", "hard"])
    a = ap.parse_args()
    man = build(Path(a.src), Path(a.manifest), a.difficulties)
    print(json.dumps({k: v for k, v in man.items() if k not in ("problems", "task_ids")}, indent=1))


if __name__ == "__main__":
    main()
