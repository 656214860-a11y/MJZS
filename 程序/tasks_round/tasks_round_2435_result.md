# R2435 可靠性轮：API 模型池稳定层补闸

## 结论

按用户确认的零依赖路线，补齐模型直连 API 的四个工程闸门：发送前准入、有界重试与 Retry-After、SSE 生命周期完整性、请求体字节闸与响应信封校验。未引入第三方依赖，未新增顶层生产模块。

## 关键改动

- [model_pool.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_pool.py:843)
  - `_http_transport` 对可重放状态（408/425/429/5xx）与网络层异常做最多 3 次有界重试；解析 `Retry-After` 秒/日期，指数退避加抖动，封顶 3 秒。
  - `http_stream` 只有在收到 `[DONE]` 或非空 `finish_reason` 时才视为完整流；连接结束但未完成的事件标记为失败，不再把半截流当成功。
  - 新增 `model_admission_error()`：空模型 ID、空地址、未知协议、无人值守任务缺 `context_length` 均拒绝发送。
- [storyboard_direct_api.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/storyboard_direct_api.py:203)
  - 真实直连分镜/视频提示词/音频脚本构造适配器前过准入门；缺上下文窗口时不进入无人值守路径，提示先补全模型管理字段。
- [writing_api.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/writing_api.py:267)
  - 增加 `DIRECT_REQUEST_MAX_BODY_BYTES`（8 MiB）请求体字节闸，与 token 上下文窗口分开，避免直接撞上网关 413。
- [model_router.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_router.py:104)
  - 新增 `response_envelope_error()`，chat 协议成功但缺 `choices` 时判为伪兼容/坏回执，并在 `ModelAdapter.chat` 中生效。
- 新增 [test_model_gateway_robustness.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/tests/test_model_gateway_robustness.py:1)，覆盖准入、Retry-After、SSE 完整性与响应信封。

## 验证

- 定向 unittest：100/100 通过（含新用例、模型池、分镜/视频/音频直连、错误分类、重定向、潜伏缺陷）。
- 架构：`test_no_circular_import` + `test_layers` 8/8 通过。
- 未跑全量；本轮为可靠性/源码轮，全量欠账按 §5 记录。

## 提交

- 已提交：`20eed281cdb8381a09849c192d6cb4842603f6e8`
- 分支：`codex/wip-R2435`
