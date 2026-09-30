"""Write the A6000 matrix (docs/A6000_PLAN.md section 3) into the file queue. Idempotent: a task whose id
is already in todo/, running/ or done/ is left alone (failed/ tasks are re-queued only with --retry).

usage: python scripts/a6000/make_tasks.py q4 q8 ...  [--retry] [--only det]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

WORK = Path("/data/ziyangs/cloq_work")
Q = WORK / "queue"
EVAL = "manifests/eval_tasks_v0.json"
CAL = "manifests/cal_tasks_v0.json"
DET = "manifests/a6000/det_tasks.json"
NONCES = ["3f9a1c07", "b84e2d91", "5c0d7e3a", "e21f6b48", "9a7c4f15"]
GAUSS_K = ["0.03", "0.1", "0.3", "1", "3"]
MODEL_PRIORITY = {"q4": 10, "q8": 20, "m24": 30, "l8": 30, "q14": 40, "q30a3": 50, "q32": 60}


def eval_task(tid, model, arm, ckpt, runs, priority, deps=()):
    return {"id": tid, "kind": "eval", "model": model, "arm": arm, "ckpt": ckpt, "runs": runs,
            "priority": priority, "deps": list(deps)}


def run(rid, task_file=EVAL, nonce=None):
    return {"run_id": rid, "task_file": task_file, "nonce": nonce}


def matrix(m: str, prefix: str = "a6000", tid: str = "") -> list[dict]:
    p = MODEL_PRIORITY[m]
    R = f"{prefix}_{m}"
    t = [eval_task(f"{m}_bf16_cal", m, "bf16", {"kind": "bf16"}, [run(f"{R}_bf16_cal", CAL)], 0),
         eval_task(f"{m}_bf16", m, "bf16", {"kind": "bf16"},
                   [run(f"{R}_bf16")] + [run(f"{R}_null_n{i + 1}", nonce=n) for i, n in enumerate(NONCES)], p)]
    for k in GAUSS_K:
        for s in (1, 2):
            t.append(eval_task(f"{m}_gauss{k}_s{s}", m, "gauss", {"kind": "gauss", "k": float(k), "seed": s},
                               [run(f"{R}_gauss{k}_s{s}")], p + 1))
    for b in (8, 4, 3):
        t.append(eval_task(f"{m}_rtn_w{b}", m, "rtn", {"kind": "rtn", "wbits": b},
                           [run(f"{R}_rtn_w{b}_n{i + 1}", nonce=NONCES[i]) for i in range(2)], p + 1))
    for d in ("c1", "c2"):
        t.append({"id": f"{m}_calib_{d}", "kind": "calib", "model": m, "arm": "fp_traj", "draw": d,
                  "fp_run": f"{R}_bf16_cal", "out": f"manifests/{prefix}/{m}/calib_fp_traj_{d}.json",
                  "priority": 0, "deps": [f"{m}_bf16_cal"]})
    for name, kind, bits, d in (("gptq_w4_d1", "gptq", 4, "c1"), ("gptq_w4_d2", "gptq", 4, "c2"),
                                ("awq_w4", "awq", 4, "c1"), ("gptq_w3", "gptq", 3, "c1")):
        t.append(eval_task(f"{m}_{name}", m, kind, {"kind": kind, "wbits": bits,
                                                    "calib": f"manifests/{prefix}/{m}/calib_fp_traj_{d}.json"},
                           [run(f"{R}_{name}_n{i + 1}", nonce=NONCES[i]) for i in range(2)], p - 1,
                           deps=[f"{m}_calib_{d}"]))
    return t


def e5(m: str, prefix: str = "a6000") -> list[dict]:
    """E5 (docs/insights/EXPERIMENTS.md): numerics-flavour null (eager BF16) + weight-only null (gauss k=0.03 s3-s5)."""
    p = MODEL_PRIORITY[m] + 2
    R = f"{prefix}_{m}"
    t = [dict(eval_task(f"{m}_bf16_eager", m, "bf16", {"kind": "bf16"}, [run(f"{R}_bf16_eager")], p),
              serve_extra=["--enforce-eager"])]
    for s in (3, 4, 5):
        t.append(eval_task(f"{m}_gauss0.03_s{s}", m, "gauss", {"kind": "gauss", "k": 0.03, "seed": s},
                           [run(f"{R}_gauss0.03_s{s}")], p))
    return t


def e3(m: str, prefix: str = "a6000", n: int = 400) -> list[dict]:
    """E3 (docs/insights/EXPERIMENTS.md): open-loop D of every matrix cell on the model's BF16 reference contexts."""
    R, tid = f"{prefix}_{m}", ""
    ref = f"{prefix}_{m}_bf16"
    out = []
    for t in matrix(m, prefix) + e5(m, prefix):
        if t["kind"] != "eval" or t["id"].endswith("_cal"):
            continue
        cell = t["id"][len(m) + 1:]
        out.append(dict(t, id=f"{m}_ol_{cell}", runs=[], priority=MODEL_PRIORITY[m] + 100,
                        deps=list(t.get("deps", [])) + [f"{m}_bf16"],
                        openloop={"ref_runs": [ref], "n": n, "out": f"analysis/openloop/{prefix}/{m}/{cell}"}))
    return out


def r1(m: str, prefix: str = "a6000") -> list[dict]:
    """Review-1 (paper/perturbation-equivalence-closed-loop.review.md): sub-grid k (is there a floor below one grid
    step?), k=2 (threshold shape), extra RTN-W4 nonces and gauss k=1 seeds (RTN-W4 vs matched-D noise, I3)."""
    p = MODEL_PRIORITY[m] + 15
    R = f"{prefix}_{m}"
    t = []
    for k in ("0.001", "0.003", "0.01", "2"):
        for s in (1, 2):
            t.append(eval_task(f"{m}_gauss{k}_s{s}", m, "gauss", {"kind": "gauss", "k": float(k), "seed": s},
                               [run(f"{R}_gauss{k}_s{s}")], p))
    for s in (3, 4, 5):
        t.append(eval_task(f"{m}_gauss1_s{s}", m, "gauss", {"kind": "gauss", "k": 1.0, "seed": s},
                           [run(f"{R}_gauss1_s{s}")], p))
    t.append(eval_task(f"{m}_rtn_w4_x", m, "rtn", {"kind": "rtn", "wbits": 4},
                       [run(f"{R}_rtn_w4_n{i + 1}", nonce=NONCES[i]) for i in (2, 3, 4)], p))
    return t


# X1 (docs/insights/PLAN_iter3.md): real deployed formats. Official repos pinned (downloaded 2026-09-28, docs/RESEARCH_LOG.md W7).
X1_HF = {
    ("q8", "awq"): ("Qwen/Qwen3-8B-AWQ", "4da05a8edb55c6046cce958586c33b61da07bb79"),
    ("q14", "awq"): ("Qwen/Qwen3-14B-AWQ", "31c69efc29464b6bb0aee1398b5a7b50a99340c3"),
    ("q32", "awq"): ("Qwen/Qwen3-32B-AWQ", "0499c3ac83fdef8810b907a23894ba91e95eddd8"),
    ("q4", "fp8"): ("Qwen/Qwen3-4B-Instruct-2507-FP8", "8591804019c8b22094c3b5b4454e0edc05dffc98"),
    ("q8", "fp8"): ("Qwen/Qwen3-8B-FP8", "220b46e3b2180893580a4454f21f22d3ebb187d3"),
    ("q14", "fp8"): ("Qwen/Qwen3-14B-FP8", "9a283b4a5efbc09ce247e0ae5b02b744739e525a"),
    ("q30a3", "fp8"): ("Qwen/Qwen3-30B-A3B-Instruct-2507-FP8", "5a5a776300a41aaa681dd7ff0106608ef2bc90db"),
    ("q32", "fp8"): ("Qwen/Qwen3-32B-FP8", "aa55da1ecc13d006e8b8e4f54579b1ea8c3db2df"),
}
X1_HF_EXTRA = {"awq": {"serve_extra": ["--dtype", "float16"]}}
# BF16 weights + a serving flag. Neither planned flag format runs here (W7), so none is generated:
#  bnb: --quantization bitsandbytes was removed in vLLM 0.29;
#  kv_fp8: on SM86 only FlashInfer takes an FP8 KV cache, and it is not batch-invariant (Triton attention needs SM89+).
X1_FLAG: dict[str, list[str]] = {}
X1_FLAG_MODELS = ("q8", "q14")


def x1_cells(m: str) -> list[tuple[str, dict, list[str]]]:
    """(format, ckpt, serve_extra) for model m."""
    # AWQ runs in FP16 activations: the official configs say float16 (vLLM's default for them), and under
    # VLLM_BATCH_INVARIANT vLLM serves AWQ via awq_dequantize + matmul, which only takes FP16 (bf16 crashed, W7).
    out = [(f, {"kind": "hf", "format": f, "hf_id": h, "revision": r, **X1_HF_EXTRA.get(f, {})}, X1_HF_EXTRA.get(f, {}).get("serve_extra", []))
           for (mm, f), (h, r) in X1_HF.items() if mm == m]
    if m in X1_FLAG_MODELS:
        out += [(f, {"kind": "bf16", "format": f, "serve_extra": x}, x) for f, x in X1_FLAG.items()]
    return out


def x1(m: str, prefix: str = "a6000", tid: str = "") -> list[dict]:
    """X1: per deployed format, canonical + 2 nonces (one task), a cross-node det pair, and E3 open-loop D."""
    p = MODEL_PRIORITY[m] + 30
    R = f"{prefix}_{m}"
    out = []
    for f, ck, extra in x1_cells(m):
        cell = f"x1_{f}"
        arm = f"x1_{f}"
        t = eval_task(f"{tid}{m}_{cell}", m, arm, ck,
                      [run(f"{R}_{cell}")] + [run(f"{R}_{cell}_n{i + 1}", nonce=NONCES[i]) for i in range(2)], p)
        for rep, node in (("a", "node005"), ("b", "node004")):
            d = eval_task(f"{tid}det_{m}_{cell}_{rep}", m, arm, ck, [run(f"{prefix}_det_{m}_{cell}_{rep}", DET)], -6)
            d["node"] = node
            out.append(d)
        ol = eval_task(f"{tid}{m}_ol_{cell}", m, arm, ck, [], MODEL_PRIORITY[m] + 100, deps=[f"{tid}{m}_bf16"])
        ol["openloop"] = {"ref_runs": [f"{R}_bf16"], "n": 400, "out": f"analysis/openloop/{prefix}/{m}/{f}"}
        for x in (t, ol) + tuple(out[-2:]):
            if extra:
                x["serve_extra"] = list(extra)
            if f == "fp8":  # Humming FP8 kernel reads NVML index 0 (faulty card on node003): scripts/a6000/pyhooks
                x["serve_env"] = {"CLOQ_PYHOOKS": "1"}
        out += [t, ol]
    return out


# W13: fake KV-cache quantization (BF16 weights; scripts/a6000/pyhooks/cloq_kvq.py wraps vLLM's Attention.forward).
FRESH_NONCES = ["6d1f0b3e", "f07a5c21", "4c8e1a7f"]  # q1..q3: never used by the canonical/null runs
KVQ_CELLS = {"kvq_int4": {"CLOQ_KVQ_BITS": "4"}, "kvq_int3": {"CLOQ_KVQ_BITS": "3"},
             "kvq_int4_rot": {"CLOQ_KVQ_BITS": "4", "CLOQ_KVQ_ROT": "1"}}
KVQ_DET = ("q4", "kvq_int4")


def kvq(m: str, prefix: str = "a6000", tid: str = "", priority: int = -2) -> list[dict]:
    """W13: per KVQ cell one task with 3 fresh-nonce runs (<cell>_q1..q3); a node005/node004 det pair for q4 INT4.
    The worker skips the BF16 canary for these (different numerics by design) and records kv_cache in quantization.json."""
    R = f"{prefix}_{m}"
    out = []
    for cell, kenv in KVQ_CELLS.items():
        senv = {"CLOQ_PYHOOKS": "1", **kenv}
        t = eval_task(f"{tid}{m}_{cell}", m, "kvq", {"kind": "bf16"},
                      [run(f"{R}_{cell}_q{i + 1}", nonce=n) for i, n in enumerate(FRESH_NONCES)], priority)
        t["serve_env"] = senv
        out.append(t)
        if (m, cell) == KVQ_DET:
            for rep, node in (("a", "node005"), ("b", "node004")):
                d = eval_task(f"{tid}det_{m}_{cell}_{rep}", m, "kvq", {"kind": "bf16"},
                              [run(f"{prefix}_det_{m}_{cell}_{rep}", DET)], priority)
                d.update(node=node, serve_env=dict(senv))
                out.append(d)
    return out


# Activation fake quantization (docs/insights/METHOD_FIDELITY.md): A8 hook, SmoothQuant W8A8, QuaRot W4A4KV4. Checkpoint
# kinds smoothquant / quarot are built by the worker (cloq/smoothquant.py, cloq/quarot.py); the online half is serve_env
# (scripts/a6000/pyhooks/cloq_aq.py, cloq_kvq.py). The W x A x KV matrix is scheduled by the main session.
AQ_H = {"CLOQ_PYHOOKS": "1"}
AQ_QUAROT_ENV = {"CLOQ_AQ_BITS": "4", "CLOQ_AQ_FMT": "sym_quarot", "CLOQ_AQ_CLIP": "0.9", "CLOQ_AQ_HAD": "quarot",
                 "CLOQ_KVQ_BITS": "4", "CLOQ_KVQ_ROT": "qk", "CLOQ_KVQ_FMT": "quarot", "CLOQ_KVQ_KCLIP": "0.95",
                 "CLOQ_KVQ_VCLIP": "0.95"}
AQ_CELLS = {  # cell -> (ckpt, serve_env)
    "aq_a8": ({"kind": "bf16"}, {**AQ_H, "CLOQ_AQ_BITS": "8"}),
    "sq_w8a8": ({"kind": "smoothquant", "alpha": "auto"}, {**AQ_H, "CLOQ_AQ_BITS": "8", "CLOQ_AQ_FMT": "sym_sq"}),
    "quarot_w4a4kv4": ({"kind": "quarot", "wbits": 4, "wmethod": "gptq", "seed": 0}, {**AQ_H, **AQ_QUAROT_ENV}),
}


# W x A x KV 2^3 matrix (W47): every cell in the QuaRot-rotated model (online Hadamards always on), bits only vary.
# KV16 cells leave the KV hook off (QuaRot rotates q/k only when K is quantized); kv16r cells (W65) keep the Q/K
# rotation with CLOQ_KVQ_BITS=16, the matched reference for the KV axis. Anchors on the same blocks: A8, SQ W8A8
# (plain BF16 = a6k2_<m>_bfpair_f0k and GPTQ-W4 = a6k2_<m>_gptq_w4_d1_f0k already exist).
WAKV_A4 = {"CLOQ_AQ_BITS": "4", "CLOQ_AQ_FMT": "sym_quarot", "CLOQ_AQ_CLIP": "0.9"}
WAKV_KV4 = {"CLOQ_KVQ_BITS": "4", "CLOQ_KVQ_ROT": "qk", "CLOQ_KVQ_FMT": "quarot", "CLOQ_KVQ_KCLIP": "0.95", "CLOQ_KVQ_VCLIP": "0.95"}


def wakv_cells() -> dict:
    out = {}
    for w in (16, 4):
        ck = {"kind": "quarot", "wbits": w, "seed": 0} if w == 16 else {"kind": "quarot", "wbits": 4, "wmethod": "gptq", "seed": 0}
        for a_ in (16, 4):
            for kv in (16, 4):
                env = {**AQ_H, "CLOQ_AQ_BITS": "16", "CLOQ_AQ_HAD": "quarot"}
                if a_ == 4:
                    env.update(WAKV_A4)
                if kv == 4:
                    env.update(WAKV_KV4)
                out[f"quarot_w{w}a{a_}kv{kv}"] = (ck, env)
                if kv == 16:  # W65: matched KV16 reference, online Q/K rotation on, no KV quantization
                    out[f"quarot_w{w}a{a_}kv16r"] = (ck, {**env, **WAKV_KV4, "CLOQ_KVQ_BITS": "16"})
    out["aq_a8"] = AQ_CELLS["aq_a8"]
    out["sq_w8a8"] = AQ_CELLS["sq_w8a8"]
    return out


def wakv(m: str, prefix: str = "a6k2", cells=None, priority: float = -8, blocks=("f01", "f02", "f03")) -> list[dict]:
    """One task per cell with one run per dev block (nonces: manifests/fork/dev_blocks_v1.json new_blocks), paired with
    <prefix>_<m>_bfpair_<block> and <prefix>_<m>_gptq_w4_d1_<block>."""
    nb = json.load(open(Path(__file__).resolve().parents[2] / "manifests/fork/dev_blocks_v1.json"))["new_blocks"]
    out = []
    for cell, (ck, senv) in wakv_cells().items():
        if cells and cell not in cells:
            continue
        t = eval_task(f"{prefix}_{m}_{cell}_fdev", m, "wakv", ck, [run(f"{prefix}_{m}_{cell}_{b}", nonce=nb[b]) for b in blocks], priority)
        t["serve_env"] = dict(senv)
        out.append(t)
    return out


def aq(m: str, prefix: str = "a6k2", cells=None, n_runs: int = 1, priority: float = -7) -> list[dict]:
    """Smoke: per cell one eval task with n_runs fresh-nonce runs <prefix>_<m>_<cell>_q1.. (arm 'aq')."""
    out = []
    for cell, (ck, senv) in AQ_CELLS.items():
        if cells and cell not in cells:
            continue
        t = eval_task(f"{prefix}_{m}_{cell}", m, "aq", ck,
                      [run(f"{prefix}_{m}_{cell}_q{i + 1}", nonce=n) for i, n in enumerate(FRESH_NONCES[:n_runs])], priority)
        t["serve_env"] = dict(senv)
        out.append(t)
    return out


# W12 (docs/RESEARCH_LOG.md): other weight-only 4-bit formats (COLM 2025 "Quantization Hurts Reasoning?" method list).
W12_NONCES = ["6d1f0b3e", "f07a5c21", "4c8e1a7f"]  # fresh-nonce stratum q1..q3 (E22)


def w12_cells(m: str, prefix: str = "a6k2") -> list[tuple[str, dict]]:
    return [("nf4", {"kind": "nf4"}), ("mxfp4", {"kind": "mxfp4"}), ("rot_bf16", {"kind": "rot_bf16", "seed": 0}),
            ("rot_rtn_w4", {"kind": "rot_rtn", "wbits": 4, "seed": 0}),
            ("rot_gptq_w4", {"kind": "rot_gptq", "wbits": 4, "seed": 0, "calib": f"manifests/{prefix}/{m}/calib_fp_traj_c1.json"})]


def w12(m: str, prefix: str = "a6k2", priority: float = -2, openloop: bool = True, cells=None) -> list[dict]:
    """Per (model, cell): one eval task with 3 fresh-nonce runs <prefix>_<m>_<cell>_q1..q3, plus its E3 open-loop task."""
    tid, R = prefix + "_", f"{prefix}_{m}"
    out = []
    cl = w12_cells(m, prefix) + [("rtnsr_w4", {"kind": "rtnsr", "wbits": 4, "seed": 1})]
    for cell, ck in cl:
        if cells and cell not in cells:
            continue
        deps = [f"{tid}{m}_calib_c1"] if ck["kind"] == "rot_gptq" else []
        p = priority - 1 if ck["kind"] == "rtnsr" else priority  # rtnsr: main-session request, -3
        out.append(eval_task(f"{tid}{m}_{cell}", m, ck["kind"], ck,
                             [run(f"{R}_{cell}_q{i + 1}", nonce=n) for i, n in enumerate(W12_NONCES)], p, deps))
        if openloop:
            ol = eval_task(f"{tid}{m}_ol_{cell}", m, ck["kind"], ck, [], p, deps + [f"{tid}{m}_bf16"])
            ol["openloop"] = {"ref_runs": [f"{R}_bf16"], "n": 400, "out": f"analysis/openloop/{prefix}/{m}/{cell}"}
            out.append(ol)
    return out


def determinism(m: str, rep: str, node: str, prefix: str = "a6000", tid: str = "") -> dict:
    """Same BF16 config, 20 tasks; two copies on different nodes must produce byte-identical decisions."""
    t = eval_task(f"{tid}det_{m}_{rep}", m, "bf16", {"kind": "bf16"}, [run(f"{prefix}_det_{m}_{rep}", DET)], -10)
    t["node"] = node
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--retry", action="store_true")
    ap.add_argument("--only", choices=["det", "matrix", "e5", "e3", "r1", "x1", "kvq", "w12", "aq", "wakv"], default=None)
    ap.add_argument("--runs", type=int, default=1, help="aq: fresh-nonce runs per cell")
    ap.add_argument("--cells", nargs="*", default=None, help="w12: restrict to these cells")
    ap.add_argument("--no-openloop", action="store_true", help="w12: eval tasks only")
    ap.add_argument("--priority", type=float, default=-2, help="w12 priority")
    ap.add_argument("--prefix", default="a6000", help="run-id prefix; a6k2 = deterministic-Inductor rerun (W3)")
    a = ap.parse_args()
    for d in ("todo", "running", "done", "failed"):
        (Q / d).mkdir(parents=True, exist_ok=True)
    n = 0
    for m in a.models:
        tasks = []
        if a.only in (None, "det"):
            tid = "" if a.prefix == "a6000" else a.prefix + "_"
            tasks += [determinism(m, "a", "node005", a.prefix, tid), determinism(m, "b", "node004", a.prefix, tid)]
        if a.only in (None, "matrix"):
            tid = "" if a.prefix == "a6000" else a.prefix + "_"
            tasks += [dict(t, id=tid + t["id"], deps=[tid + d for d in t.get("deps", [])]) for t in matrix(m, a.prefix)]
        if a.only == "e3":
            tid = "" if a.prefix == "a6000" else a.prefix + "_"
            tasks += [dict(t, id=tid + t["id"], deps=[tid + d for d in t["deps"]]) for t in e3(m, a.prefix)]
        if a.only == "r1":
            tid = "" if a.prefix == "a6000" else a.prefix + "_"
            tasks += [dict(t, id=tid + t["id"]) for t in r1(m, a.prefix)]
        if a.only == "x1":
            tasks += x1(m, a.prefix, "" if a.prefix == "a6000" else a.prefix + "_")
        if a.only == "kvq":
            tasks += kvq(m, a.prefix, "" if a.prefix == "a6000" else a.prefix + "_")
        if a.only == "w12":
            tasks += w12(m, a.prefix, a.priority, not a.no_openloop, a.cells)
        if a.only == "aq":
            tasks += aq(m, a.prefix, a.cells, a.runs, a.priority)
        if a.only == "wakv":
            tasks += wakv(m, a.prefix, a.cells, a.priority)
        if a.only == "e5":
            tid = "" if a.prefix == "a6000" else a.prefix + "_"
            tasks += [dict(t, id=tid + t["id"]) for t in e5(m, a.prefix)]
        for t in tasks:
            name = f"{t['id']}.json"
            if any((Q / d / name).exists() for d in ("todo", "running", "done")):
                continue
            if (Q / "failed" / name).exists():
                if not a.retry:
                    continue
                (Q / "failed" / name).unlink()
            (Q / "todo" / name).write_text(json.dumps(t, indent=1))
            n += 1
    print(f"queued {n} tasks")


if __name__ == "__main__":
    main()
