# R706 结构治理轮（执行）结果：服务返回契约试点

## 独立任务书

来源：`架构模块接口统一.txt` 第一批第 1 项。建立 L2 写服务统一结果契约，并在不超过三个生产模块的范围内，迁移一个已有发布器注入的生产写入口。

## 完成内容

- 新增 L0 `service_contract.py`：唯一结果结构为 `{ok, reason, recoverable, data}`；`UserError` 可直接展示，`SystemError` 只记录详情、由上层显示通用提示，`Cancelled` 不计失败。
- L2 `delivery_import_service.import_final_master()` 已成为试点：不再返回裸路径或用业务异常传递结果；成功返回 `ServiceResult.data`，格式／空文件问题返回 `UserError`，发布环境失败记录日志并返回 `SystemError`。
- `desktop.py` 的既有异步调用点消费结果对象：可修正输入仍显示原有具体提示，系统失败改为通用提示，不泄露内部失败原因。
- `AGENTS.md` 权威源表、`architecture.md` 分层表与 L2 职责说明已同步；`tests/architecture/test_service_return_contract.py` 是新统一入口的架构门禁，防止 L0/L2 登记漂移。

## 测试说明

本次改测试因契约变更，断言未弱化：原来验证的导入、源文件保留、注入发布器和格式／空文件拒绝均保留；仅将对裸路径／`ValueError` 的断言改为对结果对象、可恢复性和原因的断言。

## 验证

| 项目 | 结果 |
| --- | --- |
| 定向 `run_selftests.py -k service_contract delivery_import --safe` | 7 条 / 0 红 |
| 默认 `smoke_test.py` | 8/8 |
| `smoke_test.py --architecture` | 105/105 |
| 完整 `run_selftests.py --all --safe` | 3,411 条 / 0 红（749.0 秒） |

完整安全日志：`维护记录/r706_service_result_safe_all.log`。

## 边界与后续

本轮只迁移交付成片导入这一条 L2 写路径；音频、首帧及其他 L2 写服务仍维持原接口，须在后续独立迁移轮逐批接入本契约。未修改用户项目数据、SKILL、注册表或 UI 布局。

`[TASK_COMPLETE]`
