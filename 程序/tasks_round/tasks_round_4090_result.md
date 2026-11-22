# R4090 结果：剧本准备页的示例改成技能说明加前置锁选项，必填锁留空
<!-- round-evidence: {"commit_base": "7ea1ddeb", "credential_hits": 0, "evidence_sha256": "4fd029e06ba6b794", "exit": 0, "failed": 0, "passed": 266, "round": 4090, "tests": "run_selftests.py -k idea_inline_brief idea_chat ui_edges_pages desktop_startup_perf"} -->

## 开头三问

- 本轮属于哪种类型：功能轮（任务卡 UX-C5；车道 `codex/ux-example-locks`，基线 `7ea1ddeb`）。
- 测试跑了吗、三个基线：先红后绿。默认冒烟通过 9 项、失败 0 项；架构门禁 `Ran 696 tests`、`OK`、退出码 0；全量回归本轮没跑，全量欠账以 `full-safe-receipts.json` 为准，本轮没有改变它。定向测试逐条结果见「命令与退出码」。
- 欠账少了吗：没有新增欠账。旧示例里的三处毛病随重写消掉了（见「改前的示例有什么问题」）。新增 9 条守卫，以后契约（必填字段、本阶段必填的锁、锁的选项）改了而示例没跟着改，会红。

## 改前红

守卫是新写的 9 条（`tests/test_idea_inline_brief.py` 里的 `DefaultExampleGuardTests`）。见红的办法：把主线版的示例（`git show HEAD:程序/默认创意示例.md`）另存到仓库外，用一个小脚本把测试类的 `EXAMPLE` 指到那份副本，再跑这 9 条；车道里的文件没有回退。21:10:22，退出码 1：

```text
Ran 9 tests in 0.016s

FAILED (failures=9)
```

9 条各自红在哪里（摘自同一次输出，路径省略）：

```text
FAIL: test_example_pasted_unchanged_is_stopped_for_exactly_the_required_locks
AssertionError: Lists differ: ['素材来源', '赛道'] != ['交付形态', '素材来源', '赛道']

FAIL: test_lock_lines_are_blank_and_the_header_lists_registered_options
AssertionError: Lists differ: ['故事集数', '单集时间', '故事画幅', '视频模型', '交付形态', '故事题材'] != ['素材来源', '赛道', '交付形态', '视频模型', '故事画幅', '段缝衔接方式']

FAIL: test_required_marks_match_the_contract
AssertionError: Lists differ: [] != ['交付形态', '单集时间', '故事梗概', '故事角色', '故事集数', '故事题材', '素材来源', '赛道']

FAIL: test_theme_line_precedes_genre_so_the_genre_line_wins
AssertionError: 8 not less than 5

FAIL: test_header_is_description_and_adds_no_fields
AssertionError: [] is not true : 示例开头要有技能说明段

FAIL: test_choosing_a_listed_option_for_each_required_lock_passes_the_send_check
FAIL: test_each_empty_required_value_is_reported_by_name
FAIL: test_sent_with_chosen_locks_stores_exactly_those_options
FAIL: test_filling_from_the_missing_items_dialog_lands_on_the_blank_lock_lines
（这四条都红在同一个辅助函数里）
AssertionError: 说明段里没有「交付形态可选 → …」这一行
```

换回车道里的新示例，同一个类连同文件里原有的 `InlineBriefTests` 一起跑（21:10:24）：`Ran 21 tests`，`OK`。

## 改前的示例有什么问题

用同一套解析函数在主线版示例上实测（只读探针，不写项目文件）：

- 行尾的 `**(必填项)**` 会被当成取值的一部分：解析出的「故事集数」是 `100 集  **(必填项)**`。
- 示例里写了值的三把锁，存下来的都不是契约登记的选项：画幅 `16:9    **(必填项)**`、交付形态 `离线看板 或 markdown文本    **(必填项)**`、视频模型 `seedance 2.5`（登记的写法是 `Seedance 2.5`）。
- 「故事主题」是「故事题材」的别名，同一个字段后写的覆盖先写的。旧示例里主题行排在题材行后面，用户只改题材行，解析出来的题材仍是主题行那一串。
- 原样粘贴发送会被拦下，点名素材来源、赛道——示例里根本没有这两行，也没有任何地方告诉用户有哪些选项。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `默认创意示例.md` | 25 增 11 删，23 行变 36 行。开头新增 11 行说明：第 1 行是技能名和一句话用途；第 2 行说它动手前要先确认五把前置锁和画风；第 3 行写明本页发送前必须写明素材来源、赛道、交付形态三项，行首带星号的行必填；第 4–10 行逐项列出选项（素材来源、赛道、交付形态、视频模型、故事画幅、段缝衔接方式、故事画风）；第 11 行说明带星号的锁空着等用户填、其余各行是示例。说明之后是六行锁（素材来源、赛道、交付形态带星号，视频模型、故事画幅、段缝衔接方式不带），冒号后面都留空。故事字段示例值的文字没改（冒号后的空格统一成一个），只做了三件事：行尾的 `**(必填项)**` 去掉，改成必填行行首加星号和一个空格；「故事主题」挪到「故事题材」前面；原来写了值的「故事画幅」「视频模型」「交付形态」三行改成上面的留空锁行。角色的 7 行续行没动。文件仍是 LF、无 BOM、以换行结尾。 |
| `tests/test_idea_inline_brief.py` | 只增不删（165 增 0 删）：新类 `DefaultExampleGuardTests`，9 条用例，见下一节。原有用例一字未动。没有新建测试文件，所以没有动 `governance/structure.json`。 |
| `tasks_round/tasks_round_4090_result.md` | 本文件。 |

## 9 条守卫各管什么

必填字段、本阶段必填的锁、每把锁的选项都从契约里取（`script_contract.INLINE_REQUIRED_LABELS`、`script_contract.stage_lock_requirements('script', …)`、`PRODUCTION_LOCK_DEFINITIONS`），测试里没有把「哪三把」写死；写死的只有示例里六行锁的行序和标签、项目创建日期 `2026-11-22`。

1. `test_example_pasted_unchanged_is_stopped_for_exactly_the_required_locks`：原样粘贴发不出去，点名的正好是本阶段必填的锁，故事字段的示例值不被点名。
2. `test_choosing_a_listed_option_for_each_required_lock_passes_the_send_check`：必填的锁各取说明段列出的第一个选项后，发送检查通过。
3. `test_each_empty_required_value_is_reported_by_name`：必填的锁逐个留空，故事梗概、故事集数、单集时间、故事题材逐个清空，点名的正好是那一项。
4. `test_lock_lines_are_blank_and_the_header_lists_registered_options`：六行锁的顺序；标签是契约登记的标签或别名；取值留空；说明段给每把锁至少列两个选项，而且都是契约登记的选项。
5. `test_sent_with_chosen_locks_stores_exactly_those_options`：走 `receive_brief` 存下来的锁值正是所选的登记选项（行首星号不进取值）。
6. `test_filling_from_the_missing_items_dialog_lands_on_the_blank_lock_lines`：缺项弹窗回填（`merge_brief_creation`）的值落在空着的锁行上，总行数不变，回填后发送检查通过。
7. `test_required_marks_match_the_contract`：带星号的行正好是契约的必填故事字段加本阶段必填的锁；必填的故事字段保留示例值；说明段有且只有一行写明必须写明的锁并交代星号的意思；全文没有行尾的全角必填标记，也没有旧的「必填项」写法。
8. `test_theme_line_precedes_genre_so_the_genre_line_wins`：「故事主题」在「故事题材」前面，解析出的题材是题材行的值。
9. `test_header_is_description_and_adds_no_fields`：说明段首行含技能名、顶格、没有冒号；其余行都缩进；没有竖线、制表符和斜杠开头的行；说明段解析不出任何字段，全文的标签行正好是说明段之后的那些行。

## 与任务书不同的地方

- 记录里 UX-C5 的书面要求（需求机动窗口 20:45 写的版本）是「示例里把锁值预填好、必填行用行尾标记」。需求机动窗口 20:53 在心跳里改了决定：三把必填锁在示例里留空让用户自己选（理由是这更合技能「缺锁就停下来问」的规矩），必填行用行首星号，20:45 的预填锁值和行尾标记两条作废。本轮按 20:53 的决定做。带来的行为：原样粘贴示例发送会被拦下，点名素材来源、赛道、交付形态。
- 说明段前 10 行用的是需求机动窗口给的底稿，第 3 行按它的要求把「带必填的行缺一不可」改成「行首带星号的行必填」。第 11 行是我写的：底稿原句说下面是一组可以直接发送的示例，锁留空以后这句话不成立。需求机动窗口 21:03 同意，并建议不要把「三把」写死（赛道以后可能改成选填），现在的句子是「下面带星号的锁空着等你填，从上面的选项里各选一项。其余各行是示例，把冒号后面换成你自己的内容」。
- 「故事主题」挪到「故事题材」前面，是我提的，需求机动窗口 20:53 同意。原因见「改前的示例有什么问题」第三条。
- 提交命令的 `--agent` 写实际执行方。

## 如实说明

- 20:53 前后两个窗口的留言交叉了：我按 20:45 的版本写过第一版（预填锁值，6 条守卫，20:54 见红见绿），随后读到需求机动窗口 20:53 的答复，第一版整体作废，示例和守卫重写。作废的那一版没有提交。
- 需求机动窗口问的「气泡里会不会同一行带两种必填标记」：读代码核对，主线 `7ea1ddeb` 和当时的叠放顶 `18d962d4` 上，行尾的全角必填标记在生产代码里只出现在 `domain/idea_brief_form.py` 的 `strip_inline_required_markers`（发送前把它去掉），没有任何代码往气泡的行尾补标记，示例气泡显示的就是这个文件的原文。主线上气泡是纯文本；叠放顶上对话气泡接了 Markdown 排版，但示例气泡被排除在外（`ui/desktop_idea_bubbles.py` 里的 `markdown=not mine and not example`）。所以一行只有行首星号一种标记，星号按字面显示。这是读代码得出的，没有在真实窗口里看过。
- 留空的三行非必填锁（视频模型、故事画幅、段缝衔接方式）不会被点名，也不会存下空值：探针在最小项目里发送后，存下来的锁只有 `{'delivery_format': '两者都交付', 'track': '国内剧', 'material_source': '原创'}`。
- 老项目：创建日期早于赛道、素材来源生效日的项目（探针用 `2026-01-01`），原样粘贴只点名交付形态一项。说明段第 3 行写的是「三项」，对这类老项目来说多说了两项；没有为它另写一套文字。
- 几处改前就有、这轮没有动的解析行为（探针实测，写出来供验收窗口和后续卡参考）：「世界设定」「关键事件」「参考作品」不是登记的字段，这几行会并进它前面的那个字段；因此把「故事角色」清空不会被点名（后面的「关键事件」等行并了进来），把「故事梗概」整行删掉也不会被点名。守卫第 3 条因此只覆盖梗概、集数、时间、题材四个字段的清空。
- 整份示例粘贴后发送，开头 11 行说明是这条消息正文的一部分，发送时不会被去掉。要不要让「复制软件示例」只复制字段部分，需求机动窗口说不在这张卡里。
- 21:01–21:09 那一遍验收命令是在最后两处小改之前跑的（说明段第 11 行去掉「三把」两个字；守卫第 3 条的循环加上「故事题材」）。小改之后重跑了改前红（9 条全红）和非界面的两个类（21 条全过）；四组验收测试在最终内容上的结果是提交工具提交时跑的那一遍，记在 `tasks_round/evidence/R4090.json` 和本文件第二行的戳里。
- 定向测试的输出里有多行 `invalid command name "...start_account_renewal"` 一类的文字（窗口销毁后 `after` 定时器才触发），不是失败；主干和其他车道的既有日志里也有同样的行。
- 本轮没有改任何生产代码的 `.py` 文件，没有可填的 `smoke_test.py --affected <模块>`；读这个示例文件的页面由验收命令里的四组测试覆盖。
- 没有新建工作目录：复用闲置目录 `.agents/worktrees/l4-buttons-script`，在里面从主干切出分支 `codex/ux-example-locks`。测试进程都降到 BelowNormal 优先级。

## 命令与退出码

工作目录都是车道的 `程序`，`PY` 指 `..\..\..\..\运行环境\Python\python.exe`；时间是 2026-11-22 本机时钟。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `PY -X utf8 -B 维护记录\基准脚本\round_claim.py next` | 0 | 领到轮次 4090 |
| 9 条守卫指向主线版示例的副本（21:10:22，最终的测试内容） | 1 | `Ran 9 tests`，`FAILED (failures=9)` |
| `PY -X utf8 -B -m unittest -v tests.test_idea_inline_brief.DefaultExampleGuardTests tests.test_idea_inline_brief.InlineBriefTests`（21:10:24，最终内容；`PYTHONPATH` 指向 `tests` 目录） | 0 | `Ran 21 tests`，`OK` |
| `PY -X utf8 -B run_selftests.py -k idea_inline_brief idea_chat ui_edges_pages desktop_startup_perf`（21:01:41–21:09:59，最后两处小改之前） | 0 | 266 条全绿，0 个文件有红，实际跳过 0 条；其中约 5 分钟在等别的窗口占着的界面令牌 |
| `PY -X utf8 -B smoke_test.py`（21:13:26–21:13:27，定稿内容） | 0 | 通过 9 项、失败 0 项 |
| `PY -X utf8 -B smoke_test.py --architecture`（21:13:27–21:19:16，定稿内容） | 0 | `Ran 696 tests in 347.140s`、`OK`；输出里另有两条棘轮提示（LR-09、LR-10：实测 59 < 基线 60），是提示不是失败，本轮没有去动那份清单 |

## 未覆盖项

- 未跑全量自测（`run_selftests.py --all --safe`）：用户 2026-11-22 19:52 决定验证期间不跑全量、只跑定向测试。
- 没有在真实窗口里目检示例气泡（折行、星号的样子、36 行在空页面里占多高），只有隐藏桌面里的自动化用例。
- 赛道是否必填还在等用户答复（需求机动窗口 20:35 问的）。改成选填时契约一改守卫第 7 条会红，按提示去掉示例里赛道行的星号、改说明段第 3 行即可。
- 用户文档里的对应说法归 UX-C5D，不在本卡。
- 「复制软件示例」是否只复制字段部分，不在本卡。
- 未 push、未 merge、未改主工作区；复核、验收、合入归验收窗口。

## 合入后用户怎么看

打开一个还没有对话的项目，进剧本准备页：灰色示例的开头是技能说明和各把锁的选项。在示例上点右键选「复制软件示例」，粘贴到输入框，不改直接发送，会被拦下并点名素材来源、赛道、交付形态；三项各填一个选项后可以发送。

## 提交

本文件随 R4090 的提交一起入库（分支 `codex/ux-example-locks`）。写本文件时提交号还没有产生，提交号见 `git log` 和会话接续记录里编码窗口一节。
