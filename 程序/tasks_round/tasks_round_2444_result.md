# R2444 可靠性轮：模型组候选字段与分组路由基础

## 结论

模型记录新增 `group` 字段，并增加 `group_candidates()`，为 LiteLLM 式“同一逻辑模型多个部署/密钥”提供数据基础。当前未改 UI，先落字段与分组候选函数。

## 关键改动

- [model_pool.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_pool.py)
  - `FIELDS` 增加 `group`。
  - 新增 `group_candidates(group, current_model, records=None, program=None)`：当前模型优先，组内其他记录随后。
- [test_model_gateway_robustness.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/tests/test_model_gateway_robustness.py)
  - 增加组候选顺序用例。

## 验证

- 定向 unittest 87/87 通过。

## 提交

- 已提交：`840d7a10c31383c930a04c39df9f450f6bdf4986`
- 分支：`codex/wip-R2444`
