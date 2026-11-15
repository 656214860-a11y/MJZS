# R2669 结果：platform_tools 流式回调吞错转 app_logging.swallowed（合并阻断）
<!-- round-evidence: {"commit_base": "2a18c9b4", "credential_hits": 0, "evidence_sha256": "4586bed91680db5f", "exit": 0, "failed": 0, "passed": 6, "round": 2669, "tests": "run_selftests.py -k silent_exception platform_process"} -->

1. 轮次类型：修复轮（棘轮未登记新增静默点的最小修复，T5 口径）。
2. 测试：`-k silent_exception platform_process` 全绿。
3. 欠账：棘轮口径 platform_tools 静默点 1→0，master 欠账下降。

## 说明

R2661 引入 `_stream_communicate_or_kill` 的逐行回调吞错 `except Exception: pass`，
未登记触发合并出口棘轮。按「应记录」口径改 `app_logging.swallowed("流式输出回调失败")`
（函数内惰性 import，保持启动路径轻量与现有注释语义一致）。
