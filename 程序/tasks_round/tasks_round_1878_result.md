# R1878 结果：设计 token 间距吸附 4px 刻度＋token 门禁基线收紧（修复轮）

## 前提更正
交接所述「ui_theme 与 ui_tokens 双调色板并存」已过时：R1428 已统一，`ui_theme.py` 从 `ui_tokens` 导入，自身 0 hex。本轮无调色板决议。

## 用户拍板（2026-10-22）
A 收紧基线；B 非刻度间距按「就近、平局取小」吸附 SPACING 4px 刻度；C 本地预览页 HTML 颜色登记豁免。

## 改动
- 11 个文件 46 处数字 `padx/pady` → `SPACING[...]`：0→none，2/3/5/6→xs(4)，7/10→sm(8)，14→md(12)，18→lg(16)。单处位移 ≤2px（2→4 为 +2）。
  asset_reference_import 7、background_characters 2、cell_hover 4、cloud_assets 5、native_assets 6、qwen_setup 1、seedream_settings 5、shared_video_controls 1、storyboard_selection 1、workflow_settings 6、agent/prompt_optimizer 6。
- `tests/architecture/test_token_boundary.py`：HEX_BASELINE 41→1（仅 previs_monitor.py，注明豁免理由）；PADDING_BASELINE 62→空（全站数字 padx/pady 清零）。断言未动。
- 未纳入：元组形式间距（如 `pady=(0, 6)`，门禁不计）；width/height/wraplength 132 处待逐处裁定。

## 验证（本轮实测）
- 架构 `smoke_test.py --architecture` 394 条：392 过，2 红为环境性——`维护记录/基准历史.json` 与 `skills/00全流程SKILL/.../screenplay-gate-engine.md` 未入库、只在主检出存在，worktree 缺失；与本轮无关。
- 定向 `run_selftests.py -k`（11 个模块关键词）27/27、0 红；默认冒烟通过。
- 视觉变化未经实机截图核对；全量未跑。

## 合入说明（R1885 合入时补）
变基到 master 时发现 R1868 已在 master 做完同一件事（44 处数字间距令牌化、门禁零容忍），冲突一律取 master；本轮代码改动被 R1868 覆盖，合入后只剩本结果文件。
