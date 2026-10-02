"""W99p dry run of the fork_driver idcheck probe: no GPU, mock servers.
qwen: old vs new fork_driver with CLOQ_TOKENIZER_MODE unset -> identical HTTP request bodies and identical results.
m24 : new fork_driver with CLOQ_TOKENIZER_MODE=mistral -> chat probe; litellm mocked to echo the record -> request content checked."""
import importlib.util, io, json, os, sys
sys.path.insert(0, "/data/ziyangs/cloq"); sys.path.insert(0, "/data/ziyangs/cloq/scripts/a6000")
S = os.environ.get("PROBE_DRY_DIR", os.path.dirname(os.path.abspath(__file__)))  # holds fork_driver_old.py (HEAD before W99p probe) and fork_driver_new.py
mode = sys.argv[1]
if mode == "m24":
    os.environ["CLOQ_TOKENIZER_MODE"] = "mistral"
def load(name):
    spec = importlib.util.spec_from_file_location(name, f"{S}/{name}.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
from cloq import fork as F
out = {}
if mode == "qwen":
    blocks = [F.Block(F.ROOT if hasattr(F, "ROOT") else "/data/ziyangs/cloq", r, d) for r, d in (("a6k2_q8_gptq_w4_d1_q3", "retail"), ("a6k2_q8_gptq_w4_d1_q3", "airline"), ("a6k2_q4_gptq_w4_d1_q3", "retail"))]
    rec = {}
    for b in blocks:
        for v in b.dec.values():
            for d in v:
                rec[json.dumps(d["prompt_token_ids"])] = d.get("completion_token_ids")
    for name in ("fork_driver_old", "fork_driver_new"):
        m = load(name); bodies = []
        class R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): pass
        def urlopen(req, timeout=None):
            body = json.loads(req.data); bodies.append(req.data)
            ids = rec[json.dumps(body["prompt"])]
            return R(json.dumps({"choices": [{"token_ids": ids}]}).encode())
        m.urllib.request.urlopen = urlopen
        res = m.idcheck("http://mock/v1", blocks, 16, "Q")
        out[name] = {"bodies": bodies, "res": res}
    same_bodies = sorted(out["fork_driver_old"]["bodies"]) == sorted(out["fork_driver_new"]["bodies"])
    strip = lambda r: sorted(json.dumps(x, sort_keys=True) for x in r["rows"])
    print(json.dumps({"n_probes": len(out["fork_driver_new"]["bodies"]), "request_bodies_identical": same_bodies,
                      "results_identical": strip(out["fork_driver_old"]["res"]) == strip(out["fork_driver_new"]["res"]),
                      "new_chat_probe_flag": load("fork_driver_new").MISTRAL_CHAT_PROBE}))
else:
    m = load("fork_driver_new")
    blocks = [F.Block("/data/ziyangs/cloq", "a6k2_m24_rtn_w4_g1", d) for d in ("retail", "airline")]
    import litellm
    seen = []
    class Resp:
        def __init__(self, d): self.d = d
        def to_dict(self): return self.d
    by_msgs = {}
    for b in blocks:
        for v in b.dec.values():
            for d in v:
                by_msgs[json.dumps(d["messages"], sort_keys=True)] = d
    def completion(model, messages, tools, tool_choice, **kw):
        d = by_msgs[json.dumps(messages, sort_keys=True)]
        seen.append({"model": model, "tool_choice": tool_choice, "n_tools": len(tools), "kw": sorted(kw), "api_base": kw.get("api_base"), "seed": kw.get("seed")})
        tcs = [{"id": t["id"], "type": "function", "function": {"name": t["name"], "arguments": json.dumps(t["arguments"])}} for t in (d.get("tool_calls") or [])]
        return Resp({"prompt_token_ids": d["prompt_token_ids"], "choices": [{"token_ids": d["completion_token_ids"], "message": {"content": d.get("content"), "tool_calls": tcs or None}}]})
    litellm.completion = completion
    res = m.idcheck("http://mock/v1", blocks, 16, "Q")
    print(json.dumps({"flag": m.MISTRAL_CHAT_PROBE, "n": res["n"], "n_match": res["n_match"], "request_example": seen[0],
                      "rows_example": res["rows"][0]}, default=str))
