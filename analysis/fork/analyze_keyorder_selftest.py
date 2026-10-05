"""Synthetic selftest of analyze_keyorder.py (ko-v1): fake Bank P units (real split task ids, random Y) and fake ko-v1 outputs
(keyorder_rows.jsonl, keyorder_summary.json, branches) in a temp dir; reads no fork output. Modes: random (frame 1700 / 85 / 20,
hand-computed estimates), same (Y_KQ = Y_BQ: paired differences 0 off the overflow states), faults (KQ infra error drops its
block; failed KQ acceptance quarantines g3 whole, both swaps). Every group has a KQ context overflow before the first
continuation decision, which must score Y_KQ = 0. Run via: python analysis/fork/analyze_keyorder.py --selftest"""
from __future__ import annotations
import hashlib, json, random, tempfile
from collections import Counter
from pathlib import Path
import numpy as np


def run(K, B: int) -> None:
    rng, td = random.Random(7), Path(tempfile.mkdtemp(dir="/data/ziyangs/cloq_work/tmp"))
    tasks = [(d, str(t)) for d, ts in json.load(open(K.AD.SPLITS))["splits"]["dev"]["tasks"].items() if d in K.AD.PANEL_DOMAINS for t in ts]
    blocks = ["q3", "q4", "q5"] + [f"f{i:02d}" for i in range(1, 18)]
    for mode in ("random", "same", "faults"):
        units, el, ovf, kroot = [], {}, set(), td / mode
        for i, b in enumerate(blocks):
            for j, (d, t) in enumerate(tasks):
                yq = int(rng.random() < .4)
                u = {"model": "q8", "cell": "gptq_w4_d1", "block": b, "domain": d, "task": f"{d}:{t}", "run_id": f"a6k2_q8_gptq_w4_d1_{b}",
                     "div": j % 7 != 0, "Y": {"QQ": yq, "BQ": yq if rng.random() < .8 else 1 - yq, "BB": 0, "QB": 0}}
                if u["div"]:
                    u["state_id"] = hashlib.sha256(f"{b}{d}{t}".encode()).hexdigest()[:16]
                    if j < 41 and rng.random() < .42:
                        el[u["state_id"]] = {"group": f"{K.BANKP}/{K.GROUPS[min(3, i // 5)]}", "domain": d, "n_next_q": 900, "n_next_k": 901}
                units.append(u)
        yb = {u["state_id"]: u["Y"]["BQ"] for u in units if u.get("state_id") in el}
        for g in K.GROUPS:
            (kroot / g / "branches").mkdir(parents=True)
            rows = []
            for n, sid in enumerate(s for s, r in el.items() if K.grp(r) == g):
                br, kq = {"state_id": sid, "db_match": bool(yb[sid] if mode == "same" else rng.random() < .5), "termination_reason": "user_stop"}, {"ok": True}
                if n == 0:  # context overflow before the first continuation decision: valid failure, Y_KQ = 0
                    ovf.add(sid)
                    br = {"state_id": sid, "db_match": False, "termination_reason": "infrastructure_error", "infra_cause": "context_overflow"}
                    kq = {"ok": True, "context_overflow": True, "overflow_at": "before_first_continuation"}
                kq = {"ok": False, "error": "timeout"} if mode == "faults" and (g, n) == ("g2", 1) else \
                    {"ok": False, "record_key_order": False} if mode == "faults" and (g, n) == ("g3", 2) else kq
                if mode == "same" and (g, n) == ("g4", 1):  # A6 agent-output error after a_K: excluded (primary), Y_KQ = 0 (sensitivity)
                    kq, br = {"ok": False, "error": "InvalidFunctionCallException"}, {"error": "InvalidFunctionCallException('Function name was x')", "n_decisions": 2}
                (kroot / g / "branches" / f"{sid}.json").write_text(json.dumps({"KQ": br}))
                rows.append({"state_id": sid, "state_identical": {"x": True}, "noop_sample": n == 3, "QQ_noop": {"ok": True},
                             "shadow": {"identical": True, "completion_ids_ok": True}, "KQ": kq})
            (kroot / g / "keyorder_rows.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
            (kroot / g / "keyorder_summary.json").write_text(json.dumps({"manifest_sha256": K.MAN_SHA, "server_expect_ok": {"Q": {"canary": True}}, "spec": {}}))
        R = K.run(units, kroot, el, B)
        e, c, p = R["estimate"], R["estimate"]["conditional_pct"], R["estimate"]["full_pool_contribution_pct"]
        print(mode, {k: e[k] for k in ("n_units", "n_tasks", "n_blocks", "n_eligible_units", "n_eligible_tasks")}, "cond M_K", c["M_K"]["est"], c["M_K"]["widest"],
              "M_B", c["M_B"]["est"], "M_K-M_B", c["M_KmB"]["est"], c["M_KmB"]["widest"], "| pool M_B", p["M_B"]["est"], "of", p["M_B_all"]["est"],
              "share", p["M_B_share_of_M_B_all"]["est"], "|", R["kq_termination"], R["frame"]["excluded"], "quarantined", list(R["quarantined"]))
        ok = [u for u in units if "excluded" not in u]
        eu, bl = [u for u in ok if u["elig"]], sorted({u["block"] for u in ok})
        for s in K.S4:  # point estimates by hand; paired difference = difference of the two
            assert abs(c[f"{s}_KmB"]["est"] - c[f"{s}_K"]["est"] + c[f"{s}_B"]["est"]) < 2e-3
            assert abs(c[f"{s}_B"]["est"] - 100 * np.mean([u["E"][f"{s}_B"] for u in eu])) < 1e-3
            assert abs(p[f"{s}_K"]["est"] - 100 * np.mean([np.mean([u["E"][f"{s}_K"] for u in ok if u["block"] == b]) for b in bl])) < 1e-3
        for s in K.S4:  # 2026-10-05d: conditional readings use only the pooled-ratio intervals; t over block ratios is auxiliary
            v = c[f"{s}_K"]
            iv = [v[k] for k in ("block_boot_ci95", "crossed_ci95") if v.get(k)]
            assert "t_ci95" not in v and v["widest"] == [min(i[0] for i in iv), max(i[1] for i in iv)], v
        if mode == "random":  # unequal eligible counts per block: pooled ratio and mean of block ratios are different estimands
            nb = Counter(u["block"] for u in eu)
            mb = 100 * np.mean([np.mean([u["E"]["M_K"] for u in eu if u["block"] == b]) for b in nb])
            assert len(set(nb.values())) > 1 and abs(mb - c["M_K"]["est"]) > 1e-6, (nb, mb, c["M_K"]["est"])
            assert c["M_K"]["aux_t_mean_of_block_ratios"]
        assert p["M_B"]["est"] <= p["M_B_all"]["est"] and abs(p["M_B_share_of_M_B_all"]["est"] - 100 * p["M_B"]["est"] / p["M_B_all"]["est"]) < 2e-2
        ou = [u for u in eu if u["state_id"] in ovf]
        kt = R["kq_termination"]  # faults: g3 quarantined (not counted); an overflow state may sit in the dropped g2 block
        assert kt["context_overflow"] == kt["overflow_before_first_continuation"] == (3 if mode == "faults" else 4) and len(ou) in (kt["context_overflow"], {"faults": 2, "same": 3}.get(mode, -1))
        assert all(u["E"]["rescue_K"] == 0 and u["E"]["damage_K"] == u["Y"]["QQ"] for u in ou)
        if mode == "same":  # 2026-10-05d: the A6 state is classed and enters only the Y = 0 sensitivity
            assert R["kq_errors"] == {"agent_output:invalid_function_name": 1} and R["sensitivity_a6_y0"]["n_a6"] == 1, R["kq_errors"]
        else:
            assert R["sensitivity_a6_y0"] is None
        if mode == "same":  # Y_KQ = Y_BQ off the overflow states: every paired difference is 0 there
            assert all(u["E"][f"{s}_KmB"] == 0 for u in eu if u["state_id"] not in ovf for s in K.S4)
        if mode == "random":
            assert (e["n_units"], e["n_tasks"], e["n_blocks"], e["n_eligible_units"]) == (1700, 85, 20, len(el)) and not R["quarantined"]
        if mode == "faults":  # g3 quarantined whole (its 5 blocks, both swaps); the g2 infra error drops its block (strict rule)
            assert list(R["quarantined"]) == ["g3"] and (e["n_blocks"], e["n_units"]) == (14, 14 * 85) and not set(bl) & set(blocks[10:15])
        if mode == "random":  # 2026-10-05c: the same overflow with n_next_k <= n_next_q quarantines its task; no trailing newline is read
            g0 = kroot / "g1"
            rp = g0 / "keyorder_rows.jsonl"
            rp.write_text(rp.read_text().rstrip("\n"))
            el0 = {s: r for s, r in el.items() if K.grp(r) == "g1"}
            assert not K.ko_group(g0, el0)["quarantine"] and not K.ko_group(g0, el0)["excl"], "last row without newline"
            ko = K.ko_group(g0, {s: {**r, "n_next_k": r["n_next_q"]} if s in ovf else r for s, r in el0.items()})
            assert any("n_next_k <= n_next_q" in x for x in ko["quarantine"]), ko["quarantine"]
    print("analyze_keyorder selftest ok (synthetic Y only)")
    print(K.markdown({**R, "script_sha256": "0" * 16, "protocol_sha256": "0" * 16, "snapshot": "synthetic"}).splitlines()[2][:160])
