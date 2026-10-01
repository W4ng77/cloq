#!/bin/bash
cd /data/ziyangs/cloq
S=/tmp/claude-1064/-home-ziyangs/4a7ccb09-009e-4aee-b4c9-ef93691bb496/scratchpad
PY=/data/ziyangs/cloq_work/envs/cloq/bin/python
DRY=/data/ziyangs/cloq_work/simrelay_dry_p
rm -rf $DRY analysis/fork/simctrl_p/dry; mkdir -p $DRY
$PY tests/mock_anthropic.py --port 18871 --log $S/mockB.jsonl & P1=$!
$PY tests/mock_anthropic.py --port 18872 --log $S/mockQ.jsonl --agent-stop & P2=$!
CLOQ_SIMRELAY_DIR=$DRY $PY scripts/a6000/simrelay_cli.py --mock --concurrency 12 --mock-stop-after 3 --mock-delay 0.1 --exit-when-idle 120 --log $DRY/cli.log --quiet & P3=$!
sleep 2
CLOQ_SIMRELAY_DIR=$DRY CLOQ_SIMRELAY_TIMEOUT_S=300 timeout 900 $PY scripts/a6000/fork_driver.py --task $S/dry_task.json --b-base http://127.0.0.1:18871/v1 --q-base http://127.0.0.1:18872/v1 --user-base http://127.0.0.1:9/v1 > $S/dry.out 2> $S/dry.err; echo rc=$?
kill $P1 $P2 $P3
tail -2 $S/dry.out
