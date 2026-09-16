#!/bin/bash
# CLOQ environment: python 3.12, vllm 0.29.0 (pins torch 2.13.0), tau2-bench 1.0.1 (editable), analysis libs.
set -euo pipefail
source ~/miniconda3/etc/profile.d/conda.sh
conda create -y -n cloq python=3.12
conda activate cloq
pip install --upgrade pip
pip install "vllm==0.29.0"
pip install -e /home/xinyu/cloq/third_party/tau2-bench
pip install scipy matplotlib scikit-learn pandas pyarrow safetensors accelerate
pip list | grep -iE "^(vllm|torch|transformers|litellm|tau2|numpy|scipy|flashinfer|tokenizers)"
python -c "import torch,vllm,transformers,tau2;print(torch.__version__,vllm.__version__,transformers.__version__,torch.cuda.is_available())"
