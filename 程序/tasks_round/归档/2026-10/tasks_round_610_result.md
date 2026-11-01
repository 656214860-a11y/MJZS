# R610 结构治理轮（子场景：执行）结果

## A. 轮次信息

- 来源：`tasks_round/tasks_round_609_result.md` 的 J 节。
- 目标：收口历史兼容门面架构测试的登记、架构基线和轮次台账脱节。
- 范围：仅文档台账与验证地图；未修改任何 `.py`、测试逻辑或用户数据。

## B. 改动文件清单

1. `AGENTS.md`
   - 第 5 节新增 `test_legacy_facade_manifest.py`，明确其守护历史兼容门面的清单、调用方与淘汰日期。
   - 架构门禁基线由历史的“55 个测试文件、98/98”校正为实测“56 个测试文件、101/101”。
2. `architecture.md`
   - 已验证发布边界明确该测试文件为历史兼容门面的 AST 守卫。
3. `project_status.md`
   - 记录 R609 诊断与 R610 收口结果；当前轮次由 R610 待执行推进为 R611 待执行。

## C. 事实与修复

`smoke_test.py --architecture` 通过 `unittest.discover(tests/architecture, pattern="test_*.py")` 自动发现该测试；问题不是测试未接入，而是 AGENTS.md 的人工门禁清单和基线遗漏了它。

首轮复测时，101 项中有 1 项轮次连续性守卫失败：状态台账仍称当前 R608，而当时最新结果已是 R609，`test_round_baselines.py:30` 期望 R610。现已按“最新结果 + 1”规则校正，R610 结果写入后状态推进到 R611。

## D. 验证

- `python smoke_test.py --architecture`：101/101 通过（首次运行仅暴露上述台账连续性失败；校正至 R610 后复测通过）。
- `python smoke_test.py`：8/8 通过。
- 本轮最终再以 `test_round_baselines` 复核 R610 → R611 的连续性。

## E. 约束自检

- 变更模块：3 个文档模块（`AGENTS.md`、`architecture.md`、`project_status.md`），符合“每次最多改 3 个模块”。
- 未改分层、对外契约或产品功能；没有新增测试迁移和兼容包装。
- R609 J 节对应的登记脱节项已完成，不再列为未收口债务。
