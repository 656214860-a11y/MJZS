# R1614 逐适配器失败分类一致性测试（Q5）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round_1610_result.md) J 第二批 Q5）。
- 测试：定向 `tests.test_adapter_failure_conformance` 2/2（含 4 适配器 × 8 场景子用例）通过；架构门禁 350/350 通过（171.580 秒）；默认冒烟 0 失败。完整安全全量未跑。
- 欠账：本轮只加测试，`project_status.md` 全量欠账计数 +1，未清。

## 改动

新增 `tests/test_adapter_failure_conformance.py`：把《生成服务失败处理契约》的判定表钉在每个**内置文本适配器**上（`DeepSeekAdapter`/`GPTAdapter`/`QwenAdapter`/`AnthropicAdapter`），用桩传输喂入回执，断言 `model_router.failure_policy` 的分类一致：

| 场景 | 期望 acceptance / reason_code / retryable |
| --- | --- |
| 429 无受理证据 | not_accepted / rate_limit / 可重试 |
| 5xx 受理未知 | unknown / server_error / 不重试 |
| 5xx 明确未受理 | not_accepted / server_error / 可重试 |
| 401 | not_accepted / authentication / 不重试 |
| 400 / 422 | not_accepted / unsupported_request / 不重试 |
| 有远端编号 | accepted / server_error / 不重试 |
| 超时 | unknown / receipt_unknown / 不重试 |
| 成功 | accepted / succeeded / 不重试 |

同时断言失败回执不带正文（`text == ''`），防止错误路径泄露内容。

## 与既有测试的关系（避免重复）

`tests/test_model_failure_route.py` 已覆盖**路由层**的切换/预算/取消/流式防重提；本文件补的是**适配器层**：同一批回执经每个真实适配器的 `chat()` 后分类不得漂移。二者互补，不重复。

## 边界

- 覆盖内置文本适配器；图像/视频/音频（Comfy、云图、云视频等）走各自台账而非 `failure_policy`，不在此表（其失败处理见 O9/视频版本台账相关轮次）。
- 桩传输不发真实网络请求，不产生费用。

## 下一项

Q6（计费/金额算术不变量测试）。