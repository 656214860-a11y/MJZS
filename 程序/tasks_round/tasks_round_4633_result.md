# R4633 结果：C23 自检外层包装器统一 UTF-8/replace 防 GBK 编码错误
<!-- round-evidence: {"commit_base": "8991b93f4", "credential_hits": 0, "evidence_sha256": "f948d1c9c39b6f26", "exit": 0, "failed": 0, "passed": 89, "round": 4633, "tests": "run_selftests.py -k test_selftests"} -->

- 轮次类型：§3.2 修复轮（自检外层包装器控制台编码健壮性修复）
- 测试与三基线：
  - `run_selftests.py -k selftests`（UTF-8 环境）：89 条用例通过（2 文件 / 7 路工作单元，0 红、0 跳过，2.2 秒，退出码 0）。
  - `run_selftests.py -k selftests`（`PYTHONIOENCODING=gbk; PYTHONUTF8=0`）：89 条用例通过（0 红、0 跳过，2.4 秒，退出码 0）。
  - `smoke_test.py`（UTF-8 与 `PYTHONIOENCODING=gbk; PYTHONUTF8=0` 各跑一次）：均通过 9 项 / 失败 0 项（退出码 0）。
  - 关键架构门禁（`test_layers`、`test_coverage_baseline`、`test_module_size_ratchet`、`test_static_hygiene`、`test_structure`、`test_hidden_desktop_gate`、`test_silent_exception_ratchet`、`test_function_size_ratchet`、`test_constant_condition_ratchet`）：83 条全通过（55.2 秒，退出码 0）；终版定向架构复跑 47 条全通过（27.1 秒，`finding_count: 0`，退出码 0）。
  - 关联消费者测试（`test_smoke_affected_consumers`、`test_dev_entry`、`test_release_bindings`、`test_remote_post_receive_ci`）：40 条全通过（6.3 秒，退出码 0）。
  - 三基线通过，未修改、弱化或跳过任何既有测试断言。
- 欠账变化：未新增；消除 Windows 默认 GBK 终端下 `run_selftests.py` / `selftest_reporting.py` / `smoke_test.py` / `scripts/gui_hidden.py` / `scripts/local_ci.py` 打印 `✗`/`✅`/`❌` 等非 GBK 符号时的 `UnicodeEncodeError`。

## 改动
- `selftest_env.py`：新增 `configure_utf8_stdio`、`safe_write`、`safe_print`、`utf8_subprocess_env` 公共原语，统一将 `stdout`/`stderr` 切换为 UTF-8 + `errors='replace'`，并对无法 `reconfigure` 的严格 GBK 流在捕获 `UnicodeEncodeError` 时按目标流编码 `replace` 降级。
- `selftest_reporting.py`：`print_unit_result` 改走 `env.safe_print`，打印失败标记 `✗` 时不再抛 `UnicodeEncodeError`。
- `run_selftests.py`：模块入口及 `_run_hidden` / `main` 调用 `env.configure_utf8_stdio()`；`_run_hidden` 向隐藏桌面子进程注入 `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1` 并经 `env.safe_write` 回放日志；失败明细输出改走 `env.safe_print`。
- `smoke_test.py`：完善 `_configure_console_utf8` 并于 `main` / `_smoke_hidden` 入口再次调用；新增 `_safe_write` / `_safe_print` 用于 `check`、门禁日志回放与汇总的 `✅`/`❌` 输出；`check_the_gate` 与 `_smoke_hidden` 向子进程注入 `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1`。
- `scripts/gui_hidden.py`：入口调用 `_configure_stdio_utf8()`；在 `CreateProcessW` 期间临时注入 `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1` 并在 `finally` 还原，保证隐藏桌面子进程向日志文件写入 UTF-8。
- `scripts/local_ci.py`：入口调用 `_configure_stdio_utf8()`，子进程环境补充 `PYTHONUTF8=1`，控制台回显（含趋势报告输出）改走 `_safe_print`。
- `tests/test_selftests.py`（只追加，未改动既有测试）：新增 `Utf8ConsoleOutputTests`（6 条），先红后绿覆盖严格 GBK 流与 `PYTHONIOENCODING=gbk` 子进程场景。
