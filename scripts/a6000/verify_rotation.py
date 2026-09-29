"""Verify a QuaRot-style rotated BF16 checkpoint (cloq.rotate) against its source (queue `cmd` task, 1 GPU).

1. HF forward on 20 calibration contexts (manifests/a6k2/<m>/calib_fp_traj_c1.json, first --max-len tokens):
   rotated vs original per-position next-token log-probs, in bf16 compute (as served) and in fp32 compute
   (isolates the bf16 rounding of the rotated weights). Reference noise scale: original bf16 vs original fp32.
2. vLLM: serve the original, then the rotated checkpoint (scripts/a6000/serve.sh, this task's GPU/port), greedy
   48-token completions of 6 chat prompts; report token agreement.
Writes analysis/rotation/verify_<m>.json.

usage: python scripts/a6000/verify_rotation.py q4 [--seed 0]
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import torch

ROOT = Path("/data/ziyangs/cloq")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/a6000"))
from worker import CANARY_TEXT, MODELS, healthy, snapshot  # noqa: E402


def compare(a: torch.Tensor, b: torch.Tensor) -> dict:
    """a, b: [T, V] log-probs. Stats on the reference (a) top-1 token and on tokens with p_a > 1e-3."""
    top = a.argmax(-1)
    d_top = (a.gather(-1, top[:, None]) - b.gather(-1, top[:, None])).abs().squeeze(-1)
    mask = a.exp() > 1e-3
    d_mass = ((a - b).abs() * mask).amax(-1)
    return {"n_pos": int(a.shape[0]), "top1_agree": int((top == b.argmax(-1)).sum()),
            "max_dlp_top1": float(d_top.max()), "sum_dlp_top1": float(d_top.sum()),
            "max_dlp_p>1e-3": float(d_mass.max()),
            "last_top1_agree": int(top[-1] == b[-1].argmax()), "last_dlp_top1": float(d_top[-1])}


def merge(rs: list[dict]) -> dict:
    n = sum(r["n_pos"] for r in rs)
    return {"n_prompts": len(rs), "n_positions": n,
            "top1_agreement": sum(r["top1_agree"] for r in rs) / n,
            "max_abs_dlogprob_top1": max(r["max_dlp_top1"] for r in rs),
            "mean_abs_dlogprob_top1": sum(r["sum_dlp_top1"] for r in rs) / n,
            "max_abs_dlogprob_tokens_p>1e-3": max(r["max_dlp_p>1e-3"] for r in rs),
            "last_position_top1_agreement": sum(r["last_top1_agree"] for r in rs) / len(rs),
            "last_position_max_abs_dlogprob_top1": max(r["last_dlp_top1"] for r in rs)}


@torch.no_grad()
def hf_check(src: str, rot: str, model: str, max_len: int) -> dict:
    from transformers import AutoModelForCausalLM

    man = json.load(open(ROOT / f"manifests/a6k2/{model}/calib_fp_traj_c1.json"))
    seqs = [c["prompt_token_ids"][:max_len] for c in man["contexts"][:20]]
    A = AutoModelForCausalLM.from_pretrained(src, dtype=torch.bfloat16).cuda().eval()
    B = AutoModelForCausalLM.from_pretrained(rot, dtype=torch.bfloat16).cuda().eval()
    out = {}
    lp = lambda M, x: torch.log_softmax(M(input_ids=x).logits[0].float(), -1)
    rs = []
    for i, s in enumerate(seqs):
        x = torch.tensor([s], device="cuda")
        a, b = lp(A, x), lp(B, x)
        rs.append(compare(a, b))
        del a, b
    out["bf16_compute_rot_vs_orig"] = merge(rs)
    A.float()
    B.float()
    rs, rs_ref = [], []
    for i, s in enumerate(seqs):
        x = torch.tensor([s], device="cuda")
        a, b = lp(A, x), lp(B, x)
        rs.append(compare(a, b))
        del b
        # numerics reference: the same original weights, bf16 vs fp32 compute
        a16 = torch.log_softmax(A.to(torch.bfloat16)(input_ids=x).logits[0].float(), -1)
        A.float()
        rs_ref.append(compare(a, a16))
    out["fp32_compute_rot_vs_orig"] = merge(rs)
    out["reference_orig_bf16_vs_fp32_compute"] = merge(rs_ref)
    out["tied_embeddings_in_source"] = bool(A.config.tie_word_embeddings)
    out["rotated_config_tied"] = bool(B.config.tie_word_embeddings)
    del A, B
    torch.cuda.empty_cache()
    return out


PROMPTS = [[{"role": "system", "content": CANARY_TEXT},
            {"role": "user", "content": "My reservation is ABC123; I want to change my flight to Friday."}],
           [{"role": "user", "content": "List three prime numbers larger than 100 and explain how you checked."}],
           [{"role": "user", "content": "Write a Python function that returns the n-th Fibonacci number."}],
           [{"role": "user", "content": "I ordered a lamp (order #W123) and it arrived broken. What can you do?"}],
           [{"role": "user", "content": "Translate to French: The meeting is postponed until next Tuesday."}],
           [{"role": "user", "content": "Summarise the rules of chess in two sentences."}]]


def vllm_greedy(path: str, model: str, gpus: str, port: int, tag: str) -> list[list[int]]:
    m = MODELS[model]
    log = open(f"/data/ziyangs/cloq_work/logs/tasks/verify_rotation_{model}_{tag}.vllm.log", "w")
    p = subprocess.Popen([str(ROOT / "scripts/a6000/serve.sh"), gpus, str(port), path, "agent", "8192"],
                         env=dict(os.environ, GPU_UTIL="0.80", CLOQ_TOOL_PARSER=m["parser"]), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        t0 = time.time()
        while not healthy(port):
            if p.poll() is not None:
                raise RuntimeError(f"vLLM exited while serving {path}")
            if time.time() - t0 > 1800:
                raise RuntimeError("vLLM start timeout")
            time.sleep(5)
        res = []
        for msgs in PROMPTS:
            body = {"model": "agent", "temperature": 0.0, "max_tokens": 48, "seed": 0, "messages": msgs,
                    "return_token_ids": True}
            if m.get("chat_template_kwargs"):
                body["chat_template_kwargs"] = m["chat_template_kwargs"]
            req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                c = json.load(r)["choices"][0]
            res.append({"ids": c.get("token_ids"), "text": c["message"]["content"]})
        return res
    finally:
        os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(60)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
        time.sleep(10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-len", type=int, default=2048)
    a = ap.parse_args()
    m = MODELS[a.model]
    src = snapshot(m["hf_id"], m["revision"])
    rot = Path(os.environ.get("TMPDIR", "/tmp")) / f"verify_rot_{a.model}_s{a.seed}"
    if not (rot / "quantization.json").exists():
        subprocess.run([sys.executable, "-m", "cloq.rotate", "--src", src, "--out", str(rot), "--seed", str(a.seed),
                        "--no-sha", "--source-model", m["hf_id"], "--source-revision", m["revision"]], cwd=ROOT, check=True)
    res = {"model": a.model, "source": f"{m['hf_id']}@{m['revision']}", "seed": a.seed, "max_len": a.max_len,
           "rotation_meta": {k: v for k, v in json.load(open(rot / "quantization.json")).items() if k != "per_tensor"}}
    res["hf"] = hf_check(src, str(rot), a.model, a.max_len)
    print(json.dumps(res["hf"], indent=1), flush=True)
    gpus = os.environ["CUDA_VISIBLE_DEVICES"]
    port = int(os.environ.get("CLOQ_TASK_PORT", "8011"))
    o = vllm_greedy(src, a.model, gpus, port, "orig")
    r = vllm_greedy(str(rot), a.model, gpus, port, "rot")
    agree = [sum(x == y for x, y in zip(p["ids"], q["ids"])) for p, q in zip(o, r)]
    prefix = [next((i for i, (x, y) in enumerate(zip(p["ids"], q["ids"])) if x != y), len(p["ids"])) for p, q in zip(o, r)]
    res["vllm"] = {"served": True, "n_prompts": len(o), "tokens": sum(len(p["ids"]) for p in o),
                   "token_agreement": sum(agree) / sum(len(p["ids"]) for p in o), "identical_prefix_len": prefix,
                   "orig_text": [p["text"] for p in o], "rot_text": [q["text"] for q in r]}
    outp = ROOT / f"analysis/rotation/verify_{a.model}.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(res, indent=1))
    print(json.dumps(res["vllm"], indent=1))


if __name__ == "__main__":
    main()
