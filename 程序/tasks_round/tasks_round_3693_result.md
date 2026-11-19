# R3693 结果报告
<!-- round-evidence: {"commit_base": "b756121c", "credential_hits": 0, "evidence_sha256": "d3d23a5a76ce7b9a", "exit": 0, "failed": 0, "passed": 18, "round": 3693, "tests": "run_selftests.py -k architecture.test_layer_relations architecture.test_platform_process_boundary architecture.test_branch_coverage_floor"} -->

- 轮次类型：修复轮（R3690 合并轮出口 CI 补齐）。
- 测试：跑了；R3690 主干出口 CI 架构门禁 6 红对应修复本树复验全绿（18 条 layers/relations/process_boundary/branch_floor）；默认冒烟 9/9（随 R3691 同窗口）。主干余红 `test_site_packages_whitelist`＝邻车道当日安装未登记 pydantic 五包，环境性零因果。
- 欠账：少了——R3690 提交窗口漏 add 的整合修复经本分支入库回合主干。

## 内容

- `_layers.py` 补登记 7 条主干同层边（account_store→session_integrity、error_codes→diagnostics、model_pool→config_patch、session_integrity→core/model_secrets/publication、storage_maintenance→temporary_sweep）。
- `test_platform_process_boundary.py` 豁免锚点 storage_maintenance:54→58。
- 层间合规清单 LR-01→17、LR-04→3、LR-07→185、LR-09/LR-10→58（合并后实测）。
- 分支覆盖率基线实体集 100 模块、决策点按当前实体重计 2959；下限 100 键对齐（含 budget.py 0.0）。
