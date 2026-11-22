# R4087 结果：整页定高只收回当前页自己的表格高度（收着的缓存页、对话框里的表格不再从这一页里扣）
<!-- round-evidence: {"commit_base": "7ea1ddeb", "credential_hits": 0, "evidence_sha256": "30cf219b07bf39d9", "exit": 0, "failed": 0, "passed": 75, "round": 4087, "tests": "run_selftests.py -k ui_edges_tables desktop_compact_layout ui_edges_pages window_resize_coalescing"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮。任务卡 W4-GROWABLE-EXTRA（队列项 GROWABLE-EXTRA），车道 codex/table-height-scope，基准 7ea1ddeb。来源：未完成任务清单里的欠账，验收窗口点名给需求受理／机动执行窗口。现象：窗口不够高、页面要滚动才看得全时，当前页被压进比自己内容还矮的高度里，底部一段被挤掉，也滚不到。条件是程序里别处还有一张行数多于 2 行的表格活着：整页缓存收起来的初步分镜页（它的表格保持上次显示时的行数），或者一个开着的对话框。根因：`responsive_ui.growable_extra()` 把登记表里全程序所有活着的表格多出来的行加在一起，`LayoutMixin._fit_content_now` 拿「当前页的请求高度减去这个数」当这一页最少要多高；别的页和对话框里的表格并不在当前页的请求高度里，却从里面扣掉了。复现：先写测试，产品不改时 4 条里 1 条失败、3 条报错；全部写完后在进程内把定高那一处换回「全程序都算」的旧算法，5 条里 2 条失败（见「命令与结果」）。真实页面上量到的数（夹具项目）：窗口 1008×900 时打开初步分镜页，切到结构剧本页，再把窗口缩到 1008×700——结构剧本页自己要 651 像素，旧算法定成 505，少 146 像素，改后是 651。
- （二）测试跑了吗、三个基线：新增 5 条（`tests/test_ui_edges_tables.py` 的 `GrowableScopeTests`）。产品不改时前 4 条 1 失败 3 报错；改后连同该文件原有的 `AutoHeightScrollbarTests`、`RowHeightTests` 和 `test_window_resize_coalescing.LayoutConvergenceTests` 共 11 条全过；加上第 5 条（真实桌面）后，换回旧算法 2 条失败，最终代码 5 条全过。架构门禁在全部改动之后整套跑过，696 条全过。默认冒烟没有单独跑；全量自测没跑（用户验证期间各窗口不跑全量）。带界面的 `run_selftests.py -k ui_edges_tables desktop_compact_layout ui_edges_pages window_resize_coalescing` 由提交工具在提交时跑，结果以本文件的证据行为准。
- （三）欠账少了吗：少了一条（未完成任务清单里的这一项）。没有新增欠账；没做的事见「如实说明」和「未覆盖项」。

## 改了哪些文件

- responsive_ui.py：`growable_extra()` 改成 `growable_extra(scope=None)`。给了 scope 就只数它底下的表格（按控件路径前缀判断，前缀带上分隔的点，`.!frame` 不会把 `.!frame2` 底下的算进来）；不给 scope 和原来一样全数；销毁了的表格不论在不在范围里都从登记表里清掉。9 行新增、1 行删除，全文 779 行。
- ui/desktop_layout.py：`LayoutMixin._fit_content_now` 里那一处调用改成 `growable_extra(self.content)`，加一行注释。2 行新增、1 行删除，全文 397 行。
- tests/test_ui_edges_tables.py：新增 `GrowableScopeTests` 5 条。142 行新增，全文 897 行。
- tasks_round/tasks_round_4087_result.md 是本文件。

新增的 5 条：

- `test_only_tables_under_the_scope_are_counted`：两个内容框各有表格，只数给定内容框底下的（含嵌在里层的）；不给范围仍是全数。
- `test_a_sibling_whose_name_starts_the_same_is_outside`：名字是 page 和 page2 的两个兄弟框，量 page 时不把 page2 底下的算进来。
- `test_destroyed_tables_are_dropped_whatever_the_scope`：销毁了的表格即使不在范围里，也从登记表里清掉。
- `test_page_fit_ignores_tables_on_pages_that_are_put_away`：用真的 `LayoutMixin._fit_content_now`，两页各有一张表（10 行、30 行），定高只扣正在显示那一页的；换页后扣的是换上来那一页的。
- `test_a_real_page_keeps_its_height_after_the_storyboard_page_is_put_away`：真的 `Desktop` 加夹具项目，先显示初步分镜页，再切到结构剧本页并把窗口缩矮，滚动区高度等于这一页自己的请求高度减去这一页自己的可收回高度。前提（页码、缓存页还活着且不是当前页、缓存页确有可收回高度、这一页确实比画布高）都先断言。

## 命令与结果

下表里的 unittest 都是在车道的 程序 目录下跑的：环境变量 PYTHONPATH=tests、DRAMA_SUPPRESS_MODAL=1、DRAMA_SUPPRESS_NETWORK=1，经 `scripts\gui_hidden.py` 放在隐藏桌面上（不在用户屏幕上开窗口），进程优先级降到 BelowNormal。

| 命令 | 结果 |
| --- | --- |
| python.exe -B scripts\dev.py claim | 领到轮次 4087 |
| python.exe -B -m unittest -v test_ui_edges_tables.GrowableScopeTests（只写了测试、产品未改，当时 4 条；19:56:59） | 「Ran 4 tests in 0.132s」「FAILED (failures=1, errors=3)」：3 条「TypeError: growable_extra() takes 0 positional arguments but 1 was given」；定高那条「AssertionError: 456 != 736」 |
| python.exe -B -m unittest -v test_ui_edges_tables.GrowableScopeTests test_ui_edges_tables.AutoHeightScrollbarTests test_ui_edges_tables.RowHeightTests test_window_resize_coalescing.LayoutConvergenceTests（产品改完；19:57:22） | 「Ran 11 tests in 1.608s」「OK」 |
| python.exe -B （临时脚本：进程内把 `desktop_layout.growable_extra` 换成不分范围全数的旧算法，再跑 GrowableScopeTests；不改任何文件；19:59:55） | 「Ran 5 tests in 7.099s」「FAILED (failures=2)」：真实桌面那条「AssertionError: 505 != 651」；定高那条「AssertionError: 456 != 736」 |
| python.exe -B -m unittest -v test_ui_edges_tables.GrowableScopeTests（最终代码；20:00:02） | 「Ran 5 tests in 6.311s」「OK」 |
| python.exe -B smoke_test.py --architecture（全部改动之后；优先级 BelowNormal；20:00:48–20:07:29） | 「Ran 696 tests in 395.676s」「OK」「✅ 架构治理测试：tests/architecture」，退出码 0 |
| git diff --shortstat | 3 个文件，153 行新增、2 行删除（不含本文件） |

真实页面实测（临时探针脚本：夹具项目、真的 `Desktop`、隐藏桌面；对每一页把旧算法和新算法各算一遍，产品文件不动）。结构剧本页自己要 651 像素：

| 窗口（画布高） | 收着的初步分镜页两张表的行数 | 被多扣的高度 | 结构剧本页定成多高 |
| --- | --- | --- | --- |
| 1008×900（705） | 8、7 | 264 | 旧 705、新 705：本来就放得下，没有差别 |
| 800×600，最小窗口（405） | 2、2 | 0 | 旧 651、新 651：表格已缩到下限 2 行，没有差别 |
| 1008×700（505） | 3、3 | 48 | 旧 603、新 651：少 48 |
| 先在 1008×900 显示初步分镜页，切页后缩到 1008×700（505） | 显示时 8、7，收起后没有再量 | 至少 146 | 旧 505、新 651：少 146（第 5 条测试的场景） |

## 如实说明

- （一）范围是按控件路径前缀筛的：登记表仍是全程序共用的一张，`growable_extra(scope)` 只数路径以「scope 的路径加一个点」开头的表格。不给 scope 的调用保持原行为。产品里调用 `growable_extra` 的只有 `_fit_content_now` 这一处（`desktop.py` 只是把名字导入进来，没有调用，本轮没动）。
- （二）对话框和独立窗口里的表格从此不再从主页面里扣。用 `auto_height` 登记表格的地方有 7 处：3 处在页面里（`ui/desktop_asset_pages.py`、`ui/desktop_storyboard_page.py`、`ui/storyboard_table_ui.py`），4 处在对话框或独立窗口里（`ui/version_picker.py`、`ui/desktop_project_pages.py` 的回收站恢复对话框、`ui/pet_models_ui.py` 的模型管理窗口、`ui/local_previs.py` 的本地预演窗口）。后 4 处以前开着时会让主页面多扣一截，现在不会；这一点只有范围测试间接覆盖，没有给对话框单独写用例。本轮没有改这些对话框和窗口自己的布局。
- （三）影响有多大：只在「窗口不够高、当前页要滚动」而且「别处有超过 2 行的表格活着」时才看得出来。最小窗口 800×600 下初步分镜页的表格本来就缩到 2 行，量到的差别是 0；量到有差别的是上表后两行（48 和 146 像素）。用的是夹具项目，真实项目里表格行数不同，数字会不一样。
- （四）第 5 条测试依赖夹具项目和真的 `Desktop`：它先断言自己的前提，前提不成立时会失败而不是空过。窗口大小是在 `Desktop` 建好之后设的（`Desktop` 建窗时会按自己的规则摆放窗口）。
- （五）没有在用户的真实项目里点过，验证都在夹具项目和隐藏桌面上。
- （六）没有改文档：在 docs、architecture.md、runbook.md 里搜过「可收回」「整页定高」「growable」，没有命中，没有要同步的条文。
- （七）本轮由需求受理／机动执行窗口直接写代码。按窗口协调第 10 条，除验收窗口复核和 `verify` 外，还要加一张只读审查卡。
- （八）认领时把队列项的允许修改文件加了 `程序/ui/desktop_layout.py`（调用处在这里，不改它范围传不进去），验收命令的关键词加了 `window_resize_coalescing`（它的用例直接走 `_fit_content_now`）。对应的合入项 MERGE-GROW 的命令没有改，还不含 `window_resize_coalescing`，请验收窗口合入时留意。19:52 核过：当时未合入的各车道没有改这三个文件的。
- （九）上表里几次几秒钟的 unittest 是经 `scripts\gui_hidden.py` 直接放到隐藏桌面跑的，没有排界面令牌（每次 0.1–8 秒）；正式的带界面定向测试由提交工具经 `run_selftests.py` 排令牌跑。

## 未覆盖项

- 未跑全量自测；未跑默认冒烟；未在用户的真实项目和真实界面上验证；未 push、未 merge。
- 对话框和独立窗口里的表格不再影响主页面这一点，没有单独的用例（见「如实说明」第（二）条）。
- 实测表第 4 行的场景里，初步分镜页收起后表格的行数没有再量，只量到结果（505 对 651）。
