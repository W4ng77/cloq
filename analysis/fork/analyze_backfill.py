"""Appendix backfill, EXPLORATORY (appendix app:withdrawn, "Supplementary perturbation analyses"); A6000 a6k2 runs only.

Three CPU analyses of FINISHED runs (admitted in an integrity snapshot; pending/failed/deferred runs are listed, never used):
  1. Restoration location vs byte-matched random modules (perturb-v1, docs/insights/PERTURBATION_PROTOCOL.md §2.1, §3a-3d):
     closed-loop arms a6k2_pert_<m>_<cell>_restore_<X>_<blk>. Contrast per cell = Y(structured X) - mean over complete
     random seeds of Y(byte-matched random family), paired on task x block units (early/middle/late vs rand_third,
     attn vs rand_attn, mlp vs rand_mlp; GPTQ-W3 also restore_recal_X vs restore_recal_rand_*_s1). Turnover to BF16
     (P(Y != Y_BF16)) is reported for the same contrast. Pivot-time single-decision reversion (W55, pivot_* forks) is
     copied from the given analyze_pivot_arms output (sha recorded).
  2. Residual error dose (§2.2): W_a = W + a(W_Q - W), a in {0 (= BF16), 0.25, 0.5, 1 (= Q), 2}: success, turnover to
     BF16 and action agreement with BF16 (action signatures from cloq.fork.action_view on the trajectory's assistant
     messages; first differing decision; prefix = index / BF16 decisions) per a, adjacent steps paired on joint units.
  3. Low-bit failure modes: every finished retail/airline episode of the W3 / W2 / gauss3 cells and their BF16 references,
     one category per episode (rules in FAIL_RULES below).
Episode rules (all three parts): outage episodes are not data (W6) and user-simulator errors are missing (W41); a
context-window overflow (W10) or an episode-ending agent parse error (W27/W41) is the agent's failure (Y = 0). Part 1-2
also report the restore_eval convention (every infrastructure episode missing) as a sensitivity.
Intervals: analyze_dev.Boot (W63): t over block means is primary with < 10 blocks (here 3), crossed task x block 95%
alongside; B = 2000, seed 20261001; draws shared within a block family, so q4/q8 pools and arm contrasts are paired.

usage: python analysis/fork/analyze_backfill.py --snapshot <snapshot.json> --pivot <analysis/fork/out/pivot_arms_*.json>
-> analysis/fork/out/backfill_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from backfill_common import ROOT, excl0, fmt, git_head, sha256
from backfill_dose import dose, render_dose
from backfill_failmodes import failure_modes, render_failmodes
from backfill_restore import pivot_extract, render_restore, restoration, unfinished_arms

OUT = ROOT / "analysis/fork/out"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot")
    ap.add_argument("--pivot")
    ap.add_argument("--render", help="re-render the md of an existing backfill_<UTC>.json (no recomputation)")
    a = ap.parse_args()
    if a.render:
        jp = Path(a.render).resolve()
        jp.with_suffix(".md").write_text(render(json.load(open(jp)), jp))
        print(f"analyze_backfill: rendered {jp.with_suffix('.md').relative_to(ROOT)}")
        return
    if not (a.snapshot and a.pivot):
        ap.error("--snapshot and --pivot are required")
    t0 = time.time()
    snap = json.load(open(a.snapshot))
    fz = snap["frozen"]
    res = {"label": "EXPLORATORY appendix backfill (W100x); A6000 a6k2 runs only; never pooled with 4080 results",
           "analysis": "analysis/fork/analyze_backfill.py", "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "script": {"sha256": sha256(__file__), "git_head": git_head(),
                      "modules": {f"backfill_{m}.py": sha256(Path(__file__).with_name(f"backfill_{m}.py")) for m in ("common", "restore", "dose", "failmodes")}},
           "snapshot": {"id": snap.get("snapshot_id"), "path": str(Path(a.snapshot).resolve()), "sha256": sha256(a.snapshot)},
           "episode_rule": "outage (W6) and user_sim_error (W41) episodes missing; context_overflow (W10) and agent_parse_error (W27/W41) = failure",
           "bootstrap": "analyze_dev.Boot: ci95 = t over block means (3 blocks, df 2); crossed_ci95 = crossed task x block; B 2000, seed 20261001"}
    res["restoration"] = restoration(fz, "w10")
    res["restoration_sens_allinfra"] = {k: {"diff": v["diff"], "n_units": v["n_units"]} for k, v in restoration(fz, "allinfra")["contrasts"].items()}
    res["pivot"] = pivot_extract(ROOT / a.pivot if not Path(a.pivot).is_absolute() else Path(a.pivot))
    res["dose"] = dose(fz, "w10")
    res["dose_sens_allinfra"] = {k: {al: v["per_alpha"][al]["success"] for al in v["per_alpha"]} for k, v in dose(fz, "allinfra")["cells"].items()}
    res["failure_modes"] = failure_modes(snap)
    res["unfinished_arm_runs"] = unfinished_arms(snap)
    res["seconds"] = round(time.time() - t0, 1)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"backfill_{stamp}.json"
    json.dump(res, open(jp, "w"), indent=1, default=str)
    (OUT / f"backfill_{stamp}.md").write_text(render(res, jp))
    print(f"analyze_backfill: wrote {jp.relative_to(ROOT)} ({res['seconds']} s)")


def tldr(res: dict) -> list[str]:
    """Readable TL;DR; every number is computed here from the JSON (no hand-typed values)."""
    R, P, D, F = res["restoration"], res["pivot"], res["dose"], res["failure_modes"]
    pool, cs = R["pooled"], R["contrasts"]
    both = [k for k, v in cs.items() if excl0(v["diff"]) != "0" and excl0(v["diff"], "crossed_ci95") != "0"]
    n_t = sum(1 for v in cs.values() if excl0(v["diff"]) != "0")
    other = [k for k in cs if not k.split(":")[1] == "rtn_w3"]
    other_both = [k for k in other if k in both]
    piv = P["cells"].get("q4:rtn_w3", {})
    pg = P.get("gptq_w3_pooled_delta", {})
    inc = "; ".join(f"{i['contrast']} (located arm admitted: {len(i['structured_admitted'])} of 6 run-domains)" for i in R["incomplete"])
    exs = "; ".join(f"{k} without {', '.join(s.split('_')[-1] for s in v)}" for k, v in ((k, c["seeds_excluded"]) for k, c in cs.items()) if v)
    L = ["1. **Restoration location vs byte-matched random modules (exploratory; success pp, located minus mean of the complete random "
         "seeds; t over 3 blocks, x[crossed]).** RTN-W3, q4 and q8 pooled: attention " + fmt(pool.get("rtn_w3:attn")) +
         ", last third " + fmt(pool.get("rtn_w3:late")) + ", middle third " + fmt(pool.get("rtn_w3:middle")) + ", MLP " +
         fmt(pool.get("rtn_w3:mlp")) + " (early third: q4 not finished). "
         f"GPTQ-W3, q4 GPTQ-W4 and q8 AWQ-W4: {len(other_both)} of {len(other)} contrasts exclude 0 under both intervals. "
         f"Overall {len(both)} of {len(cs)} per-cell contrasts exclude 0 under both intervals ({', '.join(both)}), {n_t} under the t interval alone; "
         "no multiplicity correction. Pivot-time single decision (one random seed): attention reverts more actions to BF16's than "
         f"random in q4 RTN-W3 {fmt(piv.get('attn', {}).get('delta'))} and GPTQ-W3 pooled {fmt(pg.get('attn'))}; the last third fewer "
         f"(q4 RTN-W3 {fmt(piv.get('late', {}).get('delta'))}). Not analysable: {inc}. Seeds missing: {exs}. "
         "q8 RTN-W3 pivot arms incomplete, so the FORK_PROTOCOL §13 step-3 selection never ran."]
    mono = []
    for cell, c in D["cells"].items():
        st = c["steps"]
        n_dn = sum(1 for v in st.values() if excl0(v["action_prefix"]) == "-" and excl0(v["action_prefix"], "crossed_ci95") == "-")
        mono.append(n_dn == len(st))
        res_s = [f"{k} {fmt(v['success'])}" for k, v in st.items() if excl0(v["success"]) != "0" and excl0(v["success"], "crossed_ci95") != "0"]
        c["_resolved_success_steps"] = res_s
    rq4, rq8 = D["cells"].get("q4:rtn_w3"), D["cells"].get("q8:rtn_w3")
    seqs = "; ".join(f"{cell} " + " / ".join(f"{c['per_alpha'][a]['success']['est']:.1f}" for a in c["alphas"]) +
                     " (a = " + ", ".join(c["alphas"]) + ")" for cell, c in D["cells"].items())
    resolved = "; ".join(f"{cell}: {', '.join(c['_resolved_success_steps'])}" for cell, c in D["cells"].items() if c["_resolved_success_steps"]) or "none"
    L.append("2. **Error dose a (exploratory).** Action agreement with BF16 (share of BF16's decisions before the first differing action) "
             f"falls at every a step in {sum(mono)} of {len(mono)} cells, every step's two intervals below 0 (q8 RTN-W3: " +
             ", ".join(f"{rq8['per_alpha'][a]['action_prefix']['est']:.2f}" for a in rq8["alphas"]) + "). Success is not monotone in a: " + seqs +
             f". Success steps resolved under both intervals: {resolved}. a = 2 not finished: " +
             ", ".join(i["cell"] for i in D["incomplete"]) + ".")
    rows = F["rows"]

    def r(lab, k):
        x = rows.get(lab) or {}
        return x.get(k) if k.startswith("pct_") else (x.get("pct") or {}).get(k)
    bf = [lab for lab in rows if "BF16" in lab and "W2" not in lab and rows[lab]["n"]]
    L.append("3. **Low-bit failure modes (descriptive; % of finished non-outage retail/airline episodes).** BF16 failures end normally "
             "in a wrong end state (" + ", ".join(f"{lab.split()[0]} {r(lab, 'pct_normal_end_wrong_state')}" for lab in bf) +
             "; abnormal endings " + ", ".join(f"{r(lab, 'pct_abnormal_end')}" for lab in bf) + "). "
             f"q4 RTN-W3: runaway {r('q4 RTN-W3', 'runaway')}, plain-text tool calls with no parsed write {r('q4 RTN-W3', 'format')} "
             f"(text calls in {rows['q4 RTN-W3']['pct_episodes_with_text_tool_calls']} of episodes; parsed write in "
             f"{rows['q4 RTN-W3']['pct_episodes_with_parsed_write']}; {rows['q4 RTN-W3']['n_success_on_write_tasks']} of its "
             f"{rows['q4 RTN-W3']['n_success']} successes need a write). q4 AWQ-W3: runaway {r('q4 AWQ-W3', 'runaway')}, "
             f"text calls {r('q4 AWQ-W3', 'format')}, no write {r('q4 AWQ-W3', 'no_write')}. q8 RTN-W3: runaway {r('q8 RTN-W3', 'runaway')}, "
             f"tool-error cap {r('q8 RTN-W3', 'tool_errors')}. GPTQ-W3 abnormal endings: " +
             ", ".join(f"{lab.split()[0]} {r(lab, 'pct_abnormal_end')}" for lab in rows if lab.endswith("GPTQ-W3") and rows[lab]["n"]) +
             ". W2 panel (24 tasks, loop guard): runaway " + ", ".join(f"{lab.split(' W2')[0]} {r(lab, 'runaway')}" for lab in rows
                                                                       if "W2-panel" in lab and "BF16" not in lab and rows[lab]["n"]) +
             ". Not finished: " + ", ".join(sorted({u["group"] for u in F["unfinished"] if not rows.get(u["group"], {}).get("n")})) + ".")
    return L


def render(res: dict, jp: Path) -> str:
    L = ["**TL;DR** EXPLORATORY appendix backfill on finished A6000 runs (snapshot " + str(res["snapshot"]["id"]) + "); outages are not data (W6), "
         "context overflow counts as failure (W10); never pooled with 4080 results; 3 blocks per cell, so t intervals have df 2 and "
         "crossed intervals are shown alongside (x[...]).", ""] + tldr(res) + [""]
    L += [f"# Appendix backfill: restoration location, error dose, low-bit failure modes ({res['utc']})", "",
          f"Full numbers: `{jp.relative_to(ROOT) if jp.is_relative_to(ROOT) else jp}`. Script `{res['analysis']}` (sha {res['script']['sha256'][:12]}; "
          + ", ".join(f"{k} {v[:12]}" for k, v in (res["script"].get("modules") or {}).items()) + f"; "
          f"HEAD {res['script']['git_head'][:10]}); snapshot `{res['snapshot']['path']}` (sha {res['snapshot']['sha256'][:12]}). "
          f"Episode rule: {res['episode_rule']}. Intervals: {res['bootstrap']}. pp throughout; est [t over block means] x[crossed task x block].", ""]
    L += render_restore(res) + render_dose(res) + render_failmodes(res)
    return "\n".join(L)


if __name__ == "__main__":
    main()
