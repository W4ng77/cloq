#!/bin/bash
# One CLOQ runner job per node. Submit with an explicit node and GPU count, e.g.
#   sbatch -w node003 --gres=gpu:A6000:8 -c 32 scripts/a6000/node.sbatch --sim-gpus 0,1 --sim-model q30a3
#SBATCH -J cloq-node -p defq -N1 -t 3-00:00:00
#SBATCH -o /data/ziyangs/cloq_work/logs/node_%N_%j.out
source /data/ziyangs/cloq/scripts/a6000/env.sh
cd $CLOQ_ROOT
LIMIT=$(squeue -j $SLURM_JOB_ID -h -o %L | awk -F'[-:]' '{ if (NF==4) print $1*86400+$2*3600+$3*60+$4; else if (NF==3) print $1*3600+$2*60+$3; else print $1*60+$2 }')
export CLOQ_JOB_END=$(( $(date +%s) + LIMIT ))
# Probe each allocated GPU; a card whose NVML handle fails (node003 01:00.0, node009) is left out entirely.
GOOD=""; for i in $(nvidia-smi -L 2>/dev/null | sed -n 's/^GPU \([0-9]*\):.*/\1/p'); do
  if timeout 20 nvidia-smi -i $i --query-gpu=index,pci.bus_id,name --format=csv,noheader >/dev/null 2>&1 && \
     CUDA_VISIBLE_DEVICES=$i timeout 60 python -c "import torch;x=torch.ones(1024,1024,device='cuda');assert float((x@x).sum())==1024**3" 2>/dev/null; then
    GOOD="$GOOD,$i"; else echo "GPU $i FAILED probe: $(nvidia-smi -i $i --query-gpu=pci.bus_id --format=csv,noheader 2>&1 | head -1)"; fi
done
GPUS=${GOOD#,}  # physical indices; serve.sh exposes only its own cards, so a bad card never reaches vLLM
echo "node $(hostname) job $SLURM_JOB_ID gpus $GPUS cpus $SLURM_CPUS_PER_TASK end $(date -d @$CLOQ_JOB_END)"
nvidia-smi --query-gpu=index,name,memory.used,memory.total,temperature.gpu --format=csv
exec python scripts/a6000/noderunner.py --gpus $GPUS "$@"
