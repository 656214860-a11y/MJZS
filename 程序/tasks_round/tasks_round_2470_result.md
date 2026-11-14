# R2470 收口轮：API 稳定层与架构基线

## 结论

把 API 稳定层、模型组权重、熔断、认证、RPM、重试、流式完整性、台账审计和当前 master 架构欠账整理为一个可继续合入的完整变更集。

## 主要能力

- OpenAI/Responses/Anthropic Messages 协议适配保持统一入口。
- 模型组、权重路由、健康准入、五合一认证开关。
- 主机级 RPM、模型熔断/半开恢复、有界重试与 Retry-After。
- SSE 完成事件校验、响应体/流式上限、gzip/deflate、Content-Length 预检。
- 直连分镜/视频提示词/音频脚本模型组降级与有界格式退避。
- 请求尝试审计、错误分类、重试次数与台账记录。
- 模型管理 UI 支持 `rpm`、`group`、`weight`。

## 架构收口

- `model_pool` 传输层拆分到 `api_endpoints`，保留补丁兼容包装。
- `qwen_adapter → workflow_settings → qwen_adapter` 循环拆除。
- `aigc_lint` 进程边界、临时文件清理与 JSON 解析修复。
- 覆盖率基线刷新到 363 模块 / 59 有覆盖。
- skip 台账与源码双向一致。
- `IdeaChatMixin` 行数、`workflow_settings` 行数、递归参数数回到棘轮上限内。

## 验证

- API/模型池/路由/网关/计量/台账/直连/pet_llm 定向测试通过。
- 模块行数与复杂度棘轮通过。
- 全量架构曾收敛到只剩：`project_status.md` 轮次头（需 master 合入后更新）与 `bare json.loads` 历史债务台账不同步。

## 提交

- 已提交：`d9f570ba27ad6b93957ee54f09e2856673b3faa6`
- 分支：`codex/wip-R2470`
