# tasks_round_4463_result — UX-CHAT-INPUT-EXTRAS 共享输入框自动接入／快捷答复／发送钮／占位与全阶段图标
<!-- round-evidence: {"commit_base": "1f66bd04d", "credential_hits": 0, "evidence_sha256": "2027003da558292b", "exit": 0, "failed": 0, "passed": 190, "round": 4463, "tests": "run_selftests.py -k shared_input shared_send skill_command desktop_idea_chat"} -->

- 本轮属于 §3.1 功能轮（UX-CHAT-INPUT-EXTRAS 卡面 W2；含解阻收尾：codex/sanhu-fix-1b 已合入 master，本车道快进至 1f66bd04d 后重算覆盖率基线、复跑双验收并提交）。
- 测试跑了吗、三个基线过了吗：跑了卡面 2 条验收命令，退出码均 0——定向 `run_selftests.py -k shared_input shared_send skill_command desktop_idea_chat`（190 条 0 红）；`smoke_test.py --architecture`（708 条 OK）。解阻后在新基线复跑结果见「提交状态」。
- 欠账少了吗：LOST-06／LOST-09／HALF-02 三条需求追溯由 ⬜ 转 ✅；架构门禁新增模块 4 类 UI 边界违规清零；覆盖率基线随新模块刷新（新基线 1f66bd04d 上 688→689）；未新增欠账。

## 轮次号说明

- R4450 回执报废：`.git/explicit-commit-receipts/R4450.json`（及 `.lock`）绑定旧基线 `66d8e67c4`；车道快进至 `1f66bd04d` 后 `dev.py commit` 按回执身份校验拒收。按仓内先例 `tasks_round_4274_result.md`（第 17-18 行）零删除原则，`R4450.json` 与 `R4450.lock` 保留原样未删，重新 `dev.py claim` 领得新号 **4463** 完成提交；R4450 号作废、仓内无对应结果文件。

## 开工核实（续跑接管）

- `git status --porcelain`：8 个已改文件＋1 个未跟踪 `ui/desktop_shared_input_extras.py`，与卡面现场一致，未回退任何有效改动。
- 行数上限：`desktop_shared_input.py` 1000、`desktop_shared_send.py` 999、`ui/desktop_shared_menus.py` 982、`ui/desktop_idea_chat.py` 987、`ui/desktop_shared_input_extras.py` 412（新模块），全部 ≤1000。
- S01 接线核实：`desktop_shared_send.host_options`（desktop_shared_send.py:986-988）向 `SharedStageInput` 注入 `continue_state` 回调，取 `box.desktop.idea_chat_controller`（真实控制器，desktop.py 建 `IdeaChatController()`）；`continue_state` 仅当 `stage=='script'` 且 `controller.can_continue` 为真给出续写文案（`continue_plan()` 键优先，否则默认「请从上次中断处继续」）。extras 默认回退 `_default_continue_state` 同样读该控制器，双路覆盖。

## 五项规格覆盖核对

1. **REQ-S01-114 统一占位**：`COMPOSER_BASE_PLACEHOLDER = '@引用文件，/快捷指令和 skill'`（desktop_shared_input_extras.py:24）；`stage_placeholder()`＋`PLACEHOLDER_TAILS`（:25-29,:64-67）；`desktop_shared_send.py:33-39` 派生 `STAGE_PLACEHOLDERS`/`DEFAULT_STAGE_PLACEHOLDER`/`STORYBOARD_PLACEHOLDER`，`sync_stage_placeholder` 接口不变。
2. **REQ-S01-113 图标一致性**：✦ `open_skill_list`→`SkillPickPanel`、＋ `open_add_menu`→`AddMenuPanel`、🎤 `_toggle_voice`→`VoiceInput`、发送→`send`→`host_options['on_send']`，全部 13 阶段共用同一 `SharedStageInput` 实例（`make_shared_input` 唯一建，desktop_shared_send.py:994-999；`set_stage` 换阶段）。非剧本阶段附件：`_attachments`（desktop_shared_send.py:932-943）仅 `script` 走 `choose_idea_attachments`，其余 `_say(ATTACHMENT_UNSUPPORTED)`；`SharedStageInput.open_attachments` 无回调兜底同文案（desktop_shared_input.py:897-901）。
3. **REQ-S01-112 自动接入**：`continue_state()` 读 `can_continue`＋`continue_plan()`；`_continue_muted` 机制点击即发即收，clear/切页/新发送收起。
4. **REQ-S01-112 快捷答复**：`QUICK_REPLY_LIMIT=3`，`quick_reply_rules` 纯本地规则表（不调模型不扫盘），胶囊点击只 `set_text` 不发送，输入即隐藏。
5. **REQ-S01-112 发送键**：`sync_send_art` 三态实心圆经 `element_photo`＋ui_tokens，`compound='center'`，样式名与 ICON_SEND/ICON_STOP 语义不变。

## 13 阶段图标盘点（REQ-S01-113 结果文件摘要）

`pet_bus.STAGES` 13 阶段（script 剧本准备／script_structure 剧本结构／storyboard 初步分镜／animatic 分镜预演／assets 资产管理／continuity 连贯性清单／final 分镜定稿／keyframe 首帧管理／previs 白模预演／video 视频生成／audio 配音与字幕／edit 后期剪辑／delivery 质检与交付）共用同一共享输入框实例与同一套面板实现：

| 图标 | 回调 | 面板／动作 | 阶段差异 |
| --- | --- | --- | --- |
| ✦ 技能 | `open_skill_list` | `SkillPickPanel`（desktop_shared_menus） | 无；勾选＝本阶段默认技能 |
| ＋ 添加 | `open_add_menu` | `AddMenuPanel`（desktop_shared_menus） | 附件项：仅 script 有链路，其余提示「本阶段暂不支持附件」 |
| 🎤 语音 | `_toggle_voice` | `on_voice`→`VoiceInput`（desktop_voice_input） | 无 |
| 发送 | `send` | `options['on_send']`→`desktop_shared_send.send` 分流 | 无 |
| 模型 | `StageModelPicker` | 内嵌下拉（stage_model_picker） | 无 |

## 改前红 → 改后绿

### 改前（架构门禁 6 红，均指向新模块 `ui/desktop_shared_input_extras.py`＋基线）

```
test_button_boundary.test_production_modules_use_semantic_buttons:
  {'ui\\desktop_shared_input_extras.py': [323, 238]}   # 裸 ttk.Button ×2
test_coverage_baseline.test_baseline_modules_exist_and_keep_production_scope: FAIL（新模块未登记）
test_coverage_baseline.test_coverage_tool_runs_on_bundled_interpreter: FAIL
test_native_control_boundary.test_colored_native_controls_only_decrease:
  ui/desktop_shared_input_extras.py: 2>0               # 自配色 tk.Frame/tk.Label
test_text_component_boundary.test_hand_styled_labels_only_decrease:
  desktop_shared_input_extras.py 有 1 处 > 登记 0      # 手写样式 tk.Label
test_token_boundary.test_numeric_padding_does_not_increase:
  {'desktop_shared_input_extras.py': 2}               # padx=(0, …) 字面量 0 ×2
```

### 修复（最小改动，全部在允许清单内）

- `ui/desktop_shared_input_extras.py`：续写条与快捷胶囊改用 `ui_widgets.SecondaryButton`＋`ttk.Frame/ttk.Label`；新增 `Composer.Notice.TFrame/TLabel` 样式承载 `primary_subtle` 底与 hint 字号（`ui/ui_composer_style.py:15-18`）；`padx=(0,…)`→`(SPACING['none'],…)`；移除 `FONTS` 导入；登记 `_layers.py` 同层边 `('desktop_shared_input_extras','ui_widgets')`。
- `维护记录/覆盖率基线.json`：按卡面用全部 15 核心目标重跑 `scripts\coverage_report.py` 刷新（195 条用例全绿，退出码 0）；解阻后在基线 1f66bd04d 上重跑，`modules_total` 688→689、`modules_covered` 134、未触达 555；`runbook.md` §11 两处口径同步（含派生句「555 个模块覆盖率 0」）。
- `test_shared_input_ui.py`／`docs/stages/S01_剧本准备.md`／`docs/specs/08_对话式交互与输出排版.md`：测试锚点由不存在的 `test_shared_input_stages`/`SharedInputExtrasStageTests` 更正为实际的 `test_shared_input_ui`/`ComposerExtrasTests`（文档准确性修正，无断言变更）。

### 改后

命令1 `run_selftests.py -k shared_input shared_send skill_command desktop_idea_chat` → 退出码 0：

```
共 190 条用例，166.9 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
ALL TESTS PASSED
```

命令2 `smoke_test.py --architecture` → 退出码 0：

```
Ran 708 tests in 247.076s
OK
✅ 架构治理测试：tests/architecture
```

## 测试契约有意变更说明（AGENTS §2.4）

发送键视觉契约按卡面明确变更：原「透明中心圆环底图、无 image」改为 `sync_send_art` 三态实心圆（`element_photo`＋`Tokens.Composer` token 色，`compound='center'` 居中 MDL2 字形；运行中 ICON_STOP 方块；禁用 `disabled_bg`/`disabled_text`）。样式名 `Tokens.Composer.Send.TButton`、ICON_SEND/ICON_STOP 字形切换、`send()` 点击语义、UX-INPUT-FLOW 防重发／Esc／IME 行为全部不变；`test_shared_input_ui.py` 相应用例的 docstring 已注明该契约变更，断言按新契约同步（圆形底图＋前景随态），非弱化。行为回归由 `ComposerExtrasTests` 三态用例＋既有 `SharedInputFlowDefectTests` 覆盖。

## 按推荐执行的待确认项

- 续写条／胶囊栏样式新增 `Composer.Notice.*` 两个 ttk 样式名（承载 primary_subtle 细条），属样式登记扩展而非新组件；视觉上与 DES-S01-112 描述的「primary_subtle 底细条」一致。
- `pady=SPACING['xs'] // 2` 沿用 token 派生写法（=2px，无更小 token），门禁不计数。

## 三个基线数

- 默认冒烟基线：`smoke_test.py`（无参）退出码 0，`通过：9 项／失败：0 项`（本轮实测）。
- 架构门禁当轮实际：708 条，失败集合改前 6 项 → 改后 0 项（本卡修复项全清，无新增红；复跑两次均 OK）。
- 全量回归 `--all --safe`：未跑（分支车道不累计；`full-safe-receipts.json` 无本卡新增欠账记录）。

## 提交状态

- `dev.py claim` → 轮次号 **4463**（R4450 回执报废后重新领取，见「轮次号说明」）。
- 首次 `dev.py commit`（R4450）曾被车道范围门禁拒绝：`codex/sanhu-fix-1b`（R4447+R4454）未合入改动与 `runbook.md`／`维护记录/覆盖率基线.json` 同字段真实冲突。该分支其后已合入 master（R4458 `1f66bd04d`），本车道快进至该基线，冲突消除。
- 解阻收尾（本次）：在基线 `1f66bd04d` 上以全部 15 核心目标重跑 `scripts\coverage_report.py` 刷新 `覆盖率基线.json`（195 条用例全绿、退出码 0；134/689 被触达、555 未触达），同步 `runbook.md` §11；复跑两条验收命令均退出码 0（定向 190 条 0 红 22.0 秒；架构门禁 708 条 OK）。
- R4450 提交回执 `.git/explicit-commit-receipts/R4450.json` 绑定旧基线 `66d8e67c4`，快进后 `dev.py commit` 拒收；按 R4274 先例保留回执不删，改领 R4463 提交（见「轮次号说明」）。
- 提交命令（本轮执行）：
  `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4463: UX-CHAT-INPUT-EXTRAS 共享输入框自动接入/快捷答复/发送钮/占位与全阶段图标" desktop_shared_input.py desktop_shared_send.py ui/desktop_shared_input_extras.py ui/ui_composer_style.py tests/architecture/_layers.py tests/test_shared_input_ui.py docs/stages/S01_剧本准备.md docs/specs/08_对话式交互与输出排版.md docs/records/对话需求追溯.md 维护记录/覆盖率基线.json runbook.md tasks_round/tasks_round_4463_result.md --tests shared_input shared_send skill_command desktop_idea_chat`
- 机器证据：`tasks_round/evidence/R4463.json` 与结果文件头 `round-evidence` 行由 `dev.py commit` 自动生成／盖章；commit hash 以 `git log` 为准。

## 没有验证的地方

- 真实桌面可视核验（续写条出现时机、胶囊点击填入、发送键圆形观感）未人工看屏；由 Tk 隐藏桌面单测断言几何与文案覆盖。
- `continue_state` 在真实中断会话中的端到端链路（controller.can_continue 由上游流状态驱动）未做真实模型调用验证；单测以假 controller 覆盖判定分支。
- GUI_DEFERRED 未出现；Tk 测试经隐藏桌面自包装运行。
