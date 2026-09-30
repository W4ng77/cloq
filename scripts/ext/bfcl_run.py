"""BFCL v3 multi-turn adapter: one category of a fixed manifest subset against the CLOQ agent server.

Inference is BFCL's own `BaseHandler.inference_multi_turn_FC` loop (final, unchanged): per user turn the model is
queried until it returns no decodable function call, at most MAXIMUM_STEP_LIMIT (20) steps per turn (then the
entry is force-quit); miss_func holdout functions are added by the loop at their turn. The handler is BFCL's
OpenAICompletionsHandler (FC mode) with four overrides that only change transport and logging:
  _query_FC                  POST /v1/chat/completions to the CLOQ vLLM server with the frozen decoding
                             (scripts/ext/common.py) instead of the OpenAI SDK; logs the decision record;
  _parse_query_response_FC   same fields as the official method, read from the raw JSON response;
  _add_assistant_message_FC  appends {role, content, tool_calls} (the SDK message object minus server extras);
  _add_execution_results_FC  official method, plus the tool outputs are attached to the decision record.
Evaluation is the official per-entry multi-turn evaluator (eval_runner._evaluate_single_multi_turn_entry:
decode_execute + multi_turn_checker state and response checks), on entries loaded exactly as the official
evaluation loads them. Inference errors are recorded as BFCL records them ("Error during inference: ...").

usage (bfcl venv): python scripts/ext/bfcl_run.py --run-id X --arm bf16 --domain bfcl_base \
    --manifest manifests/bfcl/bfcl_mt_v1.json --subset smoke --agent-base http://127.0.0.1:8001/v1
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, ChatError, RunDir, assistant_history_message, chat, common_args, decision_record, summarize, write_headers  # noqa: E402

from bfcl_eval.constants.default_prompts import MAXIMUM_STEP_LIMIT  # noqa: E402
from bfcl_eval.constants.enums import ModelStyle  # noqa: E402
from bfcl_eval.eval_checker.eval_runner import _evaluate_single_multi_turn_entry  # noqa: E402
from bfcl_eval.model_handler.api_inference.openai_completion import OpenAICompletionsHandler  # noqa: E402
from bfcl_eval.model_handler.base_handler import BaseHandler  # noqa: E402
from bfcl_eval.utils import load_dataset_entry, load_ground_truth_entry, make_json_serializable  # noqa: E402

MODEL_NAME = "cloq_agent"  # BFCL uses it only to name the per-entry backend instances


class CloqFCHandler(OpenAICompletionsHandler):
    def __init__(self, base: str, meta: dict, task_id: str):
        BaseHandler.__init__(self, MODEL_NAME, 0.0, MODEL_NAME + "-FC", True)  # no OpenAI client
        self.model_style = ModelStyle.OPENAI_COMPLETIONS
        self.base, self.meta, self.task_id = base, meta, task_id
        self.trajectory_id = str(uuid.uuid4())
        self.decisions: list[dict] = []
        self.pending: dict | None = None
        self.turn, self.step = -1, 0
        self.history: list[dict] | None = None

    def _flush(self):
        if self.pending is not None:
            self.decisions.append(self.pending)
            self.pending = None

    def add_first_turn_message_FC(self, inference_data, first_turn_message):
        self.turn, self.step = self.turn + 1, 0
        return super().add_first_turn_message_FC(inference_data, first_turn_message)

    def _add_next_turn_user_message_FC(self, inference_data, user_message):
        self.turn, self.step = self.turn + 1, 0
        return super()._add_next_turn_user_message_FC(inference_data, user_message)

    def _query_FC(self, inference_data: dict):
        self._flush()
        self.history = inference_data["message"]
        messages, tools = list(inference_data["message"]), inference_data["tools"]
        raw, dt = chat(self.base, messages, tools)
        rec = decision_record(self.meta, self.task_id, self.trajectory_id, len(self.decisions), messages, tools, raw, dt)
        names = [t["function"]["name"] for t in tools]
        tcs = rec["tool_calls"] or []
        rec.update(turn_idx=self.turn, step_idx=self.step, available_tools=names,
                   actions_known_tool=[tc["function"]["name"] in names for tc in tcs])
        mr = self._parse_query_response_FC(raw)["model_responses"]
        try:
            rec["parsed_actions"], rec["decode_error"] = self.decode_execute(mr, has_tool_call_tag=False), None
        except Exception as e:
            rec["parsed_actions"], rec["decode_error"] = None, repr(e)[:500]
        rec["observations"] = None
        self.pending = rec
        self.step += 1
        return raw, dt

    def _parse_query_response_FC(self, raw: dict) -> dict:
        msg = raw["choices"][0]["message"]
        tcs = msg.get("tool_calls")
        if tcs is None:  # the official method falls back to content when tool_calls is None
            model_responses, ids = msg.get("content"), []
        else:
            model_responses = [{tc["function"]["name"]: tc["function"]["arguments"]} for tc in tcs]
            ids = [tc["id"] for tc in tcs]
        usage = raw.get("usage") or {}
        return {"model_responses": model_responses, "model_responses_message_for_chat_history": assistant_history_message(raw),
                "tool_call_ids": ids, "input_token": usage.get("prompt_tokens"), "output_token": usage.get("completion_tokens")}

    def _add_assistant_message_FC(self, inference_data, model_response_data):
        inference_data["message"].append(model_response_data["model_responses_message_for_chat_history"])
        return inference_data

    def _add_execution_results_FC(self, inference_data, execution_results, model_response_data):
        if self.pending is not None:
            self.pending["observations"] = list(execution_results)
        return super()._add_execution_results_FC(inference_data, execution_results, model_response_data)


def run_item(entry: dict, prompt_entry: dict, gt: list, category: str, base: str, meta: dict) -> tuple[dict, list[dict]]:
    h = CloqFCHandler(base, meta, entry["id"])
    t0 = time.time()
    term, err = "completed", None
    try:
        result, md = h.inference_multi_turn_FC(entry, include_input_log=False, exclude_state_log=False)
        if len(result) != len(gt):
            term = "force_quit"  # > MAXIMUM_STEP_LIMIT steps in one turn
    except ChatError as e:
        if e.kind == "outage":
            raise
        term, err = e.kind, str(e)[:2000]
        result, md = f"Error during inference: {e}", {"traceback": traceback.format_exc()[-4000:]}
    h._flush()
    infer_s = time.time() - t0
    ev = _evaluate_single_multi_turn_entry(h, entry["id"], result, gt, copy.deepcopy(prompt_entry), MODEL_NAME, category)
    ok = bool(ev.get("valid"))
    traj = {
        "task_id": entry["id"], "trajectory_id": h.trajectory_id, "test_category": category,
        "termination_reason": term, "error": err, "success": ok, "reward": 1.0 if ok else 0.0,
        "evaluator": {k: v for k, v in ev.items() if k not in ("prompt", "possible_answer", "inference_log")},
        "n_decisions": len(h.decisions), "n_turns_ground_truth": len(gt),
        "n_turns_run": len(result) if isinstance(result, list) else 0,
        "messages": h.history or [], "bfcl_result": make_json_serializable(result), "bfcl_metadata": make_json_serializable(md),
        "duration": time.time() - t0, "inference_seconds": infer_s,
    }
    return traj, h.decisions


def main():
    ap = argparse.ArgumentParser()
    common_args(ap)
    args = ap.parse_args()
    assert args.domain.startswith("bfcl_"), args.domain
    cat = args.domain[len("bfcl_"):]
    mpath = (ROOT / args.manifest).resolve()
    man = json.load(open(mpath))["categories"][cat]
    category = man["test_category"]
    ids = args.subset[4:].split(",") if args.subset.startswith("ids:") else man[args.subset]
    if args.limit:
        ids = ids[:args.limit]
    rd = RunDir(args.run_id, args.domain)
    if rd.completed():
        print(f"{rd.dir} already completed; skipping")
        return
    rd.prune_partial()
    bench = {"env": "bfcl", "name": "BFCL v3 multi-turn", "test_category": category, "max_steps_per_turn": MAXIMUM_STEP_LIMIT,
             "handler": "OpenAICompletionsHandler FC (transport/logging overrides only, see scripts/ext/bfcl_run.py)",
             "evaluator": "eval_runner._evaluate_single_multi_turn_entry (official)", "exclude_state_log": False}
    write_headers(rd, args, bench, ids, ["bfcl-eval", "openai", "numpy", "pydantic"], mpath)
    t_start = time.time()
    rd.write_json("status.json", {"status": "running", "started": time.strftime("%FT%TZ", time.gmtime()), "n_tasks": len(ids)})

    entries = {e["id"]: e for e in load_dataset_entry(category)}  # as the official generation loads them
    prompts = {e["id"]: e for e in load_dataset_entry(category, include_prereq=False, include_language_specific_hint=False)}
    gts = {e["id"]: e["ground_truth"] for e in load_ground_truth_entry(category)}
    todo = [i for i in ids if i not in rd.done_items()]
    meta = {"run_id": args.run_id, "arm": args.arm, "domain": args.domain}
    real_stdout, n_outage = sys.stdout, 0
    sys.stdout = open(os.devnull, "w")  # BFCL's loop prints every step
    try:
        with ThreadPoolExecutor(max_workers=args.max_concurrency) as ex:
            futs = {ex.submit(run_item, copy.deepcopy(entries[i]), prompts[i], gts[i], category, args.agent_base, meta): i for i in todo}
            for f in as_completed(futs):
                try:
                    traj, decs = f.result()
                except Exception as e:
                    n_outage += 1
                    print(f"[bfcl] {futs[f]} failed: {e!r}", file=sys.stderr, flush=True)
                    continue
                rd.write_item(traj, decs)
                print(f"[bfcl] {traj['task_id']} success={traj['success']} term={traj['termination_reason']} "
                      f"dec={traj['n_decisions']} {traj['duration']:.0f}s", file=sys.stderr, flush=True)
    finally:
        sys.stdout = real_stdout
    m = summarize(rd, {"benchmark": "bfcl_multi_turn", "test_category": category, "n_outage_items": n_outage,
                       "termination_reasons_note": "force_quit = >20 steps in a turn; context_overflow = prompt beyond the served context"})
    if n_outage:
        m["termination_reasons"]["infrastructure_error"] = n_outage
    rd.write_json("metrics.json", m)
    done = rd.done_items()
    rd.write_json("status.json", {"status": "completed" if all(i in done for i in ids) else "incomplete",
                                  "finished": time.strftime("%FT%TZ", time.gmtime()), "elapsed_seconds": time.time() - t_start,
                                  "n_tasks": len(ids), "n_simulations": len(done)})
    print(json.dumps({k: v for k, v in m.items() if k != "per_item"}))
    if n_outage:
        sys.exit(2)


if __name__ == "__main__":
    main()
