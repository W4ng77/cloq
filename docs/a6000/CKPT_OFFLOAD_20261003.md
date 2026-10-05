# Checkpoint offload and cache cleanup, 2026-10-03

**TL;DR** The dataset `datapool001/data/ziyangs` was at its 1 T quota with 1.24 G free. I deleted
re-downloadable HF caches and verified plain copies of public base models (about 428 GiB apparent size, 399 G on
disk after compression), and
uploaded part of one finished sotaquant campaign to a private repo in `pranalabs-ai`. I deleted only the
7 checkpoint folders whose every file was confirmed on the Hub (31.5 GB). The upload then stopped: HF replied
**"Private repository storage limit reached"** for the `pranalabs-ai` org. As instructed, I stopped uploading and
deleted nothing that was not uploaded and verified. Live usage (`usedds`) fell from 991 G to 592 G. `AVAIL` is
only 4.0 G for now, because ZFS snapshots still hold the deleted blocks (see the last section). Nothing under
`cloq_work/queue`, running tasks, or `analysis/fork/holdout/` was touched. No Slurm job was submitted or killed.

Evidence and logs (cluster scratch, session 4a7ccb09):
`/tmp/claude-1064/-home-ziyangs/4a7ccb09-009e-4aee-b4c9-ef93691bb496/scratchpad/`
`{verify_basecopies.{py,json,log}, dryrun_rm*.txt, rm_*.txt, delete_basecopies.log, delete_sq_caches.log, offload.py,
spec_*.json, offload_*.json, offload_logs/}`.

## ZFS before and after

| time (PDT) | used | usedds | usedsnap | avail |
|---|---|---|---|---|
| 2026-10-03 11:49 (before) | 1023G | 991G | 31.8G | 1.24G |
| 2026-10-03 12:12 (after) | 1020G | 592G | 428G | 4.00G |

## Where the 991 G was (inventory before any action, `du -xs`)

| path | size | notes |
|---|---|---|
| cloq_work/hf/hub | 435.1G | shared blob store `hub/blobs` 177.4G (FP8/AWQ/gemma/Llama 160.2G + GLM-4-9B orphans 17.5G), Mistral-24B 89.4G (incl. 44.7G `consolidated.safetensors`), Qwen3-32B 61.0G, Qwen3-30B-A3B 56.9G, Qwen3-14B 27.5G, Qwen3-8B 15.3G, Qwen3-4B 7.5G |
| cloq_work/ckpt_cache | 102.9G | base 59.0G (6 builds), m24_textonly_v1 43.9G, registry |
| cloq_work/{envs,tmp,pipcache,data,logs,simrelay,...} | 23.6G | envs 14.3G, tmp/pipcache 3.2G, pipcache 2.5G, data 2.7G |
| cloq | 57.8G | runs 54.2G (decisions/trajectories/results, no weights), analysis 2.7G |
| sotaquant | 355.8G | llama3-8b-main-v1 106G, models 73.6G, one-step-rtn-w3 44.3G, cache 30.6G, qronos-* 48.1G, qwen4b-calib-* 21G, experiments 13.4G, official-baselines 12.2G, envs 5.7G |
| naacl2027 | 15.3G | modified in the last 72 h, KEEP |
| cloq_wt, gpuq, cloq-paper | <0.3G | |

## Classification and actions (items > 1 G)

Sizes are the bytes freed as reported by `hf cache rm`/`du --apparent-size` (GB = 10^9, GiB = 2^30, as labelled).

### DELETE-ONLY (re-downloadable, done)

| # | path | size | reason | deleted (PDT) |
|---|---|---|---|---|
| 1 | hub `Qwen/Qwen3-32B-FP8` | 31.98 GiB | official pre-quantized X1 repo; X1 tasks are all in `done/`; no todo/running task has `ckpt.kind=hf` | 2026-10-03 11:53:40 |
| 2 | hub `Qwen/Qwen3-30B-A3B-Instruct-2507-FP8` | 29.05 GiB | same | 11:53:40 |
| 3 | hub `google/gemma-4-12B-it` | 22.31 GiB | W100p: g12 gate FAIL; only 3 g12 tasks, all in `deferred/`; `ckpt_cache/g12_textonly_v1` no longer exists | 11:53:40 |
| 4 | hub `Qwen/Qwen3-32B-AWQ` | 18.01 GiB | X1, unused | 11:53:40 |
| 5 | hub `Qwen/Qwen3-14B-FP8` | 15.22 GiB | X1, unused | 11:53:40 |
| 6 | hub `meta-llama/Llama-3.1-8B-Instruct` | 14.96 GiB | l8 failed the capability floor; its 43 tasks are all in `deferred/` | 11:53:40 |
| 7 | hub `Qwen/Qwen3-14B-AWQ` | 9.30 GiB | X1, unused | 11:53:40 |
| 8 | hub `Qwen/Qwen3-8B-FP8` | 8.80 GiB | X1, unused | 11:53:40 |
| 9 | hub `Qwen/Qwen3-8B-AWQ` | 5.69 GiB | X1, unused | 11:53:40 |
| 10 | hub `Qwen/Qwen3-4B-Instruct-2507-FP8` | 4.84 GiB | X1, unused | 11:53:40 |
| 11 | hub `mistralai/Ministral-8B-Instruct-2410` | 1.4 kB | config only | 11:53:40 |
| 12 | hub `Mistral-Small-3.2-24B@95a6d26c/consolidated.safetensors` (blob `2cc4cc28…`) | 48.02 GB | duplicate of the 10 HF shards. m24 is served and quantized from `ckpt_cache/m24_textonly_v1` (`models.json` `src_path`; `worker.model_src`, `build_ckpt` passes `--src` to `cloq.quantize`). `m24_textonly.py` reads only the shards and deliberately skips `consolidated.safetensors`. `cloq/quantize.py::source_dir()` (snapshot_download) runs only without `--src`. `det_probe`/`kvq_validate`/`kivi_gate`/`aq_validate` serve the raw snapshot but have no m24 task. Only `a6k2_smoke_m24.vllm.log` (old failed smoke) ever opened it; current m24 logs show `ckpt_cache/m24_textonly_v1` | 11:53:40 |
| 13 | hub `blobs/{85,c6,cc,ce,cf}/…` (GLM-4-9B-0414) | 17.53 GiB | orphan shared blobs: their `.refs` point only to `models--zai-org--GLM-4-9B-0414`, which no longer exists; GLM is not in queue/scripts/models.json | 11:54:27 |
| 14 | sotaquant/models/Qwen2.5-32B | 65.54 GB | byte-identical to `Qwen/Qwen2.5-32B@1818d358` (17/17 safetensors sha256 + all small files git-sha1 match); qwen32 campaign has no resume state (469 MB) | 12:07:37 |
| 15 | sotaquant/models/Llama-2-7b-hf | 13.48 GB | identical to `meta-llama/Llama-2-7b-hf@01c7f73d` (token has gated access, tested); the 2 provenance JSONs were kept in `models/Llama-2-7b-hf.provenance/` | 12:07:39 |
| 16 | sotaquant/qronos-ppl-v1/models/qwen3_4b | 8.06 GB | identical to `Qwen/Qwen3-4B@1cfa9a72` | 12:07:40 |
| 17 | sotaquant/one-step-rtn-w3-ohio-20260926/models/qwen3_4b | 8.06 GB | identical to `Qwen/Qwen3-4B@1cfa9a72` | 12:07:41 |
| 18 | sotaquant/qronos-llama32-3b-ppl-v1/models/llama32_3b | 6.44 GB | identical to `meta-llama/Llama-3.2-3B@13afe512` | 12:07:42 |
| 19 | sotaquant/qronos-official-llama-ppl-v1/models/llama31_8b | 16.07 GB | identical to `meta-llama/Llama-3.1-8B@d04e592b` | 12:07:44 |
| 20 | sotaquant/llama3-8b-main-v1/model | 16.07 GB | identical to `meta-llama/Meta-Llama-3-8B@8cde5ca8` | 12:07:45 |
| 21 | sotaquant/one-step-rtn-w3-ohio-20260926/models/llama3_8b | 16.07 GB | identical to `meta-llama/Meta-Llama-3-8B@8cde5ca8` | 12:07:46 |
| 22 | sotaquant/cache/huggingface hub `Qwen/Qwen3-8B` | 16.4 GB | public HF cache (datasets in the same cache kept) | 12:08:25 |
| 23 | sotaquant/cache/huggingface-downstream hub `Qwen/Qwen2.5-7B` | 15.2 GB | public HF cache (datasets kept) | 12:08:26 |
| 24 | sotaquant/qwen4b-calib-ohio-w4-v1/cache hub `Qwen/Qwen3-4B` | 8.1 GB | public HF cache | 12:08:27 |

Method: HF caches were removed with `hf cache rm` (huggingface_hub 1.33, which handles the shared-blob store and its
`.refs`). A dry run was checked first. `hf cache prune` was **not** used: its dry run would have deleted every
pinned CLOQ model, because they have no `refs/main`. Plain copies were removed with `rm -rf` only after
`verify_basecopies.py` matched every local file to the pinned revision. LFS files were compared by sha256, small
files by git blob sha1, and all 8 directories matched (`verify_basecopies.json`). After deletion, the remaining
hub snapshots have 0 broken symlinks.

### UPLOAD-THEN-DELETE

| # | path | size | reason | HF repo (private) | verification | deleted |
|---|---|---|---|---|---|---|
| 25 | sotaquant/llama3-8b-main-v1/jobs/{awq_w3_i3, gptq_w3_i0, gptq_w4_i3, omniquant_w3_i3, rtn_w3_i0, rtn_w3_i3, rtn_w4_i3}/checkpoints | 31.46 GB | finished campaign (137/137 COMPLETE, summary.json 2026-09-24), per-layer quantized weights | https://huggingface.co/pranalabs-ai/ckpt-sotaquant-llama3-8b-main-v1 | 231/231 files OK: 224 LFS sha256 + 7 git-sha1, sizes all equal | 2026-10-03 12:12:15 |
| 26 | same, remaining 9 jobs: awq_w3_i0 (16.9G), awq_w4_i0 (16.9G), awq_w4_i3 (5.0G, 32/33 files on Hub), omniquant_w4_i3 (5.0G, 12/33), gptq_w3_i3 (4.2G), gptq_w4_i0 (3.8G), rtn_w4_i0 (3.8G), omniquant_w3_i0 (3.7G), omniquant_w4_i0 (3.7G) | ~63.9 GB | same | same repo (partial) | **BLOCKED**: "Private repository storage limit reached" (pranalabs-ai) | **kept** |
| 27 | sotaquant/qronos-llama31-8b-ppl-v1/jobs/*/layers | 13.9 GB | finished campaign (5/5 COMPLETE) | https://huggingface.co/pranalabs-ai/ckpt-sotaquant-qronos-llama31-8b-ppl-v1 (created, empty) | not started | kept |
| 28 | sotaquant/experiments/strict-downstream-ohio-backfill-v1/recovery-archive | 11 GB | stale archive (`ARCHIVED_FOR_REEXPORT`), cell since re-exported and COMPLETE | (planned `ckpt-sotaquant-backfill-qwen25-7b-rtn-w3-i0-archive`) | not started | kept |

The upload is resumable. The local upload state is in `sotaquant/llama3-8b-main-v1/.cache/huggingface/upload/`.
Re-run `offload.py spec_sq_llama3_8b_main_v1.json` from the scratch directory. It verifies every file again and
deletes only verified checkpoint folders.

### UPLOAD-AND-KEEP (unfinished, inactive campaigns: upload for safety, keep the resume state; not started because of the quota)

| path | size | status |
|---|---|---|
| sotaquant/one-step-rtn-w3-ohio-20260926/cells | 17.2 GB | 0/4 evaluations, no change since 09-26 (handoff from another root) |
| sotaquant/qwen4b-calib-w4-from4080-v1/cells | 8.7 GB | GPTQ-W4 block states that feed qwen4b-calib-ohio-w4-v1 (4/4 NOT_COMPLETE) |
| sotaquant/qronos-llama32-3b-ppl-v1/jobs | 2.9 GB | 5/5 INCOMPLETE |

### KEEP

| path | size | reason |
|---|---|---|
| hub `Qwen/Qwen3-30B-A3B-Instruct-2507` | 56.9G | user simulator on every node |
| hub `Qwen/Qwen3-32B` | 61.0G | q32 tasks queued/running (`*_rro`) |
| hub `Mistral-Small-3.2-24B` shards | 44.7G | source of m24_textonly_v1; m24 phase 2 + scores |
| hub `Qwen/Qwen3-14B`, `Qwen3-8B`, `Qwen3-4B-Instruct-2507` | 27.5G, 15.3G, 7.5G | queued/running tasks |
| cloq_work/ckpt_cache/m24_textonly_v1 | 43.9G | m24 serving path |
| cloq_work/ckpt_cache/base (+registry) | 59.0G | perturbation tasks derive from it. Note: `q8_awq_8a97d2f7b45b` (15.4G) is used by no todo/running task, so it could be offloaded later |
| cloq_work/envs, pipcache, tmp/pipcache, data | 14.3G, 2.5G, 3.2G, 2.7G | envs and pip caches |
| cloq/runs, cloq/analysis | 54.2G, 2.7G | analysis data, no weights |
| naacl2027 | 15.3G | modified < 72 h |
| sotaquant envs, official-baselines (uv cache + env), runtime venvs | 5.7G, 12.2G, ~13G | environments |

## Why AVAIL is still small

Deleting files frees space only when no snapshot references the blocks. Snapshots now present: `@2026-10-02-120000`,
`@2026-10-03-000000` and `@2026-10-03-120000`, so retention is about 3 snapshots, 12 h apart.
- Items 1-13 (about 222 GiB, deleted 11:53-11:54): held by the 10-02 12:00 and 10-03 00:00 snapshots, so they
  are released when `@2026-10-03-000000` expires (expected around 2026-10-04 12:00).
- Items 14-25 (about 205 GiB, deleted 12:07-12:12): also held by `@2026-10-03-120000`, so they are released
  around 2026-10-05 00:00.
`usedsnap` moved 31.8G -> 428G while `usedds` moved 991G -> 592G, as expected.

## Update 2026-10-04 (W100al): personal account, qronos dropped, changquant

**TL;DR**
- **Moved to the personal account.** The user asked to move the uploads off `pranalabs-ai` to the personal account W4ng1204 (free tier, private storage limit about 100 GB).
  - `W4ng1204/ckpt-sotaquant-llama3-8b-main-v1`: 1,823 files, 70.7 GB. 9 states complete; the other 7 are in a companion repo.
  - `W4ng1204/ckpt-sotaquant-qronos-llama31-8b-ppl-v1`: weights removed by the user's decision; results only, 9 MB, history squashed.
  - Both are verified: the uploader re-hashed every file, then a workflow ran 2x2 independent verifiers (full hash and download-compare). Both carry fact-checked READMEs.
- **Local deletions.**
  - llama3: 9 checkpoint folders, 66.1 GB, re-verified before deletion.
  - qronos: weights only, 16.8 GB (llama31 and llama32).
  - Regenerable environments and caches, 39 GB: sotaquant runtime venvs, official-baselines cache and onecomp-env, envs/strict, sotaquant/cache, naacl2027 envs and hf cache.
- **Storage limit.** The backfill upload hit "Private repository storage limit reached" on the personal account. The rest goes to a new org `changquant`, which the user creates in the web UI; there is no API for it.
  - `migrate_changquant.py` (running, waiting for the org) copies the org-only 7 llama3 states (31.5 GB) into `changquant/ckpt-sotaquant-llama3-8b-main-v1-part2`.
  - It checks that every `pranalabs-ai` file is in personal ∪ part2 with an identical hash.
  - It then uploads backfill, one-step and qwen4b.
  - It never deletes anything. The `pranalabs-ai` repos are deleted only after that check and an independent verification.
- **Not uploaded.** CLOQ's own ckpt_cache base builds (31 GB) are deterministic and their shas are recorded. They are proposed for deletion once tonight's tasks finish.

- **Org name (07:00).** The user created the overflow org as **`ChangXWLab`**, not `changquant`; W4ng1204 is admin. `migrate_changquant.py` was stopped while still waiting, before it uploaded anything, and replaced by `migrate_changxwlab.py`. That script uploads the three local folders first (backfill, one-step, qwen4b; no disk needed), then waits for > 45 GiB free before staging llama3 part 2 into `ChangXWLab/ckpt-sotaquant-llama3-8b-main-v1-part2`. The stale upload cache of the backfill folder (from the failed personal attempt) was moved aside to `upload.personal_20261004`. Backfill: 17/17 files verified on `ChangXWLab/ckpt-sotaquant-backfill-qwen25-7b-rtn-w3-i0-archive` at 07:03. The empty personal repo `W4ng1204/ckpt-sotaquant-backfill-qwen25-7b-rtn-w3-i0-archive` (only `.gitattributes`) is left from that attempt.

- **Local deletion and READMEs (07:15-08:10).** After offload.py and an independent re-hash (workflow wf_1b133c46-ed1: 229/229 data files sha-identical; no running or queued job uses them), the three local folders were deleted (`delete_cq_local_20261004.json`: 21 + 138 + 74 files, 41.0 GiB logical; freed when the 10-04 00:00 snapshot expires). Model cards were drafted and fact-checked claim by claim (workflow wf_12e8781a-670: 165 / 215 / 145 claims) and uploaded to the three ChangXWLab repos; all private. The backfill card records that shard 3 of the archived export differs from its certificate (the reason it was archived). To resume `qwen4b-calib-ohio-w4-v1` or the one-step campaign, download `cells/` back from ChangXWLab first.

Records: `/home/ziyangs/cloq_offload_20261003/{offload_p_*.json, offload_cq_*.json, migrate_changquant.json, migrate_changxwlab.json, readmes/, verify_tmp/, offload_logs/}`, workflow runs wf_a603dd43-1cc (verify) and wf_51f0bc1e-b12 (READMEs), `/data/ziyangs/cloq_work/logs/purge_20261003.log`.

## Update 2026-10-04 17:00: pranalabs-ai repos deleted; 7 llama3 states lost

- The llama3 part-2 migration failed at 12:04. pranalabs-ai is over its private storage limit, and Hugging Face then blocks all downloads from its private repos: `resolve` returns 403 "Private repository storage limit reached"; listing still works.
- The 7 org-only states (awq_w3_i3, gptq_w3_i0, gptq_w4_i3, omniquant_w3_i3, rtn_w3_i0, rtn_w3_i3, rtn_w4_i3; 232 files, 31.5 GB) could therefore not be copied.
- The user asked to clear pranalabs-ai and deleted both repos (llama3-8b-main-v1, qronos-llama31-8b-ppl-v1) in the web UI. The 7 layer checkpoints are lost.
- Their certificates (`weights.json` with layer SHA-256), results and evaluations remain in `W4ng1204/ckpt-sotaquant-llama3-8b-main-v1`. The file list with sizes and hashes is `/home/ziyangs/cloq_offload_20261003/lost_llama3_org_only_20261004.json`.
- The README was updated ("not available"; commit df132aeb). `migrate_changxwlab.py` was stopped. The ChangXWLab part-2 repo was never created.

## Update 2026-10-04 23:40: CLOQ reproduction checkpoints to ChangXWLab

- New private repo `ChangXWLab/cloq-ckpt-cache` (40.9 GB, 177 files incl. README). offload.py verified 173 + 2 files (size and SHA-256).
- Contents:
  - `base/`: the three content-addressed W3 bases, q8 GPTQ-W3, q8 RTN-W3 and q4 RTN-W3.
  - `registry/`: 132 derived-build records with expected tensor content hashes.
  - `registry.log`.
  - `spinquant_q8_a4_s0/`: the learned SpinQuant W4A4 rotation.
- The main-text W4/KV checkpoints are not stored. They are rebuilt per task, and each rebuild is checked against the checkpoint sha and serving canary in `servers.json`. The README says so.
- Local copies are kept (the takeover panel is running). ChangXWLab now holds about 85 GB of its roughly 100 GB private cap.
