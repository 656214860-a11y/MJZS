# R452 修复轮结果：主界面设置齿轮可见性

## 范围

- 修复主界面“齿轮 → 设置”入口在窄侧栏中的可见性。
- 未改设置窗口、入口回调、项目数据或其他页面。

## 改动

- `pet_ui.py`：`GearButton` 从标题行左侧末尾改为固定排在右侧，避免 154px 侧栏中被“应用名＋版本号”横向裁掉。
- `tests/test_pet_settings.py`：真 `Desktop` 接缝测试断言齿轮位于标题行右侧，防止布局退回会裁掉入口的顺序。

## 验证

- `python -m unittest tests.test_pet_settings`：52/52 通过。
- `python smoke_test.py --architecture`：60/60 通过。
- `python smoke_test.py`：8/8 通过。

## 约束核对

- 设置仍经既有 `pet.open_settings()` 打开；未删除、隐藏或替换主界面“齿轮 → 设置”路径。
- R451 的全量安全自检在独立进程中继续执行，结果另补记其原报告与状态项。
