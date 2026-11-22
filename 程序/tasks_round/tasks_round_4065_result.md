# R4065 结果：表格定高把横向滚动条算进去，修复资产页窄窗口卡死
<!-- round-evidence: {"commit_base": "5c85dd13", "credential_hits": 0, "evidence_sha256": "e4cd8773a93e03b1", "exit": 0, "failed": 0, "passed": 21, "round": 4065, "tests": "run_selftests.py -k ui_edges_tables desktop_compact_layout"} -->

## 开头三问

（一）本轮属于哪种类型：修复轮，任务卡 B-FIX-TABLE-BAR，车道 codex/full-selftest-reds（这条车道专门收全量自测里的红，本轮是第一个提交）。修的是 R4059（R4062 合入）之后资产管理页在窄窗口里整窗卡死的问题；根因在公共函数 responsive_ui.auto_height，R4059 只是让它更容易被撞上。

（二）测试跑了吗：新增 tests/test_ui_edges_tables.py 的 AutoHeightScrollbarTests 共 1 条，改前失败（AssertionError: 4 != 2 : 表格没收回最少行数），改后通过；tests.test_ui_edges_tables 实测 16 条全过；tests.test_desktop_compact_layout 实测 5 条全过（改前这一组在 master 上会卡死，由总控复现，本次没有重做）；架构门禁实测 696 条、失败集合为空；默认冒烟实测通过 9 项、失败 0 项；全量自测没跑。

（三）欠账少了吗：修掉一个会让界面卡死的缺陷；复杂度记录没有调大；没有新增欠账；遗留一项见「未覆盖项」。

## 改了哪些文件

- responsive_ui.py（新增 _bar_height：DataTable 壳底下的横向滚动条露着时返回它的高度，否则返回 0；auto_height 算可用高度时多扣这个高度；参数、默认值、返回值不变）
- tests/test_ui_edges_tables.py（文件末尾新增 AutoHeightScrollbarTests，1 条用例）
- tasks_round/tasks_round_4065_result.md（本文件）

没有改任何页面文件，没有改 ui/desktop_asset_pages.py（R4059 的按钮对齐保留），没有改 ui_widgets.py，没有改结构登记。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| 改前只跑新测试类：unittest tests.test_ui_edges_tables.AutoHeightScrollbarTests | 退出码 1，AssertionError: 4 != 2 : 表格没收回最少行数 |
| 改后：unittest tests.test_ui_edges_tables | 退出码 0，Ran 16 tests，OK |
| 改后：unittest tests.test_desktop_compact_layout | 退出码 0，Ran 5 tests，OK |
| smoke_test.py --architecture | Ran 696 tests，OK，失败集合为空 |
| smoke_test.py | 通过 9 项，失败 0 项 |
| scripts\dev.py claim | 领到轮次号 4065 |

## 如实说明

（一）根因由总控定位，执行方照卡面落地。auto_height 按「容器高度减 padding（48）」算行数；主题下表头连边框 43 像素、横向滚动条 8 像素，合计 51，比 48 多 3。页面放不下时容器高度就是表格自己请求的高度，算回来的行数与现在一样，表格收不回最少行数；请求高度隔几轮空闲回调才传到容器，两个在途的行数互相追着改，界面不再响应。用到 auto_height 的 7 处表格（资产页、分镜镜头页、分镜文件页、白模页、回收站弹窗、模型配置、版本选择）都带横向滚动条，都在这次修复的范围里。

（二）为什么 R4059 之后才撞上：R4059 把资产页的三行按钮改成带标签的换行条、底部五个按钮定宽，窄窗口里多换几行，页面更容易放不下。总控把 ui/desktop_asset_pages.py 在内存里换回 R4059 之前的版本，同样两条用例 9 秒通过；换回现在的版本就卡死。

（三）影响范围来自总控的对比（在内存里套上本轮改动，不是执行方实测）：27 个「文件面板开关×窗口尺寸×页面」场景里 17 个完全一样；资产页 800×600 开着文件面板时，底部按钮条从只露 7 像素（共 119）变成全部显示，表格从 4 行收到 2 行；其余差别是空表格请求的行数少 1～2 行（空表提示盖着表格，占的高度没变，或两张表变得一样高）。另有 44 个相关界面测试文件逐个跑了改前、改后：41 个都全过，3 个改前就有红、改后红得一样。横向滚动条收起来时算法与改前完全一样。

（四）改前红测只做了新测试类；「整窗卡死」没有让执行方重新复现（复现就是让进程卡住等超时），证据是总控在 master 上的复现，以及本次改后 tests.test_desktop_compact_layout 全过。

（五）新用例放在 tests/test_ui_edges_tables.py：这个文件已经有表格行高的用例（RowHeightTests），放这里不用改结构登记（另一条车道正在改同一份登记）。用例里 padding 取「实测表头高度加 5」，是为了在没有套主题的测试窗口里也能复现与页面上相同的情形（padding 够表头、不够表头加滚动条）。

## 未覆盖项

- 未跑全量自测。
- 没有在真实桌面上目检，只有隐藏桌面里的自动化用例和总控的对比。
- 有数据的表格在小窗口里的行数没有逐页对比（按算法：页面放不下时表格收到最少 2 行，其余内容完整显示并可滚动）。
- 遗留一项独立的老问题本轮没动——整页定高时 growable_extra 把别的页面里的表格也算了进去，分镜文件页在小窗口里第二张表会被压扁，改前改后都一样。
- 未 push、未 merge。
