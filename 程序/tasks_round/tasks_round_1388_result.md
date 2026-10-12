# R1388：只读诊断 — 设计 token 内联视觉常量审计（路线图 v1 §一 第 2 项）

类型：只读诊断轮（§3.5，2026-10-12）。中央轮次：1388（`.git/round-counter.json` 的 `last_claimed=1388`）。范围＝`维护记录/UI统一入口路线图_v1.md` §一 第 2 项「设计 token」（权威 `ui_tokens.py`／`design_tokens.py`；审计点原文「页面是否仍内联视觉常量待审计」）。**不改任何生产代码、测试、台账或路线图**；只为该项登记可执行的 backlog。

## 三个必答
- 本轮类型：只读诊断轮（§3.5）——只读扫描 + 报告 + 登记 backlog，不改生产代码／测试／路线图。
- 测试：§5 规定「只读诊断默认不跑测试」。为陈述当前基线另跑默认冒烟 `smoke_test.py` **8/8、0 失败**（不计作本轮验收，也不触发全量）。
- 欠账：本轮不新增、不清欠账；**不跑全量**（距最近绿全量 R1387 `tree=000477da`、`last_full_safe_all_round=1386` 仅 2 轮，且本轮无生产改动）。

## 审计口径
- 生产模块＝`程序/` 下 `ROOT.rglob('*.py')`，排除 `tests/`、`tasks_round/`、`维护记录/`、`.git/`、`__pycache__/`；共 **269** 个 `.py`。
- 三类内联视觉常量：① 颜色 hex 字面量 `#[0-9a-fA-F]{3,8}`；② 数字型 `padx/pady/ipadx/ipady` 值；③ 数字型 `font=`（字号等）／`wraplength`／`width`／`height` 值。
- 权威／豁免：`ui_tokens.py`（token 定义）、`ui_theme.py`（主题定义）、`ui_widgets.py`（组件基类）、`ui_icons.py`（图标调色）、`skills/` 下独立脚本（非 Tk 页面）。

## 发现
### 1) 内联颜色 hex —— 业务页 111 处 / 8 文件
| 文件 | 处数 |
| --- | --- |
| `pet_ui.py` | 45 |
| `desktop.py` | 31 |
| `asset_detail.py` | 21 |
| `cell_hover.py` | 6 |
| `keyframe_comfy.py` | 3 |
| `app.py` | 2 |
| `storyboard_table_ui.py` | 2 |
| `previs_monitor.py` | 1 |

- 权威侧另有：`ui_theme.py` 53、`ui_tokens.py` 14、`ui_icons.py` 5；`skills/` 独立脚本 8（`generate_emotion_curve.py` 4、`remove_chroma_key.py` 3、`build_board_lite.py` 1）。
- **双调色板漂移风险（关键）**：`ui_tokens.py`（14 hex）与 `ui_theme.py`（53 hex）是两套各自硬编码的调色板，且 **`ui_theme.py` 未 `import ui_tokens`**；全生产仅 `desktop.py` import `ui_theme`，而 `ui_tokens` 被 14 个模块 import。同一 hex（如 `#243247`／`#3564a8`／`#f3f6fa`／`#ffffff`／`#8a8a8a`）在 `ui_theme`／`desktop`／`pet_ui`／`asset_detail`／`keyframe_comfy` 多点重复 → 改色须多点同改，易漂移。
- 未 `import ui_tokens` 却有内联 hex 的页面：`pet_ui.py`、`asset_detail.py`、`cell_hover.py`、`keyframe_comfy.py`、`storyboard_table_ui.py`、`previs_monitor.py`。

### 2) 数字 `padx/pady/…` —— 213 处 / 19 文件
Top：`desktop.py` 40、`keyframe_comfy.py` 36、`asset_detail.py` 21、`asset_reference_images.py` 18、`agent/prompt_optimizer.py` 16、`white_model.py` 12、`workflow_settings.py` 11、`native_assets.py` 9、`qwen_setup.py` 9、`seedream_settings.py` 9、`app.py` 7、`asset_reference_import.py` 7、`cloud_assets.py` 5 …

### 3) 数字 `font/wraplength/width/height` —— 189 处 / 32 文件
Top：`desktop.py` 41、`pet_settings_ui.py` 18、`pet_ui.py` 18、`skill_panel.py` 12、`app.py` 11、`asset_reference_images.py` 8、`asset_detail.py` 7、`local_previs.py` 7、`pet_models_ui.py` 7、`workflow_settings.py` 7 …
（备注：`width`／`height` 含 `Text`／`Canvas` 的布局尺寸，部分属布局而非纯视觉常量，迁移时需逐处判断，报告按「候选」计量。）

### 4) 现状门禁
- `tests/architecture/` 下**无** token／内联视觉常量专用门禁（仅有 `test_scrollbar_theme_boundary.py`）。规则 34（padx/pady、颜色、字号、圆角必须从 token 取值）当前**零自动化覆盖**。

## 建议（登记为后续 backlog，本轮不实现）
1. 先收口「双调色板」：让 `ui_theme.py` 复用 `ui_tokens.COLORS`（或反向合并为单一权威），消除第二套硬编码色；再逐页把 8 个业务文件的 111 处内联 hex 迁到 `COLORS`／语义色。
2. 新增 `tests/architecture/test_token_boundary.py` **棘轮门禁**：按文件冻结当前内联计数（hex／数字 padx-pady／数字字号），**只许减不许增**；权威（ui_tokens/ui_theme/ui_widgets/ui_icons）与 `skills/` 独立脚本入白名单。
3. padx/pady 与字号迁移按「单页粒度、一批一页」推进（对齐 R932–R960 卡片迁移节奏），**不与 hex 迁移混轮**。
4. 不建议一轮机械替换全仓库：数量大（111+213+189）、跨 40+ 文件，且色板须先统一。

## 结论
- 路线图 v1 §一 第 2 项「设计 token」尚**未收口**：业务页仍有 **111 处内联 hex（8 文件）**、**213 处数字 padx/pady（19 文件）**、**189 处数字字号/尺寸候选（32 文件）**，且 `ui_tokens`／`ui_theme` 双调色板并存、无专用门禁。
- 本轮只读，未改任何文件；已登记为 backlog（见 `project_status.md`「已知阻塞与待办」与 `.agent-handoff/backlog.md`）。

## 提交
- 本轮为只读诊断：结果文件＋状态页＋接力记录一次提交 **`7377586`**（7 files）。
