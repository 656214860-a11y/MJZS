# R694 契约轮结果：剧本外部包总入口审计

## 结论

已收口 R685 的 `test_script_contract.AuditTests.test_the_audit_covers_every_script_skill`：五个外部包总入口已纳入剧本阶段审计，专项 `AuditTests` 7/7 通过。

本次改测试因契约变更（外部包登记），断言未弱化：仍以完整、有序清单与 `unlisted_skills() == ()` 严格守卫全部剧本阶段 SKILL。

全量安全自检为 3380 条用例、28 个文件有红；按项目硬判定，本轮标记 `[TASK_FAILED]`，不作验收关闭。红项含 `test_skills`、`test_stage_wiring`、多组 `test_ui_edges` 等，与本轮 L0 契约范围无关；本轮专项已复核通过。

## 变更

- `script_contract.py`：为 screenplay-production-line、screenplay-writer、script-forging、短剧编剧搭子、编剧技能集新增 AUDIT 行；均分类为“支撑”。理由明确受控默认值只提供 `creative-writing`、不展开内部子 SKILL、没有 output/manifest，未虚构产物归属。
- `tests/test_script_contract.py`：扩展并按注册表实际顺序维护严格全覆盖期望清单；新增外部包均为“支撑”的分类断言。
- `AGENTS.md`、`architecture.md`：同步“只登记外部包总入口、不展开内部 SKILL、不推断 manifest”的台账约束与归属。

未修改 `workflow_settings` 契约文本、`token_saver`、SKILL 内容或注册表。

## 验证与三项基线

| 基线 | 结果 |
| --- | --- |
| 默认冒烟 | `python smoke_test.py`：8/8 通过 |
| 架构基线 | 既有登记基线：101/101；本轮 `--architecture --safe` 未匹配到文件（0/0），不以此改写既有基线 |
| 全量安全 | `python run_selftests.py --all --safe`：3380 条用例，28 个文件有红；日志 `维护记录/r694_contract_safe_all.log` |

补充验证：`python smoke_test.py --affected script_contract skill_registry` 定向执行 `test_script_contract` 与 `test_skills` 共 26 路工作单元，全部通过；`python -m unittest tests.test_script_contract.AuditTests` 为 7/7 通过。

## 范围与后续

- 仅改 L0 契约、其测试和契约轮要求的文档。
- R695 应先由用户选定全量安全红项的修复范围；截图中的“当前操作尚未结束，请稍后”可另立为界面并发/忙碌态修复项，未在本契约轮越界处理。

[TASK_FAILED]
