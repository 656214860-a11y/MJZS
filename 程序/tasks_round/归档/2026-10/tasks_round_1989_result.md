# R1989 storyboard 页服务注入（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J2**（第二页：storyboard）。日期：2026-10-24。
基线：`codex/wip-R1988` @ f5f633b4（R1988）。零行为变更。

## 改动

- `desktop_storyboard_page.py`：新增不可变 `StoryboardPageServices(open_path, file_dialog, confirm)`；`view_frame_image`、`replace`、`delete_checked_frames` 三处改走 `self.page.storyboard_page_services`；不再导入 `desktop_page_support` 的 `open_path／FileDialog／confirm` 全局宿主转发（常量 `ASSET_ROW_HEIGHT／THUMB_SIZE` 仍从该模块取）。
- `desktop.py`：`Desktop.__init__` 增加 `storyboard_page_services=None` 参数；`_init_window_and_sidebar` 按调用时取 desktop 模块名字的 lambda 构造默认服务，测试补丁 `desktop.open_path／FileDialog／confirm` 的位置不变。
- 新增 `tests/test_storyboard_page_services.py`（4 条，不建 Desktop／Tk，`desktop_page_support._host` 置空也能跑）。
- `architecture.md` R1606/O8 节登记 R1989；剩余走全局宿主的页面：project、asset、media（idea_menus 随 project）。

## 验证（本轮实测）

- `run_selftests.py -k keyframe storyboard frame ui_edges timers desktop_startup_perf test_core test_integration`（经 gui_hidden）：528 条，0 红，1 条登记跳过（缺 bundled skill，与本轮无关）。
- `smoke_test.py --architecture`：410 条，2 失败 1 错误，均为已知历史红：`test_agents_md`（缺基准历史.json）、`test_round_baselines`（状态页只在 master 同步）、`test_skill_reference_injection`（worktree 缺 skills 文件）。共享状态棘轮与复杂度棘轮通过。
- 默认 `smoke_test.py`：8 项全通过。
- 既有测试断言未动，也未改 mock；本轮无需同步任何旧测试。
- 未跑 `--all --safe`，全量欠账 +1。未在真实窗口目测首帧页的打开／替换／批量删除。

## 回滚

撤回上述三个文件与 architecture.md 的改动，删除新测试。

## 下一步

J2 第三页：project（含 idea_menus）。
