# 论文计划（2026-09-28 修订；投稿目标改为 NAACL 2027）

**投稿（2026-09-28 用户决定）：** 走 ARR 2026 年 10 月轮，截稿 **2026-10-12 AoE**（NAACL 2027 与 COLING 2027 共用这一轮），按 NAACL 要求准备；12-23 前 commit 时选 NAACL 为主会。要求：ACL 模板 review 模式、双盲匿名、长文 8 页正文、必须有 Limitations、Responsible NLP checklist、至少一位作者注册审稿（reciprocal reviewing）。LaTeX 源：`paper/latex/`。来源：https://2027.naacl.org/calls/main_conference_papers/

截稿日 D = 2026-10-12（ARR）；下文时间线以 D 倒排。

## 1. 题目与一句话
*Perturbation Equivalence in Closed-Loop Agents: When Is a Compressed Agent Actually Worse?*
闭环里任何足够大的扰动都会让轨迹重抽；因此压缩是否有损，应当用模型自身的扰动分布来衡量，而不是和单次 BF16 轨迹或分数比。我们给出这一判据、一个可证伪的一阶 margin 模型，并在 6 个模型、7 类压缩/扰动上检验。

## 2. 理论部分（第 3 节）
- 定义：闭环评测中模型 M 的成功是轨迹分布上的期望；扰动家族 𝒫_M（中性 prompt nonce、小高斯权重噪声）给出参考分布。压缩模型 C "扰动等价"当且仅当其任务级成功率分布与 𝒫_M 不可区分（任务级配对检验 + TOST）。
- 一阶 margin 模型：决策点 s 的 margin m_s（top-1 与 top-2 logit 差）；扰动造成的 logit 偏移尺度 δ；P(翻转_s) ≈ P(m_s < δ)；P(第 t 步前偏离) = 1 − ∏_{s≤t}(1 − P(m_s < δ))。
- 预测 P1 偏离饱和、P2 损伤阈值晚于偏离阈值（免费压缩区）、P3 偏离曲线可由 margin 分布跨模型预测。
- 推论：open-loop 保真度在偏离饱和区内与闭环成功无关（解释 4B 上 |r| ≤ 0.13 与 RTN 现象）；单 run 比较在饱和区内测的是 re-roll。

## 3. 大纲（COLING 长文 8 页 + 附录）
| 节 | 内容 | 数据来源 | 状态 |
|---|---|---|---|
| 1 Intro | 问题、v0 假阳性作为引子、三点贡献 | 本机 v0/v1 | 可写 |
| 2 Related Work | 量化 agent 评测（Flat Score、ACBench）、评测方差（Noise Floor Audit、Signal and Noise、AI Agents That Matter、pass^k）、calibration 数据研究、闭环 vs 开环（VLA/驾驶）、多轮退化（Sinha et al.、Lost in Multi-Turn） | analysis/coling/RELATED_WORK.md | 可写；待读全文：Singh 2608.15046、ACBench/Flat Score 逐配置表 |
| 3 Framework | §2 定义与一阶模型 | — | 本机 4B 验证后定稿 |
| 4 Setup | τ²（retail+airline，85 任务），6 模型，压缩矩阵，确定性 serving，固定 simulator，32k harness | A6000 Phase 1 | 待 Phase 1 |
| 5.1 P1 偏离饱和 | 各模型偏离率 vs δ（nonce、高斯、RTN、GPTQ、AWQ 放在同一坐标） | A6000 Phase 2 | 待跑 |
| 5.2 P2 损伤阈值 | 成功率 vs δ，叠加各模型 null 带；免费压缩区 | A6000 Phase 2 | 待跑 |
| 5.3 P3 可预测性 | margin 预测的偏离曲线 vs 实测 | A6000 Phase 2 + margin 记录 | 待跑 |
| 5.4 后果 | 4B 深入案例：18 个 ckpt 落在 null 内、v0 假阳性、calibration 不可区分、open-loop 指标失效、失败以写操作为主 | 本机，已有 + 扰动 null | 基本就绪 |
| 6 Robustness | 8k vs 32k；simulator 侧循环归因；真实 kernel；TP 确定性 | 本机已有 + A6000 Phase 4 | 部分就绪 |
| 7 Recommendations | 给评测者的清单：参考模型扰动 null、每格 ≥3 run、任务级配对推断、harness 披露、不用单次开环指标代替闭环 | — | 可写 |
| Limitations | τ² 两个域、85 任务、greedy 为主、fake-quant 为主 | — | 可写 |
| Appendix | 统计细节、全部配置表、复现说明 | — | 最后 |

## 4. 图表
- 图 1：示意图——同一任务下 BF16、nonce、W4 三条轨迹在首个低 margin 决策处分叉。
- 图 2（核心）：6 个模型的偏离率 vs δ 曲线。
- 图 3（核心）：成功率 vs δ，带 BF16 null 带，标出免费压缩区。
- 图 4：margin 预测 vs 实测偏离（P3）。
- 图 5：4B 的 18 个 GPTQ ckpt + RTN 叠加在 null 分布上。
- 表 1：模型 × 压缩矩阵及每格 run 数。
- 表 2：与相关工作对比（闭环？每格 run 数？报告方差？变动 calibration？）。
- 表 3：8k vs 32k（docs/PROGRESS_2026-09-28.md §2）。

## 5. 时间线（以截稿日 D 倒排；实际日期待 D 确定）
| 时间 | 实验 | 写作 |
|---|---|---|
| D−6 周 | 本机：扰动 null 完成、margin 记录、4B 高斯 3 档；Phase 0 代码 push | Related Work、Intro 初稿 |
| D−5 周 | A6000 Phase 1；本机：4B 验证结论 | Framework 初稿 |
| D−4 ~ D−3 周 | A6000 Phase 2（q4、q8、l8 先出） | Setup；5.4、6 用本机数据写 |
| D−2 周 | A6000 Phase 2 收尾（q14、q30a3、q32）；可选 Phase 3/4 | 5.1–5.3 随数据填入；全部图 |
| D−1 周 | 只补漏跑，不加新实验 | 全文修改、内部审稿、Limitations、附录 |
| D | 投稿 | — |

若 D 早于 6 周：砍 q32 与 Phase 3/4，保留 q4/q8/l8/q14/q30a3。

## 6. 止损与改写规则
- P1 不成立（nonce 偏离率远低于量化）：论文改为"量化扰动在闭环里是特殊的"，框架部分保留为被否定的假设，重点转向量化特有的偏离机制。
- P3 在大模型上预测失败：结论降为"不可由 margin 预测"，报告误差来源；不影响 P1/P2 与后果部分。
- 某模型工具调用成功率 < 0.1：换 §A6000_PLAN 的备选模型。

## 7. 本机（2×4080）待办
- [~] 扰动 null（BF16×5、Static/FP-Traj/RTN ×3）
- [ ] Phase 0 代码（见 docs/A6000_PLAN.md §4）
- [ ] 4B margin 定量验证 + 高斯 3 档
- [ ] 统一口径（docs/PROGRESS_2026-09-28.md §3）
- [ ] 读全文：Singh 2608.15046；ACBench、Flat Score 逐配置表
