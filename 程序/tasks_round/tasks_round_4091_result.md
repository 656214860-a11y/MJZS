# R4091 结果：底部状态栏各段按文字定宽，间距、分隔符、字号统一（UX-C4）
<!-- round-evidence: {"commit_base": "f624a5fc", "credential_hits": 0, "evidence_sha256": "76f44342519ef4f0", "exit": 0, "failed": 0, "passed": 135, "round": 4091, "tests": "run_selftests.py -k ui_status_bar writing_status_line ui_batch3_shell usage_indicator_ui ui_token_contract pet_agent_error_wiring account_entry frame_sources desktop_page_nav window_resize_coalescing media_page_buttons desktop_compact_layout desktop_startup_perf timers ui_batch5_stage_panel_and_script_page ui_style_engine desktop_media_pages"} -->

## 开头三问

- 本轮属于哪种类型：功能轮（界面排版，UX-C4，卡 W5-UX-C4；车道 `codex/ux-status-bar`，从主干 `f624a5fc` 切出，目录 `.agents/worktrees/l4-buttons-board-assets`）。
- 测试跑了吗、三个基线：先红后绿。默认冒烟通过 9 项、失败 0 项。架构门禁通过（`Ran 700 tests`，`OK`，退出码 0）。全量回归没跑：用户 2026-11-22 19:52 决定验证期间不跑全量；全量欠账以 `full-safe-receipts.json` 为准，本轮没有改变它。点名测试的结果是提交工具在提交时跑的那一遍，记在 `tasks_round/evidence/R4091.json` 和本文件第二行的戳里。
- 欠账少了吗：`ui/ui_status_bar.py` 的原生控件登记数由 4 降到 2（全仓 63 降到 61）。新增 14 条用例。新增 1 条同层依赖登记（`ui_status_bar → ui_popup`）。没有新增豁免；除了把 `NATIVE_BASELINE` 下调到实测值，没有动别的基线表和棘轮表。

## 用户的要求和这一轮做了什么

用户的要求（需求机动窗口转述）：底部提示文字的排版要改善，间距、文字格式要统一。需求点在会话接续记录 562cdbb1 小节「UX-C4 的需求点」，五条都做了：

1. 每段的宽度按文字定：不超过上限（新 token `STATUS_BAR_SEGMENT_MAX_WIDTH`，28 个字符单位）就按文字本身的宽度显示全文，超过才定在上限宽度、截断，悬停给全文。宽度用 `ui/ui_popup.py` 的 `measure_text_width`、`char_unit_px` 量。调用方给了 `width` 的段维持那个宽度。
2. 文字为空的段连同它的分隔符不占位；再有文字时回到它登记时的位置。
3. 分隔符和段文字同一字体、同一档灰（样式 `Muted.TLabel`），两侧各留 `STATUS_BAR_SEPARATOR_GAP`（8 像素）；第一段前、最后一段后没有分隔符，中间的段隐藏时不会出现两个连着的。
4. 右区消息和左区同一字号；没有消息时的「就绪」和左区同一档灰；成功、警告、错误的底色和前缀符号没动；左右留白和左区开头的留白同为 `STATUS_BAR_EDGE_PAD`（8 像素）。
5. 取值都走 `ui_tokens`（5 个新 token，写进了 `design_tokens.md`）；`ui_components.md`「统一状态栏」一节按新规则改写。

需求点之外多做的一件：用量指示（Token／¥／余额）不是状态栏的段，是 `desktop.py` 第 349 行直接摆进状态栏左区的一个控件。只改状态栏的话，它两边的间距和别的段不一样，前面也没有分隔符，字号还是 8 号。现在状态栏把这类外来控件也当成一段：按它摆进来时的位置排，分隔符和两侧间距由状态栏给；它没有内容时不配分隔符。用量指示自己去掉了末尾多出来的 4 像素留白（三项之间仍是 8 像素），字号由 8 号改成和全栏一样的 10 号。动这些文件之前都在心跳里提出过，需求机动窗口把它们补进了队列项的「允许修改文件」。

## 改前改后量出来的数

同一组样例文字（页名「02 剧本」、路径「D:/漫剧下载/示例项目」、用量指示、「当前模型：示例模型」、一个空段、「当前 JSON：第 3 集」），窗口宽 1180 像素。仓库外的脚本在屏幕外的透明窗口里搭出状态栏后量的（22:45:32，改前改后同一次跑）；脚本不写项目文件，改前用 `git show HEAD` 取出的两个旧文件（和 `HEAD` 的 sha256 核对过一致）。

| | 改前 | 改后 |
|---|---|---|
| 每个文字段的宽度 | 一律 196 像素，空段也占 196 | 50、133、121、124 像素，空段不占位 |
| 分隔符 | 宽 9 像素，两侧没有间距；用量指示前面没有分隔符 | 宽 7 像素，两侧各 8 像素；用量指示前后都有 |
| 用量指示 | 宽 111 像素（8 号字） | 宽 126 像素（10 号字） |
| 左区总宽 | 1131 像素 | 646 像素 |
| 右区消息 | 只剩 25 像素，「就绪」显示成「…」 | 510 像素，显示「就绪」 |

对比图在主工作区的 `.agent-tmp/093883fa-shot-UX-C4-before.png` 和 `.agent-tmp/093883fa-shot-UX-C4-after.png`（不入库）。这是样例，不是真实应用窗口的截图。

## 改前红

三组新用例都是先写用例，在改动之前的实现上跑红，再在改动上跑绿。

1. `tests/test_ui_status_bar.py` 新增一个类 `StatusBarLayoutTests`（11 条）。把 `ui/ui_status_bar.py` 临时换回 `HEAD` 的内容跑（22:12:19–22:12:30，退出码 1，19 条里 9 条红；新实现先存到仓库外，跑完换回，换回后的文件和存的那份 sha256 一致）：

| 用例 | 改前红在哪 |
|---|---|
| `test_short_segment_is_as_wide_as_its_text` | `150 not less than 8`：短文字的段比文字宽出 150 像素 |
| `test_empty_segment_takes_no_room_and_comes_back_in_its_place` | `1 is not false`：空段仍然摆着 |
| `test_no_separator_at_either_end_and_never_two_in_a_row` | `['', '·', '乙', '·', '', '·', '丁', '·', ''] != ['乙', '·', '丁']` |
| `test_gaps_between_visible_segments_are_equal` | `3 != 1`：段文字到分隔符的空白是 `[150, 6, 80, 6, 144, 6]` |
| `test_separator_has_the_font_and_colour_of_segment_text` | 分隔符 `'size': 8`，段文字 `'size': 10` |
| `test_segment_over_the_cap_is_cut_and_hover_keeps_the_full_text` | `28 not less than 8`：超长的段宽度和上限差 28 像素（旧实现定在 24 个字符宽） |
| `test_neutral_message_is_muted_like_the_left_zone_and_errors_stay_red` | `'#0F1419' != '#536471'`：「就绪」是正文色，不是弱化灰 |
| `test_widget_put_in_by_another_module_gets_the_same_separators` | `['01 创意', '·', '', 'Token: 1', '·', '模型：甲'] != ['01 创意', '·', 'Token: 1', '·', '模型：甲']` |
| `test_empty_widget_from_another_module_gets_no_separator` | `4 != 5`：外来控件有了内容，状态栏没有补上分隔符 |

   另外 2 条（`test_explicit_width_is_kept`、`test_edges_use_one_padding`）改前改后都过，是把不该变的行为钉住，不算先红后绿。

2. `tests/test_usage_indicator_ui.py` 新增 2 条间距用例，用量指示的留白还是改前的写法时跑（22:13:43–22:13:52，退出码 1，10 条里 2 条红）：`[(0, 4), (4, 4), (4, 4)] != [(0, 0), (8, 0), (8, 0)]`（三项各自的留白）；`(8, 12) != (8, 8)`（摆进状态栏以后它前后的空白，前 8 后 12）。

3. 同一文件再加 1 条字体用例，用量指示的字体还是 `FONTS['pet_hint']` 时跑（22:34:02–22:34:22，退出码 1，11 条里这 1 条的 3 个子项红）：Token、¥、余额三项都是 `'size': 8`，要的是 `'size': 10`。

改完以后这两个文件 30 条全过，见「命令与退出码」。

## 改了哪些文件

| 文件 | 增/删 | 改动 |
|---|---|---|
| `ui_tokens.py` | 9/0 | 新增 `STATUS_BAR_FONT`（= `FONTS["body"]`）、`STATUS_BAR_SEGMENT_MAX_WIDTH`（28）、`STATUS_BAR_SEPARATOR`（`·`）、`STATUS_BAR_SEPARATOR_GAP`（= `SPACING["sm"]`）、`STATUS_BAR_EDGE_PAD`（= `SPACING["sm"]`）。 |
| `design_tokens.md` | 4/0 | 上面 5 个 token 的 4 行说明。 |
| `ui/ui_status_bar.py` | 168/31 | 新类 `SegmentLabel`（按文字定宽，超过上限才截断）；`StatusBar` 记下左区各控件的登记顺序，`_relayout` 按顺序重摆：空段不摆，看得见的两两之间放一个分隔符；`_adopt_guests` 把别的模块摆进左区的控件也排进顺序；左区容器和分隔符由 `tk` 控件换成 `ttk` 控件；「就绪」改用弱化灰；左区开头和右区消息两侧的留白统一。旧常量 `SEGMENT_DEFAULT_WIDTH` 删掉了（搜索过，仓库里没有别处用）。消息的四种级别、自动消失、历史面板、销毁时停定时器没动。 |
| `ui/ui_usage_indicator.py` | 5/4 | 三项的字体由 `FONTS['pet_hint']`（8 号）改成 `STATUS_BAR_FONT`（10 号）；整组两端不留白：末尾原来多出的 4 像素去掉；三项之间仍是 8 像素，写法由左右各 4 改成左侧 8。颜色、文字、点击行为没动。 |
| `ui_components.md` | 6/4 | 「统一状态栏」一节按新规则改写，补了「左区排布」和「外来控件」两条。 |
| `tests/test_ui_status_bar.py` | 204/1 | 新增 `StatusBarLayoutTests` 11 条；删的 1 行是 `from ui_tokens import COLORS`，换成带新 token 的导入。原有 8 条用例一字未动。 |
| `tests/test_usage_indicator_ui.py` | 53/1 | 新增 3 条；删的 1 行同样是那句导入。原有 8 条用例一字未动。 |
| `tests/test_ui_batch3_shell.py` | 1/1 | 第 152 行一处期望值：用量指示 Token 一项的字号，原值 `FONTS['pet_hint'][1]`（8），新值 `FONTS['body'][1]`（10）。别的页的测试里钉了旧值的只有这一处；需求机动窗口 22:15 同意并把文件补进了允许修改文件。 |
| `tests/architecture/test_native_control_boundary.py` | 4/3 | `NATIVE_BASELINE` 里 `ui/ui_status_bar.py` 由 4 下调到 2（只剩历史面板里的标题和关闭两个 `tk.Label`），文件头说明里的总数 63 改成 61。只下调，没有上调。 |
| `tests/architecture/_layers.py` | 1/0 | `SAME_LAYER_EDGES` 新增 `('ui_status_bar', 'ui_popup')`：需求点指定用 `ui/ui_popup.py` 的量宽函数。 |
| `tasks_round/tasks_round_4091_result.md` | — | 本文件。 |

`git diff --check` 干净。

新用例各管什么。`StatusBarLayoutTests` 11 条：短文字的段宽等于文字宽；空段不占位、补上文字后回到原位置；两端没有分隔符、不会连着两个；相邻可见段之间的空白处处相等；分隔符和段文字同字体同颜色；超过上限的段被截断、悬停是全文；显式 `width` 的段维持指定宽度；「就绪」和左区同色、错误消息仍是危险色；左区开头和右区两侧用同一个留白值；别的模块摆进来的控件前后有同样的分隔符；它没有内容时不配分隔符、有了内容再补上。用量指示 3 条：三项都用状态栏字体；整组两端不留白、三项之间一个间距；摆进状态栏以后它前后的空白相等。需求点列的 7 项测试都在这 11 条里。

## 与需求点不同的地方

- 需求点写「只改状态栏组件本身」。实际还改了 `ui/ui_usage_indicator.py`（原因见上）和它的测试、`tests/test_ui_batch3_shell.py` 一处期望、`tests/architecture/_layers.py` 一条登记。各页往状态栏写文字的地方一处没改。
- 左区容器 `left_zone` 由 `tk.Frame` 换成了 `ttk.Frame`。搜索过：用到 `left_zone` 的只有 `desktop.py` 第 349 行（把用量指示摆进去）和几条测试（比对父控件的路径），没有读它背景色的代码。
- 需求点没有提用量指示的字号。全栏同一字号是用户要的「文字格式要统一」，所以把它从 8 号改成了 10 号；这一处连同那条被改期望的测试，需求机动窗口 22:15 同意过。

## 如实说明

- 没有在真实的应用窗口里看过。依据是隐藏桌面上的自测和上面那两张样例图。
- 这一轮动了登记表和门禁期望：`_layers.py` 加一条同层边、`NATIVE_BASELINE` 下调、`test_ui_batch3_shell.py` 一处期望值。按验收窗口定的边界，这几处请验收窗口亲自读。
- `AGENTS.md` 的验证表写着层级登记表改动在合入主干前触发当次全量。用户 19:52 决定验证期间不跑全量，本窗口没有跑；合入前怎么办由验收窗口定。
- 段宽上限 28 的单位是字符单位（本机 8 像素一个，上限 224 像素），中文大约十六个字（按样例图里的宽度估的）。改前每段固定 24 个字符宽（196 像素）。所以每一段都到上限的最坏情况下，左区比改前宽；一般情况窄得多（样例里 646 对 1131）。
- 用量指示三项的字色没动，还是正文色（Token 一项按用量变色），比两边弱化灰的段深。要不要也弱化没有人定。
- 「就绪」紧跟在最后一段后面，中间只有留白、没有分隔符，读起来像最后一段的一部分（见改后的样例图）。两种改法：两区之间也放一个分隔符，或者把消息靠右对齐。需求点没有要求，没做，供需求机动窗口定。
- 直接摆进左区的外来控件，摆不摆出来由它的主人定，状态栏只管它的位置、两侧留白和分隔符；判断它有没有内容用的是「宽度不到 2 像素」。
- 页面拿到段标签以后直接改标签文字（不经过 `set_segment`）的话，空和非空的切换状态栏不知道。搜索过：页面都是经 `set_status_segment`、`bind_status_segment` 写的，没有直接改标签文字的地方；`ui/desktop_script_pages.py` 第 534 行只是把段标签另存一个名字，没有往里写。
- `-k idea_chat ui_edges_pages` 两组在这条车道上红 5 条，改字号前后两次都是同样 5 条：`test_ui_edges_pages` 1 条（`('headings',) != ('tree', 'headings')`）、`test_idea_chat` 4 条（3 条 `'stage-group:script' not found in …`，1 条 `'项目文件 · 剧本准备' != '项目文件'`）。都是文件面板的断言，是主干基线 `f624a5fc` 上已知的过期用例（FIX-PANEL-TESTS 在修），没有状态栏的断言。所以提交时没有点名这两组。本窗口没有在不带本轮改动的代码上单独跑这两组做对照，依据是验收窗口 21:50 的复验结论和 FIX-PANEL-TESTS 的任务书。
- 补跑的另外 5 组里 `test_pet_ui` 红 2 条（`FrameBatchSeamTests` 的两条），报错是 `ValueError: 未找到 FFmpeg 解码器`（`domain/keyframe_evidence.py`），这台机器的车道里找不到 FFmpeg，出错的地方不经过状态栏。改前红不红，本窗口没有对照过。所以提交时也没有点名 `pet_ui`。
- 架构门禁的输出里有两行「[棘轮提示] LR-09、LR-10 实测 59 < 基线 60」，改前就有（R4005、R4024、R4088 的结果文件都记过），本轮没有动 `层间合规清单.json`。
- 13 组那一遍的输出里有 24 行 `invalid command name "…"`（窗口销毁以后 `after` 定时器才到点），名字是 `start_account_renewal`、`start_update_check`、`check`、`_apply_idea_send_state` 四种，不是失败，也都不是状态栏登记的回调（状态栏的回调登记名以 `_wrap` 结尾，输出里没有）。`start_account_renewal` 那一种 R4088 的结果文件记过是既有的；另外三种改前有没有，本窗口没有对照过。
- 主干已经走到 `67068467`（R4105，UX-D3 合入；22:49 查的），这条车道还在 `f624a5fc` 上，没有跟着变基。
- 没有新建工作目录；测试进程降到 BelowNormal 优先级。

## 命令与退出码

工作目录都是车道的 `程序`，`PY` 指 `..\..\..\..\运行环境\Python\python.exe`；时间是 2026-11-22 本机时钟。「定稿内容」指改完字号以后、和提交内容相同的工作区。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `PY -X utf8 -B 维护记录\基准脚本\round_claim.py next`（当晚早些时候，时间没有记下） | 0 | 领到轮次 4091 |
| `PY -B run_selftests.py -k ui_status_bar`（22:11:50–22:12:01，新用例加新实现） | 0 | 19 条全过 |
| 同一条命令（22:12:19–22:12:30，`ui/ui_status_bar.py` 临时换回 `HEAD` 的内容） | 1 | 19 条，9 条红 |
| `PY -B run_selftests.py -k usage_indicator_ui`（22:13:43–22:13:52，用量指示的留白还没改） | 1 | 10 条，2 条红 |
| `PY -B run_selftests.py -k usage_indicator_ui`（22:34:02–22:34:22，用量指示的字体还没改） | 1 | 11 条，1 条的 3 个子项红 |
| `PY -B run_selftests.py -k` 加 13 个文件名（22:34:56–22:36:40，定稿内容）：`ui_status_bar` 19、`writing_status_line` 7、`ui_batch3_shell` 8、`usage_indicator_ui` 11（这四组是卡面的验收命令，共 45 条），`ui_token_contract` 6、`pet_agent_error_wiring` 10、`account_entry` 3、`frame_sources` 4、`desktop_page_nav` 2、`window_resize_coalescing` 9、`media_page_buttons` 5、`desktop_compact_layout` 5、`desktop_startup_perf` 17 | 0 | 「共 106 条用例」「0 个文件有红」 |
| `PY -X utf8 -B smoke_test.py --architecture`（22:36:40–22:42:19，定稿内容） | 0 | `Ran 700 tests in 337.817s`，`OK` |
| `PY -B run_selftests.py -k idea_chat ui_edges_pages`（22:42:19–22:44:58，定稿内容） | 1 | 226 条，5 条红，都是文件面板的过期用例（见「如实说明」） |
| `PY -X utf8 -B smoke_test.py`（22:44:58–22:44:59，定稿内容） | 0 | 通过 9 项、失败 0 项 |
| `PY -B run_selftests.py -k desktop_media_pages pet_ui timers ui_batch5_stage_panel_and_script_page ui_style_engine`（22:47:02–22:48:07，定稿内容） | 1 | 642 条，2 条红，都是 `test_pet_ui` 里找不到 FFmpeg 的（见「如实说明」）；`test_timers` 9、`test_ui_batch5_stage_panel_and_script_page` 4、`test_desktop_media_pages` 3、`test_ui_style_engine` 13 全过 |
| 提交工具点名的测试 | 见第二行的戳 | 提交时由工具跑 |

改字号之前还跑过一遍（那时的内容和定稿只差字号这一处）：卡面四组 44 条全过（22:14:56–22:15:19）；架构门禁 `Ran 700 tests in 463.899s`、`OK`（22:15:48–22:23:34）；另外九组 61 条全过（22:24:25–22:25:48）；`idea_chat ui_edges_pages` 226 条、同样 5 条红（22:26:26–22:32:28）。

## 未覆盖项

- 未跑全量自测：用户 2026-11-22 19:52 决定验证期间不跑全量。
- 没有在真实应用窗口里看；没有试过把窗口拉得很窄时两区怎么挤。
- 各段文字的写法这次按需求点没有改。看到的不一致列在这里，供需求机动窗口受理：
  - `path` 段写的是项目完整路径，长路径会到上限被截断（悬停有全文）。
  - 「当前模型：」「当前 JSON：」带前缀，页名段、用量段不带。
  - `script_note` 是一整句流程说明，会到上限被截断。
  - 视频页的页名段自己带「 · 」（`ui/desktop_media_pages.py` 第 594、637 行，如「视频生成 · 线上生成」），和段间分隔符是同一个符号，看上去像两段。
  - 用量指示的字色、「就绪」和最后一段之间没有分隔符（见「如实说明」）。
- 未 push、未 merge、未改主工作区；复核、验收、合入归验收窗口。

## 合入后用户怎么看

打开任意项目，看窗口最下面一行：页名、项目路径、Token 和金额、模型这几段之间都是一个小圆点，圆点两边的空一样宽；各段字号一致；没有大块空白；右边的「就绪」能完整显示。项目路径很长时，路径那一段最多占 28 个字符宽，超出的截断，鼠标停上去能看到完整路径。

## 提交

本文件随 R4091 的提交一起入库（分支 `codex/ux-status-bar`）。写本文件时提交号还没有产生，提交号见 `git log` 和会话接续记录里编码窗口一节。
