# R454 修复轮：顶层设置入口与首帧替换

## 范围

- 修复主界面齿轮图案被侧栏裁掉的问题，保持“齿轮 → 设置”入口。
- 收敛首帧“导入/替换”的图片和 JSON 持久化。

## 改动

- `desktop.py`：声明主窗口根层作为齿轮专用层；首帧页面仅读取用户选择的 PNG 并委托替换服务。
- `pet_ui.py`：真实 `Desktop` 的齿轮直接用 `place(x=8, y=8)` 创建在根窗口，脱离侧栏/标题行/页面画布的裁剪；轻量测试宿主仍回退至标题行嵌入。
- `tests/test_pet_settings.py`：真接缝断言齿轮父容器为主窗口、位置为 `(8, 8)`，并保留点击打开设置验证。
- `keyframe_lifecycle_service.py`：新增 `replace_keyframe()`；验证 PNG 与镜头路径，旧首帧先安全回收，再原子发布新图和 JSON；若 JSON 保存失败，恢复旧状态和旧图。
- `tests/test_keyframe_lifecycle_service.py`、`tests/architecture/test_keyframe_replace_boundary.py`：补成功/失败回滚和页面不得直接持久化的回归门禁。
- `AGENTS.md`、`architecture.md`：架构门禁更新为 38 个测试文件、62 项检查，登记首帧导入替换职责。

## 验证

- `python -m unittest tests.test_pet_settings tests.test_keyframe_lifecycle_service tests.architecture.test_keyframe_replace_boundary`：59/59 通过。
- `python smoke_test.py --architecture`：62/62 通过。
- `python smoke_test.py`：8/8 通过。
- 既有全量安全基线：`python run_selftests.py --all --safe` 为 3,143/3,143 通过（799.5 秒）。

## 约束核对

- 设置回调仍为 `pet.open_settings()`，没有删除、隐藏或替换设置入口；重启应用后生效。
- 新替换路径使用项目回收服务；旧 `历史版本` 仅由恢复服务读取兼容，不向其新写入。
- 白模视频上传真机验收仍等待用户提供素材与授权，未执行。
