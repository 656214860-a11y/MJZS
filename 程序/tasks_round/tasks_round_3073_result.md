# R3073 结果 — 死代码清理轮（结构治理·按报告执行）收官批
<!-- round-evidence: {"commit_base": "daf90c2e", "credential_hits": 0, "evidence_sha256": "ad916cfe17053957", "exit": 0, "failed": 0, "passed": 27, "round": 3073, "tests": "run_selftests.py -k coverage_baseline layers"} -->

## 三问

1. **轮次类型**：§3.3 结构治理轮·子场景「按报告执行」。本批删 3 个模块（≤3 上限），任务书 A 节 21 个文件级死候选至此全部清理完毕。
2. **测试**：`smoke_test.py` 8/8 通过；`test_coverage_baseline`＋`test_layers` 复跑 11/11 通过。
3. **欠账**：同前轮，状态页仅 master 提交不变。

## 本批变更（任务书 A3·orchestrator 死门面第 3 批）

| 动作 | 对象 | 证据 |
|---|---|---|
| 删除 | `stage_write_preparation_service.py`、`white_model_persistence_controller.py`、`writing_preparation_ledger.py`（各 10 行别名壳） | 任务书 A3：引用全零；实体 LIVE（`stage_execution_service.py` 行 80/104、`white_model.py` 行 56/63/159、`writing_api.py` 行 21 均经包路径导入） |
| 同步 | `维护记录/覆盖率基线.json` | 移除 3 门面行，modules_total 531→528（covered=0） |
| 同步 | `runbook.md` §11 | 行覆盖 531→528/460→457 |

## 全部批次汇总（R3063–R3073，含并行车道跳号 3066/3068/3072）

- 删除文件 21 个：edit_habits_dialog、project_settings_dialog、orchestrator+顶层 stage_contract_report、orchestrator+顶层 storyboard_catalog、15 个 T10 死门面（script_brief/model_protocol/pet_settings_contract/shot_selection/store_program_locator/idea_script_heuristic/stage_animatic_gateways/stage_asset_gateways/stage_gate_gateways/stage_handoff_gateways/stage_previs_gateways/stage_publication/stage_write_preparation_service/white_model_persistence_controller/writing_preparation_ledger）。
- 改判 KEEP：previs_progress.py（Blender 宿主脚本，随批次复制执行）。
- 门禁同步：`_layers.py` 移除 4 个无实体登记名；`test_layers.py` 僵尸判定改 `entity_file` 解析（收紧）；`ui_edges_support.py`/`test_stage_layout.py` 同步删除死引用；`architecture.md`/`runbook.md`/三份覆盖率基线 JSON 同步。
- 测试契约变化（§2.4）：删除 `test_contract_rows_pair_stages_with_gates_and_docs` 用例与 `UiEdgeCase.setUp` 补丁桩——被测对象本身删除，断言未弱化。
- 遗留：任务书 B 节 117 个测试绑定门面（需产品决策）、E 节符号级/测试侧/UI 残留待续扫描。
