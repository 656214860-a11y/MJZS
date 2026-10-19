# R1746：结构治理轮——desktop.py 1949→1419 行，退出超限登记（SPLITD）

- **本轮类型**：§3.3 结构治理轮·执行（任务书 `SPLITD_taskbook.md` 派发，纯搬家，方法体逐字不改、`self` 语义不变）。
- **三个基线**：默认冒烟 **8/8** 通过；架构门禁 `smoke_test.py --architecture` **374/374 通过**（214.99 秒，0 红）；全量安全回归**未跑**（派发执行方不跑全量，欠账口径见末节，+1 待后台）。
- **欠账**：本轮改 `desktop.py` 源码并新增 3 个生产模块，`project_status.md` 全量欠账计数按规则应 +1（我未改状态页，由提交方处理）；未减少既有欠账。

## 交付摘要

`desktop.py` **1949 → 1419 行**（−530），≤1500 达成；`tests/architecture/test_module_size_ratchet.py` 已删 `'desktop.py': 1950` 一行。`Desktop` 原有 100 个方法零丢失（AST 逐名核验 `missing=[]`），37 个方法原样迁到 3 个新 L4 Mixin，`import desktop` 无错，`Desktop.__mro__` 含三个新 Mixin。

## 改动清单

| 文件 | 改动 |
| --- | --- |
| `desktop.py` | 删 37 个方法 + 2 个模块级常量（`PET_STAGE_POLL`／`UNATTENDED_SWITCH`）；`Desktop` 基类追加 `LayoutMixin, PetBridgeMixin, AsyncTasksMixin`；新增 3 条 Mixin 导入并转发 `PET_STAGE_POLL, UNATTENDED_SWITCH`。1949→1419 行 |
| `desktop_layout.py`（新） | `LayoutMixin`：布局与滚动 14 个方法 |
| `desktop_pet_bridge.py`（新） | `PetBridgeMixin`：三虎桥接 11 个方法 + `PET_STAGE_POLL`／`UNATTENDED_SWITCH` 两个模块级常量（随迁） |
| `desktop_async_tasks.py`（新） | `AsyncTasksMixin`：后台任务队列与结果轮询 11 个方法 |
| `tests/architecture/_layers.py` | L4 登记 3 个新模块 |
| `tests/architecture/_scan.py` | `DESKTOP_PARTS` 追加 3 个新模块（读新模块，断言不动） |
| `tests/architecture/test_module_size_ratchet.py` | 仅删 `'desktop.py': 1950` 一行（允许的下降，非弱化） |
| `tests/architecture/test_stage_command_contract.py` | `_L4_COMMAND_MODULES` 追加 `desktop_pet_bridge`（`pet_start`／`pet_storyboard_batch` 迁址，断言不动） |
| `tests/test_continuity_scope.py` | 读 `desktop.py` → `desktop_pet_bridge.py`（仅改读取位置，断言不变） |
| `tests/test_task_center.py` | 读 `desktop.py` → `desktop_async_tasks.py`（仅改读取位置，断言不变） |
| `architecture.md` | L4 模块职责表一行补登 3 个新模块 |
| `维护记录/覆盖率基线.json` | 门禁要求同步：+3 新模块（covered=0）、`desktop.py` total 1529→1106、`modules_total` 286→289 |
| `维护记录/TODO注释快照_20261003.json` | 门禁要求同步：`_tick_async_result` 的 `file` `desktop.py`→`desktop_async_tasks.py`（scope／文案不变） |
| `runbook.md` | §11 数字 286→289、236→239（随覆盖率基线 `modules_total` 变化，门禁要求） |

## 每组搬了哪些方法与行数

**第 1 组 → `desktop_layout.py` / `LayoutMixin`**（14 个，共 277 行）：`schedule_sidebar_fit`、`fit_sidebar`、`align_header`、`fit_content`、`_fit_content_now`、`wheel_steps`、`popdown_listbox`、`native_wheel`、`clear_hover`、`_inside_path`、`scroll_page`、`_page_scroll_target`、`scroll_page_key`、`on_window_map`。依赖按来源导入：`ui_tokens`（`DESKTOP_LAYOUT`/`FONTS`/`SPACING`）、`desktop_page_registry`（`PAGE`）、`responsive_ui`（`growable_extra`）、`pet_ui`（`PATCH_ROOM`）、`app_logging`、`tkinter`/`ttk`。

**第 2 组 → `desktop_pet_bridge.py` / `PetBridgeMixin`**（11 个，共 126 行）：`pet_show_text`、`pet_goto`、`pet_advance`、`pet_start`、`_start_unattended_stage`、`pet_storyboard_batch`、`batch_blockers`、`busy_reason`、`pet_report`、`pet_at_stage`、`pet_hides_instead_of_quitting`。`close`／`force_quit`／`finish_close`／`stop_automation_processes` **未搬**（按任务书，依赖被测试 patch 的 `desktop.confirm` 等模块全局，留在原处）。

**第 3 组 → `desktop_async_tasks.py` / `AsyncTasksMixin`**（11 个，共 121 行）：`async_`、`async_queued`、`async_descriptor`、`_start_next_queued`、`retry_failed_task`、`_schedule_async_result_poll`、`_poll_async_result`、`_schedule_auto_edit_result_poll`、`_schedule_auto_handoff_result_poll`、`_set_automation_error`、`_tick_async_result`。夹在中间的方法 `queue_initial_brief_document`（创意历史发现，不是后台任务队列机器）、`cancel_timers`／`on_window_destroy`（生命周期，且被 `close` 依赖）、`shot_numbering_hint`（提示，不属于异步）**留原处**，理由：不属于本组，未搬。

## 方法体对照表（AST dump，include_attributes=False，逐字相同）

搬前源＝`git show HEAD:程序/desktop.py` 中 `Desktop` 类原方法，搬后＝对应新模块 Mixin 类方法。37 个方法**全部 SAME**：

| 组 | 方法 | 相同？ |
| --- | --- | --- |
| G1 | schedule_sidebar_fit / fit_sidebar / align_header / fit_content / _fit_content_now / wheel_steps / popdown_listbox / native_wheel / clear_hover / _inside_path / scroll_page / _page_scroll_target / scroll_page_key / on_window_map | 14/14 SAME |
| G2 | pet_show_text / pet_goto / pet_advance / pet_start / _start_unattended_stage / pet_storyboard_batch / batch_blockers / busy_reason / pet_report / pet_at_stage / pet_hides_instead_of_quitting | 11/11 SAME |
| G3 | async_ / async_queued / async_descriptor / _start_next_queued / retry_failed_task / _schedule_async_result_poll / _poll_async_result / _schedule_auto_edit_result_poll / _schedule_auto_handoff_result_poll / _set_automation_error / _tick_async_result | 11/11 SAME |

另：`desktop.PET_STAGE_POLL is desktop_pet_bridge.PET_STAGE_POLL` 与 `UNATTENDED_SWITCH` 同对象校验为真（`test_pet_ui` 直接 `from desktop import PET_STAGE_POLL, UNATTENDED_SWITCH` 仍有效）。

## 命中的受影响测试与计数

| 测试 | 结果 |
| --- | --- |
| `tests.test_pet_ui`（直接调用 pet_goto／pet_advance／pet_start 等 + `from desktop import PET_STAGE_POLL, UNATTENDED_SWITCH, UNATTENDED_BACKOFF_FLOOR`） | **599/599 OK**（101.14s） |
| `tests.architecture.test_busy_state_boundary`（`parse_desktop()` 查 `async_`／`_tick_async_result`） | 7/7 OK |
| `tests.test_task_center`（读源码查 `_tick_async_result`，改读新模块） | 16/16 OK |
| `tests.test_continuity_scope`（读源码查 `pet_start`／`_start_unattended_stage`，改读新模块） | 15/15 OK |
| `tests.test_stage_command_contract`（根） | 5/5 OK |
| `tests.architecture.test_stage_command_contract`（`_L4_COMMAND_MODULES` 追加新模块后） | 1/1 OK |
| `tests.test_force_quit` / `tests.test_desktop_close` | 17/17、2/2 OK（exit=0） |
| `tests.test_timers` / `tests.test_desktop_compact_layout` / `tests.test_pet_settings` / `tests.test_asset_gating` | 各 exit=0 |
| `tests.test_cancellation_status` / `tests.test_desktop_automation_service` / `tests.test_ui_batch3_shell` / `tests.test_sanhu_mode` / `tests.test_skill_notes` | 各 exit=0 |
| `tests.test_idea_chat` / `tests.test_desktop_startup_perf` / `tests.test_ui_edges` | 各 exit=0 |
| `tests.test_core` / `tests.test_page_cache` / `tests.test_req_s03_anchors` / `tests.test_req_s07_anchors` | 各 exit=0 |
| `tests.test_project_recovery` / `tests.test_recovery_delivery_e2e` | 各 exit=0 |
| `tests.architecture.test_module_size_ratchet` / `test_todo_comment_snapshot` / `test_coverage_baseline` | 9/9 OK（6.33s） |
| 默认冒烟 `smoke_test.py` | **8/8** |
| 架构门禁 `smoke_test.py --architecture` | **374/374 OK**（214.99s） |
| 守卫：`tests.test_line_endings` / `tests.test_static_names` | 16/16、8/8 OK（拆分轮未定义名扫描与行尾审计） |

`tests.test_perf_baseline`（MRO 拼源码那条 `test_script_page_measurement_does_not_force_the_tk_idle_loop`）**通过**；详见裁决事项（另有一条 R1745 既有红与本轮无关）。

## 末尾自检

- `wc -l`（`read_text().splitlines()`，与门禁 `_lines()` 同口径）：`desktop.py` **1419**、`desktop_layout.py` 293、`desktop_pet_bridge.py` 151、`desktop_async_tasks.py` 134；三个新模块均 ≤1500。
- `python -B -c "import desktop"` 无错；`Desktop.__mro__` 含 `LayoutMixin`／`PetBridgeMixin`／`AsyncTasksMixin`；100 个方法零丢失。
- 方法体逐字相同：见上表（37/37 SAME）。

## 需裁决事项

1. **`PET_STAGE_POLL`／`UNATTENDED_SWITCH` 随迁而非“留原处+注入”**：任务书规则 1 说“依赖 desktop.py 模块级常量应留原处并最小注入”。但这两个常量只被迁走的 `pet_advance`／`_start_unattended_stage` 使用，且 `test_pet_ui` 直接 `from desktop import PET_STAGE_POLL, UNATTENDED_SWITCH`。若留在 desktop.py，新模块方法体仍引用裸名，会造成反向 `import desktop` 环，破坏“方法体逐字不改”。故按 R1622 的 `PAGE` 前例，把常量随迁到 `desktop_pet_bridge.py` 并在 desktop.py 按原名转发，`from desktop import …` 入口不变。
2. **`tests/architecture/_scan.py`（`DESKTOP_PARTS`）**：是“读新模块”的集中入口（R1480 起确立）。本次追加 3 个新模块，使 `desktop_text()`／`parse_desktop()` 继续覆盖全部 Desktop 方法；这是 `test_busy_state_boundary` 等门禁读到迁出方法的前提。属“因方法搬家必须同步的测试基础设施”，断言内容未动。
3. **`维护记录/TODO注释快照_20261003.json` 与 `runbook.md`**：不在任务书显式允许清单，但分别被 `test_todo_comment_snapshot`（`_tick_async_result` 的 `file` 迁址）与 `test_coverage_baseline.test_runbook_states_the_directed_measurement_caliber`（`modules_total` 286→289）强制，属“门禁要求同步”。已同步，断言均未弱化。
4. **`维护记录/覆盖率基线.json`**：新增 3 个生产模块触发了 `test_baseline_modules_exist_and_keep_production_scope`（模块清单必须等于源码）。我未重跑全量 `coverage_report.py`（它要跑 8 组定向用例的 tracer），而是用与工具 `executable_lines()` 完全相同的口径算 `total`（desktop.py=1106、layout=257、pet_bridge=92、async_tasks=110），新模块 `covered=0`（这 8 组定向用例确实不 import desktop 系），`modules_covered` 保持 50，`modules_total` 286→289。若提交方要“工具重跑”的凭据，可再显式重跑。
5. **`tests/test_perf_baseline.test_page_switch_does_not_force_the_tk_idle_loop` 是既有红，与本轮无关**：该断言 `inspect.getsource(Desktop.show)` 含 `self.fit_content()`，但 `show` 自 **R1745**（commit 7b923034）被 `@_page_paint_timed` 装饰（未用 `functools.wraps`），`inspect.getsource` 现返回 3 行 wrapper，已不含该串；R1745 未同步此测试（test_perf_baseline 最近改动是 R1499）。`Desktop.show` 与装饰器本轮均未触碰。同文件的 MRO 拼源码那条通过。`test_cold_start_reaches_the_first_frame` 在并发负载下单跑过一次 1565ms>1500ms，隔离重跑 2.17s **OK**，属抖动。
6. **run_selftests.py -k 执行情况**：`python -B run_selftests.py -k desktop force_quit close project_recovery` 前台跑完，**共 80 条用例、53.1 秒、0 个文件有红、实际跳过 0 条、ALL TESTS PASSED**（exit=0）。覆盖 test_desktop_compact_layout 5、test_desktop_startup_perf 14、test_desktop_idea_chat_desktop_paste 7、test_ui_batch4_desktop_project_pages 3、test_project_recovery 8、test_force_quit 17、test_desktop_close 2、test_desktop_settings_callers 3 等。`perf_baseline` 单独跑（见上表与裁决事项 5）。第一次 `-k` 滞留是并发后台任务争用 GUI 令牌，非本命令问题。

## 独立验收（Claude，主工作区）

- 执行链：Harness `deepseek-v4-pro`（03:37–04:23），免费组 `group-4` 当时处于冷却被跳过。
- 方法体：我自己用 `ast.dump` 对 `git show HEAD:程序/desktop.py` 的 `Desktop` 类逐方法比对——原 100 个方法，留在 `desktop.py` 64 个、搬走 36 个，搬走的 36 个与原版全部相同，留下的 64 个与原版全部相同，无丢失、无重复。（执行者结果文件写 37 个，实为 14+11+11=36，计数笔误，不影响结论。）
- 复跑（车道 split1）：`run_selftests -k desktop force_quit close project_recovery task_center continuity_scope pet_ui stage_command` 全绿；默认冒烟通过；`smoke_test --architecture` 374 tests OK；`review_batch --lane split1` PASS（15 个文件）。`desktop.py` 1419 行，登记表已删 desktop.py 一行。
- 范围：除任务书允许清单外，同步改了 `_scan.py`（DESKTOP_PARTS）、`test_stage_command_contract.py`（模块清单）、两个测试的读取位置、`TODO注释快照`、`覆盖率基线.json`、`runbook.md` 数字，均为门禁强制的同步，断言内容未动，接受。
- 裁决：`PET_STAGE_POLL`／`UNATTENDED_SWITCH` 随迁并在 `desktop.py` 按原名转发，接受。
- 遗留（非本轮引入）：`tests/test_perf_baseline.py::test_page_switch_does_not_force_the_tk_idle_loop` 在 R1745（PERFM）之后即为红——`show` 被 `@_page_paint_timed` 包装且未用 `functools.wraps`，`inspect.getsource` 取到包装函数。我验收 R1745 时只跑了任务书列出的定向测试，漏跑 perf_baseline，责任在验收方；已安排单独返修轮（给装饰器加 `functools.wraps`），不并入本轮。
- 现有测试断言未动。
