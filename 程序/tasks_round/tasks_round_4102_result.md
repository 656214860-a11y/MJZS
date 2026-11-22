# R4102 结果：视频工作台兜底入口 App.safe() 补诊断记录（EC-2 补一笔）
<!-- round-evidence: {"commit_base": "a1be417d", "credential_hits": 0, "evidence_sha256": "a767f70ab04a566b", "exit": 0, "failed": 0, "passed": 15, "round": 4102, "tests": "run_selftests.py -k ui_error_text"} -->

## 开头三问

- 本轮属于哪种类型：修复轮（任务卡 EC-2 的补充提交，补 R4098 结果文件「未覆盖项」第一条；车道 `codex/ec-catch-all`，叠在 R4098 的提交 `a1be417d` 上，基线仍是 `f624a5fc`）。
- 测试跑了吗、三个基线：先红后绿。测试文件由 9 条变 15 条，产品代码改之前 2 条红，改后 15 条全过。默认冒烟通过 9 项、失败 0 项；架构门禁 `Ran 700 tests`、`OK`、失败集合为空；全量回归本轮没跑（用户验证期间不跑全量），全量欠账以 `full-safe-receipts.json` 为准，本轮没有改变它。定向测试逐条结果见「命令与退出码」。
- 欠账少了吗：少了一条。R4098 留下的缺口（`App.safe()` 接住的异常改后查不到原文）补上了：现在先写诊断记录再提示。没有新增欠账项；只读复核指出的另一条（`_async_failed()` 在生产里收到的是文字）不在这一笔范围，见「未覆盖项」第一条。

## 改前红

只改测试文件、`app.py` 还没改的时候，`PY -B -m unittest tests.test_ui_error_text -v`，退出码 1。下面是节选：`AppSafeTests` 五条的结果行、两条失败和结尾；路径里的车道目录写成 `...`。

```text
test_busy_notice_is_shown_unchanged_and_the_action_does_not_run (tests.test_ui_error_text.AppSafeTests.test_busy_notice_is_shown_unchanged_and_the_action_does_not_run) ... ok
test_chinese_message_is_shown_unchanged (tests.test_ui_error_text.AppSafeTests.test_chinese_message_is_shown_unchanged) ... ok
test_failing_record_does_not_block_the_prompt (tests.test_ui_error_text.AppSafeTests.test_failing_record_does_not_block_the_prompt) ... ok
test_record_happens_before_the_prompt (tests.test_ui_error_text.AppSafeTests.test_record_happens_before_the_prompt) ... FAIL
test_unclassified_error_shows_the_code_and_records_the_original (tests.test_ui_error_text.AppSafeTests.test_unclassified_error_shows_the_code_and_records_the_original) ... FAIL

FAIL: test_record_happens_before_the_prompt (tests.test_ui_error_text.AppSafeTests.test_record_happens_before_the_prompt)
  File "...\程序\tests\test_ui_error_text.py", line 130, in test_record_happens_before_the_prompt
    self.assertEqual(order, ['record', 'prompt'])
AssertionError: Lists differ: ['prompt'] != ['record', 'prompt']

FAIL: test_unclassified_error_shows_the_code_and_records_the_original (tests.test_ui_error_text.AppSafeTests.test_unclassified_error_shows_the_code_and_records_the_original)
  File "...\程序\tests\test_ui_error_text.py", line 120, in test_unclassified_error_shows_the_code_and_records_the_original
    record.assert_called_once()
AssertionError: Expected 'record_degradation' to have been called once. Called 0 times.

Ran 15 tests in 0.016s

FAILED (failures=2)
```

改前就过的 13 条里，这一笔新加的有 5 条：`AppSafeTests` 的三条（记录出错不挡提示、中文提示原样、忙碌提示原样且不执行操作）守的是加了记录以后这些行为不变；`GoTests` 的两条（先记录再提示、会员账户页按页名记录）钉的是 R4098 已经做对、但当时没有断言的行为。光看改前红证明不了这 5 条咬得住，所以另做了反向验证，见「如实说明」第一条。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `app.py` | 只改 `App.safe()`（580–591 行，8 增 1 删）：接住异常后先调 `diagnostic_capture.record_degradation(e, page='视频生成', stage='app.safe', project=<当前项目目录>)`，再提示；记录自己出错走 `app_logging.swallowed()`，不影响提示。提示那一句的文字来源（`user_text(e)`）和标题「提示」都没变，只是从 `except` 那一行挪到了单独一行。接住哪些异常没有变。文件 1487 行变 1494 行，`App` 类 1374 行变 1381 行。 |
| `tests/test_ui_error_text.py` | 9 条变 15 条（69 增 4 删）：`AppSafeTests` 1 条变 5 条，`GoTests` 2 条变 4 条，`DesktopSafeTests`、`AsyncFailedTests` 各 3 条没动。新增两个小帮手：`_order_of`（给记录和提示各留一个记号，用来断言先后）、`_app_host`。仍然全部用假对象直接调未绑定的方法，不建窗口。 |
| `tasks_round/tasks_round_4102_result.md` | 本文件。 |

没有动登记表、基线和治理文件：测试文件 R4098 已登记过，这一笔没有新增测试文件。提交工具另会写一个证据文件 `tasks_round/evidence/R4102.json`。

## 测试与卡面的对应

卡面没有对应这一笔的条目（来由见下一节），左列写的是依据。

| 依据 | 用例 |
|---|---|
| 原始异常要写进现有的诊断记录 | `AppSafeTests.test_unclassified_error_shows_the_code_and_records_the_original`（改前红）：记录被调用一次，收到的就是原来那个异常对象，另三个参数是 `page='视频生成'`、`stage='app.safe'`、`project=<项目目录>`；提示仍是 `[E-UNKNOWN]` 那一句、标题「提示」 |
| 先记录再提示 | `AppSafeTests.test_record_happens_before_the_prompt`（改前红） |
| 记录自己出错不影响提示 | `AppSafeTests.test_failing_record_does_not_block_the_prompt` |
| 加了记录以后界面文字不变 | `AppSafeTests.test_chinese_message_is_shown_unchanged`、`AppSafeTests.test_busy_notice_is_shown_unchanged_and_the_action_does_not_run` |
| 只读复核指出 `go()` 的先后顺序和三个参数没有断言 | `GoTests.test_record_happens_before_the_prompt`、`GoTests.test_account_page_is_recorded_by_its_title`（停在会员账户页：`page` 是页名「00  会员账户」，`project`、`automatic_daily_open` 照传） |

## 与任务书不同的地方

- 这一笔本身在卡面之外：EC-2 的卡面对 `App.safe()` 只许换文字来源（禁止事项：「只换文字来源，外加 go() 的记录」）。R4098 照卡面做了，把由此留下的缺口写在「未覆盖项」第一条。之后的经过：需求机动窗口 22:16 在心跳里答复先补再合，要求原始异常写进现有的日志或诊断记录、不新造机制、在同一车道加一笔，并说明验收窗口有不同意见以验收为准；推进预备窗口 22:22 的只读复核（全文在主工作区 `.agent-tmp/128132c3-review-EC-2.md`）也确认这个缺口，建议合入前在同一车道补一个小提交。本窗口 22:24 在心跳里预告了这一笔；到写本文件时（22:38）验收窗口还没有新的心跳（最后一条 22:12），没有看到不同意见。
- 验收窗口如果不同意这一笔：两个提交是分开的，可以只合 `a1be417d`。
- 改的两个文件都是 R4098 已经动过的（`app.py`、`tests/test_ui_error_text.py`），没有碰别的产品文件。
- 卡面验收命令之外多跑的：一组经过 `App` 的现有测试（「命令与退出码」最后一行）、只在内存里的反向验证、一次接真实记录函数的探针。

## 如实说明

- 反向验证（只在内存里，不写仓库文件）：用一个临时脚本把 `PageNavMixin.go`、`App.safe` 的源码取出来，各做几种改坏，在内存里换上改坏的函数再跑这 15 条。结果：不改坏时 15 条全过；`go()` 改成先提示再记录，`GoTests.test_record_happens_before_the_prompt` 红；`go()` 的页名改回按序号去 `PAGES` 里取，`GoTests.test_account_page_is_recorded_by_its_title` 红；`App.safe()` 的记录去掉保护，`AppSafeTests.test_failing_record_does_not_block_the_prompt` 红；`App.safe()` 改成先提示再记录，`AppSafeTests.test_record_happens_before_the_prompt` 红；`App.safe()` 不记录，两条红。脚本在系统临时目录，没有入库。两条「文字原样」用例（中文提示、忙碌提示）没有做对应的改坏，它们守的是 R4098 已有的行为。
- 接真实记录函数走了一遍（临时探针；记录文件改指到系统临时目录里的一个文件，不写程序自己的诊断记录）：对假宿主调 `App.safe()` 两次，一次操作抛 `AttributeError`，一次处在忙碌状态。记录文件里得到两行：`exception` 分别是 `AttributeError`、`ValueError`，`message` 是各自的原话，`page` 是「视频生成」，`stage` 是 `app.safe`，`project` 是传进去的项目目录；两次提示分别是 `[E-UNKNOWN]` 那一句和「正在执行操作，请稍后」。没有在真实界面上触发过。
- 记录的范围比「认不出的错误」宽：`App.safe()` 接住的每一个异常都记，包括忙碌提示和操作里主动抛出的中文提示。这和 `Desktop.safe()` 现有的做法一样（它也是不分种类先记录再提示）。代价：诊断记录只留最近 50 条，这类提示多了会把更早的记录挤出去。要不要只记认不出的那一类，是两个入口共同的取舍，这一笔没有改，写在「未覆盖项」。
- `page`、`stage` 的写法照同一个类里已有的 `_record_result_render_failure`（`page='视频生成'`、`stage='app.tick.'` 加阶段名）；`project` 传的是 `self.root`（当前项目目录）。记录里 `message`、`project` 的脱敏由记录函数自己做，这一笔没有另加。
- 原有用例 `AppSafeTests.test_unclassified_error_shows_the_code` 改名为 `test_unclassified_error_shows_the_code_and_records_the_original`：原来的两句断言原样保留，后面加了记录的断言。改它的另一个原因：它原来没有把记录函数换成假的，产品代码改后直接跑会去写真实的诊断记录；现在这个文件里会走到记录的用例都换成了假对象。没有删除或放松任何断言。
- 行数和登记：`app.py` 1494 行，登记上限 1499；`App` 类 1381 行，登记上限 1388。两处登记都没有动。这一笔用掉 7 行，合入后 `app.py` 只剩 5 行余量、`App` 类剩 7 行：别的车道如果也给 `app.py` 加行，后合的一方会碰到上限，请验收窗口留意。为了少占行，记录调用折成两行，两个引入写在函数里（和这个文件现有写法一致）。
- `App.safe()` 包着 `app.py` 里 11 处同步操作（改后行号 193、290、294、334、375、775、776、1017、1021、1025、1489），这一笔没有逐处触发，只在入口上测。
- 架构门禁输出里仍有两行「[棘轮提示] LR-09、LR-10 实测 59 < 基线 60」，R4098 的结果文件记过，不是本轮带来的；本轮没有动 `层间合规清单.json`。
- 最后一组界面测试的日志里有 30 行 Tk 的 `invalid command name`（测试窗口销毁后，先前排好的定时回调 `start_account_renewal`、`start_update_check`、`deliver` 找不到命令），用例结果不受影响。核对过不是这一笔带来的：在停在主干 `f624a5fc`、没有改动的另一个车道里跑其中四个文件，同样的行有 35 行（三种回调都在）。这是主干现有的现象，这一笔没有处理。
- 多跑了一个不相干的测试：22:26 那条架构测试命令里顺手带上了 `tests.architecture.test_text_component_boundary`（本来是给下一张卡准备的），结果是过的，和这一笔无关。
- 验收窗口 21:56 通报的主干 5 条过期界面测试（`-k idea_chat` 4 条、`-k ui_edges_pages` 1 条）本轮的命令都没有选到。
- 需求机动窗口 22:33 更正过：提交工具不跑整套架构门禁。R4098 和这一笔的架构门禁都是单独跑的，结果在各自的「命令与退出码」里。
- 测试进程都降到 BelowNormal 优先级；没有新建工作目录。

## 命令与退出码

工作目录都是车道的 `程序`，`PY` 指 `..\..\..\..\运行环境\Python\python.exe`；时间是 2026-11-22 本机时钟。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `PY -B scripts\dev.py claim`（22:26） | 0 | 领到轮次 4102 |
| `PY -B -m unittest tests.test_ui_error_text -v`（22:26，`app.py` 改之前） | 1 | `Ran 15 tests`，2 红 |
| `PY -B -m unittest tests.test_ui_error_text -v`（22:26，改后） | 0 | `Ran 15 tests`，`OK` |
| `PY -B -m unittest tests.architecture.test_complexity_ratchet tests.architecture.test_module_size_ratchet tests.architecture.test_notification_boundary tests.architecture.test_text_component_boundary`（22:26–22:27） | 0 | `Ran 16 tests`，`OK` |
| `PY -B governance\check_structure.py --check --summary`（22:27） | 0 | `findings` 为空，`finding_count` 1（改前就有的那一条） |
| `PY -B -m unittest tests.architecture.test_silent_exception_ratchet tests.architecture.test_log_sink_boundary -v`（22:27） | 0 | `Ran 10 tests`，`OK` |
| `PY -B smoke_test.py --architecture`（22:27–22:33） | 0 | `Ran 700 tests in 336.585s`，`OK`，失败集合为空 |
| 反向验证脚本（22:28，临时脚本，只在内存里改） | 0 | 五种改坏都有对应用例变红，不改坏时 15 条全过 |
| `PY -B smoke_test.py`（22:33） | 0 | 通过 9 项，失败 0 项 |
| `PY -B run_selftests.py -k ui_error_text video_ui video_result_polling video_revision cell_menu row_targets ui_edges_tables`（22:33–22:34，卡面之外加跑） | 0 | 8 个文件 190 条全绿，实际跳过 0 条：`test_ui_error_text` 15、`test_video_ui` 66、`test_cell_menu` 40、`test_ui_edges_tables` 21、`test_row_targets` 15、`test_video_revision` 15、`test_video_result_polling` 14、`test_ui_batch8_video_ui_tokens` 4（最后一个是关键字 `video_ui` 顺带选中的） |
| 接真实记录函数的探针（22:34，临时脚本） | 0 | 记录文件得到 2 行，内容见「如实说明」第二条 |
| `PY -B run_selftests.py -k ui_edges_tables video_ui row_targets cell_menu`（22:35–22:37，对照用：在停在主干 `f624a5fc`、没有改动的另一个车道里跑） | 0 | 146 条全绿，实际跳过 0 条；日志里 `invalid command name` 35 行；152.3 秒里约 91 秒在等别的窗口占着的界面令牌 |

## 未覆盖项

- `_async_failed()` 在生产里收到的是文字不是异常（`ui/desktop_async_tasks.py` 入队前就转成了文字），带中文的系统报错（例如带中文路径的文件错误）仍会原样显示。这是推进预备窗口只读复核的第二处，它的建议是并进 EC-3、不拦合入；这一笔没有动，请验收窗口和需求机动窗口定。
- 忙碌提示和中文校验提示也进诊断记录（`Desktop.safe()`、`App.safe()` 都是），要不要只记认不出的那一类没有定，这一笔按现有做法。
- 未跑全量自测：用户 2026-11-22 19:52 决定验证期间不跑全量、只跑定向测试和架构门禁。
- 没有在真实桌面或隐藏桌面上做界面目检：这一笔不改界面上的文字和标题。
- 未 push、未 merge、未改主工作区；复核、验收、合入归验收窗口。

## 提交

本文件随 R4102 的提交一起入库（分支 `codex/ec-catch-all`，叠在 `a1be417d` 上）。写本文件时提交号还没有产生，提交号见 `git log` 和会话接续记录里编码预备窗口一节。
