# R2527 结果

1. 轮次类型：功能轮（工程闸门落地清单批次 1：G4／G3／G1），附带一处修复（`master_import_service.py` 缺 `import skill_registry`，静态名字门禁原本就红）。
2. 测试：定向 `test_round_evidence`、`test_round_gate`、`test_git_hooks`、`test_merge_round`、`test_commit_round`、`test_static_names` 全绿；默认冒烟 8/8；架构门禁 420 条，唯一的两处红来自新工作树缺本地文件（`基准历史.json`、嵌套技能仓库），补齐后复跑 `test_agents_md`、`test_skill_reference_injection` 绿。未跑全量（分支不累计欠账）。凭据扫描由 `tasks_round/evidence/R2527.json` 记录。
3. 欠账：无新增。断言未动。

## 改动

- G4：`round_gate.py` 阈值取自 `测试分层基线.json`（新增 `architecture_gate_files_min`=123、`skill_registry_count`=73、`smoke_checks_expected`=8）。`skill_registry_count`=73 与旧门禁写死的数字一致；曾在缺嵌套技能仓库的新工作树里误测成 71，补齐嵌套仓库后确认 73，定向测试首次提交即因此拒绝（门禁生效的实证）。
- G3：新增 `维护记录/基准脚本/round_evidence.py`；`round_gate.py` 读 `tasks_round/evidence/R<N>.json`；`dev.py commit` 生成证据（`--tests`）。
- G1：`merge_round.py` 合入前跑 `local_ci.py exit`，失败中止并还原；`pre-commit` 暂存 `程序/*.py` 时跑静态名字与静态卫生门禁。
- 清单：用于 G3 的凭据检查没有复用 `test_secret_sink_audit`（AST 数据流，无法扫文本），改用内置四条形态正则。

## 先红后绿

新增模块与测试同轮写成，改前这些测试因模块不存在而无法导入。
