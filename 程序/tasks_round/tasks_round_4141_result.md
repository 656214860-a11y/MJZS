# R4141 结果：钉死证书到期前 60 天告警（FIX-AUD-CERT-EXPIRY）
<!-- round-evidence: {"commit_base": "3383684c", "credential_hits": 0, "evidence_sha256": "fe6c735a544b33e1", "exit": 0, "failed": 0, "passed": 59, "round": 4141, "tests": "run_selftests.py -k account_client"} -->

## 开头三问

（一）本轮类型：修复轮。任务卡 FIX-AUD-CERT-EXPIRY（队列 167）；缺陷 AUD-MODEL D3——账号服务裸 IP＋自签钉死证书 2027-10-22 到期，到期前无告警。车道 `codex/fix-aud-cert-expiry`，基准 `3383684c`。

（二）测试与三个基线：`run_selftests.py -k account_client` 改前 59 条里 1 条红（新复现用例），改后 59 条全过（原 58 + 新增 1），退出码 0。`smoke_test.py --architecture` 700 条全过，退出码 0。默认冒烟与全量自测未跑。

（三）欠账：本卡只许改 `account_client` 与其测试，已提供 `pinned_cert_warning` 供账号页／自检调用；账号页与自检的接线未做（清单外）。

## 缺陷复现

改前模块无到期告警 API。新用例 `test_pinned_cert_warns_within_sixty_days` 调用 `pinned_cert_not_after`／`pinned_cert_warning`——改前失败：`AttributeError: module 'domain.account_client' has no attribute 'pinned_cert_not_after'`。

## 改了哪些文件

- `domain/account_client.py`：新增 `PINNED_CERT_WARN_DAYS`、`pinned_cert_not_after`（按 ASN.1 UTCTime 标签解析 `notAfter`）、`pinned_cert_warning`（到期前 60 天内及已过期返回中文告警，否则空串）。未改 `BASE_URL`／`PINNED_CERT` 正文。
- `tests/test_account_client.py`：新增上述复现／锁定用例。
- 本结果文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `git status --porcelain` / `git log -1` / 分支 | 干净；`3383684c`；`codex/fix-aud-cert-expiry` |
| `run_selftests.py -k account_client`（改产品前） | 退出码 1；共 59 条，1 红：`AttributeError: ... pinned_cert_not_after` |
| 同上（改产品后） | 退出码 0；共 59 条，0 红；`ALL TESTS PASSED` |
| `smoke_test.py --architecture` | 退出码 0；`Ran 700 tests in 291.917s`；`OK` |
| `scripts\dev.py claim` | 领到 4141 |

## 如实说明

- 未改证书与服务地址；未在真实账号页／自检界面接线展示（超出本卡允许文件）。
- 未跑默认冒烟与全量自测。
- 当前日历距 2027-10-22 仍超过 60 天，真实「现在」调用 `pinned_cert_warning()` 会返回空串；用例用注入的 `now` 覆盖。
