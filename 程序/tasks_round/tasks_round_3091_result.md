# R3091 结果：SKILL 生命周期 T8——重命名／编辑／启停用／version
<!-- round-evidence: {"commit_base": "73b5eacc", "credential_hits": 0, "evidence_sha256": "ce0afdc77e9f8e66", "exit": 0, "failed": 0, "passed": 249, "round": 3091, "tests": "run_selftests.py -k test_skill_lifecycle test_pet_skills_manage test_workflow test_skill_project_layer test_skill_registry_parse test_skill_update_check test_workflow_settings_cache pet_settings pet_skills_manage skill_lifecycle_service skill_import_service skill_project_layer skill_registry workflow_settings"} -->

**类型**：功能轮（任务书 `docs/review/优化任务书_SKILL生命周期_20261116.md` T8；基于 R3089 `73b5eacc`，同栈功能工作树 `codex/wip-R3091`）。
**测试**：`smoke_test.py --affected pet_skills_manage skill_import_service skill_project_layer skill_registry workflow_settings` → 冒烟 9/9；定向门禁 70 文件 1975 条用例 0 红（该批与模块拆分重构交错，拆分后已对全部触达模块定向复跑：`run_selftests.py -k test_skill_lifecycle test_pet_skills_manage test_skill_project_layer test_skill_registry_parse test_skill_update_check test_skill_archive_import test_skill_remote_import test_skill_user_layer test_skills test_workflow_settings_cache` 341 条、`-k pet_settings test_workflow` 185 条、`-k test_workflow` 127 条全部复绿）；`smoke_test.py --architecture` 470 条，3 红全部修复（模块行数棘轮→生命周期段拆 `skill_lifecycle_service`、裸 `json.loads`→`file_cache.read_json`、覆盖率基线 552→553＋runbook §11 同步），余 `test_round_number_continuous`（堆叠分支状态页滞后，同前轮口径）。
**基线**：冒烟 9/9；架构门禁当轮 470 条、改后实跑红 1（轮次连续性，堆叠分支已知）；全量回归凭据未新增（功能轮分支不累计欠账）。
**欠账**：无新增；`project_status.md` 仅 master 可提交，堆叠分支轮次号差按先例记录。

## 变更摘要

- 新增 `skill_lifecycle_service.py`（L4）：SKILL 生命周期操作从 `skill_import_service` 拆出（模块行数棘轮 1238>1000），台账/回收站助手按 `skill_archive` 同口径引用——
  - `find_skill_entry`：按注册名定位 `{name,path,kind,layer,project,disabled}`，启用项走 `getAll()`、禁用项按登记 `path` 兜底文件名解析，管理页/改名/启停用/删除共用同一口径；
  - `rename_plan`（只读预检：新名 `_NAME_RE` 校验、重名/目标占用拦截、受影响项目 `skill_config.json` 引用计数 dry-run）＋ `apply_rename`（清单＝写新文件再回收旧文件；包＝改入口 `name` 后整目录改名；同步迁项目引用、台账键与 `sha256`、禁用登记；agent 同步 marker 由下次同步按注册表自动重算）；
  - `set_skill_disabled`／`uninstall_skill_entry`：启停用登记与删除收尾（启用项走 `uninstall_skill`，禁用项按登记路径回收并摘登记）。
- `skill_project_layer.py`：禁用登记权威——`disabled_skills.json`（`data/skills/` 根，升级保留、扫描器不认 .json）读写/改名同步，键 `user|<名>` 全局、`project|<项目路径>|<名>` 项目隔离，内置层拒绝；`load_disabled` 改走 `file_cache.read_json`（正式 JSON 读口径）；新增 `disabled_stamp`/`disabled_view_entries` 供注册表指纹与管理页灰显；`ProjectLayerMixin` 承载 `disabled_names`/`disabled_entries` 视图查询。
- `skill_registry.py`：`scan()` 按 `(layer,name)` 过滤禁用项（不进 `getAll()`、文件保留）；禁用登记 `(mtime_ns,size)` 单独进 `fingerprint()` 组合键与 `_fresh()` TTL 早退比对——登记文件在 `data/skills/` 根下、目录组合键覆盖不到内容改写，保证禁用/启用即时生效（修复 TTL 热窗口内不生效的缺陷）。
- `workflow_settings.validate_selected_skills`：勾选项命中禁用登记时报「已勾选的 SKILL 已禁用…请在『设置 → SKILL 管理』启用后重试」，不再与「未加载」混为一谈。
- `pet_skills_manage.py`：行操作补「重命名」（预检摘要→确认→执行→刷新）、「编辑」（`os.startfile` 系统关联打开，保存后指纹热加载）、「禁用/启用」（二次确认，内置层拒绝）；禁用行 `disabled|` iid 灰显（`text_muted`）可选中恢复，删除/启停用/改名均走 `skill_lifecycle_service`。
- version：沿用 T3/T4 口径——台账行记入口 frontmatter `version`，`_entry_status` 版本可比时先比 version 再比 sha256（`unchanged/source-newer/local-modified/source-missing` 四态不变）。
- 测试：新增 `tests/test_skill_lifecycle.py`（15 条：禁用过滤/项目隔离/恢复、改名清单与包、项目引用迁移、台账重定键、禁用登记同步、删除禁用项、version 比较、更新四态）；`test_pet_skills_manage.py` +5 条（禁用灰显行、启停用、改名弹窗流、编辑入口）；`test_workflow.py` `DesktopModelPoolTests.setUp` 统一桩 `agent_skill_sync.sync_agent_skills`（T6 多目标同步后真实家目录在测试环境判冲突，5 条用例同因红）。
- `tests/architecture/_layers.py`：`skill_lifecycle_service` 登记 L4（与 `skill_import_service`/`skill_archive`/`skill_remote_service` 同组）。
- `维护记录/覆盖率基线.json`：`coverage_report.py` 同 9 组定向用例显式重跑刷新（97 条全过），模块 552→553；`runbook.md` §11 同步 553/72/481。
- `architecture.md` §57/§59、`PROJECT_MAP.md` 阶段配置行：禁用登记与生命周期模块归属登记。

## 验证

- `python smoke_test.py` → 9/9 通过（`--affected` 批次内含默认冒烟）。
- `python tests/test_skill_lifecycle.py` → 15 条全绿；`test_pet_skills_manage.py` → 13 条全绿（隐藏桌面）。
- `smoke_test.py --architecture` → 470 条；首轮 3 红：`test_module_size_ratchet`（`skill_import_service` 1238、`skill_registry` 1029 超 1000 上限）→ 生命周期段拆 `skill_lifecycle_service`（327 行）、注册表禁用视图下沉 `skill_project_layer`（registry 993、import_service 928）；`test_unification_ratchet`（`load_disabled` 裸 `json.loads` 新增债）→ 改 `file_cache.read_json`；`test_coverage_baseline`（新模块未入基线 552→553）→ 显式重跑工具刷新＋runbook §11 同步——4 个架构测试文件 17 条复跑全 OK；余 `test_round_number_continuous`（2989 vs 最新结果+1，堆叠分支状态页滞后，同 R3054/R3084/R3089 口径如实记录，master 集成时消解）。
- `run_selftests.py -k …`（见上「测试」行）→ 全部 ALL TESTS PASSED，0 红文件。
- 未运行：`--all --safe` 全量（功能轮分支不累计欠账；合入 master 前按 §5 触发——本轮动启动路径无关、动删除语义/层级登记/agent 同步间接受影响模块，合入前会跑）。

## 边界与说明

- 「编辑」按任务书不做内嵌编辑器：`os.startfile` 交系统关联程序，保存后靠注册表指纹热加载，无需手动刷新。
- 禁用是注册表视图过滤，不改目录结构；删除禁用项仍走回收站，恢复＝重新启用或删登记条目。
- 改名不迁移「内容引用」（SKILL 正文里提到旧名的地方不追改），只迁 `skill_config.json` 勾选引用、台账与禁用登记——任务书口径即「项目配置引用不断」。
- 内置层三层语义不变：只读，不能禁用/删除/改名（`rename_plan`/`set_skill_disabled`/`uninstall_skill_entry` 均拒绝）。
