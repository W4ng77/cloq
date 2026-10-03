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
        "prompt_nonce": os.environ.get("CLOQ_PROMPT_NONCE"),
        "max_prompt_tokens": C.MAX_PROMPT_TOKENS,
        "model_id": C.MODEL_ID, "model_revision": C.MODEL_REVISION,
        "chat_template_kwargs": C.CHAT_TEMPLATE_KWARGS, "user_model_id": C.USER_MODEL_ID,
        "user_chat_template_kwargs": C.USER_CHAT_TEMPLATE_KWARGS, "top_logprobs": C.TOP_LOGPROBS,
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
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
    rec.update(basis_reward(sim, task))
    msgs = rec["messages"]
    if msgs and msgs[-1].get("role") == "assistant" and msgs[-1].get("content") == "###CLOQ_LOOP_EARLY_STOP###":
        # W69 opt-in loop guard (cloq/loop_guard.py): an algorithmic failure under the panel's guarded success definition
        rec["tau2_termination_reason"] = rec["termination_reason"]
        rec["termination_reason"] = "loop_early_stop"
        rec["official_reward_unguarded_eval"] = rec.get("official_reward")
        rec["official_reward"] = 0.0
    return rec


def basis_reward(sim, task) -> dict:
    """Task-basis reward (tau2's official score) next to the ALL_IGNORE_BASIS product.

    We evaluate with ALL_IGNORE_BASIS, whose `reward` multiplies DB, ENV_ASSERTION, ACTION and COMMUNICATE
    whatever the task's reward_basis. For telecom (reward_basis ENV_ASSERTION [+ ACTION]) that product
    also demands the gold user-side action sequence, which tau2 does not score. `official_reward` is the
    product over the task's own basis only (NL_ASSERTION is judged offline by cloq.nl_judge and is left
    out here); a premature termination scores 0 as in tau2. User-side tool use (dual control) is counted
    separately from the agent's.
    """
    ri = sim.reward_info
    crit = task.evaluation_criteria
    basis = [b.value if hasattr(b, "value") else str(b) for b in ((crit.reward_basis if crit is not None else None) or [])]
    env_all = (all(c.met for c in ri.env_assertions) if (ri is not None and ri.env_assertions) else None)
    comps = {
        "DB": (ri.db_check.db_match if (ri is not None and ri.db_check is not None) else None),
        "ENV_ASSERTION": env_all,
        "ACTION": (all(c.action_match for c in ri.action_checks) if (ri is not None and ri.action_checks) else None),
        "COMMUNICATE": (all(c.met for c in ri.communicate_checks) if (ri is not None and ri.communicate_checks) else None),
    }
    reason = sim.termination_reason.value if hasattr(sim.termination_reason, "value") else str(sim.termination_reason)
    if reason not in ("user_stop", "agent_stop"):
        official = 0.0
    else:
        official = 1.0
        for b in basis:
            if b in comps and comps[b] is not None:
                official *= float(bool(comps[b]))
            elif b in ("ENV_ASSERTION", "ACTION", "COMMUNICATE"):
                pass  # empty check list: vacuously met (tau2 scores it 1.0)
    user_calls = [tc for m in sim.messages if getattr(m, "role", None) == "user" for tc in (getattr(m, "tool_calls", None) or [])]
    user_tool_msgs = [m for m in sim.messages if getattr(m, "role", None) == "tool" and getattr(m, "requestor", None) == "user"]
    return {
        "reward_basis_task": basis,
        "env_assert_all": env_all,
        "official_reward": official,
        "n_user_tool_calls": len(user_calls),
        "n_user_tool_errors": sum(1 for m in user_tool_msgs if getattr(m, "error", False)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arm", required=True, help="bf16 | static | fp_traj | cloq | q_only | rtn ...")
    ap.add_argument("--domain", required=True, choices=["retail", "airline", "telecom"])
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
    rerun = None
    if os.environ.get("CLOQ_RERUN_OUTAGE") == "1":  # W100w: re-run only the outage episodes (cloq/rerun_outage.py)
        from cloq import rerun_outage as RO
        rerun = RO.plan(run_dir)
    if rerun is None and status_path.exists() and json.load(open(status_path)).get("status") == "completed":
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
    # W100w: a re-run runs only rerun["todo"] and writes its own artifacts in rerun["dir"]; merged into run_dir below
    run_list, out_dir = (tasks, run_dir) if rerun is None else (RO.subset(tasks, rerun), rerun["dir"])

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
        task_ids=[t.id for t in run_list],
        task_split_name="base",
        max_retries=1,
        auto_resume=True,
        retry_delay=2.0,
    )

    run_meta = {"run_id": args.run_id, "arm": args.arm, "domain": args.domain}
    loop_guard = None
    if os.environ.get("CLOQ_LOOP_GUARD"):  # W69: opt-in stress-panel loop guard; the agent refuses an unpinned sha
        from cloq import loop_guard as LG
        os.environ["CLOQ_LOOP_GUARD_LOG"] = str(run_dir / "loop_guard.jsonl")
        loop_guard = {"policy": os.environ["CLOQ_LOOP_GUARD"], "code_sha256": LG.code_sha(),
                      "pinned_sha256": os.environ.get("CLOQ_LOOP_GUARD_SHA"), "window": LG.WINDOW,
                      "min_repeats": LG.MIN_REPEATS, "max_cycle": LG.MAX_CYCLE, "log": "loop_guard.jsonl"}
    (out_dir / "config.json").write_text(json.dumps({
        "run_id": args.run_id, "arm": args.arm, "domain": args.domain, "note": args.note,
        "checkpoint": args.checkpoint, "frozen": C.FROZEN, "loop_guard": loop_guard,
        "tau2_run_config": json.loads(cfg.model_dump_json()),
        "evaluation_type_at_run": "all_ignore_basis (DB/ENV_ASSERTION/ACTION/COMMUNICATE computed; NL assertions judged offline by cloq.nl_judge;"
                                  " official_reward = product over the task's own reward_basis, the telecom primary endpoint)",
    }, indent=2))
    (out_dir / "environment.json").write_text(json.dumps(environment_json(args.agent_base, args.user_base), indent=2))
    (out_dir / "model.json").write_text(json.dumps({
        "hf_id": C.MODEL_ID, "revision": C.MODEL_REVISION, "arm": args.arm, "checkpoint": args.checkpoint,
        "agent_server_models": served_model_info(args.agent_base),
        "user_server_models": served_model_info(args.user_base),
    }, indent=2))
    (out_dir / "task_manifest.json").write_text(json.dumps({
        "domain": args.domain, "task_ids": [t.id for t in run_list], "n_tasks": len(run_list),
        "task_split": "base", "tau2_commit": _git_rev(C.TAU2_DIR),
    }, indent=2))
    status = {"status": "running", "started": datetime.now(timezone.utc).isoformat(), "n_tasks": len(run_list)}
    status_path = out_dir / "status.json"
    status_path.write_text(json.dumps(status, indent=2))

    set_decision_writer(out_dir / "decisions.jsonl", run_meta)
    t0 = time.time()
    try:
        results = run_tasks(
            cfg, run_list,
            save_path=out_dir / "tau2_results.json",
            save_dir=out_dir / "tau2_logs",
            evaluation_type=EvaluationType.ALL_IGNORE_BASIS,
            console_display=False,
        )
    finally:
        close_decision_writer()
    elapsed = time.time() - t0
    if rerun is not None:  # W100w: merge the re-run into the run-domain (originals archived in rerun["dir"]/orig)
        status_path.write_text(json.dumps(dict(status, status="rerun_done", elapsed_seconds=elapsed), indent=2))
        results, status = RO.merge(run_dir, rerun, status, elapsed)
        status_path = run_dir / "status.json"

    task_by_id = {t.id: t for t in tasks}
    n_ok = 0
    with open(run_dir / "trajectory.jsonl", "w", encoding="utf-8") as f:
        for sim in results.simulations:
            rec = simulation_to_trajectory(sim, task_by_id[sim.task_id])
            if loop_guard is not None:  # live and offline guard must agree on the produced episode (W69 consistency)
                from cloq import loop_guard as LG
                off = LG.replay_episode(rec, args.domain)
                rec["loop_guard_check"] = {"live_fired": rec["termination_reason"] == "loop_early_stop",
                                           "offline_fires": off is not None,
                                           "offline_stop_before_decision": off and off["stop_before_decision"]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_ok += 1

    # W8: tau2 auto_resume / retries re-run a simulation while the decision writer appends, so keep only the final
    # attempt's records per task (the last trajectory_id written for that task)
    dp = run_dir / "decisions.jsonl"
    if dp.exists():
        recs = [json.loads(ln) for ln in dp.read_text().splitlines() if ln.strip()]
        last = {r["task_id"]: r["trajectory_id"] for r in recs}
        kept = [r for r in recs if last[r["task_id"]] == r["trajectory_id"]]
        if len(kept) < len(recs):
            tmp = dp.with_suffix(".tmp")
            tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
            os.replace(tmp, dp)

    from cloq.metrics import summarize_run

    metrics = summarize_run(run_dir)
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    status.update({
        "status": "completed" if n_ok == len(tasks) else "incomplete",
        "finished": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed, "n_simulations": n_ok,
    })
    status_path.write_text(json.dumps(status, indent=2))
    if rerun is not None:
        RO.done(rerun, status)
    print(json.dumps({k: v for k, v in metrics.items() if not isinstance(v, (list, dict))}, indent=2))
    print(f"status={status['status']} elapsed={elapsed:.0f}s -> {run_dir}")


if __name__ == "__main__":
    main()
