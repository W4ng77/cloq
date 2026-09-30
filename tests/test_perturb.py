"""Unit tests for cloq.perturb (restore / resid) and scripts/a6000/derived.py (CPU; plain asserts).

run: python tests/test_perturb.py   (writes tests/out/test_perturb.json with the measured facts)

A tiny Qwen3-shaped BF16 checkpoint (6 layers, 2 shards, tied embeddings) is written to a temp dir; Q is its RTN-W4
g128 asym fake-quant (cloq.compress.rtn_dequant), stored with the same shard layout and metadata as cloq.quantize does.
Checks
  exactness     resid a=0 == W and a=1 == Q bit for bit (tensors and, for Q, safetensors files); a in {0.25, 0.5, 2}
                equals an independent numpy fp32 evaluation of W + a (Q - W) rounded to BF16; restore arms take every
                listed linear from W and every other one from Q; none == Q, all == W; non-linears == W
  byte budget   w4_bytes against a hand count; thirds equal; random arms within RAND_TOL of their structured arm
                (params and bf16 bytes), and the real q4/q8 manifests on disk reproduce from the model headers
  determinism   two builds -> identical files and content hash; random_arm identical under another PYTHONHASHSEED
  guards        Q differing outside the decoder linears is rejected
  worker path   derived.build with a fake base builder: base cached once, reused, registry written and re-checked
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch
from safetensors import safe_open
from safetensors.torch import save_file

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cloq import perturb as P  # noqa: E402
from cloq.compress import rtn_dequant  # noqa: E402

RESULTS: dict = {}
ENV = dict(os.environ, PYTHONPATH=str(ROOT))
L, H, I, NQ, NKV, D = 6, 256, 384, 4, 2, 64


def tiny_shapes() -> dict:
    s = {"model.embed_tokens.weight": (512, H), "model.norm.weight": (H,)}
    for l in range(L):
        p = f"model.layers.{l}."
        s.update({p + "input_layernorm.weight": (H,), p + "post_attention_layernorm.weight": (H,),
                  p + "self_attn.q_norm.weight": (D,), p + "self_attn.k_norm.weight": (D,),
                  p + "self_attn.q_proj.weight": (NQ * D, H), p + "self_attn.k_proj.weight": (NKV * D, H),
                  p + "self_attn.v_proj.weight": (NKV * D, H), p + "self_attn.o_proj.weight": (H, NQ * D),
                  p + "mlp.gate_proj.weight": (I, H), p + "mlp.up_proj.weight": (I, H), p + "mlp.down_proj.weight": (H, I)})
    return s


def write_pair(d: Path, seed: int = 0, break_nonlinear: bool = False, wbits: int = 4) -> tuple[Path, Path]:
    g = torch.Generator().manual_seed(seed)
    W, Q = d / "W", d / "Q"
    W.mkdir(parents=True)
    Q.mkdir(parents=True)
    names = sorted(tiny_shapes())
    shards = {"model-00001-of-00002.safetensors": names[: len(names) // 2],
              "model-00002-of-00002.safetensors": names[len(names) // 2:]}
    for sh, ns in shards.items():
        tw, tq = {}, {}
        for n in ns:
            w = (torch.randn(tiny_shapes()[n], generator=g) * 0.05).to(torch.bfloat16)
            if n.endswith("proj.weight"):
                w.view(-1)[:3] = torch.tensor([0.0, -0.0, 1e-30]).to(torch.bfloat16)  # signed zero / tiny edge cases
                q = rtn_dequant(w.float(), wbits).to(torch.bfloat16)
            else:
                q = w.clone()
                if break_nonlinear and n == "model.norm.weight":
                    q[0] += 1
            tw[n], tq[n] = w, q
        save_file(tw, str(W / sh), metadata={"format": "pt"})
        save_file(tq, str(Q / sh), metadata={"format": "pt"})
    for p in (W, Q):
        (p / "config.json").write_text(json.dumps({"num_hidden_layers": L, "tie_word_embeddings": True}))
    (Q / "quantization.json").write_text(json.dumps({"method": "GPTQ", "wbits": wbits, "source_model": "tiny", "source_revision": "r0"}))
    return W, Q


def load(d: Path) -> dict:
    out = {}
    for sh in sorted(d.glob("*.safetensors")):
        with safe_open(sh, framework="pt") as f:
            for n in f.keys():
                out[n] = f.get_tensor(n)
    return out


def files_sha(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(d.glob("*.safetensors")):
        h.update(f.name.encode())
        h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def bits_eq(a, b) -> bool:
    return P.same_bits(a, b)


def test_resid(tmp: Path, wbits: int = 4):
    W, Q = write_pair(tmp, wbits=wbits)
    w, q = load(W), load(Q)
    lin = [n for n in w if P.is_target(n)]
    res = {}
    for a in P.ALPHAS:
        out = tmp / f"r{a}"
        m = P.build(W, Q, out, "resid", alpha=a)
        o = load(out)
        assert set(o) == set(w)
        for n in w:
            if n not in lin:
                assert bits_eq(o[n], w[n]), n
        if a == 0:
            assert m["equals"] == "bf16" and all(bits_eq(o[n], w[n]) for n in w)
            assert m["content_sha256"] == P_content(w)
        elif a == 1:
            assert m["equals"] == "q" and all(bits_eq(o[n], q[n]) for n in w)
            assert files_sha(out) == files_sha(Q), "alpha=1 files must be byte-identical to Q's"
        else:
            assert m["equals"] is None
            for n in lin:  # independent evaluation: numpy fp32, then RNE to bf16 via torch
                wn, qn = w[n].float().numpy(), q[n].float().numpy()
                ref = torch.from_numpy((wn + (qn - wn) * np.float32(a)).astype(np.float32)).to(torch.bfloat16)
                assert bits_eq(o[n], ref), (a, n)
        res[str(a)] = {"equals": m["equals"], "eff_alpha": m["eff_alpha"], "content": m["content_sha256"][:16]}
        assert abs(m["eff_alpha"] - a) < 0.02, (a, m["eff_alpha"])
    # the literal formula at the endpoints (what the endpoint rule replaces): only signed-zero / rounding differences
    diff = {}
    for a, ref in ((0.0, w), (1.0, q)):
        nd = 0
        for n in lin:
            f = (w[n].float() + (q[n].float() - w[n].float()) * a).to(torch.bfloat16)
            nd += int((f.view(torch.int16) != ref[n].view(torch.int16)).sum())
        diff[str(a)] = nd
    RESULTS["resid" if wbits == 4 else f"resid_w{wbits}"] = {"alphas": res, "literal_formula_endpoint_bit_diffs": diff}


def P_content(t: dict) -> str:
    ch = P.ContentHash()
    for n, x in t.items():
        ch.add(n, x)
    return ch.hexdigest()


def test_restore(tmp: Path, wbits: int = 4):
    W, Q = write_pair(tmp, wbits=wbits)
    w, q = load(W), load(Q)
    shapes = P.linear_shapes(W)
    assert len(shapes) == 7 * L
    arms = P.structured_arms(shapes)
    assert [len(arms[a]) for a in ("early", "middle", "late")] == [14, 14, 14]
    assert len(arms["attn"]) == 4 * L and len(arms["mlp"]) == 3 * L
    mans = P.make_manifests(W, "tiny", "r0", seeds=(1, 2, 3))
    out_rec = {}
    for name, man in mans.items():
        out = tmp / f"a_{name}"
        m = P.build(W, Q, out, "restore", restored=man["modules"])
        o = load(out)
        rs = set(man["modules"])
        for n in w:
            want = w[n] if (n in rs or not P.is_target(n)) else q[n]
            assert bits_eq(o[n], want), (name, n)
        assert m["equals"] == {"none": "q", "all": "bf16"}.get(name), (name, m["equals"])
        out_rec[name] = {"n": len(rs), "restored_params": man["budget"]["gptq"]["restored_params"],
                         "delta_frac": man.get("delta_frac", 0.0)}
    for name, man in mans.items():
        if man["family"] == "random":
            tgt = man["target_restored_params"]
            got = man["budget"]["gptq"]["restored_params"]
            assert abs(got - tgt) <= P.RAND_TOL * tgt, (name, got, tgt)
            for s in man["matched_to"]:
                assert mans[s]["budget"]["gptq"]["restored_params"] == tgt
    RESULTS["restore_tiny" if wbits == 4 else f"restore_tiny_w{wbits}"] = out_rec


def test_bytes():
    # W3 hand count, [4096, 2560] GPTQ: 3-bit codes + 4096*20 groups*(2 + 3/8) + 2560*4 g_idx
    assert P.wq_bytes(4096, 2560, "gptq", 3) == 4096 * 2560 * 3 / 8 + 4096 * 20 * 2.375 + 2560 * 4
    assert P.wq_bytes(4096, 2560, "gptq", 4) == P.w4_bytes(4096, 2560, "gptq")
    # hand count, [4096, 2560] GPTQ: 4096*2560/2 codes + 4096*20 groups*(2+0.5) + 2560*4 g_idx
    assert P.w4_bytes(4096, 2560, "gptq") == 4096 * 2560 / 2 + 4096 * 20 * 2.5 + 2560 * 4
    assert P.w4_bytes(4096, 2560, "awq") == 4096 * 2560 / 2 + 4096 * 20 * 2.5 + 2560 * 2
    assert P.w4_bytes(4096, 2560, "rtn") == 4096 * 2560 / 2 + 4096 * 20 * 2.5
    assert P.thirds(36) == [list(range(0, 12)), list(range(12, 24)), list(range(24, 36))]
    assert [len(t) for t in P.thirds(40)] == [14, 13, 13]
    shapes = {f"model.layers.{l}.{m}.weight": (1024, 1024) for l in range(3) for m in P.MODULES}
    b = P.budget(shapes, [f"model.layers.0.{m}.weight" for m in P.MODULES], "rtn")
    assert b["restored_params"] == 7 * 2**20 and b["restored_bf16_bytes"] == 14 * 2**20
    assert b["sim_storage_bytes"] == 14 * 2**20 + 14 * P.w4_bytes(1024, 1024, "rtn")
    assert abs(b["sim_bits_per_linear_param"] - (8 * b["sim_storage_bytes"] / (21 * 2**20))) < 1e-12


def test_real_manifests():
    """The committed manifests reproduce from the model headers (skipped when the snapshot is absent)."""
    models = json.load(open(ROOT / "scripts/a6000/models.json"))
    hub = Path("/data/ziyangs/cloq_work/hf/hub")
    table = {}
    for m in ("q4", "q8"):
        spec = models[m]
        src = hub / ("models--" + spec["hf_id"].replace("/", "--")) / "snapshots" / spec["revision"]
        md = ROOT / "manifests/perturb/restore_v1" / m
        if not src.exists() or not md.exists():
            table[m] = "skipped"
            continue
        fresh = P.make_manifests(src, m, spec["revision"])
        assert sorted(p.stem for p in md.glob("*.json")) == sorted(fresh)
        rows = {}
        for arm, man in fresh.items():
            disk = json.load(open(md / f"{arm}.json"))
            assert disk["modules_sha256"] == man["modules_sha256"], (m, arm)
            assert disk["budget"] == json.loads(json.dumps(man["budget"])), (m, arm)
            assert disk["budget_w3"] == json.loads(json.dumps(man["budget_w3"])), (m, arm)
            for meth in ("gptq", "awq"):  # W3 accounting: same params, 3-bit codes/zeros, never more bytes than W4
                b3, b4 = man["budget_w3"][meth], man["budget"][meth]
                assert b3["restored_params"] == b4["restored_params"]
                assert b3["sim_storage_bytes_q"] < b4["sim_storage_bytes_q"]
                assert b3["sim_storage_bytes"] <= b4["sim_storage_bytes"]
            if man["family"] == "random":
                assert abs(man["delta_frac"]) <= P.RAND_TOL, (m, arm, man["delta_frac"])
                assert man["budget"]["gptq"]["restored_params"] <= man["target_restored_params"]
            b = man["budget"]
            rows[arm] = {"n": b["gptq"]["n_restored"], "restored_params": b["gptq"]["restored_params"],
                         "restored_bf16_GB": b["gptq"]["restored_bf16_bytes"] / 1e9,
                         "frac": round(b["gptq"]["restored_param_frac"], 5), "delta_frac": man.get("delta_frac", 0.0),
                         "sim_bits_gptq": round(b["gptq"]["sim_bits_per_linear_param"], 4),
                         "sim_bits_awq": round(b["awq"]["sim_bits_per_linear_param"], 4),
                         "sim_bits_gptq_w3": round(man["budget_w3"]["gptq"]["sim_bits_per_linear_param"], 4)}
        a = fresh
        assert a["early"]["budget"]["gptq"]["restored_params"] == a["late"]["budget"]["gptq"]["restored_params"]
        for arm, man in fresh.items():  # W3 simulated budgets of random arms within 0.5% of their structured arm
            if man["family"] == "random":
                ref = fresh[man["matched_to"][0]]["budget_w3"]["gptq"]["sim_storage_bytes"]
                got = man["budget_w3"]["gptq"]["sim_storage_bytes"]
                assert abs(got - ref) <= P.RAND_TOL * ref, (m, arm, got, ref)
        table[m] = rows
    RESULTS["manifests"] = table


def test_determinism(tmp: Path):
    W, Q = write_pair(tmp)
    shapes = P.linear_shapes(W)
    man = P.make_manifests(W, "tiny", "r0")["rand_third_s2"]
    shas = []
    for i in range(2):
        out = tmp / f"d{i}"
        m = P.build(W, Q, out, "restore", restored=man["modules"])
        shas.append((files_sha(out), m["content_sha256"]))
        out2 = tmp / f"e{i}"
        m2 = P.build(W, Q, out2, "resid", alpha=0.5)
        shas.append((files_sha(out2), m2["content_sha256"]))
    assert shas[0] == shas[2] and shas[1] == shas[3]
    key = "cloq-perturb-v1|restore|tiny|r0|third|2"
    here = P.random_arm(shapes, P.params(shapes, P.structured_arms(shapes)["early"]), key)
    code = ("import sys, json; sys.path.insert(0, %r); from cloq import perturb as P; from pathlib import Path; "
            "s = P.linear_shapes(Path(%r)); print(json.dumps(P.random_arm(s, P.params(s, P.structured_arms(s)['early']), %r)))"
            % (str(ROOT), str(W), key))
    other = json.loads(subprocess.check_output([sys.executable, "-c", code], env=dict(os.environ, PYTHONHASHSEED="12345"), text=True))
    assert here == other
    RESULTS["determinism"] = {"restore_files_sha": shas[0][0][:16], "resid_files_sha": shas[1][0][:16], "cross_process_rng": True}


def test_guard(tmp: Path):
    W, Q = write_pair(tmp, break_nonlinear=True)
    try:
        P.build(W, Q, tmp / "x", "resid", alpha=0.5)
    except RuntimeError as e:
        assert "outside the decoder linears" in str(e)
        RESULTS["guard"] = "rejected"
        return
    raise AssertionError("Q with a modified norm was accepted")


def test_worker_path(tmp: Path):
    os.environ["CLOQ_CKPT_CACHE"] = str(tmp / "cache")
    sys.path.insert(0, str(ROOT / "scripts/a6000"))
    import importlib
    import derived
    importlib.reload(derived)
    W, Q = write_pair(tmp / "pair")
    calls = []

    def fake_build(task, env, gpus, scratch, log):  # stands in for worker.build_ckpt of the gptq base
        calls.append(task["ckpt"])
        out = scratch / f"ckpt_{task['id']}"
        import shutil
        shutil.copytree(Q, out)
        return str(out), json.load(open(Q / "quantization.json"))

    def sha_fn(p):
        return files_sha(Path(p))

    man_dir = tmp / "man"
    man_dir.mkdir()
    for arm, man in P.make_manifests(W, "tiny", "r0").items():
        (man_dir / f"{arm}.json").write_text(json.dumps(man))
    derived.ROOT = Path("/")  # manifests given as absolute paths below
    log = open(tmp / "log.txt", "w")
    base = {"kind": "gptq", "wbits": 4, "calib": "manifests/x.json"}
    out = {}
    for tid, ck in (("t_a0", {"kind": "resid", "base": base, "alpha": 0.0}),
                    ("t_a1", {"kind": "resid", "base": base, "alpha": 1.0}),
                    ("t_late", {"kind": "restore", "base": base, "arm": "late", "manifest": str(man_dir / "late.json")}),
                    ("t_late2", {"kind": "restore", "base": base, "arm": "late", "manifest": str(man_dir / "late.json")})):
        path, meta = derived.build({"id": tid, "model": "tiny", "ckpt": ck}, str(W), "r0", ENV, ["0"],
                                   tmp / "scratch", log, fake_build, sha_fn)
        out[tid] = (meta["equals"], meta["tag"], meta["content_sha256"][:16])
    assert len(calls) == 1, f"base built {len(calls)} times; must be cached"
    assert out["t_a0"][0] == "bf16" and out["t_a1"][0] == "q" and out["t_late"][0] is None
    assert out["t_late"][1:] == out["t_late2"][1:]
    regs = sorted(p.name for p in (tmp / "cache/registry").glob("*.json"))
    assert len(regs) == 3, regs
    # a tampered registry must make the next build fail
    r = tmp / "cache/registry" / f"tiny_{out['t_late'][1]}.json"
    rec = json.load(open(r))
    rec["content_sha256"] = "0" * 64
    r.write_text(json.dumps(rec))
    try:
        derived.build({"id": "t_late3", "model": "tiny", "ckpt": {"kind": "restore", "base": base, "arm": "late",
                                                                  "manifest": str(man_dir / "late.json")}},
                      str(W), "r0", ENV, ["0"], tmp / "scratch", log, fake_build, sha_fn)
        raise AssertionError("registry mismatch not detected")
    except RuntimeError as e:
        assert "not reproduced" in str(e)
    RESULTS["worker_path"] = {"base_builds": len(calls), "tags": {k: v[1] for k, v in out.items()}}


def test_resid_w3(tmp: Path):
    test_resid(tmp, wbits=3)


def test_restore_w3(tmp: Path):
    test_restore(tmp, wbits=3)


def test_cli_w3_budget(tmp: Path):
    """cloq.perturb restore on a W3 base records the W3 budget of the manifest (budget_w3), not the W4 one."""
    W, Q = write_pair(tmp, wbits=3)
    man = P.make_manifests(W, "tiny", "r0")["late"]
    mp = tmp / "late.json"
    mp.write_text(json.dumps(man))
    subprocess.check_call([sys.executable, "-m", "cloq.perturb", "restore", "--src", str(W), "--q", str(Q), "--out",
                           str(tmp / "o"), "--manifest", str(mp)], env=ENV, stdout=subprocess.DEVNULL)
    meta = json.load(open(tmp / "o/quantization.json"))
    assert meta["budget"] == man["budget_w3"]["gptq"] and meta["budget"] != man["budget"]["gptq"]
    RESULTS["cli_w3_budget"] = {"sim_bits": meta["budget"]["sim_bits_per_linear_param"]}


def main():
    test_bytes()
    for fn in (test_resid, test_restore, test_determinism, test_guard, test_worker_path, test_resid_w3, test_restore_w3,
               test_cli_w3_budget):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as d:
            fn(Path(d))
        print("ok", fn.__name__, flush=True)
    test_real_manifests()
    print("ok test_real_manifests")
    od = ROOT / "tests/out"
    od.mkdir(exist_ok=True)
    (od / "test_perturb.json").write_text(json.dumps(RESULTS, indent=1))
    print(json.dumps({k: v for k, v in RESULTS.items() if k != "manifests"}, indent=1))
    print("ALL PASS")


if __name__ == "__main__":
    main()
