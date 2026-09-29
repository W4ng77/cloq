"""A2-4 tally: verdict counts of the null-referenced TOST (null set A, ±7.5 pp) vs the Flat-Score-style (±7.5 pp vs the
canonical run) and Singh-style (±2 pp vs canonical) protocols, and McNemar-vs-canonical flags, over non-null families.
Reads out/p01_equivalence.json only.  Usage: python p07_protocol_tally.py -> out/p07_protocol_tally.json
"""
import json

from common import OUT, dump


def main():
    r = json.load(open(OUT / "p01_equivalence.json"))
    res = {"source_snapshot_utc": r["snapshot_utc"], "models": {}, "total": {}}
    tot = {"families": 0, "null_ref_equiv_7.5": 0, "flatscore_equiv_7.5": 0, "singh_equiv_2": 0,
           "null_ref_below": 0, "flatscore_below": 0, "mcnemar_flags": 0, "mcnemar_draws": 0}
    for m, x in r["models"].items():
        c = x["clean"]; A = c["nullsets"]["A"]["families"]; RO = c.get("reference_only", {})
        rows = []
        for f, ro in RO.items():
            if not ro or f not in A or f.startswith("null:"):
                continue
            ours, fs, sg = A[f]["verdicts"]["7.5pp"], ro["flatscore_7.5pp"], ro["singh_2pp"]
            tot["families"] += 1
            tot["null_ref_equiv_7.5"] += ours.startswith("equivalent"); tot["flatscore_equiv_7.5"] += fs.startswith("equivalent")
            tot["singh_equiv_2"] += sg.startswith("equivalent")
            tot["null_ref_below"] += ours.startswith("below"); tot["flatscore_below"] += fs.startswith("below")
            tot["mcnemar_flags"] += ro["mcnemar_flags_p<0.05"]; tot["mcnemar_draws"] += len(ro["mcnemar_per_draw"])
            rows.append({"family": f, "delta_vs_null": A[f]["delta"], "null_ref_7.5": ours, "delta_vs_canonical": ro["delta_vs_canonical"],
                         "flatscore_7.5": fs, "singh_2": sg, "mcnemar_flagged_draws": [d["run"] for d in ro["mcnemar_per_draw"] if d["p_two_sided"] < 0.05],
                         "disagree": ours.split(" ")[0] != fs.split(" ")[0]})
        res["models"][m] = rows
    res["total"] = tot
    dump("p07_protocol_tally.json", res)
    print(tot)


if __name__ == "__main__":
    main()
