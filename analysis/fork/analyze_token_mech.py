"""Token-level mechanism of consequential B/Q action differences at Bank U states (W88; exploratory; inspired by
arXiv 2606.00206, "Quantized Reasoning Models Think They Need to Think Longer").

Inputs (discovered; a block is used only when its score_summary.json exists; the dry/ directory is never read):
  analysis/fork/token_scores/<model>_<cell>/<block>/scores.jsonl.gz   scripts/a6000/score_driver.py (teacher-forced a_B,
                                                                       a_Q under B and Q, top-20 prompt logprobs)
Units: one (cell, state) row. Y, a_B, a_Q come from the Bank U native rows (copied into the score rows). f01 is
development; f02/f03 are validation. Sub-banks U1 / U2B / U2Q are never pooled.

Terms (GPT-6.1 review 5): Htk = truncated top-20 entropy (top-20 + one tail bucket), KLu = top-20-union KL(B||Q) with a
tail bucket; never "full" entropy/KL. Teacher forcing used the generated token ids on the identical prompt ids for B and Q.

1a. Whole-action analysis (primary mechanism view): consequential (flip, Y_BQ != Y_QQ) vs non-consequential ordinary
    states, all states and differing-only, per sub-bank x model, stratified by cell x a_Q length tercile; Q-visible
    whole-proposal statistics (Htk_Q and margin at the action start, mean/max Htk_Q, min margin, mean lp over a_Q),
    B-diagnostic ones (KLu, lp_B of a_Q), and position profiles over a_Q (5 relative-position bins).
1b. First divergence (DIAGNOSTIC ONLY: position k needs both models; conditioning on differing states is a selection):
    Htk/KLu/margin/log-odds at k; flip vs no flip, rescue vs damage; per sub-bank x cell and x model.
2.  Divergence-token taxonomy of the first divergent token/span; enrichment among flips (rate ratio, Fisher p,
    descriptive). --freeze also writes the frozen repair-candidate list (manifests/fork/token_repair_candidates_v1.json;
    f01 only; the repair intervention itself is NOT built).
3.  Sampled-state intervention value of one-step BF16 escalation (not a token mechanism). Y_BQ - Y_QQ at an
    outcome-independent sampled state is the realised effect of escalating that one decision. Q-visible triggers only:
    S_H0 = Htk_Q at the action start, S_mm = -min Q margin over a_Q, S_lp = -mean lp_Q(a_Q). --freeze chooses the rule on
    f01 (population U1; per-cell thresholds = f01 quantiles at 5/10/20%) and writes manifests/fork/token_trigger_rule_v1.json
    (never overwritten). Evaluation on blocks != f01 only vs a random trigger escalating the same number of states per
    cell (exact null). In-sample f01 numbers are labelled; no oracle selection. Not a closed-loop policy.

usage: python analysis/fork/analyze_token_mech.py [--boot 2000] [--freeze]
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SC = ROOT / "analysis" / "fork" / "token_scores"
OUT = ROOT / "analysis" / "fork" / "out"
RULE = ROOT / "manifests" / "fork" / "token_trigger_rule_v1.json"
SUBS = ("U1", "U2B", "U2Q")
CELLS = ("gptq_w4_d1", "awq_w4", "kvq_int8")
DEV = ("f01",)
RATES = (0.05, 0.10, 0.20)
TRIGGERS = ("S_H0", "S_mm", "S_lp")
NBIN = 5
# first-divergence metrics need both models (position k is defined by a_B vs a_Q): DIAGNOSTIC ONLY
DIV_METRICS = ("Htk_Q_k", "Htk_B_k", "KLu_k", "mQ_k", "lodds_Q_k", "k", "k_rel")
# whole-action metrics; Q-visible ones (Q_VIS) are the only admissible deployable trigger inputs
Q_VIS = ("Htk_Q_0", "mQ_0", "Htk_Q_mean", "Htk_Q_max", "mQ_min", "lpQ_mean", "len_Q")
B_DIAG = ("KLu_0", "KLu_mean", "KLu_max", "lpB_of_aQ_mean", "Htk_B_0")
METRICS = DIV_METRICS + Q_VIS + B_DIAG
REPAIR = ROOT / "manifests" / "fork" / "token_repair_candidates_v1.json"


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ----------------------------------------------------------------------------------------------------------------------
# loading and per-state features
# ----------------------------------------------------------------------------------------------------------------------

def load(blocks_allowed=None) -> tuple[list[dict], dict]:
    rows, inputs = [], {}
    for f in sorted(glob.glob(str(SC / "*_*" / "f*" / "scores.jsonl.gz"))):
        p = Path(f)
        if p.parts[-3] == "dry" or not (p.parent / "score_summary.json").exists():
            continue
        blk = p.parent.name
        if blocks_allowed is not None and blk not in blocks_allowed:
            continue
        inputs[rel(p)] = sha_file(p)
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            for line in fh:
                rows.append(json.loads(line))
    return rows, inputs


def features(r: dict) -> dict:
    Y = r["Y"]
    G = Y["BQ"] - Y["QQ"]
    u = {k: r[k] for k in ("state_key", "state_id", "sub", "model", "cell", "block", "domain", "task_id")}
    u["exact"] = bool(r["same_ids"])  # identical generated token ids (canonical-message equality is the bank's exact flag)
    u["exact_canon"] = bool(r["exact"])
    u.update({"task": f"{r['domain']}|{r['task_id']}", "G": G, "flip": int(G != 0), "r": int(G == 1), "d": int(G == -1)})
    aB, aQ = r["acts"]["a_B"], r["acts"]["a_Q"]
    tq, tb = aQ["tok"], aB["tok"]
    u["kind_Q"] = "act" if any("<tool_call>" in t for t in aQ["toks"]) else "talk"
    # Q-visible (whole Q proposal / Q-defined positions): Q's own action under Q, Q's action-start distribution
    mq = [x["m_Q"] for x in tq if x["m_Q"] is not None]
    u["Htk_Q_0"] = r["start"]["Q"]["Htk"]
    u["Htk_B_0"] = r["start"]["B"]["Htk"]
    u["KLu_0"] = tq[0]["KLu_BQ"]
    u["mQ_0"] = tq[0]["m_Q"]
    u["Htk_Q_mean"] = float(np.mean([x["Htk_Q"] for x in tq]))
    u["Htk_Q_max"] = float(np.max([x["Htk_Q"] for x in tq]))
    u["KLu_mean"] = float(np.mean([x["KLu_BQ"] for x in tq]))
    u["KLu_max"] = float(np.max([x["KLu_BQ"] for x in tq]))
    u["mQ_min"] = float(min(mq)) if mq else None
    u["lpQ_mean"] = float(np.mean([x["lp_Q"] for x in tq]))
    u["lpB_of_aQ_mean"] = float(np.mean([x["lp_B"] for x in tq]))  # needs B: diagnostic
    u["len_Q"], u["len_B"] = len(aQ["ids"]), len(aB["ids"])
    # deterministic tie-break (exact bf16 ties make min margin = 0 for many states): + 1e-9 x hash(state_key) in [0, 1)
    jit = 1e-9 * int(hashlib.sha256(f"token-trigger-v1|{r['state_key']}".encode()).hexdigest()[:8], 16) / 16 ** 8
    u["S_H0"] = u["Htk_Q_0"] + jit
    u["S_mm"] = (-u["mQ_min"] if u["mQ_min"] is not None else 0.0) + jit
    u["S_lp"] = -u["lpQ_mean"] + jit
    u["own_rank1_Q"] = all(x["lp_Q"] >= s["top_lps"][0] - 1e-4 for x, s in zip(tq, aQ["Q"]))  # tie-aware argmax
    # per-token Q-defined profile over a_Q (relative position bins), for the position-controlled whole-action analysis
    n = len(tq)
    u["_prof"] = [(min(NBIN - 1, int(NBIN * j / n)), x["Htk_Q"], x["m_Q"], x["KLu_BQ"]) for j, x in enumerate(tq)]
    if not u["exact"]:
        ib, iq = aB["ids"], aQ["ids"]
        k = next((j for j in range(min(len(ib), len(iq))) if ib[j] != iq[j]), min(len(ib), len(iq)))
        u["k"] = k
        u["k_rel"] = k / max(1, len(iq))
        if k < len(iq) and k < len(ib):
            xq, xb = tq[k], tb[k]
            u["Htk_Q_k"], u["Htk_B_k"], u["KLu_k"] = xq["Htk_Q"], xq["Htk_B"], xq["KLu_BQ"]
            u["mQ_k"] = xq["m_Q"]
            u["lodds_Q_k"] = xq["lp_Q"] - xb["lp_Q"]  # Q's log-odds of its own token vs B's token at k
            u["lodds_B_k"] = xb["lp_B"] - xq["lp_B"]
            u["div_cls"], u["div_detail"] = div_class(aB, aQ, k)
            u["span_Q"] = "".join(aQ["toks"][k:k + 6])
            u["span_B"] = "".join(aB["toks"][k:k + 6])
    return u


# ----------------------------------------------------------------------------------------------------------------------
# divergence taxonomy
# ----------------------------------------------------------------------------------------------------------------------

RE_CLOSE = re.compile(r"^\s*(is there anything else|anything else|thank you|thanks|have a (great|nice|good)|you're welcome|goodbye|"
                      r"feel free|if you (have|need)|let me know if)", re.I)
RE_CONFIRM = re.compile(r"^\s*(please confirm|could you (please )?confirm|can you confirm|confirm|would you like|do you want|shall i|"
                        r"should i|may i proceed|do you wish|is that correct|is this correct|are you sure|yes|\(yes)", re.I)
RE_DISC = re.compile(r"^\s*(however|but|let me|i'll|i will|i'm going to|i am going to|i can|i need|i see|i understand|first|now|"
                     r"next|also|additionally|unfortunately|sure|okay|ok|great|alright|certainly|of course|to |before|since|"
                     r"thank|i apologi|sorry|it (looks|seems)|based on)", re.I)


def _sentence_end(toks: list[str], k: int) -> str:
    s = "".join(toks[k:k + 80])
    m = re.search(r"[.?!:\n]", s)
    return m.group(0) if m else ""


def div_class(aB: dict, aQ: dict, k: int) -> tuple[str, str]:
    tq, tb = aQ["toks"], aB["toks"]
    pre = "".join(tq[:k])
    nq, nb = "".join(tq[k:k + 12]), "".join(tb[k:k + 12])
    cur = (tq[k] if k < len(tq) else "") + "|" + (tb[k] if k < len(tb) else "")
    if "<tool_call>" in (tq[k] if k < len(tq) else "") or "<tool_call>" in (tb[k] if k < len(tb) else ""):
        return "kind_switch", cur
    eot = ("<|im_end|>", "<|eot_id|>", "<|endoftext|>")
    if any(t in (tq[k] if k < len(tq) else "") for t in eot) or any(t in (tb[k] if k < len(tb) else "") for t in eot):
        return "closing", cur
    if pre.count("<tool_call>") > pre.count("</tool_call>"):
        call = pre[pre.rfind("<tool_call>"):]
        if '"arguments"' not in call:
            return "tool_name", cur
        if re.search(r"[\d#]", tq[k] if k < len(tq) else "") or re.search(r"[\d#]", tb[k] if k < len(tb) else ""):
            return "number_id", cur
        return "tool_arg", cur
    if re.search(r"\d|#", (tq[k] if k < len(tq) else "") + (tb[k] if k < len(tb) else "")):
        return "number_id", cur
    if RE_CLOSE.search(nq) or RE_CLOSE.search(nb):
        return "closing", cur
    eq, eb = _sentence_end(tq, k), _sentence_end(tb, k)
    if (eq == "?") != (eb == "?"):
        return "question_vs_statement", cur
    if RE_CONFIRM.search(nq) or RE_CONFIRM.search(nb):
        return "confirmation", cur
    if RE_DISC.search(nq) or RE_DISC.search(nb):
        return "discourse_marker", cur
    a = (tq[k] if k < len(tq) else "").strip()
    b = (tb[k] if k < len(tb) else "").strip()
    if (not a or not re.search(r"\w", a)) or (not b or not re.search(r"\w", b)):
        return "format_punct", cur
    return "other_lexical", cur


# ----------------------------------------------------------------------------------------------------------------------
# statistics
# ----------------------------------------------------------------------------------------------------------------------

def auc(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    x = np.concatenate([a, b])
    ranks = np.argsort(np.argsort(x, kind="mergesort"), kind="mergesort").astype(float) + 1
    # midranks for ties
    for v in np.unique(x):
        m = x == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    return float((ranks[: len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b)))


def contrast(us: list[dict], metric: str, grp: str, rng, nboot: int) -> dict:
    """grp 'flip': flip vs no flip; 'rd': rescue (G = 1) vs damage (G = -1) among flips. Task-cluster bootstrap."""
    if grp == "flip":
        sel = [u for u in us if u.get(metric) is not None]
        lab = lambda u: u["flip"] == 1  # noqa: E731
    else:
        sel = [u for u in us if u.get(metric) is not None and u["flip"]]
        lab = lambda u: u["G"] == 1  # noqa: E731
    a = np.array([u[metric] for u in sel if lab(u)], float)
    b = np.array([u[metric] for u in sel if not lab(u)], float)
    res = {"n1": len(a), "n0": len(b), "n_states": len({(u["state_id"]) for u in sel}), "n_tasks": len({u["task"] for u in sel})}
    if len(a) == 0 or len(b) == 0:
        return res
    res.update({"mean1": round(float(a.mean()), 4), "mean0": round(float(b.mean()), 4), "diff": round(float(a.mean() - b.mean()), 4),
                "auc": round(auc(a, b), 3)})
    tasks = sorted({u["task"] for u in sel})
    by = collections.defaultdict(list)
    for u in sel:
        by[u["task"]].append(u)
    dd, aa = [], []
    for _ in range(nboot):
        pick = rng.integers(0, len(tasks), len(tasks))
        x1, x0 = [], []
        for t in pick:
            for u in by[tasks[t]]:
                (x1 if lab(u) else x0).append(u[metric])
        if x1 and x0:
            x1, x0 = np.array(x1), np.array(x0)
            dd.append(x1.mean() - x0.mean())
            aa.append(auc(x1, x0))
    if dd:
        res["diff_ci"] = [round(float(np.percentile(dd, 2.5)), 4), round(float(np.percentile(dd, 97.5)), 4)]
        res["auc_ci"] = [round(float(np.percentile(aa, 2.5)), 3), round(float(np.percentile(aa, 97.5)), 3)]
    return res


def fisher_greater(a: int, b: int, c: int, d: int) -> float:
    """One-sided Fisher exact p for enrichment: table [[a, b], [c, d]] = [[class&flip, class&noflip], [other&flip, other&noflip]]."""
    n1, n2, m1 = a + b, c + d, a + c
    N = n1 + n2
    def hyp(x):
        return math.comb(n1, x) * math.comb(n2, m1 - x) / math.comb(N, m1)
    return float(sum(hyp(x) for x in range(a, min(n1, m1) + 1)))


# ----------------------------------------------------------------------------------------------------------------------
# escalation
# ----------------------------------------------------------------------------------------------------------------------

def null_dist(R: int, D: int, N: int, m: int) -> dict:
    """Exact distribution of (#rescues - #damages) when m of N states (R rescue, D damage, N-R-D zero) are drawn at random."""
    Z = N - R - D
    tot = math.comb(N, m)
    out = collections.defaultdict(float)
    for x in range(0, min(R, m) + 1):
        for y in range(0, min(D, m - x) + 1):
            z = m - x - y
            if z > Z:
                continue
            out[x - y] += math.comb(R, x) * math.comb(D, y) * math.comb(Z, z) / tot
    return dict(out)


def null_turn(R: int, D: int, N: int, m: int) -> dict:
    T = R + D
    tot = math.comb(N, m)
    return {x: math.comb(T, x) * math.comb(N - T, m - x) / tot for x in range(0, min(T, m) + 1) if m - x <= N - T}


def convolve(ds: list[dict]) -> dict:
    out = {0: 1.0}
    for d in ds:
        new = collections.defaultdict(float)
        for a, pa in out.items():
            for b, pb in d.items():
                new[a + b] += pa * pb
        out = dict(new)
    return out


def escalate(us: list[dict], score: str, thr: dict) -> dict:
    """thr: cell key -> threshold (escalate iff score > thr). Returns per-cell and pooled outcomes + exact random nulls."""
    cells = collections.defaultdict(list)
    for u in us:
        cells[f"{u['model']}_{u['cell']}"].append(u)
    per, nulls_g, nulls_t = {}, [], []
    for ck, xs in sorted(cells.items()):
        if ck not in thr:
            continue
        esc = [u for u in xs if u[score] > thr[ck]]
        R, D, N, m = sum(u["r"] for u in xs), sum(u["d"] for u in xs), len(xs), len(esc)
        per[ck] = {"N": N, "R": R, "D": D, "n_escalated": m, "rate": round(m / N, 3) if N else None,
                   "net_gain": sum(u["G"] for u in esc), "rescued": sum(u["r"] for u in esc), "damaged": sum(u["d"] for u in esc),
                   "turnover_captured": sum(u["flip"] for u in esc), "turnover_total": R + D,
                   "random_expected_net": round(m * (R - D) / N, 3) if N else None, "random_expected_turnover": round(m * (R + D) / N, 3) if N else None}
        nulls_g.append(null_dist(R, D, N, m))
        nulls_t.append(null_turn(R, D, N, m))
    tot = {k: sum(v[k] for v in per.values()) for k in ("N", "R", "D", "n_escalated", "net_gain", "rescued", "damaged", "turnover_captured", "turnover_total")}
    ng, nt = convolve(nulls_g), convolve(nulls_t)
    tot["random_expected_net"] = round(sum(k * p for k, p in ng.items()), 3)
    tot["random_expected_turnover"] = round(sum(k * p for k, p in nt.items()), 3)
    tot["p_net_ge_random"] = round(sum(p for k, p in ng.items() if k >= tot["net_gain"]), 4)
    tot["p_turnover_ge_random"] = round(sum(p for k, p in nt.items() if k >= tot["turnover_captured"]), 4)
    tot["turnover_capture_frac"] = round(tot["turnover_captured"] / tot["turnover_total"], 3) if tot["turnover_total"] else None
    return {"per_cell": per, "pooled": tot}


def thresholds(us: list[dict], score: str, rate: float) -> dict:
    cells = collections.defaultdict(list)
    for u in us:
        cells[f"{u['model']}_{u['cell']}"].append(u[score])
    out = {}
    for ck, v in sorted(cells.items()):  # escalate the top m = max(1, round(rate * N)) f01 states: threshold between ranks m and m+1
        v = sorted(v, reverse=True)
        m = max(1, int(round(rate * len(v))))
        out[ck] = float((v[m - 1] + v[m]) / 2) if m < len(v) else float(v[-1]) - 1e-9
    return out


def freeze_rule(dev: list[dict]) -> dict:
    pop = [u for u in dev if u["sub"] == "U1"]
    table = {}
    for s in TRIGGERS:
        table[s] = {}
        for rate in RATES:
            th = thresholds(pop, s, rate)
            e = escalate(pop, s, th)["pooled"]
            table[s][str(rate)] = {k: e[k] for k in ("n_escalated", "net_gain", "rescued", "damaged", "turnover_captured", "turnover_total",
                                                     "random_expected_net", "random_expected_turnover")}
    # selection criterion (declared here, applied to f01 only): highest mean over rates of in-sample net gain minus its random
    # expectation; ties -> higher mean turnover captured minus random expectation; then the fixed order of TRIGGERS.
    def key(s):
        v = table[s].values()
        return (np.mean([x["net_gain"] - x["random_expected_net"] for x in v]),
                np.mean([x["turnover_captured"] - x["random_expected_turnover"] for x in v]), -TRIGGERS.index(s))
    best = max(TRIGGERS, key=key)
    rule = {"rule_version": "token_trigger_rule_v1 (W88)", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "population": "U1 (Q's own-trajectory states); escalate iff score > per-cell threshold",
            "development_blocks": list(DEV), "validation_blocks": "every scored block != f01 (f02, f03)",
            "candidates": {"S_H0": "entropy (top-20 + tail bucket) of Q's next-token distribution at the action start",
                           "S_mm": "-(min over a_Q tokens of Q's margin lp(chosen) - max lp(other top-20))",
                           "tie_break": "every score + 1e-9 * int(sha256('token-trigger-v1|' + state_key)[:8], 16) / 16**8",
                           "S_lp": "-(mean over a_Q tokens of Q's logprob)"},
            "selection_criterion": "max mean over rates {5,10,20}% of (in-sample f01 U1 net gain - random expectation); "
                                   "tie: turnover captured - random expectation",
            "f01_in_sample_table": table, "chosen_score": best,
            "thresholds": {str(rate): thresholds(pop, best, rate) for rate in RATES},
            "thresholds_all_candidates": {s: {str(rate): thresholds(pop, s, rate) for rate in RATES} for s in TRIGGERS},
            "primary_endpoint": "validation-block U1 pooled net gain sum(Y_BQ - Y_QQ) over escalated states vs a random trigger "
                                "escalating the same number of states per cell (exact one-sided p), at each rate",
            "secondary": "rescued, damaged, turnover captured; U2B/U2Q and the non-chosen candidates are reported as secondary",
            "n_dev_units": len(pop)}
    return rule


# ----------------------------------------------------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------------------------------------------------

def strata(us: list[dict]):
    for sub in SUBS:
        for m in ("q4", "q8"):
            xs = [u for u in us if u["sub"] == sub and u["model"] == m]
            if xs:
                yield f"{sub} {m} (cells pooled)", xs
            for c in CELLS:
                ys = [u for u in xs if u["cell"] == c]
                if ys:
                    yield f"{sub} {m}_{c}", ys


def mech(us: list[dict], rng, nboot: int) -> dict:
    """First-divergence contrasts (DIAGNOSTIC: k needs both models; conditioning on differing states is a selection)."""
    out = {}
    for name, xs in strata(us):
        dif = [u for u in xs if not u["exact"] and "Htk_Q_k" in u]
        out[name] = {"n_units": len(xs), "n_unique_states": len({u["state_id"] for u in xs}), "n_differing": len(dif),
                     "n_flip": sum(u["flip"] for u in dif), "n_rescue": sum(u["r"] for u in dif), "n_damage": sum(u["d"] for u in dif),
                     "flip_vs_noflip": {m: contrast(dif, m, "flip", rng, nboot) for m in METRICS},
                     "rescue_vs_damage": {m: contrast(dif, m, "rd", rng, nboot) for m in ("Htk_Q_k", "KLu_k", "mQ_k", "Htk_Q_0", "mQ_min")}}
        out[name]["differing_vs_exact_Htk_Q_0"] = contrast([dict(u, flip=int(not u["exact"])) for u in xs], "Htk_Q_0", "flip", rng, nboot)
    return out


# ----------------------------------------------------------------------------------------------------------------------
# whole-action analysis controlled for sub-bank, cell, action length and position (GPT-6.1 review 5 point 4)
# ----------------------------------------------------------------------------------------------------------------------

def len_tercile(xs: list[dict]) -> dict:
    v = np.array([u["len_Q"] for u in xs], float)
    q1, q2 = np.quantile(v, [1 / 3, 2 / 3])
    return {id(u): int(u["len_Q"] > q1) + int(u["len_Q"] > q2) for u in xs}


def strat_contrast(xs: list[dict], val, rng, nboot: int) -> dict:
    """Flip vs no flip, stratified by cell x len_Q tercile (within one sub-bank x model). Stratified mean difference
    (weights n1 n0 / (n1 + n0)) and stratified AUC (concordance among within-stratum pairs). Task-cluster bootstrap."""
    lt = len_tercile(xs)
    items = [(f"{u['cell']}|{lt[id(u)]}", u["task"], u["flip"], val(u)) for u in xs]
    items = [x for x in items if x[3] is not None and not (isinstance(x[3], float) and math.isnan(x[3]))]

    def stat(its):
        by = collections.defaultdict(lambda: ([], []))
        for s, _, f, v in its:
            by[s][0 if f else 1].append(v)
        num = den = conc = pairs = 0.0
        n1 = n0 = 0
        for a, b in by.values():
            if a and b:
                a, b = np.array(a), np.array(b)
                w = len(a) * len(b) / (len(a) + len(b))
                num += w * (a.mean() - b.mean())
                den += w
                conc += auc(a, b) * len(a) * len(b)
                pairs += len(a) * len(b)
                n1 += len(a)
                n0 += len(b)
        if not den:
            return None
        return num / den, conc / pairs, n1, n0
    pt = stat(items)
    if pt is None:
        return {"n1": sum(1 for x in items if x[2]), "n0": sum(1 for x in items if not x[2])}
    res = {"diff": round(float(pt[0]), 4), "auc": round(float(pt[1]), 3), "n1_in_strata": pt[2], "n0_in_strata": pt[3]}
    tasks = sorted({x[1] for x in items})
    byt = collections.defaultdict(list)
    for x in items:
        byt[x[1]].append(x)
    dd, aa = [], []
    for _ in range(nboot):
        its = [x for t in rng.integers(0, len(tasks), len(tasks)) for x in byt[tasks[t]]]
        s = stat(its)
        if s:
            dd.append(s[0])
            aa.append(s[1])
    if dd:
        res["diff_ci"] = [round(float(np.percentile(dd, 2.5)), 4), round(float(np.percentile(dd, 97.5)), 4)]
        res["auc_ci"] = [round(float(np.percentile(aa, 2.5)), 3), round(float(np.percentile(aa, 97.5)), 3)]
    return res


def _bin_mean(u, b, idx):
    v = [x[idx] for x in u["_prof"] if x[0] == b and x[idx] is not None]
    return float(np.mean(v)) if v else None


def whole_action(us: list[dict], rng, nboot: int) -> dict:
    """All ordinary states (consequential = flip, vs non-consequential incl. exact-agreement states) and, separately,
    differing states only; per sub-bank x model (cells pooled, stratified by cell x length tercile); whole-action Q-visible
    statistics and position profiles (relative position bins over a_Q)."""
    out = {}
    for sub in SUBS:
        for m in ("q4", "q8"):
            for pop in ("all_states", "differing_only"):
                xs = [u for u in us if u["sub"] == sub and u["model"] == m and (pop == "all_states" or not u["exact"])]
                if not xs or not any(u["flip"] for u in xs):
                    continue
                r = {"n_units": len(xs), "n_unique_states": len({u["state_id"] for u in xs}), "n_flip": sum(u["flip"] for u in xs),
                     "whole_action": {k: strat_contrast(xs, (lambda u, k=k: u.get(k)), rng, nboot) for k in Q_VIS + B_DIAG if k != "len_Q"},
                     "position_profile": {}}
                for name, idx in (("Htk_Q", 1), ("m_Q", 2), ("KLu_BQ", 3)):
                    r["position_profile"][name] = {f"bin{b}": strat_contrast(xs, (lambda u, b=b, idx=idx: _bin_mean(u, b, idx)), rng, nboot)
                                                   for b in range(NBIN)}
                out[f"{sub} {m} | {pop}"] = r
    return out


# ----------------------------------------------------------------------------------------------------------------------
# taxonomy tables and frozen repair-candidate list
# ----------------------------------------------------------------------------------------------------------------------

def taxonomy(us: list[dict]) -> dict:
    out = {}
    for m in ("q4", "q8", "all"):
        dif = [u for u in us if not u["exact"] and "div_cls" in u and (m == "all" or u["model"] == m)]
        F = sum(u["flip"] for u in dif)
        N = len(dif)
        rows = {}
        for c in sorted({u["div_cls"] for u in dif}):
            a = sum(1 for u in dif if u["div_cls"] == c and u["flip"])
            b = sum(1 for u in dif if u["div_cls"] == c and not u["flip"])
            cc, dd = F - a, N - F - b
            rr = (a / (a + b)) / (cc / (cc + dd)) if (a + b) and (cc + dd) and cc else (float("inf") if a else 0.0)
            rows[c] = {"n": a + b, "flip": a, "flip_rate": round(a / (a + b), 3) if a + b else None,
                       "rescue": sum(1 for u in dif if u["div_cls"] == c and u["r"]), "damage": sum(1 for u in dif if u["div_cls"] == c and u["d"]),
                       "rate_ratio_vs_rest": round(rr, 2) if math.isfinite(rr) else "inf", "fisher_p_enriched": round(fisher_greater(a, b, cc, dd), 4)}
        bys = collections.Counter((u["sub"], u["div_cls"], u["flip"]) for u in dif)
        out[m] = {"n_differing": N, "n_flip": F, "classes": rows,
                  "by_sub": {s: {f"{c}|{'flip' if f else 'nf'}": n for (ss, c, f), n in bys.items() if ss == s} for s in SUBS}}
    out["flip_examples"] = [{k: u[k] for k in ("model", "cell", "sub", "block", "state_id", "G", "div_cls", "span_Q", "span_B", "Htk_Q_k", "KLu_k")}
                            for u in us if u["flip"] and "div_cls" in u]
    return out


def repair_candidates(dev: list[dict]) -> dict:
    """Frozen on f01 for a LATER local token-repair panel (not built here). Selection rule (declared before applying):
    per model, first-divergence classes among f01 differing states (all sub-banks, units cell x state) with >= 3 flips and
    flip-rate ratio vs the rest >= 1.5; if none qualifies, the 2 classes with most flips (flagged fallback). Plus a
    Q-defined span rule (no B needed): a_Q token positions whose Q margin is below the f01 per-model 10th percentile of
    per-token Q margins over U1 a_Q tokens."""
    tx = taxonomy(dev)
    out = {"version": "token_repair_candidates_v1 (W88)", "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "built_from": "f01 only", "status": "candidate list only; the repair intervention is NOT built",
           "selection_rule": repair_candidates.__doc__.split("Selection rule (declared before applying):")[1].strip(), "per_model": {}}
    for m in ("q4", "q8"):
        cl = tx[m]["classes"]
        sel = [c for c, v in cl.items() if v["flip"] >= 3 and (v["rate_ratio_vs_rest"] == "inf" or v["rate_ratio_vs_rest"] >= 1.5)]
        fb = False
        if not sel:
            sel = [c for c, _ in sorted(cl.items(), key=lambda x: (-x[1]["flip"], x[0]))[:2]]
            fb = True
        mq = [x[2] for u in dev if u["model"] == m and u["sub"] == "U1" for x in u["_prof"] if x[2] is not None]
        out["per_model"][m] = {"classes": sel, "fallback": fb, "class_table_f01": cl,
                               "q_margin_span_threshold": round(float(np.quantile(mq, 0.10)), 5) if mq else None, "n_tokens_for_threshold": len(mq)}
    return out


def fmt(c: dict) -> str:
    if "diff" not in c:
        return f"n {c.get('n1', 0)}/{c.get('n0', 0)} (too few)"
    ci = c.get("diff_ci", [float("nan")] * 2)
    aci = c.get("auc_ci", [float("nan")] * 2)
    head = f"{c['mean1']:.3g} vs {c['mean0']:.3g}; " if "mean1" in c else ""
    return f"{head}Δ {c['diff']:+.3g} [{ci[0]:+.3g}, {ci[1]:+.3g}]; AUC {c['auc']:.2f} [{aci[0]:.2f}, {aci[1]:.2f}]"


TERMS = ("Htk = truncated top-20 entropy (top-20 + one tail bucket; not the full entropy). KLu = top-20-union KL(B||Q) with one "
         "tail bucket per model (not the full KL). m = margin lp(chosen) - max lp(other top-20). lp = teacher-forced logprob of the "
         "generated token id.")


def write_md(R: dict, path: Path) -> None:
    L = [f"# Token-level analysis of Bank U action differences ({R['utc']}) — W88, exploratory", "",
         f"Script `{R['script']}` (sha256 {R['script_sha256'][:12]}). Inputs: {len(R['inputs'])} score files "
         f"(blocks {', '.join(R['blocks'])}). f01 = development; f02/f03 = validation.",
         f"Units = (cell, state); intervals = task-cluster bootstrap 95% (B = {R['boot']}); AUC = P(metric of class 1 > class 0).",
         TERMS, "Teacher forcing uses the generated token ids (recorded or regenerated on the generating server) on the identical "
         "prompt ids for B and Q.", "", "## 0. Scoring checks", ""]
    for k, v in R["checks"].items():
        L.append(f"- {k}: {v}")
    L += ["", "## 1a. Whole-action analysis (primary mechanism view): consequential vs non-consequential ordinary states", "",
          "Stratified by cell x a_Q length tercile within sub-bank x model; Δ = stratified mean difference (flip - no flip), "
          "AUC = within-stratum concordance. Q-visible: Htk_Q_0, mQ_0 (action start), Htk_Q_mean/max, mQ_min, lpQ_mean (over a_Q). "
          "B-diagnostic: KLu_*, lpB_of_aQ_mean, Htk_B_0. 'all_states' includes exact-agreement states (which cannot flip).", ""]
    for name, s in R["whole_action"].items():
        L.append(f"### {name}: units {s['n_units']} (unique states {s['n_unique_states']}), flips {s['n_flip']}")
        L.append("")
        L.append("| metric | flip vs no flip, stratified |")
        L.append("|---|---|")
        for k, c in s["whole_action"].items():
            L.append(f"| {k} | {fmt(c)} |")
        for nm, prof in s["position_profile"].items():
            L.append(f"| {nm} by relative position over a_Q | " + "; ".join(f"{b}: {c['diff']:+.3g} [{c.get('diff_ci', [float('nan')] * 2)[0]:+.3g}, "
                                                                           f"{c.get('diff_ci', [float('nan')] * 2)[1]:+.3g}]" if "diff" in c else f"{b}: n/a"
                                                                           for b, c in prof.items()) + " |")
        L.append("")
    L += ["## 1b. First-divergence analysis (DIAGNOSTIC ONLY: position k needs both models; conditioning on differing states "
          "is a selection)", "", "k = first token where the generated ids of a_B and a_Q differ; both models' distributions at k "
          "share the identical prefix. lodds_Q_k = lp_Q(a_Q[k]) - lp_Q(a_B[k]).", ""]
    for name, s in R["mech"].items():
        if "cells pooled" not in name and s["n_flip"] < 3:
            continue
        L.append(f"### {name}: units {s['n_units']} (unique states {s['n_unique_states']}), differing {s['n_differing']}, "
                 f"flips {s['n_flip']} (rescue {s['n_rescue']}, damage {s['n_damage']})")
        L.append("")
        L.append("| metric | flip vs no flip (means; Δ [CI]; AUC [CI]) |")
        L.append("|---|---|")
        for m in METRICS:
            L.append(f"| {m} | {fmt(s['flip_vs_noflip'][m])} |")
        for m, c in s["rescue_vs_damage"].items():
            L.append(f"| rescue vs damage: {m} | {fmt(c)} |")
        L.append(f"| differing vs exact: Htk_Q_0 | {fmt(s['differing_vs_exact_Htk_Q_0'])} |")
        L.append("")
    L += ["## 2. Divergence-token taxonomy (first divergent token; differing states, units cell x state; descriptive)", ""]
    for m in ("q4", "q8", "all"):
        t = R["taxonomy"][m]
        L.append(f"### {m}: differing {t['n_differing']}, flips {t['n_flip']}")
        L.append("")
        L.append("| class | n | flips | flip rate | rescue/damage | rate ratio vs rest | Fisher p (enriched) |")
        L.append("|---|---|---|---|---|---|---|")
        for c, v in sorted(t["classes"].items(), key=lambda x: -x[1]["n"]):
            L.append(f"| {c} | {v['n']} | {v['flip']} | {v['flip_rate']} | {v['rescue']}/{v['damage']} | {v['rate_ratio_vs_rest']} | {v['fisher_p_enriched']} |")
        L.append("")
    L += ["Flip examples (first divergent span, Q vs B):", ""]
    for e in R["taxonomy"]["flip_examples"][:40]:
        L.append(f"- {e['model']}_{e['cell']} {e['block']} {e['sub']} G {e['G']:+d} [{e['div_cls']}] Q `{e['span_Q']!r}` vs B `{e['span_B']!r}` "
                 f"(Htk_Q_k {e['Htk_Q_k']:.2f}, KLu_k {e['KLu_k']:.3f})")
    if R.get("repair"):
        rp = R["repair"]
        L += ["", f"Frozen repair-candidate list `{rel(REPAIR)}` sha256 `{R['repair_sha256']}` (f01 only; the repair intervention is not built):", ""]
        for m, v in rp["per_model"].items():
            L.append(f"- {m}: classes {v['classes']}{' (fallback: none met the rule)' if v['fallback'] else ''}; Q-margin span threshold "
                     f"{v['q_margin_span_threshold']} (f01 U1 per-token 10th percentile, n {v['n_tokens_for_threshold']})")
    L += ["", "## 3. Sampled-state intervention value of one-step BF16 escalation (not a token mechanism)", "",
          "At outcome-independent sampled states, G = Y_BQ - Y_QQ is the realised effect of handing this one decision to B (Q then "
          "continues). This is single-decision escalation at sampled states, not a closed-loop policy. Triggers use Q-visible "
          "whole-proposal statistics only. Random trigger = same number of escalated states per cell; p = exact one-sided "
          "P(random >= observed) (multivariate hypergeometric, convolved over cells).", ""]
    rule = R.get("rule")
    if rule:
        L.append(f"Frozen rule `{rel(RULE)}` sha256 `{R['rule_sha256']}`: chosen score **{rule['chosen_score']}** "
                 f"(created {rule['created_utc']}). Per-cell thresholds:")
        L.append("")
        for rate, th in rule["thresholds"].items():
            L.append(f"- {float(rate):.0%}: " + ", ".join(f"{k} {v:.4g}" for k, v in th.items()))
        L.append("")
        L.append("f01 U1 in-sample table (used for selection only; NOT a policy value):")
        L.append("")
        L.append("| score | rate | escalated | net gain | random exp. | rescued | damaged | turnover captured / total | random exp. turnover |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for s, v in rule["f01_in_sample_table"].items():
            for rate, x in v.items():
                L.append(f"| {s} | {float(rate):.0%} | {x['n_escalated']} | {x['net_gain']:+d} | {x['random_expected_net']:+.2f} | {x['rescued']} | "
                         f"{x['damaged']} | {x['turnover_captured']}/{x['turnover_total']} | {x['random_expected_turnover']:.2f} |")
        L.append("")
    if R.get("validation"):
        L.append("### Validation (blocks != f01, frozen thresholds)")
        L.append("")
        L.append("| population | score | rate | escalated / N | net gain | random exp. | p | rescued | damaged | turnover captured / total | random exp. | p |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for key, v in R["validation"].items():
            p = v["pooled"]
            L.append(f"| {key} | {p['n_escalated']}/{p['N']} | {p['net_gain']:+d} | {p['random_expected_net']:+.2f} | {p['p_net_ge_random']} | "
                     f"{p['rescued']} | {p['damaged']} | {p['turnover_captured']}/{p['turnover_total']} | {p['random_expected_turnover']:.2f} | {p['p_turnover_ge_random']} |")
        L.append("")
    else:
        L.append("**Validation: pending f02/f03 scoring.** Rerun this script when `analysis/fork/token_scores/*/f02|f03` land.")
        L.append("")
    path.write_text("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--freeze", action="store_true", help="choose the trigger rule and the repair-candidate list on f01; write both frozen JSONs")
    a = ap.parse_args()
    rng = np.random.default_rng(20261001)
    if a.freeze:
        for f in (RULE, REPAIR):
            if f.exists():
                raise SystemExit(f"{rel(f)} exists; frozen files are never overwritten")
        rows, inputs = load(set(DEV))  # f01 only: validation blocks are not even read
        dev = [features(r) for r in rows if "acts" in r]
        rule = freeze_rule(dev)
        rule["inputs"] = inputs
        rule["script_sha256"] = sha_file(Path(__file__))
        RULE.write_text(json.dumps(rule, indent=1) + "\n")
        rep = repair_candidates(dev)
        rep["inputs"] = inputs
        rep["script_sha256"] = sha_file(Path(__file__))
        REPAIR.write_text(json.dumps(rep, indent=1) + "\n")
        print(f"frozen {rel(RULE)} sha256 {sha_file(RULE)}; chosen {rule['chosen_score']}")
        print(f"frozen {rel(REPAIR)} sha256 {sha_file(REPAIR)}; " + "; ".join(f"{m} {v['classes']}" for m, v in rep["per_model"].items()))
        return
    rows, inputs = load()
    us = [features(r) for r in rows if "acts" in r]
    blocks = sorted({u["block"] for u in us})
    checks = {"rows": len(rows), "scored": len(us), "missing": len(rows) - len(us),
              "own_rank1_Q_on_aQ (every a_Q token is Q's argmax)": f"{sum(u['own_rank1_Q'] for u in us)}/{len(us)}",
              "identical generated ids (a_B == a_Q)": sum(u["exact"] for u in us), "differing units": sum(not u["exact"] for u in us),
              "flips": sum(u["flip"] for u in us), "flips with identical ids (should be 0)": sum(u["flip"] for u in us if u["exact"])}
    for f in sorted(glob.glob(str(SC / "*_*" / "f*" / "score_summary.json"))):
        s = json.load(open(f))
        checks[rel(Path(f).parent)] = (f"ok {s['n_ok']}/{s['n_rows']}, prompt sha ok {s['n_prompt_sha_ok']}, render ok {s['n_render_ok']}, "
                                       f"template==generated {s.get('template_eq_generated')}, regen==recorded {s.get('regen_eq_recorded')}, "
                                       f"own rank-1 B {s['n_own_rank1_B_on_aB']} Q {s['n_own_rank1_Q_on_aQ']}, "
                                       f"max |lp - decode lp| {s.get('recorded_max_abs_lp_diff_vs_decode')}")
    R = {"utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), "script": rel(Path(__file__)), "script_sha256": sha_file(Path(__file__)),
         "inputs": inputs, "blocks": blocks, "boot": a.boot, "terms": TERMS, "checks": checks}
    R["whole_action"] = whole_action(us, rng, a.boot)
    R["mech"] = mech(us, rng, a.boot)
    R["taxonomy"] = taxonomy(us)
    if REPAIR.exists():
        R["repair"], R["repair_sha256"] = json.loads(REPAIR.read_text()), sha_file(REPAIR)
    if RULE.exists():
        rule = json.loads(RULE.read_text())
        R["rule"], R["rule_sha256"] = rule, sha_file(RULE)
        val = [u for u in us if u["block"] not in DEV]
        if val:
            R["validation"] = {}
            for sub in SUBS:
                pop = [u for u in val if u["sub"] == sub]
                for s in TRIGGERS:
                    for rate in RATES:
                        th = rule["thresholds_all_candidates"][s][str(rate)]
                        tag = "PRIMARY" if (sub == "U1" and s == rule["chosen_score"]) else "secondary"
                        R["validation"][f"{sub} | {s} ({tag}) | {rate:.0%}"] = escalate(pop, s, th)
    R["units"] = [{k: v for k, v in u.items() if k != "_prof"} for u in us]
    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / f"token_mech_{R['utc']}"
    Path(str(base) + ".json").write_text(json.dumps(R, indent=1, default=str))
    write_md(R, Path(str(base) + ".md"))
    print(rel(Path(str(base) + ".md")))


if __name__ == "__main__":
    main()
