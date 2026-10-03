"""Text-only view of google/gemma-4-12B-it (g12) for vLLM 0.29 and the CLOQ quantizers (W100n; precedent m24_textonly.py).

Why: the official repo is a multimodal checkpoint (Gemma4UnifiedForConditionalGeneration: encoder-free vision embedder
+ audio/vision projections around the text stack). The study serves text only, like m24. vLLM's
Gemma4UnifiedForConditionalGeneration itself builds its language model as `Gemma4ForCausalLM` on `config.text_config`
(vllm/model_executor/models/gemma4_unified.py), so the text-only view uses exactly that class and config.

What: copy every `model.language_model.*` tensor of the single source file model.safetensors, renamed
`model.language_model.X -> model.X` (the layout cloq.quantize / cloq.compress expect, `model.model.layers`), byte-identical
values (no dtype change), into NSHARD shards in source order; drop `model.vision_embedder.*`, `model.embed_vision.*` and
`model.embed_audio.*`. No lm_head exists (tie_word_embeddings = true, as in the source). Config = the source
`text_config` (model_type gemma4_unified_text) with architectures Gemma4ForCausalLM, dtype bfloat16, and the source's
top-level eos_token_id [1, 106]. generation_config.json (stop ids 1, 106, 50), tokenizer.json, tokenizer_config.json and
chat_template.jinja (the official template) are copied byte-identical. processor_config.json is not copied (text only).

Output: --out (default /data/ziyangs/cloq_work/ckpt_cache/g12_textonly_v1) with textonly.json (provenance: source
repo/revision, source file sha256, per-output-file sha256, tensor counts, dropped prefixes). Deterministic: the same
source gives byte-identical output files.

usage: python scripts/a6000/g12_textonly.py [--out DIR] [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file

HF_ID = "google/gemma-4-12B-it"
REV = "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7"
SRC = Path("/data/ziyangs/cloq_work/hf/hub/models--google--gemma-4-12B-it/snapshots") / REV
OUT = Path("/data/ziyangs/cloq_work/ckpt_cache/g12_textonly_v1")
VERSION = "g12_textonly_v1"
SRC_FILE = "model.safetensors"
NSHARD = 6
DROP = ("model.vision_embedder.", "model.embed_vision.", "model.embed_audio.")
COPY = ("generation_config.json", "tokenizer.json", "tokenizer_config.json", "chat_template.jinja")


def rename(k: str) -> str | None:
    if k.startswith("model.language_model."):
        return "model." + k[len("model.language_model."):]
    assert k.startswith(DROP), f"unexpected tensor {k}"
    return None


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def text_config() -> dict:
    src = json.load(open(SRC / "config.json"))
    c = dict(src["text_config"])
    c.update({"architectures": ["Gemma4ForCausalLM"], "dtype": "bfloat16", "eos_token_id": src["eos_token_id"],
              "tie_word_embeddings": src["tie_word_embeddings"]})
    assert c["model_type"] == "gemma4_unified_text" and c["tie_word_embeddings"] is True
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true", help="verify an existing output against the source (values and names)")
    a = ap.parse_args()
    out = Path(a.out)
    if a.check:
        oidx = json.load(open(out / "model.safetensors.index.json"))["weight_map"]
        n = 0
        with safe_open(SRC / SRC_FILE, "pt") as fs:
            for k in fs.keys():
                nk = rename(k)
                if nk is None:
                    continue
                with safe_open(out / oidx[nk], "pt") as fo:
                    s, o = fs.get_tensor(k), fo.get_tensor(nk)
                    assert s.dtype == o.dtype and s.shape == o.shape, k
                    assert s.view(-1).view(torch.int16).equal(o.view(-1).view(torch.int16)), k
                n += 1
        assert n == len(oidx)
        for f in COPY:
            assert sha256(SRC / f) == sha256(out / f), f
        print(json.dumps({"check": "ok", "tensors": n}))
        return
    tmp = out.with_name(out.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with safe_open(SRC / SRC_FILE, "pt") as f:
        keys = list(f.keys())  # file (offset) order
        text = [(k, rename(k)) for k in keys]
        text = [(k, nk) for k, nk in text if nk is not None]
        sizes = {k: f.get_slice(k).get_shape() for k, _ in text}
        nbytes = {k: 2 * int(torch.tensor(sizes[k]).prod()) if sizes[k] else 2 for k, _ in text}
        total = sum(nbytes.values())
        target = total / NSHARD
        groups, cur, acc = [], [], 0
        for k, nk in text:
            cur.append((k, nk))
            acc += nbytes[k]
            if acc >= target * (len(groups) + 1) and len(groups) < NSHARD - 1:
                groups.append(cur)
                cur = []
        groups.append(cur)
        wmap, real_total = {}, 0
        for gi, g in enumerate(groups):
            name = f"model-{gi + 1:05d}-of-{len(groups):05d}.safetensors"
            tensors = {nk: f.get_tensor(k) for k, nk in g}
            for nk, t in tensors.items():
                assert t.dtype == torch.bfloat16 or nk.endswith("layer_scalar"), (nk, t.dtype)
                wmap[nk] = name
                real_total += t.numel() * t.element_size()
            save_file(tensors, str(tmp / name), metadata={"format": "pt"})
            print(f"{name}: {len(tensors)} tensors", flush=True)
            del tensors
    json.dump({"metadata": {"total_size": real_total}, "weight_map": dict(sorted(wmap.items()))},
              open(tmp / "model.safetensors.index.json", "w"), indent=2)
    json.dump(text_config(), open(tmp / "config.json", "w"), indent=2)
    for fn in COPY:
        shutil.copy(SRC / fn, tmp / fn)
    prov = {"version": VERSION, "builder": "scripts/a6000/g12_textonly.py", "source_hf_id": HF_ID, "source_revision": REV,
            "source_files": {SRC_FILE: sha256(SRC / SRC_FILE)}, "n_source_tensors": len(keys), "n_text_tensors": len(wmap),
            "total_bytes": real_total, "dropped_prefixes": list(DROP), "rename": "model.language_model.X -> model.X",
            "copied_byte_identical": list(COPY),
            "files_sha256": {p.name: sha256(p) for p in sorted(tmp.iterdir()) if p.is_file()}}
    json.dump(prov, open(tmp / "textonly.json", "w"), indent=1)
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    print(json.dumps({k: v for k, v in prov.items() if k != "files_sha256"}))


if __name__ == "__main__":
    main()
