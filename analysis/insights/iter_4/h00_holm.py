"""h00: Holm adjustment (alpha 0.05) over the declared confirmatory family common4.DECLARED (P1, P2, P3, P4, F1).

Reads the primary p-value of each test from the iter-4 outputs of the same tag and writes out/h00_holm_<tag>.json.
All other statistics in the iter-4 outputs are exploratory and are not adjusted here.
Usage: CLOQ_SNAPSHOT=<manifest> [CLOQ_TAG=live_<id>] python h00_holm.py (after p1, p2, p4, f1)
"""
import json

from common4 import DECLARED, OUT, TAG, dump, holm, rnd

SRC = {"P1": ("p1_overdispersion", lambda d: (d["primary"]["p"], d["primary"]["phi"])),
       "P2": ("p2_dispositions", lambda d: (d["primary"]["P2"]["p"], d["primary"]["P2"]["F"])),
       "P3": ("p2_dispositions", lambda d: (d["primary"]["P3"]["p"], d["primary"]["P3"]["rho"])),
       "P4": ("p4_openloop_forks", lambda d: (d["primary"]["p"], d["primary"]["rho"])),
       "F1": ("f1_fragile_forks", lambda d: (d["primary"]["p"], d["primary"]["rho"]))}


def main():
    rows = []
    for k in DECLARED:
        name, get = SRC[k]
        p, est = get(json.load(open(OUT / f"{name}_{TAG}.json")))
        rows.append(dict(test=k, source=f"analysis/insights/iter_4/out/{name}_{TAG}.json", estimate=est, p=p))
    adj = holm([r["p"] for r in rows])
    for r, a in zip(rows, adj):
        r["p_holm"] = rnd(a, 4)
        r["verdict"] = "reject H0 (supported)" if a < 0.05 else "not supported after Holm"
        print(r)
    dump("h00_holm", {"alpha": 0.05, "family": rows})


if __name__ == "__main__":
    main()
