# Round 230 结果：首帧自动终态职责拆分

## 改动文件

- `desktop.py`
- `project_status.md`

## 改动摘要

将首帧自动入口未派发时的完成／失败判定收拢到 `_finish_unsent_auto_keyframe()`，入口只负责批次调度；删除不可达返回。本轮同时集中登记 R226–R230 状态。

## 验证结果

- 首帧自动缺分镜出口与分层校验：3/3 通过。
- 默认 `smoke_test.py`：8/8 通过。
- 完整 `FrameBatchSeamTests` 发现 9 个既有夹具错误：裸 `studio` 缺少 `episode_dir`；未在本轮范围内修复。
