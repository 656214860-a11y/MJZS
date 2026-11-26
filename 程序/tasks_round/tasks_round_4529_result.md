# R4529 启动项目选择
<!-- round-evidence: {"commit_base": "25c0571d2", "credential_hits": 0, "evidence_sha256": "716d5f172efc1e1e", "exit": 0, "failed": 0, "passed": 255, "round": 4529, "tests": "run_selftests.py -k test_desktop_startup_perf test_launcher_imports test_startup_selfcheck test_app_metadata test_project_entry_boundary test_preview_app test_core"} -->

## 三问

启动显示应用内项目列表或恢复最后打开的项目。每次确认后的 7 日内自动续开，单项目直接进入。清除动画窗口、动画专用令牌与计时测试。

覆盖首次选择、单击行、零／单项目、六日／七日边界、最后制作项目、启动器无动画以及旧版项目找回行为。定向测试结果见机器凭据。

现有项目库升级后，多项目首次启动会建立每周确认记录。原动画曾被误删并恢复，本轮的删除是产品变更。
