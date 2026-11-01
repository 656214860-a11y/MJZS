# 第 166 轮：定向冒烟门禁零用例修复

## 问题

- `python smoke_test.py --affected run_selftests` 会把筛选词直接传给自检运行器。
- 实际测试名为 `test_selftests`，且运行器仍按增量台账跳过未改动用例，结果曾显示“0 个文件有红”但实际运行了 0 条。

## 改动

- `smoke_test.py` 增加源码模块到测试筛选词的别名：`run_selftests` 与 `smoke_test` 均映射到 `selftests`。
- 定向门禁若日志显示“跑 0 个测试文件”将明确失败，而不再误报通过。
- `run_selftests.py` 中显式 `-k` 改为忽略增量跳过并强制运行匹配测试；同时保留未选中测试的台账条目，避免定向运行冲掉其缓存。
- 补充自检运行器的迁移测试优先级和筛选映射断言。

## 验证

- `python test_selftests.py`：13 条通过。
- `python -m unittest tests.test_selftests`：13 条通过。
- `python run_selftests.py --serial -k test_selftests`：明确执行 1 个测试文件、13 条通过。
- `python smoke_test.py --affected run_selftests`：实际执行 `test_selftests` 的 13 条用例，9 项冒烟检查通过。

## 风险与下一步

- 本轮只改动测试门禁与诊断逻辑；不涉及项目数据、模型配置或外部调用。
- 后续为其他源码模块补充必要的定向筛选别名，并继续清理根目录可隔离测试。
