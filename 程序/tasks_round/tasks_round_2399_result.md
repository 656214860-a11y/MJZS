# R2399 结果：合入阶段配置「供应商/模型」两级下拉合并为单级（合并轮）

## 三个问题（§7）

- **轮次类型**：合并轮（§3 无独立「合并轮」条目，按 §2.5 规则 27 合并他人分支到 master 的语义归类）。合入 `codex/wip-R2375` 到 master，含 R2368（结构治理轮）＋ R2375（功能轮）两个提交。
- **测试跑了吗、三个基线过了吗**：
  - 默认冒烟：8/8 通过。
  - 定向：`test_skills` 154 条、`test_pet_ui`＋`test_model_manager_actions`＋`test_ui_batch7_settings_models`＋`test_account_page` 652 条，均 0 红。
  - 架构门禁：416 条，本轮改动相关项全绿（循环依赖已拆、层级已登记、Panel 复杂度棘轮已下调、pet_models_ui 行数已压回 1000 内）；**剩余 2 个红项为并行会话在主目录 master 的未提交残留**（`writing_api.py` 1383 行 > 1372、`_repro_confirm_bug.py` 未登记层级），非本轮改动引入，详见下文「并行冲突」。
  - 全量：未跑（不命中 §5 强制全量条件；但架构门禁因并行残留未全绿，故本轮不声称全量绿）。
- **project_status.md 的欠账少了吗**：无欠账增减。本分支不写状态页（合并轮登记后转绿）。

## 合入内容

- `codex/wip-R2375`（两个提交）：
  - **R2368**（结构治理轮，断言未动）：剧本准备页与阶段配置页质量清理——`desktop_idea_bubbles.py` 抽 `_clear_bubble_view`／`_bubble_tag_index`、`desktop_idea_chat.py`／`desktop_idea_deferred.py`／`desktop_writing_page.py` 气泡清空收敛、`skill_panel.py` 删 Panel 死状态 `self.labels` 与 `program_of` 委托 `stage_execution_service`、`skill_panel_support.py` 同步、`test_shared_state_ratchet.py` 共享状态棘轮 48→45。
  - **R2375**（功能轮，断言未弱化）：`stage_model_picker.py` 把按钮右侧「供应商/模型」两级下拉合并为单级「供应商 · 模型」下拉，保留自动选择、自定义兜底、添加模型入口、选完即写配置与 script 阶段刷新。

## 冲突解决（与 master 上 R2392 的语义冲突）

R2392（已在 master）给 `stage_model_picker.py` 加了 `set_model_label(label)`，基于两级下拉（`self.provider` + `_show()`）。R2375 把两级合并为单级（`_by_display` 字典 + 单 `self.models`），删除了 `self.provider` 和 `_show()`。

解决方式：采用 R2375 的单级实现，**改写 `set_model_label` 适配单级下拉**——按显示名在 `self.groups` 里匹配，命中则把单级下拉设为 `'供应商 · 模型'` 文案并返回 model id，否则返回 `None` 不动。调用方 `desktop_idea_bubbles._sync_stage_model_picker` 保持不变。

同步的测试：`test_skills.py` 的 `test_set_model_label_syncs_provider_and_model_by_display_name` 从「两级下拉」断言改为「单级下拉」断言（`picker.model.get().endswith(' · Qwen-Max')`），断言检验行为、未弱化（仍验证命中返回 model id、空值/找不到返回 None 不动）。

## 结构治理（本轮合并引入的架构欠账闭环）

- **pet_models_ui.py 行数超限**（R2398 页签化把该文件推到 1030 行 > 1000 上限）：按「新增功能放新模块」规范，拆出 `pet_models_tabs.py`（`ModelManagerModeTabsMixin`：`_on_tab_changed`／`_on_mode_change`／`_render_mode_rows` 与 `list_status`），`_ModelManager` 改为继承该 Mixin。pet_models_ui.py 降至 990 行，pet_models_tabs.py 58 行。
- **Panel 复杂度棘轮**：R2368 删 Panel 死状态后实际 908 行 < 登记 925，`test_complexity_ratchet.py` 的 `CLASS_CAPS` 下调 925→923（正向下降固化）。
- **分层登记**：`pet_models_tabs` 登记为 L4（`_layers.py` + `architecture.md` 第 3 节）；`architecture.md` 同步 `stage_model_picker` 描述「两级」→「单级」。

## 并行冲突（如实记录，非本轮改动）

主目录 master 工作区存在并行会话的未提交残留（修改时间 20:09–20:15，与本轮无关）：

- `程序/writing_api.py`（+11 行，`confirm_preparation_document` 重写草稿 revision 回退采用版本）→ 导致 `test_module_size_ratchet` 报 1383 行 > 1372。
- `程序/tests/test_preparation_confirmation.py`（+26 行，配套测试）。
- `程序/_repro_confirm_bug.py`（未跟踪，复现脚本）→ 导致 `test_layers` 报未登记层级。

以上三处**不在本轮暂存清单**，未提交、未修改、未删除。架构门禁 416 条中仅这 2 个红项由它们产生；本轮改动涉及的架构项（循环依赖、层级登记、行数棘轮、复杂度棘轮、共享状态棘轮）全绿。

## 提交

- 已提交：是（master，合并轮）。commit hash 见 git log（结果文件随提交 amend，避免 hash 自指）。
- 提交信息：`R2399: 合入阶段配置供应商/模型两级下拉合并为单级（codex/wip-R2375）`。
