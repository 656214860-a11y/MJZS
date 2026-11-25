# tasks_round_4484_result — UX-S03-EDITOR-CLOSE（W2）
<!-- round-evidence: {"commit_base": "84bed5cf2", "credential_hits": 0, "evidence_sha256": "917c2708d9980ec9", "exit": 0, "failed": 0, "passed": 103, "round": 4484, "tests": "run_selftests.py -k storyboard_page_loading ui_edges_pages ui_edges_controls ui_edges_autopilot"} -->

## 三问

- **本轮类型**：功能轮（§3.1，含 `S03_初步分镜.md` 交互文档同步）。
- **测试跑了吗、三个基线过了吗**：跑了。
  - 定向：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k storyboard_page_loading ui_edges_pages ui_edges_controls ui_edges_autopilot` → 改后 103 条用例（含新增 2 条）、0 个文件有红、0 条跳过、`ALL TESTS PASSED`，退出码 0。
  - 架构门禁：`..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → `Ran 708 tests in 397.016s`、`OK`、`✅ 架构治理测试：tests/architecture`，退出码 0（当轮实测）。
  - 默认冒烟基线 8/8：本轮验收命令未含，未运行；全量 `--all --safe` 未运行，全量欠账口径以 `full-safe-receipts.json` 为准。
- **欠账少了吗**：本轮实现用户新增需求（03 初步分镜编辑器右上角增加关闭选项），未引入新欠账；同步补齐了 `apply_catalogs` 跟随 `normalize_storyboard_for_desktop` 改名的处理，消除了既有 `test_shot_navigator_searches_jumps_and_counts_find_matches` 在 8 路并行高负载下超过 3 秒触发改名导致被切回默认 1 镜分镜的并发红。

## 需求与缺陷复现（先红后绿）

- **用户原话**：`初步分镜页面修复: 2. 文本器打开文件后没有关闭选项, 在右上角增加关闭选项;`
- **复现方式**：在 `程序/tests/test_storyboard_page_loading.py` 新增两条真实 Tk 几何与行为测试（沿用 `open_desktop(td)` + 隐藏桌面下 `win.deiconify()` 量真实几何），在未修改产品代码前运行第一条验收命令。
- **改前红灯输出摘要**（基线 `84bed5cf2`，退出码 1，共 103 条用例、1 文件 3 条红：新增 2 条稳定命中缺失缺陷 + 既有 1 条并发改名红）：

```text
### test_storyboard_page_loading（3 条红）

===== test_close_document_prompts_when_editing_dirty_and_respects_cancel =====
  File "程序\tests\test_storyboard_page_loading.py", line 307, in test_close_document_prompts_when_editing_dirty_and_respects_cancel
    page.editor.close_button.invoke()
AttributeError: 'S03EditorView' object has no attribute 'close_button'

===== test_editor_shows_top_right_close_button_when_file_opened_and_hides_after_close =====
  File "程序\tests\test_storyboard_page_loading.py", line 255, in test_editor_shows_top_right_close_button_when_file_opened_and_hides_after_close
    btn = page.editor.close_button
AttributeError: 'S03EditorView' object has no attribute 'close_button'

===== test_shot_navigator_searches_jumps_and_counts_find_matches =====
  File "程序\tests\test_storyboard_page_loading.py", line 203, in test_shot_navigator_searches_jumps_and_counts_find_matches
    self.assertEqual(len(nav.items()), 3)
AssertionError: 1 != 3
```

说明：既有测试 `test_shot_navigator_searches_jumps_and_counts_find_matches` 报错根因是 8 路并行负载下建页超过 3 秒，后台 `apply_catalogs` 调 `normalize_storyboard_for_desktop` 将未规范命名的 `EP001.json` 改名为规范名后未更新 `page.active_path`，导致 `apply_catalogs` 判 `not active_path.is_file()` 切回已采用的 1 镜默认分镜。

## 改动清单（文件:行号）

1. `程序/ui/storyboard_table_ui.py`（686 → 744 行）：
   - `L13`：从 `ui_widgets` 导入 `Tooltip`。
   - `L436`：`S03EditorView._build` 在 `_build_find_bar` 之前调用 `_build_doc_bar(frame)`。
   - `L460-L469`：新增 `_build_doc_bar`，构建默认未 `pack` 的顶栏 `doc_bar`，左为 `ttk.Label(..., style='SidebarProjectMuted.TLabel', anchor='w')`（无内联 `font`/`fg`/`foreground`），右为 `SecondaryButton(bar, text='关闭', width=0, style='Compact.TButton', ...)` 并挂 `Tooltip`。
   - `L471-L480`：新增 `set_document_header(path)`，按文件打开/关闭态显示文件名与顶栏或隐藏。
   - `L482-L488`：新增 `follow_renamed(changed)`，当 `normalize_storyboard_for_desktop` 将当前已打开分镜规范化改名时同步更新 `active_path`、`active_board_json` 与顶栏文件名，避免打断当前阅读。
   - `L490-L512`：新增 `close_current(confirm_fn=...)`，编辑态且 `viewer.edit_modified()` 为真时先弹窗确认；确认或无脏修改时清空当前文档态、置 `_user_closed_document = True`、隐藏顶栏、收起查找条与镜头定位栏（`by_user=False` 不污染后续重开自动展开）、恢复 `S03_EMPTY_TEXT`、刷新底部状态段并写状态栏「已关闭当前文档」。
   - `L659`：`set_text` 在 `edit_reset()` 后调 `edit_modified(False)`。
   - `L677-L678`：`popup_context_menu` 在 `page.active_path is not None` 时追加「关闭当前文档」。
2. `程序/ui/storyboard_files.py`（984 → 990 行，严格 ≤ 1000 行上限）：
   - `L657`：`_init_page_state` 初始化 `self._user_closed_document = False`。
   - `L684`：新增 `close_document(self)` 委托 `self.editor.close_current(confirm_fn=confirm)`。
   - `L740`：`show_document` 打开文档时复位 `_user_closed_document = False`。
   - `L758`：`_render_active_document` 同步调用 `self.editor.set_document_header(...)`。
   - `L779`、`L804`：`begin_edit` 与 `save_edited` 清零 `viewer.edit_modified(False)`。
   - `L824-L826`、`L836`、`L843`：`apply_catalogs` 跟随改名映射、在 `_user_closed_document` 为真时不自动重开默认文档，并在 `elif` 分支保护 `self.active_path is not None`。
3. `程序/tests/test_storyboard_page_loading.py`（`L227-L327`）：
   - 新增 `test_editor_shows_top_right_close_button_when_file_opened_and_hides_after_close`（验右上角真实 Tk 几何位置、关闭后状态/空态/控件隐藏、手动与后台刷新不自动重开、重开后再次显示）。
   - 新增 `test_close_document_prompts_when_editing_dirty_and_respects_cancel`（验编辑态有未保存修改时取消保稿、确认不保存关闭且磁盘原文件不被改写）。
4. `程序/docs/stages/S03_初步分镜.md`（`L220-L222`、`L253-L254`）：
   - `## 交互` → `### 页面区域` 补充第 4 条「文档顶栏」说明；
   - `### 控件与操作` 表格新增 `UX-S03-24`（「关闭」，文档顶栏右上角）与 `UX-S03-25`（「关闭当前文档」，右键菜单）。

## `git diff --numstat`（产品、测试与文档）

```text
5	2	程序/docs/stages/S03_初步分镜.md
101	0	程序/tests/test_storyboard_page_loading.py
11	5	程序/ui/storyboard_files.py
59	1	程序/ui/storyboard_table_ui.py
```

## 改后验收输出尾部（退出码均为 0）

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k storyboard_page_loading ui_edges_pages ui_edges_controls ui_edges_autopilot`（退出码 0）：
   ```text
   共 103 条用例，134.5 秒；0 个文件有红
   实际跳过 0 条用例：本机没有任何登记位被跳过
   ALL TESTS PASSED
   ```
2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（退出码 0）：
   ```text
   ----------------------------------------------------------------------
   Ran 708 tests in 397.016s

   OK
   ✅ 架构治理测试：tests/architecture
   ```

## 未验证项与卡外发现

- **未验证项**：
  - `smoke_test.py` 默认档（8/8 基线）与 `run_selftests.py --all --safe` 全量自测（验收清单未要求，未运行）。
  - 真实桌面可见窗口下的人工右键菜单与悬停 Tooltip 视觉复核（隐藏桌面自测已验证真实几何与点击交互）。
- **卡外发现**（仅记录不扩大范围）：
  - `程序/tests/test_storyboard_page_loading.py` 既有用例 `test_shot_navigator_searches_jumps_and_counts_find_matches` 写入了非规范名 `EP001.json` 且未设将来 mtime，在 8 路并发负载超 3 秒时会触发 `normalize_storyboard_for_desktop` 改名；本轮通过在 `apply_catalogs` 同步 `active_path` 跟随改名消除了该并发切页问题（未改既有测试断言）。

## 提交

- 已通过 `scripts/dev.py commit` 提交至分支 `codex/ux-s03-editor-close`（含 `--tests storyboard_page_loading ui_edges_pages ui_edges_controls ui_edges_autopilot`），不合入、不 push；提交哈希见完成报告。
