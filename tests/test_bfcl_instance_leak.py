"""Regression test for the BFCL per-branch instance-name leak (W99f finding, W99g fix in scripts/ext/bfcl_run.py).

Fork branches run BFCL entries under model names "cf_<12 hex>" (scripts/ext/fork_ext.py run_env). BFCL's call rewriter
prefixes every `name(` with the instance name, also inside string arguments, so a call such as
get_order_details(order_id="get_order_history()[0]") (Llama-3.1-8B, multi_turn_base_126, W99f gate) produced an error
observation that contained the branch's own name: two branches of one state saw different text.

The test replays scripted agent responses (no server, CPU only) through the adapter's own episode code
(bfcl_run.run_item, the code path of every fork branch) under the canonical name and two branch names, and checks
  1. with the fix switched off the leak reproduces (the branch observations differ and contain the branch name);
  2. with the fix every observation, every prompt sent to the agent and the backend-state hash before every decision
     are byte-identical across the canonical run and both branches, and no observation contains a branch name;
  3. a string argument that is stored in backend state (GorillaFileSystem touch, echo -> cat) also stays branch-independent;
  4. the official outcome (success, bfcl_result) is unchanged;
  5. (restoration fix found by the same gate) long-context backend constants are not aliased into instance state, so a
     booking in one episode cannot change the initial state of the next one in the same process.

run (bfcl venv): /data/ziyangs/cloq_work/envs/bfcl/bin/python tests/test_bfcl_instance_leak.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ext"))
import bfcl_run as BR  # noqa: E402
from bfcl_eval.utils import load_dataset_entry, load_ground_truth_entry  # noqa: E402

BRANCHES = ("cf_0123456789ab", "cf_fedcba987654")


def _sha(x) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()


def call(name: str, args: dict, i: int) -> dict:
    tc = {"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
    return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [tc]}, "token_ids": [i],
                         "finish_reason": "tool_calls"}], "prompt_token_ids": [0], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


def text(s: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": s, "tool_calls": None}, "token_ids": [1],
                         "finish_reason": "stop"}], "prompt_token_ids": [0], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


class Scripted:
    """Turn 0: the scripted tool calls, then a text reply; every later turn: a text reply."""

    def __init__(self, calls):
        self.calls, self.state_sha = calls, None

    def __call__(self, idx, messages, tools):
        if idx < len(self.calls):
            return call(*self.calls[idx], idx), 0.0
        return text("done"), 0.0


def run(category: str, item: str, calls, model_name: str):
    E = {e["id"]: e for e in load_dataset_entry(category)}
    P = {e["id"]: e for e in load_dataset_entry(category, include_prereq=False, include_language_specific_hint=False)}
    G = {e["id"]: e["ground_truth"] for e in load_ground_truth_entry(category)}
    meta = {"run_id": "test", "arm": "test", "domain": "bfcl_" + category[len("multi_turn_"):]}
    traj, decs = BR.run_item(copy.deepcopy(E[item]), P[item], G[item], category, None, meta, policy=Scripted(calls),
                             model_name=model_name, track_state=True)
    return {"obs": [d["observations"] for d in decs], "msgs": [_sha(d["messages"]) for d in decs],
            "state": [d["state_sha_before"] for d in decs], "success": traj["success"],
            "result": _sha(traj["bfcl_result"]), "final_state": traj["final_state_sha"]}


Q4_RUN = ROOT / "runs/ext_q4_bf16_bfcl_eval/bfcl_long_context"
L8_RUN = ROOT / "runs/ext_l8_bf16_bfcl_smoke_l8g_sc/bfcl_base"


def replay_recorded(recs, model_name):
    class P:
        state_sha = None

        def __call__(self, idx, messages, tools):
            r = recs[idx]
            return {"choices": [{"message": {"role": "assistant", "content": r["raw_content"], "tool_calls": r["tool_calls"]},
                                 "token_ids": r["completion_token_ids"], "finish_reason": r["finish_reason"]}],
                    "prompt_token_ids": r["prompt_token_ids"],
                    "usage": {"prompt_tokens": r["n_prompt_tokens"], "completion_tokens": r["n_completion_tokens"]}}, 0.0
    cat = "multi_turn_base"
    E = {e["id"]: e for e in load_dataset_entry(cat)}
    P_ = {e["id"]: e for e in load_dataset_entry(cat, include_prereq=False, include_language_specific_hint=False)}
    G = {e["id"]: e["ground_truth"] for e in load_ground_truth_entry(cat)}
    i = "multi_turn_base_126"
    _, decs = BR.run_item(copy.deepcopy(E[i]), P_[i], G[i], cat, None, {"run_id": "t", "arm": "t", "domain": "bfcl_base"},
                          policy=P(), model_name=model_name, track_state=True)
    return [d["observations"] for d in decs]


TRADING = ("multi_turn_base", "multi_turn_base_126",
           [("get_order_details", {"order_id": "get_order_history()[0]"}), ("cancel_order", {"order_id": "get_order_history()[1]"})])
FILES = ("multi_turn_base", "multi_turn_base_1",
         [("touch", {"file_name": "leak.txt"}), ("echo", {"content": "see ls() and pwd()", "file_name": "leak.txt"}),
          ("cat", {"file_name": "leak.txt"})])


class InstanceLeak(unittest.TestCase):
    def tearDown(self):
        BR.CANON_BRANCH_NAMES = True

    def _check(self, case):
        cat, item, calls = case
        canon = run(cat, item, calls, BR.MODEL_NAME)
        brs = [run(cat, item, calls, b) for b in BRANCHES]
        for b, r in zip(BRANCHES, brs):
            self.assertEqual(r["obs"], canon["obs"], f"observations differ for branch {b}")
            self.assertNotIn("cf_", json.dumps(r["obs"]))
            self.assertEqual(r["msgs"], canon["msgs"], "prompts sent to the agent differ")
            self.assertEqual(r["state"], canon["state"], "backend-state hash differs")
            self.assertEqual(r["final_state"], canon["final_state"])
            self.assertEqual((r["success"], r["result"]), (canon["success"], canon["result"]))
        return canon

    def test_trading_call_expression_leak_reproduces_without_fix(self):
        BR.CANON_BRANCH_NAMES = False
        cat, item, calls = TRADING
        a, b = (run(cat, item, calls, x) for x in BRANCHES)
        self.assertNotEqual(a["obs"], b["obs"])
        self.assertIn(BRANCHES[0] + "_multi_turn_base_126_TradingBot_instance.get_order_history()[0]", json.dumps(a["obs"]))

    def test_trading_call_expression_fixed(self):
        canon = self._check(TRADING)
        self.assertIn("cloq_agent_multi_turn_base_126_TradingBot_instance.get_order_history()[0]", json.dumps(canon["obs"]))

    def test_filesystem_stored_string_leak_reproduces_without_fix(self):
        BR.CANON_BRANCH_NAMES = False
        cat, item, calls = FILES
        a, b = (run(cat, item, calls, x) for x in BRANCHES)
        self.assertNotEqual(a["obs"], b["obs"])
        self.assertNotEqual(a["state"], b["state"])

    def test_filesystem_stored_string_fixed(self):
        self._check(FILES)

    def test_canonical_is_identity(self):
        s = "cloq_agent_multi_turn_base_126_TradingBot_instance.get_order_history()[0]"
        self.assertEqual(BR.canon_instance_names(s), s)
        self.assertEqual(BR._canon_string_literals(f"f(x='{s}')"), f"f(x='{s}')")
        unreg = "cf_aaaaaaaaaaaa_multi_turn_base_1_X_instance"  # never registered: left alone
        self.assertEqual(BR.canon_instance_names(unreg), unreg)

    @unittest.skipUnless((L8_RUN / "decisions.jsonl").exists(), "recorded W99f l8 run not on this machine")
    def test_recorded_l8_base_126(self):
        """The exposed case itself: replay the recorded Llama-3.1-8B base_126 episode (W99f smoke, every decision forced
        to the recorded response) under two branch names; observations must equal the recorded canonical bytes."""
        recs = sorted((json.loads(x) for x in (L8_RUN / "decisions.jsonl").read_text().splitlines()
                       if x.strip() and json.loads(x)["task_id"] == "multi_turn_base_126"), key=lambda r: r["decision_idx"])
        rec_obs = [r["observations"] for r in recs]
        self.assertTrue(any("cloq_agent_multi_turn_base_126_TradingBot_instance" in json.dumps(o) for o in rec_obs))
        got = {}
        for fix in (False, True):
            BR.CANON_BRANCH_NAMES = fix
            got[fix] = [replay_recorded(recs, b) for b in BRANCHES]
        self.assertNotEqual(got[False][0], got[False][1])  # the leak, as W99f saw it
        for o in got[True]:
            self.assertEqual(o, rec_obs)

    def test_long_context_shared_state_unaliased(self):
        """W99g restoration fix: TravelAPI long-context cards are module constants aliased into instance state; a booking
        in one episode must not change the next episode's initial state (without the fix it does)."""
        from bfcl_eval.eval_checker.multi_turn_eval.func_source_code import long_context as LC
        from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.travel_booking import TravelAPI
        card = next(iter(LC.CREDIT_CARD_EXTENSION))
        pristine = copy.deepcopy(LC.CREDIT_CARD_EXTENSION[card])
        cfg = {"access_token": "tok", "budget_limit": 0.0}

        def episode():
            t = TravelAPI()
            t._load_scenario(copy.deepcopy(cfg), long_context=True)
            before = t.credit_card_list[card]["balance"]
            t.credit_card_list[card]["balance"] -= 100.0  # what book_flight does on success
            return before
        try:
            BR._UNALIAS = False
            a, b = episode(), episode()
            self.assertEqual(b, a - 100.0)  # contamination reproduces without the fix
        finally:
            LC.CREDIT_CARD_EXTENSION[card].clear()
            LC.CREDIT_CARD_EXTENSION[card].update(pristine)
            BR._UNALIAS = True
        a, b = episode(), episode()
        self.assertEqual(a, b)
        self.assertEqual(LC.CREDIT_CARD_EXTENSION[card], pristine)

    @unittest.skipUnless((Q4_RUN / "decisions.jsonl").exists(), "recorded q4 BFCL eval not on this machine")
    def test_recorded_q4_long_context_180_twice(self):
        """The case the W99g Qwen replay check exposed: replaying the recorded q4 BF16 long_context_180 episode twice in one
        process; the second replay must still reproduce the recorded observations."""
        import fork_ext as F
        blk = F.load_block("ext_q4_bf16_bfcl_eval", "bfcl_long_context")
        it = "multi_turn_long_context_180"
        recs = blk["decs"][it]

        class Pol:
            state_sha = None

            def __call__(self, idx, messages, tools):
                return F.raw_from_rec(recs[idx]), 0.0
        rec_obs = [r["observations"] for r in recs]
        for k in range(2):
            _, decs = F.run_env("bfcl", "bfcl_long_context", it, Pol(), f"t180|{k}")
            self.assertEqual([d["observations"] for d in decs], rec_obs, f"replay {k}")

    def test_branch_name_format_enforced(self):
        cat, item, calls = TRADING
        with self.assertRaises(ValueError):
            run(cat, item, calls, "some_other_name")


if __name__ == "__main__":
    unittest.main(verbosity=2)
