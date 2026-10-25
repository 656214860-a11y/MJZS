# R2057 合入 codex/wip-R2056 到 master（合并轮）

轮次类型：合并轮。日期：2026-10-25。

- 合入分支 `codex/wip-R2056`（R2056，`72d17b47`：侧栏顶部写当前项目名、项目分组默认收起）。master 在 R2055，自动合并无冲突。
- 合并后验证（在 master 上实跑）：
  - `run_selftests -k sidebar_project_title desktop_compact_layout ui_batch3_shell ui_batch4_desktop_project_pages ui_motion project_rename`：74 条，0 红。
  - 默认冒烟通过。
- 断言未动（R2056 里仅把 `test_desktop_compact_layout` 的侧栏标题期望值改为当前项目名，见 tasks_round_2056_result.md）。未运行：`--all --safe`、真实界面目测。未 push。
