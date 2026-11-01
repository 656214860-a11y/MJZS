# R558｜结构治理轮（子场景：执行）

## 来源与执行项

- 来源：`tasks_round/tasks_round_547_result.md` J 节。
- 执行：P1-6——将 `asset_batch.show()` 的表单状态、模型配置、检测和启动决策移出 UI，保留 `asset_batch.py` 作为兼容入口及窗口组装层。

## 完成结果

新增无 Tk 的 `asset_batch_controller.AssetBatchController`，集中负责：

- 类别默认值、勾选排除状态与资产计划重载；
- ComfyUI 表单默认值及执行器选项归一（API 工作流占位模型不会传给执行器）；
- 模型检测的重试超时、已删除模型过滤；
- 启动前项目上下文、待生成项、提示词完整性与本地模型/工作流门禁，并返回待确认的未确定提交项。

`asset_batch.show()` 仍为既有兼容入口，只创建/渲染 Tk 控件、绑定事件、将后台结果投回 UI，并保留原有用户确认弹窗和执行/设置服务调用。未改用户数据、设置持久化契约或批量执行契约；未新增功能。

## 改动文件

| 文件 | 变更 |
| --- | --- |
| `asset_batch_controller.py` | 新增 L3 无 Tk 控制器。 |
| `asset_batch.py` | 注入控制器；窗口保留组装与事件绑定。 |
| `tests/test_asset_batch_controller.py` | 新增无 Tk 回归，覆盖选项归一、检测过滤与启动门禁。 |
| `tests/architecture/_layers.py` | 登记新 L3 模块，继续受依赖方向门禁保护。 |
| `architecture.md`、`PROJECT_MAP.md` | 同步控制器职责及分层。 |
| `project_status.md` | 关闭 P1-6，R182 拆分债务 10 → 9。 |

应用代码仅改动 `asset_batch.py` 与新增 `asset_batch_controller.py` 两个模块，满足最多 3 个模块限制。

## 验证

- `python -B -m unittest tests.test_asset_batch_controller`：3/3 通过。
- `python -B smoke_test.py --affected asset_batch asset_batch_controller`：5 个匹配文件、12 条用例全绿。
- `python -B smoke_test.py`：默认冒烟 8/8 通过。
- `python -B smoke_test.py --architecture`：架构门禁 95/95 通过，无新增红点。

测试仅新增控制器回归，未修改既有测试断言或 fixture；不存在因契约变更调整测试断言的情况。

## 债务状态

P1-6 已完成；R182 可执行拆分债务由 10 项降至 9 项。P0-3 的既有分层/二进制发布阻塞保持不变。
