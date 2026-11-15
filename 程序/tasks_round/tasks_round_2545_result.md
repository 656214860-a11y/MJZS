# R2545 结果
<!-- round-evidence: {"commit_base": "35493169", "credential_hits": 0, "evidence_sha256": "a6f8fe74e20687ca", "exit": 0, "failed": 0, "passed": 15, "round": 2545, "tests": "run_selftests.py -k environment_check complexity_ratchet function_size_ratchet"} -->

1. 轮次类型：修复轮（R2538 的收尾：架构门禁 `test_parameter_count_does_not_grow` 报 `environment_check.run_checks` 11 个参数 > 上限 10）。
2. 测试：先红——全部架构门禁跑出该条红（453 条仅它与分支上必红的 `test_round_number_continuous`）；修复后 `test_environment_check`、`test_complexity_ratchet`、`test_function_size_ratchet` 全绿。断言未动，登记上限未抬高。
3. 欠账：无新增。

## 根因与改动

R2538 给 `run_checks` 新增了 `probe` 参数，把参数个数顶到 11。改为保持 `run_checks` 原签名，新增 `run_checks_with_versions(program, *, probe, **kwargs)`（先 `run_checks` 再 `apply_versions`），`report_text` 与「环境自检」按钮改用它；`run_checks()` 本身仍不启动程序。runbook §8、§13 同步措辞。
