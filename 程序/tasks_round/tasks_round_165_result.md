# 第 165 轮：云端视频会话测试迁移

## 改动

- 将 `test_cloud_video.py` 的实际测试实现迁入 `tests/test_cloud_video.py`。
- 根目录保留兼容入口，既有直接执行命令不受影响。

## 验证

- 审计确认用例只测试 Provider 标签与会话目录去重，全部文件在临时目录；没有 HTTP 请求、密钥读取或模型调用。
- `python test_cloud_video.py`：7 条通过。
- `python -m unittest tests.test_cloud_video`：7 条通过。
- `python run_selftests.py --serial -k test_cloud_video`：7 条通过，增量台账刷新。

## 风险与下一步

- 覆盖万相/Seedance 标签、同配置复用目录、模型变化创建新目录及损坏配置容错。
- 继续按隔离性审查根目录测试；Provider 的真实请求路径只通过专门的替身/集成测试验证，避免夜间触发费用。
