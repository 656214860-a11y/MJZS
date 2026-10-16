# R1622 拆分 desktop.py（Q9 第五批）：页登记表、Tk 回收护栏、自动化 tick Mixin

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round/tasks_round_1610_result.md) J 第三批 Q9）。`desktop.py` 是 R1610 点名 5 个大文件里的**最后一个**，至此 Q9「继续拆 5 个大文件」部分完成（script_contract／stage_execution_service／skill_panel／pet_cloud／desktop）。
- 测试：架构门禁 `smoke_test.py --architecture` **354 项 OK**（180.6 秒）；默认冒烟 8/8；`desktop` 相关 6 个模块 209 项 OK（`test_desktop_automation_service` 14、`test_core` 127、`test_stage_completion_service` 32、`test_force_quit` 17、`test_desktop_compact_layout` 5、`test_desktop_startup_perf` 14）。
- 欠账：本轮改源码＋新增 3 个生产模块，`project_status.md` 全量欠账计数 +1；R1619–R1621 的欠账仍未清（后台全量跑完后由 post-commit 写凭据）。

## 做了什么

`desktop.py` **2259 → 1859 行**，行数棘轮登记上限 2300 → **1950**。`Desktop` 已有 9 个 Mixin，本轮再按同一模式拆出 3 个 L4 模块：

| 新模块 | 行数 | 内容 |
| --- | --- | --- |
| `desktop_page_registry.py` | 18 | `PAGES`、`PAGE`、`PAGE_SITES`、`CACHED_PAGES` 页登记表常量（被 Desktop 多处方法共用，单独成模块以免与某个 Mixin 绑死） |
| `desktop_tk_gc.py` | 104 | `protect_readonly_combobox`／`_pin_tk_app`／`protect_tk_gc`／`drain_tk_gc` ＋ 模块级状态 `_PENDING_TK_GC`／`_KEEP_APPS`（Tk 对象回收护栏，Tcl async handler 只能在主线程析构） |
| `desktop_automation_tick.py` | 289 | `AutomationTickMixin`：定时推进 7 个方法（`_startup_window_held`、`_after_first_paint`、`_request_tick_resume_after_first_paint`、`_resume_tick_after_first_paint`、`_tick_once`、`_tick_pre_automation`、`_tick_pet_events`）、门禁决策 4 个（`pick_gate`、`gate_level`、`pending_gate_asks`、`auto_decide_gates`）、自动成片扫描 5 个（`auto_final_scan`、`auto_final_target`、`auto_final_state`、`retry_auto_final`、`reconcile_storyboards`） |

`desktop.py` 改为 `class Desktop(IdeaMenusMixin, …, AutoFlowsMixin, AutomationTickMixin)`，并把上述 10 个模块级名按原名转发。

**验收校验**（脚本化）：迁出前断言三组方法只引用「已导入名 ∪ 页登记表常量 ∪ `drain_tk_gc`」，无其它模块级函数／类引用；迁出后 **110 个方法零丢失**（逐名 `hasattr`）、模块公开面零缺失、`__mro__` 含 `AutomationTickMixin`；**同一对象校验** `desktop._PENDING_TK_GC is desktop_tk_gc._PENDING_TK_GC`、`desktop.PAGE is desktop_page_registry.PAGE` 为真（`test_pet_ui` 直接断言 `desktop_module._PENDING_TK_GC` 长度，必须是同一个 list）。

## 随迁必须同步的既有门禁（3 处位置断言）

| 门禁 | 原断言 | 本轮处理 |
| --- | --- | --- |
| `test_confirm_gates_json_boundary.test_l4_confirmation_writes_delegate_to_l3` | `desktop.py` 内有 `from stage_execution_service import record_stage_confirmation` | 该惰性导入随 `auto_decide_gates` 等迁到 `desktop_automation_tick.py`；改为在「desktop.py ＋ desktop_automation_tick.py」两处文本里断言（仍要求 L4 委托 L3、且不得直连 `confirm_gates`） |
| `test_stage_display_boundary.test_desktop_pages_are_generated_from_canonical_stage_table` | 从 `desktop.py` 读 `for index, stage in enumerate(pet_bus.STAGES, start=1)` | `PAGES` 的生成迁到 `desktop_page_registry.py`，改读该文件（其余 AST 校验不变） |
| `test_todo_comment_snapshot` | 冻结 3 条关键词注释的 file/line/scope | 仅 `desktop.py` 那条 `_tick_async_result` 因上方删行走位，1206 → 1019（scope、文案不变），快照同步一行 |

同步：`tests/architecture/_layers.py` L4 登记 3 个新模块；`architecture.md` L4 行补登；`维护记录/覆盖率基线.json` 刷新（49/281）。

## 诚实边界

- 本轮是**方法体零改动的搬迁**：证据是 AST 断言、`__mro__`、逐名 `hasattr`、同一对象校验、架构门禁与定向用例；未实机点击桌面窗口（本环境 GUI 会话超时，见 R1619／R1620 说明）。
- Q9 剩余的第二半（生产裸 `print(` 统一到 `app_logging`，R1610 计数 606 处）**尚未做**，留待后续轮次；本轮只完成「拆大文件」这一半。
- 全量安全全量最后一次真实通过仍是 **R1605/e59e513**；R1606–R1622 未跑全量，最终定性以 post-commit 后台 `.git/auto-full-safe-result.json` 为准。