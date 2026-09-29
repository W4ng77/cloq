"""W2 support: how many bf16 weights does Gaussian noise at k actually change? (CPU, first shard of Qwen3-4B,
q_proj/down_proj of layers 0-1; cloq.compress.perturb used read-only, seed 1.)
Usage: python p06_weight_ulp.py -> out/p06_weight_ulp.json
"""
import glob
from types import SimpleNamespace

from safetensors import safe_open

from cloq.compress import perturb
from common import dump, now

SNAP = "/data/ziyangs/cloq_work/hf/hub/models--Qwen--Qwen3-4B-Instruct-2507/snapshots/cdbee75f17c01a7cc42f958dc650907174af0554"


def main():
    f = sorted(glob.glob(SNAP + "/*.safetensors"))[0]
    res = {"snapshot_utc": now(), "shard": f, "tensors": {}}
    with safe_open(f, "pt") as s:
        for n in [n for n in s.keys() if n.endswith(("q_proj.weight", "down_proj.weight"))][:4]:
            W = s.get_tensor(n)
            res["tensors"][n] = {}
            for k in (0.001, 0.003, 0.01, 0.03, 0.1):
                out, st = perturb(n, W, SimpleNamespace(mode="gauss", k=k, seed=1), "cpu")
                res["tensors"][n][str(k)] = {"frac_bf16_weights_changed": round(float((out != W).float().mean()), 4),
                                             "rel_weight_err": st["rel_weight_err"]}
    dump("p06_weight_ulp.json", res)


if __name__ == "__main__":
    main()
