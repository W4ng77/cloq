"""WP5 inter-annotator agreement (protocol §5, Amendment 1): per field, R1 vs R2 on double-reviewed states, and
cross-chunk consistency on the 2 calibration states. Pre-unblinding: uses only labels + packets_meta assignment.
usage: python analysis/annotation/wp5_agreement.py"""
import json, collections, itertools
W = 'analysis/annotation/wp5'
meta = json.load(open(f'{W}/packets_meta.json'))
both = {k for k, v in meta['assignment'].items() if v == 'both' and k not in meta['calibration_states']}

def load(p):
    d = {}
    for l in open(p):
        x = json.loads(l)
        for f, slots in x['labels'].items():
            for s, v in (slots or {}).items():
                if isinstance(v, dict):
                    d[(x['review_id'], x['pass'], f, s)] = str(v.get('value'))
    return d

def kappa(pairs):
    n = len(pairs)
    if not n: return None, None, None
    po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs); cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n / n
    cats = set(ca) | set(cb); q = len(cats)
    pi = {k: (ca[k] + cb[k]) / (2 * n) for k in cats}
    pe_ac1 = sum(p * (1 - p) for p in pi.values()) / (q - 1) if q > 1 else 0
    k = (po - pe) / (1 - pe) if pe < 1 else None
    ac1 = (po - pe_ac1) / (1 - pe_ac1) if pe_ac1 < 1 else None
    return po, k, ac1

r1, r2 = load(f'{W}/labels_R1.jsonl'), load(f'{W}/labels_R2.jsonl')
res = {}
fields = sorted({(p, f) for (_, p, f, _) in r1})
for p, f in fields:
    pairs = [(r1[k], r2[k]) for k in r1 if k[0] in both and k[1] == p and k[2] == f and k in r2]
    po, k, ac1 = kappa(pairs)
    unk = sum(v in ('unknown', 'None') for pr in pairs for v in pr) / max(1, 2 * len(pairs))
    res[f'pass{p}:{f}'] = dict(n=len(pairs), agree=po, kappa=k, ac1=ac1, disagreements=sum(a != b for a, b in pairs), unknown_share=unk)

cal = collections.defaultdict(dict)
for l in open(f'{W}/labels_calibration.jsonl'):
    x = json.loads(l)
    for f, slots in x['labels'].items():
        for s, v in (slots or {}).items():
            if isinstance(v, dict): cal[(x['review_id'], x['pass'], f, s)][x['chunk']] = str(v.get('value'))
calres = collections.defaultdict(lambda: [0, 0])
for (rid, p, f, s), d in cal.items():
    for a, b in itertools.combinations(sorted(d), 2):
        calres[f'pass{p}:{f}'][0] += d[a] == d[b]; calres[f'pass{p}:{f}'][1] += 1
out = {'double_states': len(both), 'r1_vs_r2': res,
       'calibration_pairwise_chunk_agreement': {k: v[0] / v[1] for k, v in calres.items() if v[1]}}
json.dump(out, open(f'{W}/agreement_v1.json', 'w'), indent=1)
print(f"{'field':38s} {'n':>4s} {'agree':>6s} {'kappa':>6s} {'AC1':>6s} {'calib':>6s}")
for k, v in res.items():
    c = out['calibration_pairwise_chunk_agreement'].get(k)
    fmt = lambda z: f'{z:6.2f}' if z is not None else '   n/a'
    print(f'{k:38s} {v["n"]:4d} {fmt(v["agree"])} {fmt(v["kappa"])} {fmt(v["ac1"])} {fmt(c)}')
