# R1439 结果：侧栏切换项目先确认、任务运行中拒绝

三个收尾问题：
- 本轮类型：修复轮（用户误点侧栏切到别的项目，看不见文件却无从察觉）。
- 测试与基线：定向 `test_project_switch_guard`（新增 4 条）＋`test_project_rename_reconcile` 18/18；`run_selftests.py -k project desktop_startup ui_edges` 全绿；默认冒烟 8/8。未跑 `--all --safe` 全量，也未在真实窗口点选实机验证。
- 欠账：未减少，也未新增。

## 范围

`desktop.py` 一处，另有两个测试文件：

- `switch()`：侧栏单击不再直接打开项目，改走 `request_project_switch()`。
- `request_project_switch()`：`project_switch_blocker()` 报后台任务／创意对话请求中／剧本 Agent 运行中时拒绝并抛出可读原因；否则弹确认框，写明目标项目与当前项目；取消则 `restore_project_selection()` 把高亮放回当前项目。
- 当前项目行文字加「●」前缀（`project_row_text()`），`mark_current_project()` 在 `load()` 后原地改文字并把「当前项目：名称」写进窗口标题；不重建树。
- 项目首页的双击进入与启动续开路径不变。

## 测试

- 新增 `tests/test_project_switch_guard.py`：取消保持原项目并恢复高亮、确认框同时写出两个项目名、三类运行中任务不弹框直接拒绝、当前项目行带标记。
- `tests/test_project_rename_reconcile.py` 只补一行 mock 接线（`project_row_text`），断言未动。

## 背景

「文件找不到」的根因是用户误切到另一个项目，不是程序丢文件。随诊断一起出现的「创意文件丢失防护」未完成改动（`file_cache.py`、`idea_transcript.py`、`stage_execution_service.py` 等）因此弃用，存于 `git stash`（`创意文件丢失防护WIP(看错项目，已弃用)`），未提交。
