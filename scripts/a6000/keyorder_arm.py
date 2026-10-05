"""Key-order arm, fork_driver mode `keyorder` (docs/insights/KEYORDER_PERTURB_PROTOCOL.md, ko-v1).

For every eligible state of one Bank P fork directory (manifests/fork/keyorder_v1.json, built by keyorder_scan.py before
any key-order suffix existed): rebuild the state from the Q block (cloq/fork.py make_state) and require it to equal the
saved Bank P state, rebuild a_K = transform(a_Q) and require its raw sha to equal the manifest, optionally let Q regenerate
a_Q at h_t (shadow), then run KQ (force a_K, Q to the end). A hash sample (noop_frac) also re-runs QQ, which must reproduce
the original episode (fork_driver.noop_check). Branch records go to <out>/branches/<sid>.json; rows and the summary carry
acceptance checks only (no outcome field), so the run can be audited without reading a key-order outcome.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import keyorder_scan as KS
from cloq import fork as F

NEED = ("KQ",)
LOCK = threading.Lock()


def noop_member(sid: str, frac: float) -> bool:
    return int(hashlib.sha256(f"ko-v1-noop|{sid}".encode()).hexdigest()[:8], 16) / 16 ** 8 < frac


def prepare(FD, row: dict, src: Path, blocks: dict) -> dict:
    saved = json.loads((src / "states" / f"{row['state_id']}.json").read_text())
    k = (row["run_id"], row["domain"])
    with LOCK:
        if k not in blocks:
            blocks[k] = F.Block(FD.ROOT, *k)
    st = F.make_state(blocks[k], row["task_id"], row["t"])
    same = {"state_id": st["state_id"] == saved["state_id"] == row["state_id"], "history_sha": st["history_sha"] == saved["history_sha"] == row["history_sha"],
            "prompt_ids_sha": st["q_decision"]["prompt_ids_sha"] == row["prompt_ids_sha"], "env_hash": st["env_hash"] == saved["env_hash"],
            "budget": st["budget"] == saved["budget"], "a_Q_raw": KS.raw_sha(st["a_Q"]["message"]["tool_calls"]) == row["a_Q_raw_sha"]}
    st["a_K"] = {"message": KS.transform(st["a_Q"]["message"]), "source": f"ko-v1 {KS.RULE} of the recorded a_Q"}
    same["a_K_raw"] = KS.raw_sha(st["a_K"]["message"]["tool_calls"]) == row["a_K_raw_sha"]
    return {"st": st, "blk": blocks[k], "state_identical": same}


def kq_checks(FD, st: dict, row: dict, r: dict) -> dict:
    """Outcome-blind acceptance of one KQ suffix: the transformed order reached the trajectory and the next prompt."""
    if "error" in r:
        return {"ok": False, "error": r["error"][:300]}
    suf, ds = r.get("suffix"), r.get("decisions") or []
    cont = [d for d in ds if not d["forced"]]
    c = {"forced_first": bool(ds) and ds[0]["forced"] and not any(d["forced"] for d in ds[1:])}
    if r.get("infra_cause") == "context_overflow":
        # A valid failure outcome (W10/W70, Y = 0), never a quarantine. cloq/fork.py keeps the decisions and the messages
        # executed before the overflow (partial_suffix, 2026-10-05d), so the forced action, its tool results and the restored
        # prefix are verified exactly as for a completed suffix; only checks on the final env and budget have no input.
        ps = r.get("partial_suffix")
        tv = [(t["content"], bool(t["error"]), t["requestor"], t["id"]) for t in (ps or [])[1:1 + row["n_calls"]]]
        c.update({"env_hash_init_ok": bool(r.get("env_hash_init_ok")), "prefix_ok": bool(r.get("partial_prefix_ok")),
                  "record_key_order": bool(ds) and [list(tc["arguments"]) for tc in ds[0].get("tool_calls") or []] == row["k_key_order"],
                  "trajectory_key_order": bool(ps) and KS.key_orders(ps[0]) == row["k_key_order"],
                  "tool_messages": len(tv) == row["n_calls"] and KS.raw_sha(tv) == row["k_tool_view_sha"]})
        if cont:
            c["next_prompt_predicted"] = cont[0]["prompt_ids_sha"] == row["k_next_ids_sha"]
        else:  # the Q episode sent its n_next_q-token next request without overflow (criterion d): under the deterministic server
            # only a longer transformed prompt can overflow there; anything else is a render / server / limit fault (2026-10-05c)
            c["overflow_consistent"] = (row.get("n_next_k") or 0) > (row.get("n_next_q") or 0)
        return {"ok": all(c.values()), **c, "context_overflow": True, "duration": r.get("duration"), "n_decisions": len(ds),
                "overflow_at": "continuation" if cont else "before_first_continuation", "n_next_k": row.get("n_next_k"), "n_next_q": row.get("n_next_q")}
    c.update({"record_key_order": bool(ds) and [list(tc["arguments"]) for tc in ds[0].get("tool_calls") or []] == row["k_key_order"],
              "next_prompt_predicted": bool(cont) and cont[0]["prompt_ids_sha"] == row["k_next_ids_sha"]})
    tv = [(t["content"], bool(t["error"]), t["requestor"], t["id"]) for t in suf[1:1 + row["n_calls"]]]
    c.update({"trajectory_key_order": bool(suf) and KS.key_orders(suf[0]) == row["k_key_order"],
              "tool_messages": KS.raw_sha(tv) == row["k_tool_view_sha"],
              "next_prompt_from_server": bool(cont) and bool(cont[0]["prompt_ids_from_server"]) and bool(cont[0]["prompt_ids_match_local"]),
              "prefix_ok": bool(r.get("prefix_ok")), "env_hash_init_ok": bool(r.get("env_hash_init_ok")),
              "budget_ok": FD.budget_check(st, r)["ok"]})
    return {"ok": all(c.values()), **c, "duration": r.get("duration"), "n_decisions": len(ds)}


def run(FD, spec, bases, user_base, servers, out: Path) -> dict:
    ROOT = FD.ROOT
    mp = ROOT / spec["manifest"]
    msha = hashlib.sha256(mp.read_bytes()).hexdigest()
    if msha != spec["manifest_sha256"]:
        raise SystemExit(f"keyorder: manifest sha {msha} != frozen {spec['manifest_sha256']}")
    src = ROOT / spec["group"]
    if out.resolve() == src.resolve():
        raise SystemExit("keyorder: out must differ from the Bank P directory (only read)")
    man = json.loads(mp.read_text())
    rows = [r for r in man["rows"] if r["eligible"] and r["group"] == spec["group"]]
    if spec.get("state_ids"):  # selftest / gate subset only; a panel task never sets it
        rows = [r for r in rows if r["state_id"] in set(spec["state_ids"])]
    exp = spec.get("expect") or {}
    srv_ok = {r: {k: (servers.get(r) or {}).get(k) == v for k, v in exp.get(r, {}).items()} for r in exp}
    if not all(all(v.values()) for v in srv_ok.values()):  # fail fast: not the Bank P servers
        raise SystemExit(f"keyorder: servers differ from the Bank P task's {srv_ok}")
    frac, t0, blocks = float(spec.get("noop_frac", 0.1)), time.time(), {}

    def one(row):
        sid = row["state_id"]
        p = prepare(FD, row, src, blocks)
        st = p["st"]
        rec = {"state_id": sid, "block": row["block"], "domain": row["domain"], "task_id": row["task_id"], "t": row["t"],
               "state_identical": p["state_identical"], "noop_sample": noop_member(sid, frac)}
        if not all(p["state_identical"].values()):
            return {**rec, "missing_reason": "state differs from the Bank P state or the manifest"}
        bf = out / "branches" / f"{sid}.json"
        got = json.loads(bf.read_text()) if spec.get("resume") and bf.exists() else {}
        need = list(NEED) + (["QQ"] if rec["noop_sample"] else [])
        if not all(a in got and "error" not in got[a] for a in need):
            if spec.get("shadow_check", True):
                a_q2, r2 = F.shadow(st, bases["Q"], f"ko-{sid}-sQ")
                got["_shadow"] = {"identical": F.canon_msg(a_q2) == F.canon_msg(st["a_Q"]["message"]) and
                                  KS.key_orders(a_q2) == KS.key_orders(st["a_Q"]["message"]),
                                  "completion_ids_ok": F.ids_sha(r2.get("completion_token_ids")) == st["q_decision"]["completion_ids_sha"]}
            for a in need:
                if a not in got or "error" in got[a]:
                    got[a] = FD._safe(F.run_branch, st, a[0], a[1], bases, user_base, f"ko-{sid}-{a}")
            FD.dump(bf, got)
        rec["shadow"] = got.get("_shadow")
        rec["KQ"] = kq_checks(FD, st, row, got["KQ"])
        if rec["noop_sample"]:
            q = got["QQ"]
            rec["QQ_noop"] = {"ok": False, "error": q["error"][:300]} if "error" in q else \
                {k: v for k, v in FD.noop_check(st, q, FD.orig_final_hash(st, p["blk"])).items() if isinstance(v, bool) or k == "ok"}
        return rec

    with ThreadPoolExecutor(spec.get("concurrency", 6)) as ex:
        recs = list(ex.map(lambda r: FD._safe(one, r), rows))
    wall = time.time() - t0
    recs = [x if "state_id" in x else {"state_id": r["state_id"], "error": x.get("error")} for r, x in zip(rows, recs)]
    out.mkdir(parents=True, exist_ok=True)
    (out / "keyorder_rows.jsonl").write_text("".join(json.dumps(x, default=str) + "\n" for x in recs))
    ok = [x for x in recs if "KQ" in x]
    nq = [x["QQ_noop"] for x in ok if "QQ_noop" in x]
    durs = [x["KQ"].get("duration") or 0 for x in ok]
    s = {"protocol": "ko-v1 (docs/insights/KEYORDER_PERTURB_PROTOCOL.md)", "manifest_sha256": msha, "spec": spec, "servers": servers,
         "user_base": user_base, "server_expect_ok": srv_ok, "n_eligible": len(rows), "n_run": len(ok),
         "n_missing": sum(1 for x in recs if "missing_reason" in x), "n_errors": sum(1 for x in recs if "error" in x),
         "n_kq_ok": sum(1 for x in ok if x["KQ"]["ok"]),
         "kq_check_fail": {k: sum(1 for x in ok if x["KQ"].get(k) is False) for k in
                           ("forced_first", "trajectory_key_order", "record_key_order", "tool_messages", "next_prompt_predicted",
                            "next_prompt_from_server", "prefix_ok", "env_hash_init_ok", "budget_ok", "overflow_consistent")},
         "shadow": {"n": sum(1 for x in ok if x.get("shadow")), "n_identical": sum(1 for x in ok if (x.get("shadow") or {}).get("identical")
                                                                                    and x["shadow"]["completion_ids_ok"])},
         "noop": {"n": len(nq), "n_ok": sum(1 for v in nq if v.get("ok"))},
         "kq_context_overflow": {w: sum(1 for x in ok if x["KQ"].get("overflow_at") == w) for w in ("before_first_continuation", "continuation")},
         "throughput": {"wall_seconds": wall, "suffix_seconds_mean": sum(durs) / len(durs) if durs else None,
                        "suffixes_per_hour": (len(ok) + len(nq)) / wall * 3600 if wall > 0 else None},
         "outcome_fields_written": "none (outcomes only in branches/*.json, read by the analysis after the protocol commit)"}
    s["pass"] = (s["n_missing"] == 0 and s["n_errors"] == 0 and s["n_kq_ok"] == s["n_run"] == len(rows)
                 and s["noop"]["n_ok"] == s["noop"]["n"] and (not spec.get("shadow_check", True) or s["shadow"]["n_identical"] == s["n_run"])
                 and all(all(v.values()) for v in srv_ok.values()))
    FD.dump(out / "keyorder_summary.json", s)
    FD.log(f"keyorder {spec['group']}: KQ ok {s['n_kq_ok']}/{len(rows)}, noop {s['noop']}, shadow {s['shadow']}, pass {s['pass']}")
    return {**s, "verdict": "pass" if s["pass"] else "fail"}
