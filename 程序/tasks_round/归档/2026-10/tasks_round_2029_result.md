# R2029 拆 desktop.py 下调行数上限（结构轮）

轮次类型：结构轮（行为零变化；用户可见行为不变）。日期：2026-10-25。

## 做了什么

1. `desktop.py` 1377→984 行，移出 `OVERSIZE_CAPS`（已 ≤1000）。
2. 新模块 `desktop_page_nav.py`（L4，`PageNavMixin`）：`page_of`、`show_stage`、`go_page`、`go`、整页缓存、`show`、`_show_reset_page`、两条页内提示，以及按页首帧耗时的 `_PAGE_PAINT_KEYS`／`_page_paint_key`／`_page_paint_timed`。
3. 新模块 `desktop_lifecycle.py`（L4，`LifecycleMixin`）：`cancel_timers`、`on_window_destroy`、`force_quit`、`stop_automation_processes`、`finish_close`、`reload`、`flush_brief`。`close` 留在 `desktop.py`（确认框按 `desktop.confirm` 取，测试按该名打补丁）。
4. 方法体原样迁出；两个 Mixin 放在 `class Desktop(...)` 基类最前，覆盖顺序不变。

## 登记

- 层表 `_layers.py` 登记两个新模块；`_scan.DESKTOP_PARTS` 加入两文件（源码契约测试仍把它们当 Desktop 的一部分）。
- `test_module_size_ratchet`：删去 `desktop.py: 1377`。
- `test_complexity_ratchet`：`Desktop` 类体 1214→838。
- `test_shared_state_ratchet`：`Desktop` 42→49。这是被动增加 7：原先同在 Desktop 内的写入变成跨 Mixin 类，属性没有新增。后续可减少耦合再下调。
- `test_startup_budget`：`STARTUP_CHAIN` 里的 `show` 随方法移到新文件。
- 覆盖率基线 323 个模块、50 个有行覆盖（`runbook.md` §11 同步）；`architecture.md` 同步。

## 测试改动（断言未动）

- `tests/test_app_logging.py`：`@app_logging.timed('page.show'` 的出处由 `desktop.py` 改读 `desktop_page_nav.py`，断言内容未动。
- `desktop.py` 工作区保持 CRLF（`test_line_endings` 钉住）。

## 三套基线

- 默认冒烟 `smoke_test.py`：通过。
- 架构门禁：除工作树缺嵌套技能仓库的既有两条（`test_agents_md` ERROR、`test_skill_reference_injection`）外全过。
- 定向 Tk 用例（引用 Desktop 的 125 个测试文件，经 `gui_hidden.py`）：本轮引入的 `app_logging`、`line_endings` 已修并重跑全过。其余红均在拆分前 HEAD 上同样红：`test_desktop_startup_perf.test_startup_script_guard_does_not_leave_tick_paused_after_page_switch`、`test_subtitle_export_service.test_desktop_export_methods_handle_success_and_failure`（`media_logic` 未定义于 exec 命名空间），以及缺嵌套技能仓库导致的 `test_idea_chat*`／`test_writing_*`／`test_cancellation_status`／`test_skills` 等、`test_pet_ui` 既有红。
- 未运行：`--all --safe`；真实界面目测。

## 债务变化

- `desktop.py` 行数上限移除；复杂度登记 −376；共享状态上限 +7（披露）。
- 新增 2 个 0 覆盖模块（原代码即无覆盖）。
- 未 push；分支 `codex/wip-R2029`。
