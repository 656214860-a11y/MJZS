# R837 结果：覆盖率审计 21 阶段目录进程收口

- `stage_layout.py` 的 Windows junction 回退改经 `platform_tools.run_process()` 执行，命令、静默标准流和基于返回码的成功判定不变。
- `platform_tools` 校准为 L0 基础适配模块，使 L0 阶段布局可以调用唯一进程入口而不形成向上层依赖。
- 审计 21 的 `stage_layout.py:411` 已从 pending 改为 migrated；冻结扫描、判据文档和台账的真候选数均为 0。
- R836 触发但漏跑的完整安全全量，由本轮实际补齐；`last_full_safe_all_round` 已更新为 R837。

## 验证

- 定向安全集：`run_selftests.py -k 'stage_layout legacy_adoption_service coverage_audit_ratchet unification_ratchet' --safe`，29 条／0 红。
- 默认冒烟：`python smoke_test.py`，8/8 通过。
- 架构门禁：`python smoke_test.py --architecture`，219/219 通过（47.123 秒）。
- 完整安全全量：`run_selftests.py --all --safe`，3663 条／0 红／928.3 秒，`ALL TESTS PASSED`。
