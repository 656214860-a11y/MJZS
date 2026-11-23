# R4112 结果：剧本结构页上下两个文本框和底部输入框左右对齐（去掉内容框左右各 4 像素的内边距）
<!-- round-evidence: {"commit_base": "24be2ed3", "credential_hits": 0, "evidence_sha256": "c7ef5143e8c87e1e", "exit": 0, "failed": 0, "passed": 68, "round": 4112, "tests": "run_selftests.py -k desktop_script_pages script_structure script_page_layout ui_batch5_stage_panel_and_script_page"} -->

## 开头三问

- （一）本轮属于哪种类型：缺陷修复轮。任务卡 W4-UX-S02-ALIGN（队列项 UX-S02-ALIGN），车道 codex/ux-s02-input-align，基准 24be2ed3。来源：用户 2026-11-22 22:45 报剧本结构页的文本框和下面的输入框没有对齐（来源 562cdbb1）。现象：剧本结构页上、下两个内容框（标题行和文本框）比底部共享输入框的外框左边缩进 4 像素、右边也缩进 4 像素。根因：`ui/desktop_script_pages.py` 的 `_ContentBox.build` 给内容框外层加了左右各 `SPACING["xs"]`（4 像素）的内边距，共享输入框没有这一层。复现：新用例在改之前红，三档窗口、文件面板开和关两种状态下，四块的左缘都是 +4、右缘都是 −4（见「命令与结果」）。
- （二）测试跑了吗、三个基线：新增 1 个测试文件 2 条用例，没有修改或删除现有用例的断言。先红：撤掉产品文件的改动后 2 条都红。改后：和剧本页、文件面板、页面缓存有关的 13 个关键词一起跑，329 条里 1 条红，是文件面板的一条已知不稳的用例，单独跑它所在的文件 150 条全过（见「如实说明」第（四）条）。架构门禁在全部改动之后整套跑过，700 条全过。结构检查退出码 0。默认冒烟没有单独跑；全量自测没跑。提交时的点名测试由提交工具跑，以本文件的证据行为准。
- （三）欠账少了吗：少了一处界面缺陷，多了一条守着它的用例。没有新增欠账，没有动任何门禁的阈值、基线和登记表。看到但没有在本轮处理的两点写在「如实说明」第（二）（六）条。

## 改了哪些文件

- ui/desktop_script_pages.py：`_ContentBox.build` 里建内容框外层的那一行，去掉 `padding=(SPACING["xs"], SPACING["none"])`；上面那行注释补一句为什么左右不留内边距。2 行新增、2 行删除。文件里别处还在用 `SPACING`，导入不变。
- tests/test_desktop_script_pages.py：新文件，120 行。一个测试类两条用例（文件面板关、文件面板开），每条在 1280x800、1024x680、880x600 三档窗口下，量「自然剧本文本框」「自然剧本标题行」「结构剧本文本框」「结构剧本标题行」四块的左右边缘，要求和共享输入框外框 `input_ring` 的左右边缘差为 0；失败时逐块报差几像素。口径和 tests/test_desktop_writing_page.py 的 T1（剧本准备页的同类用例）一致。文件名和生产模块同名，是结构检查对新测试文件的要求（第一版叫别的名字，没有提交过）。
- tasks_round/tasks_round_4112_result.md 是本文件。

## 命令与结果

下表的命令都在车道的 程序 目录下、进程优先级降到 BelowNormal 跑。界面测试整轮在隐藏桌面里跑。日志放在系统临时目录，没有放进 程序 目录。

| 命令 | 结果 |
| --- | --- |
| 在一个已合入、工作树干净的闲置车道目录里从主干切分支 codex/ux-s02-input-align（当时主干是 67068467），23:21 `git merge --ff-only master` 快进到 24be2ed3 | 没有新建工作树目录；快进没有产生提交；主干这一步只改了两个测试文件和结果文件，和本轮的文件没有重叠 |
| 改产品之前，第一版用例单独跑（基准 67068467，23:07 至 23:08） | 2 条都红：三档窗口、文件面板关和开，四块都是左缘差 +4、右缘差 −4 |
| 改产品之后第一遍回归，python.exe -B run_selftests.py -k 加 13 个关键词（第一版用例，基准 67068467，23:08:52 至 23:16） | 退出码 1，「共 329 条用例，452.0 秒；3 个文件有红」。三处：① `test_files_panel_stages` 的 `IndexLifecycleTests.test_refresh_discovers_external_file_and_retains_script_actions`（见「如实说明」第（四）条）；② `test_ui_edges_pages` 的 `UiEdgePagesTests.test_the_writing_page_wraps_the_box_with_buttons`，「Tuples differ: ('headings',) != ('tree', 'headings')」，是旧主干上的过期断言，已由 R4101 改好并随 24be2ed3 进了主干，快进后不再出现；③ 本轮第一版用例有 4 个子用例报「窗口改尺寸后 5 秒内页面没有排稳」，是等待上限定得太短，不是没对齐（见第（三）条） |
| 第一版用例单独跑（改产品之后，23:17 至 23:20） | 「共 2 条用例」「0 个文件有红」「ALL TESTS PASSED」，2 条用时 7.3 秒 |
| 定稿用例（改了文件名、首帧回调换成空动作、等待上限改成 30 秒）之后：python.exe -B governance\check_structure.py --check --summary（23:21） | 退出码 0 |
| 定稿用例见红：把产品文件的改动暂时收起来，python.exe -B run_selftests.py -k desktop_script_pages（基准 24be2ed3，23:21:37 至 23:21:48），跑完恢复改动并用 git status 核对 | 退出码 1，「共 2 条用例，8.1 秒；1 个文件有红」，报的是四块各自的「左缘差 +4」「右缘差 -4」 |
| python.exe -B run_selftests.py -k desktop_script_pages script_structure script_page_layout script_autosave script_zoom ui_reading_density ui_batch5_stage_panel_and_script_page desktop_writing_page page_cache files_panel_stages stage_wiring ui_edges_pages ui_edges_tables（全部改动之后，基准 24be2ed3，23:21:48 至 23:27:41） | 退出码 1，「定向：忽略增量台账，执行 19 个匹配测试文件」「共 329 条用例，350.5 秒；1 个文件有红」「实际跳过 0 条用例」。红的只有 `test_files_panel_stages` 那一条：「AssertionError: '05资产管理/assets/外部新增.md' not found in []」。本轮的 `test_desktop_script_pages` 2 条通过，在 8 路并行下用时 78.4 秒 |
| python.exe -B smoke_test.py --architecture（全部改动之后，基准 24be2ed3，23:27:41 至 23:32:38） | 退出码 0，「Ran 700 tests in 290.657s」「OK」「✅ 架构治理测试：tests/architecture」 |
| python.exe -B run_selftests.py -k files_panel_stages（单独跑那一个文件，全部改动之后，23:32:52 至 23:36:10） | 退出码 0，「定向：忽略增量台账，执行 1 个匹配测试文件」「共 150 条用例，195.8 秒；0 个文件有红」「ALL TESTS PASSED」 |
| python.exe -B scripts\dev.py claim | 领到轮次 4112 |
| git diff --numstat | 1 个已跟踪文件，2 行新增、2 行删除；另有 1 个新测试文件（不含本文件） |
| python.exe -B scripts\dev.py commit（点名 desktop_script_pages script_structure script_page_layout ui_batch5_stage_panel_and_script_page） | 结果以本文件的证据行和提交记录为准 |

## 如实说明

- （一）没有在真实界面上点过，也没有从车道起真实的应用窗口（车道里按应用自己的路径关窗会另起项目库清理进程，车道没有自己的配置时指向的是默认项目库）。因此没有改前改后截图。「对齐」是用控件坐标量的：每一块的屏幕横坐标和宽度，和共享输入框外框的左右边缘逐一相减。
- （二）新用例把 `Desktop._after_first_paint` 换成了空动作。原因：首帧回调会提交技能同步（写用户主目录下的三处技能目录）、旧项目迁移，并排上续期和更新检查；这条用例只量排版，不该碰测试目录以外的东西。核对过两点：换成空动作以后，用例在没改产品时照样红、改后照样绿；读代码，首帧回调设的标记只用于恢复周期任务和三虎的问候，排版不依赖它。第一版用例（23:07 至 23:20 那几次）还没有换，跑的时候首帧回调是生效的；事后只读查过用户主目录那三处目录，没有今天新写入的登记。别的现有界面用例有没有同样的情况、怎么从根上挡住，写在结论文件 `.agent-tmp/562cdbb1-finding-SKILL-SYNC-OWNER.md`，另出修复卡，本轮没有动。
- （三）等待的写法：窗口改尺寸后轮询，直到「页面内容宽度等于画布宽度，而且连续两次量到的边缘相同」才往下断言，上限 30 秒，超时直接报「没有排稳」。第一版上限是 5 秒，在 8 路并行的回归里有 4 个子用例超时，单独跑 7.3 秒通过；改成 30 秒以后在同样的并行回归里通过（78.4 秒）。并行回归只跑过这一遍，没有反复跑。
- （四）回归里那 1 条红的归因。`test_files_panel_stages` 的 `IndexLifecycleTests.test_refresh_discovers_external_file_and_retains_script_actions`（外部新增的文件没有出现在文件面板的列表里）在本轮的两遍并行回归里都红，单独跑它所在的文件 150 条全过。它验的是文件面板刷新索引，和本轮改的内边距不在同一个模块；验收窗口已经把这个文件「等文件索引画完的写法不稳、机器忙时随机红」登记为候选项。没有做的对照：没有在不含本轮改动的主干上把同一组 13 个关键词并行重跑一遍。所以「和本轮无关」是按「单独跑全过、不同模块」判断的，不是对照实验的结论；队列项的验收命令里没有放这个关键词。
- （五）同一个产品文件还有一项没合入的改动：SEND-1（分支 codex/send-stage-action）在 `ui/desktop_script_pages.py` 里登记发送动作，在第 497 行附近；本轮改的是第 606 行附近的 `_ContentBox.build`。两段不相邻，谁后合入谁变基，已在心跳里和对方说定。
- （六）别的页面和输入框对不对齐，本轮没有量。剧本准备页有现成的用例守着；其余阶段页没有同类用例。打算另出一项逐页量，量出来不齐的再一页一页改。
- （七）见红那一步用了 git stash 收起和恢复改动。stash 是整个仓库各工作树共用的，这样做有拿错别人那一条的风险；这次前后 11 秒，恢复后用 git status 和 git diff 核对过是我的那两行改动。以后这类操作改成「把文件另存到临时目录再检出」，不用 stash。
- （八）第一版用例跑的时候，应用在车道的 程序 目录里写了一个空的项目登记文件（41 字节，被忽略规则挡着，不入库），留在车道里没有删。
- （九）本轮的代码由需求受理／机动执行窗口直接写。按四窗口协调第 10 条，除验收窗口复核和 `verify` 外，还要加一张只读审查卡。本窗口没有合入、没有登记已验收。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在真实界面上验证；没有截图；未 push、未 merge。
- 其他阶段页和输入框的对齐没有量（「如实说明」第（六）条）。
- 只在本机当前的显示缩放比例下量过，其他缩放比例没有量。
- 那条不稳的文件面板用例没有做「不含本轮改动」的并行对照（「如实说明」第（四）条）。
- 新写的等待只在本机跑过：单独两遍、并行一遍（提交工具再跑一遍）。
