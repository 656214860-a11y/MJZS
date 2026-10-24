# R1987 迁移生产调用方对 auto 旧属性名的写入（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J1b**。基线：R1985（c4ce468f）；R1986 号已被其他车道领取，本轮领 R1987。日期：2026-10-24。

## 改动

- 盘点（按 `AutoState` 62 个字段的旧名在全部生产 `.py` 中 AST 外的正则扫描）：仍用旧名的生产调用方只有 `desktop_asset_pages.py`（6 处）、`desktop_media_pages.py`（11 处）和 `desktop_auto_flows.py` 里 3 处 `getattr(self,'auto_*',False)`。`desktop_async_tasks.py`、`desktop_script_pages.py` 实际没有字段旧名：前者只有 `_auto_edit_result_poll_id`／`_auto_handoff_result_poll_id` 两个计时器句柄，后者没有，都不是 `AutoState` 字段，保持不动（计时器句柄归 J4 的计时器登记表）。R1983 报告里这两处的计数口径是前缀，不是字段。
- 上述 20 处机械改为 `self.auto.<字段>`。`getattr(self,'auto_edit_busy',False)` 等三处改为直读：`auto` 对半成品对象懒建默认状态，`edit_busy`／`handoff_busy` 默认 False，`adopt_startup` 默认 True（原 getattr 默认 False 只在半成品对象上生效，生产对象恒为 True）；相关测试全绿。
- 未改转发（`AutoStateAliasesMixin`）：测试仍用旧名。生产调用方清零后是否退役另立契约轮。

## 验证（本轮实测）

- `run_selftests.py -k desktop_automation_service req_s07 desktop_auto_state test_core test_integration ui_edges timers desktop_startup_perf keyframe asset_page media`（经 gui_hidden）：473 条，0 红。
- `-k final_viewer auto adopt unattended script_page async`：105 条，0 红。
- `smoke_test.py --architecture`：410 条，仅剩 3 条既有红（缺基准历史.json、状态页仅 master 可改、skill 引用检查）；共享状态棘轮仍为 Desktop 43，未变（旧名转发不是 `self.X=` 赋值，本轮清零的是读写旧名，不改多写者计数）。
- 默认 `smoke_test.py`：8 项通过。未跑 `--all --safe`；全量欠账 +1。

## 回滚

`git revert` 本轮提交。

## 下一步

J2 页面服务注入（writing 页起）。
