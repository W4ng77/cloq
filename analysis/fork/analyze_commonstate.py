"""Common-state action-source analysis (W100a/W100b; docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md, frozen).

Inputs: manifests/fork/commonstate_v1.json (protocol sha256, bank manifest, canaries), the reference Bank U rows
analysis/fork/bank_u/q8_gptq_w4_d1/f0{1,2,3}/ (BB, BQ, QB, QQ), the new arms
analysis/fork/commonstate/q8/panel/{d2_bf16,d2_d1}/<blk>/cs_rows.jsonl (+ cs_summary.json), the gate summaries, and the
queue records (server canaries). Refuses to run unless sha256(protocol) equals the manifest value.

usage: python analysis/fork/analyze_commonstate.py [--boot 2000] [--selftest]
  --selftest  synthetic new arms (d2 := d1 action outcomes) to exercise the code; writes to $TMPDIR only, never to out/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MAN = ROOT / "manifests" / "fork" / "commonstate_v1.json"
OUT = ROOT / "analysis" / "fork" / "out"
QUEUE = Path("/data/ziyangs/cloq_work/queue")
TYPES = {"d2_bf16": {"B": "bf16", "Q": "gptq_w4_d2"}, "d2_d1": {"B": "gptq_w4_d2", "Q": "gptq_w4_d1"}}
SRC = ("bf16", "d1", "d2")
CONT = ("bf16", "d1")
PAIRS = (("bf16", "d1"), ("bf16", "d2"), ("d2", "d1"))
TCRIT = {1: (12.706, 6.314), 2: (4.303, 2.920), 3: (3.182, 2.353), 4: (2.776, 2.132), 5: (2.571, 2.015)}  # (95 % two-sided, 90 %)


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


# ----------------------------------------------------------------------------------------------------------------------
# loading and admission (protocol §4)
# ----------------------------------------------------------------------------------------------------------------------

def canary_check(tid: str, typ: str, man: dict) -> dict:
    p = QUEUE / "done" / f"{tid}.json"
    if not p.exists():
        return {"ok": False, "reason": "no done record"}
    srv = (json.load(open(p)).get("result") or {}).get("servers") or {}
    got = {r: (srv.get(r) or {}).get("canary") for r in ("B", "Q")}
    want = {r: man["canaries"][TYPES[typ][r]] for r in ("B", "Q")}
    ck = {r: (srv.get(r) or {}).get("ckpt_sha256") for r in ("B", "Q")}
    want_ck = {r: man["ckpt_sha256"].get(TYPES[typ][r]) for r in ("B", "Q")}
    ok = got == want and all(want_ck[r] is None or ck[r] == want_ck[r] for r in ("B", "Q"))
    return {"ok": ok, "canary": got, "want": want, "ckpt_sha256": ck, "host": json.load(open(p)).get("host")}


def load(man: dict, inputs: dict, selftest: bool) -> tuple[list[dict], dict]:
    bank_sha = sha_file(ROOT / man["bank_manifest"])
    if bank_sha != man["bank_manifest_sha256"]:
        raise SystemExit("bank manifest sha differs from commonstate_v1.json")
    notes = {"blocks": {}, "excluded": [], "gate": {}}
    for typ in TYPES:
        g = ROOT / man["gate_dir"] / typ / "cs_summary.json"
        if g.exists():
            s = json.loads(g.read_text())
            inputs[rel(g)] = sha_file(g)
            notes["gate"][typ] = {"verdict": s.get("verdict"), "n_rows": s.get("n_rows"), "n_ok": s.get("n_ok"),
                                  "ref_rerun": [s.get("n_ref_rerun_pass"), s.get("n_ref_rerun")], "n_implicit": s.get("n_implicit"),
                                  "idcheck": {k: [v.get("n_match"), v.get("n")] for k, v in s.items() if k.startswith("idcheck_")},
                                  "canary": canary_check(f"cs_gate_q8_{typ}", typ, man)}
    units = []
    for blk in man["blocks"]:
        rd = ROOT / man["ref_dir"] / blk
        rs = json.loads((rd / "bank_summary.json").read_text())
        if rs.get("manifest_sha256") != bank_sha:
            raise SystemExit(f"{rd}: reference bank run used a different manifest")
        inputs[rel(rd / "bank_rows.jsonl")] = sha_file(rd / "bank_rows.jsonl")
        ref = {r["state_key"]: r for r in jl(rd / "bank_rows.jsonl") if r["sub"] == "U2B"}
        new, binfo = {}, {"n_ref": len(ref)}
        for typ in TYPES:
            d = ROOT / man["panel_dir"] / typ / blk
            if selftest:
                new[typ] = {k: synth(r, typ) for k, r in ref.items()}
                binfo[typ] = {"selftest": True}
                continue
            if not (d / "cs_summary.json").exists():
                binfo[typ] = {"status": "not finished"}
                continue
            s = json.loads((d / "cs_summary.json").read_text())
            inputs[rel(d / "cs_rows.jsonl")] = sha_file(d / "cs_rows.jsonl")
            inputs[rel(d / "cs_summary.json")] = sha_file(d / "cs_summary.json")
            can = canary_check(f"cs_q8_{typ}_{blk}", typ, man)
            rows = {r["state_key"]: r for r in jl(d / "cs_rows.jsonl")}
            binfo[typ] = {"verdict": s.get("verdict"), "n_rows": s.get("n_rows"), "n_ok": s.get("n_ok"), "n_missing": s.get("n_missing"),
                          "n_errors": s.get("n_errors"), "ref_rerun": [s.get("n_ref_rerun_pass"), s.get("n_ref_rerun")],
                          "n_implicit": s.get("n_implicit"), "n_identity_fail": s.get("n_identity_fail"), "canary": can,
                          "manifest_sha_ok": s.get("manifest_sha256") == bank_sha}
            if not can["ok"] or s.get("manifest_sha256") != bank_sha:
                rows = {}
            new[typ] = rows
        # block quarantine: any failed reference re-run or implicit identity in either task
        quarantined = [typ for typ in TYPES if any(r.get("identity") and not r.get("identity_ok") for r in new.get(typ, {}).values())]
        binfo["quarantined_by"] = quarantined
        adm = []
        for k, rr in sorted(ref.items()):
            a, b = new.get("d2_bf16", {}).get(k), new.get("d2_d1", {}).get(k)
            why = None
            if any(rr["Y"].get(x) is None for x in ("BB", "BQ", "QB", "QQ")):
                why = "reference outcomes incomplete"
            elif a is None or b is None or a.get("Y") is None or b.get("Y") is None:
                why = "new arm missing: " + str((a or {}).get("missing_reason") or (a or {}).get("error") or (b or {}).get("missing_reason") or (b or {}).get("error") or "not run")[:160]
            elif not (all(a["ref_same"].values()) and all(b["ref_same"].values())):
                why = "state differs from reference"
            elif not (all(a["checks"].values()) and all(b["checks"].values())):
                why = "d2 replay/prompt check failed"
            elif a["a_src_completion_ids_sha"] != b["a_src_completion_ids_sha"] or canon(a["a_src"]) != canon(b["a_src"]):
                why = "a_d2 differs between tasks A and B"
            if why:
                notes["excluded"].append({"block": blk, "state_key": k, "reason": why})
                continue
            Y = {("bf16", "bf16"): rr["Y"]["BB"], ("bf16", "d1"): rr["Y"]["BQ"], ("d1", "bf16"): rr["Y"]["QB"], ("d1", "d1"): rr["Y"]["QQ"],
                 ("d2", "bf16"): a["Y"], ("d2", "d1"): b["Y"]}
            ag = {"bf16_d1": bool(rr["exact_agreement"]), "bf16_d2": bool(a["agreement"]["vs_bf16"]["exact"]), "d1_d2": bool(a["agreement"]["vs_d1"]["exact"]),
                  "cat_bf16_d1": rr.get("agreement_category"), "cat_bf16_d2": a["agreement"]["vs_bf16"]["category"], "cat_d1_d2": a["agreement"]["vs_d1"]["category"]}
            adm.append({"block": blk, "task": f"{rr['domain']}|{rr['task_id']}", "domain": rr["domain"], "state_key": k, "Y": Y, "ag": ag})
        binfo["n_admitted"] = len(adm)
        binfo["complete"] = len(adm) == len(ref) == 85 and not quarantined
        notes["blocks"][blk] = binfo
        units += [u for u in adm if binfo["complete"]]
    return units, notes


def canon(m: dict) -> str:
    sys.path.insert(0, str(ROOT))
    from cloq.fork import canon_msg
    return json.dumps(canon_msg(m), sort_keys=True)


def synth(rr: dict, typ: str) -> dict:
    """--selftest only: d2 := d1 (same action, same outcomes)."""
    y = rr["Y"]["QB"] if typ == "d2_bf16" else rr["Y"]["QQ"]
    return {"Y": y, "ref_same": {"x": True}, "checks": {"x": True}, "a_src_completion_ids_sha": "s", "a_src": rr["a_Q"],
            "agreement": {"vs_bf16": {"exact": bool(rr["exact_agreement"]), "category": rr.get("agreement_category")},
                          "vs_d1": {"exact": True, "category": "same"}}, "identity": {}, "identity_ok": True}


# ----------------------------------------------------------------------------------------------------------------------
# statistics (protocol §§5–6)
# ----------------------------------------------------------------------------------------------------------------------

def columns(units: list[dict]) -> dict:
    C = {}
    for s in SRC:
        for c in CONT:
            C[f"V[{s},{c}]"] = [u["Y"][(s, c)] for u in units]
    for s1, s2 in PAIRS:
        for c in CONT:
            y1 = [u["Y"][(s1, c)] for u in units]
            y2 = [u["Y"][(s2, c)] for u in units]
            C[f"D[{s1}-{s2}|{c}]"] = [a - b for a, b in zip(y1, y2)]
            C[f"r[{s1}-{s2}|{c}]"] = [int(a == 1 and b == 0) for a, b in zip(y1, y2)]
            C[f"d[{s1}-{s2}|{c}]"] = [int(a == 0 and b == 1) for a, b in zip(y1, y2)]
            C[f"M[{s1}-{s2}|{c}]"] = [int(a != b) for a, b in zip(y1, y2)]
        C[f"I[{s1}-{s2}]"] = [a - b for a, b in zip(C[f"D[{s1}-{s2}|bf16]"], C[f"D[{s1}-{s2}|d1]"])]
    for c in CONT:
        C[f"K[{c}]"] = [a - b for a, b in zip(C[f"D[bf16-d1|{c}]"], C[f"D[d2-d1|{c}]"])]
    C["Kbar"] = [(a + b) / 2 for a, b in zip(C["K[bf16]"], C["K[d1]"])]
    return C


def estimate(units: list[dict], C: dict, nboot: int, seed: int) -> dict:
    blocks = sorted({u["block"] for u in units})
    tasks = sorted({u["task"] for u in units})
    k, T = len(blocks), len(tasks)
    bidx = np.array([blocks.index(u["block"]) for u in units])
    tidx = np.array([tasks.index(u["task"]) for u in units])
    X = {s: np.array(v, dtype=float) for s, v in C.items()}

    def point(w: np.ndarray) -> tuple[dict, dict]:
        pt, bm = {}, {}
        for s, x in X.items():
            vals = np.array([(w[bidx == b] * x[bidx == b]).sum() / w[bidx == b].sum() if w[bidx == b].sum() > 0 else np.nan for b in range(k)])
            bm[s] = vals
            pt[s] = float(np.nanmean(vals))
        return pt, bm

    pt, bm = point(np.ones(len(units)))
    rng = np.random.default_rng(seed)
    draws = {s: np.empty(nboot) for s in X}
    for i in range(nboot):
        mult = np.bincount(rng.integers(0, T, T), minlength=T).astype(float)
        p, _ = point(mult[tidx])
        for s in X:
            draws[s][i] = p[s]
    res = {"n": len(units), "k": k, "n_tasks": T, "blocks": blocks, "stats": {}}
    for s in X:
        e = {"point": pt[s], "block_means": [float(v) for v in bm[s]],
             "boot95": [float(np.nanpercentile(draws[s], 2.5)), float(np.nanpercentile(draws[s], 97.5))],
             "boot90": [float(np.nanpercentile(draws[s], 5)), float(np.nanpercentile(draws[s], 95))],
             "boot_p2": float(min(1.0, 2 * min((draws[s] <= 0).mean(), (draws[s] >= 0).mean())))}
        if k >= 2:
            v = bm[s][~np.isnan(bm[s])]
            se = float(np.std(v, ddof=1) / math.sqrt(len(v)))
            t95, t90 = TCRIT[len(v) - 1]
            e["t95"] = [float(v.mean() - t95 * se), float(v.mean() + t95 * se)]
            e["t90"] = [float(v.mean() - t90 * se), float(v.mean() + t90 * se)]
        res["stats"][s] = e
    return res


def reading(e: dict, margin: float, p_holm: float | None = None, label_pos: str = "", label_neg: str = "") -> dict:
    """Frozen three-way rule (protocol §6): both 95 % intervals exclude 0 on one side (+ Holm p < .05 when given) ->
    difference; both 90 % intervals inside (-margin, +margin) -> equivalent (TOST); else not resolved."""
    if "t95" not in e:
        return {"reading": "no reading (fewer than 2 blocks)"}
    ivs95, ivs90 = (e["t95"], e["boot95"]), (e["t90"], e["boot90"])
    pos = all(lo > 0 for lo, _ in ivs95) and (p_holm is None or p_holm < 0.05)
    neg = all(hi < 0 for _, hi in ivs95) and (p_holm is None or p_holm < 0.05)
    eq = all(-margin < lo and hi < margin for lo, hi in ivs90)
    tost = {"t90_inside": -margin < e["t90"][0] and e["t90"][1] < margin, "boot90_inside": -margin < e["boot90"][0] and e["boot90"][1] < margin}
    r = label_pos if pos else label_neg if neg else f"equivalent within ±{margin * 100:.0f} pp (TOST)" if eq else "not resolved"
    return {"reading": r, "tost": tost, "p_holm": p_holm}


def holm(ps: list[float]) -> list[float]:
    o = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(o):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def agreement(units: list[dict]) -> dict:
    n = len(units)
    if not n:
        return {}
    out = {"n": n}
    for p in ("bf16_d1", "bf16_d2", "d1_d2"):
        out[f"exact_{p}"] = sum(u["ag"][p] for u in units) / n
        cats: dict = {}
        for u in units:
            c = u["ag"][f"cat_{p}"]
            cats[c] = cats.get(c, 0) + 1
        out[f"categories_{p}"] = cats

    def pat(a):
        if a["bf16_d1"] and a["bf16_d2"]:
            return "all equal"
        if a["bf16_d1"]:
            return "BF16 = d1 != d2"
        if a["bf16_d2"]:
            return "BF16 = d2 != d1"
        if a["d1_d2"]:
            return "d1 = d2 != BF16"
        return "all different"
    pats: dict = {}
    for u in units:
        pats[pat(u["ag"])] = pats.get(pat(u["ag"]), 0) + 1
    out["patterns"] = pats
    return out


# ----------------------------------------------------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------------------------------------------------

def pp(x: float) -> str:
    return f"{100 * x:+.1f}"


def iv(e: dict, key: str) -> str:
    return f"[{100 * e[key][0]:+.1f}, {100 * e[key][1]:+.1f}]" if key in e else "n/a"


def write_md(R: dict, path: Path) -> None:
    L = []
    E = R.get("estimates") or {}
    S = E.get("stats", {})
    rd = R.get("readings", {})
    L.append(f"**TL;DR** {R['tldr']}\n")
    L.append(f"# Common-state action sources on q8 (commonstate-v1) — {R['created']}\n")
    L.append(f"Protocol `{R['protocol']}` sha256 `{R['protocol_sha256']}` (verified). Analysis set: blocks "
             f"{E.get('blocks')} (k = {E.get('k')}), {E.get('n')} states, {E.get('n_tasks')} tasks. Intervals: t over block means "
             f"(df = k − 1) and task-cluster bootstrap (B = {R['boot']['B']}, seed {R['boot']['seed']}); margin ±{R['margin_pp']:.0f} pp.\n")
    if S:
        L.append("## V(source, continuation) (success, %)\n")
        L.append("| source \\ continuation | BF16 | d1 (GPTQ-W4 d1) |\n|---|---|---|")
        for s in SRC:
            L.append(f"| {s} | " + " | ".join(f"{100 * S[f'V[{s},{c}]']['point']:.1f} (t95 {iv(S[f'V[{s},{c}]'], 't95')})" for c in CONT) + " |")
        L.append("\n## Key estimand K(c) = Δ_{BF16−d1}(c) − Δ_{d2−d1}(c) = Δ_{BF16−d2}(c) (pp)\n")
        L.append("| c | K | t95 | boot95 | t90 | boot90 | boot p (Holm) | reading |\n|---|---|---|---|---|---|---|---|")
        for c in CONT + ("bar",):
            key = "Kbar" if c == "bar" else f"K[{c}]"
            e, r = S[key], rd.get(key, {})
            ph = r.get("p_holm")
            L.append(f"| {c if c != 'bar' else 'average (secondary)'} | {pp(e['point'])} | {iv(e, 't95')} | {iv(e, 'boot95')} | {iv(e, 't90')} | {iv(e, 'boot90')} | "
                     f"{e['boot_p2']:.3f}{f' ({ph:.3f})' if ph is not None else ''} | {r.get('reading')} |")
        L.append("\n## Contrasts Δ, rescue r, damage d, turnover M (pp)\n")
        L.append("| contrast | c | Δ | Δ t95 | Δ boot95 | r | d | M | reading (descriptive) |\n|---|---|---|---|---|---|---|---|---|")
        for s1, s2 in PAIRS:
            for c in CONT:
                k = f"[{s1}-{s2}|{c}]"
                e = S["D" + k]
                L.append(f"| {s1} − {s2} | {c} | {pp(e['point'])} | {iv(e, 't95')} | {iv(e, 'boot95')} | {100 * S['r' + k]['point']:.1f} | "
                         f"{100 * S['d' + k]['point']:.1f} | {100 * S['M' + k]['point']:.1f} | {rd.get('D' + k, {}).get('reading')} |")
        L.append("\n## Interaction with the continuation I = Δ(c = BF16) − Δ(c = d1) (pp; secondary reading)\n")
        L.append("| contrast | I | t95 | boot95 | t90 | boot90 | reading |\n|---|---|---|---|---|---|---|")
        for s1, s2 in PAIRS:
            e = S[f"I[{s1}-{s2}]"]
            L.append(f"| {s1} − {s2} | {pp(e['point'])} | {iv(e, 't95')} | {iv(e, 'boot95')} | {iv(e, 't90')} | {iv(e, 'boot90')} | {rd.get(f'I[{s1}-{s2}]', {}).get('reading')} |")
        A = R.get("agreement", {})
        L.append("\n## Action agreement among the three sources\n")
        L.append(f"Exact canonical agreement: BF16 = d1 {100 * A['exact_bf16_d1']:.1f}%, BF16 = d2 {100 * A['exact_bf16_d2']:.1f}%, "
                 f"d1 = d2 {100 * A['exact_d1_d2']:.1f}% (n = {A['n']}).\n")
        L.append("| pattern | n |\n|---|---|")
        for p, n in sorted(A["patterns"].items(), key=lambda x: -x[1]):
            L.append(f"| {p} | {n} |")
        L.append("\nComparator categories: " + "; ".join(f"{p}: {A['categories_' + p]}" for p in ("bf16_d1", "bf16_d2", "d1_d2")) + "\n")
        X = R.get("exploratory_subset")
        if X:
            L.append(f"Descriptive (labelled exploratory): on the {X['n']} states where a_d2 ≠ a_BF16, K(d1) = {pp(X['K[d1]'])} pp, "
                     f"K(BF16) = {pp(X['K[bf16]'])} pp (point estimates, unit means).\n")
        L.append("## Per block\n")
        L.append("| block | n | " + " | ".join(f"V[{s},{c}]" for s in SRC for c in CONT) + " | K[d1] | K[bf16] |\n|" + "---|" * 10)
        for i, b in enumerate(E["blocks"]):
            L.append(f"| {b} | 85 | " + " | ".join(f"{100 * S[f'V[{s},{c}]']['block_means'][i]:.1f}" for s in SRC for c in CONT)
                     + f" | {pp(S['K[d1]']['block_means'][i])} | {pp(S['K[bf16]']['block_means'][i])} |")
    L.append("\n## Acceptance\n")
    L.append("Gate: " + json.dumps(R["notes"]["gate"], default=str) + "\n")
    for b, info in R["notes"]["blocks"].items():
        L.append(f"- {b}: " + json.dumps(info, default=str))
    L.append(f"\nExcluded units: {len(R['notes']['excluded'])} " + json.dumps(R["notes"]["excluded"][:20]))
    L.append("\nInputs (sha256): " + json.dumps(R["inputs"], indent=0))
    path.write_text("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    man = json.loads(MAN.read_text())
    proto = ROOT / man["protocol"]
    psha = sha_file(proto)
    if psha != man["protocol_sha256"]:
        raise SystemExit(f"protocol sha256 {psha} != pre-registered {man['protocol_sha256']}: refusing to run")
    nboot = a.boot or man["boot"]["B"]
    inputs = {rel(MAN): sha_file(MAN), rel(proto): psha}
    units, notes = load(man, inputs, a.selftest)
    margin = man["margin_pp"] / 100
    R = {"protocol": man["protocol"], "protocol_sha256": psha, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "boot": {"B": nboot, "seed": man["boot"]["seed"]}, "margin_pp": man["margin_pp"], "selftest": a.selftest,
         "notes": notes, "inputs": inputs}
    k = len({u["block"] for u in units})
    if k == 0:
        R["tldr"] = "No complete, non-quarantined block yet: nothing to estimate (acceptance status below)."
    else:
        C = columns(units)
        E = estimate(units, C, nboot, man["boot"]["seed"])
        R["estimates"] = E
        S = E["stats"]
        ph = holm([S["K[bf16]"]["boot_p2"], S["K[d1]"]["boot_p2"]])
        rd = {"K[bf16]": reading(S["K[bf16]"], margin, ph[0], "BF16 action adds value beyond a W4 swap", "another W4 action does better"),
              "K[d1]": reading(S["K[d1]"], margin, ph[1], "BF16 action adds value beyond a W4 swap", "another W4 action does better"),
              "Kbar": reading(S["Kbar"], margin, None, "BF16 action adds value beyond a W4 swap (secondary)", "another W4 action does better (secondary)")}
        for s1, s2 in PAIRS:
            rd[f"I[{s1}-{s2}]"] = reading(S[f"I[{s1}-{s2}]"], margin, None, "continuation-dependent", "continuation-dependent")
            for c in CONT:
                rd[f"D[{s1}-{s2}|{c}]"] = reading(S[f"D[{s1}-{s2}|{c}]"], margin, None, "positive", "negative")
        R["readings"] = rd
        R["agreement"] = agreement(units)
        sub = [u for u in units if not u["ag"]["bf16_d2"]]
        if sub:
            Cs = columns(sub)
            R["exploratory_subset"] = {"n": len(sub), "K[d1]": float(np.mean(Cs["K[d1]"])), "K[bf16]": float(np.mean(Cs["K[bf16]"]))}
        if k < 2:
            R["tldr"] = f"Only {k} complete block: per-block numbers only, no reading (protocol §4)."
        else:
            R["tldr"] = (f"q8, {E['n']} common states (k = {k} blocks). K(d1) = BF16−d1 minus d2−d1 under the d1 continuation = "
                         f"{pp(S['K[d1]']['point'])} pp (t95 {iv(S['K[d1]'], 't95')}, boot95 {iv(S['K[d1]'], 'boot95')}): {rd['K[d1]']['reading']}. "
                         f"K(BF16) = {pp(S['K[bf16]']['point'])} pp (t95 {iv(S['K[bf16]'], 't95')}, boot95 {iv(S['K[bf16]'], 'boot95')}): "
                         f"{rd['K[bf16]']['reading']}. Δ BF16−d1 / d2−d1 under d1: {pp(S['D[bf16-d1|d1]']['point'])} / {pp(S['D[d2-d1|d1]']['point'])} pp; "
                         f"exact action agreement BF16=d1 {100 * R['agreement']['exact_bf16_d1']:.0f}%, d1=d2 {100 * R['agreement']['exact_d1_d2']:.0f}%.")
    if a.selftest:
        R["tldr"] = "SELFTEST (synthetic d2 := d1; not a result). " + R["tldr"]
        out = Path(os.environ.get("TMPDIR", "/tmp")) / f"commonstate_selftest_{R['created'].replace(':', '')}"
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        out = OUT / f"commonstate_{R['created'].replace(':', '').replace('-', '')}"
    out.with_suffix(".json").write_text(json.dumps(R, indent=1, default=str))
    write_md(R, out.with_suffix(".md"))
    print(out.with_suffix(".md"))
    print(R["tldr"])


if __name__ == "__main__":
    main()
