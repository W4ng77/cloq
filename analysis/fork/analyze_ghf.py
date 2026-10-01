"""2x2 fork (GPT-6.1 review 6): G/H/F with paired within-cell differences, the 3x3 (Delta_Q, Delta_B) table, all 16
outcome patterns, frozen-rule case studies, and the model x config x benchmark coverage matrix (W93).

Notation. First index = action at the first divergence, second = controller from the next step on; all four arms
(BB, BQ, QB, QQ) start from the same frozen state.
  G = Y_BQ - Y_QQ  (replace only the current action)        Delta_Q = Y_BQ - Y_QQ = G   (action effect, Q continues)
  H = Y_QB - Y_QQ  (replace only the continuation)          Delta_B = Y_BB - Y_QB = A   (action effect, B continues)
  F = Y_BB - Y_QQ  (replace both)                           I = Delta_Q - Delta_B (interaction)
  Paired within-cell differences: G - H = Y_BQ - Y_QB;  F - G = Y_BB - Y_BQ (= C);  F - H = Y_BB - Y_QB (= Delta_B = A).
Admission is exactly analyze_dev's (imported, not copied): split guard (--split dev; telecom holdout refused and its fork
directories are never opened here), snapshot gate, quarantine, dedupe, strict complete-block rule (W70), complete 85-task
retail/airline panel blocks only (W78). The per-cell units digest is checked against the reference dev_all output.
Denominator: each cell's observed divergent states (ratio of block sums, analyze_dev.Boot.ratio).
Intervals: primary = fixed task pool (block bootstrap with >= 10 complete blocks, else t over per-block ratios);
secondary = crossed task x block bootstrap (generalisation to new tasks); reported in separate columns. B = 2000,
seed 20261001. Pools: equal weight per cell over the complete blocks common to every pooled cell (W4 = gptq_w4_d1 +
awq_w4, KV8 = kvq_int8; per model and across models). Stress cells (gptq_w3, kvq_int4_rot, rtn_w3) are reported per cell
and flagged not poolable (one common complete block).
Identification. Everything inside a cell compares four arms of the same frozen states: identified (paired). Any comparison
across cells (q4 vs q8, W4 vs KV8, AWQ vs GPTQ) compares different sets of divergent states (each cell selects its own
first-divergence states), so it is descriptive and confounded by state selection.
Case studies: frozen rule (see CASE_RULE) over re-checked units only (QQ no-op replay passed on that state, Q replay of
the pivot passed, every branch prefix_ok and env_hash_init_ok).
Coverage: run status files (counts only), the loaded fork units, Bank U summaries, external-fork summaries; telecom
holdout fork directories are listed by name only (never opened).

usage: python analysis/fork/analyze_ghf.py [--snapshot <snapshot.json>] [--reference <dev_all json>] [--B 2000]
-> analysis/fork/out/ghf_<UTC>.{json,md}, analysis/fork/out/fig_ghf_<cell|pooled>_<UTC>.png
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
DEF_SNAPSHOT = "analysis/insights/iter_3/out/snapshot_auto_20261001T0600Z.json"
DEF_REFERENCE = "analysis/fork/out/dev_all_20261001T070326Z.json"
# Fork roots read here. analysis/fork/holdout (telecom holdout) is deliberately NOT read.
FORK_ROOTS = ["analysis/fork/dev", "analysis/fork/kv", "analysis/fork/stress", "analysis/fork/telecom", "analysis/fork/repair"]
PANEL = ("retail", "airline")
MAIN_FAMILIES = ("W4", "KV8")
VALS = (-1, 0, 1)
PATTERNS = [f"{i:04b}" for i in range(16)]  # bit order BB, BQ, QB, QQ
CASE_RULE = ("eligible: divergent, admitted retail/airline panel units of the main cells (W4: gptq_w4_d1, awq_w4; KV8: "
             "kvq_int8; q4 and q8) whose state passed the QQ no-op replay (QQ branch present and analyze_dev.noop_ok), "
             "whose Q pivot replay passed (q_replay all true) and whose three B-involving branches have prefix_ok and "
             "env_hash_init_ok. Order: sha256('ghf-case-v1:' + state_id) ascending. Categories in this order: rescue "
             "(BQ=1, QQ=0), damage (BQ=0, QQ=1), controller-dependent (Delta_Q != Delta_B); take the first 2 per "
             "category, skipping a state already chosen and a (domain, task) already chosen.")
READ_PREFIX = ("get_", "find_", "list_", "search_", "calculate", "think")


def discover() -> list[Path]:
    out = []
    for r in FORK_ROOTS:
        for p in sorted(glob.glob(str(ROOT / r / "**" / "search.json"), recursive=True)):
            d = Path(p).parent
            if (d / "states").is_dir() and (d / "branches").is_dir():
                assert "/holdout/" not in str(d)
                out.append(d)
    return out


def add_E(u: dict) -> None:
    Y = u["Y"]
    E = u["E"]
    dq, db = Y["BQ"] - Y["QQ"], Y["BB"] - Y["QB"]
    E.update({"GmH": Y["BQ"] - Y["QB"], "FmG": Y["BB"] - Y["BQ"], "FmH": Y["BB"] - Y["QB"], "dQ": dq, "dB": db,
              "offdiag": int(dq != db), "diag": int(dq == db), "Ipos": int(E["I"] > 0), "Ineg": int(E["I"] < 0),
              "Iabs2": int(abs(E["I"]) == 2)})
    for a in VALS:
        for b in VALS:
            E[f"c_{a}_{b}"] = int(dq == a and db == b)


COND = ["G", "H", "F", "GmH", "FmG", "FmH", "I", "offdiag", "diag", "strict_reversal", "Ipos", "Ineg", "Iabs2"]


def cell_stats(div: list[dict], boot) -> dict:
    out = {}
    for s in COND:
        pt, dr = boot.ratio(*boot.arrays(div, s))
        out[s] = AD.summarise(pt, dr)
    return out


def table3(div: list[dict]) -> dict:
    n = len(div)
    cnt = {f"{a},{b}": sum(u["E"][f"c_{a}_{b}"] for u in div) for a in VALS for b in VALS}
    return {"n": n, "counts": cnt, "shares": {k: (v / n if n else None) for k, v in cnt.items()},
            "diagonal_n": sum(cnt[f"{a},{a}"] for a in VALS), "offdiag_n": n - sum(cnt[f"{a},{a}"] for a in VALS),
            "strict_reversal_n": cnt["1,-1"] + cnt["-1,1"],
            "I_dist": {str(v): sum(1 for u in div if u["E"]["I"] == v) for v in (-2, -1, 0, 1, 2)}}


def patterns16(div: list[dict]) -> dict:
    n = len(div)
    c = {p: sum(1 for u in div if u["E"]["pattern"] == p) for p in PATTERNS}
    return {"n": n, "counts": c, "shares": {p: (v / n if n else None) for p, v in c.items()}}


def pool(cells_units: dict, keys: list[str], B: int) -> dict:
    """Equal-weight pool over cells on the complete blocks common to all of them (as analyze_dev)."""
    per = {lab: {(u["domain"], u["block"]) for u in us} for lab, us in cells_units.items()}
    common = set.intersection(*per.values())
    nblk = len({b for _, b in common})
    if nblk < 2:
        return {"not_poolable": f"{nblk} common complete block(s) across {sorted(cells_units)}"}
    sub = {lab: [u for u in us if (u["domain"], u["block"]) in common] for lab, us in cells_units.items()}
    allu = [u for us in sub.values() for u in us]
    bo = defaultdict(set)
    for u in allu:
        bo[u["task"]].add(u["block"])
    boot = AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=B)
    res = {"cells": sorted(sub), "common_blocks": sorted({b for _, b in common}), "k_blocks": nblk,
           "n_tasks": len(bo), "n_states_per_cell": {lab: sum(1 for u in us if u["div"]) for lab, us in sub.items()}}
    st = {}
    for s in keys:
        vals = []
        for lab, us in sub.items():
            div = [u for u in us if u["div"]]
            pt, dr = boot.ratio(*boot.arrays(div, s))
            vals.append((pt, np.asarray(dr), dr.block_means, dr.crossed, dr.crossed_pt))
        pt = float(np.mean([v[0] for v in vals]))
        t = AD.t_interval(np.nanmean(np.vstack([v[2] for v in vals]), axis=0))
        crossed = (float(np.mean([v[4] for v in vals])), np.mean([v[3] for v in vals], axis=0))
        st[s] = AD.summarise(pt, np.mean([v[1] for v in vals], axis=0), t=t, crossed=crossed)
    res["stats"] = st
    divs = {lab: [u for u in us if u["div"]] for lab, us in sub.items()}
    t3 = {lab: table3(d) for lab, d in divs.items()}
    res["table3_counts_summed"] = {k: sum(t3[l]["counts"][k] for l in t3) for k in t3[next(iter(t3))]["counts"]}
    res["table3_shares_equal_weight"] = {k: float(np.mean([t3[l]["shares"][k] for l in t3])) for k in res["table3_counts_summed"]}
    res["n_states_summed"] = sum(len(d) for d in divs.values())
    return res


# ---------------------------------------------------------------------------- case studies
def _msg(m) -> dict:
    return m if isinstance(m, dict) else {}


def action_text(a) -> str:
    m = _msg((a or {}).get("message"))
    tc = m.get("tool_calls") or []
    if tc:
        return "; ".join(f"{c.get('name')}({json.dumps(c.get('arguments'), separators=(',', ':'))})" for c in tc)
    return "TEXT: " + (m.get("content") or "").replace("\n", " ")


def trunc(s: str, n: int = 200) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def branch_events(br: dict, domain: str, max_ev: int = 9) -> dict:
    suf = br.get("suffix") or []
    ev, n_tool, n_err, writes, n_talk, n_user = [], 0, 0, [], 0, 0
    pending = {}
    for m in suf:
        role = m.get("role")
        if role == "assistant":
            tcs = m.get("tool_calls") or []
            if tcs:
                for c in tcs:
                    n_tool += 1
                    nm = c.get("name")
                    pending[c.get("id")] = len(ev)
                    kind = "transfer" if nm.startswith("transfer_to_human") else "call" if nm.startswith(READ_PREFIX) else "write"
                    ev.append({"kind": kind, "text": f"{nm}({trunc(json.dumps(c.get('arguments'), separators=(',', ':')), 70)})", "ok": None})
            else:
                n_talk += 1
        elif role == "tool":
            i = pending.get(m.get("id"))
            err = bool(m.get("error")) or str(m.get("content", "")).startswith("Error")
            if i is not None:
                ev[i]["ok"] = not err
                if err:
                    ev[i]["err"] = trunc(m.get("content"), 70)
            n_err += err
        elif role == "user":
            n_user += 1
    for e in ev:
        if e["kind"] == "write":
            writes.append(e["text"].split("(")[0] + ("" if e["ok"] else " [ERROR]"))
    lines = []
    for e in ev:
        tag = {"write": "WRITE ", "transfer": "TRANSFER "}.get(e["kind"], "")
        st = "ok" if e["ok"] else ("ERROR: " + e.get("err", "")) if e["ok"] is False else "no result"
        lines.append(f"{tag}{e['text']} -> {st}")
    if len(lines) > max_ev:
        lines = lines[: max_ev - 1] + [f"… (+{len(lines) - max_ev + 1} more tool events)", lines[-1]]
    return {"n_tool_calls": n_tool, "n_tool_errors": n_err, "writes": writes, "n_agent_text_turns": n_talk,
            "transfers": sum(e["kind"] == "transfer" for e in ev), "n_user_turns": n_user, "termination": br.get("termination_reason"),
            "steps_final": br.get("step_count_final"), "db_match": br.get("db_match"), "success": AD.success(domain, br),
            "events": lines}


def pick_cases(units: list[dict], snap: dict) -> dict:
    elig = []
    for u in units:
        if not u["div"] or AD.family(u["cell"]) not in MAIN_FAMILIES or u["domain"] not in PANEL:
            continue
        d = ROOT / u["dir"]
        bp = d / "branches" / f"{u['state_id']}.json"
        if not bp.exists():
            continue
        r4 = json.load(open(bp))
        if "QQ" not in r4:
            continue
        st = json.load(open(d / "states" / f"{u['state_id']}.json"))
        ok, _ = AD.noop_ok(st, r4["QQ"])
        if not ok or not all((st.get("q_replay") or {}).values()):
            continue
        if not all(r4[b].get("prefix_ok") and r4[b].get("env_hash_init_ok") for b in ("BB", "BQ", "QB")):
            continue
        elig.append((hashlib.sha256(f"ghf-case-v1:{u['state_id']}".encode()).hexdigest(), u, st, r4))
    elig.sort(key=lambda x: x[0])
    cats = [("rescue", lambda E: E["G"] == 1), ("damage", lambda E: E["G"] == -1), ("controller_dependent", lambda E: E["dQ"] != E["dB"])]
    chosen, seen_s, seen_t = [], set(), set()
    n_elig = {c: sum(1 for _, u, _, _ in elig if f(u["E"])) for c, f in cats}
    for cat, f in cats:
        k = 0
        for h, u, st, r4 in elig:
            if k == 2:
                break
            if not f(u["E"]) or u["state_id"] in seen_s or (u["domain"], u["task"]) in seen_t:
                continue
            seen_s.add(u["state_id"])
            seen_t.add((u["domain"], u["task"]))
            k += 1
            instr = ((st.get("task") or {}).get("user_scenario") or {}).get("instructions") or {}
            reason = instr.get("reason_for_call") if isinstance(instr, dict) else str(instr)
            chosen.append({"category": cat, "hash": h[:16], "model": u["model"], "cell": u["cell"], "block": u["block"],
                           "domain": u["domain"], "task": u["task"], "state_id": u["state_id"], "dir": u["dir"],
                           "decision_idx": u["t"], "n_decisions_orig": st.get("n_decisions_orig"),
                           "divergence_type": u["type"], "reason_for_call": trunc(reason or "", 220),
                           "Y": u["Y"], "pattern": u["E"]["pattern"], "dQ": u["E"]["dQ"], "dB": u["E"]["dB"],
                           "a_Q": trunc(action_text(st.get("a_Q")), 220), "a_B": trunc(action_text(st.get("a_B")), 220),
                           "branches": {b: branch_events(r4[b], u["domain"]) for b in ("BB", "BQ", "QB", "QQ")},
                           "files": {"state": f"{u['dir']}/states/{u['state_id']}.json", "branches": f"{u['dir']}/branches/{u['state_id']}.json"}})
    return {"rule": CASE_RULE, "n_eligible": len(elig), "n_eligible_by_category": n_elig, "cases": chosen}


# ---------------------------------------------------------------------------- coverage
RUN_ANY = re.compile(r"^a6k2_(q\d+|l8|m24)_(.+?)(?:_(q\d+|f\d\d|n\d+|h\d+))?$")  # block suffix optional (single-run cells)
REF_PREFIX = ("bf16", "bfpair", "null", "gauss", "rot_bf16")


def coverage(units_all: list[dict]) -> dict:
    cov = defaultdict(lambda: defaultdict(dict))  # (model, cfg) -> bench -> info

    def norm(cfg):
        return "awq_w4" if cfg == "awq_w4_d1" else cfg
    # end-to-end tau2 runs (status.json counts only)
    for rd in sorted((ROOT / "runs").glob("a6k2_*")):
        m = RUN_ANY.match(rd.name)
        if not m:
            continue
        model, cell, block = m.groups()
        block = block or "single"
        tel = cell.startswith("tel_")
        cell = cell[4:] if tel else cell
        for sp in rd.glob("*/status.json"):
            dom = sp.parent.name
            try:
                s = json.load(open(sp))
            except Exception:
                continue
            e = cov[(model, cell)][dom].setdefault("e2e", {"blocks_completed": 0, "blocks_other": 0, "max_n_tasks": 0, "block_ids": []})
            if s.get("status") == "completed":
                e["blocks_completed"] += 1
                e["block_ids"].append(block)
                e["max_n_tasks"] = max(e["max_n_tasks"], int(s.get("n_simulations") or s.get("n_tasks") or 0))
            else:
                e["blocks_other"] += 1
    # end-to-end external runs
    for rd in sorted((ROOT / "runs").glob("ext_*_eval")):
        m = re.match(r"^ext_(q\d+|q30a3|l8)_(.+)_(alfworld|bfcl)_eval$", rd.name)
        if not m:
            continue
        model, cfg, bench = m.groups()
        n = 0
        ok = True
        for sp in rd.glob("*/status.json"):
            s = json.load(open(sp))
            ok &= s.get("status") == "completed"
            n += int(s.get("n_simulations") or 0)
        cov[(model, norm(cfg))][bench]["e2e"] = {"blocks_completed": int(ok), "blocks_other": int(not ok), "max_n_tasks": n, "block_ids": ["eval"]}
    # 4-branch dev forks (tau2), admitted units
    g = defaultdict(list)
    for u in units_all:
        g[(u["model"], u["cell"], u["domain"])].append(u)
    for (m, c, d), us in g.items():
        ok = [u for u in us if "excluded" not in u]
        cov[(m, c)][d]["fork4"] = {"units_found": len(us), "units_analysed": len(ok), "tasks": len({u["task"] for u in ok}),
                                   "divergent_states": sum(1 for u in ok if u["div"]), "complete_blocks": len({u["block"] for u in ok}),
                                   "blocks_found": len({u["block"] for u in us})}
    # external forks (summaries)
    for sp in sorted((ROOT / "analysis/fork/ext/dev").glob("*/dev_summary.json")):
        m = re.match(r"^(alfworld|bfcl)_(q\d+)_(.+?)_(all|base|long_context|miss_func|miss_param)$", sp.parent.name)
        if not m:
            continue
        bench, model, cfg, cat = m.groups()
        s = json.load(open(sp))
        e = cov[(model, norm(cfg))][bench].setdefault("fork4", {"items": 0, "divergent_states": 0, "valid_states": 0, "categories": [], "complete_blocks": 1})
        e["items"] += int(s.get("n_items") or 0)
        e["divergent_states"] += int(s.get("n_states") or 0)
        e["valid_states"] += int(s.get("n_valid") or 0)
        e["categories"].append(cat)
    # Bank U
    for sp in sorted((ROOT / "analysis/fork/bank_u").glob("q*_*/f*/bank_summary.json")):
        mc = sp.parent.parent.name
        model, cell = mc.split("_", 1)
        s = json.load(open(sp))
        rows = [json.loads(x) for x in open(sp.parent / "bank_rows.jsonl")]
        for dom in sorted({r["domain"] for r in rows}):
            e = cov[(model, cell)][dom].setdefault("bank_u", {"blocks": [], "rows_ok": 0, "tasks": set(), "gate_pass": []})
            e["blocks"].append(sp.parent.name)
            e["rows_ok"] += sum(1 for r in rows if r["domain"] == dom and r.get("Y"))
            e["tasks"] |= {r["task_id"] for r in rows if r["domain"] == dom}
            e["gate_pass"].append(s.get("gate_pass"))
    # telecom holdout: directory names only, never opened
    for d in sorted((ROOT / "analysis/fork/holdout").glob("*")):
        if d.is_dir():
            model, cell = d.name.split("_", 1)
            cov[(model, cell)]["telecom"]["holdout"] = {"fork_task_dirs": len([x for x in d.iterdir() if x.is_dir()]),
                                                        "note": "telecom holdout fork directories exist; contents not read (split guard, prereg frozen W87)"}
    out = {}
    for (m, c), bd in sorted(cov.items()):
        row = {}
        for b in ("retail", "airline", "telecom", "alfworld", "bfcl"):
            info = dict(bd.get(b, {}))
            if "bank_u" in info:
                info["bank_u"] = {**info["bank_u"], "tasks": len(info["bank_u"]["tasks"])}
            if "e2e" in info and info["e2e"]["blocks_completed"] == 0:
                info["e2e_status"] = "started, not completed"
            levels = [k for k in ("holdout", "bank_u", "fork4") if k in info]
            info["status"] = ("+".join(levels) if levels else ("end-to-end only" if info.get("e2e", {}).get("blocks_completed") else
                              "end-to-end incomplete" if "e2e" in info else "not run"))
            row[b] = info
        out[f"{m}:{c}"] = {"model": m, "config": c, "kind": "reference/perturbation" if c.startswith(REF_PREFIX) else "quantization", "benchmarks": row}
    return out


def cov_cell(info: dict) -> str:
    if info["status"] == "not run":
        return "–"
    parts = []
    e = info.get("e2e")
    if e:
        parts.append(f"E2E {e['blocks_completed']}b×{e['max_n_tasks']}t" if e["blocks_completed"] else "E2E incomplete")
    f = info.get("fork4")
    if f:
        if "items" in f:
            parts.append(f"**F4** {f['items']} items·{f['valid_states']} st·1b")
        else:
            parts.append(f"**F4** {f['tasks']}t·{f['divergent_states']} st·{f['complete_blocks']}/{f['blocks_found']}b")
    u = info.get("bank_u")
    if u:
        parts.append(f"**U** {len(u['blocks'])}b·{u['rows_ok']} rows·{u['tasks']}t")
    if info.get("holdout"):
        parts.append(f"**HOLDOUT** {info['holdout']['fork_task_dirs']} dirs (unread)")
    return "; ".join(parts)


# ---------------------------------------------------------------------------- figure
def heat(ax, counts: dict, shares: dict, title: str):
    import matplotlib.colors as mcolors
    M = np.array([[shares[f"{a},{b}"] or 0 for b in VALS] for a in VALS])
    cmap = mcolors.LinearSegmentedColormap.from_list("seq", ["#f4f7fb", "#9ec3e6", "#2b6cb0", "#0b2f5b"])
    ax.imshow(M, cmap=cmap, norm=mcolors.PowerNorm(0.45, vmin=0, vmax=1))
    for i, a in enumerate(VALS):
        for j, b in enumerate(VALS):
            v = M[i, j]
            col = "white" if v > 0.18 else "#1a1a1a"
            ax.text(j, i, f"{counts[f'{a},{b}']}\n{100 * v:.1f}%", ha="center", va="center", fontsize=8.5, color=col)
            if a == b:
                ax.add_patch(__import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle((j - .5, i - .5), 1, 1, fill=False, ec="#333333", lw=1.6))
            if a * b == -1:
                ax.text(j + .42, i - .38, "R", ha="right", va="top", fontsize=7, color=col, fontweight="bold")
    ax.set_xticks(range(3), ["−1", "0", "+1"])
    ax.set_yticks(range(3), ["−1", "0", "+1"])
    ax.set_xlabel("Δ_B = Y_BB − Y_QB  (B continues)", fontsize=8)
    ax.set_ylabel("Δ_Q = Y_BQ − Y_QQ  (Q continues)", fontsize=8)
    ax.set_title(title, fontsize=9)
    ax.tick_params(length=0, labelsize=8)
    for s in ax.spines.values():
        s.set_visible(False)


CAPTION = ("Boxed = diagonal (same action effect under both controllers); R = strict reversal (opposite signs); "
           "colour = share of divergent states (power scale γ = 0.45).")


def figures(res: dict, utc: str) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    paths = []
    for lab, c in res["cells"].items():
        if AD.family(lab.split(":")[1]) not in MAIN_FAMILIES:
            continue
        t = c["table3"]
        fig, ax = plt.subplots(figsize=(3.6, 3.6), dpi=160)
        o = c["stats"]["offdiag"]
        heat(ax, t["counts"], t["shares"], f"{lab}  (n = {t['n']} states)\noff-diagonal {o['est']:.1f}% [{o['ci95'][0]:.1f}, {o['ci95'][1]:.1f}]")
        fig.text(0.5, 0.005, CAPTION, ha="center", va="bottom", fontsize=5.2, wrap=True)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        p = OUT / f"fig_ghf_{lab.replace(':', '_')}_{utc}.png"
        fig.savefig(p)
        plt.close(fig)
        paths.append(str(p.relative_to(ROOT)))
    pls = [k for k in ("W4:q4", "W4:q8", "W4:all", "KV8:q4", "KV8:q8", "KV8:all") if "stats" in res["pools"].get(k, {})]
    fig, axs = plt.subplots(2, 3, figsize=(10.5, 8.2), dpi=160)
    for ax, k in zip(axs.flat, pls):
        p = res["pools"][k]
        o = p["stats"]["offdiag"]
        heat(ax, p["table3_counts_summed"], p["table3_shares_equal_weight"],
             f"{k} pool ({len(p['cells'])} cell(s), {p['k_blocks']} blocks, {p['n_states_summed']} states)\n"
             f"off-diagonal {o['est']:.1f}% [{o['ci95'][0]:.1f}, {o['ci95'][1]:.1f}]")
    for ax in list(axs.flat)[len(pls):]:
        ax.axis("off")
    fig.text(0.5, 0.005, "Counts summed over cells; shares equal weight per cell.\n" + CAPTION, ha="center", va="bottom", fontsize=7.5)
    fig.tight_layout(rect=(0, 0.04, 1, 1), h_pad=2.5)
    p = OUT / f"fig_ghf_pooled_{utc}.png"
    fig.savefig(p)
    plt.close(fig)
    paths.append(str(p.relative_to(ROOT)))
    return paths


# ---------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", default=DEF_SNAPSHOT)
    ap.add_argument("--reference", default=DEF_REFERENCE, help="dev_all JSON whose per-cell units digests must match")
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    a = ap.parse_args()
    t0 = time.time()
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    snap = json.load(open(ROOT / a.snapshot))
    loaded = [AD.load_dir(d, snap, {}) for d in discover()]
    allu = [u for L in loaded for u in L["units"]]
    split_info = AD.split_guard(allu, "dev", "analyze_ghf")
    for L in loaded:
        if L["quarantined"]:
            for u in L["units"]:
                u.setdefault("excluded", "quarantined fork task (QQ no-op mismatch)")
    units, _ = AD.dedupe_units(allu)
    AD.mark_incomplete_blocks(units, "dev", strict=True)
    AD.mark_partial_panel_blocks(units, "dev")
    ok = [u for u in units if "excluded" not in u]
    for u in ok:
        u["E"] = AD.effects(u["Y"], u["div"])
        if u["div"]:
            add_E(u)
    ref = json.load(open(ROOT / a.reference))
    cells = sorted({(u["model"], u["cell"]) for u in ok if u["domain"] in PANEL})
    res = {"cells": {}, "pools": {}}
    digest_check = {}
    cu_by = {}
    for m, c in cells:
        lab = f"{m}:{c}"
        cu = [u for u in ok if (u["model"], u["cell"]) == (m, c) and u["domain"] in PANEL]
        cu_by[lab] = cu
        dg = AD.units_digest(cu)
        rd = (ref["cells"].get(lab) or {}).get("units_digest_sha256")
        digest_check[lab] = {"match": dg == rd, "digest": dg[:16], "reference": (rd or "")[:16]}
        div = [u for u in cu if u["div"]]
        bo = defaultdict(set)
        for u in cu:
            bo[u["task"]].add(u["block"])
        boot = AD.Boot(sorted(bo), {t: sorted(v) for t, v in bo.items()}, B=a.B)
        st = cell_stats(div, boot)
        refG = ((ref["cells"].get(lab) or {}).get("conditional_on_divergence_pp") or {}).get("G", {}).get("est")
        res["cells"][lab] = {"family": AD.family(c), "n_units": len(cu), "n_tasks": len(bo), "n_blocks": len({u["block"] for u in cu}),
                             "n_states": len(div), "stats": st, "table3": table3(div), "patterns16": patterns16(div),
                             "check_G_vs_reference": {"G": st["G"]["est"], "reference_G": refG}}
        for u in div:
            E = u["E"]
            assert E["GmH"] == E["G"] - E["H"] and E["FmG"] == E["F"] - E["G"] == E["C"] and E["FmH"] == E["F"] - E["H"] == E["A"]
            assert E["I"] == E["dQ"] - E["dB"] and E["strict_reversal"] == int(E["dQ"] * E["dB"] < 0)
    bad = {k: v for k, v in digest_check.items() if not v["match"]}
    if bad:
        print(f"analyze_ghf: WARNING units digest differs from reference for {sorted(bad)}")
    keys = ["G", "H", "F", "GmH", "FmG", "FmH", "I", "offdiag", "strict_reversal", "Ipos", "Ineg"]
    for fam in ("W4", "KV8", "stress"):
        for mm in ("q4", "q8", "all"):
            labs = [l for l in cu_by if AD.family(l.split(":")[1]) == fam and (mm == "all" or l.startswith(mm + ":"))]
            if labs:
                res["pools"][f"{fam}:{mm}"] = pool({l: cu_by[l] for l in labs}, keys, a.B)
                if fam == "stress":
                    res["pools"][f"{fam}:{mm}"]["flag"] = "stress cells are never pooled (fewer than 2 common complete blocks); per-cell only"
    res["cases"] = pick_cases(ok, snap)
    res["coverage"] = coverage([u for u in units if not str(u.get("excluded", "")).startswith("not in split")])
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    res["figures"] = figures(res, utc)
    git = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    meta = {"script": "analysis/fork/analyze_ghf.py", "script_sha256": AD.sha256(__file__), "analyze_dev_sha256": AD.sha256(AD.__file__),
            "git_head": git, "utc": utc, "snapshot": {"path": a.snapshot, "id": snap.get("snapshot_id"), "sha256": AD.sha256(ROOT / a.snapshot)},
            "reference": a.reference, "units_digest_check": digest_check, "split": split_info, "fork_roots": FORK_ROOTS,
            "quarantined_dirs": [L["dir"] for L in loaded if L["quarantined"]],
            "inference": {"primary": "fixed task pool: block bootstrap over complete shared blocks if >= 10 blocks, else t over per-block ratios",
                          "secondary": "crossed task x block bootstrap (new-task generalisation)", "B": a.B, "seed": AD.SEED,
                          "denominator": "each cell's observed divergent states (ratio of block sums)",
                          "pools": "equal weight per cell over common complete blocks"},
            "identification": {"within_cell": "identified: four arms of the same frozen states (paired)",
                               "cross_cell": "descriptive: different cells select different divergent states; confounded by state selection"},
            "notation": {"G": "Y_BQ - Y_QQ", "H": "Y_QB - Y_QQ", "F": "Y_BB - Y_QQ", "Delta_Q": "Y_BQ - Y_QQ (= G)",
                         "Delta_B": "Y_BB - Y_QB (= A)", "I": "Delta_Q - Delta_B", "G-H": "Y_BQ - Y_QB", "F-G": "Y_BB - Y_BQ (= C)",
                         "F-H": "Y_BB - Y_QB (= Delta_B)", "offdiag": "Delta_Q != Delta_B (= I != 0)",
                         "strict_reversal": "Delta_Q * Delta_B < 0 (patterns 0110, 1001)"}}
    out = {**meta, **res, "seconds": round(time.time() - t0, 1)}
    jp = OUT / f"ghf_{utc}.json"
    jp.write_text(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else sorted(o) if isinstance(o, set) else str(o)))
    (OUT / f"ghf_{utc}.md").write_text(markdown(out, jp))
    print(f"analyze_ghf: wrote {jp.relative_to(ROOT)} and .md, figures {res['figures']} ({out['seconds']} s)")


def markdown(r: dict, jp: Path) -> str:
    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"

    def cx(x):
        return f"[{x['crossed_ci95'][0]:+.1f}, {x['crossed_ci95'][1]:+.1f}]" if "crossed_ci95" in x else "n/a"

    def sh(x):
        return f"{x['est']:.1f} [{x['ci95'][0]:.1f}, {x['ci95'][1]:.1f}]"
    C, P = r["cells"], r["pools"]
    main = [k for k in C if C[k]["family"] in MAIN_FAMILIES]
    def odr(lab):
        t = C[lab]["table3"] if lab in C else None
        return t
    wp, kp = P.get("W4:all", {}).get("stats"), P.get("KV8:all", {}).get("stats")
    tl = "; ".join(f"{k}: G {C[k]['stats']['G']['est']:+.1f}, H {C[k]['stats']['H']['est']:+.1f}, F {C[k]['stats']['F']['est']:+.1f}, "
                   f"G−H {C[k]['stats']['GmH']['est']:+.1f}, off-diag {C[k]['stats']['offdiag']['est']:.0f}%, reversal {C[k]['stats']['strict_reversal']['est']:.1f}%"
                   for k in C)
    offs = [C[k]["stats"]["offdiag"]["est"] for k in main]
    revshare = [C[k]["table3"]["strict_reversal_n"] / max(1, C[k]["table3"]["offdiag_n"]) for k in main]
    L = [f"**TL;DR** 2×2 fork on each cell's divergent states (pp; within-cell contrasts are identified, cross-cell comparisons are "
         f"descriptive). {tl}. In the W4/KV8 cells the action effect depends on the continuation controller (Δ_Q ≠ Δ_B, off-diagonal) "
         f"in {min(offs):.0f}–{max(offs):.0f}% of divergent states (pool W4 {wp['offdiag']['est']:.1f}% [{wp['offdiag']['ci95'][0]:.1f}, "
         f"{wp['offdiag']['ci95'][1]:.1f}], KV8 {kp['offdiag']['est']:.1f}% [{kp['offdiag']['ci95'][0]:.1f}, {kp['offdiag']['ci95'][1]:.1f}]), "
         f"yet the mean interaction I is near zero (pool W4 {wp['I']['est']:+.1f}, KV8 {kp['I']['est']:+.1f} pp) because I > 0 and I < 0 states "
         f"are about equally frequent; strict sign reversals are {min(revshare) * 100:.0f}–{max(revshare) * 100:.0f}% of the off-diagonal mass "
         f"(1–4% of states), the rest is 'effect under one controller, none under the other'.", "",
         f"# 2×2 fork: G / H / F, the (Δ_Q, Δ_B) table, 16 patterns, cases, coverage ({r['utc']})", "",
         f"Script `{r['script']}` (sha {r['script_sha256'][:12]}, analyze_dev sha {r['analyze_dev_sha256'][:12]}), git {r['git_head'][:10]}, "
         f"snapshot `{r['snapshot']['id']}` (sha {r['snapshot']['sha256'][:12]}). Full numbers: `{jp.relative_to(ROOT)}`.",
         f"Admission = analyze_dev (strict complete blocks, complete 85-task retail/airline panel blocks, split guard dev; telecom holdout "
         f"directories not opened). Units digest equals the reference `{r['reference']}` for "
         f"{sum(v['match'] for v in r['units_digest_check'].values())}/{len(r['units_digest_check'])} cells"
         f"{'' if all(v['match'] for v in r['units_digest_check'].values()) else ' (MISMATCH: ' + str([k for k, v in r['units_digest_check'].items() if not v['match']]) + ')'}.", "",
         "Notation: first index = action at the first divergence, second = controller afterwards. G = Y_BQ − Y_QQ (action only), "
         "H = Y_QB − Y_QQ (continuation only), F = Y_BB − Y_QQ (both). Δ_Q = Y_BQ − Y_QQ (= G), Δ_B = Y_BB − Y_QB; I = Δ_Q − Δ_B. "
         "Paired differences: G − H = Y_BQ − Y_QB; F − G = Y_BB − Y_BQ (= C); F − H = Y_BB − Y_QB (= Δ_B).", "",
         "**What is identified.** Within a cell all four arms start from the same frozen states, so G, H, F, their differences, and the "
         "(Δ_Q, Δ_B) table are paired, identified contrasts for that cell's divergent-state population. Comparisons across cells "
         "(q4 vs q8, AWQ vs GPTQ, W4 vs KV8, main vs stress) compare different state populations (each cell selects its own first "
         "divergences): descriptive only, confounded by state selection. Pools are equal-weight averages of within-cell estimates.", "",
         "Intervals: *fixed pool* = primary (block bootstrap over ≥ 10 complete blocks, else t over per-block ratios; stress cells have 3 "
         "blocks); *new tasks* = crossed task × block bootstrap. They answer different questions and are kept in separate columns.", "",
         "## 1. G, H, F and paired within-cell differences (per cell, on its divergent states; pp)", "",
         "| cell | states (tasks × blocks) | G | H | F | G − H | F − G | F − H |", "|---|---|---|---|---|---|---|---|"]
    for k, c in C.items():
        s = c["stats"]
        L.append(f"| {k}{' (stress)' if c['family'] == 'stress' else ''} | {c['n_states']} ({c['n_tasks']} × {c['n_blocks']}) | "
                 + " | ".join(f(s[x]) for x in ("G", "H", "F", "GmH", "FmG", "FmH")) + " |")
    L += ["", "New-task generalisation (crossed task × block) intervals for the same estimates:", "",
          "| cell | G | H | F | G − H | F − G | F − H |", "|---|---|---|---|---|---|---|"]
    for k, c in C.items():
        s = c["stats"]
        L.append(f"| {k} | " + " | ".join(cx(s[x]) for x in ("G", "H", "F", "GmH", "FmG", "FmH")) + " |")
    L += ["", "Pools (equal weight per cell, common complete blocks; fixed-pool interval, then crossed):", "",
          "| pool | cells | blocks | G | H | F | G − H | F − G | F − H |", "|---|---|---|---|---|---|---|---|---|"]
    for k, p in P.items():
        if "stats" not in p:
            L.append(f"| {k} | not poolable: {p['not_poolable']} | | | | | | | |")
            continue
        s = p["stats"]
        L.append(f"| {k} | {', '.join(p['cells'])} | {p['k_blocks']} | " + " | ".join(f"{f(s[x])}<br>{cx(s[x])}" for x in ("G", "H", "F", "GmH", "FmG", "FmH")) + " |")
    L += ["", "## 2. The 3 × 3 table of (Δ_Q, Δ_B)", "",
          "Rows Δ_Q = Y_BQ − Y_QQ (the action effect when Q continues), columns Δ_B = Y_BB − Y_QB (the same action swap when B "
          "continues). Diagonal = same effect under both controllers; off-diagonal = controller-dependent (= I ≠ 0); strict reversal = "
          "opposite-sign corners (+1, −1) and (−1, +1).", "",
          "| cell | n | (−1,−1) | (−1,0) | (−1,+1) | (0,−1) | (0,0) | (0,+1) | (+1,−1) | (+1,0) | (+1,+1) | diagonal % | off-diagonal % (fixed pool) | off-diag crossed | strict reversal % | P(I>0) | P(I<0) | mean I |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    order = [f"{a},{b}" for a in VALS for b in VALS]
    for k, c in C.items():
        t, s = c["table3"], c["stats"]
        L.append(f"| {k}{' (stress, not poolable)' if c['family'] == 'stress' else ''} | {t['n']} | " + " | ".join(str(t["counts"][o]) for o in order)
                 + f" | {100 - s['offdiag']['est']:.1f} | {sh(s['offdiag'])} | {cx(s['offdiag'])} | {sh(s['strict_reversal'])} | "
                 f"{s['Ipos']['est']:.1f} | {s['Ineg']['est']:.1f} | {f(s['I'])} |")
    for k, p in P.items():
        if "stats" not in p:
            continue
        s, cs = p["stats"], p["table3_counts_summed"]
        L.append(f"| pool {k} (equal weight) | {p['n_states_summed']} | " + " | ".join(str(cs[o]) for o in order)
                 + f" | {100 - s['offdiag']['est']:.1f} | {sh(s['offdiag'])} | {cx(s['offdiag'])} | {sh(s['strict_reversal'])} | "
                 f"{s['Ipos']['est']:.1f} | {s['Ineg']['est']:.1f} | {f(s['I'])} |")
    L += ["", "Stress pools (" + ", ".join(k for k, p in P.items() if "stats" not in p) + ") are not poolable (one common complete "
          "block); stress cells are reported per cell only, with t intervals over 3 blocks.", ""]
    ex = C.get("q8:gptq_w4_d1") or next(iter(C.values()))
    exs = ex["stats"]
    L += ["", "**Why a near-zero mean I coexists with a large off-diagonal share.** I = Δ_Q − Δ_B ∈ {−2, …, +2}, and its mean is "
          "E[I] = P(I = +1) + 2P(I = +2) − P(I = −1) − 2P(I = −2). The off-diagonal share is P(I ≠ 0) = P(I > 0) + P(I < 0). A mean "
          "near zero therefore says only that the controller-dependent states with I > 0 (the action swap helps more, or hurts less, "
          "when Q continues) and with I < 0 are about equally frequent; it does not say the action effect is the same under both "
          f"controllers. Example ({[k for k in C if C[k] is ex][0]}): P(I > 0) = {exs['Ipos']['est']:.1f}%, P(I < 0) = {exs['Ineg']['est']:.1f}%, "
          f"so off-diagonal = {exs['offdiag']['est']:.1f}% while E[I] = {exs['I']['est']:+.1f} pp. Most off-diagonal mass is in cells where "
          "one controller shows an effect and the other shows none (one coordinate 0); strict sign reversals are the small corners "
          f"({ex['table3']['strict_reversal_n']} of {ex['table3']['offdiag_n']} off-diagonal states in this cell). "
          "The mean interaction is the right estimand for average policy value; the off-diagonal share is the right one for "
          "\"is the consequence of an action a property of the action alone?\" — and it is not, for roughly 1 in 4 (W4) to 1 in 7 (KV8) "
          "divergent states. Cross-cell differences in these shares (W4 vs KV8) are descriptive: the cells select different states.", "",
          "Figures: " + ", ".join(f"`{x}`" for x in r["figures"]), "",
          "## 3. All 16 outcome patterns (Y_BB, Y_BQ, Y_QB, Y_QQ), counts and shares of divergent states", "",
          "| pattern | " + " | ".join(C) + " |", "|---|" + "---|" * len(C)]
    for p in PATTERNS:
        L.append(f"| {p} | " + " | ".join(f"{C[k]['patterns16']['counts'][p]} ({100 * C[k]['patterns16']['shares'][p]:.1f}%)" for k in C) + " |")
    L.append("| n | " + " | ".join(str(C[k]["patterns16"]["n"]) for k in C) + " |")
    cs = r["cases"]
    L += ["", "## 4. Case studies (frozen rule, re-checked trajectories)", "", f"Rule: {cs['rule']}", "",
          f"Eligible re-checked states: {cs['n_eligible']} (by category {cs['n_eligible_by_category']}).", ""]
    for i, c in enumerate(cs["cases"], 1):
        Y = c["Y"]
        L += [f"### Case {i} — {c['category'].replace('_', '-')}: {c['model']} {c['cell']}, {c['task']} (block {c['block']}, pivot decision {c['decision_idx']} of {c['n_decisions_orig']}, {c['divergence_type']})", "",
              f"Outcomes BB/BQ/QB/QQ = {Y['BB']}/{Y['BQ']}/{Y['QB']}/{Y['QQ']} (pattern {c['pattern']}); Δ_Q = {c['dQ']:+d}, Δ_B = {c['dB']:+d}. "
              f"User goal: {c['reason_for_call']}", "",
              f"- **Q action at the pivot:** `{c['a_Q']}`", f"- **B action at the pivot:** `{c['a_B']}`", ""]
        for b in ("BB", "BQ", "QB", "QQ"):
            e = c["branches"][b]
            L.append(f"- **{b}** ({'success' if e['success'] else 'fail'}; {e['termination']}, {e['steps_final']} steps, {e['n_tool_calls']} tool calls, "
                     f"{e['n_tool_errors']} errors, writes: {', '.join(e['writes']) or 'none'}{', transfer to human' if e['transfers'] else ''}): " + (" → ".join(e["events"][:6]) or "no tool calls (text only)")
                     + (" → …" if len(e["events"]) > 6 else ""))
        L += ["", f"  Files: `{c['files']['state']}`, `{c['files']['branches']}`", ""]
    L += ["## 5. Coverage matrix (model × config × benchmark)", "",
          "Codes: **E2E** k b × n t = completed end-to-end blocks × tasks per block (run status files); **F4** = 4-branch dev forks: "
          "tasks · divergent states · complete/found blocks after the strict rule (tau2) or items · valid states · 1 run (ALFWorld/BFCL); "
          "**U** = Bank U blocks · rows · tasks; **HOLDOUT** = telecom holdout fork directories exist (not opened); – = not run. "
          "Queue-task counts are not used. The F4 retail/airline counts are the analysed panel; telecom F4 = dev split.", "",
          "### Quantization configs", "", "| model:config | retail | airline | telecom | alfworld | bfcl |", "|---|---|---|---|---|---|"]
    for kind in ("quantization", "reference/perturbation"):
        if kind != "quantization":
            L += ["", "### Reference and perturbation-null configs (BF16, BF16 pair, null, Gaussian)", "",
                  "| model:config | retail | airline | telecom | alfworld | bfcl |", "|---|---|---|---|---|---|"]
        for k, v in r["coverage"].items():
            if v["kind"] == kind:
                L.append(f"| {k} | " + " | ".join(cov_cell(v["benchmarks"][b]) for b in ("retail", "airline", "telecom", "alfworld", "bfcl")) + " |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
