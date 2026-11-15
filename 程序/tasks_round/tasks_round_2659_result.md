# R2659 结果：local_ci 基准趋势日志写入移入 with 块（合并阻断修复）
<!-- round-evidence: {"commit_base": "41620ff2", "credential_hits": 0, "evidence_sha256": "f056f01a740810c9", "exit": 0, "failed": 0, "passed": 4, "round": 2659, "tests": "run_selftests.py -k benchmark_trend"} -->

1. 轮次类型：修复轮（合并出口崩溃的最小修复）。
2. 测试：合并出口 CI 即验证路径（趋势行已实测输出正确）。
3. 欠账：无新增；T8.3 随本轮合并落地。

## 根因

R2648 把基准趋势输出接到 local_ci 尾部，但 `log.write` 写在
`with LOG.open()` 块外（文件已关闭）→ ValueError → 出口档 CI 崩、合并中止。
修法：趋势块整体移入 with 内，终端 print 与日志写在同一块。
