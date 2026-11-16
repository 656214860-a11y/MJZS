# R2964 结果：共享输入框模型选择器改版——无外框触发钮＋上方卡片浮层（对齐 DeepSeek Harness／Devin Desktop）
<!-- round-evidence: {"commit_base": "25a12c55", "credential_hits": 0, "evidence_sha256": "a7738ea43aa5102c", "exit": 0, "failed": 0, "passed": 789, "round": 2964, "tests": "run_selftests.py -k test_shared_input_ui test_shared_input_stages test_stage_reasoning test_skills pet_ui"} -->

## 三问

1. **轮次类型**：功能轮（§3.1；先改 `docs/stages/S01_剧本准备.md` REQ-S01-82／DES-S01-82，再改码与测试）。
2. **测试跑了吗、三个基线过了吗**：跑了。默认冒烟 **8/8 绿**；`smoke_test.py --affected stage_model_picker desktop_shared_input ui_composer_style` 门禁定向 **789 条用例 0 红**（5 个测试文件：test_pet_ui、test_shared_input_stages、test_shared_input_ui、test_skills、test_stage_reasoning）；真 Tk 探针实测浮层几何（见下）。架构门禁未单独跑（本轮只动 L4 表现层与既有 L4 消费方，无分层/契约变更；`--affected` 门禁已含相关回归）。全量 `--all --safe` 未跑（合入 master 前按凭据口径执行）。
3. **欠账少了吗**：本轮无新增欠账；消除一处历史欠账——旧 `ttk.Menubutton`＋`tk.Menu` 在输入框贴底时被系统翻转方向、盖住按钮本体，且单击存在误触尾项直开模型管理的反馈（用户实测四条修复点全部闭环）。

## 用户四条修复点 → 落点

| 用户反馈 | 落点 |
|---|---|
| 1. 去除文字外框 | 触发钮改 `ttk.Button`＋新样式 `Tokens.Composer.Model.TButton`（`ui/ui_composer_style.py`）：卡片底同色背景、无边框，悬停/按下才透出 `surface_hover`/`surface_pressed` 圆角底；文案＝模型名＋`▾`（超长按 `MODEL_LABEL_MAX_CHARS=24` 截断）。 |
| 2. 点击后卡片盖住原按钮，应上面一行弹出 | 弃用 `tk.Menu`，改 `ui_popup.Flyout` 卡片浮层：`_place_popup` 锚定按钮正上方、右缘对齐，底边留 `SPACING['xs']` 净距；上方放不下退回按钮下方，`monitor_bounds` 按显示器工作区钳位。探针实测：按钮 top=458、浮层 bottom=454（净距 4px），不遮挡。 |
| 3. 距发送按钮太近 | `desktop_shared_input.py` 模型选择器 pack 右侧 `padx` 由 `(sm, none)` 改 `(sm, md)`，与发送键视觉间距由 ~4px 拉开到 ~16px。 |
| 4. 单击误开模型管理页 | 浮层只在点「+ 添加模型…」尾行才 `open_model_manager()`；模型行/推理档/点外部/Esc 均不触发。`choose_model`/`choose_reasoning` 仍只写各自字段（`stage_config.put` 边界不变）。 |

## 本轮交付

| 文件 | 内容 |
|---|---|
| `程序/stage_model_picker.py` | 重写（约 460 行）：`StageModelPicker` 公共 API 全保留（`refresh_models`/`set_model`/`set_model_label`/`model_id`/`choose_model`/`choose_reasoning`/`save`/`open_model_manager`/`labels`/`groups`/`model`/`_by_display`/`_items`/`_capable`/`_level`）。新增 `_popup_spec()` 纯数据视图（模型行→分隔→推理等级四档→分隔→添加模型尾行）、`_fill_popup` 渲染（模型行走 `ScrollForm` 滚动区、推理区与尾行钉在下方，上限 `POPUP_MAX_MODEL_ROWS=10` 行）、`_place_popup` 定位、主窗 `<Button-1>`/`<Escape>` add 绑定点外部关闭（选中/关浮层时精确 unbind）。推理点档原地 `_fill_popup`+`_place_popup` 刷新徽标。 |
| `程序/ui/ui_composer_style.py` | 新增 `Tokens.Composer.Model.TButton` 无框触发钮样式（token 取值：`FONTS['body']`、`COLORS`、`SPACING`，无魔法数字/内联色）。 |
| `程序/desktop_shared_input.py` | 仅模型选择器 pack 右 padx `none→md`＋注释更新。 |
| `程序/docs/stages/S01_剧本准备.md` | REQ-S01-82／DES-S01-82 改写为无外框钮＋上方卡片浮层契约（文档先行）。 |
| `程序/tests/` ×4 | `test_shared_input_ui.py`、`test_ui_edges_pages.py`（2 处）、`test_skills.py`（2 处）、`test_stage_reasoning.py`：选择器断言由 `ttk.Menubutton`/`tk.Menu` 契约同步为 `ttk.Button`＋`_popup_spec()` 数据契约；行为断言（模型名无前缀、推理徽标、四档、尾项添加模型、持久化隔离）原样保留。 |

## 测试契约变更说明（§2.4）

- `ttk.Menubutton`→`ttk.Button`、`tk.Menu`→`ui_popup.Flyout` 属有意 UI 契约变更；测试定位改到 `picker.models`（按钮）与 `picker._popup_spec()`（浮层行规格，纯数据可断言），未弱化任何行为断言。
- 新增等价覆盖：浮层尾项 `kind=='add'`＋`ADD_MODEL_LABEL`；推理 spec 四档值与当前档标记；模型行 `badge` 仅能力模型有值。

## 验证记录

- `smoke_test.py`（默认）：**8/8 通过**。
- `smoke_test.py --affected stage_model_picker desktop_shared_input ui_composer_style`：检查项 9/9＋门禁定向 `run_selftests.py -k stage_model_picker desktop_shared_input ui_composer_style`（自动扩到 test_pet_ui/test_shared_input_stages/test_shared_input_ui/test_skills/test_stage_reasoning）**789 条 0 红**，最终代码复跑同绿。
- 定向补跑（padx 修复后）：`-k stage_reasoning shared_input_ui test_skills` 158 条 0 红。
- 真 Tk 探针（临时脚本，非入库）：按钮 98×29 显示「自动 ▾」；`toggle_popup` 后浮层 388×352、底边在按钮顶边上方 4px、不遮挡；点外部关、重开、Esc 关均验证；spec 尾部为 分隔→推理等级→分隔→+ 添加模型…。
- 过程中发现并修复一处真实 bug：`_model_row` 模型名 Label 误用 `padx=(a,b)` 元组（tk 部件选项只收标量）→ 改 `padx=SPACING['sm']`，探针渲染验证通过。

## 过程损耗（如实）

- 功能工作树环境补齐（与 R2939 同法）：本工作树缺 3 个人工检出的技能嵌入仓（gitlink、无 `.gitmodules` 映射），从主工作区整体复制：`skills/00全流程SKILL/AIGC创作全流程`、`skills/01 剧本准备SKILL/剧本锻造`、`skills/01 剧本准备SKILL/编剧技能集`。未补时 `test_skills` 注册表计数 71≠73（环境差异，非代码回归）；补齐后 73/73 全绿，`git status` 无新增噪声（gitlink 内容不入父库）。
- 主工作区同 commit（25a12c55）上 `test_ui_edges_pages` 有 2 条既有红（`script_structure_info_label` justify 断言、video 页 `show_back` pack 错误），与本改动无关（未触碰相关模块），已在主工作区复现确认，记录为既有欠账不扩大处理。
- 分支协调提示：`branch_scope` 曾报与活跃分支 `codex/wip-R2958` 在 `desktop_shared_input.py` 有范围重叠；本轮该文件仅改 pack padx 一处，合并时留意。

## 基线数

- 默认冒烟：8/8。
- `--affected` 门禁当轮实测：789 条用例 0 红（5 文件）。
- 架构门禁：未单独跑（无分层/契约变更）；全量 `--all --safe` 未跑，欠账口径以 `full-safe-receipts.json` 为准。

## 下一步

- 合入 master 前按 §5 由合并轮决定是否补 `--all --safe`。
- `codex/wip-R2958` 若也改 `desktop_shared_input.py`，合并时对齐 padx/布局改动。
