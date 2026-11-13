# R2396 结果

- 轮次类型：结构治理轮·执行（来源：本会话架构诊断报告「优化清单」P0-1 第 2 批）。
- 范围：仅改 1 个模块 `asset_batch.py`，两处 import 卫生收口：
  1. 删除第 25 行与第 8 行完全重复的 `from stage_execution_service import remove_asset_batch_model as remove_model, save_asset_batch_settings as save_settings`（同符号重复引入的冗余依赖声明）。
  2. 把文件中部（原第 32 行）的 `from asset_batch_controller import AssetBatchController, WORKFLOW_MODEL` 上提到顶部 import 块（第 25 行）。
- 依据：`asset_batch_controller` 经 AST 实测只依赖 `asset_batch_selection_service`，不回引 `asset_batch`，上提无循环；`import asset_batch` 实测成功。
- 说明：`asset_batch.py` 内其余 5 处函数体内 `from stage_execution_service import ...`（release_uncertain_asset_batch／asset_batch_gateway／plan_unattended_assets／asset_plan_gateway／sync_asset_plan／require_formal_asset_generation）为有意打破循环的延迟 import，留待后续按注入边界逐批收敛，本轮不触碰。

## 验证

- 默认冒烟 `smoke_test.py`：**8/8 通过**。
- 循环 import 门禁 `test_no_circular_import`：**PASS**。
- 定向 `run_selftests.py -k asset_batch`：**29 条用例、0 个文件有红、ALL TESTS PASSED**（覆盖 test_asset_batch_controller／test_asset_batch_selection_service／test_asset_batch_settings_*／architecture.test_asset_batch_*_boundary 等）。
- `import asset_batch`：**成功**。
- 全量 `--all --safe`：未跑（单模块 import 位置移动 + 删重复，不命中 §5 强制全量条件）。

## 三个问题

1. 本轮类型：结构治理轮·执行（§3.3）。
2. 测试跑了吗、三个基线过了吗：默认冒烟 8/8 过、循环 import 门禁过、定向 29 条过；全量未跑（不命中触发条件），如实标注。
3. `project_status.md` 欠账少了吗：否——结构治理，未触碰欠账条目。
