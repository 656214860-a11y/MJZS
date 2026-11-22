# R4077 结果：项目文件停靠面板架构门禁修复
<!-- round-evidence: {"commit_base": "7411213c", "credential_hits": 0, "evidence_sha256": "b2b2c9bccf6b0be6", "exit": 0, "failed": 0, "passed": 192, "round": 4077, "tests": "run_selftests.py -k file_index files_panel"} -->

## 开头三问
（一）本轮属于修复轮，任务卡 W4-UX-B34 跟进，车道 codex/ux-dock-content。
（二）测试已跑：`run_selftests.py -k file_index files_panel stage_file_index_publication` 退出码 0；`smoke_test.py --architecture` 退出码 0。
（三）欠账少了吗：修掉复杂度与分支覆盖率基线不一致，没有新增欠账。

## 改了哪些文件
- infra/file_index.py：discover 降嵌套，拆出 _collect_from_folder / _collect_discover_candidates。
- tests/test_file_index.py、tests/test_files_panel_stages.py、tests/test_files_panel.py：补齐 discover 用例与 late_result kwargs。
- 维护记录/分支覆盖率基线.json、维护记录/分支覆盖率下限.json：同步 file_index 决策点与覆盖数。
- 本结果文件。

## 命令与结果
| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k file_index files_panel stage_file_index_publication` | 退出码 0 |
| `smoke_test.py --architecture` | 退出码 0 |

## 如实说明
基线更新为真实测量值；未改业务契约。

## 未覆盖项
无。