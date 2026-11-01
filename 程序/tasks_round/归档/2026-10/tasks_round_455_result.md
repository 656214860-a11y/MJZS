# R455 修复轮结果

## 目标

修复主界面根层“齿轮 → 设置”入口遮挡侧栏文字的问题。

## 改动

- `desktop.py`：侧栏宽度由 154px 调整为 184px，并声明根层齿轮安全位 `(154, 8)`；该位置位于侧栏末端、正文起点之前。
- `pet_ui.py`：根层齿轮读取 `Desktop.settings_gear_position` 后定位；无真实 Desktop 的轻量宿主仍沿用标题行布局。
- `tests/test_pet_settings.py`：真实 Desktop 接缝测试锁定根层父容器与安全位坐标，防止回归为遮挡标题的 `(8, 8)`。

## 验证

- `python -m unittest tests.test_pet_settings`：52/52 通过。
- `python smoke_test.py`：8/8 通过。

## 边界

- 未改设置打开路径、业务服务、白模视频上传或项目数据。
- 应用已在运行时需要重启，才能加载新布局。
