"""Synthetic selftest of analyze_takeover.py / takeover_report.py (tw-v1). Fake endpoint units and fake panel directories (window_rows,
window_summary, branches) with random Y in a temp dir; reads no fork output. Run via: python analysis/fork/analyze_takeover.py --selftest"""
from __future__ import annotations
import json, tempfile
from pathlib import Path
import numpy as np


def make(M, tmp: Path, c: str, mode: str, rng, plant: bool = True) -> tuple[list, list]:
    """One cell, 3 blocks x 85 states. mode 'random': random Y; 'answer1': Y_QQ = 0, Y_Q4, Y_Qinf ~ Bern(.9) (V_Q4 > 0, R_Q4 near 0);
    'beats': Y_Q4 = Y_QQ (flipped w.p. .1), Y_Qinf = 1 (V_Qinf - V_Q4 > 0, V_Q4 near 0). Noise keeps the block-t intervals non-degenerate. plant: the planted defects below."""
    TR, units, recs = M.TR, [], []
    for blk in ("f01", "f02", "f03"):
        d, rows, eps = tmp / mode / c / blk, [], []
        (d / "branches").mkdir(parents=True, exist_ok=True)
        for i in range(85):
            sk = f"s{blk}{i:03d}"  # state keys are shared by both cells
            r = lambda p: int(rng.random() < p)  # noqa: E731
            Yep = {"QQ": r(.4), "QB": r(.7), "BQ": r(.5), "BB": r(.7)} if mode == "random" else {"QQ": 0 if mode == "answer1" else r(.3), "QB": r(.9) if mode == "answer1" else 1, "BQ": r(.5), "BB": r(.7)}
            eps.append({"task": f"retail|{i}", "block": blk, "state_key": sk, "exact": i % 5 == 0, "Y": Yep})
            w = {}
            for x in ("B", "Q"):
                for L in ("1", "4"):
                    E = i % 7 != 0  # E = 0: the window never hands back, its suffix is pi_inf's (Y_{x,L} = Y_{x,inf})
                    yl = Yep[x + "B"] if not E else (r(.65) if x == "B" or mode == "random" else r(.9) if mode == "answer1" else Yep["QQ"] if rng.random() < .9 else 1 - Yep["QQ"])
                    w[x + L] = {"Y": yl, "E": E, "handed_back": E, "n_B": int(L) if E else 2, "pattern_ok": True, "counter_ok": True, "prefix": {"ok": True}, "ref_n_gen": 9 if E else 2}
            if plant:
                if i == 3:
                    w["Q4"].update(Y=0, overflow="attempted_handback_generation_failed", handed_back=False, n_B=4, pattern_ok=None)
                if i == 4:
                    w["B1"].update(quarantine={"diagnosis": "bf16_generation_nondeterminism"}, prefix={"ok": False, "bad": ["completion1"]})
                if i == 6:
                    w["Q1"].update(Y=None, error="InvalidFunctionCallException('Function name was x')")
                if i == 8 and blk == "f02" and c == "spinquant_w4a4":
                    w["B4"].update(Y=None, error="ReadTimeout('x')")  # non-A6 missing: SpinQuant f02 leaves the primary
            rp = {"QQ": {"ok": not (plant and blk == "f03" and i == 10 and c == "gptq_w4_d1"), "L": 0, "window_counter_ok": True}}
            if plant and blk == "f02" and i == 10:  # an infrastructure error and a not-comparable re-run do not mask the block (Amendment 3)
                rp.update(QB={"ok": False, "why": "ReadTimeout('x')", "L": "inf"}, BQ={"ok": None, "why": "endpoint BQ not comparable", "L": 0})
            rows.append({"state_key": sk, "windows": w, "repro": rp})
            dec = [{"forced": True}] + [{"n_prompt_tokens": 1000 + 10 * j, "n_completion_tokens": 50} for j in range(6)]
            (d / "branches" / f"{sk}.json").write_text(json.dumps({"W_Q1": {"error": w["Q1"].get("error", ""), "n_decisions": 2}, "W_B4": {"decisions": dec}, "W_Q4": {"decisions": dec}}))
        (d / "window_rows.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
        (d / "window_summary.json").write_text(json.dumps({"server_expect_ok": {"B": {"canary": True}}, "src_ok": {"gate_pass": True}, "throughput": {"jobs_end_unix": M.DEADLINE_UNIX - 60}}))
        ws, info = M.load_windows(d, {u["state_key"] for u in eps})
        units += [{**TR.build(u, ws.get(u["state_key"]), info["endpoint_accepted"]), "_ep": u, "_w": ws.get(u["state_key"])} for u in eps]
        recs += [{**v, "block": blk} for v in ws.values()]
    return units, recs


def run(M, B: int) -> None:
    TR, rng, tmp = M.TR, np.random.default_rng(20261005), Path(tempfile.mkdtemp(prefix="tw_selftest_"))
    per = {c: make(M, tmp, c, "random", rng) for c in TR.CELLS}
    R = TR.analyse(per, B)
    g, s = R["cells"]["gptq_w4_d1"], R["cells"]["spinquant_w4a4"]
    U = {u["state_key"]: u for u in per["gptq_w4_d1"][0]}
    assert s["blocks_dropped"] == ["f02"] and s["strict_blocks"] == ["f01", "f03"] and g["strict_blocks"] == ["f01", "f02", "f03"], "strict blocks"
    assert all(U["sf01004"]["E"][f"Y_B{L}"] is None for L in TR.LS) and U["sf01004"]["E"]["D1"] is None and U["sf01004"]["E"]["D4"] is not None, "quarantine masks"
    assert U["sf01006"]["Y"][("Q", "1")] == 0, "A6 window error is Y = 0"
    assert U["sf03010"]["E"]["V_Q4"] is None and U["sf03010"]["E"]["D0"] is None and U["sf03010"]["E"]["d41_Q"] is not None and U["sf03010"]["E"]["D4"] is not None, "repro quarantine"
    assert all(u["E"]["R_Q4"] == 0 and u["E"]["V_Q4"] == u["E"]["V_Qinf"] for u in U.values() if u["Eflag"]["Q4"] is False and u["ep_ok"]), "E = 0 identity"
    hb = g["handback"]["Q4"]
    assert hb["buckets"]["attempted handback, generation failed"] == 3 and hb["n_E_handback_mismatch"] == 0 and abs(hb["tokens_mean"]["B_prefill"] - (72 * 4060 + 13 * 2010) / 85) < 1e-9, hb
    assert g["handback"]["B1"]["quarantine"] == {"bf16_generation_nondeterminism": 3}
    a = g["primary"]["all_states_pp"]
    assert a["V_Q4"]["n"] == 170 and a["V_Q4"]["n_blocks"] == 2 and "crossed_ci95" in a["V_Q4"] and "block_boot_ci95" in a["V_Q4"], a["V_Q4"]
    sq = g["sensitivity_quarantine_included"]["all_states_pp"]["D1"]["n"]
    assert sq == a["D1"]["n"] + 3 == 255 and g["sensitivity_no_prefix_mismatch"]["all_states_pp"]["D4"]["n"] == a["D4"]["n"] - 3, "sensitivities"
    assert R["spinquant_minus_gptq_pp"]["n_states"] == 170, "cross-cell pairing on common strict blocks"
    t = g["transitions"]["Q"]
    assert sum(t["patterns_Y0_Y1_Y4_Yinf"].values()) == t["n"] and all(len(v["kept"]) + len(v["undone"]) <= 255 for v in t["rescue_inf"].values())
    print("== random Y (both cells): reading ==")
    print("\n".join(g["reading"] + s["reading"]))
    print("handback gptq Q4:", json.dumps(hb))
    for mode, want in (("answer1", "survives handback to Q (§9 answer 1)"), ("beats", "continuous takeover beats four-step takeover; the four-step net gain is unresolved")):
        P = {c: make(M, tmp, c, mode, rng, plant=False) for c in TR.CELLS}
        rd = TR.analyse(P, B)["cells"]["gptq_w4_d1"]["reading"]
        assert any(want in x for x in rd), (mode, rd)
        assert mode != "answer1" or any("not distinguishable from sustained takeover at this n, R_Q4" in x for x in rd), rd
        print(f"== planted '{mode}' ==")
        print("\n".join(x for x in rd if "L=4" in x))
    cross = {"est": 1.0, "ci95": [-1.0, 3.0], "t_ci95": [-1.0, 3.0], "n_blocks": 3, "n": 9, "primary": "t"}  # every interval crosses 0: only the 'not resolved' wordings
    rd = TR.reading("x", {"all_states_pp": {"V_Q4": cross, "R_Q4": cross, "Vinf-V4_Q": cross}, "subsets_pp": {"E_Q4 curve": {}}})
    assert "V_Q4 not resolved at this n" in rd[2] and "not distinguishable from sustained takeover at this n" in rd[3] and "V_Q1 not estimable (no data)" in rd[0], rd
    assert TR.BANNED.search("four steps suffice") and TR.BANNED.search("four steps are enough") and TR.BANNED.search("short takeover is ineffective")
    one = {c: ([u for u in P[c][0] if u["block"] == "f01"], [w for w in P[c][1] if w["block"] == "f01"]) for c in TR.CELLS}  # K = 1 (review repro)
    rd = TR.analyse(one, B)["cells"]["gptq_w4_d1"]["reading"]
    assert not any("survives handback" in x or "longer is not monotone" in x for x in rd) and any("not estimable" in x and "fewer than 2 blocks" in x for x in rd), rd
    dg = {"est": -2.4, "ci95": [-2.4, -2.4], "t_ci95": [-2.4, -2.4], "n_blocks": 2, "n": 170, "primary": "t"}  # degenerate t: no answer
    rd = TR.reading("x", {"all_states_pp": {"V_Q4": cross, "R_Q4": cross, "SO_B1": dg}, "subsets_pp": {"E_Q4 curve": {}, "E_Q4": {"E_share": .8}}})
    assert not any("short-window-only" in x for x in rd) and any("SO_B1 not estimable (zero-width" in x for x in rd), rd
    short = {c: ([u for u in P[c][0] if u["state_key"] != "sf02000"], P[c][1]) for c in TR.CELLS}  # 84 states in f02: not strict
    assert TR.analyse(short, B)["cells"]["gptq_w4_d1"]["strict_blocks"] == ["f01", "f03"], "85-state strict rule"
    G = tmp / "random" / "gptq_w4_d1"
    assert M.load_windows(G / "f02", set())[1]["repro_error"] == 1 and M.load_windows(G / "f03", set())[1]["endpoint_accepted"] is False
    sm = json.loads((G / "f01" / "window_summary.json").read_text())
    (G / "f01" / "window_summary.json").write_text(json.dumps({**sm, "throughput": {"jobs_end_unix": M.DEADLINE_UNIX + 1}}))
    assert M.load_windows(G / "f01", set())[1]["status"].startswith("not complete at the deadline"), "deadline"
    (G / "f01" / "window_summary.json").write_text(json.dumps({**sm, "src_ok": {}}))
    assert M.load_windows(G / "f01", set())[1]["status"].startswith("task output invalid"), "absent src_ok"
    print("selftest OK (Amendment 3): K = 1 and zero-width intervals not estimable, repro error / not comparable do not mask, 85-state rule, deadline, src_ok required")
    print("selftest OK: strict blocks, quarantine masks + sensitivity, A6 window errors, repro quarantine (L1 vs L4 kept), E = 0 identity, "
          "overflow bucket first, n_B / tokens, cross-cell pairing, transitions, reading-rule wording (answer 1, §11.3, no 'suffice')")
