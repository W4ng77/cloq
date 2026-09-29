"""Offline NL-assertion judging with the frozen local BF16 server.

tau2 grades retail tasks with `NL_ASSERTION` in reward_basis through an LLM
judge (gpt-4.1 by default). We have no external API, so every arm is judged
by the *same* frozen local model (Qwen3-4B-Instruct-2507 BF16, greedy), and the
judgement is stored next to the trajectory so it can be re-run later with a
stronger judge without re-running any simulation.

usage: python -m cloq.nl_judge --run-dir runs/<run_id>/<domain> [--user-base ...]
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loguru import logger

from cloq import config as C


def _judge_one(traj: dict, judge_model: str, judge_args: dict) -> dict:
    from tau2.data_model.message import AssistantMessage, SystemMessage, ToolMessage, UserMessage
    from tau2.data_model.tasks import Task
    from tau2.evaluator import evaluator_nl_assertions as E
    from tau2.utils.llm_utils import extract_json_from_llm_response, generate

    task = Task(**traj["task"])
    crit = task.evaluation_criteria
    nl = (crit.nl_assertions if crit is not None else None) or []
    basis = [str(b.value if hasattr(b, "value") else b) for b in ((crit.reward_basis if crit is not None else None) or [])]
    out = {"task_id": traj["task_id"], "nl_assertions": nl, "nl_in_basis": "NL_ASSERTION" in basis}
    if not nl:
        out.update({"nl_all_met": True, "checks": [], "judge_error": None})
        return out
    msgs = []
    for m in traj["messages"]:
        r = m.get("role")
        if r == "assistant":
            msgs.append(AssistantMessage(role="assistant", content=m.get("content"), tool_calls=m.get("tool_calls")))
        elif r == "user":
            msgs.append(UserMessage(role="user", content=m.get("content"), tool_calls=m.get("tool_calls")))
        elif r == "tool":
            msgs.append(ToolMessage(id=m.get("id", ""), role="tool", content=m.get("content"), requestor=m.get("requestor", "assistant"), error=m.get("error", False)))
    # Same trajectory string / prompt as tau2 (copied from evaluate_nl_assertions).
    trajectory_str = "\n".join(f"{m.role}: {m.content}" for m in msgs)
    system_prompt = E.NLAssertionsEvaluator.evaluate_nl_assertions.__doc__  # placeholder, replaced below
    # Re-create the exact prompts by calling the tau2 method with a patched generate.
    captured = {}

    def fake_generate(model, messages, call_name=None, **kwargs):
        captured["messages"] = messages
        resp = generate(model=judge_model, messages=messages, call_name="nl_assertions_eval", **judge_args)
        # Robust JSON extraction + shape normalisation (small models wrap JSON in code
        # fences and often return one flat object instead of {"results": [...]}).
        content = resp.content or ""
        captured["raw"] = content
        obj = None
        for cand in (content, extract_json_from_llm_response(content)):
            try:
                obj = json.loads(cand); break
            except Exception:
                continue
        results = None
        if isinstance(obj, dict) and isinstance(obj.get("results"), list):
            results = obj["results"]
        elif isinstance(obj, dict) and "metExpectation" in obj:
            results = [obj]
        elif isinstance(obj, list):
            results = [x for x in obj if isinstance(x, dict)]
        if results is not None:
            norm = []
            for i, x in enumerate(results):
                met = x.get("metExpectation", x.get("met", False))
                if isinstance(met, str):
                    met = met.strip().lower() in ("true", "yes")
                norm.append({"expectedOutcome": x.get("expectedOutcome", nl[i] if i < len(nl) else ""),
                             "reasoning": str(x.get("reasoning", "")), "metExpectation": bool(met)})
            resp.content = json.dumps({"results": norm})
        else:
            resp.content = json.dumps({"results": []})
        return resp

    orig = E.generate
    E.generate = fake_generate
    try:
        checks = E.NLAssertionsEvaluator.evaluate_nl_assertions(msgs, nl)
        out.update({
            "nl_all_met": all(c.met for c in checks) and len(checks) == len(nl),
            "checks": [c.model_dump() for c in checks],
            "judge_error": None if len(checks) == len(nl) else f"judge returned {len(checks)} results for {len(nl)} assertions",
            "judge_raw": captured.get("raw"),
        })
    except Exception as e:  # parse failure -> not met, recorded
        out.update({"nl_all_met": False, "checks": [], "judge_error": repr(e), "judge_raw": captured.get("raw")})
    finally:
        E.generate = orig
    return out


def judge_run(run_dir: Path, user_base: str, concurrency: int = 8) -> dict:
    run_dir = Path(run_dir)
    trajs = [json.loads(l) for l in open(run_dir / "trajectory.jsonl", encoding="utf-8") if l.strip()]
    judge_model = f"hosted_vllm/{C.USER_SERVED_NAME}"
    judge_args = C.judge_llm_args(user_base)
    with ThreadPoolExecutor(concurrency) as ex:
        results = list(ex.map(lambda t: _judge_one(t, judge_model, judge_args), trajs))
    with open(run_dir / "nl_judge.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # Official-style task success: reward_basis components, NL from the local judge.
    by_id = {r["task_id"]: r for r in results}
    n_err = sum(1 for r in results if r.get("judge_error"))
    succ = []
    for t in trajs:
        r = by_id[t["task_id"]]
        crit = t["task"].get("evaluation_criteria") or {}
        basis = crit.get("reward_basis") or []
        from cloq.metrics import resolved_db_match

        ok = t.get("termination_reason") in ("user_stop", "agent_stop")
        if "DB" in basis:
            ok = ok and bool(resolved_db_match(t))
        if "COMMUNICATE" in basis:
            ok = ok and bool(t.get("communicate_all") if t.get("communicate_all") is not None else True)
        if "ACTION" in basis:
            ok = ok and bool(t.get("action_all") if t.get("action_all") is not None else True)
        if "NL_ASSERTION" in basis:
            ok = ok and bool(r["nl_all_met"])
        succ.append({"task_id": t["task_id"], "task_success": ok, "reward_basis": basis})
    (run_dir / "task_success.json").write_text(json.dumps({
        "judge": {"model": C.USER_MODEL_ID, "server": user_base, "args": judge_args},
        "n_tasks": len(succ), "n_judge_errors": n_err,
        "task_success_rate": sum(s["task_success"] for s in succ) / max(1, len(succ)),
        "per_task": succ,
    }, indent=2))
    summary = {"n": len(succ), "task_success_rate": sum(s["task_success"] for s in succ) / max(1, len(succ)), "judge_errors": n_err}
    logger.info(f"NL judge done for {run_dir}: {summary}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--user-base", default=C.USER_API_BASE)
    ap.add_argument("--concurrency", type=int, default=8)
    a = ap.parse_args()
    print(judge_run(Path(a.run_dir), a.user_base, a.concurrency))


if __name__ == "__main__":
    main()
