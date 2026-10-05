"""Frozen Q-only uncertainty trigger read under three upgrade modes (G / H / F). EXPLORATORY, POST HOC.

Protocol (written before this ran): docs/insights/TRIGGER_GHF_POSTHOC.md. Selections are exactly the frozen rule's
(manifests/fork/token_trigger_rule_v1.json, S_mm, per-cell thresholds at 5/10/20%); nothing is refit. Data are loaded
only via analyze_token_mech.load()/features(). Labels per state: G = Y_BQ - Y_QQ, H = Y_QB - Y_QQ, F = Y_BB - Y_QQ.
Not a deployable router; budgets are state-selection budgets, not equal BF16 compute.

usage: python analysis/fork/trigger_ghf.py [--B 2000] [--seed 20261005]
  -> analysis/fork/out/trigger_ghf_<UTC>.{md,json}
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_token_mech as TM  # noqa: E402
import trigger_ghf_core as C  # noqa: E402
import trigger_ghf_report as REP  # noqa: E402

RULE_SHA = "335e737d54bf59b948022b8054897ba703a1b9df6665f55bf6ab19b70333c052"
W98 = {"0.05": (50, 4, 0.0345), "0.1": (114, 2, 0.4169), "0.2": (222, 5, 0.2617)}
FRAMES = {"PRIMARY U1 f02+f03": ("U1", ("f02", "f03")), "SECONDARY A U1 f01 (in-sample block)": ("U1", ("f01",)),
          "SECONDARY B U2B f02+f03": ("U2B", ("f02", "f03")), "SECONDARY B U2Q f02+f03": ("U2Q", ("f02", "f03"))}


def exact_p(rows, mode):
    nulls, net = [], 0
    for c, xs in C.by_cell(rows).items():
        xs = [r for r in xs if r[mode] is not None]
        R, D = sum(r[mode] == 1 for r in xs), sum(r[mode] == -1 for r in xs)
        nulls.append(TM.null_dist(R, D, len(xs), sum(r["sel"] for r in xs)))
        net += sum(r[mode] for r in xs if r["sel"])
    ng = TM.convolve(nulls)
    return round(sum(p for k, p in ng.items() if k >= net), 4)


def oracle(rows, mode):
    tot = {}
    for c, xs in C.by_cell(rows).items():
        xl = [r for r in xs if r[mode] is not None]
        m = sum(r["sel"] for r in xl)
        o = C.oracle_cell(xs, m, mode)
        ident = C.oracle_identity(len(xl), sum(r[mode] == 1 for r in xl), sum(r[mode] == -1 for r in xl), m)
        assert abs(o[f"net_{mode}"] - ident) < 1e-9, (c, mode, o[f"net_{mode}"], ident)
        for k, v in o.items():
            tot[k] = tot.get(k, 0) + v
    return {k: round(v, 3) for k, v in tot.items()}


def run_frame(us, sub, blocks, rule, s, args, boot: bool):
    pop = [u for u in us if u["sub"] == sub and u["block"] in blocks]
    cov = {"rows": len(pop), "four_arm": sum(C.four_arm(u) for u in pop),
           **{f"has_{q}": sum(u[q] is not None for u in pop) for q in C.MODES}}
    out = {"coverage": cov, "rates": {}}
    bt = C.Boot(pop, args.B, args.seed) if boot else None
    for rate in TM.RATES:
        thr = rule["thresholds"][str(rate)]
        rows = [dict(u, sel=u[s] > thr[u["c"]]) for u in pop]
        sel = [r for r in rows if r["sel"]]
        e = {"selected": len(sel), "selected_share": round(len(sel) / len(pop), 4), "selected_four_arm": sum(C.four_arm(r) for r in sel),
             "cost_proxy_mean_remaining_decisions": round(float(np.mean([r["n_dec"] - r["t"] for r in sel])), 2) if sel else None,
             "best_mode_forced_sum": sum(max(r[q] for q in C.MODES) for r in sel if C.four_arm(r)), "modes": {}}
        for q in C.MODES:
            P = C.point(rows, q)
            e["modes"][q] = {"pooled": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in P["pooled"].items()},
                             "per_cell": P["per_cell"], "exact_p": exact_p(rows, q), "oracle": oracle(rows, q)}
        if bt is not None:
            e["boot"] = bt.summary(sel)
        out["rates"][str(rate)] = e
    if boot:
        ps = [out["rates"][str(r)]["modes"][q]["exact_p"] for r in TM.RATES for q in C.MODES]
        hs = C.holm(ps)
        for i, (r, q) in enumerate((r, q) for r in TM.RATES for q in C.MODES):
            out["rates"][str(r)]["modes"][q]["holm9"] = hs[i]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261005)
    args = ap.parse_args()
    assert TM.sha_file(TM.RULE) == RULE_SHA, "frozen rule sha changed"
    rule = json.loads(TM.RULE.read_text())
    s = rule["chosen_score"]
    rows, inputs = TM.load()
    us = [TM.features(r) for r in rows if "acts" in r]
    Ys = {(r["state_key"], r["model"], r["cell"], r["block"], r["sub"]): r for r in rows}
    assert len(Ys) == len(rows), "duplicate join keys in score rows"
    for u in us:
        r = Ys[(u["state_key"], u["model"], u["cell"], u["block"], u["sub"])]
        u.update(C.labels(r["Y"]))
        u.update({"c": f"{u['model']}_{u['cell']}", "key": u["state_key"], "n_dec": r["n_decisions"], "t": r["t"]})
    # W98 reproduction (frozen rule, G, U1 f02/f03) before anything else
    val = [u for u in us if u["sub"] == "U1" and u["block"] in ("f02", "f03")]
    assert len(val) == 1020
    for rk, (n, net, p) in W98.items():
        P = TM.escalate(val, s, rule["thresholds"][rk])["pooled"]
        assert (P["n_escalated"], P["net_gain"], P["p_net_ge_random"]) == (n, net, p), (rk, P)
    assert all(u["G"] == TM.features(Ys[(u["state_key"], u["model"], u["cell"], u["block"], u["sub"])])["G"] for u in val)
    R = {"utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "status": "EXPLORATORY, POST HOC",
         "protocol": "docs/insights/TRIGGER_GHF_POSTHOC.md", "script": TM.rel(Path(__file__)),
         "script_sha256": TM.sha_file(Path(__file__)), "core_sha256": TM.sha_file(Path(C.__file__)),
         "report_sha256": TM.sha_file(Path(REP.__file__)), "analyze_token_mech_sha256": TM.sha_file(Path(TM.__file__)),
         "git_head": subprocess.run(["git", "-C", str(TM.ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "rule_sha256": RULE_SHA, "chosen_score": s, "B": args.B, "seed": args.seed, "inputs_token_scores": inputs,
         "checks": {"score_rows": len(rows), "rows_with_acts": len(us), "w98_primary_reproduced": True}, "frames": {}}
    for name, (sub, blocks) in FRAMES.items():
        R["frames"][name] = run_frame(us, sub, blocks, rule, s, args, boot=name.startswith("PRIMARY"))
    TM.OUT.mkdir(parents=True, exist_ok=True)
    base = TM.OUT / f"trigger_ghf_{R['utc']}"
    Path(str(base) + ".json").write_text(json.dumps(R, indent=1, default=str))
    Path(str(base) + ".md").write_text(REP.markdown(R))
    print(TM.rel(Path(str(base) + ".md")))


if __name__ == "__main__":
    main()
