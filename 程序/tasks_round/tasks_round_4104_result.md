# R4104 结果：更正 R4101 结果文件里关于架构门禁的一句，补记门禁结果（只改结果文件）
<!-- round-evidence: {"commit_base": "1f5fc04c", "credential_hits": 0, "evidence_sha256": "1a257c5fa5cd941a", "exit": 0, "failed": 0, "passed": 0, "round": 4104, "tests": "docs-only"} -->

## 开头三问

- （一）本轮属于哪种类型：更正轮，只改结果文件。任务卡 W4-FIX-PANEL-TESTS（队列项 FIX-PANEL-TESTS），车道 codex/ux-dock-tests-sync，叠在 1f5fc04c（R4101）上。来源：本窗口提交 R4101 之后自己复查。现象：R4101 结果文件「开头三问」第（二）条写了「架构门禁没有单独跑，由提交工具跑」。根因：这句话是照任务书的说法写的，写之前没有核对提交工具实际跑什么。核对结果：提交工具只做凭据扫描和点名的定向测试（`tasks_round/evidence/R4101.json` 里只有 `credential_scan` 和 `targeted` 两段）；提交钩子只查白名单和分支规则，再跑两个静态检查模块；整套架构门禁是 `smoke_test.py --architecture`，要单独跑。所以 R4101 提交的时候架构门禁其实没有跑过。
- （二）测试跑了吗、三个基线：提交之后在 1f5fc04c 上单独跑了 `smoke_test.py --architecture`：「Ran 700 tests in 367.606s」「OK」，退出码 0（22:31:01–22:37:10，工作树干净）。本轮没有改任何 .py 文件，没有再跑定向测试；R4101 的定向测试结果不变（「共 231 条用例」「0 个文件有红」）。默认冒烟、全量自测没跑。
- （三）欠账少了吗：R4101 欠的一遍架构门禁补上了；结果文件里一句不实的话改掉了。没有新增欠账。

## 改了哪些文件

- tasks_round/tasks_round_4101_result.md：「开头三问」第（二）条里「架构门禁没有单独跑，由提交工具跑。」一句，换成带【R4104 更正】字样的说明和门禁结果（原话以引述的形式留着）。其他内容和证据行一字未动。
- tasks_round/tasks_round_4104_result.md 是本文件。
- 没有改任何测试文件和产品文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| 读 `tasks_round/evidence/R4101.json` | 只有 `credential_scan`（命中 0）和 `targeted`（`run_selftests.py -k idea_chat ui_edges_pages desktop_compact_layout`，退出码 0，通过 231、失败 0）两段，没有架构门禁 |
| python.exe -B smoke_test.py --architecture（车道的 程序 目录，HEAD 1f5fc04c，工作树干净，进程优先级 BelowNormal，22:31:01–22:37:10） | 「Ran 700 tests in 367.606s」「OK」「✅ 架构治理测试：tests/architecture」，退出码 0 |
| python.exe -B scripts\dev.py claim | 领到轮次 4104 |
| python.exe -B scripts\dev.py commit（只提交两个结果文件，没有点名测试） | 结果以本文件的证据行和提交记录为准 |

## 如实说明

- （一）R4101 那句话错在本窗口：任务书写的是「架构门禁不用单独再跑一遍，提交工具会跑」，本窗口没有核对就照写了。提交在 4 分钟内结束，而整套架构门禁单跑要 6 分钟多，这才去查了证据文件和钩子。
- （二）这件事对别的车道同样成立：只靠提交工具提交的轮次，除非另外跑过，架构门禁就没有跑。已在 22:31 的心跳里告诉各窗口。
- （三）架构门禁是在 R4101 的提交上跑的，不是在本轮提交上跑的；本轮只多了两个结果文件的改动，没有再跑一遍。
- （四）已经提交的结果文件被改了一句。改法是保留原话的引述并标明更正轮次，没有悄悄改写。
- （五）本轮由需求受理／机动执行窗口直接改。本窗口没有合入、没有登记已验收。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在真实界面上验证；未 push、未 merge。
- 本轮提交之后没有再跑架构门禁（只改了结果文件）。
