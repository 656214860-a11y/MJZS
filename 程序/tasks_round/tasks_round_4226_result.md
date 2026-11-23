# R4226 FIX-AUD-APPLOG-VISIBLE：app_logging.install 返回 False 时启动器静默（修复轮）
<!-- round-evidence: {"commit_base": "00c47992", "credential_hits": 0, "evidence_sha256": "1e485ef65e3776a2", "exit": 0, "failed": 0, "passed": 74, "round": 4226, "tests": "run_selftests.py -k app_logging startup_selfcheck"} -->

## 三问
- 轮次类型：§3.2 修复轮（审查 AUD-BOOT D6，验收窗口核 `.pyw` install 返回值无人检查）。
- 测试跑了吗、三个基线过了吗：定向 `run_selftests.py -k app_logging startup_selfcheck` 改前 2 红、改后 74 条全绿；`smoke_test.py --architecture` 700 条全绿。默认冒烟基线未跑（卡面只列两条验收命令）。
- 欠账少了吗：无新增欠账；本轮闭环一条启动可观测性缺陷。

## 缺陷复现方式
`app_logging.install()` 在 logs 目录不可写／`app.log` 打不开时返回 `False`（`infra/app_logging.py` 原 404–406 行 `except Exception: return False`），且不留失败原因；启动器 `启动漫剧制作助手.pyw` 原 66 行 `app_logging.install(window)` 丢弃返回值。返回 False 时文件 handler、`sys.excepthook`、`threading.excepthook`、faulthandler 全部未安装（均在 try 之后），应用无日志无崩溃钩子地运行且无任何用户可见提示。

复现测试（先写、先跑、见红）：
- `tests/test_app_logging.py::AppLoggingTests::test_failed_install_returns_false_and_keeps_reason`：把 `LOGS` 指到一个普通文件使 `mkdir` 必败，断言 `install()` 返回 False 且留下 `_install_error`，恢复后重装成功并清空原因。
- `tests/test_startup_selfcheck.py::AppLogInstallFailureTests`（新增，子进程跑真实 `.pyw`，tkinter/desktop/诊断模块全桩、不建真窗口）：
  - `test_install_false_records_degraded_and_status_warning`：两次 install 均 False → 断言降级诊断 `app-log-unavailable` 落账（`record_selfcheck`）、挂上 `window._selfcheck_degraded`、真实 `ui_status_bus.publish_startup_warnings` 产出含该 code 的【警告】。
  - `test_install_retry_success_stays_silent`：首调 False、建窗后重试 True → 断言不记降级、不误报（防回归守卫）。

## 改前红（未改产品时定向命令输出，退出码 1）
`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k app_logging startup_selfcheck`，共 74 条用例、2 条红：

```
===== test_failed_install_returns_false_and_keeps_reason (test_app_logging.AppLoggingTests.test_failed_install_returns_false_and_keeps_reason) =====
AttributeError: module 'infra.app_logging' has no attribute '_install_error'

===== test_install_false_records_degraded_and_status_warning (test_startup_selfcheck.AppLogInstallFailureTests.test_install_false_records_degraded_and_status_warning) =====
AssertionError: 'app-log-unavailable' not found in []
```

红的原因与缺陷一致：启动器不检查 install 返回值，降级诊断无从产生（`recorded` 为空）；`_install_error` 为本修复新增的失败原因留存面。F,T 防误报用例改前即绿（属预期守卫）。

## 改动（最小面）
- `infra/app_logging.py`：新增模块级 `_install_error`（36 行）；`install()` 记录/清除失败异常（376 行 global、404–407 行 except 记因、成功置 None）；docstring 补一句（374 行）。公开签名不变。
- `启动漫剧制作助手.pyw`（CRLF 行尾已核实保持纯 CRLF）：46 行诊断导入加 `Diagnostic, StartupPhase`；66–78 行把 `app_logging.install(window)` 改为返回值检查——False 时构造 `Diagnostic(severity=DEGRADED, scope='resource', code='app-log-unavailable', message=…, remedy=…)`，脱敏后的失败原因拼进 message，经 `app_logging.redact`；append 进 `degraded_items`（与 `window._selfcheck_degraded` 同一列表对象，桌面初始化时由 `publish_startup_warnings` 播报【警告】）；`diagnostic_capture.record_selfcheck(selfcheck_items+[item])` 落进诊断状态随导出带走；整段 try/except 失败走 `app_logging.swallowed()`，绝不挡启动。
- 测试：`tests/test_app_logging.py` 66–76 行新增 1 条；`tests/test_startup_selfcheck.py` 613–828 行新增 `AppLogInstallFailureTests` 2 条。既有断言未动。

## 改后验证（命令正文逐字，工作目录 `程序`，PowerShell 执行）
1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k app_logging startup_selfcheck` → 退出码 0，输出尾部：
```
共 74 条用例，1.5 秒；0 个文件有红
ALL TESTS PASSED
```
2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → 退出码 0，输出尾部：
```
Ran 700 tests in 312.321s
OK
✅ 架构治理测试：tests/architecture
```
3. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` → 退出码 0，轮次号 4226。

## 提交
- `git diff --numstat` 由验收角色复跑（本执行者不运行 git status/diff）。
- 提交命令：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4226: FIX-AUD-APPLOG-VISIBLE 修复" infra/app_logging.py tests/test_app_logging.py tests/test_startup_selfcheck.py tasks_round/tasks_round_4226_result.md 启动漫剧制作助手.pyw`（注：`.pyw` 位于仓库根，提交参数以 dev.py 实际接受的相对路径为准，见完成报告）。

## 没有验证的地方
- 未在真实 Windows 会话里启动 `.pyw` 观察状态栏像素级表现；状态栏可见性由测试用真实 `ui_status_bus.publish_startup_warnings` + 桩 Desktop 断言消息文本，桌面真实渲染路径（desktop.py:361 一带）未改动、未重测。
- `install` 首调（`.pyw`:16，建窗前）返回值仍不检查：若首调失败而二调成功则不告警（此时日志实际已生效，语义正确）；两调同指 `PROGRAM/logs`，失败面一致。
- 默认冒烟 `smoke_test.py`、全量 `run_selftests.py --all --safe` 未跑（卡面未列）。

## 卡外发现（只记录）
- `.pyw`:16 首次 `install` 早于 `os.chdir(program)`，但 `LOGS` 由模块 `__file__` 定位为绝对路径，两次调用目标一致，无实际分歧。
- `desktop_launcher.py` 另有一套启动适配，未在本卡范围，未动。

## 被拒绝的命令
- `Get-ChildItem tasks_round -Filter ... | Sort-Object ...`（PowerShell 列目录）：被拒一次，改用文件匹配工具完成同一目的，未重试。
