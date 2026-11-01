# R1992 project 页（含 idea_menus）服务注入（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J2**（第三页：project，idea_menus 随同）。日期：2026-10-24。
基线：`codex/wip-R1989` @ 94e73c76（R1989）。零行为变更。

## 改动

- `desktop_project_pages.py`：新增不可变 `ProjectPageServices(open_path, context_menu, confirm)`；项目切换确认、失效登记清除、项目回收确认、练习项目与当前项目目录打开、项目右键菜单共 10 处改走 `self.project_page_services`；不再导入 `desktop_page_support` 全局宿主转发。
- `desktop_idea_menus.py`：5 处 confirm／open_path／ContextMenu 同样改走 `self.project_page_services`（与项目页共用同一个服务对象，不另立第二个类）；不再导入全局宿主转发。
- `desktop.py`：`Desktop.__init__` 增加 `project_page_services=None`；`_init_window_and_sidebar` 构造默认服务（调用时取 desktop 模块名字的 lambda），`desktop.confirm／open_path／ContextMenu` 补丁点不变。
- 新增 `tests/test_project_page_services.py`（5 条，不建 Desktop／Tk，`desktop_page_support._host` 置空也能跑）。
- 两个测试的 MagicMock 宿主补同步：`tests/test_project_switch_guard.py`、`tests/test_project_rename_reconcile.py` 各加一个带真服务的 `app.project_page_services`，让 `desktop.confirm` 补丁继续生效。**断言未动**。
- `architecture.md` R1606/O8 节登记 R1992；仍走全局宿主的页面只剩 asset、media。

## 验证（本轮实测）

- 定向 `run_selftests.py -k project_switch project_rename project_page ui_batch4 ui_motion test_core ui_edges integration timers desktop_startup_perf storyboard`（经 gui_hidden）：445 条，0 红。
- `-k idea project ui_batch4 ui_motion` 与干净 HEAD（R1989）逐条比对：本改动后 31 红，基线 32 红，红项集合是基线的子集，无新增（均为 worktree 缺 skills 文件的既有红；基线多出的 1 条疑似并发抖动，不当作本轮修复）。
- `-k writing` 的既有红与基线一致（缺 skills 文件），未逐条再比。
- `smoke_test.py --architecture`：410 条，2 失败 1 错误，均为已知历史红（`test_agents_md`、`test_round_baselines`、`test_skill_reference_injection`）；共享状态与复杂度棘轮通过。
- 默认 `smoke_test.py`：8 项全通过。
- 未跑 `--all --safe`，全量欠账 +1。未在真实窗口目测项目切换、右键菜单、创意对话附件删除。

## 回滚

撤回 `desktop.py`、`desktop_project_pages.py`、`desktop_idea_menus.py`、`architecture.md` 与两个测试的同步，删除新测试。

## 下一步

J2 第四页：asset；之后 media，最后删除 `desktop_page_support` 的 `bind_host`／`_HostAttribute`。
