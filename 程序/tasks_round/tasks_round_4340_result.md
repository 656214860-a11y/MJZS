# R4340 结果：补齐 AppLogInstallFailureTests 子进程桩，恢复 install_calls==2 校验（FIX-MASTER-APPLOG-TEST）
<!-- round-evidence: {"commit_base": "3eacf9cc5", "credential_hits": 0, "evidence_sha256": "84fa2064913af4ae", "exit": 0, "failed": 0, "passed": 60, "round": 4340, "tests": "run_selftests.py -k startup_selfcheck"} -->

## 三问
- 轮次类型：修复轮（§3.2）。卡 FIX-MASTER-APPLOG-TEST：REL-14（R4284/R4293）给 `启动漫剧制作助手.pyw:45` 新增 `import desktop_launcher`，主干全量红灯 test_startup_selfcheck 两条。
- 测试和三个基线：定向命令 `run_selftests.py -k startup_selfcheck` 改前 2 红、改后 60 条全绿（退出码 0）；`smoke_test.py --architecture` 702 条全过（退出码 0）；默认冒烟 8/8 本轮未运行（卡面验收未列）。
- 欠账：主干复验红灯的回归已闭环，欠账减少，未新增欠账。

## 缺陷复现
- 复现命令（程序 目录下原样执行）：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k startup_selfcheck`
- 改前红 2 条，症状与卡面一致（退出码 1）：`AppLogInstallFailureTests.test_install_false_records_degraded_and_status_warning` 与 `test_install_retry_success_stays_silent` 均报 `AssertionError: 1 != 2`（`results['install_calls']` 实测 1，断言期望 2）。
- 根因（子进程 `启动错误.log` 实捕）：`启动漫剧制作助手.pyw:45` 的 `import desktop_launcher` 抛 `ModuleNotFoundError: No module named 'desktop_launcher'`。桩子进程 sys.path 只有临时根与空的临时 `程序/`，真实 `程序/desktop_launcher.py` 不在路径上——卡面所述「`from ui_widgets import notify` 抛 ImportError」是次级缺口：desktop_launcher 本体先不可达；即便可达，`import infra.hash_backend`（desktop_launcher.py:23）与 `from ui_widgets import notify`（:26）在桩中也都缺位，会依次暴露。异常被 .pyw 外层 except 吞掉（写启动错误.log＋桩 MessageBox），执行未达 line 75 的第二次 `app_logging.install(window)`，故 install_calls 停在 1。

## 改动（仅 tests/test_startup_selfcheck.py 的 `_run_launcher` 替身串内）
- `tests/test_startup_selfcheck.py:692-693`：`infra_pkg.hash_backend = hash_backend`＋`sys.modules['infra.hash_backend'] = hash_backend`——`import infra.hash_backend` 与模块级 `hash_backend.install()`（desktop_launcher.py:23-24）在桩子进程内可解析（复用已带 `install` 的顶层桩模块）。
- `tests/test_startup_selfcheck.py:730`：`ui_widgets.notify = lambda *a, **k: None`——`from ui_widgets import notify`（desktop_launcher.py:26）可解析；notify 仅在 `launch()` 的 report_callback_exception 路径被调，本子进程不触达。
- `tests/test_startup_selfcheck.py:792-794`：`runpy.run_path` 之前 `_load_real('desktop_launcher', program_dir + '/desktop_launcher.py')`——沿用本替身串对 contract.diagnostics／ui_status_bus 的既有「真实源码加载」手法，使 .pyw:45 的 `import desktop_launcher` 命中 sys.modules；不改 sys.path，无遮蔽风险。
- 无副作用核对：`enable_dpi_awareness()` 在 ctypes.windll SimpleNamespace 桩下逐级 AttributeError→`app_logging.swallowed()`，正常返回 None；`min_os_items()` 本机 `sys.getwindowsversion()` ≥ (10,17763) 返回 `[]`，不向 `selfcheck_records` 写入 `'os-below-minimum'`（改后 F,T 用例的 `assertNotIn`/`assertFalse` 全过佐证无污染）。
- 断言未动：既有断言逐字保留；产品代码（.pyw、desktop_launcher.py）未改。

## 核对（命令输出尾部原文）
- `run_selftests.py -k startup_selfcheck`，退出码 0：
  ```
  共 60 条用例，1.5 秒；0 个文件有红
  实际跳过 0 条用例：本机没有任何登记位被跳过
  增量台账已刷新：…\.git\selftest-incremental.json
  最近 5 轮自检中位基线：2.5 秒

  ALL TESTS PASSED
  ```
- `smoke_test.py --architecture`，退出码 0：
  ```
  ----------------------------------------------------------------------
  Ran 702 tests in 249.249s

  OK
  ✅ 架构治理测试：tests/architecture
  ```

## 未验证
- 默认冒烟 8/8 未运行；全量 `run_selftests.py --all --safe` 未运行（卡面验收未列，定向与架构门禁已覆盖改动面）。
- `min_os_items()` 在低于 Windows 10 1809 机器上返回 FATAL 的分支未实机验证（本机构建号达标返回 []）。

## 卡外发现（只记录不修）
- 卡面「已核实事实」所述失败原因为 `from ui_widgets import notify` 缺桩；实测首个 ImportError 是 `desktop_launcher` 本体 `ModuleNotFoundError`（桩 sys.path 不含真实 程序 目录），`infra.hash_backend` 桩亦缺——三处均需补齐才恢复 install_calls==2，已在本轮替身内一并修复。
- `desktop_launcher.min_os_items()` 在低版本 Windows 上会给 `selfcheck_items` 追加 FATAL 并使子进程 `sys.exit(1)`：若本类测试在旧系统运行会另路失败，属测试环境前提，非本轮缺陷。

## 提交
- 经 `scripts\dev.py commit --tests startup_selfcheck` 提交；提交哈希见 git log（本文件写入于提交前）。
