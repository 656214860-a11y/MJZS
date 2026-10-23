# R1937 修复轮结果：侧栏滚轮把标题与齿轮推离顶端

- 现象（用户实机截图）：左侧栏滚轮后，「漫剧助手」标题与设置齿轮整体下沉，上方留出空白。
- 根因：`ui_scroll.EasedScroll.scroll` 在内容比可视区矮（无可滚距离）时退回 Tk 原生 `yview_scroll`；Tk 画布在滚动区小于窗口时仍会把内容推离顶端。齿轮由 `align_header` 按标题真实位置摆放，所以跟着一起下沉。问题自 R1786／R1792 引入侧栏滚动与滚轮缓动起就存在，与 R1926 无关。
- 修复：新增 `_fits()`，滚动区已定且不高于可视区时取消动画、`yview_moveto(0.0)` 钉回顶端，不再滚。滚动区未定、固定 `yscrollincrement` 的原有退回原生路径不变。
- 测试：`tests/test_ui_motion_perf.py` 新增 `test_wheel_on_content_shorter_than_view_never_moves_it`（按 `canvasy(0)` 判定；原 `yview()==(0,1)` 断言在此情形下看不出位移）。在旧代码上该用例为红，修复后为绿。
- 验证：经 gui_hidden 跑 `-k ui_motion_perf desktop_compact sidebar desktop_layout`，32 条全绿。未跑全量、未跑架构全门禁，需用户实机确认滚轮手感。断言未动。
- 另答用户「是否在跑测试导致卡顿」：本次检查时本机只有用户自己的 1 个 pythonw 进程，没有测试在跑；此前定向测试在隐藏桌面运行期间会占 CPU，可能与当时感到的卡顿叠加。启动卡顿的主因仍是剧本准备页建页 1.2～3.5 秒（见 R1926 结果文件），尚未拆分。
- 回滚：`git revert` 本轮提交。
