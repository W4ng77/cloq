"""Build v1 calibration buffers: one state per calibration task, exact activation-row budget.

v0 matched raw input tokens, which bought only 10-13 contexts because one agent context is
5-8k tokens. v1 instead fixes the number of *independent agent states* (one per calibration
task) and the number of *GPTQ activation rows* (64,000), by sampling a fixed quota of token
positions inside each context and reusing those positions at every quantized layer.

Arms (plan section 5):
  static      initial decision state x0 of every calibration task; identical across draws, so only
              the row subsample varies
  fp_traj     one BF16 trajectory state per task, globally depth-balanced at 25% per quartile
  cloq_all    tasks split evenly into an FP half and a Q half (stratified by domain and BF16
              horizon quartile); FP half gives BF16 states, Q half gives uniformly depth-sampled
              Q0 states
  cloq_novel  same draw, same split, same FP-half states as cloq_all; each Q-half task gives its
              highest-novelty post-divergence Q0 state

usage:
  python -m cloq.calib_v1 --arm static   --draw c1 --out manifests/v1/calib_static_c1.json
  python -m cloq.calib_v1 --arm fp_traj  --draw c1 --out manifests/v1/calib_fp_traj_c1.json
  python -m cloq.calib_v1 --arm cloq_all --draw c1 --q-run q0_v1_c1 \
      --novelty manifests/v1/novelty_c1.json --out manifests/v1/calib_cloq_all_c1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from cloq import config as C
from cloq.calib import load_states

V1 = json.load(open(C.PROJECT_ROOT / "configs" / "frozen_v1.json"))
DRAWS = V1["calibration"]["draws"]
BUDGET_ROWS = int(V1["calibration"]["budget_rows"])


def _task_key(s: dict):
    tid = s["task_id"]
    return (s["domain"], int(tid) if str(tid).isdigit() else 10**9, str(tid))


# ---------------------------------------------------------------------------
# activation-row budget
# ---------------------------------------------------------------------------


def allocate_rows(contexts: list[dict], budget: int = BUDGET_ROWS) -> list[int]:
    """Split `budget` rows over the contexts, honouring each context's available positions.

    Base quota is budget // n, and the first (budget mod n) contexts in ascending
    (domain, task_id) order get one extra row. A context that cannot supply its quota gives
    everything it has and the shortfall is redistributed, in the same deterministic order, to
    contexts that still have spare positions. Rows are never duplicated.
    """
    n = len(contexts)
    assert n > 0, "no contexts"
    order = sorted(range(n), key=lambda i: _task_key(contexts[i]))
    base, extra = divmod(budget, n)
    quota = [base] * n
    for k in order[:extra]:
        quota[k] += 1
    avail = [len(c["prompt_token_ids"]) for c in contexts]
    # clip to what each context actually has, then redistribute the shortfall
    deficit = 0
    for i in range(n):
        if quota[i] > avail[i]:
            deficit += quota[i] - avail[i]
            quota[i] = avail[i]
    while deficit > 0:
        room = [i for i in order if avail[i] > quota[i]]
        if not room:
            raise ValueError(f"calibration contexts cannot supply {budget} rows (short by {deficit})")
        for i in room:
            if deficit == 0:
                break
            take = min(deficit, avail[i] - quota[i])
            quota[i] += take
            deficit -= take
    assert sum(quota) == budget, (sum(quota), budget)
    return quota


def sample_rows(contexts: list[dict], quota: list[int], seed: int) -> list[list[int]]:
    """Uniform sample without replacement of token positions, one draw per context."""
    rows = []
    order = sorted(range(len(contexts)), key=lambda i: _task_key(contexts[i]))
    rank = {i: r for r, i in enumerate(order)}
    for i, c in enumerate(contexts):
        L = len(c["prompt_token_ids"])
        rng = np.random.default_rng([seed, rank[i]])
        idx = rng.choice(L, size=quota[i], replace=False)
        rows.append(sorted(int(x) for x in idx))
    return rows


# ---------------------------------------------------------------------------
# state selection
# ---------------------------------------------------------------------------


def by_task(states: list[dict]) -> dict[tuple, list[dict]]:
    d = defaultdict(list)
    for s in states:
        d[(s["domain"], s["task_id"])].append(s)
    for v in d.values():
        v.sort(key=lambda s: s["decision_idx"])
    return d


def select_one_per_task_depth_balanced(states: list[dict], rng: np.random.Generator) -> list[dict]:
    """One state per task, with the global depth-quartile histogram as flat as possible.

    Tasks are shuffled, then assigned target quartiles round-robin so the counts differ by at
    most one. A task with no decision in its target quartile falls back to the nearest quartile
    it does have, which is recorded on the chosen state.
    """
    tasks = by_task(states)
    keys = sorted(tasks, key=lambda k: (k[0], int(k[1]) if str(k[1]).isdigit() else 10**9, str(k[1])))
    order = list(keys)
    rng.shuffle(order)
    chosen = []
    for rank, k in enumerate(order):
        target = rank % 4
        pool = [s for s in tasks[k] if s["depth_quartile"] == target]
        fallback = None
        if not pool:
            avail = sorted({s["depth_quartile"] for s in tasks[k]}, key=lambda q: (abs(q - target), q))
            fallback = avail[0]
            pool = [s for s in tasks[k] if s["depth_quartile"] == fallback]
        s = dict(pool[int(rng.integers(len(pool)))])
        s["target_quartile"] = target
        s["quartile_fallback"] = fallback
        chosen.append(s)
    return sorted(chosen, key=_task_key)


def select_initial_states(states: list[dict]) -> list[dict]:
    tasks = by_task(states)
    out = []
    for k in sorted(tasks, key=lambda k: (k[0], int(k[1]) if str(k[1]).isdigit() else 10**9, str(k[1]))):
        first = tasks[k][0]
        assert first["decision_idx"] == 0, f"missing decision 0 for {k}"
        out.append(dict(first))
    return sorted(out, key=_task_key)


def split_fp_q_tasks(fp_states: list[dict], split: dict, rng: np.random.Generator) -> tuple[set, set]:
    """Halve the calibration tasks, stratified by domain and BF16 horizon quartile."""
    tasks = sorted(by_task(fp_states), key=lambda k: (k[0], int(k[1]) if str(k[1]).isdigit() else 10**9, str(k[1])))
    strata = defaultdict(list)
    for dom, tid in tasks:
        q = split["domains"][dom]["quartile_by_task"].get(tid)
        strata[(dom, q)].append((dom, tid))
    fp_half, q_half = set(), set()
    flip = 0  # alternate which half gets the odd task, so the halves stay balanced overall
    for key in sorted(strata, key=lambda k: (k[0], -1 if k[1] is None else k[1])):
        items = list(strata[key])
        rng.shuffle(items)
        half = len(items) // 2
        if len(items) % 2:
            half += flip
            flip ^= 1
        fp_half.update(items[:half])
        q_half.update(items[half:])
    return fp_half, q_half


def select_q_uniform_depth(q_states: list[dict], q_half: set, rng: np.random.Generator) -> list[dict]:
    """One Q0 state per Q-half task, uniform over normalized depth."""
    tasks = by_task(q_states)
    out = []
    for k in sorted(q_half, key=lambda k: (k[0], int(k[1]) if str(k[1]).isdigit() else 10**9, str(k[1]))):
        pool = tasks.get(k)
        if not pool:
            continue
        s = dict(pool[int(rng.integers(len(pool)))])
        s["q_selection"] = "uniform_depth"
        out.append(s)
    return sorted(out, key=_task_key)


def select_q_novel(q_states: list[dict], q_half: set, novelty: dict, rng: np.random.Generator) -> list[dict]:
    """Per Q-half task, the highest-novelty post-divergence Q0 state.

    Falls back to the highest-novelty state of the whole trajectory when the task never diverged.
    Ties break on the earlier decision index, then on the draw's RNG order.
    """
    tasks = by_task(q_states)
    nov = novelty["per_state"]
    out = []
    for k in sorted(q_half, key=lambda k: (k[0], int(k[1]) if str(k[1]).isdigit() else 10**9, str(k[1]))):
        pool = tasks.get(k)
        if not pool:
            continue
        scored = []
        for s in pool:
            key = f"{s['domain']}|{s['task_id']}|{s['decision_idx']}"
            e = nov.get(key)
            if e is None:
                continue
            scored.append((s, e["novelty"], bool(e["post_divergence"])))
        if not scored:
            continue
        post = [x for x in scored if x[2]]
        candidates = post if post else scored
        best = max(candidates, key=lambda x: (x[1], -x[0]["decision_idx"]))
        s = dict(best[0])
        s["q_selection"] = "novel_post_divergence" if post else "novel_any"
        s["novelty"] = best[1]
        s["post_divergence"] = best[2]
        out.append(s)
    return sorted(out, key=_task_key)


def select_q_matched_random(q_states: list[dict], q_half: set, novelty: dict,
                            novel_contexts: list[dict], rng: np.random.Generator,
                            exclude_novel_pick: bool = False) -> list[dict]:
    """Amendment 1: per Q-half task, a RANDOM state matched to CLOQ-Novel's nuisance axes.

    CLOQ-Novel changes novelty and trajectory depth together, so a CLOQ-Novel win is
    confounded with simply calibrating on later, deeper, more truncated contexts. This arm
    holds depth quartile, truncation status and post-divergence status at CLOQ-Novel's values
    and randomises only which state inside that stratum is taken, so that

        CLOQ-Novel - CLOQ-MatchedRandom

    isolates the novelty score itself.

    Candidates come from the same universe CLOQ-Novel drew from: states of the task that carry
    a stored novelty entry. Tiers are tried in order and the first non-empty one is sampled
    uniformly; CLOQ-Novel's own pick is deliberately left in the pool (see the amendment).
    """
    tasks = by_task(q_states)
    nov = novelty["per_state"]
    target = {(c["domain"], c["task_id"]): c for c in novel_contexts if c.get("q_selection", "").startswith("novel")}
    out = []
    for k in sorted(q_half, key=lambda k: (k[0], int(k[1]) if str(k[1]).isdigit() else 10**9, str(k[1]))):
        pool = tasks.get(k)
        tgt = target.get(k)
        if not pool or tgt is None:
            continue
        # same universe as CLOQ-Novel: states with a stored representation / novelty entry
        cands = []
        for st in pool:
            e = nov.get(f"{st['domain']}|{st['task_id']}|{st['decision_idx']}")
            if e is None:
                continue
            st = dict(st)
            st["novelty"] = float(e["novelty"])
            st["post_divergence"] = bool(e["post_divergence"])
            cands.append(st)
        if not cands:
            continue
        q = int(tgt["depth_quartile"])
        t = bool(tgt.get("truncated", False))
        p = bool(tgt.get("post_divergence", False))

        def nearest(pool_):
            if not pool_:
                return []
            dmin = min(abs(x["depth_quartile"] - q) for x in pool_)
            best = [x for x in pool_ if abs(x["depth_quartile"] - q) == dmin]
            # ties on distance break toward the lower quartile
            qmin = min(x["depth_quartile"] for x in best)
            return [x for x in best if x["depth_quartile"] == qmin]

        post = [x for x in cands if x["post_divergence"] == p]
        tiers = [
            [x for x in post if x["depth_quartile"] == q and bool(x["truncated"]) == t],
            [x for x in post if x["depth_quartile"] == q],
            nearest(post),
            [x for x in cands if x["depth_quartile"] == q],
            nearest(cands),
        ]
        if exclude_novel_pick:
            # Amendment 1a: descend to the first tier that offers a state other than
            # CLOQ-Novel's own, and draw from that tier with CLOQ-Novel's state removed.
            ti = int(tgt["decision_idx"])
            alt = [(i + 1, [x for x in tp if x["decision_idx"] != ti]) for i, tp in enumerate(tiers)]
            hit = next(((i, tp) for i, tp in alt if tp), None)
            if hit is None:
                # the task offers no alternative anywhere; keep CLOQ-Novel's state
                tier_idx, chosen_pool = next((i + 1, tp) for i, tp in enumerate(tiers) if tp)
            else:
                tier_idx, chosen_pool = hit
        else:
            tier_idx, chosen_pool = next((i + 1, tp) for i, tp in enumerate(tiers) if tp)
        st = dict(chosen_pool[int(rng.integers(len(chosen_pool)))])
        st["q_selection"] = "matched_alt" if exclude_novel_pick else "matched_random"
        st["matched_tier"] = tier_idx
        st["matched_pool_size"] = len(chosen_pool)
        st["identical_to_novel"] = bool(st["decision_idx"] == int(tgt["decision_idx"]))
        st["novel_novelty"] = float(tgt.get("novelty")) if tgt.get("novelty") is not None else None
        out.append(st)
    return sorted(out, key=_task_key)


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------

CTX_FIELDS = ["source", "run_id", "domain", "task_id", "trajectory_id", "decision_idx", "n_decisions",
              "depth", "depth_quartile", "n_tokens", "prompt_sha256", "prompt_token_ids",
              "parser_error", "finish_reason", "target_quartile", "quartile_fallback",
              "q_selection", "novelty", "post_divergence", "truncated",
              "matched_tier", "matched_pool_size", "identical_to_novel", "novel_novelty"]


def build(arm: str, draw: str, split: dict, fp_run: str, q_run: str | None, novelty_path: Path | None,
          novel_calib: Path | None = None) -> dict:
    seed = int(DRAWS[draw])
    rng = np.random.default_rng(seed)
    domains = list(split["domains"].keys())
    cal_ids = {d: split["domains"][d]["calibration"] for d in domains}
    eval_ids = {d: set(split["domains"][d]["evaluation"]) for d in domains}
    fp_states = load_states(fp_run, domains, cal_ids, "fp")
    notes = []

    if arm == "static":
        chosen = select_initial_states(fp_states)
        notes.append("initial states are draw-independent; only the activation-row subsample varies")
    elif arm == "fp_traj":
        chosen = select_one_per_task_depth_balanced(fp_states, rng)
    elif arm in ("cloq_all", "cloq_novel", "cloq_matched_random", "cloq_matched_alt"):
        assert q_run, "--q-run required"
        q_states = load_states(q_run, domains, cal_ids, "q0")
        # The split RNG is consumed before any arm-specific randomness so that cloq_all and
        # cloq_novel of the same draw see exactly the same halves and the same FP-half states.
        split_rng = np.random.default_rng([seed, 0xC10])
        fp_half, q_half = split_fp_q_tasks(fp_states, split, split_rng)
        fp_pool = [s for s in fp_states if (s["domain"], s["task_id"]) in fp_half]
        fp_part = select_one_per_task_depth_balanced(fp_pool, np.random.default_rng([seed, 0xF9]))
        if arm == "cloq_all":
            q_part = select_q_uniform_depth(q_states, q_half, np.random.default_rng([seed, 0xA11]))
        elif arm == "cloq_novel":
            assert novelty_path, "--novelty required for cloq_novel"
            nov = json.load(open(novelty_path))
            assert nov["draw"] == draw, f"novelty manifest is for draw {nov['draw']}, not {draw}"
            q_part = select_q_novel(q_states, q_half, nov, np.random.default_rng([seed, 0xA12]))
        else:
            # Amendment 1: depth/truncation-matched random control for CLOQ-Novel.
            assert novelty_path, f"--novelty required for {arm}"
            assert novel_calib, f"--novel-calib required for {arm}"
            nov = json.load(open(novelty_path))
            assert nov["draw"] == draw, f"novelty manifest is for draw {nov['draw']}, not {draw}"
            novel_man = json.load(open(novel_calib))
            assert novel_man["arm"] == "cloq_novel" and novel_man["draw"] == draw, \
                f"{novel_calib} is not the cloq_novel manifest for draw {draw}"
            # the FP half must be bit-identical to CLOQ-Novel's
            novel_fp = sorted((c["domain"], c["task_id"], c["decision_idx"])
                              for c in novel_man["contexts"] if c["source"] != "q0")
            mine_fp = sorted((c["domain"], c["task_id"], c["decision_idx"]) for c in fp_part)
            assert novel_fp == mine_fp, "FP half differs from CLOQ-Novel; the control would be invalid"
            excl = arm == "cloq_matched_alt"
            q_part = select_q_matched_random(
                q_states, q_half, nov, novel_man["contexts"],
                np.random.default_rng([seed, 0xA14 if excl else 0xA13]), exclude_novel_pick=excl)
            notes.append("Amendment 1 control: Q half matched to cloq_novel on depth quartile, "
                         "truncation and post-divergence, randomised within the stratum"
                         + (" (Amendment 1a: cloq_novel's own state excluded)" if excl else ""))
        chosen = sorted(fp_part + q_part, key=_task_key)
        notes.append(f"FP half {len(fp_half)} tasks, Q half {len(q_half)} tasks; "
                     f"{len(fp_part)} FP states + {len(q_part)} Q states")
    else:
        raise ValueError(arm)

    # one state per task
    seen = defaultdict(int)
    for s in chosen:
        seen[(s["domain"], s["task_id"])] += 1
    dup = {k: v for k, v in seen.items() if v > 1}
    assert not dup, f"more than one state for {dup}"
    # no leakage
    for s in chosen:
        assert s["task_id"] not in eval_ids[s["domain"]], f"dev task {s['domain']}/{s['task_id']} leaked"

    quota = allocate_rows(chosen)
    rows = sample_rows(chosen, quota, seed)
    lens = [len(s["prompt_token_ids"]) for s in chosen]
    contexts = []
    for s, q, ix in zip(chosen, quota, rows):
        c = {k: s[k] for k in CTX_FIELDS if k in s}
        c["n_rows"] = q
        c["row_idx"] = ix
        contexts.append(c)
    man = {
        "protocol": "v1", "arm": arm, "draw": draw, "draw_seed": seed,
        "budget_rows": BUDGET_ROWS, "total_rows": int(sum(quota)),
        "rows_within_budget": int(sum(quota)) == BUDGET_ROWS,
        "n_states": len(chosen), "n_tasks": len(seen),
        "rows_per_state_min": int(min(quota)), "rows_per_state_max": int(max(quota)),
        "median_context_tokens": float(np.median(lens)), "total_context_tokens": int(sum(lens)),
        "states_by_source": {src: sum(1 for s in chosen if s["source"] == src) for src in {s["source"] for s in chosen}},
        "states_by_depth_quartile": {q: sum(1 for s in chosen if s["depth_quartile"] == q) for q in range(4)},
        "states_by_domain": {d: sum(1 for s in chosen if s["domain"] == d) for d in domains},
        "fp_run": fp_run, "q_run": q_run, "novelty": str(novelty_path) if novelty_path else None,
        "notes": notes, "contexts": contexts,
    }
    if arm in ("cloq_matched_random", "cloq_matched_alt"):
        qsel = [c for c in contexts if c.get("q_selection") in ("matched_random", "matched_alt")]
        nvl = [c["novelty"] for c in qsel if c.get("novelty") is not None]
        tgt = [c["novel_novelty"] for c in qsel if c.get("novel_novelty") is not None]
        man["match_audit"] = {
            "n_q_states": len(qsel),
            "n_identical_to_novel": int(sum(bool(c.get("identical_to_novel")) for c in qsel)),
            "tier_histogram": {t: sum(1 for c in qsel if c.get("matched_tier") == t) for t in range(1, 6)},
            "median_pool_size": float(np.median([c["matched_pool_size"] for c in qsel])) if qsel else None,
            "mean_novelty_matched": float(np.mean(nvl)) if nvl else None,
            "mean_novelty_novel": float(np.mean(tgt)) if tgt else None,
            "novelty_separation": float(np.mean(tgt) - np.mean(nvl)) if nvl and tgt else None,
            "q_truncated_share": float(np.mean([bool(c.get("truncated")) for c in qsel])) if qsel else None,
        }
        man["novel_calib"] = str(novel_calib)
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True,
                    choices=["static", "fp_traj", "cloq_all", "cloq_novel",
                             "cloq_matched_random", "cloq_matched_alt"])
    ap.add_argument("--draw", required=True, choices=sorted(DRAWS))
    ap.add_argument("--split", default=str(C.MANIFEST_DIR / "task_split_v0.json"))
    ap.add_argument("--fp-run", default="bf16")
    ap.add_argument("--q-run", default=None)
    ap.add_argument("--novelty", default=None)
    ap.add_argument("--novel-calib", default=None, help="frozen cloq_novel manifest (cloq_matched_random)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists (frozen); refusing to overwrite")
    split = json.load(open(a.split))
    man = build(a.arm, a.draw, split, a.fp_run, a.q_run, Path(a.novelty) if a.novelty else None,
                Path(a.novel_calib) if a.novel_calib else None)
    man["split_file_sha256"] = hashlib.sha256(open(a.split, "rb").read()).hexdigest()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(man))
    # separate immutable row manifest (plan section 18)
    rowman = {
        "arm": a.arm, "draw": a.draw, "draw_seed": man["draw_seed"], "total_rows": man["total_rows"],
        "rows": [{"domain": c["domain"], "task_id": c["task_id"], "decision_idx": c["decision_idx"],
                  "prompt_sha256": c["prompt_sha256"], "n_tokens": c["n_tokens"], "n_rows": c["n_rows"],
                  "row_idx": c["row_idx"]} for c in man["contexts"]],
    }
    (out.parent / f"row_manifest_{a.arm}_{a.draw}.json").write_text(json.dumps(rowman))
    print(json.dumps({k: v for k, v in man.items() if k != "contexts"}, indent=2))
    if not man["rows_within_budget"]:
        raise SystemExit("activation-row budget not met")


if __name__ == "__main__":
    main()
