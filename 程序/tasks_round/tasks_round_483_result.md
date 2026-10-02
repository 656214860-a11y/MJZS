# R483 结构治理：云视频会话设置发布服务化

## 轮次结论

- 本轮是结构治理轮：云视频设置 UI 不再直接写会话配置或项目工作区偏好。
- 三个基线均通过：定向 9/9、架构 79/79、默认冒烟 8/8、全量 3,202/3,202。
- `project_status.md` 欠账减少一处 L4 正式写入边界；后续仍需扫描其他遗留页面。

## 完成内容

- `cloud_video_service.publish_session_config()` 统一发布已校验的会话配置和对应项目工作区偏好。
- `cloud_video_service.publish_workspace_preference()` 接管删除模型后的工作区偏好保存；`cloud_video.py` 仅保留 UI 校验、选择与状态提示。
- 新增云视频设置服务行为回归及 UI→服务静态边界，并把新架构测试纳入 `AGENTS.md` 第 5 节自检表。

## 验证

- `tests.test_cloud_video` 与 `tests.architecture.test_cloud_video_settings_boundary`：9/9 通过。
- `smoke_test.py --architecture`：79/79 通过。
- `smoke_test.py`：8/8 通过。
- `unittest discover -f -q`：3,202/3,202 通过，耗时 539.3 秒。
