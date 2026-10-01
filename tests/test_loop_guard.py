"""Unit tests for cloq/loop_guard.py (lg-v1), CPU, synthetic tau2-shaped message lists. run: python tests/test_loop_guard.py"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cloq import loop_guard as G  # noqa: E402

RESULTS = {}


def A(name=None, args=None, text=None):
    if name:
        return {"role": "assistant", "content": None, "tool_calls": [{"name": name, "arguments": args or {}}]}
    return {"role": "assistant", "content": text, "tool_calls": None}


def T(content, error=False):
    return {"role": "tool", "content": content, "requestor": "assistant", "error": error}


def U(text, tool_calls=None):
    return {"role": "user", "content": text, "tool_calls": tool_calls}


GREET = [A(text="Hi! How can I help you today?"), U("I need help with my order")]


def run(msgs, hashes=None):
    """Evaluate the guard before every decision like replay_episode; hashes: fn(k) or None for constant 'h0'."""
    decs = G.decisions_from_messages(msgs, 1)
    hf = hashes or (lambda k: "h0")
    for n in range(1, len(decs) + 1):
        ev = G.check(decs[:n], hf)
        if ev:
            return n, ev
    return None, None


def tool_loop(k, vary_result=False, vary_id=False):
    m = list(GREET)
    for i in range(k):
        m += [A("get_order_details", {"order_id": f"W{i}" if vary_id else "W1"}), T(f"r{i}" if vary_result else "same")]
    return m


def test_rules():
    R = G.MIN_REPEATS
    n, ev = run(tool_loop(R))
    assert n == R and ev["cycle_len"] == 1 and ev["repeats"] == R, (n, ev)  # fires once 4 copies are complete (greeting excluded, n0=1)
    assert run(tool_loop(R - 1))[0] is None, "R-1 repeats must not fire"
    assert run(tool_loop(2 * R, vary_result=True))[0] is None, "different tool results must not fire"
    assert run(tool_loop(2 * R, vary_id=True))[0] is None, "calls on different IDs must not fire"
    # state changes between repeats (iterative write): DB hash differs
    m = tool_loop(R + 2)
    assert run(m, hashes=lambda k: f"h{k}")[0] is None, "changing DB hash must not fire"
    assert run(m, hashes=lambda k: None)[0] is None, "missing DB hash must not fire"
    # talk loop with identical user replies (L=2: ask + tool), fires; with different user replies, does not
    m = list(GREET)
    for i in range(R + 1):
        m += [A(text="Please give me your zip code."), U("98187")]
    n, ev = run(m)
    assert n is not None and ev["cycle_len"] == 1
    m = list(GREET)
    for i in range(R + 2):
        m += [A(text="Please give me your zip code."), U(f"98187 (attempt {i})")]
    assert run(m)[0] is None, "new user information must not fire"
    # talk decision without its user reply yet: incomplete evidence
    m = list(GREET)
    for i in range(R):
        m += [A(text="Please give me your zip code."), U("98187")]
    m += [A(text="Please give me your zip code.")]
    decs = G.decisions_from_messages(m, 1)
    assert decs[-1]["evidence"] is None
    # cycle of length 2 (lookup, lookup) repeated 4x fires; 4-cycle repeated 4x fires (16 decisions)
    m = list(GREET)
    for i in range(R):
        m += [A("find_user", {"zip": "1"}), T("not found"), A("get_order", {"id": "W1"}), T("error", True)]
    n, ev = run(m)
    assert ev and ev["cycle_len"] == 2 and ev["repeats"] == R
    m = list(GREET)
    for i in range(R):
        for j in range(4):
            m += [A(f"t{j}", {"x": 1}), T("same")]
    n, ev = run(m)
    assert ev and ev["cycle_len"] == 4 and ev["repeats"] == R
    # user-side tool call (dual control) in the span breaks it
    m = list(GREET)
    for i in range(R + 1):
        m += [A(text="Toggle airplane mode."), U("ok", tool_calls=[{"name": "toggle_airplane_mode", "arguments": {}}]),
              {"role": "tool", "content": "done", "requestor": "user", "error": False}]
    assert run(m)[0] is None
    # legitimate multi-item work: same tool on different orders then a write
    m = list(GREET)
    for oid in ("W1", "W2", "W3", "W4", "W5"):
        m += [A("get_order_details", {"order_id": oid}), T(f"order {oid}")]
    assert run(m)[0] is None
    RESULTS["rules"] = "ok"


def test_live_matches_offline():
    """LiveGuard (fake toolkit) fires before the same decision as the offline check with the same hashes."""
    from tau2.data_model.message import AssistantMessage, ToolCall, ToolMessage, UserMessage

    class TK:
        def __init__(self):
            self.h = "db0"

        def get_db_hash(self):
            return self.h

        def get_order_details(self):
            pass

    tk = TK()

    class Tool:
        _func = tk.get_order_details
    os.environ["CLOQ_LOOP_GUARD"] = G.POLICY
    os.environ["CLOQ_LOOP_GUARD_SHA"] = "0" * 64
    try:
        G.LiveGuard([Tool()], None)
        raise AssertionError("unpinned sha accepted")
    except RuntimeError:
        pass
    os.environ["CLOQ_LOOP_GUARD_SHA"] = G.code_sha()
    os.environ.pop("CLOQ_LOOP_GUARD_LOG", None)
    lg = G.LiveGuard([Tool()], None)
    state = [AssistantMessage(role="assistant", content="Hi! How can I help you today?"), UserMessage(role="user", content="help")]
    fired = None
    for d in range(2 * G.MIN_REPEATS):
        out = lg.before_decision(state, "t1", "tr1", d)
        if out is not None:
            fired = d
            assert out.content == G.LOOP_STOP_CONTENT
            break
        state.append(AssistantMessage(role="assistant", content=None,
                                      tool_calls=[ToolCall(id=f"c{d}", name="get_order_details", arguments={"order_id": "W1"})]))
        state.append(ToolMessage(id=f"c{d}", role="tool", content="same", requestor="assistant"))
    assert fired == G.MIN_REPEATS, fired  # R complete identical decisions -> stop before the next one
    msgs = [m.model_dump() for m in state]
    n, ev = run(msgs + [A(text="next")])
    assert n == G.MIN_REPEATS and ev["repeats"] == G.MIN_REPEATS
    os.environ.pop("CLOQ_LOOP_GUARD")
    os.environ.pop("CLOQ_LOOP_GUARD_SHA")
    from cloq.agent import CLOQAgent
    assert CLOQAgent.is_stop(AssistantMessage(role="assistant", content=G.LOOP_STOP_CONTENT))
    assert not CLOQAgent.is_stop(AssistantMessage(role="assistant", content="###STOP###"))
    RESULTS["live_matches_offline"] = {"fired_before_decision_idx": fired}


if __name__ == "__main__":
    test_rules()
    print("ok test_rules")
    test_live_matches_offline()
    print("ok test_live_matches_offline")
    od = ROOT / "tests/out"
    od.mkdir(exist_ok=True)
    (od / "test_loop_guard.json").write_text(json.dumps({**RESULTS, "code_sha256": G.code_sha()}, indent=1))
    print("ALL PASS", G.code_sha()[:16])
