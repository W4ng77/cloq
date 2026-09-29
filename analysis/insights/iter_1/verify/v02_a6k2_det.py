"""Verifier: first clean (a6k2, TORCHINDUCTOR_DETERMINISTIC=1) evidence, live snapshot.

1. P1c D==0 arm: a6k2_det_<m>_a (node005) vs a6k2_det_<m>_b (node004), and a6k2_<m>_bf16 vs a6k2_det_<m>_b.
2. E5 flavour-null pair (free): legacy BF16 (a6000_det_<m>_b == a6000_<m>_bf16 bitwise) vs a6k2 BF16 on the same
   det tasks: is D != 0, and does it saturate divergence (P1c second clause)?
3. Early a6k2 perturbation pairs vs a6k2_<m>_bf16 on whatever tasks both have finished (reported with n).
Tasks still running are right-censored (decisions missing), exactly as in v01.
Writes analysis/insights/iter_1/verify/out/v02_a6k2_det.json
"""
import json
from datetime import datetime, timezone

from v01_legacy_recompute import OUT, RUNS, first_div, flips, hazard, km, load, outcomes


def pair(a, b, key="sha"):
    A, Bv = load(a), load(b)
    if not A or not Bv:
        return None
    rows = first_div(A, Bv, key)
    # decision-0 context check: a differing decision-0 prompt means the *user simulator* (first user message) differs
    d0 = [(k[0], k[1]) for k in A if k[2] == 0 and (k[0], k[1], 0) in Bv]
    d0_mismatch = sorted(f"{d}/{t}" for d, t in d0 if A[(d, t, 0)]["sha"] != Bv[(d, t, 0)]["sha"])
    f = flips(A, Bv, key)
    n_ctx = sum(v["n"] for k, v in f.items() if k in ("text", "tool"))
    return {"a": a, "b": b, "n_tasks": len(rows), "n_events": sum(e for *_, e in rows),
            "km<=0": round(km(rows, 0), 3), "km<=4": round(km(rows, 4), 3), "km<=12": round(km(rows, 12), 3),
            "hazard": None if not rows else (round(hazard(rows), 3) if hazard(rows) is not None else None),
            "identical_ctx_decisions": n_ctx, "flip_by_kind": {k: v for k, v in f.items() if k in ("text", "tool")},
            "shift_abs_median": f.get("shift_abs_median"), "shift_abs_p90": f.get("shift_abs_p90"),
            "decision0_tasks": len(d0), "decision0_prompt_mismatch": d0_mismatch}


def status(run):
    out = {}
    for d in ("retail", "airline"):
        p = RUNS / run / d / "status.json"
        out[d] = json.load(open(p)).get("status") if p.exists() else None
    return out


def main():
    res = {"taken_utc": datetime.now(timezone.utc).isoformat(), "pairs": {}, "status": {}}
    specs = []
    for m in ("q4", "q30a3", "q8", "q14", "q32"):
        specs += [(f"a6k2_det_{m}_a", f"a6k2_det_{m}_b", "P1c det pair under flag (node005 vs node004)"),
                  (f"a6k2_det_{m}_b", f"a6k2_{m}_bf16", "P1c det vs eval-task BF16 under flag"),
                  (f"a6000_det_{m}_b", f"a6k2_det_{m}_b", "E5 flavour null: legacy BF16 vs a6k2 BF16, same node004"),
                  (f"a6000_det_{m}_a", f"a6k2_det_{m}_a", "legacy off-flavour (node005) vs a6k2, same node005")]
    for m in ("q4", "q8"):
        for c in ("gauss0.03_s1", "gauss0.03_s2", "gauss0.1_s1", "gauss0.1_s2", "gauss0.3_s1", "gauss1_s1", "rtn_w8_n1", "rtn_w4_n1"):
            ref = f"a6k2_{m}_null_n1" if c.endswith("_n1") else f"a6k2_{m}_bf16"
            specs.append((ref, f"a6k2_{m}_{c}", "early a6k2 pair (partial)"))
        specs.append((f"a6k2_{m}_bf16", f"a6k2_{m}_null_n1", "early a6k2 nonce pair (partial)"))
    for a, b, why in specs:
        if not ((RUNS / a).exists() and (RUNS / b).exists()):
            continue
        key = "ctx" if ("null_n" in b and "null_n" not in a) else "sha"
        r = pair(a, b, key)
        if r is None:
            continue
        r["why"] = why
        r["status"] = {a: status(a), b: status(b)}
        # outcome agreement on tasks both finished
        ya = {**{("r", t): v for t, v in outcomes(a, "retail").items()}, **{("a", t): v for t, v in outcomes(a, "airline").items()}}
        yb = {**{("r", t): v for t, v in outcomes(b, "retail").items()}, **{("a", t): v for t, v in outcomes(b, "airline").items()}}
        common = sorted(set(ya) & set(yb))
        r["outcome_tasks"] = len(common)
        r["outcome_disagree"] = sum(ya[k] != yb[k] for k in common)
        r["db_a"] = round(sum(ya[k] for k in common) / len(common), 3) if common else None
        r["db_b"] = round(sum(yb[k] for k in common) / len(common), 3) if common else None
        res["pairs"][f"{a} vs {b}"] = r
        print(f"{a} vs {b}: tasks={r['n_tasks']} ev={r['n_events']} KM0/4/12={r['km<=0']}/{r['km<=4']}/{r['km<=12']} "
              f"ctx={r['identical_ctx_decisions']} |d|med={r['shift_abs_median']} flips={r['flip_by_kind']} "
              f"outcomes {r['outcome_disagree']}/{r['outcome_tasks']} ({why})")
    json.dump(res, open(OUT / "v02_a6k2_det.json", "w"), indent=1, default=str)
    print("wrote", OUT / "v02_a6k2_det.json")


if __name__ == "__main__":
    main()
