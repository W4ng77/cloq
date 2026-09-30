"""ALFWorld (TextWorld text engine) adapter: a fixed manifest subset against the CLOQ agent server.

Environment: the official alfworld 0.4.2 TextWorld environment exactly as AlfredTWEnv.init_env builds it for
evaluation (AlfredDemangler(shuffle=False) + AlfredInfos wrappers, EnvInfos(won, admissible_commands, gamefile),
no expert), one game per episode, max_episode_steps = 50 environment actions (the ReAct / common LLM budget).
Evaluator: infos['won'] (the game's PDDL goal condition), unchanged.

Agent interface (fixed before any model run; identical for every checkpoint): native tool calling with one tool,
act(command). System prompt = task framing + the environment's own `help` command list (alfred.twl2) + the rule that
'Nothing happens.' means an invalid or ineffective command. The first user message is the initial observation
without the TextWorld banner (as ReAct strips it). Each act call returns the observation as the tool result. The
admissible-command list is never shown to the agent; it is logged per action for the legal-action check.
  - several act calls in one reply are executed in order (each is one environment action);
  - a reply without a tool call gets the fixed user message CONTINUE_MSG (it still costs one decision);
  - a malformed call (unknown tool / no command string) gets an error tool result and no environment action;
  - the episode ends when the game is won, after 50 environment actions, or after 50 agent decisions.
reward = success = won.

usage (alfworld venv): python scripts/ext/alfworld_run.py --run-id X --arm bf16 --domain alfworld \
    --manifest manifests/alfworld/alfworld_text_v1.json --subset smoke --agent-base http://127.0.0.1:8001/v1
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, ChatError, RunDir, assistant_history_message, chat, common_args, decision_record, summarize, write_headers  # noqa: E402

ALF_DATA = Path(os.environ.get("ALFWORLD_DATA", "/data/ziyangs/cloq_work/data/alfworld"))
os.environ["ALFWORLD_DATA"] = str(ALF_DATA)
MAX_ENV_STEPS = 50
MAX_DECISIONS = 50

HELP = ("Available commands:\n"
        "  look:                             look around your current location\n"
        "  inventory:                        check your current inventory\n"
        "  go to (receptacle):               move to a receptacle\n"
        "  open (receptacle):                open a receptacle\n"
        "  close (receptacle):               close a receptacle\n"
        "  take (object) from (receptacle):  take an object from a receptacle\n"
        "  move (object) to (receptacle):  place an object in or on a receptacle\n"
        "  examine (something):              examine a receptacle or an object\n"
        "  use (object):                     use an object\n"
        "  heat (object) with (receptacle):  heat an object using a receptacle\n"
        "  clean (object) with (receptacle): clean an object using a receptacle\n"
        "  cool (object) with (receptacle):  cool an object using a receptacle\n"
        "  slice (object) with (object):     slice an object using a sharp object\n")

SYSTEM = ("You are an agent in a household environment. You will be given a description of the room and a task to "
          "complete. Interact with the environment only by calling the `act` tool with exactly one text command per "
          "call; the tool returns what you observe after the command.\n\n" + HELP +
          "\nRefer to objects and receptacles exactly as they are named in the observations, including their number "
          "(for example \"apple 1\" or \"countertop 2\"). If the environment answers \"Nothing happens.\", the command "
          "was invalid or had no effect. The episode ends as soon as the task is completed, or after "
          f"{MAX_ENV_STEPS} commands.")

TOOLS = [{"type": "function", "function": {
    "name": "act",
    "description": "Execute one text command in the household environment and return the resulting observation.",
    "parameters": {"type": "object", "properties": {"command": {
        "type": "string", "description": "One command, e.g. \"go to countertop 1\" or \"take apple 1 from countertop 1\"."}},
        "required": ["command"]}}}]

CONTINUE_MSG = "Please continue by calling the act tool with your next command."


def make_env(game: str):
    import textworld
    import textworld.gym
    from alfworld.agents.environment.alfred_tw_env import AlfredDemangler, AlfredInfos
    ri = textworld.EnvInfos(won=True, admissible_commands=True, extras=["gamefile"])
    eid = textworld.gym.register_games([str(ALF_DATA / game)], ri, batch_size=1, asynchronous=False,
                                       max_episode_steps=MAX_ENV_STEPS, wrappers=[AlfredDemangler(shuffle=False), AlfredInfos])
    return textworld.gym.make(eid)


def strip_banner(obs: str) -> str:
    return "\n".join(obs.split("\n\n")[1:]) if obs.startswith("-= Welcome") else obs


def run_episode(job: tuple) -> tuple[dict | None, list[dict], str | None]:
    game, base, meta = job
    t0 = time.time()
    tid = str(uuid.uuid4())
    env = make_env(game)
    obs, info = env.reset()
    first = strip_banner(obs[0])
    admissible = list(info["admissible_commands"][0])
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": first}]
    decisions, actions = [], []
    won, done, term, n_env = False, False, None, 0
    try:
        while True:
            if len(decisions) >= MAX_DECISIONS:
                term = "max_decisions"
                break
            sent = list(messages)
            try:
                raw, dt = chat(base, sent, TOOLS)
            except ChatError as e:
                if e.kind == "outage":
                    return None, [], str(e)
                term = "context_overflow"
                break
            rec = decision_record(meta, game, tid, len(decisions), sent, TOOLS, raw, dt)
            messages.append(assistant_history_message(raw))
            tcs = rec["tool_calls"] or []
            parsed, legal, known, obs_list = [], [], [], []
            if not tcs:
                messages.append({"role": "user", "content": CONTINUE_MSG})
            for tc in tcs:
                fn = tc["function"]
                cmd = None
                if fn["name"] == "act":
                    try:
                        a = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                        cmd = a.get("command") if isinstance(a, dict) and isinstance(a.get("command"), str) else None
                    except Exception:
                        cmd = None
                known.append(fn["name"] == "act")
                if done:
                    o = "Error: the episode has ended; no further commands are executed."
                    parsed.append(None); legal.append(None)
                elif cmd is None:
                    o = ("Error: unknown tool." if fn["name"] != "act" else "Error: act requires a 'command' string argument.")
                    parsed.append(None); legal.append(None)
                else:
                    c = cmd.strip()
                    parsed.append(c)
                    legal.append(c in admissible)
                    obs, _, dn, info = env.step([c])
                    n_env += 1
                    o = obs[0]
                    won = bool(info["won"][0])
                    done = bool(dn[0]) or won
                    actions.append({"command": c, "admissible": c in admissible, "observation": o, "won": won})
                    admissible = list(info["admissible_commands"][0])
                obs_list.append(o)
                messages.append({"role": "tool", "tool_call_id": tc.get("id"), "content": o})
            rec.update(parsed_actions=parsed, actions_admissible=legal, actions_known_tool=known, observations=obs_list,
                       admissible_commands_after=admissible, n_env_steps=n_env, won=won)
            decisions.append(rec)
            if won:
                term = "won"
                break
            if done or n_env >= MAX_ENV_STEPS:
                term = "max_env_steps"
                break
    finally:
        env.close()
    n_act = len(actions)
    traj = {"task_id": game, "trajectory_id": tid, "task_type": game.split("/")[2].split("-")[0],
            "termination_reason": term, "success": won, "reward": 1.0 if won else 0.0,
            "evaluator": {"won": won, "source": "textworld infos['won']"},
            "n_decisions": len(decisions), "n_env_steps": n_env,
            "n_inadmissible": sum(not a["admissible"] for a in actions), "inadmissible_rate": (sum(not a["admissible"] for a in actions) / n_act) if n_act else None,
            "n_no_tool_call": sum(not d["tool_calls"] for d in decisions),
            "actions": actions, "messages": messages, "duration": time.time() - t0}
    return traj, decisions, None


def main():
    ap = argparse.ArgumentParser()
    common_args(ap)
    args = ap.parse_args()
    mpath = (ROOT / args.manifest).resolve()
    man = json.load(open(mpath))
    ids = args.subset[4:].split(",") if args.subset.startswith("ids:") else man[args.subset]
    if args.limit:
        ids = ids[:args.limit]
    rd = RunDir(args.run_id, args.domain)
    if rd.completed():
        print(f"{rd.dir} already completed; skipping")
        return
    rd.prune_partial()
    bench = {"env": "alfworld", "name": "ALFWorld text (TextWorld)", "max_env_steps": MAX_ENV_STEPS, "max_decisions": MAX_DECISIONS,
             "system_prompt": SYSTEM, "tools": TOOLS, "continue_message": CONTINUE_MSG,
             "wrappers": "AlfredDemangler(shuffle=False), AlfredInfos", "evaluator": "infos['won']"}
    write_headers(rd, args, bench, ids, ["alfworld", "textworld", "fast_downward_textworld", "tatsu"], mpath)
    t_start = time.time()
    rd.write_json("status.json", {"status": "running", "started": time.strftime("%FT%TZ", time.gmtime()), "n_tasks": len(ids)})
    done0 = rd.done_items()
    todo = [g for g in ids if g not in done0]
    meta = {"run_id": args.run_id, "arm": args.arm, "domain": args.domain}
    n_outage = 0
    with mp.get_context("spawn").Pool(processes=max(1, min(args.max_concurrency, len(todo) or 1)), maxtasksperchild=1) as pool:
        for traj, decs, err in pool.imap_unordered(run_episode, [(g, args.agent_base, meta) for g in todo]):
            if traj is None:
                n_outage += 1
                print(f"[alfworld] outage: {err}", file=sys.stderr, flush=True)
                continue
            rd.write_item(traj, decs)
            print(f"[alfworld] {traj['task_type']} won={traj['success']} term={traj['termination_reason']} dec={traj['n_decisions']} "
                  f"env={traj['n_env_steps']} inadm={traj['n_inadmissible']} {traj['duration']:.0f}s", file=sys.stderr, flush=True)
    trs = rd.trajectories()
    acts = [a for t in trs for a in t["actions"]]
    per_type = {}
    for t in trs:
        per_type.setdefault(t["task_type"], []).append(bool(t["success"]))
    m = summarize(rd, {"benchmark": "alfworld_text", "n_outage_items": n_outage,
                       "inadmissible_action_rate": (sum(not a["admissible"] for a in acts) / len(acts)) if acts else None,
                       "no_tool_call_rate": (sum(t["n_no_tool_call"] for t in trs) / max(1, sum(t["n_decisions"] for t in trs))),
                       "success_by_task_type": {k: [sum(v), len(v)] for k, v in sorted(per_type.items())}})
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
