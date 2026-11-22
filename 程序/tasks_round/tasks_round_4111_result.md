# R4111 结果：逐句配音文件名里的镜头编号做文件名清洗
<!-- round-evidence: {"commit_base": "67068467", "credential_hits": 0, "evidence_sha256": "f2ed8eee44f20c05", "exit": 0, "failed": 0, "passed": 56, "round": 4111, "tests": "run_selftests.py -k tts"} -->

## 开头三问

（一）本轮类型：修复轮。任务卡 W6-FIX-S11-E10，车道 codex/fix-tts-line-name，来源是「配音与字幕」只读审查（W6B-AUD-US05）的 E-10。

（二）测试与三个基线：点名测试 `run_selftests.py -k tts` 改前红 9 条（3 个新方法：test_line_name_neutralizes_unsafe_shot_id 的 7 个子用例、test_line_name_limits_shot_id_length、test_run_lines_keeps_audio_inside_batch_folder_for_unsafe_shot_id），改后实测共 56 条用例全部通过、0 红；架构门禁 `smoke_test.py --architecture` 实测 Ran 700 tests，全部 ok，失败集合为空；默认冒烟没单独跑；全量自测没跑。本轮新增 4 条用例，没有删除或改弱已有用例，test_line_name_keeps_original_format 保持原样且仍绿。

（三）欠账：「逐句配音文件名里镜头编号未做清洗、音频可能落到批次目录外」这条已修。无新增欠账；line_done 不校验清单路径、start 非数字报错（E-14）是审查已有的欠账，归别的卡。

## 改了哪些文件

- `domain/tts_api.py`：只改 `line_name`（341–345 行）。把 unsafe 正则提为局部变量；镜头编号段 `shot` 用同一正则清洗并截 40 字符，`str(line.get("shot_id"))` 不加 `or ""`，无镜头编号时仍拼出 `None`；safe 行只把字面量换成 `unsafe`，其余不变。
- `tests/test_tts.py`：在 `TtsBatchResumeTests.test_line_name_keeps_original_format` 之后、`test_batch_publication_requires_l3_gateway` 之前新增 4 个方法：不安全 shot_id 清洗、缺失/数字 shot_id 格式、shot_id 长度上限、run_lines 落盘一定在批次目录内。
- `tasks_round/tasks_round_4111_result.md`：本结果文件。

## 命令与结果

| 命令 | 实测结果 |
| --- | --- |
| `git -c core.quotepath=false status --porcelain` | 退出码 0，输出为空 |
| `git log -1 --format=%h` | 退出码 0，输出 `67068467` |
| `git rev-parse --abbrev-ref HEAD` | 退出码 0，输出 `codex/fix-tts-line-name` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k tts`（改前） | 退出码 1，共 56 条用例、9 条红：test_line_name_neutralizes_unsafe_shot_id（7 个子用例各 1 条）、test_line_name_limits_shot_id_length、test_run_lines_keeps_audio_inside_batch_folder_for_unsafe_shot_id |
| `git -c core.quotepath=false diff --stat`（改后） | 退出码 0，恰好 2 个文件：domain/tts_api.py、tests/test_tts.py |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k tts`（改后） | 退出码 0，共 56 条用例、0 个文件有红，输出 `ALL TESTS PASSED` |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 退出码 0，Ran 700 tests in 415.672s，全部 ok，失败集合为空 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 退出码 0，领到轮次号 4111 |

## 如实说明

- 只改了 `line_name` 一个函数；`publish_line`、`run_lines`、`line_done` 及文件其余部分未动。
- 正常镜头编号（字母、数字、下划线、连字符、中文，不超过 40 字符）拼出的文件名与改前逐字相同，由 test_line_name_keeps_original_format 钉住，实测仍绿；已有批次续跑不受影响。
- 带不能用的字符或超过 40 字符的镜头编号，文件名与改前不同。这类旧批次里已经生成的句子续跑时不会重新合成：line_done 按清单里记的 file 字段找文件、不重新拼名（domain/tts_api.py:356），旧文件名照样认；只有还没生成、或文件已经不在的句子才会用新文件名合成。这一点是读代码得出的，没有单独测。（R4117 更正：原来写的是「这类旧批次里已经生成的句子续跑时会被当成未完成而重新合成——但 line_done 只读清单里的 file 字段取路径、不重新拼名」，前半句写反了。）
- 没有在真实界面上试过；其他与卡面不一致的地方：无。

## 未覆盖项

- `line_done` 按清单里的 file 字段取路径，不检查该路径是否仍在批次目录内（只读不写，另一张卡做）。
- 起始时间不是数字时 `line_name` 的 `float(line.get("start"))` 会报错（审查报告的 E-14，另一张卡做）。
- 全量自测（`run_selftests.py --all --safe`）没跑。
- 默认冒烟没单独跑。
