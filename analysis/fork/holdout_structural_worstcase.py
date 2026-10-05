"""POST HOC SENSITIVITY (GPT-authorised 2026-10-04, not a protocol repair): the two structural task exclusions of the
telecom holdout confirmation, re-included with bounding unit values. No GPU rerun; changes no frozen file.

Frozen result: analysis/fork/out/holdout_confirm_20261002T012353Z.json, G_all -4.57 pp, crossed 90% [-7.17, -1.96].
There, one task is excluded from q4:gptq_w4_d1 and one from q8:awq_w4 in all 12 blocks (decision/trajectory count
mismatch, prereg §4.3), so n_c = 33 in those cells. Here each excluded task is put back into its cell in all used blocks
with unit G (= Y_BQ - Y_QQ, no-divergence = 0) set by one of these options:
  excluded  frozen handling (reproduces the confirmatory numbers; asserted)
  -1, 0, +1 the same value in every block
  obs/-1, obs/+1  the task's observed units where they exist (units dropped only by the structural rule), the rest -1 / +1
All 6 x 6 combinations of the two tasks are reported. Estimator, cell weights, Z matrix, crossed interval and readings are
analyze_holdout_confirm's own (HC.Matrix, HC.estimate, HC.readings; frozen, imported, unmodified). Loading: AD.split_guard
("holdout") runs before any holdout read, then HC.load; admission is holdout_r2_posthoc.admit (verbatim copy of HC.main
§4.3-4.5) and the analysed units' digest is asserted equal to the confirmatory output's.

usage: python analysis/fork/holdout_structural_worstcase.py --selftest   (synthetic data, no holdout read)
       python analysis/fork/holdout_structural_worstcase.py              -> analysis/fork/out/holdout_structural_worstcase_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_dev as AD  # noqa: E402
import analyze_holdout_confirm as HC  # noqa: E402  (frozen; imported, never modified)
import holdout_r2_posthoc as R2  # noqa: E402

ROOT, OUT = AD.ROOT, AD.OUT
LABEL = "POST HOC SENSITIVITY (GPT-authorised, not a protocol repair)"
OPTIONS = ("excluded", "-1", "0", "+1", "obs/-1", "obs/+1")
STRUCT_TAG = "structural exclusion of the task in this cell"


def fill(Mx, mc, task, opt, obs: dict) -> None:
    """Set row `task` of cell mc's G matrix in place. obs: block -> observed unit G (structurally dropped units only)."""
    if opt == "excluded":
        return
    j = Mx.ti[task]
    for b, k in Mx.bi.items():
        if opt in ("-1", "0", "+1"):
            Mx.X[mc]["G"][j, k] = float(opt)
        else:
            Mx.X[mc]["G"][j, k] = obs.get(b, float(opt[4:]))


def run_grid(Mx, cells_w: dict, excl: dict, obs: dict, k_used: int) -> list[dict]:
    """excl: mc -> task; obs: mc -> {block: G}. Recomputes G_all with the frozen estimator for every option pair."""
    keys = list(excl)
    G0 = {mc: Mx.X[mc]["G"].copy() for mc in keys}
    rows = []
    for opts in itertools.product(OPTIONS, repeat=len(keys)):
        for mc, o in zip(keys, opts):
            Mx.X[mc]["G"] = G0[mc].copy()
            fill(Mx, mc, excl[mc], o, obs.get(mc, {}))
        e = HC.estimate(Mx, "G", cells_w)
        cr = e["crossed_decisional"]
        rows.append({"options": {f"{m}:{c}": o for (m, c), o in zip(keys, opts)}, "J": e["J"], "K": e["K"],
                     "crossed_decisional_pp": HC.pp(cr), "block_t_pp": HC.pp(e["block_t"]), "readings": HC.readings(cr, k_used)})
    for mc in keys:
        Mx.X[mc]["G"] = G0[mc]
    return rows


def selftest() -> None:
    rng = np.random.default_rng(0)
    tasks, blocks = [f"telecom:t{i:02d}" for i in range(10)], [f"h{k:02d}" for k in range(1, 9)]
    units = []
    for (m, c, _), t, b in itertools.product(HC.CELLS, tasks, blocks):
        div = bool(rng.random() < 0.4)
        Y = {s: int(rng.random() < 0.5) for s in ("BB", "BQ", "QB", "QQ")}
        units.append({"model": m, "cell": c, "task": t, "block": b, "div": div, "Y": Y, "steps_left": 5})
    excl = {("q4", "gptq_w4_d1"): tasks[3], ("q8", "awq_w4"): tasks[7]}
    full = HC.Matrix(tasks, blocks, units, HC.CELLS)
    obs = {mc: {u["block"]: float(AD.effects(u["Y"], u["div"])["G"]) for u in units
                if (u["model"], u["cell"]) == mc and u["task"] == t and u["block"] != "h01"} for mc, t in excl.items()}
    for u in units:
        if excl.get((u["model"], u["cell"])) == u["task"]:
            u["excluded"] = STRUCT_TAG
    Mx = HC.Matrix(tasks, blocks, units, HC.CELLS)
    cw = {(m, c): w for m, c, w in HC.CELLS}
    rows = {tuple(r["options"].values()): r for r in run_grid(Mx, cw, excl, obs, len(blocks))}
    assert len(rows) == 36
    base = HC.estimate(Mx, "G", cw)["crossed_decisional"]
    assert abs(rows[("excluded", "excluded")]["crossed_decisional_pp"]["est"] - round(100 * base["est"], 3)) < 1e-9
    # obs with h01 = actual value equals the fully observed matrix
    for mc, t in excl.items():
        g = AD.effects(next(u for u in units if (u["model"], u["cell"]) == mc and u["task"] == t and u["block"] == "h01")["Y"],
                       next(u for u in units if (u["model"], u["cell"]) == mc and u["task"] == t and u["block"] == "h01")["div"])["G"]
        obs[mc]["h01"] = float(g)
    r = {tuple(x["options"].values()): x for x in run_grid(Mx, cw, excl, obs, len(blocks))}[("obs/-1", "obs/+1")]
    ref = HC.estimate(full, "G", cw)["crossed_decisional"]
    assert abs(r["crossed_decisional_pp"]["est"] - round(100 * ref["est"], 3)) < 1e-9
    assert abs(r["crossed_decisional_pp"]["se"] - round(100 * ref["se"], 3)) < 1e-9
    lo, hi = rows[("-1", "-1")]["crossed_decisional_pp"]["est"], rows[("+1", "+1")]["crossed_decisional_pp"]["est"]
    assert lo < rows[("0", "0")]["crossed_decisional_pp"]["est"] < hi
    assert np.isnan(Mx.X[("q4", "gptq_w4_d1")]["G"][3]).all()  # grid restores the matrix
    print(f"selftest ok: 36 combos; baseline reproduced; obs-fill equals full matrix; G range [{lo:+.3f}, {hi:+.3f}] pp")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--selftest", action="store_true", help="synthetic data only; never opens holdout files")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    AD.split_guard([], "holdout", "holdout_structural_worstcase")  # before any holdout read
    if AD.sha256(HC.CUTPOINTS) != HC.CUTPOINTS_SHA256:
        raise SystemExit("holdout_structural_worstcase: cut points differ from the frozen sha")
    snap_path = ROOT / R2.DEF_SNAPSHOT
    if AD.sha256(snap_path) != R2.SNAPSHOT_SHA256:
        raise SystemExit("holdout_structural_worstcase: snapshot sha256 differs from the confirmatory one")
    try:
        from loguru import logger
        logger.remove(); logger.add(sys.stderr, level="ERROR")
    except Exception:
        pass
    snap, man = json.load(open(snap_path)), json.load(open(AD.SPLITS))
    conf = json.load(open(ROOT / R2.CONFIRM_OUT))
    tasks = sorted(f"telecom:{t}" for t in man["splits"]["holdout"]["tasks"]["telecom"])
    units, prov = HC.load(snap, "analysis/fork/holdout", "holdout", HC.CELLS, set(HC.PRIMARY_BLOCKS) | set(HC.RESERVE_BLOCKS))
    used, blocks, struct_excl, reasons = R2.admit(units, tasks)
    digest = AD.units_digest([u for u in units if "excluded" not in u and u["block"] in used])
    assert digest == conf["units_digest_sha256"] and used == conf["blocks"]["used"]
    cells_w = {(m, c): w for m, c, w in HC.CELLS}
    excl, obs, obs_desc = {}, {}, {}
    for lab, ts in ((k, v) for k, v in struct_excl.items() if v):
        assert len(ts) == 1, f"expected one excluded task in {lab}"
        mc = tuple(lab.split(":", 1))
        excl[mc] = ts[0]
        ou = [u for u in units if (u["model"], u["cell"]) == mc and u["task"] == ts[0] and u["block"] in used]
        ok = [u for u in ou if u.get("excluded") == STRUCT_TAG]
        obs[mc] = {u["block"]: float(AD.effects(u["Y"], u["div"])["G"]) for u in ok}
        obs_desc[lab] = {"task": ts[0], "blocks_with_observed_unit": sorted(obs[mc]), "n_observed": len(ok),
                         "n_divergent": sum(bool(u["div"]) for u in ok), "observed_G": {b: obs[mc][b] for b in sorted(obs[mc])},
                         "other_unit_reasons": sorted({u["excluded"][:80] for u in ou if u.get("excluded") != STRUCT_TAG})}
    Mx = HC.Matrix(tasks, used, units, HC.CELLS)
    rows = run_grid(Mx, cells_w, excl, obs, len(used))
    b0 = rows[0]["crossed_decisional_pp"]
    c0 = conf["primary_G_all"]["crossed_decisional"]
    assert (b0["est"], b0["se"], b0["ci90"]) == (c0["est"], c0["se"], c0["ci90"]), "frozen G_all not reproduced"
    me = Path(__file__).resolve()
    res = {"label": LABEL, "authorisation": "GPT 2026-10-04: two structural exclusions, no GPU rerun; CPU worst-case sensitivity "
           "using the actual task exclusion scope and weights",
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "inputs": {"script": {"path": str(me.relative_to(ROOT)), "sha256": AD.sha256(me)},
                      "analyze_holdout_confirm_sha256": AD.sha256(HC.__file__), "holdout_r2_posthoc_sha256": AD.sha256(R2.__file__),
                      "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
                      "prereg_sha256": AD.sha256(ROOT / HC.PREREG), "splits_sha256": AD.sha256(AD.SPLITS),
                      "cutpoints_sha256": HC.CUTPOINTS_SHA256, "snapshot": {"path": R2.DEF_SNAPSHOT, "sha256": R2.SNAPSHOT_SHA256},
                      "confirm_output": {"path": R2.CONFIRM_OUT, "sha256": AD.sha256(ROOT / R2.CONFIRM_OUT)},
                      "units_digest_sha256": digest, "input_files_digest_sha256": prov["input_files_digest_sha256"]},
           "cells_weights": {f"{m}:{c}": w for (m, c), w in cells_w.items()}, "blocks_used": used,
           "structural_exclusions": obs_desc, "missing_by_reason": reasons, "options": OPTIONS, "grid": rows}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"holdout_structural_worstcase_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"{jp.stem}.md").write_text(markdown(res, jp))
    print(f"holdout_structural_worstcase: wrote {jp.relative_to(ROOT)}")


def markdown(r: dict, jp: Path) -> str:
    labs = list(r["structural_exclusions"])
    ests = [x["crossed_decisional_pp"] for x in r["grid"]]
    lo, hi = min(ests, key=lambda d: d["est"]), max(ests, key=lambda d: d["est"])
    L = [f"> **{r['label']}**", "", f"**TL;DR** Re-including the two structurally excluded tasks with any bounding unit G moves "
         f"G_all between {lo['est']:+.2f} [{lo['ci90'][0]:+.2f}, {lo['ci90'][1]:+.2f}] and {hi['est']:+.2f} "
         f"[{hi['ci90'][0]:+.2f}, {hi['ci90'][1]:+.2f}] pp (crossed 90%); readings: "
         f"{sorted({x['readings']['reading'] for x in r['grid']})}. Frozen: -4.57 [-7.17, -1.96], inconclusive.", "",
         f"# Holdout structural-exclusion sensitivity ({r['utc']})", "", f"JSON `{jp.relative_to(ROOT)}`. Inputs: "
         + "; ".join(f"{k} `{v if isinstance(v, str) else json.dumps(v)}`" for k, v in r["inputs"].items()), "",
         f"Cell weights {json.dumps(r['cells_weights'])}; blocks {r['blocks_used']}.", "", "## Excluded tasks", ""]
    for k, v in r["structural_exclusions"].items():
        L.append(f"- {k}: {v['task']}; observed (structurally dropped) units in {v['n_observed']} blocks, {v['n_divergent']} divergent, "
                 f"G {v['observed_G']}; other reasons {v['other_unit_reasons']}")
    L += ["", "## G_all (pp), crossed task x block 90% interval (decisional), block t alongside", "",
          f"| {labs[0]} | {labs[1]} | G_all | crossed 90% | block-t 90% | reading | +-5 pp small |", "|---|---|---|---|---|---|---|"]
    for x in r["grid"]:
        c, b, rd = x["crossed_decisional_pp"], x["block_t_pp"], x["readings"]
        L.append(f"| {x['options'][labs[0]]} | {x['options'][labs[1]]} | {c['est']:+.2f} | [{c['ci90'][0]:+.2f}, {c['ci90'][1]:+.2f}] | "
                 f"[{b['ci90'][0]:+.2f}, {b['ci90'][1]:+.2f}] | {rd['reading']} | {rd['sensitivity_5pp']['small_average_effect_pm5pp']} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
