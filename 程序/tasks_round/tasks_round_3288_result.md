# R3288：L1 基础设施层优化任务书 · 轮 3（丢失更新）结果
<!-- round-evidence: {"commit_base": "f7e0e3a3", "credential_hits": 0, "evidence_sha256": "086638f4e10c4200", "exit": 0, "failed": 0, "passed": 315, "round": 3288, "tests": "run_selftests.py -k l1_lost_update account model_pool usage pet_settings"} -->

## 三问

1. **轮次类型**：§3 可靠性轮（任务书「轮 3：丢失更新」，runbook §15 可靠性边界）。顺序按任务书固定：先 R3-a／R3-b 读失败处置，再 R3-c 加锁。
2. **测试跑了吗、基线过了吗**：定向自检 280 条全绿（13 文件，含新 `test_l1_lost_update` 14 条）；`smoke_test.py --affected` 见下；默认冒烟与架构门禁在合入轮出口 CI 复核。全量 `--all --safe` 由 master 合入前验收锁串行执行。
3. **欠账少了吗**：少了。四处「读—改—写」从无跨进程互斥变为 `agent.publication.access()` 内整体临界区；两处写路径从「读不出当空、整份写回」变为「读不出拒绝写／坏文件留 `.corrupt` 证」。R3-d 明确不改 `agent/core.py read_json`，只读路径泄漏按任务书记为欠账。

## 变更清单

| 编号 | 文件 | 改动 |
| --- | --- | --- |
| R3-a | `infra/account_store.py` | 新增 `_load_write()`：文件不存在→空；`FileNotFoundError` 竞态→空；其余 `OSError`/`ValueError` → 抛中文可操作错误（含路径与重试/移走指引），**不写盘**。`save_session`/`note_server_time`/`mark_update_seen`/`clear_session` 写路径全部改用；`load`/`last_email`/`update_seen` 只读路径不变。`device_fingerprint` 补种子分支锁内重读（双检），快路径仍走宽松 `load()`。 |
| R3-b | `infra/project_settings.py` | 新增 `_read_for_write()`：读失败时把原文件 `os.replace` 改名 `ui_settings.json.corrupt` 保留，再按空处理；`put()` 改走该严格读取。`load()`/`get()` 只读路径不变。 |
| R3-c | `account_store.py`、`project_settings.py`、`infra/usage_history.py`、`infra/model_pool.py` | 四处读—改—写整体放进 `with agent.publication.access():`（可重入，内层 `read()`/`save()`/`file_cache.read_json` 不死锁）。`model_pool` 新抽 `_update(mutate, program=None)`：锁内 `agent.core.read` 重读盘→`mutate`→`store()` 原子写回；配置读不出抛 `RuntimeError`，`record_health` 捕获后只留本次结果不盖写。台账 `request_ledger` 保留自有 `.lock`（R3248 已改 `time.monotonic()` 期限，L-N2 满足），未动。 |
| R3-d | — | 未改 `agent/core.py`（按任务书）。 |
| R3-e | `tests/test_l1_lost_update.py`（新）、`tests/test_account_client.py`（既有） | 新增 14 条：读失败拒写且磁盘字节不变（`PermissionError`/截断 JSON 两例）、会话合并写与 `server_time` 只增不减、双进程会话字段并发、`ui_settings.json` 坏文件 `.corrupt` 留证＋`put` 成功、双进程 100 异名键零丢失、`usage_history` 双进程异日归档零丢失、`record_health` 合并不抹模型池/坏配置拒写/健康度与前台保存并发不回滚、`lease_verifier` 签名长度不符负例。验签正例/篡改/未知 kid/宽松填充等已由 `test_account_client.LeaseVerifierTests` 覆盖，不重复。 |

## 验证记录

- `run_selftests.py -k l1_lost_update`：14 条全绿（2.8s）。
- `run_selftests.py -k project_settings account_store lease_verifier usage model_pool l1_lost_update account_client account_security account_offline pet_settings`：13 文件 280 条全绿（44.1s；Tk 项经隐藏桌面，`invalid command name` 为既有 teardown 噪音）。
- `smoke_test.py --affected project_settings account_store usage_history model_pool`：10/10 通过（门禁串行跑 103 条定向用例全绿，含 `test_login_gate`；GUI 令牌跨树排队约 2 分钟）。
- `smoke_test.py`（默认冒烟）：9/9 通过。
- `smoke_test.py --architecture`：（合入轮出口 CI 覆盖）
- `run_selftests.py --all --safe`：（合入 master 前验收锁串行；上次后台全量凭据见 `full-safe-receipts.json`）

## 边界与欠账

- `publication.access()` 全局发布锁内只做读、改、存，不做网络/子进程（任务书风险表已评估：四文件都很小）。
- `usage_history.record_today` 坏月度文件仍按既有宽松语义重建（任务书把读失败处置只授权给 account_store/project_settings）；归档失败向上抛由调用方吞掉，不影响记账——记为观察项，不扩大范围。
- `agent.core.read_json` 只读路径「锁忙/读失败当空」的泄漏按 R3-d 记欠账，待 L0 轮次评估。
- `model_pool` 其余整份读写入口（如 `require_certified` 设置）不在本轮五处清单内，未动。
- request-ledger 并发路径沿用 R3248 的自有 `.lock`＋结算降级，未新增测试（已有 `test_l1_reliability_r3248` 双进程用例覆盖）。

## 提交

- 分支：`codex/l1-lost-update`（领号 R3288，`round_claim.py next`）
- 提交：本结果文件随实现同批提交（`codex/l1-lost-update`）
- 合入 master：（待合入轮确认）
