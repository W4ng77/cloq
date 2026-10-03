"""m24 phase-1 INTERIM report (W100s). Inputs: the two analyze_newmethod.py runs
  m24: --model m24 --blocks f01,f02,f03                        (protocol run; phase 2 f04-f06 still running)
  q8 : --model q8 --blocks f01,f02,f03 --cells gptq_w4_d1,awq_w4,awq_w4_d1   (W4 reference cells only; new q8 cells never opened)
It rebuilds the same units with the same functions, ASSERTS that the protocol numbers are reproduced exactly, and adds only
what the protocol run does not print: G-H (= Y_BQ - Y_QB, analyze_ghf.add_E / ext_r2 GmH) with the same interval machinery,
per-block values, the M1 point estimate on the common block(s) (no interval: §7 gives none for k < 2), and a descriptive q8
view on the m24 83-task set. q8 and m24 are never pooled. Local fidelity (§9) is reported pending while the m24 score outputs
have n_ok < n_rows - n_missing.
usage: python analysis/fork/m24_interim_report.py <m24 run json> <q8 run json> [--reading FILE] [--dry]
-> analysis/fork/out/m24_interim_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_sp = importlib.util.spec_from_file_location("analyze_newmethod", ROOT / "analysis/fork/analyze_newmethod.py")
AN = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(AN)
AD, AE = AN.AD, AN.AE
P1 = {"f01", "f02", "f03"}
Q8REF = {"gptq_w4_d1", "awq_w4", "awq_w4_d1"}
KEYS_DIV = ("G", "H", "F", "GmH", "I", "D_cc", "M", "offdiag")
AUDIT = "analysis/fork/out/m24_budget_audit_20261003T1354Z.md"
AUDIT_ADMITTED = {"rtn_w4": ["f03"], "gptq_w4_d1": ["f02", "f03"]}
rt = lambda x: json.loads(json.dumps(x, default=str))  # noqa: E731  (compare as the protocol run serialised it)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731


def cell(units: list, B: int, proto: dict | None) -> dict:
    """AN.tau2_cell (every field the protocol run printed asserted equal) + GmH, all states (task_mean) and non-exact
    (ratio), same Boot, same seed."""
    r = AN.tau2_cell(units, B)
    if proto is not None:
        p = {k: v for k, v in proto.items() if k != "label"}
        assert rt({k: r[k] for k in p}) == p, "protocol numbers not reproduced"
    boot = AN.boot_for(units, B)
    r["all_states_pp"]["GmH"] = AD.summarise(*boot.task_mean(*boot.arrays(units, "GmH")), boot=boot)
    ne = [u for u in units if not u["exact"]]
    if ne and "nonexact_pp" in r:
        r["nonexact_pp"]["GmH"] = AD.summarise(*boot.ratio(*boot.arrays(ne, "GmH")), boot=boot)
    r["n_nonexact"] = len(ne)
    return r


def per_block(units: list) -> dict:
    m = lambda xs, k: round(100 * float(np.mean([u["E"][k] for u in xs])), 2) if xs else None  # noqa: E731
    out = {}
    for b in sorted({u["block"] for u in units}):
        us = [u for u in units if u["block"] == b]
        ne = [u for u in us if not u["exact"]]
        out[b] = {"n": len(us), "n_nonexact": len(ne), "all": {k: m(us, k) for k in KEYS_DIV}, "div": {k: m(ne, k) for k in KEYS_DIV}}
    return out


def pair_desc(a: list, b: list) -> dict:
    ib = {(u["task"], u["block"]): u for u in b}
    pr = [(u, ib[(u["task"], u["block"])]) for u in a if (u["task"], u["block"]) in ib]
    assert all(x["state_key"] == y["state_key"] for x, y in pr)
    return {"blocks": sorted({x["block"] for x, _ in pr}), "n_states": len(pr),
            **{f"d_{k}_pp": round(100 * float(np.mean([x["E"][k] - y["E"][k] for x, y in pr])), 2) for k in ("D_cc", "G", "GmH", "M", "M_cc")},
            "label": "DESCRIPTIVE point estimate only: protocol §7 t over block-mean differences needs >= 2 common blocks; no fallback"}


def bfcl(model: str, man: dict, only: set | None, proto: dict, B: int) -> dict:
    bc, _ = AN.load_bfcl(model, man, only)
    st = AN.bfcl_stats(bc, B, AN.CONTRASTS[model])
    assert rt(st) == {k: v for k, v in proto.items() if k != "log"}, "BFCL protocol numbers not reproduced"
    strata = defaultdict(set)
    for us in bc.values():
        for u in us:
            strata[u["stratum"]].add(u["task"])
    boot = AE.StratBoot({s: sorted(v) for s, v in strata.items()}, B=B)
    for c, us in bc.items():
        div = [u for u in us if "excluded" not in u and u["div"]]
        st["cells"][c]["cond_div_pp"]["GmH"] = AD.summarise(*boot.mean(*boot.arrays(div, "GmH")))
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("m24_json")
    ap.add_argument("q8_json")
    ap.add_argument("--reading", help="text file: the hand-written reading, inserted verbatim")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    PM, PQ = json.loads(Path(a.m24_json).read_text()), json.loads(Path(a.q8_json).read_text())
    for P, want in ((PM, None), (PQ, Q8REF)):
        assert P["script_sha256"] == sha(ROOT / "analysis/fork/analyze_newmethod.py") and set(P["restrict"]["blocks"]) == P1
        assert (P["restrict"]["cells"] == "all") if want is None else set(P["restrict"]["cells"]) == want
    B = PM["B"]
    gm, gq = AN.guard("m24"), AN.guard("q8")
    man, manq = json.loads((ROOT / gm["manifest"]).read_text()), json.loads((ROOT / gq["manifest"]).read_text())
    pop, exc = AN.population("m24", man)
    popq, _ = AN.population("q8", manq)
    assert pop <= popq
    raw, _ = AN.load_tau2("m24", man, P1, None)
    cells, info, cc, avail = AN.apply_population(raw, pop, len(pop))
    assert rt(info) == PM["tau2"]["blocks"]
    admitted = {c: sorted(b for b, x in v.items() if x["admitted"]) for c, v in info.items()}
    assert admitted == AUDIT_ADMITTED, admitted
    R = {"label": "INTERIM: m24 phase 1 only (f01-f03); phase 2 (f04-f06) is running. Not the protocol's final m24 analysis.",
         "utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "script_sha256": sha(Path(__file__)),
         "git": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
         "inputs": {p: sha(ROOT / p) for p in (str(Path(a.m24_json).resolve().relative_to(ROOT)), str(Path(a.q8_json).resolve().relative_to(ROOT)),
                                                AUDIT, "analysis/fork/newmethod/expansion_m24.json")},
         "guard": {"m24": gm, "q8": gq}, "B": B, "seed": AD.SEED,
         "population": {"n_tasks": len(pop), "excluded_by_mask": exc, "label": "conditional 83-task population (A3)"},
         "admission": {"blocks": info, "admitted": admitted, "audit": AUDIT, "agrees_with_audit": True}}
    m = R["m24"] = {"primary": {}, "per_block": {}, "complete_case": {}, "available_rows": {}, "per_block_available": {}}
    for c, us in sorted(cells.items()):
        m["primary"][c] = cell(us, B, PM["tau2"]["cells"][c])
        m["per_block"][c] = per_block(us)
        m["complete_case"][c] = cell(cc[c], B, PM["tau2"]["complete_case"][c])
        m["available_rows"][c] = cell(avail[c], B, PM["tau2"]["sensitivity_available_rows"][c])
        m["per_block_available"][c] = per_block(avail[c])
    m["M1"] = {"primary": PM["tau2"]["contrasts"]["M1"], "common_block_descriptive": pair_desc(cells["gptq_w4_d1"], cells["rtn_w4"]),
               "available_rows_sensitivity": PM["tau2"]["sensitivity_available_rows_contrasts"]["M1"],
               "available_rows_descriptive": pair_desc(avail["gptq_w4_d1"], avail["rtn_w4"])}
    m["bfcl"] = bfcl("m24", man, None, PM["bfcl"], B)
    m["bfcl_log"] = {k: PM["bfcl"]["log"].get(k) for k in ("quarantined", "incomplete", "coverage")}
    nm = ROOT / "analysis/fork/newmethod/token_scores"
    sc = {f"{c}/{b}": {k: json.loads((nm / f"m24_{c}" / b / "score_summary.json").read_text()).get(k) for k in ("n_rows", "n_ok", "n_missing")}
          for c in AN.M24_CELLS for b in sorted(P1) if (nm / f"m24_{c}" / b / "score_summary.json").exists()}
    ok = len(sc) == 6 and all(v["n_ok"] >= 83 for v in sc.values())
    m["fidelity"] = {"status": "available" if ok else "PENDING: m24 score tasks requeued after the W100o render fix; §9 not reported",
                     "score_summaries": sc, **({"protocol": PM["fidelity"]} if ok else {})}
    rawq, _ = AN.load_tau2("q8", manq, P1, Q8REF)
    cq, infoq, _, _ = AN.apply_population(rawq, popq, len(popq))
    assert rt(infoq) == PQ["tau2"]["blocks"]
    R["q8_reference"] = {"label": "q8 (Qwen3-8B) W4 reference cells, same protocol (U2B states on q8's own BF16 trajectory, 85 tasks, "
                                  "f01-f03). Never pooled with m24; different model, states and population (A3.2).",
                         "tau2": {c: cell(us, B, PQ["tau2"]["cells"][c]) for c, us in sorted(cq.items())},
                         "tau2_on_m24_83_tasks_descriptive": {c: cell([u for u in us if u["task"] in pop], B, None) for c, us in sorted(cq.items())},
                         "bfcl": bfcl("q8", manq, Q8REF, PQ["bfcl"], B)}
    R["paper_context"] = {"source": "analysis/fork/out/ghf_multiplicity_20261001T225727Z.md",
                          "label": "first-divergence states (dev forks, 20 blocks), NOT the U2B panel: context only",
                          "q8_GmH_div_pp": {"gptq_w4_d1": "+2.9 [+1.0, +4.8] t, p_holm .013", "awq_w4": "+3.4 [+1.3, +5.5] t, p_holm .012"}}
    R["reading"] = Path(a.reading).read_text().strip() if a.reading else None
    if a.dry:
        print(json.dumps(R, indent=1, default=str)[:200000])
        return
    jp = ROOT / "analysis/fork/out" / f"m24_interim_{R['utc']}.json"
    jp.write_text(json.dumps(R, indent=1, default=str))
    jp.with_suffix(".md").write_text(markdown(R, jp))
    print("wrote", jp.relative_to(ROOT))


def markdown(R: dict, jp: Path) -> str:
    from m24_interim_md import render  # same directory; kept separate to keep this file short
    return render(R, jp.relative_to(ROOT))


if __name__ == "__main__":
    main()
