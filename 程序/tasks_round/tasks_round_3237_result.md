# R3237 结果 · U1 共享测宽函数与三处试点
<!-- round-evidence: {"commit_base": "c264804e", "credential_hits": 0, "evidence_sha256": "20fabe95440d1205", "exit": 0, "failed": 0, "passed": 302, "round": 3237, "tests": "run_selftests.py -k text_measure select_placeholder ui_widgets_inputs ui_widgets_dialogs ui_widgets_table column_fit storyboard_page_loading ui_edges data_table_boundary dynamic_import_registry shortcut_registry_boundary skill_panel_layout_fit files_panel"} -->

- 轮次类型：功能轮（UI 统一组件标准任务书 U1）。
- 三问：测试跑了；冒烟 9/9、架构门禁实测全绿、全量欠账无新增；`project_status.md` 欠账无变化。

## 改动

- `ui/ui_popup.py` 新增共享测宽入口：`text_measure_font`（FONTS/token 规格或 tkfont.Font → 可测宽字体，按 `(root, 规格)` 缓存——自检每例重建 `tk.Tk`，跨解释器复用 Font 会拿到已销毁的 Tcl 解释器，首轮实测踩中已修）、`measure_text_width(font, texts, max_width=None, root=None)`（真实字体 `measure` 取最长文本像素宽，含上限钳位）、`char_unit_px`（ttk `-width` 字符单位像素代理，取 '0' 实测宽）、`text_units_width`（像素→字符单位向上取整）。
- `ui_widgets.py`：`SelectBox._display_width`/`_fit_width` 改调 `text_units_width(COMBOBOX_FONT, …)`，删去 `ord()>0x2E80` 全角×2/ASCII×1 近似；文件 1125→1124 行（≤1125 棘轮）。`_display_width` 保留导出（`ui/skill_panel.py` 的 Listbox 列宽同为字符单位语义）。
- `ui/desktop_files_panel.py`：`_fit_script_width` 由 `responsive_ui.measure` 逐条量改为 `measure_text_width` 一次取最长（行为等价：同字体同文本集取 max）。
- `ui/storyboard_table_ui.py`：列宽魔法数字 `+14` ×2 改取 `SPACING['lg']`（16px，最接近的标准间距，列宽行为不变）。
- 新门禁 `tests/architecture/test_text_measure_boundary.py`：AST 口径——`.measure` 属性访问（调用与绑定方法取法同罪）、`from responsive_ui import measure` 裸名调用、`ord()` 与 ≥0x2E00 常量比较三类存量按文件冻结只减不增；`ui/ui_popup.py` 为共享实现本体豁免；含坏样本 canary。
- 新功能测试 `tests/test_text_measure.py`：全角/ASCII/混合/空串/超上限钳位、集合取最长、单位换算、SelectBox 真 Tk 几何（`cget('width')` 与 `winfo_width()`）。
- `architecture.md` 门禁清单补登 `test_text_measure_boundary.py`。

## 基线与欠账

- 字符宽度近似欠账：**清零**（全仓唯一 `ord()>0x2E80` 处即本轮删除的 `_display_width` 实现）。
- 直接测宽冻结欠账 15 处（`MEASURE_BASELINE`：app/desktop/production_lock_fields/responsive_ui/asset_batch×2/keyframe_comfy×2/pet_models_ui/script_line_numbers/speech_settings_ui/ui_widgets×4）；`responsive_ui.measure` 旧入口冻结 2 处（storyboard_table_ui）。后续谁改谁迁。
- `ui_components.md` 测宽节（U0 已写）与门禁名一致，无需改动。

## 验证

- `run_selftests.py -k text_measure select_placeholder test_ui_widgets_inputs test_ui_widgets_dialogs test_ui_widgets_table` → 全绿（首轮 12 红为 Font 跨根缓存缺陷，修复后复测绿）。
- `run_selftests.py -k column_fit storyboard_page_loading ui_edges data_table_boundary dynamic_import_registry shortcut_registry_boundary skill_panel_layout_fit` → 165/165 绿（分镜表列宽、files_panel 消费方、SelectBox 全部 UI 边缘页）。
- 早前同轮 `-k files_panel files_panel_stages` → 140 条中仅上述 Font 缓存 12 红，面板/分镜消费方全绿。
- `smoke_test.py` → 9/9 绿。
- 未跑全量：功能轮按 §5 定向＋冒烟；合 master 前按规则另行触发。

## 提交

见 git log（`codex/wip-R3237`）。
