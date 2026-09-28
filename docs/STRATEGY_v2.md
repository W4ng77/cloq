# CLOQ 下一步策略备忘录（2026-09-28，修订版）

> 读者：项目负责人及潜在合作者。依据：v0/v1 历史记录、作品集、三份经独立审计的数据分析（variance / mechanism / truncation）、已核实文献地图、5 份提案、4 份分视角评审，以及一轮 critic 意见（本版按其 high/medium 缺口修订）。
> 标注约定：
> - 「审计确认」：审计者用独立代码从原始 run 文件重算过。
> - 「待建立」：需要新实验。
> - 带 † 的文献：不在已核实文献地图内，是本备忘录补充的，投稿前必须逐条核对。
> - 「本机已核实」：直接查过仓库文件。例如 `configs/frozen_v0.json` 中 agent 与 simulator 的 temperature 都是 0.0；`cloq/config.py` 第 10 行硬编码读取 `frozen_v0.json`，第 26–27 行支持 `CLOQ_MAX_PROMPT_TOKENS` 覆盖。

---

## 1. 一句话结论

**CLOQ 不再作为 calibration 方法论文推进，改做一篇闭环评测科学论文：在确定性 serving 下，测量闭环 agent benchmark 的哪个终点、在多大规模上能看到压缩模型相对参考模型的差异，并给出对应的测量协议。**

组成部分：
- 闭环 re-roll 机制；
- 对 BF16 本身采样得到的扰动零分布（perturbation null）。greedy + prompt 扰动和温度采样两种都做；
- 对同一 W4 checkpoint 的 re-roll 复制，用来直接估计 checkpoint 间的真实差异 s_c；
- 用来标定 benchmark 灵敏度（MDE）的退化梯度（degradation ladder），并在多个候选终点上比较 MDE；
- 8k 与 32k harness 的配对对照；
- 以 draw 为单位的预注册确认性研究；
- 可复用的工具包。

**为什么有影响力：**
- **现有设计的功效很低。** 压缩 agent 的论文普遍用「单 checkpoint、单次评测、约 100 个任务」的闭环分数比较方法。按一个未经独立审计的生成模型（variance Q7）估算，这种设计检测 5 个点效应的功效约为 0.23–0.26。E0 会按真实几何独立复算，在那之前这个数一律写成 model-based。
- **我们自己的预注册胜出复验时反号。** v0 的「显著胜出」（+0.121）在可交换零假设下单侧 p=0.035（审计确认），复验时符号反转。
- **RTN 的证据要按单次实现来读。** RTN 的 open-loop NLL 是 Static 的 1.7 倍，它在闭环里只有一次实现，落在 GPTQ 范围底端：pooled 0.271 恰好等于 18 个 checkpoint 的最小值，long 0.108 也在底部。这既和「benchmark 不敏感」相容，也和约 0.06 的真实效应相容。能否区分，由 E1/E2 的 RTN re-roll 复制来检验。
- **结论只在本设置下成立。** 本设置是：一个 4B 模型、τ² retail+airline、同模型 user simulator、greedy 解码、自定义 8192-token 截断 harness、db_match 终点。外推由 E1（采样 null）、E1b（换 simulator）、E4（32k）、E6 检验。
- **问题从「测不出」改为「在哪个终点、多大规模上测得出」。** Flat Score 把错误预算收紧后，分差从 1.3 拉到 16.7 个点，说明分辨不出来的可能只是 db_match 这个二值终点。
- **新颖性主张收窄为三点：** 压缩模型对参考模型的差值推断、draw 与 re-roll 的分离、用已知退化梯度标定的 MDE。
- **与邻近工作的关系。** 最接近的 [Flat Score, Amplified Failures](https://arxiv.org/abs/2607.27275) 只用单一 calibration、单次评测，没有噪声模型。Noise Floor Audit 做了 agent benchmark 的 prompt 扰动噪声审计，与我们的扰动 null 直接重叠，全文待 E0 读完再定位。

---

## 2. 我们手里真正有什么

### 2.1 已成立（审计确认，可以写进论文）

| # | 结论 | 关键数字 | 来源 |
|---|---|---|---|
| A1 | **serving 完全确定** | `VLLM_BATCH_INVARIANT=1` 下，BF16 v0/v1/rep 在 85/85 个任务结果、1046/1046 个决策（prompt SHA、文本、工具调用，去掉随机 tool-call id 后）上完全一致。不开这个 flag 时，不同并发会分叉（bi_a vs bi_b）；开启后 74/74 一致。**只在 greedy（temperature 0）下验证过** | variance Q5 审计；`scripts/bf16_replicate.sh`；本机已核实 frozen_v0 温度 |
| A2 | **给定任务难度后，18 个 W4 checkpoint 在闭环里近乎可交换** | 方差比 1.39（列置换 p=0.13），long 1.51（p=0.08）；arm 置换 p=0.68 pooled / 0.36 long；draw-seed p=0.90 / 0.74；checkpoint 均值的 split-half 信度 0.32 pooled / 0.39 long | variance Q2–Q4 审计 |
| A3 | **真实 checkpoint 差异的上界，和我们想检测的效应同一量级** | 隐含真实 checkpoint SD：pooled 0.023 [0, 0.054]，long 0.038 [0, 0.082]。这是从「每个 checkpoint 只有一次实现」加 Bernoulli 模型**间接推出**的，没有直接测量（E1 补）。「checkpoint 占方差 0.24%」这个说法被审计判为没有信息量，**不再使用** | variance 审计 |
| A4 | **open-loop 看得到 calibration 的差别，闭环看不到** | NLL/token：Static 0.094，5 个轨迹类 arm 0.075–0.077（arm 置换 p=0.0044）。但这 5 个轨迹 arm 之间 open-loop 也分不开（F=0.59，p=0.68）。NLL 与闭环成功率 r=0.05 pooled / 0.04 long | variance Q6c 审计（范围已收窄） |
| A5 | **RTN：open-loop 明显更差，闭环只有一次实现，位于 GPTQ 范围底端** | RTN NLL 0.157（Static 的 1.7 倍），full-action match 0.410（其他约 0.50）。闭环 0.271 pooled / 0.108 long：pooled 恰好等于 18 个 GPTQ checkpoint 的最小值，long 也在底部。RTN 是确定性的，n=1。这与 benchmark 不敏感和约 0.06 的真实效应同样相容，是否可区分待 E1/E2 的 RTN re-roll 复制检验 | variance 审计 |
| A6 | **v0 的正结果是一个可以当教学案例的假阳性** | v0 retail FP-Traj − Static = +7 个任务（+0.121）；朴素 McNemar p=0.039；在可交换零假设下单侧 p=0.035。v1 的 306 个有序 checkpoint 对中有 17 对差距不小于这个值。v1 复验结果为 −0.035，CI [−0.176, 0.129] | variance Q8 审计；FINDINGS_V1 |
| A7 | **open-loop 翻转由状态决定，与 arm 无关** | 工具状态（n=572）翻转率与 BF16 NLL/token 的 Spearman ρ=0.736，任务聚类 CI [0.67, 0.77]；AUC 0.93（至少 9/18 个 checkpoint 翻转）；58.4% 的工具状态从不翻转（独立模型预期 3.9%）；翻转指示 φ：同 arm 0.548，跨 arm 0.538 | mechanism Q3 审计 |
| A8 | **失败以写操作为主，各 arm 分布相同** | BF16 成功而量化失败的 234 对：漏写 76、参数错 64、提前终止 52（max_steps 循环 46）、只多了写操作 42；arm×类别 p=0.94（用 tau2 `action_checks` 独立复现）。两点注意：write 状态的 open-loop 翻转率与其他工具状态相同（0.159 vs 0.166），也就是说失败集中在写操作，翻转本身并不偏向写操作；46 个 max_steps 循环**还没有区分是 agent 在重复还是 simulator 不停止**（见 §2.3 第 13 条） | mechanism Q5 审计 |
| A9 | **截断不会触发首次分叉** | t_tool < min(BF16 截断起点, Q 截断起点) 的占 95.9%（1406/1466；分析方报的 97.1% 只对照了 BF16 的起点） | truncation 审计 |
| A10 | **32k 对照在 4080 上可行（HANDOFF.md 写错了）** | KV 144 KiB/token；agent KV 池 42,816 tokens（5.88 GiB）；33,792-token 请求需要 4.64 GiB；BF16 加 6 个 checkpoint 的 32k 对照约 5–8 h 墙钟（倍率是外推值） | truncation Q4 审计 |
| A11 | **calibration 预算按状态数计** | v0 的 64k-token 预算只买到 10–13 个 context；v1 改为 64,000 activation rows 后得到 57 个状态/draw | 历史记录 |
| A12 | **实测吞吐（2×4080）** | BF16 85 个任务 902 s；W4 中位 2452 s、均值 2664 s（1140–4786 s，循环的慢尾占主导）；open-loop replay 约 16 min/checkpoint。GPTQ 量化：v0 配方 134 s/checkpoint；**v1 配方（64k activation rows）实测 6 个 checkpoint 35 min，约 6 min/个** | 历史记录 / truncation Q4 |

### 2.2 已证伪或需要改写（历史记录里「established」的说法要被覆盖）

| 原说法 | 现状 | 依据 |
|---|---|---|
| v0 FP-Traj > Static（+0.121） | **证伪**，改作假阳性教学案例 | A6 |
| CLOQ 核心假说（on-policy/novelty calibration 修复长程闭环） | **证伪**：6 个 arm 无可检测差异 | A2 |
| 「CLOQ-Novel 最差，coverage 不等于 success」（历史中标为 strong） | **降级为「没有可检测效应」**：它的末位落在 arm 置换零分布内（p=0.36） | variance 审计 |
| 「calibration-draw 方差主导方法差异」 | **改名**为「闭环评测噪声（轨迹 re-roll）主导」：draw-seed p=0.90；FP-Traj long 0.054–0.243 的跨度与 18 次 Bernoulli draw 的预期极差（约 0.19）相当 | variance Q2/Q3 |
| 「horizon amplification 强、已复现」 | **降级为边缘假说**：8k 下 A=0.137，任务加 checkpoint 双重 bootstrap CI [−0.039, 0.315]；主要来自 airline（0.294，n=27，其中 long 12 个），retail 只有 0.063 | truncation 审计 |
| 「3 of 3 signals 触发」 | **不再使用**：Signal C 靠的正是 A6 那个假阳性 | 历史 open_confounds |
| 「早期改写或漂移导致失败」 | **不支持**：同一任务内，第 0 步被改写与未改写的成功率差 +0.03，CI [−0.03, 0.09]；漂移解释的是分叉从哪里开始，不解释失败 | mechanism 审计 |
| 「closed-loop hazard 是 open-loop 的 2–6 倍」 | **不能引用**：分子分母是按步号对齐、实际不可比的状态 | mechanism 审计 |
| 「95.8% 行为分叉」 | 要加注：其中 120/1466 只是长度不同；第 1 步分叉中有 17%（178/1031）来自工具调用，不是改写 | mechanism 审计 |
| 「用 BF16 horizon 切分存在方向确定的选择偏差」 | **只能说方向不明**：自选择检查显示各 checkpoint 在自己 long 子集上的平均优势为 −0.038；改用量化 horizon 切分后差距缩到 +0.053（p=0.19），但没有消失 | variance / mechanism 审计 |
| 「RTN 落在 GPTQ 范围内，证明 benchmark 不敏感」 | **改为**「单次实现，位于 GPTQ 范围底端；是否可区分待 E1/E2 检验」 | A5 |

### 2.3 悬而未决（新实验要回答的）

1. **量化特有损伤和闭环本身的 re-roll 分不开**：现在没有任何 BF16 自身受扰动的运行。审计明确指出缺的就是这个对照。
2. **BF16 在 long 任务上的优势**：+0.122，tasks-fixed p=0.019，但这是最有利的 cutoff 下的结果。换相邻 cutoff p=0.04–0.22；任务重采样 CI [−0.018, 0.267]；逐任务方向 11 胜 12 负。规范 BF16 的 0.297 本身也可能只是运气好的一次实现（E1 检验它在 null 分布中的分位）。
3. **≥2 个写操作的任务上可能有系统损失**：BF16 6/29，全部 18 个 checkpoint 为 1–4 个；符号翻转检验 p=0.084。这个切分是看过 85 个 dev 任务后选的，效应集中在约 6 个任务上。确认性复验只能在 57 个非 dev 任务上做，预计其中只有约 19 个 ≥2 写任务（按 dev 上 29/85≈34% 估算），功效待 E0 计算。
4. **截断可能是中介变量**：量化 run 的截断率 0.50，BF16 0.26；提前终止的 run 截断比例 0.79，正常 run 0.15。
5. **user simulator 就是同一个冻结的 4B**：第 0 步改写后，69% 的 user 下一句会变（n=825），re-roll 的程度可能依赖这个设置。
6. **Q7 功效模拟没有经过独立审计**：type-I 0.10–0.76、功效 0.23–0.26、「约 10 draws × 170 tasks」都来自它。
7. **11 个 infrastructure_error 单元**：其中 9 个实际是 67–98 步的循环，对均值的影响不超过 0.002。在确定性 serving 下重跑会复现同样的循环，所以只有 2 个真正的基础设施故障需要重跑，另外 9 个进入第 13 条的循环归因。
8. **量化模型自身 margin 预测翻转的 AUC 没测过**：0.93 是用 BF16 NLL 这个 oracle 得到的。
9. **文档不一致**：README 写 46/68，冻结的 split 是 39/58，两者关系没有文档说明。
10. **s_c 没有直接测量**：A3 的 sc0/sc_point/sc_upper 全部靠「每个 checkpoint 一次实现」加 Bernoulli 模型间接推出。上界 0.054/0.082 宽到足以决定 E3 能不能做，而 C4、E3 功效和 MDE 都依赖它。
11. **RTN 只有 1 个 checkpoint**：W4/W8/W3-RTN 都是确定性的。n=1 时不存在 draw-as-unit 检验，E2 门控需要改用 run 级 re-roll 复制。
12. **整套结论默认 greedy 解码**（本机已核实：frozen_v0.json 中 agent 和 simulator 都是 temperature 0.0）。「参考模型只有一次实现」只在 greedy 下成立；τ-bench 的标准做法是对参考模型采样，再报告 pass^k。
13. **simulator 造成的循环没有归因**：open confound 记录了「simulator 不输出 stop token 会导致步数上限终止」（`max_steps` 200）。量化失败中有 46/234 是 max_steps 循环，现在全部算作 agent 失败。
14. **终点灵敏度没测过**：MDE 只按 db_match 算过。仓库里已有 tau2 `action_checks`（写操作级部分匹配，A8 用过），但没有拿来算 MDE。
15. **外部效度（harness）**：8192-token 截断来自自定义的 `cloq/context_policy.py`，不是 τ² 的默认设置。本 harness 中 42–72% 的量化决策被截断。C1、C7 都是在这个 harness 上测得的。

---

## 3. 文献地图与空白

| 工作 | 做了什么 | 与我们的关系 | 撞车风险 |
|---|---|---|---|
| [Flat Score, Amplified Failures](https://arxiv.org/abs/2607.27275)（2026） | 在 τ²-bench 上评测 INT4 agent：聚合分数不变，但已有失败模式最多放大 2.5 倍；收紧错误预算后分差从 1.3 拉到 16.7 个点 | 最近的邻居。只变 bit-width，单一 calibration、单次评测，没有噪声模型、参考分布或功效分析。「聚合分数掩盖损伤」这个 framing 已经被它占了。我们要回答的是：它报告的这些差值本身需要什么噪声模型；**收紧预算这类终点在 perturbation null 下能否分离**（E2 在我们的数据上复算） | **高** |
| Noise Floor Audit for Agent Benchmarks（URL 不在证据包，**全文未读，E0 必读**） | 据文献地图摘要：在 BFCL 上审计 serving 和 prompt 扰动带来的噪声 | 做的正是 prompt 扰动噪声审计，与 R-nonce/R-tool null 以及可占空白 #3 直接重叠。**读完全文之前，不对它「没做什么」下任何断言**；E0 读完后逐条对照空白 #1–#5 | **高** |
| Sclar et al. 2023 FormatSpread [†](https://arxiv.org/abs/2310.11324)；Mizrahi et al. 2024 multi-prompt evaluation [†](https://arxiv.org/abs/2401.00595) | prompt 格式敏感性；用一组无害 prompt 变体构造评测分布 | 「用无害 prompt 扰动构造评测分布」已经是既有方法。R-nonce/R-tool 直接引用它们，**prompt 扰动 null 本身不主张新颖** | 中（针对扰动 null 方法本身） |
| Signal and Noise（AI2，2025，URL 待补 †） | benchmark 的信噪比与决策可靠性 | 与「MDE / 灵敏度」贡献重叠。我们的区别只在：用已知退化梯度标定，研究对象是压缩模型与参考模型的差值 | 中 |
| Kapoor et al. AI Agents That Matter [†](https://arxiv.org/abs/2407.01502)；Agentic Benchmark Checklist（URL 待补 †）；HAL（URL 待补 †） | agent 评测的严谨性、可复现性、benchmark 设计清单 | 必须引用；E5 实践审计的编码表要与 ABC 的条目对齐 | 中低 |
| [VLAQuantBench](https://arxiv.org/abs/2609.25376)（2026） | VLA 闭环 PTQ：calibration 配方不可迁移 | 每个配置只报单点估计，没有做方差分解；领域是机器人 | 中低 |
| [Anatomy of a Closed-Loop Collapse](https://arxiv.org/abs/2609.23048)（2026） | 蒸馏后的 VLA 离线检查全过，闭环崩溃，用 on-policy 数据修好 | 研究对象是蒸馏不是 PTQ，结论是正结果；可以作为对照讨论 | 低 |
| [QuantVLA](https://arxiv.org/abs/2602.20309) | VLA 的 PTQ 方法 | 我们本地没能复现它（W3A8 在 libero_10 上 0.2%），只在讨论里作为评测脆弱性的旁证 | 低 |
| Williams & Aletras [†](https://arxiv.org/abs/2311.09755)；GPTQ calibration-seed 稳健性研究 | calibration 数据和 seed 在静态指标（perplexity/MMLU）上的影响；seed 层面结论是稳健 | 和我们**不冲突，可以互相解释**：open-loop 指标上 draw 确实可靠（A4），分辨率是在闭环里丢掉的 | 低 |
| COVERCAL / COLA；Damage Predicts Recovery；[Preserving LLM Capabilities through Calibration Data Curation](https://arxiv.org/abs/2510.10618) | 按 coverage 选 calibration；「压缩损伤够大时 curation 才有用」 | 支持「W4 下 calibration 差异可能太小，闭环测不出」；它们都没做闭环 | 低中 |
| Dutta et al. 2024 flips [†](https://arxiv.org/abs/2407.09141) | 单轮场景下，准确率相同时量化模型仍会翻转答案 | 「翻转集中在低置信状态」这一点**不能声称新颖**。我们能主张的是：在闭环里翻转集合与 calibration arm 无关 | 中（只涉及机制中的这一条子主张） |
| τ-bench pass^k [†](https://arxiv.org/abs/2406.12045)；τ²-bench [†](https://arxiv.org/abs/2506.07982)；Beyond pass@1（URL 待补） | 单个模型的采样可靠性 | 不涉及「压缩模型 vs 参考模型」差值的推断，也没有 draw 作为推断单位。审稿人会问「用温度采样加 pass^k 不就行了」，所以 E1 加入采样 null，E2 把 pass^k 类指标列为候选终点 | 中低 |
| Bouthillier et al. 2021 [†](https://arxiv.org/abs/2103.03098)；Dodge et al. 2020 [†](https://arxiv.org/abs/2002.06305)；Card et al. 2020 [†](https://arxiv.org/abs/2010.06595)；Madaan et al. 2024 [†](https://arxiv.org/abs/2406.10229)；Adding Error Bars to Evals [†](https://arxiv.org/abs/2411.00640) | 方差来源随机化、seed 方差、功效分析、评测误差条 | **统计工具本身已有先例**。draw-as-unit、聚类推断、功效分析都只作为引用来的标准工具，不作为我们的贡献 | 中（针对「方法新颖性」） |
| Thinking Machines batch invariance [†](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/) | 消除 LLM 推理的非确定性 | 我们直接使用，不主张新颖。要补的一点是：在 greedy 下，确定性让参考模型只剩一次实现，但轨迹噪声还在 | 低 |
| QuantNoise [†](https://arxiv.org/abs/2004.07320) 等「量化即噪声」工作 | 把量化建模成加性噪声 | 等保真度高斯噪声这个思路是已知的。我们的新意只在闭环维度：用它区分量化特有损伤和一般扰动造成的损伤 | 中（针对 iso-fidelity 子主张） |
| FrugalGPT [†](https://arxiv.org/abs/2305.05176)、置信度 cascade/deferral、any-precision | 按置信度回退到更强的模型 | 直接覆盖了 P3 提的 margin 门控升精度，所以它只能作为「已知方法在闭环下的评测」 | **高**（针对 P3） |
| DAgger [†](https://arxiv.org/abs/1011.0686)、GKD [†](https://arxiv.org/abs/2306.13649)、MiniLLM [†](https://arxiv.org/abs/2306.08543)、Train Where the Quantized Model Goes（URL 待补） | 用梯度训练做 on-policy 修正 | 背景文献。我们的负结果是 one-shot calibration，不是训练 | 低 |
| LLMs Get Lost in Multi-Turn Conversation [†](https://arxiv.org/abs/2505.06120)；Numerical Instability and Chaos（URL 待补） | 多轮退化；推理的混沌性 | 为 re-roll 机制提供背景，二者都不涉及量化 | 低 |

**可以占住的空白**（文献地图列为未被占，且和我们的数据对得上）。E0 读完 Noise Floor Audit 全文后逐条复核。**新颖性主张收窄为三点：压缩-参考差值推断（#1）、draw 与 re-roll 的分离（#1 与 E1 的 W4 re-roll 复制）、梯度标定的 MDE（#2）。** #3–#5 在本设置下作为支撑性发现报告，不单独主张新颖。

1. 在闭环压缩 agent 上做 calibration-draw 复制，并以采样得到的 BF16 参考分布（而不是单次规范实现）为基线，做任务级的压缩-参考差值推断。prompt 扰动 null 的构造方法本身引用 FormatSpread / multi-prompt 评测。
2. 退化梯度给出的 benchmark 最小可检测退化（MDE），按终点分别给出：db_match、写操作级、失败模式、收紧预算、pass^k 类。这是一个其他论文都可以报告的灵敏度数字。
3. **限定在 greedy 协议下**的一个具体论点：确定性 serving 藏起了轨迹噪声，并没有消除它。非 greedy 下是否成立，由 E1 的采样 null 检验。
4. 闭环里的 re-roll + damage 分解，以及「翻转集合与 calibration 无关」。
5. 在闭环 agent PTQ 里把截断和 horizon 分开的对照（E4）。

**不能声称新颖的**：
- closed-loop ≠ open-loop 这个一般结论（驾驶和 VLA 领域都有）；
- batch invariance；
- draw-as-unit 与功效分析这些统计工具本身；
- 用无害 prompt 扰动构造评测分布；
- benchmark 信噪比 / 灵敏度的一般框架；
- agent 评测严谨性清单；
- 「翻转集中在低置信状态」；
- 置信度回退。

---

## 4. 推荐主线

### 4.1 Thesis

在闭环里，压缩后的 agent 相当于对 BF16 做了一次扰动，扰动的结果是重新采样轨迹。在 greedy 解码加确定性 serving 下，BF16 只贡献一次实现，所以在约 100 个任务的规模上，压缩模型之间以及压缩与参考之间的差异大部分是 re-roll 噪声，而标准的「对任务配对」检验会把这些噪声当成方法效应。要做出有效结论需要四件事：
1. 采样得到的参考分布：BF16 perturbation null，greedy+扰动与温度采样两种；
2. 以 calibration draw 为单位的推断，并用同一 checkpoint 的 re-roll 复制把 draw 方差和 re-roll 方差分开；
3. 按功效分析确定的实验规模；
4. 用已知退化程度的梯度标定 benchmark 的灵敏度，并比较不同终点的灵敏度。

我们提供这四件，用它们推翻自己早先的正结果，再用一个预注册、交叉拟合、功效足够的确认性研究，给一个真实问题一个确定的答案。如果 E2 显示原问题测不出，按 §9.3 的规则改测一个预测可检测的对比。

机制部分（从 P2 移植）把闭环效应拆成两部分：
- re-roll：是否在很小扰动下就饱和，由 α_min 高斯 rung 检验；
- damage：随误差大小增长，本文需要检验它是否存在。

论文的结论形式是「哪个闭环终点、在多大规模上测得出」，而不是单纯的「闭环测不出」。

### 4.2 标题候选

1. **Every Checkpoint Is a Re-Roll: What Closed-Loop Benchmarks Can and Cannot Detect About Compressed LLM Agents**（首选）
2. **Worse, or Just Re-Rolled? Perturbation Nulls and Sensitivity Ladders for Evaluating Quantized Tool Agents**
3. **Deterministic Serving Hides Trajectory Noise: A Measurement Protocol for Closed-Loop Evaluation of Compressed Agents**

范围要在标题或摘要里写明：一个 4B 模型、τ²-bench retail+airline、同模型作 user simulator、以 greedy 为主协议（采样作为检验）、8k 与 32k 两种 harness。

### 4.3 核心 claims

| Claim | 内容 | 状态 |
|---|---|---|
| C1 | 在 85 个 τ² 任务、8k harness、greedy、db_match 终点下，闭环成功率在 5 个点的尺度上分不开压缩 checkpoint。RTN（1.7 倍 NLL）的单次实现位于 GPTQ 范围底端 | 部分已有（A2、A3、A5）。只报 implied SD 和上界，不写「explains none」。RTN 是否可区分待 E1/E2；harness 依赖性待 E4 |
| C2 | open-loop 和闭环测的是不同的东西。open-loop 唯一可靠的 arm 效应是 Static 相对其余 arm，而这个效应与闭环成功率无关 | 已有（A4）。严格限定在 Static vs 其余 |
| C3 | 机制：扰动引发轨迹 re-roll；翻转集合由状态本身决定，与 calibration arm 无关；失败主要是写操作层面 | 已有（A7、A8）。不写「改写导致失败」。「与 arm 无关」在 5 个轨迹 arm 连 open-loop 都分不开的情况下有一定必然性，要明说。循环类失败要先按 agent/simulator 归因（E0） |
| C4 | 常用推断方法在这个场景下 miscalibrated：单 draw 的 task bootstrap 和对任务配对的 t 检验偏松，crossed bootstrap 过于保守 | **E0 独立复算、E1 直接测得 s_c 之前，一律写成 model-based** |
| C5 | 教学案例：v0 +0.121 在零假设下 p=0.035，复验反号 | 已有（A6） |
| C6 | 参考模型必须被采样：用任务级配对估计量（damage Δ、相对规范 BF16 的翻转率、规范 BF16 在 null 中的分位）给出 re-roll 与 damage 的分解；用 W4 re-roll 复制直接估计 s_c；报告 greedy 与采样两种 null 的结论是否一致 | 待建立（E1、E1b） |
| C7 | 退化梯度（W8/W4/W3 × GPTQ/RTN，加等 NLL 的高斯噪声和 α_min 高斯）在多个候选终点上给出 benchmark 的 MDE，并回答「GPTQ 是否比同保真度的随机扰动更差」「re-roll 是否在极小扰动下饱和」 | 待建立（E2） |
| C8 | 对一个预注册的对比给出确定答案：检出、TOST 等价（margin 由 E2 MDE 和实践阈值共同确定），或记录为功效模型失败。默认是 Static vs FP-Traj；按 §9.3 的规则可能改为梯度上预测可检测的对比 | 待建立（E3） |
| C9 | harness 依赖性：同一批模型在 8k 与 32k 下，re-roll 与 damage 估计量的配对差 | 待建立（E4，无条件执行） |

### 4.4 为什么有影响力

- **谁会引用**：所有报告压缩或量化 agent 闭环差值的论文，包括 Flat Score 这条线、VLA 量化这条线、agent 可靠性评测这条线。我们给它们一个应当报告的数字（按终点的 MDE），以及一个应当对照的零分布。
- **容易记住的故事**：
  - 「greedy 下的确定性让你以为噪声没了，其实只是把参考模型的 re-roll 固定成了一次」；
  - 「RTN 的 NLL 是 1.7 倍，闭环 db_match 需要多少复制才分得出来」；
  - 「我们自己的预注册胜出复验时反号」；
  - 「换一个终点，同样的预算能看到什么」。
- **能推广**：re-roll + damage 分解适用于任何权重扰动（量化、剪枝、LoRA merge、kernel 更换）。
- **诚实的上限**：一个模型、一个 benchmark 家族、同模型作 simulator、以 greedy 为主协议、自定义截断 harness。所以 E1b（换一个 simulator）、E1 的采样 null、E4 的 32k 对照都进入核心计划，不再是可选项。

### 4.5 与已有工作的区别（一段话版本）

- **Flat Score**：说明「分数平而损伤被放大」。我们说明这种分数差本身需要噪声模型，并在我们的 null 下复算它的收紧预算分析，看哪些终点在多大规模上真正分得出来。
- **Noise Floor Audit**：做的是 agent benchmark 上的 prompt 扰动噪声审计。与它的具体区别要等 E0 读完全文再写。我们不主张 prompt 扰动 null 本身新颖（FormatSpread、multi-prompt 评测已确立这种方法），只把它当作构造参考分布的工具。
- **我们的贡献**：限定在压缩模型对参考模型的差值推断、draw 与 re-roll 的分离、用已知退化梯度标定的 MDE。
- **静态 calibration-seed 研究**：它们发现 draw 稳健。我们发现 open-loop 上确实稳健，分辨率是在闭环里丢失的，这把两类结果统一起来，而不是互相矛盾。
- **统计工具与评测严谨性**：统计工具引用 Bouthillier / Card / Madaan 等人的工作；信噪比框架引用 Signal and Noise；评测严谨性引用 AI Agents That Matter / ABC / HAL。这些都不作为贡献。

---

## 5. 被合并或放弃的方向及理由

| 提案 | 处理 | 理由（结合评审意见） |
|---|---|---|
| P1 Every Checkpoint Is a Re-Roll（均分 7.875） | **作为主干** | 四个视角里三个排第一；可以确定地产出结论；GPU 预算与实测吞吐对得上 |
| P2 Re-roll, Not Drift（6.75） | **合并为机制部分**：BF16 re-roll 家族（E1）、剂量与 bit 梯度（E2，含 α_min rung）、within-row permuted-geometry 对照（E2b，设门控）；放弃标题里的全称判断 | 它的控制设计最好，但「calibration cannot repair」不被数据支持：功效 0.23–0.26 下的 null（model-based）；TIM-GPTQ 在 W2/W3 上有收益。「damage 集中在写决策」与 write 状态翻转率相同（0.159 vs 0.166）矛盾。135 GPU-h 且依赖链长 |
| P5 Worse, or Just Re-Rolled?（7.0） | **合并为快速阶段**：E0–E2 完成后可以先出 arXiv 或 workshop 版本 | 它是 P1 的子集，少了确认性研究；「explains none」这类表述改为给出上界 |
| P4 跨域等保真度（5.83 / 5.5） | **只移植 tau2 上的 iso-fidelity 检验**（E2 的 NLL 匹配高斯 rung）；**VLA 分支不进入本文关键路径** | 4080 上 LIBERO 的吞吐和确定性都没测过，它的 E3 需要 5700 个 episode；W4g128 在 GR00T 上可能接近无损，从而破坏「同一量化器」的前提；aspq 的证据在审计后很弱（65→61 是单 seed null，SE 约 6.8pp；cal=2 的崩溃是 outlier-channel 预算机制造成的）。泛化性改由第二个 simulator 或模型来补 |
| P3 margin 门控升精度 MGE（4.75） | **降为有门控的探索（E7）或后续论文**，不进主线 | 置信度 cascade 和 deferral 已覆盖这个方法；W4 可修复空间只有 0.044，CI 跨 0；配对 Δ 的 SD 约 0.05，功效不足；它的 headroom 检验把 temperature 0.7 的 simulator 和 greedy simulator 放在一起比，条件不一致。值得保留的是它的 τ=∞ / τ=0 两端逐字节复现检查，以及「匹配升精度率的随机对照」设计 |
| 作品集建议：TIM Density 加权 arm、JARQ 精修、DuQuant 旋转 backbone、GUI-agent 兄弟计划 | **暂停** | E2 给出 MDE 之前，任何新 arm 或新求解器都无法在闭环里评估；它们提高的是 open-loop 保真度，而 A4/A5 显示闭环 db_match 目前看不到保真度差异 |

---

## 6. 实验计划（按优先级）

通用约定：
- **硬件**：只用本机 2×4080。agent 占一张卡，simulator 占另一张，闭环实验只能串行；**GPU-h ≈ 2 × 墙钟**。
- **配置**：所有新配置从冻结配置复制出新文件，不改原文件。注意（本机已核实）：`cloq/config.py` 硬编码读取 `configs/frozen_v0.json`，`frozen_v1.json` 里没有 `context_policy`。context 长度改用 `CLOQ_MAX_PROMPT_TOKENS` 环境变量（config.py 第 26–27 行已支持），或者新建 `frozen_v2.json` 并修改 `CONFIG_PATH` 的读取逻辑（改代码要提交并在 PREREG 注明）。
- **终点**：确认性主终点是 db_match。E2 起同时计算候选终点，E3 的主终点按 §9.3 的规则确定。
- **推断单位**：GPTQ 用 checkpoint（draw）；RTN 与高斯 rung 用 run（nonce re-roll 或噪声 seed）。run 级复制只测 re-roll 方差或噪声 seed 方差，不含 draw 方差，报告时写明。
- **主估计量**：任务级配对量，公式见 E1 和 §9.3。run 均值的方差比只作描述性报告，不作决策门。
- **任务范围**：没有 calibration 泄漏的臂（BF16 null、RTN、高斯噪声）尽量在全部 142 个 stable 任务上跑；GPTQ 臂只能在 85 个 dev 任务上跑。
- **解码与 harness**：greedy 为主协议，E1 的采样 null 检验外推；8k 为主 harness，E4 的 32k 对照无条件执行，切换规则见 §9.3。

### E0（本周 9/28–10/4 可执行）：审计缺口、预注册冻结、零噪声复验

- **目的**：把已有数据变成冻结的论文表格；在花新的 GPU 时间之前补齐审计缺口、功效计算和文献核查。
- **设计**：
  - (a) 重跑 2 个真正的基础设施故障单元。另外 9 个标为 infrastructure_error 的实际是循环，在确定性 serving 下重跑会复现，所以并入 (i) 做归因。
  - (b) **独立重写** Q7 功效模拟、GLMM 和 Beta-binomial 拟合，要求与原结果的差在 Monte Carlo SE 0.02 以内。**必须按 E3 的真实几何重算**：2 fold、每个 checkpoint 约 71 个任务、D=10，在 sc0 / sc_point / sc_upper 三种情形下分别计算。E1 测得 s_c 后再重算一次（E0-b′）。
  - (c) 冻结 `PREREG_EVAL.md`，git 打时间戳，内容见 §9.3。
  - (d) 确定性复验：用同一 seed 跑两遍 nonce 扰动，验证新 prompt 下仍然确定。**再在 temperature 0.3/0.7、固定 per-request seed 下双跑 5–10 个任务，验证采样在 batch-invariant 下逐 seed 可复现**，这是 E1 采样 null 的前提。
  - (e) 纠正 HANDOFF.md 中关于 32k 的说法；在 README 里说明 46/68 与 39/58 的关系；实现 32k 配置路径（env 变量或 frozen_v2），并提前把 E4 要用的 W3-RTN 量化好（RTN 不需要 calibration）。
  - (f) 从 variance 和 mechanism 两份审计里删除不能再用的表述（0.24% 方差占比、2–6 倍 hazard、「漂移导致失败」）。
  - (g) **新估计量的功效模拟**：按 E1 的真实 R（null 8/6、采样 4、W4 re-roll 4）和 T（85/142），用模拟算出 §9.3 中 Δ、翻转率差、BF16 分位检验、long/≥2 写子集 Δ 各自的功效和 MDE。方差比只作描述性报告，因为 null R=6–8 对 W4 18 时，方差比的 F 抽样区间约 [0.3, 3]，没有分辨力。
  - (h) **文献核查**：读完 Noise Floor Audit 全文，逐条对照可占空白 #1–#5，并据此改写 §3、§4.5。核对所有 † 引用，包括 FormatSpread、multi-prompt 评测、Signal and Noise、AI Agents That Matter、ABC、HAL，补上缺的 URL。
  - (i) **循环归因（CPU）**：对全部 max_steps、too_many_errors 以及被标为 infra 的循环 run（量化 145 个提前终止中的循环部分，含 A8 的 46 个），判断重复的是 agent 轮还是 user 轮、user 是否输出了 stop，分为 agent 侧、simulator 侧、混合三类。归因规则在不看 arm 标签的情况下固定。报告剔除 simulator 侧循环后 A8、A2、C1 的敏感性分析。
  - (j) **≥2 写假说复验的功效计算**：确认性检验只在 57 个非 dev 任务上做（预计约 19 个 ≥2 写任务）。可用的量化复制包括 RTN re-roll（E1）、高斯 seed rung 与 W3/W8-RTN re-roll（E2），可选再加反向 split 的 GPTQ（只在 dev 任务上做 calibration，在非 dev 上评测）。功效 <0.5 就在 PREREG 里明确标为探索性。
- **2×4080**：可以做。
- **GPU 时**：约 3 GPU-h（含采样可复现性双跑）；其余在 CPU 上。
- **决策门**：
  - 独立重算的当前设计功效 ≥0.6（+0.05 pooled），或 draw-as-unit 检验的 type-I 错误超过 0.07：C4 不成立，论文缩为 workshop 短文。
  - E3 几何在 sc_upper 下功效 <0.5：E3 的主终点改为 TOST 等价，检出降为次要终点（E1 测得 s_c 后复核）。
  - (g) 显示 E1 计划的 R 下 Δ 对 0.05 的功效 <0.5：在开跑前上调 R，或者把相应估计量标为描述性。
  - (d) 的采样可复现性不通过：采样 null 改为「多 seed 独立样本」，不做 seed 级配对复用，并在 PREREG 注明。

### E1（10/1 预注册提交后开跑，10/12 前完成）：BF16 re-roll 家族、W4 re-roll 复制、采样 null

- **目的**：检验 C6。三件事：
  1. BF16 权重完全不变，只做 agent 侧的中性扰动或温度采样，看量化相对这个参考分布有没有 damage；
  2. 对已有 W4 checkpoint 施加同样的扰动，直接估计 s_c 和任务内 re-roll 方差；
  3. 检验 greedy 是特例还是一般情况。
- **设计**：user simulator 在 greedy 家族中保持 greedy，与已有量化 run 的条件一致，以修正 P3 的问题。
  - **Null 家族 1（greedy + prompt 扰动）**：
    - R-nonce：system prompt 末尾追加一行随机 8-hex，R=8；
    - R-tool：工具 schema 顺序置换加空白级编辑，R=6；
    - R-para（诊断用）：强制第 0 步使用预先写好的改写，R=3，只在 dev 上跑。
    - R-nonce 和 R-tool 在 142 个任务上评测。
  - **Null 家族 2（温度采样）**：BF16 在 temperature 0.3 和 0.7 下各 R=4 个固定 seed（agent 采样，simulator 保持 greedy），在 85 个 dev 任务上跑。
  - **W4 re-roll 复制**：
    - Static c1、FP-Traj c1、CLOQ-Novel c1 三个已有 GPTQ checkpoint，各施加 R-nonce R=4（与 BF16 用同一组 nonce），在 85 个 dev 任务上跑；
    - RTN 施加 R-nonce R=4，在 142 个任务上跑。它是 W4-RTN rung 的 run 级复制，测的是 re-roll 方差，不含 draw 方差。
  - **W4 采样**：FP-Traj c1、Static c1 在 temperature 0.7 下各 R=4，在 85 个 dev 任务上跑。
  - **主估计量**（任务级配对量，公式写进 PREREG）。记 p̂_t(F) 为家族 F 的 run 中任务 t 成功的比例，Y_t^canon 为规范 BF16 的结果：
    - (a) **damage**：Δ = mean_t[p̂_t(null) − p̂_t(W4)]，按任务聚类 bootstrap 做 CI。W4 端分别用 18 个 checkpoint 的单次实现和上面的 re-roll 复制。
    - (b) **re-roll**：flip_F = mean_{r,t} 1[Y_rt ≠ Y_t^canon]，拆成损失（1→0）和获得（0→1）两部分，比较 null 与 W4。
    - (c) **规范 BF16 在 null 分布中所处的分位**：分 pooled 和 long，直接检验 long 上的 0.297 是不是运气好的一次实现。
    - (d) 对 task-spec 定义的 long 子集（所需动作数高于中位数）和 ≥2 写子集做同样的 Δ。≥2 写子集在 dev 上只作描述，确认性检验只在非 dev 上做（见 E0-j）。
    - (e) **s_c 的直接估计**：对「checkpoint × 扰动 × 任务」拟合嵌套 GLMM 或 ANOVA。18 个单次实现提供「checkpoint 间 + re-roll」的总方差，4 个 checkpoint × R=4 提供任务内 re-roll 方差，两者相减得 s_c²。把估计值代回 E0-b′ 的功效重算和 E3 设计。
    - 描述性：分叉率（相对规范 BF16 轨迹）、run 均值方差比。
- **2×4080**：可以做。
- **GPU 时**（墙钟）：

  | 项目 | 墙钟 |
  |---|---|
  | R-nonce + R-tool：14 × 约 0.55 h | 7.7 h |
  | R-para：3 × 0.33 h | 1 h |
  | BF16 采样：8 × 约 0.3 h | 2.4 h |
  | W4 GPTQ re-roll：12 × 0.68 h | 8.2 h |
  | RTN re-roll：4 × 约 1.14 h（142 个任务） | 4.6 h |
  | W4 采样：8 × 0.68 h | 5.4 h |
  | **合计** | **约 29–31 h ≈ 60 GPU-h** |

- **决策门**（具体数值阈值由 E0-g 的功效模拟定，写入 PREREG）：
  - 两个 greedy null 家族（R-nonce 与 R-tool）的均值差超过 0.05：没有可信的参考，C6 改写。
  - K1：R-nonce 分叉率 <50%（W4 为 95.8%），则「任何扰动都会 re-roll」这一前提不成立。论文改为「量化扰动在闭环里是特殊的」，同样可以报告。E2 的 α_min rung 一并参考。
  - 规范 BF16 的 long 成功率高于 null 分布的 90% 分位：把「BF16 long 优势」改写为「很大程度上是参考模型的一次幸运实现」，之后所有 damage 一律相对 null 均值计算。
  - s_c 的 95% 上界 <0.03：re-roll framing 成立。s_c 的下界 >0.02：报告「存在真实的 checkpoint 异质性，加上功效不足」，E3 照常做，但按新的 s_c 重设 D。
  - 采样 null 与 greedy+nonce null 给出的 Δ 或翻转率差超出 CI：论文写明 greedy 是特例，空白 #3 只在 greedy 下主张。二者一致时，写成一般结论。
  - 无论哪种结果，Δ 都写入论文，可能为 0，也可能为正。

### E1b（与 E1 并行准备，10/12 前完成可行性检查）：换一个 user simulator 做泛化检查

- **目的**：回应四个视角共同指出的问题（同一个 4B 自己模拟 user）。检验 re-roll 噪声底、MDE 和循环率是否依赖 simulator。
- **设计**：
  - 先做可行性检查：选一个不同家族、能放进 16GB 的 simulator，先跑 BF16 在 20 个任务上，要求成功率不在地板上、能正常停止、确定性复验通过。具体模型待显存核算后确定，不预设。
  - 通过后跑 R-nonce R=3、W4-GPTQ 3 个（Static c1、FP-Traj c1、CLOQ-All c1，按预注册规则选）、RTN，都在 85 个 dev 任务上。
  - 按 E0-i 的规则对循环归因，**报告换 simulator 后 max_steps 循环率，尤其是 simulator 侧循环，是否下降**。
- **2×4080**：条件可行（simulator 独占一张卡）。
- **GPU 时**：约 **10–12 GPU-h**。
- **决策门**：
  - 两个 simulator 下 Δ 或翻转率的差超过各自 CI，或 null 与 W4 翻转率之比相差超过 2 倍：把 simulator 写成协议里的一级因素。
  - simulator 侧循环率明显下降：在 PREREG 允许的范围内，把原 simulator 的这类循环按「simulator 无效」处理。
  - 可行性检查不通过：列为限制，并在 E6 中用 A100 再试。

### E2（10/13–10/26）：退化梯度 + iso-fidelity + 多终点灵敏度（damage 剂量）

- **目的**：检验 C7。四个问题：
  - 得到每个候选终点的 MDE；
  - 回答「GPTQ 是否比 open-loop 保真度相同的随机扰动更差」；
  - 检验 damage 是否随误差大小单调增长；
  - 检验 re-roll 是否在极小扰动下饱和。
- **设计**：新 checkpoint 全部从原始 BF16 量化得到（`quantize.py --wbits` 已支持）。
  - **RTN 类（run 级复制，只含 re-roll 方差）**：
    - W8-RTN × R-nonce R=4（142 个任务）；
    - W3-RTN × R-nonce R=4（142 个任务）；
    - W4-RTN 复用 E1 的 R=4。
    - 另一个选项：用 stochastic-rounding RTN 的不同 seed 作为多个免 calibration 的复制。二选一写进 PREREG。
  - **GPTQ 类**：
    - W8-GPTQ ×3（fp_traj 配方，dev）；
    - W3-GPTQ ×3（dev）；
    - 复用已有 W4-GPTQ 18 个。
  - **高斯噪声**：各层噪声范数按 GPTQ 误差比例设置，全局系数 α 用 bisection 在 200 个状态上校准：
    - 匹配 W4-GPTQ-traj NLL（0.076）的 ×3 个 seed；
    - 匹配 RTN NLL（0.157）的 ×2 个 seed；
    - **α_min rung**：NLL 增量不超过 W8 水平，R≥4 个 seed。它与 BF16 prompt null、W8 放在一起，构成 re-roll 饱和曲线的左端点，K1 的判定也同时参考它的分叉率。
    - 以上都在 142 个任务上跑，同时报告工具调用解析失败率，偏离超过 2 倍就判这个 null 不公平。
  - 每个新 checkpoint 或 seed 都做 open-loop replay（1046 个状态）。
  - **多终点**：对每个 rung 同时计算以下候选终点，比较每个终点的 MDE 和对 null 的分离度（任务级 Δ 的标准化效应）：
    - db_match；
    - 写操作级 action_match 比例（tau2 `action_checks`）；
    - 失败模式率：漏写、参数错、agent 侧循环（按 E0-i 归因）、工具名幻觉；
    - Flat Score 式的收紧预算分数；
    - pass^k 类可靠性：跨 re-roll 或 seed，任务在全部 k 次中都成功的比例。
  - **Flat Score 复算**：在我们的数据上重做它的收紧预算分析，检验同类差距在 perturbation null 下能否分离。
  - **拟合与功效**：拟合「闭环终点 ~ open-loop NLL」的单调曲线，零点取 E1 的 null。按终点报告在 E3 几何下达到 80% 功效所需的 NLL 比值。
  - **≥2 写确认性复验**（按 E0-j 的功效判定是确认性还是探索性）：只在 57 个非 dev 任务上，用 RTN re-roll 和高斯 seed 复制对照 E1 null。
  - **E2b（有门控）**：within-row permuted GPTQ 误差 ×3，只在 W3 或高 α 上已经分出 damage 时才跑。
- **2×4080**：可以做。
- **GPU 时**：闭环约 26 h 墙钟（W3 按 W4 的 1.5 倍计），replay 约 4.5 h（部分可与 simulator 卡空闲时重叠），合计约 28–31 h 墙钟 ≈ **55–62 GPU-h**；E2b 另加约 8 GPU-h。如果 §9.3 的 harness 切换规则触发，按 32k 倍率 1.1–1.5 上调。
- **决策门**：
  - n=85 时闭环 db_match 已经把梯度排得很干净：与 rung 的 Spearman ≥0.9，且 W4-RTN（E1 的 R=4 re-roll，以 run 为单位）相对 E1 null 的 Δ 任务聚类 CI 不含 0。此时 C1 不成立，转入 K-ladder 判定。
  - W3 能分开而 W4-RTN 分不开：灵敏度阈值定位成功，这是预期结果，可以发表。
  - 某个非 db_match 终点在 W4 上能分开而 db_match 不能：写成「终点选择决定可检测性」，这个终点进入 §9.3 的 E3 终点选择。
  - W8、W4、W3 与 null 之间在所有候选终点上都没有单调趋势（rung 层面的 Spearman CI 含 0）：没有可分辨的 damage（K2），停止一切方法类工作。

> **里程碑（约 10/27）**：E0–E2 和 E4 完成时，已经足够写一篇 arXiv 或 workshop 版本（P5 的快速阶段），用于在 Flat Score 这条线之前确立优先权。

### E3（10/27–11/16）：预注册、交叉拟合、功效足够的确认性研究（默认 Static vs FP-Traj）

- **目的**：检验 C8，并完整演示一遍协议。同一个问题曾经得到一个假阳性（v0）和一个无法解读的 null（v1）。
- **预注册的改道规则**（写死在 PREREG，10/27 go/no-go 时机械执行）：
  - 两者的 open-loop NLL 比只有 0.094/0.076≈1.24，而 NLL 差大得多的 RTN 在闭环里都分不开。所以如果 E2 标定的「E3 几何下 80% 功效所需 NLL 比值」在所选终点上 >1.24，Static vs FP-Traj 预计测不出，按以下顺序改道：
    1. E2 预测 W3-GPTQ vs W4-GPTQ 在 E3 几何下功效 ≥0.8：把 E3 改为 W3-GPTQ vs W4-GPTQ，设计相同，用一个可检测的对比演示协议；
    2. 否则，如果 E0-j 显示 ≥2 写假说的确认性复验功效 ≥0.5 且 E2 未完成它：把部分算力转给这个复验；
    3. 否则，保留 Static vs FP-Traj，主终点直接改为 TOST。
  - **TOST margin** 不拍定 0.05，由两部分共同确定：一是 E2 给出的 E3 几何下 80% 功效可达的等价界；二是 PREREG 中预先写明的实践意义阈值 δ_prac（参照「部署上可接受」的损失，例如 W8 相对 BF16 null 的 Δ）。margin = max(二者)。当前者大于 δ_prac 时，明确报告「在实践阈值上无法做等价判定」。
- **设计**：
  - 142 个 stable 任务按领域和任务说明长度分层，2-fold 交叉拟合：在 A fold 上做 calibration、B fold 上评测，然后交换。BF16 轨迹来自 v0 已有的全任务 run。
  - 每个 arm 每个 fold D=10 个 draw（按 E1 实测的 s_c 在 E0-b′ 复核），共 40 个 checkpoint；沿用 v1 的 64k activation-row 预算。
  - 主终点按 §9.3 的终点选择规则确定，db_match 始终报告。
  - 主检验：以 fold 为 block 的 Welch t（单侧 α=0.05）加 TOST；如果 E0 或上面的改道规则触发，TOST 为主终点。
  - 次要：用 task-spec 定义的 long 子集；以 E1 null 为参考。**涉及写操作的次要终点单独报告非 dev 子集**，因为 ≥2 写切分是在 85 个 dev 任务上选出的。
  - 所有设置在量化开始前冻结并提交。
- **2×4080**：可以做；open-loop replay 可以趁 simulator 卡空闲时插空跑（v1 验证过这种做法）。
- **GPU 时**：
  - 量化按 v1 实测约 6 min/个，40 个约 **4 h**（不是 1.5 h）；
  - 闭环 40 × 71 任务 × 约 31 s ≈ 24.5 h 墙钟；
  - replay 约 8 h，可重叠；
  - 合计约 30–33 h 墙钟 ≈ **60–66 GPU-h**。
- **决策门**：检出、等价、不确定三种结果都报告。结果不确定时，用观测到的 checkpoint SD 重估实际功效；实际功效 <0.5 时，在投稿前上调论文中的设计建议，把这次失败作为一个 case 写进功效表。

### E4（**无条件执行，提前到 E1 之后、E2 之前，约 10/8–10/12**）：8k vs 32k harness 对照

- **目的**：回答外部效度质疑：噪声或不敏感是不是 harness 截断历史造成的。
  - τ² 标准设置不做这种截断；
  - 本 harness 中 42–72% 的量化决策被截断；
  - 量化 run 的截断率约为 BF16 的 2 倍；
  - 提前终止的 run 截断比例 0.79，正常 run 0.15。

  原先把 E4 门控在「long 效应 p<0.1」之后，而这个效应本身只有约 1.9 SE，门控大概率不打开，所以改为无条件执行。
- **设计**：
  - 配置：`CLOQ_MAX_PROMPT_TOKENS=32768`（或 frozen_v2），server `max-model-len` 33792，util 0.92–0.95，并发 4–6。
  - 先在 32k server 上 replay 200 个已存 context，要求 1.000 一致；通过后复用从未截断的 pair（按 A9，95.9% 的前缀在首次分叉前两种 harness 下逐字节相同）。
  - 在 85 个 dev 任务上跑：BF16 R-nonce R=3（与 E1 同 nonce）、RTN、Static c1 / FP-Traj c1 / CLOQ-Novel c1（与 E1 的 W4 re-roll 集合相同）、一个 E2 rung（W3-RTN，E0 已量化）。
  - **估计量**：同一批模型、同一 nonce 下 8k 与 32k 的配对差，包括 re-roll（翻转率）、damage Δ、A（horizon amplification），以及循环率、截断率。ΔA = A_32k − A_8k 按审计意见不与 18 个 checkpoint 的 0.137 比较。W3-RTN 的 8k 对应 run 在 E2 中优先跑。
- **2×4080**：可以做（A10）。
- **GPU 时**：BF16 3 × 0.25 h × 1.1–1.5 加上 5 个量化 run × 0.68 h × 1.1–1.5，再加 replay 审计，约 5–7 h 墙钟 ≈ **10–14 GPU-h**（倍率是外推值）。
- **决策门**：
  - 若 32k 下 re-roll 或 Δ 的配对差 CI 不含 0 且方向是「32k 更能分辨」：按 §9.3 的规则，**从 E2 起以 32k 作为主 harness**，8k 作为历史对照，E2/E3 预算按 1.1–1.5 上调。
  - ΔA 的上界 <0：报告截断是中介。
  - 效应保持：作为次要发现。
  - 无论结果如何，都写进 harness 披露表。

### E5（11–12 月，CPU）：实践审计 + 工具包 `cloq-eval`

- **目的**：说明问题在已发表工作中普遍存在，并把修正方法做成一条命令。
- **设计**：
  - (a) 对 25–40 篇压缩 agent 和闭环 VLA 论文编码以下信息：任务数、draw 数、rollout 数、CI 方法、是否确定性 serving、解码温度、是否对参考模型采样、使用的终点。编码表与 Agentic Benchmark Checklist 的条目对齐。用我们的功效计算器估计它们所报差值中功效不足的比例。
  - (b) 发布：batch-invariant serving 加 replay 审计、perturbation-null 生成器（greedy+扰动与采样两种）、任务级配对估计量与 TOST 检验、输入 pilot 矩阵即可计算的按终点 power/MDE 计算器、梯度构建器、循环归因脚本、预注册模板。
- **GPU 时**：0。
- **决策门**：超过一半的被审论文已经用了多 draw 加 draw-as-unit，就放弃「领域普遍问题」的 framing，改以梯度 MDE、终点灵敏度和机制为主线。

### E6（可选，协作方 4×A100）：外部效度

- 先在 A100 上重跑 `bf16_replicate.sh`，结果**绝不与 4080 合并**。只跑 E1 null（R=5）和 3 个 rung，换第二个 agent 家族或更强的 simulator。telecom 目前没有 cloq adapter，只作为延伸选项。
- **约 30–50 A100-h（推算值）**。到 12/15 仍不可用就跳过，论文不依赖它。

### E7（探索性，有门控，不进主时间线）：margin 门控，作为已知 deferral 方法在闭环下的评测

- 前置条件：E2 在 W3 上确立了 damage。先花约 5 GPU-h 测量化模型自身 margin 的 AUC，要求 AUC ≥0.80。`openloop.py` 现在 `prompt_logprobs=0`，要改代码，而且不是一行改动。
- 两个条件都满足，才在 W3、K≥9 个 checkpoint 上比较 G-margin 与匹配升精度率的 G-random，并加 cascade/deferral 基线。
- 否则留作后续论文。

**核心算力合计**：E0 3 + E1 60 + E1b 11 + E4 12 + E2 58 + E3 63 ≈ **207 GPU-h（约 104 h 墙钟）**。如果 harness 切换规则触发，E2/E3 按 32k 倍率上调，最多约 270 GPU-h。10 月到 11 月中旬 2×4080 可以覆盖，不依赖 A100。

---

## 7. 该砍掉或停止的东西

1. **所有新的 calibration 方法 arm**：CLOQ-Novel 的后续版本、多轮 DAgger 式刷新、TIM Density arm、novelty selector、跨 draw 的 Hessian 平均。E2 给出 MDE 之前不再讨论。
2. **按闭环结果挑 draw 或挑 arm**：信度只有约 0.32，这样挑一定会出现 winner's curse。
3. **把 occupancy、support distance、MMD 当核心指标**：最多保留一张图，用来说明代理指标改善了但行为没有改善。
4. **推断方法**：以下都不再作为主推断：
   - v1 的 crossed bootstrap（过于保守）；
   - 单 draw 的 task bootstrap 和对任务配对的 t 检验 / McNemar（偏松）；
   - **以 run 均值方差比作为决策门**（R 太小时没有分辨力，只作描述）。
5. **表述**：以下一律不再使用：
   - 「3 of 3 signals」「calibration-draw variance dominates」「coverage is not success」「horizon amplification is strong」「drift causes failure」「2–6 倍 hazard」「checkpoint 占方差 0.24%」「BF16-horizon 切分偏向某一确定方向」；
   - 「RTN 证明 benchmark 不敏感」；
   - 「对整个压缩 agent 方向都适用」；
   - 读完全文之前，关于 Noise Floor Audit「没做什么」的任何说法。
6. **为找正结果换更大的模型**；DuQuant/旋转 backbone、JARQ、真实 INT4 速度 benchmark：这些与测量问题正交。
7. **把 VLA（aspq）和 GUI agent 作为核心证据**：只在讨论中作为不合并的旁证，并按审计强度引用。
8. **HANDOFF.md 中「32k 需要 80GB」的说法**：已被审计推翻，立即更正。
9. **把 A100 当作关键路径**。

---

## 8. 时间线与投稿目标（截稿日期都是估计值）

| 时间 | 事项 |
|---|---|
| 9/28–10/4 | E0（含 Noise Floor Audit 全文、循环归因、功效模拟、采样可复现性检查）；10/1 左右提交 `PREREG_EVAL.md`；E1 开跑 |
| 10/1–10/12 | E1（约 30 h 墙钟）；E4 32k 对照（约 6 h，无条件）；E1b 可行性检查和运行 |
| 10/13–10/26 | E2（E2b 视门控而定；harness 按 E4 结果和切换规则确定） |
| 约 10/27 | **go/no-go 评审**：用 E0–E2、E4 的结果，按 §9.3 的改道规则机械确定 E3 的对比、终点和 TOST margin，同时写快速版本 |
| 10/27–11/16 | E3（约 33 h 计算，其余时间留给失败重跑） |
| 11/17–11/30 | E5 实践审计；若 harness 切换规则触发，补跑 8k 历史对照所需的缺口 |
| 12 月 | 工具包打磨，写作；**约 12 月中旬 arXiv 预印本**，确立优先权 |
| 2027-01 中旬 | 内部评审 |
| **约 2027-01 下旬** | **主投 ICML 2027** |
| 备选 | ICLR 2027 workshop（约 2 月初，承载 E0–E2）；ACL ARR（约 2027-02）；NeurIPS 2027 Datasets & Benchmarks（约 2027-05，适合协议加工具包） |

ICLR 2027 主会截稿就在眼前，赶不上。时间安排不能与 TIM-GPTQ 的 ARR 工作冲突；按记录，rebuttal 窗口 9/24 已经结束。

---

## 9. 风险、止损条件与预注册要点

### 9.1 主要风险与应对

| 风险 | 应对 |
|---|---|
| 被看成「只是一篇功效分析」（novelty 评审的核心意见） | 统计工具、prompt 扰动 null、信噪比框架都只作引用；新颖性收窄为压缩-参考差值推断、draw 与 re-roll 分离、梯度 MDE；把「哪个终点测得出」作为正面结论 |
| 与 Noise Floor Audit 高度重叠 | E0 读全文逐条对照；读之前不下断言；必要时把空白 #3 降为支撑性发现 |
| 只有一个模型和一个 simulator | E1b 进入核心计划；E6 作为可选；标题和摘要写明范围；工具包与 benchmark 无关 |
| greedy 只是特例（「用温度采样加 pass^k 就行了」） | E1 加入采样 null 和 W4 采样；空白 #3 限定 greedy；E2 把 pass^k 类指标列为候选终点 |
| 结论是 8k 截断 harness 的产物 | E4 无条件执行并提前；按切换规则从 E2 起改用 32k |
| 只有 db_match 分辨不出（Flat Score 的收紧预算反例） | E2 多终点 MDE；在我们的 null 下复算收紧预算分析 |
| Q7 功效模型没审计，s_c 只靠间接推断 | E0 按 E3 真实几何独立重算；E1 用 W4 re-roll 复制直接估计 s_c 后再算一次；有 TOST 降级和改道规则 |
| null 扰动不中性（会移动均值） | 两个独立 greedy 家族，必须在 CI 内一致；再与采样 null 互相对照；高斯 null 同时匹配解析失败率 |
| RTN 只有一次实现 | RTN 各 rung 用 R≥4 nonce re-roll 构造 run 级复制（或用 stochastic rounding seed），并注明只含 re-roll 方差 |
| simulator 不停止造成的循环被算成 agent 失败 | E0 循环归因与敏感性分析；PREREG 按归因记分；E1b 检查换 simulator 后循环率 |
| W4 下根本没有 damage，结论变成一个可预测的等价 null | 这本来就是可以报告的结论（给出 MDE 和上界）；W3、RTN-NLL 和 α_min rung 负责在梯度上找出可检测的阈值；E3 有改道规则 |
| 新配置下确定性不成立（32k、preemption、换 simulator、采样） | 每个新配置先做 replay 审计或双跑复验，不通过就不做配对复用 |
| 撞车（Flat Score 团队、Noise Floor Audit 的后续工作） | 约 10/27 的快速版本加 12 月 arXiv；投稿前再做一次 2026 年 9–12 月的文献检索 |
| 与我们早先的叙事不一致 | 论文只使用第 2.1 节的表述，v0/v1 的旧说法只作为「被推翻的案例」出现 |
| dev 任务被反复使用、事后切分被循环使用 | 能用 142 个任务的都用 142；long 定义去掉「写操作 ≥2」；≥2 写假说只在 57 个非 dev 任务上用免 calibration 复制做确认性检验；E3 做交叉拟合，写操作终点单独报告非 dev 子集 |

### 9.2 止损条件（kill）

- **K-E0**：独立重算显示当前设计功效 ≥0.6，或 draw-as-unit 检验本身 miscalibrated → 停止，改写 workshop 短文。
- **K1（E1/E2）**：R-nonce 分叉率 <50%，且 α_min 高斯 rung 的分叉率也明显低于 W4 → 放弃「任何扰动都 re-roll」，论文转为「量化扰动在闭环中特殊」。
- **K-null（E1）**：两个 greedy null 家族方向相反，且均值偏移都超过 0.05 → 没有可信参考，放弃 C6。
- **K-ladder（E2）**：同时满足以下两条 → 噪声不是故事，全文降级为「多做几个 draw」：
  - 梯度已被 db_match 干净排序（Spearman ≥0.9，W4-RTN 相对 null 的 Δ 任务聚类 CI 不含 0）；
  - E1 直接估计的 s_c 下界 >0.02。
- **K2（E2）**：所有候选终点上都没有任何单调 damage 趋势 → 不再做 E2b 和 E7，也不追加任何方法变体。
- **撞车**：投稿前已有工作同时做了「压缩闭环 agent + draw 复制 + 采样参考 + 功效分析」→ 转投工具包或可复现性 track。
- **进度**：11/15 前 E1 和 E2 没有完成 → 放弃 E3，只投 workshop；**不以换更大模型作为补救**。

### 9.3 预注册要点（写入 `PREREG_EVAL.md`）

1. **终点**：确认性主终点 db_match；task_success 只作次要终点，因为 NL judge 就是同一个 4B。E2 的候选终点及定义见 E2 设计。**E3 主终点选择规则**：取 E2 梯度上（不使用 Static vs FP-Traj 对比的任何数据）在 E3 几何下 MDE 最小的终点；db_match 始终报告。
2. **推断单位与估计量**：
   - 推断单位：GPTQ 用 checkpoint；RTN 与高斯用 run。
   - 主估计量：
     - Δ = mean_t[p̂_t(null) − p̂_t(Q)]，任务聚类 CI；
     - flip_F = mean_{r,t} 1[Y_rt ≠ Y_t^canon]，拆成损失和获得；
     - 规范 BF16 在 null 中的分位；
     - s_c 用嵌套 GLMM 估计。
   - 方差比只作描述。
   - E3 以 fold 为 block 做 Welch t 加 TOST。
3. **long 子集**只由任务说明定义（所需动作数高于中位数），不用任何 run 的 horizon，**也不再包含「写操作 ≥2」**。≥2 写是一个单独的假说，确认性检验只在 57 个非 dev 任务上做；E0-j 算出的功效 <0.5 时标为探索性。
4. **null 家族**：R-nonce、R-tool、采样（temperature 0.3/0.7）的定义、种子，以及判定一致性的规则；高斯 α 的校准集（200 个状态）和容差（5%）；α_min 的 NLL 上限（W8 水平）。
5. **循环与失败记分**：
   - 真正的基础设施故障重跑一次。
   - 循环按 E0-i 的规则（不看 arm 标签）归因：agent 侧循环记为失败；simulator 侧循环在主分析中记为缺失；另做一版全部记为失败的敏感性分析。
   - 两种结果都报告。
6. **checkpoint 选择规则**在看到结果之前固定，例如 Static c1–c3 和 FP-Traj c1–c3；E1 的 W4 re-roll 集合为 Static c1、FP-Traj c1、CLOQ-Novel c1、RTN。
7. **多重比较层级**：C6 → C7 → C9 → C8 → 次要终点；探索性结果单独成节。
8. **硬件**：只用 4080 的结果；A100 的结果即使 replicate 通过也单独报告。
9. **配置**：`frozen_v0/v1.json` 永远不改，新配置一律复制；context 长度通过 `CLOQ_MAX_PROMPT_TOKENS` 或 frozen_v2 设置（改 `CONFIG_PATH` 读取逻辑时一并提交）。
10. **门控阈值**：每个门控的数值阈值与第 6 节一致，E1 的阈值由 E0-g 的功效模拟给出，按提交时间戳为准。
11. **E3 改道规则**：E2 标定的 80% 功效 NLL 比值 >0.094/0.076≈1.24 时，按 §6 E3 中的顺序改道。TOST margin = max(E2 在 E3 几何下的可达等价界, δ_prac)，δ_prac 在提交时写明。
12. **harness 切换规则**：E4 中 32k 与 8k 的 re-roll 或 Δ 配对差 CI 不含 0 时，E2 起以 32k 为主 harness，8k 作为历史对照。

---

## 10. 附：评分表与评审主要意见

### 10.1 Scoreboard

| 提案 | 均分 | Novelty | Feasibility | Impact | Rigor |
|---|---|---|---|---|---|
| **Every Checkpoint Is a Re-Roll**（P1，主干） | **7.875** | 7 | 8.5 | 7.5 | 8.5 |
| Worse, or Just Re-Rolled?（P5，快速阶段） | 7.0 | 6.5 | 8.5 | 6 | 7 |
| Re-roll, Not Drift（P2，机制部分） | 6.75 | 6 | 6.5 | 7 | 7.5 |
| 量化损伤在闭环里特殊吗（P4，中文版） | 5.83 | — | 4.5 | 6.5 | 6.5 |
| Iso-fidelity perturbation test（P4，英文版） | 5.5 | 5.5 | — | — | — |
| Calibration 修不了「近平局」决策（P3，MGE） | 4.75 | 4 | 5 | 4.5 | 5.5 |

排名：
- Novelty 视角：P1 > P5 > P2 > P4 > P3
- Feasibility 视角：P5 > P1 > P2 > P3 > P4
- Impact 视角：P1 > P2 > P4 > P5 > P3
- Rigor 视角：P1 > P2 > P5 > P4 > P3

### 10.2 评审主要意见与本备忘录的处理

| 意见 | 来源视角 | 处理 |
|---|---|---|
| draw-as-unit、功效分析、扰动 null 都是已知工具，纯「use more draws」会被判为增量工作 | Novelty | 统计工具作引用（Bouthillier/Card/Madaan/Dodge/Error Bars）；突出本场景特有的内容（§4.5） |
| C4 的 type-I 和功效数字来自没审计的 Q7 | Novelty / Impact / Rigor | E0 独立重算；在那之前论文里写成 model-based（§1 已改） |
| E3 的功效（0.8 @ T=142）与每个 checkpoint 实际只看约 71 个任务不匹配；sc_upper 下 +0.05 不可达 | Feasibility / Rigor | E0 按真实几何重算；功效 <0.5 时 TOST 升为主终点 |
| 同一个 4B 作 simulator，噪声底可能依赖这个设置；泛化性不应是可选项 | Impact / Rigor | E1b 进入核心计划 |
| 「0.2–1% 方差」没有信息量；BF16-horizon 偏差方向不明；0.029 的 SD 被挪用 | Novelty / Impact / Rigor | 全部删除或改写（§2.2、§7） |
| 摘要里「首轮改写 → simulator 放大 → 掷硬币」这条因果链超出数据 | Rigor | 改为：漂移是分叉的来源；结果表现为 re-roll；改写对成功率的效应是 +0.03，CI 跨 0 |
| P2：全称标题不成立；write 状态翻转并不特殊；K2 很可能触发；E4 与 cascade 撞车 | 全部视角 | 只移植控制设计；标题不用全称；MGE 降为 E7 |
| P2/P3 的 E4 路由到 simulator server，但两者 max-model-len 不同，确定性没验证过 | Feasibility | E7 前先做 replay 审计 |
| P3：headroom 检验中 simulator 温度不一致；Δ 可能 <0.02 | Rigor / Feasibility | E1 的 greedy 家族保持 greedy simulator；MGE 不进主线 |
| P4：VLA 吞吐没测过，W4 可能无损，「同一特征」难以证伪；iso-fidelity 属已知思路 | Feasibility / Novelty / Rigor | 只移植 tau2 上的 iso-fidelity rung，同时匹配解析失败率；VLA 移出关键路径 |
| P4 的 E2 用绝对阈值（0.094/0.043）对 18 个 checkpoint 的 0.137；截断不变性应为 95.9% 而不是 97.1% | Rigor / truncation 审计 | E4 改用配对差；采用 95.9% |
| P5 最快但缺确认性研究，影响力上限在 workshop 水平 | Impact / Rigor | 把它作为 10/27 的快速里程碑，确认性研究由 E3 承担 |
| 11 个 infra 单元（9 个是循环）需要重跑；HANDOFF 的 32k 说法错误 | 审计 | E0 (a)(e)(i)：2 个真故障重跑，9 个循环进入归因 |
| E1 的方差比决策门没有分辨力（R=6–8 对 18，F 区间约 [0.3, 3]） | critic（high） | 主估计量换为任务级配对量，写入 PREREG；E0-g 模拟功效；方差比只作描述 |
| s_c 没有直接测量 | critic（high） | E1 对 Static c1 / FP-Traj c1 / CLOQ-Novel c1 / RTN 做 R=4 re-roll，嵌套 GLMM 直接估计 s_c，代回 E0-b′ 与 E3 |
| RTN n=1，E2 门控和 A5 措辞不成立 | critic（high） | RTN 各 rung 用 R≥4 re-roll（或 stochastic rounding seed）；A5 与 §1 改为「单次实现，位于底端，待检验」 |
| 8k 截断 harness 的外部效度；E4 门控大概率不打开 | critic（high） | E4 无条件执行并提前；设 harness 切换规则；写明 config.py 的实现路径 |
| 终点灵敏度没有进入 MDE（Flat Score 的收紧预算） | critic（high） | E2 多终点 MDE；在我们的 null 下复算收紧预算分析；E3 终点选择规则 |
| 新颖性风险被低估（Noise Floor Audit、FormatSpread、Signal and Noise、agent 评测严谨性） | critic（medium） | Noise Floor Audit 风险升为高，删掉未读断言；补 † 引用；新颖性收窄为三点 |
| 默认 greedy | critic（medium） | E1 加采样 null 和 W4 采样；空白 #3 限定 greedy |
| E3 的 Static vs FP-Traj 预计测不出；TOST margin 没有依据；量化耗时低估 | critic（medium） | PREREG 改道规则；margin 由 E2 MDE 和 δ_prac 共同确定；量化按 6 min/个重算为 4 h |
| ≥2 写复验功效不足且循环使用 | critic（medium） | E0-j 功效计算；确认性检验只在非 dev 上用免 calibration 复制做；long 定义去掉 ≥2 写 |
| simulator 造成的循环没有控制 | critic（medium） | E0-i 循环归因；PREREG 按归因记分；E1b 检查循环率 |
| 缺少权重空间的极小扰动参照 | critic（medium） | E2 加 α_min 高斯 rung（R≥4，142 个任务），作为饱和曲线左端点并参与 K1 |
| §1 功效表述和范围表述与 §2.3、§4.4 矛盾 | critic（medium） | §1 改为 model-based，并限定在本设置下 |

---

*涉及文件与路径*：
- `/home/xinyu/cloq`：`configs/frozen_v0.json`、`configs/frozen_v1.json`、`cloq/config.py`（第 10 行 `CONFIG_PATH`，第 26–27 行 `CLOQ_MAX_PROMPT_TOKENS`）、`cloq/context_policy.py`、`scripts/bf16_replicate.sh`、`cloq/openloop.py`、`cloq/quantize.py`、`HANDOFF.md`、`README.md`
- 审计脚本：`/tmp/claude-1003/-home-xinyu/822446b5-66f6-44be-b2ea-c6f351322b3f/scratchpad/impact/audit-{variance,mechanism,truncation}/`