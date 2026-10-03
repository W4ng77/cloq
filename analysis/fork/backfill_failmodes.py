"""Appendix backfill part 3 (W100x): low-bit failure modes. One category per finished, non-outage retail/airline episode
of the W3 / W2 / gauss3 / KV-INT3 cells and their BF16 references (A6000 a6k2 runs admitted in the snapshot)."""
from __future__ import annotations

import json
import re
from collections import Counter

from backfill_common import DOMAINS, read_run

FAIL_RULES = [
    ("success", "DB success (db_match with a user_stop/agent_stop ending)"),
    ("runaway", "no normal ending: context-window overflow (W10), 200-step cap (max_steps) or loop-guard stop (W73, W2 panel only)"),
    ("tool_errors", "tau2 stopped the episode after 10 failed tool executions (too_many_errors)"),
    ("parse_end", "episode ended by an unparseable agent output (infra cause agent_parse_error / agent_empty_output; W27, W41)"),
    ("format", "normal ending; a required write was never issued as a parsed tool call, and the agent wrote >= 1 tool call as "
               "plain text (JSON without the <tool_call> markup) or as markup the parser rejected"),
    ("no_write", "normal ending; a write was required and the agent attempted none, in any form (stopped, asked, refused or transferred)"),
    ("wrong_tool", "normal ending; the set of write tools the agent called differs from the required set (incl. writes when none was required)"),
    ("wrong_args", "normal ending; same write-tool set as required, end state still wrong (arguments, count or failed calls)"),
    ("other", "normal ending, DB mismatch, none of the above"),
]
FAIL_KEYS = [k for k, _ in FAIL_RULES]


def fail_category(e: dict, dom: str) -> str | None:
    """One category per data episode (FAIL_RULES); None for a non-data (missing) episode."""
    if not e["data"]:
        return None
    if e["Y"] == 1:
        return "success"
    term = e["term"]
    if term == "infrastructure_error":
        return "runaway" if e["cause"] == "context_overflow" else "parse_end"
    if term in ("max_steps", "loop_early_stop"):
        return "runaway"
    if term == "too_many_errors":
        return "tool_errors"
    if term not in ("user_stop", "agent_stop"):
        return "other"
    f = e["f"]
    if f["req"] and not f["writes"]:
        return "format" if (f["n_text_calls"] or f["n_markup_fail"]) else "no_write"
    if set(f["writes"]) != set(f["req"]):
        return "wrong_tool"
    return "wrong_args" if f["req"] else "other"


FM_GROUPS = [  # (label, model, config, run-id regex); A6000 a6k2 retail/airline closed-loop runs only
    ("q4 BF16 (q3-q5)", "q4", "BF16", r"^a6k2_q4_bfpair_q[345]$"),
    ("q4 GPTQ-W3", "q4", "GPTQ-W3", r"^a6k2_q4_gptq_w3_q[345]$"),
    ("q4 AWQ-W3", "q4", "AWQ-W3", r"^a6k2_q4_awq_w3_q[345]$"),
    ("q4 RTN-W3", "q4", "RTN-W3", r"^a6k2_q4_rtn_w3_q[345]$"),
    ("q8 BF16 (q3-q5)", "q8", "BF16", r"^a6k2_q8_bfpair_q[345]$"),
    ("q8 GPTQ-W3", "q8", "GPTQ-W3", r"^a6k2_q8_gptq_w3_q[345]$"),
    ("q8 AWQ-W3", "q8", "AWQ-W3", r"^a6k2_q8_awq_w3_q[345]$"),
    ("q8 RTN-W3", "q8", "RTN-W3", r"^a6k2_q8_rtn_w3_q[345]$"),
    ("q14 BF16", "q14", "BF16", r"^a6k2_q14_bf16$"),
    ("q14 GPTQ-W3", "q14", "GPTQ-W3", r"^a6k2_q14_gptq_w3_q\d$"),
    ("q14 RTN-W3", "q14", "RTN-W3", r"^a6k2_q14_rtn_w3_q\d$"),
    ("q14 gauss3", "q14", "gauss3", r"^a6k2_q14_gauss3_s\d$"),
    ("q30a3 BF16", "q30a3", "BF16", r"^a6k2_q30a3_bf16$"),
    ("q30a3 GPTQ-W3", "q30a3", "GPTQ-W3", r"^a6k2_q30a3_gptq_w3_n\d$"),
    ("q30a3 RTN-W3", "q30a3", "RTN-W3", r"^a6k2_q30a3_rtn_w3_n\d$"),
    ("q30a3 gauss3", "q30a3", "gauss3", r"^a6k2_q30a3_gauss3_s\d$"),
    ("q32 BF16", "q32", "BF16", r"^a6k2_q32_bf16$"),
    ("q32 GPTQ-W3", "q32", "GPTQ-W3", r"^a6k2_q32_gptq_w3_q\d$"),
    ("q32 RTN-W3", "q32", "RTN-W3", r"^a6k2_q32_rtn_w3_q\d$"),
    ("q32 gauss3", "q32", "gauss3", r"^a6k2_q32_gauss3_s\d$"),
    ("q4 KV-INT3", "q4", "KV-INT3", r"^a6k2_q4_kvq_int3_q\d$"),
    ("q8 KV-INT3", "q8", "KV-INT3", r"^a6k2_q8_kvq_int3_q\d$"),
    ("q14 KV-INT3", "q14", "KV-INT3", r"^a6k2_q14_kvq_int3_q\d$"),
    ("q4 BF16 W2-panel (guarded)", "q4", "BF16 W2p", r"^a6k2_w2p_q4_bf16_q3$"),
    ("q4 RTN-W2 W2-panel (guarded)", "q4", "RTN-W2", r"^a6k2_w2p_q4_rtn_w2_q3$"),
    ("q8 RTN-W2 W2-panel (guarded)", "q8", "RTN-W2", r"^a6k2_w2p_q8_rtn_w2_q3$"),
    ("q8 GPTQ-W2 W2-panel (guarded)", "q8", "GPTQ-W2", r"^a6k2_w2p_q8_gptq_w2_q3$"),
    ("q4 RTN-W2 cap sample (unguarded)", "q4", "RTN-W2 cap", r"^a6k2_w2p_q4_rtn_w2_cap_q3$"),
    ("q8 RTN-W2 cap sample (unguarded)", "q8", "RTN-W2 cap", r"^a6k2_w2p_q8_rtn_w2_cap_q3$"),
    ("q8 GPTQ-W2 cap sample (unguarded)", "q8", "GPTQ-W2 cap", r"^a6k2_w2p_q8_gptq_w2_cap_q3$"),
]


def failure_modes(snap: dict) -> dict:
    fz, ex, pend = snap["frozen"], snap.get("excluded") or {}, set(snap.get("queue_pending_run_ids") or [])
    rows, unfinished = {}, []
    for label, model, cfg, pat in FM_GROUPS:
        rx = re.compile(pat)
        runs_f = sorted(r for r in fz if rx.match(r))
        runs_x = sorted(r for r in set(ex) | pend if rx.match(r) and not (r in fz and set(fz[r]) >= set(DOMAINS)))
        for r in runs_x:
            unfinished.append({"group": label, "run": r, "admitted_domains": sorted(fz.get(r, {})), "pending": r in pend,
                               "reason": (ex.get(r) or ["pending in queue"])[0][:120]})
        cnt, n_missing, n_text, n_dec, n_ep, n_pw, n_sw = Counter(), Counter(), 0, 0, 0, 0, 0
        runs_used = []
        for r in runs_f:
            for dom in DOMAINS:
                if dom not in fz[r]:
                    continue
                ep = read_run(r, dom, fz[r][dom])
                if ep is None:
                    unfinished.append({"group": label, "run": f"{r}/{dom}", "reason": "trajectory differs from snapshot"})
                    continue
                runs_used.append(f"{r}/{dom}")
                for e in ep.values():
                    c = fail_category(e, dom)
                    if c is None:
                        n_missing[e["cause"]] += 1
                        continue
                    cnt[c] += 1
                    n_ep += 1
                    if e.get("f"):
                        n_text += int(e["f"]["n_text_calls"] > 0 or e["f"]["n_markup_fail"] > 0)
                        n_pw += int(bool(e["f"]["writes"]))
                        n_sw += int(c == "success" and bool(e["f"]["req"]))
                        n_dec += 1
        if not runs_used:
            rows[label] = {"model": model, "config": cfg, "n": 0, "runs": [], "excluded": dict(n_missing)}
            continue
        rows[label] = {"model": model, "config": cfg, "n": n_ep, "runs": runs_used, "counts": {k: cnt.get(k, 0) for k in FAIL_KEYS},
                       "pct": {k: round(100 * cnt.get(k, 0) / n_ep, 1) for k in FAIL_KEYS},
                       "pct_abnormal_end": round(100 * sum(cnt.get(k, 0) for k in ("runaway", "tool_errors", "parse_end")) / n_ep, 1),
                       "pct_normal_end_wrong_state": round(100 * sum(cnt.get(k, 0) for k in ("format", "no_write", "wrong_tool", "wrong_args", "other")) / n_ep, 1),
                       "excluded": dict(n_missing), "pct_episodes_with_text_tool_calls": round(100 * n_text / max(n_dec, 1), 1),
                       "pct_episodes_with_parsed_write": round(100 * n_pw / max(n_dec, 1), 1),
                       "n_success": cnt.get("success", 0), "n_success_on_write_tasks": n_sw, "n_with_messages": n_dec}
    return {"rules": dict(FAIL_RULES), "rows": rows, "unfinished": unfinished}


def render_failmodes(res: dict) -> list[str]:
    F = res["failure_modes"]
    L = []
    L += ["", "## 3. Low-bit failure modes (descriptive)", "",
          "One category per finished, non-outage retail/airline episode (A6000 a6k2 runs admitted in the snapshot). Categories, in order:", ""]
    L += [f"- `{k}`: {v}" for k, v in F["rules"].items()]
    L += ["", "Write tools are tau2's ToolType.WRITE tools; the required set comes from the task's evaluation actions. "
          "'abnormal end' = runaway + tool-error cap + parse end; 'normal end, wrong state' = the five normal-ending failure categories. 'parsed write (any)' = share of episodes with messages with >= 1 parsed write-tool call; 'successes on write tasks' = successes on tasks whose evaluation requires >= 1 write. 'text calls (any)' = share of episodes with messages in which >= 1 agent turn wrote a tool call as plain text or rejected markup. "
          "Excluded = outage (W6) / user_sim_error (W41) / unclassified infrastructure episodes, not data.", "",
          "| group | n | success | runaway | tool-error cap | parse end | text tool calls | no write | wrong tool | wrong args | other | abnormal end | normal end, wrong state | text calls (any) | parsed write (any) | successes on write tasks | excluded |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for lab, r in F["rows"].items():
        if not r["n"]:
            L.append(f"| {lab} | 0 | not finished |  |  |  |  |  |  |  |  |  |  |  |  |  | {json.dumps(r.get('excluded') or {})} |")
            continue
        p = r["pct"]
        L.append(f"| {lab} | {r['n']} | " + " | ".join(f"{p[k]:.1f}" for k in FAIL_KEYS) +
                 f" | {r['pct_abnormal_end']:.1f} | {r['pct_normal_end_wrong_state']:.1f} | {r['pct_episodes_with_text_tool_calls']:.1f} | "
                 f"{r['pct_episodes_with_parsed_write']:.1f} | {r['n_success_on_write_tasks']} of {r['n_success']} | {json.dumps(r['excluded'])} |")
    L += ["", "Runs per group: " + "; ".join(f"{lab}: {len(r['runs'])} run-domains" for lab, r in F["rows"].items() if r["n"]), "",
          "**Unfinished runs in these groups (not used):**", ""]
    L += [f"- {u['group']}: `{u['run']}` ({'pending in queue; ' if u.get('pending') else ''}{u['reason']}; admitted domains {u.get('admitted_domains')})" for u in F["unfinished"]]
    L.append("")
    return L
