# R586 修复轮结果：同页重建滚动恢复

## 结果

已修复同一页面重建（刷新／筛选／重新渲染）后画布回到顶部的问题；新页面切换仍按既有行为从顶部开始。

## 根因与修复

- 根因：`Desktop.show()` 在 `desktop.py` 中记录旧滚动位置后，`fit_content()` 通过 `after_idle` 异步更新 `scrollregion`。原先恢复动作发生在旧或中间布局上，下一次布局重算会把位置压回顶部。
- 修复：将旧位置登记为待恢复状态；`fit_content()` 对最终布局键（画布宽度、内容请求高度、目标高度）连续两次一致后，才调用 `restore_scroll()`。布局仍不稳定时仅再请求一次空闲重算，不使用固定睡眠或同步强制布局。
- 防御：布局测量异常时初始化布局键，避免异常处理路径引用未赋值的局部变量。

## 改动文件

- `desktop.py`：同页重建的待恢复滚动状态与稳定布局确认；仅调整画布布局时序，不改页面事件、数据或控件结构。

## 验证

- `python -m unittest tests.test_ui_edges.UiEdgeTests.test_same_page_rebuild_keeps_scroll_offset`：1/1 通过。
- `python smoke_test.py --affected ui_edges`：109/109 通过（165.6 秒）。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：101/101 通过。

## 剩余观察项

完整 UI 边界回归退出时仍打印少量 Tk 过期 `after` 回调告警；自检台账同时报告临时文件权限告警。两者不影响 109 条用例结果，但尚未证明定时器释放完全无噪声，保留为 UI 回归治理 P0 的下一项诊断对象。
