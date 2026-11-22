# R4108 结果：停在剧本结构页点底部发送（或回车）就开始制作结构剧本（共享输入框加按阶段登记的发送动作，结构页登记与页面按钮同一个入口）
<!-- round-evidence: {"commit_base": "67068467", "credential_hits": 0, "evidence_sha256": "e07fb35e9c9bc798", "exit": 0, "failed": 0, "passed": 204, "round": 4108, "tests": "run_selftests.py -k shared_input skill_budget_send_entries ui_batch5_stage_panel_and_script_page manual_plan manual_gate stage_flow follow_buttons desktop_writing_page"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮。任务卡 W6B-SEND-1（队列项 SEND-1），任务书是需求机动窗口写的 `.agent-tmp/562cdbb1-task-SEND.md` 的 SEND-1 一节；车道目录 ux-dock-content，分支 codex/send-stage-action，基准 67068467。来源：用户 2026-11-22 22:45 报的缺陷——停在剧本结构页点底部的发送，只得到一句「暂无对话入口」。改前的行为（读代码得出，没有在真实界面上点出来过）：`SharedStageInput.send` 在输入框为空时直接返回、什么都不做；有字时走到 `desktop_shared_send._send_free`，剧本结构不在 `FLOW_FOR_STAGE` 里，只在状态栏写「『剧本结构』阶段暂无对话入口；请使用页面上的制作按钮……」。复现：先写测试，改产品之前跑，21 条里 15 条失败（见「改前红」）。
- （二）测试跑了吗、三个基线各是什么结果：定向——跑了。新加用例所在的两个测试文件：改产品前 21 条里 15 条失败；改后任务书的验收命令（九组关键词）「共 204 条用例，379.6 秒；0 个文件有红」，退出码 0（23:10:35 至 23:16:57，其中约五分钟在等界面令牌；这一遍的说明见「命令与退出码」）。架构门禁——在全部代码和测试改动之后整套跑过：「Ran 700 tests in 296.711s」「OK」，退出码 0（23:15:59 至 23:20:57）；输出里有一条主干既有的棘轮提示（LR-09、LR-10 实测 59 < 基线 60），不是本轮造成，没有动。改写前的第一遍架构门禁红过 1 条（类行数棘轮），经过见「与任务书不同的地方」第二条。默认冒烟和全量自测——没跑（窗口约定不跑全量）。提交工具在提交时会把验收命令的几组关键词再跑一遍，结果以本文件的证据行为准；提交工具和提交钩子都不跑整套架构门禁，所以架构门禁以上面单独跑的这一遍为准。
- （三）欠账少了吗：少了一条——用户报的这条缺陷在代码上修掉了（等验收和合入）。新增三条，都写在「未覆盖项」：阶段文档没有改（任务书要求不改 docs/stages，实现合入后由需求机动窗口补状态和测试锚定）；真实界面没有点过；`desktop_shared_input.py` 整个文件和其中的 `SharedStageInput` 类都只剩 10 行余量，后续卡（SEND-3）再往里加代码之前要先拆。

## 改前红

改产品代码之前（三个产品文件都还是原样），在车道的 程序 目录下跑 `run_selftests.py -k desktop_shared_input ui_batch5_stage_panel_and_script_page`（23:06:09 至 23:06:19，进程优先级 BelowNormal），退出码 1：

```
  test_desktop_shared_input     15 条     4.0 秒  ✗ 13
  test_ui_batch5_stage_panel_and_script_page     6 条     5.7 秒  ✗ 2
共 21 条用例，6.6 秒；2 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过

### test_desktop_shared_input（13 条红）
===== test_action_errors_are_left_to_the_action (test_desktop_shared_input.EmptySendRunsStageActionTests.test_action_errors_are_left_to_the_action) =====
  File "tests\test_desktop_shared_input.py", line 154, in test_action_errors_are_left_to_the_action
    self.box.set_stage_action(STAGE, boom)
AttributeError: 'SharedStageInput' object has no attribute 'set_stage_action'
===== test_empty_send_runs_the_registered_action_once (test_desktop_shared_input.EmptySendRunsStageActionTests.test_empty_send_runs_the_registered_action_once) =====
  File "tests\test_desktop_shared_input.py", line 86, in test_empty_send_runs_the_registered_action_once
    self.box.set_stage_action(STAGE, self.make)
AttributeError: 'SharedStageInput' object has no attribute 'set_stage_action'
===== test_text_send_runs_the_action_and_keeps_the_text (test_desktop_shared_input.TextSendOnStageWithoutFlowTests.test_text_send_runs_the_action_and_keeps_the_text) =====
  File "tests\test_desktop_shared_input.py", line 168, in test_text_send_runs_the_action_and_keeps_the_text
    self.box.set_stage_action(STAGE, lambda: seen.append(self.status()))
AttributeError: 'SharedStageInput' object has no attribute 'set_stage_action'
（另外 10 条是同一个错：test_action_of_another_stage_waits_until_the_page_switches、test_enter_on_an_empty_box_runs_the_action、
test_registration_is_replaced_and_removed、test_running_stage_is_not_started_twice、test_registration_does_not_leak_to_other_stages、
test_skill_command_on_stage_without_flow_is_unchanged、test_stages_with_a_flow_ignore_stage_actions、
test_text_send_on_a_running_stage_only_says_busy、test_text_send_still_respects_the_upstream_gate、
test_the_action_has_the_last_word_in_the_status_bar）

### test_ui_batch5_stage_panel_and_script_page（2 条红）
===== test_structure_page_send_action_follows_the_page_button (test_ui_batch5_stage_panel_and_script_page.ScriptPageLayoutTests.test_structure_page_send_action_follows_the_page_button) =====
  File "tests\test_ui_batch5_stage_panel_and_script_page.py", line 204, in test_structure_page_send_action_follows_the_page_button
    first = shared.stage_action('script_structure')
AttributeError: 'SharedStageInput' object has no attribute 'stage_action'
===== test_structure_page_send_key_shares_the_manual_entry (test_ui_batch5_stage_panel_and_script_page.ScriptPageLayoutTests.test_structure_page_send_key_shares_the_manual_entry) =====
  File "tests\test_ui_batch5_stage_panel_and_script_page.py", line 178, in test_structure_page_send_key_shares_the_manual_entry
    self.assertTrue(callable(shared.stage_action('script_structure')),
AttributeError: 'SharedStageInput' object has no attribute 'stage_action'
```

上面是节选：去掉了分隔线、「Traceback」行和插入符行，13 条里只贴了 3 条的栈，其余 10 条列了名字；文件路径只留了相对部分。

要说明的两点：

- 15 条红都是「登记接口还不存在」（`AttributeError`），不是断言失败。新行为挂在一个新接口上，改之前只能红在这里。改前就通过的 2 条新用例（`test_empty_send_without_registration_does_nothing`、`test_text_send_without_registration_keeps_the_old_hint`）钉的是不许顺手改坏的旧行为：没登记时空发送什么都不做、有字时仍是原来那句提示。这 2 条在改前的代码上就是用户看到的现象。
- 看到红以后，测试文件还改过一处：页面用例的建窗口辅助函数 `_open_structure_page` 加了「不跑首帧之后的后台维护」（见「如实说明」第（二）条），断言没有动。

撤掉产品改动时哪几条用例见红：

- 三个产品文件都撤掉：上面 15 条（实测）。
- 只撤 `desktop_shared_input.py` 里 `send` 的空文本分支（登记表留着）：`EmptySendRunsStageActionTests` 里靠 `send()` 或回车触发的 5 条（`test_empty_send_runs_the_registered_action_once`、`test_action_of_another_stage_waits_until_the_page_switches`、`test_running_stage_is_not_started_twice`、`test_enter_on_an_empty_box_runs_the_action`、`test_action_errors_are_left_to_the_action`）和页面用例 `test_structure_page_send_key_shares_the_manual_entry`。
- 只撤 `desktop_shared_send.py` 的改动：`TextSendOnStageWithoutFlowTests` 里的 `test_text_send_runs_the_action_and_keeps_the_text`、`test_the_action_has_the_last_word_in_the_status_bar`、`test_text_send_on_a_running_stage_only_says_busy`（都会退回「暂无对话入口」那一句）。
- 只撤 `ui/desktop_script_pages.py` 的改动：两条页面用例（建页后没有登记）。
- 后三条是按用例所测的代码对应出来的，没有逐处分开撤掉实测。

## 改了哪些文件

- desktop_shared_input.py（33 行新增、2 行删除，959 行变 990 行）：模块常量 `STAGE_ACTION_BUSY`（正在执行时的提示）；新的小混入类 `_StageActions`（25 行），三个方法 `set_stage_action(stage, action)`（登记、替换，`None` 取消）、`stage_action(stage=None)`（读取）、`run_stage_action(stage=None)`（执行并返回有没有执行；没登记或这一阶段正在执行都返回假，后者在状态栏写提示；动作抛错不吞）；`SharedStageInput` 多继承这个混入类，`__init__` 加一行登记表，`send` 的空文本分支从 `return False` 改为 `return self.run_stage_action()`（加一行注释）。
- desktop_shared_send.py（23 行新增，295 行变 318 行）：模块说明加一段；模块常量 `STAGE_ACTION_TEXT_UNUSED`（「这一步不使用输入框里的文字……」）；新函数 `_run_stage_action(desktop, stage)`；`_send_free` 里「阶段不在 `FLOW_FOR_STAGE`」的分支先问有没有登记，有就执行并返回假（输入框保留原文），没有就还是原来那句提示。
- ui/desktop_script_pages.py（21 行新增、1 行删除，774 行变 794 行）：`_ScriptStructurePage.build` 里把「手动制作结构剧本」按钮的命令提成局部函数 `run_manual`，按钮和登记共用这一个函数（表达式原样，没有写第二遍）；新方法 `_register_send_action(button, action)`：宿主有共享输入框且有登记接口时登记，按钮销毁时撤销（只撤自己登记的那一个），假宿主没有共享输入框时跳过。页面其他部分没有动。
- tests/test_desktop_shared_input.py（新建，237 行，15 条）：真实的 `SharedStageInput` 接上真实的 `desktop_shared_send.host_options`，宿主是一个最小替身（状态栏、项目根、`safe`、只记录的 Agent 入口）。
- tests/test_ui_batch5_stage_panel_and_script_page.py（66 行新增）：在现有的 `ScriptPageLayoutTests` 类里加辅助函数 `_open_structure_page` 和 2 条用例。原有的 4 条用例没有动。
- tasks_round/tasks_round_4108_result.md 是本文件；tasks_round/evidence/R4108.json 由提交工具生成。

没有改基线、覆盖率下限、各登记表；没有改 docs/stages；没有改旧断言；没有新加跳过。

## 测试与任务书的对应

| 任务书「测试」一节 | 用例 |
| --- | --- |
| 1 空文本加当前阶段登记了动作：调用一次并返回真，输入框、在途标记不变 | `test_empty_send_runs_the_registered_action_once`（输入框里只有空白；另断言不过上游门禁、不取模型快照、不开 Agent 对话）；回车键：`test_enter_on_an_empty_box_runs_the_action`（Shift 加回车仍是换行） |
| 2 空文本加没有登记：返回假，没有任何调用 | `test_empty_send_without_registration_does_nothing` |
| 3 动作登记在别的阶段：切过去以后才会调用 | `test_action_of_another_stage_waits_until_the_page_switches` |
| 4 这一阶段正在执行：不调用，状态栏有提示，返回假 | `test_running_stage_is_not_started_twice`（用 `stage_flow.mark` 造状态，结束后再发送能执行）；有字时：`test_text_send_on_a_running_stage_only_says_busy` |
| 5 `_send_free` 在剧本结构上有文字、已登记：动作被调用，返回假，状态栏不再是原来那一句；没登记时仍是原来那一句 | `test_text_send_runs_the_action_and_keeps_the_text`（经真实的 `send()` 走完整条路：文字留在框里、在途标记和模型快照复位）、`test_the_action_has_the_last_word_in_the_status_bar`、`test_text_send_without_registration_keeps_the_old_hint`、`test_registration_does_not_leak_to_other_stages` |
| 6 结构页构建后登记了动作，调用它走到 `manual_command` 包过的 `start_structure` | `test_structure_page_send_key_shares_the_manual_entry`（确认窗、模型提醒、`safe`、`start_structure` 都换成记录用的假函数：空发送与点页面按钮各走一遍，记录完全一样）、`test_structure_page_send_action_follows_the_page_button`（重建页面后是新页面的入口；按钮销毁后不再承载） |
| 7 已有流程的七个阶段行为不变 | 现有测试保持绿（验收命令里的 `shared_input` 几个文件）；另加 `test_stages_with_a_flow_ignore_stage_actions`（初步分镜上即使登记了动作，有字的发送仍走 Agent 流程） |
| 做法第 1 条：后一次登记覆盖前一次，`None` 取消；动作抛错不吞 | `test_registration_is_replaced_and_removed`、`test_action_errors_are_left_to_the_action` |
| 做法第 4 条：技能命令在没有对话流程的阶段不改 | `test_skill_command_on_stage_without_flow_is_unchanged` |
| 有字的发送仍先过上游门禁（任务书没有单列，我加的） | `test_text_send_still_respects_the_upstream_gate` |

## 与任务书不同的地方

- 新测试文件叫 `tests/test_desktop_shared_input.py`，任务书写的是 `tests/test_shared_stage_action.py`。结构检查（`governance/check_structure.py`，规则 STR006）要求新测试文件要么和一个生产模块同名，要么在 `governance/structure.json` 里登记归属；登记表不在允许修改的文件里，所以改了文件名。验收命令里 `shared_stage_action` 这个关键词因此匹配不到文件；`shared_input` 这个关键词会带上新文件。
- 登记表的方法放在同文件的小混入类 `_StageActions` 里，`SharedStageInput` 继承它；任务书写的是「放在 SharedStageInput 上」。页面拿到的接口没有区别（仍是 `desktop.shared_input.set_stage_action`）。原因：类行数棘轮（`tests/architecture/test_complexity_ratchet.py`，上限 600 行）——`SharedStageInput` 改前 588 行，直接写在类里会到 615 行，第一遍架构门禁就红在这一条；挪进混入类后是 590 行。
- 多了一个读取接口 `stage_action(stage=None)`。`_send_free` 要区分「没登记」（保持原来的提示）和「登记了但正在执行」（提示正在执行），只靠 `run_stage_action` 的返回值分不出来；页面撤销登记时也要用它确认撤的是自己那一个。
- 有字时「先写说明、再执行动作」。这样动作自己的开工提示、「正在执行」或报错是状态栏的最后一句，不会被「不使用输入框里的文字」盖掉；动作什么都没写时（比如用户在确认窗点了取消）状态栏留着这句说明。
- 「正在执行」的判断经 `ui_plugin_registry.module('stage_flow').running(stage)` 取，和页面按钮的 `follow` 走同一条路，没有新增跨层导入。
- 结构页登记时加了「按钮销毁就撤销登记」。任务书只写了「页面每次重建都会重新登记，后一次覆盖前一次」；不撤销的话，页面销毁后没有重建成功（比如换项目后这一页被锁住）时，发送键会留着一个指向已销毁页面的入口。
- `tests/test_shared_input_stages.py` 没有改（它在冻结的契约测试名单里，现有用例保持绿）。
- 其余照任务书做，没有改允许范围以外的文件。新测试的说明文字里没有写需求编号。

## 如实说明

- （一）没有在真实界面上点过。任务书 23:03 改的一句要求不从车道直接起真实的应用窗口（关窗时会另起项目库清理进程，车道里没有配置文件时会退回用户真实的项目库）。真实界面上的点击等验收窗口的合入前预览工具可用后由验收方做。
- （二）页面登记的两条用例不是假宿主：它们和同一个类里原有的用例 `test_structure_cards_share_left_edge_and_width` 一样，在测试进程里建一个 `Desktop` 对象（只经 `run_selftests.py` 跑，在隐藏桌面上），这样才能验证「真实的建页过程把入口登记到了真实的共享输入框上」。窗口用 `destroy` 关，不走应用自己的 `close`，所以不会另起清理进程（读过 `ui/desktop_lifecycle.py`：只有 `finish_close` 调 `launch_cleanup`，窗口被直接销毁时走的 `on_window_destroy` 只收定时器和本窗口派出的进程）。我加的两条还把 `Desktop._after_first_paint` 换成了空函数，不启动首帧之后的后台维护（技能同步、旧项目迁移、续期和更新检查的排程）；原有的那条用例没有动。验收方认为这两条也应该换成假宿主的话，可以改成只建 `_ScriptStructurePage` 所需的最小替身，代价是不再覆盖真实的共享输入框接线。
- （三）输入框里有字时的行为（照样开动、说明文字用不上、文字保留）是任务书的默认做法，用户还没有最后定。要改的话只动 `desktop_shared_send._send_free` 那一处分支和常量 `STAGE_ACTION_TEXT_UNUSED`。
- （四）行为变化：停在剧本结构页、输入框空着时按回车，以前什么都不发生，现在会出「手动制作」的确认窗（和点页面按钮一样，确认后才开工）。这是任务书要的效果。
- （五）空文本这条路不过上游门禁（任务书要求和点页面按钮完全一样，前置条件由动作自己判断和报错）；有字的发送仍然先过 `send()` 里原有的上游门禁，过不去时状态栏是门禁那句话、动作不执行。所以上游没完成时，空着点发送和有字点发送得到的提示不一样。任务书第 3 条只改 `_send_free`（在门禁之后），我按字面做了，没有把有字的发送也改成绕过门禁。
- （六）这一阶段正在执行时，发送按钮本身没有变灰，只是点了以后在状态栏提示正在执行；按钮置灰和悬停提示是 SEND-3，这一张没做。「正在执行」只看 `stage_flow.running`，和页面按钮变灰用的是同一个状态。
- （七）余量：`desktop_shared_input.py` 现在 990 行（模块行数棘轮上限 1000），`SharedStageInput` 现在 590 行（类行数棘轮上限 600）。SEND-3 或别的卡再往这个文件加代码之前，要先把一部分拆出去。
- （八）测试输出里有 `invalid command name "…start_account_renewal"` 这类定时器噪声（标准错误输出，不影响结果）：来自产品代码首帧回调里排的两个定时任务（续期、检查更新），窗口销毁时没有收回。这是既有现象，别的建真实窗口的测试文件也有；不在本卡允许修改的文件里，没有改。
- （九）主干已知的红（`-k idea_chat` 4 条、`-k ui_edges_pages` 1 条、`-k distribution_selfcheck` 1 条、`test_files_panel_stages` 机器忙时随机红、`test_pet_ui` 的 `FrameBatchSeamTests` 2 条）不在本轮跑的范围里，没有动。
- （十）本轮由推进预备窗口直接写代码。按窗口协调的约定，除验收窗口复核和 `verify` 外，还要加一张不同型号的只读审查卡。

## 命令与退出码

都在车道的 程序 目录下跑，python.exe 指 `..\..\..\..\运行环境\Python\python.exe`；测试进程优先级降到 BelowNormal。时间取本机时钟。

| 命令 | 结果 |
| --- | --- |
| python.exe -B scripts\dev.py claim | 领到轮次 4108 |
| python.exe -B run_selftests.py -k desktop_shared_input ui_batch5_stage_panel_and_script_page（改产品之前，23:06:09 至 23:06:19） | 退出码 1：「共 21 条用例，6.6 秒；2 个文件有红」（15 条红） |
| 验收命令一（第一遍，23:07:57 至 23:08:53；这时登记表的方法还直接写在 `SharedStageInput` 里，页面用例的辅助函数也还没改）：python.exe -B run_selftests.py -k shared_input shared_stage_action skill_budget_send_entries ui_batch5_stage_panel_and_script_page manual_plan manual_gate stage_flow follow_buttons desktop_writing_page | 退出码 0：「共 204 条用例，52.6 秒；0 个文件有红」「实际跳过 0 条用例」 |
| python.exe -B smoke_test.py --architecture（第一遍，23:13:05 起，跑到一半我停掉了） | 没跑完。已经出现 1 条红：`test_complexity_ratchet.ComplexityRatchet.test_class_size_does_not_grow`（`SharedStageInput` 615 行，上限 600）。据此把登记表的方法挪进混入类，没有改棘轮的登记值 |
| python.exe -B scripts\dev.py scope desktop_shared_input.py desktop_shared_send.py ui/desktop_script_pages.py tests/test_desktop_shared_input.py tests/test_ui_batch5_stage_panel_and_script_page.py（23:14:14） | 退出码 0：「另 27 个工作树分支无重叠」 |
| 验收命令一（第二遍，同一条命令，23:10:35 至 23:16:57，其中约五分钟在等界面令牌） | 退出码 0：「共 204 条用例，379.6 秒；0 个文件有红」「实际跳过 0 条用例」（test_stage_flow 四段共 50 条、test_manual_plan 三段共 30 条、test_shared_input_ui 两段共 29 条、test_shared_input_stages 两段共 27 条、test_manual_gate 19 条、test_desktop_shared_input 15 条、test_skill_budget_send_entries 9 条、test_shared_input_voice 9 条、test_ui_batch5_stage_panel_and_script_page 6 条、test_stage_flow_summary 5 条、test_follow_buttons 3 条、test_desktop_writing_page 2 条）。这一遍开始时页面用例的辅助函数已改好（23:10:27）；等界面令牌期间（约 23:12:30 至 23:16:01）我做了「挪进混入类」的改写（`desktop_shared_input.py` 最后一次修改 23:15:39）。按日志里的先后推算：等令牌之前跑完的三组（test_stage_flow_summary、test_skill_budget_send_entries、test_manual_gate，共 33 条）用的是改写前的代码；其余 171 条（含新加用例所在的两个文件）在拿到令牌之后才跑，这时代码已经是最终的。提交工具会在最终代码上把这几组整个再跑一遍，以证据行为准 |
| 验收命令二：python.exe -B smoke_test.py --architecture（最终的代码和测试，23:15:59 至 23:20:57） | 退出码 0：「Ran 700 tests in 296.711s」「OK」「✅ 架构治理测试：tests/architecture」；另有一条既有的棘轮提示（LR-09、LR-10 实测 59 < 基线 60） |

第一遍验收命令一和停掉的那遍架构门禁不算数，写在这里只为了说明改动的经过。最后一遍架构门禁开始时本文件还没有建，跑到一半时建了初稿；它跑完以后只改了本文件，没有再动代码和测试。临时日志都放在系统临时目录，工作树里没有留下临时文件。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在真实界面上验证；未 push、未 merge。
- 阶段文档（docs/stages）没有改：任务书要求不改，实现合入后由需求机动窗口把那两条需求的状态改掉并补测试锚定。
- 其余五个没有对话流程的阶段（SEND-2）和发送按钮的状态（SEND-3）没有做，任务书写明暂不派。这五个阶段现在点发送仍是原来的行为。
- 「只撤某一处改动时哪几条红」没有逐处实测（见「改前红」末尾）。
- 项目续开、换项目这两条路径上的页面重建没有单独写用例：它们走的是同一个 `build`，用例覆盖的是「同一页重建」和「按钮销毁」。

## 提交

用 `scripts\dev.py commit` 提交，只提交上面列出的文件。提交号不写在本文件里，见会话接续记录里推进预备窗口那一节和队列心跳。
