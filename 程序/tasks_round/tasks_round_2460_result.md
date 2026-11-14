# R2460 结构/可靠性轮：模型传输层拆分与补丁兼容

## 结论

把重试、Retry-After、响应解压、响应体/流式上限、RPM 限流和 HTTP/SSE 实现迁到 `api_endpoints.py`，`model_pool.py` 保留薄包装与 `_http_opener` 补丁点；`model_pool.py` 从 1422 行降到 1080 行，回到上限内。

## 关键改动

- [api_endpoints.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/api_endpoints.py)
  - 承接模型 HTTP/SSE 传输实现；新增可注入 `opener`，避免测试补丁失效。
  - 保留 TLS EOF 的固定退避，其他网络/HTTP 重试继续使用有界抖动。
- [model_pool.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_pool.py)
  - 保留 `http_transport` / `_http_transport` / `http_stream` 薄包装。
  - 保留 `model_admission_error`、健康准入、认证配置和模型池业务。

## 验证

- 模型池/传输/重定向/错误分类/日志/网关测试 118/118 通过。
- 计量/台账/三条直连/请求契约/pet_llm 测试 135/135 通过。
- `test_module_size_ratchet` 与复杂度参数/类大小用例 4/4 通过。

## 提交

- 已提交：`173997560336291b7220bda61fa04070f69758b7`
- 分支：`codex/wip-R2460`
