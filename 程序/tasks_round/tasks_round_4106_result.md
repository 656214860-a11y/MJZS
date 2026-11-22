# R4106 结果：分发清单不再整目录保留 data 与配置
<!-- round-evidence: {"commit_base": "f624a5fc", "credential_hits": 0, "evidence_sha256": "52e985028ef9e559", "exit": 0, "failed": 0, "passed": 22, "round": 4106, "tests": "run_selftests.py -k distribution"} -->

## 开头三问

（一）本轮属于哪种类型：修复轮。任务卡 W6-REL-21 与续卡 W6-REL-21B，车道 `codex/rel-21-machine-state`，来源是推进窗口对发布链路盘点的复核（发布包会带上打包机写在程序目录里的运行数据）。

（二）测试跑了吗、三个基线：`run_selftests.py -k distribution` 实测 22 条全过（ALL TESTS PASSED）；架构门禁 `smoke_test.py --architecture` 实测 700 条、失败集合为空；默认冒烟没单独跑；全量自测没跑。新增 1 条用例（`test_actual_manifest_never_ships_machine_state_under_data_or_config`），没有删除用例，改了 1 条架构用例的期望（见「改了哪些文件」）。

（三）欠账少了吗：发布包夹带本机运行数据这一条，从清单整目录保留 `程序/data/`、`程序/配置/` 改成逐类排除、没登记的新文件落「未声明」由构建拒绝；架构门禁里钉着的两条「运行数据随包」已知缺口随之消掉。没有新增欠账。

## 改了哪些文件

- `程序/distribution_manifest.md`（上一次会话改的）：「必须保留」表中 `程序/data/`、`程序/配置/` 两个整目录条目改为只保留入库的三个文件（`data/skill_note_terms_zh.json`、`配置/客户端档案.json`、`配置/SKILL/预设.json`）；「必须排除」表新增「本机运行数据」一行，逐类登记 `程序/data/*/**`、`data/` 下若干具体 JSON 与 `*.flag`、`程序/配置/宠物/**`、`程序/配置/素材库.json`，并写明以后这两个目录下新写的文件要先登记，没登记的落「未声明」，构建拒绝。
- `程序/tests/test_distribution_build.py`（上一次会话改的）：新增 `test_actual_manifest_never_ships_machine_state_under_data_or_config`，用真实清单跑 `plan()`：15 条本机运行数据路径断言落在 `excluded`，3 个随包种子断言落在 `keep`，2 个未登记路径断言落在 `undecided`。
- `程序/docs/process/发布检查单.md`（上一次会话改的）：第 7 条把「`data` 不进发布包」改成「`data` 下的运行数据（只有内置的 `data/skill_note_terms_zh.json` 随包）、`配置/宠物`、`配置/素材库.json` 不进发布包」。
- `程序/docs/review/安装更新与恢复方案_A15.md`（上一次会话改的）：目标机状态段改为列明 `程序/data/` 除 `skill_note_terms_zh.json` 外全部内容及 `程序/配置/宠物/`、`程序/配置/素材库.json`，逐项名单以清单「必须排除」表「本机运行数据」行为准；验证表「发布包夹带用户状态」行补登记新用例名与「未声明→构建拒绝」。
- `程序/docs/specs/03_安装签名与分发.md`（上一次会话改的）：升级保留行同步为「保留 `data` 下的运行数据（内置的 `data/skill_note_terms_zh.json` 随包覆盖）、`配置/宠物`、`配置/素材库.json`」。
- `程序/tests/architecture/test_dynamic_import_registry.py`（本轮改的）：`test_strict_production_guard_refuses_current_release_gaps` 期望更新。原期望是「开发工具随包 + 运行数据随包 2 条（`release-generated-data`：`data/voice_asr_venv/pyvenv.cfg`、`data/voice_models/model.bin`）+ 开发启动」，新期望是「开发工具随包 + 开发启动」；另加一个 `for` 循环两条断言，钉住探针 `程序/data/voice_asr_venv/pyvenv.cfg`、`程序/data/voice_models/model.bin` 落在 `plan()` 的 `excluded` 桶——谁把 `程序/data/` 改回整目录保留，这里会红。
- `程序/tasks_round/tasks_round_4106_result.md`：本结果文件。

## 命令与结果

| 命令（执行目录） | 实测结果 |
| --- | --- |
| `git -c core.quotepath=false status --porcelain`（工作树根） | 退出码 0；正好 5 行 ` M`，与卡面名单一致 |
| `git log -1 --format=%h`（工作树根） | 退出码 0；`f624a5fc` |
| `git -c core.quotepath=false diff --stat`（工作树根） | 退出码 0；6 个文件，其中架构测试文件 5 增 5 删 |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k distribution`（`程序`） | 退出码 0；`共 22 条用例，3.5 秒；0 个文件有红`，`ALL TESTS PASSED` |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`（`程序`） | 退出码 0；`Ran 700 tests in 345.177s`，`OK`，失败集合为空 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`（`程序`） | 退出码 0；领到轮次号 4106 |

## 如实说明

- 本批改动分两次会话完成：第一次（W6-REL-21）改完前 5 个文件后停在架构门禁（700 条红 1 条，原因是期望表钉着已被修掉的两条「运行数据随包」缺口，未领号）；本次（W6-REL-21B）按接口契约同步期望后点名测试与架构门禁均通过。
- 没有实际构建发布包；没有在主工作区（有真实运行数据的目录）核对清单，这一步由推进窗口复核时只读去做。
- 上一次会话的报告里写的：第 4 步名单核对结论是「代码写进 `程序/data`、`程序/配置` 的运行时文件全部在卡面名单里，没有额外登记」。
- 其他与卡面不一致的地方：无。

## 未覆盖项

- `scripts/acceptance_release_probe.py` 的用户数据名单没有补 `配置/宠物` 和 `配置/素材库.json`（另一张卡做）。
- `配置/SKILL/预设.json` 随包，目标机上被改写后的内容在并列的发布目录之间不会带过去（另一张卡做）。
- 全量自测没跑。
- 默认冒烟没单独跑。
