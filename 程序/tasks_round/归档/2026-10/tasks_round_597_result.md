# R597｜性能轮：剧本准备 Agent 安全耗时观测

## 本轮结论

- 为 HOLLMWOOD 四角色协作的每一次模型调用补充安全耗时观测，记录请求开始至模型适配器返回的 `elapsed_ms`，以及不含正文的 `request_chars`。
- 观测写入既有 `model_diagnostics/*.json` 的 `context`，不记录提示词、回复、密钥或用户项目文本；协作顺序、重试、取消边界、模型接口和产物写入均未改变。
- 本轮的价值是建立后续流式与并发优化的可比较基线，不是性能改进。四角色严格质量路径保持默认启用。

## 改动文件

- `hollmwood_roles.py`：在单次 `adapter.chat()` 前后使用 `time.perf_counter()`；将毫秒耗时和请求字符数交给既有诊断记录器。
- `tests/test_hollmwood_roles.py`：断言每份角色诊断均带有非负 `elapsed_ms` 与 `request_chars`。
- `project_status.md`、本结果文件：登记轮次与验证事实。

## 观测语义

- `elapsed_ms`：单一角色请求在本地适配器层的完整等待时间，可分别比较导演、编剧、编辑、演员及审核步骤。
- `request_chars`：系统提示和本次请求提示的字符总数，仅用于识别上下文预算变化；不保存其内容。
- 这不是端到端 UI 耗时，附件准备、排队和界面渲染将在后续性能轮分别纳入同一链路。

## 验证与自审

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_hollmwood_roles`：10/10 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --affected hollmwood_roles writing_api`：定向门禁 30 条、0 个文件有红。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8/8 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --architecture`：101/101 通过。
- 自审：无新依赖、无用户项目数据写入；仅增加诊断元数据，接口与严格四角色质量门不变。
