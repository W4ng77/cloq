"""Loaded only when CLOQ_PYHOOKS=1 (env.sh puts this dir on PYTHONPATH). X1 FP8 serving, docs/RESEARCH_LOG.md W7.

vLLM 0.29 serves block-FP8 on Ampere with the Humming weight-only kernel. Humming picks its (deterministic, spec-based)
tile heuristics from NVML device *index 0*, ignoring CUDA_VISIBLE_DEVICES; on node003 NVML index 0 is a faulty card
(NVMLError_Unknown), so the server died. Remap logical CUDA index i -> NVML index CUDA_VISIBLE_DEVICES[i] inside
humming.utils.device only (in these Slurm jobs nvidia-smi/NVML indices equal the job-local CUDA indices; worker.gpu_pids
relies on the same). All cards are A6000s, so the heuristics are identical on every node.

With CLOQ_KVQ_BITS set as well, also wraps vLLM's Attention.forward for fake KV-cache quantization (cloq_kvq.py, W13).
"""
import importlib.abc
import importlib.machinery
import os
import sys


class _Proxy:
    def __init__(self, mod):
        self._m = mod

    def __getattr__(self, k):
        return getattr(self._m, k)

    def nvmlDeviceGetHandleByIndex(self, i):
        vis = [x for x in os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",") if x.strip()]
        if vis and all(x.strip().isdigit() for x in vis) and i < len(vis):
            i = int(vis[i])
        return self._m.nvmlDeviceGetHandleByIndex(i)


_KVQ_MOD = "vllm.model_executor.layers.attention.attention"


def _patch_humming(module):
    module.pynvml = _Proxy(module.pynvml)


def _patch_kvq(module):
    import cloq_kvq
    cloq_kvq.install(module)


_PATCHES = {"humming.utils.device": _patch_humming}
if os.environ.get("CLOQ_KVQ_BITS"):
    _PATCHES[_KVQ_MOD] = _patch_kvq


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        patch = _PATCHES.get(name)
        if patch is None:
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is None or spec.loader is None:
            return spec
        orig = spec.loader.exec_module

        def exec_module(module):
            orig(module)
            patch(module)

        spec.loader.exec_module = exec_module
        return spec


if os.environ.get("CLOQ_PYHOOKS") == "1":
    if os.environ.get("CLOQ_KVQ_BITS"):
        import cloq_kvq
        cloq_kvq.isolate_cache_root()  # before vllm.envs is read, in every process of the server
    sys.meta_path.insert(0, _Finder())
