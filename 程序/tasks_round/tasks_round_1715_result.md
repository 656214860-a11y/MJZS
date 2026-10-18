# R1715：结构治理轮·执行（UI 批次 7）——设置与模型窗：统一表单网格、底部动作区、错误不锁屏

## §7 三问

1. **本轮属于 §3 哪种类型？** 结构治理轮·UI 批次 7（执行）。范围严格限于任务书允许的 `pet_settings_ui.py`、`pet_models_ui.py`、新增测试、本结果文件与 `工作流任务\probe_ui7\`。按 `RUI_common.md` 未认领轮次、未改 `project_status.md`／`AGENTS.md`／`architecture.md`／`skills/`，**未执行任何 git 写命令**（只读 `git status`／`git diff`）。验收与提交由 Claude 完成。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8 通过**；`smoke_test.py --affected pet_settings_ui pet_models_ui` **9/9 通过**（定向 0 文件红）；任务书验收命令 **770 条、74.3 秒、3 个工作单元有红（4 条）**，其中 3 条来自并行批次的 `desktop.py`／`desktop_storyboard_page.py`／`pet_ui_support.py`，另 1 条 `test_typing_model_id_automatically_searches_after_debounce` 是 8 路并行 GUI 争用下的时序偶发（单独串行复跑 1/1 绿，见 C）；本批新增 `test_ui_batch7_settings_models` **10/10 全绿**，`test_pet_settings` 55/55、`test_token_saver` 87/87、`test_model_pool`／`test_client_profiles`／`test_layers`／`module_size_ratchet` 全绿。按共用规矩**未跑** `--architecture` 与 `--all --safe`；架构门禁未运行，不填数字。
3. **project_status.md 的欠账少了吗？** 没有。本批不改状态页、不领轮次；若由 Claude 提交，按源码轮计一次全量欠账，由验收方统一记账。

## A 现状核对（先读源码与审计，再改）

- **审计算口径**：`UI设计评审报告.md` §4 记 `pet_settings_ui` pack 50／grid 21，§5 把本批定为“统一 chrome、表单列宽、保存/取消位置；错误不锁屏”，§6 明确“不一次性删除 chrome=False”。
- **`pet_settings_ui.py`**：外壳（标题/说明/分页按钮/页面栈/底栏）用 `pack`；基础功能、预算、Token、开发信息四页各自用独立 `grid`，标签列没有固定宽，输入框只 `sticky='w'`（预算 `width=16`、Token `width=14`、免打扰 `width=3`）。设置窗底栏只有“关闭”，没有窗口级保存；预算/Token 页各有自己的“保存”，位置在页内左／左。
- **`pet_models_ui.py`**：`settings_page` 已用 grid，但标签列宽随文字变化、输入框只 `sticky='w'`，状态列 `wraplength=280`；`open_manager` 表单同样没有固定标签列，且自定义了 `ModelManager.TEntry` 样式（字号/内边距覆写，违反样式唯一入口）。动作区原顺序：`重置`（最右）→`保存`→`关闭`，`关闭`压在主按钮右侧；模型管理为 `关闭`（最右）→`保存这条`。
- **错误反馈**：两个文件里没有 `messagebox`／`error()` 调用，失败一律写 `hint`（StringVar）；也就是说本批不存在“模态锁屏”实际调用，但也没有统一错误入口。仓库中**没有模块级 `ui_widgets.error()`**，只有 `NotificationDispatcher.error()`（默认 `modal=False`）和 `notify()`（默认 `modal=True`）。本批用 `NotificationDispatcher(hint).error()`，见 D-1。
- **已有测试约束**：`test_pet_settings` 钉住 `_pet_entries`／`_pet_api_controls`／`_pet_program_row`／`_pet_manager_hint_label` 的样式、`test_token_saver` 钉住 Token 页必须有“保存”按钮，因此本批**不改测试**，只把按钮位置与列宽调整到约束之内。

## B 改动（逐文件）

### `程序\pet_models_ui.py`（894 行，< 1500）

- 新增 `form_column_width(labels)`：以 `FORM_LABEL_WIDTH`（令牌字符宽）为下限，再用令牌字体 `FONTS['body']` 实测每个标签，计入与输入列之间的 `SPACING['md']`，返回整个窗口共用的标签列宽。设置窗与模型管理窗都改用它，输入列落在同一条竖线上。
- 新增 `report_error(hint, message)`：`NotificationDispatcher(hint).error(str(message))`，`modal` 保持默认 `False`；模型检测、保存失败、删除回读失败等可恢复错误改走它；删除模型仍走 `pet.confirm_start` 模态确认。
- `window(pet, title, geometry, minsize=None)` 增加最小尺寸参数；`open_settings` 用 `SETTINGS_MIN=(620,430)`，`open_manager` 用既有 `MANAGER_MIN=(820,620)`。两窗的动作区都**先 pack 到底边**，窗口被压矮时只压缩列表／表单。
- `settings_page(..., label_width=None, show_save=True)`：内容区改为 `actions`（底边先占）＋`body`（grid）；`body.columnconfigure(0, minsize=...)`，四个任务下拉改 `sticky='ew'`。
- `open_manager`：`window(...)` 返回 `card`，内部再分 `footer`（pack 底边）＋`body`；表单 `form.columnconfigure(0, minsize=form_column_width(MANAGER_FORM_LABELS))`，所有单行输入 `sticky='ew'`；删除 `ModelManager.TEntry` 自定义样式，统一走 `LineInput` 默认样式（字号/内边距回到 `ui_widgets.setup_styles()`）。
- 动作区顺序统一为**主操作最右、取消紧挨其左**：
  - `settings_page`：`保存` 先 pack `right`，`关闭` 再 pack `right`，`重置` 最后 pack `right`；测试／小样本留在左边。
  - `open_manager`：`保存这条` 先 pack `right`，`关闭` 再 pack `right`；新建／测试／删除留在左边。
- 令牌化：`wraplength=620/860/280/640` → `TEXT_DESC['wraplength']`／`TEXT_HINT['wraplength']`；`padding=(0, xs)`、`padx=(0, xs)` 等 → `SPACING['none']`；密钥框宽、表格行高等收为模块常量 `SECRET_FIELD_WIDTH`。

### `程序\pet_settings_ui.py`（672 行，< 1500）

- 新增 `HUB_MIN=(760,560)`；`open_hub` 设置最小尺寸，并把**底部动作区先 pack 到底边**：`保存`（Primary，最右）＋`关闭`（Secondary，紧挨其左）。`save_current(win)` 把保存委托给当前页的 `save`（模型／预算／Token）或 `apply`（自动化等级）；基础功能／开发信息这类自动生效的格子只提示“不用再保存”。
- 新增 `label_width()`/`FORM_LABELS`：设置窗所有页共用同一标签列宽（含模型配置页任务标签）；各页 `grid.columnconfigure(0, minsize=...)`，输入列 `sticky='ew'`。
- `basic_page`／`budget_page`／`token_page`／`dev_page`／`level_page` 接受可选 `width`；`token_page`／`budget_page` 增加 `show_save`：单独使用（既有测试）保留页内“保存”，嵌进设置窗时由底部动作区统一承担，避免两个“保存”并排。
- `cost_reconciliation_dialog`：表单改「标签列固定宽＋输入列伸缩」的 grid；动作区改用 `BaseDialog.actions`（保存核对结果最右，导入旧账／选择凭据在左）；错误走 `_error()`。
- 令牌化：`wraplength=780/700/650/600/560` → `TEXT_DESC['wraplength']`；`padx/pady` 的 `0` → `SPACING['none']`；`width=3/14/16/30/75`、`height=11` 收为命名常量（`DND_FIELD_WIDTH`、`TOKEN_FIELD_WIDTH`、`BUDGET_FIELD_WIDTH`、`COST_CHOICE_WIDTH`、`TOKEN_PREVIEW_*`）。

### 新增 `程序\tests\test_ui_batch7_settings_models.py`（10 条，docstring 含「UI 批次 7」）

真 Tk、空 `tempfile` 项目根，不打开用户项目、不读 `private/`、不发请求：

1. 模型设置单独窗：`保存` rootx **大于** `关闭`，主/次按钮样式正确；
2. 模型管理窗：`保存这条` rootx **大于** `关闭`；
3. 设置窗最小尺寸 760×560：底部保存/关闭 `mapped=1` 且不越出窗口底边，保存仍在关闭右边；
4. 模型管理最小尺寸 820×620：动作区同样可见；
5. 设置窗预算页与模型页输入列 x 相同（切页不跳列）；
6. 设置窗模型页四个下拉左边缘同一 x；
7. 模型管理输入列六个控件左边缘同一 x；
8. 标签列宽由 `FORM_LABEL_WIDTH` 派生（非手写像素）；
9. 模型保存失败走 `NotificationDispatcher.error` 且 `modal` 非 True；
10. 预算保存失败走同一入口且非模态。

## C 验证与截图

### 本轮实跑（真实输出，非历史凭据）

| 命令 | 实际结果 |
| --- | --- |
| `python -B run_selftests.py -k test_ui_batch7` | **10 条、0 红**（约 9 秒） |
| `python -B run_selftests.py -k test_pet_settings` | **55 条、0 红** |
| `python -B run_selftests.py -k token_saver` | **87 条、0 红** |
| 任务书验收命令 `-k pet_settings pet_models model_pool test_client_profiles test_pet_ui test_layers function_size_ratchet module_size_ratchet test_ui_batch7` | **770 条、74.3 秒、3 个工作单元有红（4 条）**；`test_ui_batch7` 10/10、`test_pet_settings` 55/55、`test_model_pool`／`test_client_profiles`／`test_layers`／`module_size_ratchet` 全绿；`test_token_saver` 为另行复跑 87/87；红项见下 |
| `python -B smoke_test.py` | **8/8 通过** |
| `python -B smoke_test.py --affected pet_settings_ui pet_models_ui` | **9/9 通过**，定向 0 文件红 |
| `--architecture`／`--all --safe` | **未运行**（按 `RUI_common.md` 留给 Claude） |

**验收命令的 4 条红（3 条非本批文件，1 条并行 GUI 争用偶发）**

1. `architecture.test_function_size_ratchet::test_no_function_exceeds_its_cap`：`desktop_storyboard_page.py::storyboard 324 行 > 上限 323`；该文件当前由其他批次修改，不在本批允许范围。
2. 同文件 `::test_registry_tracks_real_sizes`：`desktop.py::__init__ 实际 132 行，已不超限，请从登记表删除`；`desktop.py` 当前由其他批次修改，本批未改。
3. `test_pet_ui::CaptionTests::test_the_caption_is_black_ink`：`pet_ui.CAPTION_INK` 为 `#1F2937`，断言仍期待 `#000000`；来自并行批次的 `pet_ui_support.py`（`CAPTION_INK = COLORS['text_primary']`），本批未触碰 `pet_ui*`。
4. `test_pet_ui::ModelPoolTests::test_typing_model_id_automatically_searches_after_debounce`：8 路并行 GUI 争用下 600ms 等待窗内没等到 `after(450)` 的自动搜寻结果（期望 `C:/apps/Gemini.exe`，实际空）。**该用例单独串行复跑 1/1 通过**（1.263 秒，命令 `PYTHONPATH=程序;程序\tests python -B -m unittest tests.test_pet_ui.ModelPoolTests.test_typing_model_id_automatically_searches_after_debounce`）；本批未改该测试或 `after` 节奏，`run_selftests` 日志无 `SUSPECT_CONCURRENCY` 标记但同一轮其他批次的 `pet_ui*` 正在改文件，按共用规矩不反复重跑，交 Claude 在干净树复验。

> 另主动跑了 `test_token_boundary`、`test_card_boundary`、`test_button_boundary`、`test_input_boundary`、`test_combobox_boundary`、`test_dialog_boundary`、`test_data_table_boundary`：**93 条、2 文件红**，红项为其他批次的 `desktop.py`（`test_data_table_boundary` 项目选择 Treeview 计数）与本批无关；`token_boundary`（本批两文件 0 内联 hex、0 数字 padx/pady）、`card_boundary`、`button_boundary`、`input_boundary`、`combobox_boundary`、`dialog_boundary`、`test_layers`、`module_size_ratchet` 全绿。

### 几何证据（`工作流任务\probe_ui7\geometry_ui7.json`，空临时项目）

- 设置窗 880×620：`保存` x=742、`关闭` x=616（保存更靠右）；预算输入列 x=**151**；模型页四个下拉 x=**151**（同窗同竖线）。
- 模型管理 1180×860：`保存这条` x=1214、`关闭` x=1088；六个输入控件 x=**379**。
- 设置窗最小 760×560：保存/关闭 `mapped=1`，y=530、高 33，窗口底 591；模型管理最小 820×620：保存/关闭 `mapped=1`，y=770，窗口底 831。
- 模型设置单独窗 700×430：`保存` x=562、`关闭` x=436。

### 截图（均用 `tempfile.mkdtemp()` 空项目根＋空程序根，未读真实密钥）

- `工作流任务\probe_ui7\settings_hub.png`：设置窗（预算页，880×620；表单列对齐，底部“关闭”左、“保存”右）。
- `工作流任务\probe_ui7\model_manager.png`：模型管理窗（1180×860；模型池空态，表单列对齐，底部“关闭”左、“保存这条”右）。
- 探针与原始输出：`show_ui7.py`、`capture_window.ps1`、`layout_probe.py`、`geometry_ui7.json`、`run_selftests_ui7.log`、`smoke_ui7.log`、`smoke_affected_ui7.log`。

## D 断言未动与需裁决事项

**断言未动**：未修改任何既有测试文件、断言或期望值，未加 skip；只新增 `tests/test_ui_batch7_settings_models.py`。

1. **`ui_widgets.error()` 不存在**：`RUI_common.md` 写“`ui_widgets.error()` 默认已是 `modal=False`”，但当前树只有 `NotificationDispatcher.error()`（默认 `modal=False`）与 `notify()`。本批用前者并显式不传 `modal=True`，未改共用文件。若 Claude 希望统一为模块级 `error()`，需在共用文件另开一批。
2. **底部“保存”的语义**：设置窗底部新增窗口级“保存”，当前页有 `save` 就委托（模型／预算／Token），自动化等级页委托 `apply`，基础功能／开发信息这类自动生效的格子只写提示“不用再保存”。这是本批的动作区统一做法；若产品希望这两种格子把按钮置灰，请裁决（不影响现有断言）。
3. **最小尺寸与 `ui_theme.place()`**：本批给设置窗/模型窗设了 `minsize`，但 `ui_theme.place()` 在弹窗首次映射时会统一改成 `DIALOG_MIN_WIDTH/HEIGHT`（240×160），会覆盖页面声明的最小值。本批仍把动作区先 pack 到底边，160 高时优先保留动作区；若要求真实最小 760×560／820×620，需要改 `ui_theme`（共用文件，本批未改）。
4. **仍是旧 `chrome=False` 的窗口**：`pet_settings_ui.open_hub`、`pet_models_ui.window`（`open_settings` 与 `open_manager` 共用）仍是旧式无标题栏浮窗，本批按审计 §6 不迁移，只统一了底部动作区。`cost_reconciliation_dialog` 本轮改用标准 `BaseDialog` chrome 的 `content/actions`。
5. **建议新增令牌（本批未改 `ui_tokens.py`，留 Claude 统一补）**：
   - `FORM_LABEL_GAP = SPACING['md']`：标签列与输入列的统一间距（本批在 `form_column_width()` 内用 `SPACING['md']`）。
   - `SETTINGS_MIN_WIDTH/HEIGHT = 620/430`、`HUB_MIN_WIDTH/HEIGHT = 760/560`：设置窗与模型设置窗的最小尺寸；`MANAGER_MIN=(820,620)` 已有。
   - `FIELD_WIDTHS` 组：`DND=3`、`TOKEN=14`、`BUDGET=16`、`SECRET=30`、`COST_CHOICE=75`（字符宽，仅作占位）。
   - `TOKEN_PREVIEW_COLUMNS=92`、`TOKEN_PREVIEW_LINES=11`、`MODEL_TABLE_ROWS=20`：Token 预览与模型池表高度。
   - `TEXT_NOTE`（建议 `wraplength=780`）：本批把设置窗总说明从 780 改成 `TEXT_DESC['wraplength']=560`，说明折成两行；若产品希望更宽的单行说明，需补这个令牌。
6. **模型管理表单行号**：`open_manager` 仍沿用既有 `api_rows={4,5,6,7}` 的 grid 行号来收集 API-only 控件，`program_label/program_row` 复用行 4（API 模式下隐藏）；本批只加列宽与令牌，未重排行号，`_pet_api_controls`／`_pet_program_row` 的既有测试继续通过。
7. **`open_manager` 棘轮余量为 0**：`architecture.test_function_size_ratchet` 登记上限 497，实测 497（本批未加高上限，也未拆分到 150 以下）。后续任何新增都要先拆函数或压缩行数，不能抬上限。
8. **模块行数**：`pet_models_ui.py` 894 行、`pet_settings_ui.py` 672 行，均低于 1500；新增函数均 < 150 行。

## E 交付状态

**未提交，由 Claude 验收后提交。** 本批未执行任何 git 写命令；工作树中 `app.py`、`desktop.py`、`desktop_asset_pages.py`、`desktop_media_pages.py`、`desktop_script_pages.py`、`desktop_storyboard_page.py`、`keyframe_comfy.py`、`pet_cloud.py`、`pet_ui.py`、`pet_ui_support.py`、`pet_ui_view.py`、`reference_wall.py`、`skill_panel.py`、`skill_panel_support.py`、`white_model.py` 及其他 `tasks_round_pending_UI*`／`test_ui_batch9_*` 属于并行批次，未触碰、未回退。

## F 收尾（RUI7b）

### F.1 改动

- `程序\pet_settings_ui.py`（672 → 690 行）
  - 新增 `save_handler(page)`（第 75-82 行）：按 `save` → `apply` 的顺序返回这一页的保存入口；`save_current()` 改用它，保存行为与提示文案不变。
  - `open_hub`（第 120-123 行）：窗口级「保存」创建后先 `state(['disabled'])`（此时还没有选页）。
  - `select`（第 184-190 行）：按目标页的 `save_handler` 结果切换 `state(['!disabled'])`／`state(['disabled'])`——基础功能、开发信息置灰；模型配置、自动化等级、Token 节省、预算恢复。禁用字色由 `PrimaryButton` 既有的 disabled 映射取 `COLORS['disabled_text']`，未新增 hex／魔法数字，未改 `ui_tokens.py`／`ui_widgets.py`。
- `程序\tests\test_ui_batch7_settings_models.py`（299 → 321 行，10 → 11 条）
  - 第 156 行 `self.skipTest('需要 Tk')` → `self.skipTest(PLATFORM_TKINTER)`，新增 `from skip_reasons import PLATFORM_TKINTER`。
  - 新增 `SaveButtonStateTests.test_save_button_greys_out_on_pages_with_nothing_to_save`（第 236-252 行）：真 Tk 窗口从预算页起，切 basic／dev 断言 `disabled`，切 model／level／token／budget 断言恢复；并核对 `Tokens.Primary.TButton` 的 disabled 前景等于 `COLORS['disabled_text']`。
- `程序\维护记录\skip台账.json`：只追加 `tests/test_ui_batch7_settings_models.py` / `Batch7Case.setUp` / `ordinal 1` / `PLATFORM_TKINTER` 一条；写入前重读，未动批次 4、5、6、8 的既有条目。

### F.2 验证（本轮实测，非历史凭据）

| 命令 | 实际结果 |
| --- | --- |
| `python -B run_selftests.py -k test_ui_batch7 test_pet_settings pet_models token_saver function_size_ratchet` | **155 条、24.6 秒、1 个文件有红（1 条）**。`test_ui_batch7_settings_models` 11/11、`test_pet_settings` 4 片共 55/55、`test_token_saver` 7 片共 87/87 全绿；`function_size_ratchet` 1 条红为 `desktop_storyboard_page.py::storyboard 324 行 > 上限 323`（并行批次文件，不在本批允许范围）。`pet_models` 无同名测试文件，未擅自扩大筛选范围。 |
| `python -B run_selftests.py -k test_ui_batch7` | **11 条、8.1 秒、0 红**（新增用例计入）。 |
| `python -B -m unittest tests.architecture.test_skip_hygiene`（PYTHONPATH 含 `tests`） | **3 条、2 个 error、1 条通过**；两个 error 均停在 `tests\test_ui_batch3_shell.py` 第 1 行 BOM（`SyntaxError: invalid non-printable character U+FEFF`），**未再指向批次 7 文件**；按任务书“批次 3 的 BOM 问题不归你”。另做只读交叉核对（排除该 BOM 文件）：源码 skip 240 条、台账 241 条，批次 7 的 1 条双向一致；多出的 1 条是并行批次 6 的 `PageLayoutTests.setUpClass`（源码用 `raise unittest.SkipTest(...)`，卫生门禁的 AST 收集器未识别该写法），未动。 |
| `python -B smoke_test.py --affected pet_settings_ui` | **9/9 通过、0 文件红、23 秒**。 |
| `python -B smoke_test.py` | **8/8 通过**。 |
| `--architecture`／`--all --safe` | **未运行**（按 `RUI_common.md` 留给 Claude）。 |

> 环境噪声：上述命令的 stderr 有本机 Tcl `pkgIndex.tcl` 的 `unknown encoding "cp1252"` 报错；把 stderr 单独丢弃后 `$LASTEXITCODE=0`，不影响 stdout 的通过结论。

### F.3 断言未动与需裁决事项

**断言未动**：既有 10 条用例的断言、期望值均未改，未新增 skip；只新增 1 条用例并合规化 1 处 skip 理由。

1. `architecture.test_function_size_ratchet` 的 `storyboard 324 > 323` 来自并行批次的 `desktop_storyboard_page.py`，本批未改该文件、未抬上限登记，需由该批次或 Claude 处理。
2. `test_skip_hygiene` 当前无法完整跑完，卡在并行批次的 `tests\test_ui_batch3_shell.py` BOM；批次 7 自身已按台账格式登记，交叉核对一致。另发现的批次 6 多余条目属于并行批次，未动。
3. **既有行为观察（本批未改）**：`open_hub(pet)` 不传 `tab` 时，`select(win, None)` 会因 `None not in pages` 直接返回，窗口不落任何页；齿轮入口正是无参调用。本轮只把这种初始状态的「保存」置灰，未擅自改默认页。是否改为默认落在「基础功能」，请 Claude 裁决（若改，只需在 `open_hub` 里把 `select(win, tab)` 的 `None` 归一为一个 `TABS` 键，不影响既有断言）。
4. 无新增令牌需求：`disabled_text` 已存在，禁用色未走内联值。

## 验收与提交（Claude，2026-10-19）

轮次号 1715 由 Claude 提交时领取（原名 `tasks_round_pending_UI7_result.md`），含 RUI7b 收尾（「保存」置灰、skip 改 `PLATFORM_TKINTER` 并登记台账；本提交台账只含批次 7 的 1 条）。Claude 在隔离验证工作树（HEAD＋本批文件）复跑：任务书定向＋全部引用 pet_settings_ui／pet_models_ui 的测试（test_pet_ui、test_app_metadata、test_client_profiles、test_model_probe_layers、test_skills 等）共 948 条 0 红；`--affected pet_settings_ui pet_models_ui` 冒烟通过；架构门禁 368/368 OK。D 节：弹窗 minsize 被 `ui_theme.place()` 覆盖、建议新增令牌，留后续批次；旧 `chrome=False` 窗口暂不迁移。另发现齿轮无参打开设置窗不落页，另立 RUI7c。断言未动。
