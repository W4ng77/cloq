"""Key-order perturbation analysis (ko-v1, docs/insights/KEYORDER_PERTURB_PROTOCOL.md §5-§7 + amendment 2026-10-05b). Exploratory.

Units: q8 GPTQ-W4 d1 Bank P (85 tasks x 20 blocks) via analyze_dev's loader, quarantine, split guard, W70 strict and W78 panel
block rules. Eligible: the 300 frozen states of manifests/fork/keyorder_v1.json. Swap X in {K, B}: r, d, M = r + d, G = r - d
of Y_XQ vs Y_QQ (Y_KQ from analysis/fork/keyorder/q8_gptq_w4_d1/<g>/branches, Y_BQ the Bank P branch). Identical units for both
swaps: a ko-v1 task with any failed no-op / KQ acceptance / shadow / state / server / manifest check is quarantined whole; a KQ
infrastructure error or missing KQ removes that unit; the strict block rule then drops affected blocks, all for K and B alike.
A KQ context overflow is a valid failure (Y_KQ = 0); before the first continuation only if n_next_k > n_next_q (2026-10-05c). Reported: conditional (ratio over eligible units; crossed over eligible
tasks), full-pool contribution (non-eligible = 0; crossed over all 85 tasks), share of the BF16 swap's full-pool M on the same
pool and draws, coverage, joint flips. Paired draws, B = 2000, seed 20261001; `widest` = union of block / t / crossed (§6).
Synthetic selftest: analyze_keyorder_selftest.py. usage: analyze_keyorder.py [--snapshot S] [--B 2000] [--complete-case] | --selftest   -> analysis/fork/out/keyorder_<UTC>.{json,md}
"""
from __future__ import annotations
import argparse, copy, importlib, importlib.util, json, sys, time
from collections import Counter
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_sp = importlib.util.spec_from_file_location("analyze_dev", ROOT / "analysis/fork/analyze_dev.py")
AD = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(AD)
_sp = importlib.util.spec_from_file_location("analyze_newmethod", ROOT / "analysis/fork/analyze_newmethod.py")
NM = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(NM)
MAN, PROTO = ROOT / "manifests/fork/keyorder_v1.json", ROOT / "docs/insights/KEYORDER_PERTURB_PROTOCOL.md"
MAN_SHA = "cbf12188ca485c03ae600f484af43f0bd22c29dcc19d8fda4436a1a1870d28ce"
SNAP = ROOT / "analysis/insights/iter_3/out/snapshot_auto_20261001T0600Z.json"  # snapshot of dev_all_20261001T070326Z (M = 17.9)
GROUPS, BANKP, KO = ("g1", "g2", "g3", "g4"), "analysis/fork/dev/q8_gptq_w4_d1", "analysis/fork/keyorder/q8_gptq_w4_d1"
S4 = ("rescue", "damage", "M", "G")
KEYS = [f"{s}_{x}" for x in ("K", "B", "KmB") for s in S4]
grp = lambda r: r["group"].rsplit("/", 1)[1]


def sw(yx: int, yq: int) -> dict:
    return {"rescue": int(yx > yq), "damage": int(yx < yq), "M": int(yx != yq), "G": yx - yq}


def ko_group(kdir: Path, el: dict) -> dict:
    """Outcome-blind acceptance of one ko-v1 task (rows + summary), then Y_KQ per accepted state. el: sid -> manifest row."""
    sm, rp = kdir / "keyorder_summary.json", kdir / "keyorder_rows.jsonl"
    if not sm.exists() or not rp.exists():
        return {"missing": True, "quarantine": [], "Y": {}, "excl": {s: "ko-v1 task missing" for s in el}, "term": {}}
    s, by = json.loads(sm.read_text()), {r["state_id"]: r for r in (json.loads(x) for x in rp.read_text().splitlines() if x.strip())}
    q = [] if s.get("manifest_sha256") == MAN_SHA else ["manifest sha"]
    q += [f"server {k}" for k, v in (s.get("server_expect_ok") or {}).items() if not all(v.values())]
    Y, excl, term, a6, err = {}, {}, Counter(), {}, Counter()
    for sid in el:
        r = by.get(sid)
        if r is None or "KQ" not in r and "missing_reason" not in r:
            excl[sid] = "KQ missing / infrastructure error"; continue
        if "missing_reason" in r or not all(r["state_identical"].values()):
            q.append(f"{sid} state differs"); continue
        sh = r.get("shadow")
        if (s.get("spec") or {}).get("shadow_check", True) and not (sh and sh.get("identical") and sh.get("completion_ids_ok")):
            q.append(f"{sid} shadow")
        if r.get("noop_sample") and not (r.get("QQ_noop") or {}).get("ok"):
            q.append(f"{sid} QQ no-op")
        if "error" in r["KQ"]:  # primary (§4): leaves the denominator; A6 agent-output errors also feed a Y = 0 sensitivity
            bp = kdir / "branches" / f"{sid}.json"
            cls, sig = NM.a6_class(json.loads(bp.read_text()).get("KQ") if bp.exists() else None, plus=True, domain=el[sid]["domain"])
            a6[sid] = sig if cls == "agent_output" else None
            excl[sid] = "KQ infrastructure error"; err[f"{cls}:{sig}"] += 1; continue
        ofc = r["KQ"].get("overflow_at") == "before_first_continuation" and not (el[sid].get("n_next_k") or 0) > (el[sid].get("n_next_q") or 0)
        if not r["KQ"]["ok"] or ofc:  # 2026-10-05c: a first-continuation overflow is consistent only with a longer transformed prompt
            q.append(f"{sid} KQ acceptance" + (" (overflow before the first continuation, n_next_k <= n_next_q)" if ofc else "")); continue
        br = json.loads((kdir / "branches" / f"{sid}.json").read_text())["KQ"]
        assert br.get("state_id") == sid, (sid, br.get("state_id"))
        Y[sid] = AD.success(el[sid]["domain"], br)  # overflow: db_match False, infrastructure_error -> Y = 0 (W10/W70)
        ovf = br.get("infra_cause") == "context_overflow"
        term["context_overflow" if ovf else br.get("termination_reason")] += 1
        term.update([f"overflow_{r['KQ'].get('overflow_at', '?')}"] if ovf else [])
    return {"missing": False, "quarantine": q, "Y": Y, "excl": excl, "term": term, "a6": {k: v for k, v in a6.items() if v}, "kq_errors": dict(err)}


def frame(units: list[dict], kos: dict, el: dict, strict: bool = True) -> tuple[list, dict]:
    """ko-v1 exclusions on the Bank P units (both swaps), then the W70 / W78 block rules once; per-unit E."""
    for u in units:
        if u.get("div") and u.get("state_id") in el and "excluded" not in u:
            k = kos[grp(el[u["state_id"]])]
            if k["quarantine"] or u["state_id"] in k["excl"]:
                u["excluded"] = "ko-v1 task quarantined" if k["quarantine"] else k["excl"][u["state_id"]]
    inc, part = AD.mark_incomplete_blocks(units, "dev", strict=strict), AD.mark_partial_panel_blocks(units, "dev")
    ok = [u for u in units if "excluded" not in u]
    for u in ok:
        u["elig"], yq = bool(u.get("div")) and u.get("state_id") in el, u["Y"]["QQ"]
        u["E"] = {key: 0 for key in KEYS}
        if u["elig"]:
            k, b = sw(kos[grp(el[u["state_id"]])]["Y"][u["state_id"]], yq), sw(u["Y"]["BQ"], yq)
            u["E"] = {**{f"{s}_K": k[s] for s in S4}, **{f"{s}_B": b[s] for s in S4}, **{f"{s}_KmB": k[s] - b[s] for s in S4}}
        u["E"]["M_B_all"] = sw(u["Y"]["BQ"], yq)["M"] if u.get("div") else 0
    return ok, {"incomplete_blocks": inc, "partial_panel_blocks": part, "excluded": dict(Counter(u["excluded"] for u in units if "excluded" in u))}


def boot_of(us: list[dict], B: int):
    ts = sorted({u["task"] for u in us})
    return AD.Boot(ts, {t: sorted({u["block"] for u in us if u["task"] == t}) for t in ts}, B=B)


def estimate(ok: list[dict], B: int) -> dict:
    eu = [u for u in ok if u["elig"]]
    bc, bf = boot_of(eu, B), boot_of(ok, B)  # conditional: crossed over eligible tasks; full pool: crossed over all tasks
    cond = {k: AD.summarise(*bc.ratio(*bc.arrays(eu, k))) for k in KEYS}
    dr = {k: bf.task_mean(*bf.arrays(ok, k)) for k in KEYS + ["M_B_all"]}
    full = {k: AD.summarise(*v) for k, v in dr.items()}
    for x in ("K", "B"):  # share of the BF16 swap's full-pool M carried by swap x on eligible units (same pool and draws)
        (a, da), (b, db) = dr[f"M_{x}"], dr["M_B_all"]
        with np.errstate(divide="ignore", invalid="ignore"):
            full[f"M_{x}_share_of_M_B_all"] = AD.summarise(a / b, np.asarray(da) / np.asarray(db), crossed=(da.crossed_pt / db.crossed_pt, da.crossed / db.crossed))
    # conditional: the t interval is over per-block ratios (mean of block proportions, 10-18 eligible states per block), a
    # different estimand from the pooled ratio; it is reported as auxiliary and never enters a reading (2026-10-05d). Full
    # pool: every strict block has all 85 tasks, so the block mean equals the pooled mean and t stays in the union.
    for v, ks in [*((v, ("block_boot_ci95", "crossed_ci95")) for v in cond.values()),
                  *((v, ("block_boot_ci95", "t_ci95", "crossed_ci95")) for v in full.values())]:
        iv = [v[k] for k in ks if v.get(k)]
        v["widest"] = [min(i[0] for i in iv), max(i[1] for i in iv)]
    for v in cond.values():
        if v.get("t_ci95"):
            v["aux_t_mean_of_block_ratios"] = v.pop("t_ci95")
    joint = Counter(f"{dn}:" + {(1, 1): "both", (1, 0): "K_only", (0, 1): "B_only", (0, 0): "neither"}[(u["E"][f"{dn}_K"], u["E"][f"{dn}_B"])]
                    for u in eu for dn in ("rescue", "damage"))
    mk, mkb = cond["M_K"]["widest"], cond["M_KmB"]["widest"]
    rules = {"K_turnover_excludes_0": mk[0] > 0, "M_K_minus_M_B_upper_below_0": mkb[1] < 0, "M_K_minus_M_B_lower_above_0": mkb[0] > 0, "basis": "conditional: widest of block bootstrap and crossed (pooled ratio); full pool: widest of block, t, crossed (§6, 2026-10-05d)",
             "reading": ("some consequences arise without changing the tool operation" if mk[0] > 0 else "K turnover not distinguished from 0")
             + ("; on these states the representation change moves outcomes less than the BF16 replacement" if mkb[1] < 0
                else "; K turnover above B (lower bound > 0; outside the §7 readings, bounds reported)" if mkb[0] > 0
                else "; K and B turnover not distinguished (no equivalence margin, equivalence never claimed)")}
    dom = lambda d: {"eligible": sum(u["domain"] == d for u in eu), "divergent": sum(bool(u.get("div")) and u["domain"] == d for u in ok),
                     "units": sum(u["domain"] == d for u in ok)}
    return {"conditional_pct": cond, "full_pool_contribution_pct": full, "joint_flips": dict(joint), "rules": rules, "n_units": len(ok),
            "n_tasks": len({u["task"] for u in ok}), "n_blocks": len({u["block"] for u in ok}), "n_eligible_units": len(eu),
            "n_eligible_tasks": len({u["task"] for u in eu}), "n_divergent": sum(bool(u.get("div")) for u in ok),
            "coverage": {d: dom(d) for d in ("airline", "retail")}}


def run(units: list[dict], kroot: Path, el: dict, B: int, strict: bool = True) -> dict:
    kos = {g: ko_group(kroot / g, {s: r for s, r in el.items() if grp(r) == g}) for g in GROUPS}
    sens = None
    if any(k.get("a6") for k in kos.values()):  # 2026-10-05d sensitivity, never the primary: A6 KQ errors score Y_KQ = 0
        k2 = {g: {**k, "Y": {**k["Y"], **{s: 0 for s in k.get("a6", {})}}, "excl": {s: v for s, v in k["excl"].items() if s not in k.get("a6", {})}}
              for g, k in kos.items()}
        e2 = estimate(frame(copy.deepcopy(units), k2, el, strict)[0], B)
        sens = {"n_a6": sum(len(k.get("a6", {})) for k in kos.values()), "M_K": e2["conditional_pct"]["M_K"], "M_KmB": e2["conditional_pct"]["M_KmB"], "rules": e2["rules"]}
    ok, fr = frame(units, kos, el, strict)
    return {"estimate": estimate(ok, B), "frame": fr, "sensitivity_a6_y0": sens, "kq_errors": dict(sum((Counter(k.get("kq_errors", {})) for k in kos.values()), Counter())), "quarantined": {g: k["quarantine"][:20] for g, k in kos.items() if k["quarantine"]},
            "missing": [g for g, k in kos.items() if k["missing"]],
            "kq_termination": dict(sum((Counter(k["term"]) for k in kos.values() if not k["quarantine"]), Counter()))}


def markdown(R: dict) -> str:
    e, p, c = R["estimate"], R["estimate"]["full_pool_contribution_pct"], R["estimate"]["conditional_pct"]
    f = lambda s: f"{s['est']:.1f} [{s['widest'][0]:.1f}, {s['widest'][1]:.1f}]"
    L = ["# Key-order perturbation ko-v1 (exploratory control)\n", f"TL;DR {e['rules']['reading']}. Eligible {e['n_eligible_units']} of {e['n_divergent']} "
         f"divergent states, {e['n_units']} units = {e['n_tasks']} tasks x {e['n_blocks']} blocks, {e['n_eligible_tasks']} eligible tasks. "
         "Intervals: conditional = widest of block bootstrap and crossed on the pooled ratio (t over block ratios is auxiliary, JSON only); full pool = widest of block, t, crossed.\n", "| stat | K cond % | B cond % | K-B cond pp | K pool pp | B pool pp | K-B pool pp |", "|---|---|---|---|---|---|---|"]
    L += [f"| {s} | " + " | ".join(f(t[f"{s}_{x}"]) for t in (c, p) for x in ("K", "B", "KmB")) + " |" for s in S4]
    L += [f"\nBF16 swap full-pool M on this pool: {f(p['M_B_all'])}. Share carried by eligible states (x100, same pool and draws): "
          f"B {f(p['M_B_share_of_M_B_all'])}, K {f(p['M_K_share_of_M_B_all'])}. A conditional share is never compared with it.",
          f"\nJoint flips {e['joint_flips']}. Coverage {e['coverage']}. KQ terminations {R['kq_termination']}.",
          f"\nKQ errors by class {R['kq_errors']}; A6 Y = 0 sensitivity (not primary): {R['sensitivity_a6_y0'] and {k: R['sensitivity_a6_y0'][k] for k in ('n_a6', 'rules')}}.",
          f"\nExcluded {R['frame']['excluded']}; quarantined ko-v1 tasks {R['quarantined']}; missing ko-v1 tasks {R['missing']}.",
          f"\nmanifest {MAN_SHA[:16]}, script {R['script_sha256'][:16]}, protocol {R['protocol_sha256'][:16]}, snapshot {R['snapshot']}."]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", default=str(SNAP)); ap.add_argument("--B", type=int, default=AD.B_BOOT)
    ap.add_argument("--complete-case", action="store_true"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).parent))
    if a.selftest:
        return importlib.import_module("analyze_keyorder_selftest").run(sys.modules[__name__], min(a.B, 300))
    if AD.sha256(MAN) != MAN_SHA:
        raise SystemExit("analyze_keyorder: manifest differs from the frozen ko-v1 manifest")
    el, snap, cache = {r["state_id"]: r for r in json.loads(MAN.read_text())["rows"] if r["eligible"]}, json.load(open(a.snapshot)), {}
    Ls = [AD.load_dir(ROOT / BANKP / g, snap, cache) for g in GROUPS]
    for u in (u for L in Ls if L["quarantined"] for u in L["units"]):
        u.setdefault("excluded", "quarantined fork task (QQ no-op mismatch)")
    units, _ = AD.dedupe_units([u for L in Ls for u in L["units"]])
    AD.split_guard(units, "dev", "analyze_keyorder")
    R = run(units, ROOT / KO, el, a.B, strict=not a.complete_case)
    R.update({"protocol": "ko-v1", "protocol_sha256": AD.sha256(PROTO), "script_sha256": AD.sha256(__file__), "manifest_sha256": MAN_SHA,
              "snapshot": AD.sha256(a.snapshot)[:16], "bank_p_quarantined": [L["dir"] for L in Ls if L["quarantined"]], "complete_case": a.complete_case,
              "bank_p_noop": {"n": sum(len(L["noop"]) for L in Ls), "n_pass": sum(x["ok"] for L in Ls for x in L["noop"])}})
    jp = AD.OUT / f"keyorder_{'cc_' if a.complete_case else ''}{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    jp.write_text(json.dumps(R, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    jp.with_suffix(".md").write_text(markdown(R)); print(f"analyze_keyorder: wrote {jp.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
