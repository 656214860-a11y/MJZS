# Round 200 结果：快捷方式平台降级

## 轮次类型

功能轮（优化清单 P2「平台适配」的快捷方式子范围）。

## 完成内容

- 非 Windows 平台的快捷方式功能不再探测或启动 PowerShell，直接按“不可用”返回。
- 保留 Windows 的 PowerShell 创建流程及现有失败降级语义。

## 改动文件

- `app_shortcut.py`
- `tests/test_app_shortcut.py`
- `project_status.md`
- `tasks_round/tasks_round_200_result.md`

## 验证结果

- `py_compile app_shortcut.py`：通过。
- 快捷方式回归（含模拟 POSIX）：37/37 通过。
- 默认 `smoke_test.py`：8/8 通过。

## 审查结论

通过。非 Windows 不再产生无效 PowerShell 探测。
