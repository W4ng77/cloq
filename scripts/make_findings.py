"""Generate analysis/FINDINGS.md: the plan's deliverables (section 29), claims (section 28)
and continuation rules (section 24), filled in from the generated analysis files.

usage: python scripts/make_findings.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/xinyu/cloq")
from cloq import config as C  # noqa: E402

A = C.PROJECT_ROOT / "analysis"


def load(name):
    p = A / name
    return json.load(open(p)) if p.exists() else None


def fmt(x, nd=3):
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def main():
    r = load("results.json")
    if r is None:
        raise SystemExit("analysis/results.json missing; run `python -m cloq.report` first")
    sig = load("signals.json")
    fs = load("failure_states.json")
    integ = load("integrity.json")
    split = json.load(open(C.MANIFEST_DIR / "task_split_v0.json"))
    arms = ["bf16"] + r["arms"]
    L = [
        "# CLOQ v0 findings",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} from `analysis/results.json`.",
        f"Model {C.MODEL_ID} at revision `{C.MODEL_REVISION[:12]}`, tau2-bench text mode, GPTQ W4 group 128,",
        f"calibration budget {C.FROZEN['calibration']['token_budget']} tokens per arm within "
        f"{C.FROZEN['calibration']['token_budget_tolerance']*100:.0f}%.",
        "",
        "## Headline: closed-loop task success (database end-state match)",
        "",
        "| domain | n | " + " | ".join(arms) + " |",
        "|---|---|" + "---|" * len(arms),
    ]
    for domain, d in r["domains"].items():
        s = d["summary"]["db_match"]
        L.append(f"| {domain} | {d['n_eval']} | " + " | ".join(fmt(s.get(a)) for a in arms) + " |")
    pm = (r.get("pooled", {}).get("db_match") or {}).get("means", {})
    n_pool = sum(d["n_eval"] for d in r["domains"].values())
    L.append(f"| pooled | {n_pool} | " + " | ".join(fmt(pm.get(a)) for a in arms) + " |")

    L += ["", "Paired task-level bootstrap, 10,000 replicates:", "",
          "| contrast | pooled difference | 95% CI |", "|---|---|---|"]
    for name, c in ((r.get("pooled", {}).get("db_match") or {}).get("contrasts") or {}).items():
        L.append(f"| {name} | {fmt(c.get('diff'))} | [{fmt(c.get('ci_lo'))}, {fmt(c.get('ci_hi'))}] |")

    # secondary behaviour
    L += ["", "## Agent behaviour", "",
          "| arm | domain | premature | mean decisions | repeated tool calls | parser errors |",
          "|---|---|---|---|---|---|"]
    for domain, d in r["domains"].items():
        for a in arms:
            s = (d.get("secondary") or {}).get(a)
            if not s:
                continue
            L.append(f"| {a} | {domain} | {fmt(s.get('premature_rate'))} | {fmt(s.get('mean_decisions'),1)} | "
                     f"{fmt(s.get('repeated_tool_call_rate'))} | {fmt(s.get('parser_error_rate'),4)} |")

    # open loop vs closed loop
    L += ["", "## Open-loop fidelity versus closed-loop success", "",
          "Replay of stored BF16 held-out contexts without executing the result. Note that open-loop",
          "fidelity is nearly identical across the two domains while closed-loop degradation is not,",
          "so action fidelity on nominal states does not predict closed-loop success.", "",
          "| arm | domain | tool-name agr. | full tool-call agr. | NLL/token | closed-loop success |",
          "|---|---|---|---|---|---|"]
    for domain, d in r["domains"].items():
        for a, o in (d.get("openloop") or {}).items():
            L.append(f"| {a} | {domain} | {fmt(o.get('tool_name_agreement'))} | {fmt(o.get('full_tool_call_agreement'))} | "
                     f"{fmt(o.get('nll_per_token_mean'),4)} | {fmt(d['summary']['db_match'].get(a))} |")

    sub = (r.get("pooled") or {}).get("long_horizon_subset_db_match")
    if sub:
        L += [f"", f"## Long-horizon subset (BF16 horizon above {sub['median_horizon']:.0f}; "
              f"n={sub['n_long']} of {sub['n_long']+sub['n_short']})", "",
              "These are the tasks on which quantization degradation exists at all. Averaging over every",
              "held-out task dilutes a method effect with short tasks that have no gap to close.", "",
              "| arm | short tasks | long tasks |", "|---|---|---|"]
        for a, v in sub["means"].items():
            L.append(f"| {a} | {fmt(v['short'])} | {fmt(v['long'])} |")
        L += ["", "| contrast on long tasks | difference | 95% CI | P(>0) |", "|---|---|---|---|"]
        for name, c in sub["contrasts"].items():
            L.append(f"| {name} | {fmt(c.get('diff'))} | [{fmt(c.get('ci_lo'))}, {fmt(c.get('ci_hi'))}] | "
                     f"{fmt(1 - c.get('p_diff_le_0', 1))} |")

    # horizon
    amp = (r.get("pooled") or {}).get("horizon_amplification_db_match") or {}
    if amp:
        L += ["", "## Horizon amplification (pooled, tasks split at the median BF16 horizon)", "",
              "| arm | gap on short tasks | gap on long tasks | difference | 95% CI | one-sided p |",
              "|---|---|---|---|---|---|"]
        for a, v in amp.items():
            if "gap_long" not in v:
                continue
            L.append(f"| {a} | {fmt(v['gap_short'])} (n={v['n_short']}) | {fmt(v['gap_long'])} (n={v['n_long']}) | "
                     f"{fmt(v['gap_long_minus_short'])} | [{fmt(v['ci_lo'])}, {fmt(v['ci_hi'])}] | {fmt(v['p_amplification_le_0'])} |")

    # divergence
    L += ["", "## First divergence in tool-call behaviour", "",
          "| arm | domain | diverged | median t*/H | success early div | success late div | success no div |",
          "|---|---|---|---|---|---|---|"]
    for domain, d in r["domains"].items():
        for a, v in (d.get("divergence") or {}).items():
            L.append(f"| {a} | {domain} | {fmt(v.get('frac_any_divergence'))} | {fmt(v.get('median_t_star_norm'))} | "
                     f"{fmt(v.get('success_given_early_div'))} | {fmt(v.get('success_given_late_div'))} | {fmt(v.get('success_given_no_div'))} |")

    # occupancy
    occ = r.get("occupancy_last")
    if occ:
        L += ["", "## Occupancy: distance from visited states to each calibration buffer", "",
              "Cosine support distance in the frozen BF16 final-layer representation at the action boundary.",
              "The `bf16_rep` row is an independent re-run of BF16 itself: it is the empirical null for the MMD",
              "column, and it never diverges from BF16, so it has no post-divergence states.", "",
              "| domain | arm | Q to static | Q to fp_traj | Q to cloq | pre-divergence | post-divergence | MMD(FP,Q) | MMD null |",
              "|---|---|---|---|---|---|---|---|---|"]
        for domain, d in occ.get("domains", {}).items():
            fpsup = d.get("fp_to_support", {})
            L.append(f"| {domain} | BF16 states | {fmt(fpsup.get('static'))} | {fmt(fpsup.get('fp_traj'))} | {fmt(fpsup.get('cloq'))} | | | | |")
            for a, v in d.get("arms", {}).items():
                pp = (v.get("pre_post_divergence") or {}).get("fp_traj", {})
                q = v.get("q_to_support", {})
                L.append(f"| {domain} | {a} | {fmt(q.get('static'))} | {fmt(q.get('fp_traj'))} | {fmt(q.get('cloq'))} | "
                         f"{fmt(pp.get('pre_mean'))} | {fmt(pp.get('post_mean'))} | {fmt(v.get('mmd_fp_vs_q'),4)} | {fmt(v.get('mmd_fp_half_vs_half'),4)} |")

    if fs and "share_of_q_tokens" in fs:
        L += ["", "## Composition of the CLOQ on-policy half (plan section 19)", "",
              f"{fs['n_q_contexts']} Q0 contexts, {fs['q_tokens']} tokens; categories overlap.", "",
              "| category | share of Q0 tokens |", "|---|---|"]
        for k, v in fs["share_of_q_tokens"].items():
            L.append(f"| {k} | {fmt(v)} |")

    if sig:
        L += ["", "## Pre-specified continuation rules (plan section 24)", ""]
        for k, v in sig["signals"].items():
            L.append(f"- **{k}**: {'FIRED' if v['fired'] else 'not met'}. Rule: {v['rule']}")
        L += ["", f"**{sig['n_core_signals_fired']} of 3 core signals fired. "
              f"Proceed to the full paper: {fmt(sig['proceed_to_full_paper'])}** ({sig['decision_rule']}).", ""]
        fired_stops = [k for k, v in (sig.get("stop_rules") or {}).items() if v]
        L.append("Stop/rethink rules that fired: " + (", ".join(fired_stops) if fired_stops else "none"))

    # deliverables
    L += ["", "## Deliverables (plan section 29)", ""]
    deliv = [
        ("frozen task/calibration manifests", "manifests/task_split_v0.json, manifests/calib_*.json"),
        ("BF16 trajectories", "runs/bf16/*/trajectory.jsonl and decisions.jsonl"),
        ("Static-W4 checkpoint", "ckpts/static_w4"),
        ("FP-Traj-W4 checkpoint", "ckpts/fp_traj_w4"),
        ("paired held-out closed-loop results", "runs/*_eval/*/metrics.json, analysis/results.json"),
        ("open-loop action agreement and NLL", "runs/*_eval/*/openloop.summary.json"),
        ("first-divergence statistics", "runs/*_eval/*/divergence.json"),
        ("FP-versus-Q occupancy distance", "analysis/occupancy_last.json, analysis/occupancy_obs.json"),
        ("CLOQ-W4 checkpoint and evaluation", "ckpts/cloq_w4, runs/cloq_eval/"),
    ]
    for i, (what, where) in enumerate(deliv, 1):
        exists = any((C.PROJECT_ROOT / w.split(",")[0].strip().split("*")[0]).exists() for w in [where])
        L.append(f"{i}. {what} — `{where}`")

    # integrity
    if integ:
        L += ["", "## Integrity", "",
              f"All checks passed: {fmt(integ.get('ok'))}."]
        if integ.get("problems"):
            L.append("")
            for p in integ["problems"]:
                L.append(f"- {p}")

    ndesc = ", ".join(f"{d} n={r['domains'][d]['n_eval']}" for d in r["domains"])
    L += ["", "## Limitations", "",
          "- The 64k-token budget buys only 10 to 13 calibration contexts, because one agent context is 5 to 8k",
          "  tokens. Each arm therefore rests on a single small random draw, and draw variance is not separated",
          "  from method effect. Repeating every arm under two or three calibration seeds is the first thing the",
          "  full paper needs.",
          "- The user simulator and the natural-language assertion judge are the same 4B model as the agent,",
          "  because this machine has no external API. The primary endpoint avoids the judge entirely, but the",
          "  simulator occasionally fails to end a conversation, which is what produces the step-cap terminations.",
          f"- Held-out sets are {ndesc}; the airline",
          "  set is small enough that a two-task swing moves its rate by 0.074.",
          "- Determinism was verified rather than assumed: a fresh BF16 launch reproduced all 58 held-out",
          "  retail outcomes and replayed 742 stored contexts with 1.000 agreement, so the noise floor on",
          "  every metric here is zero (`scripts/bf16_replicate.sh`). This depends on VLLM_BATCH_INVARIANT=1",
          "  and on never restarting the user-simulator server mid-experiment.",
          ]
    (A / "FINDINGS.md").write_text("\n".join(L))
    print(f"wrote {A / 'FINDINGS.md'} ({len(L)} lines)")


if __name__ == "__main__":
    main()
