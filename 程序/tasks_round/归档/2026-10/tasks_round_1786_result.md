# 结果：UI 现代化——设计系统升级（UIMOD）＋ 页面布局与微交互

## 三问

- **本轮类型**：功能轮（UIMOD：令牌与基础组件）＋结构治理轮·执行（主窗口与项目首页的布局、交互）。只改外观、布局参数与交互反馈，不改任何业务逻辑与用户数据。前置的只读诊断见 `tasks_round_1786_diagnosis.md`（原 R1776 草稿，编号已被他线占用，故改名随本轮归档）。
- **测试跑了吗**：窄测试均在本树真跑，全部通过：
  `test_ui_motion`(15)、`test_ui_modern_system`(27)、`test_ui_style_engine`(13)、`test_ui_theme`(15)、`test_ui_widgets_inputs`(9)、`test_ui_widgets_table`(3)、`test_ui_compact_widgets`(3)、`test_ui_batch6_pages`(7)、`test_desktop_compact_layout`(5)，
  架构门禁 `test_layers`、`test_token_boundary`、`test_module_size_ratchet`、`test_function_size_ratchet`、`test_ui_icons_boundary`、`test_scrollbar_theme_boundary`、`test_no_circular_import` 全绿；`smoke_test.py` 8/8。
  **未运行**：`test_ui_edges`（上一轮对比：主检出 115 项 1 个报错、本树 280 秒超时，无结论）、`test_video_ui`、`test_asset_detail` 的已知主干红、完整 `run_selftests`。
- **欠账**：未处理历史欠账；`test_ui_edges` 的基线对比未完成，列入欠账。

## 改动（文件:函数）

- `ui_tokens.py`：新色阶（页底 #F7F9F9、主色 #0F6FC0 等，对比度见下）；`CONTROL_HEIGHT` 32→36、`CONTROL_PADDING_Y` 6→8（对 R1689 密度契约的有意变更）；`BUTTON_RADIUS`、`CONTROL_CORNER_SURFACE`、`ROUND_TILE_*`、`SCROLLBAR_WIDTH`；`DESKTOP_LAYOUT` 新增 `nav_gap`／`section_gap`／`status_gap`，`body_padding` 与 `sidebar_padding` 改取 `SPACING`；新增 `ROW_HOVER_*`、`SPINNER_*`、`EMPTY_*`。
- `ui_rounded.py`（新，L4）：`rounded_png_bytes`、`rounded_photo`、`empty_icon_photo`——标准库生成 alpha 圆角 PNG，按根窗口缓存。
- `ui_motion.py`（新，L4）：`bind_row_hover`／`RowHover`（行悬停淡入）、`Spinner`（Canvas 转圈）、`EmptyState`。
- `ui_widgets.py`：`_configure_button`／`_install_button_styles`（圆角四态按钮）、`_install_card_style`、输入框与滚动条样式；`DataTable` 自动装行悬停、空态标签带图标；`BusyState(spinner=…)` 起停转圈。
- `ui_theme.py`：滚动条定义迁出，裸 `'white'`／padding 改取令牌。
- `desktop.py`：侧栏导航与分隔线、进度条、状态栏间距取令牌；状态栏挂 `Spinner`；项目树装行悬停。
- `desktop_layout.py:fit_sidebar`：「项目动作」按钮非紧凑档纵向内边距取 `CONTROL_PADDING_Y`（36px 契约），紧凑档仍为 4px。
- `desktop_project_pages.py`：项目首页列表装行悬停与空态（无项目时中央提示），列表上下间距 12→16。
- 文档：`design_tokens.md`、`ui_components.md`（含「微交互与空态」一节）、`architecture.md`、`PROJECT_MAP.md`。
- 测试：新增 `tests/test_ui_modern_system.py`、`tests/test_ui_motion.py`；同步 `test_ui_style_engine.py`、`test_ui_theme.py`、`test_ui_token_contract.py`、`architecture/_layers.py`（登记 `ui_rounded`、`ui_motion` 于 L4）、`test_scrollbar_theme_boundary.py`、`test_ui_icons_boundary.py`（PHOTOIMAGE_OWNERS 增 `ui_rounded.py`）。

## 色板与对比度

正文 #0F1419 / 次级 #536471 / 弱化 #616D76 在白底 18.5 / 6.1 / 5.3，在悬停面 #EFF3F4 弱化 4.75；白字 × primary 5.18、primary_hover 6.56、primary_pressed 8.37、danger 4.83、success 5.02；primary × 页底 4.90。#1D9BF0（对白 3.0）只作装饰色，不作文字或按钮色。

## 视觉验证

真实主窗口截图：`tasks_round/MODERN_2_busy.png`（宽屏：选中导航为主色圆角、状态栏右端转圈）、`MODERN_3_narrow.png`（820 宽：按钮栏自动换行、侧栏紧凑）；UIMOD 改前／改后对比图 `UIMOD_before.png`／`UIMOD_after.png`（展示窗口）。

## 契约变更同步项（断言未动）

仅按有意契约同步期望值或定位，未弱化、未删除、未跳过断言：高度 32→36（`_expected()` 读 `CONTROL_HEIGHT`）、`CONTROL_PADDING_Y` 6→8、按钮状态查询由 `background` 改为自定义选项 `fill`、滚动条定义位置迁到 `ui_widgets.py`、`PHOTOIMAGE_OWNERS` 与层级登记。`test_desktop_compact_layout::test_project_buttons_match_global_control_height` 本轮一度红（29≠37），根因在 `fit_sidebar` 写死 4px，已改代码而非测试。

## 已知限制与需裁决

1. 输入框、下拉框保持矩形（改图元会破坏占位、只读、错误态）；滚动条滑块为矩形；右键菜单与下拉弹层仍是原生。
2. 侧栏「胶囊」圆角为 8px（`RADIUS['md']`），不是整圆；如要整圆需新增 `RADIUS` 档。
3. 忙碌结束后状态栏文字不自动清除（既有行为，未改）。
4. 本分支基于 R1775；`claude/project-handoff-f6eb50` 另有 R1776～R1783 未并入主干，且改动了 `ui_tokens.py`、`ui_widgets.py`、`desktop.py`、`responsive_ui.py`，合并时需解决冲突。
