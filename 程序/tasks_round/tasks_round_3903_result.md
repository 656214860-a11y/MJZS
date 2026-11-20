# R3903 结果：治理变更集落到最新主干基线（同步、冲突解析与重复实现去重）

## 1. 三问

- 轮次类型：合并同步轮（功能分支对齐主干，§3.11 状态接续性质）。治理分支原基线 `f3e82b72` 落后主干；本提交把整份治理变更集落到最新主干 `b19e62e0` 之上，形成单一可回滚变更集（父提交为 `b19e62e0`，状态页保持主干原文未改写）。
- 测试跑了吗：本提交后立即跑退出档（静态→架构→默认冒烟）与定向证据；安全全量与分支覆盖真实重测在同一最终候选树执行，凭据写入最终候选轮。合并提交自身不冒充全量绿。
- 欠账少了吗：净债务减少——治理分支此前与主干重复实现的内建总控退役（`skills/01–13`、`domain/skill_*`、`orchestrator/*`、相关测试）全部改取主干 R3899 已验收实现，删掉本分支重复的 `skills/THIRD_PARTY_NOTICES.md` 与 `tests/test_builtin_controller_retirement.py`，避免两套退役改动同时进主干。

## 2. 冲突与差异处置

原 merge（HEAD `f3e82b72` × master `b19e62e0`）共 46 处冲突，全部按“治理自有文件保留、重复实现取主干”解析后，以单提交落到主干基线：

| 类别 | 文件 | 处置 |
|---|---|---|
| 重复退役实现（取主干 R3899） | `contract/script_contract.py`、`desktop_shared_input.py`、`desktop_shared_send.py`、`domain/skill_command.py`、`domain/skill_residue_service.py`、`orchestrator/agent_skill_sync.py`、`orchestrator/workflow_settings.py`、`scripts/distribution_build.py`、`skills/01–13 各 pipeline-*.skill.md`（13）、`tests/architecture/test_skill_reference_injection.py` 及 skill 相关 `tests/test_*.py` | 取主干 |
| 重复实现附带物 | `程序/skills/THIRD_PARTY_NOTICES.md`、`程序/tests/test_builtin_controller_retirement.py` | 删除（主干已无对应资源；`architecture.md` 的引用改为“阶段方法自包含”） |
| 治理自有 | `程序/governance/**`、`程序/docs/**`、`程序/说明/**` 迁移、`architecture.md`、`runbook.md`、`distribution_manifest.md`、`.gitignore`、`维护记录/基准脚本/doc_registry.py`、`tests/architecture/test_structure.py`、`test_doc_registry_migration.py`、`test_round_baselines.py`、`test_design_coverage.py`、`test_agent_doc_budget.py`、`程序/resources/examples/rainy_umbrella/**`、`程序/ui/desktop_project_pages.py`、`程序/tests/test_projects.py` 等 | 保留本分支治理口径；`runbook.md` §11 与 `distribution_manifest.md` 的 `--verify` 条款吸收主干措辞 |
| 基线（待工具重测） | `维护记录/分支覆盖率基线.json`、`维护记录/覆盖率基线.json`、`维护记录/文档登记快照.json` | 暂取本分支版本；随后由 `branch_coverage_report.py`、`doc_registry.py` 真实重测/重写，`round_gate` 校验 |

## 3. 后续

- 结构检查、doc_registry、设计覆盖、分支覆盖重测与退出档在最终候选轮执行并留真实回执。
- 合入 master 走合并轮 `dev.py merge`，状态页抬头只在合并轮推进；不提前填写合并 hash。
