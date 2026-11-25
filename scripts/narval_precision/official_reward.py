"""Re-score the admitted CLOQ W4 development panel with two reward definitions."""

import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path

CELLS = {(m, c) for m in ("q4", "q8") for c in ("gptq_w4_d1", "awq_w4")}
MODES = {"action": "BQ", "continuation": "QB", "joint": "BB"}


def load_upstream(repo, data):
    source = repo / "analysis/fork/analyze_dev.py"
    spec = importlib.util.spec_from_file_location("cloq_analyze_dev", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = data
    module.SPLITS = repo / "manifests/fork/splits_v1.json"
    return module


def read(path):
    return json.loads(path.read_text())


def unit_id(unit):
    return unit["run_id"], unit["domain"], unit["task"]


def score_official(domain, record):
    value = record.get("official_reward")
    return int(value) if value in (0, 1) else -1


def describe(analysis, units, draws):
    blocks = defaultdict(set)
    for unit in units:
        blocks[unit["task"]].add(unit["block"])
    boot = analysis.Boot(sorted(blocks), {task: sorted(bs) for task, bs in blocks.items()}, B=draws)
    result = {}
    for mode, arm in MODES.items():
        def values(y):
            return {
                "rescue": int(y[arm] > y["QQ"]),
                "damage": int(y[arm] < y["QQ"]),
                "net": y[arm] - y["QQ"],
            }
        result[mode] = {}
        for scope in ("all", "divergent"):
            records = []
            for unit in units:
                if scope == "divergent" and not unit["div"]:
                    continue
                db = values(unit["Y"])
                official = values(unit["official"])
                effects = {}
                for metric in db:
                    effects[f"db_{metric}"] = db[metric]
                    effects[f"official_{metric}"] = official[metric]
                    effects[f"delta_{metric}"] = official[metric] - db[metric]
                records.append({**unit, "E": effects})
            if not records:
                continue
            estimator = boot.task_mean if scope == "all" else boot.ratio
            estimates = {}
            for metric in records[0]["E"]:
                estimate, sampled = estimator(*boot.arrays(records, metric))
                estimates[metric] = analysis.summarise(estimate, sampled, boot=boot)
            result[mode][scope] = {"n_units": len(records), "estimates_pp": estimates}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("repo", "data", "snapshot", "out"):
        parser.add_argument(f"--{key}", required=True, type=Path)
    parser.add_argument("--draws", type=int, default=2000)
    args = parser.parse_args()
    analysis = load_upstream(args.repo.resolve(), args.data.resolve())
    snapshot = read(args.snapshot)
    db_score = analysis.success
    db_cache = {}
    eligible = []
    hashes = {}
    for directory in analysis.discover(False):
        rel = directory.relative_to(analysis.ROOT).parts
        if rel[:3] not in (
            ("analysis", "fork", "dev"), ("analysis", "fork", "repair")
        ):
            continue
        primary = analysis.load_dir(directory, snapshot, db_cache)
        if primary["quarantined"]:
            continue
        analysis.success = score_official
        try:
            official = analysis.load_dir(directory, snapshot, db_cache)
        finally:
            analysis.success = db_score
        hashes.update(primary["files"])
        if len(primary["units"]) != len(official["units"]):
            raise ValueError(f"Inconsistent scoring coverage in {directory}")
        for db, other in zip(primary["units"], official["units"]):
            if unit_id(db) != unit_id(other):
                raise ValueError(f"Inconsistent scoring order in {directory}")
            if (db["model"], db["cell"]) not in CELLS or db["domain"] not in analysis.PANEL_DOMAINS:
                continue
            if "excluded" not in db:
                scores = other.get("Y", {})
                if scores and all(value in (0, 1) for value in scores.values()):
                    db["official"] = scores
                else:
                    db["excluded"] = "invalid or missing official reward"
            eligible.append(db)

    split = json.loads(analysis.SPLITS.read_text())["splits"]["dev"]["tasks"]
    eligible = [u for u in eligible if analysis.unit_key(u)[1] in set(map(str, split[u["domain"]]))]
    eligible, duplicates = analysis.dedupe_units(eligible)
    incomplete = analysis.mark_incomplete_blocks(eligible, "dev")
    partial = analysis.mark_partial_panel_blocks(eligible, "dev")
    excluded = Counter(u["excluded"] for u in eligible if "excluded" in u)
    valid = [u for u in eligible if "excluded" not in u]
    groups = {}
    for model, cell in sorted(CELLS):
        units = [u for u in valid if (u["model"], u["cell"]) == (model, cell)]
        if not units:
            continue
        groups[f"{model}:{cell}"] = {
            "overall": describe(analysis, units, args.draws),
            "by_domain": {
                domain: describe(analysis, [u for u in units if u["domain"] == domain], args.draws)
                for domain in analysis.PANEL_DOMAINS
            },
            "blocks": sorted({u["block"] for u in units}),
            "db_units_digest": analysis.units_digest(units),
            "official_units_digest": analysis.units_digest([{**u, "Y": u["official"]} for u in units]),
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "snapshot_sha256": analysis.sha256(args.snapshot),
        "split_sha256": analysis.sha256(analysis.SPLITS),
        "input_file_hashes": hashes,
        "duplicate_rows": duplicates,
        "candidate_units": len(eligible),
        "included_units": len(valid),
        "excluded": dict(excluded),
        "incomplete_blocks": incomplete,
        "partial_panels": partial,
        "groups": groups,
    }
    temporary = args.out.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temporary.replace(args.out)
    print(f"{len(valid)} paired units across {len(groups)}/{len(CELLS)} W4 configurations; {args.out}")
    if len(groups) != len(CELLS):
        raise SystemExit("Incomplete W4 coverage; see exclusions and group coverage in the report.")


if __name__ == "__main__":
    main()
