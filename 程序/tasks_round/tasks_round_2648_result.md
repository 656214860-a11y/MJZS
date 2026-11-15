# R2648 结果：SWE-2 T8.3——全量耗时基准趋势告警（告警级）
<!-- round-evidence: {"commit_base": "d098f24e", "credential_hits": 0, "evidence_sha256": "25bd432a26893383", "exit": 0, "failed": 0, "passed": 4, "round": 2648, "tests": "run_selftests.py -k benchmark_trend local_ci"} -->

1. 轮次类型：验证基线轮（开发期工具＋CI 告警接线；不硬门禁）。
2. 测试：`-k benchmark_trend local_ci` 全绿；冒烟 8/8。
3. 欠账：T8 余 8.2 黄金文件／8.4 覆盖率下限；T9、T10 未动。

## 交付

- `scripts/benchmark_trend.py`：读 Git common-dir `full-safe-receipts.json`
  （唯一权威凭据），最近绿全量秒数对比近 5 次中位，> +25% 输出【警告】；恒退 0。
- `scripts/local_ci.py`：主步骤全过后追加运行趋势脚本，输出进终端＋ci 日志，不影响退出码。
- `tests/test_benchmark_trend.py`：排序过滤／回退告警／正常波动静默／样本不足 4 条。
- 实测：最近绿全量 406s（R2633）vs 中位 448s，比值 0.91，无告警。
- 启动耗时侧：app_logging 的 perf_metrics 只有 fast/slow 桶，无结构化启动秒数；
  记录为后续项（test_desktop_startup_perf 已有断言但无历史写入）。
