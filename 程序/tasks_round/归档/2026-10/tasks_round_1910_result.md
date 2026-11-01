# R1910 修复轮：修 master 三条原有红（compact_layout、idea_chat、writing_status_line）

- **本轮类型**：修复轮（含全量基线验证）。起点 master `f91edfbc`，分支 `claude/fix-old-reds`。无对应队列 ID。
- **测试**：定向 `run_selftests.py -k test_writing_status_line test_desktop_compact_layout test_idea_chat test_workflow` 经 gui_hidden 全绿；架构门禁 394 条余 1 条错误，为 worktree 缺未入库的 `维护记录/基准历史.json`（已知环境问题）。全量待合入后在主仓库复跑。
- **欠账**：本轮修掉 R1904 后台全量 4 条红中的 3 条；`test_soak_light` 耗时红（11.2 秒＞10 秒）当时用户程序在跑，留待全量复核。

## 根因与改动
1. `test_desktop_compact_layout`（5＞4）：R1857 把侧栏按钮 `pady=2` 机械替换成 `SPACING['xs']`（4px），项目树与按钮间距超出 `2*row_gap+2`。`desktop.py` 侧栏按钮改为 `DESKTOP_LAYOUT['row_gap']*2`（还原 2px），非侧栏分支 `4` 改 `SPACING['xs']`（值不变）。
2. `test_idea_chat::test_process_poll_preserves_waiting_api_request`：R1853 有意把 `workflow_process_registry` 登记键规范化（`normcase(abspath)`），测试仍用原样 `str(proj)` 比较，永远对不上。改为 `registry._key(proj)`。同类写法另有 3 处 `assertFalse`（`test_idea_chat.py:1417`、`test_workflow.py:736/769`）此前因此恒真、被架空，一并改正，恢复其检验力。
3. `test_writing_status_line`：用例不设模型，依赖本机全局默认模型才显示「API 直连」；全量里前序用例留下的缓存使其解析为空（单独跑绿、全量红）。照同仓 `queued_api_request` 做法隔离：显式 `stage_config.put(..., model='deepseek-v4-flash')` 并把 `model_pool.pool` 固定为内建池。

断言未动（只改比较所用的规范化键与测试前置条件）。

- **提交**：`R1910: 修 master 三条原有红——侧栏按钮间距还原 2px、进程登记键测试按规范化键比较、状态栏用例隔离模型配置（修复轮）`；未推送。
