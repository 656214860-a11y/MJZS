# R4140 结果：启动错误日志三处缺口修复（写失败仍弹窗、崩溃日志截断、根日志入导出白名单）
<!-- round-evidence: {"commit_base": "3383684c", "credential_hits": 0, "evidence_sha256": "906f939401bd606d", "exit": 0, "failed": 0, "passed": 67, "round": 4140, "tests": "run_selftests.py -k diagnostic_capture startup_selfcheck log_maintenance"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（AGENTS §3.2，只改根因所在模块）。任务卡 W7-FIX-AUD-ERRLOG（波次 W2），车道 `codex/fix-aud-errlog`，基准 `3383684c`。修审查 AUD-BOOT 的 D2／D3／D5 三处缺口：启动器 except 分支写日志无保护、运行期崩溃日志全量追加无截断、仓库根 `启动错误.log` 不在诊断导出白名单。
- （二）测试跑了吗、三个基线：跑了。定向命令 `run_selftests.py -k diagnostic_capture startup_selfcheck log_maintenance` 在只加测试、未改产品时 67 条用例 3 红（红项全部是本卡新增用例，原因与缺陷一致）；改产品后同一命令 67 条全绿；`smoke_test.py --architecture` 700 条全绿。默认冒烟与全量自测未跑（卡面验收只点名上述两条命令）。
- （三）欠账少了吗：少了三处真实缺陷（写失败连弹窗都没有、崩溃日志无界增长、根启动日志导不出）。没有新增欠账，未动任何门禁阈值、基线与登记表。

## 缺陷复现方式（先红后绿）

三个新用例，全部只用临时目录、不建真窗口（弹窗经 `ctypes.windll.user32` 替身捕获，与既有 `BrokenContractSubprocessTests` 同法）：

- D2：`tests/test_startup_selfcheck.py` `test_unwritable_startup_log_still_shows_dialog`——临时仓库根预建只读（`os.chmod 0o444`）的 `启动错误.log`，复制启动器进临时目录、contract 包损坏，子进程跑启动器；写日志抛 `PermissionError` 时弹窗替身必须仍收到 `MessageBoxW`。
- D3：`tests/test_diagnostic_capture.py` `test_record_crash_keeps_only_recent_tail`——`logs/启动错误.log` 预置 200KB 旧文加头部标记，连记两次崩溃，断言文件 <100KB、头部标记被裁、最新崩溃仍在。
- D5：`tests/test_diagnostic_capture.py` `test_export_includes_repo_root_startup_error_log`——临时「仓库根」放 `启动错误.log`，`PROGRAM` 指到临时 `程序/`，断言 `preview()` 含该文件且导出 ZIP 有 `logs/diagnostics/启动错误.log` 成员及其内容。

## 改前红的条数与原因（原文）

改前（只加测试）定向命令退出码 1，「共 67 条用例…2 个文件有红」，恰好 3 条新用例红：

- `test_export_includes_repo_root_startup_error_log`：`AssertionError: 'C:\\Users\\LAIBIAO\\AppData\\Local\\Temp\\drama-test-9tw5gva3\\tmpmbxkb3df\\启动错误.log' not found in ()`——白名单不含仓库根日志。
- `test_record_crash_keeps_only_recent_tail`：`AssertionError: 204904 not less than 102400`——两次崩溃后文件约 205KB，全量旧文无截断。
- `test_unwritable_startup_log_still_shows_dialog`：`AssertionError: 1 != 0`，stderr 末段显示 `启动漫剧制作助手.pyw line 146 log.write_text(...)` 抛 `PermissionError: [Errno 13] Permission denied` 后进程退出——写失败使弹窗分支不可达。

## 改了哪些文件（文件:行号）

- `启动漫剧制作助手.pyw:146-152`：写日志包进 `try/except OSError`；写失败时 `_note` 记「日志没能保存：<异常类型名>\n错误：<原异常最后一行≤200字>」（`_err` 在进入内层 except 前取好，保证是启动异常而非写异常）；写成功 `_note` 为「详情已保存到：<路径>」，弹窗首行「启动失败，」＋`_note`，成功路径文案与改前逐字相同；`MessageBoxW` 调用本身仍有既有 `except Exception:pass` 兜底。行尾保持纯 CRLF（152 个 CRLF、0 个孤立 LF，已用字节统计核实）。
- `程序/infra/diagnostic_capture.py:113`：`record_crash` docstring 注明历史只留最近约 64KB。
- `程序/infra/diagnostic_capture.py:117`：`previous` 改 `previous[-65536:]`，与启动器 `.pyw:143` 同口径（留旧文最后 65536 字符再追加新条目）。
- `程序/infra/diagnostic_capture.py:122-123`：`export_candidates` 白名单追加 `PROGRAM.parent / "启动错误.log"`（仓库根、启动器最外层 except 所写同名文件；`is_file()` 过滤照旧），只加白名单不搬位置。
- `程序/tests/test_diagnostic_capture.py:61-82`：新增上述 2 条用例。
- `程序/tests/test_startup_selfcheck.py:455-492`：新增上述 1 条用例。
- `程序/infra/log_maintenance.py`：未改。卡面修复口径为「只加入白名单，不搬位置」；该模块只管 `程序/logs` 与 `程序/维护记录` 两个目录（`log_maintenance.py:30-31`），仓库根单文件不在其设计内，且启动器写入时已自截断约 64KB（`.pyw:143`），体积有界。

## 命令与结果

以下命令都在车道 `程序` 目录下跑（git 类在车道根），解释器 `..\..\..\..\运行环境\Python\python.exe -B`，全部直接执行、无权限拒绝。

| 命令 | 结果 |
| --- | --- |
| `git -c core.quotepath=false status --porcelain`（开工） | 退出码 0，无输出 |
| `git log -1 --format=%h` | `3383684c`，退出码 0 |
| `git rev-parse --abbrev-ref HEAD` | `codex/fix-aud-errlog`，退出码 0 |
| `run_selftests.py -k diagnostic_capture startup_selfcheck log_maintenance`（只加测试、产品未改） | 退出码 1；67 条用例、3 红（原因见上） |
| 同上命令（改产品后） | 退出码 0；「共 67 条用例，1.4 秒；0 个文件有红」「ALL TESTS PASSED」 |
| `smoke_test.py --architecture` | 退出码 0；「Ran 700 tests in 262.992s」「OK」「✅ 架构治理测试：tests/architecture」 |
| `scripts\dev.py claim` | 领到轮次 4140 |
| `scripts\dev.py commit -m "R4140: FIX-AUD-ERRLOG 修复" --tests diagnostic_capture startup_selfcheck log_maintenance <文件>` | 见下方提交记录 |

改后定向命令输出尾部原文：

```
  test_startup_selfcheck#2      14 条     0.7 秒

共 67 条用例，1.4 秒；0 个文件有红
最慢 6 路工作单元：
  test_startup_selfcheck#2      0.7 秒 / 14 条
  test_startup_selfcheck#4      0.5 秒 / 15 条
  test_startup_selfcheck#1      0.3 秒 / 13 条
  test_diagnostic_capture       0.1 秒 / 7 条
  test_log_maintenance          0.1 秒 / 11 条
  test_startup_selfcheck#3      0.0 秒 / 7 条
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：1.9 秒

ALL TESTS PASSED
```

架构门禁输出尾部原文：

```
----------------------------------------------------------------------
Ran 700 tests in 262.992s

OK
✅ 架构治理测试：tests/architecture
```

## 如实说明

- 成功路径行为逐字不变：`.pyw` 写成功时弹窗仍是「启动失败，详情已保存到：<路径>」（`_note` 拼回原句）；`record_crash` 仍追加同一 `logs/启动错误.log`、同一 `[diagnostics]` 前缀与脱敏规则，只是旧文先裁到最近 64KB；导出白名单只多一个候选，`_safe_member` 把仓库根文件归入 `logs/diagnostics/启动错误.log`（`diagnostic_capture.py:155-156`），与程序侧 `logs/启动错误.log`（成员名 `logs/启动错误.log`）不冲突。
- 失败路径弹窗文案为本卡新增：「启动失败，日志没能保存：<异常类型名>\n错误：<原异常最后一行≤200字>」。与 `程序/tasks_round/L5入口层优化任务书.md` §4.4 E3 接口契约的失败分支口径同向（「日志没能保存：<异常类型名>」「错误：<原始异常的最后一行，最多 200 字>」）；E3 的错误码首行不属本卡，未做。
- `_err` 在进入写日志的内层 `except OSError` 之前取 `traceback.format_exc()`，保证取到的是启动异常末行而非写异常；格式化结果在两次 `format_exc()` 间一致（同一 except 上下文）。
- 只读场景用文件级 `os.chmod 0o444` 模拟（Windows 只读属性，`write_text` 抛 `PermissionError`，与目录只读／磁盘满同属 `OSError` 一类）；未在真只读卷上验证。
- `record_crash` 截断为字符口径 `[-65536:]`，与启动器 `[-65536:]` 一致；单条崩溃条目本身不设上限（与启动器对 traceback 的处理一致）。
- `PROGRAM.parent` 在生产即仓库根（`PROGRAM`＝`程序/`，`diagnostic_capture.py:29`）；测试经既有 `PROGRAM` patch 点控制，未新增模块级路径常量。

## 未覆盖项

- 未跑默认冒烟 `smoke_test.py`、未跑全量自测 `run_selftests.py --all --safe`（卡面验收只点名定向命令与架构门禁）。
- 仓库根 `启动错误.log` 未纳入 `log_maintenance` 的保留策略范围（见上「改了哪些文件」末条）：卡面修复口径只到导出白名单；是否要把它纳入日志保留属卡面未明确处，如实记录待总控判断。
- 真实 Win32 `MessageBoxW` 未弹出验证（子进程内以替身捕获参数，既有测试同法）；`.pyw` 行尾已字节级核实为纯 CRLF。
- 未 push、未 merge、未动主工作树与其他工作树。
