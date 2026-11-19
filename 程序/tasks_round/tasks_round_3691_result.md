# R3691 结果报告
<!-- round-evidence: {"commit_base": "1121d248", "credential_hits": 0, "evidence_sha256": "be45e222df13ddf5", "exit": 0, "failed": 0, "passed": 30, "round": 3691, "tests": "run_selftests.py -k test_budget test_skill_budget_send_entries infra/budget.py orchestrator/pet_budget.py tests/test_budget.py tests/test_skill_budget_send_entries.py orchestrator/skill_budget.py pet_agent.py tests/architecture/_layers.py architecture.md PROJECT_MAP.md tasks_round/L1基础设施层企业级任务书.md tasks_round/tasks_round_3691_result.md 维护记录/覆盖率基线.json 维护记录/分支覆盖率基线.json 维护记录/分支覆盖率下限.json"} -->

## 三问

- 类型：功能轮（任务书轮 I16，跨层 L1 机制＋L3 策略迁移）。
- 测试：跑了；三基线——默认冒烟 9/9 绿；架构门禁相关套件（layers/layer_relations/branch_coverage_floor/test_budget/test_skill_budget_send_entries）本树验证；全量未跑（合并轮后按台账由后台全量补跑）。
- 欠账：少了——FL-13 预算判定层位落地；上轮阻塞领号的「领先>10 源码提交」由 R3690 合并轮回合主干解除。

## 交付

- `infra/budget.py`（L1）：`check_amount` 超限判定、`headroom` 剩余量、`reserve`/`settle`/`cancel` 转 `request_ledger` 原语（`limits={kind:上限}` 预检越线抛 `BudgetRejected` 不落账）、`summary(project, since)` 按 kind/stage/provider 成本聚合（kinds 桶与 `report()['kinds']` 同口径）。
- `orchestrator/pet_budget.py`（L3）：pet 五类配额策略（image/firstframe/video/voice/tokens、默认值、90% 预警、别名、会话计数），`check()` 委托 `infra.budget.check_amount`；`pet_agent`（L4）再导出同名常量与 `Budget`，界面只显示（L1-H10 逐字等价：事件负载、文案、暂停行为不变）。
- `skill_budget.remaining` 收敛 `infra.budget.headroom`。
- 测试：`tests/test_budget.py` 22 条（五类边界/越线/别名/warning→exceeded 事件逐字/无界面编排 budget.exceeded 不依赖 pet_agent/台账一致）；`test_skill_budget_send_entries` qwen worker mock 按 §2.4 同步为 `executors.submit`（I11 迁移后的既有欠账，行为契约不变）。

## 验证

- test_budget 22/22、test_skill_budget_send_entries 8/8（修后）、smoke 9/9；layers/branch_coverage_floor/layer_relations 定向复验中。
- 基线：行覆盖 670 模块 88 覆盖（budget/pet_budget 未测先录 0）、分支基线 100 模块 2943 点（budget 25 点）、下限 100。
- 备注：R3690 合并轮出口 CI 6 项整合修复因领号/提交窗口漏 add 未随合并入库，主干树暂红；以 R3692 补交（同树修复内容不变），本分支提交后 ff 同步。
