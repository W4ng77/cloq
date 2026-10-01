"""Simulator robustness control for Bank U text-structure flips (W90; manifest manifests/fork/simctrl_v1.json).

Pre-specified report (the manifest's analysis_plan; v2 amendment: R = 3 independent Sonnet replicates per arm; no pass threshold):
  per unit and replicate r: D_r = Y'_BQ,r - Y'_QQ,r; replicate-mean flip indicator Dbar = mean_r D_r. The primary fates below
  use sign(Dbar) against the original direction; the per-replicate distribution and the within-simulator variability
  (share of units whose replicates disagree, per arm) are reported alongside.
  flips    (original Bank U f01 class (ii) outcome changes, M = 1): with the Sonnet 5.5 user, M' = |Y'_BQ - Y'_QQ|;
           retained = M' = 1 in the original direction (rescue: BQ succeeds, QQ fails; damage: the reverse),
           reversed = M' = 1 in the opposite direction, vanished = M' = 0 (both succeed / both fail).
  controls (matched class (ii) non-flips, M = 0): newly appearing flips M' = 1 (rescue / damage).
  Groups: all, per model, per sub-bank, per sub-class (ii_talk / ii_act), per original direction (flips).
  Exact (Clopper-Pearson) 95% intervals on the proportions; missing units (any errored arm) are counted, never imputed.
  Paired: per matched pair, flip retained (yes/no) x control newly flips (yes/no).
  Secondary: arm-level agreement Y'_arm == Y_arm per role; termination reasons; Sonnet usage (tokens, cost, request ids).
Scope: robustness of continuations on FIXED histories generated with the old simulator (Qwen3-4B-Instruct-2507); only
the user simulator after the fork state changes. Not a benchmark re-run with a new simulator.

Gate: refuses to run unless analysis/fork/simctrl/gate/gate.json has verdict PASS and the same manifest sha.

usage: python analysis/fork/analyze_simctrl.py                      # real run
       python analysis/fork/analyze_simctrl.py --manifest manifests/fork/simctrl_v3.json --dir analysis/fork/simctrl_relay --tag relay   # W91 relay run
       python analysis/fork/analyze_simctrl.py --dir analysis/fork/simctrl/dry --no-gate --tag dry   # dry run
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import time
from pathlib import Path

from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[2]
MAN = ROOT / "manifests" / "fork" / "simctrl_v2.json"  # W90 amendment: v1 units + R = 3 replicates per arm
OUT = ROOT / "analysis" / "fork" / "out"


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cp(k: int, n: int) -> list:
    if n == 0:
        return [None, None]
    lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
    return [round(lo, 3), round(hi, 3)]


def reps(u: dict, R: int) -> list:
    """[(Y_BQ_r, Y_QQ_r)] for r < R (None where missing). v1-shaped results (keys without '#') count as replicate 0."""
    Y = u.get("Y_sonnet") or {}
    g = lambda a, r: Y.get(f"{a}#{r}", Y.get(a) if r == 0 else None)  # noqa: E731
    return [(g("BQ", r), g("QQ", r)) for r in range(R)]


def fate(D: float, role: str, s: int) -> str:
    if role == "flip":
        return "vanished" if D == 0 else "retained" if (D > 0) == (s > 0) else "reversed"
    return "new_flip" if D != 0 else "stays_non_flip"


def classify(u: dict, R: int = 1) -> dict:
    """Primary outcome (replicate mean) and per-replicate outcomes under the Sonnet user."""
    s = {"rescue": 1, "damage": -1}.get(u.get("direction_orig"), 0)
    rp = reps(u, R)
    per = [None if (bq is None or qq is None) else bq - qq for bq, qq in rp]
    out = {"per_rep_D": per, "per_rep_fate": [None if d is None else fate(d, u["role"], s) for d in per],
           "arm_reps": {"BQ": [x[0] for x in rp], "QQ": [x[1] for x in rp]}}
    if any(d is None for d in per):
        return {"status": "missing", **out}
    Dbar = sum(per) / R
    bq_mean, qq_mean = sum(x[0] for x in rp) / R, sum(x[1] for x in rp) / R
    out.update({"status": "ok", "Dbar": Dbar, "dir_sonnet": "rescue" if Dbar > 0 else "damage" if Dbar < 0 else "none",
                "M_sonnet": int(Dbar != 0), "fate": fate(Dbar, u["role"], s),
                "both": ("both_succeed" if bq_mean == qq_mean == 1 else "both_fail" if bq_mean == qq_mean == 0 else "tie_mixed") if Dbar == 0 else None,
                "n_rep_same": sum(1 for d in per if s and d == s), "n_rep_opp": sum(1 for d in per if s and d == -s),
                "n_rep_zero": sum(1 for d in per if d == 0), "n_rep_nonzero": sum(1 for d in per if d != 0),
                "arm_disagree": {a: len(set(v)) > 1 for a, v in out["arm_reps"].items()}})
    return out


def summarize(g: list[dict], role: str, R: int = 1) -> dict:
    ok = [u for u in g if u["c"]["status"] == "ok"]
    z = collections.Counter(u["c"]["fate"] for u in ok)
    res = {"n": len(g), "n_missing": len(g) - len(ok), "n_ok": len(ok)}
    if role == "flip":
        for f in ("retained", "reversed", "vanished"):
            res[f] = z[f]
            res[f + "_ci95"] = cp(z[f], len(ok))
        res["vanished_both_succeed"] = sum(1 for u in ok if u["c"]["fate"] == "vanished" and u["c"]["both"] == "both_succeed")
        res["vanished_both_fail"] = sum(1 for u in ok if u["c"]["fate"] == "vanished" and u["c"]["both"] == "both_fail")
        res["vanished_tie_mixed"] = sum(1 for u in ok if u["c"]["fate"] == "vanished" and u["c"]["both"] == "tie_mixed")
        res["units_by_n_rep_same_direction"] = {k: sum(1 for u in ok if u["c"]["n_rep_same"] == k) for k in range(R + 1)}
        res["units_by_n_rep_reversed"] = {k: sum(1 for u in ok if u["c"]["n_rep_opp"] == k) for k in range(R + 1)}
        keys = ("retained", "reversed", "vanished")
    else:
        res["new_flips"] = z["new_flip"]
        res["new_flips_ci95"] = cp(z["new_flip"], len(ok))
        res["new_rescue"] = sum(1 for u in ok if u["c"]["dir_sonnet"] == "rescue")
        res["new_damage"] = sum(1 for u in ok if u["c"]["dir_sonnet"] == "damage")
        res["units_by_n_rep_flipping"] = {k: sum(1 for u in ok if u["c"]["n_rep_nonzero"] == k) for k in range(R + 1)}
        keys = ("new_flip", "stays_non_flip")
    # per-replicate distribution (complete replicates of each unit, including units missing another replicate)
    res["per_replicate"] = {}
    for r in range(R):
        fs = [u["c"]["per_rep_fate"][r] for u in g if u["c"]["per_rep_fate"][r] is not None]
        res["per_replicate"][r] = {"n": len(fs), **{k: sum(1 for f in fs if f == k) for k in keys}}
    return res


def variability(units: list[dict], R: int) -> dict:
    out = {}
    for role in ("flip", "control"):
        for arm in ("BQ", "QQ"):
            g = [u for u in units if u["role"] == role and all(y is not None for y in u["c"]["arm_reps"][arm])]
            k = sum(1 for u in g if len(set(u["c"]["arm_reps"][arm])) > 1)
            out[f"{role}:{arm}"] = {"replicates_disagree": k, "n": len(g), "share": round(k / len(g), 3) if g else None, "ci95": cp(k, len(g))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="analysis/fork/simctrl")
    ap.add_argument("--no-gate", action="store_true", help="dry runs only")
    ap.add_argument("--tag", default="")
    ap.add_argument("--manifest", default=None, help="W91: manifests/fork/simctrl_v3.json for the relay run (with --dir analysis/fork/simctrl_relay)")
    a = ap.parse_args()
    global MAN
    if a.manifest:
        MAN = ROOT / a.manifest
    man_sha = sha_file(MAN)
    man = json.loads(MAN.read_text())
    NR = int(man.get("replicates", 1))
    base = ROOT / a.dir
    inputs = {str(MAN.relative_to(ROOT)): man_sha}
    gate = base / "gate" / "gate.json"
    if not a.no_gate:
        if not gate.exists():
            raise SystemExit(f"{gate} missing: the acceptance gate must pass before any analysis")
        g = json.loads(gate.read_text())
        if g.get("verdict") != "PASS" or g.get("manifest_sha256") != man_sha:
            raise SystemExit(f"acceptance gate not passed for this manifest: verdict {g.get('verdict')}")
        inputs[str(gate.relative_to(ROOT))] = sha_file(gate)
    got = {}
    for p in sorted(base.glob("q*_*/f*/simctrl_rows.jsonl")) + sorted(base.glob("q*_*/simctrl_rows.jsonl")):
        s = p.parent / "simctrl_summary.json"
        if not s.exists():
            continue
        if json.loads(s.read_text()).get("manifest_sha256") != man_sha:
            raise SystemExit(f"{s}: different manifest")
        inputs[str(p.relative_to(ROOT))] = sha_file(p)
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if "unit_id" in r and "Y_sonnet" in r:
                    got[r["unit_id"]] = r
    units = []
    for u in man["units"]:
        r = got.get(u["unit_id"], {})
        x = {**u, "Y_sonnet": r.get("Y_sonnet"), "termination": r.get("termination"), "usage": r.get("user_llm_usage"),
             "request_ids": r.get("request_ids")}
        x["c"] = classify(x, NR)
        units.append(x)
    R = {"generated_utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "script": "analysis/fork/analyze_simctrl.py",
         "manifest": str(MAN.relative_to(ROOT)), "replicates": NR, "scope": man["scope"], "blocks": man["blocks"], "user_llm": man["user_llm"], "inputs": inputs, "dry": a.no_gate,
         "n_units_manifest": len(units), "n_units_with_results": sum(1 for u in units if u["c"]["status"] == "ok")}
    groups = {"all": lambda u: True, **{f"model={m}": (lambda m: lambda u: u["model"] == m)(m) for m in ("q4", "q8")},
              **{f"sub={s}": (lambda s: lambda u: u["sub"] == s)(s) for s in ("U1", "U2B", "U2Q")},
              **{f"sub_cls={s}": (lambda s: lambda u: u["sub_cls"] == s)(s) for s in ("ii_talk", "ii_act")}}
    R["flips"] = {k: summarize([u for u in units if u["role"] == "flip" and f(u)], "flip", NR) for k, f in groups.items()}
    for d in ("rescue", "damage"):
        R["flips"][f"direction_orig={d}"] = summarize([u for u in units if u["role"] == "flip" and u["direction_orig"] == d], "flip", NR)
    R["controls"] = {k: summarize([u for u in units if u["role"] == "control" and f(u)], "control", NR) for k, f in groups.items()}
    pairs = collections.defaultdict(dict)
    for u in units:
        pairs[u["pair_id"]][u["role"]] = u
    ct = collections.Counter()
    for p in pairs.values():
        f, c = p.get("flip"), p.get("control")
        if not f or not c or f["c"]["status"] != "ok" or c["c"]["status"] != "ok":
            ct["incomplete_pair"] += 1
            continue
        ct[f"flip_{'retained' if f['c']['fate'] == 'retained' else 'not_retained'}|control_{'new_flip' if c['c']['fate'] == 'new_flip' else 'no_flip'}"] += 1
    R["paired"] = dict(ct)
    R_var = variability(units, NR)
    R["variability"] = R_var
    agree = {}
    for role in ("flip", "control"):
        for arm in ("BQ", "QQ"):
            ys = [(y, u["Y_orig"][arm]) for u in units if u["role"] == role for y in u["c"]["arm_reps"][arm] if y is not None]
            k = sum(1 for y, o in ys if y == o)
            agree[f"{role}:{arm}"] = {"agree_replicates": k, "n_replicates": len(ys), "ci95": cp(k, len(ys))}
    R["arm_agreement_with_original"] = agree
    R["termination"] = dict(collections.Counter(t for u in units if u["termination"] for t in u["termination"].values()))
    us = [v for u in units if u["usage"] for v in u["usage"].values() if v]
    R["user_llm_usage"] = {"n_calls": sum(v["n_calls"] for v in us), "prompt_tokens": sum(v["prompt_tokens"] for v in us),
                           "completion_tokens": sum(v["completion_tokens"] for v in us), "cost_usd": round(sum(v["cost_usd"] for v in us), 4),
                           "n_request_ids": sum(len(x) for u in units if u["request_ids"] for x in u["request_ids"].values())}
    R["units"] = [{k: u[k] for k in ("unit_id", "role", "pair_id", "model", "cell", "sub", "sub_cls", "state_key", "Y_orig", "direction_orig",
                                     "Y_sonnet", "termination")} | {"fate": u["c"].get("fate"), "status": u["c"]["status"], "Dbar": u["c"].get("Dbar"),
                                    "per_rep_fate": u["c"]["per_rep_fate"]} for u in units]
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"simctrl{'_' + a.tag if a.tag else ''}_{R['generated_utc']}"
    (OUT / f"{stem}.json").write_text(json.dumps(R, indent=1))
    L = [f"# Simulator robustness control (Sonnet 5.5 user) — {R['generated_utc']}{' — DRY RUN (mock user, not results)' if a.no_gate else ''}", "",
         f"Scope: {man['scope']}", "", f"Blocks: {', '.join(man['blocks'])}. {man['blocks_note']}", "",
         f"Units with results: {R['n_units_with_results']}/{R['n_units_manifest']}. User: {man['user_llm']}.", "",
         "## Original flips under the Sonnet user", "", "Primary: sign of the replicate-mean flip indicator Dbar vs the original direction.", "",
         "| group | n | missing | retained | reversed | vanished (both succeed / both fail / mixed tie) |", "|---|---|---|---|---|---|"]
    for k, v in R["flips"].items():
        if v["n"]:
            L.append(f"| {k} | {v['n']} | {v['n_missing']} | {v['retained']} {v['retained_ci95']} | {v['reversed']} {v['reversed_ci95']} | "
                     f"{v['vanished']} ({v['vanished_both_succeed']} / {v['vanished_both_fail']} / {v['vanished_tie_mixed']}) |")
    L += ["", "## Matched non-flip controls under the Sonnet user", "", "| group | n | missing | new flips | rescue / damage |", "|---|---|---|---|---|"]
    for k, v in R["controls"].items():
        if v["n"]:
            L.append(f"| {k} | {v['n']} | {v['n_missing']} | {v['new_flips']} {v['new_flips_ci95']} | {v['new_rescue']} / {v['new_damage']} |")
    L += ["", f"## Per-replicate distribution and within-simulator variability (R = {R['replicates']})", "",
          "Flips, units by number of replicates flipping in the original direction (0..R): "
          + json.dumps(R["flips"]["all"]["units_by_n_rep_same_direction"]) + "; in the reversed direction: "
          + json.dumps(R["flips"]["all"]["units_by_n_rep_reversed"]), "",
          "Flips per replicate: " + json.dumps(R["flips"]["all"]["per_replicate"]), "",
          "Controls, units by number of replicates flipping (0..R): " + json.dumps(R["controls"]["all"]["units_by_n_rep_flipping"]), "",
          "Controls per replicate: " + json.dumps(R["controls"]["all"]["per_replicate"]), "",
          "| role:arm | units whose replicates disagree | n | share [95%] |", "|---|---|---|---|"]
    L += [f"| {k} | {v['replicates_disagree']} | {v['n']} | {v['share']} {v['ci95']} |" for k, v in R["variability"].items()]
    L += ["", f"Paired (flip x its control): {R['paired']}", "", f"Arm agreement with the original Y: {json.dumps(agree)}", "",
          f"Termination: {R['termination']}", "", f"Sonnet usage: {R['user_llm_usage']}", "",
          "Intervals: exact Clopper-Pearson 95% over units with both arms. No pass threshold was pre-specified."]
    (OUT / f"{stem}.md").write_text("\n".join(L) + "\n")
    print(f"analysis/fork/out/{stem}.json")
    print(f"analysis/fork/out/{stem}.md")


if __name__ == "__main__":
    main()
