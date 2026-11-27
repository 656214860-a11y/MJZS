# R4636 结果：C13 分镜表分页（每页 ≤100 行、跨页按 shot_id 保选中、Ctrl+A 仅选本页）
<!-- round-evidence: {"commit_base": "a95bb7777", "credential_hits": 0, "evidence_sha256": "13ea89bd364a329b", "exit": 0, "failed": 0, "passed": 10, "round": 4636, "tests": "run_selftests.py -k test_keyframe_page_controller test_storyboard_page_services"} -->

1. **轮次类型**：架构优化执行轮（卡 C13，分支 `codex/opt-c13-storyboard-page`，工作树 `.wt/opt_c13`，对照 `docs/specs/05_UIUX与交互规范.md` §4.2 U-3 / §4.3）。
   - `orchestrator/keyframe_page_controller.py`：在 `KeyframePageController` 中补齐纯分页与跨页选中状态（`DEFAULT_PAGE_SIZE = MAX_PAGE_SIZE = 100`，`page_size` 硬封顶 ≤100、`total_rows` / `total_pages` / `current_page`、`page_rows` / `page_ids`、`set_page` / `first_page` / `prev_page` / `next_page` / `last_page`、跨页 `selected_shot_ids` 集合与 `sync_page_selection` / `selected_on_page` / `select_current_page`、`locate_shot` / `jump_to_shot` / `page_summary`）。
   - `ui/desktop_storyboard_page.py`：首帧分镜表格切为 `selectmode='extended'`，`_render_page` 每页仅渲染当前页 ≤100 行；在 `table_box` 底部新增翻页条（`首页` / `上页` / 页码 `SelectBox` / `下页` / `末页` + 页码与跨页选中汇总，复用 `ui_widgets.SecondaryButton` / `SelectBox` 与 `ui_tokens`）；翻页与刷新按 `shot_id` 恢复跨页选中并保留刷新滚动位置；通过 `self.page.shortcuts.bind` 登记 `Ctrl+A` 只选当前页并提示「已选本页 N 镜」；「选中镜头」下拉跨页自动跳页并高亮；Ctrl/Shift 点击交还给 Treeview 原生多选，普通单击仍走既有勾选契约；未改动 `keyframe_menu` 区段，避免与未合入分支冲突。
   - `tests/test_keyframe_page_controller.py`、`tests/test_ui_edges_tables.py`：追加 3 条无 Tk 分页/跨页选中/Ctrl+A 控制器用例与 1 条 235 镜真 Tk 端到端用例（先红后绿，未动既有断言，无未登记 `skipTest`）。
2. **测试与三基线**：
   - 先红证据：`tests.test_keyframe_page_controller` 3 error（exit 1）；`run_selftests.py -k ui_edges_tables` 1 fail（`AssertionError: 235 != 100`，exit 1）。
   - 改后验证：
     - `run_selftests.py -k ui_edges_tables`：23 条用例全绿，0 跳过（exit 0）。
     - `run_selftests.py -k storyboard_page keyframe_page row_targets ui_batch6_pages ui_edges_controls`：7 个文件 / 65 条用例全绿，0 跳过（exit 0）。
     - `smoke_test.py`：9/9 通过（exit 0）。
     - 19 模块单测与关键架构门禁（`test_keyframe_page_controller`、`test_storyboard_page_services`、`test_layer_relations`、`test_stage_display_boundary`、`test_skip_hygiene`、`test_static_hygiene`、`test_coverage_baseline`、`test_module_size_ratchet`、`test_complexity_ratchet`、`test_function_size_ratchet`、`test_layers`、`test_structure`、`test_token_boundary`、`test_data_table_boundary`、`test_button_boundary`、`test_shortcut_registry_boundary`、`test_combobox_boundary`、`test_constant_condition_ratchet`、`test_copy_rules`）：177/177 全绿（exit 0）。
   - 覆盖率／模块规模／结构三基线均未放宽，未新增生产 `.py` 模块。
3. **欠账变化**：
   - 补齐 05_UIUX §4.2 U-3 分镜表分页、跨页按 `shot_id` 保持选中与 `Ctrl+A` 仅选本页并提示；无新增越层、同层未登记边、魔法数字或未登记 `skipTest` 欠账。
