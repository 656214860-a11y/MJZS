# R2311 结果：J 路线收尾 #20（Tk 依赖归层，重构轮）

## 现状核对
- #19（Desktop 拆 Mixin）：`desktop.py` 已是 20 个 Mixin、986 行，无需再做。
- #6（拆 workflow_settings）：R2184（J1）已把窗口拆到 `workflow_settings_dialog`，本体不再导入 Tk。
- #18（stage_execution_service 网关字典）：R2260（J21）已收口。
- #20：扫描 L0–L3 登记模块，仍有两处直接依赖 Tk：`storyboard_selection.source_selector`（L3 里的下拉框界面）与 `asset_thumbs`（登记 L1，用 `tk.PhotoImage`）。

## 改动（行为不变）
- 新增 L4 模块 `storyboard_source_selector.py`，`source_selector` 原样迁入；`desktop_page_nav` 改从新模块导入；`storyboard_selection` 删掉只为它服务的 `app_logging`、`SPACING` 导入。
- `asset_thumbs` 的调用方（app、asset_detail、asset_reference_images、desktop_*）全是 L4，层级登记 L1 → L4。
- 新门禁 `test_migrated_ui_boundaries.LowerLayersNeverImportTkTests`：L0–L3 登记模块连函数内懒导入都不得出现 `tkinter`，无例外名单。先红（两处违规）后绿。
- 覆盖率基线同步：新模块入基线（351 个模块，未覆盖 298），`storyboard_selection` 行数 394 → 337；`runbook.md` §11 数字同步。

## 验证
- 先红：新门禁红在 `asset_thumbs(L1).py:44`、`storyboard_selection(L3).py:449/450`。
- 绿：`run_selftests -k migrated_ui layers coverage_baseline page_navigation asset_thumbs` 全过。
- `smoke_test.py --architecture`：只剩已知环境红 `test_performance_history_is_declared_as_historical_only`（工作树缺 gitignored 的 `维护记录/基准历史.json`）；覆盖率基线两条红已按上面同步修好。
- `smoke_test.py --affected`：1045 条里 `test_ui_edges.BriefTintTests.test_the_users_own_words_show_up_on_the_display` 红一次；同文件单独重跑在工作树与 master 均 115 条全过，判为并行负载下偶发，与本改动无关。
- 未跑全量。断言未动。
