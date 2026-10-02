# 第 158 轮：HOLLMWOOD 进度队列测试迁移

## 改动

- 将 `test_hollmwood_ui_queue.py` 的实现迁入 `tests/test_hollmwood_ui_queue.py`。
- 根目录保留兼容入口，维持既有直接执行命令。

## 验证

- 用例仅通过 `Desktop.__new__` 构造无界面对象，使用内存队列、临时目录及状态替身；不启动 Tk 窗口、网络或模型请求。
- `python test_hollmwood_ui_queue.py`：2 条通过。
- `python -m unittest tests.test_hollmwood_ui_queue`：2 条通过。
- `python run_selftests.py --serial -k test_hollmwood_ui_queue`：2 条通过，增量台账刷新。

## 风险与下一步

- 测试仍导入 `desktop`，因而会覆盖该模块的导入可用性；隔离的是 UI 实例化与外部请求，不是模块依赖。
- 下一轮继续迁移可安全隔离的逻辑测试，并优先审查仍带固定阶段计数的断言。
