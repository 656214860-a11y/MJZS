# R450 结构治理轮结果

## 改动

- 新增 `keyframe_lifecycle_service.delete_keyframe()`：首帧回收成功后才写 `episode.json`；写入失败会恢复首帧和镜头内存状态。
- `desktop.delete_keyframe()` 保留确认、刷新与状态提示，委托服务处理持久化。
- 新增行为测试与静态边界门禁。

## 验证

- 定向测试：3/3 通过。
- `smoke_test.py --architecture`：60/60 通过（首次运行仅因结果报告未创建触发轮次连续性门禁；补齐后复跑通过）。
- `smoke_test.py`：8/8 通过。
- 主界面“齿轮 → 设置”入口未改动。
