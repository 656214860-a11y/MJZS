# R2442 可靠性轮：ModelGateway 候选组降级

## 结论

新增零依赖 `ModelGateway`，把候选模型组、健康准入、可重试判定与跨模型降级收进一个入口，向 LiteLLM Router 的“组内重试、组间 fallback”靠齐。

## 关键改动

- [model_router.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_router.py)
  - 新增 `ModelGateway.chat()` / `stream()`。
  - 候选模型按顺序尝试：跳过 `ModelRouter.usable()` 不可用或健康未通过的模型；失败且可重试时尝试下一个候选；成功后返回并附 `attempts`。
- [test_model_gateway_robustness.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/tests/test_model_gateway_robustness.py)
  - 增加候选组 fallback 用例，验证 `a(429) -> b(成功)` 的降级链。

## 验证

- 定向 unittest 86/86 通过（含新增 Gateway 用例）。

## 提交

- 已提交：`370dc9e5169b917ce9a277462235cb57ef5fa38c`
- 分支：`codex/wip-R2442`
