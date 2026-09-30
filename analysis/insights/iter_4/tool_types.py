"""tool_types: explicit agent tool-type table (read / write / handoff / other / invalid) for the tau2 retail, airline
and telecom domains, used by the trajectory feature code (common4._feat_traj, *_t features).

Source of truth: the `@is_tool(ToolType.X)` decorators in third_party/tau2-bench/src/tau2/domains/<domain>/tools.py
(agent-side tools only; telecom's user-side tools in user_tools.py are the simulated user's and never appear as agent
calls). Mapping: ToolType.WRITE -> write (changes the environment DB); ToolType.READ -> read;
transfer_to_human_agents (tau2 GENERIC) -> handoff; calculate (GENERIC) -> other (no DB access; `think` is commented
out in both retail and airline tools.py, so a think call is invalid);
any name that is not an agent tool of the episode's domain -> invalid (hallucinated / misspelled tool).
The table is written out below (so feature code does not parse third_party at import time) and `--check` re-derives
it from the tau2 source by AST and fails on any difference.

Differences to the regexes used so far (documented in docs/insights/METHODOLOGY_REVISION.md §C):
  common4.WRITE_RE  ^(cancel|modify|return|exchange|book|update|send)       identical on retail/airline; on telecom
                    it misses suspend_line, resume_line, enable_roaming, disable_roaming, refuel_data (5 of 6 writes)
  iter_2 WRITE_RE   same + 'transfer'                                       counts the handoff as a write
Usage: python tool_types.py --check      (verifies the table against the tau2 source; writes out/tool_types.json)
       python tool_types.py --feature-check <snapshot manifest>   (q4/q8 a6k2 runs in the snapshot: agreement of the
              WRITE_RE features with the table features, and invalid-call rates; writes out/tool_types_features_<id>.json)
"""
import ast
import json
import sys
from pathlib import Path

TAU2 = Path("/data/ziyangs/cloq/third_party/tau2-bench/src/tau2/domains")
HANDOFF = {"transfer_to_human_agents"}
OTHER = {"calculate", "think"}

TOOL_TYPES = {
    "retail": {
        "calculate": "other", "cancel_pending_order": "write", "exchange_delivered_order_items": "write",
        "find_user_id_by_email": "read", "find_user_id_by_name_zip": "read", "get_item_details": "read",
        "get_order_details": "read", "get_product_details": "read", "get_user_details": "read",
        "list_all_product_types": "read", "modify_pending_order_address": "write", "modify_pending_order_items": "write",
        "modify_pending_order_payment": "write", "modify_user_address": "write", "return_delivered_order_items": "write",
        "transfer_to_human_agents": "handoff",
    },
    "airline": {
        "book_reservation": "write", "calculate": "other", "cancel_reservation": "write", "get_flight_status": "read",
        "get_reservation_details": "read", "get_user_details": "read", "list_all_airports": "read",
        "search_direct_flight": "read", "search_onestop_flight": "read", "send_certificate": "write",
        "transfer_to_human_agents": "handoff", "update_reservation_baggages": "write",
        "update_reservation_flights": "write", "update_reservation_passengers": "write",
    },
    "telecom": {
        "disable_roaming": "write", "enable_roaming": "write", "get_bills_for_customer": "read",
        "get_customer_by_id": "read", "get_customer_by_name": "read", "get_customer_by_phone": "read",
        "get_data_usage": "read", "get_details_by_id": "read", "refuel_data": "write", "resume_line": "write",
        "send_payment_request": "write", "suspend_line": "write", "transfer_to_human_agents": "handoff",
    },
}


def tool_type(domain, name):
    """-> read | write | handoff | other | invalid."""
    return TOOL_TYPES.get(domain, {}).get(name or "", "invalid")


def derive(domain):
    """Parse @is_tool(ToolType.X) decorated methods from the tau2 agent tools module."""
    tree = ast.parse((TAU2 / domain / "tools.py").read_text())
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and getattr(dec.func, "id", None) == "is_tool" and dec.args:
                    tt = getattr(dec.args[0], "attr", "?")
                    n = node.name
                    out[n] = "handoff" if n in HANDOFF else "other" if n in OTHER or tt in ("THINK", "GENERIC") else tt.lower()
    return out


def feature_check(snapshot):
    import os
    import numpy as np
    os.environ["CLOQ_SNAPSHOT"] = str(Path(snapshot).resolve())
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import common4 as C4
    runs = sorted(r for r in C4.SNAP["frozen"] if r.startswith(("a6k2_q4_", "a6k2_q8_")) and not r.endswith("_cal"))
    F = C4.features(runs, procs=16)
    rows = [f for r in runs for f in F[r].values()]
    aw = np.array([f["any_write"] for f in rows]); awt = np.array([f["any_write_t"] for f in rows])
    nw = np.array([f["n_write"] for f in rows]); nwt = np.array([f["n_write_t"] for f in rows])
    inv = np.array([f["invalid_rate"] for f in rows])
    res = dict(snapshot=C4.SNAP["snapshot_id"], n_runs=len(runs), n_episodes=len(rows),
               any_write_agreement=float(np.mean(aw == awt)), n_write_agreement=float(np.mean(nw == nwt)),
               confirm_alias_identical=bool(all((f["confirm_bw"] == f["confirm_request_proxy"]) or
                                                (f["confirm_bw"] != f["confirm_bw"] and f["confirm_request_proxy"] != f["confirm_request_proxy"]) for f in rows)),
               invalid_rate_mean=float(inv.mean()), episodes_with_invalid_call=float(np.mean(inv > 0)))
    out = Path(__file__).resolve().parent / f"out/tool_types_features_{C4.SNAP['snapshot_id']}.json"
    out.write_text(json.dumps(res, indent=1))
    print(res, "wrote", out)


def main():
    if "--feature-check" in sys.argv:
        feature_check(sys.argv[sys.argv.index("--feature-check") + 1])
        return
    if "--check" not in sys.argv:
        print(__doc__)
        return
    ok = True
    for d in TOOL_TYPES:
        got = derive(d)
        if got != TOOL_TYPES[d]:
            ok = False
            print(d, "MISMATCH", {k: (TOOL_TYPES[d].get(k), got.get(k)) for k in set(got) | set(TOOL_TYPES[d]) if TOOL_TYPES[d].get(k) != got.get(k)})
    import re
    wr = re.compile(r"^(cancel|modify|return|exchange|book|update|send)")
    diff = {d: {n: (t, bool(wr.match(n))) for n, t in tab.items() if (t == "write") != bool(wr.match(n))} for d, tab in TOOL_TYPES.items()}
    out = Path(__file__).resolve().parent / "out/tool_types.json"
    out.write_text(json.dumps(dict(source=str(TAU2), verified_against_source=ok, table=TOOL_TYPES,
                                   common4_WRITE_RE_disagreements=diff), indent=1))
    print("verified" if ok else "MISMATCH", "| WRITE_RE disagreements:", diff, "| wrote", out)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
