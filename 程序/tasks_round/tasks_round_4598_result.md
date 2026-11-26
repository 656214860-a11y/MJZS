# R4598 轮次结果（S04-W2：右侧项目文件面板「临时声音」默认展开与分组计数）
<!-- round-evidence: {"commit_base": "044b88c9f", "credential_hits": 0, "evidence_sha256": "20d7a9015c059d03", "exit": 0, "failed": 0, "passed": 232, "round": 4598, "tests": "run_selftests.py -k files_panel_stages copy_rules"} -->

- **本轮属于 §3 哪种类型**：3.1 功能轮（执行《分镜预演工作台与管理预览审核改造任务书》卡 `S04-W2`，落地 `REQ-S04-117` 与 `DES-S04-40`）。
- **测试跑了吗、三个基线过了吗**：已运行——隐藏桌面 `tests.test_files_panel_stages` 与 `tests.test_animatic_page.DebounceAndPanelPerfTests.test_async_dispatch_and_s04_panel_four_groups_contract` 215/215 通过（240.78s）；文案与核心架构门禁 5 组（`test_copy_rules`、`test_requirement_traceability`、`test_module_size_ratchet`、`test_static_names`、`test_static_hygiene`）39/39 通过（22.99s）；默认冒烟 `smoke_test.py` 9/9 通过（含隐藏桌面探针）；全量安全回归留待收尾／合并轮按口径执行。
- **欠账少了吗**：`REQ-S04-117` 与 `DES-S04-40` 翻绿为 ✅ 并完成测试锚定；`ui/desktop_files_panel_index.py` 保持 597/1000 行，`_MEDIA_PREFETCH_CAP = 40` 与「镜头草图」默认折叠红线完整保留，零新增欠账。

## 改动清单

- `程序/ui/desktop_files_panel_index.py`：
  - `ANIMATIC_GROUP_SPECS` 中 `('audio', '临时声音', False)` 改为 `('audio', '临时声音', True)`；`('shots', '镜头草图', False)` 保持默认折叠。
  - `animatic_grouped_rows(rows)` 分组标题输出改为 `'%s (%d)' % (label, len(buckets[key]))`，实时反映每组文件数量；`_MEDIA_PREFETCH_CAP = 40` 与排除 `.work/` 逻辑不变。
- `程序/tests/test_files_panel_stages.py`：同步 `test_animatic_panel_four_groups_collapse_and_prefetch_throttle` 并新增 `test_req_s04_117_3000_shots_collapsed_with_count_and_prefetch_cap`（锚定 `REQ-S04-117`，验证 3000 镜折叠与预取上限 ≤40）。
- `程序/tests/test_animatic_page.py`：同步 `test_async_dispatch_and_s04_panel_four_groups_contract` 对 `animatic_grouped_rows`／`group_default_open`／`prefetch_media_paths` 的契约断言，防止跨测试回归。
- `程序/docs/stages/S04_分镜预演.md`：`REQ-S04-117`、`DES-S04-40` 翻绿为 ✅ 并回填测试锚定。

## 既有测试契约变更说明（AGENTS.md §2.4）

因用户 Q7 拍板（`REQ-S04-117` 修订 `REQ-S04-109`）将右侧项目文件面板「临时声音」改为默认展开并为分组标题追加计数 `(N)`，同步以下两处断言：
1. `程序/tests/test_files_panel_stages.py` L1843–1903（`test_animatic_panel_four_groups_collapse_and_prefetch_throttle`）：分组标题断言更新为 `('参考图库 (2)', '预演版本 (1)', '镜头草图 (50)', '临时声音 (10)')`，`audio` 组改为断言默认展开并纳入预取，`shots` 组继续断言默认折叠且不进预取。
2. `程序/tests/test_animatic_page.py` L1600–1610（`test_async_dispatch_and_s04_panel_four_groups_contract`）：同步同一组 `animatic_grouped_rows` 计数标题、`临时声音` 默认展开及预取范围断言。

## 先红后绿证据

改动 `ui/desktop_files_panel_index.py` 前先更新上述测试并运行，实测全部先红：
- `test_animatic_panel_four_groups_collapse_and_prefetch_throttle`：`AssertionError: Tuples differ: ('参考图库', '预演版本', '镜头草图', '临时声音') != ('参考图库 (2)', '预演版本 (1)', '镜头草图 (50)', '临时声音 (10)')`
- `test_req_s04_117_3000_shots_collapsed_with_count_and_prefetch_cap`：`AssertionError: Lists differ: ['参考图库', '预演版本', '镜头草图', '临时声音'] != ['参考图库 (1)', '预演版本 (1)', '镜头草图 (3000)', '临时声音 (60)']`
- `test_async_dispatch_and_s04_panel_four_groups_contract`：`AssertionError: Lists differ: ['参考图库 (1)', '预演版本 (1)', '镜头草图 (50)', '临时声音 (1)'] != ['参考图库', '预演版本', '镜头草图', '临时声音']`

改动后 215/215 隐藏桌面测试、39/39 文案与架构测试、9/9 冒烟测试全部通过。

## 提交状态

- 工作树：`D:\漫剧制作助手\.agents\worktrees\s04-workbench-spec`
- 分支：`codex/s04-workbench-spec`（未 `git push`）
- 提交方式：经 `scripts/dev.py commit` 提交。
