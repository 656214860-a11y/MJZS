# R3264 结果 · U6 字体／原生控件／表单控件三门禁
<!-- round-evidence: {"commit_base": "ba80086d", "credential_hits": 0, "evidence_sha256": "21eda4f07f8c34f9", "exit": 0, "failed": 0, "passed": 11, "round": 3264, "tests": "run_selftests.py -k font_boundary native_control_boundary form_control_boundary"} -->

- 轮次类型：功能轮（UI 统一组件标准任务书 U6，以门禁为主，D5/D6 契约）。
- 三问：测试跑了；三个新门禁合计 11/11 全绿、`smoke_test.py --architecture` 532 条实测 531 绿 1 红（`test_round_number_continuous` 为分支侧结构性红：`project_status.md` 仅 master 可提交、本分支停在 3214，合并主干后自解，与 R3252/R3261 记录同源）、默认冒烟 9/9。欠账口径：本轮新增三门禁的存量冻结清单（只减不增），未做批量迁移（D6）。
- 领号说明：`round-claims.json` 中 R3262 亦登记本工作树但无结果文件与提交（疑为同步轮期间的重复领号），本轮使用后领的 R3264；孤儿领号不产生提交，不影响门禁。

## 改动

- 新门禁 `tests/architecture/test_font_boundary.py`（AST 口径，`production_files_recursive`）：
  - `font_debt`：`font=` 关键字值子树或 `*FONT` 赋值目标值子树内含 `tuple`/`list` 字面量各计 1；`font=FONTS[...]`、`font=ICON_FONT` 等取值式不算。
  - 存量冻结 `FONT_BASELINE`＝**11 处/6 文件**：`asset_reference_images.py`×1、`desktop.py`×2、`ui/desktop_idea_bubbles.py`×2、`ui/pet_cloud.py`×2、`ui/ui_part_renderers.py`×2、`ui/ui_stage_popups.py`×2。
  - 豁免 AUTHORITY 六件（`ui_tokens`/`ui_theme`/`ui_widgets`/`ui_splash`/`ui_tooltip`/`ui_icons`，与 `test_token_boundary` 同口径）。
- 新门禁 `tests/architecture/test_native_control_boundary.py`：
  - `native_color_debt`：`tk.Label`/`tk.Frame` 构造（`tkinter.` 限定与裸名同罪，`ttk.*` 不在此列）关键字含颜色类选项（`bg/fg/background/foreground/highlight*/insertbackground/select*/disabledforeground/active*`）的处数。
  - 存量冻结 `NATIVE_BASELINE`＝**63 处/13 文件**：`app.py`×4、`cell_hover.py`×3、`desktop.py`×6、`desktop_shared_input.py`×2、`ui/desktop_file_card.py`×2、`ui/desktop_idea_bubbles.py`×5、`ui/desktop_page_nav.py`×2、`ui/desktop_shared_menus.py`×14、`ui/pet_cloud.py`×5、`ui/stage_model_picker.py`×13、`ui/ui_popup.py`×2、`ui/ui_status_bar.py`×4、`ui/ui_usage_indicator.py`×1。AST 无法圈定「浮层与卡片内」，按全仓棘轮冻结；集中处与任务书 §3.2-5 核实的浮层内部结构一致，按 D6 不迁移。
- 新门禁 `tests/architecture/test_form_control_boundary.py`：
  - `form_debt`：`Checkbutton`/`Radiobutton`/`Scale`/`Spinbox`/`Notebook`/`Listbox` 构造各计 1 的三类——① `tk.`/`tkinter.` 限定或裸名（无样式通道）；② `ttk.` 带外观关键字（颜色/`relief`/`borderwidth`/`padx`/`pady`/`highlight*`/`selectcolor`/`active*`/`troughcolor`/`sliderrelief`/`buttoncolor`/`readonlybackground`/`disabledforeground`，`font` 归字体门禁）；③ `ttk.` `style=` 取非字面量或字面量不在 `ALLOWED_STYLES`（ttk 内建 ∪ `ui_theme`/`ui_widgets`/`ui_composer_style` 经 `configure`/`map`/`layout` 登记名，导入时实测收割）。
  - `style_config_debt`：`.configure`/`.map`/`.layout` 首参命中表单控件样式名子串的局部样式改写，存量为零、新增即红。
  - 存量冻结 `FORM_BASELINE`＝**5 处/5 文件**，全部 `tk.Listbox` 原生控件：`ui/asset_reference_import.py`、`ui/desktop_writing_snapshots.py`、`ui/script_outline.py`、`ui/skill_panel.py`、`ui/skill_panel_import.py`。
- `architecture.md`「当前架构门禁清单·体验与布局」补登三门禁名。
- `ui_components.md` 表单控件存量表述修正为实测口径：冻结清单为上述 5 处 `tk.Listbox`；`ui_hitl` 的 `ttk.Radiobutton` 与 `ui_param_panel` 的 `ttk.Scale` 无外观选项、样式经主题继承，属合规不在冻结清单（U0 文档先行时的旧表述一并校正）。
- 三门禁均含坏样本自审：谓词级 canary（违规样本必须命中、合规样本必须放行）＋临时目录跑真实门禁方法的 self-audit，新增违规用例 `test_new_*_violation_is_rejected` 三个齐全。

## 验证

- `python -B -m unittest tests.architecture.test_font_boundary tests.architecture.test_native_control_boundary tests.architecture.test_form_control_boundary` → **11/11 绿**（canary＋冻结比较＋新增违规拒绝＋局部样式改写零容忍）。
- `python -B smoke_test.py --architecture` → **532 条，531 绿、1 红**；唯一红 `test_round_number_continuous`（`project_status.md` 当前轮次 3214 ≠ 最新结果 3261+1）为分支侧结构性欠账：状态页仅 master 可提交，合并主干写状态后自解，与 R3252/R3261 结果文件记录的同一红项一致；本轮新增三门禁 11 条全部在其中实测通过。
- `python -B smoke_test.py` → **9/9 绿**。
- 存量冻结口径（AST 实测 vs 任务书作者正则估计，差异如实记录、不为凑数调口径）：
  - 字体：作者约 10 处/6 文件 → 实测 **11 处/6 文件**；多 1 处为 `ui/pet_cloud.py` 的 `configure(font=FONT if ... else (FONT[0], STICKER_FONTS[0]))` 三元表达式内嵌元组，AST「值子树含元组」计入，作者正则口径未必覆盖。
  - 原生控件：作者 `tk.Label` 44＋`tk.Frame` 30＝约 74 处 → 实测 **63 处/13 文件**；正则把 `ttk.` 限定与非颜色选项计入，本门禁只认 `tk` 原生接收者＋颜色类选项。
  - 表单控件：作者 25 处/11 文件为 Checkbutton/Radiobutton/Scale/Spinbox/Notebook **全部使用点**（含合规），另记 `Listbox` 3 处 → 本门禁只计违规：全部使用点中 `ttk.` 控件无外观选项、样式经主题继承或显式 `style='TCheckbutton'` 等已登记名，属合规不计债；实际冻结仅 **5 处 `tk.Listbox` 构造点/5 文件**（作者 3 处为使用点口径差异，构造点实测 5）。
- 未运行：`run_selftests.py --all --safe`（本轮无生产 `.py` 改动，仅新增架构测试与文档；§5 全量触发条件不满足，master 提交点累计计数由主干侧判定）。

## 基线与欠账

- 字体内联元组冻结 **11 处/6 文件**；自配颜色原生控件冻结 **63 处/13 文件**；表单控件违规冻结 **5 处/5 文件**（另 `style_config_debt` 零容忍基线=0）。三门禁均「只减不增、不许新增文件」，豁免文件与 `test_token_boundary` AUTHORITY 同口径。
- 存量均未迁移（D6「谁改谁迁」）；各门禁已知 AST 盲区（类别名接收者、实例级 `configure` 改写、变量间接传参）已写入测试文件头。
- `project_status.md` 欠账无变化（仅 master 可提交）。

## 提交

见 git log（`codex/wip-R3241`）。
