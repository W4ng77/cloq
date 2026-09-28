# CLOQ v2 TODO（依据 docs/STRATEGY_v2.md，2026-09-28）

主线：闭环评测科学（"Every Checkpoint Is a Re-Roll"），不再推 calibration 方法。

## 进行中
- [~] E4 32k 对照（本机 2×4080，scripts/ctx_control.sh，runs/ctx32k_*）：BF16 + 6 个 v1 arm 的 c1，约 6–8 h

## 本周 E0（大部分 CPU）
- [ ] (a) 重跑 2 个真正的 infra 故障单元
- [ ] (b) 独立重写 Q7 功效模拟 / GLMM，按 E3 真实几何重算
- [ ] (c) 冻结 PREREG_EVAL.md（git 时间戳）
- [ ] (d) 确定性复验：nonce 扰动双跑；temperature 0.3/0.7 固定 seed 双跑 5–10 任务
- [ ] (e) 修正 HANDOFF.md 的 32k 说法；README 46/68 vs 39/58；预先量化 W3-RTN
- [ ] (f) 删除作废表述（0.24%、2–6× hazard、"漂移导致失败"）
- [ ] (g) 新估计量的功效/MDE 模拟，定 E1 的 R
- [ ] (h) 读 Noise Floor Audit 全文，核对 † 引用
- [ ] (i) max_steps 循环归因（agent 侧 / simulator 侧）
- [ ] (j) ≥2 写假说在 57 个非 dev 任务上的功效

## E1（10/1–10/12，约 60 GPU-h）——可分到 A6000
- [ ] BF16 null：R-nonce ×8、R-tool ×6（142 任务）、R-para ×3
- [ ] BF16 采样 T=0.3/0.7 ×4
- [ ] W4 re-roll：Static/FP-Traj/CLOQ-Novel c1 × nonce ×4；RTN × nonce ×4
- [ ] W4 采样 T=0.7 ×4（FP-Traj c1、Static c1）
- [ ] 嵌套 GLMM 直接估 s_c，回填功效

## E1b 换 user simulator（约 11 GPU-h）
## E2 退化梯度 + iso-fidelity + 多终点 MDE（10/13–10/26，约 58 GPU-h）
## E3 预注册确认性研究（10/27–11/16，约 63 GPU-h）
## E5 文献实践审计 + cloq-eval 工具包（CPU）
## E6 外部效度（A6000/A100，绝不与 4080 结果合并，先跑 bf16_replicate.sh）
## E7 margin 门控（有门控，探索性）

## A6000 节点
- 需要：主机名/登录方式、调度器、共享存储路径、CUDA/驱动版本
- 规则：每个节点先跑 bf16_replicate.sh 验证确定性；结果按硬件分开报告
