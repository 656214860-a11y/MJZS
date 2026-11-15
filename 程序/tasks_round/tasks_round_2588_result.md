# R2588 结果：SWE-2 T3 统一 HTTP 弹性层（第一轮：建层＋边界门禁）
<!-- round-evidence: {"commit_base": "332353f1", "credential_hits": 0, "evidence_sha256": "860692a508a38ab0", "exit": 0, "failed": 0, "passed": 49, "round": 2588, "tests": "run_selftests.py -k http_client http_boundary layers agent_doc service_return"} -->

## 类型与三问

- 类型：功能轮（L1 新模块＋架构门禁）。
- 测试：默认冒烟 8/8 绿；`run_selftests.py -k "http layers circular static_hygiene agent_doc service_return skip_hygiene"` 全绿（http_client 11 条、test_http_boundary 2 条、test_outbound_http_authority 3 条等）。
- project_status 欠账：无新增。

## 交付

- `http_client.py`（L1）：`request_json()` 超时必填；错误码经 `error_codes` 分类（429→E-NET-RATE-LIMIT、401/403→E-AUTH-REJECTED、5xx→E-NET-SERVER、超时→E-NET-TIMEOUT、连接失败→E-NET-UNREACHABLE）；指数退避+抖动；响应体上限与 Content-Length 预检；Authorization/Cookie 等敏感头在结果中脱敏；带 body 的 POST 默认永不重试（计费接口），`allow_retry_post=True` 显式放行；按 host 连续失败熔断（5 次/30 秒）。urllib 按第 34 期规则函数内惰性加载。
- `tests/test_http_client.py`：11 条——成功解析、POST 不重试、GET 退避重试、429、4xx 不重试、401、超时、不可达、响应上限、头脱敏、熔断。
- `tests/architecture/test_http_boundary.py`：AST 门禁，`urlopen`／`build_opener` 只许 `http_client.py` 与 10 个存量白名单文件；白名单条目失效即红（只减不增）。
- 登记：`_layers.py` L1、`architecture.md` 门禁清单、`AGENTS.md` §2.3 第 42 条改写、`PROJECT_MAP.md` 模型与安全行。

## 盘点（T3 步骤 1）

直连 `urlopen`／`build_opener` 存量 10 文件：agent/volcengine.py、agent/wan.py（计费 POST，设计上不重试）、api_endpoints.py（已有 _http_transport 完整重试/限流/上限）、platform_tools.py（唯一建连权威）、batch_frames_tool/batch_frames.py、local_video.py、seedream_api.py、tts_api.py。comfy_service/qwen_setup_dialog/agent/core 仅用 urllib 其它部件，不在白名单。

## 后续轮次

- 迁移 volcengine/wan（计费 POST，需保持 ArkRejected 语义与不重试）→ api_endpoints._http_transport 收编 → local_video/seedream/tts/batch_frames → platform_tools 最后。
- 每轮 ≤3 个调用方；迁移后从白名单删除对应行。

## 提交

- 待回填 hash。
