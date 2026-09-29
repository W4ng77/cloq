# 4080 机器最终交接（2026-09-28）

读者：接手 CLOQ 的 A6000 集群会话。本文件之后，4080 机器不再往 master 推代码。

## 0. 交接状态
- 本机 git 没有未提交改动（`git status` 为空），所以**没有创建 from-4080 分支**。本机最后提交的代码就是 master 上的代码。
- Phase 0（多模型配置、margin 记录、通用压缩脚本）**没有开始**，cloq/ 与 scripts/ 里没有半成品。A6000_PLAN.md §4 Phase 0 的所有项均未实现。
- 本机为 COLING 新增的代码只有两处，均已在 master：
  - `cloq/config.py`：`CLOQ_MAX_PROMPT_TOKENS` 环境变量覆盖冻结的 8192 上限（不设时行为不变）。
  - `cloq/agent.py`：`CLOQ_PROMPT_NONCE` 环境变量在 system prompt 末尾追加 `Session ID: <nonce>`（扰动 null）；`cloq/run_arm.py` 把 `prompt_nonce` 与 `max_prompt_tokens` 写进 environment.json。
  - 脚本：`scripts/ctx_control.sh`（32k 对照）、`scripts/null_rerolls.sh`（扰动 null，已中途停止）。
- 本机 GPU 已全部释放（21:28），不再有任何作业。
- 数据：runs 小文件在 GitHub Release `data-4080`（见 §5）；ckpts 不传。
- 环境：`env/freeze_4080.txt`（pip freeze，conda env `cloq`）、`env/system_4080.txt`（nvidia-smi、nvcc 12.4、tau2-bench commit）。

## 1. E0 TODO 实际完成状态（对应 docs/STRATEGY_v2.md §6 E0）
| 项 | 内容 | 状态 |
|---|---|---|
| (a) | 重跑 2 个真正的 infra 故障单元 | 未做 |
| (b) | 独立重写 Q7 功效模拟 / GLMM | 未做（analysis/coling 只做了关键统计复算，不含功效模拟） |
| (c) | 冻结 PREREG_EVAL.md | 未做 |
| (d) | nonce 双跑确定性、采样逐 seed 可复现 | 未做。nonce 只是单跑（见 §2） |
| (e) | 纠正 HANDOFF.md 32k 说法；README 46/68 vs 39/58；32k 配置路径；预量化 W3-RTN | 32k 路径已实现并跑完 32k 对照；HANDOFF.md、README 未改；W3-RTN 未量化 |
| (f) | 删除作废表述 | 未改原文档；作废清单与正确口径见 docs/PROGRESS_2026-09-28.md §3 与 analysis/coling/RESULTS.md §7 |
| (g) | 新估计量的功效/MDE 模拟 | 未做 |
| (h) | Noise Floor Audit 全文、核对 † 引用 | 已完成：Noise Floor Audit 全文在策略 workflow 中读过（BFCL 单轮、开环、不量化）；引用核对见 analysis/coling/RELATED_WORK.md。**Singh 2608.15046 未读全文；ACBench、Flat Score 逐配置表未从 PDF 取** |
| (i) | max_steps 循环归因 | 已完成：analysis/coling/04_loop_attribution.py，结果 RESULTS.md §4 |
| (j) | ≥2 写假说功效 | 未做 |

## 2. 扰动 null 结论
用户在 2026-09-28 21:28 决定停止本机实验、全部迁移到 A6000，扰动 null 因此**只跑了一部分**（8k harness，85 个 dev 任务，greedy）：
null_bf16_n1、null_bf16_n2 完整（retail+airline），null_bf16_n3 只有 retail（airline 中断，未打包）。Static/FP-Traj/RTN 的 nonce 重跑未跑。
分析脚本 `analysis/coling/06_null_partial.py`，输出 `analysis/coling/out/null_partial.json`。对照规范 BF16（bf16_v1，pooled 0.376）：

| run | 任务数 | 成功率 | 任务结果与规范 BF16 不同 | 工具级偏离（t_tool 存在） |
|---|---|---|---|---|
| null_bf16_n1 | 85 | 0.341 | 0.200 | 0.929 |
| null_bf16_n2 | 85 | 0.294 | 0.176 | 0.918 |
| null_bf16_n3（仅 retail） | 58 | 0.293 | 0.276 | 0.862 |
| 18 个 W4 GPTQ dev ckpt | 85 | 0.271–0.424 | 0.200–0.341 | 0.929–0.976 |

结论（初步，n=2 个完整 null run）：
1. **权重不变、只加一行 nonce，92–93% 的任务轨迹在工具层面偏离规范 BF16**，W4 为 93–98%。偏离饱和（P1）得到初步支持。
2. **两个 BF16 null run 的成功率（0.341、0.294）都落在 18 个 W4 ckpt 的范围（0.271–0.424）内**，且都低于规范 BF16 的 0.376。规范 BF16 很可能是偏高的一次实现，之后的 damage 应相对 null 均值计算。
3. 结果翻转率 null 0.18–0.20，W4 中位约 0.26：W4 可能比纯 re-roll 多一些结果层面的变化，这是唯一可能的 damage 信号，需要 A6000 上更多 null 重跑（计划 R=5）确认。
4. 尚未测：nonce 下的确定性双跑；量化 ckpt 的 nonce 重跑（估计 s_c 所需）。这些都在 A6000_PLAN 的矩阵里。

## 3. 发现、坑与口径决定（此前只在本地记着）
### 口径决定
- v0 FP-Traj − Static（retail +0.121）的零假设 p 值用 **0.0195**（精确 McNemar，one-sided，8/9），不用 STRATEGY_v2 的 0.035（无法从仓库重建其算法）。
- Static vs 其余 arm 的 NLL 置换 p 用复算值 ≈0.001，不用 0.0044。
- NLL 汇总有两种口径：token 加权（sum nll / sum tokens）给 NLL–成功 r=+0.05/+0.04；状态平均（mean of per-state ratios）给 r=−0.12/−0.09，而 STRATEGY_v2 的 NLL 均值表（Static 0.094、其余 0.076、RTN 0.157）用的是状态平均。**全文只能用一种**；两种下 |r|≤0.13，结论不变。
- "checkpoint 占方差 0.24%"、"closed-loop hazard 是 open-loop 的 2–6 倍"、"早期改写/漂移导致失败"三种表述作废。
- 32k 是之后的主 harness；8k 只作历史对照。

### 结果（未写进其他文档的）
- 32k vs 8k（pooled db_match，85 任务）：BF16 0.376→0.412；Static c1 0.365→0.376；FP-Traj c1 0.282→0.306；CLOQ-All c1 0.318→0.353；CLOQ-Novel c1 0.318→0.353；MatchedRandom c1 0.329→0.341；MatchedAlt c1 0.424→0.447。32k 下截断率约 0（FP-Traj airline 0.03）。MatchedAlt c1 在两种 harness 下都高于 BF16，是 re-roll 噪声的直接例子。
- 循环归因（150 条提前终止）：agent 侧 37%、无重复 35%、混合 20%、simulator 侧 8%；剔除 simulator 侧后单 ckpt 成功率变化 ≤0.009。
- 4080 上 32k 可行：Qwen3-4B KV 约 144 KiB/token，agent 在 util 0.92 下 KV 池 42,800 tokens，33,792-token 请求并发 1.27×。HANDOFF.md 说 16GB 做不了 32k 是错的。
- 实测墙钟（2×4080，85 任务）：BF16 8k 约 15 min，32k 约 25 min；W4 8k 中位约 41 min，32k 约 15–60 min。

### 坑
- 被杀的 pipeline 可能留下孤儿 `VLLM::EngineCore`（ppid=1）占满 GPU，`stop_vllm.sh` 不会清理；重启前查 `nvidia-smi --query-compute-apps=pid,used_memory --format=csv`。
- 从本机 Claude 会话 nohup 启动脚本时，PATH 里 uv 的 python 排在 conda 前面，`python -m cloq.run_arm` 会报 `No module named loguru`。脚本里要 `export PATH=$CONDA_PREFIX/bin:$PATH`（ctx_control.sh、null_rerolls.sh 已加）。
- `scripts/pipeline_v1.sh` 的 `eval_ckpt` 曾缺 `local`，覆盖了外层 DRAW；已修，但旧 divergence/judge 产物曾用 repair 脚本重建。
- `pkill -f "vllm serve"` 会杀掉自己的 shell；用 PID 文件 + stop_vllm.sh。
- 无 `VLLM_BATCH_INVARIANT=1` 时并发不同会分叉；FlashInfer sampler 需要 CUDA-13 nvcc，本机只有 12.4，所以 `VLLM_USE_FLASHINFER_SAMPLER=0`。
- 提前终止的 run `db_check` 为空，必须按失败计（resolved_db_match），否则抬高量化 arm。
- 文本改写会让每个任务在 t=0 "偏离"，偏离用 t_tool；occupancy 对齐用 t_context（off-by-one 已修）。
- `cloq/config.py` 硬编码读取 `configs/frozen_v0.json`；frozen_v1.json 没有 context_policy 段。
- README 写 46/68，冻结 split 是 39/58（retail 114 个任务中 17 个不稳定被排除后 97 = 39 cal + 58 eval；airline 50 − 5 = 45 = 18 + 27），README 未修正。
- 策略 workflow 的三份审计数据分析原本在 /tmp scratchpad，已复制到 `analysis/strategy_v2_workflow/`（脚本与 json 输出；大 csv/pkl 未复制，可由脚本重建）。完整 workflow 结果（提案、评审、审计意见）在 `analysis/strategy_v2_workflow/workflow_result_no_synthesis.json`，综合备忘录即 docs/STRATEGY_v2.md。

## 4. analysis/coling/ 对本地 runs/ 的依赖
所有脚本通过 `common.py` 的 `RUNS = ROOT / "runs"` 读取，解压 Release 后放到仓库根目录的 `runs/` 即可。

| 脚本 | 读取路径 | 需要的文件 |
|---|---|---|
| common.py | `runs/{arm}_{c1,c2,c3}_dev/{retail,airline}/`，arm ∈ static、fp_traj、cloq_all、cloq_novel、cloq_matched_random、cloq_matched_alt；`manifests/task_split_v0.json` | decisions.jsonl（load_decisions）、trajectory.jsonl、status/metrics；openloop.jsonl、openloop.summary.json |
| 01_checkpoint_success.py | 上述 18 个 dev run；`runs/bf16_v1`；`runs/rtn_eval` | trajectory.jsonl / decisions.jsonl（resolved_db_match） |
| 02_v0_gap.py | `runs/static_eval`、`runs/fp_traj_eval`（v0）；`runs/static_c1_dev`、`runs/fp_traj_c1_dev` | 同上 |
| 03_openloop_vs_closedloop.py | 18 个 dev run 与 `runs/rtn_eval`、`runs/static_eval` 的 openloop.jsonl / openloop.summary.json | openloop 输出 |
| 04_loop_attribution.py | 18 个 dev run、`runs/bf16_v1`、`runs/rtn_eval` | trajectory.jsonl、status.json、metrics.json |
| 05_figures.py | 以上全部；`runs/ctx32k_*`（bf16 与 6 个 arm 的 c1）；`runs/null_bf16_n*`（存在且 completed 时叠加 null 分布） | metrics.json、trajectory.jsonl；out/*.json |

注意：Release 不含 `tau2_results.json`（共约 9 GB）。analysis/coling 不依赖它；STRATEGY_v2 A8 用 tau2 `action_checks` 做的失败分类依赖它，需要时在 A6000 重跑生成。

## 5. 数据 Release
GitHub Release `data-4080`（私有仓库 W4ng77/cloq）：https://github.com/W4ng77/cloq/releases/tag/data-4080

| 附件 | 大小 | 内容 |
|---|---|---|
| runs4080_20260928.tgz | 746 MB | runs/ 下 936 个文件：metrics.json、status.json、config.json、environment.json、model.json、task_manifest.json、decisions.jsonl、trajectory.jsonl、task_success.json、divergence*.json、openloop*.jsonl / openloop*.summary.json、nl_judge.jsonl |
| runs4080_reps_20260928.tgz | 623 MB | 58 个 reps.npz（BF16 final-layer 表示，occupancy 与 novelty 的输入）。occupancy 结果本身已在 git：analysis/v1/occupancy_c*.json、analysis/occupancy_*.json |
| SHA256SUMS | — | 两个 tgz 的 sha256 |

范围：v0（bf16、static_eval、fp_traj_eval、cloq_eval、rtn_eval、bf16_rep_eval、q0_fp_traj）、确定性测试（bi_a–bi_d）、v1（bf16_v1、q0_v1_c*、12 个 dev run）、amendment（matched_random、matched_alt 各 3）、ctx32k（7 个）、null（n1、n2、n3 retail），以及调试用的 qtest、phase0_sanity。
不含：ckpts/、tau2_results.json（约 9 GB）、null_bf16_n3/airline（中断）。
解压：在仓库根目录 `tar xzf runs4080_20260928.tgz`，得到 runs/…，analysis/coling/make_all.sh 可直接运行。
