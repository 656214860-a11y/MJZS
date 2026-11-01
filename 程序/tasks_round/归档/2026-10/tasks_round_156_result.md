# 第 156 轮：进度广播测试迁移与阶段断言修正

## 改动

- 将 `test_broadcaster.py` 的测试实现迁入 `tests/test_broadcaster.py`，根目录保留兼容入口。
- 修正已经滞后的固定阶段总数断言：总阶段数从 `pet_bus.STAGES` 动态读取；三虎资产阶段也按规范阶段 ID 计算其序号。

## 验证

- 迁移后的第一次运行发现旧断言仍假设 `3/11`，而当前规范为 12 阶段；这是测试陈旧，不是广播实现异常。
- `python test_broadcaster.py`：4 条通过。
- `python -m unittest tests.test_broadcaster`：4 条通过。
- `python run_selftests.py --serial -k test_broadcaster`：4 条通过，增量台账刷新。

## 风险与下一步

- 测试只写入临时目录的日志；没有写入用户项目或调用网络。
- 继续逐项迁移可隔离的根目录测试；对真正依赖桌面窗口或外部进程的用例先保留在根目录并审查。
