# R2133 结果：模型管理删除模型时，提示并清理指向它的 SKILL 预设（REQ-S01-75／DES-S01-75）（功能轮）

## 问题
用户在模型管理里删掉「Google Gemini 4 Argon」后，`配置/SKILL/预设.json` 里剧本准备的预设「Gemini 4」仍指向这个已删除的模型，选这个预设会落到不存在的模型上。原因：删除只改模型池，不检查预设引用。

## 改动
- `stage_config.py`：新增 `preset_model_references(names, keep)` 和 `release_preset_model(names, keep)`。预设的 `model` 按 ID／显示名／模型名（不分大小写）匹配被删模型；如果某个名字仍被别的模型使用（`keep`），就不算失效。命中的预设只把 `model` 改为 `model_router.AUTO`（「自动」），预设名和 SKILL 勾选保留。没有命中时不写文件。
- `pet_ui_settings.py`：`delete_pool_model` 删除后调用 `release_preset_model`，提示末尾加「，N 个预设的模型已改为「自动」」。新增 `_pool_model_names`、`pool_model_presets`（给确认框用，返回阶段中文名＋预设名）。
- `pet_models_ui.py`：`_ModelManager.delete_one` 的确认框列出会被改动的预设（983 行，未超 1000 行上限）。
- `docs/stages/S01_剧本准备.md`：新增 REQ-S01-75、DES-S01-75 与锚定行。
- `tests/test_model_delete_presets.py`：新增 3 条（确认框列表、删除后只改失效引用、无引用时预设文件字节不变）。已有断言未动。

## 用户数据
- 项目里已交付的文件不动，本轮也没有改用户的 `配置/SKILL/预设.json`。
- 现存的「Gemini 4」预设不会被本轮自动修正：Argon 在本轮之前已删除，新逻辑只在删除时运行。需要用户确认后另行清理。

## 验证（本轮运行，worktree）
- `run_selftests -k model_delete_presets pet_ui ui_batch7 stage_config skill_panel model_pool req_s01_anchors requirement_traceability preset`（经 gui_hidden）：ALL TESTS PASSED。
- `smoke_test.py --architecture`：410 条通过。从主检出临时复制被忽略的 `维护记录/基准历史.json`，跑完已删除。
