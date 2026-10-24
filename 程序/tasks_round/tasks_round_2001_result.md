# R2001 桌面换页决策与 after 计时器登记表下沉 page_navigation_controller（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J4**。日期：2026-10-24。
基线：`codex/wip-R1997` @ 74ab173a。零行为变更。

轮次类型：结构治理轮·执行（AGENTS.md §3.3）。三套基线：架构门禁仅剩 3 条已知历史红；默认冒烟 8/8；覆盖率基线同步（314→315 模块，`desktop.py` 1085→1044 行）。债务：`--all --safe` 欠账 +1；Desktop 共享状态上限 43→42，Desktop 类行数上限 1262→1214。

## 改动（2 个生产模块）

- 新增 `page_navigation_controller.py`（L3，无 Tk）：侧栏视频模式（`sidebar_video_mode`／`next_video_mode`／`choosing_video`）、整页缓存失效判据与缓存项（`stale_cache_keys`／`cache_entry`，02 页签名保持惰性计算）、换页前闸门（`needs_adopted_storyboard` 读偏好回调只在下游页才调用；`needs_source_selector`）、关闭窗口要取消的 after 任务名单（`NAV_TIMER_JOBS`／`STARTUP_TIMER_JOBS`／`LIFECYCLES`）与 `cancel_jobs`／`cancel_lifecycles`。页序号表与取消回调由 `desktop.py` 注入，不 import L4。
- `desktop.py`：`go_page`、`_page_cache_for`、`_show_cached_page`、`show`、`_show_reset_page`、`cancel_timers` 改调上述函数；`cancel_timers` 的取消顺序不变（导航／侧栏 → 生命周期登记器 → `_fit_job` 及标志 → 启动／轮询类），`self.win` 仍惰性取（最小 Desktop 替身不触碰）。
- 偏差：任务单写的是迁入 `desktop_page_registry.py`，但它是 L4 且只放常量；Tk-free 决策放 L3 新模块更合分层，`desktop_page_registry` 未动。计时器登记是「具名清单＋通用取消函数」，没有改成各 Mixin 自行登记（避免改动范围外的 Mixin）。
- 测试与登记：新增 `tests/test_page_navigation_controller.py`；`_layers.py` 登记 L3；`SERVICES` 加入；`test_complexity_ratchet` Desktop 类 1262→1214；`test_shared_state_ratchet` Desktop 43→42；覆盖率基线与 `runbook.md` §11（314→315、264→265；顺带把 `media_page_controller` 总行数校正为 145）；`architecture.md` 登记。

## 验证（本轮实测，经 gui_hidden）

- 定向 `-k page_navigation_controller page_cache timers ui_edges desktop_startup_perf final_page_loading storyboard_page_loading page_paint slowpage leak_teardown force_quit desktop_automation_service video_navigation account_entry`：233 条全绿。
- `smoke_test.py --architecture`：410 条，仅 3 条已知红（`test_agents_md`、`test_round_baselines`、`test_skill_reference_injection`）。
- 默认 `smoke_test.py`：8 项通过。
- 未跑 `--all --safe`，欠账 +1。未在真实窗口目测换页（缓存命中／视频模式选择）。
- **断言未动**：未修改任何既有断言；两个上限登记值为棘轮下调。
- 已知既有红未处理：`test_desktop_settings_callers` 的 `launch_comfy` 三条（R1995 起干净 HEAD 即红）。

## 回滚

撤回 `desktop.py` 与 `architecture.md`／`runbook.md`／覆盖率基线／三个架构测试的改动，删除 `page_navigation_controller.py` 与其测试。

## 下一步

J5 Pet 播报状态（`PetBroadcastState`，涉及 `pet_ui.py`、`pet_ui_stages.py`、`pet_ui_voice.py`）。
