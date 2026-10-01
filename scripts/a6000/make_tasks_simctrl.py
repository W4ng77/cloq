"""Simulator robustness control for Bank U text-structure flips (W90; GPT-6.1 review 5, author-approved option A).

  --freeze   build manifests/fork/simctrl_v1.json from the finished Bank U f01 rows: every deduplicated class (ii)
             outcome change (M = 1; same tool structure, different text) plus a 1:1 matched class (ii) NON-flip control
             (M = 0) from the same model x cell x sub-bank x block and the same sub-class (ii_talk / ii_act), nearest in
             action length and relative position, ties broken by a frozen sha256. Refuses to overwrite an existing
             manifest (a frozen manifest is never edited; make a v2).
  --gate     write the acceptance-gate task (3 states of q4 GPTQ-W4 d1, BQ + QQ with the Sonnet user) to the queue.
  --tasks    write the 6 per-cell tasks (all manifest units of that model x cell); each depends on the gate task.
  --write    actually write queue files (default: print only). --gate/--tasks refuse to write unless the key file exists.

Branches: BQ (a_B forced at h_t, the cell's Q continues) and QQ (a_Q forced, Q continues), exactly the original Bank U
native arms; only the user simulator after h_t is replaced by claude-sonnet-5-5 (cloq/user_llm.py). Both current
actions are the ones recorded in the Bank U row; the B server regenerates a_B and the Q server a_Q as a reconstruction
check (greedy, must be identical).

usage: python scripts/a6000/make_tasks_simctrl.py --freeze
       python scripts/a6000/make_tasks_simctrl.py --gate [--write]
       python scripts/a6000/make_tasks_simctrl.py --tasks [--write]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis" / "fork"))
QUEUE = Path("/data/ziyangs/cloq_work/queue")
MAN = "manifests/fork/simctrl_v1.json"
BANK = "manifests/fork/bank_u_v1.json"
NODES = ("node004", "node005", "node007")
SALT = "simctrl-v1"
USER_LLM = {"provider": "anthropic", "model": "claude-sonnet-5-5", "max_tokens": 512, "thinking": {"type": "between_tools"},
            "timeout": 600}
CELLS = [(m, c) for m in ("q4", "q8") for c in ("gptq_w4_d1", "awq_w4", "kvq_int8")]


def h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def qrole(m, cell):  # identical to make_tasks_bank_u.py (the cell's exact serving config)
    if cell == "kvq_int8":
        return {"ckpt": {"kind": "bf16"}, "serve_env": {"CLOQ_PYHOOKS": "1", "CLOQ_KVQ_BITS": "8"}}
    ck = {"kind": "gptq" if cell.startswith("gptq") else "awq", "wbits": 4, "calib": f"manifests/a6k2/{m}/calib_fp_traj_c1.json"}
    return {"ckpt": ck}


def block_status() -> dict:
    out = {}
    for m, c in CELLS:
        for b in ("f01", "f02", "f03"):
            d = ROOT / "analysis/fork/bank_u" / f"{m}_{c}" / b
            out[f"{m}_{c}/{b}"] = "landed" if (d / "bank_summary.json").exists() else "pending"
    return out


def unit_key(u: dict) -> str:
    return f"{u['model']}|{u['cell']}|{u['block']}|{u['sub']}|{u['state_key']}"


def freeze(blocks: list[str]) -> dict:
    import analyze_bank_u as A

    inputs: dict = {}
    native, _, notes = A.load(inputs)
    rows = {(r["model"], r["cell"], r["block"], r["sub"], r["state_key"]): r for r in native if r["block"] in blocks}
    us = [u for u in A.build_units(list(rows.values()))]
    A.mark_unique_for_pools(us)
    for u in us:
        r = rows[(u["model"], u["cell"], u["block"], u["sub"], u["state_key"])]
        lb, lq = len(A.text_of(r["a_B"])), len(A.text_of(r["a_Q"]))
        u.update({"len_B": lb, "len_Q": lq, "len_mean": (lb + lq) / 2, "t": r["t"], "n_decisions": r["n_decisions"],
                  "pos": r["t"] / max(r["n_decisions"], 1), "domain": r["domain"], "task_id": r["task_id"],
                  "source_run": r["source_run"], "history_sha": r["history_sha"], "prompt_ids_sha": r["prompt_ids_sha"]})
    elig = [u for u in us if u["cls"] == "ii" and not u["dup_of"]]
    flips = sorted([u for u in elig if u["M"] == 1], key=lambda u: h(f"{SALT}|order|{unit_key(u)}"))
    pool = collections.defaultdict(list)
    for u in elig:
        if u["M"] == 0:
            pool[(u["model"], u["cell"], u["block"], u["sub"], u["sub_cls"])].append(u)

    def dist(f, c):
        return abs(math.log((1 + f["len_mean"]) / (1 + c["len_mean"]))) + abs(f["pos"] - c["pos"])

    used, pairs = set(), []
    for f in flips:
        key = (f["model"], f["cell"], f["block"], f["sub"], f["sub_cls"])
        cands = [c for c in pool[key] if unit_key(c) not in used]
        relaxed = False
        if not cands:  # never happened at freeze for f01; recorded if it does
            relaxed = True
            cands = [c for k2, v in pool.items() if k2[:4] == key[:4] for c in v if unit_key(c) not in used]
        if not cands:
            pairs.append((f, None, {"unmatched": True, "pool_size": 0}))
            continue
        best = min(cands, key=lambda c: (round(dist(f, c), 9), h(f"{SALT}|tie|{unit_key(f)}|{unit_key(c)}")))
        used.add(unit_key(best))
        pairs.append((f, best, {"distance": round(dist(f, best), 6), "pool_size": len(cands), "relaxed_sub_cls": relaxed}))

    def rec(u, role, pair_id, match):
        r = rows[(u["model"], u["cell"], u["block"], u["sub"], u["state_key"])]
        return {"unit_id": h(f"{SALT}|unit|{unit_key(u)}")[:16], "role": role, "pair_id": pair_id, "model": u["model"], "cell": u["cell"],
                "block": u["block"], "sub": u["sub"], "state_key": u["state_key"], "state_id": u["state_id"], "domain": u["domain"],
                "task_id": u["task_id"], "t": u["t"], "n_decisions": u["n_decisions"], "source_run": u["source_run"],
                "history_sha": u["history_sha"], "prompt_ids_sha": u["prompt_ids_sha"], "sub_cls": u["sub_cls"],
                "Y_orig": u["Y"], "r_orig": u["r"], "d_orig": u["d"], "M_orig": u["M"],
                "direction_orig": "rescue" if u["r"] else "damage" if u["d"] else "none",
                "len_B": u["len_B"], "len_Q": u["len_Q"], "pos": round(u["pos"], 6),
                "a_B_sha": h(u["a_B_canon"]), "a_Q_sha": h(u["a_Q_canon"]), "match": match}

    units = []
    for f, c, mt in pairs:
        pid = h(f"{SALT}|pair|{unit_key(f)}")[:12]
        units.append(rec(f, "flip", pid, mt))
        if c is not None:
            units.append(rec(c, "control", pid, mt))
    bank_files = {}
    for m, c in CELLS:
        for b in blocks:
            p = ROOT / "analysis/fork/bank_u" / f"{m}_{c}" / b / "bank_rows.jsonl"
            bank_files[str(p.relative_to(ROOT))] = sha_file(p)
    n_f = sum(1 for u in units if u["role"] == "flip")
    n_c = sum(1 for u in units if u["role"] == "control")
    man = {
        "version": "simctrl_v1",
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": "Second user-simulator robustness control for Bank U text-structure flips (GPT-6.1 review 5, option A).",
        "scope": ("Robustness of continuations on FIXED histories generated with the old simulator (Qwen3-4B-Instruct-2507). "
                  "Only the user simulator after the fork state is replaced. It does NOT replace a full benchmark re-run with a "
                  "new simulator, and makes no claim about Bank U rates under Sonnet."),
        "blocks": blocks,
        "blocks_note": ("f01 only: at freeze time f02/f03 had not landed for every cell "
                        f"(pending: {[k for k, v in block_status().items() if v == 'pending']})."),
        "block_status_at_freeze": block_status(),
        "source": {"bank_manifest": BANK, "bank_manifest_sha256": sha_file(ROOT / BANK), "bank_rows_sha256": bank_files,
                   "selector": "scripts/a6000/make_tasks_simctrl.py --freeze (taxonomy/dedup from analysis/fork/analyze_bank_u.py)"},
        "flip_rule": ("Bank U native rows of the listed blocks with taxonomy class (ii) (a_B, a_Q same tool structure, different "
                      "text; sub-classes ii_talk = both talk, ii_act = same tool calls, different content) and M = |Y_BQ - Y_QQ| = 1; "
                      "deduplicated within model x cell x block (a state in several sub-banks kept once: U1 > U2B > U2Q), as in W84."),
        "matching_rule": ("1:1 without replacement. Candidates: class (ii), M = 0, deduplicated, same model, cell, block, sub-bank and "
                          "sub-class as the flip. Distance = |ln((1 + L_f) / (1 + L_c))| + |p_f - p_c|, L = mean whitespace-normalised "
                          "character length of a_B and a_Q, p = t / n_decisions. Flips are processed in sha256('simctrl-v1|order|' + key) "
                          "order; ties broken by sha256('simctrl-v1|tie|' + flip key + '|' + candidate key). key = model|cell|block|sub|state_key."),
        "user_llm": USER_LLM,
        "user_llm_params_note": ("model id claude-sonnet-5-5 via litellm 'anthropic/claude-sonnet-5-5' (tau2's own UserSimulator, "
                                 "system prompt and stop logic unchanged). temperature: NOT settable (the model rejects non-default "
                                 "sampling with a 400), so the API default applies; seed: not supported (the orchestrator's seed is dropped "
                                 "and the drop recorded); thinking off via {'type': 'between_tools'} (default effort high); max_tokens 512 "
                                 "= the old simulator's. No server-side refusal fallback (it would change the simulator model). "
                                 "Request ids and token usage are recorded per user call. One Sonnet run per arm."),
        "old_user": {"llm_user": "hosted_vllm/user", "model": "Qwen/Qwen3-4B-Instruct-2507", "temperature": 0.0, "top_p": 1.0,
                     "max_tokens": 512, "seed": "per-task sim_seed"},
        "branches": {"BQ": "a_B (recorded in the Bank U row) forced at h_t, then the cell's Q controller",
                     "QQ": "a_Q (recorded) forced at h_t, then the cell's Q controller",
                     "servers": "B = BF16 (only to regenerate a_B as a reconstruction check), Q = the cell's exact serving config",
                     "Y": "retail/airline: db_match and termination in (user_stop, agent_stop) (fork_driver._y)"},
        "acceptance_gate": {
            "task": "simctrl_gate_q4_gptq_w4_d1 (3 manifest units of q4 GPTQ-W4 d1, first 3 by sha256 order)",
            "checks": ["state rebuilt: history_sha and prompt_ids_sha equal the Bank U row; B regenerates a_B and Q regenerates a_Q exactly",
                       "user protocol: every branch's first Sonnet request has system-prompt sha == tau2 UserSimulator system prompt built "
                       "from the task's user instructions, and its message list starts with the flipped user-visible history (role, content)",
                       "tool interface: retail/airline user has no tools (request carries none); telecom is not in Bank U",
                       "hidden user state: the system prompt carries the task instructions; env hash at init == state env hash; prefix_ok",
                       "termination: a user_stop branch ends on a user message containing ###STOP### / ###TRANSFER### / "
                       "###OUT-OF-SCOPE###, and no earlier user message contains one",
                       "every user call is anthropic/claude-sonnet-5-5 with a request id and usage; no API errors"],
            "rule": "Analysis is run only if the gate passes (analyze_simctrl.py refuses otherwise)."},
        "analysis_plan": {
            "script": "analysis/fork/analyze_simctrl.py",
            "flips": ("Among the original flips: Sonnet M' = |Y'_BQ - Y'_QQ|. 'retained' = M' = 1 with the same direction "
                      "(rescue: Y'_BQ = 1, Y'_QQ = 0; damage: the reverse); 'reversed' = M' = 1 with the opposite direction; "
                      "'vanished' = M' = 0 (split into both-succeed / both-fail). Counts per model, per sub-bank, per sub-class, all."),
            "controls": "Among the matched controls: newly appearing flips (M' = 1), split rescue / damage; counts per model, sub-bank, all.",
            "paired": "Per pair: (flip retained, control newly flips) cross-tab; descriptive.",
            "secondary": "Arm-level agreement Y'_arm == Y_arm per arm and role; termination reasons; Sonnet token usage and cost.",
            "no_threshold": "No pass/fail threshold on retention is pre-specified; counts with exact binomial 95% intervals are reported.",
            "missing": "A unit with an errored arm is reported as missing (never imputed); missing counts are reported per role."},
        "counts": {"flips": n_f, "controls": n_c, "unmatched_flips": sum(1 for _, c, _ in pairs if c is None),
                   "flips_by_model_sub_cls": dict(collections.Counter(f"{u['model']}:{u['sub']}:{u['sub_cls']}" for u in units if u["role"] == "flip")),
                   "flips_by_direction": dict(collections.Counter(u["direction_orig"] for u in units if u["role"] == "flip")),
                   "units_by_cell": dict(collections.Counter(f"{u['model']}_{u['cell']}" for u in units)),
                   "relaxed_matches": sum(1 for u in units if u["role"] == "flip" and u["match"].get("relaxed_sub_cls"))},
        "units": units,
    }
    return man


def gate_units(man: dict) -> list[str]:
    us = sorted([u for u in man["units"] if (u["model"], u["cell"]) == ("q4", "gptq_w4_d1")], key=lambda u: h(f"{SALT}|gate|{u['unit_id']}"))
    return [u["unit_id"] for u in us[:3]]


def task(m, c, man_sha, units, tid, out, prio, deps, i):
    spec = {"mode": "simctrl", "manifest": MAN, "manifest_sha256": man_sha, "model": m, "cell": c, "unit_ids": units,
            "user_llm": USER_LLM, "arms": ["BQ", "QQ"], "concurrency": 6, "out": out}
    return {"id": tid, "kind": "fork", "model": m, "gpus": 1 if m == "q4" else 2, **({"gpu_util": 0.44} if m == "q4" else {"node": NODES[i % 3]}),
            "priority": prio, "deps": deps, "B": {"ckpt": {"kind": "bf16"}}, "Q": qrole(m, c), "fork": spec,
            "note": "W90 simulator control (make_tasks_simctrl.py; Sonnet 5.5 user, Bank U f01 class (ii) flips + matched controls)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--blocks", nargs="*", default=["f01"])
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--tasks", action="store_true")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    mp = ROOT / MAN
    if a.freeze:
        if mp.exists():
            raise SystemExit(f"{MAN} exists (frozen); never overwritten")
        man = freeze(a.blocks)
        mp.write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n")
        print(json.dumps(man["counts"], indent=1))
        print("sha256", sha_file(mp))
        return
    man = json.loads(mp.read_text())
    man_sha = sha_file(mp)
    T = []
    if a.gate:
        T.append(task("q4", "gptq_w4_d1", man_sha, gate_units(man), "simctrl_gate_q4_gptq_w4_d1", "analysis/fork/simctrl/gate", -12, [], 0))
    if a.tasks:
        for i, (m, c) in enumerate(CELLS):
            ids = [u["unit_id"] for u in man["units"] if (u["model"], u["cell"]) == (m, c)]
            if ids:
                T.append(task(m, c, man_sha, ids, f"simctrl_{m}_{c}_f01", f"analysis/fork/simctrl/{m}_{c}/f01", -12,
                              ["simctrl_gate_q4_gptq_w4_d1"], i))
    for t in T:
        print(t["id"], t["gpus"], t.get("node", ""), len(t["fork"]["unit_ids"]), "units", "deps", t["deps"])
    if a.write and T:
        from cloq import user_llm as UL

        if not UL.key_available():
            raise SystemExit(f"no API key file at {UL.key_file()}: not queueing Sonnet tasks")
        n = 0
        for t in T:
            if not any((QUEUE / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
                json.dump(t, open(QUEUE / "todo" / f"{t['id']}.json", "w"), indent=1)
                n += 1
        print("wrote", n)


if __name__ == "__main__":
    main()
