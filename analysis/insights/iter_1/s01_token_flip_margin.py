"""Pilot test of the first-order margin model on identical-context decisions (A6000, live snapshot).

For a perturbed run P and its BF16 reference B (same model), every decision whose *context* is identical
in both runs (same prompt_sha256 for weight perturbations; same conversation excluding the system prompt
for nonce runs) is a clean open-loop comparison embedded in the closed loop: these are the shared
prefix of the two trajectories, up to and including the first divergent decision.

Along the BF16 completion we walk token by token while P emits the same token:
  * each shared token contributes a margin shift  d = m_P - m_B  (top-1 minus top-2 logprob; same top-1);
  * the first differing token is a flip event at BF16 margin m_B.
First-order margin model: a token flips iff the perturbation lowers its margin by more than m_B,
so the per-token hazard is h(m) = P(D < -m), D = the shift distribution. We (i) report the empirical
hazard by BF16-margin bin, (ii) the shift scale |D| per perturbation, and (iii) predict, per decision,
P(decision diverges) = 1 - prod_i (1 - h(m_i)) with D estimated on the *other* domain (cross-fit),
and compare with the observed divergence rate and AUC.

Usage: python s01_token_flip_margin.py [model]   (default q4)
"""
import re
import sys
from collections import defaultdict

import numpy as np

from common import a6000_runs, dump, load_both

MODEL = sys.argv[1] if len(sys.argv) > 1 else "q4"
REF = f"a6000_{MODEL}_bf16"
BINS = [0, 0.25, 0.5, 1, 2, 4, 8, 1e9]


def pair_stats(ref, pert, nonce):
    key = "ctx_key" if nonce else "prompt_sha"
    shifts = {"retail": [], "airline": []}
    at_risk = []  # (domain, bf16 margin, flipped?) per token at risk
    decisions = []  # (domain, [bf16 margins], diverged?, kind)
    for k, b in ref.items():
        p = pert.get(k)
        if p is None or b[key] != p[key] or not b["ids"] or not p["ids"]:
            continue
        dom = k[0]
        a, c = b["ids"], p["ids"]
        mb, mp = b["margins"], p["margins"]
        n = min(len(a), len(c))
        j = next((i for i in range(n) if a[i] != c[i]), n)
        diverged = j < n or len(a) != len(c)
        for i in range(min(j, len(mb), len(mp))):
            if mb[i] is not None and mp[i] is not None:
                shifts[dom].append(mp[i] - mb[i])
                at_risk.append((dom, mb[i], 0))
        if j < n and j < len(mb) and mb[j] is not None:
            at_risk.append((dom, mb[j], 1))
        decisions.append((dom, [m for m in mb if m is not None], diverged, b["kind"]))
    return shifts, at_risk, decisions


def hazard_fn(shift):
    s = np.sort(np.asarray(shift))
    if len(s) == 0:
        return lambda m: np.full_like(np.asarray(m, float), np.nan)
    # P(D < -m), with a floor of 0.5/n so zero-margin ties are not predicted impossible
    return lambda m: np.maximum(np.searchsorted(s, -np.asarray(m, float), side="left") / len(s), 0.5 / len(s))


def auc(scores, labels):
    scores, labels = np.asarray(scores), np.asarray(labels)
    pos, neg = scores[labels == 1], scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    r = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    return float((r[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main():
    bf16 = load_both(REF)
    res = {"model": MODEL, "reference": REF, "n_ref_decisions": len(bf16), "configs": {}}
    runs = a6000_runs(f"a6000_{MODEL}_")
    dets = [r for r in a6000_runs(f"a6000_det_{MODEL}_")]  # BF16 re-runs on other nodes: numerical floor
    for run in dets + runs:
        if run == REF or run.endswith("_cal"):
            continue
        pert = load_both(run)
        m = re.search(r"_n(\d+)$", run)
        if run in dets:
            ref, nonce, refname = bf16, False, REF + " (BF16 vs BF16 re-run, different node)"
        elif "_null_" in run:
            ref, nonce, refname = bf16, True, REF          # nonce vs BF16: prompt perturbation only
        elif m and f"a6000_{MODEL}_null_n{m.group(1)}" in runs:
            refname = f"a6000_{MODEL}_null_n{m.group(1)}"  # same nonce, BF16 weights: isolates the weight change
            ref, nonce = load_both(refname), False
        elif m:
            ref, nonce, refname = bf16, True, REF + " (composite: nonce + weights)"
        else:
            ref, nonce, refname = bf16, False, REF
        shifts, at_risk, decs = pair_stats(ref, pert, nonce)
        if not decs:
            continue
        allshift = np.array(shifts["retail"] + shifts["airline"])
        # empirical hazard by BF16 margin bin
        haz = []
        ar = np.array([(m, f) for _, m, f in at_risk]) if at_risk else np.zeros((0, 2))
        for lo, hi in zip(BINS[:-1], BINS[1:]):
            sel = (ar[:, 0] >= lo) & (ar[:, 0] < hi) if len(ar) else np.array([], bool)
            n = int(sel.sum())
            haz.append({"bin": f"[{lo},{hi})", "n_tokens": n, "flips": int(ar[sel, 1].sum()) if n else 0,
                        "hazard": float(ar[sel, 1].mean()) if n else None})
        # cross-fit prediction of decision-level divergence
        preds, obs, kinds = [], [], []
        for dom, ms, dv, kind in decs:
            other = "airline" if dom == "retail" else "retail"
            h = hazard_fn(shifts[other] if len(shifts[other]) >= 200 else shifts[dom])
            p = 1 - np.prod(1 - h(np.array(ms))) if ms else 0.0
            preds.append(float(p)); obs.append(int(dv)); kinds.append(kind)
        preds, obs, kinds = np.array(preds), np.array(obs), np.array(kinds)
        by_kind = {}
        for kd in ("text", "tool"):
            s = kinds == kd
            if s.any():
                by_kind[kd] = {"n": int(s.sum()), "observed_div": float(obs[s].mean()), "predicted_div": float(preds[s].mean())}
        res["configs"][run] = {
            "pairing": "ctx_excl_system" if nonce else "prompt_sha",
            "reference": refname,
            "n_identical_context_decisions": int(len(decs)),
            "n_shared_tokens": int(len(allshift)),
            "shift_abs_median": float(np.median(np.abs(allshift))) if len(allshift) else None,
            "shift_abs_p90": float(np.quantile(np.abs(allshift), 0.9)) if len(allshift) else None,
            "shift_sd": float(allshift.std()) if len(allshift) else None,
            "hazard_by_bf16_margin": haz,
            "decision_divergence_observed": float(obs.mean()),
            "decision_divergence_predicted_crossfit": float(preds.mean()),
            "decision_auc_pred_vs_obs": auc(preds, obs),
            "decision_auc_minmargin_only": auc([-min(ms) if ms else 0 for _, ms, _, _ in decs], obs),
            "by_bf16_kind": by_kind,
        }
        c = res["configs"][run]
        print(f"{run:28s} ctx={c['n_identical_context_decisions']:4d} tok={c['n_shared_tokens']:6d} "
              f"|d|med={c['shift_abs_median']} p90={c['shift_abs_p90']} obs={c['decision_divergence_observed']:.3f} "
              f"pred={c['decision_divergence_predicted_crossfit']:.3f} AUC={c['decision_auc_pred_vs_obs']} kinds={by_kind}")
        print("    hazard:", [(h["bin"], h["n_tokens"], None if h["hazard"] is None else round(h["hazard"], 4)) for h in haz])
    dump(f"s01_token_flip_margin_{MODEL}.json", res)


if __name__ == "__main__":
    main()
