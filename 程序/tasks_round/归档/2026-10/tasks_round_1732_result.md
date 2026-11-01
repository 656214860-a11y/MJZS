# R1732：结构治理轮——三页 `_refresh_request_width()` 下沉 `responsive_ui.refresh_request_width`（WIDTH）

任务书：`WIDTH_taskbook.md`。执行者：opencode。工作目录：独立车道 `D:\漫剧制作助手\.wt\lane_width\程序`。
未执行任何 git 写命令，未领号，未提交，未改 `project_status.md`／`AGENTS.md`，未读 `private\`／`.env`，未打开真实用户项目。

## §7 三问

1. **本轮属于 §3 哪种类型？** 结构治理轮·执行（合并重复）。来源：R1725 结果文件 D 节第 5 条
   「建议后续把 `_refresh_request_width()` 下沉到 `responsive_ui`」，即
   `程序/tasks_round/tasks_round_1725_result.md:151`。只改任务书允许的 5 个文件＋本结果文件。
2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8 通过、0 失败**（见下方计数，含在 `--affected` 输出内）。
   - 任务书 `--affected` 命令通过：8 项快速检查通过；门禁定向 6 个测试文件、**220 条用例、285.3 秒、0 个文件有红**。
   - 任务书 `--architecture`：**368 条、141.0 秒、OK、0 红**（含 `test_full_safe_all_is_required_after_eight_source_rounds`，本轮该条也是 ok，未出现任务书预期的唯一红）。
   - 全量回归与欠账：本车道未领号、未提交，源码轮欠账由验收方计入；本轮未跑 `--all --safe`。
3. **`project_status.md` 的欠账少了吗？** 没有。本批不改状态页、不领轮次。

## A 三份实现逐行对比结论

**等价。三份逐字节相同。**

- 提取范围：`desktop_asset_pages.py:35–76`、`desktop_media_pages.py:41–82`、`desktop_storyboard_page.py:33–74`，各 42 行。
- 三份 SHA256 前缀一致：`4f6d66780512af74`，字节长度均 `1622`。
- 对比脚本（只读）输出：`asset==media: True  asset==storyboard: True`。
- 无差异 → 按任务书第 1 条，不触发「停下等裁决」，继续合并。

行为点核对（三份都具备，已逐行确认）：
- `refresh()`：仅当 `winfo_width()>1` 且 `winfo_reqwidth()>winfo_width()`，且宽度与上次不同，才重设一次 `displaycolumns`。
- `run()`：`after_idle` 回体，先清 `_request_refresh_pending`／`_request_refresh_after_id`，再用 `winfo_exists()` 守卫、`except tk.TclError` 兜底。
- `on_configure()`：忽略非本控件事件；`_request_refresh_pending` 去抖，同一时刻只挂一个 `after_idle`（不重复挂回调）。
- `on_destroy()`：`after_cancel` 取消挂起回调，再清两个标记（销毁时取消挂起回调）。
- 末尾 `tree.bind('<Configure>'/'<Destroy>', ..., add='+')` 并 `return tree`。

## B 改动（文件:行）

新公共函数 `refresh_request_width(tree)` 在 `responsive_ui.py`，函数体与原三份逐字一致（含上述四个行为点），
只把 `"""窄窗时…"""` 的 docstring 扩写为说明去抖与销毁取消；页面改为 import 公共函数。

| 文件 | 改动 |
| --- | --- |
| `程序/responsive_ui.py` | **新增** `refresh_request_width()`：**378–425**（`_bind_debounced_configure` 顺延至 **427**）。文件 684→**733** 行（≤1500 模块上限）。 |
| `程序/desktop_asset_pages.py` | import 增 `refresh_request_width`（**:17**）；调用点 **:409**（原 `:453`）；**删除**本地副本（原 35–76）。 |
| `程序/desktop_media_pages.py` | import 增 `refresh_request_width`（**:21**）；调用点 **:257**（原 `:301`）；**删除**本地副本（原 41–82）。 |
| `程序/desktop_storyboard_page.py` | import 增 `refresh_request_width`（**:14**）；调用点 **:91**（原 `:135`）；**删除**本地副本（原 33–74）。 |
| `程序/tests/test_column_fit.py` | 在既有 `ColumnFitTests`（已有登记在册的真 Tk 平台 skip）内**新增**辅助 **:188** 与两条用例 **:205**、**:219**。 |
| `程序/tasks_round/tasks_round_pending_WIDTH_result.md` | 本结果文件（新建）。 |

- 分层：`responsive_ui` 是新函数所在模块，只 import `app_logging`／`tkinter`，**不反向 import 任何页面**；三个页面本就 import `responsive_ui`，方向未变。
- 复用：未新建模块、抽象或配置项（任务书 §「最简改动」）。
- 删除后全仓已无 `_refresh_request_width` 引用（grep 0 命中）；四个文件 `py_compile` OK。

### 测试设计（`程序/tests/test_column_fit.py`）

放在既有 `ColumnFitTests` 内，复用其已登记在 `维护记录/skip台账.json` 的 `ColumnFitTests.setUp` 平台 skip（`PLATFORM_TKINTER`），
**未新增 skip、未改 skip 台账**（该台账不在允许改的文件内，故刻意避免新增 skip 条目）。
- `test_request_width_is_refreshed_when_columns_exceed_the_view`：真 Tk 窄容器（列宽 180×3 > 可视 220），断言 `<Configure>` 后 `displaycolumns` 恰好重设 1 次且值为 `tree['columns']`，并记下 `_request_refresh_width == winfo_width()`。
- `test_a_pending_callback_is_cancelled_when_the_tree_is_destroyed`：制造挂起 `after_idle`，`destroy()` 时断言 `after_cancel(pending)` 恰被调用一次、两个标记清空，销毁后再跑一遍事件循环不报错。

**先红后绿**：改动前（HEAD 版 `responsive_ui`，`git show HEAD:程序/responsive_ui.py` 只读导出后置于 `sys.path` 首位）
两条新用例均 ERROR：`AttributeError: module 'responsive_ui' has no attribute 'refresh_request_width'`（`errors=2`）。
改动后两条均 ok。

## C 验证（实际计数）

命令均为 `D:\漫剧制作助手\运行环境\Python\python.exe -B`，工作目录 `…\.wt\lane_width\程序`。原始日志在临时目录，未纳入版本库。

| 命令 | 实际结果 |
| --- | --- |
| `python -B smoke_test.py --affected responsive_ui desktop_asset_pages desktop_media_pages desktop_storyboard_page` | **通过 8 项／失败 0 项**；门禁 `run_selftests.py --serial -k …` 定向 6 个测试文件（`test_checkbox_column` 2、`test_column_fit` **19**、`test_row_targets` 15、`test_ui_batch4_desktop_project_pages` 3、`test_ui_edges` ×8 共 115、`test_video_ui` ×5 共 66）= **220 条用例、285.3 秒、0 个文件有红**，`ALL TESTS PASSED`。退出码 0。（未等 GUI 令牌超时，一次拿到。） |
| `python -B smoke_test.py --architecture` | **Ran 368 tests in 141.026s — OK**，**0 红**。任务书只允许 `test_full_safe_all_is_required_after_eight_source_rounds` 一红；实测该条也是 `ok`（本车道未领号/未提交，全量欠账未在此树计入），故本轮 `--architecture` 无红。退出码 0。 |
| `python -B -m unittest discover -s tests -p test_ui_batch6_pages.py` | **Ran 7 tests — OK**（R1725 覆盖资产页／首帧页真 Tk 几何的用例，改动后仍绿；`--affected` 未自动选中该文件，故手动补跑）。 |
| `python -B -m unittest discover -s tests -p test_storyboard_page_loading.py` | **Ran 5 tests — OK**（首帧页加载消费者）。 |
| 新增两条用例单跑 | **Ran 2 tests — OK**。 |
| 改动前（HEAD `responsive_ui`）两条新用例 | **Ran 2 tests — FAILED (errors=2)**，均为 `AttributeError: … 'refresh_request_width'` 不存在（先红证据）。 |

## D 需裁决事项

1. **`--architecture` 无红，与任务书「只允许一条红」的预期不符**：实测 368/368 全绿（含该条基线测试）。
   疑因本车道未提交、轮次欠账未计入该树；请验收方在隔离验证树复跑确认。**未出现任何红**，不属失败。
2. **公共函数命名**：按 `responsive_ui` 现有公共 helper 命名法（`auto_columns`／`fit_current_columns`／`bind_view_fit`）
   取 `refresh_request_width`（去掉下划线）。若验收方偏好其它名字，一行改名即可。
3. **是否补一条「不重复挂回调」断言**：任务书第 3 条把「不重复挂回调」列为须保持的行为，但第 5 条只要求覆盖
   「请求宽度会刷新」「销毁后取消挂起回调」两点；本批按其最简口径只写了这两条。若需显式钉住去抖
   （同一时刻只挂一个 `after_idle`），可再加一条用例，请裁决。
4. **`responsive_ui.py` 体积**：684→733 行，仍低于模块 1500 行上限、新函数 42 行低于函数 150 行上限，无需登记棘轮表。
5. **范围外未见新缺陷**。工作树仅本批 5 个文件被改（`git status --short` 只列这 5 个）。

## E 交付状态

**未提交。** 由 Claude（调度兼审查方）验收后提交；执行方未领号、未跑任何 git 写命令。
回滚方式：`git checkout -- 程序/responsive_ui.py 程序/desktop_asset_pages.py 程序/desktop_media_pages.py 程序/desktop_storyboard_page.py 程序/tests/test_column_fit.py`（由提交方执行）。

## 独立验收（Claude，主工作区）

- 车道 diff 干净应用到 R1731；全仓无 `_refresh_request_width` 残留。
- `run_selftests.py -k test_column_fit test_ui_batch6_pages test_storyboard_page_loading test_ui_batch4_desktop test_video_ui`：ALL TESTS PASSED（test_column_fit 19 条）。
- `smoke_test.py --architecture`：368 条，仅 `test_full_safe_all_is_required_after_eight_source_rounds` 1 红（全量欠账，后台补跑项）。车道里该条为绿，是因为车道未计入主线源码轮。
- 裁决：函数名 `refresh_request_width` 接受；「不重复挂回调」由逐字搬移保证，不另加断言。
