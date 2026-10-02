#!/bin/bash
# CLOQ unattended autopilot (login node), default 10 h. Infra upkeep only; never kills jobs, never starts new
# experiment lines, never edits manifests/paper. Log: /data/ziyangs/cloq_work/logs/autopilot.log
#   setsid nohup scripts/a6000/autopilot.sh [hours] >/dev/null 2>&1 &
# Every 5 min:
#  1. runner upkeep: a node with no job of ours (running or pending), >=4 free GPUs and >=16 free CPUs, while todo/
#     is non-empty -> sbatch one runner there (one per node: the epilog kills same-user co-located jobs).
#  2. node008 restart: once the draining old runner (job in $DRAIN_JOB) has exited, remove DRAIN.node008 so (1)
#     resubmits it on the current noderunner.py (needed for 4-GPU m24 forks).
#  3. failed tasks: retry ONCE a task whose error looks infrastructural (outage / rc= / timeout / CUDA / OOM /
#     connection), with a note; anything else, or a second failure, is left in failed/ for a human.
#  4. every 30 min: board_sync.py (local snapshot) + git_sync.sh (queue snapshot to GitHub).
set -uo pipefail
HOURS=${1:-10}
END=$(( $(date +%s) + HOURS*3600 ))
ROOT=/data/ziyangs/cloq; Q=/data/ziyangs/cloq_work/queue; LOG=/data/ziyangs/cloq_work/logs/autopilot.log
NODES="node001 node002 node004 node005 node006 node007 node008"
DRAIN_JOB=${DRAIN_JOB:-49861}
cd $ROOT
log(){ echo "[$(date '+%F %T')] $*" >> $LOG; }
log "start: ${HOURS} h, nodes $NODES, drain job $DRAIN_JOB"
i=0
while [ "$(date +%s)" -lt "$END" ]; do
  # 2. node008 drain release
  if [ -f $Q/DRAIN.node008 ] && ! squeue -j $DRAIN_JOB -h 2>/dev/null | grep -q .; then
    rm -f $Q/DRAIN.node008; log "node008: old runner $DRAIN_JOB gone, drain removed"
  fi
  # 1. runner upkeep
  ntodo=$(ls $Q/todo | wc -l)
  if [ "$ntodo" -gt 0 ]; then
    for n in $NODES; do
      squeue -u ziyangs -h -o "%N %R" | grep -qw "$n" && continue      # running on n
      for j in $(squeue -u ziyangs -h -t PD -o "%i"); do scontrol show job $j | grep -oP "ReqNodeList=\K\S+" | grep -qw "$n" && continue 2; done  # pending pinned to n
      [ "$n" = node008 ] && [ -f $Q/DRAIN.node008 ] && continue
      info=$(scontrol show node $n 2>/dev/null)
      echo "$info" | grep -qE "State=(DOWN|DRAIN|FAIL)" && continue
      ctot=$(echo "$info" | grep -oP 'CPUTot=\K[0-9]+'); calloc=$(echo "$info" | grep -oP 'CPUAlloc=\K[0-9]+')
      galloc=$(echo "$info" | grep -oP 'AllocTRES=.*gres/gpu[^=]*=\K[0-9]+' | head -1); galloc=${galloc:-0}
      gfree=$(( 8 - galloc )); cfree=$(( ctot - calloc ))
      if [ "$gfree" -ge 4 ] && [ "$cfree" -ge 16 ]; then
        c=16; [ "$cfree" -ge 32 ] && c=32
        out=$(sbatch -w $n --gres=gpu:A6000:$gfree -c $c scripts/a6000/node.sbatch --sim-gpus 0,1 --sim-model q30a3 2>&1)
        log "runner $n: gpus $gfree cpus $c -> $out"
      fi
    done
  fi
  # 3. one-shot infra retries
  for f in $Q/failed/*.json; do
    [ -e "$f" ] || continue
    python3 - "$f" "$Q" <<'PY' >> $LOG 2>&1
import json, os, re, sys, time
f, Q = sys.argv[1], sys.argv[2]
d = json.load(open(f)); b = os.path.basename(f)
if b.startswith(("a6k2_smoke", "ext_l8_")) or d.get("autopilot_retry"):
    sys.exit()
err = str(d.get("error", ""))
if re.search(r"outage|rc=|[Tt]imeout|CUDA|out of memory|OOM|[Cc]onnection|ECONN|server", err):
    d["autopilot_retry"] = time.strftime("%F %T")
    d["requeue_note"] = (d.get("requeue_note", "") + f" | autopilot retry once ({err[:120]})").strip(" |")
    json.dump(d, open(f"{Q}/todo/{b}.tmp", "w"), indent=1); os.replace(f"{Q}/todo/{b}.tmp", f"{Q}/todo/{b}"); os.remove(f)
    print(f"[{time.strftime('%F %T')}] retry {b}: {err[:160]}")
PY
  done
  # 4. snapshots
  if [ $(( i % 6 )) -eq 0 ]; then
    timeout 300 python3 scripts/a6000/board_sync.py >/dev/null 2>&1 && log "board: $(python3 -c "import json;print(json.load(open('/data/ziyangs/cloq_work/board/cluster.json'))['note'])")"
    timeout 600 bash scripts/a6000/git_sync.sh >/dev/null 2>&1 || log "git_sync failed (non-fatal)"
  fi
  i=$((i+1)); sleep 300
done
log "end after ${HOURS} h"
