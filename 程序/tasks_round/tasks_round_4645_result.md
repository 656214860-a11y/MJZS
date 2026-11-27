# R4645 结果：C11 writing_api 迁出准备台账函数并下调体积上限
<!-- round-evidence: {"commit_base": "1e355a498", "credential_hits": 0, "evidence_sha256": "5a710b419dff970b", "exit": 0, "failed": 0, "passed": 79, "round": 4645, "tests": "run_selftests.py -k writing_preparation_ledger writing_api"} -->

- 轮次类型：执行轮（优化清单 C11）。
- 分支：`codex/opt-c11-split-writing-api`（基于 1e355a498）。

## 改动

- `orchestrator/writing_preparation_ledger.py`：迁入剧本准备台账内聚函数（`PREPARATION_REPLY_STATES`、`confirmed_preparation_files`、`preparation_file_labels`、`preparation_reply_state`、`preparation_reply_message`、`_preparation_state`、`_preserve_preparation_response`、`_preparation_task`、`_preparation_restart_affirmative`、`_versioned_publisher` 等），现 667 行。
- `writing_api.py`：删去上述实现，保留同名转发以保持全部公共符号与调用方兼容；约 1158 → 1027 行。
- `tests/architecture/test_module_size_ratchet.py`：`OVERSIZE_CAPS['writing_api.py']` 1372 → 1047（实际行数 +20，满足 ≤ 实际 +100）。
- `tests/test_writing_preparation_ledger.py`：新增 6 个回归用例，覆盖迁入函数行为与 `writing_api` 转发一致性。
- 未新增生产模块，未改 `runbook.md` 与 `维护记录/覆盖率基线.json`。

## 验证（`.wt\opt_c11\程序`，PYTHONIOENCODING=utf-8，`运行环境\Python\python.exe -B`）

| 命令 | 结果 |
|---|---|
| 暂存生产改动后 `-m unittest tests.test_writing_preparation_ledger`（修复前） | 6 测，failures=1、errors=5，exit 1（红） |
| 恢复改动后同命令（修复后） | 6/6 OK，exit 0 |
| `smoke_test.py` | 失败 0，exit 0 |
| `smoke_test.py --affected writing_api.py` | 通过 10、失败 0，exit 0 |
| `smoke_test.py --architecture` | 717 测 OK（286.5s），exit 0 |

- 断言：既有断言未删改、未弱化；无未登记 `skipTest`。
