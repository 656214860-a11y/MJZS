# R698 功能轮结果：全局 ttk.Combobox 样式

## 结果

完成全局下拉框视觉收口。`ui_tokens.py` 增加 Combobox 默认宽度、字体、内边距、字段背景、文字和箭头颜色 token；`ui_widgets.setup_styles(root)` 成为 `TCombobox`、readonly 状态与弹出 Listbox 的唯一权威样式入口。所有颜色均来自 `COLORS`，未引入内联 hex 或第三方依赖。

`COMBOBOX_WIDTH=15` 通过 Tk option database 为未显式设置宽度的 Combobox 提供统一默认值。既有页面中为内容长度显式声明的宽度保持不动，符合本轮“不修改业务页面”的边界；字体、内边距、边框和色彩统一由全局 Style 覆盖。

## 变更文件

- `ui_tokens.py`：新增 `COMBOBOX_*` token。
- `ui_widgets.py`：统一 `TCombobox`、readonly 映射、箭头色与 Popdown Listbox。
- `design_tokens.md`：登记 Combobox token、用途和允许的显式宽度例外。
- `ui_components.md`：登记下拉框组件唯一入口。
- `tests/test_ui_theme.py`：新增 token 驱动的全局 Combobox 回归。

## 验证

- `python -m unittest tests.test_ui_theme`：11/11 通过。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：102 条中 100 条通过；两条既存失败为 `idea_chat.py:609` 的 L2→L3 依赖与 `desktop.py:1403 workflow.get` 的阶段入口守卫。本轮未改这两处，且轮次连续性守卫已恢复通过。

## 三个基线数

- 默认冒烟：8/8 通过。
- 架构门禁：100/102 通过（历史基线 94/94 之上；2 条既存红如上）。
- 全量回归：3,230 条历史基线；本轮未触发全量安全回归。

[TASK_COMPLETE]
