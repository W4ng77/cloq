"""Selftest of the takeover-window controller (cloq/fork.py ForkAgent handback, scripts/a6000/takeover_window.py), CPU only.

A real frozen panel state (manifests/fork/takeover_window_v1.json row, rebuilt from runs/a6k2_q8_bfpair_f01) is run through
fork.run_branch with mock servers: the agent's and the user simulator's `generate` are replaced in-process. The mock agent
writes the api_base it was called with into its message, so the suffix itself shows which server answered each decision.
Its first generated decision carries two parallel tool calls (one decision); the mock user stops after decision G_END.
Checks: switch after exactly L decisions (L = 0, 1, 4; none for inf), a run that ends inside the window is not handed
back, per-branch counters under concurrency (all windows of a state at once, random delays), window_view and
prefix_check on the outputs. Amendment 1: the null gate (B and Q on one service, L = 0, 1, 4, inf identical, switch still
counted), the "attempted handback, generation failed" overflow category, prefix quarantine and the NO PANEL scale rule. run: source scripts/a6000/env.sh; python tests/test_takeover_window.py
"""
from __future__ import annotations

import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts/a6000")]
from cloq import fork as F  # noqa: E402
import takeover_window as TW  # noqa: E402

B, Q = "http://mock-b:1/v1", "http://mock-q:2/v1"
G_END = 7  # the mock user stops after the agent's 7th generated decision of a branch
SEEN = []
LOCK = threading.Lock()


def _gen_index(messages, n_hist_asst):
    return sum(1 for m in messages if getattr(m, "role", None) == "assistant") - n_hist_asst


def install_mocks(n_hist_asst: int) -> None:
    import cloq.agent as A
    import tau2.user.user_simulator as U
    from tau2.data_model.message import AssistantMessage, ToolCall

    def agent_generate(model, messages, tools=None, call_name=None, **kw):
        time.sleep(random.random() * 0.02)
        g = _gen_index(messages, n_hist_asst)  # assistant messages already in the branch = forced + generated so far
        base = kw["api_base"]
        with LOCK:
            SEEN.append(base)
        if g == 1:  # first generated decision: two parallel tool calls = one decision
            tcs = [ToolCall(id=f"c{k}", name="calculate", arguments={"expression": f"{k} + 1"}, requestor="assistant") for k in (1, 2)]
            return AssistantMessage(role="assistant", content=None, tool_calls=tcs, raw_data={})
        return AssistantMessage(role="assistant", content=f"srv={base} g={g}", raw_data={})

    def user_generate(model, messages, tools=None, call_name=None, **kw):
        last = next((m for m in reversed(messages) if getattr(m, "content", None)), None)  # roles are flipped for the user
        txt = getattr(last, "content", "") or ""
        stop = "g=" in txt and int(txt.rsplit("g=", 1)[1]) >= G_END
        return AssistantMessage(role="assistant", content="###STOP###" if stop else "ok, go on", raw_data={})

    A.generate = agent_generate
    U.generate = user_generate


def load_state() -> dict:
    man = json.loads((ROOT / "manifests/fork/takeover_window_v1.json").read_text())
    r = next(x for x in sorted(man["rows"], key=lambda x: x["state_key"]) if x["block"] == "f01" and x["domain"] == "retail"
             and x["n_decisions"] - x["t"] > 2)
    blk = F.Block(ROOT, r["source_run"], r["domain"])
    st = F.make_state(blk, r["task_id"], r["t"])
    st["a_B"] = {"message": st["a_Q"]["message"]}
    if st["a_B"]["message"].get("tool_calls"):  # make the forced action a plain text turn so the user mock answers it
        st["a_B"]["message"] = {**st["a_B"]["message"], "content": "Let me check that.", "tool_calls": None}
    st["a_Q"] = {"message": {**st["a_B"]["message"], "content": "One moment please."}}
    return st


def run_one(st, x, L, q=Q):
    tag = f"selftest-{x}{L}-{random.random()}"
    if L == "inf":
        return F.run_branch(st, x, "B", {"B": B, "Q": q}, "http://mock-user/v1", tag, replay_hash=False)
    return F.run_branch(st, x, "B", {"B": B, "Q": q}, "http://mock-user/v1", tag, replay_hash=False, handback=(L, q))


def servers_in_suffix(r):
    out = []
    for m in r["suffix"][1:]:
        if m["role"] == "assistant":
            out.append("T" if m.get("tool_calls") else m["content"].split()[0][4:])
    return out


def main() -> None:
    from loguru import logger

    logger.remove()
    F.setup_tau2()
    st = load_state()
    n_hist_asst = sum(1 for m in st["history"] if m["role"] == "assistant")
    install_mocks(n_hist_asst)
    cases = [(x, L) for x in ("B", "Q") for L in (0, 1, 4, 6, 8, "inf")]
    with ThreadPoolExecutor(len(cases)) as ex:  # every window of the state at once: per-agent counters must stay apart
        res = dict(zip(cases, ex.map(lambda c: run_one(st, *c), cases)))
    for (x, L), r in res.items():
        assert "error" not in r, (x, L, r.get("error"))
        ds = r["decisions"]
        cont = [d for d in ds if not d["forced"]]
        assert ds[0]["forced"] and sum(d["forced"] for d in ds) == 1
        assert len(cont) == G_END, (x, L, len(cont))  # decision 1 (two tool calls) counts once
        assert sum(1 for m in r["suffix"] if m["role"] == "assistant" and len(m.get("tool_calls") or []) == 2) == 1
        Ln = G_END + 1 if L == "inf" else L
        want = [B if i < Ln else Q for i in range(G_END)]
        assert [d["api_base"] for d in cont] == want, (x, L, [d["api_base"] for d in cont])
        txt = servers_in_suffix(r)  # what the mock server itself saw (independent of the agent's bookkeeping)
        assert [t for t in txt if t != "T"] == [w for i, w in enumerate(want) if i != 0], (x, L, txt)
        if L != "inf":
            v = TW.window_view(r, L, {"B": B, "Q": Q})
            assert v["pattern_ok"] and v["counter_ok"], (x, L, v)
            assert v["n_B"] == min(L, G_END) and v["handed_back"] == (L < G_END), (x, L, v)
            assert (r["window"]["switch_decision_idx"] is None) == (L >= G_END)
    # prefix_check: each window equals the inf run up to the switch; a run ending inside the window equals it as a whole
    for x in ("B", "Q"):
        ref = {"kind": "inf", "suffix_sha": res[(x, "inf")]["suffix_sha"],
               "decisions": [(d["prompt_ids_sha"], d["completion_ids_sha"]) for d in res[(x, "inf")]["decisions"]]}
        for L in (0, 1, 4, 6, 8):
            pc = TW.prefix_check(res[(x, L)], ref, L)
            assert pc["ok"], (x, L, pc)  # Q's first request carries the same prompt as the reference's decision L+1
            assert pc["ended_in_window"] == (L >= G_END)
        assert TW.prefix_check(res[(x, 8)], ref, 8)["ok"]
    # negative controls: a different current action breaks the prefix; a wrong L breaks the counter/pattern checks
    refB = {"kind": "inf", "suffix_sha": res[("B", "inf")]["suffix_sha"],
            "decisions": [(d["prompt_ids_sha"], d["completion_ids_sha"]) for d in res[("B", "inf")]["decisions"]]}
    assert TW.prefix_check(res[("Q", 4)], refB, 4)["bad"][0] == "prompt1"
    v = TW.window_view(res[("B", 4)], 1, {"B": B, "Q": Q})
    assert v["pattern_ok"] is False and v["counter_ok"] is False
    # context overflow at Q's first request (switch set, n_cont == L) or before it (no switch): both are valid outcomes
    ds = [{"decision_idx": 10, "forced": True}] + [{"decision_idx": 11 + i, "forced": False} for i in range(4)]
    for sw in (15, None):
        r = {"infra_cause": "context_overflow", "decisions": ds, "window": {"L": 4, "n_cont": 4, "switch_decision_idx": sw}}
        v = TW.window_view(r, 4, {"B": B, "Q": Q})
        assert v["counter_ok"] and not v["handed_back"] and v["attempted_handback"] == (sw is not None), (sw, v)
    r = {"decisions": ds, "window": {"L": 4, "n_cont": 4, "switch_decision_idx": 15}}  # without overflow: inconsistent
    assert TW.window_view(r, 4, {"B": B, "Q": Q})["counter_ok"] is False
    # amendment 1: overflow at Q's first request is its own category and does not break the prefix check
    r = {"infra_cause": "context_overflow", "suffix_sha": None, "decisions": [{**d, "prompt_ids_sha": a, "completion_ids_sha": c}
         for d, (a, c) in zip(ds, refB["decisions"])], "window": {"L": 4, "n_cont": 4, "switch_decision_idx": 15}}
    assert TW.window_view(r, 4, {"B": B, "Q": Q})["overflow"] == "attempted_handback_generation_failed"
    assert TW.prefix_check(r, refB, 4)["ok"] is True
    r["window"]["switch_decision_idx"] = None  # overflow at a B request inside the window, absent from the reference
    assert TW.prefix_check(r, refB, 4)["bad"] == ["overflow_in_window_not_in_reference"]
    assert TW.window_view(r, 4, {"B": B, "Q": Q})["overflow"] == "overflow_before_handback"
    # amendment 1 item 4: a prefix mismatch is quarantined with a diagnosis; a clean prefix is not
    qz = TW.quarantine(TW.prefix_check(res[("Q", 4)], refB, 4), "Q", 4)
    assert qz["diagnosis"] == "observation_or_simulator" and "curve_Q_all_L" in qz["excluded"], qz
    assert TW.quarantine(TW.prefix_check(res[("B", 4)], refB, 4), "B", 4) is None
    # amendment 1 item 1: null gate, both controllers on one service; every L identical, the switch still counted
    nul = {"R_Binf" if L == "inf" else ("R_B0" if L == 0 else f"W_B{L}"): run_one(st, "B", L, q=B) for L in (0, 1, 4, "inf")}
    assert not any(TW.null_identity(nul, [1, 4]).values()), TW.null_identity(nul, [1, 4])
    for L in (0, 1, 4):
        v = TW.window_view(nul["R_B0" if L == 0 else f"W_B{L}"], L, {"B": B, "Q": B})
        assert v["counter_ok"] and v["handed_back"] and v["switch_decision_idx"] == st["decision_idx"] + 1 + L, (L, v)
    neg = TW.null_identity({**nul, "W_B4": res[("B", 4)]}, [1, 4])  # negative control: a real Q after the switch differs
    assert neg["4"] and not neg["1"], neg
    # amendment 1 item 4: NO PANEL when even 3 blocks miss the deadline under the throughput rule
    import make_tasks_takeover as MK
    now = MK.DEADLINE - MK.dt.timedelta(hours=10)
    g = {c: {"overhead_h": 0.1, "block_h": 1.0, "endpoint_block_h": 0.5} for c in MK.CELLS}
    assert MK.plan_scale(g, 4, now)[1] == 6
    assert MK.plan_scale({c: {**g[c], "block_h": 2.0} for c in g}, 2, now)[1] == 3
    assert MK.plan_scale({c: {**g[c], "block_h": 5.0} for c in g}, 2, now)[1] == 0
    assert TW.raw_key({"content": None, "tool_calls": [{"name": "f", "arguments": {"a": 1, "b": 2}}]}) != \
        TW.raw_key({"content": None, "tool_calls": [{"name": "f", "arguments": {"b": 2, "a": 1}}]})
    print(json.dumps({"selftest": "ok", "state": st["state_id"], "n_branches": len(res), "n_calls": len(SEEN)}))


if __name__ == "__main__":
    main()
