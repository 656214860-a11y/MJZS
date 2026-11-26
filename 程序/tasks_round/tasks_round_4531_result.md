# R4531 启动选择合入检查
<!-- round-evidence: {"commit_base": "c844a3278", "credential_hits": 0, "evidence_sha256": "1a2d636eeda54e6c", "exit": 0, "failed": 0, "passed": 25, "round": 4531, "tests": "run_selftests.py -k test_desktop_startup_perf test_project_entry_boundary test_function_size_ratchet"} -->

## 三问

将原有手动项目管理窗保留在独立方法，启动分流与手动管理的实现边界更清晰，恢复函数长度门禁。

验证真实窗口启动、项目入口白名单和函数长度。

无项目数据迁移。任务功能及实测范围见 R4529、R4530。
