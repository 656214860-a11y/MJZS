# R4066 结果：剧本结构页分区标题并入下拉框一行，恢复正文高度（REQ-S02-32）
<!-- round-evidence: {"commit_base": "8b4d1602", "credential_hits": 0, "evidence_sha256": "edaaa199f70ce976", "exit": 0, "failed": 0, "passed": 52, "round": 4066, "tests": "run_selftests.py -k ui_reading_density script_page_layout ui_edges_pages"} -->

## 开头三问

（一）本轮属于哪种类型：修复轮，任务卡 B-L4-U7A-FIX，车道 codex/full-selftest-reds。修的是 R4047（L4-U7a）带进来的两处全量自测红（REQ-S02-32 的正文高度；内容框第一个子控件应是页头）。

（二）测试跑了吗：改前 tests.test_ui_reading_density 两个子用例失败、tests.test_ui_edges_pages 一条失败（断言原文见第三节）；改后 tests.test_ui_reading_density 与 tests.test_script_page_layout 实测 12 条全过，tests.test_ui_edges_pages 实测 40 条全过，tests.test_desktop_compact_layout 实测 5 条全过；架构门禁实测 696 条全过、失败集合为空；默认冒烟实测通过（失败 0）；全量自测没跑。没有改任何测试。

（三）欠账少了吗：全量自测少两处红；复杂度记录没有调大；没有新增欠账。

## 改了哪些文件

- `ui/desktop_script_pages.py`（`_ContentBox.build`：删掉独占一行的分区标题，改为在页头那一行最左边建标题并记在 `self.heading_label`；下拉框从第 0 列改到第 1 列，操作列从第 1 列改到第 2 列。`_align_picker_edges`：标题列、操作列各取两行里的最大需求宽度）。
- `tasks_round/tasks_round_4066_result.md`（本文件）。

没有改任何测试文件，没有删标题，没有改标题文字和字号，没有改按钮。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| 改前 `scripts\gui_hidden.py logs\u7a-red.log` 跑 tests.test_ui_reading_density + tests.test_script_page_layout，`logs\u7a-red2.log` 跑内容框首子控件用例 | density exit 1、box exit 1；`AssertionError: 265 not greater than or equal to 290`、`AssertionError: 269 not greater than or equal to 294`、`AssertionError: 'TLabel' != 'TFrame'` |
| 改后 `scripts\gui_hidden.py` 分别跑 density+layout、edges_pages、desktop_compact_layout | density exit 0（Ran 12，OK）、pages exit 0（Ran 40，OK）、compact exit 0（Ran 5，OK） |
| `smoke_test.py --architecture` | 退出码 0，Ran 696 tests，OK，失败集合为空 |
| `smoke_test.py` | 退出码 0，失败 0，输出「冒烟测试通过，可以进入下一步」 |
| `scripts\dev.py claim` | 退出码 0，轮次号 4066 |

## 如实说明

（一）原因与改法由总控定位并预验证，执行方照卡面落地。R4047 按「上下两组按钮各自放进带标题的分区」给每个内容框加了独占一行的标题，正文矮了约 25 像素，违反 REQ-S02-32；那次提交没有跑到 tests/test_ui_reading_density.py 和 tests/test_ui_edges_pages.py。

（二）与 L4-U7a R2、R3 的关系：分区标题仍在，只是从独占一行改成与文档下拉框同一行；两行下拉框的右边缘仍然对齐，左边缘现在也对齐。tests/test_script_page_layout.py 的用例没有改，仍然通过。

（三）没有在真实桌面上目检，只有隐藏桌面里的自动化用例。

## 未覆盖项

未跑全量自测；没有截图目检；未 push、未 merge。
