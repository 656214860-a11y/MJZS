# R2071 复核 10-25 后台全量 12 个红项；修状态栏用例等不到延迟回填（修复轮）

轮次类型：修复轮。日期：2026-10-26。

- 复核：在主目录 master `d39427db` 定向重跑 12 个红项 + `test_ui_edges`。9 项已转绿；仍红 3 个文件 5 条：
  - `architecture.test_round_baselines`（2 条）：轮次号要等结果文件补上；R2070 欠一次后台 `--all --safe`。属流程状态，不是代码问题，本轮提交后由后台补跑。
  - `test_distribution_selfcheck`（2 条）：主目录有 2623 个经 `info/exclude` 忽略的本机文件（`.tools/`、`.agents/worktrees/` 等）不在分发清单。属本机环境，未改。
  - `test_writing_status_line.test_visible_label_is_compact_and_tooltip_keeps_detail`：单跑也红，已修，见下。
- 原因：状态栏和真实历史由 `desktop_idea_deferred` 等布局稳定后才回填（`_idea_page_update_job`，最长 2 秒）；`settle_script_page` 只泵 0.18 秒，而且只在模型键请求已发出时才继续等，所以读 label 时回填还没跑（`full_text` 为空）。
- 修复（`tests/test_idea_chat.py::settle_script_page`）：`_idea_page_update_job` 未执行时也继续等（上限 10 秒）。只改测试同步，断言未动。
- 验证：主目录 `run_selftests -k test_idea_chat test_writing_status_line test_ui_edges test_pet_ui test_popup_no_interrupt` 共 877 条 0 红；`test_ui_edges` 批量运行本次未复现间歇红。
- 未运行：`--all --safe`、真实界面目测。未 push。
