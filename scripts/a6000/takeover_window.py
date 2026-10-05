"""Takeover-window panel, fork_driver mode `takeover_window` (docs/insights/TAKEOVER_WINDOW_PROTOCOL.md, tw-v1).

At each frozen Bank U U2B state of one (cell, block), with the current actions recorded in the endpoint block (a_B = the
BF16 source action, a_Q = the cell's shadow action; never regenerated), run the suffix policy pi_L for every source x in
spec sources and L in spec windows: force a_x, BF16 (B) generates the next L complete decisions, then Q generates every
later one (cloq/fork.py ForkAgent handback). L = 0 / inf are the existing endpoint arms xQ / xB; on a hash sample (spec
repro: "all" or a fraction) they are re-run through the same code (L = 0 with handback (0, Q)) and compared with the
endpoint records. The endpoint block (src_out, optional A7 rr_out) is only read.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cloq import fork as F

INF = "inf"
WORK = Path("/data/ziyangs/cloq_work")
SEALED = ("Y", "termination", "official_reward", "db_match")  # window outcomes, not written by a gate task (protocol §5)


def endpoint_arm(x: str, L) -> str:
    return x + ("Q" if L == 0 else "B")


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def window_view(r: dict, L: int, bases: dict) -> dict:
    """Decision accounting of one window suffix: counters from the agent itself, cross-checked with the server that
    answered each logged request (api_base). A decision = one assistant message; the forced action is not counted."""
    ds, w = r.get("decisions") or [], r.get("window") or {}
    cont = [d for d in ds if not d.get("forced")]
    n_cont = w.get("n_cont")
    got = [d.get("api_base") for d in cont]
    v = {"n_cont": n_cont, "n_B": None if n_cont is None else min(n_cont, L), "n_Q": None if n_cont is None else max(n_cont - L, 0),
         "handed_back": None if n_cont is None else n_cont > L, "switch_decision_idx": w.get("switch_decision_idx"),
         "attempted_handback": w.get("switch_decision_idx") is not None}
    # amendment 1 item 2: an overflow raised by Q's first request is a valid failure, reported as its own category
    ovf, att = r.get("infra_cause") == "context_overflow", v["attempted_handback"]
    v["overflow"] = None if not ovf else "attempted_handback_generation_failed" if att and n_cont == L else \
        "overflow_after_handback" if att else "overflow_before_handback"
    if "error" in r or not ds:
        return {**v, "pattern_ok": None, "counter_ok": None}
    want = [bases["B"] if i < L else bases["Q"] for i in range(len(cont))]
    sw = ds[0]["decision_idx"] + 1 + L if n_cont is not None and n_cont > L else None
    # an overflow raised by Q's first request (after the switch) or by the simulator before it: either is valid at n_cont == L
    sw_ok = {sw} | ({None, ds[0]["decision_idx"] + 1 + L} if r.get("infra_cause") == "context_overflow" and n_cont == L else set())
    v["pattern_ok"] = (got == want) if all(got) else None  # context-overflow records carry no api_base
    v["counter_ok"] = (n_cont == len(cont) and w.get("L") == L and v["switch_decision_idx"] in sw_ok
                       and sum(1 for d in ds if d.get("forced")) == 1 and bool(ds[0].get("forced")))
    return v


def prefix_check(r: dict, ref: dict | None, L: int) -> dict:
    """Window run vs the L = inf reference of the same current action (identical up to the switch): request prompt ids
    of decisions 0..L+1 (L+1 = Q's first, re-prefilled request), completion ids of generated decisions 1..L; a run that
    ended inside the window must equal the reference suffix as a whole."""
    if ref is None or "error" in r:
        return {"ok": None, "why": "no reference" if ref is None else "run error"}
    ds, rd = r.get("decisions") or [], ref["decisions"]
    bad = []
    for i in range(min(len(ds), L + 2)):
        if i >= len(rd) or ds[i]["prompt_ids_sha"] != rd[i][0]:
            bad.append(f"prompt{i}")
        elif 1 <= i <= L and ds[i].get("completion_ids_sha") != rd[i][1]:
            bad.append(f"completion{i}")
    inside, ovf = len(ds) <= L + 1, r.get("infra_cause") == "context_overflow"
    if inside and not ovf and r.get("suffix_sha") != ref["suffix_sha"]:
        bad.append("ended_in_window_suffix_differs")
    if ovf and (r.get("window") or {}).get("switch_decision_idx") is None and len(rd) > len(ds):  # overflow at a B request
        bad.append("overflow_in_window_not_in_reference")  # (Q's first request overflowing is amendment 1's valid failure)
    return {"ok": not bad, "bad": bad, "ref": ref["kind"], "ended_in_window": inside}


def quarantine(pc: dict, x: str, L: int) -> dict | None:
    """Amendment 1 item 4 (panel): a prefix mismatch before the switch breaks duration attribution. The suffix is kept on
    disk but excluded from the main analysis: Y_{x,L} in Delta_L, V_{x,L}, R_{x,L}, and the state from the x duration curve
    at every L (fixed composition). Diagnosis = the first mismatching item."""
    if pc.get("ok") is not False:
        return None
    b = pc["bad"][0]
    kind = ("state_rebuild" if b == "prompt0" else "bf16_generation_nondeterminism" if b.startswith("completion")
            else "reprefill_at_switch" if b == f"prompt{L + 1}" else "observation_or_simulator" if b.startswith("prompt") else b)
    return {"reason": "prefix_mismatch_before_switch", "first_bad": b, "diagnosis": kind, "bad": pc["bad"],
            "excluded": [f"Delta_{L}", f"V_{x},{L}", f"R_{x},{L}", f"curve_{x}_all_L"]}


def null_identity(got: dict, windows: list) -> dict:
    """Amendment 1 item 1: with B and Q on the same BF16 service and one fixed current action (a_B), every L must give the
    same branch signature as L = inf (full suffix, every prompt/completion, outcome, final env, budget); only key names
    of the differing fields are kept (outcome-blind)."""
    ref = got.get(f"R_B{INF}")
    runs = {"0": got.get("R_B0"), **{str(L): got.get(f"W_B{L}") for L in windows}}
    ok_ref = ref is not None and "error" not in ref
    return {L: (sig_diff(r, ref) if ok_ref and r is not None and "error" not in r else ["run error"]) for L, r in runs.items()}


def raw_key(m: dict) -> str:
    """What the chat template renders of an action: content and tool calls with argument key order (W100ae reuse audit)."""
    return json.dumps([m.get("content"), [[tc.get("name"), F._args(tc.get("arguments"))] for tc in m.get("tool_calls") or []]])


def sig_diff(a: dict, b: dict) -> list[str]:
    sa, sb = F.branch_signature(a), F.branch_signature(b)
    return [k for k in sa if sa[k] != sb[k]]


def run(FD, spec, bases, user_base, servers, out: Path) -> dict:
    ROOT = FD.ROOT
    man_path = ROOT / spec["manifest"]
    man_sha = hashlib.sha256(man_path.read_bytes()).hexdigest()
    if man_sha != spec["manifest_sha256"]:
        raise SystemExit(f"takeover_window: manifest sha {man_sha} != frozen {spec['manifest_sha256']}")
    src, rr = ROOT / spec["src_out"], (ROOT / spec["rr_out"] if spec.get("rr_out") else None)
    if out.resolve() in {src.resolve()} | ({rr.resolve()} if rr else set()):
        raise SystemExit("takeover_window: out must differ from the endpoint directories (they are only read)")
    ssum = json.loads((src / "bank_summary.json").read_text())
    if ssum.get("manifest_sha256") != spec["src_manifest_sha256"]:
        raise SystemExit(f"takeover_window: endpoint block {src} ran under manifest {ssum.get('manifest_sha256')}")
    man = json.loads(man_path.read_text())
    rows = {r["state_key"]: r for r in man["rows"] if r["block"] == spec["block"]}
    orig = {x["state_key"]: x for x in _jsonl(src / "bank_rows.jsonl") if x.get("sub") == "U2B" and x["state_key"] in rows}
    rrec = {x["state_key"]: x for x in _jsonl(rr / "recovery_rows.jsonl")} if rr and (rr / "recovery_rows.jsonl").exists() else {}
    keys = sorted(spec.get("state_keys") or rows)
    windows, sources, rep = [int(L) for L in spec.get("windows", [1, 4])], spec.get("sources", ["B", "Q"]), spec.get("repro", 0.1)
    gate, null = bool(spec.get("gate")), bool(spec.get("null"))
    if null:  # amendment 1 item 1: both controllers on the one BF16 service (B's); the Q-role server is not used
        bases = {"B": bases["B"], "Q": bases["B"]}
    exp = spec.get("expect") or {}
    srv_ok = {r: {k: (servers.get(r) or {}).get(k) == v for k, v in exp.get(r, {}).items()} for r in exp}
    src_srv = ssum.get("servers") or {}  # the endpoint block's own gate (noop) and server identity (protocol §2)
    src_ok = {"gate_pass": ssum.get("gate_pass") is True,
              **{f"{r}_{k}": (src_srv.get(r) or {}).get(k) == v for r in exp if not null or r == "B" for k, v in exp[r].items()}}
    blocks: dict = {}

    def endpoint(sk: str, arm: str, st: dict, depth: int = 0):
        """(kind, branch record or None) of an endpoint arm: 'orig' (BF16 source episode), 'run' / 'rerun' (A7), or None."""
        x, how = orig[sk], str(orig[sk]["arm_source"].get(arm, ""))
        if how == "orig":
            return "orig", None
        if how.startswith("reuse=") and depth == 0 and raw_key(x["a_B"]) == raw_key(x["a_Q"]):
            return endpoint(sk, how[6:], st, 1)
        if how == "run":
            return "run", json.loads((src / "branches" / f"{sk}.json").read_text()).get(arm)
        r7 = rrec.get(sk)
        if how.startswith("error") and r7 and r7.get("arm_source", {}).get(arm) == "rerun":
            return "rerun", json.loads((rr / "branches" / f"{sk}.json").read_text()).get(arm)
        return None, None

    def ref_for(sk: str, x: str, st: dict, blk) -> dict | None:
        kind, br = endpoint(sk, endpoint_arm(x, INF), st)
        if kind == "orig":
            ds = blk.dec[st["task_id"]][st["decision_idx"]:]
            full = blk.traj[st["task_id"]]["messages"]
            return {"kind": "orig", "suffix_sha": st["orig"]["suffix_sha"], "full": full,
                    "decisions": [(F.ids_sha(d["prompt_token_ids"]), F.ids_sha(d.get("completion_token_ids"))) for d in ds]}
        if br and "error" not in br:
            return {"kind": kind, "suffix_sha": br["suffix_sha"], "full": st["history"] + br["suffix"],
                    "decisions": [(d["prompt_ids_sha"], d.get("completion_ids_sha")) for d in br["decisions"]]}
        return None

    def prepare(sk):
        r, x = rows[sk], orig.get(sk)
        if x is None or "a_Q" not in x:
            return {"state_key": sk, "missing_reason": "no complete endpoint row"}
        k = (r["source_run"], r["domain"])
        if k not in blocks:
            blocks[k] = F.Block(ROOT, *k)
        st = F.make_state(blocks[k], r["task_id"], r["t"])
        same = {"state_id": st["state_id"] == x["state_id"], "history_sha": st["history_sha"] == x["history_sha"],
                "prompt_ids_sha": st["q_decision"]["prompt_ids_sha"] == x["prompt_ids_sha"], "steps_left": st["budget"]["steps_left"] == x["steps_left"]}
        rec = {"state_key": sk, "cell": spec["cell"], "block": spec["block"], "domain": r["domain"], "task_id": r["task_id"], "t": r["t"],
               "state_id": st["state_id"], "state_identical": same, "exact_agreement": x.get("exact_agreement"),
               "raw_identical_actions": raw_key(x["a_B"]) == raw_key(x["a_Q"]),
               "src_Y_raw": x.get("Y"), "src_arm_source": x.get("arm_source")}
        if not all(same.values()):
            return {**rec, "missing_reason": f"state differs from the endpoint row {same}"}
        if spec.get("shadow_check", True):
            a_q2, _ = F.shadow(st, bases["Q"], f"tw-{spec['cell']}-{sk}-sQ")
            rec["shadow_identical"] = F.canon_msg(a_q2) == F.canon_msg(x["a_Q"])
        st["a_B"], st["a_Q"] = {"message": x["a_B"]}, {"message": x["a_Q"]}
        u = int(hashlib.sha256(f"tw-v1-repro|{sk}|{spec['cell']}".encode()).hexdigest()[:8], 16) / 16 ** 8
        rec["repro_sample"] = rep == "all" or u < float(rep)
        return {**rec, "_st": st, "_blk": blocks[k]}

    def job(p, kind, x, L):
        st, tag = p["_st"], f"tw-{spec['cell']}-{p['state_key']}-{kind}{x}{L}"
        if kind == "W":  # window: B for L decisions, then Q
            return F.run_branch(st, x, "B", bases, user_base, tag, handback=(L, bases["Q"]))
        if L == 0:  # endpoint xQ through the switch path (handback before the first generated decision)
            return F.run_branch(st, x, "B", bases, user_base, tag, handback=(0, bases["Q"]))
        return F.run_branch(st, x, "B", bases, user_base, tag)  # endpoint xB (L = inf): the controller to the end

    def at_switch(full: list, st: dict, L: int) -> tuple[str, list, dict] | None:
        """(history sha, budget used, DB hashes) just before the first handed-back decision (Q's first request)."""
        from tau2.data_model.tasks import Task

        pos = [i for i in range(st["n_history"], len(full)) if full[i]["role"] == "assistant"]
        if len(pos) <= L + 1:
            return None
        h = full[:pos[L + 1]]
        env = F.restore_env(st["domain"], Task.model_validate(st["task"]), [F.msg_from_dict(m) for m in h])
        return F.canon_seq_sha(h), list(F.budget_used(h, st["n_prefix"])), F.env_hashes(env)

    t0 = time.time()
    with ThreadPoolExecutor(spec.get("concurrency", 6)) as ex:
        prep = list(ex.map(lambda sk: FD._safe(prepare, sk), keys))
    good = [p for p in prep if "_st" in p]
    jobs = [(i, "W", x, L) for i, p in enumerate(good) for x in sources for L in windows]
    jobs += [(i, "R", x, L) for i, p in enumerate(good) if p["repro_sample"] for x in sources for L in (0, INF)]
    co = {"peer": spec.get("co_gate"), "peer_seen": None, "waited_s": 0.0}
    if co["peer"]:  # both gates load the simulator together (protocol §6): wait up to 30 min for the peer to start
        tw = time.time()
        while time.time() - tw < 1800:
            co["peer_seen"] = next((d for d in ("running", "done", "failed") if (WORK / "queue" / d / f"{co['peer']}.json").exists()), None)
            if co["peer_seen"]:
                break
            time.sleep(15)
        co["waited_s"] = time.time() - tw
    sim, stop = [], threading.Event()

    def sample():  # simulator load on this task's replica during the suffix jobs
        try:
            from sim_balancer import metrics_direct
        except Exception:
            return
        while not stop.wait(20):
            m = metrics_direct(user_base) if user_base else None
            if m:
                sim.append(m)
    th = threading.Thread(target=sample, daemon=True)
    th.start()
    t1 = time.time()
    with ThreadPoolExecutor(spec.get("concurrency", 6)) as ex:
        res = list(ex.map(lambda j: FD._safe(job, good[j[0]], j[1], j[2], j[3]), jobs))
    t_jobs = time.time() - t1
    stop.set()
    by: dict = {}
    for (i, kind, x, L), r in zip(jobs, res):
        by.setdefault(i, {})[f"{kind}_{x}{L}"] = r
    rows_out = [p for p in prep if "_st" not in p]
    for i, p in enumerate(good):
        st, blk, sk, got = p.pop("_st"), p.pop("_blk"), p["state_key"], by.get(i, {})
        p["windows"], p["repro"] = {}, {}
        for x in sources:
            ref = ref_for(sk, x, st, blk)
            for L in windows:
                r = got.get(f"W_{x}{L}") or {"error": "not run"}
                v = {"Y": None if "error" in r else FD._y(st["domain"], r), "termination": r.get("termination_reason"),
                     "official_reward": r.get("official_reward"), "db_match": r.get("db_match"), "error": (r.get("error") or "")[:200] or None,
                     "n_decisions_logged": r.get("n_decisions") if "error" in r else len(r.get("decisions") or []),
                     **window_view(r, L, bases), "prefix": prefix_check(r, ref, L),
                     "budget_ok": None if "error" in r or r.get("infra_cause") == "context_overflow" else FD.budget_check(st, r)["ok"], "env_hash_init_ok": r.get("env_hash_init_ok"),
                     "history_prefix_ok": r.get("prefix_ok"), "suffix_sha": r.get("suffix_sha"), "duration": r.get("duration"),
                     # eligibility (protocol §7): the L = inf endpoint of this source generated more than L decisions
                     "ref_n_gen": None if ref is None else len(ref["decisions"]) - 1,
                     "E": None if ref is None else len(ref["decisions"]) - 1 > L}
                if gate:  # outcome-blind gate: window outcomes are not written (protocol §5); branches/ is not read before decide
                    v = {k: x for k, x in v.items() if k not in SEALED}
                if spec.get("switch_env_check") and ref is not None and v["handed_back"] and "error" not in r:
                    a, b = at_switch(st["history"] + r["suffix"], st, L), at_switch(ref["full"], st, L)
                    v["at_switch"] = {"ok": a is not None and a == b, "history_sha": a and a[0], "budget": a and a[1], "env_hash": a and a[2]}
                q = None if gate else quarantine(v["prefix"], x, L)
                if q:  # amendment 1 item 4: recorded and diagnosed; excluded downstream from the main analysis
                    v["quarantine"] = q
                p["windows"][f"{x}{L}"] = v
            if p["raw_identical_actions"]:  # identical current actions: the B- and Q-first windows must coincide
                for L in windows:
                    rb, rq = got.get(f"W_B{L}"), got.get(f"W_Q{L}")
                    if rb and rq and "error" not in rb and "error" not in rq:
                        p.setdefault("exact_pair", {})[str(L)] = not sig_diff(rb, rq)
        for x in sources:
            for L in (0, INF) if p["repro_sample"] else ():
                r, arm = got.get(f"R_{x}{L}") or {"error": "not run"}, "BB" if null else endpoint_arm(x, L)
                kind, br = endpoint(sk, arm, st)
                if "error" in r:
                    c = {"ok": False, "why": r["error"][:200]}
                elif kind == "orig":
                    c = FD.noop_check(st, r, FD.orig_final_hash(st, blk))
                elif br is not None and "error" not in br:
                    d = sig_diff(r, br)
                    c = {"ok": not d, "differs": d, "endpoint": kind}
                else:
                    c = {"ok": None, "why": f"endpoint {arm} not comparable ({p['src_arm_source'].get(arm)})"}
                c.update(arm=arm, L=L, Y=None if "error" in r else FD._y(st["domain"], r), duration=r.get("duration"))
                wv0 = window_view(r, 0, bases) if L == 0 else {}
                c["window_counter_ok"], c["handed_back"] = wv0.get("counter_ok"), wv0.get("handed_back")
                p["repro"][f"BB{L}" if null else arm] = c  # null: both L = 0 and L = inf are arm BB; keep both records
        if null:
            p["null_identity"] = null_identity(got, windows)
        FD.dump(out / "branches" / f"{sk}.json", got)
        rows_out.append(p)
    out.mkdir(parents=True, exist_ok=True)
    (out / "window_rows.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False, default=str) + "\n" for x in rows_out))
    W = [v for x in rows_out for v in (x.get("windows") or {}).values()]
    R = [v for x in rows_out for v in (x.get("repro") or {}).values()]
    allv = lambda vs: all(v is not False for v in vs)  # noqa: E731
    hb = {f"{x}{L}": sum(1 for p in rows_out if (p.get("windows") or {}).get(f"{x}{L}", {}).get("handed_back")) for x in sources for L in windows}
    durs = sorted(v["duration"] for v in W if v.get("duration"))
    rdurs = [v["duration"] for v in R if v.get("duration")]
    pq = lambda xs, q: sorted(xs)[int(len(xs) * q)] if xs else None  # noqa: E731
    s = {"protocol": "tw-v1 (docs/insights/TAKEOVER_WINDOW_PROTOCOL.md)", "manifest_sha256": man_sha, "spec": spec, "servers": servers,
         "server_expect_ok": srv_ok, "n_states": len(keys), "n_prepared": len(good), "n_missing": sum(1 for x in rows_out if "missing_reason" in x),
         "n_errors": sum(1 for x in rows_out if "error" in x) + sum(1 for v in W if v["error"]) + sum(1 for v in R if v["ok"] is False and "why" in v),
         "state_identical": all(all(x["state_identical"].values()) for x in rows_out if "state_identical" in x),
         "shadow_identical": sum(1 for x in good if x.get("shadow_identical")), "n_window_suffixes": len(W), "n_repro_suffixes": len(R),
         "pattern_ok": allv(v["pattern_ok"] for v in W), "counter_ok": allv(v["counter_ok"] for v in W),
         "prefix_ok": allv(v["prefix"]["ok"] for v in W), "prefix_unchecked": sum(1 for v in W if v["prefix"]["ok"] is None),
         "at_switch_ok": allv(v.get("at_switch", {}).get("ok") for v in W), "n_at_switch_checked": sum(1 for v in W if "at_switch" in v),
         "budget_ok": allv(v["budget_ok"] for v in W), "env_hash_init_ok": allv(v["env_hash_init_ok"] for v in W),
         "history_prefix_ok": allv(v["history_prefix_ok"] for v in W),
         "exact_pair": {"n": sum(len(x.get("exact_pair", {})) for x in rows_out), "n_ok": sum(sum(x.get("exact_pair", {}).values()) for x in rows_out)},
         "repro": {"n": len(R), "n_ok": sum(1 for v in R if v["ok"] is True), "n_not_comparable": sum(1 for v in R if v["ok"] is None)},
         "handed_back": hb, "src_ok": src_ok,
         "overflow": {c: sum(1 for v in W if v.get("overflow") == c) for c in ("attempted_handback_generation_failed", "overflow_before_handback", "overflow_after_handback")},
         "quarantine": [[x["state_key"], k, v["quarantine"]["diagnosis"]] for x in rows_out for k, v in (x.get("windows") or {}).items() if v.get("quarantine")],
         "null": None if not null else {"single_server": bases["Q"] == bases["B"], "n_states": len(good),
                                        "n_identical": sum(1 for x in good if not any((x.get("null_identity") or {"": ["missing"]}).values())),
                                        "switch_counted": all(v["handed_back"] and v["counter_ok"] for v in W) and len(W) == len(good) * len(windows)
                                        # amendment 1 item 1: the L = 0 handback (0, B) must also happen and be counted
                                        and sum(1 for v in R if v["L"] == 0 and v["handed_back"] and v["window_counter_ok"] is True) == len(good)},
         "n_E_handback_mismatch": sum(1 for v in W if v.get("E") is not None and v.get("handed_back") is not None and v["E"] != v["handed_back"]
                                     and v.get("overflow") != "attempted_handback_generation_failed"),  # overflow bucket first (amendment 1)
         "repro_window_counter_ok": allv(v["window_counter_ok"] for v in R), "throughput": {"concurrency": spec.get("concurrency", 6), "job_seconds": t_jobs, "n_suffixes": len(jobs),
                                            "suffixes_per_hour": len(jobs) / t_jobs * 3600 if t_jobs > 0 else None,
                                            "suffix_seconds_p50_p90": [durs[len(durs) // 2], durs[int(len(durs) * 0.9)]] if durs else None,
                                            "prep_seconds": t1 - t0, "jobs_start_unix": t1, "jobs_end_unix": t1 + t_jobs,
                                            # panel-mix projection inputs (make_tasks_takeover decide): mean window / endpoint
                                            # suffix seconds and the pool efficiency sum(durations) / (concurrency x job wall)
                                            "mean_W_seconds": sum(durs) / len(durs) if durs else None,
                                            "mean_R_seconds": sum(rdurs) / len(rdurs) if rdurs else None,
                                            "pool_efficiency": (sum(durs) + sum(rdurs)) / (spec.get("concurrency", 6) * t_jobs) if t_jobs > 0 else None,
                                            "user_base": user_base, "co_gate": co,
                                            "sim_load": {"n_samples": len(sim), "waiting_p50_p90_max": [pq([m["wait"] for m in sim], .5), pq([m["wait"] for m in sim], .9), max((m["wait"] for m in sim), default=None)],
                                                         "running_p50_max": [pq([m["run"] for m in sim], .5), max((m["run"] for m in sim), default=None)]}},
         "seconds": time.time() - t0}
    s["gate_pass"] = (s["n_errors"] == 0 and s["n_missing"] == 0 and s["state_identical"]
                      and (s["shadow_identical"] == len(good) or not spec.get("shadow_check", True))
                      and (not null or (s["null"]["single_server"] and s["null"]["switch_counted"] and s["null"]["n_identical"] == len(good) > 0))
                      and s["pattern_ok"] and s["counter_ok"] and s["prefix_ok"] and s["at_switch_ok"] and s["budget_ok"]
                      and s["env_hash_init_ok"] and s["history_prefix_ok"] and s["exact_pair"]["n"] == s["exact_pair"]["n_ok"]
                      and s["repro"]["n_ok"] == s["repro"]["n"] - s["repro"]["n_not_comparable"]
                      and all(all(v.values()) for v in srv_ok.values()) and all(src_ok.values()) and s["repro_window_counter_ok"]
                      and (not gate or (s["repro"]["n_ok"] > 0 and s["n_at_switch_checked"] > 0 and s["prefix_unchecked"] == 0
                                        and s["repro"]["n_not_comparable"] == 0
                                        and all(any(v.get("handed_back") and v.get("pattern_ok") is True for p in rows_out
                                                    for v in [(p.get("windows") or {}).get(f"{x}{max(windows)}", {})]) for x in sources))))
    FD.dump(out / "window_summary.json", s)
    FD.log(f"takeover_window {spec['cell']} {spec['block']}: states {len(good)}/{len(keys)}, suffixes {len(jobs)} in {t_jobs:.0f} s, "
           f"handed back {hb}, repro {s['repro']}, gate_pass {s['gate_pass']}")
    if gate and not s["gate_pass"]:
        raise RuntimeError(f"takeover_window gate failed for {spec['cell']}: see {out / 'window_summary.json'}")
    return s
