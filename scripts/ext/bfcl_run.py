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
import re
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ROOT, ChatError, RunDir, assistant_history_message, canonical_json, chat, common_args, decision_record,  # noqa: E402
                    sha256_text, summarize, write_headers)  # noqa: E402

from bfcl_eval.constants.default_prompts import MAXIMUM_STEP_LIMIT  # noqa: E402
from bfcl_eval.constants.enums import ModelStyle  # noqa: E402
from bfcl_eval.eval_checker.eval_runner import _evaluate_single_multi_turn_entry  # noqa: E402
from bfcl_eval.model_handler.api_inference.openai_completion import OpenAICompletionsHandler  # noqa: E402
from bfcl_eval.model_handler.base_handler import BaseHandler  # noqa: E402
from bfcl_eval.utils import load_dataset_entry, load_ground_truth_entry, make_json_serializable  # noqa: E402

MODEL_NAME = "cloq_agent"  # BFCL uses it only to name the per-entry backend instances

# W99g: per-branch instance-name leak. Fork branches (scripts/ext/fork_ext.py run_env) run under model names
# "cf_<12 hex>" so that concurrent branches of one entry get separate backend instances. BFCL's call rewriter
# (multi_turn_utils._process_method_calls) prefixes every `name(` with the instance name, including inside string
# arguments: order_id='get_order_history()[0]' becomes '<model>_<entry>_TradingBot_instance.get_order_history()[0]',
# and that text reaches the error message the agent sees (W99f, l8 base_126) or can be stored in backend state.
# Fix: the instance-name prefix of a registered branch name is mapped back to the canonical MODEL_NAME (a) inside the
# string literals of rewritten calls and (b) in the execution results the agent sees. Live runs (MODEL_NAME) never
# register a name, so both steps are the identity there; fork branches then see exactly what MODEL_NAME would show.
BRANCH_NAME_RE = re.compile(r"cf_[0-9a-f]{12}")
_BRANCH_NAMES: set[str] = set()
CANON_BRANCH_NAMES = True  # tests/test_bfcl_instance_leak.py switches it off to reproduce the leak
_INST_RE = re.compile(r"(?<![A-Za-z0-9_])(cf_[0-9a-f]{12})_(?=\w*_instance\b)")


def canon_instance_names(s):
    """Replace a registered fork-branch model-name prefix of BFCL instance names by MODEL_NAME (identity otherwise)."""
    if not CANON_BRANCH_NAMES or not isinstance(s, str) or "_instance" not in s:
        return s
    return _INST_RE.sub(lambda m: MODEL_NAME + "_" if m.group(1) in _BRANCH_NAMES else m.group(0), s)


def _canon_string_literals(code: str) -> str:
    """canon_instance_names applied only inside the string literals of a rewritten call (the call targets keep the
    branch's own instance). Unparsable code is returned unchanged (eval then fails with a SyntaxError that quotes no
    source text)."""
    import io
    import tokenize
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return code
    starts, pos = [], 0
    for line in io.StringIO(code).readlines():
        starts.append(pos)
        pos += len(line)
    kinds = {tokenize.STRING} | ({tokenize.FSTRING_MIDDLE} if hasattr(tokenize, "FSTRING_MIDDLE") else set())
    out, last = [], 0
    for tk in toks:
        if tk.type in kinds and "_instance" in tk.string:
            a = starts[tk.start[0] - 1] + tk.start[1]
            b = starts[tk.end[0] - 1] + tk.end[1]
            out += [code[last:a], canon_instance_names(code[a:b])]
            last = b
    return "".join(out) + code[last:] if out else code


def _install_rewriter_patch():
    import bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils as MU
    if getattr(MU._process_method_calls, "_cloq_canon", False):
        return
    orig = MU._process_method_calls

    def _process_method_calls(function_call_string, instance_mapping):
        out = orig(function_call_string, instance_mapping)
        return _canon_string_literals(out) if CANON_BRANCH_NAMES and _BRANCH_NAMES else out

    _process_method_calls._cloq_canon = True
    MU._process_method_calls = _process_method_calls


_install_rewriter_patch()

# W99g: shared-state restoration fix. Some BFCL backends alias module-level constants into instance state when they load
# a scenario: TravelAPI._load_scenario(long_context=True) inserts the CREDIT_CARD_EXTENSION / BOOKING_RECORD_EXTENSION
# dicts by reference, and book_flight then decrements `balance` inside the shared constant. Every later TravelAPI
# instance in the process (another item of a concurrent eval, another fork branch, the evaluator's instances) then
# starts from a mutated card list, so a restored state depends on what ran before in the process. Fix: right after
# _load_scenario each backend instance gets a private deep copy of its own attributes (one deepcopy call, so internal
# sharing such as GorillaFileSystem's root/_current_dir is kept). The loaded values are unchanged; only the aliasing of
# module constants is cut. Episodes that never mutate an aliased constant behave byte-identically.
MULTI_TURN_CLASSES = ("GorillaFileSystem", "MathAPI", "MessageAPI", "TicketAPI", "TradingBot", "TravelAPI", "TwitterAPI",
                      "VehicleControlAPI")  # every involved_classes value of the four multi_turn categories
_UNALIAS = True  # tests/test_bfcl_instance_leak.py switches it off to reproduce the contamination


def _install_unalias_patch():
    import importlib
    from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING
    for cname in MULTI_TURN_CLASSES:  # never import the memory/web backends (memory_vector loads an encoder at import)
        cls = getattr(importlib.import_module(CLASS_FILE_PATH_MAPPING[cname]), cname)
        orig = cls.__dict__.get("_load_scenario")
        if orig is None or getattr(orig, "_cloq_unalias", False):
            continue

        def _load_scenario(self, *a, _orig=orig, **k):
            r = _orig(self, *a, **k)
            if _UNALIAS:
                self.__dict__.update(copy.deepcopy(self.__dict__))
            return r

        _load_scenario._cloq_unalias = True
        cls._load_scenario = _load_scenario


_install_unalias_patch()


def state_sha(model_name_u: str, test_entry_id: str) -> str:
    """Hash of the live backend instances of one entry (fork replay fidelity; scripts/ext/fork_ext.py)."""
    import bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils as MU
    pre = re.sub(r"[-./:]", "_", f"{model_name_u}_{test_entry_id}_")
    objs = {k[len(pre):]: v for k, v in list(vars(MU).items()) if k.startswith(pre) and k.endswith("_instance")}
    return sha256_text(canonical_json(canon(objs)))


def canon(o, seen=None):
    """Deterministic plain-data view of backend state (no memory addresses; parent back-references and cycles cut)."""
    seen = set() if seen is None else seen
    if o is None or isinstance(o, (bool, int, float, str)):
        return o
    if isinstance(o, dict):
        return {str(k): canon(v, seen) for k, v in sorted(o.items(), key=lambda kv: str(kv[0]))}
    if isinstance(o, (list, tuple)):
        return [canon(v, seen) for v in o]
    if isinstance(o, (set, frozenset)):
        return sorted((canon(v, seen) for v in o), key=lambda x: json.dumps(x, sort_keys=True, default=str))
    if hasattr(o, "__dict__"):
        if id(o) in seen:
            return "<cycle>"
        seen = seen | {id(o)}
        d = {"__cls__": type(o).__name__, **{k: canon(v, seen) for k, v in sorted(vars(o).items())
                                              if not k.startswith("_") and k != "parent"}}
        if hasattr(o, "_random") and hasattr(o._random, "getstate"):  # seeded backend RNG: its position is state too
            d["_random"] = sha256_text(repr(o._random.getstate()))
        return d
    return repr(o) if " at 0x" not in repr(o) else type(o).__name__


class CloqFCHandler(OpenAICompletionsHandler):
    def __init__(self, base: str, meta: dict, task_id: str, policy=None, model_name: str = MODEL_NAME, track_state: bool = False):
        BaseHandler.__init__(self, model_name, 0.0, model_name + "-FC", True)  # no OpenAI client
        self.policy, self.track_state = policy, track_state  # fork replay (scripts/ext/fork_ext.py); None = live agent
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
        ssha = state_sha(self.model_name_underline_replaced, self.task_id) if self.track_state else None
        if self.policy is not None:
            self.policy.state_sha = ssha  # fork search freezes the backend-state hash at the divergence
            raw, dt = self.policy(len(self.decisions), messages, tools)
        else:
            raw, dt = chat(self.base, messages, tools)
        rec = decision_record(self.meta, self.task_id, self.trajectory_id, len(self.decisions), messages, tools, raw, dt)
        names = [t["function"]["name"] for t in tools]
        tcs = rec["tool_calls"] or []
        rec.update(turn_idx=self.turn, step_idx=self.step, available_tools=names,
                   actions_known_tool=[tc["function"]["name"] in names for tc in tcs])
        if self.track_state:
            rec["state_sha_before"] = ssha
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
        execution_results = [canon_instance_names(x) for x in execution_results]  # W99g; identity for MODEL_NAME
        if self.pending is not None:
            self.pending["observations"] = list(execution_results)
        return super()._add_execution_results_FC(inference_data, execution_results, model_response_data)


def run_item(entry: dict, prompt_entry: dict, gt: list, category: str, base: str, meta: dict, policy=None,
             model_name: str = MODEL_NAME, track_state: bool = False) -> tuple[dict, list[dict]]:
    if model_name != MODEL_NAME:  # fork branch: register its name for the instance-name canonicalisation (W99g)
        if not BRANCH_NAME_RE.fullmatch(model_name):
            raise ValueError(f"fork branch model name {model_name!r} must match {BRANCH_NAME_RE.pattern}")
        _BRANCH_NAMES.add(model_name)
    h = CloqFCHandler(base, meta, entry["id"], policy=policy, model_name=model_name, track_state=track_state)
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
    final_state = state_sha(h.model_name_underline_replaced, entry["id"]) if track_state else None
    ev = _evaluate_single_multi_turn_entry(h, entry["id"], result, gt, copy.deepcopy(prompt_entry), model_name, category)
    if model_name != MODEL_NAME:  # fork branches: drop this branch's backend instances (inference and _eval)
        import bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils as MU
        for k in [k for k in list(vars(MU)) if k.startswith(re.sub(r"[-./:]", "_", model_name + "_"))]:
            vars(MU).pop(k, None)
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
    if track_state:
        traj["final_state_sha"] = final_state
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
