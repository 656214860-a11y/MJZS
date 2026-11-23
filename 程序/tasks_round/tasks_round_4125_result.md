# R4125 结果：FLAKY-PANEL-STAGES 文件面板阶段测试的固定等待改成等索引画完（只改测试）
<!-- round-evidence: {"commit_base": "a1d9c565", "credential_hits": 0, "evidence_sha256": "886ed0df50c744ac", "exit": 0, "failed": 0, "passed": 163, "round": 4125, "tests": "run_selftests.py -k files_panel"} -->

## 开头三问

（一）本轮属于哪种类型：测试修复轮——只改 `tests/test_files_panel_stages.py` 一个测试文件的等待方式，任务卡 W6B-FLAKY-PANEL-STAGES（任务书：验收窗口；派卡：推进预备窗口）。车道目录 doc-stages-c，分支 codex/flaky-panel-stages，基准 a1d9c565。

（二）测试跑了吗、三个基线：

- 点名测试 `run_selftests.py -k files_panel` 按卡跑了 3 遍：每遍 163 条用例、0 个文件有红、退出码 0、输出 ALL TESTS PASSED（耗时 273.8 / 277.5 / 296.7 秒）。
- 改动的单个测试文件 `run_selftests.py -k files_panel_stages`：改前 150 条、211.8 秒、0 红；改后 150 条、273.4 秒、0 红，退出码均 0。
- 架构门禁 `smoke_test.py --architecture`：实测 700 条，453.8 秒，OK，失败集合为空，退出码 0。
- 默认冒烟没单独跑；全量自测（--all --safe）没跑。
- 没有新增、删除、跳过任何用例；没有改任何断言（diff 里全是 pump→wait_index 的原行替换）。

（三）欠账少了吗：这个测试文件机器忙时随机红的原因（触发索引重读后固定等零点几秒就断言）改掉 12 处（含 setUp 1 处）。基类 12 条用例在 7 个子类名下重复跑的结构没动（留给验收窗口决定）。新增欠账：无；拿不准未改的 2 处见「没有改的各处」末尾。

## 原因和派卡窗口的探针

原因（执行者复述）：面板换阶段或刷新时 `_request_index`（`ui/desktop_files_panel_index.py:163`）先清空列表、置 `_index_loading`，把读索引交给后台队列，结果回来后由 `_start_index_render`（同文件 :207）分批 `after(1)` 插行。变红的几条用例在 `show_stage`／`refresh_file_index` 之后只 `pump(.2/.4)` 就断言，机器忙时后台读索引还没回、列表刚被清空，断言看到空列表。

探针是派卡窗口跑的，执行者没有跑，原文照抄：

> 探针做法：在测试进程里把 ui.desktop_files_panel_index.load_index 包一层，先睡 0.8 秒再调原函数，经隐藏桌面、拿着界面令牌，用测试执行器自己的单元执行函数只跑这三条（StageRailTests 名下两条、IndexLifecycleTests 名下一条）。基准 a1d9c565、没有改动时：放慢 0.8 秒（2026-11-22 23:40:34 至 23:40:45）跑 3 条、3 条全红，报错原文是 AssertionError: 'stage-group:script' not found in ()、AssertionError: Tuples differ: () != ('05资产管理/assets/CHAR_001.png',)、AssertionError: '05资产管理/assets/外部新增.md' not found in []，和验收窗口看到的失败是同一种；对照（同一个探针不放慢，23:41:10 至 23:41:21）跑 3 条、3 条全绿。改后的探针、把改好的一处改回去的反向验证、和架构门禁同时跑的两遍，由派卡窗口在验收时做，不在本卡范围。

## 逐处改动清单

全部是把一行 `self.pump(...)` 原地换成 `self.wait_index()`（缩进不变，行数不变；等待语义：任务队列里没有「文件索引」「素材库」任务且 `_index_render_job`、`_index_loading` 都为空，测试文件 :74–83）。行号为改前基准行号（原地替换后行号不变）。

| 行号 | 所在用例／位置 | 改前 | 改后 | 触发调用 → 到 `_request_index` 的同步路径 |
| --- | --- | --- | --- | --- |
| 68 | `StageRailTests.setUp` | `self.pump(.3)` | `self.wait_index()` | `open_panel()`（`ui/desktop_files_panel.py:328`）→ `_reload_current_view`（`panel:348→313`）→ `_fill_index_list`（`filters:548→550`）→ `_request_index`（`index:163`） |
| 213 | `test_clicking_a_stage_fills_the_list_from_the_index` | `self.pump(.2)` | `self.wait_index()` | `show_stage('assets')`（`filters:539`）→ `_reload_current_view`（`filters:546`）→ `_fill_index_list` → `_request_index` |
| 233 | `test_all_returns_to_grouped_project_index` | `self.pump(.2)` | `self.wait_index()` | `show_stage('assets')` 同上链 |
| 235 | 同上 | `self.pump(.4)` | `self.wait_index()` | `show_stage(None)` 同上链（两次换阶段各等一次） |
| 577 | `test_group_modes_keep_status_keyword_and_global_library_filters`（`with patch` 块内原地改） | `self.pump(.2)` | `self.wait_index()` | `_apply_filters`（`filters:168`）→ `_reload_current_view`（`filters:181`）→ `_fill_index_list` → `_request_index` |
| 604 | `test_missing_cache_rebuild_runs_off_tk_thread`（`with patch` 块内原地改） | `self.pump(.4)` | `self.wait_index()` | `fill_script_list`（`panel:417`）→ `_reload_current_view`（`panel:420`）→ `_fill_index_list` → `_request_index` |
| 705 | `test_group_order_sort_missing_and_real_thumbnail` | `self.pump(.5)` | `self.wait_index()` | `_apply_filters` 同 577 链（其后原有的一行 `wait_index()` 保留，等于连等两次，第二句立即返回） |
| 741 | `test_selected_filtered_file_recycles_without_deleting_project`（`with` 块内原地改） | `self.pump(.2)` | `self.wait_index()` | `delete_script`（`panel:617`）→ `delete_index_files`（`panel:620`）→ `_reload_current_view`（`index:386`）→ `_request_index` |
| 821 | `test_refresh_discovers_external_file_and_retains_script_actions` | `self.pump(.4)` | `self.wait_index()` | `refresh_file_index`（`index:142`）→ `_reload_current_view`（`index:145`）→ `_fill_index_list` → `_request_index` |
| 970 | `test_global_first_scan_runs_in_background_and_filters_keep_library`（`with patch` 块内原地改） | `self.pump(.3)` | `self.wait_index()` | `show_library`（`filters:235`）→ `_fill_global_list`（`filters:255→257`）→ `_request_index(library, library=True)`（`filters:260`） |
| 976 | 同上 | `self.pump(.3)` | `self.wait_index()` | `_apply_filters` → `_reload_current_view` → `_fill_global_list`（`library_view=True`）→ `_request_index` |
| 1051 | `test_library_view_lists_library_relative_rows` | `self.pump(.3)` | `self.wait_index()` | `show_library` 同 970 链 |

## 没有改的各处

| 行号 | 所在用例／位置 | 等的是什么 | 不改理由 |
| --- | --- | --- | --- |
| 66 | `StageRailTests.setUp` | 换页后、面板收着时 | 卡面明确不改 |
| 79 | `wait_index` 方法体 | 轮询泵 | 禁改等待方法体 |
| 120 | `test_scroll_rail_requests_minimum_width_without_geometry_feedback` | `win.geometry` 后布局 | 量按钮宽，不读列表 |
| 131 | 同上 | 10 次重采样 `script_tree` 高 | 几何测量 |
| 136 | 同上 finally | 恢复窗口尺寸 | 收尾几何 |
| 186 | `test_stage_rail_scrolls_vertically_when_window_is_short` | `open_panel` 后布局 | 之后只量画布／按钮几何，不读列表 |
| 191 | 同上 | `win.geometry('560x380')` | 几何 |
| 198 | 同上 | `yview_moveto` 滚动 | 滚动绘制 |
| 206 | 同上 finally | 恢复窗口尺寸 | 收尾几何 |
| 259 | `test_project_change_resets_the_stage_filter` | `show_stage('video')` 后一拍 | 之后只断言 `stage_filter` 与按钮样式，不读列表 |
| 262 | 同上 | `project_changed()`（root 不同→收起＋复位） | 断言均同步状态，不读列表 |
| 278 | `FilterBarTests.setUp` | 换页后、面板收着时 | 此刻 `_open=False`，`_request_index` 在 `index:166` 直接返回，无索引可读 |
| 280 | `FilterBarTests.setUp` | `open_panel` 触发后一拍 | 其后到下次触发前没有列表读取（各用例自身先触发再等），按契约规则(3)不改 |
| 389 | `FilterDedupTests._restore_panel` | `win.geometry(old)` 收尾 | 几何；同函数内 `refresh_file_index` 后已有 `wait_index` |
| 404 | `test_filter_controls_sit_on_two_rows_at_wide_window` | `win.geometry('1280x800')` | 量控件顶边坐标 |
| 427 | `test_each_dropdown_fully_shows_current_value` | `win.geometry(size)` | 量下拉框宽 |
| 450 | `test_group_sort_pair_wraps_aligned_with_kind_box` | `win.geometry('880x600')` | 量标签左缘 |
| 467 | `test_clicking_stage_icon_updates_panel_title` | 图标钮 invoke 后一拍 | 断言 `script_title` 文本（`show_stage` 内 `_sync_stage_title` 同步写好），不读列表 |
| 472 | 同上 | 回到「全部」后一拍 | 同上 |
| 613 | `wait_for_index` 方法体 | 轮询泵 | 禁改等待方法体 |
| 637 | `test_late_result_after_collapse_is_discarded` | `release.set()` 后等迟到结果被丢弃 | 契约规则(1)：用例用 `threading.Event` 打桩 `load_index`，等的就是后台相关中间状态 |
| 656 | `test_late_result_after_project_switch_is_discarded` | 等后台 `slow` 进入 `release.wait` | 同上，规则(1) |
| 659 | 同上 | 等迟到结果被丢弃 | 同上，规则(1) |
| 682 | `test_render_is_batched_and_collapse_cancels_pending_rows` | `collapse` 后一拍证明批次渲染已停 | `collapse` 只取消不触发重读；等的是「渲染已取消」的时间窗，规则(3) |
| 780 | `test_four_script_categories_keep_adoption_confirmation_and_history` | `see(item)` 滚动后量 `bbox` | 几何；行存在已由前一句 `wait_for_index` 保证 |
| 981 | `test_global_first_scan_runs_in_background_and_filters_keep_library` | `show_stage(None)` 后一拍 | 之后断言 `library_view`、`status_box` 状态（均为同步写好的状态），不读列表 |
| 1256 | `test_long_filename_fully_visible_at_wide_window` | `win.geometry('1280x800')` | 几何；行存在已由 `_seed_long_file` 内 `wait_index` 保证 |
| 1268 | 同上 finally | 恢复窗口尺寸 | 收尾几何 |
| 1279 | `test_long_filename_middle_elided_at_narrow_window` | `win.geometry('880x600')` | 同上 |
| 1294 | 同上 finally | 恢复窗口尺寸 | 收尾几何 |
| 1305 | `test_table_never_scrolls_horizontally` | `win.geometry(size)` | 量 `xview` 滚动范围 |
| 1312 | 同上 finally | 恢复窗口尺寸 | 收尾几何 |
| 1324 | `test_no_column_half_visible` | `win.geometry(size)` | 量列宽合计 |
| 1336 | 同上 finally | 恢复窗口尺寸 | 收尾几何 |
| 1373 | `test_elided_row_opens_the_full_filename` | `win.geometry('880x600')` | 几何 |
| 1389 | 同上 finally | 恢复窗口尺寸 | 收尾几何 |

拿不准、单列的 2 处（不改）：

- 行 1076 与 1080（`test_index_view_shows_preview_and_meta_columns`）：`show_stage('assets')`／`show_stage(None)` 后断言 `script_tree.cget('show')` 与 `heading('meta')` 文本。「show」确实由 `_start_index_render`（`index:209/227`）按渲染结果写，但表头文本在构建期写好（`panel:267`），且本用例期望的 `'tree headings'` 与 setUp 全量视图渲染留下的值相同——等不等都不影响断言结果；它不属于卡面枚举的列表内容读取（`get_children`/`rows`/`script_row_category`/`script_row_details`/`_index_rows`/行操作）。拿不准是否算「断言列表内容」，按「拿不准就不改」处理，留给验收窗口裁决。

## setUp

改了：`StageRailTests.setUp` 第 68 行 `self.pump(.3)` → `self.wait_index()`。

依据：`open_panel()`（`desktop_files_panel.py:328`）在有项目、入口允许时当场走到 `_request_index`——`:332` 置 `_open=True`，`:348` 调 `_reload_current_view`（`:313`）→ `_fill_index_list`（`filters:548`）→ `_request_index`（`index:163`），`:169` 同步置 `_index_loading=True`。setUp 里页面已切到 `PAGE['script']`（`_entry_allowed` 满足，`panel:280`）、项目根存在，不命中 `:166` 的提前返回。

没改的相邻行：setUp 第 66 行 `self.pump(.2)`（换页后、面板收着时，卡面明确不改）；`setUpClass` 的 `cls.pump(2)`（第 44 行）不改。

耗时对比（同一测试文件 `-k files_panel_stages`）：改前 150 条、211.8 秒、0 红；改后 150 条、273.4 秒、0 红（改后这一遍开头排跨树 GUI 令牌约 30 秒以上，且 `wait_index` 逐处轮询比原固定短等慢，属预期）。

## 两件核对

1. `wait_index()` 会不会在索引「还没开始」时提前返回——确认卡面所述，并逐处核了路径：
   - `_request_index` 在调用当场（`index:169`）就把 `_index_loading` 置真，之后才 `submit`（`index:191–192`）；同步触发的调用返回时 `_index_loading` 已为真，`wait_index` 不会提前返回。
   - `task_queue.labels()` 只含排队中任务（`orchestrator/desktop_automation_service.py:300–305` 的 `labels()`；`async_queued` 在 `ui/desktop_async_tasks.py:33–44` 空闲时经 `async_` 直接开跑、不进入 `labels()`）；运行中的任务由 `_index_loading` 覆盖，批次渲染由 `_index_render_job` 覆盖，三路都在 `wait_index`（测试文件 :80–81）的判定里。
   - 提前返回只在 `index:166–167`（`root is None or not self._open`）——本轮改的每一处触发时 `_open=True`、`root` 非空，不命中。
   - `done` 在结果过期时（`index:183–184`）提前返回、不把 `_index_loading` 置假；置假靠下一次 `_invalidate_index_load`（`index:131–140`）——与卡面一致。
   - 各改动处的触发与同步链路见「逐处改动清单」最右列。
2. 基类重复跑的数字：基类 `StageRailTests`（:25–266）有 12 条 `def test_`；整个文件实测跑 150 条（`run_selftests.py -k files_panel_stages` 输出「共 150 条用例」）。7 个子类（FilterBar/FilterDedup/IndexLifecycle/DockContent/GlobalLibraryView/FileActions/FilenameDisplay）各自把基类 12 条再跑一遍＝84 条；加上基类自己 12 条，基类用例合计 96 条，按条数约占 150 条的 64%（估，按条数比例，未按各路实测耗时加权）。是否去重由验收窗口另行决定，本卡未动继承结构。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git -c core.quotepath=false status --porcelain` | 0 | 无输出（工作树干净） |
| `git log -1 --format=%h` | 0 | `a1d9c565` |
| `git rev-parse --abbrev-ref HEAD` | 0 | `codex/flaky-panel-stages` |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k files_panel_stages`（改前） | 0 | 150 条，211.8 秒，0 个文件有红，ALL TESTS PASSED |
| `git -c core.quotepath=false diff --numstat` | 0 | `12  12  程序/tests/test_files_panel_stages.py`（增删相等，单文件） |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k files_panel_stages`（改后） | 0 | 150 条，273.4 秒，0 红，ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k files_panel`（第 1 遍） | 0 | 163 条，273.8 秒，0 红，ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k files_panel`（第 2 遍） | 0 | 163 条，277.5 秒，0 红，ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k files_panel`（第 3 遍） | 0 | 163 条，296.7 秒，0 红，ALL TESTS PASSED |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | `Ran 700 tests in 453.755s` → `✅ 架构治理测试：tests/architecture` `OK`，失败集合为空 |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 输出 `4125`，本轮 R4125 |

如实备注：同一测试命令最初两次发出时因命令会话停在车道根目录（不在 `程序` 子目录）报 CommandNotFoundException（退出码 1），按卡面把执行目录切到 `程序` 后原样重跑成功；除此之外所有项目命令一次通过，无权限拒绝。

## 如实说明

- 只改了断言之前的等待：12 处 `self.pump(...)` 原行换成 `self.wait_index()`；没有改任何断言、没有改产品代码、没有动 `wait_index`/`wait_for_index`/`pump`/`rows` 的方法体、没有动继承结构。
- `wait_for_index` 仍留在 `IndexLifecycleTests`（:610–614），本轮没有别处需要它，未搬动。
- 与卡面不一致处：无（卡面说 50 处 `self.pump(`，实测 50 处；必改 4 处行号与内容均与基准一致）。
- 结果文件不写用户名与个人信息；用户目录一律写 %USERPROFILE%。

## 未覆盖项

- 改后的探针、把改好处改回去的反向验证、与架构门禁并行带负载的两遍——按卡面由派卡窗口在验收时做，本卡未做。
- 全量自测（`--all --safe`）没跑；默认冒烟没单独跑。
- `tests/test_files_panel.py` 里「Esc 收起」那条与别的文件连跑时的顺序敏感红不在本卡范围（会话接续记录欠账第 4 条已有记载）。
