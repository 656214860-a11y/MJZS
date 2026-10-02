# R786｜UI 统一入口第三批第 13 项：滚动条主题（已验收）

## 改动

将 `Vertical.TScrollbar` 与 `Horizontal.TScrollbar` 的滑块、轨道、箭头、边框和 active 颜色收口到 `ui_tokens.SCROLLBAR_*`，由 `ui_theme.apply()` 统一应用。新增架构门禁，要求两个方向均共用 token 与 active 映射。未改动任一滚动容器、滚动命令或页面数据语义。

## 验证

- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected ui_theme ui_tokens`：9/9；`test_ui_theme` 15 条／0 红。
- 主题边界与 AGENTS 清单：10 条／0 红。
- `python smoke_test.py --architecture`：152/152，通过且不低于 R785 的 151/151。

## 分档

本轮未改 Tk 生命周期／事件绑定、启动路径、删除语义或层级登记表；R786−R785=1，不触发完整安全全量。未执行 git add、commit 或 push。

建议 commit message：`style(ui): centralize scrollbar theme tokens`
