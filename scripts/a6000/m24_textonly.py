"""Text-only view of Mistral-Small-3.2-24B-Instruct-2506 (m24) for vLLM 0.29 and the CLOQ quantizers (W99p).

Why: the official repo is a multimodal checkpoint (Mistral3ForConditionalGeneration, Pixtral vision tower). vLLM 0.29
resolves it to PixtralForConditionalGeneration / Mistral3ForConditionalGeneration, whose module imports
`transformers.models.pixtral.modeling_pixtral.PixtralRotaryEmbedding`, which transformers 5.17 no longer has, so the
server dies before loading (queue/failed/a6k2_smoke_m24.json). The language model alone is a plain MistralForCausalLM.

What: copy every `language_model.*` tensor of the HF-format shards (model-0000k-of-00010.safetensors), renamed
`language_model.model.X -> model.X`, `language_model.lm_head.weight -> lm_head.weight`, byte-identical values (no
dtype change), into shards with the same numbering; drop the vision tower and the projector; write the text config
(`text_config` of the source, architectures MistralForCausalLM), generation_config.json and tekken.json (the official
tokenizer; served with --tokenizer-mode mistral). params.json and consolidated.safetensors are NOT copied: with them
vLLM would auto-select the mistral config format and the Pixtral architecture again.

Output: --out (default /data/ziyangs/cloq_work/ckpt_cache/m24_textonly_v1) with textonly.json (provenance: source
repo/revision, source blob sha256 = HF LFS blob names, per-output-file sha256, tensor count). Deterministic: the same
source gives byte-identical output files.

usage: python scripts/a6000/m24_textonly.py [--out DIR] [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from safetensors import safe_open
from safetensors.torch import save_file

HF_ID = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
REV = "95a6d26c4bfb886c58daf9d3f7332c857cb27b43"
SRC = Path("/data/ziyangs/cloq_work/hf/hub/models--mistralai--Mistral-Small-3.2-24B-Instruct-2506/snapshots") / REV
OUT = Path("/data/ziyangs/cloq_work/ckpt_cache/m24_textonly_v1")
VERSION = "m24_textonly_v1"


def rename(k: str) -> str | None:
    if k.startswith("language_model.model."):
        return "model." + k[len("language_model.model."):]
    if k == "language_model.lm_head.weight":
        return "lm_head.weight"
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
    c.update({"architectures": ["MistralForCausalLM"], "model_type": "mistral", "torch_dtype": "bfloat16",
              "tie_word_embeddings": False, "bos_token_id": 1, "eos_token_id": 2})
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true", help="verify an existing output against the source (values and names)")
    a = ap.parse_args()
    out = Path(a.out)
    idx = json.load(open(SRC / "model.safetensors.index.json"))["weight_map"]
    shards = sorted(set(idx.values()))
    if a.check:
        oidx = json.load(open(out / "model.safetensors.index.json"))["weight_map"]
        n = 0
        for sh in shards:
            with safe_open(SRC / sh, "pt") as fs:
                for k in fs.keys():
                    nk = rename(k)
                    if nk is None:
                        continue
                    with safe_open(out / oidx[nk], "pt") as fo:
                        assert fs.get_tensor(k).view(-1).view(dtype=__import__("torch").int16).equal(
                            fo.get_tensor(nk).view(-1).view(dtype=__import__("torch").int16)), k
                    n += 1
        print(json.dumps({"check": "ok", "tensors": n}))
        return
    tmp = out.with_name(out.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    wmap, files, n_src = {}, [], 0
    total = 0
    for sh in shards:
        tensors = {}
        with safe_open(SRC / sh, "pt") as f:
            for k in sorted(f.keys()):
                n_src += 1
                nk = rename(k)
                if nk is not None:
                    tensors[nk] = f.get_tensor(k)
        if not tensors:
            continue
        name = sh  # keep the source numbering (shards without text tensors are skipped)
        save_file(tensors, str(tmp / name), metadata={"format": "pt"})
        for nk, t in tensors.items():
            wmap[nk] = name
            total += t.numel() * t.element_size()
        files.append(name)
        print(f"{sh}: {len(tensors)} tensors", flush=True)
    json.dump({"metadata": {"total_size": total}, "weight_map": dict(sorted(wmap.items()))},
              open(tmp / "model.safetensors.index.json", "w"), indent=2)
    json.dump(text_config(), open(tmp / "config.json", "w"), indent=2)
    for f in ("generation_config.json", "tekken.json"):
        shutil.copy(SRC / f, tmp / f)
    prov = {"version": VERSION, "builder": "scripts/a6000/m24_textonly.py", "source_hf_id": HF_ID, "source_revision": REV,
            "source_files": {sh: os.path.basename(os.readlink(SRC / sh)) for sh in shards},
            "n_source_tensors": n_src, "n_text_tensors": len(wmap), "total_bytes": total,
            "dropped_prefixes": ["vision_tower.", "multi_modal_projector."],
            "files_sha256": {p.name: sha256(p) for p in sorted(tmp.iterdir()) if p.is_file()}}
    json.dump(prov, open(tmp / "textonly.json", "w"), indent=1)
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    print(json.dumps({k: v for k, v in prov.items() if k != "files_sha256"}))


if __name__ == "__main__":
    main()
