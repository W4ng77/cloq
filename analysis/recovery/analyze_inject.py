"""Recovery-intervention analysis (W71 design + Amendment 1; W83: per-state turnover, manipulation checks, event chains,
replay audit). docs/insights/RECOVERY_INTERVENTION_DESIGN.md.

Arms per state: INV (injected error), VAL (matched valid action; VAL x Q is the original episode) and PP, the
process-perturbation control (Amendment 1; called NC in inject-v1 files: rows' "NC*" keys and branch files' "NC*" keys are
read as PP), each continued under controller B (BF16) and Q (GPTQ-W4 d1).

Outputs, per model directory <d> (analysis/recovery/inject_<model>/):
  summary.json         v1 means (R_B, R_Q, D, PP - VAL), keys renamed NC -> PP.
  annotations.jsonl    per state: cloq.fork_annotate.annotate_state on all six branches (compact), CPU only; cached.
  replay_audit.jsonl   per state: VAL x Q vs the original episode, field by field ("not recorded" where nothing is stored).
  summary_v2.json/.md  per controller x category: rescue / damage / turnover / net for INV vs VAL, PP vs VAL and INV vs PP
                       (paired, task-clustered bootstrap, exact McNemar on discordant pairs); D_i and D_PP,i distributions;
                       manipulation checks; event chains (error -> correction -> related requirement satisfied); process cost.

Bootstrap: resample tasks (domain, task_id) with replacement, B = 2000, seed 20261001 (one state per task in inject-v1, so
this equals the state bootstrap). Success Y = DB success (retail/airline), as frozen in the design.

usage: /data/ziyangs/cloq_work/envs/cloq/bin/python analysis/recovery/analyze_inject.py analysis/recovery/inject_q4 [inject_q8 ...]
       [--reannotate] [--procs 6]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
B, SEED = 2000, 20261001
ARMS = ("INV", "VAL", "PP")
CTRL = ("B", "Q")
BR = [f + c for f in ARMS for c in CTRL]
NR = "not recorded"
CONSENT_ASK = re.compile(r"\b(confirm|proceed|shall i|should i|would you like me to|do you want me to|yes)\b", re.I)  # = inject_driver


def _pp(k: str) -> str:
    """Backward-compatible key read: inject-v1 'NC' (negative control) == 'PP' (process-perturbation control)."""
    return "PP" + k[2:] if k.startswith("NC") else k


def _norm_branches(br: dict) -> dict:
    return {_pp(k): v for k, v in br.items()}


# ----------------------------------------------------------------------------
# statistics
# ----------------------------------------------------------------------------


def _clusters(rows):
    keys = sorted({(r["domain"], r["task_id"]) for r in rows})
    idx = {k: i for i, k in enumerate(keys)}
    return np.array([idx[(r["domain"], r["task_id"])] for r in rows], int), len(keys)


def cboot(x: np.ndarray, cl: np.ndarray, nc: int) -> dict:
    """Mean with a task-clustered percentile bootstrap interval."""
    if len(x) == 0:
        return {"est": None, "ci95": None, "n": 0}
    rng = np.random.default_rng(SEED)
    sums = np.bincount(cl, weights=x, minlength=nc)
    cnts = np.bincount(cl, minlength=nc).astype(float)
    draw = rng.integers(0, nc, (B, nc))
    d = sums[draw].sum(1) / np.maximum(cnts[draw].sum(1), 1)
    lo, hi = np.percentile(d, [2.5, 97.5])
    return {"est": round(float(x.mean()), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)], "n": int(len(x))}


def mcnemar(r: int, d: int) -> float | None:
    n = r + d
    if n == 0:
        return None
    k = min(r, d)
    return round(min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n), 4)


def turnover(a: np.ndarray, b: np.ndarray, cl, nc) -> dict:
    """Arm a vs reference arm b (paired 0/1): rescue = a1 b0, damage = a0 b1."""
    resc, dam = (a == 1) & (b == 0), (a == 0) & (b == 1)
    return {"n": int(len(a)), "rescue": int(resc.sum()), "damage": int(dam.sum()), "turnover": int((resc | dam).sum()),
            "net": cboot((a - b).astype(float), cl, nc), "rescue_rate": cboot(resc.astype(float), cl, nc),
            "damage_rate": cboot(dam.astype(float), cl, nc), "turnover_rate": cboot((resc | dam).astype(float), cl, nc),
            "mcnemar_exact_p": mcnemar(int(resc.sum()), int(dam.sum()))}


def dist(x: np.ndarray) -> dict:
    return {str(v): int((x == v).sum()) for v in range(-2, 3)}


def outcome_block(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0}
    cl, nc = _clusters(rows)
    Y = {k: np.array([int(r["Y"][k]) for r in rows]) for k in BR}
    out = {"n": len(rows), "n_tasks": nc, "success": {k: f"{int(v.sum())}/{len(v)}" for k, v in Y.items()}}
    for c in CTRL:
        out[c] = {"INV_vs_VAL": turnover(Y["INV" + c], Y["VAL" + c], cl, nc),
                  "PP_vs_VAL": turnover(Y["PP" + c], Y["VAL" + c], cl, nc),
                  "INV_vs_PP": turnover(Y["INV" + c], Y["PP" + c], cl, nc)}
        ch_inv = (Y["INV" + c] != Y["VAL" + c]).astype(float)
        ch_pp = (Y["PP" + c] != Y["VAL" + c]).astype(float)
        out[c]["excess_turnover_INV_minus_PP"] = cboot(ch_inv - ch_pp, cl, nc)
        out[c]["error_specific_effect"] = {
            "definition": "[Y(INV)-Y(VAL)] - [Y(PP)-Y(VAL)] = Y(INV) - Y(PP), per state",
            **cboot((Y["INV" + c] - Y["PP" + c]).astype(float), cl, nc)}
    D = (Y["INVB"] - Y["VALB"]) - (Y["INVQ"] - Y["VALQ"])
    Dp = (Y["PPB"] - Y["VALB"]) - (Y["PPQ"] - Y["VALQ"])
    out["D_INV"] = {"est": cboot(D.astype(float), cl, nc), "n_nonzero": int((D != 0).sum()), "dist": dist(D),
                    "states_nonzero": [r["state_key"] for r, d in zip(rows, D) if d != 0]}
    out["D_PP"] = {"est": cboot(Dp.astype(float), cl, nc), "n_nonzero": int((Dp != 0).sum()), "dist": dist(Dp)}
    out["D_INV_minus_D_PP"] = {"est": cboot((D - Dp).astype(float), cl, nc), "n_nonzero": int(((D - Dp) != 0).sum())}
    return out


# ----------------------------------------------------------------------------
# annotation (CPU, tau2 environments) -- worker
# ----------------------------------------------------------------------------

_BLOCKS: dict = {}


def _block(run_id, dom):
    from cloq import fork as F
    if (run_id, dom) not in _BLOCKS:
        _BLOCKS[(run_id, dom)] = F.Block(ROOT, run_id, dom)
    return _BLOCKS[(run_id, dom)]


def _init_worker():
    from loguru import logger
    logger.remove()
    from cloq import fork as F
    F.setup_tau2()


def annotate_one(paths: tuple[str, str]) -> dict:
    from cloq import fork as F
    from cloq import fork_annotate as A
    from tau2.data_model.tasks import Task
    st = json.loads(Path(paths[0]).read_text())
    br = _norm_branches(json.loads(Path(paths[1]).read_text()))
    full = A.annotate_state(st, br)
    comp = {"state_key": st["inject_key"], "requirements_at_state": {"success": full["requirements_at_state"].get("success")},
            "branches": {}}
    for b, a in full["branches"].items():
        if "error" in a:
            comp["branches"][b] = a
            continue
        calls = a["defect"]["calls"]
        comp["branches"][b] = {
            "flags": a["defect"]["flags"], "kind": a["defect"]["kind"],
            "calls": [{"name": c["name"], "type": c["type"], "execution": c["execution"], "ids": c["ids"],
                       "invalid_args": c["invalid_args"]["status"], "invalid_tool": c["invalid_tool"]["status"]} for c in calls],
            "changed_by_action": a["changed_by_action"], "correction": a["correction"]["evidence"],
            "any_auto_correction": a["correction"]["any_auto_correction"],
            "requirements": {k: a["requirements"][k] for k in ("success", "termination", "db_match", "failing", "action_checks")},
            "extra_steps_used": a["extra_steps_used"]}
    # original final DB hash, recomputed by strict replay of the recorded original messages (not stored in the run)
    b = _block(st["run_id"], st["domain"])
    tr = b.traj[st["task_id"]]
    env = F.restore_env(st["domain"], Task.model_validate(tr["task"]), [F.msg_from_dict(m) for m in tr["messages"]])
    comp["orig_final_db_recomputed"] = F.env_hashes(env)
    return comp


def annotate_dir(d: Path, keys: list[str], procs: int, force: bool) -> dict:
    p = d / "annotations.jsonl"
    have = {}
    if p.exists() and not force:
        have = {r["state_key"]: r for r in map(json.loads, p.read_text().splitlines()) if r}
    todo = [k for k in keys if k not in have]
    if todo:
        jobs = [(str(d / "states" / f"{k}.json"), str(d / "branches" / f"{k}.json")) for k in todo]
        with ProcessPoolExecutor(procs, initializer=_init_worker) as ex:
            for r in ex.map(annotate_one, jobs):
                have[r["state_key"]] = r
                print(f"  annotated {r['state_key']} ({len(have)}/{len(keys)})", file=sys.stderr)
        p.write_text("".join(json.dumps(have[k], default=str) + "\n" for k in keys if k in have))
    return have


# ----------------------------------------------------------------------------
# manipulation checks and event chains
# ----------------------------------------------------------------------------


def _first_result(br: dict) -> dict | None:
    s = br.get("suffix") or []
    return s[1] if len(s) > 1 and s[1].get("role") == "tool" else None


def manipulation(st: dict, br: dict, an: dict, Y: dict) -> dict:
    from cloq import fork as F
    inj = st["injection"]
    cat = inj["category"]
    out = {"category": cat}
    for c in CTRL:
        b = br["INV" + c]
        a = an["branches"]["INV" + c]
        forced_ok = F.canon_msg((b.get("suffix") or [{}])[0]) == F.canon_msg(st["a_INV"]["message"])
        res = _first_result(b)
        txt = (res or {}).get("content") or ""
        if cat == "wrong_id":
            ok = forced_ok and res is not None and (bool(res.get("error")) or "not found" in txt.lower())
            ev = {"tool_result_error": bool((res or {}).get("error")), "result": txt[:160],
                  "invalid_value_absent_from_db": a["flags"]["id_not_found"]}
        elif cat == "wrong_tool":
            name = (b["suffix"][0].get("tool_calls") or [{}])[0].get("name")
            ok = forced_ok and name == inj["invalid_tool"] != inj["valid_tool"] and res is not None
            ev = {"called": name, "intended_wrong": inj["invalid_tool"], "valid": inj["valid_tool"],
                  "tool_result_error": bool((res or {}).get("error")), "result": txt[:160]}
        else:
            ch = a["changed_by_action"].get("db") or []
            ok = forced_ok and res is not None and not res.get("error") and bool(ch)
            ev = {"write_executed": res is not None and not res.get("error"), "db_paths_changed": ch, "result": txt[:160]}
        out["INV" + c] = {"ok": bool(ok), "forced_action_reproduced": forced_ok, **ev}
    # VALID reference validity (VAL x Q and VAL x B force the same recorded action)
    v = an["branches"]["VALQ"]
    if cat == "premature_write":
        vtxt = st["a_VAL"]["message"].get("content") or ""
        ask = CONSENT_ASK.search(vtxt)
        out["VAL"] = {"ok": not st["a_VAL"]["message"].get("tool_calls") and bool(ask), "kind": v["kind"],
                      "is_text_confirmation_request": bool(ask), "db_changed": bool(v["changed_by_action"].get("db"))}
    else:
        res = _first_result(br["VALQ"])
        f = v["flags"]
        ok = res is not None and not res.get("error") and not (f["invalid_tool"] or f["invalid_args"] or f["exec_error"] or f["id_not_found"])
        out["VAL"] = {"ok": bool(ok), "tool_result_error": bool((res or {}).get("error")),
                      "flags": {k: f[k] for k in ("invalid_tool", "invalid_args", "exec_error", "id_not_found", "id_needs_review")},
                      "result": ((res or {}).get("content") or "")[:120]}
    # process-perturbation control: the repeated read must execute without error and change nothing
    pp = an["branches"]["PPQ"]
    res = _first_result(br["PPQ"])
    out["PP"] = {"ok": res is not None and not res.get("error") and not pp["changed_by_action"].get("db"),
                 "tool_result_error": bool((res or {}).get("error"))}
    out["VALQ_success"] = int(Y["VALQ"])
    out["all_ok"] = all(out[k]["ok"] for k in ("INVB", "INVQ", "VAL", "PP"))
    return out


def _later_calls(suffix: list[dict]):
    """(agent turn index, call, result) for every tool call after the forced action."""
    later = suffix[1:]
    ai = 0
    for i, m in enumerate(later):
        if m["role"] != "assistant":
            continue
        ai += 1
        for j, tc in enumerate(m.get("tool_calls") or []):
            k = i + 1 + j
            r = later[k] if k < len(later) and later[k]["role"] == "tool" else None
            yield ai, tc, r


def chain(st: dict, br: dict, an: dict, arm: str, manip_ok: bool) -> dict:
    """error occurs -> correction -> related requirement satisfied, for one branch (INV; VAL for the reference)."""
    from cloq import fork as F
    from cloq.fork_annotate import OBJECT_RE, TT
    inj = st["injection"]
    cat, dom = inj["category"], st["domain"]
    b, a = br[arm], an["branches"][arm]
    suf = b.get("suffix") or []
    req = a["requirements"]
    corr, ev, related = None, {}, None
    if cat in ("wrong_id", "wrong_tool"):
        vtc = st["a_VAL"]["message"]["tool_calls"][0]
        vname, vargs = vtc["name"], F._args(vtc["arguments"])
        for ai, tc, r in _later_calls(suf):
            okr = r is not None and not r.get("error")
            targs = F._args(tc.get("arguments"))
            if cat == "wrong_id" and tc.get("name") == vname and okr and inj["invalid_value"] not in json.dumps(targs, default=str):
                corr = corr or {"agent_turn": ai, "exact_valid_id": isinstance(targs, dict) and targs.get(inj["key"]) == inj["valid_value"]}
            if cat == "wrong_tool" and tc.get("name") == vname and okr:
                corr = corr or {"agent_turn": ai, "same_args": targs == vargs}
        gold = [x for x in req["action_checks"] if x["name"] == vname]
        related = {"definition": f"gold action checks on {vname} all matched", "n_gold": len(gold),
                   "satisfied": all(x["match"] for x in gold) if gold else None}
    else:
        ch = an["branches"]["INVQ"]["changed_by_action"].get("db") or []  # paths the injected write changes (same in B and Q)
        later = suf[1:]
        obj = next((i for i, m in enumerate(later) if m["role"] == "user" and OBJECT_RE.search(m.get("content") or "")), None)
        writes = [(ai, tc.get("name")) for ai, tc, r in _later_calls(suf) if TT.tool_type(dom, tc.get("name")) == "write"]
        ev = {"user_objection_msg": obj, "later_writes": writes[:10]}
        corr = {"user_objection_then_write": True} if (obj is not None and writes) else None
        bad = [p for p in req["failing"] if p.startswith("db:") and any(p[3:].startswith(c) for c in ch)]
        related = {"definition": "end DB equals gold on every path the premature write changed", "paths": ch,
                   "failing_paths": bad[:10], "satisfied": (not bad) if ch else None}
    return {"error_occurred": manip_ok, "correction": corr, "corrected": corr is not None, **ev,
            "related_requirement": related, "task_success": bool(req["success"]),
            "chain_complete": bool(manip_ok and corr is not None and (related["satisfied"] is True))}


def process_cost(st: dict, br: dict, arm: str) -> dict:
    b = br[arm]
    dec = b.get("decisions") or []
    extra = (b.get("step_count_final") or 0) - st["budget"]["steps_used"]
    return {"extra_steps": extra, "budget_used_frac": round(extra / st["budget"]["steps_left"], 4),
            "tool_errors": (b.get("num_errors_final") or 0) - st["budget"]["errors_used"],
            "agent_turns": len(dec), "completion_tokens": sum(d.get("n_completion_tokens") or 0 for d in dec),
            "termination": b.get("termination_reason")}


# ----------------------------------------------------------------------------
# replay audit (VAL x Q vs the original episode)
# ----------------------------------------------------------------------------


def replay_audit(st: dict, br: dict, an: dict) -> dict:
    from cloq import fork as F
    v = br["VALQ"]
    o = st["orig"]
    blk = _block(st["run_id"], st["domain"])
    tr = blk.traj[st["task_id"]]
    msgs = tr["messages"]
    n0 = F.prefix_len(tr["task"])
    p = F.agent_positions(msgs, n0)[st["decision_idx"]]
    odec = blk.dec[st["task_id"]][st["decision_idx"]:]
    vdec = v.get("decisions") or []
    f = {}

    def eq(name, a, b, src):
        f[name] = {"equal": a == b, "branch": a, "original": b, "source": src}

    def acts(ds):
        return [[d.get("content"), [(tc["name"], F._args(tc["arguments"])) for tc in (d.get("tool_calls") or [])]] for d in ds]

    # initial state at t
    eq("history_prefix", v.get("prefix_ok"), True, "branch.prefix_ok (canonical messages[:n_history] == state.history)")
    eq("history_sha_vs_run", st["history_sha"], F.canon_seq_sha(msgs[:p]),
       "state.history_sha vs canonical sha of runs/<run>/<domain>/trajectory.jsonl messages[:p]")
    eq("db_hash_at_t", (v.get("env_hash_init") or {}).get("db"), st["env_hash"]["db"],
       "branch.env_hash_init (orchestrator env after init) vs state.env_hash (strict replay of the original history at state build)")
    eq("user_db_hash_at_t", (v.get("env_hash_init") or {}).get("user_db"), st["env_hash"]["user_db"], "as above, user DB")
    eq("sim_seed", v.get("sim_seed"), tr["seed"], "branch.sim_seed vs original trajectory seed")
    # budget
    su, eu = F.budget_used(msgs[:p], n0)
    eq("budget_used_at_t", [st["budget"]["steps_used"], st["budget"]["errors_used"]], [su, eu],
       "state.budget vs recount of the original messages[:p]")
    eq("budget_left_at_t", [st["budget"]["steps_left"], st["budget"]["errors_left"]],
       [st["run_config"]["max_steps"] - su, st["run_config"]["max_errors"] - eu], "state.budget left vs run max - recount")
    f["branch_counters_at_t"] = {"equal": None, "status": NR,
                                 "note": "the branch does not store its counters after the restore (run_branch sets step_count/num_errors from "
                                         "state.budget in code; only the tau2 defaults before the override are stored, counters_tau2_default)",
                                 "counters_tau2_default": v.get("counters_tau2_default")}
    eq("budget_final_counters", [v.get("step_count_final"), v.get("num_errors_final")], list(o["budget_final"]),
       "branch step_count_final/num_errors_final vs state.orig.budget_final (recount of the original messages)")
    eq("budget_final_recount", v.get("budget_recount"), list(o["budget_final"]), "branch budget_recount vs state.orig.budget_final")
    # prompts and messages
    eq("first_prompt_ids_sha", vdec[0]["prompt_ids_sha"] if vdec else None, st["q_decision"]["prompt_ids_sha"],
       "branch forced-decision prompt ids vs state.q_decision")
    eq("prompt_ids_sha_seq", [d["prompt_ids_sha"] for d in vdec], o["suffix_prompt_ids_sha"],
       "branch decisions[].prompt_ids_sha vs state.orig.suffix_prompt_ids_sha (original decisions.jsonl)")
    eq("system_sha_seq", [d.get("system_sha256") for d in vdec], [d.get("system_sha256") for d in odec],
       "branch decisions[].system_sha256 vs original decisions.jsonl")
    f["prompt_text_sha256_seq"] = {"equal": None, "status": NR,
                                   "note": "branch decisions keep prompt token-id hashes, not the rendered-prompt sha256 (prompt_sha256)"}
    f["tools_sha_seq"] = {"equal": None, "status": NR, "note": "branch decisions do not store tools_sha256"}
    sv = v.get("suffix") or []
    eq("message_hash_seq", [F.sha(F.canon_msg(m))[:16] for m in sv], [F.sha(F.canon_msg(m))[:16] for m in msgs[p:]],
       "per-message canonical sha, branch suffix vs original messages[p:]")
    # per-turn actions
    eq("actions_seq", acts(vdec), acts(odec), "branch decisions content/tool_calls vs original decisions.jsonl (from t)")
    eq("completion_ids_sha_seq", [d["completion_ids_sha"] for d in vdec[1:]], [F.ids_sha(d.get("completion_token_ids")) for d in odec[1:]],
       "non-forced decisions' completion token ids, branch vs original decisions.jsonl")
    # end
    eq("suffix_sha", v.get("suffix_sha"), o["suffix_sha"], "branch.suffix_sha vs state.orig.suffix_sha")
    eq("n_messages", v.get("n_messages"), o["n_messages"], "branch vs state.orig")
    eq("reward", v.get("reward"), o["reward"], "branch vs state.orig")
    eq("official_reward", v.get("official_reward"), o["official_reward"], "branch vs state.orig")
    eq("db_match", v.get("db_match"), o["db_match"], "branch vs state.orig")
    eq("termination", v.get("termination_reason"), o["termination_reason"], "branch vs state.orig")
    f["final_db_hash"] = {"equal": (v.get("env_hash_final") or {}).get("db") == an["orig_final_db_recomputed"]["db"],
                          "branch": (v.get("env_hash_final") or {}).get("db"), "original": an["orig_final_db_recomputed"]["db"],
                          "source": "original final DB hash is not recorded in the run; recomputed by strict replay of the recorded original "
                                    "messages (runs/<run>/<domain>/trajectory.jsonl)",
                          "branch_replay_eq_final": v.get("env_hash_replay") == v.get("env_hash_final")}
    checked = {k: x["equal"] for k, x in f.items() if x["equal"] is not None}
    return {"state_key": st["inject_key"], "category": st["injection"]["category"], "domain": st["domain"], "task_id": st["task_id"],
            "t": st["decision_idx"], "pass": all(checked.values()), "n_fields_checked": len(checked),
            "failed_fields": [k for k, ok in checked.items() if not ok], "not_recorded": [k for k, x in f.items() if x.get("status") == NR],
            "fields": f}


# ----------------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------------


def summarise_v1(rows):
    """v1 means (unchanged arithmetic), PP naming."""
    ok = [r for r in rows if not r["errors"] and all(k in r["Y"] for k in BR) and all(r["noop_VALQ"].values())]
    cl, nc = _clusters(ok) if ok else (np.array([], int), 0)
    Y = {k: np.array([float(r["Y"][k]) for r in ok]) for k in BR}
    return {"n_states": len(rows), "n_used": len(ok), "n_branch_error": sum(1 for r in rows if r["errors"]),
            "noop_VALQ_rate": round(sum(all(r["noop_VALQ"].values()) for r in rows) / len(rows), 4) if rows else None,
            "R_B": cboot(Y["INVB"] - Y["VALB"], cl, nc), "R_Q": cboot(Y["INVQ"] - Y["VALQ"], cl, nc),
            "R_B_minus_R_Q": cboot((Y["INVB"] - Y["VALB"]) - (Y["INVQ"] - Y["VALQ"]), cl, nc),
            "PP_minus_VAL_B": cboot(Y["PPB"] - Y["VALB"], cl, nc), "PP_minus_VAL_Q": cboot(Y["PPQ"] - Y["VALQ"], cl, nc),
            "success_rates": {k: round(float(v.mean()), 4) if len(v) else None for k, v in Y.items()}}


def _mean(xs):
    return round(float(np.mean(xs)), 3) if xs else None


def analyse(d: Path, procs: int, force: bool) -> dict:
    res = json.loads((d / "inject.json").read_text())
    rows = res["rows"]
    for r in rows:
        r["Y"] = {_pp(k): v for k, v in r["Y"].items()}
        r["errors"] = {_pp(k): v for k, v in r["errors"].items()}
    keys = [r["state_key"] for r in rows]
    cats = sorted({r["category"] for r in rows})
    v1 = {"model": res["model"], "source": str((d / "inject.json").relative_to(ROOT)),
          "naming": "PP = process-perturbation control (NC in inject-v1 files)",
          "all": summarise_v1(rows), "by_category": {c: summarise_v1([r for r in rows if r["category"] == c]) for c in cats},
          "bootstrap": {"B": B, "seed": SEED, "unit": "task (domain, task_id); one state per task"}}
    (d / "summary.json").write_text(json.dumps(v1, indent=1) + "\n")

    an = annotate_dir(d, keys, procs, force)
    states = {k: json.loads((d / "states" / f"{k}.json").read_text()) for k in keys}
    brs = {k: _norm_branches(json.loads((d / "branches" / f"{k}.json").read_text())) for k in keys}

    audit = [replay_audit(states[k], brs[k], an[k]) for k in keys]
    (d / "replay_audit.jsonl").write_text("".join(json.dumps(a, default=str) + "\n" for a in audit))
    apass = {a["state_key"]: a["pass"] for a in audit}

    per_state = []
    for r in rows:
        k = r["state_key"]
        st, br, a = states[k], brs[k], an[k]
        if r["errors"]:
            per_state.append({"state_key": k, "excluded": "branch error", "errors": r["errors"]})
            continue
        m = manipulation(st, br, a, r["Y"])
        ch = {f"INV{c}": chain(st, br, a, f"INV{c}", m[f"INV{c}"]["ok"]) for c in CTRL}
        ch["VAL_related_requirement"] = {c: chain(st, br, a, f"VAL{c}", False)["related_requirement"]["satisfied"] for c in CTRL}
        cost = {b: process_cost(st, br, b) for b in BR}
        per_state.append({"state_key": k, "category": r["category"], "domain": r["domain"], "task_id": r["task_id"], "t": r["t"],
                          "Y": r["Y"], "replay_audit_pass": apass[k], "manipulation": m, "chains": ch, "cost": cost,
                          "D_INV": (r["Y"]["INVB"] - r["Y"]["VALB"]) - (r["Y"]["INVQ"] - r["Y"]["VALQ"]),
                          "D_PP": (r["Y"]["PPB"] - r["Y"]["VALB"]) - (r["Y"]["PPQ"] - r["Y"]["VALQ"])})

    ps = {s["state_key"]: s for s in per_state if "excluded" not in s}
    used = [r for r in rows if r["state_key"] in ps and ps[r["state_key"]]["replay_audit_pass"]]
    used_m = [r for r in used if ps[r["state_key"]]["manipulation"]["all_ok"]]

    def agg(sub_rows):
        ss = [ps[r["state_key"]] for r in sub_rows]
        man = {"n": len(ss), "INV_ok": {c: sum(s["manipulation"]["INV" + c]["ok"] for s in ss) for c in CTRL},
               "VAL_ok": sum(s["manipulation"]["VAL"]["ok"] for s in ss), "PP_ok": sum(s["manipulation"]["PP"]["ok"] for s in ss),
               "VALQ_already_failure": sum(1 - s["manipulation"]["VALQ_success"] for s in ss),
               "INVQ_tool_result_error": sum(bool(s["manipulation"]["INVQ"].get("tool_result_error")) for s in ss),
               "failed_states": [{"state_key": s["state_key"], "category": s["category"],
                                  "failed": [x for x in ("INVB", "INVQ", "VAL", "PP") if not s["manipulation"][x]["ok"]],
                                  "detail": {x: {kk: vv for kk, vv in s["manipulation"][x].items() if kk != "ok"}
                                             for x in ("INVB", "INVQ", "VAL", "PP") if not s["manipulation"][x]["ok"]}}
                                 for s in ss if not s["manipulation"]["all_ok"]]}
        chains = {}
        for c in CTRL:
            cs = [s["chains"]["INV" + c] for s in ss]
            vr = [s["chains"]["VAL_related_requirement"][c] for s in ss]
            chains[c] = {"error_occurred": sum(x["error_occurred"] for x in cs), "corrected": sum(x["corrected"] for x in cs),
                         "related_requirement_satisfied": sum(x["related_requirement"]["satisfied"] is True for x in cs),
                         "related_requirement_na": sum(x["related_requirement"]["satisfied"] is None for x in cs),
                         "chain_complete": sum(x["chain_complete"] for x in cs), "task_success": sum(x["task_success"] for x in cs),
                         "VAL_related_requirement_satisfied": f"{sum(x is True for x in vr)}/{sum(x is not None for x in vr)}"}
        cost = {b: {f: _mean([s["cost"][b][f] for s in ss]) for f in
                    ("extra_steps", "budget_used_frac", "tool_errors", "agent_turns", "completion_tokens")} for b in BR}
        for b in BR:
            terms = {}
            for s in ss:
                terms[s["cost"][b]["termination"]] = terms.get(s["cost"][b]["termination"], 0) + 1
            cost[b]["termination"] = terms
        diffs = {}
        if sub_rows:
            cl, nc = _clusters(sub_rows)
            for c in CTRL:
                for arm in ("INV", "PP"):
                    for f in ("extra_steps", "tool_errors"):
                        x = np.array([s["cost"][arm + c][f] - s["cost"]["VAL" + c][f] for s in ss], float)
                        diffs[f"{arm}{c}-VAL{c}:{f}"] = cboot(x, cl, nc)
        return {"outcomes": outcome_block(sub_rows), "manipulation": man, "event_chains_INV": chains,
                "process_cost_mean": cost, "process_cost_paired_diff": diffs}

    out = {"version": "inject-analysis-v2", "model": res["model"], "dir": str(d.relative_to(ROOT)),
           "naming": "PP = process-perturbation control (Amendment 1; 'NC' keys in inject-v1 files are read as PP)",
           "bootstrap": v1["bootstrap"],
           "definitions": {
               "rescue/damage (A vs ref)": "rescue = Y(A)=1 & Y(ref)=0; damage = Y(A)=0 & Y(ref)=1; turnover = rescue + damage; "
                                           "net = mean Y(A)-Y(ref)",
               "D_INV": "[Y(INV,B)-Y(VAL,B)] - [Y(INV,Q)-Y(VAL,Q)]", "D_PP": "same with PP in place of INV",
               "error_specific_effect": "Y(INV,c) - Y(PP,c) per state: the injection's effect beyond a generic process perturbation",
               "excess_turnover_INV_minus_PP": "1[Y(INV,c) != Y(VAL,c)] - 1[Y(PP,c) != Y(VAL,c)] per state",
               "manipulation": "wrong_id: injected call reproduced and the tool returned an error / not-found; wrong_tool: the intended wrong "
                               "tool was called and executed (its result recorded); premature_write: the write executed and changed the DB; "
                               "VAL: the recorded read executed without error/defect flags (premature_write: a text confirmation request); "
                               "PP: repeated read without error and no DB change",
               "event chain": "error occurred (manipulation ok) -> correction (wrong_id: the same tool later called without error and "
                              "without the bad id; wrong_tool: the valid tool later called without error; premature_write: a user objection "
                              "followed by a later write) -> related requirement satisfied (wrong_id/wrong_tool: all gold action checks on "
                              "the valid tool matched, n/a if the gold has none; premature_write: end DB equals gold on every path the "
                              "injected write changed)",
               "process cost": "extra_steps = final steps - steps used at t; budget_used_frac = extra_steps / steps left at t; tool_errors "
                               "= final errors - errors at t; agent_turns and completion tokens over the branch decisions"},
           "replay_audit": {"n": len(audit), "pass": sum(a["pass"] for a in audit),
                            "failed": [{"state_key": a["state_key"], "fields": a["failed_fields"]} for a in audit if not a["pass"]],
                            "not_recorded": sorted({x for a in audit for x in a["not_recorded"]}),
                            "fields_checked": sorted(k for k, x in audit[0]["fields"].items() if x["equal"] is not None) if audit else [],
                            "file": str((d / "replay_audit.jsonl").relative_to(ROOT))},
           "population": {"n_states": len(rows), "n_used_replay_pass": len(used), "n_used_replay_and_manipulation_pass": len(used_m)},
           "all": agg(used), "by_category": {c: agg([r for r in used if r["category"] == c]) for c in cats},
           "manipulation_pass_only": {"all": outcome_block(used_m),
                                      "by_category": {c: outcome_block([r for r in used_m if r["category"] == c]) for c in cats}},
           "per_state": per_state}
    (d / "summary_v2.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    (d / "summary_v2.md").write_text(render_md(out))
    return out


def _f(x):
    return "n/a" if not x or x.get("est") is None else f"{x['est']:+.3f} [{x['ci95'][0]:+.3f}, {x['ci95'][1]:+.3f}]"


def _turn_rows(o: dict, label: str) -> list[str]:
    L = []
    if not o.get("n"):
        return L
    for c in CTRL:
        for comp in ("INV_vs_VAL", "PP_vs_VAL", "INV_vs_PP"):
            t = o[c][comp]
            L.append(f"| {label} | {c} | {comp.replace('_vs_', ' vs ')} | {t['rescue']} | {t['damage']} | {t['turnover']}/{t['n']} | "
                     f"{_f(t['net'])} | {_f(t['turnover_rate'])} | {t['mcnemar_exact_p']} |")
    return L


def render_md(o: dict) -> str:
    L = [f"# Recovery intervention {o['model']}: per-state turnover, manipulation checks, event chains, replay audit (v2)", "",
         f"Generated by `analysis/recovery/analyze_inject.py` from `{o['dir']}/` (inject.json, states/, branches/). "
         f"PP = process-perturbation control (called NC in inject-v1 files). Intervals: task-clustered bootstrap, B = {B}, seed {SEED}; "
         "p = exact McNemar on discordant pairs. Development data, one block.", ""]
    ra = o["replay_audit"]
    L += ["## Replay audit (VAL×Q vs the original episode)", "",
          f"- **{ra['pass']}/{ra['n']} states pass** every recorded field. Failed: {ra['failed'] or 'none'}.",
          f"- Fields checked: {', '.join(ra['fields_checked'])}.",
          f"- Not recorded: {', '.join(ra['not_recorded']) or 'none'}. The original episode's final DB hash is not stored in the run; "
          "`final_db_hash` compares against a strict replay of the recorded original messages.",
          f"- Per state: `{ra['file']}`.", ""]
    p = o["population"]
    L += [f"States: {p['n_states']}; used (replay pass): {p['n_used_replay_pass']}; replay and manipulation pass: "
          f"{p['n_used_replay_and_manipulation_pass']}.", ""]
    L += ["## Outcome turnover", "",
          "| population | ctrl | contrast | rescue | damage | turnover | net [95% CI] | turnover rate [95% CI] | p |",
          "|---|---|---|---|---|---|---|---|---|"]
    L += _turn_rows(o["all"]["outcomes"], "all")
    for c, s in o["by_category"].items():
        L += _turn_rows(s["outcomes"], c)
    L += ["", "## Controller dependence D and the error-specific effect", "",
          "| population | success INVB VALB PPB / INVQ VALQ PPQ | D_INV | D_INV≠0 | D_INV dist (−2..2) | D_PP | D_PP≠0 | "
          "INV−PP (B) | INV−PP (Q) | excess turnover INV−PP (B) | (Q) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, s in [("all", o["all"])] + list(o["by_category"].items()):
        u = s["outcomes"]
        if not u.get("n"):
            continue
        sc = u["success"]
        L.append(f"| {name} | {sc['INVB']} {sc['VALB']} {sc['PPB']} / {sc['INVQ']} {sc['VALQ']} {sc['PPQ']} | {_f(u['D_INV']['est'])} | "
                 f"{u['D_INV']['n_nonzero']} | {list(u['D_INV']['dist'].values())} | {_f(u['D_PP']['est'])} | {u['D_PP']['n_nonzero']} | "
                 f"{_f(u['B']['error_specific_effect'])} | {_f(u['Q']['error_specific_effect'])} | "
                 f"{_f(u['B']['excess_turnover_INV_minus_PP'])} | {_f(u['Q']['excess_turnover_INV_minus_PP'])} |")
    L += ["", "## Manipulation checks", "", "| population | n | INV ok (B) | INV ok (Q) | INV×Q tool result error | VAL valid | PP ok | VAL×Q already failure |",
          "|---|---|---|---|---|---|---|---|"]
    for name, s in [("all", o["all"])] + list(o["by_category"].items()):
        m = s["manipulation"]
        L.append(f"| {name} | {m['n']} | {m['INV_ok']['B']} | {m['INV_ok']['Q']} | {m['INVQ_tool_result_error']} | {m['VAL_ok']} | {m['PP_ok']} | {m['VALQ_already_failure']} |")
    fs = o["all"]["manipulation"]["failed_states"]
    L += ["", f"States where a manipulation check failed ({len(fs)}):", ""]
    keep = ("called", "tool_result_error", "result", "write_executed", "db_paths_changed", "flags", "is_text_confirmation_request",
            "forced_action_reproduced")
    for x in fs:
        L.append(f"- `{x['state_key']}` ({x['category']}): {', '.join(x['failed'])} — " +
                 "; ".join(f"{k}: {json.dumps({kk: vv for kk, vv in v.items() if kk in keep}, default=str)[:300]}" for k, v in x["detail"].items()))
    mp = o["manipulation_pass_only"]["all"]
    if mp.get("n"):
        L += ["", f"Restricted to replay- and manipulation-pass states (n = {mp['n']}): INV vs VAL turnover B {mp['B']['INV_vs_VAL']['turnover']} "
              f"(net {_f(mp['B']['INV_vs_VAL']['net'])}), Q {mp['Q']['INV_vs_VAL']['turnover']} (net {_f(mp['Q']['INV_vs_VAL']['net'])}); "
              f"D_INV {_f(mp['D_INV']['est'])}, D_INV≠0 in {mp['D_INV']['n_nonzero']}."]
    L += ["", "## Event chains on INV branches (error → correction → related requirement satisfied)", "",
          "| population | ctrl | error occurred | corrected | related req. satisfied | related req. n/a | chain complete | task success | "
          "VAL related req. satisfied |", "|---|---|---|---|---|---|---|---|---|"]
    for name, s in [("all", o["all"])] + list(o["by_category"].items()):
        for c in CTRL:
            e = s["event_chains_INV"][c]
            L.append(f"| {name} | {c} | {e['error_occurred']} | {e['corrected']} | {e['related_requirement_satisfied']} | "
                     f"{e['related_requirement_na']} | {e['chain_complete']} | {e['task_success']} | {e['VAL_related_requirement_satisfied']} |")
    L += ["", "## Process cost per arm (means over states)", "",
          "| population | arm | extra steps | budget used | tool errors | agent turns | completion tokens | termination |",
          "|---|---|---|---|---|---|---|---|"]
    for name, s in [("all", o["all"])] + list(o["by_category"].items()):
        for b in BR:
            x = s["process_cost_mean"][b]
            L.append(f"| {name} | {b} | {x['extra_steps']} | {x['budget_used_frac']} | {x['tool_errors']} | {x['agent_turns']} | "
                     f"{x['completion_tokens']} | {x['termination']} |")
    L += ["", "Paired differences (all used states, task-clustered 95% CI):", ""]
    for k, v in o["all"]["process_cost_paired_diff"].items():
        L.append(f"- {k}: {_f(v)}")
    L += ["", "## Definitions", ""] + [f"- **{k}**: {v}" for k, v in o["definitions"].items()]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--reannotate", action="store_true")
    ap.add_argument("--procs", type=int, default=6)
    a = ap.parse_args()
    from loguru import logger
    logger.remove()
    for d in a.dirs:
        d = (ROOT / d).resolve() if not Path(d).is_absolute() else Path(d)
        if not (d / "inject.json").exists():
            print(f"{d}: no inject.json, skipped")
            continue
        o = analyse(d, a.procs, a.reannotate)
        u = o["all"]["outcomes"]
        print(f"{o['model']}: replay audit {o['replay_audit']['pass']}/{o['replay_audit']['n']}; {o['population']}")
        for c in CTRL:
            t = u[c]
            print(f"  {c}: INV/VAL r{t['INV_vs_VAL']['rescue']} d{t['INV_vs_VAL']['damage']} net {_f(t['INV_vs_VAL']['net'])}; "
                  f"PP/VAL r{t['PP_vs_VAL']['rescue']} d{t['PP_vs_VAL']['damage']}; INV-PP {_f(t['error_specific_effect'])}")
        print(f"  D_INV {_f(u['D_INV']['est'])} nonzero {u['D_INV']['n_nonzero']} {u['D_INV']['dist']}; D_PP nonzero {u['D_PP']['n_nonzero']}")
        print(f"  manipulation failures: {[(x['state_key'], x['category'], x['failed']) for x in o['all']['manipulation']['failed_states']]}")
        print(f"  -> {o['dir']}/summary_v2.md")


if __name__ == "__main__":
    main()
