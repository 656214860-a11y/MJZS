# R1985 Desktop 自动化状态收进 desktop_auto_state.py（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J1a**。基线：`claude/bold-ardinghelli-d6a54d` @ 14fad60f（R1984）。日期：2026-10-24。

## 改动

- 新增 L3 模块 `desktop_auto_state.py`（无 Tk）：`AutoState` dataclass 持有 62 个自动化字段（自动定稿／粗剪／首帧／资产／视频／预演／交接／采用八条流程）；`create_auto_state()` 按原初始化顺序建队列与 `BackgroundTaskLifecycle`，阶段队列工厂 `pet_ui.StageQueue` 和宠物 `drain` 由 `Desktop` 注入，本模块不反向导入 L4。
- `AutoStateAliasesMixin`：旧属性名（`auto_*`、`_auto_<流程>_ticket`）读写转发到 `self.auto.<字段>`；`Desktop.__new__` 半成品对象首次读或写 `auto` 时懒建默认 `AutoState()`。
- `desktop.py`、`desktop_auto_flows.py`、`desktop_automation_tick.py` 的 `self.auto_*` 机械改为 `self.auto.<字段>`（共 268 处）；`_initialize_automation_state` 缩为一次 `create_auto_state` 调用。`desktop.py` 1454→1406 行。
- 登记：`tests/architecture/_layers.py`、`architecture.md`（L3 表）、覆盖率基线（312→313 模块）与 `runbook.md` §11 数字。
- 棘轮下调：`SHARED_STATE_CAPS['Desktop']` 86→**43**；`('desktop.py','Desktop')` 类行数上限 1302→1269。

## 测试同步

- 新增 `tests/test_desktop_auto_state.py`（9 条，无 Tk）：字段数、默认值与原初始化器一致、队列与任务接线、旧名转发读写、半成品对象懒建。
- `tests/test_desktop_automation_service.py`、`tests/test_req_s07_anchors.py` 的桩对象需要 `.auto`：契约有意变更，仅同步 mock（桩类混入 `AutoStateAliasesMixin`，构造时带 `AutoState()`），**断言未动**。

## 验证（本轮实测）

- `run_selftests.py -k desktop_automation_service req_s07 desktop_auto_state test_core test_integration ui_edges timers desktop_startup_perf pet_ui`（经 gui_hidden）：935 条，6 条红全在 `test_pet_ui`（5 条登录门禁文案 + 1 条云朵几何）。已在干净 HEAD 的临时 worktree 上复跑 `-k pet_ui`，同样 5+1 条红，与本轮无关。
- `smoke_test.py --architecture`：410 条，剩 3 条既有红（test_agents_md 缺基准历史.json、test_round_baselines 状态页仅 master 可改、test_skill_reference_injection）；Desktop 类行数红已消失。
- 默认 `smoke_test.py`：8 项通过。
- 未跑 `--all --safe`；全量欠账计数 +1。

## 回滚

`git revert` 本轮提交；旧属性名转发保证回滚前后外部读写语义一致。

## 下一步

J1b：迁 `desktop_async_tasks.py`、`desktop_media_pages.py`、`desktop_asset_pages.py`、`desktop_script_pages.py` 对旧属性名的写入；转发保留给测试，是否退役另轮决定。
