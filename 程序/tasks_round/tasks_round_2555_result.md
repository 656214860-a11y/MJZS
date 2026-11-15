# R2553 结果：SWE-2 优化清单批次 1（T2／T3／T4／T5 落地）

1. 类型：功能轮（开发期工具与契约旁路，不改阶段行为）。冒烟 8/8；架构门禁与相关测试见下；本轮未触发全量。`project_status.md` 欠账未变。
2. 范围：
   - T4：新增 L0 `error_codes.py`（17 个错误码，带可重试／用户说明／修复建议）。保持 `ServiceResult` 四字段不变，错误码经 `data['error_code']` 携带（`code_data`／`code_of`），`from_http_result` 映射 `api_endpoints._http_transport` 结果。
   - T3：核验现状——`api_endpoints._http_transport` 已含重试、退避、限流、响应体上限与脱敏，审计 26 已限制出站调用模块，故不再新建第二套 HTTP 客户端（规则 28）；本轮只补错误码映射。熔断未做，记为后续。
   - T5：核验现状——全仓无裸 `except:`，`except Exception: pass` 已由棘轮限制在 14 处（日志基础设施等）。此前口径 533 为粗略文本匹配，不代表静默吞异常数。新增「禁止裸 except」门禁。
   - T2：新增 `pyproject.toml`、`dev-requirements.txt`、`scripts/dev_lint.py`、`dev.py lint`。ruff 只开 E9／F821／F601；mypy 严格模式覆盖 `service_contract`、`error_codes`。`distribution_manifest.md` 登记这些文件为开发期文件，不进分发副本。
3. 未完成（后续轮）：T1 远端 CI、T6 安全、T7 测试拆分并行、T8 门禁补强、T9 归档与文档、T10 包化。
