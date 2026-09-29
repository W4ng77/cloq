import json, sys
from pathlib import Path
sys.path.insert(0, '/home/xinyu/cloq')
from cloq.metrics import load_decisions
from load import TASKS, R, OUT, per_task
runs = ['bf16', 'bf16_rep_eval', 'bf16_v1']
dec = {}
for r in runs:
    dd = {}
    for dom in ['retail', 'airline']:
        for x in load_decisions(R / 'runs' / r / dom):
            dd[(dom, str(x['task_id']), x['decision_idx'])] = (x.get('prompt_sha256'), x.get('content'), json.dumps([{k: v for k, v in c.items() if k != 'id'} for c in (x.get('tool_calls') or [])], sort_keys=True), tuple(x.get('completion_token_ids') or []))
    dec[r] = dd
out = {}
for a, b in [('bf16', 'bf16_v1'), ('bf16', 'bf16_rep_eval'), ('bf16_rep_eval', 'bf16_v1')]:
    pa, pb = per_task(a), per_task(b)
    o = dict(n_tasks=len(TASKS), outcome_equal=sum(bool(pa[k]['db_match']) == bool(pb[k]['db_match']) for k in TASKS),
             n_decisions_equal=sum(pa[k]['n_decisions'] == pb[k]['n_decisions'] for k in TASKS),
             reward_equal=sum(pa[k]['reward'] == pb[k]['reward'] for k in TASKS))
    d0p = d0c = allsame = 0; ndec = nsame = 0; firstdiff = []
    for dom, t in TASKS:
        ka = sorted(i for (d_, t_, i) in dec[a] if d_ == dom and t_ == t)
        kb = sorted(i for (d_, t_, i) in dec[b] if d_ == dom and t_ == t)
        if dec[a].get((dom, t, 0), (None,))[0] == dec[b].get((dom, t, 0), (1,))[0]: d0p += 1
        if dec[a].get((dom, t, 0))[1:3] == dec[b].get((dom, t, 0))[1:3]: d0c += 1
        same = ka == kb and all(dec[a][(dom, t, i)] == dec[b][(dom, t, i)] for i in ka)
        allsame += same
        for i in set(ka) & set(kb):
            ndec += 1; nsame += dec[a][(dom, t, i)][:3] == dec[b][(dom, t, i)][:3]
        if not same:
            fd = next((i for i in range(max(len(ka), len(kb))) if dec[a].get((dom, t, i)) != dec[b].get((dom, t, i))), None)
            firstdiff.append((dom, t, fd))
    o.update(decision0_prompt_sha_equal=d0p, decision0_completion_equal=d0c, full_trajectory_identical=allsame,
             shared_decisions=ndec, shared_decisions_identical=nsame, first_diffs=firstdiff[:20])
    out[f'{a}_vs_{b}'] = o
json.dump(out, open(OUT / 'determinism.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
