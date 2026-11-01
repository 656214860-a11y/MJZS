# Round 358 结果

修复测试模式的 CLI 阻断：`run_selftests.py --incremental` 现在是显式兼容参数，不再被误当成筛选词而运行 0 个文件。自检调度与测试模式服务回归 19/19、默认 `smoke_test.py` 8/8 通过。
