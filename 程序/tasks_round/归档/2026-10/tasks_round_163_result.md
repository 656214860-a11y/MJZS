# 第 163 轮：三虎模式状态测试迁移

## 改动

- 将 `test_sanhu_mode.py` 的测试实现迁入 `tests/test_sanhu_mode.py`。
- 根目录保留兼容入口，不影响现有直接执行方式。

## 验证

- 测试创建最小临时项目，并使用没有窗口的 Desktop 替身；未启动 GUI、网络或真实 Agent。
- `python test_sanhu_mode.py`：9 条通过。
- `python -m unittest tests.test_sanhu_mode`：9 条通过。
- `python run_selftests.py --serial -k test_sanhu_mode`：9 条通过，增量台账刷新。

## 风险与下一步

- 覆盖手动/自动切换、自动开关接管、结构剧本完成前的下游阻塞、自动派发和失败停机。
- 接下来继续审查纯逻辑和替身驱动的三虎测试；真实桌面回调保持分离，避免引入 UI 时序不稳定。
