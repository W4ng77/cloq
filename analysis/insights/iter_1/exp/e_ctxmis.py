"""Reclassify s02's "context mismatch without agent flip" events (read-only over runs/).

s02 compares normalised actions (common.action_key: text content, or tool names + args without call ids). When
the next prompt differs although the normalised action matched, the candidates doc attributed it to the user
simulator. This checks the raw evidence: did the *agent's* completion token ids differ at the previous decision,
and which message is the first to differ in the next context?
usage: python e_ctxmis.py q4 q8   -> out/ctxmis.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import a6000_runs, load_both  # noqa: E402
from s02_trajectory_divergence import first_divergence  # noqa: E402

RUNS = Path("/data/ziyangs/cloq/runs")
HERE = Path(__file__).parent


def raw(run):
    out = {}
    for d in ("retail", "airline"):
        p = RUNS / run / d / "decisions.jsonl"
        if p.exists():
            for line in open(p):
                x = json.loads(line)
                out[(d, x["task_id"], x["decision_idx"])] = x
    return out


res = {}
for m in sys.argv[1:] or ["q4", "q8"]:
    ref = f"a6000_{m}_bf16"
    R = raw(ref)
    refl = load_both(ref)
    for pert in sorted(r for r in a6000_runs() if r.startswith(f"a6000_{m}_gauss")):
        P = raw(pert)
        rows = first_divergence(refl, load_both(pert), False)
        cnt = {}
        for r in rows:
            if not r.get("ctx_mismatch_without_action_flip"):
                continue
            d, t = r["task"].split("/")
            i = r["idx"]
            a, b = R.get((d, t, i - 1)), P.get((d, t, i - 1))
            prev_raw_same = a is not None and b is not None and a["completion_token_ids"] == b["completion_token_ids"]
            ma, mb = R[(d, t, i)]["messages"], P[(d, t, i)]["messages"]
            j = next((k for k in range(min(len(ma), len(mb))) if ma[k] != mb[k]), None)
            key = f"prev_agent_tokens_same={prev_raw_same}|first_diff_role={ma[j]['role'] if j is not None else 'length'}"
            cnt[key] = cnt.get(key, 0) + 1
        res[pert] = cnt
        print(pert, cnt)
(HERE / "out").mkdir(exist_ok=True)
(HERE / "out/ctxmis.json").write_text(json.dumps(res, indent=1))
