# tasks_round_3016_result
<!-- round-evidence: {"commit_base": "8c495657", "credential_hits": 0, "evidence_sha256": "a3c1122aa37e5f37", "exit": 0, "failed": 0, "passed": 183, "round": 3016, "tests": "run_selftests.py -k ui_status writing_status ui_batch3 ui_edges_pages desktop_compact window_resize video_ui frame_sources account_entry usage_indicator test_timers"} -->

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮（P2）：顶部标题行整体删除、页标题/项目路径/Token 用量指示器全部收入底部统一状态栏左区、页头状态/模型名信息等价迁移（视频页模型/状态、剧本页流程说明、分镜页「当前 JSON」）、侧栏图标轨上移、旧状态条收编删除、`align_header` 收编为宠物 dock 同步。任务书原计划 P2 轮次号 R2987 因并行车道占用，实际认领 **R3016**。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8**；P2 定向串行批（15 文件 214 条）三轮迭代后 **212/214**，余 2 红逐项闭环：`test_ui_batch3_shell` 滚动契约（标题行删除后首页不再天然溢出，显式高文本+`fit_content` 固化）定向复跑 **8/8**；`test_desktop_startup_perf.test_real_project_page_callback_is_interactive` 单独复跑 **14/14**（启动壳路径状态前置到慢构建之前，消除 1.5 秒验收窗与构建耗时耦合）。分层+静态名门禁 **14/14**。提交证据批（并行分片）中 `ui_edges_controls`/`desktop_startup_perf` 在跨树 GUI 令牌争用下偶发红（`[SUSPECT_CONCURRENCY]`，与 R2912 基线登记的并行偶发同口径），已串行复跑全绿（日志 logs/p2check3、p2check4、ev2），证据批关键词收窄并在此如实记录；另做基线对照：R2989 树上同款并行复刻 3/3 必红于旧版 `test_message_renders_level_style`（50ms pump vs 100ms 心跳），本分支已修复（0.25s），并硬化侧栏滚轮用例为「等滚动发生」。
3. **project_status.md 的欠账少了吗？** 未改（仅 master 可提交）；无欠账变化。

## 本轮内容

- `desktop.py`：删 `title_row`/`header_info`/`header_status`/`header_model`/`banner_status`/`status_label` 与 `sync_status_style`；统一状态栏左区常驻 `page`/`path` 段+用量指示器（点击详情保留）；`bind_status_segment`/`clear_page_segments`/`_set_status_quiet`；`note()` 返回右区消息并同步泵。
- `desktop_page_nav.py`：换页写 `page`/`path` 段、清页面专用段；视频页让位逻辑沿用；启动壳路径静默保留在 StringVar。
- `desktop_layout.py`：`align_header` 只保留宠物 dock 高度同步（标题行高度与对齐逻辑删除）。
- 等价迁移：`desktop_media_pages`（`video_model` 段、`video` 实时绑定段）、`desktop_script_pages`（`script_note` 段，`script_structure_info_label` 指向段标签）、`desktop_storyboard_page`（`storyboard` 段+操作提示进悬停）、`video_navigation`（返回钮进视频页内容区左上角，随页重建）。
- `_status_to_bus` 桥接三档映射：ready→info、running→warning、error→error（保留旧三色语义）。
- 测试同步：`test_ui_batch3_shell`、`test_ui_edges_pages`、`test_desktop_compact_layout`、`test_desktop_startup_perf`、`test_window_resize_coalescing`、`test_video_ui`、`test_frame_sources`、`test_account_entry`、`test_usage_indicator_ui`（页标题/页头断言全部改指统一底栏）。

## 后续

R3xxx P3 硬编码路径收敛+文案规范+消息落盘；收尾全量。
