"""E4-2: fork-alternative open loop. Top-k alternatives at BF16's decision forks, under a served checkpoint.

`openloop_d.py` (E3) keeps only the log-probability and rank of the token BF16 chose. This sibling script asks the
served cell for the top-k (default 20) alternatives, with token ids and log-probabilities, at the two places where a
tau-bench agent decision forks:
  first  the first completion token of every decision. On Qwen3 (hermes format) a tool call starts with the special
         token `<tool_call>` (id 151657) and anything else starts a text reply, so P(act) = P(`<tool_call>` | context)
         and P(talk) = 1 - P(act). Tool-start tokens by parser: hermes `<tool_call>`, mistral `[TOOL_CALLS]`,
         llama3_json `<|python_tag|>` + the JSON opener tokens `{` / `{"` (Llama emits bare JSON).
  tool   every token that overlaps the tool name inside the first `"name": "<tool>"` of a BF16 tool call (character
         spans from the model's tokenizer).
It uses the same deterministic decision sample as E3 (openloop_d.load, Random(seed).shuffle, first n, sorted), so rows
line up with the E3 .npz. Both positions are read from ONE request per decision: prompt + BF16 completion, truncated
after the last needed token, `prompt_logprobs=k`. vLLM 0.29 returns for every prompt position a dict
{token_id: {logprob, rank, decoded_token}} with the top-k plus the actual token when it is outside the top-k.
With --first-all it also scores the first-token distribution of EVERY BF16 decision, not only the sample, by one
`max_tokens=1, logprobs=k` generation on the bare prompt. That is exactly the closed-loop computation of the first
token, and it is cheap (a prefill, no long response).

The contrast is served-vs-served. BF16 is run through this script as its own cell (`--out .../bf16_topk`), and every
other cell passes `--ref .../bf16_topk` (the worker does this by default when that file exists), so that KL and
Δ-propensity compare identical numerics. The logged `token_logprobs` of the closed loop are top-1 only; they are used
only as a sanity check (`bf16_consistency`: BF16's first-token logprob here vs. in closed loop).

Summary quantities (<out>.json):
  act.p_act_mean / p_act_by_bf16_type   mean P(tool start) at decision starts, overall and split by what BF16 did
  act.argmax_act_rate                   share of starts where the cell's argmax is a tool start
  act.act_flip_vs_bf16_decision         argmax act/talk differs from the BF16 closed-loop decision type
  vs_ref.*                              (with --ref) per-decision Δlogit P(act) = logit P_cell - logit P_bf16
                                        (clipped to [1e-6, 1-1e-6]); KL(BF16||cell) at first and tool-name positions
                                        (top-k approximation below); binary act KL; total variation; mean Δ P(tool=T)
  tool.p_bf16_name_mean                 mean P_cell(BF16's tool name) = product over name tokens (exact, teacher-forced)
  tool.p_name_mean                      mean estimated probability mass per tool name (prefix-tree estimate below)
  tool.name_switch_rate                 share of tool decisions whose most likely name under the cell is not BF16's
Top-k KL approximation: over the union U of both top-k sets (plus BF16's teacher-forced token, whose exact logprob is
known on both sides), a token missing from one side takes that side's k-th log-probability (an upper bound on its
mass); a 'rest' bucket holds 1 - mass(U) on each side (floored at 1e-12). The mean is heavy-tailed (a few positions
where the cell is confidently elsewhere give KL 10-30 nats); read the median and q90 alongside it.
Tool-name estimate: with p_k the cell's probability of BF16's k-th name token, a tool T whose name diverges from
BF16's at name token k* gets P(T) = prod_{k<k*} p_k * sum of top-k alternatives at k* whose text is consistent with T
(a token consistent with several tools is split evenly among them: an alternative `update` at the first name token
gives each update_* tool an equal share, so per-tool mass below the family level is only an estimate; name_switch_rate
is robust to this because BF16's name then gets ~0). It assumes the rest of T's name is then forced
(an upper bound per token), and it misses alternatives outside the top-k.
Tool names come from the tool list in the prompt (`"function": {"name": ...}`), cached per domain.

Schema v2 (2026-09-30, docs/insights/METHODOLOGY_REVISION.md §C; `--schema 2`, written to <out>.v2.json so schema-1
<out>.json files stay byte-identical and reproducible; the default schema stays 1 for the running worker):
  p_act      a tool-start token outside the returned top-k has unknown probability in [0, p_k] (p_k = the k-th, i.e.
             smallest returned, probability). Schema 1 counted it as 0 (a lower bound). v2 reports p_act_lo (= schema-1
             value), p_act_hi (= lo + p_k per missing start token), missing_frac (share of positions with >= 1 start
             token outside the top-k), and Δlogit bounds [logit(lo_cell) - logit(hi_ref), logit(hi_cell) - logit(lo_ref)].
  KL         schema-1 `kl_*` / `tv_*` is renamed `approx_topk_kl_*` / `approx_topk_tv_*` (NOT an exact KL: a token missing
             on one side is imputed at that side's k-th logprob). v2 adds `coarse_kl_*` / `coarse_tv_*`: the exact KL / TV
             of the coarse-grained distributions over C = tokens whose probability is known on BOTH sides (common top-k
             tokens, plus the teacher-forced BF16 token) and one residual category (1 - mass(C) on each side). By the
             data-processing inequality coarse_kl <= the true KL (a lower bound), and it needs no imputation.
  name_mass  the prefix-tree tool-name estimate is a PROXY (`name_mass_proxy_*`, `name_switch_rate_proxy`). Measurable
             error terms: `name_mass_unassigned_mean` = 1 - sum_T est(T) (mass at the divergence token that is outside the
             top-k or inconsistent with every tool name); `name_switch_upper_bound` = share of decisions where
             P(BF16's name) < 0.5 (P(BF16's name) is exact: the teacher-forced product; a switch is impossible when it is
             >= 0.5). The main tool metric is the fully generated and parsed tool name and arguments (fork study).

Output: <out>.npz holds these arrays.
  sampled positions (P rows): pos_dec (decision index into the sample), pos_kind (0 first, 1 tool-name), pos_j
    (completion token index), pos_k (name token index, -1 for first), pos_tok (BF16 token), pos_lp (cell logprob of
    BF16's token), pos_rank, top_ids [P,k] int32, top_lp [P,k] float32 (descending; padded -1 / -inf).
  sampled decisions (D rows): dec_run, dec_domain, dec_task, dec_idx, dec_is_tool, dec_first_tok, dec_bf16_name.
  --first-all (A rows): fa_run, fa_domain, fa_task, fa_idx, fa_is_tool, fa_top_ids, fa_top_lp.
Plan: docs/insights/iter_4_disposition.md (E4-2).

usage (inside a worker, server already up; the worker sets CLOQ_MODEL_ID / CLOQ_MODEL_REVISION / CLOQ_TOOL_PARSER):
  python scripts/a6000/openloop_topk.py --port 8003 --ref-run a6k2_q4_bf16 --n 400 --topk 20 --first-all \
      --out analysis/openloop/a6k2/q4/topk/rtn_w4 --ref analysis/openloop/a6k2/q4/topk/bf16
recompute the summary offline (e.g. after the BF16 cell finished):
  python scripts/a6000/openloop_topk.py --resummarize analysis/openloop/a6k2/q4/topk/rtn_w4 \
      --ref analysis/openloop/a6k2/q4/topk/bf16 --model q4
Queue: tasks a6k2_<m>_olk_<cell> with openloop {"topk": 20, ...} (scripts/a6000/make_tasks_e42.py, worker.py).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from openloop_d import ROOT, load  # noqa: E402  (same decision loader as E3)

WORK = Path("/data/ziyangs/cloq_work")
NAME_RE = re.compile(r'"name"\s*:\s*"([^"]*)"')
TOOLS_RE = re.compile(r'"function"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"')
TOOL_START = {"hermes": ["<tool_call>"], "mistral": ["[TOOL_CALLS]"], "llama3_json": ["<|python_tag|>", "{", '{"'], "gemma4": ["<|tool_call>"]}  # W100n g12: gemma4 key only; other parsers unchanged
EPS = 1e-6
TOL = 5.001e-5  # decisions.jsonl token_logprobs are rounded to 4 decimals (cloq/agent.py)


# ---------------------------------------------------------------- tokenizer / decision geometry
def tokenizer_for(model: str | None):
    from transformers import AutoTokenizer
    if model:
        m = json.load(open(ROOT / "scripts/a6000/models.json"))[model]
        hf, rev, parser = m["hf_id"], m["revision"], m["parser"]
    else:
        hf, rev, parser = os.environ["CLOQ_MODEL_ID"], os.environ["CLOQ_MODEL_REVISION"], os.environ.get("CLOQ_TOOL_PARSER", "hermes")
    tok = AutoTokenizer.from_pretrained(str(WORK / "hf/hub" / ("models--" + hf.replace("/", "--")) / "snapshots" / rev))
    return tok, parser


def tool_start_ids(tok, parser: str) -> list[int]:
    out = []
    for s in TOOL_START.get(parser, ["<tool_call>"]):
        if s in tok.get_vocab():
            out.append(tok.convert_tokens_to_ids(s))
        else:
            ids = tok.encode(s, add_special_tokens=False)
            if len(ids) == 1:
                out.append(ids[0])
    return sorted(set(out))


def name_positions(tok, comp: list[int]):
    """(first name token j, token texts of the name tokens, lead chars before the name in the first name token, name)
    for the first `"name": "<tool>"` in the completion; None when there is none."""
    text = tok.decode(comp, skip_special_tokens=False)
    m = NAME_RE.search(text)
    if not m:
        return None
    s, e = m.span(1)
    spans, prev = [], 0
    for j in range(len(comp)):
        cur = len(tok.decode(comp[:j + 1], skip_special_tokens=False))
        spans.append((prev, cur))
        prev = cur
        if cur >= e + 1:
            break
    js = [j for j, (a, b) in enumerate(spans) if b > s and a < e and b > a]
    if not js:
        return None
    texts = [text[spans[j][0]:spans[j][1]] for j in js]
    return js, texts, text[spans[js[0]][0]:s], m.group(1)


def tool_names(tok, d: dict, cache: dict) -> list[str]:
    key = d["domain"]  # the tool list is fixed per domain (openloop_d.load does not keep tools_sha256)
    if key not in cache:
        cache[key] = list(dict.fromkeys(TOOLS_RE.findall(tok.decode(d["prompt_token_ids"], skip_special_tokens=False))))
    return cache[key]


# ---------------------------------------------------------------- server calls
def parse_entry(ent: dict, k: int):
    """One prompt_logprobs position -> (ids[k], lps[k]) sorted by logprob, padded with -1 / -inf."""
    items = sorted(((int(t), float(v["logprob"])) for t, v in ent.items()), key=lambda x: -x[1])[:k]
    ids = np.full(k, -1, np.int32)
    lps = np.full(k, -np.inf, np.float32)
    for i, (t, lp) in enumerate(items):
        ids[i], lps[i] = t, lp
    return ids, lps


def score_positions(port: int, d: dict, js: list[int], k: int) -> list[dict]:
    comp = d["completion_token_ids"]
    body = {"model": "agent", "prompt": d["prompt_token_ids"] + comp[:max(js) + 1], "max_tokens": 1,
            "temperature": 0.0, "prompt_logprobs": k, "return_token_ids": True}
    r = requests.post(f"http://127.0.0.1:{port}/v1/completions", json=body, timeout=1800)
    r.raise_for_status()
    pl = r.json()["choices"][0]["prompt_logprobs"]
    P = len(d["prompt_token_ids"])
    out = []
    for j in js:
        ent = pl[P + j]
        tok = comp[j]
        own = ent.get(str(tok)) or ent.get(tok)
        ids, lps = parse_entry(ent, k)
        out.append({"j": j, "tok": tok, "lp": float(own["logprob"]), "rank": int(own.get("rank", 1)), "ids": ids, "lps": lps})
    return out


def parse_gen_top(top: dict, k: int):
    """legacy completions top_logprobs[0] with return_tokens_as_token_ids -> keys 'token_id:<id>'."""
    return parse_entry({t.split(":", 1)[1]: {"logprob": v} for t, v in top.items()}, k)


def score_first(port: int, d: dict, k: int):
    body = {"model": "agent", "prompt": d["prompt_token_ids"], "max_tokens": 1, "temperature": 0.0, "logprobs": k,
            "return_tokens_as_token_ids": True}
    r = requests.post(f"http://127.0.0.1:{port}/v1/completions", json=body, timeout=1800)
    r.raise_for_status()
    return parse_gen_top(r.json()["choices"][0]["logprobs"]["top_logprobs"][0], k)


# ---------------------------------------------------------------- distribution helpers
def p_act(ids: np.ndarray, lps: np.ndarray, start: list[int]) -> float:
    return float(sum(math.exp(l) for t, l in zip(ids, lps) if t in start and np.isfinite(l)))


def p_act_bounds(ids: np.ndarray, lps: np.ndarray, start: list[int]) -> tuple[float, float, bool]:
    """(lower, upper, missing): a start token outside the returned top-k has probability in [0, p_k]."""
    fin = [(int(t), float(l)) for t, l in zip(ids, lps) if t >= 0 and np.isfinite(l)]
    lo = sum(math.exp(l) for t, l in fin if t in start)
    present = {t for t, _ in fin}
    n_miss = sum(1 for t in start if t not in present)
    pk = math.exp(min(l for _, l in fin)) if fin else 1.0
    return float(lo), float(min(1.0, lo + n_miss * pk)), bool(n_miss > 0)


def coarse_kl(ids_p, lp_p, ids_q, lp_q, extra_p=None, extra_q=None) -> tuple[float, float, int]:
    """Exact KL(P||Q) and TV of the coarse-grained distributions over C = tokens with known probability on BOTH sides
    (+ one residual category). Lower bound on the true KL / TV (data-processing inequality). Returns (kl, tv, |C|)."""
    P = {int(t): float(l) for t, l in zip(ids_p, lp_p) if t >= 0 and np.isfinite(l)}
    Q = {int(t): float(l) for t, l in zip(ids_q, lp_q) if t >= 0 and np.isfinite(l)}
    for D, x in ((P, extra_p), (Q, extra_q)):
        if x is not None:
            D.setdefault(int(x[0]), float(x[1]))
    C = sorted(set(P) & set(Q))
    p = np.array([math.exp(P[t]) for t in C]); q = np.array([math.exp(Q[t]) for t in C])
    p = np.append(p, max(1 - p.sum(), 0.0)); q = np.append(q, max(1 - q.sum(), 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(p > 0, p * (np.log(np.maximum(p, 1e-300)) - np.log(np.maximum(q, 1e-12))), 0.0)
    return float(max(terms.sum(), 0.0)), float(0.5 * np.abs(p - q).sum()), len(C)


def logit(p: float) -> float:
    p = min(max(p, EPS), 1 - EPS)
    return math.log(p / (1 - p))


def topk_kl(ids_p, lp_p, ids_q, lp_q, extra_p=None, extra_q=None) -> tuple[float, float]:
    """APPROXIMATE KL(P||Q) and total variation between two top-k lists (imputation in the module docstring); NOT an
    exact KL. Kept unchanged for schema-1 reproducibility; schema v2 reports it as approx_topk_kl and adds coarse_kl.
    extra_p / extra_q: exact (token, logprob) known outside the top-k (the teacher-forced BF16 token)."""
    P = {int(t): float(l) for t, l in zip(ids_p, lp_p) if t >= 0 and np.isfinite(l)}
    Q = {int(t): float(l) for t, l in zip(ids_q, lp_q) if t >= 0 and np.isfinite(l)}
    fp, fq = min(P.values()), min(Q.values())
    for D, x in ((P, extra_p), (Q, extra_q)):
        if x is not None:
            D.setdefault(int(x[0]), float(x[1]))
    U = set(P) | set(Q)
    p = np.array([math.exp(P.get(t, fp)) for t in U])
    q = np.array([math.exp(Q.get(t, fq)) for t in U])
    rp, rq = max(1 - p.sum(), 1e-12), max(1 - q.sum(), 1e-12)
    p, q = np.append(p, rp), np.append(q, rq)
    kl = float(np.sum(p * (np.log(p) - np.log(q))))
    return max(kl, 0.0), float(0.5 * np.abs(p - q).sum())


def binary_kl(p: float, q: float) -> float:
    p, q = min(max(p, EPS), 1 - EPS), min(max(q, EPS), 1 - EPS)
    return p * math.log(p / q) + (1 - p) * math.log((1 - p) / (1 - q))


def name_mass(tok, rows: list[dict], texts: list[str], lead: str, name: str, tools: list[str]) -> dict:
    """Prefix-tree estimate of P(tool name = T) for every T (module docstring)."""
    tools = list(dict.fromkeys(tools + [name]))
    full = {T: lead + T + '"' for T in tools}
    cons = lambda c, T: full[T].startswith(c) or c.startswith(full[T])  # noqa: E731
    est = {T: 0.0 for T in tools}
    pref_p, prefix = 1.0, ""
    alive = set(tools)  # tools still consistent with BF16's prefix
    for r, t in zip(rows, texts):
        diverge = {T for T in alive if not cons(prefix + t, T)}
        for a, l in zip(r["ids"], r["lps"]):
            if a < 0 or not np.isfinite(l) or a == r["tok"]:
                continue
            c = prefix + tok.decode([int(a)], skip_special_tokens=False)
            hit = [T for T in diverge if cons(c, T)]
            for T in hit:
                est[T] += pref_p * math.exp(l) / len(hit)
        pref_p *= math.exp(r["lp"])
        prefix += t
        alive -= diverge
    for T in alive:  # only BF16's own name (or names it is a prefix of) survive to the end
        est[T] += pref_p / len(alive)
    return est


# ---------------------------------------------------------------- summary
def summarize(z: dict, ref: dict | None, start: list[int]) -> dict:
    D = len(z["dec_is_tool"])
    first = np.flatnonzero(z["pos_kind"] == 0)
    fd = z["pos_dec"][first]
    pa = np.array([p_act(z["top_ids"][i], z["top_lp"][i], start) for i in first])
    is_tool = z["dec_is_tool"][fd].astype(bool)
    top1_act = np.isin(z["top_ids"][first, 0], start)
    bf_act_tok = np.isin(z["dec_first_tok"][fd], start)
    s = {"n_decisions": int(D), "n_tool_decisions": int(z["dec_is_tool"].sum()), "tool_start_ids": [int(x) for x in start],
         "n_positions": int(len(z["pos_kind"])), "n_tool_name_positions": int((z["pos_kind"] == 1).sum()),
         "act": {"p_act_mean": float(pa.mean()), "p_talk_mean": float(1 - pa.mean()),
                 "p_act_by_bf16_type": {"tool": float(pa[is_tool].mean()) if is_tool.any() else None,
                                        "text": float(pa[~is_tool].mean()) if (~is_tool).any() else None},
                 "bf16_share_tool_decisions": float(is_tool.mean()),
                 "bf16_share_tool_start_token": float(bf_act_tok.mean()),
                 "argmax_act_rate": float(top1_act.mean()),
                 "act_flip_vs_bf16_decision": float((top1_act != bf_act_tok).mean()),
                 "first_token_flip_rate": float((z["pos_rank"][first] > 1).mean())}}
    if "fa_top_ids" in z and len(z["fa_top_ids"]):
        fa = np.array([p_act(i, l, start) for i, l in zip(z["fa_top_ids"], z["fa_top_lp"])])
        ft = z["fa_is_tool"].astype(bool)
        s["act_all"] = {"n": int(len(fa)), "p_act_mean": float(fa.mean()),
                        "p_act_by_bf16_type": {"tool": float(fa[ft].mean()), "text": float(fa[~ft].mean())},
                        "argmax_act_rate": float(np.isin(z["fa_top_ids"][:, 0], start).mean())}
    # tool names
    tn = z.get("tool_name_est", {})
    if tn:
        pb, sw, agg = [], [], {}
        for di, est in tn.items():
            nm = str(z["dec_bf16_name"][int(di)])
            pb.append(est[nm])
            sw.append(max(est, key=est.get) != nm)
            for T, v in est.items():
                agg.setdefault(T, []).append(v)
        s["tool"] = {"n": len(pb), "p_bf16_name_mean": float(np.mean(pb)), "p_bf16_name_median": float(np.median(pb)),
                     "name_switch_rate": float(np.mean(sw)),
                     "p_name_mean": {T: float(np.mean(v)) for T, v in sorted(agg.items())}}
    if ref is not None:
        s["vs_ref"] = contrast(z, ref, start)
    return s


def _key(z, i, pre="pos"):
    return (int(z[f"{pre}_dec"][i]), int(z[f"{pre}_kind"][i]), int(z[f"{pre}_j"][i]))


def contrast(z: dict, ref: dict, start: list[int]) -> dict:
    same = all(np.array_equal(z[k], ref[k]) for k in ("dec_run", "dec_domain", "dec_task", "dec_idx"))
    if not same:
        return {"error": "decision sample differs from the reference cell"}
    R = {_key(ref, i): i for i in range(len(ref["pos_kind"]))}
    out = {}
    for kind, nm in ((0, "first"), (1, "tool_name")):
        kl, tv, dl, bkl, isd = [], [], [], [], []
        for i in np.flatnonzero(z["pos_kind"] == kind):
            r = R.get(_key(z, i))
            if r is None:
                continue
            isd.append(bool(z["dec_is_tool"][z["pos_dec"][i]]))
            a, b = (ref["top_ids"][r], ref["top_lp"][r]), (z["top_ids"][i], z["top_lp"][i])
            k_, t_ = topk_kl(*a, *b, (ref["pos_tok"][r], ref["pos_lp"][r]), (z["pos_tok"][i], z["pos_lp"][i]))
            kl.append(k_)
            tv.append(t_)
            if kind == 0:
                pr, pc = p_act(*a, start), p_act(*b, start)
                dl.append(logit(pc) - logit(pr))
                bkl.append(binary_kl(pr, pc))
        if not kl:
            continue
        o = {"n": len(kl), "kl_mean": float(np.mean(kl)), "kl_median": float(np.median(kl)),
             "kl_q90": float(np.quantile(kl, 0.9)), "tv_mean": float(np.mean(tv))}
        if kind == 0:
            dl, is_tool = np.array(dl), np.array(isd)
            o.update({"dlogit_act_mean": float(dl.mean()), "dlogit_act_median": float(np.median(dl)),
                      "dlogit_act_by_bf16_type": {"tool": float(dl[is_tool].mean()), "text": float(dl[~is_tool].mean())},
                      "binary_act_kl_mean": float(np.mean(bkl))})
        out[nm] = o
    if "fa_top_ids" in z and "fa_top_ids" in ref and all(np.array_equal(z[k], ref[k]) for k in ("fa_run", "fa_domain", "fa_task", "fa_idx")):
        pr = np.array([p_act(i, l, start) for i, l in zip(ref["fa_top_ids"], ref["fa_top_lp"])])
        pc = np.array([p_act(i, l, start) for i, l in zip(z["fa_top_ids"], z["fa_top_lp"])])
        dl = np.array([logit(c) - logit(r) for c, r in zip(pc, pr)])
        kl = [topk_kl(ref["fa_top_ids"][i], ref["fa_top_lp"][i], z["fa_top_ids"][i], z["fa_top_lp"][i])[0] for i in range(len(pr))]
        out["first_all"] = {"n": int(len(pr)), "dp_act_mean": float((pc - pr).mean()), "dlogit_act_mean": float(dl.mean()),
                            "dlogit_act_median": float(np.median(dl)), "kl_mean": float(np.mean(kl)),
                            "binary_act_kl_mean": float(np.mean([binary_kl(r, c) for r, c in zip(pr, pc)])),
                            "argmax_act_change": float((np.isin(z["fa_top_ids"][:, 0], start) != np.isin(ref["fa_top_ids"][:, 0], start)).mean())}
    tz, tr = z.get("tool_name_est", {}), ref.get("tool_name_est", {})
    common = sorted(set(tz) & set(tr), key=int)
    if common:
        names = sorted({T for d in common for T in list(tz[d]) + list(tr[d])})
        dp = {T: float(np.mean([tz[d].get(T, 0.0) - tr[d].get(T, 0.0) for d in common])) for T in names}
        out["tool_name_dp_mean"] = dp
        out["tool_name_dp_bf16_name_mean"] = float(np.mean([tz[d][str(z["dec_bf16_name"][int(d)])] - tr[d][str(ref["dec_bf16_name"][int(d)])] for d in common]))
    return out


def summarize_v2(z: dict, ref: dict | None, start: list[int]) -> dict:
    """Schema v2 (module docstring): schema-1 quantities under honest names, plus bounds, flags and coarse KL."""
    s1 = summarize(z, ref, start)
    first = np.flatnonzero(z["pos_kind"] == 0)
    fd = z["pos_dec"][first]
    is_tool = z["dec_is_tool"][fd].astype(bool)
    b = np.array([p_act_bounds(z["top_ids"][i], z["top_lp"][i], start) for i in first])
    lo, hi, miss = b[:, 0], b[:, 1], b[:, 2].astype(bool)
    bf_act_tok = np.isin(z["dec_first_tok"][fd], start)
    act = dict(s1["act"])
    act.update({"p_act_lo_mean": float(lo.mean()), "p_act_hi_mean": float(hi.mean()), "p_act_missing_frac": float(miss.mean()),
                "p_act_by_bf16_type_lo_hi": {"tool": [float(lo[is_tool].mean()), float(hi[is_tool].mean())] if is_tool.any() else None,
                                             "text": [float(lo[~is_tool].mean()), float(hi[~is_tool].mean())] if (~is_tool).any() else None},
                "bf16_first_token_class_vs_generated_action_agreement": float((bf_act_tok == is_tool).mean()),
                "note": "p_act_mean / p_act_by_bf16_type are lower bounds (schema 1 counted a start token outside the top-k as 0)"})
    out = {"schema": 2, "act": act}
    if "act_all" in s1:
        fb = np.array([p_act_bounds(i, l, start) for i, l in zip(z["fa_top_ids"], z["fa_top_lp"])])
        out["act_all"] = dict(s1["act_all"], p_act_lo_mean=float(fb[:, 0].mean()), p_act_hi_mean=float(fb[:, 1].mean()),
                              p_act_missing_frac=float(fb[:, 2].mean()),
                              bf16_first_token_class_vs_generated_action_agreement=float(
                                  (np.isin(z["fa_first_tok"], start) == z["fa_is_tool"].astype(bool)).mean()) if "fa_first_tok" in z else None)
    tn = z.get("tool_name_est", {})
    if tn:
        pb, un = [], []
        for di, est in tn.items():
            pb.append(est[str(z["dec_bf16_name"][int(di)])])
            un.append(1 - sum(est.values()))
        t = s1["tool"]
        out["tool"] = {"n": t["n"], "p_bf16_name_mean": t["p_bf16_name_mean"], "p_bf16_name_median": t["p_bf16_name_median"],
                       "name_switch_rate_proxy": t["name_switch_rate"], "name_switch_upper_bound": float(np.mean(np.array(pb) < 0.5)),
                       "name_mass_unassigned_mean": float(np.mean(un)), "name_mass_unassigned_q90": float(np.quantile(un, 0.9)),
                       "name_mass_proxy_mean": t["p_name_mean"],
                       "note": "tool-name masses are a prefix-tree PROXY; P(BF16's name) is exact (teacher-forced product)"}
    if ref is not None and "error" not in s1.get("vs_ref", {}):
        out["vs_ref"] = contrast_v2(z, ref, start, s1["vs_ref"])
    return out


def contrast_v2(z: dict, ref: dict, start: list[int], c1: dict) -> dict:
    R = {_key(ref, i): i for i in range(len(ref["pos_kind"]))}
    out = {}
    ren = {"kl_mean": "approx_topk_kl_mean", "kl_median": "approx_topk_kl_median", "kl_q90": "approx_topk_kl_q90", "tv_mean": "approx_topk_tv_mean"}
    for kind, nm in ((0, "first"), (1, "tool_name")):
        if nm not in c1:
            continue
        o = {ren.get(k, k): v for k, v in c1[nm].items()}
        ck, ct, nc, dlo, dhi, flag = [], [], [], [], [], []
        for i in np.flatnonzero(z["pos_kind"] == kind):
            r = R.get(_key(z, i))
            if r is None:
                continue
            a, b = (ref["top_ids"][r], ref["top_lp"][r]), (z["top_ids"][i], z["top_lp"][i])
            k_, t_, n_ = coarse_kl(*a, *b, (ref["pos_tok"][r], ref["pos_lp"][r]), (z["pos_tok"][i], z["pos_lp"][i]))
            ck.append(k_); ct.append(t_); nc.append(n_)
            if kind == 0:
                rl, rh, rm = p_act_bounds(*a, start)
                cl, chh, cm = p_act_bounds(*b, start)
                dlo.append(logit(cl) - logit(rh)); dhi.append(logit(chh) - logit(rl)); flag.append(rm or cm)
        o.update({"coarse_kl_mean": float(np.mean(ck)), "coarse_kl_median": float(np.median(ck)), "coarse_kl_q90": float(np.quantile(ck, 0.9)),
                  "coarse_tv_mean": float(np.mean(ct)), "coarse_n_common_tokens_mean": float(np.mean(nc))})
        if kind == 0:
            flag = np.array(flag)
            o.update({"dlogit_act_mean_bounds": [float(np.mean(dlo)), float(np.mean(dhi))], "p_act_missing_frac_either": float(flag.mean()),
                      "dlogit_act_mean_complete_only": float(np.mean(np.array(dlo)[~flag])) if (~flag).any() else None,
                      "note": "dlogit_act_mean (schema 1) uses the lower bounds of both P(act); bounds and complete-only mean added"})
        out[nm] = o
    if "first_all" in c1:
        fa = dict(c1["first_all"])
        fa["approx_topk_kl_mean"] = fa.pop("kl_mean")
        pr = [p_act_bounds(i, l, start) for i, l in zip(ref["fa_top_ids"], ref["fa_top_lp"])]
        pc = [p_act_bounds(i, l, start) for i, l in zip(z["fa_top_ids"], z["fa_top_lp"])]
        ck = [coarse_kl(ref["fa_top_ids"][i], ref["fa_top_lp"][i], z["fa_top_ids"][i], z["fa_top_lp"][i])[0] for i in range(len(pr))]
        fa.update({"coarse_kl_mean": float(np.mean(ck)), "coarse_kl_median": float(np.median(ck)),
                   "dp_act_mean_bounds": [float(np.mean([c[0] - r[1] for c, r in zip(pc, pr)])), float(np.mean([c[1] - r[0] for c, r in zip(pc, pr)]))],
                   "p_act_missing_frac_either": float(np.mean([c[2] or r[2] for c, r in zip(pc, pr)]))})
        out["first_all"] = fa
    for k in ("tool_name_dp_mean", "tool_name_dp_bf16_name_mean"):
        if k in c1:
            out[k.replace("tool_name_dp", "tool_name_proxy_dp")] = c1[k]
    return out


def load_npz(path: str) -> dict:
    f = np.load(path + ".npz", allow_pickle=False)
    z = {k: f[k] for k in f.files}
    side = Path(path + ".names.json")
    z["tool_name_est"] = json.loads(side.read_text()) if side.exists() else {}
    return z


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int)
    ap.add_argument("--ref-run", action="append")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--topk", type=int, default=20)
    ap.add_argument("--positions", default="first,tool")
    ap.add_argument("--first-all", action="store_true", help="first-token top-k of every BF16 decision (generation)")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--model", help="model code (models.json); default: CLOQ_MODEL_ID/REVISION from the worker env")
    ap.add_argument("--ref", help="output prefix of the BF16 top-k cell of this model (KL / Δ contrasts)")
    ap.add_argument("--out")
    ap.add_argument("--resummarize", metavar="OUT", help="recompute <OUT>.json from <OUT>.npz (no server)")
    ap.add_argument("--schema", type=int, default=1, choices=(1, 2),
                    help="2: write the v2 summary (bounds, coarse KL, proxy names) to <OUT>.v2.json; <OUT>.json is untouched")
    a = ap.parse_args()
    if a.resummarize and a.schema == 2:
        out = ROOT / a.resummarize
        s1 = json.loads(Path(str(out) + ".json").read_text())
        start = [int(x) for x in s1["tool_start_ids"]]  # recorded by schema 1; no tokenizer needed
        ref = load_npz(str(ROOT / a.ref)) if a.ref and Path(ROOT / (a.ref + ".npz")).exists() else None
        s2 = {k: s1[k] for k in ("ref_runs", "topk", "positions", "seed", "parser", "n_decisions", "n_tool_decisions",
                                 "tool_start_ids", "n_positions", "n_tool_name_positions", "bf16_consistency") if k in s1}
        s2.update(summarize_v2(load_npz(str(out)), ref, start))
        s2["ref"] = a.ref if ref is not None else None
        s2["schema1_file"] = str(out) + ".json"
        Path(str(out) + ".v2.json").write_text(json.dumps(s2, indent=1))
        print(json.dumps({k: s2[k] for k in ("act", "vs_ref") if k in s2})[:1500])
        return
    tok, parser = tokenizer_for(a.model)
    start = tool_start_ids(tok, parser)
    ref = None
    if a.ref and Path(ROOT / (a.ref + ".npz")).exists():
        ref = load_npz(str(ROOT / a.ref))
    if a.resummarize:
        out = ROOT / a.resummarize
        z = load_npz(str(out))
        s = json.loads(Path(str(out) + ".json").read_text())
        s.update(summarize(z, ref, start))
        s.pop("vs_ref", None) if ref is None else None
        s["ref"] = a.ref if ref is not None else None
        Path(str(out) + ".json").write_text(json.dumps(s, indent=1))
        print(json.dumps({k: s[k] for k in ("act", "vs_ref") if k in s})[:2000])
        return
    assert a.port and a.ref_run and a.out, "--port, --ref-run and --out are required"
    want = set(a.positions.split(","))
    all_ds = load(a.ref_run)
    ds = list(all_ds)
    random.Random(a.seed).shuffle(ds)
    ds = sorted(ds[:a.n], key=lambda x: (x["run_id"], x["domain"], x["task_id"], x["decision_idx"]))
    geo, name_cache = [], {}
    for d in ds:
        js, npos = ([0] if "first" in want else []), None
        if "tool" in want and d["tool_calls"]:
            npos = name_positions(tok, d["completion_token_ids"])
            if npos:
                js += [j for j in npos[0] if j not in js]
        geo.append((sorted(set(js)), npos))

    def work(i):
        js, _ = geo[i]
        return score_positions(a.port, ds[i], js, a.topk) if js else []
    with ThreadPoolExecutor(a.concurrency) as ex:
        res = list(ex.map(work, range(len(ds))))
    rows = {k: [] for k in ("pos_dec", "pos_kind", "pos_j", "pos_k", "pos_tok", "pos_lp", "pos_rank", "top_ids", "top_lp")}
    est_all = {}
    for i, (d, r, (js, npos)) in enumerate(zip(ds, res, geo)):
        by_j = {x["j"]: x for x in r}
        name_js = npos[0] if npos else []
        for j in js:
            x = by_j[j]
            kinds = ([0] if j == 0 and "first" in want else []) + ([1] if j in name_js else [])
            for kd in kinds:
                rows["pos_dec"].append(i); rows["pos_kind"].append(kd); rows["pos_j"].append(j)
                rows["pos_k"].append(name_js.index(j) if kd == 1 else -1)
                rows["pos_tok"].append(x["tok"]); rows["pos_lp"].append(x["lp"]); rows["pos_rank"].append(x["rank"])
                rows["top_ids"].append(x["ids"]); rows["top_lp"].append(x["lps"])
        if npos:
            names = tool_names(tok, d, name_cache)
            est_all[str(i)] = name_mass(tok, [by_j[j] for j in name_js], npos[1], npos[2], npos[3], names)
    k = a.topk
    z = {"pos_dec": np.asarray(rows["pos_dec"], np.int32), "pos_kind": np.asarray(rows["pos_kind"], np.int8),
         "pos_j": np.asarray(rows["pos_j"], np.int32), "pos_k": np.asarray(rows["pos_k"], np.int16),
         "pos_tok": np.asarray(rows["pos_tok"], np.int32), "pos_lp": np.asarray(rows["pos_lp"], np.float32),
         "pos_rank": np.asarray(rows["pos_rank"], np.int32),
         "top_ids": np.asarray(rows["top_ids"], np.int32).reshape(-1, k), "top_lp": np.asarray(rows["top_lp"], np.float32).reshape(-1, k),
         "dec_run": np.array([d["run_id"] for d in ds]), "dec_domain": np.array([d["domain"] for d in ds]),
         "dec_task": np.array([str(d["task_id"]) for d in ds]), "dec_idx": np.array([d["decision_idx"] for d in ds], np.int32),
         "dec_is_tool": np.array([bool(d["tool_calls"]) for d in ds]),
         "dec_first_tok": np.array([d["completion_token_ids"][0] for d in ds], np.int32),
         "dec_bf16_name": np.array([g[1][3] if g[1] else "" for g in geo])}
    cons = []  # BF16 sanity: first-token logprob here vs closed loop (only meaningful for the BF16 cell)
    for i in np.flatnonzero(z["pos_kind"] == 0):
        cons.append(float(z["pos_lp"][i]) - ds[z["pos_dec"][i]]["token_logprobs"][0])
    if a.first_all:
        order = sorted(all_ds, key=lambda x: (x["run_id"], x["domain"], x["task_id"], x["decision_idx"]))
        with ThreadPoolExecutor(a.concurrency) as ex:
            fr = list(ex.map(lambda d: score_first(a.port, d, k), order))
        z.update({"fa_run": np.array([d["run_id"] for d in order]), "fa_domain": np.array([d["domain"] for d in order]),
                  "fa_task": np.array([str(d["task_id"]) for d in order]),
                  "fa_idx": np.array([d["decision_idx"] for d in order], np.int32),
                  "fa_is_tool": np.array([bool(d["tool_calls"]) for d in order]),
                  "fa_first_tok": np.array([d["completion_token_ids"][0] for d in order], np.int32),
                  "fa_top_ids": np.stack([x[0] for x in fr]), "fa_top_lp": np.stack([x[1] for x in fr])})
        fa_lp_own = []
        for d, (ids, lps) in zip(order, fr):
            w = np.flatnonzero(ids == d["completion_token_ids"][0])
            fa_lp_own.append(float(lps[w[0]]) - d["token_logprobs"][0] if len(w) else np.nan)
    z["tool_name_est"] = est_all
    s = {"ref_runs": a.ref_run, "topk": k, "positions": sorted(want), "seed": a.seed, "parser": parser,
         "ref": a.ref if ref is not None else None}
    s.update(summarize(z, ref, start))
    cons = np.abs(np.array(cons))
    s["bf16_consistency"] = {"note": "|logprob here - closed-loop token_logprobs[0]| of BF16's first token; the log rounds to 4 decimals, so the BF16 cell should be <= 5e-5 everywhere",
                             "prompt_logprobs_max": float(cons.max()) if len(cons) else None,
                             "prompt_logprobs_frac_within_log_rounding": float((cons <= TOL).mean()) if len(cons) else None}
    if a.first_all:
        fl = np.abs(np.array(fa_lp_own))
        s["bf16_consistency"].update({"generation_max": float(np.nanmax(fl)), "generation_frac_within_log_rounding": float(np.nanmean(fl <= TOL)),
                                      "generation_missing": int(np.isnan(fl).sum())})
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(str(out) + ".npz", **{k_: v for k_, v in z.items() if k_ != "tool_name_est"})
    Path(str(out) + ".names.json").write_text(json.dumps(est_all))
    Path(str(out) + ".json").write_text(json.dumps(s, indent=1))
    if a.schema == 2:  # also write the v2 summary (schema-1 file above is unchanged)
        s2 = {k_: s[k_] for k_ in ("ref_runs", "topk", "positions", "seed", "parser", "n_decisions", "n_tool_decisions",
                                  "tool_start_ids", "n_positions", "n_tool_name_positions", "bf16_consistency", "ref") if k_ in s}
        s2.update(summarize_v2(dict(z), ref, start))
        s2["schema1_file"] = str(out) + ".json"
        Path(str(out) + ".v2.json").write_text(json.dumps(s2, indent=1))
    print(json.dumps({k_: s.get(k_) for k_ in ("act", "tool", "vs_ref", "bf16_consistency")})[:3000])


if __name__ == "__main__":
    main()
