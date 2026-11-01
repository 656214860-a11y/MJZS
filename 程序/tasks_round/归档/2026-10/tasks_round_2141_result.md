# R2141 结果：删除全部页面进度条，改为转圈；剧本准备页等待模型回复时转圈（功能轮）

## 需求
用户：删除全部页面的进度条，参考 Claude Code 桌面版改为转圈；剧本准备页在模型返回数据时用转圈表现进度；其他页面的位置按最优方案设计。

## 设计
- 主窗口（各阶段页）：删掉状态栏上方的 `ttk.Progressbar`，忙碌只由状态栏右端已有的 `ui_motion.Spinner` 表示。
- 视频页（`app.py`）：删掉底部进度条，转圈挂在进度文字标签右端（`Spinner(host=progress_label)`）。
- 资源制作窗（`native_assets.py`）：同上，转圈挂在进度文字右端。
- 剧本准备页：「<模型> 模型正在思考…」行首内嵌一个转圈（Text `window_create`）；重绘时旧转圈随内容一起销毁，回复落地（`clear_thinking`）即撤。
- 启动画面 `ui_splash` 的加载条不属于页面，保留；`ui_theme` 的 `TProgressbar` 样式与 `BusyState` 的 progress 参数保留（无生产调用方，旧测试仍在用）。

## 改动文件
- `desktop.py`：删除进度条，`BusyState(self.status)`，spinner 仍在状态栏建好后挂上。
- `desktop_page_nav.py`：切页时不再 pack／forget 进度条。
- `app.py`、`native_assets.py`：进度条换成挂在进度文字右端的转圈。
- `desktop_idea_bubbles.py`：新增 `add_thinking_line`、`drop_thinking_spinner`；`clear_thinking` 撤转圈。
- `desktop_idea_chat.py`：思考行改调 `add_thinking_line`，重绘前 `drop_thinking_spinner`；去掉不再用的 `BUBBLE_TIME_FONT` 导入。

## 测试
- 新增：`test_idea_chat.test_thinking_notice_spins_until_the_reply_lands`（思考行内嵌运行中的转圈，重绘换新不累积，回复落地后销毁）；`tests/architecture/test_busy_state_boundary.test_production_pages_do_not_build_progressbars`（生产代码不得构造 Progressbar）。
- 契约有意变更、同步断言（断言未弱化）：`test_asset_gating` 资源窗子控件顺序 `Card, Progressbar, ProgressLabel, FlowBar` 改为 `Card, ProgressLabel, Spinner, FlowBar`（测试改名 `test_progress_text_with_spinner_directly_above_action_buttons`）；`test_generation_is_dispatched_through_the_desktop_async_boundary` 收尾停的对象由进度条改为按类型找到的转圈。

## 验证（本轮运行）
- `run_selftests -k idea_chat ui_edges script_composer asset_gating video_revision ui_motion ui_compact_widgets ui_notifications busy_state`：365 条，修正 asset_gating 一处后该文件 18 条全通过；改动收尾后 `-k idea_chat script_composer idea_bubble video_revision` 174 条、`-k idea_chat ui_edges` 268 条全通过。
- `smoke_test.py`：通过。
- `smoke_test.py --architecture`：411 条，仅既有红 `test_performance_history_is_declared_as_historical_only`（worktree 下基准历史.json 未入库）。中途曾触发 app.py 与 IdeaChatMixin 体量棘轮、Desktop 多写者属性棘轮，已通过把思考行搬进 bubbles mixin、合并行解决，未抬高上限。

## 未验证
- 未在真机启动截图确认三处转圈的视觉位置与底色。
