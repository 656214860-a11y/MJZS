# R1772：修复轮——剧本准备文件表去掉底部滑块、收窄勾选列、滚动条防抖

1. 本轮类型：§3.2 修复轮。剧本准备页四棵文件树（项目设定／项目大纲／角色卡／项目剧本）各带一条永不横向溢出的横向滚动条（底部滑块），且 auto_hide 的 grid/grid_remove 在拖动时会放大成持续重排；勾选列固定 36px 也偏宽。

2. 测试跑了吗、三个基线过了吗：
   - 定向：test_ui_widgets_table 3/3、test_checkbox_column 2/2、test_column_fit 19/19、test_ui_edges 的文件表/点击规则 2 用例 OK。
   - 默认冒烟 8/8。
   - 架构门禁全量、完整安全全量：未跑（改动为纯 UI 布局，未命中 §5 强制条件；全量由 post-commit 后台补跑）。

3. project_status.md 欠账少了吗：本轮改源码 +1（ui_widgets.py、desktop_writing_page.py、responsive_ui.py），全量欠账由后台补跑清账。

## 根因
- 底部滑块：`DataTable` 无条件为每棵文件树建横向滚动条（`grid(row=1)`）；单列 `stretch=True` 的树永不横向溢出，滚动条既无用又占掉底部一整行。
- 拖动卡死缓解：`auto_hide_scrollbars` 的 `_scroll_state` 每次回调都 `grid()`／`grid_remove()`，与拖动时的各 Configure 回调互相喂，放大成持续重排。

## 修复
- `ui_widgets.DataTable` 新增 `horizontal=True` 参数：`horizontal=False` 时不建横向滚动条、`xscrollcommand` 置空；剧本准备四棵文件树传入 `horizontal=False`。
- `DataTable._scroll_state` 只在可见性真实变化时改布局，避免反复 grid/grid_remove。
- `responsive_ui.CHECK_COLUMN_WIDTH` 36→28（勾选图标约 14px，28px 仍居中可点），节省四列横向空间。

## 校验与契约
- 断言同步：`tests/test_ui_edges.py` 首列宽度断言 36→28（用户要求的 UI 契约有意变更，共享常量 `CHECK_COLUMN_WIDTH` 全站一致）。
- 未删除、未弱化其它断言；仅新增 DataTable 参数默认值向后兼容。

## 独立验收（advisor，主树真实环境直接运行）

- 范围：ui_widgets.py（DataTable horizontal 参数 + _scroll_state 防抖）、desktop_writing_page.py（四棵文件树 horizontal=False）、responsive_ui.py（CHECK_COLUMN_WIDTH 36→28）、tests/test_ui_edges.py（宽度断言同步 36→28）。
- diff 审查：horizontal=False 时横向滚动条不建、xscrollcommand 置空，单列 stretch 树无横向滚动语义不变；_scroll_state 只在可见性变化时 grid/grid_remove。
- 定向回归：test_ui_widgets_table 3/3、test_checkbox_column 2/2、test_column_fit 19/19、test_ui_edges 文件表 2 用例 OK；冒烟 8/8。
- 契约变更：CHECK_COLUMN_WIDTH 36→28 为共享常量，全站勾选列一并收窄；唯一硬编码 36 断言同步为 28，其余断言未动。
- 说明：拖动卡死是 R1751/R1757 一类的重排风暴，本轮从滚动条防抖＋去掉横向滑块两个方向缓解；若仍复现需进一步定位 fit_talk/fit_content 链。
