# R2107 补 REQ-S01-68 测试锚定、修正轮次连续性、复核 R2105 全量红项（修复轮）

轮次类型：修复轮。日期：2026-10-30。直接在 master `8a330a78`（R2105）上做，因为只有 master 能改状态页。复核的是 R2105 提交后 `--all --safe` 的 4 个红项（详见 `tasks_round_2105_result.md` 补记）。

| 红项 | 结论 | 处理 |
|---|---|---|
| `architecture.test_requirement_traceability` | REQ-S01-68（R2098 下载件按日期另存新批次）标 ✅，但 R2098 的 5 个测试没写需求编号 | 在 `tests/test_download_inbox.py` 的 4 个用例和 `tests/test_idea_download_import.py` 的 1 个用例开头加 `REQ-S01-68` docstring；测试逻辑与断言未动 |
| `architecture.test_round_baselines::test_round_number_continuous` | AGENTS §2.5 规则 27 要求状态页当前轮次 N＝最新结果文件号 M＋1。R1911 起的写法是“当前轮次：<本轮号＋1>（R<本轮号> …）”，之后的合并轮都把本轮号写成了当前轮次 | 状态页头改为“当前轮次：2108（R2107 …）” |
| `test_soak_light` | 最慢一轮 10.977 秒，超 10 秒上限，全量时有其他会话并行跑测试 | 复跑 2 次 0 红，判定为负载不稳；上限未改 |
| `test_leak_teardown` | 第 3 轮 after 回调 7，期望 6，R2080 全量也红过 | 复跑 2 次 0 红，判定为时序不稳；未改 |

- 本轮运行（主检出，经 `gui_hidden.py`）：`run_selftests -k test_soak_light test_leak_teardown test_requirement_traceability test_download_inbox test_idea_download_import` 跑 2 次，各 45 条，0 个文件有红。改状态页后再跑 `-k test_round_baselines test_requirement_traceability`：10 条，`test_round_number_continuous` 已通过；红 1 条是 `test_full_safe_all_is_required_after_eight_source_rounds`（欠一次完整安全全量），要等全量跑绿才会消失。
- 注意：R2106 的结果文件在 `codex/wip-R2106` 上，还没合入 master。它合入时状态页头要写成“当前轮次：<合并轮号＋1>”，否则这条连续性测试会再红。
- 未运行：`--all --safe`（交给提交后的后台全量）。断言未动，债务未减少。未 push。
