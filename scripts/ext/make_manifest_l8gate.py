"""W99f: frozen BFCL manifest for the Llama-3.1-8B (l8) second-family four-arm fork gate and the (staged) formal panel.

Selection uses ids only (no model outcome, no divergence information): per category, the 197 ids of bfcl_mt_v1 that are
not its dev items (dev was used for adapter development on Qwen), sorted by sha256('cloq-ext-l8-v1:' + id);
smoke_l8g = first 5 per category (20 items, the gate), formal_l8 = next 50 per category (200 items, disjoint from smoke).
Categories are pre-stratified (equal counts). Written once; refuses to overwrite.

usage: python3 scripts/ext/make_manifest_l8gate.py
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "manifests/bfcl/bfcl_mt_v1.json"
OUT = ROOT / "manifests/bfcl/bfcl_mt_l8gate_v1.json"
SALT = "cloq-ext-l8-v1"
N_SMOKE, N_FORMAL = 5, 50


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT} exists (frozen); refusing to overwrite")
    src = json.load(open(SRC))
    man = {k: v for k, v in src.items() if k not in ("manifest", "selection", "categories", "frozen_before_model_runs")}
    man.update(manifest="bfcl_mt_l8gate_v1", parent_manifest="bfcl_mt_v1",
               parent_manifest_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),
               selection={"rule": f"per category, the ids of bfcl_mt_v1 minus its dev ids, sorted by sha256('{SALT}:' + id); "
                                  f"smoke_l8g = first {N_SMOKE}; formal_l8 = next {N_FORMAL} (disjoint). No model outcome or "
                                  "divergence information used.", "salt": SALT},
               created=time.strftime("%FT%TZ", time.gmtime()), categories={})
    for cat, c in src["categories"].items():
        pool = sorted(set(c["eval"]) | set(c["dev"]))
        assert len(pool) == c["n_total"], (cat, len(pool))
        pool = [i for i in pool if i not in set(c["dev"])]
        order = sorted(pool, key=lambda i: hashlib.sha256(f"{SALT}:{i}".encode()).hexdigest())
        man["categories"][cat] = {"test_category": c["test_category"], "n_total": c["n_total"], "n_pool": len(pool),
                                  "smoke_l8g": order[:N_SMOKE], "formal_l8": order[N_SMOKE:N_SMOKE + N_FORMAL]}
        assert not set(order[:N_SMOKE]) & set(order[N_SMOKE:N_SMOKE + N_FORMAL])
    man["frozen_before_model_runs"] = True
    OUT.write_text(json.dumps(man, indent=1) + "\n")
    print(OUT, {k: (len(v["smoke_l8g"]), len(v["formal_l8"])) for k, v in man["categories"].items()})


if __name__ == "__main__":
    main()
