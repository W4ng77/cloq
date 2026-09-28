# COLING 速成稿计划（2026-09-28）

**截稿日期待核实。**

## 定位
分析型长文（findings），不主张新方法。
暂定题目：*Is Your Quantized Agent Worse, or Just Re-Rolled? Pitfalls in Closed-Loop Evaluation of Post-Training-Quantized Tool Agents*

## 论点（按"无论新实验结果如何都成立"来写）
1. **calibration 数据的选择，在闭环 agent 评测中测不出差别**：6 个方案 × 3 个 draw，按任务难度对齐后可交换（arm 置换 p=0.68）。v0 的"显著胜出"（+0.121，p=0.035）复验时反号，作为警示案例。
2. **开环保真度不能预测闭环成功**：NLL 能区分 Static 和其余方案（p=0.004），但和闭环成功率的相关只有 r=0.05；RTN 的 NLL 是 Static 的 1.7 倍，闭环成绩却仍落在 GPTQ 范围内。
3. **扰动 null（新）**：BF16 权重不变，只在 system prompt 里加一个中性 nonce，看它的闭环成功率散布有多大，再和"量化方案间的差异""量化相对 BF16 的差距"比较。R=5；Static、FP-Traj、RTN 各 R=3，用来估计同一 checkpoint 的 re-roll 方差。
4. **机制**：哪些状态会翻转由状态本身决定，与方案无关（BF16 NLL 预测翻转，AUC 0.93）；失败以写操作为主，各方案的失败类别分布相同（p=0.94）。
5. **harness 敏感性（新）**：8k 截断 vs 32k。BF16 在 32k 下截断率降到 0，retail db_match 从 0.362 升到 0.414，airline 不变。
6. **给评测者的清单**：确定性 serving、参考模型扰动 null、以 draw 为单位推断、功效和 MDE、harness 披露。

两种可能结果都能成文，这是这篇稿子稳妥的原因：
- null 散布 ≈ 量化差距：结论是"W4 损伤在这个 benchmark 上与 re-roll 分不开"；
- null 散布 ≪ 量化差距：结论是"量化损伤是真实的，但 calibration 修不了"。

## 实验（全部在本机 2×4080 上）
- [~] E4 32k：BF16 + 6 个方案的 c1（scripts/ctx_control.sh），约 6–8 h
- [ ] 扰动 null（scripts/null_rerolls.sh，排在 32k 之后）：BF16×5，Static/FP-Traj/RTN 各 ×3，约 8 h
- [ ] （可选）nonce 确定性双跑 10 个任务

## CPU 工作
- [ ] 独立复算关键统计（置换检验、NLL 相关、翻转 AUC），脚本放进 analysis/coling/
- [ ] max_steps 循环归因（agent 侧 / simulator 侧）
- [ ] 删除作废的表述（0.24% 方差占比、2–6× hazard、"漂移导致失败"）
- [ ] 相关工作：Flat Score (2607.27275)、VLAQuantBench (2609.25376)、TASA (2607.00908)、Noise Floor Audit (2608.22331)、Williams & Aletras 2024、Self-calibration 2024、Sinha et al. ICLR 2026
- [ ] 图：(1) 18 个 checkpoint 与 null 分布的对比；(2) NLL 与闭环成功率散点；(3) 翻转率与 BF16 NLL；(4) 8k 与 32k

## 必须如实写进局限
一个 4B 模型；τ² retail+airline 共 85 个 dev 任务；user simulator 是同一个模型；以 greedy 解码为主；只有 W4 这一种比特宽度。
