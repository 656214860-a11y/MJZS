# R456 结构治理轮结果

## 轮次自检

1. 本轮是功能轮还是整理轮？结构治理轮：收敛本地视频镜头删除的持久化边界。
2. 测试跑了吗？三个基线过了吗？定向 58/58、架构 63/63、默认冒烟 8/8 均已通过；全量安全基线沿用 R451 的 3,143/3,143，未在本轮重跑。
3. project_status.md 的欠账少了吗？少了一项 L5 直接修改并保存视频删除标记的欠账；白模视频真实上传验收仍按用户约束等待授权。

## 改动

- 新增 `video_lifecycle_service.mark_video_deleted()`：拒绝不确定任务；只更新选中镜头的删除标记；使用原子保存；保存失败恢复内存记录。
- `app.App.delete_video_shot()` 保留确认、锁、刷新和提示，委托服务完成状态校验与发布。
- 新增服务行为测试与 `test_video_delete_boundary.py` 静态门禁，防止 UI 重获直接读写职责。
- 同步 `AGENTS.md` 架构门禁清单/基线及 `architecture.md` L2 职责表。

## 验证

- 定向：`tests.test_video_lifecycle_service`、`tests.test_cell_menu`、`tests.test_row_targets`、`tests.architecture.test_video_delete_boundary` 为 58/58 通过。
- 架构门禁：63/63 通过。
- 默认冒烟：8/8 通过。

## 边界

- 未执行任何白模视频上传、未修改真实项目视频素材，也未改“齿轮 → 设置”入口。
