"""Common-state action-source analysis (W100a/W100b; docs/insights/COMMONSTATE_SOURCES_PROTOCOL.md, frozen).

Inputs: manifests/fork/commonstate_v1.json (protocol sha256, bank manifest, canaries), the reference Bank U rows
analysis/fork/bank_u/q8_gptq_w4_d1/f0{1,2,3}/ (BB, BQ, QB, QQ), the new arms
analysis/fork/commonstate/q8/panel/{d2_bf16,d2_d1}/<blk>/cs_rows.jsonl (+ cs_summary.json), the gate summaries, and the
queue records (server canaries). Refuses to run unless sha256(protocol) equals the manifest value.

usage: python analysis/fork/analyze_commonstate.py [--boot 2000] [--selftest]
  --selftest  synthetic new arms (d2 := d1 action outcomes) to exercise the code; writes to $TMPDIR only, never to out/.
W100u (amendment A1): --design q8ext (K = 6: commonstate_v1 f01-f03 + commonstate_q8ext_v1 f04-f06, own d1 reference, Pocock
two-look reading, first look reported) | --design q4 (commonstate_q4_v1, K = 3). Once only, at the earlier of all tasks done
and the freeze; blocks whose tasks finished after the freeze are excluded. --selftest also synthesises missing reference rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime
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
DESIGNS = {"q8ext": ROOT / "manifests" / "fork" / "commonstate_q8ext_v1.json", "q4": ROOT / "manifests" / "fork" / "commonstate_q4_v1.json"}
PROTOCOL_SHA_A1 = "dce4024597441ab874324f03eb02609364b66cf821b67826b04a39feaa7b13ee"  # amendment A1 (W100u, commit ccf9f13)
PREFIX_D1 = (12813, "c73ab2eec2f14052633e0703c2f50b1df9356c8222ba2ad1c8541301948198d0")  # v1 + D1, byte-identical prefix
POCOCK = (0.0294, 0.0304)  # A1.3: two equally spaced looks, two-sided / one-sided nominal (commonstate_twolook_mc.py)
TCRIT_POCOCK = {1: (21.649, 10.450), 2: (5.704, 3.870), 3: (3.927, 2.935), 4: (3.320, 2.589), 5: (3.021, 2.412)}


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

def canary_check(tid: str, typ: str | dict, man: dict) -> dict:
    p = QUEUE / "done" / f"{tid}.json"
    if not p.exists():
        return {"ok": False, "reason": "no done record"}
    roles = TYPES[typ] if isinstance(typ, str) else typ
    srv = (json.load(open(p)).get("result") or {}).get("servers") or {}
    got = {r: (srv.get(r) or {}).get("canary") for r in ("B", "Q")}
    want = {r: man["canaries"][roles[r]] for r in ("B", "Q")}
    ck = {r: (srv.get(r) or {}).get("ckpt_sha256") for r in ("B", "Q")}
    want_ck = {r: man["ckpt_sha256"].get(roles[r]) for r in ("B", "Q")}
    ok = got == want and all(want_ck[r] is None or ck[r] == want_ck[r] for r in ("B", "Q"))
    return {"ok": ok, "canary": got, "want": want, "ckpt_sha256": ck, "host": json.load(open(p)).get("host")}


def done_by(tid: str, freeze: float) -> bool:
    p = QUEUE / "done" / f"{tid}.json"
    return p.exists() and float(json.load(open(p)).get("finished") or math.inf) <= freeze


def ref_check(seg: dict, blk: str, rs: dict) -> dict:
    """A1.1: an f04-f06 reference block (this study's bank_u task) counts only if complete, every BB no-op passed, canaries ok."""
    tid, nb = seg["ref_task"]["id"].format(blk=blk), rs.get("noop") or {}
    can = canary_check(tid, {"B": "bf16", "Q": seg["ref_task"]["cell"]}, seg)
    ok = rs.get("n_rows") == rs.get("n_ok") == 85 and rs.get("n_errors") == 0 and rs.get("n_missing") == 0 \
        and nb.get("n_pass") == nb.get("n") and can["ok"]
    return {"ok": bool(ok), "task": tid, "n_rows": rs.get("n_rows"), "n_ok": rs.get("n_ok"), "n_errors": rs.get("n_errors"),
            "n_missing": rs.get("n_missing"), "noop": nb, "canary": can}


def crosscheck(seg: dict, blk: str, ref: dict) -> dict | None:
    """A1.1 acceptance note only: agreement with NEWMETHOD's phase-2 gptq_w4_d1 rows when they exist (never changes admission)."""
    p = ROOT / seg["crosscheck_dir"] / blk / "bank_rows.jsonl"
    if not p.exists():
        return None
    other = {r["state_key"]: r for r in jl(p) if r.get("sub") == "U2B"}
    both = [k for k in ref if k in other and other[k].get("Y")]
    return {"n": len(both), "a_Q_equal": sum(canon(ref[k]["a_Q"]) == canon(other[k]["a_Q"]) for k in both),
            "Y_equal": {x: sum(ref[k]["Y"].get(x) == other[k]["Y"].get(x) for k in both) for x in ("BB", "BQ", "QB", "QQ")}}


def synth_ref(seg: dict, blk: str) -> dict:
    """--selftest only: synthetic reference rows (hash-random outcomes) for a block whose reference was not run."""
    out = {}
    for r in json.loads((ROOT / seg["bank_manifest"]).read_text())["rows"]:
        if r["model"] == seg["model"] and r["block"] == blk and r["sub"] == "U2B":
            h = hashlib.sha256(f"commonstate-selftest|{r['state_key']}".encode()).digest()
            a = {"role": "assistant", "content": f"synthetic {r['state_key']}"}
            out[r["state_key"]] = {**{k: r[k] for k in ("state_key", "sub", "domain", "task_id")}, "a_B": a,
                                   "Y": {x: int(h[i] < 77) for i, x in enumerate(("BB", "BQ", "QB", "QQ"))},
                                   "a_Q": a if h[4] < 150 else {**a, "content": a["content"] + " (Q)"},
                                   "exact_agreement": h[4] < 150, "agreement_category": "same" if h[4] < 150 else "text_only"}
    return out


def load(man: dict, inputs: dict, selftest: bool, segs: list[dict] | None = None, freeze: float | None = None) -> tuple[list[dict], dict]:
    notes = {"blocks": {}, "excluded": [], "gate": {}}
    units = []
    for seg in segs or [man]:
        units += load_seg(seg, notes, inputs, selftest, freeze)
    return units, notes


def load_seg(man: dict, notes: dict, inputs: dict, selftest: bool, freeze: float | None) -> list[dict]:
    m = man.get("model", "q8")
    bank_sha = sha_file(ROOT / man["bank_manifest"])
    if bank_sha != man["bank_manifest_sha256"]:
        raise SystemExit(f"bank manifest sha differs from the commonstate manifest ({man['bank_manifest']})")
    for typ in TYPES if "gate_dir" in man else ():
        g = ROOT / man["gate_dir"] / typ / "cs_summary.json"
        if g.exists():
            s = json.loads(g.read_text())
            inputs[rel(g)] = sha_file(g)
            notes["gate"][typ] = {"verdict": s.get("verdict"), "n_rows": s.get("n_rows"), "n_ok": s.get("n_ok"),
                                  "ref_rerun": [s.get("n_ref_rerun_pass"), s.get("n_ref_rerun")], "n_implicit": s.get("n_implicit"),
                                  "idcheck": {k: [v.get("n_match"), v.get("n")] for k, v in s.items() if k.startswith("idcheck_")},
                                  "canary": canary_check(f"cs_gate_{m}_{typ}", typ, man)}
    units = []
    for blk in man["blocks"]:
        rd = ROOT / man["ref_dir"] / blk
        if selftest and "ref_task" in man and not (rd / "bank_summary.json").exists():
            rs, ref = {}, synth_ref(man, blk)
        elif not (rd / "bank_summary.json").exists():  # W100u: an f04-f06 reference task not finished
            notes["blocks"][blk] = {"status": "reference not finished", "complete": False}
            continue
        else:
            rs = json.loads((rd / "bank_summary.json").read_text())
            if rs.get("manifest_sha256") != bank_sha:
                raise SystemExit(f"{rd}: reference bank run used a different manifest")
            inputs[rel(rd / "bank_rows.jsonl")] = sha_file(rd / "bank_rows.jsonl")
            ref = {r["state_key"]: r for r in jl(rd / "bank_rows.jsonl") if r["sub"] == "U2B"}
        new, binfo = {}, {"n_ref": len(ref)}
        if "ref_task" in man and not selftest:
            binfo["reference"] = ref_check(man, blk, rs)
        if freeze is not None and not selftest:
            tids = [f"cs_{m}_{t}_{blk}" for t in TYPES] + ([man["ref_task"]["id"].format(blk=blk)] if "ref_task" in man else [])
            binfo["finished_by_freeze"] = {t: done_by(t, freeze) for t in tids}
        if man.get("crosscheck_dir") and not selftest:
            binfo["nmp_crosscheck"] = crosscheck(man, blk, ref)
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
            can = canary_check(f"cs_{m}_{typ}_{blk}", typ, man)
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
        if "reference" in binfo or "finished_by_freeze" in binfo:  # W100u designs only (A1.1, A1.5)
            binfo["complete"] = binfo["complete"] and binfo.get("reference", {}).get("ok", True) and all(binfo.get("finished_by_freeze", {}).values())
        notes["blocks"][blk] = binfo
        units += [u for u in adm if binfo["complete"]]
    return units


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


def estimate(units: list[dict], C: dict, nboot: int, seed: int, pocock: bool = False) -> dict:
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
        if pocock:  # A1.3 two-look levels: two-sided 0.0294 (difference), one-sided 0.0304 per TOST side
            e["boot97"] = [float(np.nanpercentile(draws[s], 100 * POCOCK[0] / 2)), float(np.nanpercentile(draws[s], 100 - 100 * POCOCK[0] / 2))]
            e["boot94"] = [float(np.nanpercentile(draws[s], 100 * POCOCK[1])), float(np.nanpercentile(draws[s], 100 - 100 * POCOCK[1]))]
        if k >= 2:
            v = bm[s][~np.isnan(bm[s])]
            se = float(np.std(v, ddof=1) / math.sqrt(len(v)))
            t95, t90 = TCRIT[len(v) - 1]
            e["t95"] = [float(v.mean() - t95 * se), float(v.mean() + t95 * se)]
            e["t90"] = [float(v.mean() - t90 * se), float(v.mean() + t90 * se)]
            if pocock:
                t97, t94 = TCRIT_POCOCK[len(v) - 1]
                e["t97"] = [float(v.mean() - t97 * se), float(v.mean() + t97 * se)]
                e["t94"] = [float(v.mean() - t94 * se), float(v.mean() + t94 * se)]
        res["stats"][s] = e
    return res


def reading(e: dict, margin: float, p_holm: float | None = None, label_pos: str = "", label_neg: str = "",
            k95: tuple = ("t95", "boot95"), k90: tuple = ("t90", "boot90"), alpha: float = 0.05) -> dict:
    """Frozen three-way rule (protocol §6): both 95 % intervals exclude 0 on one side (+ Holm p < .05 when given) ->
    difference; both 90 % intervals inside (-margin, +margin) -> equivalent (TOST); else not resolved.
    A1.3 two-look reading: the same rule on the Pocock intervals (k95/k90) and Holm p < alpha."""
    if k95[0] not in e:
        return {"reading": "no reading (fewer than 2 blocks)"}
    ivs95, ivs90 = (e[k95[0]], e[k95[1]]), (e[k90[0]], e[k90[1]])
    pos = all(lo > 0 for lo, _ in ivs95) and (p_holm is None or p_holm < alpha)
    neg = all(hi < 0 for _, hi in ivs95) and (p_holm is None or p_holm < alpha)
    eq = all(-margin < lo and hi < margin for lo, hi in ivs90)
    tost = {f"{k}_inside": -margin < e[k][0] and e[k][1] < margin for k in k90}
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
    L.append(f"# Common-state action sources on {R.get('title', 'q8 (commonstate-v1)')} — {R['created']}\n")
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
        if R.get("readings_two_look"):  # W100u A1.3
            L.append(f"\n## Two-look reading (A1.3, Pocock: difference two-sided {POCOCK[0]}, TOST one-sided {POCOCK[1]} per side)\n")
            L.append("| c | K | t97 | boot97 | t94 | boot94 | Holm p | reading |\n|---|---|---|---|---|---|---|---|")
            for c in CONT:
                e, r = S[f"K[{c}]"], R["readings_two_look"][f"K[{c}]"]
                L.append(f"| {c} | {pp(e['point'])} | {iv(e, 't97')} | {iv(e, 'boot97')} | {iv(e, 't94')} | {iv(e, 'boot94')} | {r['p_holm']:.3f} | {r['reading']} |")
        if R.get("first_look"):
            fl = R["first_look"]
            L.append(f"\nFirst look (k = 3, W100b, `{fl['file']}`, unchanged): " + "; ".join(
                f"{key} {pp(fl[key]['point'])} pp (t95 {iv(fl[key], 't95')}, boot95 {iv(fl[key], 'boot95')}): {fl[key]['reading']}" for key in ("K[d1]", "K[bf16]")) + "\n")
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


def guard(proto: Path, want: str) -> str:
    """Pre-registered sha, or (W100u) the A1 file whose first PREFIX_D1[0] bytes are the v1 + D1 text that `want` names."""
    b = proto.read_bytes()
    psha = hashlib.sha256(b).hexdigest()
    amended = psha == PROTOCOL_SHA_A1 and hashlib.sha256(b[:PREFIX_D1[0]]).hexdigest() == PREFIX_D1[1]
    if psha != want and not (amended and want == PREFIX_D1[1]):
        raise SystemExit(f"protocol sha256 {psha} != pre-registered {want}: refusing to run")
    return psha


def once_only(design: str, dm: dict, freeze: float) -> None:
    """A1.5: one reading per design, at the earlier of all of its tasks done and the freeze."""
    prior = sorted(OUT.glob(f"commonstate_{design}_*.json"))
    if prior:
        raise SystemExit(f"{design}: reading already made ({rel(prior[0])}); once only (A1.5)")
    tids = [f"cs_{dm['model']}_{t}_{b}" for b in dm["blocks"] for t in TYPES] + \
        ([dm["ref_task"]["id"].format(blk=b) for b in dm["blocks"]] if "ref_task" in dm else [])
    left = [t for t in tids if not (QUEUE / "done" / f"{t}.json").exists()]
    if left and time.time() < freeze:
        raise SystemExit(f"{design}: not yet (A1.5): {len(left)} task(s) not done before the freeze {dm['freeze']}: {left}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=None)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--design", choices=sorted(DESIGNS), default=None, help="W100u amendment A1 readings")
    a = ap.parse_args()
    man = json.loads(MAN.read_text())
    proto = ROOT / man["protocol"]
    psha = guard(proto, man["protocol_sha256"])
    nboot = a.boot or man["boot"]["B"]
    inputs = {rel(MAN): sha_file(MAN), rel(proto): psha}
    segs, freeze, dm = None, None, {}
    if a.design:
        dm = json.loads(DESIGNS[a.design].read_text())
        if guard(proto, dm["protocol_sha256"]) != PROTOCOL_SHA_A1 or dm["protocol_prefix"]["sha256"] != PREFIX_D1[1]:
            raise SystemExit("design manifests need the amendment A1 protocol")
        inputs[rel(DESIGNS[a.design])] = sha_file(DESIGNS[a.design])
        segs = ([man] if a.design == "q8ext" else []) + [dm]
        freeze = datetime.fromisoformat(dm["freeze"]).timestamp()
        if not a.selftest:
            once_only(a.design, dm, freeze)
    units, notes = load(man, inputs, a.selftest, segs, freeze)
    margin = man["margin_pp"] / 100
    R = {"protocol": man["protocol"], "protocol_sha256": psha, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "boot": {"B": nboot, "seed": man["boot"]["seed"]}, "margin_pp": man["margin_pp"], "selftest": a.selftest,
         "notes": notes, "inputs": inputs}
    label = {"q8ext": "q8 K = 6 (amendment A1, confirmatory)", "q4": "q4 (amendment A1.4, separate prospective analysis)"}.get(a.design, "q8")
    if a.design:
        R.update(design=a.design, title={"q8ext": "q8, K = 6 (commonstate-v1 + amendment A1)", "q4": "q4 (commonstate-v1, amendment A1.4)"}[a.design])
    k = len({u["block"] for u in units})
    if k == 0:
        R["tldr"] = "No complete, non-quarantined block yet: nothing to estimate (acceptance status below)."
    else:
        C = columns(units)
        E = estimate(units, C, nboot, man["boot"]["seed"], pocock=a.design == "q8ext")
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
        if a.design == "q8ext":  # A1.3: prespecified two-look (Pocock) reading + the first look, unchanged
            R["readings_two_look"] = {key: reading(S[key], margin, ph[i], "BF16 action adds value beyond a W4 swap", "another W4 action does better",
                                                   ("t97", "boot97"), ("t94", "boot94"), POCOCK[0]) for i, key in enumerate(("K[bf16]", "K[d1]"))}
            fp = ROOT / dm["two_look"]["first_look"]
            fl = json.loads(fp.read_text())
            inputs[rel(fp)] = sha_file(fp)
            R["first_look"] = {"file": rel(fp), **{key: {**{x: fl["estimates"]["stats"][key][x] for x in ("point", "t95", "boot95")},
                                                          "reading": fl["readings"][key]["reading"]} for key in ("K[bf16]", "K[d1]")}}
        R["agreement"] = agreement(units)
        sub = [u for u in units if not u["ag"]["bf16_d2"]]
        if sub:
            Cs = columns(sub)
            R["exploratory_subset"] = {"n": len(sub), "K[d1]": float(np.mean(Cs["K[d1]"])), "K[bf16]": float(np.mean(Cs["K[bf16]"]))}
        if k < 2:
            R["tldr"] = f"Only {k} complete block: per-block numbers only, no reading (protocol §4)."
        else:
            R["tldr"] = (f"{label}, {E['n']} common states (k = {k} blocks). K(d1) = BF16−d1 minus d2−d1 under the d1 continuation = "
                         f"{pp(S['K[d1]']['point'])} pp (t95 {iv(S['K[d1]'], 't95')}, boot95 {iv(S['K[d1]'], 'boot95')}): {rd['K[d1]']['reading']}. "
                         f"K(BF16) = {pp(S['K[bf16]']['point'])} pp (t95 {iv(S['K[bf16]'], 't95')}, boot95 {iv(S['K[bf16]'], 'boot95')}): "
                         f"{rd['K[bf16]']['reading']}. Δ BF16−d1 / d2−d1 under d1: {pp(S['D[bf16-d1|d1]']['point'])} / {pp(S['D[d2-d1|d1]']['point'])} pp; "
                         f"exact action agreement BF16=d1 {100 * R['agreement']['exact_bf16_d1']:.0f}%, d1=d2 {100 * R['agreement']['exact_d1_d2']:.0f}%.")
            if R.get("readings_two_look"):
                r2, fl = R["readings_two_look"], R["first_look"]
                R["tldr"] += (f" Two-look (Pocock) reading: K(d1) {r2['K[d1]']['reading']}, K(BF16) {r2['K[bf16]']['reading']}. First look "
                              f"(k = 3, W100b): K(d1) {pp(fl['K[d1]']['point'])} pp, {fl['K[d1]']['reading']}; K(BF16) {pp(fl['K[bf16]']['point'])} pp, "
                              f"{fl['K[bf16]']['reading']}.")
    if a.design and not R["tldr"].startswith(label):  # no-reading cases (k < 2) still name the design
        R["tldr"] = f"{label}: " + R["tldr"]
    dtag = f"{a.design}_" if a.design else ""
    if a.selftest:
        R["tldr"] = "SELFTEST (synthetic d2 := d1; not a result). " + R["tldr"]
        out = Path(os.environ.get("TMPDIR", "/tmp")) / f"commonstate_selftest_{dtag}{R['created'].replace(':', '')}"
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        out = OUT / f"commonstate_{dtag}{R['created'].replace(':', '').replace('-', '')}"
    out.with_suffix(".json").write_text(json.dumps(R, indent=1, default=str))
    write_md(R, out.with_suffix(".md"))
    print(out.with_suffix(".md"))
    print(R["tldr"])


if __name__ == "__main__":
    main()
