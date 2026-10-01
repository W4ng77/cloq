"""WP5: content characterization of τ² development fork states (EXECUTION_PLAN_20260930.md §5.4; CONSEQUENCE_ANALYSIS_PLAN.md §7).

Subcommands (all CPU; the LLM labeller only sends HTTP requests to an existing simulator replica):
  sample   freeze the review sample from the latest analysis/fork/out/consequence_units_*.jsonl:
           frame = divergent units that passed the replay gate and have their branch files; strata = consequence sign
           (rescue / damage / both_succeed / both_fail; sign of Y_BQ vs Y_QQ) x family (W4 = GPTQ-W4 + AWQ-W4, KV8, stress =
           GPTQ-W3 + KV4) x domain. 20 states per sign, allocated over the sign's non-empty strata proportionally to
           frame size (largest remainder, at least one per stratum, ties by stratum name), units drawn in
           sha256(salt|state_id|dir) order, preferring tasks not yet in the sample (a task is reused only when a stratum
           runs out, never twice in one stratum). 5 states per
           sign (20) are double-reviewed (first 5 selected of that sign in hash order). Each unit carries its
           stratum frame size and its approximate inclusion probability (n/N): sample frequencies are NOT prevalences.
           -> manifests/annotation/wp5_sample_v1.json (refuses to overwrite a different sample)
  events   automatic event extraction for the sampled states, all four branches (QQ = the original episode suffix):
           cloq.fork_annotate defect / correction / requirements plus the WP5 event list (wrong tool / argument / id,
           consent-before-write, irreversible DB mutation, retry loops, transfer to a human, correction after the pivot,
           premature completion, budget exhaustion) and process costs (turns, tool calls, tool errors, agent and
           simulator tokens, steps / errors consumed, termination).  -> analysis/annotation/wp5/events.jsonl
  packets  blinded human-review packets (pass 1: current decision with the two actions as X / Y in hashed order;
           pass 2: the four suffixes as S1..S4 in hashed order), with no model / precision / quantizer / outcome /
           effect values; the unblinding key is written OUTSIDE the repository (cloq_work/annotation/) and only its
           sha256 is committed.  -> analysis/annotation/wp5/packets/
  llm      LLM labels with the frozen rubric (docs/insights/WP5_RUBRIC_v1.md, sha checked against the frozen hash in
           manifests/annotation/wp5_rubric_freeze.json) on the same blinded views, greedy, evidence spans required.
           -> analysis/annotation/wp5/llm_labels.jsonl (provenance per record)

usage: python -m cloq.wp5 {sample|events|packets|llm} [...]
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import glob
import hashlib
import html
import json
import math
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = Path("/data/ziyangs/cloq_work")
SAMPLE = ROOT / "manifests/annotation/wp5_sample_v1.json"
OUTD = ROOT / "analysis/annotation/wp5"
KEYD = WORK / "annotation"
RUBRIC = ROOT / "docs/insights/WP5_RUBRIC_v1.md"
RUBRIC_FREEZE = ROOT / "manifests/annotation/wp5_rubric_freeze.json"
SALT = "wp5-sample-v1"
FAMILY = {"gptq_w4_d1": "W4", "awq_w4": "W4", "kvq_int8": "KV8", "gptq_w3": "stress", "kvq_int4_rot": "stress", "kvq_int4": "stress"}
SIGNS = ["rescue", "damage", "both_succeed", "both_fail"]
N_PER_SIGN, N_DOUBLE_PER_SIGN = 20, 5


def sha(x) -> str:
    return hashlib.sha256((x if isinstance(x, str) else json.dumps(x, sort_keys=True, default=str)).encode()).hexdigest()


def sha_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sign_of(y: dict) -> str:
    return {(1, 0): "rescue", (0, 1): "damage", (1, 1): "both_succeed", (0, 0): "both_fail"}[(int(y["BQ"]), int(y["QQ"]))]


# ----------------------------------------------------------------------------
# sample
# ----------------------------------------------------------------------------


def cmd_sample(a) -> None:
    src = Path(a.units) if a.units else Path(sorted(glob.glob(str(ROOT / "analysis/fork/out/consequence_units_*.jsonl")))[-1])
    frame = []
    for l in open(src):
        u = json.loads(l)
        if u.get("eligibility_status") != "divergent" or not u.get("replay_gate_pass") or u.get("cell") not in FAMILY:
            continue
        d = ROOT / u["branch_artifact_refs"]["dir"]
        if not (d / "states" / f"{u['state_id']}.json").exists() or not (d / "branches" / f"{u['state_id']}.json").exists():
            continue
        frame.append({"state_id": u["state_id"], "dir": u["branch_artifact_refs"]["dir"], "domain": u["domain"], "task_id": u["task_id"],
                      "model": u["model_id"], "cell": u["cell"], "family": FAMILY[u["cell"]], "block": u.get("prompt_block_id"),
                      "sign": sign_of(u["Y"]), "pattern": u["pattern_BB_BQ_QB_QQ"], "divergence_type": u.get("divergence_type"),
                      "decision_idx": u["decision_idx"]})
    strata = collections.defaultdict(list)
    for u in frame:
        strata[(u["sign"], u["family"], u["domain"])].append(u)
    chosen, used_tasks, alloc = [], set(), {}
    for s in SIGNS:
        keys = sorted(k for k in strata if k[0] == s)
        N = {k: len(strata[k]) for k in keys}
        tot = sum(N.values())
        raw = {k: N_PER_SIGN * N[k] / tot for k in keys}
        n = {k: max(1, math.floor(raw[k])) for k in keys}
        while sum(n.values()) < N_PER_SIGN:
            k = max(keys, key=lambda k: (raw[k] - n[k], k))
            n[k] += 1
        while sum(n.values()) > N_PER_SIGN:
            k = max((k for k in keys if n[k] > 1), key=lambda k: (n[k] - raw[k], k))
            n[k] -= 1
        for k in keys:
            n[k] = min(n[k], N[k])
            alloc["|".join(k)] = {"frame": N[k], "target": n[k]}
            got, here = 0, set()
            order = sorted(strata[k], key=lambda u: sha(f"{SALT}|{u['state_id']}|{u['dir']}"))
            for reuse in (False, True):  # prefer tasks not yet in the sample; reuse a task only if the stratum runs out
                for u in order:
                    tk = (u["domain"], u["task_id"])
                    if got >= n[k] or tk in here or (tk in used_tasks and not reuse):
                        continue
                    used_tasks.add(tk)
                    here.add(tk)
                    chosen.append({**u, "stratum": "|".join(k), "stratum_frame_size": N[k], "inclusion_prob_approx": round(n[k] / N[k], 6),
                                   "task_reused": tk in used_tasks and reuse})
                    got += 1
            alloc["|".join(k)]["drawn"] = got
    for s in SIGNS:
        su = sorted([u for u in chosen if u["sign"] == s], key=lambda u: sha(f"{SALT}|double|{u['state_id']}"))
        for i, u in enumerate(su):
            u["double_review"] = i < N_DOUBLE_PER_SIGN
    for u in chosen:
        u["review_id"] = sha(f"{SALT}|review|{u['state_id']}|{u['dir']}")[:10]
    chosen.sort(key=lambda u: u["review_id"])
    man = {"manifest": "wp5_sample_v1", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "frame_source": str(src.relative_to(ROOT)), "frame_source_sha256": sha_file(src), "frame_size": len(frame),
           "rule": __doc__.split("sample   ")[1].split("events")[0].strip(), "salt": SALT,
           "allocation": alloc, "n": len(chosen), "n_double": sum(u["double_review"] for u in chosen),
           "composition_note": "stratified by consequence sign (equal 20 per sign): label frequencies are sample composition, not prevalence; use inclusion_prob_approx for weighting",
           "units": chosen}
    text = json.dumps(man, indent=1)
    if SAMPLE.exists():
        old = json.loads(SAMPLE.read_text())
        if [u["state_id"] for u in old["units"]] != [u["state_id"] for u in chosen]:
            raise SystemExit(f"{SAMPLE} exists with a different sample; frozen")
        print(f"{SAMPLE} unchanged")
        return
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE.write_text(text + "\n")
    print(f"wrote {SAMPLE.relative_to(ROOT)}: {len(chosen)} states ({man['n_double']} double), frame {len(frame)}")


# ----------------------------------------------------------------------------
# loading states and the four branches
# ----------------------------------------------------------------------------


_TRAJ: dict = {}


def orig_traj(run_id: str, domain: str, task_id: str) -> dict:
    k = (run_id, domain)
    if k not in _TRAJ:
        p = ROOT / "runs" / run_id / domain / "trajectory.jsonl"
        _TRAJ[k] = {json.loads(l)["task_id"]: json.loads(l) for l in open(p) if l.strip()}
    return _TRAJ[k][task_id]


def load_unit(u: dict) -> tuple[dict, dict]:
    """State file and the four branches; QQ is the original episode's suffix after h_t."""
    d = ROOT / u["dir"]
    st = json.loads((d / "states" / f"{u['state_id']}.json").read_text())
    br = json.loads((d / "branches" / f"{u['state_id']}.json").read_text())
    tr = orig_traj(st["run_id"], st["domain"], st["task_id"])
    n = len(st["history"])
    prefix_ok = [m.get("role") for m in tr["messages"][:n]] == [m.get("role") for m in st["history"]]
    from cloq import fork as F
    n0 = F.prefix_len(tr["task"]) if "task" in tr else 0
    steps, errs = F.budget_used(tr["messages"], n0)
    br["QQ"] = {"first": "Q", "controller": "Q", "suffix": tr["messages"][n:], "termination_reason": tr["termination_reason"],
                "reward": tr.get("reward"), "db_match": tr.get("db_match"), "official_reward": tr.get("official_reward"),
                "reward_info": tr.get("reward_info"), "step_count_final": steps, "num_errors_final": errs, "orig_prefix_ok": prefix_ok,
                "source": "original episode"}
    return st, br


# ----------------------------------------------------------------------------
# events
# ----------------------------------------------------------------------------


def _calls(m: dict) -> list[dict]:
    out = []
    for tc in m.get("tool_calls") or []:
        a = tc.get("arguments")
        if isinstance(a, str):
            try:
                a = json.loads(a)
            except Exception:
                pass
        out.append({"name": tc.get("name") or (tc.get("function") or {}).get("name"), "arguments": a})
    return out


def process_events(st: dict, b: dict, ann: dict) -> dict:
    from cloq.fork_annotate import TT
    dom = st["domain"]
    suf = b["suffix"]
    agent = [m for m in suf if m.get("role") == "assistant"]
    users = [m for m in suf if m.get("role") == "user"]
    tools = [m for m in suf if m.get("role") == "tool"]
    calls = [c for m in agent for c in _calls(m)]
    sigs = collections.Counter(json.dumps([c["name"], c["arguments"]], sort_keys=True, default=str) for c in calls)
    writes_ok, k = [], 0
    for i, m in enumerate(suf):
        if m.get("role") != "assistant":
            continue
        cs = _calls(m)
        res = [x for x in suf[i + 1: i + 1 + len(cs)] if x.get("role") == "tool"]
        for j, c in enumerate(cs):
            if TT.tool_type(dom, c["name"]) == "write" and j < len(res) and not res[j].get("error"):
                writes_ok.append({"turn": i, "tool": c["name"], "first_action": i == 0})
    run = mx = 0
    prev = None
    for c in calls:  # consecutive identical calls
        s = json.dumps([c["name"], c["arguments"]], sort_keys=True, default=str)
        run = run + 1 if s == prev else 1
        prev, mx = s, max(mx, run)
    tok = lambda ms, key: sum(((m.get("usage") or {}).get(key) or 0) for m in ms)
    dfx = ann["defect"]["flags"]
    term = b.get("termination_reason")
    return {
        "wrong_tool": dfx.get("invalid_tool"), "wrong_argument": dfx.get("invalid_args") or dfx.get("exec_error"),
        "wrong_id": dfx.get("id_not_found"), "id_needs_review": dfx.get("id_needs_review"),
        "consent_before_write_needs_review": dfx.get("write_consent_needs_review"),
        "irreversible_db_mutation_current": bool(ann.get("changed_by_action") and any(ann["changed_by_action"].values())),
        "irreversible_db_mutations_suffix": len(writes_ok),
        "retry_loop": mx >= 3, "max_identical_consecutive_calls": mx, "max_identical_calls": max(sigs.values(), default=0),
        "transfer_to_human": any(c["name"] in TT.HANDOFF for c in calls),
        "correction_after_pivot": (ann.get("correction") or {}).get("any_auto_correction"),
        "premature_completion": dfx.get("premature_end") if "premature_end" in dfx else None,
        "budget_exhaustion": term in ("max_steps", "too_many_errors"),
        "cost": {"agent_turns": len(agent), "user_turns": len(users), "tool_calls": len(calls),
                 "tool_errors": sum(1 for m in tools if m.get("error")),
                 "agent_prompt_tokens": tok(agent, "prompt_tokens"), "agent_completion_tokens": tok(agent, "completion_tokens"),
                 "simulator_prompt_tokens": tok(users, "prompt_tokens"), "simulator_completion_tokens": tok(users, "completion_tokens"),
                 "steps_used": (b.get("step_count_final") or 0) - st["budget"]["steps_used"],
                 "errors_used": (b.get("num_errors_final") or 0) - st["budget"]["errors_used"], "termination": term},
    }


def cmd_events(a) -> None:
    from cloq import fork as F
    from cloq.fork_annotate import annotate_state, VERSION, TT_SHA
    F.setup_tau2()
    man = json.loads(SAMPLE.read_text())
    OUTD.mkdir(parents=True, exist_ok=True)
    rows = []
    for u in man["units"]:
        st, br = load_unit(u)
        ann = annotate_state(st, br)
        for b in ("BB", "BQ", "QB", "QQ"):
            if b in ann["branches"] and "error" not in ann["branches"][b]:
                ann["branches"][b]["events"] = process_events(st, br[b], ann["branches"][b])
        ann["branches"]["QQ"]["orig_prefix_ok"] = br["QQ"]["orig_prefix_ok"]
        rows.append({"review_id": u["review_id"], "state_id": u["state_id"], "dir": u["dir"], "annotation": ann})
        print(f"events {u['review_id']} {u['domain']} {u['sign']}", flush=True)
    meta = {"version": "wp5-events-v1", "fork_annotate": VERSION, "tool_types_sha256": TT_SHA, "sample_sha256": sha_file(SAMPLE),
            "script_sha256": sha_file(__file__), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUTD / "events.jsonl").write_text("".join(json.dumps({**meta, **r}, default=str) + "\n" for r in rows))
    print(f"wrote {(OUTD / 'events.jsonl').relative_to(ROOT)} ({len(rows)} states)")


# ----------------------------------------------------------------------------
# blinded views (shared by human packets and LLM labels)
# ----------------------------------------------------------------------------


def _strip(m: dict) -> dict:
    out = {"role": m.get("role")}
    if m.get("content"):
        out["content"] = m["content"]
    if m.get("tool_calls"):
        out["tool_calls"] = _calls(m)
    if m.get("role") == "tool":
        out["requestor"] = m.get("requestor")
        if m.get("error"):
            out["error"] = True
    if m.get("role") == "user" and m.get("tool_calls"):
        out["requestor"] = "user"
    return out


def views(u: dict) -> dict:
    """Blinded pass-1 and pass-2 views of one state. X/Y and S1..S4 orders are hashed; nothing identifies model,
    precision, quantizer, branch role, outcome or effect values."""
    st, br = load_unit(u)
    rid = u["review_id"]
    xy = sorted(["Q", "B"], key=lambda r: sha(f"{SALT}|xy|{rid}|{r}"))
    acts = {"Q": br["QQ"]["suffix"][0] if br["QQ"]["suffix"] else {"role": "assistant", "content": ""},
            "B": br["BB"]["suffix"][0] if br.get("BB") and br["BB"].get("suffix") else st["a_B"]["message"]}
    scen = st["task"].get("user_scenario") or {}
    instr = scen.get("instructions") if isinstance(scen, dict) else scen
    p1 = {"review_id": rid, "domain": st["domain"],
          "policy_note": "The agent follows the domain policy shown to it; the policy text is part of the system prompt (not repeated here).",
          "user_goal_summary_hidden_from_agent": instr if isinstance(instr, (str, dict)) else str(instr),
          "history": [{"i": i, **_strip(m)} for i, m in enumerate(st["history"])],
          "actions": {lab: _strip(acts[r]) for lab, r in zip(("X", "Y"), xy)}}
    order = sorted(["BB", "BQ", "QB", "QQ"], key=lambda b: sha(f"{SALT}|suffix|{rid}|{b}"))
    p2 = {"review_id": rid, "domain": st["domain"], "n_history": len(st["history"]),
          "budget_at_state": {k: st["budget"][k] for k in ("steps_left", "errors_left")},
          "suffixes": {f"S{i + 1}": [{"i": j, **_strip(m)} for j, m in enumerate(br[b]["suffix"])] for i, b in enumerate(order) if b in br}}
    key = {"review_id": rid, "state_id": u["state_id"], "dir": u["dir"], "X": xy[0], "Y": xy[1],
           **{f"S{i + 1}": b for i, b in enumerate(order)}}
    return {"pass1": p1, "pass2": p2, "key": key}


def _msg_html(m: dict) -> str:
    role = m["role"] + (f" ({m['requestor']})" if m.get("requestor") else "") + (" ERROR" if m.get("error") else "")
    body = html.escape(m.get("content") or "")
    if m.get("tool_calls"):
        body += "".join(f"<div class=tc>→ {html.escape(c['name'] or '')}({html.escape(json.dumps(c['arguments'], ensure_ascii=False))})</div>"
                        for c in m["tool_calls"])
    return f"<div class='m {m['role']}'><span class=r>[{m.get('i', '')}] {html.escape(role)}</span><pre>{body}</pre></div>"


CSS = ("<style>body{font-family:system-ui,sans-serif;max-width:980px;margin:16px auto;padding:0 16px;background:#fff;color:#111}"
       "pre{white-space:pre-wrap;margin:2px 0}.m{border-left:3px solid #ccc;padding:2px 8px;margin:6px 0}.assistant{border-color:#36c}"
       ".user{border-color:#3a3}.tool{border-color:#999;font-size:90%}.tc{font-family:monospace;color:#036}.r{font-size:80%;color:#555}"
       ".act{border:2px solid #c60;padding:8px;margin:10px 0}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:4px}"
       "@media (prefers-color-scheme: dark){body{background:#111;color:#eee}.tc{color:#8bf}.r{color:#aaa}}</style>")


def cmd_packets(a) -> None:
    man = json.loads(SAMPLE.read_text())
    pdir = OUTD / "packets"
    pdir.mkdir(parents=True, exist_ok=True)
    KEYD.mkdir(parents=True, exist_ok=True)
    keys, index = [], []
    fields1 = ["groundedness", "tool_validity", "argument_validity", "permission_consent", "goal_relevance", "state_ambiguity", "defensible"]
    fields2 = ["retries", "defect_corrected", "irreversible_change", "user_clarification", "loop", "budget_exhaustion", "requirements_satisfied"]
    calib = []
    src = ROOT / man["frame_source"]
    insample = {u["state_id"] for u in man["units"]}
    cand = []
    for l in open(src):
        x = json.loads(l)
        if x.get("eligibility_status") == "divergent" and x.get("replay_gate_pass") and x.get("cell") in FAMILY and x["state_id"] not in insample:
            d = ROOT / x["branch_artifact_refs"]["dir"]
            if (d / "branches" / f"{x['state_id']}.json").exists():
                cand.append({"state_id": x["state_id"], "dir": x["branch_artifact_refs"]["dir"], "domain": x["domain"], "double_review": True})
    for x in sorted(cand, key=lambda x: sha(f"{SALT}|calib|{x['state_id']}"))[:2]:
        x["review_id"] = "calib_" + sha(f"{SALT}|review|{x['state_id']}|{x['dir']}")[:6]
        calib.append(x)
    for u in calib + man["units"]:
        v = views(u)
        keys.append({**v["key"], "calibration": u in calib})
        p1, p2 = v["pass1"], v["pass2"]
        rid = u["review_id"]
        h1 = [CSS, f"<title>WP5 {rid} pass 1</title><h1>State {rid} — pass 1 (current decision)</h1>",
              f"<p>Domain: {p1['domain']}. Reviewer: label each action X and Y separately (see ANNOTATION_PROTOCOL.md). "
              "Cite evidence as message indices [i]. Use <b>unknown</b> or <b>n/a</b> freely.</p>",
              "<h2>User goal (hidden from the agent)</h2><pre>" + html.escape(json.dumps(p1["user_goal_summary_hidden_from_agent"], indent=1, ensure_ascii=False)) + "</pre>",
              "<h2>History</h2>"] + [_msg_html(m) for m in p1["history"]] + ["<h2>Candidate current actions</h2>"]
        for lab, m in p1["actions"].items():
            h1.append(f"<div class=act><b>Action {lab}</b>{_msg_html({**m, 'i': lab})}</div>")
        h1.append("<h2>Labels</h2><table><tr><th>field</th><th>X</th><th>X evidence</th><th>Y</th><th>Y evidence</th></tr>"
                  + "".join(f"<tr><td>{f}</td><td></td><td></td><td></td><td></td></tr>" for f in fields1) + "</table>")
        (pdir / f"{rid}_pass1.html").write_text("<!doctype html><meta charset=utf-8>" + "".join(h1))
        h2 = [CSS, f"<title>WP5 {rid} pass 2</title><h1>State {rid} — pass 2 (continuations)</h1>",
              f"<p>Four continuations S1–S4 from the same state (history as in pass 1, {p2['n_history']} messages; "
              f"remaining budget {p2['budget_at_state']}). Their first message is the current action. Label each suffix.</p>"]
        for s, msgs in p2["suffixes"].items():
            h2.append(f"<h2>{s}</h2>" + "".join(_msg_html(m) for m in msgs))
        h2.append("<h2>Labels</h2><table><tr><th>field</th>" + "".join(f"<th>{s}</th><th>{s} evidence</th>" for s in p2["suffixes"]) + "</tr>"
                  + "".join(f"<tr><td>{f}</td>" + "<td></td><td></td>" * len(p2["suffixes"]) + "</tr>" for f in fields2) + "</table>")
        (pdir / f"{rid}_pass2.html").write_text("<!doctype html><meta charset=utf-8>" + "".join(h2))
        index.append({"review_id": rid, "domain": p1["domain"], "double_review": u["double_review"], "calibration": u in calib})
    kp = KEYD / "wp5_KEY_unblinding.jsonl"
    ktxt = "".join(json.dumps(k) + "\n" for k in keys)
    kp.write_text(ktxt)
    tmpl = [{"review_id": i["review_id"], "reviewer": None, "pass": p, "labels": {}, "notes": None} for i in index for p in (1, 2)]
    (OUTD / "labels_TEMPLATE.jsonl").write_text("".join(json.dumps(t) + "\n" for t in tmpl))
    rows = "".join(f"<tr><td>{i['review_id']}</td><td>{i['domain']}</td><td>{'R1+R2' if i['double_review'] else 'R1 or R2'}</td>"
                   f"<td><a href='{i['review_id']}_pass1.html'>pass 1</a></td><td><a href='{i['review_id']}_pass2.html'>pass 2</a></td></tr>" for i in index)
    (pdir / "index.html").write_text(f"<!doctype html><meta charset=utf-8>{CSS}<title>WP5 review</title><h1>WP5 blinded review ({len(index)} states)</h1>"
                                     "<p>Do all pass-1 labels before opening any pass-2 page of the same state.</p>"
                                     f"<table><tr><th>state</th><th>domain</th><th>reviewers</th><th></th><th></th></tr>{rows}</table>")
    meta = {"packets": len(index), "calibration_states": [i["review_id"] for i in index if i["calibration"]],
            "double": sum(i["double_review"] for i in index if not i["calibration"]), "key_path": str(kp), "key_sha256": sha(ktxt),
            "sample_sha256": sha_file(SAMPLE), "script_sha256": sha_file(__file__), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "assignment": {i["review_id"]: ("both" if (i["double_review"] or i["calibration"]) else ("R1" if int(sha(f"{SALT}|assign|{i['review_id']}")[:8], 16) % 2 else "R2")) for i in index}}
    (OUTD / "packets_meta.json").write_text(json.dumps(meta, indent=1))
    print(f"packets: {len(index)} states -> {pdir.relative_to(ROOT)}; key outside repo ({kp}), sha {meta['key_sha256'][:12]}")


# ----------------------------------------------------------------------------
# LLM labels (frozen rubric)
# ----------------------------------------------------------------------------


def _rubric() -> tuple[str, str]:
    txt = RUBRIC.read_text()
    h = sha(txt)
    fr = json.loads(RUBRIC_FREEZE.read_text())
    if fr["rubric_sha256"] != h:
        raise SystemExit(f"rubric changed after freeze: {h} != {fr['rubric_sha256']}")
    return txt, h


def _ask(url: str, system: str, user: str) -> tuple[dict | None, str, dict]:
    body = {"model": "user", "temperature": 0.0, "top_p": 1.0, "seed": 0, "max_tokens": 1500,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1200) as r:
        resp = json.load(r)
    txt = resp["choices"][0]["message"]["content"] or ""
    m = re.search(r"\{.*\}", txt, re.S)
    try:
        return json.loads(m.group(0)) if m else None, txt, resp.get("usage") or {}
    except Exception:
        return None, txt, resp.get("usage") or {}


def cmd_llm(a) -> None:
    rubric, rh = _rubric()
    man = json.loads(SAMPLE.read_text())
    sys1 = rubric.split("<!-- PASS1 -->")[1].split("<!-- END PASS1 -->")[0].strip()
    sys2 = rubric.split("<!-- PASS2 -->")[1].split("<!-- END PASS2 -->")[0].strip()
    with urllib.request.urlopen(a.url.split(",")[0].rstrip("/") + "/models", timeout=10) as r:
        served = json.load(r)["data"][0]
    jobs = []
    for u in man["units"]:
        v = views(u)
        jobs.append((u, 1, sys1, json.dumps(v["pass1"], ensure_ascii=False)))
        jobs.append((u, 2, sys2, json.dumps(v["pass2"], ensure_ascii=False)))

    urls = a.url.split(",")
    outp = OUTD / "llm_labels.jsonl"
    done = {}
    if outp.exists():  # resume: keep parsed records made with the same rubric
        for l in outp.read_text().splitlines():
            r = json.loads(l)
            if r.get("parse_ok") and r.get("rubric_sha256") == rh:
                done[(r["review_id"], r["pass"])] = r
    lock = __import__("threading").Lock()

    def run(j):
        u, p, s, usr = j
        if (u["review_id"], p) in done:
            return done[(u["review_id"], p)]
        t0 = time.time()
        lab, raw, usage, err, url = None, "", {}, None, None
        for k in range(len(urls) * 2):  # an overloaded replica times out: try the next one
            url = urls[(hash(u["review_id"]) + k) % len(urls)]
            try:
                lab, raw, usage = _ask(url, s, usr if k % 2 == 0 else usr + "\n\nReturn ONLY the JSON object described in the instructions.")
                err = None
                if lab is not None:
                    break
            except Exception as e:
                err = repr(e)[:300]
        rec = {**prov, "model_url": url, "review_id": u["review_id"], "pass": p, "labels": lab, "parse_ok": lab is not None, "error": err,
               "raw": raw[:6000], "usage": usage, "seconds": time.time() - t0}
        with lock:
            with open(outp, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    prov = {"labeller": "llm", "rubric": str(RUBRIC.relative_to(ROOT)), "rubric_sha256": rh, "served_model": served.get("root"),
            "served_name": served.get("id"), "decoding": {"temperature": 0, "top_p": 1, "seed": 0, "max_tokens": 1500},
            "sample_sha256": sha_file(SAMPLE), "script_sha256": sha_file(__file__)}
    OUTD.mkdir(parents=True, exist_ok=True)
    with cf.ThreadPoolExecutor(a.conc) as ex:
        out = list(ex.map(run, jobs))
    final = {(r["review_id"], r["pass"]): r for r in out}  # one line per (state, pass): the latest record
    outp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in final.values()))
    print(f"llm labels: {sum(r['parse_ok'] for r in final.values())}/{len(final)} parsed -> {outp.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("sample")
    s.add_argument("--units", default=None)
    sp.add_parser("events")
    sp.add_parser("packets")
    s = sp.add_parser("llm")
    s.add_argument("--url", required=True, help="an existing simulator replica, e.g. http://node002:8000/v1")
    s.add_argument("--conc", type=int, default=4)
    a = ap.parse_args()
    {"sample": cmd_sample, "events": cmd_events, "packets": cmd_packets, "llm": cmd_llm}[a.cmd](a)


if __name__ == "__main__":
    main()
