# R4139 结果：软提示「已见」改到展示回调成功之后再记（FIX-AUD-UPDATE-SEEN）
<!-- round-evidence: {"commit_base": "3383684c", "credential_hits": 0, "evidence_sha256": "b28b566976da9b0e", "exit": 0, "failed": 0, "passed": 12, "round": 4139, "tests": "run_selftests.py -k update_notice account_background_checks"} -->

## 开头三问

（一）本轮类型：修复轮。任务卡 FIX-AUD-UPDATE-SEEN（队列 166）；缺陷 AUD-BOOT D4——后台线程里先 `mark_update_seen` 再回界面展示，展示前崩溃则该版本软提示永久丢失。车道 `codex/fix-aud-update-seen`，基准 `3383684c`。

（二）测试与三个基线：`run_selftests.py -k update_notice account_background_checks` 改前 11 条里 1 条红（新复现用例），改后 12 条全过（原 11 + 新增 1，另有展示回调用例共使 update_notice 从 5 条增到 7 条），退出码 0。`smoke_test.py --architecture` 700 条全过，退出码 0。默认冒烟与全量自测未跑。

（三）欠账：无。未在真实界面点过版本提示；`account_store.py` 本轮未改。

## 缺陷复现

改前 `AccountController.check_update` 的后台 `work()` 在调用展示回调之前就对软提示写入 `update_seen`。新用例 `test_soft_seen_not_marked_when_display_callback_crashes`：展示回调抛错后断言 `update_seen` 仍为空——改前失败：`AssertionError: '1.0' != ''`。

## 改了哪些文件

- `orchestrator/account_controller.py`：`check_update` 的 `work()` 去掉提前 `mark_update_seen`；新增 `mark_update_seen` 供展示回调调用。
- `ui/desktop_account_page.py`：`_update_checked` 在软提示且 `proactive` 时，`status.set` 成功之后再 `account.mark_update_seen`。
- `tests/test_update_notice.py`：旧「每版本只主动一次」改为展示成功后才 mark；新增崩溃不 mark、以及 `_update_checked` 写状态栏成功才 mark / 失败不 mark 两条。
- 本结果文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `git status --porcelain` / `git log -1` / `git rev-parse --abbrev-ref HEAD` | 干净；`3383684c`；`codex/fix-aud-update-seen` |
| `run_selftests.py -k update_notice account_background_checks`（改产品前） | 退出码 1；共 11 条，1 个文件有红。红：`test_soft_seen_not_marked_when_display_callback_crashes`，`AssertionError: '1.0' != ''` |
| 同上（改产品后） | 退出码 0；共 12 条，0 个文件有红；`ALL TESTS PASSED` |
| `smoke_test.py --architecture` | 退出码 0；`Ran 700 tests in 236.474s`；`OK` |
| `scripts\dev.py claim` | 领到 4139 |

## 如实说明

- 未在真实界面验证版本提示弹条与账号页卡片。
- 未跑默认冒烟与全量自测。
- 强制升级（hard）仍每次 `proactive=True`、不写 `update_seen`，行为未改。
