"""Conservative loop early-stop guard for NEW stress panels only (W69; docs/EXECUTION_PLAN_20260930.md §8.4).

Opt-in: active only when the run's environment sets CLOQ_LOOP_GUARD=lg-v2 and CLOQ_LOOP_GUARD_SHA equals the sha256 of
this file (pinned in manifests/stress/loop_guard_v2.json before any W2 outcome).
Revision history: lg-v1 (window 16, >= 4 repeats; manifests/stress/loop_guard_v1.json) failed its premature-stop check
(18 / 5874 later-successful stress episodes stopped); lg-v2 (W73) tightens to window 32, >= 8 repeats, everything else
unchanged. The lg-v2 thresholds were chosen on already-viewed development stress traces, before any W2 outcome existed. Frozen / primary runs never set it, and
an unset guard changes nothing (cloq.agent imports this module only when enabled).

Rule (policy lg-v2). Before the agent generates decision n, look at the completed decisions in the last WINDOW = 32.
The guard fires iff for some cycle length L in 1..4 the most recent R >= 8 complete copies of an L-decision cycle
(L * R <= 32) are identical in ALL of:
  - canonical action: tool name + fully normalised arguments for every tool call, in order (cloq.metrics
    normalize_tool_call: IDs, numbers, list order preserved; whitespace collapsed), or the full normalised talk text;
  - evidence: digest of the tool results answering the decision (content + error flag, in order) for tool decisions;
    digest of the full user reply for talk decisions (text-only loops need the repeated assistant/user turn);
  - task-relevant environment: the agent-side DB hash after every decision of the span equals the hash before it
    (unchanged state; iterative writes that change state break the cycle);
  - no new user-information event: any user-side tool call, or a talk decision without its user reply, breaks it.
If any required evidence is missing (no DB hash, no tool result, no user reply), the decision does not count and the
guard does not fire. Final success, the precision arm and any classifier play no role.
On firing the agent emits LOOP_STOP_CONTENT; cloq.agent.CLOQAgent.is_stop ends the episode and cloq.run_arm records
termination_reason "loop_early_stop" (official_reward 0) with the evidence persisted in loop_guard.jsonl.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Optional

POLICY = "lg-v2"
WINDOW = 32
MIN_REPEATS = 8
MAX_CYCLE = 4
LOOP_STOP_CONTENT = "###CLOQ_LOOP_EARLY_STOP###"


def code_sha() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()[:16]


def _args(a):
    if isinstance(a, str):
        try:
            return json.loads(a)
        except json.JSONDecodeError:
            return {"__unparsed__": a}
    return a if isinstance(a, dict) else {"__unparsed__": a}


def canonical_action(m: dict) -> str:
    from cloq.metrics import normalize_tool_call
    tcs = m.get("tool_calls") or []
    if tcs:
        return "TOOL|" + "|".join(normalize_tool_call(tc.get("name"), _args(tc.get("arguments"))) for tc in tcs)
    return "TEXT|" + " ".join((m.get("content") or "").strip().split())


def decisions_from_messages(msgs: list[dict], n0: int) -> list[dict]:
    """Agent decisions after the prefix msgs[:n0] with their evidence. Message dicts in tau2 trajectory form.

    Each decision: {"pos": index of the assistant message, "end": index after its evidence, "action", "evidence"
    (None if missing), "user_event": True if a user-side tool call / non-reply user event belongs to it}.
    The last decision is complete only if its evidence has arrived."""
    out = []
    i = n0
    while i < len(msgs):
        m = msgs[i]
        if m.get("role") != "assistant":
            i += 1
            continue
        d = {"pos": i, "action": canonical_action(m), "evidence": None, "user_event": False}
        j = i + 1
        if m.get("tool_calls"):
            res = []
            while j < len(msgs) and msgs[j].get("role") == "tool":
                res.append([msgs[j].get("content"), bool(msgs[j].get("error"))])
                j += 1
            if len(res) == len(m["tool_calls"]):
                d["evidence"] = "R" + _h(res)
        else:
            if j < len(msgs) and msgs[j].get("role") == "user":
                u = msgs[j]
                d["evidence"] = "U" + _h([u.get("content"), u.get("tool_calls")])
                d["user_event"] = bool(u.get("tool_calls"))  # the user acts on the environment (dual control)
                j += 1
                while j < len(msgs) and msgs[j].get("role") != "assistant":  # anything else before the next decision
                    d["user_event"] = True
                    j += 1
        d["end"] = j
        out.append(d)
        i = j
    return out


def check(decs: list[dict], env_hash: Callable[[int], Optional[str]]) -> Optional[dict]:
    """Guard decision over completed decisions decs (oldest first). env_hash(k) = agent-side DB hash after the first k
    messages of the trajectory (k = a decision's "end", or the first decision's "pos" for the state before it), None if
    unavailable. Returns the firing evidence or None. Cheap evidence is checked first; DB hashes only for a candidate."""
    win = [d for d in decs[-WINDOW:]]
    for L in range(1, MAX_CYCLE + 1):
        R = 0
        while (R + 1) * L <= len(win):
            a = win[len(win) - (R + 1) * L: len(win) - R * L]
            b = win[len(win) - L:]
            if [(x["action"], x["evidence"]) for x in a] != [(x["action"], x["evidence"]) for x in b]:
                break
            R += 1
        R = min(R, WINDOW // L)
        if R < MIN_REPEATS:
            continue
        span = win[len(win) - R * L:]
        if any(x["evidence"] is None or x["user_event"] for x in span):
            continue
        before = env_hash(span[0]["pos"])
        after = [env_hash(x["end"]) for x in span]
        if before is None or any(h is None for h in after) or any(h != before for h in after):
            continue
        return {"policy": POLICY, "cycle_len": L, "repeats": R, "span_decisions": len(span),
                "actions": [x["action"] for x in span[-L:]], "action_hashes": [_h(x["action"]) for x in span],
                "evidence_hashes": [x["evidence"] for x in span], "env_hash": before,
                "first_pos": span[0]["pos"], "last_end": span[-1]["end"]}
    return None


def budget(msgs: list[dict], n0: int) -> dict:
    """Orchestrator counters at this point (same counting as cloq.fork.budget_used) + tool calls consumed."""
    steps = errors = calls = 0
    for i in range(n0, len(msgs)):
        m = msgs[i]
        if m.get("role") == "tool":
            if i == n0 or msgs[i - 1].get("role") != "tool":
                steps += 1
            errors += bool(m.get("error"))
        else:
            steps += 1
            if m.get("role") == "assistant":
                calls += len(m.get("tool_calls") or [])
    return {"steps": steps, "errors": errors, "agent_tool_calls": calls}


def replay_episode(traj: dict, domain: str, restore_env=None) -> Optional[dict]:
    """Offline: the decision before which the guard would have fired in this finished episode, or None.

    DB hashes come from a strict tau2 environment replay of the episode prefix (cloq.fork.restore_env), the same state
    the live toolkit hashes. Evaluated at every decision boundary exactly as the live guard does."""
    from cloq.fork import msg_from_dict, prefix_len
    msgs = traj["messages"]
    n0 = prefix_len(traj["task"])
    decs = decisions_from_messages(msgs, n0)
    cache: dict[int, Optional[str]] = {}
    task = None

    def env_hash(k: int) -> Optional[str]:
        nonlocal task
        if k in cache:
            return cache[k]
        try:
            from tau2.data_model.tasks import Task
            from cloq.fork import restore_env as _re
            if task is None:
                task = Task.model_validate(traj["task"])
            env = (restore_env or _re)(domain, task, [msg_from_dict(m) for m in msgs[:k]])
            cache[k] = env.get_db_hash()
        except Exception:
            cache[k] = None
        return cache[k]

    for n in range(1, len(decs)):  # before generating decision n, decisions 0..n-1 are complete
        ev = check(decs[:n], env_hash)
        if ev is not None:
            ev.update({"stop_before_decision": n, "n_decisions_actual": len(decs), "budget": budget(msgs[:decs[n]["pos"]], n0)})
            return ev
    return None


# ---------------------------------------------------------------------------------------------- live (in-loop) guard

_LOG_LOCK = __import__("threading").Lock()


class LiveGuard:
    """Per-agent live guard (cloq.agent.CLOQAgent, only when CLOQ_LOOP_GUARD is set). Records the agent-side DB hash
    at every decision boundary from the environment toolkit the agent's tools are bound to, and evaluates check()
    with exactly the offline semantics (positions index the agent's state.messages, which align with the trajectory)."""

    def __init__(self, tools, task):
        import os
        policy = os.environ.get("CLOQ_LOOP_GUARD")
        if policy != POLICY:
            raise RuntimeError(f"CLOQ_LOOP_GUARD={policy!r}: only {POLICY} is implemented")
        if os.environ.get("CLOQ_LOOP_GUARD_SHA") != code_sha():
            raise RuntimeError(f"loop guard code sha {code_sha()[:16]} != pinned CLOQ_LOOP_GUARD_SHA "
                               f"{(os.environ.get('CLOQ_LOOP_GUARD_SHA') or '')[:16]}")
        from cloq.fork import prefix_len
        self.tk = None
        for t in tools or []:
            tk = getattr(getattr(t, "_func", None), "__self__", None)
            if tk is not None and hasattr(tk, "get_db_hash"):
                self.tk = tk
                break
        self.n0 = prefix_len(task.model_dump()) if task is not None else 1
        self.hash_at: dict[int, Optional[str]] = {}
        self.tokens = {"prompt": 0, "completion": 0, "decisions": 0}
        self.log = os.environ.get("CLOQ_LOOP_GUARD_LOG")

    def before_decision(self, messages, task_id, trajectory_id, decision_idx):
        k = len(messages)
        try:
            self.hash_at[k] = self.tk.get_db_hash() if self.tk is not None else None
        except Exception:
            self.hash_at[k] = None
        msgs = [m.model_dump() for m in messages]
        ev = check(decisions_from_messages(msgs, self.n0), lambda kk: self.hash_at.get(kk))
        if ev is None:
            return None
        import time as _t
        ev.update({"task_id": task_id, "trajectory_id": trajectory_id, "stop_before_decision_idx": decision_idx,
                   "budget": budget(msgs, self.n0), "tokens": dict(self.tokens), "code_sha256": code_sha(),
                   "utc": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())})
        if self.log:
            with _LOG_LOCK, open(self.log, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        from tau2.data_model.message import AssistantMessage
        return AssistantMessage(role="assistant", content=LOOP_STOP_CONTENT)

    def after_decision(self, rec: dict) -> None:
        self.tokens["prompt"] += int(rec.get("n_prompt_tokens") or 0)
        self.tokens["completion"] += int(rec.get("n_completion_tokens") or 0)
        self.tokens["decisions"] += 1
