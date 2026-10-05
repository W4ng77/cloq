"""Takeover-window panel tw-v1: frozen analysis (docs/insights/TAKEOVER_WINDOW_PROTOCOL.md §7-§9 + Amendment 1 §11). EXPLORATORY.
Per cell (q8 gptq_w4_d1, spinquant_w4a4), x in {B,Q}, L in {0,1,4,inf}: Y_{x,L}, Delta_L, V_{x,L}, R_{x,L}, DeltaDelta, rescue/damage, V_{x,L}-V_{x,L'},
short-window-only changes, transitions, handback / overflow / n_B / BF16 tokens. All-state primary; subsets E_{x,4} (x curve, every L), E_{x,L}
(each V/R), E_{B,L}&E_{Q,L}, E_{B,4}&E_{Q,4} (Delta). t over blocks primary, block and crossed task x block bootstrap alongside (analyze_dev.Boot).
Endpoints L = 0 / inf: analyze_newmethod.load_tau2 (A6 + A7), never imputed; a repro mismatch (Amendment 3: not an error or not-comparable record) in a (cell, block) masks its endpoint-dependent
contrasts (§8); quarantined suffixes (§11.4) leave the main analysis (sensitivity only). Reading text is mechanical (§9, §11.3). No holdout.
Estimands and reporting: takeover_report.py; synthetic selftest: analyze_takeover_selftest.py.
usage: python analysis/fork/analyze_takeover.py [--B 2000] [--selftest]  -> analysis/fork/out/takeover_<UTC>.{json,md}"""
from __future__ import annotations
import argparse, hashlib, importlib, json, sys, time
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import takeover_report as TR  # noqa: E402
NM, AD, ROOT = TR.NM, TR.AD, TR.ROOT
PROTOCOL, TW, OUT = ROOT / "docs/insights/TAKEOVER_WINDOW_PROTOCOL.md", ROOT / "analysis/fork/takeover", ROOT / "analysis/fork/out"
PROTOCOL_PREFIX_SHA256 = "75bf7c3557c63d7b8e1cf9026447ffce2a24a6d398501495c82c86daeb009750"  # sections 1-11 as committed in 560d717
MANIFEST, MANIFEST_SHA256 = "manifests/fork/takeover_window_v1.json", "396e3b35f4eaea15359e6c5e13b85e66218711bdeee2fe5da4cb8c05c428501d"
ROWS_SHA = {3: "119d01d4c6f854ad45df5240fb4283712c11b24037239034b75de4b70a3bc602", 6: "b8c607fe2b05422e6d2f0e1c56f4dd10856bb2129c77c78b51afe4a1ce9e3c6c"}
DEADLINE_UNIX = 1791259200  # 2026-10-05 21:00 PDT (§6, §11.5)
sh = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731
jl = lambda p: [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]  # noqa: E731
SCRIPTS = tuple(Path(__file__).with_name(n) for n in ("analyze_takeover.py", "takeover_report.py", "analyze_takeover_selftest.py"))

def guard() -> dict:
    """Sections 1-11 must hash to the frozen value and an appended amendment must record the sha256 of every script file."""
    txt, me = PROTOCOL.read_bytes(), [sh(p.read_bytes()) for p in SCRIPTS]
    i = txt.find(b"\n## 12.")
    if sh(txt if i < 0 else txt[:i].rstrip(b"-\n") + b"\n") != PROTOCOL_PREFIX_SHA256 or not all(m.encode() in txt for m in me):
        raise SystemExit(f"analyze_takeover: protocol sections 1-11 changed, or script sha256 {me} not recorded by an amendment")
    if sh((ROOT / MANIFEST).read_bytes()) != MANIFEST_SHA256:
        raise SystemExit("analyze_takeover: manifest sha256 differs from the frozen value")
    return {"protocol_sha256": sh(txt), "script_sha256": me, "manifest_sha256": MANIFEST_SHA256}


def repro_kind(v: dict) -> str:
    """Amendment 3: ok / mismatch (signature diff or noop_check fail) / error (re-run raised: infrastructure, §10) / not_comparable."""
    return "ok" if v.get("ok") is True else "not_comparable" if v.get("ok") is None else "error" if "why" in v and "differs" not in v else "mismatch"


def load_windows(d: Path, keys: set) -> tuple[dict, dict]:
    """One panel (cell, block): window records by state_key (A6 applied to window errors) and the block status."""
    if not (d / "window_summary.json").exists():
        return {}, {"status": "not finished"}
    s, rows, out = json.loads((d / "window_summary.json").read_text()), {r["state_key"]: r for r in jl(d / "window_rows.jsonl")}, {}
    inv = [f"{k}:{x}" for k, r in rows.items() for x, v in (r.get("windows") or {}).items() if False in (v.get("pattern_ok"), v.get("counter_ok"))]
    inv += [f"{k}:repro {a}" for k, r in rows.items() for a, v in (r.get("repro") or {}).items() if v.get("L") == 0 and v.get("window_counter_ok") is False]  # §5.5
    srv = bool(s.get("server_expect_ok")) and bool(s.get("src_ok")) and all(all(v.values()) for v in s["server_expect_ok"].values()) and all(s["src_ok"].values())
    rep = Counter(repro_kind(v) for r in rows.values() for v in (r.get("repro") or {}).values())
    end = (s.get("throughput") or {}).get("jobs_end_unix")
    info = {"status": "ok", "invalid_pattern_or_counter": inv[:20], "server_and_src_ok": srv, "jobs_end_unix": end, "deadline_unix": DEADLINE_UNIX,
            **{f"repro_{k}": rep[k] for k in ("ok", "mismatch", "error", "not_comparable")}, "endpoint_accepted": rep["mismatch"] == 0 and rep["ok"] > 0,
            "n_E_handback_mismatch": s.get("n_E_handback_mismatch"), "overflow": s.get("overflow")}
    if inv or not srv:  # §8: pattern_ok / counter_ok false on any suffix (L = 0 endpoint re-runs included) invalidates the task output
        return {}, {**info, "status": "task output invalid (pattern/counter or server identity, §8)"}
    if end is None or end > DEADLINE_UNIX:  # §6: only blocks complete at the deadline enter
        return {}, {**info, "status": "not complete at the deadline (§6)"}
    for k in keys & set(rows):
        ws, br = {}, None
        for xl, v in (rows[k].get("windows") or {}).items():
            v = dict(v)
            if v.get("Y") is None:  # a window error: A6 (agent-output signature) is Y = 0, anything else stays missing
                br = br if br is not None else TR.branches(d, k)
                c = NM.a6_class(br.get(f"W_{xl}"))
                v["Y"], v["a6"] = (0, c[1]) if c[0] == "agent_output" else (None, None)
            ws[xl] = v
        out[k] = {**rows[k], "windows": ws, "_dir": d}
    return out, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=AD.B_BOOT)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:  # synthetic data only (analyze_takeover_selftest.py); reads no fork output
        return importlib.import_module("analyze_takeover_selftest").run(sys.modules[__name__], a.B)
    g, man = guard(), json.loads((ROOT / MANIFEST).read_text())
    dec = json.loads((TW / "scale_decision.json").read_text())
    blocks = set(dec["blocks"])
    rs = sh(json.dumps(sorted([r["state_key"], r["block"], r["domain"], r["task_id"], r["t"], r["source_run"]] for r in man["rows"] if r["block"] in blocks), separators=(",", ":")).encode())
    if len(blocks) not in ROWS_SHA or rs != ROWS_SHA[len(blocks)]:  # NO PANEL, or a row list other than the frozen one (make_tasks_takeover.rows_sha)
        raise SystemExit(f"analyze_takeover: blocks {sorted(blocks)} / row-list sha {rs[:12]} not frozen")
    raw, tlog = NM.load_tau2("q8", json.loads((ROOT / NM.MANIFESTS["q8"][0]).read_text()), blocks=blocks, only=set(TR.CELLS), a6=True, recovery=True)
    per, binfo = {}, {}
    for c in TR.CELLS:
        units, recs = [], []
        for blk in sorted(blocks):
            eps = [u for u in raw.get(c, []) if u["block"] == blk]
            ws, info = binfo[f"{c}/{blk}"] = load_windows(NM.no_holdout(TW / f"q8_{c}" / blk), {u["state_key"] for u in eps})
            units += [{**TR.build(u, ws.get(u["state_key"]), info.get("endpoint_accepted") is True), "_ep": u, "_w": ws.get(u["state_key"])} for u in eps] if ws else []
            recs += [{**w, "block": blk} for w in ws.values()]
        per[c] = (units, recs)
    binfo = {k: v[1] for k, v in binfo.items()}
    R = {"guard": g, "B": a.B, "scale_decision": dec, "blocks_info": binfo, "endpoint_log": tlog, **TR.analyse(per, a.B)}
    R["design_incomplete"] = sorted(k for k, v in binfo.items() if v["status"] != "ok")
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"takeover_{time.strftime('%Y%m%dT%H%MZ', time.gmtime())}"
    p.with_suffix(".json").write_text(json.dumps(R, indent=1, default=lambda o: None))
    md = [f"# Takeover window tw-v1 ({p.name})", "", TR.LABEL, "", f"Scale decision: blocks {dec['blocks']}; incomplete (cell/block): {R['design_incomplete'] or 'none'}", ""]
    md += [f"Scale decision record (verbatim, §9): `{json.dumps(dec, sort_keys=True)}`", "", "Blocks (status, repro ok/mismatch/error/not comparable):"]
    md += [f"- {k}: {v['status']}, repro {[v.get('repro_' + x) for x in ('ok', 'mismatch', 'error', 'not_comparable')]}, endpoints accepted {v.get('endpoint_accepted')}" for k, v in binfo.items()]
    md += ["", "Handback per window (§9: buckets, E share, n_B, BF16 decisions):"] + [f"- {c} {xl}: {json.dumps(h, sort_keys=True)}" for c in TR.CELLS
                                                                                    for xl, h in (R["cells"][c]["handback"] or {}).items()] + ["", "Reading:"]
    p.with_suffix(".md").write_text("\n".join(md + [f"- {s}" for c in TR.CELLS for s in R["cells"][c]["reading"]]) + "\n")
    print(p.with_suffix(".md").read_text())


if __name__ == "__main__":
    main()
