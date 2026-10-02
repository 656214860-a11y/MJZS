# R749 结果｜修复轮：自动门禁失败反馈

## 结论

已修复自动处理待办时的静默失败。资产清单或确认账本写入失败不再被 `continue` 掩盖，而是交给既有调度器节流；状态栏会显示失败原因及“将在约 20 秒后重试”。

## 证据与验证

- 根因：`desktop.py:5022-5041` 捕获 `OSError`、`ValueError`、`KeyError`、`TypeError` 后直接 `continue`，所以 `desktop.py:2326-2332` 的可见失败回调永远收不到此类异常。
- 处置：移除该伪容错，保留外层 `DesktopAutomationScheduler.run_due()` 的异常类型、到期时间推进与 20 秒重试节流；状态文案明确重试行为。
- 回归：`tests/test_core.py` 新增两条，分别验证写入故障语义化上抛、调度器把原因及重试提示交给状态栏；13 条直接回归通过。
- 默认 `smoke_test.py`：8/8 通过。
- `smoke_test.py --affected desktop`：9/9 通过；定向 5 个测试文件、13 条、0 红。
- `smoke_test.py --architecture`：138 条、0 红、36.462 秒，通过（不低于既有基线）。
- 完整安全全量判断：`749 - last_full_safe_all_round(748) = 1 < 3`，且本轮未改 Tk 绑定／生命周期；不运行全量。

## J. 整改路线

继续按 `维护记录/缺陷台账_20261001.md` 收口剩余 UI 反馈链：每一项先以注入故障证实，再选择可见降级、语义化上抛或销毁态守卫，禁止以更宽的捕获替代修复。

## K. 测试迁移计划

自动门禁的无 Tk 行为回归保留在 `tests/test_core.py`；调度器节流的通用契约继续由 `tests/test_desktop_automation_service.py` 覆盖。若未来改动实际 Tk 状态控件，再增补桌面交互组，而不削弱这里的异常传播断言。
