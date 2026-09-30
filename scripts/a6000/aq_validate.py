"""Validate fake activation quantization (pyhooks/cloq_aq.py), SmoothQuant W8A8 and QuaRot W4A4 on one GPU
(docs/insights/METHOD_FIDELITY.md, acceptance steps 2-6; step 1 = tests/test_aq.py on CPU).

Per config: build the checkpoint if needed (cloq.smoothquant / cloq.quarot into $TMPDIR), start a q4 server with the
hook env, then measure
  coverage   "[cloq_aq] module" lines of the engine process: quantized / Hadamard-only / pass-through / excluded
             LinearBase modules by kind and class (QKVParallelLinear, MergedColumnParallelLinear, RowParallelLinear);
             "[cloq_kvq] hooked attention" lines; compile-cache namespace (VLLM_CACHE_ROOT tag, vLLM's cache dir)
  canary     worker.canary (greedy tokens + exact top-5 logprobs) vs the BF16 reference              (step 2)
  det        8 real agent prompts: alone (cold prefix cache) == in one batch with 8 fillers == alone again
             (prefix-cache hit); token ids + chosen-token logprobs exact                              (step 4)
  chunk      the same prompts on a second server of the same config with --max-num-batched-tokens 34816
             (no chunked prefill; default 2048 chunks every prompt) must give identical ids/logprobs   (step 4)
  causal     prompt_logprobs of a 1500-token prefix P, alone vs as the prefix of a 2600-token P+S (which is
             split 2048 + 552 by chunked prefill): identical on P => no token sees later tokens       (step 6)
  openloop   teacher-forced shift on BF16 reference decisions (openloop_d.py): mean |dlogprob|, flip rate  (step 5)
Server logs: /data/ziyangs/cloq_work/logs/ahook/. Output: --out (json, rewritten after every config).

usage (cmd task, CUDA_VISIBLE_DEVICES and CLOQ_TASK_PORT set):
  python scripts/a6000/aq_validate.py --model q4 --suite a8 --out analysis/ahook/validate_a8_q4.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
WORK = Path("/data/ziyangs/cloq_work")
sys.path.insert(0, str(ROOT / "scripts/a6000"))
from kvq_validate import complete, det_test, prompts  # noqa: E402
from worker import MODELS, canary, healthy, snapshot, stop_server  # noqa: E402

H = {"CLOQ_PYHOOKS": "1"}
QR_KV4 = {"CLOQ_KVQ_BITS": "4", "CLOQ_KVQ_ROT": "qk", "CLOQ_KVQ_FMT": "quarot", "CLOQ_KVQ_KCLIP": "0.95", "CLOQ_KVQ_VCLIP": "0.95"}
QR_A4 = {"CLOQ_AQ_BITS": "4", "CLOQ_AQ_FMT": "sym_quarot", "CLOQ_AQ_CLIP": "0.9", "CLOQ_AQ_HAD": "quarot"}
QR_A16 = {"CLOQ_AQ_BITS": "16", "CLOQ_AQ_HAD": "quarot"}
FULL = dict(det=True, chunk=True, causal=True, openloop=150)
SUITES = {
    "a8": {
        "b16": ({**H, "CLOQ_AQ_BITS": "16"}, None, FULL),
        "a8": ({**H, "CLOQ_AQ_BITS": "8"}, None, FULL),
        "a4": ({**H, "CLOQ_AQ_BITS": "4"}, None, dict(det=True, openloop=150)),
        **{f"a4_only_{k}": ({**H, "CLOQ_AQ_BITS": "4", "CLOQ_AQ_ONLY": k}, None, dict(openloop=30))
           for k in ("qkv", "o", "gate_up", "down")},
    },
    "sq": {
        "sq_w8a16": ({**H, "CLOQ_AQ_BITS": "16"}, "sq", dict(openloop=150)),
        "sq_w8a8": ({**H, "CLOQ_AQ_BITS": "8", "CLOQ_AQ_FMT": "sym_sq"}, "sq", FULL),
        "rtn_w8a8_nosmooth": ({**H, "CLOQ_AQ_BITS": "8", "CLOQ_AQ_FMT": "sym_sq"}, "sq0", dict(openloop=150)),
    },
    "quarot": {
        "qr_w16a16": ({**H, **QR_A16}, "qr16", dict(det=True, openloop=150)),
        "qr_w16a8": ({**H, **QR_A16, "CLOQ_AQ_BITS": "8", "CLOQ_AQ_CLIP": "0.9"}, "qr16", dict(openloop=150)),
        "qr_w16a4": ({**H, **QR_A4}, "qr16", dict(openloop=150)),
        "qr_w16a16kv4": ({**H, **QR_A16, **QR_KV4}, "qr16", dict(openloop=150)),
        "qr_w4a16": ({**H, **QR_A16}, "qr4", dict(openloop=150)),
        "qr_w4a4kv4": ({**H, **QR_A4, **QR_KV4}, "qr4", FULL),
        "noqr_w16a4": ({**H, "CLOQ_AQ_BITS": "4", "CLOQ_AQ_CLIP": "0.9"}, None, dict(openloop=150)),
    },
    "kvr": {  # W65: online Q/K rotation with KV16 (CLOQ_KVQ_BITS=16, ROT=qk) must be a pure pass-through of rotated q/k
        "qr_w16a16": ({**H, **QR_A16}, "qr16", dict(det=True, openloop=150)),
        "qr_w16a16kv16r": ({**H, **QR_A16, **QR_KV4, "CLOQ_KVQ_BITS": "16"}, "qr16", FULL),
        "qr_w4a4kv16": ({**H, **QR_A4}, "qr4", dict(openloop=150)),
        "qr_w4a4kv16r": ({**H, **QR_A4, **QR_KV4, "CLOQ_KVQ_BITS": "16"}, "qr4", dict(det=True, openloop=150)),
    },
}
PAIRS = {"kvr": [("qr_w16a16kv16r", "qr_w16a16"), ("qr_w4a4kv16r", "qr_w4a4kv16")]}
CKPTS = {  # name -> cloq builder argv (after --src/--out)
    "sq": ["-m", "cloq.smoothquant", "--alpha", "auto"],
    "sq0": None,  # SmoothQuant's W8 per-channel without smoothing: built by cloq.smoothquant --alpha none
    "qr16": ["-m", "cloq.quarot", "--wbits", "16", "--check"],
    "qr4": ["-m", "cloq.quarot", "--wbits", "4", "--wmethod", "gptq"],
}


def build(name: str, model: dict, env: dict, logdir: Path, a) -> tuple[str, dict]:
    src = snapshot(model["hf_id"], model["revision"])
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"ahook_{a.model}_{name}"
    if (out / "quantization.json").exists():
        return str(out), json.load(open(out / "quantization.json"))
    shutil.rmtree(out, ignore_errors=True)
    argv = CKPTS[name] if name != "sq0" else ["-m", "cloq.smoothquant", "--alpha", "none"]
    cmd = [sys.executable, *argv, "--src", src, "--out", str(out), "--no-sha",
           "--source-model", model["hf_id"], "--source-revision", model["revision"]]
    t0 = time.time()
    with open(logdir / f"build_{a.model}_{name}.log", "w") as lf:
        r = subprocess.run(cmd, cwd=ROOT, env=env, stdout=lf, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        raise RuntimeError(f"build {name} failed rc={r.returncode}; see {logdir}/build_{a.model}_{name}.log")
    q = json.load(open(out / "quantization.json"))
    q["build_seconds"] = round(time.time() - t0)
    rec = {k: v for k, v in q.items() if k not in ("per_tensor", "weight_files")}
    (ROOT / f"analysis/ahook/ckpt_{a.model}_{name}.quantization.json").write_text(json.dumps(rec, indent=1))
    return str(out), q


def coverage(txt: str) -> dict:
    mods = [l for l in txt.splitlines() if "[cloq_aq]" in l and " module " in l]
    by_pid = Counter(l.split("pid=")[1].split()[0] for l in mods)
    pid = by_pid.most_common(1)[0][0] if by_pid else None
    cnt, cls = Counter(), Counter()
    for l in mods:
        if pid and f"pid={pid} " not in l:
            continue
        kind = re.search(r"kind=(\S+)", l).group(1)
        act = re.search(r"action=(\S+)", l).group(1)
        cnt[f"{kind}:{act}"] += 1
        cls[f"{kind}:{l.split(' module ')[1].split()[1]}"] += 1
    kv = [l for l in txt.splitlines() if "[cloq_kvq]" in l and "hooked attention" in l]
    kv_pid = Counter(l.split("pid=")[1].split()[0] for l in kv)
    wrapped = [l.split("] ", 1)[-1][:400] for l in txt.splitlines() if ("[cloq_aq]" in l or "[cloq_kvq]" in l) and "wrapped" in l]
    return {"engine_pid": pid, "by_kind_action": dict(cnt), "by_kind_class": dict(cls),
            "n_quant": sum(v for k, v in cnt.items() if k.endswith(":quant")),
            "n_had_only": sum(v for k, v in cnt.items() if k.endswith(":had_only")),
            "n_pass": sum(v for k, v in cnt.items() if k.endswith(":pass")),
            "n_excluded": sum(v for k, v in cnt.items() if k.endswith(":excluded")),
            "kv_attention_hooked": max(kv_pid.values()) if kv_pid else 0, "wrapped_lines": wrapped[:6]}


def provenance(txt: str) -> dict:
    g = lambda pat: (re.search(pat, txt).group(1) if re.search(pat, txt) else None)  # noqa: E731
    return {"vllm": g(r"LLM engine \(v([\d.]+)\)"), "attention_backend": g(r"Using (\S+) attention backend"),
            "flash_attn_version": g(r"Using FlashAttention version (\d+)"),
            "tensor_parallel_size": g(r"tensor_parallel_size=(\d+)"), "prefix_caching": g(r"enable_prefix_caching=(\w+)"),
            "chunked_prefill": g(r"enable_chunked_prefill=(\w+)"), "compile_ranges_endpoints": g(r"'compile_ranges_endpoints': (\[[^\]]*\])"),
            "cudagraph_mode": g(r"'cudagraph_mode': <CUDAGraphMode\.(\w+)"),
            "cache_dirs": sorted(set(re.findall(r"cache directory:? (\S+)", txt)))[:4]}


def causal_test(port: int, ids: list[int], n_p: int = 1500, n_ps: int = 2600) -> dict:
    def plp(p):
        body = {"model": "agent", "prompt": p, "max_tokens": 1, "temperature": 0.0, "prompt_logprobs": 0}
        req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            pl = json.load(r)["choices"][0]["prompt_logprobs"]
        return [None if e is None else sorted((int(k), v["logprob"]) for k, v in e.items()) for e in pl]
    assert len(ids) >= n_ps
    a = plp(ids[:n_p])
    b = plp(ids[:n_ps])[:n_p]
    return {"n_prefix": n_p, "n_full": n_ps, "identical_positions": sum(x == y for x, y in zip(a, b)), "n_positions": len(a)}


def serve(gpus, port, path, env, vlog, extra=()):
    p = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), gpus, str(port), path, "agent", "33792", *extra], env=env,
                         stdout=open(vlog, "w"), stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    while not healthy(port):
        if p.poll() is not None:
            raise RuntimeError(f"server died; see {vlog}")
        if time.time() - t0 > 2400:
            raise RuntimeError("server did not come up in 40 min")
        time.sleep(5)
    return p, round(time.time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="q4")
    ap.add_argument("--suite", required=True, choices=list(SUITES))
    ap.add_argument("--configs", default=None)
    ap.add_argument("--n-det", type=int, default=8)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    m = MODELS[a.model]
    port = int(os.environ["CLOQ_TASK_PORT"])
    gpus = os.environ["CUDA_VISIBLE_DEVICES"]
    ref = json.load(open(ROOT / f"analysis/determinism/canary_agent_{a.model}.json"))["hash"]
    ref_run = f"a6k2_{a.model}_bf16"
    ps, fill = prompts(ref_run, a.n_det, 8)
    longp = [p for p in prompts(ref_run, 200, 0, seed=1)[0] if len(p) >= 2600][:3]
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    res = json.load(open(out)) if out.exists() else {}
    res.update({"model": a.model, "suite": a.suite, "canary_ref": ref, "ref_run": ref_run, "host": os.uname()[1],
                "job": os.environ.get("SLURM_JOB_ID")})
    res.setdefault("configs", {})
    logdir = WORK / "logs/ahook"
    logdir.mkdir(parents=True, exist_ok=True)
    names = a.configs.split(",") if a.configs else list(SUITES[a.suite])
    base_env = dict(os.environ, CLOQ_TOOL_PARSER=m["parser"])
    built = {}
    for name in names:
        henv, ck, tests = SUITES[a.suite][name]
        r = {"env": henv, "ckpt": ck, "tests": tests}
        procs = []
        try:
            path = snapshot(m["hf_id"], m["revision"])
            if ck:
                if ck not in built:
                    built[ck] = build(ck, m, base_env, logdir, a)
                path, q = built[ck]
                r["ckpt_method"] = q.get("method")
                for k, v in (q.get("requires_serve_env") or {}).items():
                    assert str(henv.get(k)) == str(v) or ck in ("sq", "sq0"), f"{name}: ckpt requires {k}={v}"
            env = dict(base_env, **henv)
            vlog = logdir / f"validate_{a.model}_{name}.vllm.log"
            p, r["startup_s"] = serve(gpus, port, path, env, vlog)
            procs.append(p)
            txt = vlog.read_text()
            r["coverage"] = coverage(txt)
            r["provenance"] = provenance(txt)
            r["canary"] = canary(port, a.model)
            r["canary_eq_bf16"] = r["canary"] == ref
            if tests.get("det"):
                r["det"] = det_test(port, ps, fill)
            if tests.get("causal"):
                r["causal"] = [causal_test(port, lp) for lp in longp]
            if tests.get("chunk"):
                cold = [complete(port, x) for x in ps]
            if tests.get("openloop"):
                ol = f"analysis/ahook/openloop_{a.model}_{name}"
                subprocess.run([sys.executable, str(ROOT / "scripts/a6000/openloop_d.py"), "--port", str(port), "--n",
                                str(tests["openloop"]), "--ref-run", ref_run, "--out", ol], cwd=ROOT, env=env, check=True)
                s = json.load(open(ROOT / (ol + ".json")))
                r["openloop"] = {k: s.get(k) for k in ("n_decisions", "n_tokens", "abs_d_mean", "abs_d_quantiles",
                                                        "frac_tokens_shifted", "flip_rate", "decision_any_flip")}
            stop_server(p, gpus.split(","))
            procs = []
            if tests.get("chunk"):
                vlog2 = logdir / f"validate_{a.model}_{name}_nochunk.vllm.log"
                p2, _ = serve(gpus, port, path, env, vlog2, ("--max-num-batched-tokens", "34816"))
                procs.append(p2)
                txt2 = vlog2.read_text()
                nochunk = [complete(port, x) for x in ps]
                r["chunk"] = {"n": len(ps), "unchunked_eq_chunked": sum(x == y for x, y in zip(nochunk, cold)),
                              "ids_only_eq": sum(x["ids"] == y["ids"] for x, y in zip(nochunk, cold)),
                              "max_num_batched_tokens": 34816, "canary_nochunk": canary(port, a.model),
                              "provenance": provenance(txt2)}
                stop_server(p2, gpus.split(","))
                procs = []
        except Exception as e:  # record and continue with the next config
            r["error"] = repr(e)
        finally:
            for p in procs:
                stop_server(p, gpus.split(","))
        res["configs"][name] = r
        out.write_text(json.dumps(res, indent=1))
        print(name, json.dumps({k: v for k, v in r.items() if k not in ("provenance",)}), flush=True)
    for x, y in PAIRS.get(a.suite, []):  # per-token comparison of two configs on the same teacher-forced tokens
        try:
            import numpy as np
            zx = np.load(ROOT / f"analysis/ahook/openloop_{a.model}_{x}.npz")
            zy = np.load(ROOT / f"analysis/ahook/openloop_{a.model}_{y}.npz")
            assert (zx["decision"] == zy["decision"]).all()
            dd = np.abs(zx["d"] - zy["d"])
            res.setdefault("pairs", {})[f"{x}_vs_{y}"] = {
                "n_tokens": int(dd.size), "mean_abs_dlogprob": float(dd.mean()), "max_abs_dlogprob": float(dd.max()),
                "frac_tokens_differing": float((dd > 0).mean()), "flip_disagreement": float((zx["flip"] != zy["flip"]).mean()),
                "canary_equal": res["configs"][x].get("canary") == res["configs"][y].get("canary")}
        except Exception as e:
            res.setdefault("pairs", {})[f"{x}_vs_{y}"] = {"error": repr(e)}
        out.write_text(json.dumps(res, indent=1))
        print("pair", x, y, json.dumps(res["pairs"][f"{x}_vs_{y}"]), flush=True)
    for ck, (path, _) in built.items():
        shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    main()
