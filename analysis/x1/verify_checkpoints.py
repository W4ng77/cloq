"""X1: verify each official quantized checkpoint is a quantization of exactly the BF16 variant we evaluate.
Checks: model-card base_model, tokenizer (tokenizer.json hash, vocab hash, special/added tokens hash), chat_template,
generation_config. Output: analysis/x1/checkpoint_verification.json. usage: python analysis/x1/verify_checkpoints.py"""
import hashlib, json, re, sys
from pathlib import Path
sys.path.insert(0, "/data/ziyangs/cloq/scripts/a6000")
import make_tasks as MT  # noqa: E402
from worker import MODELS, snapshot  # noqa: E402


def sha(b): return hashlib.sha256(b if isinstance(b, bytes) else json.dumps(b, sort_keys=True).encode()).hexdigest()[:16]


def info(p):
    p = Path(p)
    tj = json.load(open(p / "tokenizer.json"))
    tc = json.load(open(p / "tokenizer_config.json"))
    tpl = tc.get("chat_template") or ((p / "chat_template.jinja").read_text() if (p / "chat_template.jinja").exists() else None)
    special = {k: tc.get(k) for k in ("bos_token", "eos_token", "pad_token", "unk_token", "additional_special_tokens")}
    card = (p / "README.md").read_text() if (p / "README.md").exists() else ""
    fm = re.search(r"^---\n(.*?)\n---", card, re.S)
    base = re.findall(r"base_model:\s*\n((?:\s*-\s*\S+\n)+)|base_model:\s*(\S+)", fm.group(1) + "\n") if fm else []
    base = [x.strip("- \n") for a, b in base for x in (a.split("\n") if a else [b]) if x.strip("- \n")]
    return {"tokenizer_json": sha((p / "tokenizer.json").read_bytes()), "vocab": sha(tj["model"]["vocab"]),
            "added_tokens": sha(tj["added_tokens"]), "special_tokens": sha([special, tc.get("added_tokens_decoder")]),
            "chat_template": sha((tpl or "").encode()), "generation_config": sha(json.load(open(p / "generation_config.json"))),
            "base_model": base, "quantization_config": json.load(open(p / "config.json")).get("quantization_config")}


out, ok_all = {}, True
for (m, f), (hf, rev) in MT.X1_HF.items():
    ref = info(snapshot(MODELS[m]["hf_id"], MODELS[m]["revision"]))
    q = info(snapshot(hf, rev))
    same = {k: q[k] == ref[k] for k in ("tokenizer_json", "vocab", "added_tokens", "special_tokens", "chat_template", "generation_config")}
    base_ok = MODELS[m]["hf_id"] in q["base_model"]
    ok = base_ok and all(same[k] for k in ("vocab", "added_tokens", "special_tokens", "chat_template", "tokenizer_json"))
    ok_all &= ok
    out[f"{m}/{f}"] = {"hf_id": hf, "revision": rev, "bf16": MODELS[m]["hf_id"], "bf16_revision": MODELS[m]["revision"],
                       "base_model": q["base_model"], "base_model_ok": base_ok, "identical": same, "hashes": {k: q[k] for k in same},
                       "chat_template_kwargs": MODELS[m].get("chat_template_kwargs"), "quantization_config": q["quantization_config"], "ok": ok}
    print(f"{m:6s} {f:4s} ok={ok} base={q['base_model']} " + " ".join(f"{k}={v}" for k, v in same.items()))
Path("/data/ziyangs/cloq/analysis/x1/checkpoint_verification.json").write_text(json.dumps(out, indent=1))
sys.exit(0 if ok_all else 1)
