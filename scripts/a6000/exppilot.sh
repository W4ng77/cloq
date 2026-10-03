#!/bin/bash
# Experiment pilot launcher (W100r; scripts/a6000/EXPPILOT.md). Login node, default 12 h:
#   setsid nohup scripts/a6000/exppilot.sh [hours] [--until 2026-10-04T13:00-07:00] >/dev/null 2>&1 &
# The start line of the log lists the scheduled duties that fall after the end (NOT covered).
# Stop: touch /data/ziyangs/cloq_work/queue/EXPPILOT_STOP (remove it before the next start).
# Log: /data/ziyangs/cloq_work/logs/exppilot.log (stdout/stderr of the process: logs/exppilot.out).
cd /data/ziyangs/cloq || exit 1
exec nice -n 5 python3 scripts/a6000/exppilot.py --hours "${1:-12}" "${@:2}" >> /data/ziyangs/cloq_work/logs/exppilot.out 2>&1
