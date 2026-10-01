"""Simulator robustness control for Bank U text-structure flips (W90; manifest manifests/fork/simctrl_v1.json).

Pre-specified report (the manifest's analysis_plan; no pass threshold):
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
MAN = ROOT / "manifests" / "fork" / "simctrl_v1.json"
OUT = ROOT / "analysis" / "fork" / "out"


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cp(k: int, n: int) -> list:
    if n == 0:
        return [None, None]
    lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
    return [round(lo, 3), round(hi, 3)]


def classify(u: dict) -> dict:
    """Outcome under the Sonnet user for one unit; None if any arm is missing."""
    Y = u.get("Y_sonnet") or {}
    if Y.get("BQ") is None or Y.get("QQ") is None:
        return {"status": "missing"}
    bq, qq = Y["BQ"], Y["QQ"]
    dirn = "rescue" if (bq, qq) == (1, 0) else "damage" if (bq, qq) == (0, 1) else "none"
    out = {"status": "ok", "dir_sonnet": dirn, "M_sonnet": int(dirn != "none"),
           "both": "both_succeed" if (bq, qq) == (1, 1) else "both_fail" if (bq, qq) == (0, 0) else None}
    if u["role"] == "flip":
        out["fate"] = "vanished" if dirn == "none" else "retained" if dirn == u["direction_orig"] else "reversed"
    else:
        out["fate"] = "new_flip" if dirn != "none" else "stays_non_flip"
    return out


def summarize(g: list[dict], role: str) -> dict:
    ok = [u for u in g if u["c"]["status"] == "ok"]
    z = collections.Counter(u["c"]["fate"] for u in ok)
    res = {"n": len(g), "n_missing": len(g) - len(ok), "n_ok": len(ok)}
    if role == "flip":
        for f in ("retained", "reversed", "vanished"):
            res[f] = z[f]
            res[f + "_ci95"] = cp(z[f], len(ok))
        res["vanished_both_succeed"] = sum(1 for u in ok if u["c"]["fate"] == "vanished" and u["c"]["both"] == "both_succeed")
        res["vanished_both_fail"] = sum(1 for u in ok if u["c"]["fate"] == "vanished" and u["c"]["both"] == "both_fail")
    else:
        res["new_flips"] = z["new_flip"]
        res["new_flips_ci95"] = cp(z["new_flip"], len(ok))
        res["new_rescue"] = sum(1 for u in ok if u["c"]["dir_sonnet"] == "rescue")
        res["new_damage"] = sum(1 for u in ok if u["c"]["dir_sonnet"] == "damage")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="analysis/fork/simctrl")
    ap.add_argument("--no-gate", action="store_true", help="dry runs only")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    man_sha = sha_file(MAN)
    man = json.loads(MAN.read_text())
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
        x["c"] = classify(x)
        units.append(x)
    R = {"generated_utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "script": "analysis/fork/analyze_simctrl.py",
         "scope": man["scope"], "blocks": man["blocks"], "user_llm": man["user_llm"], "inputs": inputs, "dry": a.no_gate,
         "n_units_manifest": len(units), "n_units_with_results": sum(1 for u in units if u["c"]["status"] == "ok")}
    groups = {"all": lambda u: True, **{f"model={m}": (lambda m: lambda u: u["model"] == m)(m) for m in ("q4", "q8")},
              **{f"sub={s}": (lambda s: lambda u: u["sub"] == s)(s) for s in ("U1", "U2B", "U2Q")},
              **{f"sub_cls={s}": (lambda s: lambda u: u["sub_cls"] == s)(s) for s in ("ii_talk", "ii_act")}}
    R["flips"] = {k: summarize([u for u in units if u["role"] == "flip" and f(u)], "flip") for k, f in groups.items()}
    for d in ("rescue", "damage"):
        R["flips"][f"direction_orig={d}"] = summarize([u for u in units if u["role"] == "flip" and u["direction_orig"] == d], "flip")
    R["controls"] = {k: summarize([u for u in units if u["role"] == "control" and f(u)], "control") for k, f in groups.items()}
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
    agree = {}
    for role in ("flip", "control"):
        for arm in ("BQ", "QQ"):
            g = [u for u in units if u["role"] == role and u["c"]["status"] == "ok"]
            k = sum(1 for u in g if u["Y_sonnet"][arm] == u["Y_orig"][arm])
            agree[f"{role}:{arm}"] = {"agree": k, "n": len(g), "ci95": cp(k, len(g))}
    R["arm_agreement_with_original"] = agree
    R["termination"] = dict(collections.Counter(t for u in units if u["termination"] for t in u["termination"].values()))
    us = [v for u in units if u["usage"] for v in u["usage"].values() if v]
    R["user_llm_usage"] = {"n_calls": sum(v["n_calls"] for v in us), "prompt_tokens": sum(v["prompt_tokens"] for v in us),
                           "completion_tokens": sum(v["completion_tokens"] for v in us), "cost_usd": round(sum(v["cost_usd"] for v in us), 4),
                           "n_request_ids": sum(len(x) for u in units if u["request_ids"] for x in u["request_ids"].values())}
    R["units"] = [{k: u[k] for k in ("unit_id", "role", "pair_id", "model", "cell", "sub", "sub_cls", "state_key", "Y_orig", "direction_orig",
                                     "Y_sonnet", "termination")} | {"fate": u["c"].get("fate"), "status": u["c"]["status"]} for u in units]
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"simctrl{'_' + a.tag if a.tag else ''}_{R['generated_utc']}"
    (OUT / f"{stem}.json").write_text(json.dumps(R, indent=1))
    L = [f"# Simulator robustness control (Sonnet 5.5 user) — {R['generated_utc']}{' — DRY RUN (mock user, not results)' if a.no_gate else ''}", "",
         f"Scope: {man['scope']}", "", f"Blocks: {', '.join(man['blocks'])}. {man['blocks_note']}", "",
         f"Units with results: {R['n_units_with_results']}/{R['n_units_manifest']}. User: {man['user_llm']}.", "",
         "## Original flips under the Sonnet user", "", "| group | n | missing | retained | reversed | vanished (both succeed / both fail) |", "|---|---|---|---|---|---|"]
    for k, v in R["flips"].items():
        if v["n"]:
            L.append(f"| {k} | {v['n']} | {v['n_missing']} | {v['retained']} {v['retained_ci95']} | {v['reversed']} {v['reversed_ci95']} | "
                     f"{v['vanished']} ({v['vanished_both_succeed']} / {v['vanished_both_fail']}) |")
    L += ["", "## Matched non-flip controls under the Sonnet user", "", "| group | n | missing | new flips | rescue / damage |", "|---|---|---|---|---|"]
    for k, v in R["controls"].items():
        if v["n"]:
            L.append(f"| {k} | {v['n']} | {v['n_missing']} | {v['new_flips']} {v['new_flips_ci95']} | {v['new_rescue']} / {v['new_damage']} |")
    L += ["", f"Paired (flip x its control): {R['paired']}", "", f"Arm agreement with the original Y: {json.dumps(agree)}", "",
          f"Termination: {R['termination']}", "", f"Sonnet usage: {R['user_llm_usage']}", "",
          "Intervals: exact Clopper-Pearson 95% over units with both arms. No pass threshold was pre-specified."]
    (OUT / f"{stem}.md").write_text("\n".join(L) + "\n")
    print(f"analysis/fork/out/{stem}.json")
    print(f"analysis/fork/out/{stem}.md")


if __name__ == "__main__":
    main()
