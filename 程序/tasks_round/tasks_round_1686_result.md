# R1686 修复轮：模型管理「测试连接」HTTP 403 / error code 1010

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（源码轮）。仅改模型 HTTP 传输的请求头，不动密钥、路由与重试逻辑。
2. **测试跑了吗？三个基线过了吗？** 定向 `-k model_pool_redirects model_failure_route model_call_error_kind model_router_diagnostics pet_llm`：92 条 0 红；默认冒烟 8/8；`function_size_ratchet agents_md module_size_ratchet test_layers` 全绿。未跑安全全量。
3. **project_status.md 的欠账少了吗？** 没有减少。本轮改源码，全量欠账 **+1**。

## A 根因与改动

- 现象：新增 opencode 的 API 配置后测试连接返回 `HTTP 403, error code: 1010`。1010 是 Cloudflare 的「浏览器签名被禁」，对默认 `User-Agent: Python-urllib/3.x` 的请求会直接拒绝。
- `model_pool.py`：新增常量 `HTTP_USER_AGENT = 'ManjuAssistant/1.0'` 与 `_request_headers(headers)`（大小写不敏感检查，调用方已给 `User-Agent` 则原样保留）；`_http_transport` 与 `http_stream` 构造 `Request` 时改用它。测试连接（`probe`）与正式调用共用这两个函数，所以一并生效。
- `tests/test_model_pool_redirects.py`：新增 `test_requests_carry_a_non_urllib_user_agent`（非流式＋流式，走真实 urllib 重定向机制，断言发出的头为常量且不含 `Python-urllib`）与 `test_caller_supplied_user_agent_is_kept`。既有断言未动。

## C 未验证

- **根因是推断**：未用用户的真实密钥与网关复验。若补 User-Agent 后仍报 403／1010，说明网关还按 IP 或其它指纹拦截，需要贴出完整返回再查。
- 未改 `api_endpoints`／`token_saver` 的其它请求路径（如有独立的 urllib 调用，仍是默认签名）；是否存在这类调用未在本轮排查。
