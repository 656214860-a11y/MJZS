# R3309 结果文件
<!-- round-evidence: {"commit_base": "55254fb2", "credential_hits": 0, "evidence_sha256": "5587c069df90b586", "exit": 0, "failed": 0, "passed": 49, "round": 3309, "tests": "run_selftests.py -k startup_perf rename_reconcile bounded_growth"} -->

1. **本轮属于 §3 哪种类型**：§3.2 修复轮——轮 2（R2-g）遗留临时文件清扫线程在「打开项目」时立即起 os.walk，撞上规则 33「窗口出现到可交互之间零递归扫描」，全量自检 `test_startup_path_does_not_recurse_directories` 实测红（隐藏桌面日志 traceback 指向 `temporary_sweep.py:51→31`）。
2. **测试跑了吗、三个基线过了吗**：跑了。先红：`test_project_open_defers_stale_temporary_sweep` 新测试在改动前 `sweep.assert_not_called()` 失败（`schedule_stale_temporary_sweep` 被 load() 同步调用），`test_startup_path_does_not_recurse_directories` 同轮复现红。改后：`test_desktop_startup_perf` 15/15 绿、`test_project_rename_reconcile` 13/13 绿（断言按 §2.4 契约变更更新：延迟载入现有页面壳＋清扫两个 after 任务，断言收紧为「show_loaded_project 已排程且 show 未提前」）；默认冒烟 9/9；`--affected desktop temporary_sweep` 95 文件批 868 秒仅该契约断言一处红、修后复跑绿（生产码此后未再动）；`--gate` 增量串行 900 秒超时（GUI 令牌跨树排队所致，非用例红）。
3. **欠账少了吗**：少了——清扫仍在线程内跑、仍只删 24h 前 `agent.core.temporary_path` 形态文件；新增欠账：无。

## 改动

- `infra/temporary_sweep.py`：新增 `TEMP_SWEEP_START_DELAY_MS = 3000`（与 `ui.desktop_account_page.RENEW_DELAY_MS` 同档；实测启动窗口约 1.5 秒，3 秒延迟确定性避开）。
- `desktop.py` `load()`：清扫由「立即起线程」改为 `self.win.after(3000, start_stale_temporary_sweep)`；回调内守卫 `shutting_down` 与 `self.root==sweep_target`（快速切项目只清扫当前项目，语义与 `_complete_project_recovery` 一致）。
- `tests/test_desktop_startup_perf.py`：新增 `test_project_open_defers_stale_temporary_sweep`——录制 `window.after` 回调，断言 load() 不同步触发清扫、延迟回调按名触发且参数为项目根。
- `tests/test_project_rename_reconcile.py`：deferred 分支断言由 `after.assert_called_once()` 更新为「`show_loaded_project` 在已排程回调名中」——契约变更＝延迟载入多一个清扫延迟任务，页面壳延后语义不变。

## 验证证据

- 先红输出（改动前）：`sweep.assert_not_called()` → `Called 1 times. call(WindowsPath('...desktop-sweep-defer-...'))`；`test_startup_path_does_not_recurse_directories` → `AssertionError: 1 != 0`（walk 栈含 temporary_sweep.py:51/31）。
- 改后：`-k startup_perf` 15/15 绿（含原 flaky 项连续通过）；`-k project_rename_reconcile` 13/13 绿。
- 三个基线：默认冒烟 9/9 ✅；架构门禁未单独跑（合入轮出口 CI 含架构门禁）；全量凭据：master 全量在排队/后台补跑，`full-safe-receipts.json` 为唯一权威。

## 备注

- 本轮源于 master 全量自检（HEAD=72caf20b）暴露的真实缺陷；同批还暴露轮 5 传输收敛的测试接缝不兼容（model_pool_redirects 等）与 subprocess cp936 解码崩溃（merge_queue/测试内 text=True），另立轮次处理。
