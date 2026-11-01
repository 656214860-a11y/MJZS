# R1713：结构治理轮·执行（UI 批次 5）——阶段配置与剧本页：动作栏可换行、主体滚动兜底、同宽同间距

## §7 三问

1. **本轮属于 §3 哪种类型？** 结构治理轮·UI 批次 5（执行）。只改任务书允许的 `skill_panel.py`、`skill_panel_support.py`、`desktop_script_pages.py`、新增测试与本结果文件；未认领轮次、未改 `project_status.md`／`AGENTS.md`／`architecture.md`／`skills/`，**未执行任何 git 写命令**。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **8/8 通过**；`smoke_test.py --affected skill_panel desktop_script_pages` **9/9 通过**（定向 `skill_panel`／`desktop_script_pages` 0 红）。任务书验收命令实跑 **287 条、3 个文件有红**，3 条红均来自并行批次正在改的 `desktop.py`／主壳滚动，与本批文件无调用关系（详见 D 节）；本批相关文件（`test_skills` 152、`test_ui_batch5` 5、`test_skill_panel_*`、`test_ui_edges` 的剧本结构页用例）全绿。按共用规矩**未跑** `--architecture` 与 `--all --safe`。架构门禁未运行，不填数字。
3. **project_status.md 的欠账少了吗？** 没有。本批按共用规矩不改状态页、不领轮次；若并由 Claude 提交，源码轮全量欠账将 +1，由验收方计入。

## A 现状核对（先量后改）

- **阶段配置面板 800×460 的真实几何（改前）**：走 `skill_panel.show()`，面板 `776×398`，底栏 `y=363 h=35`，固定表单到 `y=358`；`skill_section` 高 **64px**、请求 **107px**，说明区 `LabelFrame` `mapped=0`。与任务书所述 RUI2d 遗留一致：底栏保住了，SKILL 勾选区被压。880×600 时 `skill_section=107`、说明区 96；1280×800 时说明区 302。底栏 RUI2d 修复保留，`tests/test_skills.py::test_skill_notes_resize_with_the_stage_panel` 继续通过。
- **pack/grid**：逐容器核对后，本批没有“同一容器混用两种管理器”：`build_workflow_coordinator` 的 `header` 内 label／下拉／制作锁全部 `grid`，协调器本身其余行全部 `pack`；`build_notes` 全 `grid`；`_build` 全 `pack`。因此只保留原骨架，未为凑“全改骨架”而重写。
- **动作栏**：改前预设行 611px、SKILL 行 559px 的请求宽度在 776px 面板内能排一行；但窗口允许继续缩到 800 以下（`show()` 的 `minsize(1,1)`），缩窄时靠 `pack` 挤压会裁字。已改为可换行容器，标准三档下仍保持一行，不改变现有高度。
- **橙色/强调**：允许改的三个文件内没有 `warning`／`emphasis`／内联 hex。阶段配置里的「必选」提示仍用 `COLORS['warning_text']`，定义在 `production_lock_fields.py`（本批**不允许改**），是语义警示文字而非橙色按钮；如需彻底退成主蓝需另批裁决（见 D）。
- **剧本页**：`desktop_script_pages.py` 的说明文字 `wraplength=760` 是手写值；字号、padding 已走令牌。两张卡片的左边缘实测同为 `x=496`、宽同为 `1098`，中间 `FlowBar` 同 `x/width`；可恢复错误原本已走 `notifier.error()` 的非模态默认，本批再显式写 `modal=False` 固定契约。

## B 改动（逐文件）

### `程序\skill_panel.py`（1478 行，≤1500 上限）

- 预设行、SKILL 操作行、编剧风格行、接口行改用 `WrappingActionRow`：一行放不下就换行，控件按 `winfo_reqwidth` 排，不再被 `pack` 挤到裁字；行内标签的 `wraplength` 不被改写（外部包提示继续保持单行）。
- `Panel(FormScrollMixin, ttk.Frame)`：`_build` 先占位底栏，再建表单主体；预设／总控／厂商／编剧风格／接口／SKILL 区放入滚动表单，**说明区仍在滚动区之外**，继续按窗口余量伸缩。800×460 时表单请求 397px、视口 359px，自动出现纵向滚动条；滚到底可见完整 SKILL 勾选区，底栏固定。880×600 及以上内容放得下时滚动条自动收起，说明区高度与改前一致（`880×690` 说明正文 155px，未降）。
- 卡片间距由 `max(1, round(pad/3))` 改为 `SPACING['none']`（相邻卡片 1px 边框即分隔线），预设行加同一 4px 左内边距，标签列与卡片内标签同基准；总控对话框 `padding=12`、共享预设 `pady=2`、说明区 `round(pad/3)` 改 `SPACING['md']`／`SPACING['xs']`／`SPACING['none']`。
- 面板内 8 处可恢复提示 `notify(...)` 显式 `modal=False`；删除／覆盖类 `confirm(dangerous=True)` 保持模态。
- `show()` 以 `Panel(..., scroll=True)` 打开弹窗；`Panel` 直接构造（测试／嵌入）默认 `scroll=False`，保留原结构。
- `stage_button_label()` 缩为薄包装，主体下沉到 `skill_panel_support.stage_button_label_for()`；包装显式传入本模块当前的 `STAGE_FLOW`／`stage_for`／`desktop_project`／`stage_config`／`stage_models`／`model_pool`／`pool_records`，`test_opencode_engine` 的 `patch.object(skill_panel, 'STAGE_FLOW'/'stage_for'/'desktop_project'/'pool_records', ...)` 继续生效。
- `refresh_all()`／活动面板名单下沉到 `skill_panel_support`（`register_live`／`unregister_live`／`refresh_all`）；`skill_panel.refresh_all` 仍可调用。
- 结果：模块 1653→1478 行，`function_size_ratchet` 未新增 ≥150 行函数。

### `程序\skill_panel_support.py`（650 行）

- 新增 `WrappingActionRow`：换行动作栏（place 布局、请求宽度优先、4px 间距、销毁时撤销 idle 任务）。
- 新增 `FormScrollMixin`：表单主体 canvas＋scrollbar、按请求高度同步、内容放得下自动收滚动条、滚轮只在表单可滚时消费事件。
- 新增 `stage_button_label_for()`：承接原 `stage_button_label` 主体，依赖以参数传入以保留原补丁点。
- 新增 `register_live()`／`unregister_live()`／`refresh_all()`：活动面板名单随实现下沉，`skill_panel.refresh_all` 公开名不变。
- 新增 `tkinter`／`ttk`／`COLORS` 导入，仍为 L4，无新分层依赖。

### `程序\desktop_script_pages.py`（622 行）

- `wraplength=760` → `TEXT_DESC['wraplength']`（说明文字）；字号继续由 `Muted.TLabel` 主题令牌提供，padding 原有值均已是 `SPACING`／`SCRIPT_VIEW_PADDING` 令牌。
- 两处 `notifier.error(..., title='模型调用失败')` 显式 `modal=False`；删除类操作仍走 `recycle_paths` 与既有确认。
- 未改卡片骨架：两张卡片仍在同一 `grid` 列、同 `sticky`，改前后实测左边缘与宽度一致。

### 新增 `程序\tests\test_ui_batch5_stage_panel_and_script_page.py`

- docstring 写「UI 批次 5」；5 条真 Tk 用例：
  1. 800×460／880×600／1280×800 三档：底栏可见、按钮 `winfo_width() >= winfo_reqwidth()`、预设动作栏子控件不越出右沿；
  2. 500×560 窄窗：预设动作栏换行（高度 >35）且换行后仍不越界、不裁字；
  3. 800×460：滚动条出现、`scrollregion` 高于视口、滚到底后底栏 rooty 不变、每个 SKILL 勾选框完整落在视口内；
  4. 无项目时 `skill_panel.show()` 的提示 `modal=False`；
  5. 剧本结构页两张关键卡片同 `x`、同宽，中间动作栏同 `x`／同宽，底部说明不越出卡片右沿。

## C 验证与截图

### 本轮实跑

| 命令 | 实际结果 |
| --- | --- |
| 过程中分项复跑：`test_ui_batch5`／`test_skills`／`test_skill_notes`+`test_skill_panel_layout_fit` | 分别为 5/5、152/152、17/17，均 0 红；最终代码由下方 287 条验收与 29 条复跑再次覆盖 |
| `python -B run_selftests.py -k test_ui_batch5 test_skill_notes test_skill_panel_layout_fit module_size_ratchet token_boundary` | 29 条、0 红（11.5 秒，最终代码） |
| `python -B run_selftests.py -k token_boundary` | 5 条、0 红；`skill_panel.py` 数字 padding 由 1 降为 0，未新增 hex／padding |
| 任务书验收命令 `-k test_skills skill_panel desktop_script ui_edges test_layers function_size_ratchet module_size_ratchet test_ui_batch5` | 287 条、**3 个文件有红**（228.4 秒）：`architecture.test_function_size_ratchet` 1 红、`test_ui_edges` 2 红（均为并行批次 `desktop.py` 相关，详见 D）；`test_layers` 5/5、`module_size_ratchet` 2/2、`test_ui_batch5` 5/5、`test_skills` 152/152、`test_skill_panel_*` 全绿 |
| `python -B smoke_test.py` | **8/8 通过** |
| `python -B smoke_test.py --affected skill_panel desktop_script_pages` | **9/9 通过**；定向 `skill_panel`／`desktop_script_pages` 0 个文件有红（107 秒） |
| `python -B run_selftests.py -k test_idea_chat test_workflow` | 259 条、0 红（117.8 秒，补验 `stage_button_label` 补丁点） |
| `python -B run_selftests.py -k test_opencode_engine` | 12 条中 11 绿；唯一红为既有 `model_pool.call_mode({'provider':'desktop','model':'opencode'})` 期望 `CLI`、现返回 `Desktop`（与本批无关，见 D） |
| `--architecture`／`--all --safe` | **未运行**（按 RUI_common 由 Claude 验收时统一跑） |

### 截图（均用 `tempfile.mkdtemp()` 空项目根，未打开用户项目）

- `工作流任务\probe_ui5\panel.png`：阶段配置面板 880×600（动作栏一行、说明区完整、无多余滚动条）。
- `工作流任务\probe_ui5\panel_800x460.png`：同一面板 800×460（底栏固定，右侧出现表单纵向滚动条，SKILL 勾选区可继续下滚）。
- `工作流任务\probe_ui5\script_page.png`：剧本结构页（临时项目，项目列表为空；两张卡片与中间动作栏左边缘同一 x）。
- 几何证据：`probe_ui5\before_real.json`／`after_real.json`（改前/改后三档几何）、`probe_ui5\run_selftests_ui5_final.log`（最终验收命令原始输出）、`probe_ui5\run_selftests_ui5.log`（首次验收输出）；探针 `layout_probe.py`、`real_probe.py`、`show_panel.py`、`show_script.py`。

## D 断言未动与需裁决事项

**断言未动**：本批没有修改任何既有测试文件或断言；`tests/test_skills.py`、`tests/test_skill_notes.py`、`tests/test_skill_panel_*.py`、`tests/test_ui_edges.py`、`tests/architecture/test_function_size_ratchet.py` 全部保持原样，无 skip 新增。新增用例只覆盖本批行为。

**需 Claude 裁决/复跑**：

1. **`architecture.test_function_size_ratchet` 1 红（非本批）**：`desktop.py::__init__ 实际 132 行，已不超限，请从登记表删除`。`desktop.py` 当前在工作树被并行批次修改（把侧栏拆到 `_build_sidebar`），本批未改 `desktop.py`、也未改棘轮登记表。请并行批次合并后按规则下调/删除该登记，再复跑。
2. **`test_ui_edges` 2 红（非本批）**：`test_restored_main_window_recomputes_page_scroll_before_wheel`（`d.canvas.yview()[0]` 仍为 0）与 `test_table_hover_clears_when_wheel_scrolls`（`table.yview()[0]` 仍为 0）。失败在**主页面/表格滚轮**路径；本批只改阶段配置弹窗与剧本结构页，未触碰 `desktop.py` 的 `scroll_page`／表格滚轮绑定。当前工作树中 `desktop.py`、`app.py`、`keyframe_comfy.py` 等由并行批次修改，请合并后复跑；若仍红，再按主壳滚轮专项定位。
3. **「必选」提示颜色**：仍为 `production_lock_fields.py` 的 `COLORS['warning_text']`（深琥珀文字，5.02:1）。该文件不在本批允许清单，且这是语义警示文字；若产品要求“阶段配置内零橙色”，需另批改该文件并同步视觉契约。
4. **建议新增令牌（本批未改共用文件，留 Claude 统一补）**：
   - `BORDER_WIDTH = 1`：卡片/分隔线边框宽度；用于 `skill_panel.py:276/280/297/303` 的 `borderwidth=1`，以及后续同类卡片。仅用于线，不用于布局。
   - `SPACING['hairline'] = 1`：卡片间距/细分隔线，若日后恢复卡片间 1px 间隙时使用；本批暂用 `SPACING['none']`（相邻 1px 边框即分隔线），未新增该令牌。
   - `SCRIPT_FILE_COLUMN_WIDTH = 170`、`SCRIPT_FILE_COLUMN_MIN_WIDTH = 105`：剧本结构页文件表列宽/最小列宽；用于 `desktop_script_pages.py:396`，当前无对应尺寸令牌。
5. **运行期覆盖说明**：`desktop_script_pages.py:607` 初始 `wraplength` 已取 `TEXT_DESC['wraplength']`，但 `desktop._fit_content_now()`（`desktop.py:528-529`）会对带正 `wraplength` 的非 `local_wrap` 标签按内容宽度重设；实际显示宽度随窗口自适应。本批只去掉手写 `760`，未改变该既有自适应策略。
6. **模块容量提醒**：`skill_panel.py` 现 1478 行，距 1500 行上限 22 行。后续再加功能应先拆到 `skill_panel_support.py` 或新模块，不能继续堆入本文件。
7. **探针范围自纠（如实记录）**：剧本页第一版截图探针误把真实 `程序\` 当程序根，侧栏读取到真实项目登记的名称；**没有打开或读取任何用户项目内容**。该截图已删除并用隔离程序根（空 `projects.json`、空下载目录）重拍（现 `script_page.png` 的项目列表为空）。同窗口期内 `程序\配置\宠物\配置.json` 的 mtime 有更新；已核对内容为正常 UTF-8、不含探针临时路径或本批新增模型，本批未主动改写该文件。验收时如发现该全局配置有异常，请以并行批次/真实使用记录为准回查。
8. **额外观察（非本批验收命令）**：`test_opencode_engine` 12 条中 11 绿，唯一红是 `test_opencode_is_a_cli_engine_not_a_desktop_model` 期望 `model_pool.call_mode({'provider': 'desktop', 'model': 'opencode'}) == 'CLI'`，当前实现经 `desktop_engine('opencode') == 'desktop-app'` 返回 `Desktop`。这是 R1592 的 Desktop 调用方式与旧用例期望不一致，与本批文件无调用关系；本批未改该测试或 `model_pool`。

## E 交付状态

**未提交，由 Claude 验收后提交。** 本批未执行任何 git 写命令；工作树中的 `desktop.py`、`app.py`、`desktop_project_pages.py`、`keyframe_comfy.py`、`reference_wall.py`、`white_model.py` 及其他 `tasks_round_pending_UI*` 属于并行批次，未触碰、未回退。

## 验收与提交（Claude，2026-10-19）

轮次号 1713 由 Claude 提交时领取（原名 `tasks_round_pending_UI5_result.md`）。补交 RUI58b：两处 skip 改用 `PLATFORM_TKINTER` 并登记 skip台账（本提交只含批次 5 的 2 条）。Claude 在隔离验证工作树（HEAD＋本批文件）复跑：任务书定向＋全部引用 skill_panel／desktop_script_pages 的测试＋test_idea_chat／test_workflow 共 1511 条，红 2 条均与本批无关——`test_opencode_engine` 为 R1706 已知回归（HEAD 上同红，R1706b 修复中），`test_pet_ui` 的 `test_tk_gc_guard_skips_worker_threads` 为并行分片下偶发（单条、整组、整文件 599 条串行均 OK）；受影响冒烟 9/9、架构 368/368。D 节：「必选」提示橙色在 `production_lock_fields.py`，留后续批次；建议令牌由 Claude 统一补；`skill_panel.py` 距行数上限 22 行，后续新增先拆。
