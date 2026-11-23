# R4133 结果：UX-D2B 返工——空壳相关提示统一叫「目录」
<!-- round-evidence: {"commit_base": "b28b1203", "credential_hits": 0, "evidence_sha256": "d0563255565fd6d2", "exit": 0, "failed": 0, "passed": 38, "round": 4133, "tests": "run_selftests.py -k project_open copy_rules"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（返工）。UX-D2B 返工：b28b1203（R4127）已提交代码在 `test_copy_rules.OneActionOneNameTests.test_directories_are_called_directories` 上红——`domain/projects.py` 空壳相关用户可见句仍用「文件夹」，文案规则要求「目录就叫目录」。车道 `codex/ux-project-library-missing`，工作树 `.agents/worktrees/dist-manifest-declare`。
- （二）测试跑了吗、三个基线：跑了。`run_selftests.py -k project_open project_rename_reconcile project_recovery projects core project_switch_guard copy_rules static_names` 退出码 0，212 条用例 0 个文件有红（`test_core` 1 条登记跳过为存量，非本轮新增）；`smoke_test.py --architecture` 退出码 0，700 条全绿。默认冒烟未单独跑；全量自测未跑。
- （三）欠账少了吗：少了——还清 R4127 留下的 copy_rules 真实红（空壳提示混用「文件夹」）。无新增欠账，未动任何门禁阈值、基线和登记表。

## 改了哪些文件

- `domain/projects.py`：6 处「文件夹」→「目录」，全部是 R4127 新增的空壳句子——`_EMPTY_SHELL_HINT`（「没有找到可以自动接回的项目目录」）、`EMPTY_SHELL_OPEN_NOTICE`、`empty_shell_open_error`（「项目目录里没有项目配置文件…」）、`claimed_registration_notice`（「原位置留下的空目录没有动。」）、`manual_claim_error` 与 `_claim_reconciled` 的「这个目录已经登记为另一个项目。」。
- `ui/desktop_project_pages.py`：空壳删除警告句「这个文件夹里没有项目配置文件（空壳），把它移入回收站找不回项目，建议先取消；」→「这个目录里…」。
- `tests/test_project_open.py`：承接工作区已有未提交半成品改动并补齐——「空文件夹没有动」断言改「空目录没有动」、删除警告加 `assertNotIn("文件夹")`、新增 `test_shell_sentences_call_a_directory_a_directory` 守 `EMPTY_SHELL_OPEN_NOTICE`／`empty_shell_open_error`／`claimed_registration_notice`／`manual_claim_error` 四句不含「文件夹」且含「目录」。
- `tasks_round/tasks_round_4133_result.md`：本文件。

## 命令与结果

以下命令都在车道的 `程序` 目录下跑（git 类在车道根），解释器 `D:\漫剧制作助手\运行环境\Python\python.exe`，先设 `PYTHONIOENCODING=utf-8` 与 UTF-8 控制台。

| 命令 | 结果 |
| --- | --- |
| `git status --porcelain` / `git rev-parse --short HEAD` / `git branch --show-current`（开工核对） | ` M 程序/tests/test_project_open.py`（上一位助手半成品，保留）/ `b28b1203` / `codex/ux-project-library-missing` |
| `python.exe -B 维护记录\基准脚本\round_claim.py next` | 领到轮次 4133 |
| `python.exe -B run_selftests.py -k project_open project_rename_reconcile project_recovery projects core project_switch_guard copy_rules static_names` | 退出码 0；「共 212 条用例，22.8 秒；0 个文件有红」「ALL TESTS PASSED」 |
| `python.exe -B smoke_test.py --architecture` | 退出码 0；「Ran 700 tests in 255.554s」「OK」「✅ 架构治理测试：tests/architecture」 |
| `python.exe -B scripts\dev.py commit -m "R4133: UX-D2B 返工：空壳相关提示统一叫「目录」" --tests project_open copy_rules <四文件>` | 见下方提交记录 |

跳过：1 条既有登记位（`test_core.ValidateProfileTests.test_stage_profile_wrong_preset_rejected`，发行包未含受测 bundled skill，存量跳过，非本轮新增）。

## 如实说明

- （一）只改字不改判定：`is_empty_shell_open_error`／`needs_cleanup_after_open_error` 仍按 `_EMPTY_SHELL_HINT` 常量匹配，engine 原句不含该提示，壳句子与 engine 句的区分不变；`test_desktop_load_on_shell_without_match_reports_shell_sentence` 里的 `engine_sentence` 夹具（engine 的 R4097 旧句，本就用「文件夹」）保持原样，断言未动。
- （二）`orchestrator/engine.py` 的「项目文件夹里没有项目配置文件 config.json：…」是 R4097 既有文案、不在本分支 diff 内，按「不碰无关旧文案」未动；`ui/desktop_project_pages.py` 余下 3 处「文件夹」（303 行注释引用户原话、531／535 删除项目旧流程文案）同为存量旧文案未动。copy_rules 只查弹窗正文与按钮固定文案，本就不含这些位置。
- （三）分支 diff 内全部 7 处新增「文件夹」用户可见句已清零（`git diff 89fdb829...HEAD` 中 `文件夹` 命中均为 `+` 行，逐一对应本次修改）；`domain/projects.py` 现已无「文件夹」。
- （四）界面未实际点过：文案由隐藏桌面自测经真 Tk 断言（`confirm` 调用参数、`textvariable`、`status.set` 实参）。

## 未覆盖项

- 未跑默认冒烟、未跑全量自测（返工仅文案统一，点名回归＋架构门禁已覆盖）；未 push、未 merge、未动主工作树与 master。
