# Round 416 结果：模型请求阶段并发修复

## 目标与范围

按规则 30 处理已知阻塞的首个可自主推进项：阶段级上下文预算的并发限制。
白模视频上传验收仍需用户指定镜头与外发授权，未触碰该项。

## 改动

- `workflow_process_registry.py`：新增无业务依赖的模型进程槽位预留/释放；进程注销会释放关联槽位。
- `workflow_engines.py`：在 L3 依据 `stage_parallel.CONFIG` 和全局上限计算容量；普通与 Qwen 的后台、交互启动均在启动前占位，异常、结束和停止路径均释放。
- `qwen_adapter.py`：Qwen 交互进程重新纳入统一进程台账；容量策略保持由 L3 工作流入口负责，避免 L1 反向依赖阶段并行模块。
- `tests/test_workflow_process_registry.py`：覆盖阶段上限、中文显示名对应的同阶段限制、全局上限及释放后的重试。
- `tests/test_workflow.py`、`tests/test_qwen_adapter.py`：启动夹具在断言后注销模拟进程；因新生命周期契约补齐清理，既有断言未弱化。

## 根因与复现

此前仅有 96,000 字符上下文预检，多个模型请求可同时绕过阶段配置启动；Qwen 交互窗口还没有登记在可停止的进程台账中。
连续预留同一 `script` 阶段的第二个槽位会稳定触发“剧本准备已有 1 个模型请求”的等待提示；释放第一个槽位后可再次预留。

## 验证

- `python -m unittest tests.test_workflow_process_registry tests.test_workflow tests.test_qwen_adapter`：84/84 通过。
- `python smoke_test.py --architecture`：36/36 通过。
- `python smoke_test.py`：8/8 通过。

## 未完成项

- 优化清单的“摘要替代重复全文”尚未覆盖其他阶段，原总项继续保留。
- 白模视频上传真机验收继续等待用户授权；未上传任何用户素材。
