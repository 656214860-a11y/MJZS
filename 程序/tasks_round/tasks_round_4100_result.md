# R4100 结果：资产图片制作结束时不把用户从别的页拉回资产管理页（两处结束回调只在用户停在资产管理页时重画，S05 文档补规则）
<!-- round-evidence: {"commit_base": "f624a5fc", "credential_hits": 0, "evidence_sha256": "845f73d6d6c038ed", "exit": 0, "failed": 0, "passed": 23, "round": 4100, "tests": "run_selftests.py -k asset_batch_window native_run stage_display_boundary"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮。任务卡 W6B-UX-B6B（队列项 UX-B6B），车道目录 ux-assets-stay，分支 codex/ux-batch-stay，基准 f624a5fc。来源：R4080 结果文件「如实说明」第（一）条留给用户定的取舍；队列项写明用户 2026-11-22 19:52 定了：停在资产管理页才重画，停在别的页只更新状态栏。改前的行为（读代码得出，没有在真实界面上点出来过）：批次窗的结束回调 `done`（`ui/asset_batch.py`）和制图窗的结束回调 `finished`（`ui/native_assets.py`）只判断「批次所属项目就是当前项目」，成立就 `show(PAGE_OF['assets'])`，不看用户此刻停在哪一页；用户在别的页干活时，批量生成一结束就被切到资产管理页。复现：先写测试，改产品之前跑，3 条失败（见「改前红」）。
- （二）测试跑了吗、三个基线各是什么结果：定向——跑了。只跑新加的两个测试类：改产品前 7 条里 3 条失败，改后 7 条全过。验收命令一（三组定向，含 3 条带界面的旧用例）「共 23 条用例，51.7 秒；0 个文件有红」，退出码 0；验收命令二（文档守卫四组）「共 34 条用例，1.6 秒；0 个文件有红」，退出码 0。架构门禁——在全部改动之后整套跑过：「Ran 700 tests in 360.996s」「OK」，退出码 0；输出里有一条主干既有的棘轮提示（LR-09、LR-10 实测 59 < 基线 60），不是本轮造成，没有动。默认冒烟和全量自测——没跑（窗口约定不跑全量）。提交工具在提交时会再跑一遍验收命令一的三组，结果以本文件的证据行为准；提交工具和提交钩子都不跑整套架构门禁，所以架构门禁以上面单独跑的这一遍为准。
- （三）欠账少了吗：少了一条——R4080「未覆盖项」里的「批量生成结束时要不要把用户带回资产页，等用户裁决」，已按用户的裁决落地。没有新增欠账。新增一条带测试锚点的需求 REQ-S05-24。

## 改前红

改产品代码之前（两处结束回调都还是原样），在车道的 程序 目录下只跑新加的两个测试类（22:29:16，进程优先级 BelowNormal），退出码 1：

```
test_finish_after_project_switch_does_not_redraw (test_asset_batch_window.AssetBatchFinishStaysOnPageTests.test_finish_after_project_switch_does_not_redraw) ... ok
test_finish_leaves_other_pages_alone (test_asset_batch_window.AssetBatchFinishStaysOnPageTests.test_finish_leaves_other_pages_alone) ... FAIL
test_finish_redraws_assets_page_when_user_is_on_it (test_asset_batch_window.AssetBatchFinishStaysOnPageTests.test_finish_redraws_assets_page_when_user_is_on_it) ... ok
test_finished_after_project_switch_does_not_redraw (test_native_run.FinishedStaysOnPageTests.test_finished_after_project_switch_does_not_redraw) ... ok
test_finished_leaves_other_pages_alone (test_native_run.FinishedStaysOnPageTests.test_finished_leaves_other_pages_alone) ... FAIL
test_finished_on_another_page_still_reports_in_the_drawing_window (test_native_run.FinishedStaysOnPageTests.test_finished_on_another_page_still_reports_in_the_drawing_window) ... FAIL
test_finished_redraws_assets_page_when_user_is_on_it (test_native_run.FinishedStaysOnPageTests.test_finished_redraws_assets_page_when_user_is_on_it) ... ok

FAIL: test_finish_leaves_other_pages_alone (test_asset_batch_window.AssetBatchFinishStaysOnPageTests.test_finish_leaves_other_pages_alone)
  File "tests\test_asset_batch_window.py", line 198, in test_finish_leaves_other_pages_alone
    self.assertEqual(window.app.shown, [], '人在别的页时不许翻回资产管理页')
AssertionError: Lists differ: [4] != []

FAIL: test_finished_leaves_other_pages_alone (test_native_run.FinishedStaysOnPageTests.test_finished_leaves_other_pages_alone)
  File "tests\test_native_run.py", line 280, in test_finished_leaves_other_pages_alone
    self.assertEqual(controls.app.shown, [], '人在别的页时不许翻回资产管理页')
AssertionError: Lists differ: [4] != []

FAIL: test_finished_on_another_page_still_reports_in_the_drawing_window (test_native_run.FinishedStaysOnPageTests.test_finished_on_another_page_still_reports_in_the_drawing_window)
  File "tests\test_native_run.py", line 285, in test_finished_on_another_page_still_reports_in_the_drawing_window
    self.assertEqual(controls.app.shown, [], '制图窗还开着也不许翻回资产管理页')
AssertionError: Lists differ: [4] != []

Ran 7 tests in 0.021s
FAILED (failures=3)
```

上面是节选：去掉了分隔线、列表差异的逐行对比，文件路径只留了相对部分。`[4]` 就是资产管理页的页码（`PAGE_OF['assets']`）：用户停在「初步分镜」时，结束回调仍然翻到了资产管理页。

撤掉产品改动时哪几条用例见红：

- 撤掉 `ui/asset_batch.py` 那一行：`test_asset_batch_window.AssetBatchFinishStaysOnPageTests.test_finish_leaves_other_pages_alone`。
- 撤掉 `ui/native_assets.py` 那一行：`test_native_run.FinishedStaysOnPageTests.test_finished_leaves_other_pages_alone` 和 `test_native_run.FinishedStaysOnPageTests.test_finished_on_another_page_still_reports_in_the_drawing_window`。
- 实测的是两行都没改时这 3 条一起红；「哪一行对哪几条」是按用例所测的模块对应的，没有逐行分开撤。
- 其余 4 条改前改后都通过，它们钉的是不许顺手改坏的旧行为：用户停在资产管理页时仍然重画；项目已经换了就不重画。

改完产品代码后同一条命令（22:30:01）：「Ran 7 tests in 0.023s」「OK」，退出码 0。

## 改了哪些文件

- ui/asset_batch.py：`_AssetBatchWindow.start` 里的结束回调 `done`，翻页那一行的条件从 `self.app.root==self.project` 改为 `self.app.root==self.project and getattr(self.app,'page_index',None)==PAGE_OF['assets']`，行尾加一句注释。1 行新增、1 行删除，文件行数不变。
- ui/native_assets.py：`_AssetControls.start` 里的结束回调 `finished`，同样的改法。1 行新增、1 行删除，文件行数不变。
- tests/test_asset_batch_window.py：加 3 个导入（`queue`、`SimpleNamespace`、`PAGE_OF`）、主窗口替身 `_Host`、测试类 `AssetBatchFinishStaysOnPageTests`（3 条）。83 行新增。原有的 3 条界面用例没有动。
- tests/test_native_run.py：加 2 个导入（`mock`、`PAGE_OF`）、主窗口替身 `_Host`、测试类 `FinishedStaysOnPageTests`（4 条）。71 行新增。原有的 6 条用例没有动。
- docs/stages/S05_资产管理.md：需求 REQ-S05-24、设计 DES-S05-24、「测试锚定」表一行、「页面状态」表一行 UX-S05-67。4 行新增。
- tasks_round/tasks_round_4100_result.md 是本文件；tasks_round/evidence/R4100.json 由提交工具生成。

没有改基线、覆盖率下限、各登记表；没有新增测试文件，所以不需要在 governance/structure.json 登记。

## 测试与卡面的对应

| 卡面的话 | 用例 |
| --- | --- |
| 停在资产管理页才重画 | `test_finish_redraws_assets_page_when_user_is_on_it`（批次窗）、`test_finished_redraws_assets_page_when_user_is_on_it`（制图窗）：停在资产管理页时 `show` 被调一次，参数是 `PAGE_OF['assets']` |
| 停在别的页只更新状态栏 | `test_finish_leaves_other_pages_alone`（批次窗）：停在初步分镜时 `show` 一次也不调；主窗口状态栏和批次窗自己的状态行都写了结果；完成消息照常上报；没显示完的进度消息照常清掉。`test_finished_leaves_other_pages_alone`（制图窗已关）：`show` 不调，状态栏写了结果。`test_finished_on_another_page_still_reports_in_the_drawing_window`（制图窗还开着）：`show` 不调，制图窗照常写进度行、弹「制作完成」、关窗 |
| 原有的「项目换了就不重画」不能丢 | `test_finish_after_project_switch_does_not_redraw`、`test_finished_after_project_switch_does_not_redraw` |
| 页码不写死数字 | 既有守卫 tests/architecture/test_stage_display_boundary.py（本轮没改它，验收命令一和架构门禁都会跑到） |
| S05 阶段文档补一条规则 | REQ-S05-24；两个新测试类的说明里写了这个编号，需求锚定守卫据此认定它有测试（验收命令二） |

## 与任务书不同的地方

- 卡面写「S05 阶段文档补一条规则」。规则只有一条（REQ-S05-24），但文档里改了四行：需求一行，另外三行是它在「设计条目」「测试锚定」「页面状态」三处的对应行（DES-S05-24、表格一行、UX-S05-67），都指回 REQ-S05-24，没有别的新内容。这样写是因为这份文档里每条已实现的需求都有这几处对应行。验收方认为只该留一行的话，删掉另外三行不影响任何门禁。
- REQ-S05-24 的条文把第三处（Skill 批次自动导入，`ui/asset_skill_batch.py` 的 `watch`）也写了进去。那一处在 R4080 已经是这个口径，并有 `tests/test_asset_skill_batch.py` 的两条用例；本轮没有改它的代码和测试，只是让文档一次说全三处。
- 其余照卡面做，没有改卡面以外的文件。

## 如实说明

- （一）没有在真实界面上点过。新用例不开窗口：拿 `MagicMock` 当批次窗（或制图窗的控件组），直接调 `_AssetBatchWindow.start`／`_AssetControls.start`，从替身主窗口的 `async_` 里拿到结束回调再调用。所以它们钉住的是结束回调的行为，不验证控件接线；`start()` 的写法大改时这几条用例要跟着改。
- （二）「停在资产管理页」按 `page_index==PAGE_OF['assets']` 判断，和 R4080 在 `ui/asset_skill_batch.py` 里的写法一样。资产详情页、资产清单页是这一页的子页，页码相同，所以也算「停在资产管理页」；重画后仍在原来的子页，这一点是读 `ui/desktop_page_nav.py` 的 `show` 得出的（只在翻到别的页时清 `asset_detail_id`、`asset_roster`），本轮没有为它写用例。
- （三）用户停在别的页时不重画资产管理页，切回来会不会看到旧内容：资产管理页不在整页缓存名单里（`ui/desktop_page_registry.py` 的 `CACHED_PAGES` 只有剧本结构和初步分镜两页），每次切回来都重建。这一点也是读代码得出的，本轮没有为它写用例。
- （四）批次窗、制图窗自己的表现没有改：批次窗照常刷新自己的列表和状态行，制图窗照常弹完成提示并关窗。用户停在别的页时，主窗口只有状态栏那一句变了。
- （五）其他会切到资产管理页的调用没有动。在 ui 等产品目录里搜 `show(PAGE['assets'])`、`show(PAGE_OF['assets'])` 共 19 处：本轮改的 2 处；`ui/asset_skill_batch.py` 1 处和 `ui/desktop_auto_flows.py` 1 处本来就先判断页码；其余 15 处是用户自己在资产管理页上操作后的重画（筛选、进出详情、删除、改名、导入参考图等），不属于「批量生成结束」，没有逐处核对它们的调用时机。
- （六）主干已知的红（`-k idea_chat` 4 条、`-k ui_edges_pages` 1 条、`-k distribution_selfcheck` 1 条、`test_files_panel_stages` 机器忙时随机红）不在本轮跑的范围里，没有动。
- （七）本轮由推进预备窗口直接写代码。按窗口协调的约定，除验收窗口复核和 `verify` 外，还要加一张不同型号的只读审查卡。

## 命令与退出码

都在车道的 程序 目录下跑，python.exe 指 `..\..\..\..\运行环境\Python\python.exe`；测试进程优先级降到 BelowNormal。时间取本机时钟。

| 命令 | 结果 |
| --- | --- |
| python.exe -B scripts\dev.py claim（22:24:45） | 领到轮次 4100 |
| python.exe -B scripts\dev.py scope ui/asset_batch.py ui/native_assets.py tests/test_asset_batch_window.py tests/test_native_run.py docs/stages/S05_资产管理.md（22:25:58） | 退出码 0：「另 27 个工作树分支无重叠」 |
| 只跑新加的两个测试类（改产品之前，22:29:16） | 退出码 1：「Ran 7 tests」「FAILED (failures=3)」 |
| 同一条命令（改产品之后，22:30:01） | 退出码 0：「Ran 7 tests」「OK」 |
| 验收命令二：python.exe -B run_selftests.py -k stage_doc_sections agent_doc_budget requirement_traceability design_coverage（22:33:02 至 22:33:06） | 退出码 0：「共 34 条用例，1.6 秒；0 个文件有红」（design_coverage 8 条、stage_doc_sections 10 条、agent_doc_budget 11 条、requirement_traceability 5 条） |
| 验收命令三：python.exe -B smoke_test.py --architecture（22:33:06 至 22:39:09） | 退出码 0：「Ran 700 tests in 360.996s」「OK」「✅ 架构治理测试：tests/architecture」；另有一条既有的棘轮提示（LR-09、LR-10 实测 59 < 基线 60） |
| 验收命令一：python.exe -B run_selftests.py -k asset_batch_window native_run stage_display_boundary（22:39:09 至 22:40:03，第一次就拿到界面令牌，等了约半分钟） | 退出码 0：「共 23 条用例，51.7 秒；0 个文件有红」（test_native_run 10 条、architecture.test_stage_display_boundary 7 条、test_asset_batch_window 6 条）；「实际跳过 0 条用例」 |

三条验收命令是在本文件还是初稿（上表这三行和三问第（二）条还没填）时跑的；跑完以后只改了本文件，没有再动代码、测试和文档。

「只跑新加的两个测试类」用的是放在系统临时目录里的一个七行小脚本：把 程序 和 程序\tests 加进模块搜索路径，按名字装载 `test_asset_batch_window.AssetBatchFinishStaysOnPageTests` 和 `test_native_run.FinishedStaysOnPageTests`，用 unittest 跑。工作树里没有留下临时文件。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在真实界面上验证；未 push、未 merge。
- 「重画后仍在原来的子页」「切回资产管理页时按最新数据重建」两点只读了代码，没有用例（见「如实说明」第（二）（三）条）。
- 其余 15 处切到资产管理页的调用没有核对调用时机（见「如实说明」第（五）条）。

## 提交

用 `scripts\dev.py commit` 提交，只提交上面列出的文件。提交号不写在本文件里，见会话接续记录里推进预备窗口那一节和队列心跳。
