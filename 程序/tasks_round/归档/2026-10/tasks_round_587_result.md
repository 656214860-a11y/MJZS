# R587 修复轮结果：关闭时取消布局空闲任务

## 结果

已消除完整 UI 边界回归退出时的 Tk `invalid command name "...run"` 残留回调告警。

## 根因、复现与修复

- 根因：`desktop.py:fit_content()` 通过 `after_idle(run)` 建立空闲布局任务，但未保存返回的任务 ID；`Desktop.cancel_timers()` 因而无法在窗口销毁前取消该任务。该匿名回调的函数名正是日志中的 `run`。
- 触发场景：首帧或页面重建刚登记布局、用户或测试立即关闭窗口；Tcl 已删除 Python 回调命令时，已登记的 `after` 仍到期执行。
- 修复：保存 `_fit_job`，回调执行时清空；`cancel_timers()` 在停止聊天、启动控制器及自动化调度器前取消该空闲任务并清除布局重排状态。未改页面结构、数据或业务事件。
- 回归：新增 `tests/test_timers.py::WindowTimerTests.test_desktop_cancels_pending_content_fit_job`，用最小窗口替身验证关闭链路取消待执行的 `content-fit-idle`。这是一条新增生命周期契约，未弱化任何既有断言。

## 改动文件

- `desktop.py`：为桌面自有的内容布局空闲任务保存、执行后释放并在关闭时取消。
- `tests/test_timers.py`：新增关闭时清理内容布局任务的回归覆盖。

## 验证

- 定时器清理 + 同页滚动恢复精确回归：2/2 通过。
- `python smoke_test.py --affected ui_edges`：109/109 通过（167 秒）；stderr 未出现 Tk `invalid command name`。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：101/101 通过。

## 剩余观察项

定向自检结束时仍提示 `维护记录/自检增量.json.*.tmp` 权限不足；测试结果不受影响，且该提示来自维护增量台账写入，不属于 Tk UI 或产品关闭路径。本轮未扩大范围处理它。
