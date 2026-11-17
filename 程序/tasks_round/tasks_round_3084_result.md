# R3084 结果：SKILL 生命周期 T6——多端技能导出（agent_skill_sync 泛化 codex→claude/agents）
<!-- round-evidence: {"commit_base": "2a72ded2", "credential_hits": 0, "evidence_sha256": "3ceaff609f412b3d", "exit": 0, "failed": 0, "passed": 229, "round": 3084, "tests": "run_selftests.py -k agent_skill_sync skill_user_layer flow_agent_launch idea_semantic_brief idea_chat desktop_send_ledger"} -->

**类型**：功能轮（任务书 `docs/review/优化任务书_SKILL生命周期_20261116.md` T6；基于 R3054 `2a72ded2`，同栈 `codex/skill-t4-updates`）。
**测试**：`run_selftests.py -k agent_skill_sync skill_user_layer flow_agent_launch idea_semantic_brief idea_chat desktop_send_ledger` → 11 文件 229 条全绿（526.1s，0 红文件）；`smoke_test.py` 8/8；`smoke_test.py --architecture` 470 条，初跑 4 红——覆盖率基线（新模块 549→551，`coverage_report.py` 9 组定向用例显式重跑全过后刷新，`runbook.md` §11 同步）、`_layers` 僵尸登记（补顶层门面 `agent_skill_sync.py`）均已修复并复验 `test_coverage_baseline`+`test_layers` 11 条 OK；余 `test_round_number_continuous`（2989 vs 3085）为堆叠分支已知状态页滞后，同 R3054 口径如实记录。
**基线**：冒烟 8/8；架构门禁当轮 470 条、改后实跑红 0（轮次连续性除外，见上）；全量回归凭据未新增（功能轮分支不累计欠账）。
**欠账**：无新增；`project_status.md` 仅 master 可提交，堆叠分支轮次号差按先例记录。

## 变更摘要

- 新增 `orchestrator/agent_skill_sync.py`（L3）：`codex_skill_sync.py` 的「渲染＋marker＋冲突＋孤儿回收」泛化，按 `TARGETS` 参数化目标根——`codex`→`CODEX_HOME`（默认 `~/.codex/skills`，现状不变）、`claude`→`~/.claude/skills`、`agents`→`~/.agents/skills`。
- marker 增 `target` 字段；孤儿回收与所有权判定按 `(owner, root, target)` 三元组，旧 marker 无 `target` 视为 `codex`（升级兼容，不接管他目标目录）。
- `sync_agent_skills(program, target, skill_home)` 单目标；`sync_all_agent_skills` 串行全部目标、单目标异常不拖垮其他（`swallowed` 记日志）；`start_agent_skill_sync` 首帧后台线程入口（`before` 前置迁移注入保留）。
- `orchestrator/codex_skill_sync.py` 收敛为 Codex 单目标兼容入口（旧签名与 `threading.Thread`/`sync_codex_skills` patch 面不变）；顶层 `codex_skill_sync.py` 门面不动。
- 触发点：`desktop_automation_tick._after_first_paint` 改用 `start_agent_skill_sync`（全部目标）；`desktop_idea_chat` 发送前按 `ENGINE_TARGETS` 校验——`codex`→`(codex, agents)`、`claude`→`(claude,)`，问题按 `目标标签：明细` 汇总后快速失败；未登记引擎（qwen 等）不校验，与现状一致。
- 测试：`test_codex_skill_sync.py` 迁移为 `test_agent_skill_sync.py`（18 条，三目标参数化＋target 隔离/旧 marker/多目标故障隔离/引擎映射/后台入口/兼容层）；`test_flow_agent_launch`、`test_idea_semantic_brief` 的 patch 目标同步改为 `orchestrator.agent_skill_sync.sync_agent_skills`（§2.4 契约变更）；`test_flow_agent_launch.stubs()` 增加干净同步桩（claude 引擎此前无同步路径）。
- 文档：`PROJECT_MAP.md` 同步条目、`architecture.md` §2 R1139 段改写为多目标口径；`tests/architecture/_layers.py` L3 登记 `agent_skill_sync`。

## `.agents/skills` 目标启用结论（任务书要求先验证）

已启用。依据（2026-11-17 检索）：Codex 官方文档扫描 `~/.agents/skills`（用户级）与仓库 `.agents/skills`；Cursor、Gemini CLI、OpenCode、Pi 同读该共享目录；Claude Code 只读 `~/.claude/skills`（故 `ENGINE_TARGETS` 不把 claude 引擎映到 agents）。三家目标均为**写出**方向（本应用是 SKILL 生产者/分发方），与 T5「`.agents/skills` 只评估不实现」的读取侧结论不冲突。

## 验证

- `python smoke_test.py` → 8/8 通过。
- `run_selftests.py -k agent_skill_sync skill_user_layer flow_agent_launch idea_semantic_brief idea_chat desktop_send_ledger` → 11 个测试文件 / 229 条用例，526.1 秒，0 个文件有红，ALL TESTS PASSED（含 GUI 分片，跨树令牌排队约 7 分钟后取得）。
- `smoke_test.py --architecture` → 470 条；首轮 4 红：`test_coverage_baseline`×2（新模块未入基线）、`test_layers` 僵尸登记（`agent_skill_sync` 缺顶层门面）——均已修复；`test_round_number_continuous`（2989≠3085）为堆叠分支状态页滞后， master 集成时消解，同前轮如实记录。
- 修复后复验：`test_coverage_baseline`＋`test_layers` 11 条 OK；`test_agent_skill_sync` 18 条、`test_skill_user_layer` 10 条、`test_flow_agent_launch` 8 条单独复跑全绿。
- `维护记录/覆盖率基线.json` 由 `scripts/coverage_report.py` 以既有 9 组定向用例显式重跑刷新（97 条用例全过），模块数 549→551（`orchestrator/agent_skill_sync.py` 实体＋顶层门面），行覆盖模块 72 不变；`runbook.md` §11 口径同步为 551/72。
- 未运行：`--all --safe` 全量（功能轮分支不累计欠账；合入 master 前按 §5 触发）。

## 边界与说明

- 不同步项目级 SKILL（`default_registry(program)` 无 project，沿用 codex 现状）；不同步外部包、不做双向回导。
- 实机观察：`~/.claude/skills`、`~/.agents/skills` 已存在主工作区 root 写入的同名技能（marker `root` 不同）→ 按设计报 conflicts 不接管；生产安装单一 root 不受影响，开发工作树间互不接管是既有语义。
- R3054 提交前静态门禁曾拦 `desktop_shared_input._skill_description` 的 `@staticmethod`+`self` 冲突，已改实例方法并复测 `test_static_names`/`test_static_hygiene` 通过（补记于此，R3054 结果文件成文早于该修复）。
