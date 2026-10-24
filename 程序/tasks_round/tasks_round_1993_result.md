# R1993 asset 页服务注入（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J2**（第四页：asset）。日期：2026-10-24。
基线：`codex/wip-R1992` @ 4ca2b6a1（R1992）。零行为变更。

## 改动

- `desktop_asset_pages.py`：新增不可变 `AssetPageServices(open_path, file_dialog, confirm)`；`AssetPagesMixin` 11 处、`_AssetPage.preview` 1 处调用改走 `asset_page_services`；`Desktop.asset_write_base`／`Desktop.asset_batch_gateway` 的类自引用改为 `AssetPagesMixin.<同名>`（两个方法只在 `AssetPagesMixin` 里定义，`Desktop` 无覆盖，解析结果相同）；不再从 `desktop_page_support` 导入 `Desktop／FileDialog／confirm／open_path`，只留页面常量。
- `desktop.py`：`Desktop.__init__` 增加 `asset_page_services=None`；五个默认服务（script／writing／storyboard／project／asset）统一改用模块级 `_late(名字)`，调用时按名字取 desktop 模块当前值，`desktop.confirm／open_path／ContextMenu／FileDialog` 补丁点不变。这样 `Desktop` 类体反而少了 9 行，复杂度棘轮 `Desktop` 上限 1269 → 1262（只降不升）。
- 新增 `tests/test_asset_page_services.py`（4 条，不建 Desktop／Tk，`desktop_page_support._host` 置空也能跑）。
- `tests/test_cell_menu.py` 的 `Stub(desktop.Desktop)` 绕过 `Desktop.__init__`，补一个带真服务的 `asset_page_services`，`desktop.confirm` 补丁继续生效。**断言未动**。
- `architecture.md` R1606/O8 节登记 R1993；仍走全局宿主的页面只剩 media。

## 验证（本轮实测）

- 定向 `-k asset cell_menu project ui_batch4 ui_motion ui_edges test_core integration timers desktop_startup_perf storyboard keyframe script_page writing_page services`（经 gui_hidden，`_late` 改造后复跑）：970 条，0 红。
- `test_asset_gating` 有一次单条红（缩略图用例），干净 HEAD 上通过，复跑本改动后也通过，判为并发抖动（运行器曾提示 SUSPECT_CONCURRENCY），未归因于本轮。
- `smoke_test.py --architecture`：410 条，2 失败 1 错误，均为已知历史红（`test_agents_md`、`test_round_baselines`、`test_skill_reference_injection`）；共享状态与复杂度棘轮通过。
- 默认 `smoke_test.py`：8 项全通过。
- 未跑 `--all --safe`，全量欠账 +1。未在真实窗口目测资产页导入、删除、预览。

## 回滚

撤回 `desktop.py`、`desktop_asset_pages.py`、`architecture.md`、`tests/test_cell_menu.py` 与复杂度上限的改动，删除新测试。

## 下一步

J2 第五页：media；之后删除 `desktop_page_support` 的 `bind_host`／`_HostAttribute`。
