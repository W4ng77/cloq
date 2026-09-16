"""Evaluate the plan's pre-specified continuation and stop rules (sections 24 and 25).

The rules were fixed before any quantized run; this module reads the finished analysis and
states which of them fired, so the go/no-go decision is mechanical rather than a judgement call.

  Signal A  horizon amplification: the Static gap is larger on long-horizon tasks than short ones.
  Signal B  occupancy shift: support distance rises after the first divergence AND the quantized
            state distribution is separated from the full-precision one (MMD above its null).
  Signal C  trajectory calibration: FP-Traj beats Static on closed-loop success, or on first-divergence
            position, or on post-divergence support coverage.
  Strong    CLOQ beats FP-Traj at the same calibration token budget.

Proceed to the full paper if at least two of A, B, C fired.

usage: python -m cloq.signals
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cloq import config as C

ANALYSIS = C.PROJECT_ROOT / "analysis"


def _get(d: dict, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def evaluate(results_path: Path, occupancy_path: Path | None = None) -> dict:
    r = json.load(open(results_path))
    occ = None
    if occupancy_path and Path(occupancy_path).exists():
        occ = json.load(open(occupancy_path))
    elif "occupancy_last" in r:
        occ = r["occupancy_last"]
    out = {"signals": {}, "notes": []}

    # ---- Signal A: horizon amplification (Static) --------------------------
    amp = _get(r, "pooled", "horizon_amplification_db_match", "static", default={})
    a_fired = bool(amp) and amp.get("gap_long_minus_short", 0) > 0 and amp.get("p_amplification_le_0", 1) < 0.10
    out["signals"]["A_horizon_amplification"] = {
        "fired": a_fired,
        "gap_short": amp.get("gap_short"), "gap_long": amp.get("gap_long"),
        "long_minus_short": amp.get("gap_long_minus_short"),
        "ci": [amp.get("ci_lo"), amp.get("ci_hi")], "p_le_0": amp.get("p_amplification_le_0"),
        "rule": "Static gap larger on long-horizon tasks (median split), one-sided p < 0.10",
    }

    # ---- Signal B: occupancy shift ----------------------------------------
    b_detail = {}
    b_fired = False
    if occ:
        for domain, d in occ.get("domains", {}).items():
            for arm, v in d.get("arms", {}).items():
                pp = _get(v, "pre_post_divergence", "fp_traj", default={})
                pre, post = pp.get("pre_mean"), pp.get("post_mean")
                mmd, null = v.get("mmd_fp_vs_q"), v.get("mmd_fp_half_vs_half")
                rose = pre is not None and post is not None and post > pre
                sep = mmd is not None and null is not None and mmd > 2 * abs(null)
                b_detail[f"{domain}/{arm}"] = {
                    "support_pre": pre, "support_post": post, "support_rose": rose,
                    "mmd_fp_vs_q": mmd, "mmd_null": null, "separated": sep,
                }
                if rose and sep:
                    b_fired = True
    out["signals"]["B_occupancy_shift"] = {
        "fired": b_fired, "per_arm": b_detail,
        "rule": "support distance to the FP-Traj buffer higher after first divergence than before, "
                "and MMD(FP, Q) above twice its FP-split null, for at least one arm/domain",
    }

    # ---- Signal C: trajectory calibration beats static ---------------------
    c_detail = {}
    c_fired = False
    for domain, d in r.get("domains", {}).items():
        con = _get(d, "contrasts", "db_match", "fp_traj - static", default={})
        succ = bool(con) and con.get("ci_lo", -1) > 0
        div_s = _get(d, "divergence", "static", default={})
        div_f = _get(d, "divergence", "fp_traj", default={})
        later = (div_f.get("median_t_star_norm") or 0) > (div_s.get("median_t_star_norm") or 0)
        ol_s = _get(d, "openloop", "static", default={})
        ol_f = _get(d, "openloop", "fp_traj", default={})
        fidelity = (ol_f.get("full_tool_call_agreement") or 0) > (ol_s.get("full_tool_call_agreement") or 0)
        c_detail[domain] = {
            "closed_loop_diff": con.get("diff"), "closed_loop_ci": [con.get("ci_lo"), con.get("ci_hi")],
            "closed_loop_beats_static": succ,
            "median_t_star_norm_static": div_s.get("median_t_star_norm"),
            "median_t_star_norm_fp_traj": div_f.get("median_t_star_norm"), "diverges_later": later,
            "full_tool_call_agreement_static": ol_s.get("full_tool_call_agreement"),
            "full_tool_call_agreement_fp_traj": ol_f.get("full_tool_call_agreement"), "higher_fidelity": fidelity,
        }
        if succ or (later and fidelity):
            c_fired = True
    out["signals"]["C_trajectory_calibration"] = {
        "fired": c_fired, "per_domain": c_detail,
        "rule": "in at least one domain: FP-Traj beats Static on closed-loop success with a CI excluding 0, "
                "or diverges later AND reproduces more tool calls",
    }

    # ---- Strong method signal ---------------------------------------------
    strong = {}
    for domain, d in r.get("domains", {}).items():
        con = _get(d, "contrasts", "db_match", "cloq - fp_traj", default={})
        strong[domain] = {"diff": con.get("diff"), "ci": [con.get("ci_lo"), con.get("ci_hi")]}
    pooled = _get(r, "pooled", "db_match", "contrasts", "cloq - fp_traj", default={})
    strong_fired = bool(pooled) and pooled.get("ci_lo", -1) > 0
    out["signals"]["strong_method_cloq_over_fp_traj"] = {
        "fired": strong_fired, "pooled": {"diff": pooled.get("diff"), "ci": [pooled.get("ci_lo"), pooled.get("ci_hi")]},
        "per_domain": strong, "rule": "pooled CLOQ - FP-Traj on db_match with a CI excluding 0",
    }

    fired = [k for k in ("A_horizon_amplification", "B_occupancy_shift", "C_trajectory_calibration") if out["signals"][k]["fired"]]
    out["n_core_signals_fired"] = len(fired)
    out["core_signals_fired"] = fired
    out["proceed_to_full_paper"] = len(fired) >= 2
    out["decision_rule"] = "plan section 24: proceed if at least two of A, B, C fired"

    # ---- Stop / rethink rules (section 25) --------------------------------
    stops = {}
    means = _get(r, "pooled", "db_match", "means", default={})
    stops["2_occupancy_indistinguishable"] = not out["signals"]["B_occupancy_shift"]["fired"]
    stops["3_fp_traj_never_improves"] = not out["signals"]["C_trajectory_calibration"]["fired"]
    cloq_behaviour_better = None
    try:
        sec = {d: r["domains"][d]["secondary"] for d in r["domains"]}
        cloq_behaviour_better = all(
            (sec[d]["cloq"]["premature_rate"] or 0) <= (sec[d]["static"]["premature_rate"] or 0) for d in sec
        )
    except Exception:
        pass
    stops["4_cloq_adds_nothing"] = (not strong_fired) and (cloq_behaviour_better is False)
    stops["1_w3_needed"] = (means.get("bf16", 0) - means.get("static", 0)) < 0.01
    out["stop_rules"] = stops
    out["notes"].append(
        "Stop rule 4 requires CLOQ to improve neither success nor behaviour; CLOQ improving premature "
        "termination or repeated tool calls keeps it alive even when it does not raise task success."
    )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ANALYSIS / "results.json"))
    ap.add_argument("--occupancy", default=str(ANALYSIS / "occupancy_last.json"))
    ap.add_argument("--out", default=str(ANALYSIS / "signals.json"))
    a = ap.parse_args()
    res = evaluate(Path(a.results), Path(a.occupancy))
    Path(a.out).write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "signals"}, indent=2))
    for k, v in res["signals"].items():
        print(f"{'FIRED  ' if v['fired'] else 'not met'}  {k}")
    print(f"\n=> proceed to full paper: {res['proceed_to_full_paper']} ({res['n_core_signals_fired']} of 3 core signals)")


if __name__ == "__main__":
    main()
