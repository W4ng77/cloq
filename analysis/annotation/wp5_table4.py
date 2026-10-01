"""WP5 Table 4 (post-unblinding, Amendment 1): Sonnet 5.5 adjudicated labels joined to branch roles and consequence
sign. Final label = R3 adjudication where R1/R2 disagreed on a double state, else the (agreeing or single) reviewer.
Descriptive sample frequencies per sign (20 states each); NOT prevalences (stratified sample, see protocol §1).
Also checks label validity: requirements_satisfied vs the true branch outcome Y.
usage: python analysis/annotation/wp5_table4.py"""
import json, collections
W = 'analysis/annotation/wp5'
key = {json.loads(l)['review_id']: json.loads(l) for l in open('/data/ziyangs/cloq_work/annotation/wp5_KEY_unblinding.jsonl')}
samp = {u['review_id']: u for u in json.load(open('manifests/annotation/wp5_sample_v1.json'))['allocation_units']} \
    if 'allocation_units' in json.load(open('manifests/annotation/wp5_sample_v1.json')) else None
if samp is None:
    m = json.load(open('manifests/annotation/wp5_sample_v1.json'))
    units = next(v for v in m.values() if isinstance(v, list) and v and isinstance(v[0], dict) and 'review_id' in v[0])
    samp = {u['review_id']: u for u in units}
lab = collections.defaultdict(dict)
for R in ('R2', 'R1'):  # R1 last: on agreeing double states identical anyway
    for l in open(f'{W}/labels_{R}.jsonl'):
        x = json.loads(l)
        for f, sl in x['labels'].items():
            for s, v in (sl or {}).items():
                if isinstance(v, dict): lab[x['review_id']][(x['pass'], f, s)] = str(v.get('value'))
for l in open(f'{W}/adjudication_R3.jsonl'):
    a = json.loads(l); lab[a['review_id']][(a['pass'], a['field'], a['slot'])] = str(a['final'])
ORDER = ['BB', 'BQ', 'QB', 'QQ']
rows = []
for rid, u in samp.items():
    k = key[rid]; L = lab[rid]
    role = {k['X']: 'X', k['Y']: 'Y'}  # B/Q -> X/Y
    sl = {k[s]: s for s in ('S1', 'S2', 'S3', 'S4')}  # branch -> S
    Y = dict(zip(ORDER, map(int, u['pattern'])))
    r = {'rid': rid, 'sign': u['sign'], 'family': u['family'], 'Y': Y}
    for a in ('B', 'Q'):
        for f in ('defensible', 'groundedness', 'tool_validity', 'argument_validity', 'permission_consent', 'goal_relevance'):
            r[f'{a}.{f}'] = L.get((1, f, role[a]))
    r['both_defensible'] = L.get((1, 'both_defensible', 'state')); r['state_ambiguity'] = L.get((1, 'state_ambiguity', 'state'))
    for b in ORDER:
        for f in ('requirements_satisfied', 'irreversible_change', 'loop', 'budget_exhaustion', 'defect_corrected', 'retries', 'user_clarification'):
            r[f'{b}.{f}'] = L.get((2, f, sl[b]))
    rows.append(r)
def defect(r, a):
    return (r[f'{a}.groundedness'] in ('partly_grounded', 'ungrounded') or r[f'{a}.argument_validity'] in ('wrong_id', 'wrong_value', 'missing_or_extra')
            or r[f'{a}.tool_validity'] in ('wrong_tool', 'no_tool_needed_but_called', 'tool_needed_but_talked') or r[f'{a}.permission_consent'] == 'write_without_consent')
signs = ['rescue', 'damage', 'both_succeed', 'both_fail']
def pct(rs, pred):
    n = len(rs); k = sum(1 for r in rs if pred(r)); return f'{k}/{n}'
T = collections.OrderedDict()
T['Q action defensible = no'] = lambda r: r['Q.defensible'] == 'no'
T['B action defensible = no'] = lambda r: r['B.defensible'] == 'no'
T['Q action has a local defect'] = lambda r: defect(r, 'Q')
T['B action has a local defect'] = lambda r: defect(r, 'B')
T['Q write without consent'] = lambda r: r['Q.permission_consent'] == 'write_without_consent'
T['Q works against goal'] = lambda r: r['Q.goal_relevance'] == 'works_against_goal'
T['both actions defensible'] = lambda r: r['both_defensible'] == 'yes'
T['state ambiguous'] = lambda r: r['state_ambiguity'] == 'ambiguous'
T['QQ: unconsented irreversible change'] = lambda r: r['QQ.irreversible_change'] == 'unintended_or_unconsented_change'
T['BQ: unconsented irreversible change'] = lambda r: r['BQ.irreversible_change'] == 'unintended_or_unconsented_change'
T['QQ: first-action defect corrected later'] = lambda r: r['QQ.defect_corrected'] == 'corrected'
T['QQ: first-action defect NOT corrected'] = lambda r: r['QQ.defect_corrected'] == 'not_corrected'
T['QQ: loop or budget exhaustion'] = lambda r: r['QQ.loop'] == 'yes' or r['QQ.budget_exhaustion'] == 'yes'
T['BQ: loop or budget exhaustion'] = lambda r: r['BQ.loop'] == 'yes' or r['BQ.budget_exhaustion'] == 'yes'
out = {s: {name: pct([r for r in rows if r['sign'] == s], p) for name, p in T.items()} for s in signs}
# validity: LLM requirements_satisfied=='yes' vs true Y across all 4 branches x 80 states
vc = collections.Counter()
for r in rows:
    for b in ORDER:
        v = r[f'{b}.requirements_satisfied']; vc[(v, r['Y'][b])] += 1
json.dump({'table4': out, 'requirements_vs_Y': {f'{a}|Y={y}': n for (a, y), n in sorted(vc.items(), key=str)}, 'rows': rows},
          open(f'{W}/table4_v1.json', 'w'), indent=1, default=str)
print(f"{'':42s}" + ''.join(f'{s:>14s}' for s in signs))
for name in T: print(f'{name:42s}' + ''.join(f'{out[s][name]:>14s}' for s in signs))
print('\nrequirements_satisfied label vs true outcome Y (all 320 branches):')
for (a, y), n in sorted(vc.items(), key=str): print(f'  {a:8s} Y={y}: {n}')
