# R4397 · UX-S02-MENU-FOLD：编辑功能收进右键菜单、行号栏折叠标记、Ctrl+G 与状态栏信息
<!-- round-evidence: {"commit_base": "67fd96c99", "credential_hits": 0, "evidence_sha256": "c59ea4582748c42c", "exit": 0, "failed": 0, "passed": 118, "round": 4397, "tests": "run_selftests.py -k script_structure script_context_menu script_outline script_line_numbers script_find_bar desktop_script_pages"} -->

## 三问

- 本轮类型：§3.1 功能轮（REQ-S02-39、REQ-S02-40 做法甲、REQ-S02-43；先改 `docs/stages/S02_剧本结构.md` 的 REQ/DES/测试锚定再写码）。
- 测试跑了吗：跑了。改前定向红 24 条（23 条为本轮新用例的功能缺失红，1 条为既有基线红，原文节选见下）；改后 `run_selftests.py -k script_structure script_context_menu script_outline script_line_numbers script_find_bar desktop_script_pages` 12 个测试文件 118 条全绿（退出码 0）；`smoke_test.py --affected desktop_script_pages script_reading script_find_bar script_outline script_line_numbers` 10 项检查＋17 个测试模块全绿（退出码 0）；`smoke_test.py --architecture` 708 条全绿（退出码 0）。全量回归未跑（分支轮次不累计）。
- 三个基线数：默认冒烟本轮未按验收清单跑（未取 8/8 基线，如实标注未运行）；架构门禁当轮实测 708 条、失败 0（改前同命令曾因未登记同层边 `script_reading→ui_widgets` 红 2 条：`test_compliance_ledger_matches_measured_violations` 与 `test_lr03_unregistered_same_layer_edge_is_red`，改为 `_ContentBox` 注入 `goto_ask` 后归零）；全量凭据未跑。
- 欠账少了吗：`test_script_structure_empty_box_edit` 的既有基线红（旧菜单含分隔符项，`entrycget -label` 崩）随新菜单恰好五键无分隔符转绿，欠账减一；未新增欠账。

## 缺陷复现方式

剧本结构页唯一编辑器右键仍是编辑会话旧六键菜单（编辑／后退一步／前进一步／复原全文／立即保存＋打开其他文件），REQ-S02-39 要求的「剪切／复制／粘贴／全选／查找…／大纲／全部折叠／全部展开」不在菜单里；行号栏无折叠标记（REQ-S02-40）；无 Ctrl+G 跳转与状态栏光标信息（REQ-S02-43）；查找条没有「只在标题里找」开关。`<Button-3>` 绑定在 `desktop_script_edit_session.py`（不在允许文件），因此菜单由 `script_reading.ReadingAids.context_menu` 接管并在 `_ContentBox.build` 里无 `add` 重绑覆盖。

## 改前红（24 条，节选原文）

产品文件还原 HEAD、仅上新测试时同一条定向命令输出 24 条失败；23 条为功能缺失，典型原因：

```
AttributeError: module 'script_outline' has no attribute 'outline_sections'
AttributeError: 'LineNumberGutter' object has no attribute 'set_fold_support'
TypeError: FindBar.__init__() got an unexpected keyword argument 'headings'
AttributeError: 'ReadingAids' object has no attribute 'context_menu'   # 另有 heading_lines／fold_marks／toggle_fold／fold_all／expand_all／ensure_line_visible／select_all／goto_line／update_cursor_status 同款缺失
AssertionError: 旧右键菜单标签序列 != REQ-S02-39 十三键序列            # 菜单仍是旧六键
AssertionError: 'script_cursor' not in desktop.status_bar._segments    # 状态栏无光标段
```

另 1 条为既有基线红：`test_script_structure_empty_box_edit` 对旧菜单分隔符项执行 `entrycget -label` 抛 TclError（新菜单空文档恰好五键无分隔符，改后转绿）。

## 改动（文件:行号）

- `程序/ui/script_outline.py:18-23,39-77`：`outline_sections(text, kind)` 复用 `script_view_style.spans` 产出 `[(行号, 标题, 层级, 段末行)]`（段末＝下一个同级或更高级标题行，文末为总行数加一）；`highlight_line(widget, line)` 施加 `script_outline_hit` 并 `see()`。
- `程序/ui/script_line_numbers.py:17-19,57-101`：`set_fold_support(marks, toggle)`；`_draw_fold_marks` 按 `fold@行号` tag 画命中框＋三角（展开朝下／收起朝右），跳过未布局行；`_on_press` 在 ±`_MARK_PAD` 内 `find_overlapping` 命中即回调。
- `程序/ui/script_find_bar.py:48-67,114-141`：构造新增 `headings=`/`reveal=` 注入；`headings` 给定时出「只在标题里找」Checkbutton（`titles_only`）；`_positions` 按标题行号过滤；`_highlight` 先 `reveal(行号)` 再高亮（折叠段自动展开）。
- `程序/ui/script_reading.py:24-25,156-419`：`_FOLD_TAG='script_fold'`／`_CURSOR_SEGMENT='script_cursor'`；`refresh_fold_support`／`heading_lines`／`fold_marks`／`_apply_elide`（elide 施加在标题行下一行到下一标题行的间隙，标题行不收）；`toggle_fold`（含子标题）、`fold_all`／`expand_all`、`ensure_line_visible`；`context_menu` 按 REQ-S02-39 十三键构建（非编辑态仅「编辑／复制／全选／查找…／大纲／全部折叠／全部展开」可用，只读连「编辑」也置灰，空文档退化五键置灰），有文档且 `box.open_any_document` 可调时追加「打开其他文件… (Ctrl+O)」，写 `session.last_menu`；`select_all` 把选区归一到 `end-1c`；`goto_line`（`goto_ask` 由宿主注入，行号钳位／标题子串，先 `ensure_line_visible` 再高亮定位）；`update_cursor_status` 写 `script_cursor` 段（行号·所在集场·全文字数·mtime HH:MM）；`release()` 销毁清段；`install_reading_shortcuts` 增登 Ctrl+G。
- `程序/ui/desktop_script_pages.py:32,46-48,739-767,838`：引入 `ask_string` 并注入 `aids.goto_ask`（`script_reading` 不新增 ui_widgets 同层边，修 LR-03 门禁红）；提示串补 Ctrl+G；`gutter.set_fold_support`；FindBar 传 `headings`/`reveal`；`<Button-3>` 无 `add` 重绑到 `aids.context_menu`（覆盖会话旧菜单）；`<Destroy>` 挂 `aids.release`；`<<Modified>>` 挂 `schedule_reading_views`。
- `程序/tests/test_script_outline.py`、`test_script_line_numbers.py`、`test_script_find_bar.py`、`test_script_context_menu.py`、`test_desktop_script_pages.py`：新契约用例（段表/段末、标记点击、只在标题里找、十三键菜单与非编辑/只读/空文档三态、折叠命中自动展开、Ctrl+G 双口径、状态段文案）；`test_script_context_menu` 夹具改用生产同款装配（FindBar/OutlinePanel 放 grid 宿主——pack 容器里 grid 会被 TclError 吞掉）。
- `程序/docs/stages/S02_剧本结构.md`：REQ-S02-39/40/43 状态、DES-S02-39/40/43 做法与测试锚定更新。

## 验收命令与退出码

1. `run_selftests.py -k script_structure script_context_menu script_outline script_line_numbers script_find_bar desktop_script_pages` → 退出码 0。尾部：`共 118 条用例，38.0 秒；0 个文件有红` → `ALL TESTS PASSED`。
2. `smoke_test.py --affected desktop_script_pages script_reading script_find_bar script_outline script_line_numbers` → 退出码 0。尾部：`通过：10 项　失败：0 项` → `✅ 冒烟测试通过`（定向自检 17 个测试模块 0 红）。
3. `smoke_test.py --architecture` → 退出码 0。尾部：`Ran 708 tests in 242.034s` → `OK` → `✅ 架构治理测试：tests/architecture`。

## 「建议，待确认」项（用户 11-23 授权按推荐执行）

- DES-S02-40 按做法甲实现：折叠用 Tk Text 标签 `script_fold` 的 `elide`（只藏显示不动文本，行号/查找/大纲/缩放/自动保存/采用失效不受影响），折叠标记画在 `LineNumberGutter` Canvas 上并响应点击。

## 未验证项

- 大文件折叠流畅度：未实测超过 `SCRIPT_VIEW_MAX_CHARS` 级别文档的折叠耗时；实现与大纲同源（超限 `spans` 返回空、不产生标记，折叠无成本），界面只做 elide 标签增删与行号槽增量重绘，不写未测承诺。
- 隐藏桌面下 `event_generate('<Button-3>')` 对「从未有过内容的 Text」不派发（实测 x=5／x=0／无坐标三种都不触发任何 bindtag，非空 Text 正常）：空文档菜单断言改为直接调用同一绑定回调覆盖；真实页面控件已映射，原生右键不受影响（真页面 `test_editor_menu_full_order_on_real_page` 走 event_generate 全链路已绿）。

## 未运行

- `run_selftests.py --all --safe` 全量：分支轮次不累计，留待合入评估。
- `smoke_test.py`（默认冒烟）：未按本轮验收清单运行。

## 卡外发现（只记录，未顺手修）

- 隐藏桌面合成 `<Button-3>` 对空 `tk.Text` 不派发：Tk 行为，影响只限测试夹具层，已在 `test_script_context_menu.py` 注释记档。

## 回滚

`git revert` 本轮提交。
