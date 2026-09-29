# A6000 实验计划与交接（2026-09-28）

读者：在 A6000 集群上执行实验的 Claude Code 会话（及协作者）。本机（2×4080）会话负责代码、4B 深入分析、汇总与写作；A6000 会话负责多模型矩阵。两边通过私有仓库 github.com/W4ng77/cloq 同步。**不要把仓库设为公开。**

## 0. 目标
检验"扰动等价"及一阶 margin 模型（docs/COLING_PLAN.md §2）在 6 个模型上是否成立：
- P1 偏离饱和：轨迹偏离率随扰动大小 δ 很快饱和。
- P2 损伤阈值更晚：成功率下降出现在比偏离饱和大得多的 δ；二者之间为"免费压缩区"。
- P3 跨模型可预测：各模型的偏离曲线可由其 BF16 决策 margin 分布预测。
同时给出每个模型的 BF16 扰动 null，使所有压缩配置都能与之比较。

## 1. 硬规则
1. A6000 结果**绝不与 4080 结果合并**；4B 在 A6000 上整体重跑一套。
2. 每个节点、每种并行方式（单卡 / TP=2）先过确定性检查（§4 Phase 1），未通过不开跑。
3. 所有新配置通过环境变量或新 config 文件，**不修改 configs/frozen_v0.json / frozen_v1.json**。
4. 任务集固定：manifests/eval_tasks_v0.json（retail 58 + airline 27 = 85）；calibration 状态只来自 manifests/cal_tasks_v0.json 的 57 个任务。
5. 主 harness = 32k（CLOQ_MAX_PROMPT_TOKENS=32768，agent max-model-len 33792）。本机已证明 8k 截断会压低分数。
6. greedy 解码，VLLM_BATCH_INVARIANT=1，VLLM_USE_FLASHINFER_SAMPLER=0。
7. 运行完成后 push 的只有 runs/<id>/ 下的小文件（metrics.json、divergence 相关、decisions.jsonl、trajectory.jsonl、status.json、config/env json）；ckpt 不进 git。runs/ 若过大，用 git-lfs 或打包后告知本机会话。
8. 杀进程后检查孤儿 VLLM::EngineCore（`nvidia-smi --query-compute-apps=pid --format=csv`），stop_vllm.sh 不会清理它。

## 2. 模型
| 代号 | HF id | 类型 | BF16 显存 | 服务方式 | tool parser | 备注 |
|---|---|---|---|---|---|---|
| q4 | Qwen/Qwen3-4B-Instruct-2507 | dense | 8 GB | 1 卡 | hermes | 与本机同一模型 |
| q8 | Qwen/Qwen3-8B | dense，混合思考 | 16 GB | 1 卡 | hermes | chat_template_kwargs enable_thinking=false |
| q14 | Qwen/Qwen3-14B | dense，混合思考 | 28 GB | 1 卡 | hermes | 同上 |
| q32 | Qwen/Qwen3-32B | dense，混合思考 | 64 GB | TP=2 | hermes | 同上 |
| q30a3 | Qwen/Qwen3-30B-A3B-Instruct-2507 | MoE | 61 GB | TP=2 | hermes | 专家层只做 RTN/高斯（见 §3） |
| l8 | meta-llama/Llama-3.1-8B-Instruct | dense，另一家族 | 16 GB | 1 卡 | llama3_json | 若工具调用成功率 < 0.1 改用 mistralai/Mistral-Small-3.2-24B-Instruct-2506（mistral parser，1 卡） |

每个模型固定 HF revision，写入 run 的 model.json。

## 3. 压缩与扰动配置（每个模型相同）
所有压缩都以 **fake-quant（反量化回 BF16）** 形式服务，与 BF16 走同一 kernel 路径，从而只隔离权重误差。真实 kernel 另做一个检查（§4 Phase 4）。

| 配置 | 说明 | 需要 calibration | 重跑 |
|---|---|---|---|
| bf16 | 规范实现 | — | 1 |
| null_nonce | BF16 + CLOQ_PROMPT_NONCE（5 个固定 nonce，同本机） | — | 5 |
| gauss_k | BF16 权重加高斯噪声，每个 linear 的噪声 Frobenius 范数 = k × 该层 RTN-W4 g128 误差范数，k ∈ {0.03, 0.1, 0.3, 1, 3} | — | 每档 2 个噪声 seed |
| rtn_w8 / rtn_w4 / rtn_w3 | RTN，g128，asym | — | 各 2（nonce 1、2） |
| gptq_w4_d1 / gptq_w4_d2 | GPTQ W4 g128，FP-Traj 式 calibration（该模型自己的 BF16 轨迹状态，57 个状态/draw，64000 rows），2 个 draw | 是 | 各 2 |
| awq_w4 | AWQ W4 g128，同一 calibration 状态（draw 1） | 是 | 2 |
| gptq_w3 | GPTQ W3 g128，draw 1 | 是 | 2 |

每模型 1 + 5 + 10 + 6 + 4 + 2 + 2 = **30 个 run**（85 任务，retail + airline）。
MoE（q30a3）：GPTQ/AWQ 只作用于 attention 与共享层，专家层用 RTN，并在论文中注明；若 llm-compressor 对该架构支持良好则全量 GPTQ。
calibration 数据需要先跑该模型的 BF16 在 57 个 calibration 任务上（每模型多 1 个 run）。

## 4. 阶段
### Phase 0（本机会话完成后 push，A6000 会话开始前）
本机会话负责，A6000 会话**不要重复实现**：
- [ ] config 泛化：CLOQ_MODEL_ID、CLOQ_MODEL_REVISION、CLOQ_TOOL_PARSER、CLOQ_CHAT_TEMPLATE_KWARGS 环境变量；context policy 用对应 tokenizer。
- [ ] margin 记录：agent 请求 logprobs + top_logprobs=5，写入 decisions.jsonl（首 token margin 与全序列最小 margin）。
- [ ] 压缩生成器通用化：任意 HF decoder 的 RTN（W8/W4/W3）、高斯噪声（按 RTN 误差范数标定）、GPTQ/AWQ（llm-compressor 或现有 cloq/gptq.py），输出 fake-quant BF16 ckpt。
- [ ] scripts/a6000/：setup_env.sh、determinism_check.sh、run_model_matrix.sh（参数：模型代号、GPU 列表、user server 地址），全部幂等。
- [ ] 本机 4B 上先验证：margin 预测翻转的定量形式；高斯 3 档是否出现偏离饱和。

### Phase 1（A6000，第 1–2 天）：环境与确定性
- setup_env.sh：conda env（vllm 0.29.0、torch 2.13.0、transformers 5.17.0、litellm 1.82.6、compressed-tensors 0.17.0），tau2-bench 固定 commit 2174a60，下载 §2 模型。
- determinism_check.sh：每种服务方式（1 卡、TP=2）同一配置在 20 个任务上跑两遍，要求 decisions 逐字节一致（去掉随机 tool-call id）。TP=2 不确定时：记录分叉率，改为把 TP=2 的非确定性当作额外 null 家族测量并在论文中报告，不能静默使用。
- user simulator 选择（所有 agent 共用、固定 BF16、greedy）：首选 Qwen3-30B-A3B-Instruct-2507（TP=2）；若 TP=2 不确定，改用 Qwen3-14B（1 卡，enable_thinking=false）。要求：20 个任务上正常 stop、确定性通过、q4 BF16 成功率不落地板。选定后冻结。
- 一个 user server 可同时服务多个 agent 进程；推荐每节点：simulator 占 1–2 卡，其余卡各跑一个 agent server。
- 输出 docs/A6000_PHASE1.md：确定性结果、simulator 选择、每模型单 run 墙钟。据此重算 §5 预算。

### Phase 2（第 3–10 天）：主矩阵
- 每模型先跑 bf16 在 calibration 任务上 → 构建 calibration → 生成全部压缩 ckpt → 跑 §3 的 30 个 run。
- 优先级：q4 → q8 → l8 → q14 → q30a3 → q32（先小后大，尽早给本机会话数据）。
- 每个模型完成立即 push，本机会话随即做分析（偏离、首次偏离位置、成功率、margin）。

### Phase 3（可选，视时间）：calibration 案例扩展
- q8 上 Static vs FP-Traj GPTQ W4 各 3 个 draw（6 run），检验 4B 上"calibration 不可区分"在更大模型上是否仍成立；W3 上同样对比 2 个 draw。

### Phase 4（可选）：真实 kernel 检查
- q8 与 q32 的 gptq_w4_d1 以 compressed-tensors / marlin 真实量化格式服务，nonce R=3，与 fake-quant 对比偏离率与成功率，并记录真实 kernel 下确定性是否保持。

## 5. 预算（Phase 1 后重算）
按 4080 实测：4B BF16 85 任务约 15 min，量化约 45 min（循环慢尾）。假设 A6000 上 8B ≈ 1.3×、14B ≈ 2×、32B/30B-A3B（TP=2）≈ 3×：
- 每模型 31 run × 平均 0.5–2.5 h ≈ 15–75 run-h；6 模型合计约 250 run-h。
- 加上 simulator 分摊与 TP=2，约 **350–450 A6000·h**，16–24 卡并行约 1–1.5 周墙钟。
- Phase 3/4 另加约 60 A6000·h。

## 6. 交付物（A6000 会话 → 仓库）
- runs/a6000_<model>_<config>[_r<k>]/{retail,airline}/ 标准 artifacts + margins。
- docs/A6000_PHASE1.md，docs/A6000_LOG.md（每天一段：完成了什么、异常、墙钟）。
- 不做分析与作图（由本机会话统一做，保证口径一致）。
