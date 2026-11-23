# R4166 结果：UX-REPLY-FORMAT-CHOICE 回话格式约束与可点选项卡
<!-- round-evidence: {"commit_base": "6997ae43", "credential_hits": 0, "evidence_sha256": "9261a0fe285fb69f", "exit": 0, "failed": 0, "passed": 331, "round": 4166, "tests": "run_selftests.py -k idea_chat ui_hitl hitl writing_api prompt"} -->

## 开头三问

- 类型：功能轮（DOC-D8-3／DOC-D8-4；REQ／DES-S01-108／109）
- 测试和三个基线数：定向 `run_selftests.py -k idea_chat ui_hitl hitl writing_api prompt` 331 条、0 红、退出码 0；`smoke_test.py --architecture` 700 条、退出码 0。默认冒烟未单跑；全量未跑。
- 欠账：真实模型是否遵守回话格式未用付费调用验证；审批门 `build_approval_gate` 仍未接线。

## 改了哪些文件

- `docs/specs/08_对话式交互与输出排版.md`、`docs/stages/S01_剧本准备.md`：DOC-D8-3／4 与 REQ／DES-S01-108／109 状态落盘
- `orchestrator/workflow_engines.py`：`REPLY_FORMAT_RULE` 注入 `prompt_with_settings`（常量放文件末尾，避免进程启动点行号漂移）
- `domain/hitl.py`：`parse_choice_reply`／`MAX_CHOICES`
- `ui/ui_hitl.py`：`build_choice_card` 支持 `on_pick`／`selected`；「其他…」走 `LineInput`／`HintLabel`
- `ui/desktop_idea_bubbles.py`：落地剥离标记并嵌卡；流式剥离半截标记不出卡
- `tests/test_prompt_templates.py`、`tests/test_hitl_ui.py`、`tests/test_idea_chat_markdown.py`：新增断言；`card_widgets` 排除 Spinner

## 命令与结果

| 命令 | 退出码 | 结果行 |
|---|---|---|
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k idea_chat ui_hitl hitl writing_api prompt` | 0 | 共 331 条用例；0 个文件有红；ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | Ran 700 tests；OK；架构治理测试通过 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 4166 |

先红后绿（本车道续做）：上一个执行者留下文档／测试／半成品；补齐产品后首轮定向见红（正文尾换行、`window_create(align='left')` 非法、按钮 `cget('state')`、Spinner 计入选项卡、架构门禁五行）。改产品后上述两条验收命令均为 0。

## 按推荐执行的待确认项

- 回话格式：唯一注入 `prompt_with_settings`，产物契约排除——已按推荐执行
- 可点选项：```` ```choices ````、最多 4、点选即发、置灰「已选：X」、与 FormDialog 并存——已按推荐执行

## 如实说明

- 续做说明：保留上一个执行者的文档、解析、测试与 `build_choice_card` 扩展；补上 `REPLY_FORMAT_RULE` 与气泡接线；修正嵌入对齐、禁用态与架构门禁（类行数外提、`LineInput`、启动点行号）。
- `test_idea_chat_markdown.ChoiceCardTests.card_widgets` 排除 `Spinner`：流式思考行本身有转圈窗口，不计为选项卡（新辅助函数，断言意图不变）。

## 未覆盖项

- 未真实调用付费模型验证回话格式遵守
- 未改 FormDialog；审批门仍未接线
- 未跑默认冒烟与全量自测
