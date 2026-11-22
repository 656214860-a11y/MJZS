# R4078 结果：根目录登记表补登 .agents（仓库级项目开发技能）
<!-- round-evidence: {"commit_base": "90344ce9", "credential_hits": 0, "evidence_sha256": "540ae897b3d6e38e", "exit": 0, "failed": 0, "passed": 1, "round": 4078, "tests": "run_selftests.py -k root_layout"} -->

## 开头三问

- 本轮属于哪种类型：修复轮（任务卡 B-ROOT-LAYOUT，车道 `codex/full-selftest-reds`，基线 `90344ce9`）。
- 测试跑了吗、三个基线：先红后绿；改前 `tests.test_root_layout` 1 条红，改后 1 条全绿；`smoke_test.py --architecture` 696 条全绿、失败集合为空；默认冒烟按卡面未跑。
- 欠账少了吗：没有新增欠账；`ALLOWED` 只补登 `.agents` 一项，其余条目与断言未动。

## 起因与改前红

- 起因：master 全量自测中 `tests.test_root_layout.test_tracked_root_entries_are_registered` 红。R4025（接入开发规格与审查工具）把 `.agents/skills/spec-context-review/SKILL.md` 纳入版本管理，它是仓库级项目开发技能（会话接续记录与 `开发者工具/AI开发流程/README.md` 均以它为正式入口），但根目录登记表未补登；该轮未跑全量故当时未发现。`.agents` 下被跟踪的仅此一个文件。
- 改前红原文：`AssertionError: Lists differ: ['.agents'] != []`（`self.assertEqual(sorted(tracked - set(ALLOWED)), [], '新增根目录入口须先在 ALLOWED 登记用途')`）。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `tests/test_root_layout.py` | `ALLOWED` 在第 13 行 `'.claude'` 项的下一行新增一项：`'.agents': '仓库级项目开发技能（spec-context-review；说明见 开发者工具/AI开发流程/README.md）',`；numstat 为 1 增 0 删。 |
| `tasks_round/tasks_round_4078_result.md` | 本文件。 |

## 命令与退出码

| 命令（执行目录：`程序`） | 退出码 | 结果 |
|---|---|---|
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k root_layout`（改前） | 1 | 1 条红，「1 个文件有红」，失败信息含 `['.agents']` |
| 同一条命令（改后） | 0 | `ALL TESTS PASSED`，共 1 条用例、0 个文件有红 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | `Ran 696 tests`，`OK`，失败集合为空 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 领到轮次 4078 |

## 未覆盖项

- 未跑全量自测（`run_selftests.py --all --safe`），未跑不带参数的 `smoke_test.py`。
- 未动 `.agents` 下任何文件；未 push、未 merge、未改主工作区。
