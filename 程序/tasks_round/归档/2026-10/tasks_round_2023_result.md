# R2023 测试套件统一离线桩＋拆 ui_widgets 下调行数上限（测试隔离＋结构轮）

轮次类型：测试隔离＋结构轮（行为零变化；用户可见行为不变）。日期：2026-10-25。

## 做了什么

1. **统一离线桩**：`master_skill_update._fetch` 在环境变量 `DRAMA_SUPPRESS_NETWORK`（常量 `master_skill_update.SUPPRESS_NETWORK_ENV`）有值时直接按离线处理，`check()` 返回 `ERROR`，不碰 GitHub、不往 `data/总控包更新/` 写缓存；显式传入 `fetch=` 的调用不受影响。`run_selftests.py`（顶部 `setdefault`）、`smoke_test.py main()`、`scripts/auto_full_safe.py`、`scripts/local_ci.py` 都设置它，约定与 `DRAMA_SUPPRESS_MODAL`／`DRAMA_SUPPRESS_TRAY` 一致。正常运行不设该变量，更新检查照旧联网。根因见 R2020 结果文件：首帧 `after` 排程的 `start_master_update_check` 在自检里真联网，遇“有新版本”弹确认窗卡住隐藏桌面。新增 `test_default_fetch_stays_offline_under_the_suppress_env`。
2. **拆 ui_widgets**：`Tooltip`／`TreeRowTooltip` 移到新模块 `ui_tooltip.py`（L4，101 条可执行语句），`SPLASH_STAGES`／`Splash` 移到 `ui_splash.py`（L4，132 条）。`ui_widgets` 仍转出这些名字，旧导入路径不变；清掉拆出后不再使用的 import。`ui_widgets.py` 1425→1125 行。
3. **行数棘轮下调**：`OVERSIZE_CAPS['ui_widgets.py']` 1425→1125。`desktop.py` 仍 1377，未动。

## 三套基线

- 默认冒烟 `smoke_test.py`：8/8 通过（失败 0 项）。
- 架构门禁 `smoke_test.py --architecture`：410 条。拆分引起的 3 条红（`test_dialog_boundary`、`test_token_boundary`、`test_tooltip_boundary`，它们按文件名放行 `ui_widgets.py`）已把 `ui_splash.py`／`ui_tooltip.py` 加入同一放行集合，之后这三条与 `test_module_size_ratchet`、`test_coverage_baseline`、层表一并通过。其余 2 条红是工作树缺 `00全流程SKILL/AIGC创作全流程` 嵌套仓库造成的既有红（`test_agents_md` ERROR、`test_skill_reference_injection`），主目录无此问题。
- 覆盖率基线：321 个模块、50 个有行覆盖（`runbook.md` §11 同步）；`ui_widgets.py` 的可执行语句 886→693，新增 `ui_splash.py` 132、`ui_tooltip.py` 101，均 0 覆盖。

## 测试改动（断言未动）

- `tests/test_multi_monitor_popups.py`：`Tooltip` 现在读 `ui_tooltip.monitor_bounds`，mock 目标由 `ui_widgets.monitor_bounds` 改为 `ui_tooltip.monitor_bounds`，断言未动。
- `tests/test_app_metadata.py`：`DISPLAY_SOURCES` 里 `ui_widgets.py` 换成 `ui_splash.py`（`APP_NAME` 的用法随启动画面搬走），断言未动。
- 三个架构门禁与层表只扩放行集合／登记新模块，没有放宽任何检查口径。

## 验证

- 定向 Tk 用例经 `工作流任务/gui_hidden.py` 在隐藏桌面跑（`ui_widgets`／`Splash`／`Tooltip` 相关 35 个测试文件）：除工作树既有红外全过。既有红：`test_idea_chat`（缺嵌套技能仓库）、`test_skills` 71≠73（同因）、`test_pet_ui` 两条（几何、`test_it_opens_the_unattended_switch_then_starts_the_step`，合并前即有）以及 `test_idea_chat_presentation.test_shortcut_lookup_delegates_to_the_platform_adapter`（`media_page_services` 属性缺失，主目录 master 上同样红），均与本轮无关；`test_multi_monitor_popups`、`tooltip`、`splash_timing`、`ui_modern_system` 在 mock 目标更新后重跑全过。
- 同一份 `test_ui_edges` 在不打桩时会真联网；设置 `DRAMA_SUPPRESS_NETWORK` 后 115 条全过（上一轮已验证）。
- 未运行：`--all --safe`；真实界面目测（启动画面、提示浮层）。

## 债务变化

- 行数棘轮：`ui_widgets.py` 上限降 300 行；`desktop.py` 1377 待下一轮拆分。
- 新增 2 个 0 覆盖模块（拆出的代码原本就无行覆盖）。
- 未 push；本轮在分支 `codex/wip-R2023`，合入 master 需按合并轮流程在主目录操作并补记 R 轮次。
