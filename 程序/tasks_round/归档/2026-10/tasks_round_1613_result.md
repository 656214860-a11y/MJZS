# R1613 持久化产物版本契约与清单（Q4）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round_1610_result.md) J 第二批 Q4）。
- 测试：定向 31/31 通过（`tests.test_artifact_schema`＋`tests.architecture.test_layers`＋`test_agents_md`）；架构门禁 350/350 通过；默认冒烟 0 失败。完整安全全量未跑。
- 欠账：本轮改源码／测试，`project_status.md` 全量欠账计数 +1，未清。

## 先更正 R1610 的错误前提

R1610 的 Q4 原文写“正式 JSON 产物无 schema/版本字段”，**不准确**：本轮核实到桌面任务队列、连续性台账／issues、Animatic 清单**已有** `version: 1`（`desktop_automation_service._load` 还会拒绝 `version != 1`）。真实缺口是：键名不统一（`version` vs 无）、无集中登记与必备字段声明、无迁移入口，且不少产物（`assets.json`、`skill_config.json` 等）尚未核实。清单已按此更正。

## 改动

1. **新增 L0 契约模块** `artifact_schema.py`：`VERSION_KEY='schema_version'`、`SCHEMA_VERSION`、`REGISTRY`（kind→版本／必备字段／写入模块／历史键）、`stamp()`、`validate()`、`migrate()`。设计原则：**读取侧只报告不自动改写用户数据**；历史 `version` 键由 `migrate()` 显式抬升且只加键。
2. **分层登记** `tests/architecture/_layers.py` L0 加入 `artifact_schema`；`architecture.md` §3 L0 行同步模块与判定。
3. **名单与文档**：`AGENTS.md` §2.2 权威表新增「持久化产物版本 | `artifact_schema`」；新增 `说明/持久化产物版本清单.md`（已核实的 4 类产物＋待核查产物清单与后续收口方式）。
4. **单测** `tests/test_artifact_schema.py`：登记完整性、stamp 不改入参、validate 四类问题、migrate 抬升历史键／补写缺失／幂等。

## 边界

- **未改动任何既有产物的磁盘格式**，无用户数据迁移；既有 `version` 键继续可用。
- 本轮是“登记＋只读校验＋迁移入口”的落地；把**每个既有写入器改写成写 `schema_version`** 属多模块迁移，按清单文档逐项收口，不在本轮冒充完成。

## 下一项

Q5（逐 AI 适配器的失败分类一致性测试）。