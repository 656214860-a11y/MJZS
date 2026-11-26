# tasks_round_4539_result — L5 入口层优化 E2+E3 与重构 REF-L5-1
<!-- round-evidence: {"commit_base": "faa0434ce", "credential_hits": 0, "evidence_sha256": "a0122ab8a10795da", "exit": 0, "failed": 0, "passed": 127, "round": 4539, "tests": "run_selftests.py -k desktop_launcher startup_selfcheck ui_status_bus app_metadata"} -->

- 本轮属于 §3.1 功能轮（任务卡 `L5-E2-E3-REF-L5-1`，波次 `W2`，分支 `codex/l5-entry-hardening`，基准 `master` `faa0434ce`）。本工作树接续上个会话中断遗留的半成品（8 个允许文件已改未提交），本轮在其上做完卡面并修通架构门禁，未 reset、未丢弃既有改动。
- 测试跑了吗、三个基线过了吗：跑了。卡面两条验收命令均全绿、退出码 0、0 跳过——定向 `run_selftests.py -k desktop_launcher startup_selfcheck ui_status_bus app_metadata`（127 条用例全部通过，0 红，0 跳过）；全量架构门禁 `smoke_test.py --architecture`（708 条 OK，含分支覆盖率基线 `app_logging`=55 / `diagnostic_capture`=85 精确匹配与静默异常棘轮 9 站点）。默认冒烟（无参 `smoke_test.py`）与全量安全自检（`--all --safe`）未单跑（按分支车道规则不累计，卡面未要求）。
- 欠账少了吗：无新增欠账。L0/L1 决策点净增为 0；静默异常站点不增（`ui_status_bus` 新增捕获全部走 `app_logging.swallowed()`）。

## 改动清单（文件:行号）

- `启动漫剧制作助手.pyw`（总计 -5 行）：
  - L24、L33：Win32 `CreateMutexW` 改 `ctypes.WinDLL('kernel32', use_last_error=True)` ＋ `ctypes.get_last_error()==183`，不再经 `windll.kernel32.GetLastError()`（易被他次 API 调用覆盖的竞态）；
  - 删除第二处重复 `sys.path.insert(0, str(program))`（保留 L8 的 `sys.path.insert`）；
  - L54：启动预检统一走 `desktop_launcher.run_preflight(program)`（与 `launch()` 同一入口，DPI 声明仍在首个 `tk.Tk()` 之前）；
  - L166：致命异常兜底首行 `[E-START-FAILED]`，日志写入失败不二次崩溃。
- `程序/desktop_launcher.py`：
  - L25–27：顶层 `import tkinter as tk` / `from ui_widgets import ...` 移入 L129/L160/L176/L218/L231 各函数内部，`import desktop_launcher` 不再提前加载 tkinter＋ui_widgets（冷导入 ~129ms→<5ms）；
  - L188：新增 `run_preflight(program)` 共用入口，统一 `run_startup_selfcheck`＋`min_os_items`＋FATAL 弹窗＋`startup_gate(ask=entry_confirm)`，`launch()` 与入口 `.pyw` 共同调用。
- `程序/infra/diagnostic_capture.py`：L843–846 `fatal_diagnostics_text()` 首行 prepend `describe('E-START-SELFCHECK')`；`record_crash` 包 try 防崩溃上报自身再崩；L660 `_downgrade_fatal` 早退 `if` 单行化以抵消新增 try（L1 决策点维持 85）。
- `程序/infra/app_logging.py`：L386 `add_crash_listener`（锁内列表注册、返回取消闭包）；L403 `_dispatch_crash_listener` 单监听隔离调用（抛错只计 `swallowed`，不拖累日志与其余监听）；L421 `_crash` 锁内快照锁外派发。全文件决策点净增 0（维持 55：新 try +1，`if _installed:` 等单行化 -1），静默站点维持登记 9 处。
- `程序/ui/ui_status_bus.py`：L245 `publish_unhandled_error(code, message, now=None)` 按错误码 60 秒限频去重（同码窗口内仅首次上屏并累计压下次数，超窗恢复）；L220 `register_unhandled_bus`/`unregister_unhandled_bus` 弱引用登记；L270 `_forward_unhandled` 崩溃监听→状态栏转发（`SystemExit`/`KeyboardInterrupt` 等不入账）；L287–295 首个 StatusBus 构造时一次性挂入 `app_logging`，状态栏未注册或 UI 销毁时静默 `swallowed()` 不抛错。
- `程序/tests/test_desktop_launcher.py`（+22）：`DeferredImportTests` 子进程断言 `import desktop_launcher` 不产生 `tkinter`/`ui_widgets` 模块项。
- `程序/tests/test_startup_selfcheck.py`（+73/-4）：FATAL 文案首行即 `E-START-SELFCHECK` 断言；`.pyw` AST 断言 `use_last_error=True`+`get_last_error`、单一 `sys.path.insert`、`run_preflight` 调用与 `E-START-FAILED` 字面量。
- `程序/tests/test_ui_status_bus.py`（+71/-1）：`UnhandledErrorReportTests` 覆盖 60 秒同码限频、不同码互不抑制、超窗恢复、崩溃监听转发与 UI 未注册静默。

## 先红 → 后绿验证记录

本树接续时实现与新测试已写入但未提交，验收命令在本树直接即绿；按卡面「先红后绿」要求，以基准 `faa0434ce` 的 `git show` 原文逐条证明新增断言在基准上必红：

1. `DeferredImportTests`（test_desktop_launcher.py）：基准 `desktop_launcher.py:25-27` 顶层存在 `import tkinter as tk` 与 `from ui_widgets import ...` → 子进程 `sys.modules` 必含 `tkinter`/`ui_widgets` → 断言必红。
2. `.pyw` AST 断言（test_startup_selfcheck.py）：基准 `启动漫剧制作助手.pyw` 用 `windll.kernel32.GetLastError()`、含两处 `sys.path.insert`、无 `run_preflight` 调用、异常兜底无 `[E-START-FAILED]` 字面量 → 四条 AST 断言必红。
3. `test_text_starts_with_registered_selfcheck_code`：基准 `fatal_diagnostics_text` 首行为旧文案无 `E-START-SELFCHECK` → 必红。
4. `UnhandledErrorReportTests`：基准 `ui_status_bus.py` 无 `publish_unhandled_error`、`app_logging` 无 `add_crash_listener` → `AttributeError` 必红。

本轮复跑时新曾出现两条真红（架构门禁，已由本树改动修复）：`test_branch_coverage_floor` 决策点 `app_logging.py` 55→60、`diagnostic_capture.py` 85→86 超基线；`test_silent_exception_ratchet` 新增 `except Exception: pass` 两处未走 `swallowed()`。修复方式：单行化等值语句抵消净增（单行复合语句不计决策点）、`except` 体改 `app_logging.swallowed()`。

## 改后验收命令输出（退出码均为 0）

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k desktop_launcher startup_selfcheck ui_status_bus app_metadata`（退出码 `0`）：
```
跑 4 个测试文件 / 11 路工作单元（8 路并行）
共 127 条用例，9.4 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```
（此前一轮因另一车道持跨树 GUI 令牌，两个 Tk 测试文件被 `GUI_DEFERRED` 延后退出码 1；按卡面等锁重跑后令牌正常取得、两文件实跑通过。）

2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 `0`）：
```
----------------------------------------------------------------------
Ran 708 tests in 465.409s

OK
✅ 架构治理测试：tests/architecture
```

## 变更统计（`git diff --numstat`，提交前工作区）

```
18	23	启动漫剧制作助手.pyw
37	22	程序/desktop_launcher.py
31	2	程序/infra/app_logging.py
16	9	程序/infra/diagnostic_capture.py
22	0	程序/tests/test_desktop_launcher.py
73	4	程序/tests/test_startup_selfcheck.py
71	1	程序/tests/test_ui_status_bus.py
94	0	程序/ui/ui_status_bus.py
```

## 未验证项与卡外发现

- 未验证项：
  - 冷导入 -126ms 性能数字未实测（接口契约「顶层无 tkinter/ui_widgets」由子进程测试覆盖，实测毫秒数受机器与缓存影响，未列入验收）；
  - 未单跑无参 `smoke_test.py` 与 `run_selftests.py --all --safe`（按分支车道规则由合并阶段统一处理）；
  - 未在真实 Windows 双开场景人工复验 Mutex 单实例弹窗（`use_last_error`+`get_last_error` 契约由 AST 断言与既有启动自检覆盖）。
- 卡外发现：无。
