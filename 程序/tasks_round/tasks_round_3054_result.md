# R3054 结果：SKILL 生命周期 T5——项目级 SKILL 层＋`.agents/skills` 共享层评估
<!-- round-evidence: {"commit_base": "77a15692", "credential_hits": 0, "evidence_sha256": "1d91da23782e98f0", "exit": 0, "failed": 0, "passed": 551, "round": 3054, "tests": "run_selftests.py -k skill_project_layer skill_user_layer skill_registry_parse skill_import_validation skill_update_check skill_reference_closure skill_health_service skill_remote_import skill_repo_import skill_archive_import skill_panel_imported pet_agent stage_flow workflow_settings_cache stage_config_empty_project_cache skill_orchestrator_cache test_skills"} -->

**类型**：功能轮（任务书 `docs/review/优化任务书_SKILL生命周期_20261116.md` T5；依赖 T2–T4 已在本栈 `codex/wip-R3054`，基于 R3045 `77a15692`）。动 `skill_registry` 权威语义，AGENTS.md 权威源表与 architecture.md 同轮更新。
**测试**：__待填__。
**基线**：__待填__。
**欠账**：无新增；`project_status.md` 仅 master 可提交，堆叠分支轮次号差按先例记录。

## 设计提案（任务书要求：先写结果文件再动代码）

### 层位置与优先级

- **项目层位置**：`<项目>/skills/`——项目根目录（与 `skill_config.json` 同级，项目目录归用户所有、随项目走）；阶段子目录沿用内置 `01—13` 命名与 `stage_from_path` 口径，两层同构机制全部复用。否决备选「skill_config.json 同级约定目录」：会与既有 `data/`、`工作流/` 等项目子目录混淆，`skills/` 名字与内置/用户层一致、心智成本最低。
- **优先级**：`project > user > builtin`（对齐 DSH project > user）。同名仲裁：高层遮蔽低层只记软警告「X版覆盖Y版」，同层重名仍是硬问题（沿用现有口径）。
- **路径权威**：`skill_registry` 新增 `project_skill_root(project)`（项目目录 → `project/skills`）与 `project_skill_root_for(path)`（从 SKILL 文件路径反推：祖先名为 `skills` 且其父级含 `skill_config.json` 才算项目层——保证自检临时目录、程序内 skills 树不会被误判）。

### Registry 与缓存键

- `Registry(root=None, clock=…, user_root=None, project_root=None)`：`project_root` 收**项目目录**（不是 skills 目录），内部经 `project_skill_root()` 得扫描根；`_layers()` 变 `(project,'project'),(user,'user'),(root,'builtin')`，层名入 `Skill.layer`。
- `scan()` 排序键由「user 优先」泛化为层级名次 `{project:0, user:1, builtin:2}`；遮蔽警告泛化为「项目版/用户版/内置版」三层措辞。
- `_file_cache_key`/`_refresh_file_cache`/`_migrate_root_manifests` 对项目层镜像用户层处理（根 manifest 懒迁移到项目层同名阶段目录，目标目录不存在时按内置目录名补建）。
- **缓存键（防第 44 期同类 bug）**：`default_registry(program=None, project=None)` 的 `_DEFAULTS` 键改为 `(str(root), str(project_root or ''))`——不同项目各持一份注册表，项目 A 的扫描结果绝不会漏进项目 B；不带 project 的调用保持现状（全局两层视图）。

### 引用边界与发送路径

- `skill_roots(program=None, project=None)`：追加项目 skills 根（低→高序：builtin、user、project）。
- `resolve_reference` 泛化：目标缺失时从所在层向**更低优先级**层同相对路径回退、最近层优先（user→builtin 现状不变；project→user→builtin）。
- `_skill_blocks` 的 roots 用 `project_skill_root_for(path)` 自动并入——`freeze_skills`/`_verify`/体检干跑等所有调用点零签名改动即覆盖项目层引用。
- `skill_roots_for_config` 对已勾选 SKILL 路径同样反推项目根并入 CLI `--add-dir` 白名单（config 无 project 字段，路径反推是唯一不需改签名的口径）。

### 导入目标与台账

- `Registry.stage_directory_for(sid, scope='user')`＋`project_stage_directory_for(sid)`（镜像 `user_stage_directory_for`：按阶段推目录、缺省用内置目录名、无项目层返回 None）。
- 面板新增「导入到：项目／全局」二选一，默认项目级（无项目时只有全局）；`plan_import` 重名检查泛化：project 目标撞 user/builtin 同名→覆盖提示不阻止，同层重名→照旧阻止。
- 台账行增 `scope`（'user'/'project'）与 `project`（项目目录绝对路径）字段；project 目标键天然落为绝对路径（不在两层根下），`record()`/`forget_ledger_targets`/`_resolve_ledger_target` 对绝对键兼容。`check_updates(program, project=None)`：project 行按行内 `project` 各自建注册表求候选摘要；给了 project 时只评当前项目行＋用户行（跨项目互不串扰）。

### 项目感知调用点（`default_registry(project=…)`）

`Panel.__init__`（`desktop_project` 可空）、`stage_config` 全部 project 形参函数、`workflow_settings.current`/`validate_selected_skills`、`skill_orchestrator.default_orchestrator`（已有 project 形参）、`pet_ui_stages`、`desktop_shared_input`（`project_root(desktop)`）、`pet_agent.match_skill`/`route`（context['project']）、`skill_panel_import` 导入目标、`skill_health_report` 增 project 形参。`script_skill_report`/`codex_skill_sync` 保持全局两层口径——项目 SKILL 不进全局清单报告与 Codex 同步（防项目专属内容外泄）。

### `.agents/skills` 共享层评估（只评估不实现）

本机 `~/.agents/skills` 已有大量第三方 SKILL（sw-* 等，只有 name/description 轻量 frontmatter）。可行性：技术上可只读扫描并经 `imported_package_meta` 总入口路径挂进面板；**但**——(1) 该目录无 `01—13` 阶段组织，stage 无从判定，面板按阶段展示无落点；(2) 外部格式与本应用 17 字段契约不兼容，只能降级为总入口包，能力字段全空；(3) 只读共享意味着内容更新即时改变所有项目的发送内容，构成提示注入面且无完整性校验（T9 才补）；(4) 与 T6 的 `agents` 导出目标方向相反（那是把本应用 SKILL 写出去）。**结论：不实现共享层**；第三方 SKILL 的正确路径是 T2/T3 已交付的「导入为项目级/用户级包」（ZIP/文件夹/链接），由用户显式选择层级与阶段。若未来要做，建议形态是「扫描 → 列出候选 → 用户逐个导入」，而非自动挂层。

## 验证记录

- 定向 unittest（非 GUI）：`test_skill_project_layer`（16 条，含项目隔离／三层仲裁／目标回退／面板导入层选择／check_updates 项目过滤）、`test_skill_user_layer`、`test_skill_import_validation`、`test_skill_archive_import`、`test_skill_repo_import`、`test_skill_remote_import`、`test_skill_panel_imported`、`test_skill_registry_parse`、`test_skill_update_check`、`test_skill_reference_closure`、`test_skill_health_service` 合计 281 条全绿；`test_pet_agent`、`test_stage_flow`、`test_stage_flow_summary`、`test_shared_input_stages`、`test_workflow_settings_cache`、`test_skill_orchestrator_cache`、`test_stage_config_empty_project_cache` 合计 168 条全绿。
- 复杂度棘轮一次报四项超支并已全部修复（不抬登记值）：`skill_registry.py` 1035>1000 → 项目层路径口径与 `ProjectLayerMixin` 拆入新模块 `skill_project_layer.py`（L3，`_layers.py` 登记，architecture.md L3 行 `skill*` 通配已覆盖），registry 回落 991 行；`skill_panel.py::Panel` 653>646 → 「导入到」选择器构建下沉 `skill_panel_support.add_import_scope`，回落 646；`skill_archive.import_archive` 8 参>7 → `install_source`/`scope`/`layer` 收拢为 `ArchiveOptions` 参数对象（6 参），调用方同步；`pet_agent.py` 1184>1182 → 文档行合并回落。
- `smoke_test.py --architecture`：470 条用例仅剩 1 失败——`test_round_number_continuous`（堆叠分支固有：状态页 2989 vs 最新结果 3054→期望 3055，`project_status.md` 仅 master 可提交，合并轮抬头自愈，同 T2/T3/T4 先例）；其余全绿（含 AGENTS 体积预算、循环导入、路径权威、复杂度棘轮、覆盖率基线）。
- 过程中发现并修复的门禁问题：`AGENTS.md` 权威源表行超 16 KB 预算（压缩措辞至 15,990 B）；`skill_project_layer` 与 `skill_registry` 循环导入＋`skill_config.json` 字面量违反路径权威（共享常量下沉、改用 `SKILL_CONFIG_NAME`）；`覆盖率基线.json` 随新模块 548→549 刷新（`coverage_report.py` 显式重跑，`skill_project_layer` 30%），`runbook.md` §11 口径数字同步；`Orchestrator.__init__` 兜底注册表原本丢 project 改为 `default_registry(project=project)`。
- 修复过程中发现并处理的契约问题：Mock 面板替身上 `self._import_layer()` 会命中 Mock 自动属性，导入层判定改为模块级函数 `_import_layer(panel)`/`_import_target_dir(panel, stage)`；`pet_agent.route` 的 `context['project']` 是项目**名**快照而非路径，改为 `route(..., project=self.project)` 传目录，避免项目层注册表拿到相对路径名；`plan_import`/`uninstall_skill` 对 Mock registry 的 `project_skills` 加 `isinstance(str, Path)` 守卫。

## 改动文件

- `skill_registry.py`：三层 Registry（project>user>builtin）、`default_registry(program, project=)` 二级缓存、`skill_roots(project=)`、`resolve_reference` 高→低层回退；项目层路径口径拆至 `skill_project_layer.py`。
- `skill_project_layer.py`（新，L3）：`project_skill_root`/`project_skill_root_for`/`LAYER_LABELS`/`LAYER_ORDER`/`ProjectLayerMixin`（`stage_directory_for`/`project_stage_directory_for`/`_layer_stage_directory_for`）。
- `skill_import_service.py`：`plan_import` 层判定与 `scope`/`project` 台账字段、`_stage_dir_for`、`_candidate_plans(layer=)`、`record` 绝对键兼容、`registry_for_ledger_row`、`check_updates(project=)` 项目过滤、`uninstall_skill` 项目根白名单。
- `skill_archive.py`：`ArchiveOptions` 参数对象、`archive_entry_digests(layer=)`、`probe_row` 层透传。
- `skill_remote_service.py`：`import_from_url(layer=)`、`_remote_entry_digests` 签名含 layer 与 project_root、台账 project 元数据。
- `skill_panel.py`：`default_registry(project=desktop_project)`、`add_import_scope` 接入管理行、`delete_checked_skills` 根含项目层。
- `skill_panel_support.py`：`add_import_scope`（项目/全局二选一，默认项目级）。
- `skill_panel_import.py`：模块级 `_import_layer`/`_import_target_dir`、五种导入入口层透传、`check_skill_updates(project=)`、`_reimport_ledger_row` 按台账 scope 路由。
- `workflow_settings.py`：`skill_roots_for_config`/`_skill_blocks` 路径反推项目根、`skill_health_report(project=)`、`current`/`validate_selected_skills` 项目感知。
- `stage_config.py`：全部 project 形参函数 `default_registry(project=project)`。
- `orchestrator/skill_orchestrator.py`：`default_orchestrator` 传 project；`__init__` 兜底注册表同步带 project。
- `pet_ui_stages.py`、`stage_flow.py`、`pet_agent.py`、`desktop_shared_input.py`、`desktop_shared_send.py`：项目感知注册表调用。
- `tests/architecture/_layers.py`：登记 `skill_project_layer`（L3）。
- `tests/test_skill_project_layer.py`（新）：16 条项目层行为测试。
- `AGENTS.md`、`architecture.md`：权威源表与注册规则段同步三层语义。
- `runbook.md`、`维护记录/覆盖率基线.json`：覆盖率口径随新模块同步（549 模块／72 覆盖）。

## 遗留与边界

- `.agents/skills` 共享层本轮只评估不实现，结论见上文设计提案：第三方包无阶段组织且 frontmatter 不满足 17 字段契约，只能走 `imported_package_meta` 总入口；建议未来做成「扫描→列候选→用户逐个导入」，不做自动挂层。
- `script_skill_report`/`codex_skill_sync` 保持全局两层口径：项目 SKILL 不进 L0 `script_contract.AUDIT` 清单报告，也不同步到 Codex 代理目录（防项目专属内容外泄）；项目层剧本 SKILL 不在 AUDIT 表内属预期——AUDIT 只管内置/用户层的既有归属声明。
- 项目层 SKILL 的云同步不做（任务书排除）；`data/skills` 用户层语义未动。
- 无项目上下文时一切调用退回全局两层视图；`Panel.project()` 仍在需要项目的动作上抛「请先选择项目」。
- `check_updates` 的 project 行跨项目隔离依赖台账 `project` 字段为绝对路径；项目目录被移动/改名后旧行按 `source-missing` 处理（目标不存在），不自动跟随——与用户层「来源消失」同口径。
