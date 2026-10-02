# 第 161 轮：自检运行器测试迁移

## 改动

- 将 `test_selftests.py` 的测试实现迁入 `tests/test_selftests.py`。
- 根目录同名文件改为兼容入口，保留原有直接运行行为。

## 验证

- 用例只写入临时目录，并对导入失败和后台清理使用 mock；未触发真实项目文件、网络或模型调用。
- `python test_selftests.py`：11 条通过。
- `python -m unittest tests.test_selftests`：11 条通过。
- `python run_selftests.py --serial -k test_selftests`：11 条通过，增量台账刷新。

## 风险与下一步

- 该测试覆盖安全串行策略、可恢复超时、分块调度、缩略图后台清理和 smoke 参数策略。
- 继续迁移无外部副作用的根目录用例；在全量检查前，仍需单独诊断历史 Tk `after` 警告。
