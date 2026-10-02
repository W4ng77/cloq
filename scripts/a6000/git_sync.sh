#!/bin/bash
# Periodic GitHub update: small per-run artifacts (no decisions/trajectories, no ckpts) + queue snapshot.
set -uo pipefail
cd /data/ziyangs/cloq
mkdir -p docs/a6000
python3 - <<'PY' > docs/a6000/QUEUE.md
import json, glob, os, time
W='/data/ziyangs/cloq_work/queue'
print(f"# A6000 queue snapshot ({time.strftime('%F %T %Z')})\n")
for d in ('running','failed','done','todo'):
    ts=sorted(glob.glob(f'{W}/{d}/*.json'))
    print(f"## {d} ({len(ts)})\n")
    for f in ts[:200]:
        t=json.load(open(f)); extra=''
        if d=='done': extra=f" · {t.get('seconds',0)/60:.0f} min · {t.get('host','')}"
        if d=='failed': extra=f" · {t.get('error','')[:160]}"
        print(f"- `{t['id']}`{extra}")
    print()
PY
mkdir -p analysis/determinism
git add docs/RESEARCH_LOG.md docs/insights analysis/insights analysis/determinism scripts/a6000 env/README_A6000.md 2>/dev/null
git add -f docs/a6000/QUEUE.md $(ls runs/a6000_*/*/{metrics,status,config,environment,model,task_manifest}.json runs/a6000_*/quantization.json 2>/dev/null) >/dev/null 2>&1
git diff --cached --quiet && { echo "nothing new"; exit 0; }
git commit -q -m "A6000 progress $(date '+%F %H:%M'): $(ls /data/ziyangs/cloq_work/queue/done | wc -l) tasks done

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git pull -q --rebase --autostash origin master && git push -q origin master && git log --oneline -1
