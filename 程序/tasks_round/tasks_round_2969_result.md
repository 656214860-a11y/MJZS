# R2969 结果：修复轮——页头 justify 断言第二处同步（R2966 同类欠账收口）
<!-- round-evidence: {"commit_base": "90287812", "credential_hits": 0, "evidence_sha256": "a3a6a09a2158322a", "exit": 0, "failed": 0, "passed": 4, "round": 2969, "tests": "run_selftests.py -k ui_batch5"} -->

## 三问

1. **轮次类型**：修复轮（§3.2）。R2966 修复轮合入后 master 定向复测发现同一契约变更的第二处陈旧断言，一并收口。
2. **测试跑了吗、三个基线过了吗**：跑了。改前红：`test_ui_batch5_stage_panel_and_script_page.test_structure_cards_share_left_edge_and_width` 断言 `justify=='right'`（master `abec90bd` 实测复现）；改后该文件 4/4 绿。默认冒烟与 `--affected` 见提交证据。
3. **欠账少了吗**：是。R2950 页头改单行（状态居左）引起的 justify 断言陈旧点全部清零（`test_ui_edges_pages` 已在 R2966、`test_ui_batch5` 本轮）；全量 20 红的可复现代码缺陷至此全部闭环。

## 根因与修复

- `tests/test_ui_batch5_stage_panel_and_script_page.py:147`：与 R2966 同处——`script_structure_info_label` 即 `header_status`，R2950 页头改单行后 `justify` 由 `'right'`（两行右对齐时代）变为 `'left'`（状态居左可伸展）。断言值同步为 `'left'` 并注 R2950 口径；同行「不越出卡片右沿」几何断言不受影响（justify 只管行内对齐，label 宽度不变）。
- 契约变更说明（§2.4）：断言值随 R2950 有意设计同步，行为断言原样。

## 验证记录

- 改前红输出：`AssertionError: 'left' != 'right'`（master `abec90bd`，`test_ui_batch5` 4 条中 1 红）。
- 改后：`run_selftests.py -k ui_batch5` 4/4 绿；合入前 `--affected`/`smoke_test.py` 以 local_ci 出口为准。
- 全量 `--all --safe`：后台自动补跑中，凭据以 `full-safe-receipts.json` 为准；本轮消除的是上轮全量红清单中最后一处已知代码断言欠账。
