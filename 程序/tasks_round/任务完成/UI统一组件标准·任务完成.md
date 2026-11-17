# 任务完成文件：UI统一组件标准（UI统一组件标准任务书.md）

> 规则 35 收尾归档：任务书 U0–U7 共 31 条验收勾选逐条对账（U7 两条为收尾自检项）。每条给轮次、结果文件、commit 与测试凭据；全部完成，无未完成项。
> 文件名按 `taskbook_closure.stem_of` 口径（任务书文件名去 `任务书.md` 后缀）为 `UI统一组件标准·任务完成.md`；任务书 §U7 字面写法 `UI统一组件标准任务书·任务完成.md` 与门禁同名规则冲突，按门禁口径命名并在此注明。

## U0 文档轮（R3164 `72807cb0`＋R3178 `dfcb3cde` 预算补正＋R3219 `5d5507dd` 合并树复核，`tasks_round_3164_result.md`／`tasks_round_3178_result.md`／`tasks_round_3219_result.md`）

- [x] `ui_components.md` 每一节都写明入口、禁止项、对应门禁名，且门禁名与 U1–U6 的实际测试文件名一致。 → R3164 新增 8 节（浮层与测宽／图标／框体／发送键／字体／原生控件／表单控件／消息卡片与 HITL）；R3219 合并树按 D11/D12 修订后门禁名与实测文件一致；R3266（本轮）逐一核对 `test_text_measure_boundary`／`test_nav_icon_size_boundary`／`test_icon_source_boundary`／`test_box_boundary`／`test_font_boundary`／`test_native_control_boundary`／`test_form_control_boundary` 均存在于 `tests/architecture/`。
- [x] 文件卡片任务新增的组件已纳入标准，其违规项有登记。 → R3164「消息卡片与 HITL」节纳入 `ui_part_renderers`／`ui_hitl`／`ui_param_panel`／`ui_media`／`ui_citation`／`desktop_file_card`；`ui_hitl` 的 `ttk.Radiobutton`、`ui_param_panel` 的 `ttk.Scale` 登记为合规使用，`ui_components.md` 存量表述经 R3264 修正为实测口径（表单门禁冻结仅 5 处 `tk.Listbox`）。
- [x] `AGENTS.md` 仍在 16 KB 预算内，新增内容不超过一行指针。 → R3164 初版 16135 字节超真实门禁 16000（原报告误判），R3178 压缩规则 34 为一行等义指针至 16000 字节、`test_agent_doc_budget` 5/5；R3264 `--architecture` 实测该项仍绿。
- [x] REQ/DES 编号可被后续测试锚定。 → REQ-S01-62／DES-S01-62 落 `docs/stages/S01_剧本准备.md`，`test_script_composer` 锚定；U4（R3241）按任务书同步 DES 文字为圆形描边契约。

## U1 共享测宽函数与三处试点（R3237 `cc998ada`，`tasks_round_3237_result.md`）

- [x] 共享函数有单测：全角、ASCII、混合、空字符串、超过上限四类输入。 → `ui_popup.measure_text_width`＋`tests/test_text_measure.py` 覆盖全角／ASCII／混合／空串／超上限钳位／集合取最长／单位换算，R3237。
- [x] `SelectBox` 在含中文长选项时宽度能完整显示选项且不超过 `COMBOBOX_MAX_WIDTH`；用真 Tk 量几何。 → `SelectBox._fit_width` 改调 `text_units_width`；`test_text_measure` 真 Tk 量 `cget('width')` 与 `winfo_width()`，R3237。
- [x] 文件面板与分镜表列宽行为不变（既有 `test_files_panel*`、分镜表相关测试全绿）。 → `_fit_script_width` 改一次取最长（行为等价）、`+14` 魔法数改 `SPACING['lg']`；定向 165/165＋140 条消费方全绿，R3237。
- [x] 新门禁通过，且对"新增一处直接调用 `measure`"的坏样本能报错。 → `tests/architecture/test_text_measure_boundary.py`：`.measure` 访问／`responsive_ui.measure` 裸名／`ord()` 字符近似三类按文件冻结只减不增，含 canary 坏样本；近似欠账清零、直接测宽冻结 15 处＋旧入口 2 处，R3237。
- [x] `ui_widgets.py` 行数不高于 1125，`test_module_size_ratchet` 通过。 → 迁移后 1124 行（净减），棘轮绿，R3237。
- [x] 默认冒烟 8/8；`run_selftests.py -k select_box files_panel storyboard_table ui_widgets` 全绿。 → 冒烟 9/9（现行口径）；定向集 `text_measure select_placeholder ui_widgets_* column_fit storyboard_page_loading ui_edges data_table_boundary dynamic_import_registry shortcut_registry_boundary skill_panel_layout_fit files_panel` 全绿，R3237。

## U2 图标固定画布与尺寸门禁（R3178 `dfcb3cde`＋R3219 `5d5507dd` 合并树复核，`tasks_round_3178_result.md`／`tasks_round_3219_result.md`）

- [x] 所有主导航 PNG 为 24×24、M3 阶段文件图标豁免，合并树门禁通过。 → `ui_tokens.NAV_ICON_SIZE=24`，`build_nav_icons.render_icons()` 居中固定画布重生 26 张 PNG；`test_nav_icon_size_boundary.py` 按 `ICONS` 字形表逐个查 IHDR、只豁免 M3 的 13 个 `*_files.png`，坏尺寸样本自审；R3219 合并树按 D12 修订后 6/6 绿。
- [x] 侧栏 13 个阶段图标与设置、项目分组图标对齐，在 100% 与 125% 缩放下肉眼复核，截图存入结果文件。 → 隐藏桌面真 Tk 抓图 `tasks_round/evidence/R3178_sidebar_100.png`／`R3178_sidebar_125.png`（`tk scaling`≈1.332/1.664），R3178。
- [x] `test_ui_icons`、`test_login_gate`、`test_page_lock` 等既有图标测试全绿。 → R3178 图标与视频页定向 76/76、侧栏布局 18/18；R3195 `-k icon_source ui_icons shared_input_ui script_composer idea_chat` 219/219；R3219 合并树 `-k nav_icon icon_source ui_icons agent_doc module_size taskbook` 31/31。
- [x] 缺失 PNG 时的退回行为不变。 → `IconLoader.nav_icon` 缺图 emoji 回退未动；`test_missing_png_falls_back_to_emoji` 绿（R3191 契约在 U2/U3 各轮保持），R3178/R3195/R3219 复测均绿。

## U3 图标取用入口门禁（R3195 `3710f972`＋R3219 `5d5507dd` 合并树复核，`tasks_round_3195_result.md`／`tasks_round_3219_result.md`）

- [x] 门禁通过；"新增 `from ui_tokens import ICON_FOLDER` 并用于非允许文件"的坏样本能报错。 → `tests/architecture/test_icon_source_boundary.py` 6/6：直接/别名/模块属性导入 `ICON_*`、`assets/nav` 路径字面量、emoji 图标均拦；R3219 合并树把 T10 包路径基线修订后仍 6/6 绿。
- [x] emoji 存量被准确冻结，不误伤文案里的普通符号（先实测判定口径，写入结果文件）。 → 口径限图标命名赋值及控件 `text=` 开头图标字面量；`STAGE_RAIL_ICONS` 13＋`STAGE_RAIL_ALL` 1＋视频封面空态 1 共 15 处按 AST 实测冻结，`处理成功 ✅` 类文案不误报，判定口径写入 R3195 结果文件。
- [x] 既有引用 `ICON_*` 的测试全绿。 → R3195 定向 219/219（含 `ui_icons`／`shared_input_ui`／`script_composer`／`idea_chat`），R3219 合并树 31/31。

## U4 发送键改圆形外框 + ↑（R3241 `e109879a`，`tasks_round_3241_result.md`）

- [x] 发送键为圆形外框、中间 ↑；运行中为 ■；悬停、不可点、聚焦三态都有可见变化，截图存入结果文件。 → `Tokens.Composer.Send.TButton` 32px 圆环底图四态（`border_input_hover`/`primary`/`disabled_text`/`focus`）＋MDL2 `ICON_SEND`(↑)/`ICON_STOP`(■)；截图 `tasks_round/evidence/R3241_send_{idle,running,hover,disabled,focus}.png` 与 `_150.png`（150% scaling），像素核验五态主题色与字形形状，R3241。
- [x] 与 ✦＋🎤 同一档尺寸，在输入框图标行里垂直居中、间距一致（真 Tk 量几何）。 → `test_send_outline_is_circular_and_matches_icon_row` 断言宽≈高（圆）、与 `voice_button` 垂直中心 Δ≤3px、style map 四态映射，R3241。
- [x] 点击发送、Enter 发送、运行中点终止、Esc 终止的行为不变。 → 行为类断言全部保持原样；`update_script_interrupt_button()` 只换字形与 command 映射；定向复测 222/222，R3241。
- [x] 输入框其余图标的外观未变。 → 仅 `send`/`stop` 两 PNG 全仓零引用后删除，✦＋🎤 仍走 `ICON_FONT`/`Icon.TButton`；`test_shared_input_ui` 其余断言未动，R3241。
- [x] `test_script_composer`、`test_shared_input_ui`、`test_idea_chat` 全绿；结果文件逐条列出被改写的断言及原因。 → 222/222 全绿；契约变化逐条列于 R3241 结果文件「测试契约变化」节（新增圆形几何断言 1 条、听写样式 `Send→Listening.TButton` 同步 1 处、icon_source 基线 3→4 注明样式拆分）。**补记 R3271**：合入前全量预审发现圆环图误入 `_drama_rounded_cache` 共享平铺缓存（`test_ui_modern_system` 平铺下限断言红），已修复为私有缓存并定向复绿 82/82＋冒烟 9/9（`tasks_round_3271_result.md`），外观与交互契约不变。

## U5 Box 框体组件与聊天框迁移（R3252 `3b53e005`，`tasks_round_3252_result.md`）

- [x] 剧本页聊天框迁移前后截图一致。 → `desktop_writing_page.py` 聊天框改走 `ui_theme.box_frame()`，padding 不变；`tasks_round/evidence/R3252_script_page.png` 真机截图＋`R3252_box_ab.png` 同窗并排像素对比 `mean_abs=0.0000`，R3252。
- [x] 全仓除 `ui_theme.py` 外不再出现 `Box.TFrame` 字面量；门禁通过且坏样本能报错。 → `tests/architecture/test_box_boundary.py`：字面量零容忍（豁免样式定义本体）＋自拼 1px 边框按文件冻结 3 处（`cell_hover.py`×1、`ui/skill_panel.py`×2）＋正向锚点要求 `box_frame` 调用；canary 坏样本双组，R3252。
- [x] `Card` 的外观与 `test_card_boundary` 不受影响。 → `Card` 未动；`test_card_boundary` 全部用例在 R3252 定向集与 R3264 `--architecture`（532 条）中实测绿。
- [x] `test_module_size_ratchet`、`test_complexity_ratchet`、`test_function_size_ratchet` 通过。 → `ui_theme.py` 405→416 行，三棘轮 8/8 绿（R3252 验证节），R3264 `--architecture` 复测仍绿。

## U6 字体、原生控件、表单控件门禁（R3264 `1e08035f`，`tasks_round_3264_result.md`）

- [x] 三个门禁各有"新增违规"的坏样本，均能报错。 → `test_new_font_violation_is_rejected`／`test_new_native_color_violation_is_rejected`／`test_new_form_violation_is_rejected` 三个新增违规拒绝用例全绿，另各有谓词 canary＋临时目录 self-audit，R3264（11/11）。
- [x] 三个门禁在当前树上全绿，基线值与文件清单写入测试文件头并注明 AST 口径。 → `test_font_boundary.py`／`test_native_control_boundary.py`／`test_form_control_boundary.py` 文件头 docstring 载明 AST 口径、豁免清单、已知盲区与冻结基线（字体 11 处/6 文件、自配颜色原生控件 63 处/13 文件、表单违规 5 处/5 文件＋局部样式改写零容忍）；合并树 `--architecture` 532 条实测三门禁 11 条全绿，R3264。
- [x] 与作者统计数字不一致时，结果文件说明原因，不为凑数调整口径。 → R3264 结果文件「基线与欠账」节逐项说明：字体作者约 10→实测 11（三元表达式内嵌元组口径差异）、原生控件作者约 74→实测 63（正则含 `ttk.` 与非颜色选项）、表单作者 25 处为全部使用点→实测违规仅 5 处 `tk.Listbox`（合规 `ttk.` 不计债）。

## U7 收尾（R3266，`tasks_round_3266_result.md`）

- [x] 完成文件覆盖本任务书每一条验收勾选，证据或处置标记数不少于任务条数。 → 本文件逐条覆盖全部 31 条勾选，每条带 R 轮次/commit hash/结果文件或测试凭据；`test_taskbook_closure` 实测通过（R3266 验证节）。
- [x] 遗留项已登记到待办队列。 → `维护记录/优化待办队列.md` 新增「UI 统一组件标准遗留项」节：键盘焦点覆盖审计（`takefocus` 11 处、含 focus 行 188 处，计数不足以证明覆盖完整，D16 范围外）、深色模式（D16 范围外）、各门禁存量冻结清单指针（字体 11/6、自配颜色 63/13、表单 5/5、测宽 15+2、Box 边框 3、图标字形/emoji 基线），R3266。
