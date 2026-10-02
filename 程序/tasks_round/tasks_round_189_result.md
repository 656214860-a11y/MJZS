# Round 189 结果：后台命令平台适配收口

## 轮次类型

功能轮（优化清单 P2「平台适配」的后台进程子范围）。

## 完成内容

- 新增 `platform_tools.hidden_console_flags()`，集中处理 Windows 后台命令的隐藏控制台标志；
  非 Windows 或精简运行时稳定返回零。
- 本地媒体应用、图片转码、白模探测、引擎探测、工作流引擎和桌面中断入口不再嵌入
  `0x08000000` 魔法常量。
- 用户明确需要可见窗口的 Blender/交互式 Agent 启动保持原样。

## 改动文件

- `platform_tools.py`
- `native_apps.py`
- `native_asset_codec.py`
- `previs_automation.py`
- `engine_probe.py`
- `workflow_engines.py`
- `desktop.py`
- `tests/test_platform_tools.py`
- `project_status.md`
- `tasks_round/tasks_round_189_result.md`

## 验证

- 项目内置 Python：受影响模块 `-m py_compile` 通过。
- `-m unittest tests.test_platform_tools tests.test_engine_probe tests.test_previs tests.test_workflow`：145/145 通过。
- `smoke_test.py`：8/8 通过。

## 审查

通过：后台命令的主机差异只留在平台适配器；没有改变进程参数、执行时序或用户可见窗口行为。
