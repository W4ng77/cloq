"""Loaded only when CLOQ_PYHOOKS=1 (env.sh puts this dir on PYTHONPATH). X1 FP8 serving, docs/RESEARCH_LOG.md W7.

vLLM 0.29 serves block-FP8 on Ampere with the Humming weight-only kernel. Humming picks its (deterministic, spec-based)
tile heuristics from NVML device *index 0*, ignoring CUDA_VISIBLE_DEVICES; on node003 NVML index 0 is a faulty card
(NVMLError_Unknown), so the server died. Remap logical CUDA index i -> NVML index CUDA_VISIBLE_DEVICES[i] inside
humming.utils.device only (in these Slurm jobs nvidia-smi/NVML indices equal the job-local CUDA indices; worker.gpu_pids
relies on the same). All cards are A6000s, so the heuristics are identical on every node.

With CLOQ_KVQ_BITS set as well, also wraps vLLM's Attention.forward for fake KV-cache quantization (cloq_kvq.py, W13).
With CLOQ_AQ_BITS set, also wraps vLLM's linear layers for fake activation quantization / QuaRot online Hadamards
(cloq_aq.py, docs/insights/METHOD_FIDELITY.md). The compile-cache root gets one subdirectory per hook config
(KV tag, activation tag, or both joined by "__"; KV-only keeps the W13 name).
With CLOQ_KIVI_KBITS set, wraps vLLM's FlashAttentionImpl.forward with the KIVI attention kernel (cloq_kivi.py, W99t);
exclusive with the other KV / activation hooks; compile-cache subdirectory = cloq_kivi.TAG.
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
_AQ_MOD = "vllm.model_executor.layers.linear"
_KIVI_MOD = "vllm.v1.attention.backends.flash_attn"


def _patch_humming(module):
    module.pynvml = _Proxy(module.pynvml)


def _patch_kvq(module):
    import cloq_kvq
    cloq_kvq.install(module)


def _patch_kivi(module):
    import cloq_kivi
    cloq_kivi.install(module)


def _patch_aq(module):
    import cloq_aq
    cloq_aq.install(module)


_AQ_ON = bool(os.environ.get("CLOQ_AQ_BITS") or os.environ.get("CLOQ_AQ_HAD", "0") != "0")
_KIVI_ON = bool(os.environ.get("CLOQ_KIVI_KBITS"))
if _KIVI_ON and (_AQ_ON or os.environ.get("CLOQ_KVQ_BITS")):
    raise RuntimeError("CLOQ_KIVI_* cannot be combined with CLOQ_KVQ_* / CLOQ_AQ_* hooks")
_PATCHES = {"humming.utils.device": _patch_humming}
if os.environ.get("CLOQ_KVQ_BITS"):
    _PATCHES[_KVQ_MOD] = _patch_kvq
if _AQ_ON:
    _PATCHES[_AQ_MOD] = _patch_aq
if _KIVI_ON:
    _PATCHES[_KIVI_MOD] = _patch_kivi


def _isolate_cache_root():
    """Per-config compile-cache namespace, set before vllm.envs is read, in every process of the server (idempotent)."""
    if _KIVI_ON:
        import cloq_kivi
        cloq_kivi.isolate_cache_root()
        return
    if not _AQ_ON:
        import cloq_kvq
        cloq_kvq.isolate_cache_root()  # W13 behaviour and name
        return
    import cloq_aq
    tags = []
    if os.environ.get("CLOQ_KVQ_BITS"):
        import cloq_kvq
        tags.append(cloq_kvq.TAG)
    tags.append(cloq_aq.tag())
    tag = "__".join(tags)
    root = os.environ.get("VLLM_CACHE_ROOT", os.path.expanduser("~/.cache/vllm"))
    if os.path.basename(root.rstrip("/")) != tag:
        os.environ["VLLM_CACHE_ROOT"] = os.path.join(root, tag)


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
    if os.environ.get("CLOQ_KVQ_BITS") or _AQ_ON or _KIVI_ON:
        _isolate_cache_root()
    sys.meta_path.insert(0, _Finder())
