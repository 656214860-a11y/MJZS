# R4061 结果：分支覆盖率基线按实测补上 error_codes 新增的决策点
<!-- round-evidence: {"commit_base": "46df4676", "credential_hits": 0, "evidence_sha256": "29cf61db9a8fb23f", "exit": 0, "failed": 0, "passed": 33, "round": 4061, "tests": "run_selftests.py -k branch_coverage_floor error_codes"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮，任务卡 B-EC1-FIX，车道 codex/ec-1-contract；补 R3984 漏掉的基线更新（R3984 给 contract/error_codes.py 加了 user_text()，决策点从 11 变成 17，基线没有跟着改，合入时架构门禁报 11 != 17）。
- （二）测试跑了吗、三个基线：定向守卫 tests.architecture.test_branch_coverage_floor 改前 5 条里 1 条失败、改后 5 条全过；tests.test_error_codes 28 条全过；架构门禁 695 条全过、失败集合为空；默认冒烟本卡没有单独跑；全量自测没跑。
- （三）欠账少了吗：少了一条（基线与代码对不上）；没有新增欠账；整份基线没有重测，见「如实说明」。

## 改了哪些文件

- 维护记录/分支覆盖率基线.json 只改 4 个数字（points_total 3059 改成 3065；points_covered 1743 改成 1749；error_codes.py 这一行的 points 11 改成 17、covered 11 改成 17，percent 仍是 100.0）。
- tasks_round/tasks_round_4061_result.md 是本文件。
- 没有改下限表、测试和产品代码。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| python.exe -B -m unittest tests.architecture.test_branch_coverage_floor -v（改前） | 5 条里 1 条失败，原文「AssertionError: 11 != 17 : error_codes.py 基线决策点与当前实体不一致；须真实重测，不能计量兼容门面」 |
| python.exe -B scripts\branch_coverage_report.py tests.test_error_codes --quiet --json 系统临时目录里的文件 | 28 条用例全过，输出里有「error_codes.py 100.0% 17/ 17」，末尾「模块：103；决策点：17/3065；目标用例：全通过」 |
| git diff --stat | 1 个文件，4 行新增 4 行删除 |
| python.exe -B -m unittest tests.architecture.test_branch_coverage_floor -v（改后） | 5 条全过 |
| python.exe -B -m unittest tests.test_error_codes -v | 28 条全过 |
| python.exe -B smoke_test.py --architecture | 695 条全过，失败集合为空 |
| python.exe -B scripts\dev.py claim | 领到轮次 4061 |

## 如实说明

- （一）本轮分两次执行。第一次执行做完了基线修改、上表全部检查并领了号，写结果文件时因执行方额度用完而中断。第二次执行（续做）只复核了车道现状和两条快速检查（守卫 5 条全过、错误代码用例 28 条全过），然后写本文件并提交，没有再改基线文件。上表里改前的失败原文、实测那一行、架构门禁 695 条来自第一次执行的日志，总控已核对；第一次执行之后车道内容没有变化。
- （二）只重测了 error_codes.py 这一行（定向目标 tests.test_error_codes），其余 102 行沿用上次整体测量的值。整份基线没有重测：用基线登记的 102 个目标整体重跑时，工作树里有 1 条目标用例（tests.test_script_contract.AuditTests.test_the_audit_covers_every_script_skill）因缺少主工作区未跟踪的技能数据而失败，测量工具因此拒绝写整份基线。这是总控实测的结论，不是本轮执行者测的。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟和 --affected（本卡没有要求）；未 push、未 merge。
