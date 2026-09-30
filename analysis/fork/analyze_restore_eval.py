"""Closed-loop restoration / residual-dose arms (W40, pert_*_fdev): paired Q vs arm vs BF16 success and turnover.

Runs (all must be admitted in the integrity-gated snapshot, with the same prompt nonce per block):
  arm   a6k2_pert_<model>_<cell>_<arm>_<block>     (restore_<module set> / resid_a<alpha>; scripts/a6000/derived.py)
  Q     a6k2_<model>_<cell>_<block>                (the dev-block Q run of the same checkpoint)
  BF16  a6k2_<model>_bfpair_<block>                (BF16 on the same nonce)
Unit = task x block, used only where all three episodes exist and none is an infrastructure episode (the snapshot's
infra_missing list). Y = DB success for retail/airline (db_match with a user_stop/agent_stop ending), official task-basis
success for telecom (official_reward == 1).
Per model x cell x arm:
  - success of Q, arm and BF16;
  - paired differences arm - Q, BF16 - Q and arm - BF16;
  - gap closed = (arm - Q) / (BF16 - Q), a ratio of the bootstrap means; undefined when the Q-BF16 gap is 0 in a draw;
  - turnover vs Q (P(Y_arm != Y_Q), fix = P(arm 1, Q 0), break = P(arm 0, Q 1)) and vs BF16.
Intervals come from the hierarchical bootstrap of analysis/fork/analyze_dev.py (tasks, then blocks within task; B = 2000;
seed 20261001; draws shared by every arm, so arm contrasts are paired).
Idempotent: an output with the same input fingerprint (script, snapshot, every run file sha) is not rewritten.

usage: python analysis/fork/analyze_restore_eval.py --snapshot <snapshot.json> [--models q4 q8]
-> analysis/fork/out/restore_eval_<UTC>.{json,md}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_dev import Boot, SEED, B_BOOT, sha256, success, summarise  # noqa: E402

OUT = ROOT / "analysis/fork/out"
ARM_RE = re.compile(r"^a6k2_pert_(q\d+)_(gptq_w4_d1|awq_w4)_(.+)_(f\d\d|q\d+)$")


def parse_arm(rid: str):
    """-> (model, cell, arm, block) for an arm run id, else None."""
    m = ARM_RE.match(rid)
    return m.groups() if m else None


def episodes(run_id: str, dom: str, fr: dict, det: dict) -> dict[str, int] | None:
    p = ROOT / "runs" / run_id / dom / "trajectory.jsonl"
    if not p.exists() or sha256(p) != fr["files"]["trajectory.jsonl"]["sha256"]:
        return None
    infra = set(map(str, (det or {}).get("infra_missing") or fr.get("infra_missing") or []))
    out = {}
    for ln in open(p):
        t = json.loads(ln)
        if str(t["task_id"]) in infra or t.get("termination_reason") == "infrastructure_error":
            continue
        out[f"{dom}:{t['task_id']}"] = success(dom, t)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--B", type=int, default=B_BOOT)
    a = ap.parse_args()
    t0 = time.time()
    snap = json.load(open(a.snapshot))
    fz, det = snap["frozen"], snap.get("detail", {})
    arms = defaultdict(list)  # (model, cell, arm) -> [(block, arm run id)]
    for rid in fz:
        g = parse_arm(rid)
        if g and (not a.models or g[0] in a.models):
            arms[g[:3]].append((g[3], rid))
    if not arms:
        print("analyze_restore_eval: no admitted restoration arm runs (a6k2_pert_<model>_<cell>_<arm>_<block>) in the snapshot yet; nothing to do.")
        return
    files, units, skipped = {}, defaultdict(list), []
    for (model, cell, arm), blocks in sorted(arms.items()):
        for blk, arm_rid in sorted(blocks):
            ids = {"arm": arm_rid, "Q": f"a6k2_{model}_{cell}_{blk}", "B": f"a6k2_{model}_bfpair_{blk}"}
            for dom in sorted(fz[ids["arm"]]):
                if not all(dom in (fz.get(r) or {}) for r in ids.values()):
                    skipped.append({"arm": ids["arm"], "domain": dom, "reason": "Q or BF16 run not admitted"})
                    continue
                nonces = {k: fz[r][dom].get("prompt_nonce") for k, r in ids.items()}
                if len(set(nonces.values())) != 1:
                    skipped.append({"arm": ids["arm"], "domain": dom, "reason": f"nonce mismatch {nonces}"})
                    continue
                ep = {k: episodes(r, dom, fz[r][dom], (det.get(r) or {}).get(dom)) for k, r in ids.items()}
                if any(v is None for v in ep.values()):
                    skipped.append({"arm": ids["arm"], "domain": dom, "reason": "trajectory differs from the snapshot"})
                    continue
                for k, r in ids.items():
                    files[f"runs/{r}/{dom}/trajectory.jsonl"] = fz[r][dom]["files"]["trajectory.jsonl"]["sha256"]
                for task in sorted(set(ep["arm"]) & set(ep["Q"]) & set(ep["B"])):
                    units[(model, cell, arm)].append({"task": task, "block": blk, "domain": dom,
                                                      "Y": {"arm": ep["arm"][task], "Q": ep["Q"][task], "B": ep["B"][task]}})
    script_sha = sha256(__file__)
    fp = hashlib.sha256(json.dumps({"script": script_sha, "dev": sha256(ROOT / "analysis/fork/analyze_dev.py"),
                                    "snapshot": sha256(a.snapshot), "files": files, "models": a.models, "B": a.B},
                                   sort_keys=True).encode()).hexdigest()[:16]
    OUT.mkdir(parents=True, exist_ok=True)
    for p in sorted(OUT.glob("restore_eval_*.json")):
        try:
            if json.load(open(p)).get("input_fingerprint") == fp:
                print(f"analyze_restore_eval: unchanged inputs (fingerprint {fp}); existing output {p.relative_to(ROOT)}")
                return
        except Exception:
            continue
    allu = [u for v in units.values() for u in v]
    if not allu:
        print(f"analyze_restore_eval: arm runs found but no complete Q/arm/BF16 triples yet ({len(skipped)} skipped); nothing to do.")
        return
    bo = defaultdict(set)
    for u in allu:
        bo[u["task"]].add(u["block"])
    boot = Boot(sorted(bo), {k: sorted(v) for k, v in bo.items()}, B=a.B)

    def stat(us, fn):
        for u in us:
            u["E"] = {"x": fn(u["Y"])}
        X, M = boot.arrays(us, "x")
        return boot.task_mean(X, M)

    res_arms = {}
    for key, us in sorted(units.items()):
        m, c, arm = key
        r = {"n_units": len(us), "n_tasks": len({u["task"] for u in us}), "blocks": sorted({u["block"] for u in us}),
             "domains": sorted({u["domain"] for u in us})}
        fns = {"success_Q": lambda y: y["Q"], "success_arm": lambda y: y["arm"], "success_B": lambda y: y["B"],
               "arm_minus_Q": lambda y: y["arm"] - y["Q"], "B_minus_Q": lambda y: y["B"] - y["Q"], "arm_minus_B": lambda y: y["arm"] - y["B"],
               "turnover_vs_Q": lambda y: int(y["arm"] != y["Q"]), "fix_vs_Q": lambda y: int(y["arm"] == 1 and y["Q"] == 0),
               "break_vs_Q": lambda y: int(y["arm"] == 0 and y["Q"] == 1), "turnover_vs_B": lambda y: int(y["arm"] != y["B"]),
               "turnover_Q_vs_B": lambda y: int(y["Q"] != y["B"])}
        raw = {k: stat(us, f) for k, f in fns.items()}
        r["pp"] = {k: summarise(*v) for k, v in raw.items()}
        num, den = raw["arm_minus_Q"], raw["B_minus_Q"]
        ok = np.abs(den[1]) > 1e-12
        gc = num[1][ok] / den[1][ok]
        r["gap_closed"] = {"est": round(num[0] / den[0], 3) if abs(den[0]) > 1e-12 else None,
                           "ci95": [round(float(x), 3) for x in np.percentile(gc, [2.5, 97.5])] if ok.sum() > 10 else None,
                           "draws_defined": int(ok.sum()), "note": "ratio of bootstrap means; unstable when BF16 - Q is near 0"}
        res_arms[f"{m}:{c}:{arm}"] = r
    res = {"analysis": "analysis/fork/analyze_restore_eval.py", "input_fingerprint": fp,
           "snapshot": {"id": snap.get("snapshot_id"), "path": str(Path(a.snapshot).resolve()), "sha256": sha256(a.snapshot)},
           "script": {"path": str(Path(__file__).resolve()), "sha256": script_sha,
                      "git_head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "bootstrap": {"B": a.B, "seed": SEED, "scheme": "tasks, then blocks within task; draws shared by all arms"},
           "success_definition": {"retail/airline": "DB success", "telecom": "official task-basis success"},
           "arms": res_arms, "skipped": skipped, "input_files": files, "seconds": round(time.time() - t0, 1)}
    utc = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    jp = OUT / f"restore_eval_{utc}.json"
    jp.write_text(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))

    def f(x):
        return f"{x['est']:+.1f} [{x['ci95'][0]:+.1f}, {x['ci95'][1]:+.1f}]"
    L = [f"**TL;DR** Restoration arms vs Q vs BF16 on shared nonces, {len(res_arms)} arms, "
         f"{sum(v['n_units'] for v in res_arms.values())} paired units; {len(skipped)} run-domains skipped. Snapshot {res['snapshot']['id']}.",
         "", f"# Restoration closed-loop arms ({res['utc']})", "", f"Full numbers: `{jp.relative_to(ROOT) if jp.is_relative_to(ROOT) else jp}`. pp; 95% hierarchical bootstrap.", "",
         "| arm | units | Q | arm | BF16 | arm-Q | BF16-Q | gap closed | turnover vs Q (fix/break) |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res_arms.items():
        p = v["pp"]
        L.append(f"| {k} | {v['n_units']} | {p['success_Q']['est']:.1f} | {p['success_arm']['est']:.1f} | {p['success_B']['est']:.1f} | "
                 f"{f(p['arm_minus_Q'])} | {f(p['B_minus_Q'])} | {v['gap_closed']['est']} | {p['turnover_vs_Q']['est']:.1f} "
                 f"({p['fix_vs_Q']['est']:.1f}/{p['break_vs_Q']['est']:.1f}) |")
    (OUT / f"restore_eval_{utc}.md").write_text("\n".join(L) + "\n")
    print(f"analyze_restore_eval: wrote {jp.relative_to(ROOT) if jp.is_relative_to(ROOT) else jp} ({res['seconds']} s)")


if __name__ == "__main__":
    main()
