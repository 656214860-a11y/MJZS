# R4532 项目导航架构门禁
<!-- round-evidence: {"commit_base": "3696f221b", "credential_hits": 0, "evidence_sha256": "1db6bac7240b7764", "exit": 0, "failed": 0, "passed": 29, "round": 4532, "tests": "run_selftests.py -k test_data_table_boundary test_source_text_contracts"} -->

## 三问

导航门禁按具体入口约束项目选择树，覆盖主窗口启动列表、手动项目管理窗和项目首页。其他制作表格继续由公共组件管理。

运行针对性的 DataTable 边界测试复核实际入口。

本轮只调整架构断言，界面行为见 R4529 与 R4530。
