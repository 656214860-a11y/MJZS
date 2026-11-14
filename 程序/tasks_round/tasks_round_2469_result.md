# R2469 可靠性轮：模型组权重路由

## 结论

模型记录新增 `weight` 字段，组内候选按权重降序排列；权重相同保持当前模型优先。模型管理页增加权重输入，形成 LiteLLM 式加权部署路由的零依赖基础。

## 关键改动

- [model_pool.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_pool.py)
  - `FIELDS` 增加 `weight`。
  - `group_candidates()` 按权重降序、当前模型优先、模型 id 稳定排序。
- [pet_models_ui.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/pet_models_ui.py)
  - 模型管理表单增加权重输入与回填/保存/新建清空。
- [test_model_gateway_robustness.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/tests/test_model_gateway_robustness.py)
  - 增加权重排序用例。

## 验证

- 网关/模型池 78/78 通过。
- 模块行数与复杂度 4/4 通过。

## 提交

- 已提交：`dc03c9bb10f26ff5804d7a0b091557573b864f2a`
- 分支：`codex/wip-R2469`
