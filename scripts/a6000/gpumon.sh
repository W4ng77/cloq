#!/bin/bash
# Per-node sampler (runs as an overlap step inside the node's runner job): every 30 s append one JSON line with
# per-GPU util/mem/power/SM clock and, for every local vLLM server (ports 8000-8010 plus every simulator port this node
# has in the instance registry /data/ziyangs/cloq_work/sims/<node>-<port>.json, W34-infra), running/waiting requests,
# KV-cache usage and cumulative prompt/generation tokens; registered simulator ports carry "sim":1.
# Output: /data/ziyangs/cloq_work/gpumon/<node>.jsonl
NODE=$(hostname -s)
OUT=/data/ziyangs/cloq_work/gpumon/$NODE.jsonl
SIMS=/data/ziyangs/cloq_work/sims
while true; do
  ts=$(date +%s)
  gpus=$(nvidia-smi --query-gpu=index,utilization.gpu,memory.used,power.draw,clocks.sm --format=csv,noheader,nounits 2>/dev/null \
         | grep -E "^[0-9]" | awk -F', ' '{printf "%s{\"i\":%s,\"util\":%s,\"mem\":%s,\"pw\":%s,\"clk\":%s}", (NR>1?",":""), $1,$2,$3,$4,$5}')
  simports=$(ls $SIMS/$NODE-*.json 2>/dev/null | sed -n "s|.*/$NODE-\([0-9]*\)\.json|\1|p" | sort -n | tr '\n' ' ')
  srv=""
  for p in $(echo $(seq 8000 8010) $simports | tr ' ' '\n' | sort -nu); do
    m=$(curl -s --max-time 2 localhost:$p/metrics) || continue
    [ -z "$m" ] && continue
    r=$(awk '/^vllm:num_requests_running[ {]/{v=$NF} END{print v+0}' <<<"$m")
    w=$(awk '/^vllm:num_requests_waiting[ {]/{v=$NF} END{print v+0}' <<<"$m")
    kv=$(awk '/^vllm:kv_cache_usage_perc[ {]/{v=$NF} END{print v+0}' <<<"$m")
    pt=$(awk '/^vllm:prompt_tokens_total[ {]/{v=$NF} END{print v+0}' <<<"$m")
    gt=$(awk '/^vllm:generation_tokens_total[ {]/{v=$NF} END{print v+0}' <<<"$m")
    sim=0; [[ " $simports " == *" $p "* ]] && sim=1
    srv="$srv${srv:+,}{\"port\":$p,\"sim\":$sim,\"run\":$r,\"wait\":$w,\"kv\":$kv,\"ptok\":$pt,\"gtok\":$gt}"
  done
  echo "{\"ts\":$ts,\"gpus\":[${gpus}],\"srv\":[${srv}]}" >> "$OUT"
  sleep 30
done
