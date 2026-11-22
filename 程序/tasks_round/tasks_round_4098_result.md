# R4098 结果：界面四个兜底入口的报错文字统一经 user_text，翻页兜底补诊断记录
<!-- round-evidence: {"commit_base": "f624a5fc", "credential_hits": 0, "evidence_sha256": "5271bf1ef805bfba", "exit": 0, "failed": 0, "passed": 9, "round": 4098, "tests": "run_selftests.py -k ui_error_text"} -->

## 开头三问

- 本轮属于哪种类型：修复轮（任务卡 EC-2，对应 EC-B1、EC-B2、EC-B3；《错误代码统一任务书》4.2 节；车道 `codex/ec-catch-all`，基线 `f624a5fc`）。
- 测试跑了吗、三个基线：先红后绿，新测试 9 条，改前 7 条红，改后全过。默认冒烟通过 9 项、失败 0 项；架构门禁 `Ran 700 tests`、`OK`、失败集合为空；全量回归本轮没跑（用户验证期间不跑全量），全量欠账以 `full-safe-receipts.json` 为准，本轮没有改变它。定向测试逐条结果见「命令与退出码」。
- 欠账少了吗：少了。四个兜底入口不再把程序原文显示给用户（EC-B2 里归本卡的部分）；认不出的错误显示带代码的 `[E-UNKNOWN]` 一句，带代码的基础层异常显示码表说明（EC-B1 里归本卡的部分）；`go()` 接住的异常现在进诊断记录（EC-B3）。其余 27 处调用点和守卫归 EC-3，本轮没有动。没有新增欠账项；有一处改后原文查不到的入口（`App.safe()`），卡面不许本轮补，写在「未覆盖项」第一条，请验收窗口先看。

## 改前红

只放进新测试文件和它的登记、四处产品代码还没改的时候，`PY -B -m unittest tests.test_ui_error_text -v`，退出码 1。下面是节选：九条用例的结果行、三条有代表性的失败和结尾；每条失败里 `unittest.mock` 库内部的几层调用栈省略了，路径里的车道目录写成 `...`。

```text
test_unclassified_error_shows_the_code (tests.test_ui_error_text.AppSafeTests.test_unclassified_error_shows_the_code) ... FAIL
test_chinese_text_is_shown_unchanged (tests.test_ui_error_text.AsyncFailedTests.test_chinese_text_is_shown_unchanged) ... ok
test_exception_object_shows_the_code (tests.test_ui_error_text.AsyncFailedTests.test_exception_object_shows_the_code) ... FAIL
test_raw_text_shows_the_code (tests.test_ui_error_text.AsyncFailedTests.test_raw_text_shows_the_code) ... FAIL
test_chinese_message_is_shown_unchanged (tests.test_ui_error_text.DesktopSafeTests.test_chinese_message_is_shown_unchanged) ... ok
test_coded_infra_error_shows_the_code_description (tests.test_ui_error_text.DesktopSafeTests.test_coded_infra_error_shows_the_code_description) ... FAIL
test_unclassified_error_shows_the_code_and_records_the_original (tests.test_ui_error_text.DesktopSafeTests.test_unclassified_error_shows_the_code_and_records_the_original) ... FAIL
test_failing_record_does_not_block_the_prompt (tests.test_ui_error_text.GoTests.test_failing_record_does_not_block_the_prompt) ... FAIL
test_page_failure_shows_the_code_keeps_the_title_and_records_the_original (tests.test_ui_error_text.GoTests.test_page_failure_shows_the_code_keeps_the_title_and_records_the_original) ... FAIL

FAIL: test_unclassified_error_shows_the_code_and_records_the_original (tests.test_ui_error_text.DesktopSafeTests.test_unclassified_error_shows_the_code_and_records_the_original)
  File "...\tests\test_ui_error_text.py", line 40, in test_unclassified_error_shows_the_code_and_records_the_original
    host.notifier.error.assert_called_once_with(UNKNOWN)
AssertionError: expected call not found.
Expected: error('[E-UNKNOWN] 发生了未分类的错误（建议：查看日志中的详细信息后重试）')
  Actual: error("'NoneType' object has no attribute 'state'")

FAIL: test_coded_infra_error_shows_the_code_description (tests.test_ui_error_text.DesktopSafeTests.test_coded_infra_error_shows_the_code_description)
  File "...\tests\test_ui_error_text.py", line 55, in test_coded_infra_error_shows_the_code_description
    host.notifier.error.assert_called_once_with(error_codes.describe('E-IO-READ'))
AssertionError: expected call not found.
Expected: error('[E-IO-READ] 读取文件失败（建议：检查文件是否被占用、权限或路径）')
  Actual: error('')

FAIL: test_page_failure_shows_the_code_keeps_the_title_and_records_the_original (tests.test_ui_error_text.GoTests.test_page_failure_shows_the_code_keeps_the_title_and_records_the_original)
  File "...\tests\test_ui_error_text.py", line 69, in test_page_failure_shows_the_code_keeps_the_title_and_records_the_original
    host.notifier.error.assert_called_once_with(UNKNOWN, title='页面无法显示')
AssertionError: expected call not found.
Expected: error('[E-UNKNOWN] 发生了未分类的错误（建议：查看日志中的详细信息后重试）', title='页面无法显示')
  Actual: error("'NoneType' object has no attribute 'state'", title='页面无法显示')

Ran 9 tests in 0.019s

FAILED (failures=7)
```

另外 4 条红（`App.safe()` 一条、`_async_failed()` 两条、`go()` 记录出错那一条）的报错是同一种：期望 `[E-UNKNOWN]` 那一句，实际是程序原文。改前就过的 2 条是「中文提示原样显示」，它们守的是改后不把中文句子也换掉。

## 改了哪些文件

| 文件 | 改动 |
|---|---|
| `desktop.py` | 只改 `Desktop.safe()` 里 `notifier.error` 那一行（567 行，1 增 1 删）：文字来源由 `str(e)` 换成 `error_codes.user_text(e)`。记录那几行没动，`notifier.error` 仍只有一处，文件行数没变（977 行），`Desktop` 类的行数也就没变。 |
| `app.py` | 只改 `App.safe()` 里 `notifier.error` 那一行（584 行，1 增 1 删），标题「提示」不变。 |
| `ui/desktop_async_tasks.py` | 只改 `_async_failed()` 最后一行（104 行，1 增 1 删），标题「操作未完成」不变。收到的是异常或文字都交给 `user_text`。 |
| `ui/desktop_page_nav.py` | 只改 `go()`（89–99 行，10 增 1 删）：接住异常后先用 `diagnostic_capture.record_degradation` 记录，再提示；记录自己出错走 `app_logging.swallowed()`，不影响提示；文字换成 `user_text(exc)`，标题「页面无法显示」不变。接住哪些异常没有变。 |
| `tests/test_ui_error_text.py` | 新增，9 条用例，全部用假对象直接调未绑定的方法，不建窗口。 |
| `governance/structure.json` | `test_ownership` 里给新测试文件加一条登记（11 增 0 删），别的内容没动。 |
| `governance/structure-baseline.json` | 用 `governance\check_structure.py --write-baseline --summary` 重新生成，只变头部三行（`source_commit`、`inventory_sha256`、`policy_sha256`，3 增 3 删），`violations` 没有变。 |
| `tasks_round/tasks_round_4098_result.md` | 本文件。 |

四处的引入都写在函数里（`import contract.error_codes as error_codes`，和调用写在同一行）：这样 `desktop.py`、`app.py` 的行数不增加，四处写法一致。引入方向都是上层引下层。

## 测试与卡面的对应

| 卡面 | 用例 |
|---|---|
| T1 | `DesktopSafeTests.test_unclassified_error_shows_the_code_and_records_the_original`（改前红） |
| T2 | `DesktopSafeTests.test_chinese_message_is_shown_unchanged` |
| T3 | `DesktopSafeTests.test_coded_infra_error_shows_the_code_description`（改前红） |
| T4 | `GoTests.test_page_failure_shows_the_code_keeps_the_title_and_records_the_original`（改前红）；另加 `GoTests.test_failing_record_does_not_block_the_prompt`，对应接口契约「记录本身出错不得影响提示」 |
| T5 | `AppSafeTests.test_unclassified_error_shows_the_code`；`AsyncFailedTests` 三条（收到文字、收到异常、收到中文文字） |

## 与任务书不同的地方

- `go()` 记录时的 `page=` 参数写的是 `page_title(getattr(self,'page_index',0))`，没有照 `Desktop.safe()` 写 `PAGES[...]`。理由：这个模块已经引入 `page_title`，没有引入 `PAGES`；`PAGES[...]` 停在会员账户页时会越界（页序号等于 `len(PAGES)`），那样这一页翻页失败的记录会被自己的 `IndexError` 吞掉。另两个参数和 `safe()` 逐字相同。
- T5 写的是「断言同 T1」，T1 里有一句「`record_degradation` 被调用一次且收到原始异常」。`App.safe()` 和 `_async_failed()` 这两处，卡面只许换文字来源（禁止事项：「只换文字来源，外加 go() 的记录」），所以这几条用例只断言提示的文字和标题，没有断言记录。由此留下的缺口见「未覆盖项」第一条。
- 卡面的允许清单没有列两个治理文件。依据是任务书 4.0 第 11 条（新增测试文件要在 `governance/structure.json` 登记）和队列项 EC-2 的允许修改文件（列了 `governance/structure.json`、`governance/structure-baseline.json`）。登记变了以后 `check_structure.py --check` 报 `Directory policy changed without explicit baseline review`，所以基线要用工具重新生成。
- 提交命令的文件列表比卡面多这两个治理文件；`--agent` 写实际执行方。
- 验收命令之外多跑了两条：`run_selftests.py -k ui_error_text`（提交工具点名要跑的那一组，先跑一遍）和一组现有测试（「命令与退出码」最后一行），后者经过这四个入口或断言了它们的提示文字。

## 如实说明

- 改动的来历：四处改动、测试文件和登记条目是调度窗口 2026-11-22 19:43 至 20:05 预验证时写好的（基于当时的主干 `7ea1ddeb`，在仓库外的副本上，材料在系统临时目录 `cpa-fast-1122b\ec2\`）。本窗口逐行读过改动和测试、对照卡面核对后，用它的落地脚本原样写入（每个锚点恰好命中一次），没有改写法；下面的命令都是本窗口在新主干 `f624a5fc` 上重新跑的。
- 中文提示「原样」有一点出入：`user_text` 的规则是含中文的句子原样返回，但换行和连续空白会并成一个空格（EC-1 已合入的规则 R3）。经这四个入口弹出的中文提示如果原来分成几行，改后会变成一行。本轮没有逐个查哪些提示是多行的；现有测试里没有因此变红的。
- 英文说明不再显示：改后 `_async_failed()` 收到不带中文、也认不出类型的文字（例如外部接口返回的英文报错），用户看到的是 `[E-UNKNOWN]` 那一句。这是任务书第 6 节已经评估过的风险。原文的去处：`_async_failed()` 只有一个调用方 `_tick_async_result()`（同文件 128 行），它在调用之前已经把原文交给 `background_tasks.finish(..., error=str(value))`，这一段本轮没有动；那边把它存到哪里、存多久，本轮没有查。
- 范围扫描报了 1 处重叠：分支 `polished-edison` 也改过 `desktop.py`。查过，它是另一个编辑器 2026-11-18 留下的快照分支，落后主干 736 个提交、领先 4 个，改 `desktop.py` 的是 R2962 的 3 行，不是在途车道。另外 26 个工作树分支没有重叠。
- 结构基线：`--write-baseline --summary` 的输出里 `delta` 的 `added`、`removed` 都是空，`finding_count` 是 1（改前就有的那一条）；重新生成后 `--check --summary` 退出码 0。工具在本机写出的文件是 CRLF 行尾，这个文件的属性是 `eol=lf`，提交时 git 按属性转回 LF，没有手改这个文件。别的车道如果也重新生成过基线，改的是同三行，后合的一方要再生成一次。
- 主干既有缺陷，不在本卡范围，没有改：停在会员账户页时 `Desktop.safe()` 里记诊断那句的 `PAGES[...]` 越界，`safe()` 自己抛 `IndexError`，提示弹不出。调度窗口 20:07 已经把它转给需求机动窗口登记，排在本车道合入之后。本轮没有碰 `Desktop.safe()` 里记录的那几行。
- 架构门禁输出里有两行「[棘轮提示] LR-09、LR-10 实测 59 < 基线 60」，R4088 的结果文件也记过，不是本轮带来的；本轮没有动 `层间合规清单.json`。
- 验收窗口 21:56 通报的主干 5 条过期界面测试（`-k idea_chat` 4 条、`-k ui_edges_pages` 1 条）本轮的命令都没有选到：`--affected desktop_page_nav` 选中的是 `test_desktop_page_nav`、`test_shared_input_stages` 两个文件。
- 没有新建工作目录：复用闲置目录 `.agents/worktrees/ec-1-contract`（原分支 `codex/ec-1-contract` 已合入主干、工作树干净），在里面从主干切出 `codex/ec-catch-all`。测试进程都降到 BelowNormal 优先级。

## 命令与退出码

工作目录都是车道的 `程序`，`PY` 指 `..\..\..\..\运行环境\Python\python.exe`；时间是 2026-11-22 本机时钟。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `PY -B -c "from contract import error_codes as e; print(e.user_text(ValueError('boom')))"`（21:52，前置检查） | 0 | 输出以 `[E-UNKNOWN]` 开头 |
| `PY -B scripts\dev.py scope <七个路径>`（21:52） | 0 | 1 处重叠（见「如实说明」），另 26 个分支无重叠 |
| `PY -B scripts\dev.py claim`（21:52） | 0 | 领到轮次 4098 |
| `PY -B -m unittest tests.test_ui_error_text -v`（21:53，产品代码改之前） | 1 | 9 条中 7 红 |
| `PY -B -m unittest tests.test_ui_error_text -v`（21:54，改后） | 0 | `Ran 9 tests`，`OK` |
| `PY -B governance\check_structure.py --check`（21:54，基线重新生成之前） | 2 | `Directory policy changed without explicit baseline review` |
| `PY -B governance\check_structure.py --write-baseline --summary`（21:54） | 0 | `delta` 为空，`finding_count` 1 |
| `PY -B governance\check_structure.py --check --summary`（21:54） | 0 | `ok` 为真 |
| `PY -B -m unittest tests.architecture.test_notification_boundary tests.architecture.test_complexity_ratchet tests.architecture.test_silent_exception_ratchet tests.architecture.test_log_sink_boundary -v`（21:55） | 0 | `Ran 20 tests`，`OK` |
| `PY -B smoke_test.py --architecture`（21:55–22:00） | 0 | `Ran 700 tests in 324.874s`，`OK`，失败集合为空 |
| `PY -B run_selftests.py -k ui_error_text`（22:00–22:08，卡面之外加跑） | 0 | 1 个文件 9 条全绿，实际跳过 0 条；476.7 秒里约 476 秒在等别的窗口占着的界面令牌 |
| `PY -B smoke_test.py --affected desktop_page_nav`（22:08–22:09） | 0 | 选中 2 个测试文件（`test_desktop_page_nav`、`test_shared_input_stages`），29 条全绿，实际跳过 0 条；冒烟汇总「通过：10 项，失败：0 项」 |
| `PY -B smoke_test.py`（22:09） | 0 | 通过 9 项，失败 0 项 |
| `PY -B run_selftests.py -k desktop_async_tasks desktop_automation_service video_result_polling desktop_media_pages`（22:09–22:10，卡面之外加跑） | 0 | 4 个文件 36 条全绿，实际跳过 0 条；其中 `test_desktop_async_tasks`、`test_video_result_polling` 断言 `_async_failed()` 的中文提示原样，`test_desktop_media_pages` 经 `go()` 逐页打开 15 个页面 |

## 未覆盖项

- 请验收窗口先看这一条：`App.safe()` 改后原始异常查不到。`App` 是视频页里嵌的视频工作台（`ui/desktop_media_pages.py` 689 行创建），它的 `safe()` 接住异常后只弹提示，不写日志也不写诊断记录；`user_text` 是纯函数，也不记。改前认不出的错误至少把程序原文显示出来；改后显示 `[E-UNKNOWN]` 那一句（句子里建议「查看日志中的详细信息」），而日志里没有这条错误。卡面只许换这一行的文字来源、禁止加别的动作，任务书第 6 节的缓解措施「原文必须进记录」也只点了 T1、T4（`Desktop.safe()`、`go()`），所以本轮照卡面做、没有给 `App.safe()` 加记录。要不要补（另开一张卡，或并进 EC-3）、补之前这一轮能不能先合，请验收窗口和需求机动窗口定。
- 未跑全量自测：用户 2026-11-22 19:52 决定验证期间不跑全量、只跑定向测试和架构门禁。
- 没有在真实桌面或隐藏桌面上做界面目检。任务书第 5 节的「主控合入前复测」（空项目点「12 后期剪辑」看状态栏文字）前提是 L4-U6 还没合入；现在 L4-U6 已在主干，那一页能正常打开，这条复测要不要换一种触发办法由验收窗口定。
- 四个入口里的多行中文提示改后并成一行（见「如实说明」第二条），没有逐个查。
- 未 push、未 merge、未改主工作区；复核、验收、合入归验收窗口。

## 提交

本文件随 R4098 的提交一起入库（分支 `codex/ec-catch-all`）。写本文件时提交号还没有产生，提交号见 `git log` 和会话接续记录里编码预备窗口一节。
