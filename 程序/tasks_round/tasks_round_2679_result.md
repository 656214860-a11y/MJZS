# R2679 结果：platform_tools 静默点改走登记豁免（R2669 路线更正）
<!-- round-evidence: {"commit_base": "54cf7f5d", "credential_hits": 0, "evidence_sha256": "6bb96779e7086734", "exit": 0, "failed": 0, "passed": 26, "round": 2677, "tests": "run_selftests.py -k silent_exception layers"} -->

1. 轮次类型：修复轮（合并阻断的最小修复＋路线更正）。
2. 测试：`-k silent_exception layers` 全绿。
3. 欠账：与 master 持平——R2661 引入的静默点经登记豁免获得正当身份，
   不再是未登记新增债。

## 路线更正

- R2669 先按「应记录」改 `app_logging.swallowed()`，合并出口被 test_layers 拦下：
  platform_tools 是底层平台适配，引 app_logging 构成未登记越层。
- 更正为 T5 另一合规路径：回退 swallowed 改动，在静默异常棘轮
  `ALLOWED` 登记 `platform_tools.py: 1` 并注明豁免理由（越层实证＋注释语义降噪）。
- 棘轮总数 11→12：新增 1 处登记豁免（非未登记债），口径仍单调只降不升于「未登记」面。
