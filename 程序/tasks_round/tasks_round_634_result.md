# R634 结构治理轮（子场景：执行）——R630 J-4 后期页控制器迁出

## 轮末三问

1. 本轮是功能轮还是整理轮？**结构治理轮（子场景：执行）**；来源为 `tasks_round/tasks_round_630_result.md` 的 J 节第 4 项，只处理一个页面入口：后期剪辑页。
2. 测试跑了吗？三个基线过了吗？跑了。专项 `tests.test_editing_page_controller` 为 **2/2**，默认冒烟为 **8/8**，架构门禁为 **102/102**；全量安全自检为 **3338 条、16 个失败文件**，未通过，故三个基线未全绿。
3. `project_status.md` 的欠账少了吗？没有。此次只完成控制器迁出；全量既有红项仍阻塞本轮验收，未声称减少台账欠账。

## 来源与范围

- 来源：`tasks_round/tasks_round_630_result.md`，J-4「以一个页面为单位继续从 `desktop.py` 或 `pet_ui.py` 迁出控制器，必须先选定单一入口」。
- 选定入口：`desktop.py:5884` 的 `Desktop.editing()`（后期剪辑页）。
- 范围：仅迁出无 Tk 的视频可用性判断、自动粗剪调用报告与完成状态文案。Tk 控件构造、事件绑定、`async_()` 调度、剪映发现和页面布局仍在 `desktop.py`。

## 修改文件与摘要

- `editing_page_controller.py`（新增，L3）：`EditingPageController` 持有项目路径和注入的 `Studio`；提供 `has_downloaded_video()`、`assemble()`、`assembled_message()`；不导入 Tk、不写用户配置。
- `desktop.py`：后期页创建控制器并委派上述三项逻辑，保留既有按钮、可用/禁用状态、后台装配与完成提示语义。
- `tests/test_editing_page_controller.py`（新增）：覆盖仅登记但文件不存在时不可用、文件出现后可用，以及 `skip_unready=True`、报告和完成文案的保留。
- `tests/architecture/_layers.py`、`tests/architecture/test_migrated_ui_boundaries.py`：将新 L3 模块纳入层级与“无 Tk 服务”静态门禁。本次改测试因模块拆分这一契约变更，原有断言未弱化或删除。
- `architecture.md`：L3 模块表和职责说明登记 `editing_page_controller.EditingPageController`。

## 验证原始汇总

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_editing_page_controller
Ran 2 tests in 0.008s
OK

D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py
通过：8 项
失败：0 项

D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py --architecture
Ran 102 tests in 36.670s
OK
```

跨 L3/L4 迁出后还执行了：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B run_selftests.py --all --safe
共 3338 条用例，1137.4 秒；16 个文件有红
```

全量红项不属于本轮的 `editing_page_controller`/后期页边界，且专项、默认和架构均绿；按用户硬判定仍记为 **[TASK_FAILED]**。失败组为：`test_copy_rules`、`test_core`、`test_hollmwood_ui_queue`、`test_idea_chat`（两组）、`test_line_endings`、`test_model_pool`、`test_pet_ui`（五组）、`test_row_targets`、`test_skills`（两组）、`test_static_names`。其中可复核的直接错误包括 `storyboard_files.py` 的 `remove_selected` 使用未定义 `remove`，以及 SKILL 顺序/工具登记断言失配；均未在本轮越界修复。

## 自审

- 只迁出一个页面入口的无 Tk 状态与业务判断；未改 UI 布局、页面路由、剪映启动或用户数据。
- 新模块登记为 L3，`desktop.py` 保持 L4；102/102 架构门禁确认无 Tk 反向依赖。
- 未新增越界依赖；未改任何项目配置或用户项目数据。

## J 后续

先单独处理全量回归的既有失败，再继续 R630 J-4 的下一页迁出；下一页仍需在开工前锁定单一入口，建议从 `desktop.py` 的 `delivery()` 或 `continuity_page()` 二选一，不与后期页混做。

## K 测试计划

下一次页面迁出延续本轮方式：为新控制器添加无 Tk 专项单测、登记 L3 和迁出边界静态检查；不为纯文件拆分新增 E2E。全量红项应按其各自模块另立修复轮并先复现对应失败断言。

[TASK_FAILED]
