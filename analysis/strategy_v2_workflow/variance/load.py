import json, numpy as np
from pathlib import Path
R = Path('/home/xinyu/cloq')
OUT = Path('/tmp/claude-1003/-home-xinyu/822446b5-66f6-44be-b2ea-c6f351322b3f/scratchpad/impact/variance')
split = json.load(open(R/'manifests/task_split_v0.json'))['domains']
TASKS = []  # (domain, tid)
LONG = []
for dom in ['retail', 'airline']:
    for t in split[dom]['evaluation']:
        TASKS.append((dom, t)); LONG.append(split[dom]['horizon_by_task'][t] > 11)
LONG = np.array(LONG); RETAIL = np.array([d == 'retail' for d, _ in TASKS])
ARMS = ['static', 'fp_traj', 'cloq_all', 'cloq_novel', 'cloq_matched_random', 'cloq_matched_alt']
DRAWS = ['c1', 'c2', 'c3']
V1 = [(a, d, f'{a}_{d}_dev') for a in ARMS for d in DRAWS]
V0 = ['static_eval', 'fp_traj_eval', 'cloq_eval', 'rtn_eval']

def per_task(run, field='db_match'):
    out = {}
    for dom in ['retail', 'airline']:
        m = json.load(open(R/'runs'/run/dom/'metrics.json'))
        for row in m['per_task']:
            out[(dom, row['task_id'])] = row
    return out

def outcome_vec(run):
    pt = per_task(run)
    v = []
    for k in TASKS:
        db = pt[k]['db_match']
        if db is None: raise ValueError((run, k, 'None'))
        v.append(float(bool(db)))
    return np.array(v)

def load_all():
    Y = np.array([outcome_vec(r) for _, _, r in V1])
    bf = outcome_vec('bf16_v1')
    v0 = {r: outcome_vec(r) for r in V0}
    v0['bf16'] = outcome_vec('bf16')
    v0['bf16_rep_eval'] = outcome_vec('bf16_rep_eval')
    return Y, bf, v0
