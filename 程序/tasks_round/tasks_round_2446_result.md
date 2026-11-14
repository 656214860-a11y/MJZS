# R2446 可靠性轮：API 网关稳定性与 LiteLLM 对齐

## 结论

把此前分散在 R2435–R2445 的 API 稳定层改动压缩为一个完整变更集，并补上模型管理 UI 的 `rpm` 与 `group` 字段。分支回到 master 之上、领先 1 个提交，恢复可领轮次状态。

## 关键改动

- 传输层：有界重试、Retry-After、gzip/deflate 解压、响应体/流式缓冲上限、Content-Length 预检、主机级 RPM 限流。
- 模型准入：`context_length` 缺失拦截、五合一认证 `certify()`、健康记录阻止路由、`REQUIRE_CERTIFIED_FOR_UNATTENDED` 开关。
- 网关：`ModelGateway` 候选组降级、`group_candidates()`、`for_group()`／`chat_group()`／`stream_group()`。
- 审计：`RequestLedger.record_attempt()` 与 `metered()` 记录状态/错误类/Retry-After/协议/重试次数。
- 结构化输出：分镜/视频提示词/音频脚本有界指数退避。
- UI：[pet_models_ui.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/pet_models_ui.py) 增加“每分钟请求上限”与“模型组”字段，并接入回填/保存/新建清空与本地/API 显隐。

## 验证

- 定向 unittest：模型池/路由/网关/直连/台账相关用例通过。
- 架构：`test_no_circular_import` + `test_layers` 8/8 通过。
- UI 相关测试因仓库既有 `skip_reasons` 导入路径问题无法以当前命令直接单跑，未视为本轮回归。

## 提交

- 已提交：`ff86992b`
- 分支：`codex/wip-R2446`
