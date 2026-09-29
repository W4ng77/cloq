"""Validate fake KV-cache quantization (pyhooks/cloq_kvq.py, docs/RESEARCH_LOG.md W13) on one GPU.

For each config, start a q4 server with the hook enabled and measure:
  (a) canary hash (worker.canary: greedy tokens + exact top-5 logprobs) vs the BF16 reference;
  (b,c) open-loop logprob shift D on the BF16 reference contexts (openloop_d.py, teacher-forced);
  (d) determinism: N real agent prompts completed one at a time (cold prefix cache), all at once in one batch with
      fillers, and one at a time again (every prefix now cached); token ids + chosen-token logprobs must be identical.
Also checks that the wrapper was installed in the EngineCore process (log line) and that the compile cache root was
isolated per config.

usage (inside a cmd task, CUDA_VISIBLE_DEVICES and CLOQ_TASK_PORT set):
  python scripts/a6000/kvq_validate.py --model q4 --out analysis/kvq/validate_q4.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
WORK = Path("/data/ziyangs/cloq_work")
sys.path.insert(0, str(ROOT / "scripts/a6000"))
from worker import MODELS, canary, healthy, snapshot, stop_server  # noqa: E402

CONFIGS = {  # name -> env
    "b16": {"CLOQ_KVQ_BITS": "16"},
    "int8": {"CLOQ_KVQ_BITS": "8"},
    "int4": {"CLOQ_KVQ_BITS": "4"},
    "int3": {"CLOQ_KVQ_BITS": "3"},
    "int4_rot": {"CLOQ_KVQ_BITS": "4", "CLOQ_KVQ_ROT": "1"},
}


def complete(port: int, ids: list[int], max_tokens: int = 64) -> dict:
    body = {"model": "agent", "prompt": ids, "max_tokens": max_tokens, "temperature": 0.0, "seed": 0,
            "logprobs": 1, "return_token_ids": True}
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        c = json.load(r)["choices"][0]
    toks = c.get("token_ids") or (c.get("provider_specific_fields") or {}).get("token_ids")
    return {"ids": toks, "lp": c["logprobs"]["token_logprobs"]}


def prompts(model_run: str, n: int, n_fill: int, seed: int = 0):
    ds = []
    for d in ("retail", "airline"):
        for line in open(ROOT / "runs" / model_run / d / "decisions.jsonl"):
            x = json.loads(line)
            if x.get("prompt_token_ids"):
                ds.append(x["prompt_token_ids"])
    random.Random(seed).shuffle(ds)
    return ds[:n], ds[n:n + n_fill]


def det_test(port: int, ps: list, fill: list) -> dict:
    alone_cold = [complete(port, p) for p in ps]
    with ThreadPoolExecutor(len(ps) + len(fill)) as ex:
        batch = list(ex.map(lambda p: complete(port, p), ps + fill))[:len(ps)]
    alone_hit = [complete(port, p) for p in ps]
    same = lambda A, B: sum(a == b for a, b in zip(A, B))  # noqa: E731  (ids AND logprobs, exact)
    return {"n": len(ps), "batch_eq_alone": same(batch, alone_cold), "prefixhit_eq_alone": same(alone_hit, alone_cold),
            "ids_only_batch_eq": sum(a["ids"] == b["ids"] for a, b in zip(batch, alone_cold)),
            "mean_len": sum(len(a["ids"]) for a in alone_cold) / len(ps)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="q4")
    ap.add_argument("--configs", default=",".join(CONFIGS))
    ap.add_argument("--n-openloop", type=int, default=150)
    ap.add_argument("--n-det", type=int, default=8)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    m = MODELS[a.model]
    port = int(os.environ["CLOQ_TASK_PORT"])
    gpus = os.environ["CUDA_VISIBLE_DEVICES"]
    ref = json.load(open(ROOT / f"analysis/determinism/canary_agent_{a.model}.json"))["hash"]
    ref_run = f"a6k2_{a.model}_bf16"
    ps, fill = prompts(ref_run, a.n_det, 8)
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    res = {"model": a.model, "canary_ref": ref, "ref_run": ref_run, "configs": {}}
    logdir = WORK / "logs/kvq"
    logdir.mkdir(parents=True, exist_ok=True)
    for name in a.configs.split(","):
        env = dict(os.environ, CLOQ_TOOL_PARSER=m["parser"], CLOQ_PYHOOKS="1", **CONFIGS[name])
        vlog = logdir / f"validate_{a.model}_{name}.vllm.log"
        t0 = time.time()
        p = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), gpus, str(port), snapshot(m["hf_id"], m["revision"]),
                              "agent", "33792"], env=env, stdout=open(vlog, "w"), stderr=subprocess.STDOUT,
                             start_new_session=True)
        r = {"env": CONFIGS[name]}
        try:
            while not healthy(port):
                if p.poll() is not None:
                    raise RuntimeError(f"server {name} died; see {vlog}")
                time.sleep(5)
            r["startup_s"] = round(time.time() - t0)
            txt = vlog.read_text()
            r["hook_lines"] = [l for l in txt.splitlines() if "[cloq_kvq]" in l][:4]
            r["compile_lines"] = [l[-160:] for l in txt.splitlines()
                                  if any(k in l for k in ("torch.compile take", "Graph capturing finished", "Using cache directory", "Dynamo bytecode",
                                                          "Directly load", "Compiling a graph", "attention backend", "aot"))][:10]
            h = canary(port, a.model)
            r["canary"] = h
            r["canary_eq_bf16"] = h == ref
            r["det"] = det_test(port, ps, fill)
            ol = f"analysis/kvq/openloop_{a.model}_{name}"
            subprocess.run([sys.executable, str(ROOT / "scripts/a6000/openloop_d.py"), "--port", str(port), "--n",
                            str(a.n_openloop), "--ref-run", ref_run, "--out", ol], cwd=ROOT, env=env, check=True)
            s = json.load(open(ROOT / (ol + ".json")))
            r["openloop"] = {k: s[k] for k in ("n_decisions", "n_tokens", "abs_d_mean", "abs_d_quantiles",
                                                "frac_tokens_shifted", "flip_rate", "decision_any_flip")}
        except Exception as e:  # record and continue with the next config
            r["error"] = repr(e)
        finally:
            stop_server(p, gpus.split(","))
        res["configs"][name] = r
        out.write_text(json.dumps(res, indent=1))
        print(name, json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
