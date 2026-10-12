# R1400：UI 路线图 §一 第 2 项（设计 token）第 3 批单页迁移（5 页，零视觉变更）

类型：功能轮（§3.1，UI 统一入口／设计 token）。中央轮次：1400。范围＝设计 token 迁移中**可证明零视觉变更**子集的第 3 批：`keyframe_comfy.py`／`workflow_settings.py`／`white_model.py`／`native_assets.py`／`background_characters.py` 五页内联 `padx/pady`（值恰等于 `ui_tokens.SPACING`）改从 token 取值，另 `keyframe_comfy.py` 1 处等值 `#ffffff → COLORS['background_card']`。

## 三个必答
- 本轮类型：功能轮（§3.1）——5 个生产页的内联视觉常量等值改用 token ＋各页 1 处 import；不改业务逻辑、阶段、路径、分层；不改字体；颜色仅等值提换。
- 测试：定向 `tests.test_keyframe_comfy`＋`test_previs`＋`test_assets`＋`test_auto_import`＋`test_workflow_settings_cache`＋架构 3 项 **168/168**；默认冒烟 **8/8**；架构 `--architecture` **341/341**。
- 欠账：`1400−1396=4<5` 且未命中 §5 升级条件 → **不跑全量**（最近绿全量 R1399 `tree=250b6384…`）。

## 实现（等值提换，零视觉变更）
- 24 处内联标量 `padx/pady`（值∈{4,8,12,16}＝`SPACING` 既有档）改 `SPACING['xs'/'sm'/'md'/'lg']`：`keyframe_comfy.py` 11、`workflow_settings.py` 5、`white_model.py` 4、`native_assets.py` 3、`background_characters.py` 1。
- `keyframe_comfy.py` 1 处 `bg='#ffffff'` → `bg=COLORS['background_card']`（#FFFFFF 等值）。
- 5 页各新增 `from ui_tokens import SPACING`（`keyframe_comfy.py` 另含 `COLORS`）——纯数据模块、无依赖、无环。
- 保留不动：值非 token 的间距（2／3／5／6／10／14 等）与全部 tuple 间距（棘轮不计）。

## 过程缺陷与修正（同轮内）
- 首版替换脚本用「整文件是否出现该名字」判定是否需补 import；因替换后正文已含 `SPACING[...]`，被误判为「已 import」→ 5 页均未加 import，`test_keyframe_comfy` 5 条 `NameError`。改为**只按 `from ui_tokens …` 行**判定后补齐 import，复验全绿。教训：import 存在性判定只能看 import 语句，不能扫全文。

## 验证
- 定向：`test_keyframe_comfy`＋`test_previs`＋`test_assets`＋`test_auto_import`＋`test_workflow_settings_cache`＋`test_token_boundary`＋`test_todo_comment_snapshot`＋`test_unification_ratchet` **168/168、OK**（12.4 秒；首版 5 条 NameError 已于同轮修绿）。
- 默认冒烟 `smoke_test.py`：**8/8、0 失败**。
- 架构 `smoke_test.py --architecture`：**341/341、0 红**（127.77 秒）。
- `test_token_boundary` 计数下降：`keyframe_comfy.py` 36→25、`workflow_settings.py` 11→6、`white_model.py` 12→8、`native_assets.py` 9→6、`background_characters.py` 3→2；HEX `keyframe_comfy.py` 3→2。
- 全量：**不跑**（见「三个必答」）。

## 提交
- 内容：`e81df9c`（5 页）。
- 报告／状态／接力：本轮收尾提交。

## 复盘
- 已收口：第 3 批 24 处间距＋1 处等值色迁移。`test_token_boundary` 两个类别合计从 213／111 降至约 165／108（含 R1396／R1399 累计）。
- 决策-free 子集**接近耗尽**：仅余 `agent/prompt_optimizer.py`（10 处）与 `desktop.py`（13 处，启动路径，须单独评估 §5 与风险）——其余只剩 0 值间距（`cell_hover.py`／`shared_video_controls.py`）。
- 未做（理由）：hex 其余 6 处、103 处旧 `ui_theme` 调色板值、非 token 间距值、旧页面文字层级——均需用户对设计 token 调色板决议（①改视觉／②零视觉补值／③暂不迁移）后逐页推进；本轮不擅自改视觉。
- 下一轮候选：`agent/prompt_optimizer.py`（10）；或等调色板决议后统一推进 `desktop.py`／hex／文字层级。
