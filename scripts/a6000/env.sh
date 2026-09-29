# Source from every A6000 script: the cloq env, caches under /data, node-local scratch.
export CLOQ_ROOT=/data/ziyangs/cloq
export CLOQ_WORK=/data/ziyangs/cloq_work
export PATH=$CLOQ_WORK/envs/cloq/bin:$PATH
unset LD_LIBRARY_PATH  # the module gcc-12 libstdc++ is too old for the conda env
export LD_PRELOAD=$CLOQ_WORK/envs/cloq/lib/libstdc++.so.6  # node /lib64 libstdc++ lacks CXXABI_1.3.15; newer one is backward compatible
export HF_HOME=$CLOQ_WORK/hf HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export TMPDIR=${SLURM_TMPDIR:-/tmp}/cloq_${SLURM_JOB_ID:-login}; mkdir -p "$TMPDIR"
export PYTHONUNBUFFERED=1 PYTHONPATH=$CLOQ_ROOT
# Frozen numerics (docs/A6000_PLAN.md rule 6).
export VLLM_BATCH_INVARIANT=${CLOQ_BATCH_INVARIANT:-1} VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_CACHE_ROOT=$TMPDIR/vllm_cache
snapshot() { ls -d $HF_HOME/hub/models--${1//\//--}/snapshots/$2 2>/dev/null; }
