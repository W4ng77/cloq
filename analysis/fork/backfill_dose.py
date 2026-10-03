"""Appendix backfill part 2 (W100x): residual error dose W_a = W + a(W_Q - W) (PERTURBATION_PROTOCOL.md §2.2): success,
turnover to BF16 and action agreement with BF16 per a, adjacent steps paired on joint units."""
from __future__ import annotations

from backfill_common import ALPHAS, CELL_BLOCKS, CELLS, admitted_arms, boot_for, cell_units, complete, first_act_div, fmt, stat, summ

def dose(fz: dict, rule: str) -> dict:
    res = {"cells": {}, "incomplete": []}
    built = {}
    for model, cell in CELLS:
        adm = admitted_arms(fz, model, cell)
        alist = [a for a in ALPHAS[cell] if complete(adm, f"resid_a{a:g}", cell)]
        for a in ALPHAS[cell]:
            if a not in alist:
                res["incomplete"].append({"cell": f"{model}:{cell}", "arm": f"resid_a{a:g}", "admitted": adm.get(f"resid_a{a:g}", [])})
        if not alist:
            continue
        units, info = cell_units(fz, model, cell, [f"resid_a{a:g}" for a in alist], rule)
        built[(model, cell)] = (alist, units, info)
    fams = {"q": {k: v[1] for k, v in built.items() if CELL_BLOCKS[k[1]][0].startswith("q")},
            "f": {k: v[1] for k, v in built.items() if CELL_BLOCKS[k[1]][0].startswith("f")}}
    boots = {f: boot_for(us) for f, us in fams.items() if us}
    for (model, cell), (alist, us, info) in built.items():
        boot = boots["q" if CELL_BLOCKS[cell][0].startswith("q") else "f"]
        names = {0.0: "B"} | {a: f"resid_a{a:g}" for a in alist} | {1.0: "Q"}
        order = sorted(names)
        act = [u for u in us if all(u["ep"][names[a]]["sig"] is not None for a in order) and len(u["ep"]["B"]["sig"]) > 0]

        def div(u, a):
            return int(first_act_div(u["ep"][names[a]]["sig"], u["ep"]["B"]["sig"]) is not None)

        def prefix(u, a):
            k = first_act_div(u["ep"][names[a]]["sig"], u["ep"]["B"]["sig"])
            nb = len(u["ep"]["B"]["sig"])
            return 1.0 if k is None else k / nb

        per = {}
        for a in order:
            n = names[a]
            per[f"{a:g}"] = {"success": summ(stat(boot, us, lambda u, n=n: u["ep"][n]["Y"])),
                             "turnover_to_B": summ(stat(boot, us, lambda u, n=n: int(u["ep"][n]["Y"] != u["ep"]["B"]["Y"]))),
                             "action_div": summ(stat(boot, act, lambda u, a=a: div(u, a))),
                             "action_prefix": summ(stat(boot, act, lambda u, a=a: prefix(u, a)), pct=False)}
        steps = {}
        for a0, a1 in zip(order, order[1:]):
            n0, n1 = names[a0], names[a1]
            steps[f"{a0:g}->{a1:g}"] = {
                "success": summ(stat(boot, us, lambda u, n0=n0, n1=n1: u["ep"][n1]["Y"] - u["ep"][n0]["Y"])),
                "action_prefix": summ(stat(boot, act, lambda u, a0=a0, a1=a1: prefix(u, a1) - prefix(u, a0)), pct=False)}
        res["cells"][f"{model}:{cell}"] = {"alphas": [f"{a:g}" for a in order], "n_units": len(us), "n_units_action": len(act),
                                           "n_tasks": len({u["task"] for u in us}), "blocks": sorted({u["block"] for u in us}),
                                           "skipped": info["skipped"], "per_alpha": per, "steps": steps}
    return res


def render_dose(res: dict) -> list[str]:
    D = res["dose"]
    L = []
    L += ["", "## 2. Residual error dose W_a = W + a(W_Q - W)", "",
          "a = 0 is BF16 and a = 1 is Q (bit for bit by construction). Joint units: every finished a of the cell, Q and BF16 have a data "
          "episode. Action metrics use units where all episodes have messages (an overflow episode has none): div = P(action sequence "
          "differs from BF16's), prefix = first differing decision / BF16 decisions (1 = identical). turnover = P(outcome != BF16).", ""]
    for cell, c in D["cells"].items():
        L += [f"**{cell}** ({c['n_units']} units, {c['n_tasks']} tasks, blocks {', '.join(c['blocks'])}; action metrics on {c['n_units_action']} units)", "",
              "| a | success | turnover to BF16 | action div | action prefix |", "|---|---|---|---|---|"]
        for a in c["alphas"]:
            p = c["per_alpha"][a]
            L.append(f"| {a} | {fmt(p['success'], sign=False)} | {fmt(p['turnover_to_B'], sign=False)} | {fmt(p['action_div'], sign=False)} | "
                     f"{fmt(p['action_prefix'], dec=3, sign=False)} |")
        L += ["", "| step | success change | action prefix change |", "|---|---|---|"]
        for k, v in c["steps"].items():
            L.append(f"| {k} | {fmt(v['success'])} | {fmt(v['action_prefix'], dec=3)} |")
        if c["skipped"]:
            L.append("")
            L.append("Skipped: " + "; ".join(c["skipped"][:12]))
        L.append("")
    L += ["Not finished (no a = 2 or other arm in this cell): " + ("; ".join(f"{i['cell']} {i['arm']} (admitted {i['admitted'] or 'none'})" for i in D["incomplete"]) or "none"), "",
          "**Sensitivity, every infrastructure episode missing (success by a):**", ""]
    for cell, v in res["dose_sens_allinfra"].items():
        L.append(f"- {cell}: " + ", ".join(f"a={a} {s['est']:.1f}" for a, s in v.items()))
    return L
