# R552｜结构治理轮（子场景：执行）｜P1-2 自动流程调度器

## 完成结论

- 已完成 R547 J 节 P1-2：`tick()` 的周期重排、取消和异常兜底，以及各 `poll_auto_*()` 的到期/节流/受控异常处理，已迁入无 Tk 的 `DesktopAutomationScheduler`。
- 阶段状态机、队列收尾、状态文案和各 `poll_auto_*()` 的阶段动作均保留在 `desktop.py`，因此不改变既有阶段转换或公开契约。
- 本轮生产改动为 2 个模块：`desktop.py`、`desktop_automation_service.py`；另有独立无 Tk 回归测试。

## 改动文件

| 文件 | 改动 |
| --- | --- |
| `desktop_automation_service.py` | 新增 L3 无 Tk 调度器：统一命名周期任务的登记、重排、取消、异常兜底和到期轮询；在轮询前推进 due，失败仍保持原有节流。 |
| `desktop.py` | 注入现有 `after`/`after_cancel`，将主心跳与 HOLLMWOOD 进度轮询注册为周期任务；九类自动阶段改经 `_poll_auto_due()` 委派统一服务，保留原状态字段、异常文案与阶段动作。 |
| `tests/test_desktop_automation_service.py` | 新增无 Tk 回归：验证周期回调异常后继续重排、取消回收，以及到期轮询失败仍推进下一次 due 且守住不允许分支。 |
| `tests/architecture/_layers.py`、`architecture.md`、`PROJECT_MAP.md`、`project_status.md` | 登记 L3 模块、职责边界与债务台账。 |

## 调度边界

```
Desktop（Tk after / 状态文案 / 阶段动作）
  └─ DesktopAutomationScheduler（周期重排、取消、异常、due 节流）
       └─ poll_auto_*（原有阶段状态机与队列收尾）
```

- 关闭窗口时先设 `shutting_down`，再由调度器取消所拥有的两个 pending 回调；运行中的回调不会在 finally 重新登记已取消任务。
- 自动阶段的 `due` 在调用轮询前推进，成功与受控失败均保持既有节流；忙碌、无项目和未到期时不调用阶段动作。

## 验证

| 检查 | 结果 |
| --- | --- |
| `python tests/test_desktop_automation_service.py` | 2/2 通过 |
| `python smoke_test.py --affected desktop_automation_service` | 1 个测试文件、2 条通过 |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --architecture` | 95/95 通过，无新增架构红点；L3→L4 依赖方向检查通过 |

## 债务台账

- P1-2 已关闭；R182 可执行拆分债务由 **14 项减至 13 项**。
- P0-3 仍为 R550 已登记阻塞项，未扩大范围处理。
