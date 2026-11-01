# R1620 拆分 skill_panel.py 为 L4 支撑模块（Q9 第三批）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round/tasks_round_1610_result.md) J 第三批 Q9；`skill_panel.py` 是 Q9 第 3 个模块）。
- 测试：定向 9 个模块单跑（见下，1 个既有红、1 个由用户脏文件引起、1 个会话级 GUI 超时，均非本轮引入）；架构门禁 `smoke_test.py --architecture` **354 项 OK**；默认冒烟 8/8；`test_line_endings` 16/16。
- 欠账：本轮改源码＋新增模块，`project_status.md` 全量欠账计数 +1；R1619 的欠账仍未清（后台全量跑完后由 post-commit 写凭据）。

## 做了什么

`skill_panel.py` **1886 → 1475 行**（仍为 CRLF，行数口径不变），已 ≤ LIMIT 1500，故按棘轮规则从登记表删除。

新增 L4 模块 `skill_panel_support.py`（486 行），承接 **39 个纯函数 + 4 个模块级常量**：

- 严格闭包（依赖只落在已导入名与彼此之间，33 个）：`markdown_document`、`note_text`、`workflow_note_text`、`open_cloud_video`、`open_tts`、`flow_skill_*`、`chinese_skill_display`、`skill_checkbox_label`、`registered_skill_checkbox_label`、`set_flow_skills`、`stage_label`、`panel_title`、`stage_of_page`、`stage_button_for`、`desktop_project`、`pet_of`、`status_of`、`run_report`、`waiting_reason`、`pool_records`、`stage_capabilities`、`model_fits_stage`、`model_choices`、`grouped_model_choices`、`sync_models`、`build_orchestrator`、`program_of`、`stage_context`、`panel_window_size`。
- 额外自洽小簇（迁移脚本已断言其全部引用都落在「已迁集合 ∪ 已导入名」内）：`skill_order`／`SKILL_FLOW_ORDER`、`external_package_api_hint`／`EXTERNAL_PACKAGE_API_HINT`、`manual_path`／`manual_entry`／`MANUAL_NAME`、`stage_for`／`FLOW_STAGE`，以及因此变为可迁的 `interfaces_of`。

原模块用 `from skill_panel_support import (...)` 按**原名转发**这 43 个名；**旧文件顶层名零缺失**（`hasattr` 校验 missing=[]，新增名字 0 个）。`Panel` 类与其余 UI 绑定（`stage_button*`、`refresh_all`、`show`、`open_for_page`）留在 `skill_panel.py`。

同步：`tests/architecture/_layers.py` L4 登记 `skill_panel_support`；`architecture.md` L4 行补登；`维护记录/覆盖率基线.json` 刷新（49/276）。

## 定向验证

| 模块 | 结果 |
| --- | --- |
| `tests.test_skills` | 152 项 OK |
| `tests.test_core` | 127 项 OK（1 skipped） |
| `tests.test_asset_gating` | 18 项 OK |
| `tests.test_skill_import_validation` | 11 项 OK |
| `tests.test_production_lock_ui` | 2 项 OK |
| `tests.test_line_endings` | 16 项 OK |
| `tests.test_skill_notes` | 1 红——**干净工作树 OK**，master 红由用户未提交的 `程序/配置/SKILL/预设.json` 引起（不提交、不越权改用户文件） |
| `tests.test_manual_plan` | 1 error「执行页呈现器尚未安装」——**干净工作树（b6863b4）同样复现**，既有 |
| `tests.test_pet_ui` | 会话级 GUI 超时（`pet_cloud.py:2099 TclError` 噪声），与本轮无关 |

架构门禁 `python smoke_test.py --architecture`：**354 项 OK**（172.8 秒）。其中 `test_round_baselines.test_full_safe_all_is_required_after_eight_source_rounds`（R1619 全量欠账账簿项）因后台补跑进行中、`auto_full_running()` 放行而不报红；后台全量跑完后若该模块仍红，属既有会话级 GUI 限制（见诚实边界），非本轮代码。

## 本轮自身缺陷（已修）

1. 首版 `skill_panel.py` 被写成 LF，而 `.gitattributes` 把该文件钉为 `eol=crlf`，`test_line_endings` 报「换行符被换了」。改回 CRLF 后 16/16。
2. 一处因拆文件而失效的冒烟检查：`smoke_test.py` ROUND_CHECKS 第 411 行原以「`程序\skill_panel.py` 里存在 `def grouped_model_choices(`」作为「阶段配置具备供应商到模型的两级下拉数据」的证据；该函数已迁出，故把该检查的 `path` 改指 `程序\skill_panel_support.py`（**只改指向、检查项仍 8 条**，不新增／不删除）。

## 诚实边界

- 全量安全全量最后一次真实通过仍是 **R1605/e59e513**；R1606–R1620 未跑全量。R1608 的 `save_bytes` 回归已在 R1619 修复，但「全量是否转绿」要等 post-commit 后台跑完 `.git/auto-full-safe-result.json` 才能定性（会话内 `test_manual_gate`／`test_perf_baseline`／`test_row_targets`／`test_ui_edges`／`test_pet_ui` 超时，需真实全量）。
- 拆分正确性的依据是 AST 引用闭包＋`hasattr` 公开面校验＋架构门禁，不依赖运行期 GUI 行为；未实机点击该面板。