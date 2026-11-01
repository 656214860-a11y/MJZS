# R1475 功能轮：运行状况面板显示后台任务失败原因（优化清单第 13 项补全）

1. **本轮类型？** 功能轮（小）。
2. **测试与基线？** `test_task_center` 历史用例扩展断言（失败原因出现、凭据被脱敏）；automation／lifecycle／cancellation 相关 44 项通过；默认冒烟、架构门禁与全量见提交前后运行。断言未动，只新增。
3. **是否欠账？** 改了 `desktop.py`（一处 `finish` 多传 `error`）、`desktop_automation_service.py`、`task_center_service.py`，计入源码轮次。

## 改动

- `BackgroundTaskLifecycle.finish(..., error='')` 把失败消息记入最近历史（经 `app_logging.redact` 脱敏、截 200 字）；`Desktop._tick_async_result` 失败时传入 `str(value)`。
- 运行状况面板的“最近完成的主动任务”在失败项下多显示一行“原因：…”。

## 第 13 项最终状态（任务中心要求：状态、失败原因、重试、取消）

- 状态／耗时／排队／失败原因：运行状况面板已集中展示。
- 取消：既有的各处“中断”按钮与 `BackgroundTaskLifecycle.cancel` 已承担，面板只读展示，不另造第二个取消入口（§2.5 规则 28 一个动作一个入口）。
- 重试：失败后由用户在原页面重新操作；后台任务没有统一的可重放描述，自动重试存在重复计费风险（付费生成类请求），不做。
- 排队：`async_queued` 已有真实调用方（云端测试连接，R1472）。

## 提交

已提交，见 git log 标题 `R1475:`。
