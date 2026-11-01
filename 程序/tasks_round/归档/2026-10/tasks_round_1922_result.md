# R1922 修复轮结果：测试模块治理阶段 1（部分）

类型：修复轮（测试资产）。依据：`C:\Users\LAIBIAO\.claude\plans\purring-frolicking-beaver.md` 的四阶段计划。本轮只完成阶段 1 的第一小段，其余明确未做。

## 已做（断言未弱化）
- `tests/test_subtitle_export_service.py::test_skill_tool_delegates_srt_publication_to_service`：原先 `inspect.getsource` + `assertIn/NotIn` 源码字符串，改为行为断言——替身发布器只被调用一次、参数为目标路径、skill 工具自己不落盘、返回的 `subtitle_file` 正确。
- `tests/test_desktop_shortcuts.py::test_cloud_fade_out_skips_steps_when_reduced`：原先只查源码里有没有 `reduce_motion()` 字样，改为用假窗口跑 `CloudTimingMixin._fade_out`：减少动效时直接收起（不调 alpha、不排定时器），关闭时走第一档渐隐并排一个定时器。

## 验证
- 经 `gui_hidden.py` 跑 `run_selftests.py -k subtitle_export desktop_shortcuts`：ALL TESTS PASSED（14 条 + 8 条 + 架构 3 条）。
- 未跑 `smoke_test.py`、`--architecture`、全量。

## 未做（交接）
阶段 1 其余：仍有 15 处 `inspect.getsource`（`test_page_paint_metric.py:115`、`test_perf_baseline.py:286/296`、`test_project_recovery.py:122/125`、`test_project_rename_reconcile.py:218`、`test_selftests.py` 6 处、`test_ui_edges.py:1140`、`test_desktop_shortcuts.py:46`），多数是"不得出现 X"的契约锁，需逐个判断改行为断言还是迁入 `tests/architecture/`（后者要同轮更新架构门禁清单）；`Desktop(root=PROGRAM)` 隔离排查、`test_asset_gating.py` ffmpeg 路径、宽松断言抽样。阶段 2、3、4 整段未开始。
