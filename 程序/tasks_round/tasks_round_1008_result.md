# R1008 云视频会话项目上下文迁移

## 已完成

- `cloud_video_service` 的会话目录与旧会话兼容凭据查询改为只接收 L3 注入的 `ProjectContext`。
- 云视频 L4 页面通过 `stage_execution_service` 的 L3 包装器请求会话目录和凭据，不再向 L2 传递裸项目根路径。
- 增加架构边界测试，禁止 L2 自行构造 `ProjectContext`。

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_cloud_video tests.architecture.test_cloud_video_settings_boundary tests.architecture.test_project_context_boundary`

## 未完成

- 路线图第 2 项仍有 7 个服务待迁移或审计；后续继续按清单顺序处理。

## 提交凭据

- 实现提交：`9a4fadd`。
