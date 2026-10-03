# R855 结果｜旧版 ComfyUI 提交异常可见化

旧版 `/drama/assets/dispatch` 即使任务可能已排队也会返回 HTTP 异常。现在该分支保留安全的“不重复提交”语义，并向用户明确显示将继续核对进度与输出目录；回归断言该提示可见。

验证：`test_native_run.py` 6／0 红；`smoke_test.py` 8／8。

完整安全全量：`run_selftests.py --all --safe`，3,698 条用例、996.8 秒、`0 红`；`tests.architecture.test_round_baselines` 已复核本记录。

`[TASK_COMPLETE]`：网络异常不再静默伪装为正常提交。
