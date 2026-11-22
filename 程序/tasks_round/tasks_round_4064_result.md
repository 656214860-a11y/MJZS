# R4064 结果：剧本准备页模型回话按排版显示（REQ-S01-99）
<!-- round-evidence: {"commit_base": "c53e60da", "credential_hits": 0, "evidence_sha256": "62aa12545338ca47", "exit": 0, "failed": 0, "passed": 9, "round": 4064, "tests": "run_selftests.py -k idea_chat_markdown"} -->

## 开头三问

（一）本轮属于哪种类型：功能轮，任务卡 B-CHT-3，车道 codex/chat-bubbles，对应《对话区排版接入任务书》4.3 节（CHT-3）和 REQ-S01-99。

（二）测试跑了吗、三个基线：新增 tests/test_idea_chat_markdown.py 共 9 条，改前 3 条失败 2 条报错，改后实测 9 条全过；原有 tests.test_idea_chat_presentation、tests.test_idea_chat、tests.test_skill_note_render 实测 177 条全过；架构门禁实测 696 条通过、失败集合为空；默认冒烟实测通过 9 项、失败 0 项；--affected desktop_idea_bubbles 实测选中 0 个测试文件，门禁按失败处理（明细见第三节）；全量自测没跑。

（三）欠账少了吗：REQ-S01-99 从 ⬜ 变成 ✅；复杂度记录没有调大；没有新增欠账（流式输出边写边排是 REQ-S01-100，由 CHT-4 另做）。

## 改了哪些文件

- ui/desktop_idea_bubbles.py：顶部引入 skill_note_render；新增 _write_bubble_body，模型消息按排版写入，排版结果为空时退回原文；add_bubble 在 _bubble_full 里多记 markdown、left、right 三个键，正文改由 _write_bubble_body 写入；toggle_bubble 展开、收起时用同一个方法重写正文。
- tests/architecture/_layers.py：SAME_LAYER_EDGES 登记 desktop_idea_bubbles 到 skill_note_render 这条同层依赖。
- tests/test_idea_chat_markdown.py：新增，9 条用例。
- governance/structure.json：test_ownership 加一条登记；governance/structure-baseline.json：用工具重写，未手改。
- docs/stages/S01_剧本准备.md：REQ-S01-99 的 ⬜ 改成 ✅，DES-S01-99 括号里去掉「未实现」。
- tasks_round/tasks_round_4064_result.md：本文件。

没有改 ui/skill_note_render.py，没有改用户消息和软件示例的显示，没有改折叠阈值。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| check_structure.py --write-baseline --summary | 退出码 0；写入基线后 finding_count 0，无新增、无移除 |
| gui_hidden.py … unittest tests.test_idea_chat_markdown | new exit 0；Ran 9 tests，OK |
| gui_hidden.py … unittest tests.test_idea_chat_presentation tests.test_idea_chat tests.test_skill_note_render | old exit 0；Ran 177 tests，OK |
| smoke_test.py --architecture | 退出码 0；Ran 696 tests，OK，失败集合为空 |
| smoke_test.py | 退出码 0；通过 9 项，失败 0 项 |
| smoke_test.py --affected desktop_idea_bubbles | 退出码 1；选中 0 个测试文件，门禁报「定向筛选未命中任何测试」，未产生任何用例红（-k 只按测试文件名匹配，仓库里没有以 desktop_idea_bubbles 命名的测试文件，该模块的消费者测试名为 test_idea_chat*，与本轮改动无关） |
| scripts\dev.py claim | 退出码 0；轮次 4064 |

## 如实说明

（一）本轮分两次执行。第一次执行新建了车道，写好测试文件并做了改前红测，写了 _write_bubble_body、改了 toggle_bubble，之后因执行方额度用完而中断。第二次执行（续做）按任务卡补上 add_bubble 的改动、分层登记、结构登记和文档状态，跑了上表的检查，领号并提交。改前红测的结果（9 条里 3 条失败：排版显示、展开收起、嵌套列表；2 条报错：标签顺序、重画，原因都是当时还没有 md_bold 标签；其余 4 条通过）来自第一次执行的日志，总控已核对，第二次执行没有重做。

（二）与任务书写法不同的三处：车道名是 codex/chat-bubbles（任务书写 codex/chat-render；CHT-1、CHT-2 已随 R4055 合入，所以从 master 新建）；领号和提交按任务卡用 scripts\dev.py claim 和 scripts\dev.py commit；S01 文件除了状态，还去掉了 DES-S01-99 括号里的「未实现」，因为实现后这三个字不再属实。

（三）测试文件开头把 程序 目录和 tests 目录加进了 sys.path：tests/test_idea_chat.py 在模块顶部引入 skip_reasons，直接用 -m unittest 跑时需要 tests 目录可导入。

（四）列表、引用、代码块这几种行的缩进比普通正文大，灰色底块的左边缘在这些行上是否整齐，本轮没有目检；合入前由总控在隐藏桌面截图核对。

## 未覆盖项

- 未跑全量自测。
- 流式输出边写边排（REQ-S01-100，CHT-4）不在本卡。
- 隐藏桌面截图目检不在本卡。
- --affected desktop_idea_bubbles 选中 0 个测试文件，没有跑到任何受影响用例；该模块的消费者用例已在第二节的 9 条与 177 条里全过。
- 未 push、未 merge。
