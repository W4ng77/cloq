"""Build per-state and per-(checkpoint,task) tables for the mechanism analysis.
CPU only, read-only on /home/xinyu/cloq. Outputs pickles in this directory."""
import json, os, re, sys, pickle
from pathlib import Path
from collections import defaultdict
import numpy as np, pandas as pd

os.environ["CUDA_VISIBLE_DEVICES"] = ""
ROOT = Path("/home/xinyu/cloq"); sys.path.insert(0, str(ROOT))
from cloq.metrics import load_decisions, read_jsonl, normalize_action, resolved_db_match
from cloq.divergence import analyze_task

OUT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
SPLIT = json.load(open(ROOT / "manifests/task_split_v0.json"))
ARMS = ["static", "fp_traj", "cloq_all", "cloq_novel", "cloq_matched_random", "cloq_matched_alt"]
DRAWS = ["c1", "c2", "c3"]
CKPTS = [f"{a}_{d}" for a in ARMS for d in DRAWS]
DOMS = ["retail", "airline"]

WRITE = {"cancel_pending_order", "exchange_delivered_order_items", "modify_pending_order_address",
         "modify_pending_order_items", "modify_pending_order_payment", "modify_user_address",
         "return_delivered_order_items", "create_order", "create_gift_card",
         "book_reservation", "cancel_reservation", "update_reservation_baggages",
         "update_reservation_flights", "update_reservation_passengers", "send_certificate"}
IDENT = {"find_user_id_by_email", "find_user_id_by_name_zip", "get_user_details"}


def tool_cat(name):
    if name in WRITE: return "write"
    if name in IDENT: return "identity"
    if name == "transfer_to_human_agents": return "transfer"
    if name == "calculate": return "calculate"
    return "read"


def text_cat(t):
    t = t or ""; l = t.lower()
    if t.strip().startswith("{") or "<tool_call>" in l or '"name":' in l: return "malformed_toolish"
    if re.search(r'confirm|"yes"|reply with|proceed\?|shall i|should i proceed|do you want me to', l): return "confirm_q"
    if re.search(r'authenticat|email address|zip code|user id', l): return "identity_q"
    if re.search(r"anything else|further assistance|feel free|have a (great|wonderful|nice)|don't hesitate|any other questions", l) and not re.search(r'would you like to|which', l): return "closing"
    if re.search(r"can't|cannot|unable|sorry|not (possible|allowed|eligible)|policy", l): return "refusal/policy"
    if "?" in t: return "other_q"
    return "inform"


def act_type(d):
    """(kind, category, tool names) for a decision record; None => trajectory ended."""
    if d is None: return ("end", "END", "")
    if d["tool_calls"]:
        names = [tc["name"] for tc in d["tool_calls"]]
        cats = [tool_cat(n) for n in names]
        c = "write" if "write" in cats else cats[0]
        return ("tool", "T:" + c, "+".join(names))
    return ("text", "X:" + text_cat(d["content"]), "")


def dec_by_task(run, dom):
    by = defaultdict(list)
    for d in load_decisions(RUNS / run / dom):
        by[d["task_id"]].append(d)
    for v in by.values(): v.sort(key=lambda d: d["decision_idx"])
    return by


def main():
    states, closed, consist = [], [], []
    for dom in DOMS:
        ev = SPLIT["domains"][dom]["evaluation"]
        hz = SPLIT["domains"][dom]["horizon_by_task"]
        fp = dec_by_task("bf16_v1", dom)
        rep = {(d["task_id"], d["decision_idx"]): d["prompt_sha256"] for d in load_decisions(RUNS / "bf16_rep_eval" / dom)}
        selfol = {(r["task_id"], r["decision_idx"]): r for r in read_jsonl(RUNS / "bf16_rep_eval" / dom / "openloop_self.jsonl")}
        fpm = {r["task_id"]: r for r in json.load(open(RUNS / "bf16_v1" / dom / "metrics.json"))["per_task"]}
        fptraj = {t["task_id"]: t for t in read_jsonl(RUNS / "bf16_v1" / dom / "trajectory.jsonl")}
        ol = {}
        for ck in CKPTS:
            ol[ck] = {(r["task_id"], r["decision_idx"]): r for r in read_jsonl(RUNS / f"{ck}_dev" / dom / "openloop.jsonl")}
        # ---------- state table ----------
        for tid in ev:
            for d in fp[tid]:
                k = (tid, d["decision_idx"]); s = selfol[k]
                kind, cat, names = act_type(d)
                row = dict(domain=dom, task_id=tid, idx=d["decision_idx"], H=len(fp[tid]), sha=d["prompt_sha256"],
                           sha_rep_equal=(rep.get(k) == d["prompt_sha256"]), kind=kind, cat=cat, tools=names,
                           nll=float(s["nll"]), nlltok=float(s["nll_per_token"]), ntok=int(s["n_action_tokens"]),
                           self_match=bool(s["full_action_match"]), rend_eq=bool(s["rendered_equals_generated"]),
                           truncated=bool(d["context"]["truncated"]), pre_tok=d["context"]["pre_truncation_tokens"],
                           bf16_success=bool(fpm[tid]["db_match"]), horizon_manifest=hz.get(tid))
                for ck in CKPTS:
                    r = ol[ck][k]
                    row[f"fam__{ck}"] = bool(r["full_action_match"])
                    row[f"tem__{ck}"] = r["tool_exact_match"]
                    row[f"km__{ck}"] = bool(r["kind_match"])
                    row[f"qnll__{ck}"] = float(r["nll"])
                    row[f"qkind__{ck}"] = r["q_kind"]
                    # behavioural flip = the t_tool criterion: kind differs, or tool call differs
                    row[f"bflip__{ck}"] = (r["fp_kind"] != r["q_kind"]) or (r["fp_kind"] == "tool" and not r["full_action_match"])
                states.append(row)
        # ---------- closed-loop table ----------
        for ck in CKPTS:
            run = f"{ck}_dev"
            q = dec_by_task(run, dom)
            div = {r["task_id"]: r for r in json.load(open(RUNS / run / dom / "divergence.json"))["per_task"]}
            qm = {r["task_id"]: r for r in json.load(open(RUNS / run / dom / "metrics.json"))["per_task"]}
            qtraj = {t["task_id"]: t for t in read_jsonl(RUNS / run / dom / "trajectory.jsonl")}
            for tid in ev:
                if tid not in q or tid not in div: continue
                F, Q = fp[tid], q[tid]
                a = analyze_task(F, Q); dv = div[tid]
                same = all(a[x] == dv[x] for x in ["t_tool", "t_context", "t_star"])
                tt, tc = a["t_tool"], a["t_context"]
                tr = (tc - 1) if tc is not None else None  # decision that caused the context split
                # consistency: closed-loop Q decisions on identical-context steps vs open-loop replay
                upto = tc if tc is not None else min(len(F), len(Q))
                for i in range(min(upto, len(Q), len(F))):
                    r = ol[ck][(tid, i)]
                    consist.append(dict(ck=ck, domain=dom, task_id=tid, idx=i,
                                        eq=normalize_action(Q[i]["content"], Q[i]["tool_calls"])[:500] == r["q_norm"],
                                        match_eq=(normalize_action(Q[i]["content"], Q[i]["tool_calls"]) == normalize_action(F[i]["content"], F[i]["tool_calls"])) == bool(r["full_action_match"]),
                                        sha_eq=Q[i]["prompt_sha256"] == F[i]["prompt_sha256"]))
                fk = act_type(F[tt] if (tt is not None and tt < len(F)) else None)
                qk = act_type(Q[tt] if (tt is not None and tt < len(Q)) else None)
                fr = act_type(F[tr] if (tr is not None and 0 <= tr < len(F)) else None)
                qr = act_type(Q[tr] if (tr is not None and 0 <= tr < len(Q)) else None)
                t = qtraj[tid]
                closed.append(dict(ck=ck, arm=ck.rsplit("_", 1)[0], draw=ck.rsplit("_", 1)[1], domain=dom, task_id=tid,
                                   H_fp=len(F), H_q=len(Q), t_tool=tt, t_context=tc, t_render=tr, t_star=a["t_star"],
                                   recompute_matches_file=same,
                                   fp_tool_kind=fk[0], fp_tool_cat=fk[1], fp_tool_names=fk[2],
                                   q_tool_kind=qk[0], q_tool_cat=qk[1], q_tool_names=qk[2],
                                   fp_rend_cat=fr[1], q_rend_cat=qr[1],
                                   tool_at_same_ctx=(tt is not None and tc is not None and tt < tc) or (tt is not None and tc is None),
                                   bf16_success=bool(fpm[tid]["db_match"]), q_success=bool(qm[tid]["db_match"]),
                                   q_term=qm[tid]["termination_reason"], q_premature=bool(qm[tid]["premature"]),
                                   fp_term=fpm[tid]["termination_reason"],
                                   q_n_trunc=qm[tid]["n_truncated_contexts"], q_n_dec=qm[tid]["n_decisions"],
                                   q_tool_errors=qm[tid]["n_tool_errors"],
                                   q_trunc_at_ttool=(bool(Q[tt]["context"]["truncated"]) if (tt is not None and tt < len(Q)) else None),
                                   q_trunc_frac_all=float(np.mean([bool(x["context"]["truncated"]) for x in Q])) if Q else None,
                                   q_trunc_first=next((i for i, x in enumerate(Q) if x["context"]["truncated"]), None),
                                   fp_trunc_first=next((i for i, x in enumerate(F) if x["context"]["truncated"]), None)))
    S = pd.DataFrame(states); Cl = pd.DataFrame(closed); Co = pd.DataFrame(consist)
    pickle.dump(dict(S=S, C=Cl, consist=Co, CKPTS=CKPTS, ARMS=ARMS), open(OUT / "tables.pkl", "wb"))
    print("states", S.shape, "closed", Cl.shape, "consist", Co.shape)
    print("sha_rep_equal all:", S.sha_rep_equal.all(), " recompute==file:", Cl.recompute_matches_file.mean())
    print("consistency closed vs open-loop on shared-context steps:", Co["eq"].mean(), Co["match_eq"].mean(), len(Co), "sha_eq", Co.sha_eq.mean())


if __name__ == "__main__":
    main()
