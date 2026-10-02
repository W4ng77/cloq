"""W99t diagnostic: where does the GPU kernel deviate from the KIVI view reference? (K-only / V-only, by position, dtype)."""
import json
import sys

import torch

sys.path[:0] = ["/data/ziyangs/cloq", "/data/ziyangs/cloq/scripts/a6000", "/data/ziyangs/cloq/scripts/a6000/pyhooks"]
import kivi_gate  # noqa: E402
from cloq import kivi_ref  # noqa: E402

out = {}
Hq, Hkv, D, L = 32, 8, 128, 700
for dt in (torch.float16, torch.bfloat16):
    g = torch.Generator().manual_seed(1)
    q = torch.randn(L, Hq, D, generator=g).cuda().to(dt)
    k = (torch.randn(L, Hkv, D, generator=g) + torch.randn(1, Hkv, D, generator=g) * 2).cuda().to(dt)
    v = torch.randn(L, Hkv, D, generator=g).cuda().to(dt)
    for kb, vb in ((16, 16), (2, 16), (16, 2), (2, 2), (4, 4)):
        o = kivi_gate.run_schedule([(q, k, v)], [[(0, 0, L)]], kb, vb)[0].float()
        ref = kivi_ref.view_attention(q, k, v, kb, vb)
        e = (o - ref).abs().amax(dim=(1, 2)).cpu()
        worst = torch.topk(e, 8)
        out[f"{str(dt)[6:]}_k{kb}v{vb}"] = {"max": float(e.max()), "mean": float((o - ref).abs().mean()),
                                            "worst_pos": worst.indices.tolist(), "worst_err": [round(float(x), 4) for x in worst.values],
                                            "err_by_256": [round(float(e[i:i + 256].max()), 4) for i in range(0, L, 256)],
                                            "err_by_128_mean": [round(float(e[i:i + 128].mean()), 5) for i in range(0, L, 128)]}
        print(f"{dt} k{kb}v{vb}", json.dumps(out[f"{str(dt)[6:]}_k{kb}v{vb}"]), flush=True)
json.dump(out, open("/data/ziyangs/cloq/analysis/fork/kivi_gate/diag_q8.json", "w"), indent=1)
