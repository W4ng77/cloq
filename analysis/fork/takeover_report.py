"""Takeover-window tw-v1 estimands and reporting, imported by analyze_takeover.py (docs/insights/TAKEOVER_WINDOW_PROTOCOL.md §7, §9, §11).
build: per-state values and masks; cell_stats: all-state and reference-policy subsets (analyze_dev.Boot: t over blocks primary, block and
crossed bootstrap alongside); transitions, handback (disjoint buckets, BF16 / Q tokens), reading (mechanical §9 / §11.3 wording); analyse."""
from __future__ import annotations
import importlib.util, json, re
from collections import Counter
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
_sp = importlib.util.spec_from_file_location("analyze_newmethod", ROOT / "analysis/fork/analyze_newmethod.py")
NM = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(NM)
AD = NM.AD
CELLS, XS, LS, WL = ("gptq_w4_d1", "spinquant_w4a4"), ("B", "Q"), ("0", "1", "4", "inf"), ("1", "4")
EP = {"BQ": ("B", "0"), "BB": ("B", "inf"), "QQ": ("Q", "0"), "QB": ("Q", "inf")}
SENS = ("V_Q4", "R_Q4", "V_Q1", "R_Q1", "V_B4", "R_B4", "D1", "D4")
BANNED = re.compile(r"suffice|are enough|is ineffective|only sustained takeover helps|no difference", re.I)
LABEL = ("EXPLORATORY follow-up diagnostic (configurations chosen after seeing results). States are U2B: states a BF16 agent reaches, not the "
         "states Q visits. Temporal-response diagnostic of precision value, not a routing method (DMR, arXiv 2602.02711).")
N_STATES = 85  # states per (cell, block), §3 / §8
sub = lambda a, b: None if a is None or b is None else a - b  # noqa: E731

def branches(d: Path, sk: str) -> dict:
    p = NM.no_holdout(d) / "branches" / f"{sk}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def build(ep: dict, w: dict | None, ep_ok: bool, use_quarantined: bool = False) -> dict:
    """Unit: the 8 values, masks (quarantine: x curve at every L and Delta at that L; endpoint acceptance: L = 0 / inf) and estimands E."""
    Y = {EP[a]: (ep.get("Y") or {}).get(a) for a in EP} if "excluded" not in ep else {}
    W = (w or {}).get("windows") or {}
    Y.update({(x, L): (W.get(x + L) or {}).get("Y") for x in XS for L in WL})
    q = {(x, L) for x in XS for L in WL if (W.get(x + L) or {}).get("quarantine") and not use_quarantined}
    u = {"task": ep["task"], "block": ep["block"], "state_key": ep["state_key"], "exact": bool(ep.get("exact")), "Y": Y, "quarantined": sorted(q), "ep_ok": ep_ok,
         "complete": all(Y.get((x, L)) in (0, 1) for x in XS for L in LS), "Eflag": {x + L: (W.get(x + L) or {}).get("E") for x in XS for L in WL},
         "prefix_bad": any((v.get("prefix") or {}).get("ok") is False for v in W.values())}
    epm = lambda L: not ep_ok and L in ("0", "inf")  # noqa: E731
    E = {f"D{L}": None if epm(L) or ("B", L) in q or ("Q", L) in q else sub(Y.get(("B", L)), Y.get(("Q", L))) for L in LS}
    for L in WL:
        E[f"DD{L}_0"], E[f"DD{L}_inf"] = sub(E[f"D{L}"], E["D0"]), sub(E[f"D{L}"], E["Dinf"])
    for x in XS:
        y = {L: None if epm(L) or any(k[0] == x for k in q) else Y.get((x, L)) for L in LS}
        E.update({f"Y_{x}{L}": y[L] for L in LS})
        E.update({f"V_{x}{L}": sub(y[L], y["0"]) for L in ("1", "4", "inf")})
        E.update({f"R_{x}{L}": sub(y[L], y["inf"]) for L in ("0", "1", "4")})
        E.update({f"d41_{x}": sub(y["4"], y["1"]), f"Vinf-V4_{x}": sub(y["inf"], y["4"]), f"Vinf-V1_{x}": sub(y["inf"], y["1"]), f"V4-V1_{x}": sub(y["4"], y["1"])})
        for L in ("1", "4", "inf"):
            ok = None not in (y[L], y["0"])
            E[f"rescue_{x}{L}"], E[f"damage_{x}{L}"] = (int(y["0"] == 0 and y[L] == 1), int(y["0"] == 1 and y[L] == 0)) if ok else (None, None)
        for L in WL:  # short-window-only change (Y_{x,L} != Y_{x,0} while Y_{x,inf} = Y_{x,0}), signed and unsigned; E = 0 contribution (§7)
            so = None if None in (y[L], y["0"], y["inf"]) else (y[L] - y["0"]) * int(y["inf"] == y["0"])
            ef = u["Eflag"][x + L]
            E.update({f"SO_{x}{L}": so, f"SOabs_{x}{L}": None if so is None else abs(so),
                      f"E0contrib_V_{x}{L}": None if E[f"V_{x}{L}"] is None or ef is None else E[f"V_{x}{L}"] * (1 - int(ef))})
    return {**u, "E": E}


def st(units: list, boot, key: str, mask=None, ratio: bool = False) -> dict | None:
    us = [u for u in units if (mask is None or mask(u)) and u["E"].get(key) is not None]
    if not us:
        return None
    pt, dr = (boot.ratio if ratio else boot.task_mean)(*boot.arrays(us, key))
    return {**AD.summarise(pt, dr, boot=boot), "n": len(us)}


def ef(*names):
    return lambda u: all(u["Eflag"].get(n) is True for n in names)


def cell_stats(units: list, B: int, keys=None) -> dict:
    boot, K = NM.boot_for(units, B), keys or list(units[0]["E"])
    r = {"n_states": len(units), "blocks": sorted({u["block"] for u in units}), "all_states_pp": {k: st(units, boot, k) for k in K}}
    if keys:
        return r
    S = r["subsets_pp"] = {}
    for x in XS:  # fixed composition E_{x,4} = 1 for the whole x curve (§11.2 registers x = Q; x = B alongside)
        S[f"E_{x}4 curve"] = {k: st(units, boot, k, ef(x + "4")) for k in K if k.endswith(f"_{x}") or re.match(rf"[\w]+_{x}(0|1|4|inf)$", k)}
        for L in WL:  # §7: each V / R within its own E_{x,L} = 1, with the E share
            S[f"E_{x}{L}"] = {k: st(units, boot, k, ef(x + L)) for k in (f"V_{x}{L}", f"R_{x}{L}", f"Y_{x}{L}")}
            S[f"E_{x}{L}"]["E_share"] = float(np.mean([u["Eflag"][x + L] is True for u in units]))
    for L in WL:
        S[f"E_B{L}&E_Q{L}"] = {k: st(units, boot, k, ef("B" + L, "Q" + L)) for k in (f"D{L}", f"DD{L}_0", f"DD{L}_inf")}
    S["E_B4&E_Q4 Delta curve"] = {f"D{L}": st(units, boot, f"D{L}", ef("B4", "Q4")) for L in LS}
    r["nonexact_pp"] = {f"D{L}": st(units, boot, f"D{L}", lambda u: not u["exact"], ratio=True) for L in LS}
    return r


def transitions(units: list) -> dict:
    out, tag = {}, lambda u: f"{u['task'].replace('|', ':')}@{u['block']}"  # noqa: E731
    for x in XS:
        v = lambda u, L: u["E"][f"Y_{x}{L}"]  # noqa: E731
        full = [u for u in units if all(v(u, L) is not None for L in LS)]
        o = out[x] = {"n": len(full), "patterns_Y0_Y1_Y4_Yinf": dict(Counter("".join(str(v(u, L)) for L in LS) for u in full))}
        for name, d in (("rescue_inf", 1), ("damage_inf", -1)):
            ch = [u for u in full if v(u, "inf") - v(u, "0") == d]
            o[name] = {f"L{L}": {"kept": [tag(u) for u in ch if v(u, L) == v(u, "inf")], "undone": [tag(u) for u in ch if v(u, L) == v(u, "0")]} for L in WL}
        o["short_window_only"] = {f"L{L}": [f"{tag(u)} {v(u, '0')}->{v(u, L)}" for u in full if v(u, L) != v(u, "0") and v(u, "inf") == v(u, "0")] for L in WL}
    return out


def tokens(rec: dict, xl: str) -> dict:
    """BF16 / Q prefill and generated tokens of one window suffix (the first n_B generated decisions are B's: pattern_ok, §5.5)."""
    cont = [c for c in (branches(rec["_dir"], rec["state_key"]).get(f"W_{xl}") or {}).get("decisions") or [] if not c.get("forced")]
    nb, f = rec["windows"][xl].get("n_B") or 0, lambda ds, k: sum(c.get(k) or 0 for c in ds)
    return {"B_prefill": f(cont[:nb], "n_prompt_tokens"), "B_gen": f(cont[:nb], "n_completion_tokens"), "Q_prefill": f(cont[nb:], "n_prompt_tokens"), "Q_gen": f(cont[nb:], "n_completion_tokens")}


def handback(recs: list) -> dict:
    """Disjoint buckets, overflow first (§11.2): attempted handback, generation failed / other overflow / error / handed back / ended inside window."""
    out = {}
    for x in XS:
        for L in WL:
            vs = [(r, r["windows"].get(x + L) or {}) for r in recs]
            b = Counter("attempted handback, generation failed" if v.get("overflow") == "attempted_handback_generation_failed" else f"overflow ({v['overflow']})" if v.get("overflow")
                        else "error (missing)" if v.get("Y") is None else "handed back" if v.get("handed_back") else "ended inside window" for _, v in vs)
            tk = [tokens(r, x + L) for r, v in vs if v.get("Y") is not None]
            out[x + L] = {"n": len(vs), "buckets": dict(b), "n_B": dict(Counter(str(v.get("n_B")) for _, v in vs)), "E_share": float(np.mean([v.get("E") is True for _, v in vs])) if vs else None,
                          "n_E_handback_mismatch": sum(1 for _, v in vs if None not in (v.get("E"), v.get("handed_back")) and v["E"] != v["handed_back"]
                                                           and v.get("overflow") != "attempted_handback_generation_failed"),  # as the driver (§11.2)
                          "quarantine": dict(Counter(v["quarantine"]["diagnosis"] for _, v in vs if v.get("quarantine"))), "a6_Y0": sum(1 for _, v in vs if v.get("a6")),
                          "tokens_mean": {k: float(np.mean([t[k] for t in tk])) for k in tk[0]} if tk else None}
        out[x + "inf"] = {"BF16_decisions (ref_n_gen of the L = inf endpoint)": dict(Counter(str((r["windows"].get(x + "4") or {}).get("ref_n_gen")) for r in recs)),
                          "tokens": "not in window rows (reused endpoint)"}
    return out


def why(s: dict | None) -> str | None:
    """Amendment 3: a resolved wording needs a t interval over >= 2 block means (n_blocks) of nonzero width; else the reason."""
    if not s:
        return "no data"
    if s.get("t_ci95") is None or (s.get("n_blocks") or 0) < 2:
        return "data in fewer than 2 blocks, no t interval"
    return "zero-width interval (zero between-block variance)" if s["ci95"][0] >= s["ci95"][1] else None


resolvable = lambda s: bool(s) and why(s) is None  # noqa: E731


def reading(c: str, R: dict) -> list[str]:
    """Mechanical §9 / §11.3 wording; each line carries its primary interval. Banned phrasings are asserted absent."""
    iv = lambda s: f"[{s['ci95'][0]:+.1f}, {s['ci95'][1]:+.1f}] pp (est {s['est']:+.1f}, n={s['n']}, {s['primary']})"  # noqa: E731
    pos, neg = (lambda s: resolvable(s) and s["ci95"][0] > 0), (lambda s: resolvable(s) and s["ci95"][1] < 0)
    out, A = [], R["all_states_pp"]
    for lab, S in (("all states", A), ("E_Q4=1 subset (reference policy, continuous BF16, generated >4 decisions)", R["subsets_pp"]["E_Q4 curve"])):
        for L in WL:
            V, Rr, G, n = S.get(f"V_Q{L}"), S.get(f"R_Q{L}"), S.get(f"Vinf-V{L}_Q"), ("four" if L == "4" else "one")
            if not resolvable(V):  # Amendment 3: no wording from a one-block or zero-width interval
                out.append(f"{c} {lab} L={L}: V_Q{L} not estimable ({why(V)})")
            elif pos(V):
                out.append(f"{c} {lab} L={L}: V_Q{L} > 0, interval {iv(V)}" + (f": a short-takeover gain that survives handback to Q (§9 answer 1), E_Q4 = 1 share {R['subsets_pp']['E_Q4']['E_share']:.3f}" if lab[0] == "E" and L == "4"
                           else ": not by itself §9 answer 1 (E = 0 states add V_Qinf mechanically, §7)" if lab[0] == "a" else ""))
            elif neg(V):
                out.append(f"{c} {lab} L={L}: V_Q{L} < 0 (net loss after handback), interval {iv(V)}")
            elif pos(G):  # §11.3: the only permitted wording here
                out.append(f"{c} {lab} L={L}: continuous takeover beats {n}-step takeover; the {n}-step net gain is unresolved. V_Q{L} {iv(V)}; V_Qinf - V_Q{L} {iv(G)}")
            else:
                out.append(f"{c} {lab} L={L}: V_Q{L} not resolved at this n, interval {iv(V)}")
            if not resolvable(Rr):
                out.append(f"{c} {lab} L={L}: R_Q{L} not estimable ({why(Rr)})")
            elif not (pos(Rr) or neg(Rr)):
                out.append(f"{c} {lab} L={L}: not distinguishable from sustained takeover at this n, R_Q{L} interval {iv(Rr)} (no equivalence margin registered)")
            elif not (pos(G) and not pos(V) and not neg(V)):
                out.append(f"{c} {lab} L={L}: R_Q{L} {'>' if pos(Rr) else '<'} 0, interval {iv(Rr)}")
    for x in XS:  # §9 answer 3: longer is not monotone
        out += [f"{c} x={x}: {k} not estimable ({why(A[k])}), no answer 3 reading" for k in (f"Vinf-V4_{x}", f"Vinf-V1_{x}", f"V4-V1_{x}") + tuple(f"SO_{x}{L}" for L in WL) if A.get(k) and why(A[k])]
        out += [f"{c} x={x}: longer is not monotone, {k} < 0, interval {iv(A[k])}" for k in (f"Vinf-V4_{x}", f"Vinf-V1_{x}", f"V4-V1_{x}") if neg(A.get(k))]
        out += [f"{c} x={x}: short-window-only changes at L={L} that are absent at inf, SO_{x}{L} interval {iv(A[f'SO_{x}{L}'])}" for L in WL
                if pos(A.get(f"SO_{x}{L}")) or neg(A.get(f"SO_{x}{L}"))]
    assert not any(BANNED.search(s) for s in out), out
    return out


def analyse(per_cell: dict, B: int) -> dict:
    """per_cell[c] = (units, window records). Strict blocks: all N_STATES states present, each with all 8 values (a quarantined value counts)."""
    res = {"label": LABEL, "cells": {}}
    for c, (units, recs) in per_cell.items():
        okb = {b for b in {u["block"] for u in units} if all(u["complete"] for u in units if u["block"] == b)
               and len({u["state_key"] for u in units if u["block"] == b}) == N_STATES}  # §8: all 85 states (Amendment 3)
        prim, cc = [u for u in units if u["block"] in okb], [u for u in units if u["complete"]]
        r = res["cells"][c] = {"strict_blocks": sorted(okb), "blocks_dropped": sorted({u["block"] for u in units} - okb), "primary": cell_stats(prim, B) if prim else None,
                               "complete_case": cell_stats(cc, B, SENS) if cc else None, "transitions": transitions(prim), "handback": handback([w for w in recs if w["block"] in okb])}
        qi = [build(u["_ep"], u["_w"], u["ep_ok"], True) for u in prim]
        r["sensitivity_quarantine_included"] = cell_stats(qi, B, SENS) if qi else None
        r["sensitivity_no_prefix_mismatch"] = cell_stats(npm, B, SENS) if (npm := [u for u in prim if not u["prefix_bad"]]) else None
        r["reading"] = reading(c, r["primary"]) if prim else [f"{c}: no strict block admitted, not estimable"]
    if all(c in per_cell for c in CELLS):  # cross-cell, paired by state (SpinQuant - GPTQ), common strict blocks
        a, b = [{u["state_key"]: u for u in per_cell[c][0] if u["block"] in res["cells"][c]["strict_blocks"]} for c in CELLS]
        pairs = [{"task": u["task"], "block": u["block"], "E": {k: sub(b[s]["E"][k], u["E"][k]) for k in SENS + ("V_Qinf", "D0", "Dinf")}} for s, u in a.items() if s in b]
        res["spinquant_minus_gptq_pp"] = cell_stats(pairs, B, list(pairs[0]["E"])) if pairs else None
    return res
