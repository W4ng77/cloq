"""Matched oracles and a post-hoc KL reference row for the frozen Q-only escalation trigger (GPT-6.1 review 9; after W98).

Population: Bank U sub-bank U1, validation blocks f02/f03 (1020 cell x state rows, 6 cells x 170), exactly the rows of the
W98 validation (analysis/fork/analyze_token_mech.py, frozen rule manifests/fork/token_trigger_rule_v1.json, sha 335e737d...).
Nothing in analyze_token_mech.py or the frozen rule is changed; its loader, features, thresholds and escalate() are imported.

1a. ACTION-REPLACEMENT ORACLE (direct upper bound for the trigger). Per cell and budget, select the SAME number of rows m_c
    as the frozen rule selected, choosing only rows with G = Y_BQ - Y_QQ > 0 (rescues). If a cell has fewer rescues than
    m_c, all rescues are taken and the rest is filled with G = 0 rows (counted). Hindsight selection: not a policy.
1b. THREE-OPTION MENU ORACLE (extra diagnostic). Per state, max(G, H, F, 0) with G = BQ-QQ, H = QB-QQ, F = BB-QQ; binary Y
    makes it the indicator "QQ fails and some other arm succeeds". Primary data: Bank P divergent states (W93 admission,
    imported from analyze_ghf/analyze_dev; units digests checked against dev_all_20261001T070326Z). Also on the same Bank U
    U1 f02/f03 rows (Bank U has all four arms). Hindsight outcome selection that ALSO allows a different replacement type
    (continuation, or both): NOT comparable to the action trigger as a same-cost deployment.
2.  KL REFERENCE ROW (post-hoc auxiliary baseline; needs BF16). Score = top-20-union KL(B||Q) with one tail bucket
    (KLu, as scored by score_driver.py) over Q's own action a_Q, teacher-forced under B and Q. Candidates KLu_0 (first a_Q
    token), KLu_mean, KLu_max over a_Q; chosen on f01 U1 only with the frozen rule's own criterion and per-cell f01
    quantile thresholds at 5/10/20% (analyze_token_mech.thresholds); evaluated on f02/f03 U1 with escalate() (exact
    hypergeometric null vs a matched-count random trigger), Holm over the three budgets. Post-hoc: the f02/f03 outcomes
    were already seen (W98), so this is not a prospective validation. Not a DMR reproduction.

usage: python analysis/fork/oracle_trigger.py  -> analysis/fork/out/oracle_trigger_<UTC>.{md,json}
"""
from __future__ import annotations

import collections
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_token_mech as TM  # noqa: E402

ROOT, OUT = TM.ROOT, TM.OUT
RULE_SHA = "335e737d54bf59b948022b8054897ba703a1b9df6665f55bf6ab19b70333c052"
RATES = TM.RATES
KL_CANDS = ("KLu_0", "KLu_mean", "KLu_max")
REF_DEV_ALL = "analysis/fork/out/dev_all_20261001T070326Z.json"
SNAPSHOT = "analysis/insights/iter_3/out/snapshot_auto_20261001T0600Z.json"
MAIN_CELLS = ("gptq_w4_d1", "awq_w4", "kvq_int8")


def ck(u):
    return f"{u['model']}_{u['cell']}"


def cp(k, n, a=0.05):
    from scipy.stats import beta
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return [round(lo, 4), round(hi, 4)]


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [None] * len(ps), 0.0
    for j, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - j) * ps[i]))
        adj[i] = round(run, 4)
    return adj


# ----------------------------------------------------------------------------------------------------------------------
# 1a. action-replacement oracle
# ----------------------------------------------------------------------------------------------------------------------

def action_oracle(val, frozen):
    cells = collections.defaultdict(list)
    for u in val:
        cells[ck(u)].append(u)
    per, tot = {}, collections.Counter()
    for c, xs in sorted(cells.items()):
        m = frozen["per_cell"][c]["n_escalated"]
        R = sum(u["r"] for u in xs)
        Z = sum(1 for u in xs if u["G"] == 0)
        take_r = min(m, R)
        fill0 = m - take_r
        assert fill0 <= Z, (c, m, R, Z)
        per[c] = {"N": len(xs), "R": R, "D": sum(u["d"] for u in xs), "selected": m, "rescues": take_r, "damages": 0,
                  "net": take_r, "zero_fill": fill0, "frozen_net": frozen["per_cell"][c]["net_gain"],
                  "frozen_rescued": frozen["per_cell"][c]["rescued"], "frozen_damaged": frozen["per_cell"][c]["damaged"],
                  "random_expected_net": frozen["per_cell"][c]["random_expected_net"]}
        for k in ("N", "R", "selected", "rescues", "damages", "net", "zero_fill"):
            tot[k] += per[c][k]
    tot = dict(tot)
    fp = frozen["pooled"]
    tot.update({"frozen_net": fp["net_gain"], "frozen_rescued": fp["rescued"], "frozen_damaged": fp["damaged"],
                "random_expected_net": fp["random_expected_net"], "headroom_vs_frozen": tot["net"] - fp["net_gain"],
                "frozen_rescue_capture_of_oracle": round(fp["rescued"] / tot["rescues"], 3) if tot["rescues"] else None,
                "oracle_net_pp": round(100 * tot["net"] / tot["N"], 2), "frozen_net_pp": round(100 * fp["net_gain"] / tot["N"], 2),
                "random_net_pp": round(100 * fp["random_expected_net"] / tot["N"], 2),
                "cells_short_of_rescues": sorted(c for c, v in per.items() if v["zero_fill"] > 0)})
    return {"per_cell": per, "pooled": tot}


# ----------------------------------------------------------------------------------------------------------------------
# 1b. three-option menu oracle
# ----------------------------------------------------------------------------------------------------------------------

def menu_stats(Ys):
    n = len(Ys)
    G = [y["BQ"] - y["QQ"] for y in Ys]
    H = [y["QB"] - y["QQ"] for y in Ys]
    F = [y["BB"] - y["QQ"] for y in Ys]
    mx = [max(g, h, f, 0) for g, h, f in zip(G, H, F)]
    k = sum(mx)
    only = collections.Counter()
    for y in Ys:
        if y["QQ"] == 0:
            arms = "".join(a for a in ("BQ", "QB", "BB") if y[a] == 1)
            if arms:
                only[arms] += 1
    return {"n_states": n, "QQ_success": sum(y["QQ"] for y in Ys),
            "E_max_GHF0": round(k / n, 4) if n else None, "E_max_GHF0_ci95_CP": cp(k, n) if n else None, "n_some_arm_beats_QQ": k,
            "E_max_G0 (action-only oracle share)": round(sum(max(g, 0) for g in G) / n, 4) if n else None,
            "n_G_pos": sum(g > 0 for g in G), "n_H_pos": sum(h > 0 for h in H), "n_F_pos": sum(f > 0 for f in F),
            "n_beats_QQ_but_not_via_G": sum(1 for m, g in zip(mx, G) if m > 0 and g <= 0),
            "E_G": round(float(np.mean(G)), 4) if n else None, "E_H": round(float(np.mean(H)), 4) if n else None,
            "E_F": round(float(np.mean(F)), 4) if n else None,
            "winning_arm_sets_when_QQ_fails": dict(sorted(only.items()))}


def bank_p_menu():
    import analyze_dev as AD
    import analyze_ghf as GHF
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    snap = json.load(open(ROOT / SNAPSHOT))
    loaded = [AD.load_dir(d, snap, {}) for d in GHF.discover()]
    allu = [u for L in loaded for u in L["units"]]
    AD.split_guard(allu, "dev", "oracle_trigger")
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined fork task (QQ no-op mismatch)")
    units, _ = AD.dedupe_units(allu)
    AD.mark_incomplete_blocks(units, "dev", strict=True)
    AD.mark_partial_panel_blocks(units, "dev")
    ok = [u for u in units if "excluded" not in u]
    ref = json.load(open(ROOT / REF_DEV_ALL))
    out = {}
    cells = sorted({(u["model"], u["cell"]) for u in ok if u["domain"] in GHF.PANEL})
    for m, c in cells:
        lab = f"{m}:{c}"
        cu = [u for u in ok if (u["model"], u["cell"]) == (m, c) and u["domain"] in GHF.PANEL]
        dg = AD.units_digest(cu)
        rd = (ref["cells"].get(lab) or {}).get("units_digest_sha256")
        div = [u for u in cu if u["div"]]
        st = menu_stats([u["Y"] for u in div])
        st.update({"family": AD.family(c), "units_digest_match_dev_all": dg == rd, "n_blocks": len({u["block"] for u in cu})})
        out[lab] = st
    return out, {"snapshot": SNAPSHOT, "snapshot_sha256": AD.sha256(ROOT / SNAPSHOT), "reference": REF_DEV_ALL,
                 "fork_roots": GHF.FORK_ROOTS, "analyze_ghf_sha256": AD.sha256(GHF.__file__), "analyze_dev_sha256": AD.sha256(AD.__file__)}


# ----------------------------------------------------------------------------------------------------------------------
# 2. KL reference row
# ----------------------------------------------------------------------------------------------------------------------

def add_kl_scores(us):
    for u in us:
        jit = 1e-9 * int(hashlib.sha256(f"token-trigger-v1|{u['state_key']}".encode()).hexdigest()[:8], 16) / 16 ** 8
        for s in KL_CANDS:
            u[f"S_{s}"] = u[s] + jit


def kl_fit(dev):
    pop = [u for u in dev if u["sub"] == "U1"]
    table = {}
    for s in KL_CANDS:
        table[s] = {}
        for rate in RATES:
            e = TM.escalate(pop, f"S_{s}", TM.thresholds(pop, f"S_{s}", rate))["pooled"]
            table[s][str(rate)] = {k: e[k] for k in ("n_escalated", "net_gain", "rescued", "damaged", "turnover_captured",
                                                     "random_expected_net", "random_expected_turnover")}

    def key(s):  # the frozen rule's criterion (analyze_token_mech.freeze_rule), applied to the KL candidates
        v = table[s].values()
        return (np.mean([x["net_gain"] - x["random_expected_net"] for x in v]),
                np.mean([x["turnover_captured"] - x["random_expected_turnover"] for x in v]), -KL_CANDS.index(s))
    best = max(KL_CANDS, key=key)
    return {"f01_in_sample": table, "chosen": best, "n_f01_U1": len(pop),
            "thresholds": {s: {str(r): TM.thresholds(pop, f"S_{s}", r) for r in RATES} for s in KL_CANDS}}


def kl_eval(val, fit):
    pop = [u for u in val if u["sub"] == "U1"]
    out = {}
    for s in KL_CANDS:
        res = {str(r): TM.escalate(pop, f"S_{s}", fit["thresholds"][s][str(r)]) for r in RATES}
        adj = holm([res[str(r)]["pooled"]["p_net_ge_random"] for r in RATES])
        for r, a in zip(RATES, adj):
            res[str(r)]["pooled"]["p_net_holm3"] = a
        out[s] = res
    return out


def kl_count_matched(val, frozen_by_rate, s):
    """Secondary: top-m_c per cell by the KL score with m_c = the frozen rule's per-cell counts (uses validation ranks)."""
    pop = [u for u in val if u["sub"] == "U1"]
    cells = collections.defaultdict(list)
    for u in pop:
        cells[ck(u)].append(u)
    out = {}
    for r in RATES:
        thr = {}
        for c, xs in cells.items():
            m = frozen_by_rate[str(r)]["per_cell"][c]["n_escalated"]
            v = sorted((u[f"S_{s}"] for u in xs), reverse=True)
            thr[c] = (v[m - 1] + v[m]) / 2 if 0 < m < len(v) else (v[0] + 1 if m == 0 else v[-1] - 1e-9)
        out[str(r)] = TM.escalate(pop, f"S_{s}", thr)
    adj = holm([out[str(r)]["pooled"]["p_net_ge_random"] for r in RATES])
    for r, a in zip(RATES, adj):
        out[str(r)]["pooled"]["p_net_holm3"] = a
    return out


# ----------------------------------------------------------------------------------------------------------------------

def main():
    rule_sha = TM.sha_file(TM.RULE)
    assert rule_sha == RULE_SHA, f"frozen rule sha changed: {rule_sha}"
    rule = json.loads(TM.RULE.read_text())
    rows, inputs = TM.load()
    us = [TM.features(r) for r in rows if "acts" in r]
    n_missing_acts = len(rows) - len(us)
    add_kl_scores(us)
    dev = [u for u in us if u["block"] in TM.DEV]
    val = [u for u in us if u["block"] not in TM.DEV and u["sub"] == "U1"]
    assert {u["block"] for u in val} == {"f02", "f03"} and len(val) == 1020, (len(val), {u["block"] for u in val})
    s = rule["chosen_score"]
    frozen = {str(r): TM.escalate(val, s, rule["thresholds"][str(r)]) for r in RATES}
    # reproduce the W98 primary numbers
    w98 = {"0.05": (50, 4, 0.0345), "0.1": (114, 2, 0.4169), "0.2": (222, 5, 0.2617)}
    for r, (n, net, p) in w98.items():
        P = frozen[r]["pooled"]
        assert (P["n_escalated"], P["net_gain"], P["p_net_ge_random"]) == (n, net, p), (r, P)
    oracle = {r: action_oracle(val, frozen[r]) for r in frozen}
    menu_u = {}
    cells = collections.defaultdict(list)
    for u in val:
        cells[ck(u)].append(u)
    rowsY = {(r["state_key"], r["model"], r["cell"], r["block"], r["sub"]): r["Y"] for r in rows}
    for c, xs in sorted(cells.items()):
        menu_u[c] = menu_stats([rowsY[(u["state_key"], u["model"], u["cell"], u["block"], u["sub"])] for u in xs])
    menu_u["pooled (6 cells)"] = menu_stats([rowsY[(u["state_key"], u["model"], u["cell"], u["block"], u["sub"])] for u in val])
    menu_p, menu_p_meta = bank_p_menu()
    # KL
    kl_missing = sum(1 for u in us if any(v is None for v in (u["KLu_0"], u["KLu_mean"], u["KLu_max"])))
    fit = kl_fit(dev)
    kl = kl_eval(val, fit)
    kl_cm = kl_count_matched(val, frozen, fit["chosen"])
    cost = {"mean_prompt_tokens_U1_val": round(float(np.mean([r["n_prompt"] for r in rows if r["sub"] == "U1" and r["block"] != "f01"])), 1),
            "mean_len_aQ_tokens_U1_val": round(float(np.mean([u["len_Q"] for u in val])), 1)}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    git = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    R = {"utc": utc, "script": TM.rel(Path(__file__)), "script_sha256": TM.sha_file(Path(__file__)), "git_head": git,
         "analyze_token_mech_sha256": TM.sha_file(Path(TM.__file__)), "rule_sha256": rule_sha, "rule_chosen_score": s,
         "inputs_token_scores": inputs, "bank_p_inputs": menu_p_meta,
         "checks": {"score_rows": len(rows), "rows_without_acts": n_missing_acts, "val_U1_rows": len(val),
                    "kl_missing_rows (all blocks)": kl_missing, "w98_primary_reproduced": True},
         "frozen": {r: frozen[r] for r in frozen}, "action_oracle": oracle,
         "menu_oracle_bank_p": menu_p, "menu_oracle_bank_u_U1_f02f03": menu_u,
         "kl": {"definition": "KLu(B||Q): KL over the union of B's and Q's top-20 next-token sets plus one tail bucket, "
                              "per a_Q token, teacher-forced on the identical prompt ids (score_driver.py); truncated, not the full KL",
                "candidates": {"KLu_0": "KLu at the first a_Q token", "KLu_mean": "mean KLu over a_Q", "KLu_max": "max KLu over a_Q"},
                "tie_break": "same as the frozen rule: + 1e-9 * int(sha256('token-trigger-v1|' + state_key)[:8], 16) / 16**8",
                "fit_f01": fit, "val_f02f03": kl, "val_count_matched_to_frozen": kl_cm, "cost": cost}}
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / f"oracle_trigger_{utc}.json"
    jp.write_text(json.dumps(R, indent=1, default=str))
    (OUT / f"oracle_trigger_{utc}.md").write_text(markdown(R))
    print(TM.rel(jp.with_suffix(".md")))


def pp(x, n=1020):
    return f"{100 * x / n:+.2f}"


def markdown(R):
    L = []
    fr, orc, kl = R["frozen"], R["action_oracle"], R["kl"]
    ch = kl["fit_f01"]["chosen"]
    klv = kl["val_f02f03"][ch]
    mp = R["menu_oracle_bank_p"]
    mu = R["menu_oracle_bank_u_U1_f02f03"]["pooled (6 cells)"]
    core = [k for k in mp if k.split(":")[1] in MAIN_CELLS]
    w4 = [k for k in core if k.split(":")[1] != "kvq_int8"]
    L.append(f"# Matched oracles and a post-hoc KL reference row for the frozen token trigger ({R['utc']})\n")
    L.append("## TL;DR\n")
    o = {r: orc[r]["pooled"] for r in orc}
    L.append(f"- **Action-replacement oracle** (same rows, same per-cell counts as the frozen rule; hindsight). On f02/f03 U1 (1020 rows; 38 rescues, 31 damages) "
             f"it nets +{o['0.05']['net']} / +{o['0.1']['net']} / +{o['0.2']['net']} at 5/10/20% "
             f"({o['0.05']['oracle_net_pp']:+.2f} / {o['0.1']['oracle_net_pp']:+.2f} / {o['0.2']['oracle_net_pp']:+.2f} pp of 1020). "
             f"The frozen rule nets +{o['0.05']['frozen_net']} / +{o['0.1']['frozen_net']} / +{o['0.2']['frozen_net']} and random "
             f"+{o['0.05']['random_expected_net']:.2f} / +{o['0.1']['random_expected_net']:.2f} / +{o['0.2']['random_expected_net']:.2f}. "
             f"The rule captured {o['0.05']['frozen_rescued']}/{o['0.1']['frozen_rescued']}/{o['0.2']['frozen_rescued']} of the "
             f"oracle's {o['0.05']['rescues']}/{o['0.1']['rescues']}/{o['0.2']['rescues']} rescues and added "
             f"{o['0.05']['frozen_damaged']}/{o['0.1']['frozen_damaged']}/{o['0.2']['frozen_damaged']} damages. "
             f"At 10% and 20% every rescue in the bank fits in the budget ({o['0.1']['zero_fill']} and {o['0.2']['zero_fill']} zero-effect fill rows); "
             f"at 5% the cells {', '.join(o['0.05']['cells_short_of_rescues'])} have fewer rescues than selections ({o['0.05']['zero_fill']} fill rows).")
    pk = sum(mp[k]["n_some_arm_beats_QQ"] for k in core)
    pn = sum(mp[k]["n_states"] for k in core)
    pg = sum(mp[k]["n_G_pos"] for k in core)
    L.append(f"- **Three-option menu oracle** (diagnostic only; hindsight AND a different replacement type allowed; not a same-cost "
             f"deployment and not comparable to the action rule). On Bank P divergent states of the 6 core cells, E[max(G,H,F,0)] = "
             f"{min(mp[k]['E_max_GHF0'] for k in core):.3f}–{max(mp[k]['E_max_GHF0'] for k in core):.3f} per cell "
             f"({pk}/{pn} states pooled = {pk / pn:.3f}); action-only E[max(G,0)] is {pg}/{pn} = {pg / pn:.3f}. "
             f"On the Bank U U1 f02/f03 rows: {mu['n_some_arm_beats_QQ']}/{mu['n_states']} = {mu['E_max_GHF0']:.3f} "
             f"(action-only {mu['n_G_pos']}/{mu['n_states']}).")
    ps = [klv[str(r)]["pooled"] for r in RATES]
    L.append(f"- **KL reference row** (post-hoc; needs BF16; not Q-only; not a DMR reproduction). Chosen on f01 U1: **{ch}** "
             f"(top-20-union KL(B||Q) + tail bucket). On f02/f03 U1: selected {'/'.join(str(p['n_escalated']) for p in ps)}, net "
             f"{', '.join(f'{p['net_gain']:+d}' for p in ps)} vs random {'/'.join(f'{p['random_expected_net']:+.2f}' for p in ps)}, "
             f"exact p {'/'.join(f'{p['p_net_ge_random']:.4f}' for p in ps)}, Holm(3) {'/'.join(f'{p['p_net_holm3']:.4f}' for p in ps)}; "
             f"r/d {', '.join(f'{p['rescued']}/{p['damaged']}' for p in ps)}; turnover captured "
             f"{'/'.join(str(p['turnover_captured']) for p in ps)} vs random {'/'.join(f'{p['random_expected_turnover']:.2f}' for p in ps)} "
             f"(p {'/'.join(f'{p['p_turnover_ge_random']:.4f}' for p in ps)}). No row was missing a KL score "
             f"({R['checks']['kl_missing_rows (all blocks)']} missing; nothing imputed).")
    L.append(f"- **Reading.** The frozen Q-only rule realises {o['0.05']['frozen_net']}/{o['0.05']['net']}, {o['0.1']['frozen_net']}/{o['0.1']['net']} "
             f"and {o['0.2']['frozen_net']}/{o['0.2']['net']} of the same-budget action-oracle net. The headroom is large because rescues are "
             f"rare (38/1020) and the rule's selections are mostly zero-effect rows, plus damages that cancel most of its rescues. A BF16-informed "
             f"KL score, chosen on f01 the same way, also captures turnover above chance (count-matched to the rule's per-cell budget: "
             f"{'/'.join(str(kl['val_count_matched_to_frozen'][str(r)]['pooled']['turnover_captured']) for r in RATES)} vs the rule's "
             f"{'/'.join(str(fr[str(r)]['pooled']['turnover_captured']) for r in RATES)}) but does not select net-beneficial "
             f"replacements either; the non-chosen KL candidates (KLu_0, KLu_mean) look better on f02/f03, but picking them now would be "
             f"selection on validation data.")
    L.append("")
    L.append(f"Frozen rule sha256 `{R['rule_sha256']}` (chosen score {R['rule_chosen_score']}), unchanged; the W98 primary numbers "
             f"(50/114/222 selected, net +4/+2/+5, p .0345/.4169/.2617) are reproduced by the imported escalate() before anything else runs. "
             f"Script `{R['script']}` sha256 `{R['script_sha256'][:16]}…`; analyze_token_mech.py sha256 `{R['analyze_token_mech_sha256'][:16]}…`; "
             f"git HEAD at run `{R['git_head'][:10]}`.\n")
    # 1a
    L.append("## 1a. Action-replacement oracle (direct upper bound for the trigger)\n")
    L.append("Same 1020 f02/f03 U1 rows; per cell the oracle selects exactly as many rows m_c as the frozen rule did at that budget, "
             "taking only rows with G = Y_BQ − Y_QQ > 0; if a cell has fewer rescues than m_c, all of them are taken and the rest are "
             "G = 0 rows ('zero fill'). It never selects a damage. Random = matched-count random-trigger expectation (exact). "
             "pp = count / 1020 × 100. Hindsight selection, not a policy.\n")
    L.append("| budget | selected | oracle r / d / net (pp) | zero fill | frozen r / d / net (pp) | random net (pp) | headroom oracle − frozen | frozen rescues / oracle rescues |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in RATES:
        P = orc[str(r)]["pooled"]
        L.append(f"| {r:.0%} | {P['selected']} | {P['rescues']} / 0 / +{P['net']} ({pp(P['net'])}) | {P['zero_fill']} | "
                 f"{P['frozen_rescued']} / {P['frozen_damaged']} / {P['frozen_net']:+d} ({pp(P['frozen_net'])}) | "
                 f"{P['random_expected_net']:+.2f} ({pp(P['random_expected_net'])}) | {P['headroom_vs_frozen']:+d} ({pp(P['headroom_vs_frozen'])}) | "
                 f"{P['frozen_rescued']}/{P['rescues']} = {P['frozen_rescue_capture_of_oracle']:.3f} |")
    L.append("\nTotal rescues available in the bank: 38 (damages 31, turnover 69).\n")
    L.append("Per cell (selected m_c; R = rescues in the cell; oracle net; frozen r/d/net; random net):\n")
    L.append("| cell | N | R | D | 5%: m, oracle, frozen r/d/net, random | 10%: m, oracle, frozen r/d/net, random | 20%: m, oracle, frozen r/d/net, random |")
    L.append("|---|---|---|---|---|---|---|")
    for c in orc["0.05"]["per_cell"]:
        cells = []
        for r in RATES:
            v = orc[str(r)]["per_cell"][c]
            cells.append(f"{v['selected']}, +{v['net']}{' (fill ' + str(v['zero_fill']) + ')' if v['zero_fill'] else ''}, "
                         f"{v['frozen_rescued']}/{v['frozen_damaged']}/{v['frozen_net']:+d}, {v['random_expected_net']:+.2f}")
        v0 = orc["0.05"]["per_cell"][c]
        L.append(f"| {c} | {v0['N']} | {v0['R']} | {v0['D']} | " + " | ".join(cells) + " |")
    # 1b
    L.append("\n## 1b. Three-option menu oracle (extra diagnostic; NOT comparable to the action rule)\n")
    L.append("**Label:** hindsight outcome selection that ALSO allows different replacement types (replace only the continuation, H; "
             "or both action and continuation, F; or only the action, G). Replacing the continuation means running B for the rest of "
             "the episode, so this is neither the same intervention nor the same cost as one-step escalation. Y is binary, so "
             "max(G, H, F, 0) = 1 exactly when QQ fails and at least one of BQ, QB, BB succeeds; E[max(G,H,F,0)] therefore equals the "
             "share of states where some arm beats QQ. 95% Clopper–Pearson intervals over states (states are not independent across "
             "tasks/blocks; the interval is descriptive). Within-cell only; cross-cell comparisons are descriptive (each cell selects its "
             "own states).\n")
    L.append("### Bank P divergent states (W93 admission; analyze_ghf/analyze_dev loaders)\n")
    L.append("| cell | family | states | QQ success | E[max(G,H,F,0)] = share some arm beats QQ [CP 95%] | action-only E[max(G,0)] | G>0 / H>0 / F>0 | beats QQ only via H/F | E[G] / E[H] / E[F] | digest = dev_all |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for k, v in mp.items():
        L.append(f"| {k} | {v['family']} | {v['n_states']} | {v['QQ_success']} | {v['n_some_arm_beats_QQ']} = {v['E_max_GHF0']:.3f} "
                 f"[{v['E_max_GHF0_ci95_CP'][0]:.3f}, {v['E_max_GHF0_ci95_CP'][1]:.3f}] | {v['E_max_G0 (action-only oracle share)']:.3f} | "
                 f"{v['n_G_pos']} / {v['n_H_pos']} / {v['n_F_pos']} | {v['n_beats_QQ_but_not_via_G']} | "
                 f"{v['E_G']:+.3f} / {v['E_H']:+.3f} / {v['E_F']:+.3f} | {v['units_digest_match_dev_all']} |")
    for name, ks in (("6 core cells (W4 + KV8)", core), ("W4 core (4 cells)", w4)):
        k_ = sum(mp[k]["n_some_arm_beats_QQ"] for k in ks)
        n_ = sum(mp[k]["n_states"] for k in ks)
        g_ = sum(mp[k]["n_G_pos"] for k in ks)
        L.append(f"\nPooled over {name} (state-weighted, descriptive): some arm beats QQ {k_}/{n_} = {k_ / n_:.3f} "
                 f"[{cp(k_, n_)[0]:.3f}, {cp(k_, n_)[1]:.3f}]; action-only {g_}/{n_} = {g_ / n_:.3f}.")
    L.append("\nStress cells (gptq_w3, kvq_int4_rot, rtn_w3; 3 blocks) are listed for completeness and are not pooled.\n")
    L.append("Winning arm sets when QQ fails (Bank P; keys = arms that succeed among BQ/QB/BB):\n")
    for k, v in mp.items():
        L.append(f"- {k}: {v['winning_arm_sets_when_QQ_fails']}")
    L.append("\n### Same diagnostic on the Bank U U1 f02/f03 rows (all four arms exist on Bank U)\n")
    L.append("| cell | rows | QQ success | some arm beats QQ [CP 95%] | action-only (G>0) | G>0 / H>0 / F>0 | beats QQ only via H/F |")
    L.append("|---|---|---|---|---|---|---|")
    for k, v in R["menu_oracle_bank_u_U1_f02f03"].items():
        L.append(f"| {k} | {v['n_states']} | {v['QQ_success']} | {v['n_some_arm_beats_QQ']} = {v['E_max_GHF0']:.3f} "
                 f"[{v['E_max_GHF0_ci95_CP'][0]:.3f}, {v['E_max_GHF0_ci95_CP'][1]:.3f}] | {v['n_G_pos']} | "
                 f"{v['n_G_pos']} / {v['n_H_pos']} / {v['n_F_pos']} | {v['n_beats_QQ_but_not_via_G']} |")
    L.append("\nBank U U1 rows are sampled ordinary states of Q's own trajectory (most have identical B/Q actions), so the "
             "denominator differs from Bank P's divergent states; the two banks are not compared numerically.\n")
    # 2
    L.append("## 2. KL reference row (post-hoc auxiliary baseline using BF16 information)\n")
    L.append("**Labels.** (i) Needs BF16: the score requires B's next-token distribution over Q's proposed action, i.e. a B forward "
             f"(prefill) pass of the prompt plus a_Q at every decision (here a mean of {kl['cost']['mean_prompt_tokens_U1_val']} prompt "
             f"tokens + {kl['cost']['mean_len_aQ_tokens_U1_val']} a_Q tokens per U1 validation decision), in addition to Q's decode; it is "
             "not a Q-only trigger and costs a BF16 prefill at every step, not only at escalated steps. (ii) Post-hoc: the f02/f03 "
             "outcomes were seen in W98 before this baseline was specified, so this is not a prospective validation. (iii) KL "
             "definition: " + kl["definition"] + ". (iv) Not a DMR reproduction (DMR trains a router; this is a fixed threshold on one "
             "divergence score).\n")
    L.append(f"**Fit (f01 U1 only, n = {kl['fit_f01']['n_f01_U1']}).** Candidates {', '.join(KL_CANDS)} (tie-break as the frozen rule). "
             "Per-cell thresholds = f01 quantiles at 5/10/20% (analyze_token_mech.thresholds); choice by the frozen rule's criterion "
             "(max mean over rates of in-sample net − random expectation; tie: turnover captured − random). In-sample f01:\n")
    L.append("| candidate | 5% sel / net / r / d / random | 10% | 20% |")
    L.append("|---|---|---|---|")
    for s_ in KL_CANDS:
        t = kl["fit_f01"]["f01_in_sample"][s_]
        L.append(f"| {s_}{' (chosen)' if s_ == ch else ''} | " + " | ".join(
            f"{t[str(r)]['n_escalated']} / {t[str(r)]['net_gain']:+d} / {t[str(r)]['rescued']} / {t[str(r)]['damaged']} / {t[str(r)]['random_expected_net']:+.2f}" for r in RATES) + " |")
    L.append("\n**Validation f02/f03 U1 (1020 rows), same table format as W98** (exact one-sided hypergeometric p of net ≥ observed under a "
             "matched-count per-cell random trigger; Holm over the 3 budgets):\n")
    L.append("| row | rate | selected | net vs random (p; Holm) | r/d | turnover vs random (p) |")
    L.append("|---|---|---|---|---|---|")
    for r in RATES:
        P = fr[str(r)]["pooled"]
        L.append(f"| frozen S_mm (Q-only; prospective) | {r:.0%} | {P['n_escalated']} | {P['net_gain']:+d} vs {P['random_expected_net']:+.2f} "
                 f"({P['p_net_ge_random']:.4f}; {holm([fr[str(x)]['pooled']['p_net_ge_random'] for x in RATES])[RATES.index(r)]:.4f}) | "
                 f"{P['rescued']}/{P['damaged']} | {P['turnover_captured']} vs {P['random_expected_turnover']:.2f} ({P['p_turnover_ge_random']:.4f}) |")
    for s_ in KL_CANDS:
        for r in RATES:
            P = kl["val_f02f03"][s_][str(r)]["pooled"]
            tag = "KL chosen on f01" if s_ == ch else "KL, not chosen"
            L.append(f"| {s_} ({tag}; BF16; post-hoc) | {r:.0%} | {P['n_escalated']} | {P['net_gain']:+d} vs {P['random_expected_net']:+.2f} "
                     f"({P['p_net_ge_random']:.4f}; {P['p_net_holm3']:.4f}) | {P['rescued']}/{P['damaged']} | "
                     f"{P['turnover_captured']} vs {P['random_expected_turnover']:.2f} ({P['p_turnover_ge_random']:.4f}) |")
    for r in RATES:
        P = kl["val_count_matched_to_frozen"][str(r)]["pooled"]
        L.append(f"| {ch} count-matched to frozen per cell (secondary; ranks on validation) | {r:.0%} | {P['n_escalated']} | "
                 f"{P['net_gain']:+d} vs {P['random_expected_net']:+.2f} ({P['p_net_ge_random']:.4f}; {P['p_net_holm3']:.4f}) | "
                 f"{P['rescued']}/{P['damaged']} | {P['turnover_captured']} vs {P['random_expected_turnover']:.2f} ({P['p_turnover_ge_random']:.4f}) |")
    L.append("\nThe frozen row's Holm column is computed here for side-by-side reading (the frozen rule fixed no multiplicity rule; W98a). "
             "The non-chosen KL candidates are shown so the choice can be audited; only the chosen row is the KL baseline. The "
             "count-matched row ranks validation rows by the KL score (no outcome use) to put the KL row on the frozen rule's exact "
             "per-cell budget.\n")
    L.append("KL per cell (chosen score; selected / r / d / net / random):\n")
    L.append("| cell | 5% | 10% | 20% |")
    L.append("|---|---|---|---|")
    for c in klv["0.05"]["per_cell"]:
        L.append(f"| {c} | " + " | ".join(
            f"{klv[str(r)]['per_cell'][c]['n_escalated']} / {klv[str(r)]['per_cell'][c]['rescued']} / {klv[str(r)]['per_cell'][c]['damaged']} / "
            f"{klv[str(r)]['per_cell'][c]['net_gain']:+d} / {klv[str(r)]['per_cell'][c]['random_expected_net']:+.2f}" for r in RATES) + " |")
    L.append("\n## Checks\n")
    for k, v in R["checks"].items():
        L.append(f"- {k}: {v}")
    L.append(f"- Bank P units digests equal to `{REF_DEV_ALL}`: "
             f"{sum(v['units_digest_match_dev_all'] for v in mp.values())}/{len(mp)} cells")
    L.append(f"\nInputs (sha256) in `oracle_trigger_{R['utc']}.json`.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
