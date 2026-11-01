# R460 修复轮结果

## 任务

按最新截图将主界面设置齿轮左移，水平贴近应用名称，且不遮挡下方文字。

## 改动

- `desktop.py`：根层设置齿轮坐标从 `(154, 8)` 调整为 `(138, 8)`；保留 `y=8`。
- `tests/test_pet_settings.py`：真实 Desktop 接缝断言更新为 `(138, 8)`，继续覆盖根层挂载与设置入口。

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_pet_settings.DesktopGearSeamTests`：2/2 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8/8 通过。

## 边界

仅调整齿轮水平位置与对应断言；未修改用户项目数据、阶段流程或设置窗口行为。
