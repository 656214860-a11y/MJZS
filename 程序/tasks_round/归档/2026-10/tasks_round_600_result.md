# R600｜性能轮：剧本准备统一模型请求排队

## 本轮结论

- 剧本准备页的直接模型请求已接入既有阶段并发槽：可用时立即发起；槽满时只在 Tk 定时器中轮询票据并显示排队位次，主线程不等待网络或锁。
- 请求实际发起后，无论模型成功、失败还是抛异常，均在 `finally` 中归还槽位；用户中断会撤销该项目尚未取得槽位的票据，并继续沿用既有取消令牌丢弃旧进度/结果。
- 交互式 Agent 与直接 API 现在共用 `workflow_process_registry` 的剧本阶段容量，未新增第二套并发规则；四角色质量流程、请求格式和正式发布语义均未改动。

## 改动文件

- `desktop.py`：直接模型发送改为申请、轮询、领取和释放阶段槽；排队状态可见且不阻塞 UI。
- `workflow_engines.py`：补充阶段槽释放、撤销的薄适配器，保持 UI 只依赖既有工作流入口。
- `tests/test_workflow_process_registry.py`：覆盖两个阶段适配器的委派行为。

## 验证

- 精确回归：`tests.test_workflow_process_registry`、`tests.test_model_router_diagnostics`、`tests.test_hollmwood_roles`、`tests.test_writing_api`，43/43 通过。
- 定向：`python smoke_test.py --affected desktop workflow_engines`，9 项通过（定向自检 7 条、0 红）。
- 架构：`python smoke_test.py --architecture`，101/101 通过。
- 默认冒烟：`python smoke_test.py`，8/8 通过。

## 注意

- 首段流式文本使用与 `async_()` 相同的请求序号，避免极快 SSE 分段在工作线程刚启动时被错误丢弃。
- 修改后需重启应用以加载新代码。
