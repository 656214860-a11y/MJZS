# R2392 功能轮结果

## §7 三问

1. **本轮类型**：功能轮（§3.1）——模型目录条与阶段配置两级下拉联动（REQ-S01-80）。
2. **测试跑了吗、三个基线过了吗**：
   - 定向：`run_selftests.py -k test_skills test_idea_chat --serial` 313 条 0 红（含新增 `test_set_model_label_syncs_provider_and_model_by_display_name`、`test_select_idea_model_syncs_stage_model_picker`）。
   - 需求追踪门禁：`test_requirement_traceability` 5/5（REQ-S01-80 锚定通过）。
   - 受影响冒烟：`smoke_test.py --affected desktop_idea_bubbles stage_model_picker` 9 项通过。
   - 默认冒烟：`smoke_test.py`（经 `工作流任务/gui_hidden.py`）8/8 通过。
   - 全量：未跑（改动不命中 §5 强制全量条件：`desktop_idea_bubbles.py`/`stage_model_picker.py` 为 L4 展示层，非启动路径/Tk 控件生命周期/删除语义/层级登记表改动）。
3. **project_status.md 的欠账少了吗**：本轮属中断任务（11/6 遗留）收口，不涉及 project_status 既有欠账条目。

## 需求与设计（文档先行）

- 新增 `REQ-S01-80`：点模型目录条标签时，下方「阶段配置」供应商/模型两级下拉按显示名同步；点「全部」或找不到匹配不动原选择。见 `docs/stages/S01_剧本准备.md`。
- 新增 `DES-S01-80`：L4 `desktop_idea_bubbles.select_idea_model` 调 `_sync_stage_model_picker`；L4 `stage_model_picker.StageModelPicker.set_model_label` 按显示名在 `groups` 里匹配后 `_show`，只改界面、不写 `stage_config`。

## 实现

- `stage_model_picker.py`：新增 `set_model_label(label)`（按显示名同步两级下拉，命中返回 model id，否则 None 不动）；供应商下拉宽度 `xl→md`、模型下拉 `3xl→lg`（配合目录条紧凑布局）。
- `desktop_idea_bubbles.py`：`select_idea_model` 末尾调 `_sync_stage_model_picker(model)`，从 `stage_button.picker` 取 picker 并调 `set_model_label`；无 picker/无该方法时安全跳过。

## 测试资产

- `tests/test_skills.py`：`test_set_model_label_syncs_provider_and_model_by_display_name`（docstring 锚定 REQ-S01-80）——命中显示名同步并返回 model id、供应商落对应分组；找不到/空值返回 None 且不动。
- `tests/test_idea_chat.py`：`test_select_idea_model_syncs_stage_model_picker`（docstring 锚定 REQ-S01-80）——目录条切换后把显示名传给 picker；无 stage_button 时安全跳过。断言未弱化（均新增）。

## 提交

- 已提交：是（`codex/wip-R2392` 分支，提交信息 `R2392: 模型目录条联动阶段配置下拉（功能轮，REQ-S01-80）`）。
- commit hash：以 git log 为准（结果文件随提交 amend，避免 hash 自指）。
