# R1851 结果（功能轮）：前端改进清单第 1～3 项

- 第 1 项 边框对比度：`border_default` #EFF3F4→#DCE3E7（原在 background_primary 上约 1.06:1，几乎看不见）；表格「已完成」行底色原借用 border_default，改用新令牌 `row_completed`（值不变 #EFF3F4），涉及 app.py、desktop_asset_pages.py、desktop_storyboard_page.py、local_previs.py、storyboard_files.py；design_tokens.md 同步。accent／warning 经查没有用作文字色，无需改。
- 第 2 项 键盘快捷键：desktop_layout.LayoutMixin.page_shortcut＋desktop.py 绑定。Ctrl+1…9／Ctrl+0 跳到第 1…10 页，Ctrl+PageUp／PageDown 前后翻页（循环），全走 go_page；焦点在文本框时不抢键。新增 tests/test_desktop_shortcuts.py（5 条）。
- 第 3 项 三虎字号：未改。test_pet_cloud_r1449 与 test_pet_ui 把「气泡正文比 body 小一档、提示比回复框小一档」写成契约，单独调大会破坏层级；要改需整体调整字号阶梯，留待用户决定。断言未动。

## 验证
- gui_hidden 下 run_selftests -k ui_ pet_cloud pet_ui storyboard asset_pages local_previs app_ desktop_layout：除 test_ui_edges 5 条外全绿；这 5 条在干净 HEAD 上同样红（隐藏桌面窗口无法放大／滚动），与本轮无关。
- -k desktop_shortcuts desktop_layout desktop_nav ui_token：28 条 0 红。
