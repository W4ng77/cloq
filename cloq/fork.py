"""Same-state 2x2 fork: state extraction, divergence search and branch execution (protocol fork-v1).

Protocol and every deviation from the design: docs/insights/FORK_PROTOCOL.md. Driver: scripts/a6000/fork_driver.py.
Worker task kind "fork": scripts/a6000/worker.py::run_fork.

Terms
  block     one closed-loop run of a cell (a quantized agent Q) on one prompt nonce (runs/<run_id>/<domain>/).
  h_t       the full saved history (agent, user and tool messages of trajectory.jsonl) before Q's t-th generated
            agent message. The CLOQ agent re-reads it exactly as it read it in the original run.
  a_Q       Q's recorded action at t (the trajectory message). a_B: B's full greedy action at h_t, generated from the
            identical prompt token ids (checked against Q's recorded prompt ids).
  branch XY forced current action a_X at h_t, then controller Y to the end. BB, BQ, QB, QQ.

Mechanics (tau2 half-duplex orchestrator, third_party/tau2-bench/src/tau2/orchestrator/orchestrator.py)
  * A task copy with initial_state.message_history = h_t. Orchestrator.initialize() replays every tool call in h_t
    (agent and user side, strict: a replayed mutating call must return the recorded content) on a fresh
    environment to rebuild the DB and the telecom device state, builds the agent state from the agent-visible
    messages and the user-simulator state from the user-visible messages (the simulator has no other state:
    system prompt = global guidelines + task instructions; greedy, seed = the original simulation seed).
  * h_t always ends with a message addressed to the agent (user text or the agent's tool result), so the next
    orchestrator step is an agent step. ForkAgent returns the forced action for that one step, without an LLM call,
    and logs the prompt it would have seen. The forced action then goes through the normal step (tool execution or
    delivery to the user simulator), so it consumes one step and its tool errors count, exactly as in live play.
  * The step and error counters are restored to their values at h_t (tau2 would restart them at 0).
  * The continuation controller is a separate vLLM server per checkpoint. A switch sends the full history to the
    other server, which prefills it from scratch; prefix caches are per process and never shared across weights.
  * Scoring: tau2 evaluate_simulation on the ORIGINAL task (its gold environment must not see h_t) with the full
    trajectory (h_t + continuation), EvaluationType.ALL_IGNORE_BASIS as in cloq.run_arm, plus official_reward.
"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

PROTOCOL = "fork-v1"
STOP_TOKEN = "###STOP###"

# ----------------------------------------------------------------------------
# hashing / canonical views
# ----------------------------------------------------------------------------


def sha(obj: Any) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def ids_sha(ids: Optional[list[int]]) -> Optional[str]:
    return None if ids is None else sha(",".join(map(str, ids)))


def _args(a: Any) -> Any:
    if isinstance(a, str):
        try:
            return json.loads(a)
        except json.JSONDecodeError:
            return a
    return a


def canon_msg(d: dict) -> dict:
    """Exact content view of a message: everything the agent, the user simulator or the environment can see,
    without volatile fields (tool-call ids are random vLLM ids and never rendered by the Qwen templates;
    timestamps, turn_idx, cost, usage)."""
    role = d.get("role")
    if role == "tool":
        return {"role": "tool", "content": d.get("content"), "requestor": d.get("requestor"), "error": bool(d.get("error"))}
    tcs = d.get("tool_calls") or []
    return {"role": role, "content": d.get("content"),
            "tool_calls": [{"name": tc.get("name"), "arguments": _args(tc.get("arguments")), "requestor": tc.get("requestor")} for tc in tcs]}


def canon_seq_sha(msgs: list[dict]) -> str:
    return sha([canon_msg(m) for m in msgs])


# ----------------------------------------------------------------------------
# tau2 message (de)serialisation
# ----------------------------------------------------------------------------


def msg_from_dict(d: dict):
    from tau2.data_model.message import AssistantMessage, ToolMessage, UserMessage

    d = {k: v for k, v in d.items() if k != "raw_data"}
    cls = {"assistant": AssistantMessage, "user": UserMessage, "tool": ToolMessage}[d["role"]]
    return cls.model_validate(d)


def msg_to_dict(m) -> dict:
    d = m.model_dump()
    d.pop("raw_data", None)
    return d


# ----------------------------------------------------------------------------
# blocks, positions, budget
# ----------------------------------------------------------------------------


def read_jsonl(p: Path) -> list[dict]:
    with open(p, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


class Block:
    """One closed-loop run of one cell on one nonce: runs/<run_id>/<domain>/."""

    def __init__(self, root: Path, run_id: str, domain: str):
        self.run_id, self.domain = run_id, domain
        self.dir = Path(root) / "runs" / run_id / domain
        self.config = json.load(open(self.dir / "config.json"))
        self.environment = json.load(open(self.dir / "environment.json"))
        self.nonce = self.environment.get("prompt_nonce")
        self.traj = {t["task_id"]: t for t in read_jsonl(self.dir / "trajectory.jsonl")}
        recs = read_jsonl(self.dir / "decisions.jsonl")
        last = {}
        for r in recs:  # W8: keep the final attempt per task
            last[r["task_id"]] = r["trajectory_id"]
        self.dec = defaultdict(list)
        for r in recs:
            if last[r["task_id"]] == r["trajectory_id"]:
                self.dec[r["task_id"]].append(r)
        for v in self.dec.values():
            v.sort(key=lambda r: r["decision_idx"])

    @property
    def run_config(self) -> dict:
        return self.config["tau2_run_config"]

    def checkpoint(self) -> Optional[dict]:
        ck = self.config.get("checkpoint")
        return json.loads(ck) if isinstance(ck, str) else ck


def prefix_len(task_dict: dict) -> int:
    """Messages present before the first orchestrator step: the task's own initial history, else the greeting."""
    mh = ((task_dict.get("initial_state") or {}).get("message_history")) or []
    return len(mh) if mh else 1


def agent_positions(msgs: list[dict], n0: int) -> list[int]:
    """Trajectory indices of the agent's generated messages (decision t <-> positions[t])."""
    return [i for i in range(n0, len(msgs)) if msgs[i]["role"] == "assistant"]


def budget_used(msgs: list[dict], n0: int) -> tuple[int, int]:
    """(steps, errors) the orchestrator had counted when the trajectory was msgs.

    One step per agent or user message and one per tool-execution step (all results of one tool-calling message);
    errors = tool results with error=True (agent and user side), as Orchestrator._execute_tool_calls counts them.
    """
    steps = errors = 0
    for i in range(n0, len(msgs)):
        m = msgs[i]
        if m["role"] == "tool":
            if i == n0 or msgs[i - 1]["role"] != "tool":
                steps += 1
            errors += bool(m.get("error"))
        else:
            steps += 1
    return steps, errors


# ----------------------------------------------------------------------------
# environment restoration
# ----------------------------------------------------------------------------


def restore_env(domain: str, task, history: list):
    """Fresh environment with the task's initialization plus a strict replay of every tool call in `history`."""
    from tau2.runner.build import build_environment

    env = build_environment(domain)
    ist = task.initial_state
    env.set_state(initialization_data=ist.initialization_data if ist else None,
                  initialization_actions=ist.initialization_actions if ist else None,
                  message_history=[copy.deepcopy(m) for m in history], strict=True)
    env.sync_tools()
    return env


def env_hashes(env) -> dict:
    return {"db": env.get_db_hash(), "user_db": env.get_user_db_hash()}


# ----------------------------------------------------------------------------
# semantic action comparison
# ----------------------------------------------------------------------------


def _norm_call(tc: dict) -> str:
    from cloq.metrics import normalize_tool_call

    a = _args(tc.get("arguments"))
    return normalize_tool_call(tc.get("name"), a if isinstance(a, dict) else {"__unparsed__": a})


def action_view(m: dict, schemas: dict[str, dict]) -> dict:
    """act (tool calls) | talk (text) | stop (###STOP###) | parse_fail (tool-call markup the parser rejected) | empty."""
    tcs = m.get("tool_calls") or []
    content = m.get("content")
    if tcs:
        kind = "act"
    elif content and STOP_TOKEN in content:
        kind = "stop"
    elif content and "<tool_call>" in content:
        kind = "parse_fail"
    elif not (content or "").strip():
        kind = "empty"
    else:
        kind = "talk"
    calls = []
    for tc in tcs:
        name = tc.get("name")
        a = _args(tc.get("arguments"))
        sch = schemas.get(name)
        invalid_args = None
        if sch is not None:
            props = set((sch.get("properties") or {}).keys())
            req = set(sch.get("required") or [])
            keys = set(a.keys()) if isinstance(a, dict) else None
            invalid_args = keys is None or not req <= keys or not keys <= props
        calls.append({"name": name, "norm": _norm_call(tc), "invalid_tool": sch is None, "invalid_args": invalid_args})
    return {"kind": kind, "calls": calls, "text": " ".join((content or "").split())}


def compare_actions(q: dict, b: dict, schemas: dict[str, dict]) -> dict:
    """Primary categories (first match): class (act/talk/stop/parse_fail/empty differ), invalid_tool, tool_count,
    multi_tool_order, tool_name, invalid_args, tool_args. Non-primary: same, text_only (same class, different text)."""
    vq, vb = action_view(q, schemas), action_view(b, schemas)
    out = {"q_kind": vq["kind"], "b_kind": vb["kind"], "q_calls": [c["norm"] for c in vq["calls"]],
           "b_calls": [c["norm"] for c in vb["calls"]]}
    if vq["kind"] != vb["kind"]:
        return {**out, "category": f"class:{vq['kind']}->{vb['kind']}", "primary": True}
    if vq["kind"] == "act":
        nq, nb = [c["name"] for c in vq["calls"]], [c["name"] for c in vb["calls"]]
        cq, cb = out["q_calls"], out["b_calls"]
        if cq == cb:
            return {**out, "category": "same", "primary": False}
        inv_t = any(c["invalid_tool"] for c in vq["calls"] + vb["calls"])
        if nq != nb and inv_t:
            return {**out, "category": "invalid_tool", "primary": True}
        if len(nq) != len(nb):
            return {**out, "category": "tool_count", "primary": True}
        if sorted(cq) == sorted(cb):
            return {**out, "category": "multi_tool_order", "primary": True}
        if nq != nb:
            return {**out, "category": "tool_name", "primary": True}
        if any(c["invalid_args"] for c in vq["calls"] + vb["calls"]):
            return {**out, "category": "invalid_args", "primary": True}
        return {**out, "category": "tool_args", "primary": True}
    same = vq["text"] == vb["text"]
    return {**out, "category": "same" if same else "text_only", "primary": False}


def tool_schemas(tools_schema: list[dict]) -> dict[str, dict]:
    return {t["function"]["name"]: t["function"].get("parameters") or {} for t in tools_schema}


# ----------------------------------------------------------------------------
# agent with a forced first action, per-agent nonce, routed decision records
# ----------------------------------------------------------------------------


class RoutingWriter:
    """Decision records routed by trajectory_id (= branch tag), so concurrent branches never mix."""

    def __init__(self):
        self._lock = threading.Lock()
        self.recs: dict[str, list[dict]] = defaultdict(list)

    def write(self, rec: dict) -> None:
        with self._lock:
            self.recs[rec["trajectory_id"]].append(rec)

    def pop(self, tag: str) -> list[dict]:
        with self._lock:
            return self.recs.pop(tag, [])

    def close(self) -> None:
        pass


_W: Optional[RoutingWriter] = None


def install_writer() -> RoutingWriter:
    global _W
    import cloq.agent as A

    if _W is None:
        _W = RoutingWriter()
    A._WRITER = _W
    A._RUN_META = {}
    return _W


def _make_agent_cls():
    from cloq.agent import CLOQAgent
    from cloq.context_policy import apply_context_policy, render_prompt_ids, sha256_text, render_prompt
    from tau2.agent.llm_agent import LLMAgent
    from tau2.data_model.message import MultiToolMessage
    from tau2.utils.llm_utils import to_litellm_messages
    from tau2.utils.utils import get_now

    class ForkAgent(CLOQAgent):
        def __init__(self, tools, domain_policy, llm, llm_args, task, nonce, forced=None, tag=None, decision_idx=0):
            self._nonce = nonce
            super().__init__(tools=tools, domain_policy=domain_policy, llm=llm, llm_args=llm_args, task=task)
            self._forced = forced
            if tag:
                self.trajectory_id = tag
            self.decision_idx = decision_idx

        @property
        def system_prompt(self) -> str:  # the block's nonce, per agent (CLOQAgent reads it from the process env)
            base = LLMAgent.system_prompt.fget(self)
            return f"{base}\nSession ID: {self._nonce}\n" if self._nonce else base

        def _generate_next_message(self, message, state):
            if self._forced is None:
                t0 = time.time()
                out = super()._generate_next_message(message, state)
                usage = (out.raw_data or {}).get("usage") or {}
                recs = _W.recs.get(self.trajectory_id) if _W is not None else None
                if recs:
                    recs[-1]["usage"] = usage
                    recs[-1]["wall_seconds"] = time.time() - t0
                    recs[-1]["api_base"] = self.llm_args.get("api_base")
                return out
            forced, self._forced = self._forced, None
            if isinstance(message, MultiToolMessage):
                state.messages.extend(message.tool_messages)
            else:
                state.messages.append(message)
            full_lm = to_litellm_messages(state.system_messages + state.messages)
            kept_lm, cinfo = apply_context_policy(full_lm, self.tools_schema)
            ids = render_prompt_ids(kept_lm, self.tools_schema)
            rec = {"task_id": self.task_id, "trajectory_id": self.trajectory_id, "decision_idx": self.decision_idx,
                   "forced": True, "n_state_messages": len(state.messages), "context": cinfo.__dict__,
                   "prompt_sha256": sha256_text(render_prompt(kept_lm, self.tools_schema)),
                   "prompt_token_ids": ids, "prompt_ids_from_server": False, "n_prompt_tokens": len(ids),
                   "system_sha256": self.system_sha, "tools_sha256": self.tools_sha,
                   "content": forced.content,
                   "tool_calls": [tc.model_dump() for tc in forced.tool_calls] if forced.is_tool_call() else None}
            if _W is not None:
                _W.write(rec)
            self.decision_idx += 1
            out = forced.model_copy(deep=True)
            out.timestamp = get_now()
            out.turn_idx = None
            return out

    return ForkAgent


_AGENT_CLS = None


def fork_agent_cls():
    global _AGENT_CLS
    if _AGENT_CLS is None:
        _AGENT_CLS = _make_agent_cls()
    return _AGENT_CLS


def setup_tau2() -> None:
    from cloq.agent import register_cloq_agent
    import litellm

    register_cloq_agent()
    litellm.register_model({
        f"hosted_vllm/{n}": {"input_cost_per_token": 0.0, "output_cost_per_token": 0.0, "litellm_provider": "hosted_vllm", "mode": "chat"}
        for n in ("agent", "user")})
    install_writer()


def run_config(rc: dict, agent_base: str, user_base: str):
    from tau2.data_model.simulation import TextRunConfig

    d = copy.deepcopy(rc)
    d["llm_args_agent"]["api_base"] = agent_base
    d["llm_args_user"]["api_base"] = user_base
    return TextRunConfig.model_validate(d)


# ----------------------------------------------------------------------------
# states
# ----------------------------------------------------------------------------


def official_from_traj(tr: dict) -> Optional[float]:
    """official_reward of an original episode. Runs written before cloq.run_arm.basis_reward existed lack the field;
    it is then recomputed from the stored reward_info with the same formula (product over the task's reward_basis of
    DB / ENV_ASSERTION / ACTION / COMMUNICATE; empty check lists vacuously met; premature termination scores 0)."""
    if "official_reward" in tr:
        return tr["official_reward"]
    ri = tr.get("reward_info") or {}
    if tr.get("termination_reason") not in ("user_stop", "agent_stop"):
        return 0.0
    basis = (tr["task"].get("evaluation_criteria") or {}).get("reward_basis") or []
    comps = {"DB": (ri.get("db_check") or {}).get("db_match"),
             "ENV_ASSERTION": all(c.get("met") for c in ri["env_assertions"]) if ri.get("env_assertions") else None,
             "ACTION": all(c.get("action_match") for c in ri["action_checks"]) if ri.get("action_checks") else None,
             "COMMUNICATE": all(c.get("met") for c in ri["communicate_checks"]) if ri.get("communicate_checks") else None}
    out = 1.0
    for b in basis:
        if comps.get(b) is not None:
            out *= float(bool(comps[b]))
    return out


def make_state(block: Block, task_id: str, t: int, extra: Optional[dict] = None) -> dict:
    """Fork state at Q's decision t of `block` (without a_B; the search adds it). Machine-readable manifest fields
    are listed in docs/insights/FORK_PROTOCOL.md §State manifest."""
    from tau2.data_model.tasks import Task

    tr = block.traj[task_id]
    msgs = tr["messages"]
    n0 = prefix_len(tr["task"])
    pos = agent_positions(msgs, n0)
    p = pos[t]
    hist = msgs[:p]
    dec = block.dec[task_id][t]
    steps, errs = budget_used(hist, n0)
    rc = block.run_config
    task = Task.model_validate(tr["task"])
    env = restore_env(block.domain, task, [msg_from_dict(m) for m in hist])
    st = {
        "protocol": PROTOCOL, "state_id": sha([block.run_id, block.domain, task_id, t])[:16],
        "run_id": block.run_id, "domain": block.domain, "task_id": task_id, "decision_idx": t,
        "n_decisions_orig": len(pos), "nonce": block.nonce, "checkpoint": block.checkpoint(), "arm": block.config.get("arm"),
        "model": {"hf_id": block.environment.get("model_id"), "revision": block.environment.get("model_revision"),
                  "chat_template_kwargs": block.environment.get("chat_template_kwargs")},
        "simulator": {"user_model_id": block.environment.get("user_model_id"), "sim_seed": tr["seed"],
                      "llm_user": rc.get("llm_user"), "llm_args_user": {k: v for k, v in rc["llm_args_user"].items() if k != "api_base"},
                      "original_api_base": rc["llm_args_user"].get("api_base")},
        "agent_llm": {"llm_agent": rc.get("llm_agent"), "llm_args_agent": {k: v for k, v in rc["llm_args_agent"].items() if k != "api_base"}},
        "run_config": rc, "max_prompt_tokens": block.environment.get("max_prompt_tokens"),
        "task": tr["task"], "task_sha": sha(tr["task"]), "n_prefix": n0,
        "history": hist, "history_sha": canon_seq_sha(hist), "n_history": len(hist),
        "budget": {"steps_used": steps, "errors_used": errs, "max_steps": rc.get("max_steps"), "max_errors": rc.get("max_errors"),
                   "steps_left": rc.get("max_steps") - steps, "errors_left": rc.get("max_errors") - errs},
        "env_hash": env_hashes(env),
        "q_decision": {"prompt_ids_sha": ids_sha(dec["prompt_token_ids"]), "n_prompt_tokens": len(dec["prompt_token_ids"]),
                       "prompt_sha256": dec["prompt_sha256"], "completion_ids_sha": ids_sha(dec.get("completion_token_ids")),
                       "system_sha256": dec["system_sha256"], "tools_sha256": dec["tools_sha256"],
                       "parser_error": dec.get("parser_error"), "finish_reason": dec.get("finish_reason")},
        "a_Q": {"message": msgs[p], "source": "trajectory (recorded Q action)"},
        "orig": {"termination_reason": tr["termination_reason"], "reward": tr.get("reward"), "db_match": tr.get("db_match"),
                 "official_reward": official_from_traj(tr),
                 "official_reward_source": "trajectory" if "official_reward" in tr else "recomputed from reward_info",
                 "n_messages": len(msgs),
                 "suffix_sha": canon_seq_sha(msgs[p:]),
                 "suffix_prompt_ids_sha": [ids_sha(d["prompt_token_ids"]) for d in block.dec[task_id][t:]],
                 "budget_final": budget_used(msgs, n0)},
        "versions": {"tau2_commit": block.environment.get("tau2_commit"), "cloq_commit_run": block.environment.get("cloq_commit"),
                     "packages": block.environment.get("packages")},
        "created": time.time(),
    }
    if extra:
        st.update(extra)
    return st


def state_io_check(st: dict, path: Path) -> dict:
    """Save/load round trip: write the state, read it back, rebuild the environment from the loaded copy and compare
    the canonical history and DB hashes with the ones computed at creation."""
    from tau2.data_model.tasks import Task

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, ensure_ascii=False))
    ld = json.loads(path.read_text())
    env = restore_env(ld["domain"], Task.model_validate(ld["task"]), [msg_from_dict(m) for m in ld["history"]])
    h = env_hashes(env)
    return {"history_sha_ok": canon_seq_sha(ld["history"]) == st["history_sha"], "env_hash_ok": h == st["env_hash"],
            "task_sha_ok": sha(ld["task"]) == st["task_sha"], "env_hash_loaded": h}


# ----------------------------------------------------------------------------
# shadow query and branch execution
# ----------------------------------------------------------------------------


def _agent_for(st: dict, base: str, tag: str, forced=None, user_base: str = "http://127.0.0.1:8000/v1"):
    from tau2.data_model.tasks import Task
    from tau2.runner.build import build_environment

    cfg = run_config(st["run_config"], base, user_base)
    env = build_environment(st["domain"])
    A = fork_agent_cls()
    agent = A(tools=env.get_tools(), domain_policy=env.get_policy(), llm=cfg.llm_agent,
              llm_args=copy.deepcopy(cfg.llm_args_agent), task=Task.model_validate(st["task"]), nonce=st["nonce"],
              forced=forced, tag=tag, decision_idx=st["decision_idx"])
    agent.set_seed(st["simulator"]["sim_seed"])
    return agent


def shadow(st: dict, base: str, tag: str) -> tuple[dict, dict]:
    """The controller at `base` generates its full action at h_t, from the agent state the orchestrator would build
    (agent-visible history without the last message, then the last message delivered)."""
    from tau2.agent.base_agent import is_valid_agent_history_message

    hist = [msg_from_dict(m) for m in st["history"]]
    agent = _agent_for(st, base, tag)
    state = agent.get_init_state(message_history=[m for m in hist[:-1] if is_valid_agent_history_message(m)])
    msg, _ = agent.generate_next_message(hist[-1], state)
    recs = _W.pop(tag)
    assert len(recs) == 1, f"shadow {tag}: {len(recs)} records"
    return msg_to_dict(msg), recs[0]


def local_prompt_ids(st: dict) -> list[int]:
    """The prompt ids the CLOQ agent renders at h_t (no server): the state-restoration check against Q's record."""
    from tau2.agent.base_agent import is_valid_agent_history_message

    hist = [msg_from_dict(m) for m in st["history"]]
    tag = "local-" + st["state_id"] + "-" + str(threading.get_ident())
    agent = _agent_for(st, "http://127.0.0.1:1/v1", tag, forced=msg_from_dict(st["a_Q"]["message"]))
    state = agent.get_init_state(message_history=[m for m in hist[:-1] if is_valid_agent_history_message(m)])
    agent.generate_next_message(hist[-1], state)
    return _W.pop(tag)[0]["prompt_token_ids"]


def run_branch(st: dict, first: str, controller: str, bases: dict[str, str], user_base: str, tag: str,
               replay_hash: bool = True) -> dict:
    """Branch <first><controller>: force a_<first> at h_t, continue with the controller server to the end."""
    from tau2.data_model.tasks import InitialState, Task
    from tau2.evaluator.evaluator import EvaluationType, evaluate_simulation
    from tau2.orchestrator.modes import CommunicationMode
    from tau2.runner.build import build_text_orchestrator

    from cloq.run_arm import basis_reward

    task = Task.model_validate(st["task"])
    hist = [msg_from_dict(m) for m in st["history"]]
    ftask = task.model_copy(deep=True)
    ist = task.initial_state
    ftask.initial_state = InitialState(initialization_data=ist.initialization_data if ist else None,
                                       initialization_actions=ist.initialization_actions if ist else None,
                                       message_history=hist)
    cfg = run_config(st["run_config"], bases[controller], user_base)
    orch = build_text_orchestrator(cfg, ftask, seed=st["simulator"]["sim_seed"])
    forced = msg_from_dict(st["a_" + first]["message"])
    A = fork_agent_cls()
    orch.agent = A(tools=orch.environment.get_tools(), domain_policy=orch.environment.get_policy(), llm=cfg.llm_agent,
                   llm_args=copy.deepcopy(cfg.llm_args_agent), task=task, nonce=st["nonce"], forced=forced, tag=tag,
                   decision_idx=st["decision_idx"])
    probe: dict = {}
    base_init = orch.initialize

    def init():
        base_init()
        probe["counters_tau2"] = [orch.step_count, orch.num_errors]
        orch.step_count = st["budget"]["steps_used"]
        orch.num_errors = st["budget"]["errors_used"]
        probe["env_hash_init"] = env_hashes(orch.environment)
        probe["to_role"] = getattr(orch.to_role, "value", str(orch.to_role))

    orch.initialize = init
    t0 = time.time()
    try:
        sim = orch.run()
    except Exception as e:
        recs = _W.pop(tag)
        return {"tag": tag, "branch": first + controller, "error": repr(e), "n_decisions": len(recs), "probe": probe}
    dur = time.time() - t0
    rinfo = evaluate_simulation(simulation=sim, task=task, evaluation_type=EvaluationType.ALL_IGNORE_BASIS,
                                solo_mode=False, domain=st["domain"], mode=CommunicationMode.HALF_DUPLEX)
    sim.reward_info = rinfo
    br = basis_reward(sim, task)
    msgs = [msg_to_dict(m) for m in sim.messages]
    n_h = st["n_history"]
    recs = _W.pop(tag)
    out = {
        "tag": tag, "state_id": st["state_id"], "branch": first + controller, "first": first, "controller": controller,
        "controller_base": bases[controller], "termination_reason": getattr(sim.termination_reason, "value", str(sim.termination_reason)),
        "reward": rinfo.reward, "db_match": rinfo.db_check.db_match if rinfo.db_check is not None else None,
        "official_reward": br["official_reward"], "env_assert_all": br["env_assert_all"],
        "reward_info": rinfo.model_dump(mode="json"),
        "step_count_final": orch.step_count, "num_errors_final": orch.num_errors,
        "budget_recount": list(budget_used(msgs, st["n_prefix"])),
        "prefix_ok": [canon_msg(m) for m in msgs[:n_h]] == [canon_msg(m) for m in st["history"]],
        "env_hash_init": probe.get("env_hash_init"), "env_hash_init_ok": probe.get("env_hash_init") == st["env_hash"],
        "counters_tau2_default": probe.get("counters_tau2"), "to_role_at_init": probe.get("to_role"),
        "env_hash_final": env_hashes(orch.environment),
        "suffix": msgs[n_h:], "suffix_sha": canon_seq_sha(msgs[n_h:]), "n_messages": len(msgs),
        "decisions": [{"decision_idx": r["decision_idx"], "forced": bool(r.get("forced")),
                       "prompt_ids_sha": ids_sha(r.get("prompt_token_ids")), "n_prompt_tokens": r.get("n_prompt_tokens"),
                       "prompt_ids_from_server": r.get("prompt_ids_from_server"), "prompt_ids_match_local": r.get("prompt_ids_match_local"),
                       "completion_ids_sha": ids_sha(r.get("completion_token_ids")), "n_completion_tokens": r.get("n_completion_tokens"),
                       "finish_reason": r.get("finish_reason"), "content": r.get("content"), "tool_calls": r.get("tool_calls"),
                       "parser_error": r.get("parser_error"), "system_sha256": r.get("system_sha256"),
                       "usage": r.get("usage"), "wall_seconds": r.get("wall_seconds"), "api_base": r.get("api_base")}
                      for r in recs],
        "duration": dur, "sim_seed": sim.seed,
        "n_user_msgs": sum(1 for m in msgs[n_h:] if m["role"] == "user"),
    }
    if replay_hash:
        env2 = restore_env(st["domain"], task, [msg_from_dict(m) for m in msgs])
        out["env_hash_replay"] = env_hashes(env2)
    return out


def branch_signature(r: dict) -> dict:
    """What must agree between branches that should be identical."""
    return {"suffix_sha": r.get("suffix_sha"), "prompts": [d["prompt_ids_sha"] for d in r.get("decisions", [])],
            "completions": [d["completion_ids_sha"] for d in r.get("decisions", []) if not d["forced"]],
            "termination": r.get("termination_reason"), "reward": r.get("reward"), "db_match": r.get("db_match"),
            "official_reward": r.get("official_reward"), "env_hash_final": r.get("env_hash_final"),
            "steps": r.get("step_count_final"), "errors": r.get("num_errors_final")}
