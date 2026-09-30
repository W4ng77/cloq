"""act_talk_selection: selection effect in the act/talk shift conditional on BF16's choice; unconditional and
random-perturbation-control versions; cross-check of the first-token act class against the generated action class.

Issue (docs/insights/EXTERNAL_REVIEW_GPT61_20260930.md §C last bullet; STORYLINE_v6 B5). E4-2 reports
P_cell(act | BF16 acted) and P_cell(act | BF16 talked) at BF16's decision starts (q4 RTN-W4: 0.956 -> 0.831 and
0.016 -> 0.065) and reads it as "RTN blurs the fork". Conditioning on BF16's own choice selects positions where BF16's
P(act) is near 1 or near 0, so ANY perturbation that is not exactly zero, including a sign-symmetric one with no
direction at all, moves both conditional means toward the middle (regression to the mean on a bounded scale). The
conditional pair therefore measures the SIZE of the perturbation, not a directional change of the act/talk fork.

What this script reports per E4-2 top-k cell (served-vs-served against the model's BF16 top-k cell; first-token
distribution of EVERY BF16 closed-loop decision, `first_all`; p_act bounds from openloop_topk.p_act_bounds, lower
bound used for point values as in schema 1, positions with a start token outside the top-k flagged):
  conditional       P(act | BF16 acted), P(act | BF16 talked) for the cell and for BF16 itself
  sign-symmetric    the same conditional means expected under a perturbation with the cell's own per-decision |Δlogit|
  null              but a random sign (exact average over both signs): logit_cell* = logit_BF16 +- |Δlogit|
  excess            observed conditional mean minus the sign-symmetric expectation (the part not explained by size)
  unconditional     mean ΔP(act) = mean (P_cell - P_BF16) and mean Δlogit over all decisions (directional), argmax
                    act/talk change rate vs the BF16 cell's argmax
Controls: fixed random weight perturbations with top-k cells (Gaussian k=1 seeds s1, s2, s4, s5; gshape_w4 =
Gaussian with RTN's per-group RMS; rtnsign_w4 = RTN magnitudes with random signs). These are control interventions
(size-matched random weight changes), not a "no change" null. No rotated-BF16 or eager top-k cell exists.
Cross-check (where data exist): for BF16 and for the Gaussian k=1 cells whose SAME checkpoint also ran closed loop on
the canonical prompt (a6k2_<m>_gauss1_s<k>), decisions whose prompt_sha256 equals BF16's at the same (domain, task,
decision index) give the cell's fully generated action class on the identical context; agreement with the top-k
argmax class, and mean P(act) bounds split by the generated class.
Usage:
  source scripts/a6000/env.sh; cd analysis/insights/iter_4
  python act_talk_selection.py --snapshot /data/ziyangs/cloq/analysis/insights/iter_3/out/snapshot_live_20260930T0044Z.json
-> out/act_talk_selection_<snapshot id>.json
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path("/data/ziyangs/cloq")
TOPK = ROOT / "analysis/openloop/a6k2"
CONTROL = ("gauss1_s1", "gauss1_s2", "gauss1_s4", "gauss1_s5", "gshape_w4", "rtnsign_w4")
EPS = 1e-6


def sig(x):
    return 1 / (1 + np.exp(-x))


def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def rnd(x, k=4):
    if x is None:
        return None
    if isinstance(x, (list, tuple, np.ndarray)):
        return [rnd(v, k) for v in list(x)]
    x = float(x)
    return None if not np.isfinite(x) else round(x, k)


def cell_stats(z, ref, start, OT):
    b_r = np.array([OT.p_act_bounds(i, l, start) for i, l in zip(ref["fa_top_ids"], ref["fa_top_lp"])])
    b_c = np.array([OT.p_act_bounds(i, l, start) for i, l in zip(z["fa_top_ids"], z["fa_top_lp"])])
    pr, pc = b_r[:, 0], b_c[:, 0]
    miss = b_r[:, 2].astype(bool) | b_c[:, 2].astype(bool)
    acted = ref["fa_is_tool"].astype(bool)
    L0, dl = logit(pr), logit(pc) - logit(pr)
    sym = 0.5 * (sig(L0 + np.abs(dl)) + sig(L0 - np.abs(dl)))  # expected P under a sign-symmetric perturbation
    o = dict(n=int(len(pr)), p_act_missing_frac_either=rnd(miss.mean()),
             bf16=dict(act=rnd(pr[acted].mean()), talk=rnd(pr[~acted].mean())),
             cell=dict(act=rnd(pc[acted].mean()), talk=rnd(pc[~acted].mean()),
                       act_hi=rnd(b_c[acted, 1].mean()), talk_hi=rnd(b_c[~acted, 1].mean())),
             sign_symmetric_expected=dict(act=rnd(sym[acted].mean()), talk=rnd(sym[~acted].mean())),
             excess_over_selection=dict(act=rnd(pc[acted].mean() - sym[acted].mean()), talk=rnd(pc[~acted].mean() - sym[~acted].mean())),
             unconditional=dict(dp_act_mean=rnd((pc - pr).mean()), dlogit_mean=rnd(dl.mean()), abs_dlogit_mean=rnd(np.abs(dl).mean()),
                                dp_act_mean_complete_only=rnd((pc - pr)[~miss].mean()),
                                argmax_act_change=rnd((np.isin(z["fa_top_ids"][:, 0], start) != np.isin(ref["fa_top_ids"][:, 0], start)).mean())))
    return o


def crosscheck(m, cell_run, z, start, OT, C2):
    """Generated action class of `cell_run` on contexts identical to BF16's (same prompt_sha256)."""
    bf = f"a6k2_{m}_bf16"
    if cell_run not in C2.SNAP["frozen"] or bf not in C2.SNAP["frozen"]:
        return None
    L = C2.load_many([bf, cell_run], procs=4)
    b = np.array([OT.p_act_bounds(i, l, start) for i, l in zip(z["fa_top_ids"], z["fa_top_lp"])])
    arg = np.isin(z["fa_top_ids"][:, 0], start)
    gen, idx = [], []
    for i, (d, t, k) in enumerate(zip(z["fa_domain"], z["fa_task"], z["fa_idx"])):
        key = (str(d), str(t), int(k))
        rb, rc = L[bf].get(key), L[cell_run].get(key)
        if rb is None or rc is None or rb["sha"] is None or rb["sha"] != rc["sha"]:
            continue
        gen.append(rc["kind"] == "tool"); idx.append(i)
    if not idx:
        return dict(n_identical_context=0)
    gen, idx = np.array(gen), np.array(idx)
    return dict(run=cell_run, n_identical_context=int(len(idx)), n_all=int(len(arg)),
                argmax_vs_generated_agreement=rnd((arg[idx] == gen).mean()),
                p_act_lo_given_generated_tool=rnd(b[idx][gen, 0].mean()) if gen.any() else None,
                p_act_hi_given_generated_text=rnd(b[idx][~gen, 1].mean()) if (~gen).any() else None,
                n_generated_tool=int(gen.sum()))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", required=True)
    a = ap.parse_args()
    os.environ["CLOQ_SNAPSHOT"] = str(Path(a.snapshot).resolve())
    sys.path.insert(0, str(ROOT / "scripts/a6000"))
    sys.path.insert(0, str(HERE.parent / "iter_2"))
    import common as C2  # noqa: E402
    import openloop_topk as OT  # noqa: E402
    res = dict(snapshot=dict(id=C2.SNAP["snapshot_id"], path=str(Path(a.snapshot).resolve()),
                             sha256=hashlib.sha256(open(a.snapshot, "rb").read()).hexdigest()), models={})
    for mdir in sorted(TOPK.iterdir()):
        ref_p = mdir / "topk/bf16"
        if not (ref_p.with_suffix(".npz")).exists():
            continue
        m = mdir.name
        ref = OT.load_npz(str(ref_p))
        start = [int(x) for x in json.load(open(str(ref_p) + ".json"))["tool_start_ids"]]
        out = {}
        for f in sorted((mdir / "topk").glob("*.npz")):
            cell = f.stem
            z = OT.load_npz(str(f.with_suffix("")))
            if "fa_top_ids" not in z or not all(np.array_equal(z[k], ref[k]) for k in ("fa_run", "fa_domain", "fa_task", "fa_idx")):
                continue
            o = cell_stats(z, ref, start, OT)
            o["role"] = "reference" if cell == "bf16" else ("control (fixed random weight perturbation)" if cell in CONTROL else "quantizer")
            cr = None
            if cell == "bf16":
                cr = dict(argmax_vs_generated_agreement=rnd((np.isin(z["fa_top_ids"][:, 0], start) == z["fa_is_tool"].astype(bool)).mean()),
                          first_token_class_vs_generated=rnd((np.isin(z["fa_first_tok"], start) == z["fa_is_tool"].astype(bool)).mean()),
                          n_identical_context=int(len(z["fa_is_tool"])), run=f"a6k2_{m}_bf16")
            elif cell.startswith("gauss1_s"):
                cr = crosscheck(m, f"a6k2_{m}_{cell}", z, start, OT, C2)
            o["generated_class_crosscheck"] = cr
            out[cell] = o
        res["models"][m] = out
        for cell, o in out.items():
            print(m, cell.ljust(12), o["role"][:9], "cond act/talk", o["cell"]["act"], o["cell"]["talk"], "| sym-exp", o["sign_symmetric_expected"]["act"],
                  o["sign_symmetric_expected"]["talk"], "| excess", o["excess_over_selection"], "| uncond dP", o["unconditional"]["dp_act_mean"],
                  "dlogit", o["unconditional"]["dlogit_mean"], "| xchk", (o["generated_class_crosscheck"] or {}).get("argmax_vs_generated_agreement"),
                  (o["generated_class_crosscheck"] or {}).get("n_identical_context"))
    p = HERE / "out" / f"act_talk_selection_{C2.SNAP['snapshot_id']}.json"
    json.dump(res, open(p, "w"), indent=1)
    print("wrote", p)


if __name__ == "__main__":
    main()
