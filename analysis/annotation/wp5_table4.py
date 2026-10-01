"""WP5 Table 4 (post-unblinding, Amendment 1): Sonnet 5.5 adjudicated labels and programmatic labels joined to branch
roles and consequence sign.

Final LLM label = R3 adjudication where R1/R2 disagreed on a double state, else the (agreeing or single) reviewer.
Programmatic labels come from analysis/annotation/wp5_verify.py (programmatic_v1.jsonl; run it first).

v2 (W79, GPT-6.1 review) changes vs v1 (table4_v1.json, W75, kept unchanged in git):
  * the rubric category keeps its own name, `unintended_or_unconsented_change` ("unintended or unconsented change");
    v1 called it "unconsented irreversible write". The mechanical parts are reported separately: "write executed" and
    "executed write without recorded operation-specific consent" (programmatic); "unintended" stays an LLM judgement.
  * QQ vs BQ (and Q vs B action) are compared WITHIN the same state: paired 2x2 counts, McNemar exact p on the
    discordant pairs, the paired difference with a Newcombe (1998, method 10) score interval and a task-clustered
    bootstrap interval (clusters = (domain, task_id); resampled within sign). No independent-proportion tests.
  * single proportions get Wilson 95% intervals.
  * tool_validity (R1/R2 kappa 0.29) is out of the core rows: the core "local defect" uses groundedness,
    argument_validity and permission_consent only. The tool_validity rows and the v1 composite are in the appendix.
  * the signs are outcome-defined groups (Y_BQ vs Y_QQ). Everything here describes the process conditional on those
    groups; it is not causal evidence and frequencies are sample composition, not prevalences (protocol section 1).

usage: python analysis/annotation/wp5_table4.py          -> table4_v2.json, table4_v2.md
       python analysis/annotation/wp5_table4.py --v1     -> regenerates table4_v1.json (W75 definitions)
"""
import collections
import json
import math
import random
import sys

W = 'analysis/annotation/wp5'
KEYP = '/data/ziyangs/cloq_work/annotation/wp5_KEY_unblinding.jsonl'
ORDER = ['BB', 'BQ', 'QB', 'QQ']
SIGNS = ['rescue', 'damage', 'both_succeed', 'both_fail']
UUC = 'unintended_or_unconsented_change'
B_REPS, SEED = 10000, 0


def load_rows():
    key = {json.loads(l)['review_id']: json.loads(l) for l in open(KEYP)}
    samp = {u['review_id']: u for u in json.load(open('manifests/annotation/wp5_sample_v1.json'))['units']}
    lab = collections.defaultdict(dict)
    for R in ('R2', 'R1'):  # R1 last: on agreeing double states identical anyway
        for l in open(f'{W}/labels_{R}.jsonl'):
            x = json.loads(l)
            for f, sl in x['labels'].items():
                for s, v in (sl or {}).items():
                    if isinstance(v, dict):
                        lab[x['review_id']][(x['pass'], f, s)] = str(v.get('value'))
    for l in open(f'{W}/adjudication_R3.jsonl'):
        a = json.loads(l)
        lab[a['review_id']][(a['pass'], a['field'], a['slot'])] = str(a['final'])
    rows = []
    for rid, u in samp.items():
        k = key[rid]
        L = lab[rid]
        role = {k['X']: 'X', k['Y']: 'Y'}
        sl = {k[s]: s for s in ('S1', 'S2', 'S3', 'S4')}
        Y = dict(zip(ORDER, map(int, u['pattern'])))
        r = {'rid': rid, 'sign': u['sign'], 'family': u['family'], 'domain': u['domain'], 'task_id': u['task_id'], 'Y': Y}
        for a in ('B', 'Q'):
            for f in ('defensible', 'groundedness', 'tool_validity', 'argument_validity', 'permission_consent', 'goal_relevance'):
                r[f'{a}.{f}'] = L.get((1, f, role[a]))
        r['both_defensible'] = L.get((1, 'both_defensible', 'state'))
        r['state_ambiguity'] = L.get((1, 'state_ambiguity', 'state'))
        for b in ORDER:
            for f in ('requirements_satisfied', 'irreversible_change', 'loop', 'budget_exhaustion', 'defect_corrected', 'retries',
                      'user_clarification'):
                r[f'{b}.{f}'] = L.get((2, f, sl[b]))
        rows.append(r)
    return rows


def defect(r, a, with_tool=False):
    d = (r[f'{a}.groundedness'] in ('partly_grounded', 'ungrounded')
         or r[f'{a}.argument_validity'] in ('wrong_id', 'wrong_value', 'missing_or_extra')
         or r[f'{a}.permission_consent'] == 'write_without_consent')
    if with_tool:
        d = d or r[f'{a}.tool_validity'] in ('wrong_tool', 'no_tool_needed_but_called', 'tool_needed_but_talked')
    return d


# ---------------------------------------------------------------- intervals
Z = 1.959963984540054


def wilson(k, n):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / den
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe_paired(a, b, c, d):
    """Newcombe (1998) method 10: score CI for p1 - p2 with paired data. a=both, b=first only, c=second only, d=neither."""
    n = a + b + c + d
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n)
    l2, u2 = wilson(a + c, n)
    den = (a + b) * (c + d) * (a + c) * (b + d)
    phi = (a * d - b * c) / math.sqrt(den) if den else 0.0
    D = p1 - p2
    lo = D - math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    hi = D + math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return (max(-1.0, lo), min(1.0, hi))


def mcnemar_exact(b, c):
    m = b + c
    if m == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(m, i) for i in range(k + 1)) / 2 ** m)


def cluster_boot_diff(rs, f1, f2, seed=SEED, reps=B_REPS):
    cl = collections.defaultdict(list)
    for r in rs:
        cl[(r['domain'], r['task_id'])].append(r)
    keys = sorted(cl)
    rng = random.Random(seed)
    ds = []
    for _ in range(reps):
        smp = [r for kk in (rng.choice(keys) for _ in keys) for r in cl[kk]]
        ds.append(sum(f1(r) - f2(r) for r in smp) / len(smp))
    ds.sort()
    return (ds[int(0.025 * reps)], ds[int(0.975 * reps) - 1])


def paired(rs, f1, f2):
    a = sum(1 for r in rs if f1(r) and f2(r))
    b = sum(1 for r in rs if f1(r) and not f2(r))
    c = sum(1 for r in rs if not f1(r) and f2(r))
    d = len(rs) - a - b - c
    n = len(rs)
    return {'n': n, 'first': a + b, 'second': a + c, 'both': a, 'first_only': b, 'second_only': c, 'neither': d,
            'diff': (b - c) / n, 'newcombe95': newcombe_paired(a, b, c, d), 'cluster_boot95': cluster_boot_diff(rs, f1, f2),
            'mcnemar_exact_p': mcnemar_exact(b, c)}


def single(rs, f):
    k = sum(1 for r in rs if f(r))
    return {'k': k, 'n': len(rs), 'wilson95': wilson(k, len(rs))}


# ---------------------------------------------------------------- v1 (W75) for reproducibility
def v1(rows):
    T = collections.OrderedDict()
    T['Q action defensible = no'] = lambda r: r['Q.defensible'] == 'no'
    T['B action defensible = no'] = lambda r: r['B.defensible'] == 'no'
    T['Q action has a local defect'] = lambda r: defect(r, 'Q', True)
    T['B action has a local defect'] = lambda r: defect(r, 'B', True)
    T['Q write without consent'] = lambda r: r['Q.permission_consent'] == 'write_without_consent'
    T['Q works against goal'] = lambda r: r['Q.goal_relevance'] == 'works_against_goal'
    T['both actions defensible'] = lambda r: r['both_defensible'] == 'yes'
    T['state ambiguous'] = lambda r: r['state_ambiguity'] == 'ambiguous'
    T['QQ: unconsented irreversible change'] = lambda r: r['QQ.irreversible_change'] == UUC
    T['BQ: unconsented irreversible change'] = lambda r: r['BQ.irreversible_change'] == UUC
    T['QQ: first-action defect corrected later'] = lambda r: r['QQ.defect_corrected'] == 'corrected'
    T['QQ: first-action defect NOT corrected'] = lambda r: r['QQ.defect_corrected'] == 'not_corrected'
    T['QQ: loop or budget exhaustion'] = lambda r: r['QQ.loop'] == 'yes' or r['QQ.budget_exhaustion'] == 'yes'
    T['BQ: loop or budget exhaustion'] = lambda r: r['BQ.loop'] == 'yes' or r['BQ.budget_exhaustion'] == 'yes'
    out = {s: {name: f"{sum(1 for r in rows if r['sign'] == s and p(r))}/{sum(1 for r in rows if r['sign'] == s)}"
               for name, p in T.items()} for s in SIGNS}
    vc = collections.Counter((r[f'{b}.requirements_satisfied'], r['Y'][b]) for r in rows for b in ORDER)
    json.dump({'table4': out, 'requirements_vs_Y': {f'{a}|Y={y}': n for (a, y), n in sorted(vc.items(), key=str)}, 'rows': rows},
              open(f'{W}/table4_v1.json', 'w'), indent=1, default=str)


# ---------------------------------------------------------------- v2
def main_v2(rows):
    prog = {}
    for l in open(f'{W}/programmatic_v1.jsonl'):
        x = json.loads(l)
        prog[x['review_id']] = x
    for r in rows:
        p = prog[r['rid']]
        for b in ORDER:
            g = p['branches'][b]
            for f in ('write_executed', 'unconsented_write', 'budget_exhaustion', 'loop_proxy', 'repeated_same_call'):
                r[f'{b}.prog.{f}'] = g[f]
        for a in ('B', 'Q'):
            r[f'{a}.prog.permission_consent'] = p['actions'][a]['permission_consent']
            r[f'{a}.prog.exec_error'] = p['actions'][a]['exec_error']
    is_ = lambda f, v: (lambda r: r[f] == v)  # noqa: E731
    lb = lambda b: (lambda r: r[f'{b}.loop'] == 'yes' or r[f'{b}.budget_exhaustion'] == 'yes')  # noqa: E731
    PAIRED = [
        ('unintended_or_unconsented_change (LLM)', 'LLM', is_('QQ.irreversible_change', UUC), is_('BQ.irreversible_change', UUC), 'QQ', 'BQ'),
        ('write executed (programmatic)', 'prog', lambda r: r['QQ.prog.write_executed'], lambda r: r['BQ.prog.write_executed'], 'QQ', 'BQ'),
        ('executed write without recorded operation-specific consent (programmatic)', 'prog',
         lambda r: r['QQ.prog.unconsented_write'], lambda r: r['BQ.prog.unconsented_write'], 'QQ', 'BQ'),
        ('loop or budget exhaustion (LLM)', 'LLM', lb('QQ'), lb('BQ'), 'QQ', 'BQ'),
        ('budget exhaustion (programmatic: max_steps / too_many_errors)', 'prog',
         lambda r: r['QQ.prog.budget_exhaustion'], lambda r: r['BQ.prog.budget_exhaustion'], 'QQ', 'BQ'),
        ('action judged indefensible (LLM)', 'LLM', is_('Q.defensible', 'no'), is_('B.defensible', 'no'), 'Q action', 'B action'),
        ('action has a local defect, core (LLM; groundedness/argument/consent)', 'LLM',
         lambda r: defect(r, 'Q'), lambda r: defect(r, 'B'), 'Q action', 'B action'),
    ]
    SINGLE = [
        ('QQ: first-action defect corrected later (LLM)', 'LLM', is_('QQ.defect_corrected', 'corrected')),
        ('QQ: first-action defect not corrected (LLM)', 'LLM', is_('QQ.defect_corrected', 'not_corrected')),
        ('QB: first-action defect corrected later (LLM)', 'LLM', is_('QB.defect_corrected', 'corrected')),
        ('QQ: UUC (LLM) although every executed write has recorded consent (programmatic) = the "unintended" part', 'LLM+prog',
         lambda r: r['QQ.irreversible_change'] == UUC and r['QQ.prog.write_executed'] and not r['QQ.prog.unconsented_write']),
        ('BQ: UUC (LLM) although every executed write has recorded consent (programmatic) = the "unintended" part', 'LLM+prog',
         lambda r: r['BQ.irreversible_change'] == UUC and r['BQ.prog.write_executed'] and not r['BQ.prog.unconsented_write']),
    ]
    APPX_PAIRED = [
        ('APPENDIX tool_validity != valid (LLM; kappa 0.29)', 'LLM',
         lambda r: r['Q.tool_validity'] not in ('valid', 'n/a', 'unknown', None),
         lambda r: r['B.tool_validity'] not in ('valid', 'n/a', 'unknown', None), 'Q action', 'B action'),
        ('APPENDIX local defect incl. tool_validity (v1 composite)', 'LLM',
         lambda r: defect(r, 'Q', True), lambda r: defect(r, 'B', True), 'Q action', 'B action'),
    ]
    res = {'paired': {}, 'single': {}, 'appendix_paired': {}}
    for tgt, spec in (('paired', PAIRED), ('appendix_paired', APPX_PAIRED)):
        for name, src, f1, f2, n1, n2 in spec:
            res[tgt][name] = {'source': src, 'first': n1, 'second': n2,
                              **{s: paired([r for r in rows if r['sign'] == s], f1, f2) for s in SIGNS}}
    for name, src, f in SINGLE:
        res['single'][name] = {'source': src, **{s: single([r for r in rows if r['sign'] == s], f) for s in SIGNS}}
    vc = collections.Counter((r[f'{b}.requirements_satisfied'], r['Y'][b]) for r in rows for b in ORDER)
    note = ("Signs are outcome-defined groups (rescue: Y_BQ=1,Y_QQ=0; damage: Y_BQ=0,Y_QQ=1). All numbers describe the process "
            "conditional on those groups (n=20 each, stratified sample, LLM-annotated by Sonnet 5.5 R1/R2+R3 plus rule-based "
            "programmatic labels); they are not causal evidence and not prevalences. Paired = within the same state. "
            "'unintended' is a semantic LLM judgement and is kept apart from 'write executed' and 'consent recorded'.")
    out = {'version': 'table4-v2', 'note': note, 'bootstrap': {'reps': B_REPS, 'seed': SEED, 'cluster': '(domain, task_id) within sign'},
           **res, 'requirements_vs_Y': {f'{a}|Y={y}': n for (a, y), n in sorted(vc.items(), key=str)}, 'rows': rows}
    json.dump(out, open(f'{W}/table4_v2.json', 'w'), indent=1, default=str)
    write_md(out)


def fmt_ci(ci, pct=False):
    if ci[0] is None:
        return 'n/a'
    return f'[{ci[0]:+.2f}, {ci[1]:+.2f}]' if not pct else f'[{ci[0]:.2f}, {ci[1]:.2f}]'


def write_md(out):
    L = ['# WP5 Table 4 v2 (W79): within-state paired comparisons; LLM-annotated (Sonnet 5.5, two independent instances + R3) '
         'and programmatic labels', '', f"> {out['note']}", '',
         'Generated by `analysis/annotation/wp5_table4.py` → `table4_v2.json` (programmatic labels: `programmatic_v1.jsonl`, '
         'from `wp5_verify.py`).', '',
         '## Core: QQ vs BQ continuation, and Q vs B action, within the same state', '',
         'Columns: counts of first vs second (n = 20 states per sign); discordant pairs `first-only:second-only`; paired '
         'difference (first − second) with a Newcombe score 95% CI and a task-clustered bootstrap 95% CI; McNemar exact p on '
         'the discordant pairs (descriptive only).', '']
    for tgt, title in (('paired', None), ('appendix_paired', '## Appendix (not used for conclusions): tool_validity, κ = 0.29')):
        if title:
            L += ['', title, '']
        L += ['| label | first vs second | sign | counts | discordant | diff | Newcombe 95% | cluster-boot 95% | McNemar p |',
              '|---|---|---|---|---|---|---|---|---|']
        for name, d in out[tgt].items():
            for s in SIGNS:
                x = d[s]
                L.append(f"| {name} | {d['first']} vs {d['second']} | {s} | {x['first']}/{x['n']} vs {x['second']}/{x['n']} | "
                         f"{x['first_only']}:{x['second_only']} | {x['diff']:+.2f} | {fmt_ci(x['newcombe95'])} | "
                         f"{fmt_ci(x['cluster_boot95'])} | {x['mcnemar_exact_p']:.3f} |")
    L += ['', '## Single-branch rows (Wilson 95%)', '', '| label | ' + ' | '.join(SIGNS) + ' |', '|---|---|---|---|---|']
    for name, d in out['single'].items():
        L.append(f"| {name} | " + ' | '.join(f"{d[s]['k']}/{d[s]['n']} {fmt_ci(d[s]['wilson95'], True)}" for s in SIGNS) + ' |')
    L += ['', '## Reading (W79 wording)', '',
          '- Local defects and final failure do not correspond one-to-one; some successful continuations contain later corrections.',
          '- Within rescue and damage states, the failing continuation carries the `unintended_or_unconsented_change` label more '
          'often than the succeeding continuation of the same state (paired rows above). This describes how failing branches look '
          'given outcome-defined groups; it is not a cause of the sign.']
    P = out['paired']
    we, uw = P['write executed (programmatic)'], P['executed write without recorded operation-specific consent (programmatic)']
    S = out['single']
    sq = S['QQ: UUC (LLM) although every executed write has recorded consent (programmatic) = the "unintended" part']
    sb = S['BQ: UUC (LLM) although every executed write has recorded consent (programmatic) = the "unintended" part']
    L += [f"- Mechanically, whether a write executes does not separate the branches (rescue QQ vs BQ {we['rescue']['first']} vs "
          f"{we['rescue']['second']}; damage {we['damage']['first']} vs {we['damage']['second']}). Executed writes without recorded "
          f"operation-specific consent: rescue {uw['rescue']['first']} vs {uw['rescue']['second']} (diff {uw['rescue']['diff']:+.2f}, "
          f"Newcombe {fmt_ci(uw['rescue']['newcombe95'])}), damage {uw['damage']['first']} vs {uw['damage']['second']}. In damage "
          f"states the BQ `unintended_or_unconsented_change` labels are mostly on writes WITH recorded consent "
          f"({sb['damage']['k']}/{uw['damage']['n']} states), i.e. the semantic 'unintended' part (consented but wrong change), "
          f"which overlaps with the DB-based outcome by construction (rescue QQ: {sq['rescue']['k']}/20).", '']
    open(f'{W}/table4_v2.md', 'w').write('\n'.join(L) + '\n')
    for name, d in out['paired'].items():
        print(name)
        for s in SIGNS:
            x = d[s]
            print(f"   {s:13s} {x['first']:2d} vs {x['second']:2d}  disc {x['first_only']}:{x['second_only']}  diff {x['diff']:+.2f} "
                  f"N{fmt_ci(x['newcombe95'])} B{fmt_ci(x['cluster_boot95'])} p={x['mcnemar_exact_p']:.4f}")
    for name, d in out['single'].items():
        print(name, {s: f"{d[s]['k']}/{d[s]['n']}" for s in SIGNS})


if __name__ == '__main__':
    rows = load_rows()
    if '--v1' in sys.argv:
        v1(rows)
    else:
        main_v2(rows)
