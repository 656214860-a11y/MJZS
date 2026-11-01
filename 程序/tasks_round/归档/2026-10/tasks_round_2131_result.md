# R2131 结果：剧本准备页输入框空框高度由一行增为两行（功能轮）

## 需求（用户原话）
剧本准备页的输入框高度向上增高一倍。

## 改动（`desktop_writing_page.py`）
- 新增 `COMPOSER_MIN_LINES=2`、`COMPOSER_MAX_LINES=8`：输入框初始 `height` 与 `fit_composer()` 的下限由 1 改为 2，按内容撑开的上限仍为 8 行（原魔法数字 8 改为常量）。输入区 pack 在页面底部，增高部分向上长。
- 占位提示 `input_hint` 由「按输入框中线垂直居中（rely=0.5, anchor='w'）」改为「对齐首行左上（y=0, anchor='nw'）」，避免两行框里提示落在两行之间。

## 测试（契约有意变更，同步断言，未弱化）
- `tests/test_idea_chat.py`：空框高度、点击空框后高度稳定、点击提示后高度三处断言由 1 改为 2。
- `tests/test_ui_edges.py`：`test_the_writing_page_gives_the_brief_more_room` 空框高度 1 改 2；提示定位断言由 `rely=0.5／anchor=w` 改为 `anchor=nw`，并新增「提示顶边与首行顶边对齐（±3 像素）」的几何断言；横向对齐断言未动。

## 验证（本轮运行，经 gui_hidden）
- `run_selftests -k ui_edges idea_chat script_composer writing_restart`：289 条，全通过。
- `smoke_test.py`：通过。
- `smoke_test.py --architecture`：410 条，剩 1 项既有红 `test_performance_history_is_declared_as_historical_only`（worktree 下基准历史.json 未入库），非本轮引入。

## 未验证
- 未在真机界面截图确认视觉效果。
