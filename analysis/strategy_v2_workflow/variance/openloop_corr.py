import json, numpy as np
from scipy import stats
from load import *
Y, bf, v0 = load_all()
feat = []
for a, d, r in V1:
    rows = []
    for dom in ['retail', 'airline']:
        rows += [json.loads(l) for l in open(R / 'runs' / r / dom / 'openloop.jsonl')]
    feat.append(dict(n=len(rows), full=np.mean([x['full_action_match'] for x in rows]),
                     tool=np.mean([x['tool_name_match'] for x in rows]),
                     nll=np.mean([x['nll_per_token'] for x in rows if x.get('nll_per_token') is not None])))
out = {}
for k in ['full', 'tool', 'nll']:
    f = np.array([x[k] for x in feat])
    out[k] = dict(values_min=float(f.min()), values_max=float(f.max()), n_states=feat[0]['n'])
    for s, m in [('pooled', np.ones(Y.shape[1], bool)), ('long', LONG)]:
        y = Y[:, m].mean(1)
        rho, p = stats.spearmanr(f, y); r_, pr = stats.pearsonr(f, y)
        out[k][s] = dict(spearman=float(rho), p_spearman=float(p), pearson=float(r_), p_pearson=float(pr))
    # arm effect on the open-loop metric (it is deterministic -> low noise)
    arm = np.repeat(np.arange(6), 3)
    F, pF = stats.f_oneway(*[f[arm == g] for g in range(6)])
    out[k]['arm_anova_F'] = float(F); out[k]['arm_anova_p'] = float(pF)
    out[k]['arm_means'] = {ARMS[g]: float(f[arm == g].mean()) for g in range(6)}
json.dump(out, open(OUT / 'openloop_corr.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
