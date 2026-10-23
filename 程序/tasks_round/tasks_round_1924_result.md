# R1924 结果：测试治理阶段1收尾——源码文本断言迁入架构门禁

轮次类型：修复轮（测试资产整改）。分支 claude/affectionate-goldstine-5e7003。

## 改动
- 新增 `tests/architecture/test_source_text_contracts.py`（12 条），承接 12 处 `inspect.getsource` 契约锁：
  test_selftests 6 条、perf_baseline 2 条、desktop_shortcuts／project_recovery／project_rename_reconcile／ui_edges 各 1 条（ui_edges 为内联 2 句断言）、page_paint_metric 的 `fit_content` 一句。
- 原测试中对应用例或断言行删除；`test_page_paint_metric` 保留 `__name__`／`__wrapped__` 行为断言。
- architecture.md 门禁清单新增一行；该清单与文件集合相等性由 `test_agents_md` 通过。
- **断言未动**：迁移的断言内容逐字保留，无弱化、无跳过。

## 验证
- `run_selftests.py -k perf_baseline source_text_contracts selftests desktop_shortcuts page_paint project_recovery rename_reconcile`：ALL TESTS PASSED（经 gui_hidden）。
- 本工作树缺 `维护记录/基准历史.json` 等，`test_agents_md...performance_history...` 假红，与本轮无关。
- 未运行：`smoke_test.py --architecture` 全量、`--all --safe`。
- 剩余阶段 1 未做：`Desktop(root=PROGRAM)` 隔离、asset_gating ffmpeg 路径、宽松断言抽样；阶段 2–4 未开始。
