# R3096 死代码任务书收口轮结果
<!-- round-evidence: {"commit_base": "ca3bc131", "credential_hits": 0, "evidence_sha256": "3bd95b05bf284c58", "exit": 0, "failed": 0, "passed": 1112, "round": 3096, "tests": "run_selftests.py -k assets workflow api account writing core pet_settings storyboard_source ui_edges idea_chat"} -->

## 三问

1. **轮次类型**：§3.3 结构治理轮·按报告执行（用户任务书《死代码与无效功能任务书》授权的收口批；脚本化机械迁移，非手工逐模块治理）。
2. **测试跑了吗、三个基线过了吗**：定向测试随 `dev.py commit --tests` 生成 `evidence/R3096.json`；冒烟 9/9、架构门禁 483/483 已于同一文件状态实测通过；全量 `--all --safe` 结果以合入前验收为准。
3. **project_status.md 的欠账少了吗**：死代码任务书 A/B/E 节执行完毕——A 节 21 死文件（R3063–R3073）＋B 节 123 个 T10 兼容门面全删＋E1a 309 个未用 import 清除；门禁基线全部按删除后实测同步（覆盖率 554→410、分支覆盖 75→34、类型检查 136→100 模块、统一基数 historical_name_audit_pending 24 名）。

## 本轮内容（468 文件）

- **B 节门面退役**：123 个顶层 T10 别名壳删除（contract 22／infra 19／domain 23／ui 16／orchestrator 43），与 `facade_map.json` 一一对应；生产侧原本零引用。
- **测试迁包路径 codemod**：313 个测试/工具文件改写为包路径（import/from/patch/import_module/sys.modules/__import__ fromlist），零平铺 import 残留（`migrate_report.json`）。
- **E1a 未用 import 清理**：60 文件 309 个名字（`e1a_v2`→`rm_unused_imports`，保留副作用/动态引用；`skill_panel.py` 的 `SecondaryButton` 按按钮边界契约恢复）。
- **门禁同步**：覆盖率基线、分支覆盖率基线/下限（34 个 L0/L1 顶层存活模块）、类型检查基线（100 模块/total 2730）、架构统一基数（第一项 pending 24 名＋第四项 json.loads 台账身份重锚）、模块行数棘轮（script_contract 1208）、runbook §11 口径、`test_layers`/`test_project_context_boundary`/`test_agents_md`/`test_stage_display_boundary` 实体解析改 `entity_file`、展示位点改指 `skill_panel_support.py`。
- **任务书收口**：任务书移至 `tasks_round/死代码与无效功能任务书.md`（G 节改执行结果）；《任务完成》文件归档；deadcode_20261116 审计证据（facade_map/migrate/retire/rm_unused_imports/e_scan/e1a_v2/batch_snapshots）入库。
- **契约测试同步（§2.4）**：断言未删未弱化；改动均为导入路径/实体解析/基线口径，行为断言原样。例外一处：`test_ui_edges_guards.test_approval_consumers_use_the_shared_helper` 原断言 `desktop.py` 必须 import `approved_versions`/`adoption_summary`——E1a 清理证实 desktop.py 自 R30xx 拆分后不再调用这两个名字（真实消费者为 `orchestrator/media_page_controller.py`，其 import `adopted_edit_version`/`adoption_summary`/`review_label` 不变），断言改指真实消费者文件与其实际使用的助手名，守卫意图（交付界面走 engine 统一采用版助手）不变。

## 验证

- 编译：全部改动 .py `py_compile` 通过。
- 冒烟：`smoke_test.py` 9/9。
- 架构门禁：`smoke_test.py --architecture` 483/483（修复项：project_context_boundary entity_file、agents_md 权威表、branch_coverage 基线 34 模块、runbook 口径、module_size、stage_display 位点、unification_ratchet 台账、skill_panel SecondaryButton）。
- 定向测试：迁移相关批 ~800 用例绿（test_assets/workflow/api/account_page/writing_api、test_core/pet_settings/storyboard_source_service/ui_edges_*/idea_chat）。
- 合并树验证：R3095 合入 master 时出口档 CI（静态+架构+冒烟）全绿。

## 移交（范围外，任务书已注明）

- E1b def/class 死代码专项（需 vulture 级调用图）；E3 UI 回调/`auto_*_var` 残留专项。
- 产品决策档：`legacy_compat`（2027-03-31 淘汰）、`engine_probe` 迁 scripts/、CRT-026/027/028。
- `说明/版本文件校验.json` 为约定不手改的过期快照（体积分析_20260921 记录），8 条陈旧条目属历史漂移非本轮引入。
