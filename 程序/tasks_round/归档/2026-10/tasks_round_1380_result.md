# R1380：UI 统一入口覆盖轮 — 文字层级（第 1 批：批量表单页 + 全量站点审计收口）

类型：功能轮（§3.1，UI 统一入口：文字层级覆盖；不改业务逻辑、阶段、路径与分层）。中央轮次 1380（`.git/round-counter.json` 的 `last_claimed=1380`）。范围＝`维护记录/UI统一入口路线图_v1.md` 待收口 4 项之「文字层级」（§一 第 5 项／§二 第一批 第 5 项，完成判据原文「新增辅助／说明／进度文字使用相应组件；旧页面覆盖率另审计。」）。

## 三个必答
- 本轮类型：功能轮（§3.1）——页面文字层级由局部 `ttk.Label(font=/foreground=/style='Muted.TLabel')` 收口到 `ui_widgets.HintLabel／DescriptionBlock／ProgressLabel`，标题改用 `style='Tokens.Title.TLabel'`；本批为单页粒度迁移第 1 批。
- 测试：定向 `run_selftests.py -k "keyframe batch_frames asset_batch ui_theme ui_edges video_ui text_component"` **333 条 / 0 文件红 / 220.1 秒**；默认冒烟 `smoke_test.py` **8/8**；`py_compile` 3 文件 OK；架构 `smoke_test.py --architecture` **325/325**（收口干净 master 全量后复核）。
- 欠账：1380 − 1375 = 5 **≥ 5 命中 §5 五轮规则，强制收口全量** `run_selftests.py --all --safe`（在干净 master 工作树执行）：**4967/4967、631.2 秒、0 红**（凭据 round=1380、tree f62cd088，last_full_safe_all_round=1380）。。文字层级**完成全量覆盖审计**（见审计表）。

## 范围与口径
- 组件语义（`ui_components.md` §文字组件）：`HintLabel` 短提示（≤20 字）、`DescriptionBlock` 可折行功能说明（≤60 字）、`ProgressLabel` 单行状态/进度（≤40 字）；视觉规格（font／foreground／wraplength／anchor／justify／padding）由 `ui_tokens` 的 `TEXT_HINT／TEXT_DESC／TEXT_PROGRESS` 唯一决定，页面不得覆写。
- 标题层级无独立语义组件；统一改用 `style='Tokens.Title.TLabel'`（skill_panel 既有用法）。
- 完成判据原文：新增辅助／说明／进度文字使用相应组件；旧页面覆盖率另审计。故本轮＝迁移一批 ＋ 收口全量站点审计（逐站点分类）。

## 实现（本批迁移 2 页）
### 1. asset_batch.py（本地资产批量表单）
- 表单顶标题 `ttk.Label(...,font=FONTS['title'])` → `style='Tokens.Title.TLabel'`；移除不再使用的 `FONTS` 导入（仅此一处使用）。
- 该页原已用 `DescriptionBlock`（生成范围／Qwen 说明）与 `ProgressLabel`（状态行）；本批补齐标题后整页纳入门禁。
### 2. keyframe_comfy.py（首帧 ComfyUI 窗）
- 顶标题 `ttk.Label(...,font=('Microsoft YaHei UI',12,'bold'))` → `style='Tokens.Title.TLabel'`。
- 目标集说明、提示词/参考图说明 → `DescriptionBlock`；状态行（`status`）→ `ProgressLabel`；计划说明（`plan_note`）→ `DescriptionBlock`；导入补 `DescriptionBlock`／`ProgressLabel`。
### 3. 门禁冻结
- `tests/architecture/test_text_component_boundary.py` 的 `TEXT_PAGE_COMPONENTS` 增加 `asset_batch.py`、`keyframe_comfy.py`（两页此后不得退回局部文字样式）。文件已在 §5 清单内，未增删门禁文件。

## 测试契约同步（§2.4）
- 无既有测试断言这两页文字的具体 font／foreground／wraplength；`test_text_component_boundary` 直接覆盖（含反向 canary）。

## 验证
- 定向 `run_selftests.py -k "keyframe batch_frames asset_batch ui_theme ui_edges video_ui text_component"`：**333 条、0 文件红、220.1 秒**。
- 默认冒烟 `smoke_test.py`：**8/8**；`py_compile asset_batch.py keyframe_comfy.py tests/architecture/test_text_component_boundary.py` OK。
- 架构 `smoke_test.py --architecture`：**325/325、0 红**（与原 323 相比 +0：仅在既有 dict 增两项，未增删门禁文件）。
- 收口全量（§5 五轮规则，干净 master `run_selftests.py --all --safe`）：**4967/4967、631.2 秒、0 红**（凭据 round=1380、tree f62cd088；`test_desktop_startup_perf` 14/14、`test_perf_baseline` 9/9 均通过，无阈值抖动）。
- 新增 `skipTest`：无。

## 文字层级覆盖审计表（全量站点，收口）
- 已迁移（门禁固化，7 页）：skill_panel.py、agent/prompt_optimizer.py、seedream_settings.py、qwen_setup.py、tts_settings.py、**asset_batch.py**、**keyframe_comfy.py**。
- 明确豁免（非页面文字层级）：ui_widgets.py（组件自身实现）、ui_theme.py（主题搭建）、cell_hover.py（单元格自绘）；asset_detail.py 缩略图／锚点窄格状态色文字 15 处（R1051 已定不做机械替换）。
- 标题层级（无 Title 语义组件，登记改用 `Tokens.Title.TLabel`——本轮 asset_batch／keyframe_comfy 已示范）：asset_detail.py 2、asset_reference_images.py 1、desktop.py 10、pet_models_ui.py 1、pet_settings_ui.py 2、white_model.py 1、ui_widgets.py 2（内部）。
- 旧页面说明／状态／提示文字（DescriptionBlock／ProgressLabel／HintLabel 待逐页迁移 backlog）：desktop.py 32、pet_settings_ui.py 8、skill_panel.py 6、storyboard_files.py 6、pet_models_ui.py 5、pet_cloud.py 8、app.py 4、workflow_settings.py 2、asset_reference_images.py 1、background_characters.py 1、cloud_video.py 1、prompt_window.py 1、pet_ui.py 1、asset_detail.py 1。
- 续跟计划：按单页粒度（参照 R932–R960／R1378–R1379 卡片节奏），每轮触达某页时迁移该页说明／状态／标题文字并加入 `TEXT_PAGE_COMPONENTS`；不整仓机械替换。

## 全量判定
- 1380 − last_full_safe_all_round(1375) = 5 ≥ 5 → §5 五轮规则命中，`test_round_baselines.test_full_safe_all_is_required_every_five_rounds` 强制要求收口全量；在干净 master 工作树执行 `run_selftests.py --all --safe`：**4967/4967、631.2 秒、0 红**（凭据 round=1380、tree f62cd088，last_full_safe_all_round=1380；架构门禁在同树复核 325/325）。

## 提交
- 内容：`程序/asset_batch.py`、`程序/keyframe_comfy.py`、`程序/tests/architecture/test_text_component_boundary.py`。
- 报告与状态页：`程序/tasks_round/tasks_round_1380_result.md`、`程序/project_status.md`（轮次头改为 1381）。
- 未触碰主树他人已暂存改动与未跟踪用户目录。
