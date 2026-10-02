# R551｜结构治理轮（子场景：执行）｜P1-1 Desktop 启动控制器

## 完成结论

- 已完成 `tasks_round/tasks_round_547_result.md` J 节 **P1-1**：`Desktop.__init__` 不再自身保存“150ms 首帧延迟 → `after_idle` 项目选择”的生命周期细节；无 Tk 的 `DesktopStartupController` 负责该时序与取消。
- 在该启动边界，视图层继续创建窗口、绑定销毁／关闭事件，并只注入 Tk 的 `after`、`after_idle`、`after_cancel` 与原有 `choose_project` 回调；项目选择、记住项目和页面最终样式均未改变。
- 本轮生产改动为 2 个模块（`desktop.py`、`desktop_startup_service.py`）；回归在既有 `tests/test_ui_edges.py` 内，未新增功能或改变公开契约。

## 改动文件

| 文件 | 改动 |
| --- | --- |
| `desktop_startup_service.py` | 新增 L3 无 Tk `DesktopStartupController`：持有注入的延迟／空闲／取消调度器、停止判定、状态提示和项目选择回调；`start()` 保持 150ms 后转空闲队列，`cancel()` 回收未执行任务。 |
| `desktop.py` | `Desktop.__init__` 仅装配并启动控制器；窗口关闭时委派控制器取消首帧回调；删除旧的视图内 `_choose_project_after_first_paint()`。 |
| `tests/test_ui_edges.py` | 首帧回归改为无 Tk 控制器测试，验证 150ms → idle → `choose_project` 的顺序，并验证已停止窗口不再进入 idle 项目选择。 |
| `tests/architecture/_layers.py`、`architecture.md`、`PROJECT_MAP.md` | 将新服务登记为 L3，并明确 UI 只负责窗口/事件/回调注入，服务不持有 Tk。 |

## 时序与边界

```
Desktop（创建窗口、绑定关闭事件）
  └─ DesktopStartupController.start()
       └─ after(150ms) → 状态提示 → after_idle(choose_project)
```

- `DesktopStartupController` 不导入 `tkinter`，可由普通回调替身验证。
- 关闭窗口先将 `shutting_down` 置真，随后 `cancel()` 撤销仍挂起的启动任务；若延迟回调已开始，则停止判定阻止其继续登记空闲项目选择。
- 未移动 `choose_project()`、项目恢复规则或同步页面构建，因此不改变现有项目恢复语义。

## 验证

| 检查 | 结果 |
| --- | --- |
| `python -m unittest tests.test_ui_edges.StartupFirstPaintTests` | 2/2 通过（无 Tk 时序与停止分支） |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --architecture` | 95/95 通过，无新增架构红点；L3→L4 依赖方向检查通过 |

## 债务台账

- P1-1 已关闭；R182 可执行拆分债务由 **15 项减至 14 项**。
- P0-3 仍为 R550 已登记阻塞项，未在本轮扩大范围处理。

## 风险与复验

- 本轮只验证控制器的无 Tk 调度语义；真实首屏与用户项目的页面构建耗时仍应在重启应用后按 R541 的方法观测，不将本次结构提取宣称为性能优化。
