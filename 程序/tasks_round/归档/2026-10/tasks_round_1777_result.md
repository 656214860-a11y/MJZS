# R1777：启动画面不再被建页任务吞帧 + 启动耗时落诊断（优化轮）

1. 本轮类型：§3.1 优化轮（启动路径）。来源：R1777 审计第 27 项——启动画面各段耗时没有任何记录，进度条冻结问题无法复盘。

2. 测试跑了吗、三个基线过了吗：
   - 新增 `tests/test_splash_timing.py`（3 条，不起 Tk，直接测 `Splash` 的计时方法）通过。
   - 定向 `run_selftests.py -k splash_timing ui_widgets ui_edges launcher startup architecture`：378 条，1 个文件有红（见「未通过项」），5 个 GUI 测试因别的进程持有 GUI 令牌被延后；延后的 `test_ui_edges test_ui_widgets_dialogs test_ui_widgets_inputs test_ui_widgets_table test_desktop_startup_perf` 随后单独串行复跑：148 条、0 个文件有红。
   - 默认冒烟通过。
   - 完整安全全量：本轮改了启动路径（`启动漫剧制作助手.pyw`、`ui_widgets.Splash`），合入 master 后由 `scripts/auto_full_safe.py --run` 补跑，未跑前不写通过。

3. project_status.md 欠账少了吗：本轮改源码 +2（ui_widgets.py、启动漫剧制作助手.pyw）；全量欠账由合入后补跑清账。

## 改动

- `ui_widgets.Splash.step` 改为只 `update_idletasks()`：`update()` 会把已到期的 `after` 任务（项目加载、建页）整队排空进这一次调用，Splash 的动画帧没机会执行，进度条冻结。加载交给主循环按拍推进。
- `Splash` 记录各段与收尾耗时（`marks`：`stage_N`、`ready`、`total`，毫秒，距创建），收起时一次性交给 `on_finish`；回调抛错只记 `app_logging.swallowed()`，不挡揭开主窗口。
- `启动漫剧制作助手.pyw` 给 `splash.on_finish` 挂回调，把 `ready`、`total` 经 `diagnostic_capture.record_startup_timing` 写成 `splash_ready`、`splash_total`（L5 入口调用，不新增层级依赖）。

## 未通过项

- `architecture.test_round_baselines.test_round_number_continuous`：状态页轮次头是 1776，而最新结果文件已是 R1776／R1777，要求头＝最新结果＋1。`project_status.md` 只允许 master 提交，按规则 41 在合入 master 后单独补一次（`R<n>: 补记分支 … 的轮次记录`），分支上此项预期为红，不是本批引入。

## 提交

- 已在分支 `claude/project-handoff-f6eb50` 提交，commit hash 见 git log `R1777:`。
