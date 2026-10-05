"""Markdown writer for trigger_ghf.py (EXPLORATORY, POST HOC). No em-dashes in output."""
from __future__ import annotations

MODES = ("G", "H", "F")
DESC = {"G": "G = Y_BQ - Y_QQ (replace current action; Q continues)", "H": "H = Y_QB - Y_QQ (Q action stands; B continues)",
        "F": "F = Y_BB - Y_QQ (replace action and continuation)"}


def iv(b, k):
    x = b[k]
    t, c = x["task"], x["crossed"]
    return f"{x['point']:+.2f} [{t[0]:+.2f}, {t[1]:+.2f}] [{c[0]:+.2f}, {c[1]:+.2f}]{' R' if x['resolved'] else ''}"


def frame_table(F, N, boot):
    L = ["| rate | sel (share; 4-arm) | mode | r / d / net (pp) | random net (count) | trig - rand (count) | exact p | oracle r / d / net | trig/oracle net |"
         + (" Holm(9) |" if boot else ""), "|---|---|---|---|---|---|---|---|---|" + ("---|" if boot else "")]
    for rk, e in F["rates"].items():
        for q in MODES:
            m = e["modes"][q]
            P, O = m["pooled"], m["oracle"]
            share = f"{P['net'] / O[f'net_{q}']:.2f}" if O[f"net_{q}"] else "n/a"
            L.append(f"| {float(rk):.0%} | {e['selected']} ({100 * e['selected_share']:.1f}%; {e['selected_four_arm']}) | {q} | {P['r']} / {P['d']} / {P['net']:+d} "
                     f"({100 * P['net'] / N:+.2f}) | {P['rand']:+.2f} | {P['net'] - P['rand']:+.2f} | {m['exact_p']} | "
                     f"{O[f'r_{q}']:.0f} / {O[f'd_{q}']:.0f} / {O[f'net_{q}']:+.0f} | {share} |" + (f" {m['holm9']} |" if boot else ""))
    return L


def markdown(R):
    L = [f"# Frozen trigger read under G / H / F ({R['utc']})", "",
         "**EXPLORATORY, POST HOC.** These Bank U outcomes were seen before (W88, W98, oracle_trigger). Selections are the "
         "frozen S_mm rule's, unchanged. Hindsight oracles are not policies. Not a deployable router. Budgets are state-selection "
         "budgets, not equal BF16 compute (H and F run B for the rest of the episode).", "",
         f"Protocol `{R['protocol']}`. Script `{R['script']}` sha256 `{R['script_sha256']}`; core `{R['core_sha256'][:16]}...`; "
         f"report `{R['report_sha256'][:16]}...`; analyze_token_mech `{R['analyze_token_mech_sha256'][:16]}...`; rule `{R['rule_sha256'][:16]}...`; "
         f"git HEAD `{R['git_head']}`; B = {R['B']}; seed = {R['seed']}. W98 primary reproduced: {R['checks']['w98_primary_reproduced']}.", "",
         "Labels: " + "; ".join(DESC[q] for q in MODES) + ". Rescue = +1, damage = -1. pp = per 100 rows of the frame.", ""]
    for name, F in R["frames"].items():
        cov, N = F["coverage"], F["coverage"]["rows"]
        boot = "boot" in next(iter(F["rates"].values()))
        L += [f"## {name}", "", f"Coverage: {cov['rows']} rows; all four arms on {cov['four_arm']}; "
              f"G/H/F computable on {cov['has_G']}/{cov['has_H']}/{cov['has_F']}.", ""]
        L += frame_table(F, N, boot)
        L.append("")
        L.append("Oracle = per-cell top-m_c rows by that mode's label (m_c = trigger's count), uniform tie-break, exact expectation. "
                 "Random = matched-count expectation. Budgets are the frozen f01 thresholds, so the realised share differs from the "
                 "nominal rate (column 2). Cost proxy = n_decisions - t with t 0-indexed, i.e. Q decisions from the state onward, "
                 "counting the current one. Exact p: one-sided hypergeometric, trig net >= observed.")
        L.append("")
        L += ["| rate | some arm beats QQ: trig vs random | forced best-mode sum | mean remaining decisions (cost proxy) |",
              "|---|---|---|---|"]
        for rk, e in F["rates"].items():
            P = e["modes"]["G"]["pooled"]
            ra = ""
            if boot:
                b = e["boot"]["adj_pp_any"]
                ra = f" (adj pp {b['point']:+.2f}; task [{b['task'][0]:+.2f}, {b['task'][1]:+.2f}], crossed [{b['crossed'][0]:+.2f}, {b['crossed'][1]:+.2f}])"
            L.append(f"| {float(rk):.0%} | {P['any_pos']}{ra} | {e['best_mode_forced_sum']:+d} | {e['cost_proxy_mean_remaining_decisions']} |")
        L.append("")
        if boot:
            L += ["Bootstrap (pp of frame rows; point [task-cluster 95%] [crossed task x block 95%]; R = both exclude 0):", "",
                  "| rate | trig - rand G | trig - rand H | trig - rand F | net H - G | net F - G | net F - H | adj H - G | adj F - G |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for rk, e in F["rates"].items():
                b = e["boot"]
                L.append(f"| {float(rk):.0%} | " + " | ".join(iv(b, k) for k in ("adj_pp_G", "adj_pp_H", "adj_pp_F", "net_pp_H-G", "net_pp_F-G",
                                                                              "net_pp_F-H", "adj_pp_H-G", "adj_pp_F-G")) + " |")
            L.append("")
            L += ["Oracle cross-read: hindsight, no interval, trigger-allocated budget (per-cell m_c), NOT the label-transfer "
                  "matrix (Analysis 1); do not cite as Analysis 1 evidence. Oracle chosen on row mode; expected r / d / net in "
                  "each column mode under uniform ties. Beyond R_X rows of the chosen mode the set is tie-filled from label-0 "
                  "rows; H and F share the B continuation, so their overlap is partly mechanical. Last row per rate = matched-"
                  "count random expectation (net, count).", "",
                  "| rate | oracle on | G r / d / net | H r / d / net | F r / d / net |", "|---|---|---|---|---|"]
            for rk, e in F["rates"].items():
                for q in MODES:
                    O = e["modes"][q]["oracle"]
                    L.append(f"| {float(rk):.0%} | {q} | " + " | ".join(f"{O[f'r_{x}']:.2f} / {O[f'd_{x}']:.2f} / {O[f'net_{x}']:+.2f}" for x in MODES) + " |")
                L.append(f"| {float(rk):.0%} | random | " + " | ".join(f"net {e['modes'][x]['pooled']['rand']:+.2f}" for x in MODES) + " |")
            L.append("")
            L += ["Per cell, trigger r/d/net by mode (G | H | F):", "", "| rate | cell | m | G | H | F |", "|---|---|---|---|---|---|"]
            for rk, e in F["rates"].items():
                for c in e["modes"]["G"]["per_cell"]:
                    cs = [e["modes"][q]["per_cell"][c] for q in MODES]
                    L.append(f"| {float(rk):.0%} | {c} | {cs[0]['m']} | " + " | ".join(f"{x['r']}/{x['d']}/{x['net']:+d} (rand {x['rand']:+.2f})" for x in cs) + " |")
            L.append("")
    return "\n".join(L) + "\n"
