"""Run one arm of the code loop on a set of LiveCodeBench problems (the cloq.run_arm analogue).

usage:
  python -m cloq_code.run_code --run-id code_q4_bf16 --arm bf16 \
      [--task-file manifests/code/lcb_emh_v5v6.json] [--limit 20 | --task-ids abc374_f ...] \
      [--agent-base http://127.0.0.1:8001/v1] [--max-turns 8] [--max-concurrency 8]

Artifacts under runs/<run_id>/code/ (same names and record conventions as cloq.run_arm):
  config.json, environment.json, model.json, task_manifest.json,
  decisions.jsonl (one record per model call: prompt/completion token ids, token_logprobs, token_margins, ...),
  trajectory.jsonl (one line per problem: outcome, termination_reason, messages, per-turn success),
  metrics.json, status.json
Env as for run_arm: CLOQ_MODEL_ID/REVISION, CLOQ_CHAT_TEMPLATE_KWARGS, CLOQ_TOP_LOGPROBS (5 for margins),
CLOQ_MAX_PROMPT_TOKENS, CLOQ_PROMPT_NONCE; sandbox: CLOQ_CODE_CPU_LIMIT, CLOQ_CODE_SANDBOX_PAR, CLOQ_CODE_TMP.
Resumable: problems already in trajectory.jsonl are skipped; decisions of an interrupted attempt are dropped (W8).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from cloq import config as C
from cloq_code import data as D
from cloq_code import loop as L
from cloq_code import sandbox as S

DOMAIN = "code"


def _git_rev(path: Path) -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def _pkg_versions() -> dict:
    import importlib.metadata as md

    out = {}
    for p in ["vllm", "torch", "transformers", "tokenizers", "numpy"]:
        try:
            out[p] = md.version(p)
        except Exception:
            out[p] = None
    return out


def served_model_info(api_base: str) -> dict:
    import urllib.request

    try:
        with urllib.request.urlopen(api_base + "/models", timeout=10) as r:
            return json.load(r)
    except Exception as e:  # pragma: no cover
        return {"error": repr(e)}


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


def summarize(run_dir: Path) -> dict:
    trajs = read_jsonl(run_dir / "trajectory.jsonl")
    decs = read_jsonl(run_dir / "decisions.jsonl")
    n = len(trajs)
    nd = len(decs)

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return float(np.mean(xs)) if xs else None

    max_t = max((t["n_turns"] for t in trajs), default=0)
    # pass@turn t: success if the problem was solved by its t-th submission (a solved episode stops, so carry forward)
    pass_at_turn = []
    for k in range(1, max_t + 1):
        pass_at_turn.append(mean([float(any(t["turn_success"][:k])) for t in trajs]))
    changed = [t["turn1_success"] != t["success"] for t in trajs]
    per_task = [{
        "task_id": t["task_id"], "success": t["success"], "db_match": t["success"], "reward": t["reward"],
        "turn1_success": t["turn1_success"], "n_decisions": t["n_turns"], "termination_reason": t["termination_reason"],
        "premature": t["termination_reason"] in ("infrastructure_error", "context_limit"),
        "final_public_passed": t["final_public_passed"], "duration": t["duration"], "platform": t["problem"]["platform"],
        "difficulty": t["problem"]["difficulty"],
    } for t in trajs]
    return {
        "benchmark": "cloq_code/" + json.load(open(run_dir / "task_manifest.json"))["task_file"].rsplit("/", 1)[-1].removesuffix(".json") if (run_dir / "task_manifest.json").exists() else "cloq_code",
        "n_tasks": n,
        "pass_rate": mean([t["success"] for t in trajs]),
        "reward_mean": mean([t["reward"] for t in trajs]),
        "db_match_rate": mean([t["success"] for t in trajs]),  # alias so tau2-keyed analyses read the primary endpoint
        "turn1_pass_rate": mean([t["turn1_success"] for t in trajs]),
        "feedback_gain": (mean([t["success"] for t in trajs]) or 0) - (mean([t["turn1_success"] for t in trajs]) or 0),
        "feedback_changed_outcome_rate": mean(changed),
        "public_pass_rate": mean([t["final_public_passed"] for t in trajs]),
        "public_pass_hidden_fail_rate": mean([t["final_public_passed"] and not t["final_hidden_passed"] for t in trajs]),
        "pass_at_turn": pass_at_turn,
        "n_decisions_total": nd,
        "mean_decisions": mean([t["n_turns"] for t in trajs]),
        "mean_turns": mean([t["n_turns"] for t in trajs]),
        "no_code_rate": (sum(1 for d in decs if d.get("parser_error")) / nd) if nd else None,
        "parser_error_rate": (sum(1 for d in decs if d.get("parser_error")) / nd) if nd else None,
        "finish_length_rate": (sum(1 for d in decs if d.get("finish_reason") == "length") / nd) if nd else None,
        "premature_rate": mean([r["premature"] for r in per_task]),
        "termination_reasons": dict(Counter(t["termination_reason"] for t in trajs)),
        "n_wall_timeouts": sum(t.get("n_wall_timeouts", 0) for t in trajs),
        "mean_seconds_per_task": mean([t["duration"] for t in trajs]),
        "mean_prompt_tokens": mean([d.get("n_prompt_tokens") for d in decs]),
        "max_prompt_tokens": max((d.get("n_prompt_tokens") or 0 for d in decs), default=None),
        "prompt_ids_from_server_frac": (sum(1 for d in decs if d.get("prompt_ids_from_server")) / nd) if nd else None,
        "prompt_ids_match_local_frac": (sum(1 for d in decs if d.get("prompt_ids_match_local")) / nd) if nd else None,
        "mean_completion_tokens": mean([d.get("n_completion_tokens") for d in decs]),
        "unclosed_at_length_rate": (sum(1 for d in decs if d.get("unclosed_code_block")) / nd) if nd else None,
        "multi_block_rate": (sum(1 for d in decs if (d.get("n_code_blocks") or 0) > 1) / nd) if nd else None,
        "max_tokens": L.MAX_TOKENS, "generation_deviation": D.GEN_DEVIATION,
        "pass_rate_by_difficulty": {x: mean([t["success"] for t in trajs if t["problem"]["difficulty"] == x])
                                    for x in sorted({t["problem"]["difficulty"] for t in trajs})},
        "per_task": per_task,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--task-file", default=str(C.PROJECT_ROOT / "manifests/code/lcb_emh_v5v6.json"))
    ap.add_argument("--task-ids", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=None, help="first N problems of the manifest order")
    ap.add_argument("--agent-base", default=C.AGENT_API_BASE)
    ap.add_argument("--max-turns", type=int, default=L.MAX_TURNS_DEFAULT)
    ap.add_argument("--max-concurrency", type=int, default=int(C.FROZEN["serving"]["max_concurrency"]))
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    run_dir = C.RUNS_DIR / args.run_id / DOMAIN
    run_dir.mkdir(parents=True, exist_ok=True)
    status_path = run_dir / "status.json"
    if status_path.exists() and json.load(open(status_path)).get("status") == "completed":
        print(f"{run_dir} already completed; skipping")
        return

    man = json.load(open(args.task_file))
    task_ids = args.task_ids or (man["task_ids"] if isinstance(man, dict) else man)
    if args.limit:
        task_ids = task_ids[: args.limit]
    task_ids = [str(t) for t in task_ids]
    problems = [D.load_problem(t) for t in task_ids]

    run_meta = {"run_id": args.run_id, "arm": args.arm, "domain": DOMAIN}
    sandbox_cfg = {"cpu_limit_s": S.CPU_LIMIT_S, "wall_limit_s": S.WALL_LIMIT_S, "mem_limit_bytes": S.MEM_LIMIT_B,
                   "python": S.PYTHON, "hashseed": 0, "random_seed": 0, "float_tol": 1e-6}
    (run_dir / "config.json").write_text(json.dumps({
        "run_id": args.run_id, "arm": args.arm, "domain": DOMAIN, "note": args.note, "checkpoint": args.checkpoint,
        "frozen": C.FROZEN, "benchmark": "cloq_code: LiveCodeBench v5+v6 increments, public-test feedback loop",
        "max_turns": args.max_turns, "max_tokens": L.MAX_TOKENS, "prompt_limit": L.PROMPT_LIMIT,
        "generation_deviation": D.GEN_DEVIATION, "max_concurrency": args.max_concurrency, "sandbox": sandbox_cfg,
        "request_body_template": {k: v for k, v in L.request_body([]).items() if k != "messages"},
        "system_prompt": L.system_prompt(args.max_turns),
        "task_file": args.task_file, "selection_rule": man.get("selection_rule") if isinstance(man, dict) else None,
    }, indent=2))
    (run_dir / "environment.json").write_text(json.dumps({
        "hostname": platform.node(), "platform": platform.platform(), "python": sys.version, "packages": _pkg_versions(),
        "cloq_commit": _git_rev(C.PROJECT_ROOT), "agent_api_base": args.agent_base,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"), "prompt_nonce": os.environ.get("CLOQ_PROMPT_NONCE"),
        "max_prompt_tokens": C.MAX_PROMPT_TOKENS, "model_id": C.MODEL_ID, "model_revision": C.MODEL_REVISION,
        "chat_template_kwargs": C.CHAT_TEMPLATE_KWARGS, "top_logprobs": C.TOP_LOGPROBS,
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "timestamp": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    (run_dir / "model.json").write_text(json.dumps({
        "hf_id": C.MODEL_ID, "revision": C.MODEL_REVISION, "arm": args.arm, "checkpoint": args.checkpoint,
        "agent_server_models": served_model_info(args.agent_base),
    }, indent=2))
    (run_dir / "task_manifest.json").write_text(json.dumps({
        "domain": DOMAIN, "task_ids": task_ids, "n_tasks": len(task_ids), "task_file": args.task_file,
        "hf_repo": man.get("hf_repo") if isinstance(man, dict) else None,
        "hf_revision": man.get("hf_revision") if isinstance(man, dict) else None,
    }, indent=2))
    status = {"status": "running", "started": datetime.now(timezone.utc).isoformat(), "n_tasks": len(task_ids)}
    status_path.write_text(json.dumps(status, indent=2))

    done = {t["task_id"] for t in read_jsonl(run_dir / "trajectory.jsonl")}
    todo = [p for p in problems if p["task_id"] not in done]
    lock = threading.Lock()
    fd = open(run_dir / "decisions.jsonl", "a", encoding="utf-8")
    ft = open(run_dir / "trajectory.jsonl", "a", encoding="utf-8")
    t0 = time.time()
    n_ok = len(done)
    try:
        with ThreadPoolExecutor(max_workers=args.max_concurrency) as ex:
            futs = {ex.submit(L.run_episode, p, args.agent_base, run_meta, args.max_turns): p for p in todo}
            for f in as_completed(futs):
                traj, decs = f.result()
                with lock:
                    for d in decs:
                        fd.write(json.dumps(d, ensure_ascii=False) + "\n")
                    fd.flush()
                    ft.write(json.dumps(traj, ensure_ascii=False) + "\n")
                    ft.flush()
                n_ok += 1
                print(f"[{n_ok}/{len(task_ids)}] {traj['task_id']} {traj['termination_reason']} turns={traj['n_turns']} "
                      f"success={traj['success']} turn1={traj['turn1_success']} {traj['duration']:.0f}s", flush=True)
    finally:
        fd.close()
        ft.close()
    elapsed = time.time() - t0

    # keep only the final attempt per task (decisions written by an interrupted earlier attempt carry another id)
    trajs = read_jsonl(run_dir / "trajectory.jsonl")
    last = {t["task_id"]: t["trajectory_id"] for t in trajs}
    for name, key in (("decisions.jsonl", "trajectory_id"), ("trajectory.jsonl", "trajectory_id")):
        pth = run_dir / name
        recs = read_jsonl(pth)
        kept = [r for r in recs if last.get(r["task_id"]) == r[key]]
        if len(kept) < len(recs):
            tmp = pth.with_suffix(".tmp")
            tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
            os.replace(tmp, pth)

    metrics = summarize(run_dir)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    status.update({"status": "completed" if n_ok == len(task_ids) else "incomplete",
                   "finished": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": elapsed, "n_simulations": n_ok})
    status_path.write_text(json.dumps(status, indent=2))
    print(json.dumps({k: v for k, v in metrics.items() if not isinstance(v, (list, dict))}, indent=2))
    print(f"status={status['status']} elapsed={elapsed:.0f}s -> {run_dir}")


if __name__ == "__main__":
    main()
