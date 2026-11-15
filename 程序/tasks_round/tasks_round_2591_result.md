# R2591 结果：修复 R2589 合入门禁——request_json 参数收拢与覆盖率基线刷新
<!-- round-evidence: {"commit_base": "0c730585", "credential_hits": 0, "evidence_sha256": "e993883bdc01dcbc", "exit": 0, "failed": 0, "passed": 22, "round": 2591, "tests": "run_selftests.py -k coverage_baseline complexity_ratchet http_client http_boundary"} -->

## 类型与三问

- 类型：修复轮（合入门禁暴露）。
- 测试：`run_selftests.py -k "coverage_baseline complexity_ratchet http_client http_boundary"` 全绿。
- project_status 欠账：无新增。

## 修复

- `http_client.request_json` 11 个参数超复杂度棘轮上限 7：可选项收进 `**opts`（`_OPTION_KEYS` 白名单，未知键 TypeError），签名降为 6 参；调用方 kwargs 不变。
- `维护记录/覆盖率基线.json` 增 `http_client.py` 条目 → 368 模块／59 覆盖；`runbook.md` §11 口径同步 368/59/309。

## 提交

- 待回填 hash。
