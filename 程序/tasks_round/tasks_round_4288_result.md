# R4288 SANHU-ADOPT-A 三虎判断「下一阶段用哪一份」（修复轮·续做，只做判断逻辑与测试）
<!-- round-evidence: {"commit_base": "02e2c3e0", "credential_hits": 0, "evidence_sha256": "40efd42cf0034b0f", "exit": 0, "failed": 0, "passed": 92, "round": 4288, "tests": "run_selftests.py -k script_workspace_service script_structure"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮（§3.2），且是续做卡——车道里上一位执行者留下的两个未暂存改动就是本卡交付物，在这份现场上续跑核对、补缺、跑验收、领号、提交。技术正文 `.agent-tmp/b752e4fb-card-SANHU-FIX-ADOPT-A.md` §5–§9；车道、允许清单、治理口径按需求设计卡 `.agent-tmp/需求设计-card-SANHU-ADOPT-A.md`。
- （二）测试跑了吗、三个基线各是什么结果：定向 `run_selftests.py -k script_workspace_service script_structure` 改后 92 条全绿（exit 0）；架构门禁 `smoke_test.py --architecture` 700 条全过（exit 0）；默认冒烟与全量自测本卡未要求、未跑。改前（接手时、未做任何修改）同一定向命令 92 条里 1 红，红因是上一位执行者测试断言与 §5.6 prefer 规则不符（见下「改前红」），不是产品缺陷。
- （三）欠账少了吗：本卡范围内没有新增欠账；接手时遗留的 1 条红测试断言已按契约改正转绿。卡外观察一条记在「卡外发现」，未顺手修。

## 续做现场核对（接手时实测）

- `git status --porcelain`：恰好 2 行，与预期逐行一致——` M 程序/domain/script_workspace_service.py`、` M 程序/tests/test_script_workspace_service.py`（中文路径显示为八进制转义，按文件名对照）。
- `git log -1 --format=%h` → `02e2c3e0`；`git rev-parse --abbrev-ref HEAD` → `codex/sanhu-adopt-judge`。
- `git rev-parse --abbrev-ref HEAD` 与基准一致；`git diff --numstat` 只有上述两文件且删除数全 0（接手时 `237 0` / `292 0`）。

## 上一位执行者改动的处置（保留与修改）

保留：产品文件头三行导入（`hashlib`/`json`/`threading`，§5.1）与文件末尾追加的全部内容——`ADOPTION_KIND_NAMES`/`ADOPTION_SOURCES`/`ADOPTION_ENTRANCES` 常量、`AdoptionTouches`、`AdoptionCandidate`/`AdoptionSnapshot`/`AdoptionVerdict`、`adoption_snapshot`、`judge_adoption`、`adoption_notice`、`adoption_question`、`apply_adoption`；测试文件头 `import json` 与 `import script_workspace_service as workspace`，文件末尾 `AdoptionJudgeTests`（11 条用例）。以上逐条对照 §5 接口契约核对一致，未推倒重写。

修改（全部在追加区域内，`git diff --numstat` 删除数保持 0）：

1. `domain/script_workspace_service.py` 5 处文案「您」改回契约逐字的「你」：§5.7 `fresh`/`edited`/`picked` 三句、§5.7 `several_fresh`/`picked_other` 两句（现文件 738、739、741、760、764 行）。契约 §5 标题即「名字、字段、文案逐字照做」，§5.7 表与 §6.9 期望句均为「你」。
2. `tests/test_script_workspace_service.py` 同一处期望句同步改「你」（633 行）；删除与契约冲突的 `assertNotIn('你', text)` 及只为它服务的 `sentences` 收集（契约句子本身含「你」，该断言必红）；「#12 missing other」用例 prefer 断言由 `a` 改为 `''`（458 行，理由见「改前红」）；删掉按需才加的 `from unittest import mock`（最终测试未用，§6 说「按需再加」）。

## 改前红（接手后、改动前实测）

`run_selftests.py -k script_workspace_service script_structure`：共 92 条用例，1 个文件有红，exit 1。红项原文：

```
===== test_judge_table_without_picked (test_script_workspace_service.AdoptionJudgeTests.test_judge_table_without_picked) =====
AssertionError: Tuples differ: ('ask', 'adopted_missing', '', '甲.md') != ('ask', 'adopted_missing', '', '')
First differing element 3:
'甲.md'
```

位置：`tests/test_script_workspace_service.py` 458 行「#12 missing other」断言 `('ask', 'adopted_missing', '', a)`。性质：测试断言写错——§5.6 末「prefer 取：有 picked 用 picked，否则 A 在候选里用 A，否则 ''」；该样本 `adopted='甲.md'` 不在候选 `(乙.md, 丙.md)` 里，prefer 应为 `''`，产品实现返回的正是 `''`，符合契约。按「红的原因与卡面不一致就修测试」改断言，产品代码未动。

按接口契约第一条如实记录：续做现场已有实现，未观察到「卡面缺陷在旧代码上复现」的改前红；接手时唯一的红是上述测试断言错误。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `domain/script_workspace_service.py` | 在上一位执行者追加块内改 5 个模板字符串的「您」→「你」（738、739、741、760、764 行）；其余未动 |
| `tests/test_script_workspace_service.py` | 改 1 处断言期望（458 行 prefer `a`→`''`）、1 处文案期望（633 行「您」→「你」）、删 `assertNotIn('你')` 与 `sentences` 收集、删未用的 `from unittest import mock`；现有行未删未改 |
| `tasks_round/tasks_round_4288_result.md` | 本文件 |
| `tasks_round/evidence/R4288.json` | 提交工具生成的证据文件 |

`git diff --numstat` 原文（提交前）：

```
237	0	"\347\250\213\345\272\217/domain/script_workspace_service.py"
285	0	"\347\250\213\345\272\217/tests/test_script_workspace_service.py"
```

`domain/script_workspace_service.py` 改后 777 行（卡面上限 800）。

## §5.6 两张表与用例的对应

有 picked 表（`test_judge_table_with_picked`）：valid 且 picked==A→keep/valid（断言 1）；changed 且 picked==A→adopt/picked（断言 2）；valid/changed 且 picked!=A→ask/picked_other（断言 3、4）；none/missing→adopt/picked（断言 5、6）。

无 picked 表 15 行（`test_judge_table_without_picked` 内注释 #1–#15 逐行对应）：#1 valid others 空→keep、#2 valid 恰一 other fresh→adopt/fresh、#3 valid 多 fresh→ask/several_fresh、#4 无候选→none/empty、#5 单候选 changed→edited/only_changed 两断言、#6 单候选 missing→only_left、#7 单候选 none→only、#8 changed A fresh others 空→edited、#9 changed A fresh others 非空→several_fresh、#10 changed A 不 fresh→changed_outside、#11 missing 恰一 fresh→fresh、#12 missing 其余→adopted_missing（prefer=''，已按契约改正）、#13 none 恰一 fresh→fresh、#14 none 多 fresh→several_fresh、#15 none 无 fresh→no_signal。边界三条在 `test_judge_boundaries`；读盘四态、登记只认内容、不看文件时间、执行、端到端、老规矩不放松、拒绝、两句话分别由其余 8 条用例覆盖。

## 验收命令与结果

工作目录均为车道 `程序`；解释器 `..\..\..\..\运行环境\Python\python.exe -B`。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `run_selftests.py -k script_workspace_service script_structure`（改动前） | 1 | 92 条用例，1 红（见「改前红」原文） |
| `run_selftests.py -k script_workspace_service script_structure`（改动后） | 0 | `共 92 条用例，127.8 秒；0 个文件有红` … `ALL TESTS PASSED`；8 个测试文件全绿，`test_script_workspace_service` 34 条 = 旧 23 + 新 `AdoptionJudgeTests` 11；卡面 §9 记的改前基线为这两组 81 条，92−81=11 与新增用例数一致 |
| `smoke_test.py --architecture` | 0 | `Ran 700 tests in 231.535s` … `OK` … `✅ 架构治理测试：tests/architecture` |
| `scripts\dev.py claim` | 0 | 领到轮次 4288 |

## 和卡面不一致的地方

逐条：上一位执行者把 §5.7/§6.9 契约文案的「你」写成「您」（5 处产品模板 + 测试期望句 + 反向断言 `assertNotIn('你')`），已按「文案逐字照做」改回「你」；测试用例 #12 的 prefer 断言与 §5.6 prefer 规则不符，已改为 `''`。除此两类外，§5 接口契约（常量、登记本、三个数据类、读盘四态、判断表、两句话、执行函数）逐条核对一致；§6 测试清单 9 组用例齐全。除此之外无不一致。

## 卡外发现（只记录，未顺手修）

- 应用界面既有文案惯用「您」（`程序/ui/` 43 处、`程序/domain/` 13 处），而本卡契约逐字要求「你」。本卡按契约实现；若后续要统一口吻，属 ADOPT-B 接线或单独文案轮的事。
- 首次定向自测输出 `[SUSPECT_CONCURRENCY]`：当时另一 PID 持有跨树 GUI 令牌；属环境排队，复跑后全绿，与本卡改动无关。

## 被拒绝的命令原文（均为取证/核对类，已改用专用文件工具完成同等核对，未影响实施）

1. `Get-ChildItem -Name "D:\漫剧制作助手\.agent-tmp" | Select-String -Pattern "SANHU|b752e4fb"`（shell: powershell）
2. `Get-ChildItem -Force -Name "D:\漫剧制作助手\.agents\worktrees\l4-buttons-script" | Select-Object -First 40`（shell: powershell）
3. `Select-String -Path "程序\domain\script_workspace_service.py" -Pattern "st_mtime|getmtime|os\.stat|os\.utime|except Exception" | Select-Object LineNumber, Line`（workdir `程序`）
4. `Get-ChildItem -Name "scripts" | Select-Object -First 30`（workdir `程序`）
5. `Select-String -Path "C:\Users\LAIBIAO\AppData\Local\Temp\devin.exe-overflows\shell-13359c-ae671944fa97428f\content.txt" -Pattern "FAIL|FAILED|Ran \d+ tests|✅|❌|架构门禁|smoke" | Select-Object -First 40`

## 未覆盖项／没跑的东西

- 未跑默认冒烟 `smoke_test.py`、未跑全量自测（卡面验收只列定向与 `--architecture` 两条）。
- 真实界面未试：本卡只做判断逻辑，不接界面（接线是 SANHU-ADOPT-B）。
- `setting`/`outline`/`character` 三种文件只登记了 `ADOPTION_KIND_NAMES` 常量，读盘判断按 §5.2/§5.5 设计未接（等对应采用记录定下来再接）。
- 未改 `governance/`、`维护记录/`、`contract/`、`stage_execution_service.py`、任何 `ui/` 文件；未新建模块、未加全局登记本实例。
- 提交号写本文件时尚未产生，见 `git log`；证据文件 `tasks_round/evidence/R4288.json` 由提交工具生成。

## 未跟踪文件

提交前 `git status --porcelain` 只有上述两个 ` M` 行，无未跟踪文件；提交后以最终 `git status --porcelain` 为准（`.agent-tmp/` 在主工作区根、不属于本工作树）。
