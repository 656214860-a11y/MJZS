# R2411 结果：统一内容框列表自适应高度，消除模型管理等处的空白（功能轮）

## 三个问题（§7.3）

1. **本轮类型**：功能轮（L4 UI 布局一致性优化）。只改 UI 显示逻辑，不改分层、契约、权威源或阶段行为，故不触发 §2.7 文档变更。
2. **测试**：默认冒烟 8/8 通过；定向 `run_selftests.py -k test_ui_batch7_settings_models test_version_pin test_ui_batch4_desktop_project_pages test_skills` 共 177 条 0 红；模块行数门禁 `test_module_size_ratchet` 2/2。架构门禁未整跑（功能轮不要求），唯一与我相关的大小门禁已单独复验绿；`--architecture` 其余红项均为 worktree 环境缺失 gitignored 文件所致，非本轮引入（见下）。
3. **欠账**：`project_status.md` 欠账未减少（本轮不涉及、未改状态页，按分支流程由合入 master 后补记）。

## 用户要求

确认应用内所有内容框／列表框的显示逻辑是否一致；模型管理的模型列表下方总出现大量空白；参考企业级应用，是否应让列表框自动调整尺寸、缩减空白、布局更美观。

## 诊断结论（一致性核查）

- 应用已有「列表自适应高度」的唯一权威实现 `responsive_ui.auto_height(tree, container, ...)`：读当前样式行高、按容器可用高度算可见行数、并把行数夹到 `min(算出的行数, 实际条目数)`，从而既随窗口缩放又随条目收缩、不留空白。
- 它此前只接入了部分页面：资产管理表（`desktop_asset_pages.py`）、分镜表（`desktop_storyboard_page.py`）、白模预演表（`local_previs.py`）、文件表（`storyboard_table_ui.py`）。
- 未接入、且确实会留白的「伸展容器 + 固定 height + 无 auto_height」处：**模型管理**（`pet_models_ui.py`，用户点名）、版本采用选择器（`version_picker.py`）、回收批次条目表（`desktop_project_pages.py`）。
- 其余固定高度表（`app.py` 镜头表 `pack(fill='x')`、`asset_batch.py` 滚动表单内表、`asset_reference_images.py` 对话框表、`desktop_project_pages.py` 回收批次表 `expand=False`、项目首页列表已有专用高度逻辑）经核验不满足「可伸展容器」判据，不在本轮改动范围。

## 改动

- `pet_models_ui.py`：`_build_window_and_table()` 建表后接 `auto_height(self.tree, self.table_shell)`，把返回的 `fit` 存为 `self._fit_model_list`；`load_rows()` 在 `_render_mode_rows()` 之后调用 `self._fit_model_list()`，行数变化即重新收紧高度。
- `version_picker.py`：`open_picker()` 对版本表接 `auto_height(table, table_shell)`，`refresh()` 末尾调用 `fit_list()`。
- `desktop_project_pages.py`：回收批次条目表接 `auto_height(item_tree, item_table)`，`show_items()` 末尾调用 `fit_items()`。
- `tests/test_ui_batch7_settings_models.py`：新增 `ModelListAutoHeightTests` 两条——加载 3 条模型后列表高度收缩到 3 行；行数多时高度不超实际条目数且至少保留 2 行。均走真实 `load_rows` 代码路径（monkeypatch `agent_model_records` 后 `win._pet_reload()`）。

## 验证（本轮运行）

- 默认 `smoke_test.py`：8/8 通过。
- 定向 `run_selftests.py -k test_ui_batch7_settings_models test_version_pin test_ui_batch4_desktop_project_pages test_skills`：177 条 0 红（含新增 2 条、`test_skills` 154 条、`test_version_pin` 3 条、`test_ui_batch4_desktop_project_pages` 3 条）。
- `run_selftests.py -k test_module_size_ratchet`：2/2 通过（`pet_models_ui.py` 收敛到 1000 行、不超上限）。

## 环境说明（非本轮引入、已补齐后复验）

worktree 由 `git worktree add` 从干净 master 检出，缺失两类 gitignored/子模块内容，导致 `test_skills`（SKILL 注册表 71≠73）与架构门禁 `基准历史.json` 红。二者与本次 UI 改动无关（主检出同 HEAD 全绿）。按既往轮次（R2077/R2165）同法补齐后复验：

- 补齐 3 个 SKILL 子模块内容：`skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/剧本锻造`、`skills/01 剧本准备SKILL/编剧技能集`（从主检出复制，未入库）。
- 补齐 `维护记录/基准历史.json`（gitignored）。
- 补齐后 `test_skills` 注册表恢复 73，`run_selftests -k ... test_skills` 0 红。

## 未验证

- 未跑完整安全全量 `--all --safe`（功能轮不命中触发条件；纯 L4 UI 改动，未触及启动路径/Tk 生命周期/删除语义/层级登记）。
- 未在用户真机（高 DPI、实际字体）目测窗口缩放与条目增删时的列表高度。

## 提交

已提交：commit `5e74aa64`（分支 `codex/wip-R2411`），含 `desktop_project_pages.py`、`pet_models_ui.py`、`version_picker.py`、`tests/test_ui_batch7_settings_models.py` 与本结果文件。
