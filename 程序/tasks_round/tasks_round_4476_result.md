# tasks_round_4476_result — FIX-FULLSAFE-IDEA-CHAT-AND-PAGES（W3）
<!-- round-evidence: {"commit_base": "05a2dcc24", "credential_hits": 0, "evidence_sha256": "5655aa0e4c99d605", "exit": 0, "failed": 0, "passed": 402, "round": 4476, "tests": "run_selftests.py -k idea_chat ui_edges_pages files_panel_stages"} -->

## 三问

- **本轮类型**：修复轮（§3.2）。真产品缺陷 1 处 + 有意测试契约同步 4 条（§2.4）。
- **测试跑了吗、三个基线过了吗**：跑了。
  - 定向：`run_selftests.py -k idea_chat ui_edges_pages files_panel_stages` → 402 条用例、0 文件红、退出码 0（含新增 1 条，改前 401 条 5 红 → 改后 402 条 0 红）。
  - 架构门禁：`smoke_test.py --architecture` → Ran 708 tests，OK，退出码 0（改后实测，非历史凭据）。
  - 默认冒烟基线 8/8：本轮未跑 `smoke_test.py` 默认档（验收命令未含）；全量 `--all --safe` 未跑，欠账口径以 `full-safe-receipts.json` 为准，本轮不宣称消灭欠账。
- **欠账少了吗**：少了 5 条主干全量既有红（2 文件）：`test_idea_chat.py` 2 条、`test_ui_edges_pages.py` 3 条清零；files_panel_stages 全绿保持。

## 改前 5 红原文（基线 05a2dcc24，命令退出码 1，401 条 4 文件有红）

```
### test_ui_edges_pages（1 条红）
===== test_a_shrunk_box_grows_back_only_up_to_the_window (test_ui_edges_pages.TalkBoxFitTests.test_a_shrunk_box_grows_back_only_up_to_the_window) =====
  File "程序\tests\test_ui_edges_pages.py", line 1403, in test_a_shrunk_box_grows_back_only_up_to_the_window
    self.assertEqual(int(box.cget("height")), tall, "内容多了共享输入框不撑高（框内滚动）")
AssertionError: 10 != 4 : 内容多了共享输入框不撑高（框内滚动）

### test_ui_edges_pages（2 条红）
===== test_a_long_creative_box_grows_when_clicked (test_ui_edges_pages.ContentBoxFitTests.test_a_long_creative_box_grows_when_clicked) =====
  File "程序\tests\test_ui_edges_pages.py", line 1301, in test_a_long_creative_box_grows_when_clicked
    self.assertEqual(int(box.cget("height")), before, "共享输入框不随内容撑高")
AssertionError: 10 != 4 : 共享输入框不随内容撑高

===== test_a_very_long_composer_stays_within_the_responsive_limit (test_ui_edges_pages.ContentBoxFitTests.test_a_very_long_composer_stays_within_the_responsive_limit) =====
  File "程序\tests\test_ui_edges_pages.py", line 1321, in test_a_very_long_composer_stays_within_the_responsive_limit
    self.assertLessEqual(fitted_height, TEXT_ROWS["sm"])
AssertionError: 10 not less than or equal to 4

### test_idea_chat（1 条红）
===== test_uploaded_file_list_survives_send_clear_and_deletes_only_confirmed_copy (test_idea_chat.SendMessageTests.test_uploaded_file_list_survives_send_clear_and_deletes_only_confirmed_copy) =====
  File "程序\tests\test_idea_chat.py", line 1543, in test_uploaded_file_list_survives_send_clear_and_deletes_only_confirmed_copy
    self.assertEqual(self.attachment_ref_lines(d), [])
AssertionError: Lists differ: ['@角色设定.txt'] != []

### test_idea_chat（1 条红）
===== test_empty_script_list_keeps_category_headers_and_chat_visible (test_idea_chat.SendMessageTests.test_empty_script_list_keeps_category_headers_and_chat_visible) =====
  File "程序\tests\test_idea_chat.py", line 1140, in test_empty_script_list_keeps_category_headers_and_chat_visible
    self.assertFalse(tree._data_table.empty_label.winfo_ismapped(), '空态不能遮住标题栏')
AssertionError: 1 is not false : 空态不能遮住标题栏
```

## 根因与改法

1. **真缺陷（test_idea_chat.py:1543）**：`ui/desktop_idea_attachments.py` `_sync_idea_ref_block` 仅用**本轮** `idea_attachment_paths` 构造 `valid` 集合；引用清空为 `()` 后 `valid` 为空，上一轮同步写入且带 `idea_ref` 标签的「@角色设定.txt」行既不命中 `valid` 又不被移除，残留为用户可见正文。
   - **改法**：新增实例属性 `_idea_synced_ref_names` 记录本方法上次同步写入的引用名集；删除判定集合改为 `本轮引用 ∪ 上次写入集`，使已取消引用的「@名」行仍被认出并删除；写块后更新该集、`names` 为空时置空。REQ-S01-107 不变量保持：只删整行恰为「@名」的标签行，被用户扩写的行只摘标签保留；`remove_idea_ref_line`、多附件顺序与右键命中语义未动。

## 契约同步说明（AGENTS §2.4）

| 位置 | 上游 | 同步内容 | 保留的核心不变量 |
| --- | --- | --- | --- |
| test_idea_chat.py `test_empty_script_list_keeps_category_headers_and_chat_visible` | R4386（commit b770b7e35，`ui/desktop_files_panel_index.py` 空阶段空态，tests/test_files_panel_stages.py:928 守护文案） | 空阶段断言改为 `empty_label` 显示且文案为「当前阶段暂无文件」；切到「全部阶段」有文件时 `empty_label` 隐藏的断言保持原样 | 表头 `identify_region=='heading'`、列表为空 `get_children()==()`、聊天区/输入区可见性断言全部不变；files_panel_stages 未改、全绿 |
| test_ui_edges_pages.py `test_a_long_creative_box_grows_when_clicked` | R4396（UX-INPUT-FLOW／REQ-S01-107，`ui/desktop_shared_menus.py::_fit_input_height`，`min(TEXT_ROWS['xl'], max(TEXT_ROWS['sm'], shown, logical))` 再经 `_input_room_rows` 钳制） | 「固定 4 行」改为：空框 `==TEXT_ROWS['sm']`，30 行长内容 `==TEXT_ROWS['xl']`（=10）封顶 | 「内容全部保留在框内」（第30行在）不变 |
| test_ui_edges_pages.py `test_a_very_long_composer_stays_within_the_responsive_limit` | 同上 R4396 | `fitted_height <= TEXT_ROWS['sm']` 改为 `<= TEXT_ROWS['xl']` 且 `> TEXT_ROWS['sm']`（确实撑高） | 「高度受限不许丢失用户已输入长内容」（第200行在）不变 |
| test_ui_edges_pages.py `test_a_shrunk_box_grows_back_only_up_to_the_window` | 同上 R4396 | `height==tall` 改为 `sm < grown <= xl`；删短后断言回落 `==TEXT_ROWS['sm']` | 共享实例同一性（`box is d.shared_input.input`）、共享框可见、内容不丢（「一句话的创意」在）不变 |

未弱化或删除任何业务不变量断言；`test_shared_input_ui.py:test_height_follows_display_lines_sm_to_xl`（sm→xl→sm 全链）为同契约既有绿证。

## 新增测试

`test_idea_chat.py::test_clearing_references_keeps_user_typed_lines`：清空引用后同步写入的「@角色设定.txt」行被删除，用户手写正文与手打 @ 行（无 idea_ref 标签）原样保留。

## 改后验证（退出码均为 0）

- `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k idea_chat ui_edges_pages files_panel_stages`
  尾部：`共 402 条用例，407.8 秒；0 个文件有红`／`实际跳过 0 条用例`／`ALL TESTS PASSED`，退出码 0。
- `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`
  尾部：`Ran 708 tests in 281.783s`／`OK`／`✅ 架构治理测试：tests/architecture`，退出码 0。

## 改动文件

- `程序/ui/desktop_idea_attachments.py`：`_sync_idea_ref_block` 增 `_idea_synced_ref_names` 同步写入集。
- `程序/tests/test_idea_chat.py`：1 条契约同步（R4386）+ 1 条新测试。
- `程序/tests/test_ui_edges_pages.py`：3 条契约同步（R4396）+ 类 docstring 更新。

## 未验证项

- `smoke_test.py` 默认档（8/8 基线）：本轮验收命令未含，未跑。
- `run_selftests.py --all --safe` 全量：未跑；本轮只清卡面点名的 5 条既有红。
- 真实桌面交互（可见窗口下右键 @ 行菜单）：隐藏桌面自测覆盖逻辑层，未做人工可视确认。

## 提交

- 已用 `scripts/dev.py commit` 提交（含 `--tests idea_chat ui_edges_pages files_panel_stages`）；commit hash 见提交输出与完成报告。
- 未 push、未合入 master。
