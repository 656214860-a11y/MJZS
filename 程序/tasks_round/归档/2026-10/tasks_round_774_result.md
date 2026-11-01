# R774｜`app.py` 网关名称补全（修复轮）

## 结果

`app.py:import_json()` 使用 `project_registry_gateway` 前缺少该名称定义。现仅在使用处导入 `stage_execution_service.project_registry_gateway`，解除 R771 遗留的静态名称错误；未改项目数据、业务语义或测试断言。

## 验证

| 命令 | 结果 |
| --- | --- |
| 静态名称检查 | 8/8 通过 |
| `python smoke_test.py` | 8/8 通过 |
| `python run_selftests.py --all --safe` | 3,523 条；仅 `test_perf_baseline` 1 条红 |

完整安全全量的唯一红项为 `tests/test_perf_baseline.py:321`：300 行滚动中位 179.0ms，独立复跑为 172.9ms，均超过 150ms 阈值。因此不更新 `维护记录/测试分层基线.json`，`last_full_safe_all_round` 保持 R769。

## Git

本轮未提交；commit hash：无。
