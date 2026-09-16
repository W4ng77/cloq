#!/bin/bash
# wait_server.sh <port> [timeout_s]
PORT=$1; T=${2:-600}; t0=$(date +%s)
while true; do
  if python3 -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:$PORT/v1/models',timeout=3)" 2>/dev/null; then echo "port $PORT up"; exit 0; fi
  if [ $(( $(date +%s) - t0 )) -gt $T ]; then echo "port $PORT TIMEOUT"; exit 1; fi
  sleep 5
done
