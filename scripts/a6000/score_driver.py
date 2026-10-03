"""Token-level scoring of Bank U states (W88; inspired by arXiv 2606.00206): teacher-force both recorded current actions
a_B and a_Q under both servers (B = BF16, Q = the cell's exact serving config incl. KV hooks) with vLLM prompt_logprobs.

Dispatched by scripts/a6000/worker.py::run_fork when task["fork"]["driver"] == "score" (servers launched exactly as for
bank_u). Per Bank U row of analysis/fork/bank_u/<m>_<cell>/<blk>/bank_rows.jsonl (spec["bank_out"]):
  1. rebuild the state (cloq.fork.make_state from the source run), rebuild the agent's prompt exactly as the ForkAgent
     does (agent-visible history, context policy, frozen chat template) and require sha256(prompt ids) == the row's
     prompt_ids_sha (= the recorded decision's);
  2. render each action with the chat template (history + action, add_generation_prompt=False): the rendered text must
     start with the prompt text and the tokenization must start with the prompt ids; the action ids are the rest, up
     to and including the first end-of-turn token (tool-call serialization exactly as the template renders it);
  3. POST /completions {prompt: prompt_ids + action_ids, max_tokens: 1, prompt_logprobs: K} to B and to Q (K = 20, the
     servers' --max-logprobs). The entry at action position j is the model's next-token distribution before action
     token j (top-K + the forced token); position 0 is the action-start distribution (identical for both actions).
Requests are phased (all B requests, then all Q requests): prompt logits of a 2048-token prefill chunk are allocated
outside vLLM's memory budget, and on one GPU (q4) only one server spikes at a time.

Teacher forcing uses the GENERATED token ids (GPT-6.1 review 5): the source run's logged completion ids where it logged
this action, else a greedy regeneration on the generating server (a_B on B, a_Q on Q); every action is also regenerated,
so recorded actions check that the server reproduces them. Template re-tokenization is only compared and flagged.
Per action token and model we store the chosen-token logprob and rank, the top-K (ids, logprobs), the truncated top-K
entropy Htk (top-K + one tail bucket; NOT the full entropy) and the margin; per token the top-K-union KL with tail bucket
KLu(B||Q) on the union of both top-K sets (+ the forced token; NOT the full KL) (missing in-union probabilities imputed as min(own K-th prob, own tail mass /
number missing)). Checks: prompt sha, render prefix, rank of the generating model's own action (must be 1 where the
template rendering equals the generated ids), template ids vs recorded completion ids and teacher-forced vs decode-time
logprobs for recorded actions (U1 a_Q, U2B a_B, U2Q a_Q of the source cell).

Output (spec["out"]): scores.jsonl.gz (one row per Bank U row), score_summary.json.
usage: python scripts/a6000/score_driver.py --task <task.json> --b-base URL --q-base URL --servers <json>
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import sys
import threading
import time
import traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(os.environ.get("CLOQ_ROOT", "/data/ziyangs/cloq"))
sys.path.insert(0, str(ROOT))

K = 20
LOCK = threading.Lock()


def log(msg: str) -> None:
    with LOCK:
        print(f"[{time.strftime('%F %T')}] {msg}", flush=True)


# ----------------------------------------------------------------------------------------------------------------------
# prompt and action rendering (CPU)
# ----------------------------------------------------------------------------------------------------------------------

def render(st: dict, actions: dict) -> dict:
    """Prompt ids at h_t exactly as cloq.fork.ForkAgent renders them, and each action's template-rendered ids."""
    from cloq import fork as F
    from cloq.context_policy import CHAT_TEMPLATE_KWARGS, apply_context_policy, get_tokenizer, render_prompt, render_prompt_ids, template_view
    from tau2.agent.base_agent import is_valid_agent_history_message
    from tau2.data_model.message import MultiToolMessage
    from tau2.utils.llm_utils import to_litellm_messages

    hist = [F.msg_from_dict(m) for m in st["history"]]
    agent = F._agent_for(st, "http://127.0.0.1:1/v1", "score-" + st["state_id"])
    state = agent.get_init_state(message_history=[m for m in hist[:-1] if is_valid_agent_history_message(m)])
    last = hist[-1]
    if isinstance(last, MultiToolMessage):
        state.messages.extend(last.tool_messages)
    else:
        state.messages.append(last)
    full_lm = to_litellm_messages(state.system_messages + state.messages)
    tools = agent.tools_schema
    kept_lm, cinfo = apply_context_policy(full_lm, tools)
    pids = render_prompt_ids(kept_lm, tools)
    ptext = render_prompt(kept_lm, tools)
    tok = get_tokenizer()
    # W100o (m24 only): cloq.mistral_render.MistralChatRender (CLOQ_TOKENIZER_MODE=mistral) has no HF vocab and renders
    # control tokens ([TOOL_CALLS], [/INST], </s>) that a text->ids re-encode does not reproduce, so the action ids come
    # from mistral_common directly, on the raw messages as for the prompt (context_policy._view). HF path unchanged.
    mistral = getattr(tok, "is_mistral", False)
    if mistral:
        eot = {tok.tok.eos_token_id}
    else:
        eot = {tok.convert_tokens_to_ids(t) for t in ("<|im_end|>", "<|eot_id|>") if t in tok.get_vocab()}
        if tok.eos_token_id is not None:
            eot.add(tok.eos_token_id)
    out = {"prompt_ids": pids, "prompt_ids_sha": F.ids_sha(pids), "n_prompt": len(pids), "context": cinfo.__dict__, "actions": {}}
    for name, msg in actions.items():
        a_lm = to_litellm_messages([F.msg_from_dict(msg)])
        if mistral:
            full, ids = tok.render_turn(kept_lm + a_lm, tools)
            rec = {"render_prefix_ok": full.startswith(ptext)}
        else:
            full = tok.apply_chat_template(template_view(kept_lm + a_lm), tools=tools or None, add_generation_prompt=False,
                                           tokenize=False, **CHAT_TEMPLATE_KWARGS)
            rec = {"render_prefix_ok": full.startswith(ptext)}
            ids = tok.encode(full, add_special_tokens=False)
        rec["ids_prefix_ok"] = ids[:len(pids)] == pids
        aids = ids[len(pids):]
        cut = next((i for i, x in enumerate(aids) if x in eot), None)
        rec["has_eot"] = cut is not None
        if cut is not None:
            aids = aids[:cut + 1]
        rec["ids"] = aids
        rec["toks"] = [tok.decode([x]) for x in aids]
        out["actions"][name] = rec
    return out


# ----------------------------------------------------------------------------------------------------------------------
# scoring (GPU servers)
# ----------------------------------------------------------------------------------------------------------------------

def prompt_logprobs(base: str, ids: list[int], start: int) -> list[dict]:
    body = {"model": "agent", "prompt": ids, "max_tokens": 1, "temperature": 0.0, "top_p": 1.0, "top_k": -1, "seed": 0,
            "prompt_logprobs": K, "skip_special_tokens": False}
    req = urllib.request.Request(base + "/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        c = json.load(r)["choices"][0]
    pl = c["prompt_logprobs"]
    assert len(pl) == len(ids), (len(pl), len(ids))
    out = []
    for j in range(start, len(ids)):
        d = pl[j] or {}
        top = sorted(((int(t), v["logprob"], v.get("rank")) for t, v in d.items()), key=lambda x: -x[1])
        ch = d.get(str(ids[j]))
        out.append({"lp": ch["logprob"] if ch else None, "rank": ch.get("rank") if ch else None,
                    "top_ids": [t for t, _, r in top if r is not None and r <= K][:K],
                    "top_lps": [round(lp, 5) for t, lp, r in top if r is not None and r <= K][:K]})
    return out


def generate_ids(base: str, prompt_ids: list[int], max_tokens: int, seed: int) -> list[int]:
    """Greedy regeneration of the action from prompt ids (as fork_driver.idcheck): batch-invariant serving reproduces the
    recorded generation token for token."""
    body = {"model": "agent", "prompt": prompt_ids, "max_tokens": max_tokens, "temperature": 0.0, "top_p": 1.0, "top_k": -1,
            "seed": seed, "return_token_ids": True, "skip_special_tokens": False}
    req = urllib.request.Request(base + "/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.load(r)["choices"][0]["token_ids"]


def entropy_tail(lps: list[float]) -> float:
    ps = [math.exp(x) for x in lps]
    tail = max(0.0, 1.0 - sum(ps))
    return -sum(p * math.log(p) for p in ps if p > 0) - (tail * math.log(tail) if tail > 1e-12 else 0.0)


def margin(pos: dict) -> float | None:
    """lp(chosen) - max lp(other tokens in top-K): positive iff the forced token is the model's argmax."""
    if pos["lp"] is None:
        return None
    alts = [lp for t, lp in zip(pos["top_ids"], pos["top_lps"]) if lp is not None and (pos.get("chosen") is None or t != pos["chosen"])]
    return pos["lp"] - max(alts) if alts else None


def kl_union(b: dict, q: dict, chosen: int) -> float:
    """Approximate KL(B||Q) over U = topK_B u topK_Q u {chosen}, plus one tail bucket per model."""
    def dist(m):
        d = {t: math.exp(lp) for t, lp in zip(m["top_ids"], m["top_lps"])}
        if m["lp"] is not None:
            d[chosen] = math.exp(m["lp"])
        return d
    db, dq = dist(b), dist(q)
    U = set(db) | set(dq)
    out = []
    for d in (db, dq):
        known = sum(d.values())
        miss = [t for t in U if t not in d]
        kth = min(d.values()) if d else 0.0
        tail0 = max(0.0, 1.0 - known)
        imp = min(kth, tail0 / len(miss)) if miss else 0.0
        full = {t: d.get(t, imp) for t in U}
        full["__tail__"] = max(1e-12, 1.0 - sum(full.values()))
        out.append(full)
    pb, pq = out
    return sum(p * (math.log(p) - math.log(max(pq[t], 1e-12))) for t, p in pb.items() if p > 0)


def summarise(seqs: dict, ids: list[int]) -> dict:
    """Per-token derived metrics for one action under B and Q."""
    per = []
    for j, t in enumerate(ids):
        b, q = seqs["B"][j], seqs["Q"][j]
        b["chosen"] = q["chosen"] = t
        row = {"lp_B": b["lp"], "lp_Q": q["lp"], "rank_B": b["rank"], "rank_Q": q["rank"],
               "Htk_B": round(entropy_tail(b["top_lps"]), 5), "Htk_Q": round(entropy_tail(q["top_lps"]), 5),
               "m_B": None if margin(b) is None else round(margin(b), 5), "m_Q": None if margin(q) is None else round(margin(q), 5),
               "KLu_BQ": round(kl_union(b, q, t), 6)}
        per.append(row)
    return per


def run_task(spec: dict, bases: dict, servers: dict, out: Path) -> dict:
    """Phases: CPU prep (state, prompt ids + sha check, template ids) -> regenerate every action on its generating server
    (a_B on B, a_Q on Q) -> teacher-force the GENERATED ids (recorded completion ids where the source run logged them, else
    the regeneration) under B and under Q on the identical prompt ids -> per-token metrics."""
    from cloq import fork as F
    from cloq.context_policy import get_tokenizer

    bank_dir = ROOT / spec["bank_out"]
    rows = [json.loads(x) for x in open(bank_dir / "bank_rows.jsonl") if x.strip()]
    bank_sha = hashlib.sha256((bank_dir / "bank_rows.jsonl").read_bytes()).hexdigest()
    if spec.get("only_state_keys"):
        keep = set(spec["only_state_keys"])
        rows = [r for r in rows if r["state_key"] in keep]
    if spec.get("limit"):
        rows = rows[: spec["limit"]]
    t0 = time.time()
    blocks = {}
    prep = []
    for r in rows:  # CPU preparation, sequential (the HF tokenizer is not thread-safe)
        base = {k: r.get(k) for k in ("state_key", "state_id", "sub", "model", "cell", "block", "domain", "task_id", "t",
                                      "n_decisions", "source_run", "exact_agreement", "agreement_category", "Y", "prompt_ids_sha")}
        if "Y" not in r or r.get("missing_reason"):
            prep.append({**base, "missing_reason": r.get("missing_reason") or "bank row without Y"})
            continue
        try:
            k = (r["source_run"], r["domain"])
            if k not in blocks:
                blocks[k] = F.Block(ROOT, *k)
            st = F.make_state(blocks[k], r["task_id"], r["t"])
            rd = render(st, {"a_B": r["a_B"], "a_Q": r["a_Q"]})
            checks = {"prompt_sha_ok": rd["prompt_ids_sha"] == r["prompt_ids_sha"] == st["q_decision"]["prompt_ids_sha"],
                      **{f"{a}_{c}": rd["actions"][a][c] for a in ("a_B", "a_Q") for c in ("render_prefix_ok", "ids_prefix_ok", "has_eot")}}
            dec = blocks[k].dec[r["task_id"]][r["t"]]
            rec_act = "a_B" if r["sub"] == "U2B" else ("a_Q" if (r["sub"] == "U1" or (r["sub"] == "U2Q" and r["cell"] == "gptq_w4_d1")) else None)
            la = st["agent_llm"]["llm_args_agent"]
            prep.append({**base, "exact": F.canon_msg(r["a_B"]) == F.canon_msg(r["a_Q"]), "checks": checks, "n_prompt": rd["n_prompt"],
                         "prompt_ids": rd["prompt_ids"], "template_ids": {a: rd["actions"][a]["ids"] for a in ("a_B", "a_Q")},
                         "recorded": {"action": rec_act, "ids": dec.get("completion_token_ids"), "token_logprobs": dec.get("token_logprobs")} if rec_act else None,
                         "gen_args": {"max_tokens": int(la.get("max_tokens") or 2048), "seed": int(la.get("seed") or 0)}})
        except Exception as e:
            prep.append({**base, "missing_reason": f"prep error {e!r}", "trace": traceback.format_exc()[-1500:]})
    log(f"prepared {len(prep)} rows in {time.time() - t0:.0f} s; prompt sha ok "
        f"{sum(1 for p in prep if p.get('checks', {}).get('prompt_sha_ok'))}/{len(prep)}")
    live = [i for i, p in enumerate(prep) if "prompt_ids" in p and p["checks"]["prompt_sha_ok"]]

    # regeneration: a_B on B, a_Q on Q (greedy, frozen max_tokens)
    regen = {}
    t1 = time.time()
    for role, a in (("B", "a_B"), ("Q", "a_Q")):
        def gen(i):
            p = prep[i]
            try:
                return i, generate_ids(bases[role], p["prompt_ids"], p["gen_args"]["max_tokens"], p["gen_args"]["seed"])
            except Exception as e:
                return i, {"error": repr(e)[:300]}
        with ThreadPoolExecutor(spec.get("concurrency", 4)) as ex:
            for i, ids in ex.map(gen, live):
                regen[(i, a)] = ids
        log(f"regenerated {a} on {role}: {len(live)} requests, {time.time() - t1:.0f} s")
    tok = get_tokenizer()
    jobs = []  # (row index, sequence name)
    for i in live:
        p = prep[i]
        gids, src = {}, {}
        for a in ("a_B", "a_Q"):
            rg = regen.get((i, a))
            rc = p["recorded"] if p["recorded"] and p["recorded"]["action"] == a and p["recorded"]["ids"] else None
            if rc:
                gids[a], src[a] = list(rc["ids"]), "recorded"
            elif isinstance(rg, list):
                gids[a], src[a] = list(rg), "regenerated"
            else:
                gids[a], src[a] = None, f"regeneration failed {rg}"
            p["checks"][f"{a}_template_eq_generated"] = gids[a] == p["template_ids"][a] if gids[a] is not None else None
            if rc:
                p["checks"][f"{a}_regen_eq_recorded"] = isinstance(rg, list) and rg == list(rc["ids"])
        p["gen_ids"], p["gen_src"] = gids, src
        if any(v is None for v in gids.values()):
            p["missing_reason"] = f"no generated ids {src}"
            continue
        p["same_ids"] = gids["a_B"] == gids["a_Q"]
        p["toks"] = {a: [tok.decode([x]) for x in gids[a]] for a in gids}
        for a in (("a_B",) if p["same_ids"] else ("a_B", "a_Q")):
            jobs.append((i, a))
    res = {}
    for role in ("B", "Q"):  # phased: one server's prompt-logit spike at a time
        def one(j):
            i, a = j
            p = prep[i]
            try:
                return (role, i, a), prompt_logprobs(bases[role], p["prompt_ids"] + p["gen_ids"][a], p["n_prompt"])
            except Exception as e:
                return (role, i, a), {"error": repr(e)[:300]}
        with ThreadPoolExecutor(spec.get("concurrency", 4)) as ex:
            for key, val in ex.map(one, jobs):
                res[key] = val
        log(f"scored {role}: {len(jobs)} requests, {time.time() - t1:.0f} s")
    gpu_seconds = time.time() - t1

    out.mkdir(parents=True, exist_ok=True)
    recs = []
    for i, p in enumerate(prep):
        p.pop("prompt_ids", None)
        p.pop("template_ids", None)
        if "missing_reason" in p:
            recs.append(p)
            continue
        if not p["checks"]["prompt_sha_ok"]:
            p["missing_reason"] = "prompt ids sha mismatch"
            recs.append(p)
            continue
        acts, err = {}, None
        for a in ("a_B", "a_Q"):
            src = "a_B" if p["same_ids"] else a
            ids = p["gen_ids"][src]
            seqs = {role: res.get((role, i, src)) for role in ("B", "Q")}
            if any(not isinstance(s, list) for s in seqs.values()):
                err = {role: (s or {}).get("error") if not isinstance(s, list) else None for role, s in seqs.items()}
                break
            acts[a] = {"ids": ids, "ids_source": p["gen_src"][a], "toks": p["toks"][src], "B": seqs["B"], "Q": seqs["Q"], "tok": summarise(seqs, ids)}
        if err:
            p["missing_reason"] = f"scoring error {err}"
            recs.append(p)
            continue
        p.pop("gen_ids")
        p.pop("toks")
        # action-start distributions (position 0; identical prefix for both actions)
        p["start"] = {role: {"top_ids": acts["a_B"][role][0]["top_ids"], "top_lps": acts["a_B"][role][0]["top_lps"],
                             "Htk": round(entropy_tail(acts["a_B"][role][0]["top_lps"]), 5)} for role in ("B", "Q")}
        p["checks"]["start_same_across_actions"] = all(acts["a_B"][r][0]["top_lps"] == acts["a_Q"][r][0]["top_lps"] for r in ("B", "Q"))
        # own action is the generating model's argmax at every position (tie-aware: vLLM ranks exact ties as 2)
        p["checks"]["own_rank1_B_on_aB"] = all(x["lp_B"] >= s["top_lps"][0] - 1e-4 for x, s in zip(acts["a_B"]["tok"], acts["a_B"]["B"]))
        p["checks"]["own_rank1_Q_on_aQ"] = all(x["lp_Q"] >= s["top_lps"][0] - 1e-4 for x, s in zip(acts["a_Q"]["tok"], acts["a_Q"]["Q"]))
        rc = p.pop("recorded")
        if rc and rc["ids"] and rc["token_logprobs"]:
            role = "B" if rc["action"] == "a_B" else "Q"
            dl = rc["token_logprobs"]
            diffs = [abs(acts[rc["action"]]["tok"][j]["lp_" + role] - dl[j]) for j in range(min(len(dl), len(acts[rc["action"]]["tok"]))) if dl[j] is not None]
            p["checks"]["recorded_max_abs_lp_diff_vs_decode"] = round(max(diffs), 5) if diffs else None
        p["acts"] = acts
        recs.append(p)
    with gzip.open(out / "scores.jsonl.gz", "wt", encoding="utf-8") as f:
        for x in recs:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    ok = [x for x in recs if "acts" in x]

    def cnt(key):
        v = [x["checks"].get(key) for x in ok if x["checks"].get(key) is not None]
        return f"{sum(1 for z in v if z)}/{len(v)}"
    summ = {"protocol": "score_states v2 (W88; GPT-6.1 review 5: teacher-forced from generated token ids)", "spec": spec, "servers": servers,
            "bank_rows_sha256": bank_sha, "n_rows": len(recs), "n_ok": len(ok), "n_missing": len(recs) - len(ok),
            "missing": [{"state_key": x["state_key"], "reason": x.get("missing_reason")} for x in recs if "acts" not in x],
            "n_prompt_sha_ok": sum(1 for x in recs if x.get("checks", {}).get("prompt_sha_ok")),
            "n_render_ok": sum(1 for x in ok if all(v for kk, v in x["checks"].items() if kk.endswith(("_prefix_ok", "has_eot")))),
            "template_eq_generated": {a: cnt(f"{a}_template_eq_generated") for a in ("a_B", "a_Q")},
            "regen_eq_recorded": {a: cnt(f"{a}_regen_eq_recorded") for a in ("a_B", "a_Q")},
            "ids_source": dict(__import__("collections").Counter(f"{a}:{x['acts'][a]['ids_source']}" for x in ok for a in ("a_B", "a_Q"))),
            "n_start_same": sum(1 for x in ok if x["checks"]["start_same_across_actions"]),
            "n_own_rank1_B_on_aB": sum(1 for x in ok if x["checks"]["own_rank1_B_on_aB"]),
            "n_own_rank1_Q_on_aQ": sum(1 for x in ok if x["checks"]["own_rank1_Q_on_aQ"]),
            "recorded_max_abs_lp_diff_vs_decode": max([x["checks"]["recorded_max_abs_lp_diff_vs_decode"] for x in ok
                                                       if x["checks"].get("recorded_max_abs_lp_diff_vs_decode") is not None], default=None),
            "n_score_requests": len(jobs) * 2, "n_regen_requests": len(live) * 2,
            "n_action_tokens": sum(len(x["acts"]["a_B"]["ids"]) + (0 if x["same_ids"] else len(x["acts"]["a_Q"]["ids"])) for x in ok),
            "gpu_phase_seconds": gpu_seconds, "seconds": time.time() - t0}
    (out / "score_summary.json").write_text(json.dumps(summ, indent=1, default=str))
    log(f"score {spec['model']}:{spec['cell']} {spec['bank_out']}: ok {summ['n_ok']}/{summ['n_rows']}, prompt sha ok {summ['n_prompt_sha_ok']}, "
        f"render ok {summ['n_render_ok']}, template==generated {summ['template_eq_generated']}, regen==recorded {summ['regen_eq_recorded']}, "
        f"own rank1 B {summ['n_own_rank1_B_on_aB']} Q {summ['n_own_rank1_Q_on_aQ']}, lp diff vs decode {summ['recorded_max_abs_lp_diff_vs_decode']}, "
        f"{summ['seconds']:.0f} s")
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--b-base", required=True)
    ap.add_argument("--q-base", required=True)
    ap.add_argument("--user-base", default=None)  # unused: no simulator needed (accepted for the run_fork command line)
    ap.add_argument("--servers")
    a = ap.parse_args()
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="ERROR")
    from cloq import fork as F
    F.setup_tau2()
    task = json.load(open(a.task))
    spec = task["fork"]
    r = run_task(spec, {"B": a.b_base, "Q": a.q_base}, json.load(open(a.servers)) if a.servers else {}, ROOT / spec["out"])
    print(json.dumps({k: v for k, v in r.items() if k in ("n_rows", "n_ok", "n_prompt_sha_ok", "n_render_ok", "template_eq_generated", "regen_eq_recorded")}, default=str))
    if r["n_ok"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
