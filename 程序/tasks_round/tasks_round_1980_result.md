# R1980 拆分 ui_widgets.py：阶段弹窗移入 ui_stage_popups.py（重构轮）

## 改动
- 新模块 `ui_stage_popups.py`（L4）：从 `ui_widgets.py` 原样迁出阶段弹窗相关全部代码——`_release_stage_popup_jobs`／`_schedule_stage_popup_job`／`_activate_stage_popup`、批量执行窗 `_show_stage_execution`、手动制作精简窗 `_show_manual_plan`、`install_stage_presenters()` 及登记调用。`ui_widgets.py` 由 1535 行降到 1381 行，`test_module_size_ratchet` 转绿。
- 登记入口：`desktop.py` 顶部 `import ui_stage_popups`（导入即向 `stage_exec` 登记呈现器）；`ui_widgets` 不反向导入新模块，避免循环依赖。
- 迁入时顺手把字面量改成令牌（门禁要求新文件不得新增数字 width／height／wraplength／padx／pady）：wraplength 520→`WRAPLENGTH['sm']`(480，旧值向下取档)、log 行数 10→`TEXT_ROWS['xl']`、pady 2／4→`SPACING['xs']`(4)、6→`SPACING['sm']`(8)、10→`SPACING['md']`(12)。弹窗内上下留白因此各有 ±2px 以内的变化，未目测。
- 登记同步：`tests/architecture/_layers.py`（L4 登记新模块）、`architecture.md`、`PROJECT_MAP.md`、`维护记录/覆盖率基线.json`（用 AGENTS 约定的 8 组定向用例重跑 `scripts/coverage_report.py`，模块 309→310，新模块覆盖 0/127；同次刷新也带入 master 近期改动的行数）、`runbook.md` §11 数字（309→310、259→260）。
- 测试路径迁移（断言未动）：`tests/test_button_consistency.py` 改读 `ui_stage_popups.py`；`tests/architecture/test_complexity_ratchet.py` 的 `_show_stage_execution` 登记键由 `ui_widgets.py` 改为 `ui_stage_popups.py`，数值不变。

## 验证
- 相关 747 条（button_consistency、ui_style_engine、ui_modern_system、manual_plan、stage、architecture 全组、desktop_compact_layout、launcher_imports、splash 等）仅余历史／他线红：architecture 的 agents_md、round_baselines、skill_reference_injection，test_workflow_writing_stages 2 条（worktree 缺 skills 文件），test_complexity_ratchet 2 条（`skill_panel.py::Panel` 973>972、`production_lock_fields.py::__init__` 9 个参数>8，均来自 master 近期合入，与本轮无关）。coverage_baseline 另跑已绿。迁出前 manual_plan 里「重试失败项」用例曾因迁入漏 `TextArea` 导入而红，补导入后转绿。
- 未跑 --all --safe，未真实窗口目测。
