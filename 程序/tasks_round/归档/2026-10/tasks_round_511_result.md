# R511 修复轮：任务栏最小化后无法恢复或关闭

## 根因与修复

- `Pet.show_main()` 原先只在 `iconic` 状态先设置 `normal`，且一次聚焦失败会让恢复流程整体失败；Windows/Tk 的任务栏恢复需要先映射，再显式恢复状态并刷新布局。
- 现按 `deiconify → state('normal') → update_idletasks → lift → 临时置顶 → focus_force` 执行；聚焦失败单独记录，不撤销已完成的窗口恢复。
- `Desktop.close()` 在后台任务仍运行时显示强制关闭确认前，先走同一恢复入口；确认框不会再跟随最小化主窗口隐藏。

## 范围

- 修改：`pet_ui.py`、`desktop.py`、`tests/test_pet_ui.py`、`tests/test_desktop_close.py`。
- 未修改用户项目数据、任务成果、模型配置或密钥。

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest tests.test_pet_ui.MainWindowRestoreTests tests.test_desktop_close -q`：4/4 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe -m py_compile pet_ui.py desktop.py`：通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：默认冒烟 8/8 通过。

## 使用说明

- 本轮涉及 Tk 界面代码，必须重启应用后生效。
- 若旧实例已卡住且确认框不可见，可从任务管理器结束该旧实例；重启后的版本会在关闭确认前自动恢复主窗口。
