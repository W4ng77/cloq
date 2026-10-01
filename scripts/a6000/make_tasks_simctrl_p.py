"""Bank P simulator control (W97; GPT-6.1 review 7): freeze 80 first tool-structure divergence states, build queue tasks.

  --freeze   write manifests/fork/simctrl_p_v1.json (refuses to overwrite: a frozen manifest is never edited).
             80 candidate states, 20 per core W4 cell (q4/q8 x gptq_w4_d1/awq_w4), chosen WITHOUT looking at any outcome:
             eligibility = the dev-split retail/airline panel units that analyze_ghf / analyze_dev admit (same snapshot,
             split guard, quarantine, dedupe, strict complete blocks, complete 85-task panel blocks), divergent (Bank P:
             first tool-structure divergence), and re-checkable (RECHECK_RULE). Allocation and order: SAMPLING_RULE.
  --tasks    print the queue tasks (one per cell per batch; --batch 1|2|all, default 1); with --write also write them to
             /data/ziyangs/cloq_work/queue/todo (never overwrites an existing id). Default: print only.
  --estimate throughput / cost estimate from the W95 relay run and the dev branches' user-turn counts of the frozen states
             (counts only, no outcomes) -> analysis/fork/simctrl_p/estimate.json.

usage: python scripts/a6000/make_tasks_simctrl_p.py --freeze
       python scripts/a6000/make_tasks_simctrl_p.py --tasks [--batch 1|2|all] [--write]
       python scripts/a6000/make_tasks_simctrl_p.py --estimate
Run with /data/ziyangs/cloq_work/envs/cloq/bin/python (needs numpy; --freeze loads every dev fork directory).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis" / "fork"))
sys.path.insert(0, str(ROOT / "scripts" / "a6000"))
QUEUE = Path("/data/ziyangs/cloq_work/queue")
MAN = "manifests/fork/simctrl_p_v1.json"
SALT = "simctrl-p-v1"
CELLS = [("q4", "gptq_w4_d1"), ("q4", "awq_w4"), ("q8", "gptq_w4_d1"), ("q8", "awq_w4")]
N_PER_CELL = 20
N_BATCH1 = 10
REPLICATES = 5
ARMS = ["BB", "BQ", "QB", "QQ"]
PRIORITY = -14
NODES = ("node004", "node005", "node007")  # q8 (2-GPU) pinning, as make_tasks_simctrl.py
USER_LLM = {"provider": "relay", "model": "claude-sonnet-5-5 (headless claude -p, one clean call per user turn)",
            "protocol": "simrelay-v2", "max_tokens": 512}
RECHECK_RULE = ("re-checkable state: (1) the Q pivot replay at the state passed (state file q_replay: completion_ids_ok, "
                "prompt_ids_ok and action_ok all true); (2) the QQ no-op replay ran on this state (hash-selected noop sample of "
                "the dev fork, noop|state_id < noop_frac) and reproduced the original suffix, every suffix prompt-id sha, the "
                "termination reason and the step/error counters (analyze_dev.noop_ok checks suffix, prompts, termination, "
                "counters; its 'outcome' key is NOT consulted); (3) the BB, BQ and QB dev branches have prefix_ok and "
                "env_hash_init_ok. This is analyze_ghf's CASE_RULE eligibility without its outcome-based categories.")
SAMPLING_RULE = (
    "Per cell (n = 20): two-level proportional allocation over the eligible states, both levels by largest remainder "
    "(Hamilton). Level 1: domains (retail, airline) in proportion to their eligible counts; ties in the remainder broken by "
    "sha256('simctrl-p-v1:alloc:' + model:cell + ':' + domain). Level 2: within a domain, its blocks in proportion to their "
    "eligible counts; ties broken by sha256('simctrl-p-v1:alloc:' + model:cell + ':' + domain + ':' + block). A stratum never "
    "receives more than it has. Within a stratum (domain, block) states are taken in ascending sha256('simctrl-p-v1:' + "
    "state_id). Batch 1 (10 per cell): per domain floor(k_d / 2) of its k_d selected states, the remaining slot(s) (0 or 1) "
    "to the domain with fewer selected states (ties: airline), so batch 1 is balanced by domain as far as possible; within "
    "a domain the states with the smallest sha256('simctrl-p-v1:' + state_id) go to batch 1. Batch 2 = the other 10. No "
    "outcome (Y, flips, G, H, I, rewards, terminations of any arm) is read by the selection.")


def h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canon_sha(m) -> str:
    from cloq import fork as F

    return hashlib.sha256(json.dumps(F.canon_msg(m), sort_keys=True).encode()).hexdigest()


def hamilton(n: int, counts: dict, tie: dict) -> dict:
    tot = sum(counts.values())
    q = {k: n * v / tot for k, v in counts.items()}
    alloc = {k: min(int(q[k]), counts[k]) for k in counts}
    rest = n - sum(alloc.values())
    order = sorted(counts, key=lambda k: (-(q[k] - int(q[k])), tie[k]))
    while rest > 0:
        moved = False
        for k in order:
            if rest and alloc[k] < counts[k]:
                alloc[k] += 1
                rest -= 1
                moved = True
        if not moved:
            raise SystemExit("allocation impossible: fewer eligible states than requested")
    return alloc


def admitted_units():
    import analyze_dev as AD
    import analyze_ghf as G

    snap = json.load(open(ROOT / G.DEF_SNAPSHOT))
    dirs = G.discover()
    assert not any("/holdout/" in str(d) for d in dirs)
    loaded = [AD.load_dir(d, snap, {}) for d in dirs]
    allu = [u for L in loaded for u in L["units"]]
    split_info = AD.split_guard(allu, "dev", "make_tasks_simctrl_p")
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined fork task (QQ no-op mismatch)")
    units, _ = AD.dedupe_units(allu)
    AD.mark_incomplete_blocks(units, "dev", strict=True)
    AD.mark_partial_panel_blocks(units, "dev")
    ok = [u for u in units if "excluded" not in u]
    ref = json.load(open(ROOT / G.DEF_REFERENCE))
    digest = {}
    for m, c in CELLS:
        cu = [u for u in ok if (u["model"], u["cell"]) == (m, c) and u["domain"] in G.PANEL]
        rd = (ref["cells"].get(f"{m}:{c}") or {}).get("units_digest_sha256")
        digest[f"{m}:{c}"] = {"match": AD.units_digest(cu) == rd, "reference": (rd or "")[:16]}
    meta = {"snapshot": G.DEF_SNAPSHOT, "snapshot_sha256": sha_file(ROOT / G.DEF_SNAPSHOT), "reference": G.DEF_REFERENCE,
            "reference_sha256": sha_file(ROOT / G.DEF_REFERENCE), "units_digest_check_vs_reference": digest, "split": split_info,
            "fork_roots": G.FORK_ROOTS, "quarantined_dirs": [L["dir"] for L in loaded if L["quarantined"]],
            "analyze_dev_sha256": sha_file(AD.__file__), "analyze_ghf_sha256": sha_file(G.__file__),
            "splits_sha256": sha_file(AD.SPLITS)}
    return ok, meta, AD, G


def recheck(u, AD) -> tuple[bool, dict, dict, dict]:
    """RECHECK_RULE; reads the state file and the dev branch file (integrity flags only)."""
    d = ROOT / u["dir"]
    sp, bp = d / "states" / f"{u['state_id']}.json", d / "branches" / f"{u['state_id']}.json"
    if not bp.exists():
        return False, {"branch_file": False}, {}, {}
    st = json.load(open(sp))
    r4 = json.load(open(bp))
    why = {"q_replay": bool(st.get("q_replay")) and all((st.get("q_replay") or {}).values()),
           "a_B_present": bool((st.get("a_B") or {}).get("message"))}
    why["qq_noop_ran"] = "QQ" in r4 and "error" not in r4["QQ"]
    if why["qq_noop_ran"]:
        _, c = AD.noop_ok(st, r4["QQ"])
        why["qq_noop_reproduced"] = all(c[k] for k in ("suffix", "prompts", "termination", "counters"))
    why["b_branches_integrity"] = all(r4.get(b, {}).get("prefix_ok") and r4.get(b, {}).get("env_hash_init_ok") for b in ("BB", "BQ", "QB"))
    return all(why.values()), why, st, r4


def freeze() -> dict:
    import simrelay_cli as SC

    ok, meta, AD, G = admitted_units()
    elig_counts, units_out, by_cell_elig = {}, [], {}
    for m, c in CELLS:
        lab = f"{m}:{c}"
        div = [u for u in ok if (u["model"], u["cell"]) == (m, c) and u["domain"] in G.PANEL and u["div"]]
        el, why_n = [], collections.Counter()
        for u in div:
            good, why, st, _ = recheck(u, AD)
            for k, v in why.items():
                why_n[f"{k}_{'ok' if v else 'fail'}"] += 1
            if good:
                el.append((u, st))
        by_cell_elig[lab] = el
        dom_n = collections.Counter(u["domain"] for u, _ in el)
        blk_n = collections.Counter((u["domain"], u["block"]) for u, _ in el)
        elig_counts[lab] = {"n_admitted_divergent": len(div), "n_eligible": len(el), "by_domain": dict(dom_n),
                            "by_domain_block": {f"{d}|{b}": n for (d, b), n in sorted(blk_n.items())}, "recheck_tallies": dict(why_n)}
        alloc_d = hamilton(N_PER_CELL, dict(dom_n), {d: h(f"{SALT}:alloc:{lab}:{d}") for d in dom_n})
        chosen = []
        for dom, kd in sorted(alloc_d.items()):
            bn = {b: n for (d, b), n in blk_n.items() if d == dom}
            alloc_b = hamilton(kd, bn, {b: h(f"{SALT}:alloc:{lab}:{dom}:{b}") for b in bn}) if kd else {b: 0 for b in bn}
            for b, kb in sorted(alloc_b.items()):
                pool = sorted([x for x in el if x[0]["domain"] == dom and x[0]["block"] == b], key=lambda x: h(f"{SALT}:{x[0]['state_id']}"))
                chosen += pool[:kb]
        assert len(chosen) == N_PER_CELL, (lab, len(chosen))
        k = collections.Counter(u["domain"] for u, _ in chosen)
        b1 = {d: k[d] // 2 for d in k}
        rest = N_BATCH1 - sum(b1.values())
        for d in sorted(k, key=lambda d: (k[d], d != "airline")):
            if rest > 0 and b1[d] < k[d]:
                b1[d] += 1
                rest -= 1
        batch1 = set()
        for d in k:
            for u, _ in sorted([x for x in chosen if x[0]["domain"] == d], key=lambda x: h(f"{SALT}:{x[0]['state_id']}"))[: b1[d]]:
                batch1.add(u["state_id"])
        for u, st in sorted(chosen, key=lambda x: (x[0]["domain"], x[0]["block"], h(f"{SALT}:{x[0]['state_id']}"))):
            sp = ROOT / u["dir"] / "states" / f"{u['state_id']}.json"
            bp = ROOT / u["dir"] / "branches" / f"{u['state_id']}.json"
            units_out.append({
                "unit_id": h(f"{SALT}|unit|{u['state_id']}")[:16], "model": m, "cell": c, "block": u["block"], "domain": u["domain"],
                "task_id": str(st["task_id"]), "t": st["decision_idx"], "run_id": u["run_id"], "state_id": u["state_id"],
                "dir": u["dir"], "state_file": str(sp.relative_to(ROOT)), "state_file_sha256": sha_file(sp),
                "dev_branch_file": str(bp.relative_to(ROOT)), "dev_branch_file_sha256": sha_file(bp),
                "history_sha": st["history_sha"], "prompt_ids_sha": st["q_decision"]["prompt_ids_sha"],
                "a_B_sha": canon_sha(st["a_B"]["message"]), "a_Q_sha": canon_sha(st["a_Q"]["message"]),
                "divergence_category": st["divergence"]["category"], "divergence_type": u.get("type"),
                "n_decisions": u.get("n_decisions"), "steps_left": st["budget"]["steps_left"],
                "stratum": f"{u['domain']}|{u['block']}", "order_key": h(f"{SALT}:{u['state_id']}"),
                "batch": 1 if u["state_id"] in batch1 else 2})
        elig_counts[lab]["allocation_domain"] = alloc_d
        elig_counts[lab]["batch1_by_domain"] = b1
    cnt = collections.Counter
    man = {
        "version": "simctrl_p_v1",
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": ("Bank P simulator control (W97; GPT-6.1 review 7): re-run all four arms of frozen first tool-structure "
                    "divergence states with a second user simulator, to check whether the W93 G/H/F picture of the core W4 "
                    "cells is robust to the simulator."),
        "scope": ("Robustness check on FIXED histories generated with the original simulator. Only the user simulator after "
                  "the fork state changes. 80 states (40 if only batch 1 runs) and R = 5 per arm are too few to confirm or "
                  "refute few-pp G/H/F effects; this is not a benchmark re-run and makes no claim about rates under the new "
                  "simulator beyond these states."),
        "cells": [f"{m}:{c}" for m, c in CELLS],
        "eligibility": {"admission": ("analyze_ghf/analyze_dev admission, dev split only: snapshot gate, split guard (telecom "
                                      "holdout refused and never opened), quarantine, dedupe, strict complete-block rule (W70), "
                                      "complete 85-task retail/airline panel blocks (W78); divergent units only (Bank P = the "
                                      "first tool-structure divergence of the dev search; text-only differences are skipped by "
                                      "the search)"), "recheck": RECHECK_RULE, "counts": elig_counts},
        "sampling_rule": SAMPLING_RULE,
        "selection_reads_no_outcomes": True,
        "source": {**meta, "selector": "scripts/a6000/make_tasks_simctrl_p.py --freeze",
                   "selector_sha256": sha_file(Path(__file__)), "simrelay_cli_sha256": sha_file(Path(SC.__file__)),
                   "user_llm_sha256": sha_file(ROOT / "cloq/user_llm.py")},
        "user_llm": USER_LLM,
        "responder": {
            "daemon": "scripts/a6000/simrelay_cli.py (login node; responder ids cli-<n>; default concurrency 12)",
            "call": ("claude -p --model claude-sonnet-5-5 --tools '' --strict-mcp-config --setting-sources '' --max-turns 1 "
                     "--no-session-persistence --system-prompt <request system_prompt> --output-format json; cwd = an empty "
                     "directory; user message on stdin; CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1; newest installed "
                     "anthropic.claude-code-* binary"),
            "isolation": ("one fresh headless call per user turn: no session, no tools, no MCP, no settings sources, empty cwd; "
                          "no context shared across requests. Residual (identical for every request, no experiment "
                          "identifiers): Claude Code appends its environment block (cwd, platform, date, model name) and an "
                          "account-context reminder to the user message. Sampling settings are Claude Code's defaults "
                          "(not controllable; adaptive thinking on); max_tokens is advisory."),
            "template_version": SC.TEMPLATE["version"], "template": SC.TEMPLATE, "template_sha256": SC.TEMPLATE_SHA256,
            "cleaning": "strip only an accidental code fence, role prefix or surrounding quotes around the whole reply",
            "retries": "up to 3 attempts per claim with backoff; then back to pending (cool-down); never a garbage answer"},
        "relay_protocol": {
            "version": "simrelay-v2 (cloq/user_llm.py)",
            "request_fields": ["req_id", "protocol", "system_prompt", "messages", "max_tokens", "msg_sha256", "stop_token_convention"],
            "req_id": "'v2-' + random uuid4 hex (no state, unit, arm or replicate identifiers)",
            "bookkeeping": "sidecar <root>/meta/<req_id>.json (state_id, unit_id, arm, replicate, branch tag); never read by responders",
            "msg_sha256": "sha256 of the canonical JSON (sort_keys, separators ',' ':', UTF-8) of the exact litellm message list incl. the system message",
            "answer_must_echo": ["req_id", "protocol", "msg_sha256"],
            "on_mismatch": "relay_call raises RelayIntegrityError: the branch fails as infra (missing, never imputed)",
            "root": "/data/ziyangs/cloq_work/simrelay/v2 ($CLOQ_SIMRELAY_DIR/v2), separate from the v1 relay"},
        "replicates": REPLICATES,
        "arms": ARMS,
        "branches": {"XY": "a_X (recorded in the frozen dev state file) forced at h_t, then controller Y (B = BF16, Q = the cell)",
                     "replicates": "R = 5 independent runs per arm per state; keyed '<arm>#<r>'; all 20 branches of a state run concurrently",
                     "servers": "B = BF16; Q = the cell's exact serving config (GPTQ/AWQ W4, calib c1), as the dev forks",
                     "state_checks": ("state file sha; rebuilt state id, history sha, prompt-id sha equal the frozen file and the "
                                      "manifest; a_B/a_Q canonical shas; B regenerates a_B and Q regenerates a_Q exactly from "
                                      "the identical prompt ids (greedy); a failure makes the state missing"),
                     "Y": "retail/airline: db_match and termination in (user_stop, agent_stop) (fork_driver._y)"},
        "unexposed": ("A branch that ends before any user-simulator call (n_user_calls == 0; e.g. the agent stops or the step "
                      "budget ends after tool calls) is recorded exposed: false with its Y kept. It is NOT missing and does not "
                      "fail the protocol check (relay checks apply only when n_user_calls > 0). Reported per arm; estimands are "
                      "computed on all branches, and also on exposed-only as a sensitivity."),
        "analysis_plan": {
            "per_state_arm_means": "Ybar_s,XY = mean over the R = 5 replicates of arm XY on state s (complete replicates only).",
            "estimands": ("G = mean_s(Ybar_BQ - Ybar_QQ), H = mean_s(Ybar_QB - Ybar_QQ), F = mean_s(Ybar_BB - Ybar_QQ), "
                          "G - H = mean_s(Ybar_BQ - Ybar_QB); per cell (equal weight per sampled state; the sample is "
                          "proportionally stratified so no reweighting) and pooled over the 4 cells (equal weight per cell). "
                          "Intervals: bootstrap over states within cell (B = 2000)."),
            "simulator_change": ("Same states, original vs new simulator: original per-state arm outcomes from the frozen dev "
                                 "branch files (one run each; QQ = the recorded original continuation) vs the new arm means; "
                                 "report G/H/F/G-H under each simulator on the SAME 80 (or 40) states and their paired "
                                 "difference; per arm, the agreement of the original Y with the new replicate mean."),
            "within_simulator_variability": "per arm, share of states whose 5 replicates are not all equal.",
            "not_allowed": ("The per-state four binary outcomes must NOT be summarised as an off-diagonal (Delta_Q != Delta_B) "
                            "share comparable to W93's 26.9%: under a stochastic simulator with R = 5 replicate means the "
                            "off-diagonal indicator is not the same quantity (noise alone creates off-diagonal patterns)."),
            "reading": ("Robustness check only: whether the sign/size picture of G/H/F/G-H on these states survives the "
                        "simulator change. It cannot confirm few-pp advantages (n = 80 states)."),
            "missing": "A state with a failed state check, or an arm-replicate with an infra error, is missing (never imputed); counts reported."},
        "batches": {
            "rule": "batch 1 = 10 per cell (40), batch 2 = the other 10 per cell (40); see sampling_rule.",
            "launch_rule": ("Batch 1 runs first. Batch 2 may be launched ONLY on throughput/time grounds (relay throughput, GPU "
                            "and wall time available), decided without looking at any batch-1 outcome; if launched, the "
                            "primary analysis uses all 80, otherwise the 40 of batch 1."),
            "batch1": [u["unit_id"] for u in units_out if u["batch"] == 1],
            "batch2": [u["unit_id"] for u in units_out if u["batch"] == 2]},
        "counts": {"units": len(units_out), "by_cell": dict(cnt(f"{u['model']}:{u['cell']}" for u in units_out)),
                   "by_cell_domain": dict(cnt(f"{u['model']}:{u['cell']}|{u['domain']}" for u in units_out)),
                   "by_cell_domain_batch": dict(cnt(f"{u['model']}:{u['cell']}|{u['domain']}|b{u['batch']}" for u in units_out)),
                   "by_cell_block": dict(cnt(f"{u['model']}:{u['cell']}|{u['block']}" for u in units_out)),
                   "by_divergence_type": dict(cnt(u["divergence_type"] for u in units_out))},
        "tasks": {"builder": "scripts/a6000/make_tasks_simctrl_p.py --tasks --batch 1|2 [--write]",
                  "per_task": "one task per cell per batch; q4: 1 GPU (gpu_util 0.44); q8: 2 GPUs pinned to node004/005/007; priority -14",
                  "unit_concurrency": 5},
        "units": units_out,
    }
    return man


def qrole(m, cell):  # as make_tasks_simctrl.qrole / the dev forks
    return {"ckpt": {"kind": "gptq" if cell.startswith("gptq") else "awq", "wbits": 4, "calib": f"manifests/a6k2/{m}/calib_fp_traj_c1.json"}}


def task(m, c, man_sha, units, batch, i, prio):
    tid = f"simctrl_p_b{batch}_{m}_{c}"
    spec = {"mode": "simctrl_p", "manifest": MAN, "manifest_sha256": man_sha, "model": m, "cell": c, "unit_ids": units,
            "user_llm": USER_LLM, "arms": ARMS, "replicates": REPLICATES, "concurrency": 5,
            "out": f"analysis/fork/simctrl_p/{m}_{c}/b{batch}"}
    return {"id": tid, "kind": "fork", "model": m, "gpus": 1 if m == "q4" else 2,
            **({"gpu_util": 0.44} if m == "q4" else {"node": NODES[i % 3]}), "priority": prio, "deps": [],
            "B": {"ckpt": {"kind": "bf16"}}, "Q": qrole(m, c), "fork": spec,
            "note": (f"W97 Bank P simulator control, batch {batch} (simrelay-v2: needs scripts/a6000/simrelay_cli.py running on "
                     "the login node; make_tasks_simctrl_p.py)")}


def estimate(man: dict) -> dict:
    """Counts only: user turns per branch of the original dev branches (BB/BQ/QB, + QQ = the original continuation from the
    trajectory) of the frozen states, and the W95 relay run's per-branch user-call counts and durations."""
    w95 = []
    agent_per_turn, relay_lat = [], []
    for p in sorted((ROOT / "analysis/fork/simctrl_relay").glob("*/f01/branches/*.json")):  # the W95 run (6 cells, f01)
        for a, b in json.loads(p.read_text())["arms"].items():
            if "error" in b or not b.get("duration"):
                continue
            cs = b.get("user_llm_calls") or []
            lat = sum(c.get("latency_s") or 0 for c in cs)
            w95.append({"dur": b["duration"], "n_calls": len(cs)})
            relay_lat += [c["latency_s"] for c in cs if c.get("latency_s")]
            if cs:
                agent_per_turn.append((b["duration"] - lat) / len(cs))
    w95_calls = [x["n_calls"] for x in w95]
    w95_dur = [x["dur"] for x in w95]
    per_state, turns_all = {}, []
    for u in man["units"]:
        r4 = json.load(open(ROOT / u["dev_branch_file"]))
        st = json.load(open(ROOT / u["state_file"]))
        nb = {b: r4[b].get("n_user_msgs") for b in ("BB", "BQ", "QB") if b in r4 and r4[b].get("n_user_msgs") is not None}
        tr_suffix = None
        if "QQ" in r4 and r4["QQ"].get("n_user_msgs") is not None:
            tr_suffix = r4["QQ"]["n_user_msgs"]
        nb["QQ"] = tr_suffix
        vals = [v for v in nb.values() if v is not None]
        per_state[u["unit_id"]] = {"batch": u["batch"], "turns": nb, "mean": statistics.mean(vals) if vals else None,
                                   "unexposed_arms_orig": [b for b, v in nb.items() if v == 0]}
        turns_all += vals
    out = {"w95": {"n_branches": len(w95), "user_calls_per_branch_mean": statistics.mean(w95_calls) if w95 else None,
                   "user_calls_per_branch_median": statistics.median(w95_calls) if w95 else None,
                   "branch_seconds_median": statistics.median(w95_dur) if w95 else None,
                   "branch_seconds_mean": statistics.mean(w95_dur) if w95 else None,
                   "relay_latency_s_median_subagents": statistics.median(relay_lat) if relay_lat else None,
                   "agent_seconds_per_user_turn_median": statistics.median(agent_per_turn) if agent_per_turn else None,
                   "agent_seconds_per_user_turn_mean": statistics.mean(agent_per_turn) if agent_per_turn else None},
           "dev_user_turns_per_branch_mean": statistics.mean(turns_all), "dev_user_turns_per_branch_median": statistics.median(turns_all),
           "dev_share_branches_zero_user_turns": sum(1 for v in turns_all if v == 0) / len(turns_all)}
    calls = {}
    for b in ("1", "both"):
        ss = [s for s in per_state.values() if b == "both" or s["batch"] == 1]
        calls[b] = sum(4 * REPLICATES * (s["mean"] or 0) for s in ss)
    out["user_calls_expected"] = {"batch1": round(calls["1"]), "both": round(calls["both"])}
    A = out["w95"]["agent_seconds_per_user_turn_median"] or 12.0
    out["simulation"] = {"assumptions": {
        "agent_seconds_per_turn": A, "cli_seconds_per_call": CLI_S, "relay_poll_overhead_s": POLL_S,
        "replicate_turns": "each replicate of arm XY has the dev branch's user-turn count of XY on that state (QQ: the no-op replay = original)",
        "tasks": "4 cell tasks of a batch run at once on separate GPUs; unit concurrency 5 per task (20 branches per unit at once)",
        "excluded": "checkpoint build + vLLM start per task (~10-20 min) and GPU contention"}}
    for b in ("1", "both"):
        for c in (12, 24):
            out["simulation"][f"batch{b}_c{c}"] = simulate(man, per_state, b, c, A)
    cost = {"usd_per_call_measured_w97_test": COST_PER_CALL, "usd_per_call_range_given": [0.015, 0.03]}
    for b, n in out["user_calls_expected"].items():
        cost[b] = {"at_measured": round(n * COST_PER_CALL, 2), "at_0.015": round(n * 0.015, 2), "at_0.03": round(n * 0.03, 2)}
    out["cost_usd"] = cost
    out["per_state"] = per_state
    return out


CLI_S = 4.0  # seconds per headless call (2.3-3.2 s in the W97 relay test; ~4 s reported); conservative
POLL_S = 1.8  # branch polls done/ every 3 s (mean 1.5 s) + daemon claim poll 0.3 s
COST_PER_CALL = 0.0074  # mean total_cost_usd of the 3 real calls in the W97 relay test (side model call disabled)


def simulate(man: dict, per_state: dict, batch: str, c: int, A: float) -> dict:
    """Discrete-event FIFO model: per task (cell) units run 5 at a time; a branch alternates agent phases (A s) and user
    calls served by c CLI slots (CLI_S + POLL_S s each). Returns the wall time to finish all branches (hours)."""
    import heapq

    ev, seq = [], 0
    q, free, t_end, ncalls = collections.deque(), c, 0.0, 0
    tasks = collections.defaultdict(list)
    for u in man["units"]:
        if batch == "both" or u["batch"] == 1:
            tasks[(u["model"], u["cell"])].append(u["unit_id"])
    pend_units = {k: list(v) for k, v in tasks.items()}
    left = {}  # unit -> branches still running

    def push(t, kind, data):
        nonlocal seq
        seq += 1
        heapq.heappush(ev, (t, seq, kind, data))

    def start_unit(t, k):
        if not pend_units[k]:
            return
        uid = pend_units[k].pop(0)
        turns = per_state[uid]["turns"]
        left[uid] = 0
        for arm in ARMS:
            for _ in range(REPLICATES):
                left[uid] += 1
                push(t + A, "agent_done", (k, uid, turns.get(arm) or 0))

    for k in tasks:
        for _ in range(5):
            start_unit(0.0, k)
    while ev:
        t, _, kind, data = heapq.heappop(ev)
        t_end = max(t_end, t)
        if kind == "agent_done":
            k, uid, rem = data
            if rem <= 0:
                left[uid] -= 1
                if left[uid] == 0:
                    start_unit(t, k)
                continue
            if free:
                free -= 1
                ncalls += 1
                push(t + CLI_S + POLL_S, "call_done", (k, uid, rem))
            else:
                q.append((k, uid, rem))
        elif kind == "call_done":
            k, uid, rem = data
            push(t + A, "agent_done", (k, uid, rem - 1))
            if q:
                ncalls += 1
                push(t + CLI_S + POLL_S, "call_done", q.popleft())
            else:
                free += 1
    return {"hours": round(t_end / 3600, 2), "n_calls": ncalls, "throughput_bound_hours": round(ncalls * (CLI_S + POLL_S) / c / 3600, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--tasks", action="store_true")
    ap.add_argument("--batch", default="1", choices=["1", "2", "all"])
    ap.add_argument("--priority", type=int, default=PRIORITY)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--estimate", action="store_true")
    a = ap.parse_args()
    mp = ROOT / MAN
    if a.freeze:
        if mp.exists():
            raise SystemExit(f"{MAN} exists (frozen); never overwritten")
        man = freeze()
        mp.write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n")
        print(json.dumps(man["counts"], indent=1))
        print(json.dumps({k: {kk: v[kk] for kk in ("n_admitted_divergent", "n_eligible", "by_domain", "allocation_domain", "batch1_by_domain")}
                          for k, v in man["eligibility"]["counts"].items()}, indent=1))
        print("sha256", sha_file(mp))
        return
    man = json.loads(mp.read_text())
    man_sha = sha_file(mp)
    if a.estimate:
        est = estimate(man)
        p = ROOT / "analysis/fork/simctrl_p/estimate.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(est, indent=1) + "\n")
        print(json.dumps({k: v for k, v in est.items() if k != "per_state"}, indent=1))
        return
    if a.tasks:
        T = []
        for b in ((1, 2) if a.batch == "all" else (int(a.batch),)):
            for i, (m, c) in enumerate(CELLS):
                ids = [u["unit_id"] for u in man["units"] if (u["model"], u["cell"]) == (m, c) and u["batch"] == b]
                T.append(task(m, c, man_sha, ids, b, i, a.priority))
        for t in T:
            print(t["id"], "gpus", t["gpus"], t.get("node", ""), len(t["fork"]["unit_ids"]), "units", "prio", t["priority"], "out", t["fork"]["out"])
        if a.write:
            n = 0
            for t in T:
                if not any((QUEUE / d / f"{t['id']}.json").exists() for d in ("todo", "running", "done", "failed")):
                    json.dump(t, open(QUEUE / "todo" / f"{t['id']}.json", "w"), indent=1)
                    n += 1
            print("wrote", n)
        else:
            print("(print only; --write to queue)")


if __name__ == "__main__":
    main()
