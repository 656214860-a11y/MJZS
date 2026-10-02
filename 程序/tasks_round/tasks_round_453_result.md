# R453 结构治理轮结果：首帧恢复生命周期服务

## 范围

- 收敛首帧“恢复”动作的文件移动与 `episode.json` 状态发布。
- 保持首帧页面的确认框、重建页面与状态提示在 UI 层。

## 改动

- `keyframe_lifecycle_service.py`：新增 `restore_keyframe()`；使用 `storage_maintenance.restore_latest_recycled_child()` 优先恢复项目回收站记录，兼容旧 `frames/历史版本` 的只读恢复，只有恢复成功后才更新并原子保存状态；状态保存失败时回收刚恢复的文件并复原内存状态。
- `desktop.py`：恢复按钮只负责确认与委托服务，不再直接复制文件或保存分镜 JSON。
- `tests/test_keyframe_lifecycle_service.py`：补恢复成功与保存失败回收的行为回归。
- `tests/architecture/test_keyframe_restore_boundary.py`：禁止 `Desktop.restore_keyframe()` 重回直接文件/JSON 持久化。
- `AGENTS.md`、`architecture.md`：登记第 37 份架构门禁、61/61 基线与恢复服务职责。

## 验证

- `python -m unittest tests.test_keyframe_lifecycle_service tests.architecture.test_keyframe_delete_boundary tests.architecture.test_keyframe_restore_boundary`：6/6 通过。
- `python smoke_test.py --architecture`：61/61 通过。
- `python smoke_test.py`：8/8 通过。
- `python run_selftests.py --all --safe`：3,143/3,143 通过，799.5 秒，0 个文件有红（R451 启动，R453 后完成记录）。

## 约束核对

- 新恢复路径使用阶段生命周期服务与项目回收服务；旧目录不写入、不搬迁，只做读取兼容。
- 未触及白模视频上传真机验收；该项仍等待用户授权。
- 主界面“齿轮 → 设置”入口未改动。
