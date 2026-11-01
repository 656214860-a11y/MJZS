# R1789：剧本结构页布局调整——文件选择改横向下拉框（功能轮）

1. 本轮类型：§3 功能轮（只改剧本结构页布局，不改业务数据与阶段流程）。

2. 测试跑了吗：
   - 定向（本树真跑）：`test_ui_reading_density` 8/8、`test_stage_wiring` 16/16、`test_ui_batch5_stage_panel_and_script_page` 5/5、`test_ui_edges.test_script_structure_page_shows_source_and_output_in_separate_boxes` 1/1、`tests.architecture.test_function_size_ratchet` 2/2。
   - 默认冒烟 8/8；`smoke_test.py --affected desktop_script_pages` 通过。
   - 架构门禁（`unittest discover tests/architecture`）376 项，8 项红，**均非本轮引入**：`test_skip_hygiene` 两项（R1786 新增的 `tests/test_ui_motion.py:19` skip 未引用原因常量）、`test_round_baselines`（状态页轮次头待合入 master 后同步）、`test_coverage_baseline` 两项／`test_agents_md`／`test_skill_reference_injection`（与本轮文件无关，未逐项复核根因）。本轮引入的函数行数登记红已收口。
   - `test_ui_edges` 整文件：本轮前一次 115 项 1 个报错（`test_storyboard_switch_never_inflates_the_footer_row`，托盘窗口创建超时，与本轮无关）；合入 R1786 后未重跑整文件。
   - 未跑完整安全全量。

3. 欠账：本轮改源码 +1（`desktop_script_pages.py`）；全量欠账由合入后补跑清账，未跑前不写通过。

## 改动

- `desktop_script_pages.py`：新增 `_DocumentPicker`（Combobox，保留 `selection`／`get_children`／`item`／`selection_set`）；`content_box` 去掉左侧目录表与可拖动分隔条，下拉框与「修改内容／恢复删除／保存修改」同一行，三按钮固定宽 `SCRIPT_EDIT_BUTTON_WIDTH=7`；右键删除作用于当前选中文件；流程按钮（采用选中剧本／手动制作结构剧本／阶段配置）移到上下两框之后；说明文字缩为一行放在按钮下方；删除不再使用的 `_fit_script_directory` 与相关导入。
- 测试（断言对象随布局有意变更，**未弱化**其余断言）：`test_ui_reading_density.py` 目录行高／滚动／悬停断言改为下拉框存在、位于正文上方、列出全部文件；`test_ui_edges.py`、`test_ui_batch5_stage_panel_and_script_page.py` 同步容器类型与说明文字；`architecture/test_function_size_ratchet.py` 将 `script_structure`、`content_box` 登记下调为 244／181。
- 文档：`docs/stages/S02_剧本结构.md` 的 REQ-S02-32、DES-S02-32 同步新布局。

## 未验证

- 未在真实窗口里目视确认；高 DPI 与窄窗口下的下拉框宽度未实测。
