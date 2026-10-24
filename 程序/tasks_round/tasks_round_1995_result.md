# R1995 media 页服务注入并删除全局宿主（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J2**（第五页：media，收尾）。日期：2026-10-24。
基线：`codex/wip-R1993` @ ae8f6fe3（R1993）。零行为变更。

## 改动

- `desktop_media_pages.py`：新增不可变 `MediaPageServices(open_path, file_dialog, confirm, open_studio, comfy_executable, find_editor_shortcut)`；全部调用点改走 `self.media_page_services`（局部函数 `confirm` 与方法 `find_editor_shortcut` 本身未动）。
- `desktop_script_pages.py`：`ScriptPageServices` 增 `confirm`，取代 `from desktop_page_support import confirm as page_confirm`。
- `desktop.py`：`Desktop.__init__` 改收 `**page_services`，六页默认服务由模块级 `_page_services()` 构建（`_late` 调用时取 desktop 模块当前值，`desktop.<名字>` 补丁点不变；未知关键字抛 `TypeError`）；`_init_window_and_sidebar(win, root, page_services)` 参数由 9 个降到 3 个（满足参数棘轮）；删除 `bind_host` 导入与调用。
- `desktop_page_support.py`：删除 `_host`、`bind_host`、全部转发函数、`_HostAttribute`、`messagebox`、`Desktop`；只留页面常量与 `_prefs`。**全局宿主已不存在，J2 完成。**
- 测试：新增 `tests/test_media_page_services.py`（3 条）；五个 `*_page_services` 测试删除不再需要的 `patch('desktop_page_support._host', None)`；`test_script_structure_edit.py` 的 `_FakePage` 带 `script_page_services.confirm`，取代对 `desktop_page_support.confirm` 的补丁；`test_script_page_services.py` 构造多一个 confirm；`test_ui_edges.py` 的 `Desktop.find_editor_shortcut(object())` 宿主改为带真 `MediaPageServices` 的对象。**断言均未动**，仅 mock／构造同步。
- `architecture.md` R1606/O8 节登记 R1995。

## 验证（本轮实测）

- 定向 `-k media comfy ui_edges test_core integration timers desktop_startup_perf script writing storyboard project asset keyframe audio delivery edit page_services pet`（经 gui_hidden）：剩余红仅 `test_writing_*`／`test_script_contract`／`test_workflow_writing_stages`（本工作树缺 skills 文件）与 `test_pet_ui` 6 条，均为已知既有红，与干净 HEAD 一致。
- `smoke_test.py --architecture`：410 条，仅 3 条已知历史红（`test_agents_md`、`test_round_baselines`、`test_skill_reference_injection`）；共享状态与复杂度（含参数数）棘轮通过。
- 默认 `smoke_test.py`：8 项全通过。
- 未跑 `--all --safe`，全量欠账 +1。未在真实窗口目测配音／后期／交付页。

## 回滚

撤回 `desktop.py`、`desktop_media_pages.py`、`desktop_script_pages.py`、`desktop_page_support.py`、`architecture.md` 与上述测试改动，删除新测试。

## 下一步

J3 媒体页逻辑下沉（`media_page_controller.py`）。
