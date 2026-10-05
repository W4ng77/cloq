"""Summaries and markdown for label_transfer.py (EXPLORATORY, POST HOC). Arrays (4 X [G, H, F, random], 3 budgets, D, 12): D = point +
B block + B crossed draws; columns per mode j: 4j net, 4j+1 rescue, 4j+2 damage, 4j+3 BF16-decision proxy per selected state.
Amendment 2026-10-05b: random-selection reference, excess over random, retained share, tie-aware R2, ratios only on same-draw."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

MODES, NAMES = ("G", "H", "F"), {"G": "action only (BQ)", "H": "continuation (QB)", "F": "both (BB)"}
TOL = 1e-9


def s(d, B, f=100.0):
    d = np.asarray(d, float) * f
    q = lambda x: [round(float(v), 2) for v in np.nanpercentile(x, [2.5, 97.5])] if np.isfinite(x).any() else None  # noqa: E731
    bl, cr = q(d[1:B + 1]), q(d[B + 1:])
    ex = lambda c: None if c is None else bool(c[0] > 0 or c[1] < 0)  # noqa: E731
    return {"est": None if not np.isfinite(d[0]) else round(float(d[0]), 2), "block": bl, "crossed": cr, "block_excl0": ex(bl), "crossed_excl0": ex(cr)}


def order(v):
    """Ordering with ties written as '=' (within TOL), e.g. 'G=F>H'."""
    ix = np.argsort(-v, kind="stable")
    return MODES[ix[0]] + "".join(("=" if abs(v[a] - v[c]) < TOL else ">") + MODES[c] for a, c in zip(ix, ix[1:]))


def ratio(num, den, B, f=100.0):
    """num/den where den > TOL, else NaN; also the share of bootstrap draws dropped (den <= TOL) per scheme."""
    r = s(np.where(den > TOL, num / np.where(den > TOL, den, 1), np.nan), B, f)
    return r | {"dropped_block": round(float((den[1:B + 1] <= TOL).mean()), 3), "dropped_crossed": round(float((den[B + 1:] <= TOL).mean()), 3)}


def mat(A, B, budgets, ratios=True):
    out = {}
    sh = lambda z: {"block": round(float(z[1:B + 1].mean()), 3), "crossed": round(float(z[B + 1:].mean()), 3)}  # noqa: E731
    for i, b in enumerate(budgets):
        orc = np.stack([A[y, i, :, 4 * y] for y in range(3)], 1)  # (D, 3)
        rnd = np.stack([A[3, i, :, 4 * y] for y in range(3)], 1)  # random selection, same capacity
        To = np.abs(orc - orc.max(1, keepdims=True)) < TOL
        m = {"oracle": {Y: s(orc[:, y], B) for y, Y in enumerate(MODES)}, "random": {Y: s(rnd[:, y], B) for y, Y in enumerate(MODES)},
             "oracle_top_tied": {"point": bool(To[0].sum() > 1), **sh(To.sum(1) > 1)}, "cells": {}, "R2": {}, "R3": {}}
        for x, X in enumerate(MODES):
            nets = A[x, i, :, 0::4]
            for y, Y in enumerate(MODES):
                loss = orc[:, y] - nets[:, y]
                c = {"net": s(nets[:, y], B), "rescue": s(A[x, i, :, 4 * y + 1], B), "damage": s(A[x, i, :, 4 * y + 2], B),
                     "bf16_dec_per_selected_proxy": s(A[x, i, :, 4 * y + 3], B, 1.0), "loss": s(loss, B), "excess_over_random": s(nets[:, y] - rnd[:, y], B)}
                if ratios:
                    c |= {"loss_pct_of_oracle": ratio(loss, orc[:, y], B), "retained_pct_vs_random": ratio(nets[:, y] - rnd[:, y], orc[:, y] - rnd[:, y], B)}
                m["cells"][f"{X}->{Y}"] = c
            Tx = np.abs(nets - nets.max(1, keepdims=True)) < TOL
            match = (Tx & To).sum(1) / Tx.sum(1)  # P(argmax under X, uniform among X's tied top modes, lies in the oracle's tied top set)
            m["R2"][X] = {"order_point": order(nets[0]), "oracle_order_point": order(orc[0]), "same_order_point": order(nets[0]) == order(orc[0]),
                          "share_argmax_in_oracle_top_block": round(float(match[1:B + 1].mean()), 3), "share_argmax_in_oracle_top_crossed": round(float(match[B + 1:].mean()), 3)}
            m["R3"][X] = {f"{MODES[p]}-{MODES[q]}": s(nets[:, p] - nets[:, q], B) for p, q in ((1, 0), (2, 0), (2, 1))}
        out[f"{round(100 * b)}%"] = m
    return out


def ci(x, k="crossed"):
    if x["est"] is None:
        return "n/a"
    iv = lambda q: f" [{x[q][0]:+.2f}, {x[q][1]:+.2f}]" if x.get(q) else " [n/a]"  # noqa: E731
    return f"{x['est']:+.2f}" + (f" blk{iv('block')} cr{iv('crossed')}" if k == "both" else iv(k))


def table(M, k):
    L = [f"| select by \\ execute | {' | '.join(f'{Y} ({NAMES[Y]})' for Y in MODES)} |", "|---|---|---|---|",
         f"| oracle (select by Y) | {' | '.join(ci(M['oracle'][Y], k) for Y in MODES)} |", f"| random (same capacity) | {' | '.join(ci(M['random'][Y], k) for Y in MODES)} |"]
    for X in MODES:
        row = []
        for Y in MODES:
            c = M["cells"][f"{X}->{Y}"]
            t = f"net {c['net']['est']:+.2f} (r {c['rescue']['est']:.2f}, d {c['damage']['est']:.2f})"
            if X != Y:
                t += f"; loss {ci(c['loss'], k)}; over random {ci(c['excess_over_random'], k)}"
                if "retained_pct_vs_random" in c:
                    rt, lp = c["retained_pct_vs_random"], c["loss_pct_of_oracle"]["est"]
                    t += f"; retained {ci(rt, k)}%" + (f", lost {lp:.0f}% of oracle" if lp is not None else "")
            row.append(t)
        L.append(f"| {X} | {' | '.join(row)} |")
    ot = M["oracle_top_tied"]
    L += ["", f"R2 ordering of executed net by selection label (ties within 1e-9 written '='; oracle top tied: point {ot['point']}, draws {ot['block']:.2f} block / {ot['crossed']:.2f} crossed): "
          + "; ".join(f"{X}: {r['order_point']} (oracle {r['oracle_order_point']}; argmax in oracle top set {r['share_argmax_in_oracle_top_block']:.2f} block / {r['share_argmax_in_oracle_top_crossed']:.2f} crossed)" for X, r in M["R2"].items())]
    L += ["R3 within-row differences: " + "; ".join(f"{X}: " + ", ".join(f"{d} {ci(v, k)}" for d, v in r.items()) for X, r in M["R3"].items()), ""]
    return L


def write(o, R, out: Path, secs):
    B, bud = o["B"], o["budgets"]
    for fr in R.values():
        fr["same_draw"] = {"meta": fr["same_draw"][1], "results": {c: mat(A, B, bud) for c, A in fr["same_draw"][0].items()}}
        fr["split_half"] = {"meta": fr["split_half"][1], "results": {d: {c: mat(A, B, bud, False) for c, A in r.items()} for d, r in fr["split_half"][0].items()}}
    o["frames"], o["seconds"] = R, round(secs)
    jp = out / f"label_transfer_{o['utc']}.json"
    jp.write_text(json.dumps(o, indent=1, default=float))
    sha = o["sources_sha256"]["analysis/fork/label_transfer.py"]
    L = [f"# Upgrade-label transfer matrix ({o['utc']})", "", f"**{o['label']}**", "",
         f"Protocol `docs/insights/LABEL_TRANSFER_POSTHOC.md`. Script `analysis/fork/label_transfer.py` sha256 {sha}; git HEAD {o['git_head']}; B = {B}; seed {o['seed']}. Full numbers: `{jp.relative_to(out.parents[2])}`.",
         "Values in pp of all states in the frame (rescue r, damage d, net = r - d of the EXECUTED mode). loss = oracle_Y - executed. Intervals 95% percentile; which scheme is shown is stated per table.",
         "Same-draw selection is hindsight (labels and outcomes share the QQ arm). The split-half variant is a same-task replication across blocks, not new-task prediction. Budgets count states, not BF16 compute.",
         "Same-draw losses are >= 0 by construction (the oracle maximises the weighted sum in every draw), so a same-draw loss interval excluding 0 is not evidence. Read 'over random' (executed minus random selection at the same capacity; can be negative) and 'retained' = (executed - random) / (oracle - random). Only the split-half loss can be negative.",
         "Saturation: an oracle whose label has fewer +1 states than the capacity in every pooled cell adds only tie-fill at higher budgets; such oracles are listed per table. Point estimates are pooled unit sums (equal to analyze_dev's mean of block means only when blocks have equal state counts, as in Bank U).", "",
         "## Frame counts", "", "| frame | cell | four-arm states | units | tasks | blocks | G+/G- | H+/H- | F+/F- |", "|---|---|---|---|---|---|---|---|---|"]
    L += [f"| {f} | {c} | {n['states_4arm']} | {n['units']} | {n['tasks']} | {','.join(n['blocks'][:3])}{'...' if len(n['blocks']) > 3 else ''} ({len(n['blocks'])}) | {n['nG+']}/{n['nG-']} | {n['nH+']}/{n['nH-']} | {n['nF+']}/{n['nF-']} |"
          for f, fr in R.items() for c, n in fr["counts"].items()]
    names = {"U1": "Bank U U1 (PRIMARY, ordinary own-trajectory states)", "P": "Bank P first-divergence states (SECONDARY)", "U2B": "Bank U U2B (SENSITIVITY, BF16-sourced states)"}
    shn = {"U1": names["U1"], "U2B": names["U2B"], "P": "Bank P dev_all units (SECONDARY; pp of all units, non-divergent units count 0)"}
    for f in ("U1", "P", "U2B"):
        k, kn = ("both", "block and crossed") if f == "P" else ("crossed", "crossed")
        cnt = R[f]["counts"]
        for p in ("pool W4", "pool KV8"):
            if p not in R[f]["same_draw"]["results"]:
                continue
            cs = [c for c in cnt if ("kvq" in c) == (p == "pool KV8")]
            for bk, M in R[f]["same_draw"]["results"][p].items():
                b = float(bk[:-1]) / 100
                sat = [Y for Y in MODES if all(cnt[c][f"n{Y}+"] <= b * cnt[c]["states_4arm"] for c in cs)]
                L += ["", f"## {names[f]}: {p}, same-draw (hindsight), budget {bk} ({kn} intervals)", ""] + table(M, k)
                L += [f"Saturated oracles at {bk} (all +1 states fit in every pooled cell): {', '.join(sat) or 'none'}.", ""]
        for bk, M in R[f]["split_half"]["results"]["mean of directions"].get("pool W4", {}).items():
            L += ["", f"## {shn[f]}: pool W4, split-half (mean of A->B and B->A), budget {bk} ({kn} intervals; ratios suppressed: noisy oracle)", ""] + table(M, k)
    L += ["", "## Per cell, same-draw, budget 10%: executed net (oracle on the diagonal) and BF16-decision proxy per selected state", "",
          "| frame | cell | G->G | G->H | G->F | H->G | H->H | H->F | F->G | F->H | F->F | proxy BF16 dec/selected (G, H, F; diag) |", "|---|---|" + "---|" * 10]
    for f, fr in R.items():
        for c, Mb in fr["same_draw"]["results"].items():
            M = Mb["10%"]["cells"]
            L.append(f"| {f} | {c} | " + " | ".join(f"{M[f'{X}->{Y}']['net']['est']:+.2f}" for X in MODES for Y in MODES) + " | " + ", ".join(str(M[f"{Y}->{Y}"]["bf16_dec_per_selected_proxy"]["est"]) for Y in MODES) + " |")
    L += ["", f"Inputs: {json.dumps(o['inputs'])}", "", "## Sources (sha256)", ""] + [f"- `{p}` {v}" for p, v in o["sources_sha256"].items()]
    (out / f"label_transfer_{o['utc']}.md").write_text("\n".join(L) + "\n")
    print(f"label_transfer: wrote {jp} and .md ({o['seconds']} s)")
