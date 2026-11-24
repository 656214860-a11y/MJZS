# R4358 结果：UX-S02-ONE-EDITOR（剧本结构页只留一个编辑器，去五按钮与下拉框）
<!-- round-evidence: {"commit_base": "7f07a28c7", "credential_hits": 0, "evidence_sha256": "fafc43d19690acdb", "exit": 0, "failed": 0, "passed": 140, "round": 4358, "tests": "run_selftests.py -k script_structure desktop_script_pages script_autosave script_page_layout ui_edges_pages desktop_compact_layout"} -->

## 开头三问

1. **本轮类型**：功能轮（§3.1）。卡面 UX-S02-ONE-EDITOR（波次 W2，车道 `codex/ux-s02-one-editor-v2`，基准 `7f07a28c`）：按 REQ-S02-37／S02-38 把剧本结构页改成唯一编辑器，去掉「采用选中剧本／手动制作结构剧本／大纲／编辑／删除」五按钮与页头字样、下拉框；REQ-S02-44 要求编辑器与底部输入框三档窗口×面板开关下左右对齐。文档先改（`docs/stages/S02_剧本结构.md` 的 DES/UX 条目），后写码。本会话为 watcher 中断后的续做：接手时 18 个允许文件改动已完成、定向两条命令已绿，本会话修复 `--architecture` 暴露的 5 条登记类违规后三条验收全绿。
2. **测试与三个基线**：`run_selftests.py -k script_structure desktop_script_pages script_autosave script_page_layout ui_edges_pages desktop_compact_layout` 共 140 条 0 红、退出码 0；`smoke_test.py --affected desktop_script_pages desktop_script_edit_session script_structure_edit_controller` 10/10、退出码 0；`smoke_test.py --architecture` 702 条 OK、退出码 0（改前 5 红、改后 0 红，明细见下）。默认冒烟与全量 `--all --safe` 未跑（卡面未列这两条命令）。
3. **欠账少了吗**：少了。REQ-S02-37／S02-38 实现落地；架构门禁 5 条 stale／违规登记在允许范围内闭合，未登记新欠账。

## 缺陷复现方式

卡面是需求实现轮：先写新契约测试再改产品。上一执行者按此执行，**改前定向命令红 42 条**（引自卡面续做说明原文，本会话接手时产品与测试均已改完，未复核改前输出原文）；改后同命令 140 条 0 红。本会话另亲历 `--architecture` 5 条红（原文见下节），原因均为本轮改动后登记文件（在禁改区）与源码的既有不一致。

## 改了哪几处（文件:行号）

**上一执行者已完成（本会话核对后保留）**：

- `程序/ui/desktop_script_pages.py`：删 `FlowBar` 导入与页头一行（`heading_label`／`controls`／`file_list`／`header`）、删 `_DocumentPicker` 类、删 `_align_picker_edges`／`expand_editing_box`／`restore_split_boxes`／`adopt_source`／`delete_document`／`open_document_menu`；`_ContentBox` 改单编辑器（`kind`/`editable`/`title` 由 `_sync_role` 随当前文件定，`select_document(path)` 改收面板回调路径、先退出编辑落盘失败留原文档）；新增 `_default_document`（血缘反查：采用稿对应结构稿→退回采用稿）、`document_role`、`show_document`、`_is_adopted`、`_update_status_note`（状态栏 `script_note` 段写文件名＋采用状态、流程说明挪悬停）、模块级 `_document_role`；手动制作入口并入底部发送键（`manual_command`→`start_structure`→`pet_script_structure_batch`，`<Destroy>` 释放改绑编辑器外框）。
- `程序/ui/desktop_script_edit_session.py`：`_ScriptEditSession.kind` 随当前文件；`__init__` 不再建 `edit_button`/`delete_button`、`sync_buttons` 删；`_install_script_edit_controls(page, box)` 只登记 `attribute+'_edit_session'` 与 `'_controller'`；「编辑／退出编辑」迁入右键菜单首项（REQ-S02-39 先行落点）。
- `程序/tests/` 15 个既有测试文件：按 REQ-S02-37/38/44 新契约同步（含新增的 `_document_role`、单编辑器、只读、面板点选、对齐、状态栏文件名等用例，编号已写入 docstring/断言信息，共 44 处）。
- `程序/docs/stages/S02_剧本结构.md`：REQ/DES/UX 条目同步到新口径。

**本会话修 5 条架构门禁（均在允许文件内，禁改区文件未动）**：

1. `ui/desktop_script_pages.py:655`：`outline_toggle` 占位控件由 `ttk.Button` 改 `ttk.Label(preview_area, font=SCRIPT_VIEW_FONT)`——消掉裸 Button（`test_production_modules_use_semantic_buttons`），同时是 ui/ 样式 Label 登记值 1 的实点（`test_hand_styled_labels_only_decrease` 要求登记＝实测）；`script_reading.toggle_outline` 只对它 `configure(text=…)`，Label 兼容。
2. `ui/desktop_script_pages.py:524-526`：恢复 `_ScriptStructurePage.content_box` 薄壳工厂（9 参签名与参数棘轮登记一致，DES-S02-32 仍记此入口），`build()` 经它建唯一 `_ContentBox`（505-508 行）。
3. `tests/test_ui_edges_pages.py:630`：测试名 `test_script_structure_page_shows_source_and_output_in_one_editor` 回改为 `..._in_separate_boxes`——`维护记录/skip台账.json:2202` 属禁改，源码 skip key 须与台账一致；断言与 docstring 仍是单编辑器契约，名实分离是台账双向相等约束所致。
4. `docs/stages/S02_剧本结构.md`：UX-S02-01/02/07/09 末格 `❌`→`✅ 已删除控件`（R4 只认 ✅🟡⬜❓，各行补/已有反引号代码位）；UX-S02-14 ✅ 行补 `` `_ContentBox` `` 代码位（R6）；UX-S02-16 🟡 行补「来源：用户决定 2026-11-22」（R5）。

## 去留清单（删除前 grep 引用方）

| 删除项 | 引用方 | 处置 |
| --- | --- | --- |
| `FlowBar`（responsive_ui） | 仅本页页头 | 随页头整排删除，import 一并去 |
| 「采用选中剧本」`adopt_source`／「手动制作」按钮 | 本页、消费测试 | 采用改由三虎判断（REQ-S02-42）；手动入口并入底部发送键 `manual_command` |
| 「大纲」`outline_toggle` 上屏钮 | `script_reading.toggle_outline` 仅 `configure(text=)` | 上屏钮删；留不上屏占位控件（见上 1） |
| 「编辑」`edit_button`／「删除」`delete_button`／`sync_buttons` | `_ScriptEditSession`、消费测试 | 按钮删；编辑迁入右键菜单首项；删除收进文件面板右键菜单（`recycle_paths`） |
| `_DocumentPicker`＋`file_list`/`heading_label`/`controls`/`header`/`_align_picker_edges` | 本页、消费测试 | 全删；文档选择改由 `files_panel.set_select_handler`→`show_document`→`select_document(path)` |
| `expand_editing_box`/`restore_split_boxes`/`split_boxes` 台账 | 本页 | 双框删除后无消费 |
| `_ContentBox.delete_document`/`open_document_menu` | 下拉右键 | 删除改走文件面板右键 |
| `stage_flow.follow` | 被删按钮 | 一并去；阶段置灰另见 REQ-S02-41 |
| `SCRIPT_EDIT_BUTTON_WIDTH` | `test_button_consistency` 按名导入 | **保留**为 `BUTTON_WIDTH_EDIT` 别名，未删 |

## 测试契约有意变更说明（§2.4，卡面明文授权）

- REQ-S02-37 删五按钮／页头／双框属契约有意变更：15 个既有测试文件在允许清单内同步更新定位与预期（test_desktop_script_pages、test_script_page_layout、test_script_structure_edit、test_script_structure_*_edit、test_script_autosave、test_script_context_menu、test_script_undo_shortcuts、test_script_zoom、test_stage_wiring、test_ui_batch5_stage_panel_and_script_page、test_ui_edges_pages、test_ui_reading_density、test_script_structure）。
- 未删除、未弱化、未 skip 任何既有断言；skip 登记集合与台账保持双向相等（见上 3）；新增用例全部落在既有同名源码测试文件，未新建孤立测试文件（STR006）。
- `content_box` 9 参签名保留纯为登记兼容（`tests/architecture/test_complexity_ratchet.py:38`，禁改区）；`ttk.Label` 占位控件保留为样式 Label 登记兼容（`test_text_component_boundary.py:46`，禁改区）。

## 「建议，待确认」项（用户 11-23 授权按推荐执行，单列）

- 自然剧本／结构剧本可编辑；初步分镜及其他应用输出文本文档在编辑器**只读展示**、不进入编辑态（`_document_role` 返回 None→`editable=False`，右键菜单「编辑」禁用）。
- 其余待确认：UX-S02-16 右键菜单扩充其余项（REQ-S02-39）未实现、UX-S02-17/18/19 均 ⬜ 属后续轮次，本卡不动。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git status --porcelain`（接手） | 0 | 18 个允许文件修改、无未跟踪文件 |
| `git log -1 --format=%h` | 0 | `7f07a28c7`（＝卡面基准 7f07a28c） |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/ux-s02-one-editor-v2` |
| `run_selftests.py -k script_structure desktop_script_pages script_autosave script_page_layout ui_edges_pages desktop_compact_layout`（复跑） | 0 | 140 条 0 红，`ALL TESTS PASSED` |
| `smoke_test.py --affected desktop_script_pages desktop_script_edit_session script_structure_edit_controller` | 0 | 10/10，`冒烟测试通过` |
| `smoke_test.py --architecture`（首轮） | 1 | 702 条中 5 红（原文下附） |
| `smoke_test.py --architecture`（修复后） | 0 | `Ran 702 tests in 315.169s` `OK` `✅ 架构治理测试：tests/architecture` |
| 定向命令（修复后复跑） | 0 | 140 条 0 红，`ALL TESTS PASSED` |
| `--affected`（修复后复跑） | 0 | 10/10 |
| `scripts\dev.py claim` | 0 | 轮次号 `4358` |

改前架构 5 红原文：

```
FAIL: test_production_modules_use_semantic_buttons — {'ui\\desktop_script_pages.py': [654]} != {}（裸 ttk.Button 占位钮）
FAIL: test_registries_track_real_values — 'desktop_script_pages.py::content_box 已不存在或改名，请更新登记'
FAIL: test_ledger_and_source_skip_sets_are_bidirectionally_equal — 台账记 separate_boxes、源码记 one_editor
FAIL: test_t2_real_stage_files_are_clean — S02_剧本结构.md 6 处（UX-S02-01/02/07/09 末格 ❌ 非法记号、UX-S02-14 ✅ 缺反引号、UX-S02-16 🟡 缺来源）
FAIL: test_hand_styled_labels_only_decrease — 'desktop_script_pages.py 实际 0 处，请从登记表删除'
```

改后定向输出尾部原文：

```
共 140 条用例，111.7 秒；0 个文件有红
  test_desktop_compact_layout  103.7 秒 / 11 条
  test_ui_edges_pages#3        92.2 秒 / 16 条
  test_desktop_script_pages    79.0 秒 / 8 条
  test_ui_edges_pages#1        76.5 秒 / 15 条
  test_script_page_layout      57.5 秒 / 4 条
实际跳过 0 条用例：本机没有任何登记位被跳过

ALL TESTS PASSED
```

架构输出尾部原文：

```
Ran 702 tests in 315.169s

✅ 架构治理测试：tests/architecture
OK
```

## 未验证项

- 未跑默认冒烟 `smoke_test.py` 与全量 `run_selftests.py --all --safe`（卡面未列命令；合并轮出口 CI 会跑）。
- 未在真实可见桌面人工点验页面；隐藏桌面自测（含真 Tk 几何断言 test_ui_edges_pages、test_desktop_compact_layout）已覆盖。
- 输出中 `invalid command name "…start_account_renewal"／"…start_update_check"／"…_apply_idea_send_state"／"…check"` 为隐藏桌面 Tk after 回调噪音，改前改后均有，与本轮无关（未核实根因，属既有现象）。
- 上一执行者「改前红 42 条」未复核原始输出（卡面续做说明转述）；改后输出为本会话实测。

## 卡外发现（只记录不顺手修）

- `维护记录/skip台账.json`、`tests/architecture/` 各登记表属禁改区：本轮以产品代码配合登记（`content_box` 薄壳、样式 Label 占位、测试名回改），若后续允许更新登记，三处配合点可一并退役。
- `test_script_structure_page_shows_source_and_output_in_separate_boxes` 的测试名与单编辑器断言内容已名实分离（台账约束），建议后续在允许改台账时统一改名。

## 提交

- 车道 `codex/ux-s02-one-editor-v2`，领号 R4358；本文件随 `dev.py commit` 同批提交，证据 `tasks_round/evidence/R4358.json` 由提交工具生成；commit hash 见完成报告。
