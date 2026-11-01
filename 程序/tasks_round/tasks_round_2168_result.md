# R2168 结果：剧本结构页空框「编辑」报错；自检写进真实诊断记录（缺陷轮）

## 三问
- 轮次类型：缺陷轮（§3.2 修复轮）。用户要求“先修高频报错”，依据是 `程序/logs/diagnostics/latest.json` 最近 50 条降级记录（2026-10-22～10-31）。无对应队列 ID。
- 轮次号：开工时领的是 2157。提交前其它并行会话已领到 2167，commit-msg 钩子只收中央最新领号，于是按规则 27 重新领号为 2168。改动随 `git switch -c` 带到分支 `codex/wip-R2168`；`codex/wip-R2157` 仍指向 master 的 14f853f7，上面没有提交。
- 测试和三个基线：在 worktree 分支 `codex/wip-R2157` 上运行（重新领号前；之后只改了注释和测试文档串里的轮次号），含 Tk 的都经 `工作流任务/gui_hidden.py`。
  - `run_selftests.py -k script_structure diagnostic secret_status app_logging video_result_polling desktop_async_tasks ui_reading_density`：135 条全过。
  - `run_selftests.py -k ui_edges`：全过。
  - `smoke_test.py --affected desktop_script_pages diagnostic_capture`：9 项全过（定向 40 秒，0 个文件有红）。
  - 默认冒烟：8 项全过。
  - `--architecture`：411 项除轮次基线 `test_round_number_continuous` 外全过（状态页待合并轮登记，见文末“基线”）。
  - 全量 `--all --safe` 本轮未手动运行。提交在 worktree 里做，worktree 没有 `运行环境/Python`，提交后钩子直接跳过，没有补跑（R2179 合并轮更正）。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 诊断记录里各类报错的来源
| 页面 | 报错 | 条数 | 项目路径 |
| --- | --- | --- | --- |
| 02 剧本结构 | 当前没有可修改的剧本文档。 | 26 | 用户项目 `摄影侠_20260930` |
| 08 首帧管理 | 当前操作尚未结束，请稍后 | 15 | 测试临时目录 `AppData\Local\Temp\tmp…\p` |
| 01 剧本准备 | 分镜预演 还没做完…（SG-B） | 3 | 测试临时目录 |
| 01 剧本准备 | 当前金额预估支持 Seedream 直连… | 3 | 测试临时目录 |
| 02 剧本结构 | 没有可恢复的删除内容。 | 1 | 用户项目 |
| 03 初步分镜 | 对应分镜初稿不存在或已迁移 | 1 | 用户项目 |
| 01 剧本准备 | 当前操作尚未结束，请稍后 | 1 | 用户项目 |

首帧页、剧本准备页那 21 条不是用户操作报的错，是自动化测试写进来的（根因 2）。

## 根因 1：剧本结构页空框的「编辑」可点
- 复现：项目里有自然剧本、还没生成结构剧本，打开剧本结构页，点结构剧本框右上的「编辑」，状态栏报「当前没有可修改的剧本文档。」。两份剧本都没有时，两个框都这样。
- 根因：`desktop_script_pages._install_script_edit_controls` 的 `sync_buttons()` 在非编辑态无条件启用「编辑」；建框后也只有结构剧本框调用过一次 `sync_buttons()`。`begin_edit()` 遇到 `active['path'] is None` 才报错。
- 需求对照：REQ-S02-35 只规定“无可后退时「后退」禁用”，没有规定空框的「编辑」，代码不偏离需求，需求文字不用改。本轮沿用同一条规则：没有可操作的对象就禁用按钮。
- 改动（`desktop_script_pages.py`）：非编辑态下「编辑」按当前是否有文档启停；两类内容框建好后都调用一次 `sync_buttons()`。框内文档只在下拉框里切换（只能选已有文档），删除后整页重建，所以建框时同步一次就够。
- 只读文档（`editable=False`）仍可点并报错：`test_script_structure_edit.py::test_readonly_box_refuses_edit_and_empty_restore_reports` 的断言未动。

## 根因 2：自检把测试里的报错写进程序自己的诊断记录
- 现象：例如 `tests/test_ui_edges.py::test_source_selector_display_snaps_back_when_switch_is_blocked` 故意在 `worker=True` 时切换首帧分镜，`Desktop.safe` 照常调用 `diagnostic_capture.record_degradation`，记录落进运行这次测试的那份程序的 `logs/diagnostics/latest.json`。主检出里跑的后台全量就写进用户那份。
- 根因：`diagnostic_capture.STATE_FILE` 固定指向程序目录；自检入口给弹窗、托盘、联网都设了 `DRAMA_SUPPRESS_*` 开关，诊断记录没有。测试里构造 `Desktop` 还会覆盖 `startup_timings`：本轮改前在 worktree 跑一次，`desktop_shell_ready` 就被写成 57.47 毫秒。
- 影响：这些记录显示在运行状况里，也会打进诊断导出包；本轮最初也按它们把首帧页当成了高频报错。
- 改动：
  - `diagnostic_capture.py`：新增 `SUPPRESS_DIAGNOSTICS_ENV = "DRAMA_SUPPRESS_DIAGNOSTICS"`。值为 `1` 且 `STATE_FILE` 仍指向程序自己的文件时，`_save_state` 不落盘；测试把 `STATE_FILE` 改指到临时文件时照常写，正常运行不受影响。
  - `run_selftests.py`、`smoke_test.py`：和其它 `DRAMA_SUPPRESS_*` 一样 `setdefault` 为 `1`。`scripts/auto_full_safe.py`、`scripts/local_ci.py` 都经这两个入口启动，不用改。
- 首帧页“忙碌时点击”的行为不变：`test_ui_edges` 要求这句提示落在非模态状态栏，属于既定设计。
- `启动错误.log`（`record_crash`）不在本轮范围：主检出那份最后修改于 2026-10-16，只有 2 条，没有测试污染的迹象。

## 测试
- 新增 `tests/test_script_structure_empty_box_edit.py`（真 Tk，2 条）。改前红：
  ```
  AssertionError: False is not true : 还没有结构剧本时「编辑」应禁用
  AssertionError: False is not true : script_structure_source_preview：框里没有文档时「编辑」应禁用
  ```
- 新增 `tests/test_selftest_diagnostics_isolation.py`（4 条）。改前红：
  ```
  test_selftest_never_writes_program_diagnostics
  AssertionError: WindowsPath('…/程序/logs/diagnostics/latest.json') unexpectedly found in [同一路径 ×3]
  test_selftest_entry_points_set_the_flag（run_selftests）
  IndexError: list index out of range        ← 子进程打印的开关值为空
  test_selftest_entry_points_set_the_flag（smoke_test）
  AssertionError: '    route(pet_bus STAGE_NAMES)' != '1'   ← 同上，空值被 strip 掉后只剩清单最后一行
  ```
  这条入口探针的红是在加 `FLAG=` 前缀之前拿到的；前缀只改输出的解析方式，不改判定（开关必须是 `1`）。另外两条（改指临时文件照常写、正常运行照常记录）改前改后都绿，用来防止屏蔽过头。
- 端到端：改后跑 `run_selftests.py -k ui_edges`，worktree 的 `logs/diagnostics/latest.json` 修改时间和大小都没变（改前同一批测试会追加首帧页记录）。
- 已有测试断言未动。

## 未做
- 剧本准备页的 SG-B 与估价报错：6 条全部来自测试临时目录，不是用户报的错。污染修掉后看新记录里是否还有真实触发，再决定要不要修。
- 气泡（pet_cloud／pet_cloud_hint）定时器在控件销毁后触发的 TclError：在吞掉的异常日志里，不在本轮范围；先查那份日志是否同样被测试污染。

## 用户需做
- 重启应用后生效。
- 你那份 `程序\logs\diagnostics\latest.json` 里已有的 21 条测试记录本轮没动（运行数据不属于源码）。新记录只留最近 50 条，会逐步挤掉它们；想立刻清掉可以自己删这个文件。

## 基线
- 默认冒烟 `smoke_test.py`（经 gui_hidden）：通过 8 项，失败 0 项。
- `--architecture`（经 gui_hidden）：411 项中 1 项失败，`test_round_number_continuous`（运行时结果文件还是 2157 号，报 2153 != 2158）。本分支不写状态页，合并轮登记当前轮次后恢复。其余全过。
  - worktree 缺受忽略的 `维护记录/基准历史.json`，第一次运行因此多一个 ERROR（`test_performance_history_is_declared_as_historical_only`）。第二次运行前从主检出临时拷入，跑完已删除，未提交。
- 全量 `--all --safe`：本轮未手动运行。worktree 没有 `运行环境/Python`，提交后钩子跳过，没有补跑（R2179 合并轮更正）。
