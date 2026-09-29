"""One code-agent episode: problem -> program -> public-test feedback -> revision, up to T turns.

Scaffold (fixed for every arm):
  system  LiveCodeBench's generic system prompt + the loop rules (+ "Session ID: <nonce>" line when
          CLOQ_PROMPT_NONCE is set, exactly as cloq.agent.CLOQAgent.system_prompt does)
  user    LiveCodeBench's code-generation prompt (question + format instruction + starter code)
  loop    assistant reply -> last ```python block -> run on the public tests in the sandbox ->
          all pass: stop (termination "public_pass"; the program is final)
          otherwise: deterministic feedback as the next user message (termination "max_turns" after T replies)
  grade   every distinct submitted program is graded on the hidden tests (stop at first failure);
          success = final program passes all public and all hidden tests.
No LLM user simulator, no judge; the only stochastic element would be the agent model, served greedy.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid

from cloq import config as C
from cloq.agent import _token_margins
from cloq.context_policy import render_prompt, render_prompt_ids, sha256_text
from cloq_code import sandbox as S

MAX_TURNS_DEFAULT = 8

SYSTEM_BASE = ("You are an expert Python programmer. You will be given a question (problem specification) and will "
               "generate a correct Python program that matches the specification and passes all tests.")
LOOP_RULES = ("You may submit up to {T} times. Each submission is run on the public example tests and you are shown "
              "the result; once all public example tests pass, your program is final and is judged on hidden tests. "
              "Keep any reasoning brief (each reply is limited to {M} tokens) and always end your reply with the "
              "complete program in a single ```python code block.")
FMT_STARTER = "You will use the following starter code to write the solution to the problem and enclose your code within delimiters."
FMT_STDIN = ("Read the inputs from stdin solve the problem and write the answer to stdout (do not directly test on the "
             "sample inputs). Enclose your code within delimiters as follows. Ensure that when the python program runs, "
             "it reads the inputs, runs the algorithm and writes output to STDOUT.")
NO_CODE = ("No complete ```python code block was found in your reply{why}. Reply with the complete program in a single "
           "```python code block.")


class InfraError(RuntimeError):
    pass


def system_prompt(max_turns: int) -> str:
    base = SYSTEM_BASE + "\n\n" + LOOP_RULES.format(T=max_turns, M=C.AGENT_MAX_TOKENS)
    nonce = os.environ.get("CLOQ_PROMPT_NONCE")
    return f"{base}\nSession ID: {nonce}\n" if nonce else base


def user_prompt(p: dict) -> str:
    s = f"### Question:\n{p['content']}\n\n"
    if p["testtype"] == "functional":
        s += f"### Format: {FMT_STARTER}\n```python\n{p['starter_code']}\n```\n\n"
    else:
        s += f"### Format: {FMT_STDIN}\n```python\n# YOUR CODE HERE\n```\n\n"
    return s + "### Answer: (use the provided format with backticks)\n\n"


def request_body(messages: list[dict]) -> dict:
    """The exact request cloq.run_arm sends through litellm, from the frozen generation_agent settings."""
    a = C.agent_llm_args()
    body = {"model": C.AGENT_SERVED_NAME, "messages": messages}
    for k in ("temperature", "top_p", "max_tokens", "seed", "presence_penalty", "frequency_penalty", "logprobs", "top_logprobs"):
        if k in a:
            body[k] = a[k]
    body.update(a["extra_body"])
    return body


def generate(api_base: str, messages: list[dict], retries: int = 1) -> dict:
    data = json.dumps(request_body(messages)).encode()
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(api_base + "/chat/completions", data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            last = e
            time.sleep(2.0)
    raise InfraError(f"agent server request failed: {last!r}")


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def run_episode(p: dict, api_base: str, run_meta: dict, max_turns: int = MAX_TURNS_DEFAULT) -> tuple[dict, list[dict]]:
    """Returns (trajectory record, decision records)."""
    t_start = time.time()
    traj_id = str(uuid.uuid4())
    sysmsg = system_prompt(max_turns)
    messages = [{"role": "system", "content": sysmsg}, {"role": "user", "content": user_prompt(p)}]
    decisions, submissions = [], []  # submissions: (decision_idx, code or None, public result dict or None)
    termination, infra = "max_turns", None
    public = p["public_tests"]
    try:
        for turn in range(max_turns):
            prompt_text = render_prompt(messages, None)
            local_ids = render_prompt_ids(messages, None)
            if len(local_ids) > C.MAX_PROMPT_TOKENS:
                termination = "context_limit"
                break
            t0 = time.time()
            resp = generate(api_base, messages)
            dt = time.time() - t0
            choice0 = (resp.get("choices") or [{}])[0]
            msg = choice0.get("message") or {}
            content = msg.get("content") or ""
            prompt_ids = resp.get("prompt_token_ids")
            completion_ids = choice0.get("token_ids")
            finish = choice0.get("finish_reason")
            code = S.extract_code(content)
            rec = {
                **run_meta,
                "task_id": p["task_id"], "trajectory_id": traj_id, "decision_idx": turn,
                "n_state_messages": len(messages) - 1,
                "messages": [dict(m) for m in messages],
                "tools_sha256": None, "system_sha256": sha256_text(sysmsg),
                "context": {"pre_truncation_tokens": len(local_ids), "post_truncation_tokens": len(local_ids),
                            "n_units_dropped": 0, "truncated": False},
                "prompt_sha256": sha256_text(prompt_text),
                "prompt_token_ids": prompt_ids if prompt_ids is not None else local_ids,
                "prompt_ids_from_server": prompt_ids is not None,
                "prompt_ids_match_local": (prompt_ids == local_ids) if prompt_ids is not None else None,
                "n_prompt_tokens": len(prompt_ids) if prompt_ids is not None else len(local_ids),
                "completion_token_ids": completion_ids,
                "n_completion_tokens": (resp.get("usage") or {}).get("completion_tokens"),
                "finish_reason": finish,
                "raw_content": msg.get("content"), "content": content, "tool_calls": None,
                "parser_error": code is None,
                "generation_seconds": dt,
                **_token_margins(choice0.get("logprobs")),
                "code_sha256": _sha(code) if code is not None else None,
            }
            messages.append({"role": "assistant", "content": content})
            if code is None:
                why = " (the reply hit the length limit before the code block was closed)" if finish == "length" else ""
                fb, pub = NO_CODE.format(why=why), None
                rec["public_verdicts"], rec["public_passed"] = None, False
            else:
                pub = S.run_tests(code, public, p["testtype"], p.get("func_name"), stop_at_first_fail=False)
                if pub["sandbox_error"]:
                    raise InfraError("sandbox error on public tests: " + pub["_results"][-1].stderr[:500])
                rec["public_verdicts"], rec["public_passed"] = pub["verdicts"], pub["passed"]
                fb = None if pub["passed"] else S.feedback_text(pub, public, p["testtype"])
            rec["feedback"] = fb
            decisions.append(rec)
            submissions.append((turn, code, pub))
            if code is not None and pub["passed"]:
                termination = "public_pass"
                break
            messages.append({"role": "user", "content": fb})
    except InfraError as e:
        termination, infra = "infrastructure_error", str(e)

    # hidden grading of every distinct submitted program (stop at the first failing test)
    hidden_cache: dict[str, dict] = {}
    if termination != "infrastructure_error":
        hp = None
        for turn, code, pub in submissions:
            if code is None or _sha(code) in hidden_cache:
                continue
            if hp is None:
                from cloq_code.data import load_problem
                hp = load_problem(p["task_id"], with_hidden=True)["hidden_tests"]
            h = S.run_tests(code, hp, p["testtype"], p.get("func_name"), stop_at_first_fail=True)
            if h["sandbox_error"]:
                termination, infra = "infrastructure_error", "sandbox error on hidden tests"
                break
            hidden_cache[_sha(code)] = {k: v for k, v in h.items() if k != "_results"}
    turn_success = []
    for (turn, code, pub), rec in zip(submissions, decisions):
        h = hidden_cache.get(_sha(code)) if code is not None else None
        rec["hidden_passed"] = h["passed"] if h else (False if code is None else None)
        rec["hidden_verdicts"] = h["verdicts"] if h else None
        ok = bool(code is not None and pub["passed"] and h and h["passed"])
        rec["turn_success"] = ok
        turn_success.append(ok)
    final = next(((t, c, pb) for t, c, pb in reversed(submissions) if c is not None), None)
    success = bool(final and final[2]["passed"] and hidden_cache.get(_sha(final[1]), {}).get("passed"))
    if termination == "infrastructure_error":
        success = False
    turn1 = turn_success[0] if turn_success else False
    n_wall = sum(1 for r in decisions for v in (r.get("public_verdicts") or []) + (r.get("hidden_verdicts") or []) if v == "wall_timeout")
    traj = {
        **run_meta,
        "task_id": p["task_id"], "trajectory_id": traj_id, "simulation_id": traj_id, "seed": None,
        "termination_reason": termination, "infrastructure_error": infra,
        "duration": time.time() - t_start,
        "n_turns": len(decisions), "n_messages": len(messages), "messages": messages,
        "success": success, "reward": float(success), "db_match": success,
        "turn1_success": turn1, "turn_success": turn_success,
        "final_decision_idx": final[0] if final else None,
        "final_public_passed": bool(final and final[2]["passed"]),
        "final_hidden_passed": bool(final and hidden_cache.get(_sha(final[1]), {}).get("passed")),
        "final_code": final[1] if final else None,
        "n_no_code": sum(1 for _, c, _ in submissions if c is None),
        "n_wall_timeouts": n_wall,
        "problem": {k: p[k] for k in ("title", "platform", "contest_date", "difficulty", "testtype", "func_name")},
        "n_public": len(public),
    }
    return traj, decisions
