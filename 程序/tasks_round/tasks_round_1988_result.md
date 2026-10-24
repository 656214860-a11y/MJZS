# R1988 writing 页页面服务注入（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J2**（顺序第一页：writing）。基线：R1987（9061fb97）。日期：2026-10-24。

## 改动

- `desktop_writing_page.py`：新增不可变 `WritingPageServices`（`open_path`、`context_menu`、`confirm`、`confirm_project_removal`，只放该页实际用到的四项）；删除对 `desktop_page_support` 全局宿主转发的导入；七处调用改为 `self.page.writing_page_services.<名字>(...)`。
- `desktop.py`：`Desktop.__init__` 新增可选参数 `writing_page_services`；默认服务在 `_init_window_and_sidebar` 里用 lambda 在调用时取 desktop 模块的 `open_path`／`ContextMenu`／`confirm`／`confirm_project_removal_from_last_script`，所以测试按 `desktop.<名字>` 打补丁照常生效。
- `architecture.md` R1606／O8 节追加 R1988 说明与剩余页面清单（storyboard、project、asset、media）。`desktop_page_support.bind_host`／`_HostAttribute` 仍被其余页面使用，不删。

## 测试

- 新增 `tests/test_writing_page_services.py`（5 条，无 Desktop／Tk 主窗口，`desktop_page_support._host` 置 None 证明不依赖全局宿主）。
- `tests/test_writing_restart.py` 的 `script_menu` 桩原来把 `ContextMenu` 注入 exec 命名空间，现改为经桩的 `writing_page_services.context_menu` 提供：契约有意变更只同步 mock，**断言未动**。

## 验证（本轮实测）

- `run_selftests.py -k writing script idea_chat recon ui_edges test_core test_integration timers desktop_startup_perf desktop_automation`（经 gui_hidden）：880 条，128 条红。在干净 HEAD 的临时 worktree 上用同一关键词复跑：875 条，同样 128 条红，红用例名集合逐条相同（`diff` 为空）。红因是本工作树缺 skills 文件（FileNotFoundError 等），与本轮无关；多出的 5 条是新增测试，全部通过。
- `smoke_test.py --architecture`：410 条，仅 3 条既有红（缺基准历史.json、状态页仅 master 可改、skill 引用检查）。
- 默认 `smoke_test.py`：通过。未跑 `--all --safe`，全量欠账 +1。

## 回滚

`git revert` 本轮提交。

## 下一步

J2 第二页：storyboard 页服务注入。
