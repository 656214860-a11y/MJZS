# R459 修复轮结果

## 任务

按截图将主界面设置齿轮右移至箭头位置，且不得遮挡下方文字。

## 改动

- `desktop.py`：根层设置齿轮坐标由 `(112, 8)` 调整为 `(154, 8)`；保持 `y=8`，使其位于下方文案上方。
- `tests/test_pet_settings.py`：真实 Desktop 接缝断言同步为 `(154, 8)`，继续验证齿轮挂在主窗口根层且设置入口可达。

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_pet_settings.DesktopGearSeamTests`：2/2 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8/8 通过。

## 边界

仅调整主界面齿轮位置和对应回归断言；未修改用户项目数据、阶段流程或设置窗口行为。
