# R1779：剧本准备四类文件合并成一张整宽表 + 左侧阶段导航去滚动条（优化轮）

1. 本轮类型：§3.1 优化轮（UI）。来源：用户要求——侧栏不要滚动条；剧本准备页四张文件表（项目设定／项目大纲／角色卡／项目剧本）合并成一张。

2. 测试跑了吗、三个基线过了吗：
   - 定向 `run_selftests.py -k desktop_compact_layout test_idea_chat test_ui_edges test_writing_restart writing_page script_workspace responsive scroll_form checkbox column_fit row_targets architecture`：722 条，1 个文件有红（见「未通过项」，非本批引入）；GUI 测试均已执行，无延后。
   - 默认冒烟通过。
   - 真机：用户已试用，确认界面正常。
   - 完整安全全量：合入 master 后由 `scripts/auto_full_safe.py --run` 补跑，未跑前不写通过。

3. project_status.md 欠账少了吗：本轮改源码 +4（desktop_writing_page.py、desktop.py、responsive_ui.py、ui_tokens.py）；全量欠账由合入后补跑清账。

## 改动

- `desktop_writing_page.py`：四类文件合并成一张 `Script.Treeview`（`DataTable`），只留一个勾选列（表头即全选）、一个窄「类别」列（设定／大纲／角色卡／剧本）和一个占满剩余宽度的「文件名」列；行按类别分组、组内保持原顺序；表高按行数收紧，最多露出 `SCRIPT_FILE_MAX_ROWS`＝6 行，更多靠滚动条。右键菜单的阶段动作改按所点行的类别决定（`script_row_category`），不再按「点的是哪张表」判断。行提示 `TreeRowTooltip` 改为单实例按行取。
- `ui_tokens.py`：新增 `SCRIPT_KIND_COLUMN_WIDTH`＝56、`SCRIPT_FILE_MAX_ROWS`＝6。
- `responsive_ui.ScrollForm`：新增 `scrollbar=` 关键字（默认 True，行为不变）；`False` 时不建可见滚动条，仍可用滚轮／翻页键滚动。`desktop.py` 左侧阶段导航使用 `scrollbar=False`，省出一条竖栏的宽度。
- 测试随契约改动同步（`test_desktop_compact_layout`、`test_idea_chat`、`test_ui_edges`、`test_writing_restart`）：表由四张变一张，按行取类别；**断言目标不变**（仍断言标题、列、勾选列宽、右键菜单阶段动作等，只是数据来源从 `script_trees[category]` 变为 `script_tree` 与 `script_row_category`），无弱化。
- `tests/architecture/test_function_size_ratchet.py`：`writing` 因合并变短（实测 531 行），登记值 554→531，`open_manager` 497→493（实测）；只降不升。

## 未通过项

- `architecture.test_round_baselines.test_round_number_continuous`：状态页轮次头是 1776，最新结果文件已是 R1779，要求头＝最新结果＋1。`project_status.md` 只允许 master 提交（规则 41），合入 master 后单独补一次；分支上此项预期为红，非本批引入。

## 提交

- 已在分支 `claude/project-handoff-f6eb50` 提交，commit hash 见 git log `R1779:`。
