# R1964 功能轮：剧本准备页文件名悬停预览卡片

## 需求
剧本准备页「项目设定／项目大纲／角色卡／项目剧本」四张文件表，列窄时文件名被截断读不全。鼠标悬停在文件名上时显示预览卡片，方便读取文件全名。

## 原状
四张表原来已挂 `TreeRowTooltip`，但浮层只有一行 `row.name` 加修改时间，且 `row.name` 是 `script_workspace_service._document_display_name` 的展示名：历史文件的模型目录段会被改写成 Provider（如 `…_Google_…`），并不是磁盘上的真实文件名，所以悬停也读不到真名。

## 改动
- 新模块 `desktop_file_card.py`（L4）：`TreeRowCard`（继承 `TreeRowTooltip`，首行粗体折行作标题，其余行为说明）和 `script_row_card()`（拼卡片文本）。
- 卡片内容：首行磁盘上的完整文件名；展示名与真名不同时多一行“列表显示”；有状态标记时“状态”；修改时间；相对项目目录的“位置”。全部取自行加载时已有的数据，悬停不读磁盘（沿用 `TreeRowTooltip` 约束）。
- `ui_widgets.Tooltip`：把浮层内容构建抽成 `_populate(tip)`，边框、定位、出屏处理仍统一在 `show`；默认实现与原来完全一致。
- `desktop_writing_page.py`：四张表改用 `TreeRowCard`，行文本改调 `script_row_card`。
- 架构登记：`tests/architecture/_layers.py` 登记 `desktop_file_card`（L4）；覆盖率基线刷新到 309 个模块，`runbook.md` §11 的数字同步为 309／259。

## 测试
- 新增 `tests/test_script_file_hover_card.py`（5 条）：卡片首行为粗体全名、详情在下；无详情只有标题；离开后收起；悬停期间 `open`/`scandir` 被禁；卡片文本在展示名与真名不同时多“列表显示”行、相同且无状态时省略、项目外路径退回绝对目录。
- 既有断言未动：`test_desktop_compact_layout`（文件名与修改时间都在提示中）、`test_ui_compact_widgets` 全绿。

## 验证（经 `gui_hidden.py`）
- `-k architecture ui_ writing_page script_file desktop_compact`：746 条，仅余 3 个历史红：`test_agents_md`、`test_skill_reference_injection`（worktree 缺文件）、`test_round_baselines`（状态页只能在 master 同步）。
- `smoke_test.py` 默认集通过。
- 未跑 `--all --safe`；未在真实窗口目测。

## 未做
卡片不含文件内容预览（那需要悬停时读盘，与现有“悬停不读磁盘”约束冲突）；如需内容摘要，应在加载阶段缓存或后台读取，另立一轮。
