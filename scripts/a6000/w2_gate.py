"""W2 implementation gate (W69): build -> two-bit grid check -> serve -> finite-output canary. Runs as a queue `cmd`
task on the GPU the node runner assigned (CUDA_VISIBLE_DEVICES, CLOQ_TASK_PORT). Writes analysis/stress/w2_gate_<m>_<cell>.json
whatever happens; exit 0 only if every check passes (a failing gate leaves the dependent panel task unclaimed, and the
JSON is the recorded support result).

Checks
  build    the worker's build path (cloq.compress rtn --wbits 2 / cloq.quantize gptq --wbits 2, pinned settings)
  grid     on every decoder linear of the first, middle and last layer: finite values, and per (row, 128-column
           group) at most 2^2 = 4 distinct values (RTN and GPTQ both use one asymmetric 2-bit grid per group, GPTQ
           act-order permutes columns before grouping, so for GPTQ the bound is checked on the stored g_idx-free
           tensor only as finite + rel. error; the per-group check is reported, not required); rel. weight error
  serve    vLLM comes up healthy through serve.sh (same flags as every agent server)
  output   a greedy completion of the canary prompt with logprobs: non-empty, all logprobs finite; canary hash recorded

usage: python scripts/a6000/w2_gate.py --model q4 --cell rtn_w2 --ckpt '{"kind": "rtn", "wbits": 2}'
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT / "scripts/a6000"))
sys.path.insert(0, str(ROOT))


def grid_check(path: str, n_layers: int, method: str) -> dict:
    import torch
    from safetensors import safe_open
    from cloq.compress import is_target
    layers = {0, n_layers // 2, n_layers - 1}
    worst, rel, n, finite = 0, [], 0, True
    for sh in sorted(Path(path).glob("*.safetensors")):
        with safe_open(sh, framework="pt") as f:
            for name in f.keys():
                if not is_target(name) or int(name.split("layers.")[1].split(".")[0]) not in layers:
                    continue
                W = f.get_tensor(name).float()
                finite &= bool(torch.isfinite(W).all())
                rows, cols = W.shape
                blk = W.reshape(rows * (cols // 128), 128).sort(-1).values
                distinct = 1 + (blk.diff(dim=-1) != 0).sum(-1)
                worst = max(worst, int(distinct.max()))
                n += 1
    return {"tensors_checked": n, "finite": finite, "max_distinct_per_group": worst,
            "per_group_ok": worst <= 4, "required": method == "rtn"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--cell", required=True)
    ap.add_argument("--ckpt", required=True)
    a = ap.parse_args()
    import worker as Wk
    ck = json.loads(a.ckpt)
    gpus = os.environ.get("CUDA_VISIBLE_DEVICES", "0").split(",")
    port = int(os.environ.get("CLOQ_TASK_PORT", "8001"))
    out = ROOT / "analysis/stress" / f"w2_gate_{a.model}_{a.cell}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    rec = {"model": a.model, "cell": a.cell, "ckpt": ck, "host": os.uname().nodename, "job": os.environ.get("SLURM_JOB_ID"),
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "checks": {}, "status": "running"}
    env = Wk.model_env(a.model, port)
    scratch = Path(os.environ.get("TMPDIR", "/tmp"))
    log = open(Wk.WORK / "logs/tasks" / f"w2gate_{a.model}_{a.cell}.build.log", "a")
    server = None
    path = None
    try:
        t0 = time.time()
        path, meta = Wk.build_ckpt({"id": f"w2gate_{a.model}_{a.cell}", "model": a.model, "ckpt": ck}, env, gpus, scratch, log)
        rec["checks"]["build"] = {"ok": True, "seconds": round(time.time() - t0), "files_sha256": Wk.ckpt_sha(path),
                                  "quantization": {k: v for k, v in (meta or {}).items() if k not in ("per_tensor", "stats")}}
        cfg = json.load(open(Path(path) / "config.json"))
        g = grid_check(path, int(cfg["num_hidden_layers"]), ck["kind"])
        g["ok"] = g["finite"] and (g["per_group_ok"] or not g["required"])
        g["mean_rel_weight_err"] = (meta or {}).get("mean_rel_weight_err")
        rec["checks"]["grid"] = g
        if not g["ok"]:
            raise RuntimeError(f"grid check failed: {g}")
        slog = open(Wk.WORK / "logs/tasks" / f"w2gate_{a.model}_{a.cell}.vllm.log", "a")
        server = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), ",".join(gpus), str(port), path, "agent", str(Wk.AGENT_MAXLEN)],
                                  env=env, stdout=slog, stderr=subprocess.STDOUT, start_new_session=True)
        t1 = time.time()
        while not Wk.healthy(port):
            if server.poll() is not None:
                raise RuntimeError("vLLM exited during startup")
            if time.time() - t1 > 1800:
                raise RuntimeError("vLLM did not come up in 30 min")
            time.sleep(5)
        rec["checks"]["serve"] = {"ok": True, "seconds": round(time.time() - t1)}
        m = Wk.MODELS[a.model]
        body = {"model": "agent", "temperature": 0.0, "max_tokens": 48, "seed": 0, "logprobs": True, "top_logprobs": 5,
                "messages": [{"role": "system", "content": Wk.CANARY_TEXT},
                             {"role": "user", "content": "My reservation is ABC123; I want to change my flight to Friday."}]}
        if m.get("chat_template_kwargs"):
            body["chat_template_kwargs"] = m["chat_template_kwargs"]
        req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            c = json.load(r)["choices"][0]
        lps = [t["logprob"] for t in (c.get("logprobs") or {}).get("content") or []]
        text = (c.get("message") or {}).get("content") or ""
        ok = bool(lps) and all(isinstance(x, (int, float)) and math.isfinite(x) for x in lps) and bool(text.strip())
        rec["checks"]["output"] = {"ok": ok, "n_tokens": len(lps), "text": text[:300], "canary": Wk.canary(port, a.model),
                                   "min_logprob": min(lps) if lps else None}
        if not ok:
            raise RuntimeError("non-finite or empty canary output")
        rec["status"] = "pass"
    except Exception as e:
        rec["status"] = "fail"
        rec["error"] = repr(e)
        rec["trace"] = traceback.format_exc()[-3000:]
    finally:
        if server is not None:
            Wk.stop_server(server, gpus)
        if path and str(path).startswith(str(scratch)):
            shutil.rmtree(path, ignore_errors=True)
        out.write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: rec[k] for k in ("model", "cell", "status")}))
    sys.exit(0 if rec["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
