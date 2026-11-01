# 第 159 轮：HOLLMWOOD 四角色协作测试迁移

## 改动

- 将 `test_hollmwood_roles.py` 的实际测试实现迁入 `tests/test_hollmwood_roles.py`。
- 根目录保留兼容入口，确保既有执行命令仍有效。

## 验证

- 用例以本地 `ModelAdapter` 替身模拟每个角色响应，日志和状态均写入临时目录；未发起模型或网络请求。
- `python test_hollmwood_roles.py`：6 条通过。
- `python -m unittest tests.test_hollmwood_roles`：6 条通过。
- `python run_selftests.py --serial -k test_hollmwood_roles`：6 条通过，增量台账刷新。

## 风险与下一步

- 覆盖导演空正文的一次受控重试、审核空正文、取消边界和四角色串行编排；不涉及真实 Provider 配置。
- 后续继续迁移隔离测试，并针对已发现但未能稳定复现的 Tk `after` 警告保留独立诊断，不混入本轮。
