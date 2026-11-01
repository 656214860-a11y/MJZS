# R2215 结果：界面代码适配 Tk 9.0（Python 3.15.0 稳定版迁移前置，兼容轮）

## 三问
- 轮次类型：兼容轮（runbook §9 迁移步骤 3 的前置修复）。用户「逐步修复2-7项」第 4 项，用户明确要求先适配 Tk 9。
- 测试和三个基线：见「验证」。新旧解释器（3.15.0a2／Tk 8.6.15 与 3.15.0／Tk 9.0.4）对同一批测试各跑一遍；全量 `--all --safe` 本轮未手动运行。断言未动，未改任何测试。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 根因与改动
3.15.0 正式版随附 Tcl/Tk 9.0.4（旧 alpha 是 8.6.15），全量里 4 处界面测试只在新版红：
1. `desktop_tk_gc.protect_readonly_combobox`：把 `ttk::combobox::Scroll` 重写成固定两参 `{cb dir}`，Tk 9 的滚轮绑定改成三参 `Scroll %W %D -120.0`，调用报 wrong # args，可编辑下拉框滚轮失效（只读保护照常）。改为 `{cb args}` 并用 `{*}$args` 原样转发，两个版本都认。覆盖 `test_ui_edges::test_readonly_combobox_ignores_mouse_wheel` 与 `test_ui_widgets_inputs::test_select_box_keeps_readonly_wheel_guard_and_editable_scroll`。
2. `skill_panel._sync_form_view`：`int(canvas.cget('height'))`，Tk 9 的 Canvas 默认高度回 `'7c'`（带单位），int() 抛 ValueError，Configure 回调中断，矮窗口的纵向滚动条也就不出现。改为 `winfo_pixels(cget('height'))`。覆盖 `test_skill_panel_dropdown_layout` 与 `test_ui_batch5_stage_panel_and_script_page` 两条（后一条是同一个异常的后果）。

## 验证（含 Tk 的都经 `工作流任务/gui_hidden.py`）
- 4 个测试文件（test_ui_edges、test_ui_widgets_inputs、test_skill_panel_dropdown_layout、test_ui_batch5_stage_panel_and_script_page）：改前 3.15.0 下 4 处红；改后 3.15.0 与旧解释器下都只剩 `BriefTintTests::test_the_users_own_words_show_up_on_the_display`，是 R2192 结果文件已记的存量偶发红，新旧解释器都出现。
- `smoke_test.py --affected desktop_tk_gc skill_panel`（3.15.0）：通过 8 项，失败 1 项，即上述偶发红。
- 迁移基线（3.15.0，改前已测）：`test_stdlib_closure` 全过、默认冒烟 8/8、`--architecture` 411/411。
- 全量 `--all --safe`（3.15.0，改前）：7 个文件红，其中本轮修掉 4 处；`test_client_profiles`（1）、`test_distribution_selfcheck`（2）旧解释器同样红，是存量问题，与 Tk 版本无关；`test_leak_teardown` 单独重跑为绿（偶发）。该次全量因测量期间 HEAD 变化，未写绿凭据。

## 未做
- 3.15.0 的绿凭据（要求存量红清零或确认后重跑全量）；切换默认解释器路径；GUI 手工检查（Tk 启动、图标、白模宿主）。
- `test_client_profiles`、`test_distribution_selfcheck` 的存量红，另轮处理。
