# R3165 结果：T10 包化——ui/（L4 界面层）第五批 22 个模块迁移（skill_panel 族＋ui 设计系统＋asset/keyframe/desktop 散件）

## 三问

1. **轮次类型**：结构治理轮（T10 包化迁移批次；只移动文件、修 import 路径与门面，不改业务逻辑与断言）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 9/9 绿；`smoke_test.py --architecture` 架构门禁 483 项（覆盖率基线 2 红已重测修复，`test_coverage_baseline` 复跑 5/5 绿）；覆盖率基线重测 728 模块／74 覆盖（97 条目标用例全过）。
3. **欠账少了吗**：是。T10 包化 **ui/ L4 第五批**：`ui/` 实体由 103 → 125 个（合并树含他道新增后 `ui/` 目录共 140 个 `.py`）。L4 顶层剩余约 13 个实体＋枢纽大模块继续分批；L3 仅剩 `writing_api`（拆分批）、`stage_execution_service`（扇出 50 单独一轮）、`image_agent_runner`（子进程入口永久除外）；门面清除轮需单独授权。

## 本轮交付

| 项 | 内容 |
|---|---|
| `ui/` 实体 | 22 个顶层 L4 模块迁入 `ui/`：asset_detail、asset_thumbs、white_model、keyframe_comfy、keyframe_import、shot_numbering、cell_menu、desktop_tray、desktop_auto_flows、desktop_idea_chat、desktop_shared_menus、desktop_status_bridge、skill_import_service、skill_panel、skill_panel_import、skill_panel_support、ui_dialogs、ui_icons、ui_motion、ui_rounded、ui_shortcuts、ui_theme。 |
| 别名门面 ×22 | 顶层同名 `.py` 统一为 `sys.modules[__name__] = ui.<名>` 别名门面（沿用 domain/orchestrator/ui 前批体例，保留 mock.patch 扁平补丁面）。 |
| 消费方 import | 生产文件改包路径导入；`ui/` 内既有实体的消费边随批同迁；AST 复扫残留 0。 |
| `__file__` 锚点 | `ui/skill_panel.py` `delete_checked_skills()` 的 `Path(__file__).resolve().parent` → `.parents[1]`（入包后父目录变 ui/ 会误删范围，恢复程序根解析）；`test_skills.py` ×3 处 `__file__` mock 路径同步补 `ui/` 段。 |
| 行尾钉 | `.gitattributes`：`程序/skill_panel.py` → `程序/ui/skill_panel.py` 显式钉 CRLF（实体恢复 CRLF，门面保持 LF 史钉）。 |
| 冒烟源路径 | `smoke_test.py` 源路径检查 `程序\skill_panel_support.py` → `程序\ui\skill_panel_support.py`（同前批先例）。 |
| 测试取径 ×15 文件 | 直读门面源码改实体取径：`tests/architecture/` 下 asset_detail_binding/card/data_table/edit_publication/handoff_publication/keyframe_reference_publication/scrollbar_theme/text_component/tooltip/white_model_import/white_model_json 边界测试＋`test_frame_checks`、`test_line_endings`、`test_skills`、`test_ui_style_engine`。 |
| 快照重排 | `维护记录/TODO注释快照_20261003.json` 按新扫描序重排（内容零变化，pet_ui_stages→asset_detail→desktop_async_tasks；R3085 先例）。 |
| 台账与基线 | `架构统一基数.json` 命中项经架构门禁复核通过（file 字段扁平名由扫描器归一）；`architecture.md` 分层表「六批共 125 个」；`PROJECT_MAP.md` 冲突按「包路径＋主干新增条目」并集合并；覆盖率基线重测 **728 模块／74 覆盖**，`runbook.md` §11 同步（728/74/654）。 |

## 验证记录

- `smoke_test.py`（随附解释器，合并树）：**9/9 通过**。
- `smoke_test.py --architecture`（合并树）：483 项中 **2 红**——`test_coverage_baseline` 两项（基线模块集合缺本批 22 个 `ui/` 实体、工具口径 728≠基线 706）；按官方工具 `scripts/coverage_report.py <基线 9 组 targets>` 重测（97 条目标用例 32.4s 全过）刷新基线并同步 runbook §11 后，`tests.architecture.test_coverage_baseline` 复跑 **5/5 绿**，其余 481 项首轮全绿。
- 定向单测（前批工作树已验，本批合并树未重跑全量）：`test_skills`／`test_line_endings`／`test_frame_checks`／`test_ui_style_engine`＋7 个修复边界文件全绿；`test_skills` 技能计数 71→73 系工作树缺两个嵌套技能仓（`.git` 子仓不受版本控制），已从主工作区补入，非代码回归。
- 未跑：`run_selftests.py --all --safe` 全量（合入 master 的 exit CI 会跑静态→架构→冒烟）；`distribution_build --verify`。

## 过程损耗（如实）

- **本批代码此前从未提交**：第五批 22 模块改动在 `devin-dead-symbols` 工作树以 105 个未提交文件滞留；期间 master 先后合入 R3073 死代码清理、R3100 包化收官（只含已提交的第四批）、R3152/R3161/R3163 等约 50 个提交。本轮先以 WIP 提交 `719bdc66` 保全现场，再合入最新 master（`5b82c2b8`）。
- **冲突**：两轮合入各仅 `PROJECT_MAP.md` 一处内容冲突（HEAD 包路径 vs 主干新增 ui_* 条目），按并集解决；主干侧 `project_status.md` 自动取主干版（工作树不写该文件）。
- **提交结构**：为满足「一轮＝一个可独立回滚变更集」与轮次号纪律，合并解算树经 `git write-tree` 固化（`118f4c2a`），`merge --abort` 后从 master 新建 `codex/wip-ui5-b5`，`git restore --source=<tree>` 落盘为「master＋本批」单提交形态；`codex/wip-R3088` 上的 WIP 合并提交仅作现场保全，不进入本批。
- **轮次号**：`round_claim.py next` 领得 **R3165**（本工作树 codex/wip-ui5-b5）。
- **master 两次前移**：首次合并基于 `804e11cb`（R3157），解算期间 master 前进至 `5b82c2b8`（R3163），已弃首次解算重并新主干；覆盖率基线按新合并树重测。


## 主干同步合并（master `a6b4b83f`／R3167 SKILL 生命周期 T1–T10）

合并前 master 前进至 `a6b4b83f`（SKILL 生命周期十轮合入），本分支同步合入，冲突 9 文件全部解算：

- **门面-vs-实体冲突 ×5**（skill_panel／skill_panel_import／skill_panel_support／skill_import_service／desktop_idea_chat）：顶层取 HEAD 门面；`ui/` 实体经三方合并（base=merge-base 顶层版、ours=ui 实体、theirs=主干新版）合入主干生命周期新代码——`ui/skill_panel.py` 实体 822→977 行（体检/检查更新/仓库·文件夹·ZIP·链接导入分支、`default_registry(project=)`、`forget_ledger_targets`），懒加载导入同步包路径（`ui.skill_import_service`、`orchestrator.workflow_settings`）；`skill_panel.theirs` 为 LF 已归一 CRLF 后合并。
- **真实实体冲突 ×1**（desktop_shared_input.py `_import_skill_local`）：包路径导入＋主干 `project=`/`layer` 新参数并集。
- **文档 ×3**：PROJECT_MAP.md 取「本批包路径＋主干新增生命周期模块条目」并集；runbook.md §11 与覆盖率基线按合并树重测 **737 模块／76 覆盖**（97 用例 25.2s 全过）；project_status.md 取分支侧待合入轮处理。
- **测试取径 ×3 文件**（主干新增用例的 `__file__` mock 仍指扁平路径）：test_skill_update_check ×3、test_skill_archive_import ×1、test_skill_remote_import ×1 补 `ui/` 段；修复前 `test_delete_checked_skills_clears_ledger` 红（parents[1] 解析到 tmp 根），修复后复跑三文件全绿。

验证：定向 `-k skill shared_input desktop_shared idea_chat` **808 条／633.8s／修复前 1 红**（上述用例）→ 修复后 3 文件复跑全绿；冒烟 **9/9**；覆盖率基线重测 737/76；`--architecture` 结果见下方提交记录。

## 下一步（T10 后续批次）

- L4 剩余约 13 个顶层真实实体＋枢纽：app、desktop、pet_ui、pet_ui_stages、pet_ui_support、pet_agent、ui_widgets、responsive_ui、writing_api、stage_execution_service、model_pool、pet_cloud（已门面）等——`app.py`/`writing_api.py`/`pet_cloud.py`/`model_pool.py`/`pet_agent.py`/`ui_widgets.py`/`script_contract.py`/`pet_ui_stages.py`/`pet_ui_voice.py` 仍在 `OVERSIZE_CAPS`（9 项），拆分按轮次推进；`stage_execution_service`（扇出 50）单独一轮；`image_agent_runner` 永久除外。
- 门面清除轮需单独授权。
