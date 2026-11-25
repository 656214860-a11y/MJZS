# R4433 结果：UX-DOC-S01-SYNC S01 阶段文档与需求追溯同步（纯文档轮）
<!-- round-evidence: {"commit_base": "e292ef283", "credential_hits": 0, "evidence_sha256": "173f5067e5c510cf", "exit": 0, "failed": 0, "passed": 0, "round": 4433, "tests": "docs-only"} -->

## 开头三问

1. **本轮类型**：纯文档同步轮（卡面 UX-DOC-S01-SYNC，波次 W2，车道 `codex/ux-example-locks`，基准 `e292ef283`）。只改 `docs/stages/S01_剧本准备.md` 与 `docs/records/对话需求追溯.md`，把 UX-C1、UX-FP-NOTIFY、UX-FP-IMPORT、SEND-2 已合入主干的真实轮次、合入提交与测试锚点同步进文档；未改任何 `.py`。
2. **测试与三个基线**：卡面验收 `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage` → 34 条用例 0 红，退出码 0。默认冒烟、`--affected`、全量 `--all --safe` 未跑（纯文档轮，卡面未列）。
3. **欠账少了吗**：少了。REQ-S01-102／103 由 🟡 转 ✅，REQ-S01-105 的占位符与轮次号补齐；REQ-S01-101 功能已落地但无挂本编号的测试锚点，按 REQ-S01-110 先例如实保持 🟡；REQ-S01-104 仍 ⬜ 未实现；追溯表 LOST-08 由 ⬜ 转 ✅。无新增欠账。

## 核实依据（git log／源码／测试逐一核对）

- UX-C1（LOST-08，右侧文件面板图标改版）：实现 R4222（`368f88585`）→ 合入 R4227（`e4f0c15c1`）；`git log --oneline --all --grep` 核实。
- UX-FP-NOTIFY（REQ-S01-101/102 面板侧）：实现 R4297（`687930b98`）→ 合入 R4310（`68326e2c7`），同上核实。
- UX-FP-IMPORT（REQ-S01-103）：实现 R4361（`6e6c1bb94`）→ 合入 R4369（`24ce952ae`），同上核实。
- SEND-2（REQ-S01-105）：实现 R4424（`6ab6ee487`）→ 合入 R4432（`e292ef283`），同上核实；`tasks_round_4424_result.md` 存在且含「全链路盘点表」节（该文件第 10–28 行）。
- 消费端接线（`git log -S set_select_handler`＋源码）：
  - 剧本结构页 `ui/desktop_script_pages.py:596-601` 登记 `set_select_handler(page_index, show_document, default=…)`，注释引 REQ-S01-102＋REQ-S02-38，R4358（UX-S02-ONE-EDITOR，`1fb0d4c85`）加入。
  - 初步分镜页 `ui/storyboard_files.py:702-713` 登记 `set_select_handler(PAGE_OF['storyboard'], show_document, default=…)`，R4380（`7b2354c9e`）加入。
  - `ui/` 全目录仅此两处消费登记；接口实现在 `ui/desktop_files_panel_filters.py:679`（`set_select_handler`）与 `:698`（`_notify_file_select`）。
- 测试锚点（tests/ 目录 grep）：REQ-S01-102 锚定 `tests/test_files_panel_stages.py` 6 条 docstring（:1001–1091，`DockContentTests`）；REQ-S01-103 锚定 `tests/test_files_panel.py:435`（`FilesPanelImportTests`）；REQ-S01-105 锚定 `tests/test_desktop_shared_input.py:293`（`EmptySendFallbackEntryTests`）。**REQ-S01-101 无任何锚点**，`维护记录/需求锚定基线.json` 的 `untested_done` 为 `[]`——升 ✅ 必红 `test_new_done_requirement_needs_a_test_anchor`，且本卡禁改 `.py`，故如实保持 🟡。
- 锚定表旧文「FollowedStageViewTests」类名不存在，实际类名为 `DockContentTests`（`test_files_panel_stages.py:840`）；103 的测试在 `test_files_panel.py`（仓库无 `test_files_panel_import.py`）。

## 改动明细

- `docs/stages/S01_剧本准备.md`：
  - 小节标题去掉「（目标，大部分未实现）」；导语改为「REQ-S01-101/102/103/105 已按各条括号内轮次落地，仅 REQ-S01-104 未实现」。
  - REQ-S01-101：保持 🟡——面板侧 R4297／合入 R4310，消费端剧本结构页 R4358、初步分镜页 R4380 已登记 `default` 预选；仍缺挂本编号的测试锚点（现用例挂 102 名下），其余页面登记按原文属建议待确认。
  - REQ-S01-102：🟡→✅，补 UX-FP-NOTIFY R4297／合入 R4310 与消费端 R4358（REQ-S02-38）／R4380。
  - REQ-S01-103：🟡→✅，补 UX-FP-IMPORT 实现 R4361／合入 R4369，去掉「实现轮次号见结果文件」占位话术。
  - REQ-S01-105：补「实现 R4424、合入 R4432」，两处 `tasks_round_<N>_result.md` 占位符改为 `tasks_round_4424_result.md`。
  - DES-S01-101/102/103/105 括号状态与轮次号同步；REQ/DES-S01-104 保持 ⬜ 未动。
  - 测试锚定表：原「REQ-S01-101 至 REQ-S01-105」合并行拆为五行，按实测测试文件与类名逐条登记（101 如实注明无本编号锚点）。
- `docs/records/对话需求追溯.md`：LOST-08（UX-C1）⬜→「✅ 已实现（R4222，合入 R4227）；拆分去向 UX-C1 已收口」。表内无其他对应 UX-FP-NOTIFY／UX-FP-IMPORT／SEND-2 的 ⬜ 条目；LOST-06/09、HALF-01/02/03 等范围外条目未动。

## 验收

- `run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage`：34 条用例、0 红，退出码 0。

## 未验证项与卡外记录

- REQ-S01-101 缺测试锚点属既有事实，本卡禁改 `.py` 未补；其余阶段页面是否登记默认选中按原条目属建议待确认。
- 全量 `--all --safe`、默认冒烟未跑（纯文档轮，卡面未列）。
- 卡外发现（未动）：`### 共享输入框候选用途与编辑（十三阶段目标，未实现）` 标题里「未实现」与其下 REQ-S01-106/107 已实现状态不一致，超出本卡范围，仅记录。
