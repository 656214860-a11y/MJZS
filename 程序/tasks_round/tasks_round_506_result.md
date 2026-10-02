# R506 修复轮：Responses 协议与回归收口

## 结论

- P1 已完成：Responses 调用使用原生请求字段，并从原生嵌套内容提取文本。
- P0/P1 已由完整安全全量回归收口；下一优先级为 P2 云视频设置的密钥显示保护。

## 变更

1. `model_router.ModelAdapter` 对 `responses` 仅发送 `max_output_tokens`，不再混用 Chat Completions 的 `max_tokens`。
2. 响应仅汇聚 `output[*].content[*].type == 'output_text'` 的文本；工具调用、拒绝项、空输出和 HTTP 错误不伪造回复。
3. 云视频的 `key_provider=model_pool` 配置直接读取 `model_secrets` 的 DPAPI 记录，消除 `api_endpoints` 与 `model_pool` 的循环依赖。
4. 原子写入架构登记移除已不直接写盘的 `model_pool`，使静态门禁继续约束真正的写入边界。

## 验证

- 模型、云视频、模型池与令牌回归：335/335 通过。
- 原子写入与循环依赖架构门禁：4/4 通过。
- `run_selftests.py --all --safe`：3,239/3,239，852.9 秒，0 个失败文件。
- `smoke_test.py`：8/8 通过。

## 后续

- P2：云视频 API Key 输入默认掩码，显式显示后自动重新掩码，并补充无头 Tk 回归。
