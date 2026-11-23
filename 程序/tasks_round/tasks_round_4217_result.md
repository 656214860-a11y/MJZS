# R4217 结果：FIX-S11-E1 编码席位中断后的总监督修复与代提交

<!-- round-evidence: {"commit_base": "6e687b94", "credential_hits": 0, "evidence_sha256": "45604c0c486ab1a6", "exit": 0, "failed": 0, "passed": 73, "round": 4217, "tests": "run_selftests.py -k tts request_recording"} -->

## 开头三问

- （一）本轮属于哪种类型：编码卡 FIX-S11-E1 的修复收尾轮。编码席位中断后，车道 `fix-s11-e1` 留下未提交改动；总监督按用户 2026-11-23「编码角色擅自中断了任务…修复」的指示验证并修复架构门禁后代提交。本卡目标（TTSRejected 4xx 分类、unsaved 状态口径、逐句配音待核实句子人工放开带二次确认）与卡面一致，未扩范围。
- （二）测试跑了吗、三个基线：卡面两条验收命令全绿——`run_selftests.py -k tts request_recording` 73 条 0 红；`smoke_test.py --architecture` 700 条 OK。反向验证（撤掉产品改动看用例变红）本轮未做，验收窗口如需可补。
- （三）欠账少了吗：少了。FIX-S11-E1 从「派工中断、改动滞留车道」收口为待审交付，等待验收独立复核。

## 为什么由总监督代做

- 编码席位心跳失联、任务中断，车道 `fix-s11-e1` 留下 5 个文件 +224/-8 的未提交改动（实现与卡面规格一致），面板卡 38 号被撤回。
- 总监督复核发现两条架构门禁红在遗留改动上：① `MediaPagesMixin` 901 行超 CLASS_CAPS 登记 890；② 付费闸口新增行把 `launch_windows_app` 调用点从 914 推到 925，spawn 豁免行号失效。
- 修复：① 把 `generate_tts_per_line` 的付费闸口（待核实句确认放开、取消不提交）提取为模块级函数 `_line_quote_gate`，类内只留一次调用，行为等价；② 按 R4051 先例（行位移时更新豁免行号）把 `SPAWN_SITE_EXEMPT['detached']` 里 `ui/desktop_media_pages.py:914` 更新为 930（实测行号）。

## 改了哪些文件

- `程序/domain/tts_api.py`：TTSRejected 4xx 分类与 unsaved 状态口径（编码席位遗留实现，总监督核对与卡面一致）。
- `程序/stage_execution_service.py`：`release_tts_unknown`（遗留实现）。
- `程序/ui/desktop_media_pages.py`：逐句配音付费闸口接入；`_line_quote_gate` 模块化修复（本文件 886 行类体 ≤ 890、998 行模块 ≤ 1000，两处棘轮均绿）。
- `程序/tests/test_tts.py`、`程序/tests/test_request_recording.py`：新增用例；未改既有断言（仅 import 加 Mock）。
- `程序/tests/architecture/test_platform_process_boundary.py`：spawn 豁免行号 914→930。**越界说明**：卡面允许修改文件不含此文件，但它是架构门禁红的直接原因，且按 R4051 先例属行位移登记的既定维护；用户指示下由总监督照实修改，验收请复核。
- `程序/tasks_round/tasks_round_4217_result.md`：本文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k "tts request_recording"` | 73 条全过，退出码 0（两次） |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | Ran 700 tests OK（287 秒） |
| `..\..\..\..\运行环境\Python\python.exe -B -m unittest tests.architecture.test_complexity_ratchet tests.architecture.test_module_size_ratchet tests.architecture.test_platform_process_boundary -v` | 14 条 OK |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 领到轮次 4217 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4217: FIX-S11-E1 编码中断遗留修复（监督代提交）" --tests tts request_recording …` | 见提交证据 |

## 未验证

- 真实界面未点过：付费闸口是人工确认交互，本轮以用例覆盖口径，未在桌面应用里点击验证。
- 编码席位遗留的 5 文件改动由总监督按卡面目标与规格核对，非原执行者自述，验收请独立复核（请放与 Claude 不同的型号）。
- 未跑全量 `--all --safe`；合并轮出口 CI 会重跑。
- 面板卡 39 号（FIX-S11-E2）已由监督恢复回队列 B，与本轮无关，请勿重复派。
