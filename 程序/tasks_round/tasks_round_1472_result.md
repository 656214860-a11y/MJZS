# R1472 功能轮：把后台任务排队接到真实用户流程（云端「测试连接」）

1. **本轮类型？** 功能轮（小）。
2. **测试与基线？** `test_task_center` 增到 11 项（含云端探测改用排队的源码断言、无进度条探测排队续跑）；idea_chat／cancellation／automation 等相关测试通过；默认冒烟、架构门禁与全量见提交前后运行。断言未动。
3. **是否欠账？** 改了 `desktop.py`、`desktop_automation_service.py`、`cloud_video.py`，计入源码轮次。

## 根因与改动

- 云端设置里的「测试连接」直接调 `desktop.async_`。后台正忙时它不会被“请稍候”拦截（该按钮没走 `Desktop.safe()`），而 `async_` 的代次覆盖会逻辑取消正在进行的主动任务，使那个任务的结果被丢弃——这是真实存在的隐患。
- 该探测只读、互不依赖，正好符合排队的适用条件：改用 `desktop.async_queued(..., label='测试云端连接', show_progress=False)`，忙时排队、空闲立即执行，不再顶掉进行中的任务。
- `async_queued`／`BackgroundTaskQueue` 补上 `show_progress` 透传，排队项保持原来的“无进度条”体验。

## 说明

这是排队的第一个真实调用方；其余 `async_` 调用点多在 `Desktop.safe()` 之后，忙时在进入前就被拦截，改排队会改变既有交互，仍不动。

## 提交

已提交，见 git log 标题 `R1472:`。
