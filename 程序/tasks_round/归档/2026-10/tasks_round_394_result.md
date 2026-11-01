# R394 功能轮结果

## 范围

- 前置已读：`tasks_round/tasks_round_391_result.md` 第 1 节第 6 条。
- 修改：`PROJECT_MAP.md`、`tests/architecture/test_agents_md.py`、`project_status.md`、本结果文件。
- 未修改：`AGENTS.md`、生产 `.py`、`architecture.md` 第 3 节。

## PROJECT_MAP.md 改动摘要

- 桌面与页面表的“11 阶段页面”改为“12 阶段页面”。
- 阶段基础设施表的“11 阶段目录”改为“12 阶段目录”。
- 地图目录标题已为“12 阶段目录与交付契约”；新增测试确认其与 `pet_bus.STAGES`、`STAGE_NAMES` 和两份权威文档一致。

## 新增一致性门禁

`test_agents_md.py` 共 7 条：工作流阶段数、播报分母、2.2 模块存在性、删除回收契约、路径权威、测试文件位置，以及三份文档阶段数一致性。

## 验证

命令：`D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --architecture`

- `test_agents_md.py`：7/7 通过。
- 架构测试总计：25 项；22 通过、3 失败。
- 三项失败均为 R393 已建立门禁发现的既存生产代码违规，且本轮禁止修改生产代码：`app.py:1438` 动态导入、`pet_ui.py:1056,1125` 直接完成事件、21 处未经回收服务的物理删除。

## 结论

本轮验收中的地图阶段数和新增 7 条一致性测试均通过。25/25 未达成的原因是已有三类生产违规，本轮按范围约束未修复。
