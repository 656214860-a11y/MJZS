# R2421 结果：气泡框滑块加速、右键展开/收起、SKILL 提示移回框外

## 三个必答（§7）

- **轮次类型**：功能轮（§3.1）——三项交互/视觉调整：聊天框滚轮加速、右键菜单加展开/收起全文、SKILL 页脚移回底框外。
- **测试跑了吗、三个基线过了吗**：
  - 定向 `run_selftests.py -k test_idea_chat test_req_s01_anchors test_script_composer`：**171 条，0 红，ALL TESTS PASSED**（新增右键展开/收起、滚轮加速 2 条用例）。
  - 默认冒烟 `smoke_test.py`：**8/8 通过**。
  - 架构门禁／全量：未跑（本轮改 L4 气泡渲染 + 滚动 + 菜单，不命中 §5 触发条件）。
- **project_status.md 的欠账少了吗**：无新增欠账。

## 本轮内容

1. **聊天框滚轮加速**（`desktop_layout.py`）：新增 `IDEA_LOG_WHEEL_LINES = 5`，`scroll_page` 识别到 `idea_log` 时 `yview_scroll(steps * 5, 'units')`，一格滚 5 行（气泡消息跨多行，默认 1 行太慢）；其余 Text/表格仍一格一行。
2. **右键菜单加展开/收起全文**（`desktop_idea_menus.py`）：`open_bubble_menu` 在悬停气泡上右键时，按 `_bubble_full[name]['expanded']` 给出「展开全文」或「收起全文」，转调既有 `toggle_bubble`；空白处/示例不出现该项。
3. **SKILL 提示移回框外**（`desktop_idea_bubbles.py`）：页脚 tag `bubble_<n>_time` 恢复贴框左边沿（`lmargin=left`）、不铺底色、`justify='left'`＋`wrap='none'`；`refit_bubbles` 相应只给正文 tag 补内边距。

## 改动文件

- `desktop_layout.py`（滚轮加速）
- `desktop_idea_menus.py`（右键展开/收起）
- `desktop_idea_bubbles.py`（页脚回框外）
- `docs/stages/S01_剧本准备.md`（REQ-S01-65/66、DES-S01-65 同步）
- `tests/test_idea_chat.py`（页脚框外断言、右键展开/收起、滚轮加速 3 组用例）

## 提交

- 提交信息：`R2421: 气泡框滑块加速、右键展开/收起、SKILL 提示移回框外`
