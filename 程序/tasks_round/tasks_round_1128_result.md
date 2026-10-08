# R1128：新增 Animatic 分镜预演阶段

## §7 三问

1. 功能轮，含已授权阶段契约变更；接续 R1124 保留实现，整合 R1127 基线。
2. 整合后定向 91/91（1.8 秒）、受影响冒烟 9/9、默认冒烟 8/8；全量实跑失败，失败项修复后 stage_flow 45/45。`smoke_test.py --architecture` 实跑退出 0、架构治理测试通过；无 R1128 全量绿色凭据。
3. 实现与已发现流程失败项已处理，但全量验收、收尾提交尚未完成，不能关闭待办。

## 范围与授权

- 新阶段位于 storyboard 之后、assets 之前；本地 ComfyUI 草图、临时声音、应用内部合成，人工确认后进入正式资产生成。
- 用户选择应用内部合成；旧编号目录只读，首次修改复制至新编号目录，不移动或覆盖旧用户数据。
- 保留 R1127 阶段制作锁、单次 SKILL 注入及四角色共享规则。
- 中央 next 领取 1128；中央队列无匹配 Animatic 项，不认领无关任务。

## 实跑证据

- `run_selftests.py -k animatic stage_copy_on_write stage_layout stage_parallel`：91/91，1.8 秒。
- `smoke_test.py --affected animatic stage_layout pet_bus stage_parallel desktop`：9/9。
- 技能/治理专项：补齐本地既有子仓库后 ALL TESTS PASSED；未保存精确总数，不补造。
- `run_selftests.py --all --safe`：真实执行、退出 1；暴露 stage_flow 新阶段标签与旧流程契约未同步，无成功凭据。
- `run_selftests.py -k stage_flow`：修复后 45/45。原阶段标签不改；新增 Animatic 标签、顺序断言及 SG-A/SG-B 阻塞断言。
- `smoke_test.py`：8/8。
- `smoke_test.py --architecture`：退出 0、架构治理测试通过；终端过滤未留总数，不虚报计数。此前架构基线 309，不减少既有断言。
- 未调用真实付费 API、ComfyUI 或用户项目，未重启应用，未进行真实媒体视觉验收。

## 状态

[TASK_FAILED] 首轮技能回归因隔离工作树缺两份既有子仓库失败（72 != 74），补齐登记提交后技能/治理复测已绿。第一轮全量暴露阶段流程标签缺项与旧阶段顺序/门禁测试未同步；补齐 Animatic 标签，保留旧阶段断言并增加新阶段顺序与 SG-A/SG-B 阻塞断言，stage_flow 45/45 已绿。继续全量验收，不标记 TASK_COMPLETE。

## 接续阻塞

[TASK_BLOCKED] 修复提交被中央门禁拒绝：中央号已由另一任务推进为 R1129，而本轮为 R1128。不绕过 hooks、不冒用他人轮次。已询问用户是否待 R1129 验收合入后领取新收尾轮次。

本轮检查点：`427f51a`、`55a0db3`；最新 stage_flow 修复及本报告尚未提交，保留在 `assistant-animatic-integration` 工作树。下一步：架构结果登记；在轮次协调完成后建立修复检查点，重新运行全量安全回归取得真实凭据，再同步状态、快照并完成提交。原 `assistant-selectbox` 的 R1124 未提交内容仍保留。
