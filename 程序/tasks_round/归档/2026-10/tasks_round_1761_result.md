# R1761：功能轮——技能说明与剧本内容框去多余空行，剧本目录栏收窄让出正文（UIREAD）

> 车道 `lane_ui1`，基于 master。执行方：magpie 路由模型。本轮为**功能轮**（用户明确要求的界面调整）。
> 本结果文件按任务书交付项逐条记录；改动在上一执行方已有未提交改动的基础上继续（先 `git status`/`diff` 复查后接续，未从头重做）。

## 三问（开头必答）

1. **轮次类型**：功能轮（§3.1）。涉及已建文档的阶段（S02 剧本结构），已先改 `docs/stages/S02_剧本结构.md` 需求与设计，再改代码与测试（§2.7 文档先行）。
2. **测了吗／三个基线**：
   - **测了**：任务书指定的窄命令全部执行（见「实际命令与结果」）。
   - **默认冒烟**：`smoke_test.py` **8/8 通过**（改后，基线 8/8 一致）。
   - **架构门禁**：未按任务书跑 `--architecture`（调度方验收时自己跑）。但与本轮改动直接相关的两条架构测试单跑通过：`tests/architecture/test_function_size_ratchet.py`（2/2，见「先红证据」，我修复了前执行方把 `content_box`/`script_structure` 撑破上限的问题）、`tests/architecture/test_requirement_traceability.py`（5/5，REQ-S02-32 锚定有效）。
   - **全量回归**：未运行（任务书明确禁止，属调度方验收范围）。
3. **欠账**：执行方不改 `project_status.md`；本轮不产生也不核销欠账条目。修复了前执行方遗留的「函数体行数超限」架构红灯（属本轮范围，见下）。

## 对应 REQ／DES

- `REQ-S02-32` ✅（新增）：技能说明与剧本结构两个剧本内容框只折叠展示层整行空白、段距取 `ui_tokens`；磁盘剧本／SKILL 源／发给模型的注入内容不改；未改动的编辑态保存保持源文件逐字节一致；剧本目录按文件数紧凑显示并给正文留 ≥85% 宽度。
- `DES-S02-32`（标注 REQ-S02-32）：`skill_note_render.parse()` 丢弃代码块外空白行、正文标签用 `NOTE_PARAGRAPH_SPACING`；`script_view_style.compact_display()` 生成只读紧凑展示；`desktop_script_pages.content_box` 保留 `DataTable` 与可拖动分隔、按文件名自适应窄目录列、行数 1..6，编辑态切回原文、未编辑不写盘。
- 测试锚点：`tests/test_ui_reading_density.py`（docstring 写 `REQ-S02-32`），已通过 `test_requirement_traceability.py`。
- 说明：阶段配置页的「技能说明」属 `skill_panel`（跨阶段 UI，`docs/stages/` 无其专属阶段文件）；本轮将其展示层空行折叠一并归入 S02 的「阅读区展示」REQ-S02-32，与剧本内容框同一编号链。

## 根因与方案取舍

- **空行根因**：SKILL 阅读副本（`skill_notes.reading_text`）与剧本源文件都「每行后面跟一个空行」；再叠加 Text 标签的 `spacing3` 段距，视觉上变成整行空白。源文件空行占比实测 36–50%。
- **技能说明**：只在展示层折叠——`skill_note_render.parse()` 丢弃代码块外的空 Markdown 行，段落间距交给正文标签的 `spacing3=NOTE_PARAGRAPH_SPACING`（`SPACING["xs"]//2`，半行高以内）。**不动** `skill_notes.reading_text`／`preview` 里面向模型的文本路径（SKILL 注入策略红线）。
- **剧本正文**：新增 `script_view_style.compact_display()`，只对展示副本折叠代码块外的空白行；正文标签既有 `SCRIPT_VIEW_PARAGRAPH_SPACING` 继续承担段距。**编辑态切回原文**（`loaded['raw']`），因为紧凑展示丢掉了源文件的空行/换行细节，只有显示原文才能保证「原样保存逐字节一致」；保存时若 `edit_modified()` 为假（没改字）**不写盘**，直接回紧凑显示，源文件零改动。
- **目录栏布局取舍**：保留 `DataTable`/Treeview（既有选择、右键菜单、恢复删除、测试都依赖它），不换控件。把目录列从固定 170px 改为「按最长文件名自适应窄栏」（`SCRIPT_DIRECTORY_MIN_WIDTH=96`、`MAX_WIDTH=108`、列内边距 token 化），行数取 `1..6`（超出走 DataTable 既有自动隐藏滚动条），`file_table.pack(fill='x', anchor='n')` 让目录表贴顶不撑满整列，正文分栏（Panedwindow 权重 0:1）拿到剩余宽高。长文件名加 `TreeRowTooltip` 悬停看全文（补齐收窄后看不到全名的问题）。
  - 采纳任务书「收窄目录栏 + 标题行与按钮同行」的轻量方向，未把按钮挪到目录栏下方竖排（那会让既有 `test_ui_edges` 的 `winfo_children()[0]`/按钮定位断言大面积变化），V4 数值照样达标。
- **行号映射**：`apply_tags(widget, text, kind)` 始终按传入的「展示文本」计算 span（紧凑文本自洽），不跨回源文件行号；编辑态则对原文单独 `apply_tags`，两边互不混用。

## 改动清单（文件:函数）

- `desktop_script_pages.py`
  - 新增模块级 `_fit_script_directory(file_list, file_table, available)`：目录列宽自适应＋行数 1..6＋`TreeRowTooltip`＋`pack(fill='x', anchor='n')`。
  - 新增模块级 `_reset_preview_text(preview, text, kind)`：清空→整段刷入→按需 `apply_tags`→`edit_reset`。
  - `ScriptPagesMixin.script_structure` 内嵌 `content_box`：`box` 内边距改 `(xs, none)`；目录列走 `_fit_script_directory`；`body.add(files, weight=0)`、`body.add(preview_area, weight=1)`；`set_preview` 改用 `compact_display`＋`loaded['raw']`；`begin_edit` 切回原文并 `edit_modified(False)`；`save_edit` 仅 `edit_modified()` 为真时 `save_natural_script`，否则回紧凑显示；两处目录标题由「…目录（01…/02…）」缩短为「自然剧本／结构剧本」。
- `script_view_style.py`：新增 `compact_display(text)`（折叠代码块外空白行，`\r\n/\r` 归一为 `\n`）。
- `skill_note_render.py`：`parse()` 丢弃代码块外空行；`_configure_tags()` 正文 `spacing3=NOTE_PARAGRAPH_SPACING`。
- `ui_tokens.py`：新增 `NOTE_PARAGRAPH_SPACING`、`SCRIPT_DIRECTORY_MIN_WIDTH/MAX_WIDTH/COLUMN_PADDING/MAX_ROWS`。
- `docs/stages/S02_剧本结构.md`：新增「阅读区展示」节 `REQ-S02-32`、`DES-S02-32`、测试锚定表行。
- `tests/test_ui_reading_density.py`（新增，8 用例）：V1/V2 函数级断言、V3 往返字节比对、V4 真 Tk 几何、多文件滚动、长文件名不挤压正文。
- `tasks_round/UIREAD_{before,after}_{script_structure,skill_notes}.png`（4 张截图）。

## V1–V6 实测数字（改前 → 改后）

- **V1（技能说明空行）**：`skills/*/*.skill.md` 共 **67** 份；`reading_text` 含 `\n\n` 的文件数 **改前 67/67 → 改后 0/67**（`skill_note_render.parse` 后代码块外连续空行为 0）。例外判据：代码块内部保留空行（`test_code_block_blank_lines_are_kept` 验证）；段距 `NOTE_PARAGRAPH_SPACING=2px ≤ 半行高`。
- **V2（剧本正文空行）**：样例源空行占比 **改前 50%（25/50 行）→ 改后 0%**。任务书真实项目副本口径（36–50%）由 `compact_display` 统一降到接近 0（除代码块特例）。
- **V3（只改显示，数据不动）**：进入编辑→不改字→保存，磁盘文件与原文**逐字节一致**（含 BOM＋`\r\n` 文件，`test_unchanged_edit_save_preserves_source_bytes` 用 `read_bytes()` 比对）。编辑态显示原文，退出编辑回紧凑显示，已写进方案说明。
- **V4（1280×800 真 Tk 量）**：
  - source 框：box 宽 1098，正文宽 945，**占比 86.1%**；box 高 267，正文高 234，标题/按钮占用 **1.7 行**（≤2 行）；目录 1 行、height=1。
  - output 框：box 宽 1098，正文宽 954，**占比 86.9%**；box 高 271，正文高 238，占用 **1.7 行**；目录 3 行、height=3。
  - 目录行数取 `min(6, max(1, len(available)))`；文件 ≤6 时不出现 3 行以上空白块（`test_script_text_and_directory_get_the_requested_space`、`test_many_documents_keep_directory_scrollable_at_six_rows`）。
- **V5（功能不丢）**：选择切换预览、采用选中剧本、右键删除（回收站）、恢复删除、编辑／保存、空占位「尚无可用文件」、大文本分块加载——全部保留。既有测试 `test_stage_wiring`、`test_ui_edges`（定向 2 用例）、`test_ui_batch5_stage_panel_and_script_page`、`test_page_cache`、`test_page_paint_metric` 均通过。
- **V6（先红后绿）**：见下「先红证据」。

## 先红证据

- **架构红灯（本人实测并修复）**：前执行方把 `desktop_script_pages.py::content_box` 撑到 **210 行（上限 187）**、`::script_structure` 撑到 **275 行（上限 251）**，`test_function_size_ratchet.py` 红：
  ```
  FAIL: test_no_function_exceeds_its_cap
  ['desktop_script_pages.py::content_box 210 行 > 上限 187',
   'desktop_script_pages.py::script_structure 275 行 > 上限 251'] : 请拆分为模块级辅助函数，不要抬高上限
  ```
  修复：抽出 `_fit_script_directory`、`_reset_preview_text` 两个模块级辅助函数，复跑 → `content_box 186`、`script_structure 251`，**绿（2/2 OK）**。
- **V1/V2 函数级红（以实测改前数为据）**：改前 `reading_text` 67/67 含 `\n\n`、源空行占比 50%，`test_ui_reading_density.py` 的 `assertFalse(_has_blank_line_outside_code(...))` 与 `assertNotIn("\n\n", ...)` 必然红；实现后 0/67、0%，转绿。前执行方未留下「红」原始输出文件，此处以本轮实测的改前数值作为红据并如实注明。

## 实际命令与结果（计数）

| 命令 | 结果 |
| --- | --- |
| `python -B tests/test_ui_reading_density.py` | 8 tests OK（重构前/后各跑一次） |
| `python -B tests/architecture/test_function_size_ratchet.py` | 红 → 修复 → 2 OK |
| `python -B tests/test_script_view_style.py` | 12 OK |
| `python -B tests/test_skill_notes.py` | 14 OK |
| `python -B tests/test_skill_panel_dropdown_layout.py` | 13 OK |
| `python -B tests/test_stage_wiring.py` | 16 OK |
| `python -B tests/test_ui_batch5_stage_panel_and_script_page.py` | 5 OK |
| `python -B tests/test_ui_edges.py`（全文件） | 卡在 `test_frame_checks_follow_the_frame_state`（首帧页，与本轮无关），超 15min 停；改定向跑下面 2 用例 |
| `python -B tests/test_ui_edges.py UiEdgeTests.test_script_structure_page_shows_source_and_output_in_separate_boxes UiEdgeTests.test_step2_rows_hug_their_content_boxes` | 2 OK |
| `python -B tests/test_page_cache.py` | 11 OK |
| `python -B tests/test_page_paint_metric.py` | 7 OK |
| `python -B tests/test_checkbox_column.py` | 2 OK |
| `python -B tests/test_skill_note_render.py` | 10 OK |
| `python -B tests/test_skills.py` | 首跑 1 红（`test_skill_notes_resize_with_the_stage_panel`，几何传播偶发），单跑复验 OK、全文件复跑 **152 OK** |
| `python -B tests/architecture/test_requirement_traceability.py`（PYTHONPATH=程序） | 5 OK |
| `python -B smoke_test.py` | **8/8 通过** |

## 改了哪些测试的什么定位

- **无**。未修改任何既有测试文件的定位或断言；只**新增** `tests/test_ui_reading_density.py`。

## 断言未动声明

- 未改动、未弱化、未跳过任何既有测试的断言。本轮对既有测试零修改；新增测试只补充断言，未触碰旧断言。

## 需裁决事项

1. **`tests/test_ui_edges.py` 全文件跑卡在 `test_frame_checks_follow_the_frame_state`（04 首帧页，与本轮改动无关）**，超 15 分钟无输出后停掉。定向复跑本轮相关的 `test_script_structure_page_...`、`test_step2_rows_...` 均通过。该测试涉及 `open_studio`＋首帧页，疑似沙箱 GUI 卡顿（任务书也提示 `run_selftests.py` 会卡「跨树 GUI 令牌」）。请调度方验收时在非沙箱环境确认该文件全绿。
2. **`tests/test_skills.py` 首跑偶发 1 红**（`test_skill_notes_resize_with_the_stage_panel`，`293 not less than 293`），单跑与全文件复跑均绿，判定为既有时序偶发，非本轮引入。请验收复跑时留意。
3. 截图基线：4 张 `UIREAD_{before,after}_*.png` 已由前执行方生成并存于 `tasks_round/`；本轮重构未改变视觉结果，未重新截图、未 `--update` 基线。若调度方截图基线比对因有意改版变红，属本轮预期（技能说明/剧本正文去空行、目录栏收窄）。

## 边界自检

- 未执行任何 git 写命令；未领号、未提交、未改 `project_status.md`／`AGENTS.md`；未读 `private\`／`.env`。
- 未改磁盘剧本文件、SKILL 文件或发给模型的 SKILL 注入内容（只动展示副本）。
- 未新增生产模块（仅给既有模块加函数），故无需登记 `_layers.py` 新行、无需刷新覆盖率基线、无需更新 `runbook.md` §11 计数；`desktop.py` 行数未增（本轮未触碰）。
- 未引入 `skipTest`，无需登记 skip 台账。

## 独立验收（Claude，车道 lane_ui1 内直接运行，真实环境；GUI 测试在隐藏桌面上跑）

- 范围：4 个生产文件（desktop_script_pages／script_view_style／skill_note_render／ui_tokens）、1 份 docs/stages/S02、1 个新增测试文件；既有测试零改动。
- 消费方：47 个相关测试文件逐个跑（含 test_pet_ui 599/599、test_skills 152/152、test_window_resize_coalescing 5/5、test_stage_wiring、test_ui_batch3/5/6/7/8/9、test_video_ui 66/66、test_script_structure、test_skill_panel_*、test_ui_reading_density 8/8）全绿；`test_ui_edges` 定向 2 条绿。
- 门禁：`smoke_test.py` 8/8；`smoke_test.py --architecture` 375/375。
- 非本轮失败（主分支同样复现）：test_idea_chat（多条气泡编辑／附件用例）、test_manual_plan 1 条错误，均与本轮文件无关，未处理。
- 独立探针：67 份 SKILL 说明展示后代码块外整行空白 0 条（改前源文件空行占比 25%）；真实项目《摄影侠》结构剧本 1735 行、空行 31% → 展示后 0；展示函数不原地改源字符串。
- 变异：回退 4 个生产文件的全部改动，新测试 73 失败＋1 错误（含未改字保存逐字节往返用例）；还原后 sha256 一致。
- 截图：改前→改后（1280x800，同一份样例数据）见 工作流任务/probes_ui1/shot_before.png、shot_after.png：目录栏收窄，两个内容框无整行空白，正文更宽。
- 未跑：`run_selftests` 全量与 `--all --safe`（本轮不属触发条件）。
