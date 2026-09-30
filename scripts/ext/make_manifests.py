"""Fixed item manifests for the simulator-free external environments (engineering line 2).

Written once, before any model run; selection is by sha256(salt + item id) order only (never by any model's
outcome). Re-running reproduces the same files bit for bit; the script refuses to overwrite a manifest whose
content would change.

  BFCL v3 multi-turn (bfcl-eval 2026.3.23; its data files are named BFCL_v4_multi_turn_*.json, the v3 multi-turn
  categories as maintained in the current release): categories base, miss_param, miss_func, long_context
  (200 items each). Per category: dev = first 3 ids in hash order (adapter checks only), smoke = next 10,
  eval = all 200 minus dev (197; smoke is a subset of eval).
  ALFWorld text (alfworld 0.4.2 TextWorld engine, data json_2.1.1 + tw-pddl 2.1.2): dev = 1 game per task type
  from valid_seen (eval_in_distribution, 140 games); eval = the official eval_out_of_distribution split
  (valid_unseen, 134 games); smoke = 2 games per task type from eval in hash order (12).

usage: python3 scripts/ext/make_manifests.py
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
WORK = Path("/data/ziyangs/cloq_work")
BFCL_PKG = WORK / "envs/bfcl/lib/python3.12/site-packages/bfcl_eval"
ALF_DATA = WORK / "data/alfworld"
SALT = "cloq-ext-v1"
BFCL_CATS = ["base", "miss_param", "miss_func", "long_context"]
TASK_TYPES = {1: "pick_and_place_simple", 2: "look_at_obj_in_light", 3: "pick_clean_then_place_in_recep",
              4: "pick_heat_then_place_in_recep", 5: "pick_cool_then_place_in_recep", 6: "pick_two_obj_and_place"}


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha_tree(files: list[Path], base: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(str(f.relative_to(base)).encode())
        h.update(bytes.fromhex(sha_file(f)))
    return h.hexdigest()


def hkey(x: str) -> str:
    return hashlib.sha256((SALT + ":" + x).encode()).hexdigest()


def write(path: Path, obj: dict) -> None:
    text = json.dumps(obj, indent=1) + "\n"
    if path.exists() and path.read_text() != text:
        raise SystemExit(f"{path} exists with different content; manifests are frozen (write a new version instead)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    print(f"wrote {path} sha256={hashlib.sha256(text.encode()).hexdigest()[:16]}")


def bfcl() -> None:
    data = BFCL_PKG / "data"
    cats, files = {}, {}
    for c in BFCL_CATS:
        name = f"BFCL_v4_multi_turn_{c}.json"
        ids = [json.loads(l)["id"] for l in open(data / name) if l.strip()]
        gt = [json.loads(l)["id"] for l in open(data / "possible_answer" / name) if l.strip()]
        assert ids == gt and len(ids) == 200, (c, len(ids), len(gt))
        order = sorted(ids, key=hkey)
        dev = order[:3]
        cats[c] = {"test_category": f"multi_turn_{c}", "n_total": len(ids), "dev": dev, "smoke": order[3:13],
                   "eval": [i for i in ids if i not in dev]}
        files[name] = sha_file(data / name)
        files["possible_answer/" + name] = sha_file(data / "possible_answer" / name)
    docs = sorted((data / "multi_turn_func_doc").glob("*.json"))
    src = sorted((BFCL_PKG / "eval_checker/multi_turn_eval/func_source_code").glob("*.py"))
    write(ROOT / "manifests/bfcl/bfcl_mt_v1.json", {
        "manifest": "bfcl_mt_v1", "benchmark": "BFCL v3 multi-turn",
        "blog": "https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html",
        "package": {"name": "bfcl-eval", "version": "2026.3.23",
                    "wheel_sha256": "3bb6dfa5f0c68ad403c9ec50b00db2bb3b4cc9b38ab1ff33f48fe30d853d3a0a",
                    "env": str(WORK / "envs/bfcl")},
        "data_sha256": files, "func_doc_tree_sha256": sha_tree(docs, data), "backend_source_tree_sha256": sha_tree(src, BFCL_PKG),
        "selection": {"rule": "per category, ids sorted by sha256('%s:' + id); dev = first 3; smoke = next 10; eval = all minus dev "
                              "(smoke is a subset of eval). No model outcome used." % SALT, "salt": SALT},
        "inference": "BFCL's own BaseHandler.inference_multi_turn_FC loop (FC mode, OpenAI-compatible chat completions to the "
                     "CLOQ vLLM agent server; MAXIMUM_STEP_LIMIT 20 per turn; miss_func holdout functions injected by the loop)",
        "evaluator": "bfcl_eval.eval_checker.eval_runner._evaluate_single_multi_turn_entry (the per-entry body of the official "
                     "multi_turn_runner: decode_execute + multi_turn_checker state/response checks), unchanged",
        "categories": cats,
        "frozen_before_model_runs": True,
    })


def alfworld() -> None:
    def games(split: str) -> list[str]:
        out = []  # same filter as alfworld.agents.environment.alfred_tw_env.AlfredTWEnv.collect_game_files
        for root, _, fs in os.walk(ALF_DATA / "json_2.1.1" / split, topdown=False):
            if "traj_data.json" not in fs or "movable" in root or "Sliced" in root:
                continue
            tt = json.load(open(Path(root, "traj_data.json")))["task_type"]
            g = Path(root, "game.tw-pddl")
            if tt not in TASK_TYPES.values() or not g.exists():
                continue
            gd = json.load(open(g))
            if not gd.get("solvable"):
                continue
            out.append(str(g.relative_to(ALF_DATA)))
        return sorted(out)

    def ttype(g: str) -> str:
        return g.split("/")[2].split("-")[0]

    seen, unseen = games("valid_seen"), games("valid_unseen")
    assert len(seen) == 140 and len(unseen) == 134, (len(seen), len(unseen))
    dev = [sorted([g for g in seen if ttype(g) == t], key=hkey)[0] for t in TASK_TYPES.values()]
    smoke = [g for t in TASK_TYPES.values() for g in sorted([g for g in unseen if ttype(g) == t], key=hkey)[:2]]
    per_type = {t: sum(ttype(g) == t for g in unseen) for t in TASK_TYPES.values()}
    write(ROOT / "manifests/alfworld/alfworld_text_v1.json", {
        "manifest": "alfworld_text_v1", "benchmark": "ALFWorld (TextWorld text engine)",
        "repo": "https://github.com/alfworld/alfworld",
        "package": {"alfworld": "0.4.2", "alfworld_wheel_sha256": "29affbea28f6041d1e8516ed3efd6b55becd52cfca4fb9dd5c75b9d6b8a56c2f",
                    "textworld": "1.7.0", "textworld_wheel_sha256": "ca7486cff540c4d90865c54a3465e948c2790357aa78ad64de4406387854cbc8",
                    "env": str(WORK / "envs/alfworld")},
        "data": {"dir": str(ALF_DATA), "download_zip_sha256": {
            "json_2.1.1_json.zip": "25171f16e20ad7b048c47275c45b0babf3aa1cbab29cec97387922350a9844bc",
            "json_2.1.1_pddl.zip": "913942ebed06659ea0da2f8122512d98bc6add30d84961ca803132d8fbcad585",
            "json_2.1.2_tw-pddl.zip": "eea90499df27b9cb3147d1d1927264146d38194b575e25f70a82875545742dcb"},
            "logic_sha256": {n: sha_file(ALF_DATA / "logic" / n) for n in ("alfred.pddl", "alfred.twl2")},
            "eval_games_tree_sha256": sha_tree([ALF_DATA / g for g in unseen], ALF_DATA),
            "dev_games_tree_sha256": sha_tree([ALF_DATA / g for g in dev], ALF_DATA)},
        "splits": {"eval": "valid_unseen = AlfredTWEnv eval_out_of_distribution (official unseen split), task_types 1-6, all 134 games",
                   "dev": "valid_seen = eval_in_distribution; 1 game per task type (adapter checks only)"},
        "selection": {"rule": "dev: per task type the first valid_seen game in sha256('%s:' + path) order; smoke: per task type the "
                              "first 2 valid_unseen games in the same order. No model outcome used." % SALT, "salt": SALT},
        "evaluator": "TextWorld infos['won'] (the game's PDDL goal condition) from the official alfworld TW environment, unchanged",
        "eval_per_task_type": per_type,
        "dev": dev, "smoke": smoke, "eval": unseen,
        "frozen_before_model_runs": True,
    })


if __name__ == "__main__":
    bfcl()
    alfworld()
