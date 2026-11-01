# R485 结构治理：桌面视频工作区发布服务化与自检表补漏

## 轮次结论

- 桌面视频工作区选择不再由 `desktop.py` 直接写项目设置，统一委托既有云视频服务发布。
- `AGENTS.md` 的架构自检表已补入遗漏的本地视频设置与资产详情绑定边界测试。
- 三个基线均通过：定向 12/12、架构 81/81、默认冒烟 8/8、全量 3,205/3,205。

## 完成内容

- `desktop.set_video_workspace()` 在既有项目边界校验后，改调用 `cloud_video_service.publish_workspace_preference()`。
- 扩展云视频设置边界回归：桌面工作区选择必须委托服务，禁止直接调用 `save()`。
- 在 `AGENTS.md` 的写入与删除边界自检表中加入 `test_local_video_settings_boundary.py` 与 `test_asset_detail_binding_boundary.py`。

## 验证

- `tests.test_cloud_video` 与 `tests.architecture.test_cloud_video_settings_boundary`：12/12 通过。
- `smoke_test.py --architecture`：81/81 通过。
- `smoke_test.py`：8/8 通过。
- `unittest discover -f -q`：3,205/3,205 通过，耗时 535.4 秒。
