# R4222 结果：UX-C1 右侧文件面板图标改版（Cursor 停摆后的监督验证收口）

<!-- round-evidence: {"commit_base": "6e687b94", "credential_hits": 0, "evidence_sha256": "8bcd28d534cb4ff7", "exit": 0, "failed": 0, "passed": 183, "round": 4222, "tests": "run_selftests.py -k ui_icons files_panel"} -->

## 开头三问

- （一）本轮属于哪种类型：编码卡 UX-C1 的收口轮。Cursor 面板卡 34 号于 2026-11-23 23:12 认领，改到 23:27 后对话停摆（README 空等机制等用户确认），8 个文件半成品留在车道 `ux-dock-icons`。总监督按「发现阻塞立即优化」的授权验证半成品：改动与卡面目标一致、三条验收命令全绿，故代提交，不重做。
- （二）测试跑了吗、三个基线：卡面三条验收命令全绿——① `run_selftests.py -k ui_icons files_panel` ALL TESTS PASSED；② `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` ALL TESTS PASSED；③ `smoke_test.py --architecture` Ran 700 tests OK。反向验证（撤掉产品改动看用例变红）未做。
- （三）欠账少了吗：少了。UX-C1 从「在派但停摆」收口为待审交付，解开 MERGE-UX-C1 → UX-FP-NOTIFY → UX-S02-ONE-EDITOR 链条。

## 为什么由总监督收口

- Cursor 对话 23:27 后无任何文件与队列活动（KEEP-WATCH 停在 22:25、claims 停在 23:12），半成品滞留在车道，直接卡住结构剧本页改版（UX-S02-ONE-EDITOR）的两条前置链之一。
- 半成品验证结论：改动与卡面目标一致（去掉面板内与入口重复的「全部文件」图标；⚙/♻/🗑 四个字符按钮换成与侧栏同套的 Filled 图标：library_settings/recycle/recycle_purge），测试全绿，无需返工。
- Cursor 卡面注明「复核由验收窗口负责，你不合入、不 push」，监督代提交后仍标待审由验收独立复核。

## 改了哪些文件（均为 Cursor 遗留半成品，监督未改内容）

- `程序/ui/desktop_files_panel_filters.py`：侧栏去掉「全部文件」重复图标；四个动作按钮经 `_make_rail_icon_button` 统一为 Filled 图标；全项目视图由入口打开、`show_stage(None)` 复位。
- `程序/scripts/build_nav_icons.py`：新增 library、library_settings、recycle、recycle_purge 四个图标映射。
- `程序/assets/nav/library.png`、`library_settings.png`、`recycle.png`、`recycle_purge.png`：新图标文件（有效 PNG）。
- `程序/tests/test_ui_icons.py`、`程序/tests/test_files_panel_stages.py`：新增/调整用例。
- `程序/tasks_round/tasks_round_4222_result.md`：本文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k ui_icons files_panel` | ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` | ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | Ran 700 tests OK（304 秒） |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 领到轮次 4222 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4222: UX-C1 …" --tests ui_icons files_panel …` | 见提交证据 |

## 未验证

- 真实界面未点过：图标观感（PNG 尺寸/对齐）请验收窗口在桌面应用或截图基线上确认。
- Cursor 停摆时的最后一步是否完整（比如它是否还差一步「验证四条命令条数」）无法确认；三条卡面验收命令均已重跑全绿。
- 全量 `--all --safe` 未在本车道跑；合并轮出口 CI 会重跑。
