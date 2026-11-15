# R2644 结果：修复 test_selftest_incremental_gaps 环境变量恢复目标漂移（全量 73 秒崩）
<!-- round-evidence: {"commit_base": "f4e7e7f3", "credential_hits": 0, "evidence_sha256": "c386e7908d801ea7", "exit": 0, "failed": 0, "passed": 5, "round": 2644, "tests": "run_selftests.py -k selftest_incremental"} -->

1. 轮次类型：修复轮（全车道合并阻断的最小修复）。
2. 测试：`-k selftest_incremental_gaps` 全绿；冒烟同轮验证。
3. 欠账：T7.2 拆分引入的回归清除一处；T8 余 8.2/8.3/8.4，T9、T10 未动。

## 根因

R2639 拆分把 HERE/TESTS_DIR 权威移入 `selftest_env`；本测试 setUp 设置
`selftest_env.HERE/TESTS_DIR` 指向 TemporaryDirectory，但 addCleanup 仍恢复
`run_selftests.HERE/TESTS_DIR`（拆分后的 facade 影子属性）。清理后 env.HERE
仍指向已删临时目录 → 并行 worker 复用时下一单元 `os.chdir(env.HERE)` 崩
（FileNotFoundError tmpk8u5sv1u，全量 73 秒退出 1，无凭据）。

## 修法

恢复目标改回 `selftest_env`（一处）。全仓 grep 复核：其余 env.HERE/TESTS_DIR
设置点均同模块恢复，无第二处漂移。
