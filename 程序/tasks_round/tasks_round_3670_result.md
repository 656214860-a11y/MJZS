# R3670 — A12 第三批 HTTP 重试预算与提交结果核对
<!-- round-evidence: {"commit_base": "abbb7f83", "credential_hits": 0, "evidence_sha256": "6a935a40373350a0", "exit": 0, "failed": 0, "passed": 211, "round": 3670, "tests": "run_selftests.py -k test_http_client test_platform_tools test_l1_transport_requests test_model_gateway_robustness test_model_router test_model_failure_route test_l1_reliability_r3248 test_pet_llm"} -->

## 三问

1. §3.8 可靠性轮。自 R3662 的 `abbb7f83` 在专用工作树分支 `codex/a12-retry-budget` 开工，先领 R3670，再改生产代码。生产改动限 `contract/platform_tools.py`、`infra/http_client.py`、`infra/api_endpoints.py`。车道范围扫描发现前置 A10–A12、foundation 和 L2 的既有路径重叠，合入时需按符号复核。
2. 默认冒烟 8/8，含隐藏桌面探针 9/9。定向与架构结果见下。安全全量未运行，共享最近通过的回执为 R3633。
3. 降低了默认传输重试叠乘和取消后发送的风险。非幂等 POST 的不明回执明确要求先核对供应商，继续使用现有 Seedream 未决流程。剩余缺口见末节。

## 行为与红测

- 默认 Requests 适配器每次调用最多发送一次，保留 TLS 校验、拒绝重定向及清理行为。通用 HTTP 循环计算尝试数和退避。模型 GET 使用原有共享计数。
- 执行取消或超过 deadline 后停止发新请求。重试等待钳制在剩余时限内，默认用取消事件唤醒。通用 HTTP 对 Retry-After 额外设 30 秒上限，模型 HTTP 保留现有 60 秒上限。
- 通用非重放 POST 遇到断线、超时、HTTP 408 或 5xx，返回 `acceptance=unknown` 及 `recoverable=False`。显式允许重放的 POST 保留原接口，调用方须先确认请求可安全重放。模型对话沿用既有可重放策略及共享预算。
- 生产改动前用同一本机假服务见红。持续 503 实际 9 次而预算为 3，退避取消后继续发请求，断线 POST 虽只发 1 次却把结果标为可重试。测试仅访问 127.0.0.1。

| 本机假服务场景 | 最终请求数 | 结果 |
| --- | --- | --- |
| 通用 GET 持续 503，配置 2 次重试 | 3 | 计数与预算一致 |
| 模型 GET 持续 503，共享预算 2 | 2 | 共享预算归零 |
| 退避中取消 / 预取消 | 1 / 0 | 后续发送被阻止 |
| 429 携带 Retry-After 7200 秒，虚拟时间推进到 deadline | 1 | 等待被剩余时限钳制 |
| 通用非幂等 POST / Seedream 付费入口，服务器收件后断开 | 各 1 | 通用结果为 unknown，Seedream 抛出 Uncertain |
| 已明确允许重放的通用 POST，503 后恢复 | 2 | 既有显式重放契约通过 |

## 验证与提交

- 终态定向自检 211/211。分支覆盖率工具定向测量 207/207，仅刷新本轮三行，模型 HTTP 30/86、平台工具 53/135、通用 HTTP 19/24。覆盖率下限保留。纯度台账删除实测已消失的 urllib3 导入豁免。相关架构门禁复测 32/32。
- 受影响冒烟 9/10，选中 43 个文件，743/744 用例通过。唯一红为 `test_api_cache_usage.ClaudeSystemBlockTests.test_writing_reply_sends_skill_rules_as_the_cached_block`，在进入 HTTP 前缺 `sd-decision-engine/SKILL.md`。起点指向未展开的 SKILL gitlink `1a43ae5a`，仓库没有该路径的 .gitmodules 映射。用起点的三个生产 Git blob 在内存加载后单独重演，同一用例在同一文件缺失处报错。
- 完整架构 602/605（2 失败、1 错误），与 R3662 的失败集合一致。分别为 `test_performance_history_is_declared_as_historical_only`（缺 `维护记录/基准历史.json`）、`test_round_number_continuous`（分支状态页滞后）、`test_script_stages_name_only_their_approved_00_references`（缺 `screenplay-gate-engine.md`）。最终架构和定向使用通过依赖白名单的本机 Python 3.14。
- 分支状态页仍为 R3409。报告落盘后轮次关系应为 3671，按分支规则交由主线补记。因基线实测有红，按规则提交 `R3670-FAIL: A12 HTTP 重试预算与付费提交回执` 检查点。提交哈希可由该唯一轮次标题和机器证据定位。

## 剩余缺口

- 在途请求可能已到供应商。取消或 I/O timeout 不能推断撤单与退款，自动查单、跨进程去重及供应商真实账单仍待验收。
- 本轮覆盖默认 Requests 和两个 HTTP 调用入口，未逐条验收上层工作流重试、其他付费供应商、长任务关窗与真实子进程树。
- A12 仍需完成跨进程恢复矩阵、缓存与队列容量、启动与长任务响应的同条件测量。此轮只交付第三批。
