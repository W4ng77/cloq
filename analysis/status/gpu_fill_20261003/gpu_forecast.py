"""Hour-by-hour agent-GPU demand vs supply forecast, 2026-10-03 07:00 -> 2026-10-05 00:00 PDT (W100q).

Greedy list scheduler over node pools. Inputs are point estimates (stated in the proposal); the output is
indicative, not a commitment. Pins: q8 rotation/score tasks only on node004/005/007 (as queued).
"""
import json, sys
from datetime import datetime, timedelta

T0 = datetime(2026, 10, 3, 7, 0)
HORIZON = 41  # hours to 2026-10-05 00:00
# agent GPUs per node and last claim time (job end - 3 h min-left)
NODES = {"node001": (6, datetime(2026, 10, 4, 21, 8)), "node002": (4, None), "node004": (6, None),
         "node005": (6, datetime(2026, 10, 4, 20, 6)), "node006": (6, None), "node007": (6, datetime(2026, 10, 4, 20, 6)),
         "node008": (6, None)}
JOB_END = {"node005": datetime(2026, 10, 4, 23, 6), "node007": datetime(2026, 10, 4, 23, 6)}
Q8PIN = {"node004", "node005", "node007"}

# running tasks: (id, node, gpus, remaining_h)  -- remaining from claim time + family medians (see proposal §2)
RUNNING = [
    ("nmp_tau2_q8_quarot_w4a4_f02", "node004", 2, 1.0), ("nmp_tau2_q8_spinquant_w16_f01", "node004", 2, 1.0),
    ("nmp_tau2_q8_spinquant_w4a4_f01", "node005", 2, 1.0), ("nmp_tau2_q8_spinquant_w4a4_f02", "node007", 2, 1.5),
    ("a6k2_q8_tel_x6", "node001", 1, 1.0), ("a6k2_q8_tel_x6b", "node002", 1, 0.3), ("a6k2_q8_tel_x6c", "node008", 1, 1.0),
    ("a6k2_q8_tel_x6d", "node008", 1, 1.0), ("a6k2_q8_tel_x6e", "node007", 1, 1.0), ("a6k2_q8_tel_x6f", "node007", 1, 1.0),
    ("a6k2_q14_tel_gptq_w3", "node001", 1, 1.5), ("a6k2_q14_tel_rtn_w3", "node008", 1, 1.5),
    ("a6k2_q32_tel_rtn_w3", "node001", 2, 99),  # 28/80 sims in 22.75 h, 7 agent timeouts: runs past the freeze, then fails
    ("a6k2_q4_gauss2_s1_redo", "node004", 1, 2), ("a6k2_q4_gauss3_s1_redo", "node005", 1, 3), ("a6k2_q4_gauss3_s2_redo", "node005", 1, 3),
    ("a6k2_q8_gauss2_s1", "node008", 1, 2), ("a6k2_q8_gauss2_s2", "node006", 1, 1), ("a6k2_q8_gauss3_s1", "node002", 1, 3),
    ("a6k2_q8_gauss3_s2_redo", "node004", 1, 3),
    ("a6k2_q4_kvq_int3", "node008", 1, 10), ("a6k2_q4_kvq_int4", "node008", 1, 6),
    ("a6k2_q8_kvq_int3", "node002", 1, 10), ("a6k2_q8_kvq_int4", "node002", 1, 6),
    ("pert_q4_rtn_w3_resid_a2_q345", "node006", 1, 6), ("pert_q4_rtn_w3_restore_rand_third_s3_q345", "node007", 1, 2),
    ("pert_q8_gptq_w3_resid_a2_q345", "node005", 1, 4), ("pert_q8_rtn_w3_resid_a2_q345", "node005", 1, 4),  # doomed (agent timeouts)
    ("pert_q8_tel_a", "node007", 1, 1), ("pert_q8_tel_b", "node001", 1, 1), ("pert_q8_tel_c", "node001", 1, 1),
    ("a6k2_q8_x1_awq", "node006", 1, 1), ("a6k2_q8_x1_fp8", "node006", 1, 1), ("fork_repair_q4_rtn_w3", "node006", 1, 2),
]


def batch(prefix, n, gpus, dur, release_h, pin=None):
    return [{"id": f"{prefix}_{i}", "gpus": gpus, "dur": dur, "release": release_h, "pin": pin} for i in range(n)]


def scenario(name):
    q = []
    # todo now: 1 runnable rotation tau2 (f03) + 5 rotation scores (after their tau2), all pinned
    q += batch("nmp_tau2_q8_spinquant_w4a4_f03", 1, 2, 2.0, 0.0, Q8PIN)
    q += batch("nmp_score_q8_rot", 5, 2, 0.6, 1.5, Q8PIN)
    if name in ("known", "known+fill"):
        # m24 phase 2 (expansion_m24.json expand=true 04:53): 6 tau2 x 4 GPU (phase-1 median 1.08 h, max 3.96 h)
        q += batch("nmp_tau2_m24_p2", 6, 4, 1.5, 0.0)       # queued 07:05 at -30 (W100o)
        q += batch("nmp_score_m24_p1redo", 6, 4, 0.8, 0.0)  # requeued 07:05 after the score_driver fix
        q += batch("nmp_score_m24_p2", 6, 4, 0.8, 2.0)      # after their tau2
        # q8 phase 2: decision when rotation phase 1 completes (~11:00) -> queued ~12:00 (5 h). 11 cells x 3 blocks.
        q += batch("q8p2_rot_tau2", 15, 2, 1.6, 5.0, Q8PIN)
        q += batch("q8p2_kivi_tau2", 9, 2, 4.5, 5.0)
        q += batch("q8p2_ref_tau2", 9, 2, 0.75, 5.0)
        q += batch("q8p2_scores", 24, 2, 0.6, 9.0)
        # g12 formal: none (W100p gate FAIL on replay)
        q += batch("q8p2_ref_gates", 6, 2, 0.8, 5.0)       # reference cells get both gates (W100r)
    if name == "known+fill":
        # proposal options (GPU_FILL_PROPOSAL_20261003.md): F2 pivot dep fix, F1b cs q4, F1a cs q8 f04-f06,
        # F3 outage-episode completion, F4 two deferred pert arms + det_b
        q += batch("fill_pivot_rtn_w3_q4", 6, 1, 1.0, 1.0)
        q += batch("fill_pivot_rtn_w3_q8", 6, 2, 0.6, 1.0)
        q += batch("fill_cs_q4", 8, 1, 1.2, 4.0)
        q += batch("fill_cs_q8_f456", 6, 2, 1.3, 9.0)
        q += batch("fill_outage_rerun", 14, 1, 2.5, 6.0)
        q += batch("fill_deferred_pert", 2, 1, 14.0, 2.0)
    return q


def simulate(name):
    free = {n: g for n, (g, _) in NODES.items()}
    run = []
    for tid, node, g, rem in RUNNING:
        free[node] -= g
        run.append((node, g, rem))
    pend = sorted(scenario(name), key=lambda t: t["release"])
    out = []
    for h in range(HORIZON):
        t_now = T0 + timedelta(hours=h)
        # finish
        nxt = []
        for node, g, rem in run:
            end_cut = JOB_END.get(node)
            if rem <= 0 or (end_cut and t_now >= end_cut):
                free[node] += g
            else:
                nxt.append((node, g, rem))
        run = nxt
        # claim
        for t in list(pend):
            if t["release"] > h:
                continue
            for node in sorted(free, key=lambda n: -free[n]):
                last = NODES[node][1]
                if last and t_now >= last:
                    continue
                if t["pin"] and node not in t["pin"]:
                    continue
                if free[node] >= t["gpus"]:
                    free[node] -= t["gpus"]
                    run.append((node, t["gpus"], t["dur"]))
                    pend.remove(t)
                    break
        supply = sum(g for n, (g, last) in NODES.items() if not (last and t_now >= last))
        busy = sum(g for _, g, _ in run)
        out.append((t_now.strftime("%m-%d %H:00"), supply, busy, max(0, supply - busy), len(pend)))
        run = [(n, g, rem - 1) for n, g, rem in run]
    return out


if __name__ == "__main__":
    res = {k: simulate(k) for k in ("now_only", "known", "known+fill")}
    print("hour | supply | busy(now_only) idle | busy(known) idle | busy(known+fill) idle")
    tot = {k: 0 for k in res}
    for i in range(HORIZON):
        row = [res[k][i] for k in res]
        for k in res:
            tot[k] += res[k][i][3]
        print(f"{row[0][0]} | {row[0][1]:2d} | {row[0][2]:2d} {row[0][3]:2d} | {row[1][2]:2d} {row[1][3]:2d} | {row[2][2]:2d} {row[2][3]:2d}")
    print("idle GPU-h:", tot)
    json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else "/dev/null", "w"))
