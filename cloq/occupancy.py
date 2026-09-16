"""Occupancy / context-shift analysis (plan section 17).

Representation extractor: the frozen BF16 model (HF transformers), replaying
the exact stored prompt token ids.
  primary   phi_last : final-layer hidden state (after final norm) at the last prompt token
  secondary phi_obs  : mean final-layer hidden state over the tokens of the most recent
                       observation (the last user or tool message block)

Steps:
  1. `extract`: for a list of runs, compute phi for every decision record -> runs/<run>/<domain>/reps.npz
  2. `analyze`: support distances D_supp(x; C) = min_z 1 - cos(phi(x), phi(z)) of visited states
     against each calibration buffer, aligned at first divergence; MMD between FP and Q states.

usage:
  python -m cloq.occupancy extract --runs bf16 static_eval fp_traj_eval cloq_eval q0_fp_traj --domains retail airline
  python -m cloq.occupancy analyze --bf16-run bf16 --arm-runs static_eval fp_traj_eval cloq_eval \
        --calib static=manifests/calib_static.json fp_traj=manifests/calib_fp_traj.json cloq=manifests/calib_cloq.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from cloq import config as C
from cloq.metrics import load_decisions, read_jsonl


# ----------------------------------------------------------------------------
# 1. extraction
# ----------------------------------------------------------------------------


def _last_observation_span(prompt_ids: list[int], tok) -> tuple[int, int]:
    """Token span [start, end) of the most recent user/tool block before the generation prompt.

    The prompt ends with '<|im_start|>assistant\n'. The last observation block starts at the last
    '<|im_start|>user' before that (tool results are wrapped in a user block by the template).
    """
    im_start = tok.convert_tokens_to_ids("<|im_start|>")
    n = len(prompt_ids)
    # positions of <|im_start|>
    pos = [i for i, t in enumerate(prompt_ids) if t == im_start]
    if len(pos) < 2:
        return 0, n
    gen_start = pos[-1]  # '<|im_start|>assistant\n' generation prompt
    obs_start = pos[-2]
    return obs_start, gen_start


def extract(run_ids: list[str], domains: list[str], device: str = "cuda", batch_tokens_limit: int = 9000) -> None:
    import torch
    from transformers import AutoModelForCausalLM

    from cloq.context_policy import get_tokenizer

    import os

    tok = get_tokenizer()
    rep_model = os.environ.get("CLOQ_REP_MODEL")  # test hook only; the protocol extractor is the frozen BF16 model
    if rep_model:
        model = AutoModelForCausalLM.from_pretrained(rep_model, dtype=torch.float32 if device == "cpu" else torch.bfloat16, attn_implementation="sdpa").to(device).eval()
    else:
        model = AutoModelForCausalLM.from_pretrained(C.MODEL_ID, revision=C.MODEL_REVISION, dtype=torch.bfloat16, attn_implementation="sdpa").to(device).eval()
    for run_id in run_ids:
        for domain in domains:
            run_dir = C.RUNS_DIR / run_id / domain
            out = run_dir / "reps.npz"
            if out.exists() or not (run_dir / "decisions.jsonl").exists():
                print("skip", run_dir); continue
            decs = load_decisions(run_dir)
            keys, last, obs = [], [], []
            with torch.no_grad():
                for d in decs:
                    ids = d["prompt_token_ids"]
                    x = torch.tensor([ids], dtype=torch.long, device=device)
                    h = model.model(input_ids=x, use_cache=False).last_hidden_state[0].float()  # [T, H], after final norm
                    s, e = _last_observation_span(ids, tok)
                    last.append(h[-1].cpu().numpy())
                    obs.append(h[s:e].mean(0).cpu().numpy())
                    keys.append(f"{d['task_id']}|{d['decision_idx']}|{d['prompt_sha256']}")
            np.savez_compressed(
                out, keys=np.array(keys),
                last=np.stack(last).astype(np.float32), obs=np.stack(obs).astype(np.float32),
                extractor=np.array([rep_model or f"{C.MODEL_ID}@{C.MODEL_REVISION}"]),
            )
            print("wrote", out, len(keys))


# ----------------------------------------------------------------------------
# 2. analysis
# ----------------------------------------------------------------------------


def _load_reps(run_id: str, domain: str) -> dict[str, dict[str, np.ndarray]]:
    path = C.RUNS_DIR / run_id / domain / "reps.npz"
    z = np.load(path)
    expected = f"{C.MODEL_ID}@{C.MODEL_REVISION}"
    got = str(z["extractor"][0]) if "extractor" in z else "<unrecorded>"
    if got != expected:
        raise ValueError(
            f"{path} was written by representation extractor {got!r}, not the frozen {expected!r}. "
            "Delete it and re-run `python -m cloq.occupancy extract`."
        )
    out = {}
    for k, a, b in zip(z["keys"], z["last"], z["obs"]):
        tid, idx, sha = str(k).split("|")
        out[sha] = {"last": a, "obs": b, "task_id": tid, "decision_idx": int(idx)}
    return out


def _normalize(m: np.ndarray) -> np.ndarray:
    return m / np.clip(np.linalg.norm(m, axis=1, keepdims=True), 1e-8, None)


def support_distance(X: np.ndarray, Cset: np.ndarray) -> np.ndarray:
    Xn, Cn = _normalize(X), _normalize(Cset)
    sims = Xn @ Cn.T
    return 1.0 - sims.max(axis=1)


def mmd_rbf(X: np.ndarray, Y: np.ndarray, gamma: float | None = None, max_n: int = 2000, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    if len(X) > max_n:
        X = X[rng.choice(len(X), max_n, replace=False)]
    if len(Y) > max_n:
        Y = Y[rng.choice(len(Y), max_n, replace=False)]
    X, Y = _normalize(X), _normalize(Y)
    Z = np.vstack([X, Y])
    d2 = np.maximum(0.0, 2.0 - 2.0 * (Z @ Z.T))  # squared euclidean on unit sphere
    if gamma is None:
        med = np.median(d2[d2 > 0]) if (d2 > 0).any() else 1.0
        gamma = 1.0 / med
    K = np.exp(-gamma * d2)
    n, m = len(X), len(Y)
    Kxx, Kyy, Kxy = K[:n, :n], K[n:, n:], K[:n, n:]
    return float((Kxx.sum() - np.trace(Kxx)) / (n * (n - 1)) + (Kyy.sum() - np.trace(Kyy)) / (m * (m - 1)) - 2 * Kxy.mean())


def calib_reps(manifest_path: Path, rep_cache: dict[str, dict], rep: str) -> np.ndarray:
    man = json.load(open(manifest_path))
    vecs = []
    missing = 0
    for c in man["contexts"]:
        key = (c["run_id"], c["domain"])
        r = rep_cache.get(key)
        if r is None or c["prompt_sha256"] not in r:
            missing += 1; continue
        vecs.append(r[c["prompt_sha256"]][rep])
    if missing:
        print(f"warning: {missing} calibration contexts without representation ({manifest_path})")
    return np.stack(vecs)


def analyze(bf16_run: str, arm_runs: dict[str, str], calibs: dict[str, Path], domains: list[str], eval_file: Path, out_path: Path, rep: str = "last") -> dict:
    eval_ids = json.load(open(eval_file))
    rep_cache: dict[tuple[str, str], dict] = {}

    def reps(run_id, domain):
        key = (run_id, domain)
        if key not in rep_cache:
            rep_cache[key] = _load_reps(run_id, domain)
        return rep_cache[key]

    # calibration supports (contexts may come from bf16 run or q0 run; load lazily by run_id)
    for name, path in calibs.items():
        man = json.load(open(path))
        for c in man["contexts"]:
            reps(c["run_id"], c["domain"])
    supports = {name: calib_reps(path, rep_cache, rep) for name, path in calibs.items()}

    results = {"rep": rep, "domains": {}}
    for domain in domains:
        ids = set(eval_ids[domain])
        fp = reps(bf16_run, domain)
        fp_states = {sha: v for sha, v in fp.items() if v["task_id"] in ids}
        Xfp = np.stack([v[rep] for v in fp_states.values()])
        dom_res = {"n_fp_states": len(Xfp), "fp_to_support": {}, "arms": {}}
        for sname, S in supports.items():
            dom_res["fp_to_support"][sname] = float(np.mean(support_distance(Xfp, S)))
        for arm, run_id in arm_runs.items():
            q = reps(run_id, domain)
            q_states = {sha: v for sha, v in q.items() if v["task_id"] in ids}
            Xq = np.stack([v[rep] for v in q_states.values()])
            div = json.load(open(C.RUNS_DIR / run_id / domain / "divergence.json"))
            tstar = {r["task_id"]: r.get("t_align", r["t_star"]) for r in div["per_task"]}
            arm_res = {"n_q_states": len(Xq), "q_to_support": {}, "pre_post_divergence": {}, "aligned_curve": {}}
            for sname, S in supports.items():
                d = support_distance(Xq, S)
                arm_res["q_to_support"][sname] = float(np.mean(d))
                pre, post = [], []
                curve = defaultdict(list)
                for (sha, v), dist in zip(q_states.items(), d):
                    ts = tstar.get(v["task_id"])
                    if ts is None:
                        pre.append(dist); continue
                    rel = v["decision_idx"] - ts  # ts = t_context: rel < 0 means the context still matched BF16
                    curve[rel].append(dist)
                    (pre if rel < 0 else post).append(dist)
                arm_res["pre_post_divergence"][sname] = {
                    "pre_mean": float(np.mean(pre)) if pre else None, "n_pre": len(pre),
                    "post_mean": float(np.mean(post)) if post else None, "n_post": len(post),
                }
                arm_res["aligned_curve"][sname] = {str(k): [float(np.mean(v)), len(v)] for k, v in sorted(curve.items()) if -10 <= k <= 15}
            arm_res["mmd_fp_vs_q"] = mmd_rbf(Xfp, Xq)
            # MMD null: FP split in halves
            rng = np.random.default_rng(0)
            perm = rng.permutation(len(Xfp))
            arm_res["mmd_fp_half_vs_half"] = mmd_rbf(Xfp[perm[: len(perm) // 2]], Xfp[perm[len(perm) // 2:]])
            dom_res["arms"][arm] = arm_res
        results["domains"][domain] = dom_res
    out_path.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2)[:6000])
    return results


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--runs", nargs="+", required=True)
    e.add_argument("--domains", nargs="+", default=C.FROZEN["benchmark"]["domains"])
    e.add_argument("--device", default="cuda")
    a = sub.add_parser("analyze")
    a.add_argument("--bf16-run", default="bf16")
    a.add_argument("--arm-runs", nargs="+", required=True, help="arm=run_id ...")
    a.add_argument("--calib", nargs="+", required=True, help="name=manifest.json ...")
    a.add_argument("--domains", nargs="+", default=C.FROZEN["benchmark"]["domains"])
    a.add_argument("--eval-file", default=str(C.MANIFEST_DIR / "eval_tasks_v0.json"))
    a.add_argument("--rep", default="last", choices=["last", "obs"])
    a.add_argument("--out", default=str(C.PROJECT_ROOT / "analysis" / "occupancy_last.json"))
    args = ap.parse_args()
    if args.cmd == "extract":
        extract(args.runs, args.domains, args.device)
    else:
        arm_runs = dict(kv.split("=", 1) for kv in args.arm_runs)
        calibs = {k: Path(v) for k, v in (kv.split("=", 1) for kv in args.calib)}
        out = Path(args.out)
        if args.rep != "last" and out.name == "occupancy_last.json":
            out = out.with_name(f"occupancy_{args.rep}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        analyze(args.bf16_run, arm_runs, calibs, args.domains, Path(args.eval_file), out, args.rep)


if __name__ == "__main__":
    main()
