# R4072 结果：共享输入框发送不换页，技能命令在当前页的入口里执行（DOC-D8-7）
<!-- round-evidence: {"commit_base": "5c85dd13", "credential_hits": 0, "evidence_sha256": "b41289852cd52f5f", "exit": 0, "failed": 0, "passed": 86, "round": 4072, "tests": "run_selftests.py -k shared_input skill_command"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮，用户报的使用问题。任务卡 W4-UX-B12（队列项 UX-B12），车道 codex/ux-send-routing，基准 5c85dd13。现象：在「剧本结构」页的输入框点发送后，页面跳到了「剧本准备」。根因：`desktop_shared_send._send_skill` 解析出技能所属阶段后，只要它和当前页不同就调 `_goto_stage` 换页再执行；这是 R2898 的既有设计，`test_skill_command_dispatches_with_skill_prompt` 钉着这个行为。复现：改代码前把这条用例按新规则改写并新增用例，3 条失败（见「命令与结果」）。
- （二）测试跑了吗、三个基线：定向 `tests.test_shared_input_stages.SendDispatchTests` 改前 13 条里 3 条失败、改后 13 条全过，连同 `tests.test_skill_command` 共 34 条全过；架构门禁 696 条全过（最后一处改动之后重跑的）；默认冒烟没有单独跑；全量自测没跑。带界面的 `run_selftests.py -k shared_input skill_command` 由提交工具在提交时跑，结果以本文件的证据行为准。
- （三）欠账少了吗：少了一条（发送后被带离当前页）。没有新增欠账。同一次反馈里的「API 模型弹出命令行窗口」本轮没有改，见「如实说明」第（三）条。

## 改了哪些文件

- desktop_shared_send.py：`_send_skill` 不再调用 `_goto_stage`。当前页有对话入口（在 `FLOW_FOR_STAGE` 里）就把技能提示交给当前页的入口；没有就在状态栏提示并返回 False，输入框保留原文；不在制作阶段页面时提示先打开一个制作阶段页面。新增 `_no_entry_hint`：技能属于有入口的别的阶段时，提示里给出用户自己换页的写法（`/<阶段名> /<技能名>`）。`_goto_stage` 的说明文字改为只服务 `/阶段` 命令。`_send_free` 在无入口页的提示语后半句由「或 /skill、/<阶段名> 命令」改为「或输入 /阶段名 换到有对话入口的阶段」（见「如实说明」第（八）条）。21 行新增、11 行删除。
- tests/test_shared_input_stages.py：改写 1 条既有用例的断言，新增 4 条用例（当前页无入口时用别的阶段的技能只提示不换页；本阶段技能在无入口页沿用原提示；明确写 `/阶段名 /技能名` 仍然换页；不在制作阶段页面时提示先打开阶段页）。59 行新增、1 行删除。
- docs/specs/08_对话式交互与输出排版.md：决定表加 DOC-D8-7 一行，引导句由「共六条」改为「共七条」并注明第七条的日期；§8 加「命令的去向」一段；§8 里引用的无入口提示语同步成新文案。5 行新增、2 行删除。
- docs/records/对话需求追溯.md：加一行（11-22 · 562cdbb1，发送不换页）。
- tasks_round/tasks_round_4072_result.md 是本文件。

## 命令与结果

下表里的 `-m unittest` 都是在车道的 程序 目录下、环境变量 PYTHONPATH=tests 时跑的（不设这个变量时 `tests/ui_edges_support.py` 导入不到同目录的辅助模块）。

| 命令 | 结果 |
| --- | --- |
| python.exe -B scripts\dev.py claim | 领到轮次 4072 |
| python.exe -B -m unittest tests.test_shared_input_stages.SendDispatchTests（改测试后、改代码前） | 13 条里 3 条失败：`test_skill_command_dispatches_with_skill_prompt`（「Lists differ: ['storyboard'] != []」）、`test_cross_stage_skill_on_page_without_entry_stays_and_hints`（「True is not false」）、`test_skill_command_outside_stage_pages_asks_for_a_stage`（「True is not false」） |
| python.exe -B -m unittest tests.test_shared_input_stages.SendDispatchTests tests.test_skill_command（全部改动之后） | 「Ran 34 tests」「OK」 |
| python.exe -B smoke_test.py --architecture（全部改动之后） | 「Ran 696 tests in 267.171s」「OK」，退出码 0 |
| git diff --shortstat | 4 个文件，86 行新增、14 行删除（不含本文件） |

## 如实说明

- （一）本轮改了一条既有测试的断言，属于契约变更。`test_skill_command_dispatches_with_skill_prompt` 原来断言「技能属于别的阶段时跳到那个阶段」，现在断言「不换页、交给当前页的入口」。依据是用户 2026-11-22 的缺陷反馈（来源 562cdbb1）和规格 08 新增的 DOC-D8-7。其余既有用例没有改动。
- （二）修复后，在「剧本结构」页用 `/技能名` 发送的结果是不换页、不发送、状态栏提示。这一页仍然没有自己的对话入口；要不要加，取决于用户对「剧本结构阶段去留」的裁决，本轮没有做。
- （三）用户同时反馈的「API 模型弹出 Qwen Code 命令行窗口」本轮没有改。读代码的结论：这是没有直连执行的流程的既有回退，`ui/desktop_direct_dispatch.dispatch` 只有 storyboard、audio、video_prompt、assets 四个流程有应用内直连分支，其余（含剧本准备的 writing）会把 API 模型放进 Qwen Code 窗口里跑。本轮之后，在「剧本结构」页发送不再开窗口；在「剧本准备」页用 `/技能名` 加 API 模型仍会开。改掉它涉及取舍（大的技能包塞不进单次请求、纯 HTTP 请求不能读写本地文件），已向用户给出两种做法，等裁决。
- （四）新规则的一个直接结果：在有入口的页面上用别的阶段的技能，会按当前页的流程名和会员闸门执行（`_open_flow` 取 `FLOW_FOR_STAGE[当前阶段]`、`account.stage_gate(当前阶段)`），不再按技能所属阶段的流程执行。
- （五）没有在真实界面上点过。本轮的验证都是单元级的：`SendDispatchTests` 用桩对象和一个隐藏的 Tk 根窗口，是直接用 `-m unittest` 跑的。
- （六）`/分镜` 这类模糊的阶段名仍按阶段顺序取第一个匹配的阶段并换页（`tests/test_skill_command.py` 的 `test_ambiguous_stage_name_takes_first_in_order` 钉着解析结果），它是用户明确输入的阶段命令，状态栏会提示「已切换到…」，本轮没有动。
- （七）本轮由需求受理／机动执行窗口直接写代码。按四窗口协调第 10 条，除验收窗口复核和 `verify` 外，还要加一张只读审查卡。
- （八）无入口页发自由文本时的提示语改了后半句。原文建议「或 /skill、/<阶段名> 命令」，技能命令不再换页之后，在无入口页用技能命令只会再得到一句提示，这个建议不成立了，改为「或输入 /阶段名 换到有对话入口的阶段」。既有测试只钉「暂无对话入口」这几个字，没有改测试。历史文件（专题一对话式交互盘点报告 F30、R4011 结果、工程文档细化任务书）里引用的是旧原文和当时的行号，属于当时的记录，没有改；这句提示仍在 `desktop_shared_send.py` 第 138 行。
- （九）架构门禁跑了两次：第一次在改提示语之前（696 条全过），第二次在全部改动之后，表里写的是第二次。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在真实界面上验证；未 push、未 merge。
- 「剧本结构」页的页内对话入口、API 模型不开命令行窗口两项等用户裁决，不在本轮。
