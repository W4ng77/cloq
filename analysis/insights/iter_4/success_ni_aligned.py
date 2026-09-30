"""success_ni_aligned (W64): Q - BF16 success on exactly the checkpoints, tasks and nonce blocks the forks use.

Why (GPT-6.1 code review, W64): success_ni.py averages the calibration draws d1-d4 of each method. That is a statement
about the population of calibration draws, not about d1, the checkpoint every fork uses (q4 GPTQ d1 alone is +5.7 pp).
This script is the aligned analysis; success_ni.py stays as the "population of calibration draws" analysis.

Cells: the fork cells of manifests/fork/dev_blocks_v1.json, q4/q8 x {gptq_w4_d1, awq_w4} (both calibration draw c1).
Blocks: the blocks listed in the fork dev tasks' q_blocks (queue fork_dev_<m>_<cell>_g*; all 20: q3-q5, f01-f17), each
  paired on its nonce: Q = a6k2_<m>_<cell>_<blk>, BF16 = a6k2_<m>_bfpair_<blk>, both admitted in the integrity snapshot
  with the same prompt nonce and unchanged trajectory sha.
Tasks: every retail + airline task scored in both runs of the block (as in the forks; no W17 drop; infrastructure
  episodes of either run excluded). Outcome = analysis/fork/analyze_dev.success (DB success with a normal ending).
Estimand per cell: Delta = mean over (task, block) units of y_Q - y_BF16 (equal unit weights, the fork population).
Inference: crossed task x block bootstrap, B = 2000, seed 20261001: task ids resampled with replacement and COMPLETE
  blocks (nonces) resampled with replacement, independently, unit weight = w_task x v_block. The same draws are used
  for every cell and model: q4 and q8 (and GPTQ / AWQ) share task ids and nonces, so pools are computed per draw from
  the joint resample and never assume independence. A block-only variant (fixed task set, blocks resampled) is also
  reported. [TODO once agent a5468c1 pushes the corrected analysis/fork/analyze_dev.Boot (complete-block + crossed):
  switch to that implementation; this file implements the same scheme locally and is labelled so.]
Tests (eps = 3 pp primary, 5 pp sensitivity): non-inferiority passes iff the 5th percentile > -eps; TOST equivalence
  passes iff the 90% interval (5th, 95th) lies inside (-eps, +eps); ordinary two-sided 95% percentile interval and
  bootstrap p = 2 min(P*(D <= 0), P*(D >= 0)).
Pools (equal weights, joint draws): per model (GPTQ, AWQ), per method (q4, q8), all four cells.

usage: python analysis/insights/iter_4/success_ni_aligned.py [--snapshot <snapshot.json>] [--B 2000]
-> analysis/insights/iter_4/out/success_ni_ALIGNED_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT / "analysis/fork"))
from analyze_dev import success  # noqa: E402

QUEUE = Path("/data/ziyangs/cloq_work/queue")
OUT = ROOT / "analysis/insights/iter_4/out"
CELLS = [("q4", "gptq_w4_d1"), ("q4", "awq_w4"), ("q8", "gptq_w4_d1"), ("q8", "awq_w4")]
DOMS = ("retail", "airline")
EPS = (3.0, 5.0)
SEED, B_BOOT = 20261001, 2000


def sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fork_blocks(model: str, cell: str) -> list[str]:
    """Blocks named in the fork dev tasks' q_blocks for this cell (the population the forks sample)."""
    out = set()
    for d in ("done", "running", "todo"):
        for f in glob.glob(str(QUEUE / d / f"fork_dev_{model}_{cell}_g*.json")):
            for rid, _dom in json.load(open(f)).get("fork", {}).get("q_blocks", []):
                out.add(rid.rsplit("_", 1)[1])
    if not out:  # fall back to the frozen block manifest
        man = json.load(open(ROOT / "manifests/fork/dev_blocks_v1.json"))
        out = set(man["existing_blocks"]) | set(man["new_blocks"])
    return sorted(out)


def episodes(run: str, dom: str, fr: dict) -> dict | None:
    p = ROOT / "runs" / run / dom / "trajectory.jsonl"
    if not p.exists() or sha256(p) != fr["files"]["trajectory.jsonl"]["sha256"]:
        return None
    infra = set(map(str, fr.get("infra_missing") or []))
    out = {}
    for ln in open(p):
        t = json.loads(ln)
        if str(t["task_id"]) in infra or t.get("termination_reason") == "infrastructure_error":
            continue
        out[f"{dom}:{t['task_id']}"] = success(dom, t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--B", type=int, default=B_BOOT)
    a = ap.parse_args()
    snap_p = a.snapshot or sorted(glob.glob(str(ROOT / "analysis/insights/iter_3/out/snapshot_auto_*.json")))[-1]
    snap = json.load(open(snap_p))
    fz = snap["frozen"]
    units, files, skipped, blocks_used = {}, {}, [], {}
    for m, c in CELLS:
        us = []
        blks = fork_blocks(m, c)
        blocks_used[f"{m}:{c}"] = blks
        for b in blks:
            q, bf = f"a6k2_{m}_{c}_{b}", f"a6k2_{m}_bfpair_{b}"
            for d in DOMS:
                if d not in (fz.get(q) or {}) or d not in (fz.get(bf) or {}):
                    skipped.append({"cell": f"{m}:{c}", "block": b, "domain": d, "reason": "Q or BF16 not admitted"})
                    continue
                if fz[q][d].get("prompt_nonce") != fz[bf][d].get("prompt_nonce"):
                    skipped.append({"cell": f"{m}:{c}", "block": b, "domain": d, "reason": "nonce mismatch"})
                    continue
                eq, eb = episodes(q, d, fz[q][d]), episodes(bf, d, fz[bf][d])
                if eq is None or eb is None:
                    skipped.append({"cell": f"{m}:{c}", "block": b, "domain": d, "reason": "trajectory differs from snapshot"})
                    continue
                files[f"runs/{q}/{d}/trajectory.jsonl"] = fz[q][d]["files"]["trajectory.jsonl"]["sha256"]
                files[f"runs/{bf}/{d}/trajectory.jsonl"] = fz[bf][d]["files"]["trajectory.jsonl"]["sha256"]
                for t in sorted(set(eq) & set(eb)):
                    us.append((t, b, eq[t], eb[t]))
        units[f"{m}:{c}"] = us
    tasks = sorted({u[0] for us in units.values() for u in us})
    blocks = sorted({u[1] for us in units.values() for u in us})
    ti, bi = {t: i for i, t in enumerate(tasks)}, {b: i for i, b in enumerate(blocks)}
    rng = np.random.default_rng(SEED)
    B = a.B
    W = np.stack([np.bincount(rng.integers(0, len(tasks), len(tasks)), minlength=len(tasks)) for _ in range(B)]).astype(float)
    V = np.stack([np.bincount(rng.integers(0, len(blocks), len(blocks)), minlength=len(blocks)) for _ in range(B)]).astype(float)

    def cell_arrays(us):
        T = np.array([ti[u[0]] for u in us])
        K = np.array([bi[u[1]] for u in us])
        return T, K, np.array([u[2] for u in us], float), np.array([u[3] for u in us], float)

    draws, point = {}, {}
    for k, us in units.items():
        T, K, yq, yb = cell_arrays(us)
        z = yq - yb
        wc = W[:, T] * V[:, K]           # crossed
        wb = V[:, K]                       # block-only (fixed tasks)
        point[k] = {"Q": 100 * yq.mean(), "B": 100 * yb.mean(), "D": 100 * z.mean()}
        draws[k] = {"crossed": 100 * (wc * z).sum(1) / np.maximum(wc.sum(1), 1e-12),
                    "block_only": 100 * (wb * z).sum(1) / np.maximum(wb.sum(1), 1e-12)}

    def summ(pt, dr):
        lo95, hi95 = np.percentile(dr, [2.5, 97.5])
        lo90, hi90 = np.percentile(dr, [5, 95])
        p = float(min(1.0, 2 * min((dr <= 0).mean(), (dr >= 0).mean())))
        return {"est_pp": round(pt, 2), "ci95": [round(lo95, 2), round(hi95, 2)], "ci90": [round(lo90, 2), round(hi90, 2)],
                "p_two_sided": round(p, 4),
                "NI": {f"{e:g}pp": bool(lo90 > -e) for e in EPS}, "TOST": {f"{e:g}pp": bool(lo90 > -e and hi90 < e) for e in EPS}}

    res_cells = {}
    for k, us in units.items():
        res_cells[k] = {"n_units": len(us), "n_tasks": len({u[0] for u in us}), "n_blocks": len({u[1] for u in us}),
                        "success_Q_pp": round(point[k]["Q"], 2), "success_BF16_pp": round(point[k]["B"], 2),
                        "crossed": summ(point[k]["D"], draws[k]["crossed"]),
                        "block_only": summ(point[k]["D"], draws[k]["block_only"])}
    pools = {"q4 (GPTQ, AWQ)": ["q4:gptq_w4_d1", "q4:awq_w4"], "q8 (GPTQ, AWQ)": ["q8:gptq_w4_d1", "q8:awq_w4"],
             "GPTQ-W4 d1 (q4, q8)": ["q4:gptq_w4_d1", "q8:gptq_w4_d1"], "AWQ-W4 d1 (q4, q8)": ["q4:awq_w4", "q8:awq_w4"],
             "all four": [k for k in units]}
    res_pools = {}
    for name, ks in pools.items():
        pt = float(np.mean([point[k]["D"] for k in ks]))
        res_pools[name] = {"cells": ks, "crossed": summ(pt, np.mean([draws[k]["crossed"] for k in ks], 0)),
                           "block_only": summ(pt, np.mean([draws[k]["block_only"] for k in ks], 0))}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    res = {"analysis": "analysis/insights/iter_4/success_ni_aligned.py", "utc": utc, "W": "W64",
           "population": "fork-aligned: the d1 checkpoint of each fork cell on the fork's tasks x nonce blocks",
           "contrast_with": "success_ni.py = population of calibration draws (d1-d4 mixture)",
           "snapshot": {"path": snap_p, "id": snap.get("snapshot_id"), "sha256": sha256(snap_p)},
           "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
           "bootstrap": {"B": B, "seed": SEED, "scheme": "crossed: task ids x complete nonce blocks, joint across all cells "
                         "and models (shared task ids and nonces); block_only: fixed tasks, complete blocks",
                         "implementation": "local (switch to analyze_dev.Boot after a5468c1's complete-block/crossed fix)"},
           "eps_pp": EPS, "blocks_used": blocks_used, "cells": res_cells, "pools": res_pools, "skipped": skipped,
           "input_files": files, "script_sha256": sha256(__file__)}
    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / f"success_ni_ALIGNED_{utc}.json"
    jp.write_text(json.dumps(res, indent=1))

    def row(name, r, extra=""):
        c = r["crossed"]
        bo = r["block_only"]
        return (f"| {name} | {extra}{c['est_pp']:+.1f} | [{c['ci95'][0]:+.1f}, {c['ci95'][1]:+.1f}] | [{c['ci90'][0]:+.1f}, {c['ci90'][1]:+.1f}] | "
                f"{'pass' if c['NI']['3pp'] else 'fail'} / {'pass' if c['TOST']['3pp'] else 'fail'} | "
                f"{'pass' if c['TOST']['5pp'] else 'fail'} | {c['p_two_sided']:.3f} | [{bo['ci90'][0]:+.1f}, {bo['ci90'][1]:+.1f}] |")
    L = [f"**TL;DR** Fork-aligned Q - BF16 success (d1 checkpoints, fork tasks x 20 nonce blocks, crossed task x block "
         f"bootstrap, joint across models). Snapshot {snap.get('snapshot_id')}. " + "; ".join(
             f"{k} {v['crossed']['est_pp']:+.1f} pp [{v['crossed']['ci95'][0]:+.1f}, {v['crossed']['ci95'][1]:+.1f}]" for k, v in res_cells.items()),
         "", f"# Success, fork-aligned (W64, {utc})", "",
         "Population: the d1 checkpoint of each fork cell on exactly the forks' tasks and nonce blocks. The d1-d4 mixture "
         "analysis (`success_ni.py`) is the *population of calibration draws* and is not an equivalence statement about d1.",
         f"Full numbers: `{jp.relative_to(ROOT)}`.", "",
         "| cell / pool | Q - BF16 (pp) | 95% CI | 90% CI | NI / TOST at 3 pp | TOST 5 pp | p | 90% CI, fixed tasks |",
         "|---|---|---|---|---|---|---|---|"]
    for k, v in res_cells.items():
        L.append(row(f"{k} (Q {v['success_Q_pp']:.1f}, BF16 {v['success_BF16_pp']:.1f}; {v['n_units']} units)", v))
    for k, v in res_pools.items():
        L.append(row(f"pool: {k}", v))
    (OUT / f"success_ni_ALIGNED_{utc}.md").write_text("\n".join(L) + "\n")
    print(f"wrote {jp.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
