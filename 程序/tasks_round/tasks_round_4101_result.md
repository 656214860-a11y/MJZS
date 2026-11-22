# R4101 结果：5 条过期的界面测试改成文件面板「跟随当前页」之后的断言（只改测试，不动产品）
<!-- round-evidence: {"commit_base": "f624a5fc", "credential_hits": 0, "evidence_sha256": "20b88f054c5bcc11", "exit": 0, "failed": 0, "passed": 231, "round": 4101, "tests": "run_selftests.py -k idea_chat ui_edges_pages desktop_compact_layout"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮，只改测试。任务卡 W4-FIX-PANEL-TESTS（队列项 FIX-PANEL-TESTS），车道 codex/ux-dock-tests-sync，基准 f624a5fc。来源：验收窗口 2026-11-22 21:50 复验时发现主干上有 5 条界面测试必红，挡着 UX-C5 合入；任务书 `.agent-tmp/ccc4a5fe-task-FIX-PANEL-TESTS.md`。现象：`tests/test_idea_chat.py` 4 条、`tests/test_ui_edges_pages.py` 1 条在干净的 f624a5fc 上必红。根因：R4075 起项目文件面板跟随当前页——不在素材库视图时只列当前阶段的用户文件，标题带阶段名；只有一个分组时文件行平铺、不套分组父行；没有带缩略图的行时不留左侧树列。这 5 条用例还按「默认列全部阶段、根下总是阶段分组父行」写。产品行为和 R4075 的设计一致，过期的是测试。复现：改之前先在干净的 f624a5fc 上跑了基线，红的正好是这 5 条（见「命令与结果」）。
- （二）测试跑了吗、三个基线：改前基线 452 条里红 5 条；改后任务书的验收命令 `run_selftests.py -k idea_chat ui_edges_pages desktop_compact_layout`「共 231 条用例」「0 个文件有红」，退出码 0，只跑了一遍；提交时提交工具再跑同一组点名测试，以本文件的证据行为准。架构门禁没有单独跑，由提交工具跑。默认冒烟没有单独跑；全量自测没跑。本轮改的就是现有用例的断言，逐条见「断言改动对照」；没有删用例，没有加跳过，没有改产品文件、覆盖率下限、基线和登记表。
- （三）欠账少了吗：主干上的必红少了 5 条。顺带把一组恒真的断言改成了有对象可验（对照第 4 条）。没有新增欠账；看到但没有处理的两点写在「如实说明」第（四）（五）条。

## 改了哪些文件

- tests/test_idea_chat.py：公共辅助 `assert_script_file_row` 和用例 `test_empty_script_list_keeps_category_headers_and_chat_visible`。29 行新增、13 行删除。
- tests/test_ui_edges_pages.py：用例 `test_the_writing_page_wraps_the_box_with_buttons`。31 行新增、4 行删除。
- tasks_round/tasks_round_4101_result.md 是本文件。
- 队列项允许清单里的 tests/test_desktop_compact_layout.py 没有动（它在基线里就是绿的）。

## 断言改动对照（原断言 → 新断言 → 理由）

### tests/test_idea_chat.py

1. 公共辅助 `assert_script_file_row`（三条用例共用：`test_delayed_script_rows_are_not_covered_by_empty_state`、`test_double_click_on_script_header_does_not_open_selected_file`、`test_refresh_script_workspace_shows_agent_internal_draft`）。
   - 原：表格根下有 `stage-group:script`；文件行在这个分组的子行里；文件行的父行是 `stage-group:script`。
   - 新：文件行直接在表格根下；根下没有任何以 `stage-group:` 开头的行；文件行的父行是根（空串）。
   - 理由：剧本准备页的面板只列本阶段文件，只有一个分组，产品在只有一个分组时不套分组父行。这三条用例自己的断言一个字没改（空态标签不显示；双击表头不打开文件、双击文件行和按键才打开；内部工作稿那一行带「内部工作稿」字样）。双击用例取点的算法不用改：探查里文件行在表头下面，算出来的那个点仍落在表头区。
2. `test_empty_script_list_keeps_category_headers_and_chat_visible`。
   - （a）原：标题等于「项目文件」。新：标题等于「项目文件 · 剧本准备」。理由：标题现在带当前阶段名。
   - （b）新增：剧本准备视图下表格根下没有任何行。理由：夹具只有项目根目录的一个说明文件，它不属于剧本准备阶段。以前默认列全部阶段，这条用例名叫「空列表」，表格里其实有一行；现在默认视图是真的空，用例名和场面第一次对上。
   - （c）原：空态标签不显示（保留，一字未改）。新增：表格左上角那一点识别为表头（列表为空时表头仍在表格顶部）。理由：验收窗口提醒要保住「空态提示不能盖住表头和对话区」这层意思，不能只改标题字符串。
   - （d）原：对话记录可见、高度大于 1、输入框可见，只在用例末尾查一次（那时表格里有行）。新：同样三条包成一个内部函数，空列表时查一次，切到「全部阶段」之后再查一次。理由：空列表那一刻才是这条用例要守的场面。
   - （e）原：根下的行非空，且每一行都以 `stage-group:` 开头；文件叶子取各分组的子行。新：先 `show_stage(None)` 切到「全部阶段」并等索引加载、渲染完；标题等于「项目文件 · 全部阶段」；空态标签不显示；根下的行非空，且没有以 `stage-group:` 开头的行；`all_script_items()` 和根下的行一一对应。理由：「根目录的用户文件也进索引」只在「全部阶段」下成立；这个夹具在「全部阶段」下也只有「其他文件」一个分组，所以同样平铺。多个分组时套分组父行的行为，这条用例不再覆盖，由 tests/test_files_panel_stages.py 的 `DockContentTests.test_multiple_groups_keep_stage_group_rows` 和下面第 4 条覆盖。
   - （f）保留不变：说明文件在文件叶子里；每个叶子是项目相对路径、对应的文件存在。

### tests/test_ui_edges_pages.py（`test_the_writing_page_wraps_the_box_with_buttons`）

3. 默认视图（剧本准备）。
   - （a）新增：标题等于「项目文件 · 剧本准备」；根下的行和 `all_script_items()` 一一对应（平铺、没有分组父行）。
   - （b）原：表高等于「上限 6」和「文件数加根下行数」里较小的。新：表高等于「上限 6」和「文件数」里较小的。理由：平铺时根下的行就是文件行，原式把文件算了两遍；产品的算法是文件数加分组数，只有一个分组时分组不占行。
   - （c）原：`show` 等于 `("tree", "headings")`（基线里红的就是这一条）。新：`show` 等于 `("headings",)`。理由：只有一个分组、又没有带缩略图的行时，产品不留左侧树列。
4. 用例末尾，原来按 `02剧本结构/` 筛出来的那组断言。
   - 原：从文件叶子里筛出 `02剧本结构/` 开头的，断言它们的类别全是 `index`。夹具里从来没有这个目录下的用户文件，现在默认又只列剧本准备阶段，筛出来是空的，这条断言恒真。
   - 新：先在夹具里补一个剧本结构阶段的用户文件（`02剧本结构/结构剧本/结构剧本_测试.md`），重建文件索引，`show_stage(None)` 切到「全部阶段」并等加载、渲染完。然后断言：标题等于「项目文件 · 全部阶段」；分组父行正好是 `stage-group:script` 和 `stage-group:script_structure` 两个；`show` 等于 `("tree", "headings")`（原 3（c）的断言挪到了它成立的场面）；表高等于「上限 6」和「文件数加分组数」里较小的；筛出来的正好是补进去的那一个文件（非空）；它的类别是 `index`（原断言，保留）。
   - 理由：验收窗口提醒的第二点——挪到 `show_stage(None)` 之后并加非空断言。

## 命令与结果

下表的命令都是在车道的 程序 目录下、进程优先级降到 BelowNormal 跑的。界面测试整轮在隐藏桌面里跑，失败原文和汇总行取自车道的 `logs\hidden_selftest.log`。

| 命令 | 结果 |
| --- | --- |
| 在一个已合入、工作树干净的闲置车道目录里从 f624a5fc 切分支 codex/ux-dock-tests-sync | 没有新建工作树目录；`git status` 干净 |
| python.exe -B run_selftests.py -k（任务书的三个关键词之外多点了几个和面板、剧本准备页有关的关键词；改动之前，21:59:48–22:08:42） | 「定向：忽略增量台账，执行 19 个匹配测试文件」「共 452 条用例，528.2 秒；3 个文件有红」，退出码 1。红的是三个工作单元里的 5 条，没有第 6 条：`test_ui_edges_pages.py` 596 行「Tuples differ: ('headings',) != ('tree', 'headings')」；`test_idea_chat.py` 1126 行「'项目文件 · 剧本准备' != '项目文件'」；`test_idea_chat.py` 1185、1199、1231 行各一条，都经 `assert_script_file_row`（914 行）报「'stage-group:script' not found in (...)」 |
| 探查（临时放进车道的一个探查用例，只读界面状态并写成 JSON；跑完即删，开始改之前 `git status` 是干净的） | 最小项目加根目录说明文件：默认视图标题「项目文件 · 剧本准备」，表格没有行，空态标签不显示，左上角那一点识别为表头，对话记录和输入框可见；`show_stage(None)` 之后标题「项目文件 · 全部阶段」，根下只有说明文件一行（类别 `index`），没有分组父行。页面边界那条用例的夹具：默认视图 7 个文件平铺，`show` 是 `("headings",)`，表高 6；磁盘上没有 `02剧本结构/` 下的用户文件 |
| python.exe -B run_selftests.py -k idea_chat ui_edges_pages desktop_compact_layout（改动之后，22:17:27–22:24:24） | 「定向：忽略增量台账，执行 9 个匹配测试文件」「共 231 条用例，413.2 秒；0 个文件有红」「实际跳过 0 条用例」「ALL TESTS PASSED」，退出码 0 |
| python.exe -B scripts\dev.py claim | 领到轮次 4101 |
| git diff --numstat | 2 个文件，60 行新增、17 行删除（不含本文件） |
| python.exe -B scripts\dev.py commit（点名 idea_chat ui_edges_pages desktop_compact_layout） | 结果以本文件的证据行和提交记录为准 |

## 如实说明

- （一）和任务书不一样的地方有一处：页面边界那条用例里补了一个夹具文件，并在测试里调 `infra.file_index.rebuild` 重建索引。原因是原来那组 `02剧本结构/` 的断言没有对象可验；任务书给的两个选项是「挪到 `show_stage(None)` 之后并加非空断言」或「写明没有覆盖」，夹具里没有这样的文件，要非空就得补一个。用 `rebuild` 而不是等面板自己发现，是为了让「全部阶段」读到的索引一定包含新文件，不依赖面板的增量发现走没走到这个目录。只动了测试文件。
- （二）空态那条守卫现在守的是什么：面板的表格建表时空态文字是空串（`ui/desktop_files_panel.py` 209 行），探查里列表为空时空态标签也没有显示。所以「空态标签不显示」这条断言现在挡的是以后有人把空态文字加回来、又盖住表头；「左上角识别为表头」是表格控件自己算的，不知道上面有没有别的控件盖着，两条要合起来看。
- （三）等索引加载的写法：`test_idea_chat.py` 里沿用文件里已有的 `wait_file_index`，没有改这个公共辅助（往里加条件有可能让「加载到一半就收起面板」的用例卡住）；`test_ui_edges_pages.py` 里没有这个辅助，写了一段等价的显式等待（后台任务、任务队列、渐进渲染三者都空了才往下走，10 秒超时报错），超时时长和已有辅助一致。在 8 路并行的负载下跑过一遍是过的，没有反复跑过。
- （四）表高那两条断言在这两个夹具下都顶到上限 6（7 个文件；8 个文件加 2 个分组），等于只验了封顶，改之前也是这样。按上限常量名搜，测试目录里只有这个文件引用它；别的测试有没有用字面数字验过上限以下的表高，我没有逐个看。没有在本轮加，报给验收窗口定。
- （五）按任务书的要求把两个文件里所有碰文件面板的地方过了一遍（搜 `script_tree`、`script_title`、`files_panel`、`all_script_items`、`stage-group`、`empty_label`、`script_row_category`）：`test_ui_edges_pages.py` 只有这一条用例碰面板；`test_idea_chat.py` 除了上面四条，还有 `test_project_files_panel_toggle_and_page_switch`，它只验面板的展开、收起和切页，不看列表内容，基线里是绿的，没有动。除对照第 4 条那一组以外，没有发现别的恒真断言。页面边界那条用例里「每个文件的类别属于五种之一」那个循环现在有 7 个文件可验，不是空集。
- （六）没有在真实界面上点过；这轮没有界面改动，所以没有改前改后截图。
- （七）本轮由需求受理／机动执行窗口直接改。验收窗口已说明这一项由它自己复核、跑 `verify`，再放一张只读审查卡。本窗口没有合入、没有登记已验收。
- （八）基线那次多点的关键词没有留在日志里，只留下「19 个匹配测试文件」和各工作单元的名字；红的 5 条都在任务书点名的两个文件里。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在真实界面上验证；未 push、未 merge。
- 上限以下的表高算法（「如实说明」第（四）条）。
- 「空列表」用例里多个分组的场面不再由它覆盖，改由对照第 2（e）条写明的另外两处覆盖。
- 新写的等待和夹具只在本机、一种负载下跑过一遍（提交工具再跑一遍）。
