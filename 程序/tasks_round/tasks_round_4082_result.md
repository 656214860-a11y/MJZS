# R4082 结果：模型回话流式输出边写边排（REQ-S01-100）
<!-- round-evidence: {"commit_base": "64dcdbdb", "credential_hits": 0, "evidence_sha256": "4c566c48338226d0", "exit": 0, "failed": 0, "passed": 186, "round": 4082, "tests": "run_selftests.py -k idea_chat"} -->

## 开头三问

（一）本轮属于哪种类型：功能轮，任务卡 B-CHT-4（测试文件由前一张卡 B-CHT-4A 写入），车道 codex/chat-bubbles，对应《对话区排版接入任务书》4.4 节（CHT-4）和 REQ-S01-100。

（二）测试跑了吗：tests/test_idea_chat_markdown.py 新增 ChatStreamMarkdownTests 共 7 条，改前实测 7 条全部失败，断言原文：

- `AssertionError: '# 标题\n正文 **粗' != '标题\n正文 **粗'`
- `AssertionError: '# 标题\n正文 **粗体**\n' != '标题\n正文 粗体\n'`
- `AssertionError: 0 != 1`
- `AssertionError: '# 标题\n正文 **粗体**\n没写完' != '标题\n正文 粗体\n没写完'`
- `AssertionError: '**新**的一行\n新的半' != '新的一行\n新的半'`
- `AssertionError: '**' unexpectedly found in '# 标题\n正文 **粗体**\n- 甲\n- 乙\n'`
- `AssertionError: 14 != 24`

改后与 tests.test_idea_chat_presentation、tests.test_idea_chat 一起实测 165 条全过；架构门禁实测 696 条全过、失败集合为空；默认冒烟实测通过 9 项、失败 0 项；全量自测没跑；没有改原有用例。

（三）欠账少了吗：REQ-S01-100 从 ⬜ 变成 ✅；复杂度记录没有调大；没有新增欠账。

## 改了哪些文件

- ui/desktop_idea_bubbles.py：refresh_stream_text 把缓冲按最后一个换行分成写完的行和没写完的一行，写完的行经 skill_note_render.insert 按排版写入，没写完的一行按原文接在后面，写完的行没有变化时只替换最后一行；新增 _draw_stream_done，从 stream_start 起整段重排写完的行并放下 stream_tail 标记；add_thinking_line、begin_stream、end_stream 清掉 _stream_done；bubble_stream 标签的左右边距改为落地气泡正文的边距，左右各加 BUBBLE_PAD。
- tests/test_idea_chat_markdown.py：新增 ChatStreamMarkdownTests 7 条，顶部多引入 skill_note_render，模块说明两行补上 REQ-S01-100；原有 9 条用例未改；由前一张卡写入。
- docs/stages/S01_剧本准备.md：REQ-S01-100 的 ⬜ 改成 ✅，DES-S01-100 括号里去掉「未实现」。
- tasks_round/tasks_round_4082_result.md（本文件）。

没有改 ui/skill_note_render.py、ui/desktop_idea_chat.py，没有改轮询间隔和 push_stream。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `scripts\gui_hidden.py logs\cht4-red.log . -- python -m unittest tests.test_idea_chat_markdown.ChatStreamMarkdownTests` | 退出码 1；Ran 7 tests；FAILED (failures=7)，7 行 FAIL:，无 ERROR |
| `scripts\gui_hidden.py logs\cht4-green.log . -- python -m unittest tests.test_idea_chat_markdown tests.test_idea_chat_presentation tests.test_idea_chat` | 退出码 0；Ran 165 tests；OK |
| `python -B smoke_test.py --architecture` | 退出码 0；Ran 696 tests；OK；失败集合为空 |
| `python -B smoke_test.py` | 退出码 0；通过 9 项；失败 0 项 |
| `python -B scripts\dev.py claim` | 退出码 0；轮次 4082 |

## 如实说明

（一）本轮由两张卡接力：B-CHT-4A（执行者 Devin）只写测试文件，没有运行命令；本卡（执行者 OpenCode）做改前红测、改实现、改后测试、门禁、阶段文件状态、领号和提交。测试和实现的代码由总控给出，派卡前用内存补丁预验证过，执行方照卡面落地。

（二）与任务书写法不同的地方：车道名是 codex/chat-bubbles（任务书写 codex/chat-render）。任务书 S2 写流式正文的左右边距用 bubble_stream 标签的 lmargin1、rmargin，本轮照做，同时把 bubble_stream 标签自己的边距从气泡外边距改成了落地气泡正文的边距（左右各多 BUBBLE_PAD）：排版标签整个聊天框共用一套，流式和落地的边距不同的话，前面回话里的列表、引用缩进会在流式期间跟着变；流式文字因此比改前向内缩了一个 BUBBLE_PAD，与落地后的正文对齐。这一点总控已报给负责人，负责人有不同意见时再改回。测试比任务书多一条（第 7 条，守上面这条边距）；T4 用 show_conversation 做真实重画（它会重新调用 add_thinking_line）；T6 用真实的落地流程（clear_thinking 后写入模型消息再重画）比对，没有直接调 add_bubble。S01 文件除了状态记号，还去掉了 DES-S01-100 括号里的「未实现」，与 R4064 对 DES-S01-99 的做法一致。测试文件的模块说明改了两行（补上 REQ-S01-100），任务书写的是只新增用例；原有用例没有动。

（三）已知的显示限制：没写完的最后一行按原文显示，所以行内的记号（例如两个星号）要等这一行的换行到达或回复落地后才变成排版；段落之间的空行要等下一段的第一行写完才出现。

（四）没有在真实桌面上目检，只有隐藏桌面里的自动化用例。

## 未覆盖项

- 未跑全量自测。
- 没有截图目检。
- 没有运行 `smoke_test.py --affected desktop_idea_bubbles`（R4064 的结果文件已记录：它按测试文件名筛选，选中 0 个文件并按失败处理；受影响的用例就是上面三个对话测试文件）。
- 未 push、未 merge。
