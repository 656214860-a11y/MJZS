# R2468 可靠性轮：模型熔断与半开恢复

## 结论

新增按模型 id 的熔断器：连续 3 次可重试失败后打开 60 秒，冷却后进入半开探测，成功即恢复。已接入 `ModelRouter`、`ModelGateway` 和直连降级链路。

## 关键改动

- [model_router.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_router.py)
  - 新增 `circuit_state()`／`circuit_allows()`／`record_circuit_failure()`／`record_circuit_success()`。
  - `usable()` 跳过 open 熔断模型。
  - `ModelRouter.chat()` 与 `ModelGateway.chat()/stream()` 记录成功/失败。
- [storyboard_direct_api.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/storyboard_direct_api.py)
  - 首选与降级候选都记录熔断结果。
- [test_model_gateway_robustness.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/tests/test_model_gateway_robustness.py)
  - 覆盖 open→half_open→closed 生命周期。

## 验证

- 网关/失败路由/诊断/直连 37/37 通过。

## 提交

- 已提交：`fbc43c171d6792d883c55e11508444be357a5222`
- 分支：`codex/wip-R2468`
