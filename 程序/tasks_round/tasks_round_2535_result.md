# R2535 结果：功能轮——剧本结构页编辑时内容框扩展到整页，退出自动复原

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（用户点名的新交互）——剧本结构页：点「自然剧本」编辑，本框向下扩大盖住结构剧本框；点「结构剧本」编辑，本框向上扩大盖住自然剧本框；退出编辑自动复原成上下各占一半。保存不退出编辑（R1864/R1958 既有契约钉住），故复原只发生在「退出」时，保存后仍保持扩展。

2. **测试跑了吗、三个基线过了吗？**
   - 定向 `run_selftests.py -k script_structure expand_edit ui_reading req_anchor_s02`：**79 条 0 红**（新增 `test_script_structure_expand_edit` 2 条用例：上框扩下、下框扩上、保存不塌、退出复原）。
   - 默认冒烟 `smoke_test.py`：**8/8**。
   - 架构门禁 `dev.py arch`：**419/420**。唯一红 `test_round_number_continuous`（状态页 2514 ≠ 最新结果文件+1）：`git stash` 全部改动后单跑该用例**改前同红（2514 ≠ 2523）**，属分支固有状态——结果文件号已超前派生点状态页轮次，`project_status.md` 仅 master 合并时推进，与本轮源码无关。

3. **`project_status.md` 的欠账少了吗？**
   不增不减；本轮无新欠账。

## 改动清单

- `程序/desktop_script_pages.py`：
  - `_ScriptStructurePage`：新增 `split_boxes` 台账与 `expand_editing_box()`／`restore_split_boxes()`；`content_box()` 保留 `_ContentBox` 实例入台账。
  - `_ContentBox.build()`：`self.frame` 记录内容框外框。
  - `_install_script_edit_controls`：`begin_edit` 成功后调 `box.owner.expand_editing_box(box)`（本框 `grid_configure(row=0, rowspan=2)` 占满两行，另一框 `grid_remove` 暂离布局）；`exit_edit` 调 `restore_split_boxes()`（编辑框回原行 `rowspan=1`，另一框 `grid()` 按记忆复原）。底部动作栏（采用/手动制作）保持可见。
- `程序/tests/test_script_structure_expand_edit.py`（新增）：真实窗口两向扩展/复原断言，含「保存后仍扩展、退出才复原」契约。
- `程序/tests/test_script_structure_edit.py`：假内容框补 `owner` 桩（扩展/复原空实现）；断言未动。

## 环境说明

- 工作树内并存其他车道的未提交改动（`project_status.md` 瘦身、`docs/review/优化任务书_SWE2_20261115.md`、`维护记录/工程闸门落地清单.md`），非本轮内容，未暂存、未回退。

## 提交

- 轮次类型：功能轮；经 `dev.py claim` 领取 R2535（分支 `codex/wip-R2535`）。
- 本轮已提交：仅 `desktop_script_pages.py`、两个测试文件、本结果文件；**未合入 master、未 push**。
- 页面改动需重启应用生效。
