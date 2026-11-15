# R2879 修复轮结果
<!-- round-evidence: {"commit_base": "f4afbe32", "credential_hits": 0, "evidence_sha256": "56144db7d797c77c", "exit": 0, "failed": 0, "passed": 69, "round": 2879, "tests": "run_selftests.py -k selftests selftest_incremental"} -->

1. 轮次类型：修复轮（§3.2）。`run_selftests.py --all --safe` 自 R2853 合入后连续 8+ 次全红在同一对新用例：`test_script_find_bar`、`test_script_zoom`（定向与小批量复跑均绿，全量必红）。
2. 测试：跑了。根因修复后 `--layer gui-short --safe --all`（131 文件 / 205 单元，含两目标文件）中 `test_script_find_bar`、`test_script_zoom` 全绿；`run_selftests.py -k selftests selftest_incremental` 69 条全绿（含同步后的 mock 契约断言）。三个基线：默认冒烟未单独重跑；架构门禁未跑（只动自检调度与其测试）；全量安全待合并轮后由后台凭据流程验证。
3. 欠账：project_status.md 欠账减少——消除全量回归唯一确定性红灯对，解开后续合并轮的全量凭据门禁。

## 根因

`selftest_scheduling.run_units` 用 `ProcessPoolExecutor` 复用 worker 进程，一个 worker 顺序跑多个工作单元。隐藏桌面上**同一进程的第二个及以后 `tk.Tk()` 无法投递 `event_generate` 合成按键**（tests/test_script_zoom.py 卷首已记载该平台怪癖）。GUI 单元经 `prioritize_gui_units` 后由少量 worker 池消化，凡落在已跑过 Tk 单元的 worker 上的按键断言用例必然拿不到按键投递——`_press_until` 连发 15 次仍不生效、`bar.visible` 不关闭。用例定向/小批量跑时各占新 worker 或本身是进程内首个 Tk，故恒绿；全量 137 个 GUI 单元下必红。该对用例由 R2853 引入，合入后从未有过全绿全量。

## 修法

`run_units(todo, jobs, fresh_children=False)` 新增参数，`fresh_children=True` 时 `ProcessPoolExecutor(max_tasks_per_child=1)` 让每个工作单元独占新进程，其 `tk.Tk()` 恒为进程内第一个，按键投递恢复。两处 GUI 调用点（`--safe` 受控池与 `--all` 非 safe 池）传 `fresh_children=True`；非 GUI 单元不受影响仍复用 worker。`test_selftests_gui_token` 三处 `run_units` mock 签名同步，并新增断言钉住「GUI 单元必须 fresh_children=True、非 GUI 不传」的契约。

## 提交

- commit：见 evidence/R2879.json。
