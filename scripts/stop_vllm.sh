#!/bin/bash
# stop_vllm.sh <port> : stop the vLLM server started by serve_vllm.sh on that port (via pid file), wait for GPU release
PORT=$1; PF=/home/xinyu/cloq/logs/vllm_port${PORT}.pid
if [ -f "$PF" ]; then PID=$(cat "$PF"); kill "$PID" 2>/dev/null; for i in $(seq 1 60); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done; kill -9 "$PID" 2>/dev/null; rm -f "$PF"; fi
# also kill orphaned engine cores bound to this port's parent (they die with parent normally)
sleep 3; echo "stopped port $PORT"
