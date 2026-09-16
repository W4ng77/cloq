"""Novelty of Q0-visited states against the draw-matched FP-Traj calibration support.

For every decision state x of a Q0 calibration rollout,

    nu(x) = min over z in the draw's fp_traj support of ( 1 - cosine(phi(x), phi(z)) )

with phi the frozen BF16 final-layer hidden state at the action-generation boundary, the same
representation the v0 occupancy analysis used. Each state also carries a post-divergence flag:
true once the Q0 context differs from the paired BF16 trajectory on the same calibration task.

CLOQ-Novel picks, per Q-half task, the highest-novelty post-divergence state.

usage:
  python -m cloq.novelty --draw c1 --q-run q0_v1_c1 --fp-calib manifests/v1/calib_fp_traj_c1.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from cloq import config as C
from cloq.divergence import analyze_task, load_decisions_by_task
from cloq.metrics import load_decisions
from cloq.occupancy import _load_reps, _normalize


def support_matrix(fp_calib: Path) -> np.ndarray:
    """phi of the draw's fp_traj calibration states, read from the BF16 run's representations."""
    man = json.load(open(fp_calib))
    cache: dict[tuple, dict] = {}
    vecs, missing = [], []
    for c in man["contexts"]:
        key = (c["run_id"], c["domain"])
        if key not in cache:
            cache[key] = _load_reps(*key)
        r = cache[key].get(c["prompt_sha256"])
        if r is None:
            missing.append((c["domain"], c["task_id"], c["decision_idx"]))
            continue
        vecs.append(r["last"])
    if missing:
        raise SystemExit(
            f"{len(missing)} fp_traj support states have no stored representation, e.g. {missing[:3]}. "
            f"Run `python -m cloq.occupancy extract --runs {man['fp_run']}` first."
        )
    return np.stack(vecs)


def post_divergence_flags(q_run: str, bf16_run: str, cal_ids: dict[str, list[str]]) -> dict[tuple, int | None]:
    """First decision index whose context differs from BF16, per calibration task."""
    out = {}
    for dom, ids in cal_ids.items():
        fp = load_decisions_by_task(bf16_run, dom, set(ids))
        q = load_decisions_by_task(q_run, dom, set(ids))
        for tid in ids:
            if tid in fp and tid in q:
                out[(dom, tid)] = analyze_task(fp[tid], q[tid])["t_align"]
    return out


def run(draw: str, q_run: str, fp_calib: Path, bf16_run: str, split_path: Path, out_path: Path) -> dict:
    split = json.load(open(split_path))
    domains = list(split["domains"].keys())
    cal_ids = {d: split["domains"][d]["calibration"] for d in domains}
    S = _normalize(support_matrix(fp_calib))
    tstar = post_divergence_flags(q_run, bf16_run, cal_ids)

    per_state, by_task = {}, defaultdict(int)
    for dom in domains:
        reps = _load_reps(q_run, dom)
        allowed = set(cal_ids[dom])
        decs = [d for d in load_decisions(C.RUNS_DIR / q_run / dom) if d["task_id"] in allowed]
        sha2idx = {}
        X = []
        for d in decs:
            r = reps.get(d["prompt_sha256"])
            if r is None:
                continue
            sha2idx[(d["task_id"], d["decision_idx"])] = len(X)
            X.append(r["last"])
        if not X:
            continue
        Xn = _normalize(np.stack(X))
        nu = 1.0 - (Xn @ S.T).max(axis=1)
        for d in decs:
            k = (d["task_id"], d["decision_idx"])
            if k not in sha2idx:
                continue
            ts = tstar.get((dom, d["task_id"]))
            per_state[f"{dom}|{d['task_id']}|{d['decision_idx']}"] = {
                "novelty": float(nu[sha2idx[k]]),
                "post_divergence": bool(ts is not None and d["decision_idx"] >= ts),
                "t_align": ts,
            }
            by_task[(dom, d["task_id"])] += 1

    vals = np.array([v["novelty"] for v in per_state.values()])
    postv = np.array([v["novelty"] for v in per_state.values() if v["post_divergence"]])
    prev = np.array([v["novelty"] for v in per_state.values() if not v["post_divergence"]])
    res = {
        "draw": draw, "q_run": q_run, "bf16_run": bf16_run, "fp_calib": str(fp_calib),
        "support_size": int(S.shape[0]), "n_states": len(per_state), "n_tasks": len(by_task),
        "n_tasks_with_post_divergence": int(sum(1 for k in by_task if tstar.get(k) is not None)),
        "novelty_mean": float(vals.mean()), "novelty_median": float(np.median(vals)),
        "novelty_max": float(vals.max()),
        "novelty_mean_post_divergence": float(postv.mean()) if len(postv) else None,
        "novelty_mean_pre_divergence": float(prev.mean()) if len(prev) else None,
        "n_post_divergence_states": int(len(postv)), "n_pre_divergence_states": int(len(prev)),
        "per_state": per_state,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res))
    print(json.dumps({k: v for k, v in res.items() if k != "per_state"}, indent=2))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draw", required=True)
    ap.add_argument("--q-run", required=True)
    ap.add_argument("--fp-calib", required=True)
    ap.add_argument("--bf16-run", default="bf16")
    ap.add_argument("--split", default=str(C.MANIFEST_DIR / "task_split_v0.json"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = Path(a.out) if a.out else (C.MANIFEST_DIR / "v1" / f"novelty_{a.draw}.json")
    if out.exists():
        raise SystemExit(f"{out} exists (frozen); refusing to overwrite")
    run(a.draw, a.q_run, Path(a.fp_calib), a.bf16_run, Path(a.split), out)


if __name__ == "__main__":
    main()
