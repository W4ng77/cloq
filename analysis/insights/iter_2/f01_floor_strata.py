"""Floor hazard by pairing stratum + stratum-matched cross-model floor prediction (review v2 Q4; C1).

p02's `cross_model.<m>.observed_floor_hazard_median` pools two kinds of floor cells (p02 FLOOR regex):
  same-prompt  : bf16_eager, gauss k <= 0.03, rtn_w8_n*  (paired with their reference on identical prompts);
  nonce        : null_n*                                  (paired with canonical bf16 across a prompt change).
Nonce pairs sit above the same-prompt floor (iter_2_prep.md A2-3 item 3), so the pooled median moves with the number
of nonce nulls in the snapshot (q4: 3 -> 5 nonce cells after the redos/null_extra). This script reports both strata
and the q4-calibrated cross-model prediction (p02 `pred_all_decisions_q4_floor_h` x q4 observed/predicted) per stratum.
Reads out/p02_ties.json only.  Usage: python f01_floor_strata.py -> out/f01_floor_strata.json
"""
import json
import re

import numpy as np

from common import OUT, dump, now

SAME = re.compile(r"_(bf16_eager|gauss0\.00[13]_s\d|gauss0\.01_s\d|gauss0\.03_s\d|rtn_w8_n\d)$")
NONCE = re.compile(r"_null_n\d+$")


def main():
    p02 = json.load(open(OUT / "p02_ties.json"))
    res = {"snapshot_utc": now(), "p02_snapshot_utc": p02.get("snapshot_utc"), "p02_frozen_snapshot": p02.get("_frozen_snapshot"),
           "models": {}}
    cm, cl = p02["cross_model"], p02["closed_loop"]
    for m, x in cm.items():
        cells = {r: cl[m][r]["hazard"] for r in x["floor_cells"] if r in cl[m]}
        e = {"pred_uncalibrated": x["pred_all_decisions_q4_floor_h"], "pooled_median_p02": x["observed_floor_hazard_median"]}
        for lab, rx in (("same_prompt", SAME), ("nonce", NONCE)):
            v = {r: h for r, h in cells.items() if rx.search(r)}
            e[lab] = {"n": len(v), "median": round(float(np.median(list(v.values()))), 4) if v else None,
                      "range": [round(min(v.values()), 4), round(max(v.values()), 4)] if v else None, "cells": v}
        res["models"][m] = e
    q4 = res["models"].get("q4")
    for lab in ("same_prompt", "nonce", "pooled"):
        obs4 = q4["pooled_median_p02"] if lab == "pooled" else q4[lab]["median"]
        if not obs4:
            continue
        scale = obs4 / q4["pred_uncalibrated"]
        for m, e in res["models"].items():
            obs = e["pooled_median_p02"] if lab == "pooled" else e[lab]["median"]
            pred = e["pred_uncalibrated"] * scale
            e.setdefault("calibrated_prediction", {})[lab] = {
                "q4_scale": round(scale, 4), "pred": round(pred, 4), "obs": obs,
                "rel_err": round((pred - obs) / obs, 3) if obs else None}
    dump("f01_floor_strata.json", res)
    for m, e in res["models"].items():
        print(m, {k: (v["median"], v["n"]) for k, v in e.items() if isinstance(v, dict) and "median" in v},
              e.get("calibrated_prediction"))


if __name__ == "__main__":
    main()
