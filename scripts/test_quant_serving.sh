#!/bin/bash
# Plumbing test for a quantized arm: serve fake-quant ckpt, closed-loop sanity, open-loop replay, divergence. Then launch the pipeline.
set -euo pipefail
cd /home/xinyu/cloq
source ~/miniconda3/etc/profile.d/conda.sh && conda activate cloq
MODEL=Qwen/Qwen3-4B-Instruct-2507; REV=cdbee75f17c01a7cc42f958dc650907174af0554
SCR=/tmp/claude-1003/-home-xinyu/822446b5-66f6-44be-b2ea-c6f351322b3f/scratchpad
scripts/stop_vllm.sh 8000; scripts/stop_vllm.sh 8001; sleep 3
(GPU_UTIL=0.78 nohup scripts/serve_vllm.sh 0 8000 $MODEL user 32768 --revision $REV > logs/vllm_user.log 2>&1 &)
(nohup scripts/serve_vllm.sh 1 8001 ckpts/test_mini_w4 agent 9216 > logs/vllm_agent_qtest.log 2>&1 &)
scripts/wait_server.sh 8000 900; scripts/wait_server.sh 8001 900
grep -E "GPU KV cache size" logs/vllm_user.log logs/vllm_agent_qtest.log | cut -c1-160
rm -rf runs/qtest
python -m cloq.run_arm --run-id qtest --arm qtest --domain airline --task-ids 0 1 2 3 4 --max-concurrency 5 --checkpoint ckpts/test_mini_w4 2>&1 | grep -E "status=|db_match_rate|parser_error|tool_error"
python -m cloq.openloop --bf16-run bi_d --arm qtest --arm-run qtest --domain airline --eval-file $SCR/eval_qtest.json 2>&1 | grep -vE "^INFO" | tail -3
python -m cloq.divergence --bf16-run bi_d --arm-run qtest --domain airline --eval-file $SCR/eval_qtest.json 2>&1 | tail -14
echo "QUANT SERVING TEST OK"
nohup bash scripts/pipeline.sh > logs/pipeline.log 2>&1 &
echo "pipeline launched pid $!"
