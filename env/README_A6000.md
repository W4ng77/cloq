# A6000 environment (Ohio HPC, 2026-09-28)

Driver 550.144 (CUDA 12.4) on every node, so the repo's torch 2.13.0+cu130 / vLLM 0.29.0 (cu130) cannot run.
Built instead (scripts in /data/ziyangs/cloq_work/build_env.sh): python 3.12 (conda-forge), torch 2.13.0+cu129,
vLLM 0.29.0+cu129 (GitHub release wheel), transformers 5.17.0, litellm 1.82.6, numpy 2.3.5, tau2 1.0.1 @ 2174a60 —
identical to env/freeze_4080.txt except the CUDA build. A6000 results are a separate replication (plan rule 1).

Local patches (no numerical effect):
- vllm/platforms/cuda.py `log_warnings`: tolerate NVML errors from dead cards elsewhere on the node (node003 has two);
  the function only prints a mixed-device warning.
- scripts/a6000/env.sh preloads the env's libstdc++ (node /lib64 copy lacks CXXABI_1.3.15) and unsets the module
  LD_LIBRARY_PATH.
