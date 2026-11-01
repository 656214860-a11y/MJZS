# R1684 功能轮：阶段配置页「总控＋制作锁＋更多制作锁」布局整理、下拉按内容自适应宽度、厂商 `openai-compatible` 改显示名

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（UI，源码轮）。仅改阶段配置页 UI 与厂商显示名，不改变任何数据流（`save_workflow_locks`、`lock_inputs` 键、`context_values`、事件绑定、制作锁含义与取值均不变）。

2. **测试跑了吗？三个基线过了吗？**
   - 默认冒烟 `smoke_test.py`：**8/8**。
   - 定向 `run_selftests.py -k skill_panel production_lock model_pool pet_models ui_widgets ui_tokens`：**102 条用例，0 文件有红**（10 个工作单元）。
   - 架构 `run_selftests.py -k function_size_ratchet agents_md ui_tokens`：**17/17**。
   - 额外跑 `smoke_test.py --architecture`：368 条，**唯一红**为 `test_round_baselines.test_full_safe_all_is_required_after_eight_source_rounds`（R1683 欠一次完整安全全量，后台 post-commit 自动补跑负责，与本轮无关，未手动跑全量）。
   - 未跑安全全量（§5：欠账由后台补跑，禁止手动 `run_selftests.py --all`）。

3. **project_status.md 的欠账少了吗？** 没有减少；本轮是源码轮，**全量欠账 +1**（R1679 已记 13/8，此后 R1680/R1681 修复轮亦为源码轮，本轮继续 +1，交由后台补跑闭环）。

## A 改动

### A. 下拉框按内容自适应宽度（`ui_widgets.py` + `production_lock_fields.py` + `ui_tokens.py`）

- `ui_widgets.SelectBox` 加 `fit=False` 关键字参数与 `refit()` 方法；`_fit_width(values, current='')` 现把「全部选项＋当前值」一并计入最长显示宽度（CJK 按 2 计），封顶 `COMBOBOX_MAX_WIDTH=28`。默认 `fit=False` 保持旧行为（只读自适应、可编辑固定 `COMBOBOX_WIDTH`），故既有 `test_ui_widgets_inputs` 断言不动。
- `ProductionLockFields` 的每个锁下拉改 `SelectBox(..., state='normal', fit=True)`（弃用固定 `width=6/12/24`）；`refresh_states()` 末尾对全部锁 `entry.refit()`，使选项刷新（`set_values`）或用户输入长文本（`changed`→`refresh_states`）后宽度重算。
- `ui_tokens.PRODUCTION_LOCK_WIDTH` 已无引用，删除；新增 `ui_tokens.FORM_LABEL_WIDTH = 10` 作表单标签列宽基准。全局搜索确认 `PRODUCTION_LOCK_WIDTH` 无残留引用。

### B. 总控＋制作锁＋更多制作锁 布局对齐（`skill_panel.py` + `production_lock_fields.py`）

- 标签列统一 `FORM_LABEL_WIDTH`：`build_workflow_coordinator` 的「总控」标签（原硬编码 `width=10`）与 `build_flow_skill` 的「SKILL」标签、`_build` 的「预设／厂商」标签（原局部 `label_width=10`）、以及 `ProductionLockFields` 各锁标签（原无固定宽）共用一处基准。
- 各锁仍「标签＋下拉」成对封装在 field 框内，`padx`/`sticky` 全部走 `SPACING` 令牌；`new_lock_row`／`optional_lock_row` 保持 FlowBar 按「组（field 框）」换行，`lock_row` 保持旧五锁 grid 同排（未改其布局，避免破坏 `test_production_lock_ui` 的 grid 断言与既有设计意图）。
- 删除 `build_workflow_coordinator` 里对 `style_directors` 的 `configure(width=PRODUCTION_LOCK_WIDTH['normal'])` 特判（自适应后不再需要）。
- `更多制作锁` 展开/收起逻辑（`toggle_optional_locks` 的 pack/pack_forget）未动。

### C. 厂商显示名（`model_pool.py`）

- `PROVIDERS` 里 `('openai-compatible', 'openai-compatible')` 第二项 label 改为 `'OpenAI 兼容接口'`；第一项 id `openai-compatible` 不变。`anthropic`、`custom` 两项不动。
- 全局搜 `PROVIDER_LABELS`／`PROVIDERS`／`provider_name` 使用点（`pet_models_ui.py`、`model_pool.provider_name` 等）确认：均靠 id 存取、只用 label 展示；`pet_models_ui` 保存经 `id_of_label(label, PROVIDERS)` 写回 id `openai-compatible`，无把中文 label 当 id 存盘之处。`pet_models_ui.py` 无需改动（在 ALLOWLIST 内但未命中）。

### 测试

- 新增 `tests/test_skill_panel_layout_fit.py`（3 用例）：①可编辑锁 `state='normal'` 宽度＝选项＋当前值最长项（含封顶）、改值后重算；②900/560 两种面板宽度下总控＋制作锁区域无子控件越界、同一行相邻控件 x 不重叠（布局用例临时 deiconify，因 FlowBar 几何需已映射窗口，其余用例 withdraw）；③`PROVIDER_LABELS['openai-compatible']=='OpenAI 兼容接口'`、`PROVIDER_IDS` 仍含 id、显示名↔id 往返写盘为 id。
- `tests/test_production_lock_ui.py` 第 45 行断言同步（**超出 ALLOWLIST，见 C 节说明**）：原 `assertLess(width, 14)` 为旧固定宽度 6/12 的过期断言，现改为 `width <= COMBOBOX_MAX_WIDTH` 且 `width == SelectBox._fit_width(选项, 当前值)`。这是「用户明确要求的 UI 契约有意变更」（§2.4）下的断言同步，不是放宽上限或删断言——旧 `<14` 已被更精确的等值契约断言替代。

## C 待用户裁决

1. **越 ALLOWLIST 改动说明**：`tests/test_production_lock_ui.py` 不在任务书 ALLOWLIST，但其第 45 行 `assertLess(width, 14)` 与任务 A「全部制作锁按选项最长项自适应（封顶 28）」直接冲突（`delivery_format` 最长项「只要 markdown 文档」宽 18、`material_source` 最长项「对标爆款（现场采风）」宽 20）。因提问通道不可用，按 AGENTS.md §2.4（用户明确要求的 UI 契约有意变更可同步相关测试预期）将其同步为等价强度的新契约断言并在此列出；未弱化、未删除、未跳过。
2. **目视项未验证**（无头环境无法目视）：标签列与下拉的视觉等宽观感、行内等高的像素级美观度、`更多制作锁` 展开/收起时上方控件是否「零跳动」的主观观感——仅以「无越界、无重叠」的几何断言覆盖，**不声称已目视确认**。
3. 各锁下拉自适应后，`aspect_ratio`/`fps` 等短选项锁宽度会比旧固定值更窄（如 `16:9` 宽 4）；这是按内容自适应的预期结果，非缺陷。

## 提交

见提交信息 `R1684:`。
