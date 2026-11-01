# R1378：UI 统一入口覆盖轮 — 卡片容器（第 1 批：资产详情页 / 原生资产窗 / 批量资产表单）

类型：功能轮（§3.1，UI 统一入口：卡片容器覆盖；不改业务逻辑、阶段、路径与分层）。中央轮次 1378（`.git/round-counter.json` 的 `last_claimed=1378`）。范围＝`维护记录/UI统一入口路线图_v1.md` 待收口 4 项之「卡片容器」（§一 第 3 项；§二 无独立完成判据，权威取 `ui_components.md` §卡片）。

## 三个必答
- 本轮类型：功能轮（§3.1）——页面级信息／操作单元承载区从 `ttk.LabelFrame` 迁移到统一 `ui_widgets.Card`。
- 测试：架构 `smoke_test.py --architecture` **323/323**（原 321，只增不减；只在既有 `test_card_boundary.py` 增 2 条方法，未增删门禁文件，§5 清单不变）；定向 `run_selftests.py -k "asset_detail asset_batch asset_gating native asset_contract ui_edges ui_widgets"` **0 文件红**；默认冒烟 `smoke_test.py` **8/8**；`py_compile` 3 文件 OK。
- 欠账：1378 − 1375 = 3 < 5；未命中 §5 升级条件。按用户「不因为是收尾就跑全量兜底」不跑全量。卡片容器**本轮为分批迁移第 1 批**，审计表见下，其余站点下一轮续跟（不写「完成全量覆盖审计」）。

## 范围与口径（`ui_components.md` §卡片）
- 卡片规格：背景 `color.background.card`、边框 1px `color.border.default`、圆角 `radius.lg`、内边距 `space.lg`；「卡片承载一个完整的信息或操作单元」。
- 收口口径：页面／对话框里承载一组相关字段或说明、构成一个完整信息／操作单元的最外层容器，用 `ui_widgets.Card`（标题用卡内普通标签，卡片不用 LabelFrame 的标题行——与 `test_ui_edges` 既有「无标签行卡片」一致）。
- 本轮参照 R932–R960「单页粒度」分批：**只迁移资产详情页、原生资产窗、批量资产表单**，不整仓机械替换。

## 实现（迁移的 9 处）
### 1. `asset_detail.py`：详情页七个信息／操作单元（`ttk.LabelFrame(text=…) padding=6` → `Card` ＋ 卡内标题 `ttk.Label`）
- `_pending_block`（待确认）、`_board_block`（正典板）、`_anchor_block`（锚点字符串）、`_role_block`（参考职责声明）、`_variants_block`（状态变体）、`_raw_block`（原始数据）、`_roster_role`（角色清单块）；导入补 `Card`。

### 2. `native_assets.py`：`attach_controls` 的「生图模型」配置区
- `ttk.LabelFrame(form,text='生图模型',padding=10)` → `Card(form)` ＋ 标题行 `grid(row=0,columnspan=4)`，原 grid 行（0/1/2）顺移为 1/2/3，控件不变。

### 3. `asset_batch.py`：本地资产表单的「ComfyUI 连接与本地工作流」配置区
- `ttk.LabelFrame(form,text=…,padding=SPACING['sm'])` → `Card(form,padding=SPACING['sm'])` ＋ 标题行 `grid(row=0)`，字段行 `enumerate(..., start=1)` 顺移；导入补 `Card`。

## 测试契约同步（§2.4：有意 UI 契约变化）
- `tests/test_asset_gating.py`：`NativeAssetsGatingTests.test_progressbar_directly_above_action_buttons` 断言 `["Labelframe", …]` → `["Card", …]`（同一承载区改类，顺序与后续断言强度不变）。
- `tests/architecture/test_card_boundary.py` 增 2 条：`test_asset_detail_page_blocks_use_card`（详情页 ≥7 个 Card）、`test_native_assets_and_asset_batch_forms_use_card`。文件已在 §5 清单内，不新增门禁文件。
- `维护记录/TODO注释快照_20261003.json`：`asset_detail.py` 行注释行号 351 → 353（本轮在 `_board_block` 前插入 2 行，行号平移；分类与结论不变）。

## 验证
- 架构 `smoke_test.py --architecture`：**323/323、0 红**（第 1 次 1 红＝TODO 注释快照行号漂移，定向修 `TODO注释快照` 后第 2 次通过；原 321，+2 为本轮新增方法）。
- 定向 `run_selftests.py -k "asset_detail asset_batch asset_gating native asset_contract ui_edges ui_widgets"`：**0 文件红**（首轮 `test_asset_detail.BoardTests.test_image_actions_are_keyboard_buttons` 1 条红，属焦点相关顺序抖动：单跑 36/36、整模块 36/36、定向复跑均绿，非本轮引入；该用例对 `desktop.safe` 与 `<Return>` 焦点敏感）。
- 默认冒烟 `smoke_test.py`：**8/8**；`py_compile asset_detail.py native_assets.py asset_batch.py` OK。
- 新增 `skipTest`：无。

## 卡片容器覆盖审计表（全量站点）
- 已用 Card（门禁固化，共 19 页）：云端视频、本地视频、云端工作室(app.settings)、资产参考导入、云端资产、背景角色、参考墙、Qwen、TTS、Seedream、提示词优化器、工作流设置、宠物设置中心、宠物模型窗、白模选择、白模工作区、**资产详情页**、**原生资产窗**、**批量资产表单**。
- 待续跟（本轮未改，下一批迁移）：`keyframe_comfy.py` 生成模型与接口／ComfyUI 连接（2）、`desktop.py` 分类导航组／表格框／待办裁决／开工前先确认／本地生成／线上生成（6）。
- 明确豁免（并说明理由，不属「页面级单元容器」）：`white_model.py` 两处与 `workflow_settings.py`、`cloud_video.py` 的 LabelFrame 均位于**已用 Card 的窗口内部**，是卡内小节；`skill_panel.py` 技能说明是锁定几何传播的列表＋正文阅读区（`grid_propagate(False)`，R934 曾回退类似改动），不属配置卡；`batch_frames_tool/启动批量首帧.pyw` 是独立工具脚本，不属桌面主界面页面。

## 全量判定
- 1378 − last_full_safe_all_round(1375) = 3 < 5；未命中 §5 升级条件（启动路径／Tk 控件销毁重建／删除语义／层级登记表均未改：Card 仅改容器类与 Style，不销毁重建控件）。
- 本轮改了生产代码与测试，内容树变化，7 日内同树绿凭据不可复用；按用户指令不跑全量。

## 提交
- 内容：`程序/asset_detail.py`、`程序/native_assets.py`、`程序/asset_batch.py`、`程序/tests/architecture/test_card_boundary.py`、`程序/tests/test_asset_gating.py`、`程序/维护记录/TODO注释快照_20261003.json`。
- 报告与状态页：`程序/tasks_round/tasks_round_1378_result.md`、`程序/project_status.md`（轮次头改为 1379）。
- 未触碰主树他人已暂存改动与未跟踪用户目录。
