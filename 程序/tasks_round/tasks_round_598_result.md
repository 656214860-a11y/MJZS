# R598｜性能轮：剧本准备流式体验

## 本轮结论

- OpenAI 兼容 chat 协议新增 SSE 分段传输；`ModelAdapter.stream()` 保持既有 `chat()` 不变，并在非 chat 协议、协议不支持或流失败时回退完整响应。
- HOLLMWOOD 仍完整执行导演、编剧、编辑、演员与三次导演审核；仅演员成稿可逐段回显。临时正文经线程安全队列由 Tk 主线程显示为“生成中”气泡，成功后以正式回复替换，取消或失败不落盘。
- 严格四角色质量路径未减少任何一次调用或审核。

## 文件

- `model_pool.py`：SSE 读取与 `[DONE]` 收束。
- `model_router.py`：保持兼容的 `stream()` 与非流式回退。
- `hollmwood_roles.py`、`writing_api.py`、`desktop.py`：演员成稿回调、队列投递及临时对话显示。
- `tests/test_model_router_diagnostics.py`：分段回调和标准结果回归。

## 验证

- 流式适配器／剧本协作／剧本 API 精确回归：36/36 通过。
- `smoke_test.py --affected desktop writing_api hollmwood_roles model_router model_pool`：100 条、0 个文件有红。
- `smoke_test.py`：8/8 通过。

## 后续

- 下一项为取消请求的网络层协作与统一排队；普通非流式协议仍保持既有请求完成后检查取消的语义。
