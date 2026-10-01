"""WP5 human-check subset (30 states): compare the Sonnet 5.5 *proxy* check (NOT human) with the programmatic verifier,
the adjudicated R1/R2/R3 LLM labels and the true outcome Y. Proxy labels' sha was committed before this ran (7b516b9).
usage: python analysis/annotation/wp5_proxy_compare.py"""
import json, collections
W = 'analysis/annotation/wp5'
key = {json.loads(l)['review_id']: json.loads(l) for l in open('/data/ziyangs/cloq_work/annotation/wp5_KEY_unblinding.jsonl')}
prog = {json.loads(l)['review_id']: json.loads(l) for l in open(f'{W}/programmatic_v1.jsonl')}
llm = {r['rid']: r for r in json.load(open(f'{W}/table4_v1.json'))['rows']}
prox = collections.defaultdict(dict)
for l in open(f'{W}/human_check_v1/labels_proxy_sonnet.jsonl'):
    x = json.loads(l)
    for f, sl in x['labels'].items():
        for s, v in (sl or {}).items():
            if isinstance(v, dict): prox[x['review_id']][(x['pass'], f, s)] = str(v.get('value'))
def kappa(p):
    n = len(p)
    if not n: return float('nan'), float('nan')
    po = sum(a == b for a, b in p) / n
    ca, cb = collections.Counter(a for a, _ in p), collections.Counter(b for _, b in p)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n / n
    return po, ((po - pe) / (1 - pe) if pe < 1 else float('nan'))
yn = lambda b: 'yes' if b else 'no'
cmp = collections.defaultdict(list)
for rid, P in prox.items():
    k = key[rid]; br = {k[s]: s for s in ('S1', 'S2', 'S3', 'S4')}; role = {k['X']: 'X', k['Y']: 'Y'}
    pr = prog[rid]['branches']; L = llm[rid]
    for b, s in br.items():
        g = lambda f: P.get((2, f, s))
        if g('write_executed') is not None: cmp['write_executed: proxy vs programmatic'].append((g('write_executed'), yn(pr[b]['write_executed'])))
        if pr[b]['write_executed'] and g('consent_recorded') in ('yes', 'no'):
            cmp['consent_recorded (writes only): proxy vs programmatic'].append((g('consent_recorded'), yn(pr[b]['consent_recorded'])))
        if g('budget_exhaustion'): cmp['budget_exhaustion: proxy vs programmatic'].append((g('budget_exhaustion'), yn(pr[b]['budget_exhaustion'])))
        for f in ('irreversible_change', 'defect_corrected', 'requirements_satisfied', 'loop', 'budget_exhaustion', 'retries'):
            if g(f) is not None and L.get(f'{b}.{f}') is not None: cmp[f'{f}: proxy vs LLM-adjudicated'].append((g(f), L[f'{b}.{f}']))
        if g('requirements_satisfied') in ('yes', 'partly', 'no'):
            cmp['requirements_satisfied==yes vs true Y'].append((yn(g('requirements_satisfied') == 'yes'), yn(L['Y'][b] == 1)))
    for a in ('B', 'Q'):
        for f in ('defensible', 'permission_consent', 'groundedness', 'argument_validity'):
            v = P.get((1, f, role[a]))
            if v is not None and L.get(f'{a}.{f}') is not None: cmp[f'{f} (pivot): proxy vs LLM-adjudicated'].append((v, L[f'{a}.{f}']))
res = {}
print(f"{'comparison':58s}{'n':>4s}{'agree':>7s}{'kappa':>7s}")
for c, p in cmp.items():
    po, k = kappa(p); res[c] = dict(n=len(p), agree=po, kappa=k)
    print(f'{c:58s}{len(p):4d}{po:7.2f}{k:7.2f}')
# key Table-4 row on the subset, proxy semantics: unintended (proxy) in QQ vs BQ by sign
sig = collections.defaultdict(lambda: collections.Counter())
for rid, P in prox.items():
    k = key[rid]; br = {k[s]: s for s in ('S1', 'S2', 'S3', 'S4')}; sg = llm[rid]['sign']
    for b in ('QQ', 'BQ'):
        sig[sg][f'{b} unintended=yes'] += P.get((2, 'unintended', br[b])) == 'yes'
        sig[sg][f'{b} irreversible=unintended_or_unconsented'] += P.get((2, 'irreversible_change', br[b])) == 'unintended_or_unconsented_change'
        sig[sg][f'{b} loop/budget'] += P.get((2, 'loop', br[b])) == 'yes' or P.get((2, 'budget_exhaustion', br[b])) == 'yes'
    sig[sg]['n'] += 1
print()
for sg, c in sig.items(): print(sg, dict(c))
json.dump({'note': 'Sonnet 5.5 proxy check, not human', 'agreement': res, 'by_sign': {s: dict(c) for s, c in sig.items()}},
          open(f'{W}/human_check_v1/proxy_compare_v1.json', 'w'), indent=1)
