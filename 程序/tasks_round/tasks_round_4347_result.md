# R4347 · FIX-MASTER-SB-PREP-TEST 分镜批量准备 selected_many 归位后台 work() 线程
<!-- round-evidence: {"commit_base": "7f3706fa6", "credential_hits": 0, "evidence_sha256": "df74f84ae5cd4e5a", "exit": 0, "failed": 0, "passed": 82, "round": 4347, "tests": "run_selftests.py -k desktop_automation_service shared_input_stages desktop_shared_input storyboard_page_controller"} -->

## 三问

- 本轮类型：§3.2 修复轮（先定位根因，只改根因所在模块 `desktop_shared_send.py`）。
- 测试跑了吗：跑了。改前定向红 2 条（原文见下）；改后 `run_selftests.py -k desktop_automation_service shared_input_stages desktop_shared_input storyboard_page_controller` 82 条全绿（退出码 0）；`smoke_test.py --architecture` 702 条全绿（退出码 0，失败集合为空）。默认冒烟基线 8/8 与全量回归未跑（卡面验收未列，未运行；车道分支不累计全量轮次）。
- 欠账少了吗：本卡消除主干全量 2 条红；未新增欠账。卡外发现记录于文末。

## 缺陷复现方式

`tests/test_desktop_automation_service.py::BackgroundDeliveryMatrixTests.test_storyboard_preparation_delivers_once_only_to_live_project` 直接复现，无需新增用例：`Desktop.pet_storyboard_batch(desktop)` → `stage_handler_registry.start` → `stage_run_action` → `present_stage(OPEN_STORYBOARD)` → `open_storyboard_skill` → `desktop.async_(work, finish)`（`ui/desktop_async_tasks.py:18-30` 把 work 包成 Thread target；测试打桩 Thread 后在 patch 上下文手动执行 target）。`selected_many` 若在 `work()` 之外同步执行，patch 生效期间 `call_count` 为 0，断言 `2` 失败。

## 改前红（2 条，原文）

命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k desktop_automation_service shared_input_stages desktop_shared_input storyboard_page_controller`（退出码 1；共 82 条，2 红）

```
### test_desktop_automation_service（2 条红）

===== test_storyboard_preparation_delivers_once_only_to_live_project (mode='current') =====
  File "...\tests\test_desktop_automation_service.py", line 371, in test_storyboard_preparation_delivers_once_only_to_live_project
    self.assertEqual(selected.call_count, 2)
AssertionError: 0 != 2

===== test_storyboard_preparation_delivers_once_only_to_live_project (mode='switch') =====
  File "...\tests\test_desktop_automation_service.py", line 371, in test_storyboard_preparation_delivers_once_only_to_live_project
    self.assertEqual(selected.call_count, 2)
AssertionError: 0 != 2
```

红因与卡面一致：R4287（UX-S03-SEND，提交 `71d5b2b90`）把 `open_storyboard_skill` 从 `desktop.py` 迁到 `desktop_shared_send.py` 时，将原本在 `work()` 内执行（71d5b2b90~1 `desktop.py:839`）的 `selected_many(project,'script')`/`selected_many(project,'storyboard')` 挪到主线程同步段（`desktop_shared_send.py:326-328`），后台线程不再读盘，且读的是实时 `desktop.root` 之前的同步值——既破坏「主线程不读盘」也让 patch 后执行的 `work()` 里 `call_count==0`。

## 契约取舍核对（卡面要求）

- 无既有测试要求 `open_storyboard_skill` 在同步段校验 `selected_many`：自动链「读取结构剧本输入失败」由注册器层 `stage_handler_registry._start_storyboard` → `storyboard_work_plan`（`orchestrator/storyboard_plan_service.py:32-33` 同步调 `selected_many`，本轮未动）拦下，`tests/test_pet_ui.py:4710-4724` 的 `stage.failed` 断言走该路径，不受影响（该模块不在本卡定向命令内，按读码核实注明）。
- `test_shared_input_stages.py` 全部用例在 patch 后才调 `open_storyboard_skill`/`send_storyboard` 且 `finish()` 于同一上下文执行 `work()`；`test_send_snapshots_selected_files_model_and_supplement` 断言调用顺序 `script`→`storyboard`，归位后保持。
- `test_shared_input_stages.py:528-541` `test_switch_project_or_destroyed_window_drops_late_result` 要求 `win.winfo_exists()==False` 时丢弃迟到结果：`_window_alive` 的「可报死即丢」语义保留。

## 改动（文件:行号）

- `程序/desktop_shared_send.py:325-339`：`selected_many(project,'script')`/`selected_many(project,'storyboard')` 移回 `work()` 内执行（闭包冻结 `project`，不读 `desktop.root`）；读盘异常时 `work()` 返回 `('err','读取结构剧本输入失败：'+str(exc))`，由 `finish()` 既有 `kind=='err'` 分支 `_say(desktop, value)`（`:369-372`）。其余批次逻辑逐字未动。
- `程序/desktop_shared_send.py:242`：`_window_alive` 对完全没有 `winfo_exists` 的 `win` 视同 `win is None`（非窗口对象、无窗可毁）判活；有该方法且报 False 或抛错仍判死。缘由：R4287 同提交新增该校验，`except` 把「方法不存在」一并判死，吞掉 mode='current' 的交付（改前红只到 371 行被掩盖，修好 selected_many 后 377 行 `open_flow_agent` 0 次调用的第二个红才暴露）；回归前 `finish()` 本不查窗口（71d5b2b90~1 `desktop.py:846-847` 仅挡 `root!=project`/`shutting_down`），本行恢复该可观察行为，真实 Tk 窗口销毁时 `winfo_exists` 仍在且抛 TclError→判死，语义无损。
- 测试文件零改动，既有断言全部原样。

## 验收命令与退出码

1. `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k desktop_automation_service shared_input_stages desktop_shared_input storyboard_page_controller` → 退出码 0

```
共 82 条用例，3.9 秒；0 个文件有红
实际跳过 0 条用例：本机没有任何登记位被跳过
增量台账已刷新：D:\漫剧制作助手\.git\selftest-incremental.json
最近 5 轮自检中位基线：3.1 秒

ALL TESTS PASSED
```

2. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` → 退出码 0

```
----------------------------------------------------------------------
Ran 702 tests in 291.901s

✅ 架构治理测试：tests/architecture
OK
```

## 未验证

- `test_pet_ui.py`（自动链 `stage.failed` 路径）不在本卡定向命令内；按读码核实 `storyboard_work_plan` 同步校验未动，判定不受影响，未实跑。
- 真实 Tk 界面下「结构剧本选择配置损坏」的状态栏提示未人工复现；`('err', …)` → `finish()` → `_say` 链路由桩断言覆盖。
- 默认冒烟 `python smoke_test.py` 未单独跑（卡面未列）。
- `git status` 收尾核对在提交后记录。

## 卡外发现（只记录，不修）

- R4287 迁移时除卡面缺陷外同址引入 `_window_alive` 的「方法缺失判死」边界（已在本轮一并修复，理由见「改动」节）；`finish()` 的 `desktop.root != project` 丢弃判定在 mode='switch' 下行为符合既有契约，未动。

## 回滚

`git revert` 本轮提交。
