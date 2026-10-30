# R2137 结果：合入 codex/wip-R2133（R2133：模型管理删除模型时提示并清理指向它的 SKILL 预设）到 master（合并轮）

## 合并
- 来源：`codex/wip-R2133` 的 R2133（f96eb436），基于 ea86aa03；master 当时为 cf383c3c（含 R2131／R2132）。`git merge --no-ff`，无冲突。
- 合入内容：`stage_config.preset_model_references／release_preset_model`、`pet_ui_settings.delete_pool_model` 删除后把失效预设模型改为「自动」、`pet_models_ui` 确认框列出受影响预设、REQ-S01-75／DES-S01-75、`tests/test_model_delete_presets.py`。断言未动。

## 用户配置（经用户要求，不进提交）
- 用合入后的 `stage_config.release_preset_model` 把本机 `配置/SKILL/预设.json` 里剧本准备预设「Gemini 4」的模型由已删除的「Google Gemini 4 Argon」改为 `auto`（界面显示「自动」），SKILL 勾选保留，其他预设不动。
- 该文件在 git 中标记 skip-worktree，改动只在本机，本提交不含它。项目里已交付的文件未动。

## 验证（本轮运行，主检出合并后）
- `run_selftests -k model_delete_presets pet_ui ui_batch7 stage_config skill_panel model_pool req_s01_anchors requirement_traceability preset`（经 gui_hidden）：ALL TESTS PASSED。
- `smoke_test.py`：通过。
- `smoke_test.py --architecture`：通过。
- 未跑全量。
