"""Run one precision arm on a set of tau2 tasks and write the run artifacts.

usage:
  python -m cloq.run_arm --run-id bf16_pilot --arm bf16 --domain retail \
      [--task-ids 0 1 2] [--agent-base http://127.0.0.1:8001/v1] [--max-concurrency 8]

Artifacts (plan section 22) under runs/<run_id>/<domain>/:
  config.json, environment.json, model.json, task_manifest.json,
  decisions.jsonl (exact model input at every agent decision point),
  tau2_results.json (raw tau2 Results), trajectory.jsonl (one line / task),
  metrics.json, status.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from cloq import config as C
from cloq.agent import close_decision_writer, register_cloq_agent, set_decision_writer


def _git_rev(path: Path) -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def _pkg_versions() -> dict:
    import importlib.metadata as md

    out = {}
    for p in ["vllm", "torch", "transformers", "litellm", "tau2", "tokenizers", "safetensors"]:
        try:
            out[p] = md.version(p)
        except Exception:
            out[p] = None
    return out


def environment_json(agent_base: str, user_base: str) -> dict:
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "packages": _pkg_versions(),
        "tau2_commit": _git_rev(C.TAU2_DIR),
        "cloq_commit": _git_rev(C.PROJECT_ROOT),
        "agent_api_base": agent_base,
        "user_api_base": user_base,
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def served_model_info(api_base: str) -> dict:
    import urllib.request

    try:
        with urllib.request.urlopen(api_base + "/models", timeout=10) as r:
            return json.load(r)
    except Exception as e:  # pragma: no cover
        return {"error": repr(e)}


def _normalize_tool_call(name: str, arguments: dict) -> str:
    from cloq.metrics import normalize_tool_call

    return normalize_tool_call(name, arguments)


def simulation_to_trajectory(sim, task) -> dict:
    """Flatten a tau2 SimulationRun into one JSON record."""
    msgs = []
    for m in sim.messages:
        d = m.model_dump()
        d.pop("raw_data", None)
        msgs.append(d)
    ri = sim.reward_info
    rec = {
        "task_id": sim.task_id,
        "simulation_id": sim.id,
        "seed": sim.seed,
        "termination_reason": sim.termination_reason.value if hasattr(sim.termination_reason, "value") else str(sim.termination_reason),
        "duration": sim.duration,
        "n_messages": len(sim.messages),
        "messages": msgs,
        "reward_info": ri.model_dump() if ri is not None else None,
        "reward": ri.reward if ri is not None else None,
        "db_match": (ri.db_check.db_match if (ri is not None and ri.db_check is not None) else None),
        "communicate_all": (all(c.met for c in ri.communicate_checks) if (ri is not None and ri.communicate_checks) else None),
        "action_all": (all(c.action_match for c in ri.action_checks) if (ri is not None and ri.action_checks) else None),
        "task": task.model_dump(),
    }
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arm", required=True, help="bf16 | static | fp_traj | cloq | q_only | rtn ...")
    ap.add_argument("--domain", required=True, choices=["retail", "airline"])
    ap.add_argument("--task-ids", nargs="*", default=None)
    ap.add_argument("--task-file", default=None, help="json list of task ids or manifest with domain->ids")
    ap.add_argument("--agent-base", default=C.AGENT_API_BASE)
    ap.add_argument("--user-base", default=C.USER_API_BASE)
    ap.add_argument("--max-concurrency", type=int, default=int(C.FROZEN["serving"]["max_concurrency"]))
    ap.add_argument("--checkpoint", default=None, help="checkpoint path served for this arm (recorded)")
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    run_dir = C.RUNS_DIR / args.run_id / args.domain
    run_dir.mkdir(parents=True, exist_ok=True)
    status_path = run_dir / "status.json"
    if status_path.exists() and json.load(open(status_path)).get("status") == "completed":
        print(f"{run_dir} already completed; skipping")
        return

    from tau2.data_model.simulation import TextRunConfig
    from tau2.evaluator.evaluator import EvaluationType
    from tau2.runner.batch import run_tasks
    from tau2.runner.helpers import get_tasks

    register_cloq_agent()
    import litellm
    litellm.register_model({
        f"hosted_vllm/{n}": {"input_cost_per_token": 0.0, "output_cost_per_token": 0.0, "litellm_provider": "hosted_vllm", "mode": "chat"}
        for n in (C.AGENT_SERVED_NAME, C.USER_SERVED_NAME)
    })

    task_ids = args.task_ids
    if args.task_file:
        tf = json.load(open(args.task_file))
        task_ids = tf[args.domain] if isinstance(tf, dict) else tf
        task_ids = [str(t) for t in task_ids]
    tasks = get_tasks(args.domain, task_split_name="base", task_ids=task_ids)
    if task_ids is not None:
        # keep the requested order
        order = {t: i for i, t in enumerate(task_ids)}
        tasks = sorted(tasks, key=lambda t: order[t.id])

    bench = C.FROZEN["benchmark"]
    cfg = TextRunConfig(
        domain=args.domain,
        agent="cloq_agent",
        llm_agent=f"hosted_vllm/{C.AGENT_SERVED_NAME}",
        llm_args_agent=C.agent_llm_args(args.agent_base),
        user="user_simulator",
        llm_user=f"hosted_vllm/{C.USER_SERVED_NAME}",
        llm_args_user=C.user_llm_args(args.user_base),
        max_steps=int(bench["max_steps"]),
        max_errors=int(bench["max_errors"]),
        seed=int(bench["seed"]),
        num_trials=1,
        max_concurrency=args.max_concurrency,
        log_level="ERROR",
        save_to=f"{args.run_id}_{args.domain}",
        task_ids=[t.id for t in tasks],
        task_split_name="base",
        max_retries=3,
        retry_delay=2.0,
    )

    run_meta = {"run_id": args.run_id, "arm": args.arm, "domain": args.domain}
    (run_dir / "config.json").write_text(json.dumps({
        "run_id": args.run_id, "arm": args.arm, "domain": args.domain, "note": args.note,
        "checkpoint": args.checkpoint, "frozen": C.FROZEN,
        "tau2_run_config": json.loads(cfg.model_dump_json()),
        "evaluation_type_at_run": "all_ignore_basis (DB/ACTION/COMMUNICATE computed; NL assertions judged offline by cloq.nl_judge)",
    }, indent=2))
    (run_dir / "environment.json").write_text(json.dumps(environment_json(args.agent_base, args.user_base), indent=2))
    (run_dir / "model.json").write_text(json.dumps({
        "hf_id": C.MODEL_ID, "revision": C.MODEL_REVISION, "arm": args.arm, "checkpoint": args.checkpoint,
        "agent_server_models": served_model_info(args.agent_base),
        "user_server_models": served_model_info(args.user_base),
    }, indent=2))
    (run_dir / "task_manifest.json").write_text(json.dumps({
        "domain": args.domain, "task_ids": [t.id for t in tasks], "n_tasks": len(tasks),
        "task_split": "base", "tau2_commit": _git_rev(C.TAU2_DIR),
    }, indent=2))
    status = {"status": "running", "started": datetime.now(timezone.utc).isoformat(), "n_tasks": len(tasks)}
    status_path.write_text(json.dumps(status, indent=2))

    set_decision_writer(run_dir / "decisions.jsonl", run_meta)
    t0 = time.time()
    try:
        results = run_tasks(
            cfg, tasks,
            save_path=run_dir / "tau2_results.json",
            save_dir=run_dir / "tau2_logs",
            evaluation_type=EvaluationType.ALL_IGNORE_BASIS,
            console_display=False,
        )
    finally:
        close_decision_writer()
    elapsed = time.time() - t0

    task_by_id = {t.id: t for t in tasks}
    n_ok = 0
    with open(run_dir / "trajectory.jsonl", "w", encoding="utf-8") as f:
        for sim in results.simulations:
            rec = simulation_to_trajectory(sim, task_by_id[sim.task_id])
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_ok += 1

    from cloq.metrics import summarize_run

    metrics = summarize_run(run_dir)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    status.update({
        "status": "completed" if n_ok == len(tasks) else "incomplete",
        "finished": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed, "n_simulations": n_ok,
    })
    status_path.write_text(json.dumps(status, indent=2))
    print(json.dumps({k: v for k, v in metrics.items() if not isinstance(v, (list, dict))}, indent=2))
    print(f"status={status['status']} elapsed={elapsed:.0f}s -> {run_dir}")


if __name__ == "__main__":
    main()
