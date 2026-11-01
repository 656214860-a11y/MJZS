# R2056 侧栏顶部写当前项目名、项目分组默认收起（功能轮）

轮次类型：功能轮。日期：2026-10-25。

- 侧栏顶部原来固定写「漫剧助手」，现在写当前项目名；没打开项目时仍写应用名。名字超过 5 个字（`DESKTOP_LAYOUT['sidebar_title_chars']`）截断加「…」，免得把齿轮挤出侧栏。
  - 入口：`ProjectPagesMixin.refresh_sidebar_title`，在 `mark_current_project`、侧栏 `fill_projects`、取消当前项目时调用，改名后刷新列表也会跟着变。
- 侧栏「在制作项目／已完成项目」分组默认收起。用户手动展开过的，后续刷新（新建、改名、状态切换）保持展开，不再收回。
  - 项目选择窗、项目首页的列表不变（仍展开有项目的分组）。
  - 打开项目时的 `list.see` 会把收起的分组展开，改为只在所在分组已展开时才调用。
- 新增 `tests/test_sidebar_project_title.py`（3 条）。
- 契约有意变更：`test_desktop_compact_layout` 里侧栏标题的期望值由应用名改为当前项目名「性能项目」，其余断言未动。
- 验证：`run_selftests -k` 侧栏标题／compact_layout／batch3_shell／batch4 项目页／ui_motion／project_rename／pet_settings 共 129 条全绿（`desktop_project` 等复跑 24 条绿）；`--architecture` 只剩 3 条旧红（`test_agents_md`、`test_skill_reference_injection`、`test_round_number_continuous`），与本轮无关。
- 未运行：`--all --safe`、真实界面目测（5 字名与齿轮的实际排版）。未 push。
