"""W99f: Llama-3.1-8B (l8) BFCL four-arm fork gate -- evidence summary (CPU only).

Reads
  runs/ext_l8_{bf16,gptq_w4_d1}_bfcl_smoke_l8g/bfcl_*/{trajectory,decisions}.jsonl   (evals on the frozen smoke subset)
  analysis/fork/ext_l8_gate/gate_bfcl_l8_gptq_w4_d1/gate.json                       (fork-ext-v1 gate mode)
  analysis/fork/ext_l8_gate/dev/bfcl_l8_gptq_w4_d1_<cat>/                            (dev mode, QQ no-op on every state)
and recomputes the four-arm cells with the unchanged analysis code (analyze_ext.load_dir, ext_r2.r2_effects), pointed at
the gate directory instead of analysis/fork/ext/dev (the Qwen pools are not touched).

Parse-failure causes per decision (agent side; the chat template / llama3_json parser path):
  multi_call      the response carries > 1 tool call (BFCL may accept it; the Llama-3.1 template refuses to render it
                  at the next request -> the item ends 'agent_parse_error', W27 rule)
  toolish_text    no parsed tool call but the text looks like a call ('<|python_tag|>', '{"name"', '"parameters"')
  unknown_tool    a parsed call to a tool not offered at that step
  decode_error    BFCL could not decode a parsed tool call (text-only replies, which end the turn, always carry
                  BFCL's decode error and are not counted)
  empty           no content and no tool call
Item terminations: completed / force_quit / context_overflow / agent_parse_error / other.

usage: /data/ziyangs/cloq_work/envs/bfcl/bin/python analysis/fork/ext_l8_gate/analyze_gate.py  (tokenizers for the truncation count)
       -> analysis/fork/ext_l8_gate/gate_summary.{json,md}
"""
from __future__ import annotations

import importlib.util
import json
import statistics as S
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "analysis/fork/ext_l8_gate"
RUNS = {"bf16": "ext_l8_bf16_bfcl_smoke_l8g_sc", "gptq_w4_d1": "ext_l8_gptq_w4_d1_bfcl_smoke_l8g_sc"}
RUN_PROBE = "ext_l8_bf16_bfcl_probe_l8_sc"  # BF16 capability probe, manifests/bfcl/bfcl_mt_l8probe_v1.json
RUN_R0 = "ext_l8_bf16_bfcl_smoke_l8g"  # r0: parallel tool calls allowed (template failure)
DOMS = ["bfcl_base", "bfcl_miss_param", "bfcl_miss_func", "bfcl_long_context"]
QDONE = Path("/data/ziyangs/cloq_work/queue/done")


def mod(name, path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def jl(p: Path):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def parse_causes(d: dict) -> list[str]:
    tc = d.get("tool_calls") or []
    txt = (d.get("content") or d.get("raw_content") or "") or ""
    out = []
    if len(tc) > 1:
        out.append("multi_call")
    if not tc and any(s in txt for s in ("<|python_tag|>", '{"name"', '"parameters"', "{'name'")):
        out.append("toolish_text")
    if tc and not all(d.get("actions_known_tool") or [True]):
        out.append("unknown_tool")
    if tc and d.get("decode_error") not in (None, "None", ""):  # text-only replies always carry a decode error (turn end)
        out.append("decode_error")
    if not tc and not txt.strip():
        out.append("empty")
    return out


def _tok():
    try:
        from tokenizers import Tokenizer
        snap = sorted(Path("/data/ziyangs/cloq_work/hf/hub/models--meta-llama--Llama-3.1-8B-Instruct/snapshots").glob("*/tokenizer.json"))
        return Tokenizer.from_file(str(snap[0])) if snap else None
    except Exception:
        return None


TOK = _tok()


def truncated_multi(d: dict) -> bool | None:
    """A response whose generated text holds > 1 call although vLLM returned only the first (parallel_tool_calls=false)."""
    if TOK is None or not d.get("tool_calls"):
        return None if TOK is None else False
    return TOK.decode(d["completion_token_ids"], skip_special_tokens=False).count('"name"') > 1


def evals() -> dict:
    res = {}
    for arm, rid in {"bf16_r0_parallel": RUN_R0, **RUNS, "bf16_probe100": RUN_PROBE}.items():
        r = {"run_id": rid, "per_category": {}, "decisions": 0, "parse_causes": Counter(), "terminations": Counter(),
             "items": 0, "success": 0, "inference_seconds": []}
        for d in DOMS:
            tr = jl(ROOT / "runs" / rid / d / "trajectory.jsonl")
            de = jl(ROOT / "runs" / rid / d / "decisions.jsonl")
            causes = Counter(c for x in de for c in parse_causes(x))
            causes["generated_multi_truncated"] = sum(1 for x in de if truncated_multi(x))
            causes["decisions_with_tool_call"] = sum(1 for x in de if x.get("tool_calls"))
            term = Counter(t["termination_reason"] for t in tr)
            r["per_category"][d] = {"n": len(tr), "success": sum(bool(t["success"]) for t in tr), "terminations": dict(term),
                                    "decisions": len(de), "parse_causes": dict(causes),
                                    "decisions_with_any_parse_issue": sum(1 for x in de if parse_causes(x))}
            r["decisions"] += len(de)
            r["parse_causes"].update(causes)
            r["terminations"].update(term)
            r["items"] += len(tr)
            r["success"] += sum(bool(t["success"]) for t in tr)
            r["inference_seconds"] += [t.get("inference_seconds") or t.get("duration") or 0 for t in tr]
        r["parse_causes"], r["terminations"] = dict(r["parse_causes"]), dict(r["terminations"])
        isec = r.pop("inference_seconds")
        r["item_seconds_median"] = S.median(isec) if isec else None
        t = QDONE / f"{rid}.json"
        r["task_seconds"] = json.load(open(t)).get("seconds") if t.exists() else None
        res[arm] = r
    return res


def dev_cells() -> dict:
    AE = mod("analyze_ext", ROOT / "analysis/fork/analyze_ext.py")
    R2 = mod("ext_r2", ROOT / "analysis/fork/ext_r2.py")
    dirs = sorted(p for p in (G / "dev").glob("*") if p.is_dir())
    loaded = [AE.load_dir(d) for d in dirs]
    out = {"dirs": [], "units": []}
    tot = Counter()
    pat = Counter()
    for L in loaded:
        summ = {}
        sp = ROOT / L["dir"] / "dev_summary.json"
        if sp.exists():
            summ = json.loads(sp.read_text())
        out["dirs"].append({"dir": L["dir"], "stratum": L["stratum"], "incomplete": L["incomplete"], "quarantined": L["quarantined"],
                            "noop": L.get("noop"), "n_items": summ.get("n_items"), "n_states": summ.get("n_states"),
                            "n_excluded": summ.get("n_excluded"), "n_no_divergence": summ.get("n_no_divergence"),
                            "wall_per_branch": summ.get("wall_per_branch"), "search_seconds": summ.get("search_seconds"),
                            "branch_seconds": summ.get("branch_seconds"), "n_branches": summ.get("n_branches")})
        for u in L["units"]:
            tot["items"] += 1
            if "excluded" in u:
                tot["excluded"] += 1
                continue
            tot["div" if u["div"] else "no_div"] += 1
            for b in ("BB", "BQ", "QB", "QQ"):
                tot[f"Y_{b}_all"] += u["Y"][b]
            if u["div"]:
                e = R2.r2_effects(u["Y"])
                for k in ("G", "H", "F", "I"):
                    if k in e:
                        tot[f"sum_{k}"] += e[k]
                for b in ("BB", "BQ", "QB", "QQ"):
                    tot[f"Y_{b}_div"] += u["Y"][b]
                pat["".join(str(u["Y"][b]) for b in ("BB", "BQ", "QB", "QQ"))] += 1
                tot["dQ_ne_dB"] += int((u["Y"]["BQ"] - u["Y"]["QQ"]) != (u["Y"]["BB"] - u["Y"]["QB"]))
            out["units"].append({k: u.get(k) for k in ("stratum", "item", "div", "t", "category", "Y", "excluded")})
    out["totals"], out["patterns_BB_BQ_QB_QQ"] = dict(tot), dict(pat)
    return out


def main():
    res = {"evals": evals()}
    gp = G / "gate_bfcl_l8_gptq_w4_d1_sc" / "gate.json"
    if gp.exists():
        g = json.loads(gp.read_text())
        res["gate"] = {"verdict": g.get("verdict"), "throughput": g.get("throughput"), "search": g.get("search"),
                       "seconds_total": g.get("seconds_total"),
                       "states": [{k: s.get(k) for k in ("state_id", "domain", "task_id", "t", "category", "outcomes")} | {
                           "a_noop_QQ_ok": s["a_noop_QQ"]["ok"], "replay_ok": s["replay"]["ok"]} for s in g.get("states", [])],
                       "a_noop_BB": [{"state_id": x["state_id"], "domain": x["domain"], "ok": x["noop"]["ok"]} for x in g.get("a_noop_BB", [])],
                       "c_isolation": g.get("c_isolation"),
                       "servers": {r: {k: (g.get("servers", {}).get(r) or {}).get(k) for k in ("canary", "ckpt_sha256", "effective_config_sha", "canary_ref_ok")}
                                   for r in ("B", "Q")}}
    if "gate" in res:  # four-arm effects on the gate states (QQ = the live QQ branch, verified equal to the original)
        R2 = mod("ext_r2", ROOT / "analysis/fork/ext_r2.py")
        eff = []
        for st in res["gate"]["states"]:
            Y = {b: int(o["reward"]) for b, o in st["outcomes"].items()}
            eff.append({"state_id": st["state_id"], "domain": st["domain"], **R2.r2_effects(Y)})
        res["gate"]["effects"] = eff
        res["gate"]["effects_sum"] = {k: sum(e[k] for e in eff) for k in ("Y_BB", "Y_BQ", "Y_QB", "Y_QQ", "G", "H", "F", "I", "offdiag", "strict_reversal")}
        res["gate"]["patterns_BB_BQ_QB_QQ"] = dict(Counter(e["pattern"] for e in eff))
    res["dev"] = dev_cells()
    (G / "gate_summary.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps({"evals": {a: {k: v for k, v in r.items() if k != "per_category"} for a, r in res["evals"].items()},
                      "gate_verdict": res.get("gate", {}).get("verdict"), "gate_effects_sum": res.get("gate", {}).get("effects_sum"),
                      "gate_patterns": res.get("gate", {}).get("patterns_BB_BQ_QB_QQ"), "dev_totals": res["dev"]["totals"],
                      "dev_dirs": res["dev"]["dirs"], "patterns": res["dev"]["patterns_BB_BQ_QB_QQ"]}, indent=1, default=str))


if __name__ == "__main__":
    main()
