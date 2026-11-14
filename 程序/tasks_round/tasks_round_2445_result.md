# R2445 可靠性轮：ModelGateway 按 group 生成候选组

## 结论

`ModelGateway` 增加 `for_group()` 与 `chat_group()`/`stream_group()`，用模型记录的 `group` 字段直接构造候选组网关，当前模型优先。仍属基础设施，未接入现有发送链路。

## 关键改动

- [model_router.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_router.py)
  - `ModelGateway.for_group()` 调 `model_pool.group_candidates()` 构造候选组。
  - `ModelGateway` 保存默认候选组，新增 `chat_group()`/`stream_group()`。
- [test_model_gateway_robustness.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/tests/test_model_gateway_robustness.py)
  - 增加按 group 构造网关并优先使用当前模型的用例。

## 验证

- 定向 unittest 26/26 通过。

## 提交

- 已提交：`e6ba75f906c78ed0931feca8bb20fa0a37f0716d`
- 分支：`codex/wip-R2445`
