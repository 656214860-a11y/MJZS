# R4431 FIX-SELFCHECK-LAUNCHER-STUB：同步 selfcheck 桩 ui_widgets 导入（修复轮）
<!-- round-evidence: {"commit_base": "7cd480e35", "credential_hits": 0, "evidence_sha256": "e31a8bb875c78ebb", "exit": 0, "failed": 0, "passed": 67, "round": 4431, "tests": "run_selftests.py -k startup_selfcheck"} -->

## 来源
任务卡 FIX-SELFCHECK-LAUNCHER-STUB（W2）：UX-L5-DIALOGS（R4419 commit 13632998e / R4427 合入 master）在 `desktop_launcher.py:26-27` 顶层导入新增 `BaseDialog`、`DescriptionBlock`、`PrimaryButton`、`SecondaryButton`、`DIALOG_ACTION_GAP`、`SPACING`，而 `tests/test_startup_selfcheck.py` 的 `AppLogInstallFailureTests._run_launcher` 子进程桩只挂了 `Splash` 与 `notify`，导致 `_load_real('desktop_launcher', ...)` 抛 `ImportError: cannot import name 'BaseDialog' from 'ui_widgets'`，EC-5 验证门禁 2 条红。

## 基线
分支 `codex/fix-selfcheck-launcher-stub`，基线 `7cd480e35`，开工时 `git status --porcelain` 无输出。

## 轮次类型／三套基线／债务
修复轮：测试桩与生产代码导入面不同步，属测试契约跟随（§2.4）。只补桩属性，断言一行未动，生产代码零改动。无新增债务。

## 改前输出（先跑定向留红）
`run_selftests.py -k startup_selfcheck`：67 条用例，1 个文件有红，退出码 1。
- `test_install_false_records_degraded_and_status_warning`：`AssertionError: 1 != 0`，子进程 wrap.py:168 `_load_real('desktop_launcher', ...)` → `ImportError: cannot import name 'BaseDialog' from 'ui_widgets' (unknown location)`（desktop_launcher.py:26）。
- `test_install_retry_success_stays_silent`：同上 ImportError。

## 改动
- `tests/test_startup_selfcheck.py`（约 802-810 行）：fake `ui_widgets` 桩补齐 `BaseDialog`、`DescriptionBlock`、`PrimaryButton`、`SecondaryButton`（共用 `_DialogStub` 空类）、`DIALOG_ACTION_GAP = 8`、`SPACING = {'none': 0}`，注释注明对齐 R4427（UX-L5-DIALOGS）顶层导入。断言全部原样保留。

## 测试
- `run_selftests.py -k startup_selfcheck`：67 条用例，0 红，`ALL TESTS PASSED`，退出码 0。
- `smoke_test.py --architecture`：708 条用例全 ok，退出码 0。
- 未运行默认冒烟与全量（卡面未列）。

## 回滚
`git revert` 本轮提交。

## 下一步
无；EC-5 验证门禁阻塞解除。
