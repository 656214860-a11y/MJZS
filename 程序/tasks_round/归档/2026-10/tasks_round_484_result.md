# R484 结构治理：云视频工作室设置发布服务化

## 轮次结论

- 本轮是结构治理轮：云视频工作室设置 UI 不再直接写根目录会话配置。
- 三个基线均通过：定向 11/11、架构 80/80、默认冒烟 8/8、全量 3,204/3,204。
- `project_status.md` 欠账减少一处 L4 正式写入边界；后续仍需扫描其他遗留页面。

## 完成内容

- `cloud_video_service.publish_studio_config()` 统一发布已由 UI 完成预算、联网与凭据路径预检的工作室会话配置。
- `app.py` 仅保留设置输入、预检、内存配置更新和界面刷新。
- 扩展既有云视频服务行为回归与静态边界，覆盖工作室设置保存委托。

## 验证

- `tests.test_cloud_video` 与 `tests.architecture.test_cloud_video_settings_boundary`：11/11 通过。
- `smoke_test.py --architecture`：80/80 通过。
- `smoke_test.py`：8/8 通过。
- `unittest discover -f -q`：3,204/3,204 通过，耗时 540.3 秒。
