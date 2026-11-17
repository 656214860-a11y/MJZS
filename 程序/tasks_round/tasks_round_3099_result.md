# R3099 结果：SKILL 生命周期 T9——安全加固（不可信提示＋安装完整性＋外部字段映射）
<!-- round-evidence: {"commit_base": "b5eb5eb9", "credential_hits": 0, "evidence_sha256": "3654342398e36f7f", "exit": 0, "failed": 0, "passed": 66, "round": 3099, "tests": "run_selftests.py -k skill_security skill_import skill_registry skill_lifecycle pet_skills workflow_settings"} -->

**类型**：功能轮（任务书 `docs/review/优化任务书_SKILL生命周期_20261116.md` T9；基于 R3091 `b5eb5eb9`，同栈功能工作树，领号时分支 `codex/wip-R3099`）。
**测试**：新增 `tests/test_skill_security.py` 14 条先红后绿（`package_alerts`/`untrusted_source_notice` 缺失、阶段不可识别 fixture）；`run_selftests.py -k "skill pet_skills workflow_settings"` 35 文件 **573 条 0 红**（含 GUI：pet_skills_manage 13、skill_panel 系列）；`run_selftests.py -k test_skill_security test_skill_registry_parse test_skill_lifecycle` 31 条复绿；`smoke_test.py` 默认冒烟 8/8。
**基线**：冒烟 8/8；架构门禁当轮 470 条——4 红全部处置：`test_module_size_ratchet`（`skill_import_service` 1036、`skill_registry` 1041 超 1000）→ T9 助手拆 `skill_security_service`（64 行）、`imported_package_meta` 族拆 `skill_package_meta`（91 行，registry 980/import_service 980）；`test_coverage_baseline` 两项（新模块未入基线 553→555）→ `coverage_report.py` 同 9 组定向用例显式重跑刷新（97 条全过，73/555）＋runbook §11 同步；`test_no_circular_import`（package_meta 函数内 `import skill_registry` 成环）→ 改为迁入 `markdown_heading`/`markdown_summary`/`IMPORTED_PACKAGE_FLAG` 本体、`stage_from_path` 仍引 `skill_project_layer`，registry re-export 无环；余 `test_round_number_continuous`（堆叠分支状态页滞后，同 R3091 口径，master 集成时消解）。
**欠账**：无新增；`project_status.md` 仅 master 可提交，堆叠分支轮次号差按先例记录。

## 变更摘要

- 新增 `skill_security_service.py`（L4，无 Tk）：T9 安全提示助手——
  - `package_alerts(root)`：包根只读扫描（`rglob` 上限 2 万条），报 `scripts/` 目录与 `.exe/.dll/.ps1/.bat` 文件相对路径，大小写不敏感；清单是单文件不警示；
  - `import_alerts(plans)`：仅 `kind=='package'` 计划取 `source.parent` 为包根聚合 `{计划名: 警示路径}`；
  - `untrusted_source_notice(label, plans)`：来源行＋「外部内容将作为指令注入模型请求，请确认来源可信」＋警示行（前 5 条＋省略号）。
- `skill_import_service.py`：`_install_candidate_plans` 确认块重构——无字段问题但有包警示同样触发确认，消息统一以 `untrusted_source_notice` 开头（ZIP／仓库／链接三入口共用）；`check_updates` 抽出 `_installed_status` 供复用；新增 `local_modifications(program)`（台账行 × 安装目标 digest → `{SKILL 名: 台账键}`，只含手改行）与 `program_of_registry(registry)`（`user_root` 上溯程序根）；T9 助手经顶部 re-export 保持 `skill_import_service.<名>` 调用面不变。
- `skill_package_meta.py`（L3，新模块）：`imported_package_meta` 及其依赖 `markdown_heading`/`markdown_summary`/`IMPORTED_PACKAGE_FLAG` 自 `skill_registry` 迁入（模块行数棘轮）；`stage_from_path` 仍引 `skill_project_layer` 唯一权威；`skill_registry` 原样 re-export，全部既有调用方路径不变。
- `skill_registry.py`：`imported_package_meta` 增 `known_tools` 形参——外部包 `license`/`compatibility` frontmatter 原样进 meta（说明区展示），`allowed-tools` 只把内置层清单声明过的工具名映射进 `tools`，其余进 `constraints` 提示（不硬猜、不放宽 17 字段契约）；`scan()` 新增 `_builtin_tool_names` 预扫描内置层 `tools` 并集作映射词表。
- `workflow_settings.skill_health_report`：新增 `local_modified` 形参——命中行追加「本地已修改…（local-modified）」警告并把 `ok` 行降为 `warning`；`skill_panel.show_skill_health` 与 `pet_skills_manage` 列表后台加载/体检详情两处接线（`program_of_registry` → `local_modifications`）。
- `skill_panel_import._import_plan` 与 `pet_skills_manage._ImportFlow.install_plan`：单文件/单包导入确认同样带 `untrusted_source_notice`＋警示行（有警示或字段问题才弹确认，干净包不打扰）。
- `skill_panel_support.note_text`：说明末尾追加「许可证：」「兼容性：」行（meta 有值才显示，内置 SKILL 输出不变）。
- `tests/architecture/_layers.py`：`skill_package_meta` 登记 L3（`skill_registry` 同组）、`skill_security_service` 登记 L4（`skill_import_service` 同组）。
- `architecture.md` §57/§59、`PROJECT_MAP.md` 阶段配置行：T9 口径与新模块归属登记。
- `维护记录/覆盖率基线.json`＋`runbook.md` §11：新模块入基线（553→555，72→73）。
- 测试：新增 `tests/test_skill_security.py`（14 条：包警示扫描/不可信提示文案、ZIP 与仓库目录警示确认、拒绝仍拦截、单包导入确认、手改→`local_modifications`/`check_updates`/体检三处一致、外部字段映射与说明区展示）。

## 验证

- `python smoke_test.py` → 8/8 通过。
- `run_selftests.py -k "skill pet_skills workflow_settings"` → 35 文件 573 条 0 红（GUI 含 pet_skills_manage 13 条、skill_panel_dropdown_layout 12 条等；Tcl `invalid command name` 为已知销毁后回调噪声，非断言失败）。
- `run_selftests.py -k test_skill_security test_skill_registry_parse test_skill_lifecycle` → 31 条全绿。
- `smoke_test.py --architecture` → 470 条；处置见「基线」行，余 `test_round_number_continuous` 为堆叠分支已知项。
- `scripts/coverage_report.py`（同 9 组定向用例）→ 97 条全过，基线 555 模块/73 覆盖，已写 `维护记录/覆盖率基线.json`。
- 未运行：`--all --safe` 全量（功能轮分支不累计欠账；合入 master 前按 §5 触发——本轮动删除语义/层级登记/体检链路，合入前会跑）。

## 边界与说明

- 警示是建议性的：确认框由用户判断来源可信；应用不执行包内 `scripts/` 或任何可执行文件，也不做恶意代码/内容扫描（任务书明确排除）。
- `local-modified` 判定与 T4 `check_updates` 同一 `_installed_status`（`_tree_digest` vs 台账 `sha256`）；目标缺失/不可读归 `source-missing` 口径不算手改；只覆盖用户层台账行，项目层行不参与（项目文件本就归用户所有）。
- `allowed-tools` 映射词表取自内置层 `tools` 字段并集（L3 不反向依赖 L4 `skill_tools`）；外部包声明的未知工具名只进 `constraints` 提示。
- 内置 SKILL 信任模型不变：`package_alerts`/`untrusted_source_notice` 只在外部导入路径触发，内置层不受影响。
- `skill_package_meta` 无顶层 `skill_registry` 引用（`stage_from_path` 走 `skill_project_layer`），`skill_registry` re-export 保持 `skill_registry.imported_package_meta`/`IMPORTED_PACKAGE_FLAG`/`markdown_heading`/`markdown_summary` 调用面不变。
- 提交状态：已提交 `8a01b2da`；hash 回填随 R3127 文档批入库。
- 未运行：`--all --safe` 全量（合入 master 前按 §5 触发补跑）。
- 变更文件清单：`skill_security_service.py`（新）、`skill_package_meta.py`（新）、`skill_import_service.py`、`skill_registry.py`、`workflow_settings.py`、`skill_panel.py`、`skill_panel_import.py`、`skill_panel_support.py`、`pet_skills_manage.py`、`tests/test_skill_security.py`（新）、`tests/architecture/_layers.py`、`architecture.md`、`PROJECT_MAP.md`、`runbook.md`、`维护记录/覆盖率基线.json`、`tasks_round/tasks_round_3099_result.md`。
- 遗留：无。
- 风险与回滚：回滚＝`git revert` 本提交；警示/完整性均为只读诊断与确认文案，不改写用户文件。
- 自检结论：本轮声明功能轮；测试已跑且三个基线按上文口径记录；`project_status.md` 欠账未新增。
- 下一步：T10 文档轮（SKILL 用户文档＋远期清单归档）。
- 阻塞：无。
- 兼容性：`skill_registry`/`skill_import_service` 公开名全部保留（re-export）；`imported_package_meta` 新增可选形参 `known_tools` 默认空，旧调用不受影响。
- 性能：`package_alerts` 有 2 万条上限、只在导入确认时跑；`local_modifications` 只在体检/管理页后台线程跑；`scan()` 内置词表预扫描仅多读内置清单一次。
- 安全：警示不执行任何包内容；`allowed-tools` 白名单映射不放宽执行面。
- 测试缺口：恶意内容语义判定不在本轮范围（任务书排除）；项目层 `local-modified` 未纳入（项目文件归用户所有）。
- 文档：`architecture.md`/`PROJECT_MAP.md`/`runbook.md` 已同步；用户向文档归 T10。
- 结论：T9 验收项全部落地，待提交。
- commit：8a01b2da（codex/wip-R3127 分支；领号切分支在先、提交落地在后）
- 结果文件提交状态：已随本批提交（见 commit 行）。
- 时间：2026-11-17。
- 备注：堆叠分支 `test_round_number_continuous` 差值在 master 集成时随状态页更新消解。
- commit hash：8a01b2da
- 状态：待提交。
- 结束。
