"""Integrity checks before any result is reported (plan section 23).

usage: python -m cloq.integrity --bf16-run bf16 --arm-runs static=static_eval fp_traj=fp_traj_eval cloq=cloq_eval \
          --calib static=manifests/calib_static.json fp_traj=... cloq=... --split manifests/task_split_v0.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cloq import config as C


def check(bf16_run: str, arm_runs: dict[str, str], calibs: dict[str, Path], split_path: Path) -> dict:
    split = json.load(open(split_path))
    domains = list(split["domains"].keys())
    problems: list[str] = []
    info: dict = {}

    runs = {"bf16": bf16_run, **arm_runs}
    ref = None
    for arm, run_id in runs.items():
        for domain in domains:
            rd = C.RUNS_DIR / run_id / domain
            st = json.load(open(rd / "status.json"))
            if st.get("status") != "completed":
                problems.append(f"{arm}/{domain}: status {st.get('status')}")
            cfg = json.load(open(rd / "config.json"))
            tm = json.load(open(rd / "task_manifest.json"))
            mj = json.load(open(rd / "model.json"))
            key = {
                "model": (mj["hf_id"], mj["revision"]),
                "gen": json.dumps(cfg["frozen"]["generation_agent"], sort_keys=True),
                "user": json.dumps(cfg["frozen"]["generation_user"], sort_keys=True),
                "ctx": json.dumps(cfg["frozen"]["context_policy"], sort_keys=True),
                "bench": json.dumps({k: cfg["frozen"]["benchmark"][k] for k in ["max_steps", "max_errors", "seed", "num_trials"]}, sort_keys=True),
                "tau2": tm.get("tau2_commit"),
                "user_llm_args": json.dumps(cfg["tau2_run_config"]["llm_args_user"], sort_keys=True),
            }
            if ref is None:
                ref = key
            else:
                for k, v in key.items():
                    if ref[k] != v:
                        problems.append(f"{arm}/{domain}: {k} differs from bf16 ({v} vs {ref[k]})")
            # evaluation task ids identical across arms
            eval_ids = split["domains"][domain]["evaluation"]
            if arm != "bf16":
                if sorted(tm["task_ids"]) != sorted(eval_ids):
                    problems.append(f"{arm}/{domain}: task ids != frozen evaluation set")
            # decision-level input identity check (server ids == local rendering)
            n = 0; bad = 0
            with open(rd / "decisions.jsonl", encoding="utf-8") as f:
                for line in f:
                    d = json.loads(line); n += 1
                    if d.get("prompt_ids_match_local") is False:
                        bad += 1
            if bad:
                problems.append(f"{arm}/{domain}: {bad}/{n} decisions where server prompt ids != local rendering")
            info[f"{arm}/{domain}"] = {"n_decisions": n, "status": st.get("status")}

    # calibration manifests: disjointness, budget, source checkpoint
    budget = int(C.FROZEN["calibration"]["token_budget"]); tol = float(C.FROZEN["calibration"]["token_budget_tolerance"])
    for name, path in calibs.items():
        man = json.load(open(path))
        if abs(man["total_tokens"] - budget) > budget * tol:
            problems.append(f"calib {name}: total tokens {man['total_tokens']} outside {budget}±{tol*100:.0f}%")
        for c in man["contexts"]:
            if c["task_id"] in set(split["domains"][c["domain"]]["evaluation"]):
                problems.append(f"calib {name}: evaluation task {c['domain']}/{c['task_id']} leaked into calibration")
                break
        info[f"calib/{name}"] = {k: man[k] for k in ["n_contexts", "total_tokens", "median_context_tokens", "tokens_by_source"]}
    # checkpoints quantized from the BF16 source with identical quantizer settings
    qsettings = None
    for arm, run_id in arm_runs.items():
        for domain in domains:
            cfg = json.load(open(C.RUNS_DIR / run_id / domain / "config.json"))
            ck = cfg.get("checkpoint")
            if not ck:
                problems.append(f"{arm}/{domain}: no checkpoint recorded"); continue
            qj = json.load(open(Path(ck) / "quantization.json"))
            if qj.get("source_revision") != C.MODEL_REVISION or qj.get("source_model") != C.MODEL_ID:
                problems.append(f"{arm}: checkpoint not quantized from the frozen BF16 source")
            s = json.dumps({k: qj.get(k) for k in ["method", "wbits", "group_size", "sym", "percdamp", "blocksize", "act_order", "true_sequential"]}, sort_keys=True)
            if qsettings is None:
                qsettings = s
            elif s != qsettings:
                problems.append(f"{arm}: quantizer settings differ: {s} vs {qsettings}")
            info[f"ckpt/{arm}"] = {"calibration_manifest": qj.get("calibration_manifest"), "n_tokens": (qj.get("stats") or {}).get("n_tokens")}
    out = {"ok": not problems, "problems": problems, "info": info}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bf16-run", default="bf16")
    ap.add_argument("--arm-runs", nargs="+", required=True)
    ap.add_argument("--calib", nargs="+", required=True)
    ap.add_argument("--split", default=str(C.MANIFEST_DIR / "task_split_v0.json"))
    ap.add_argument("--out", default=str(C.PROJECT_ROOT / "analysis" / "integrity.json"))
    a = ap.parse_args()
    res = check(a.bf16_run, dict(kv.split("=", 1) for kv in a.arm_runs), {k: Path(v) for k, v in (kv.split("=", 1) for kv in a.calib)}, Path(a.split))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    if not res["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
