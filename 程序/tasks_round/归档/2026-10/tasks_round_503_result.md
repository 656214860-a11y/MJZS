# R503 兼容/平台适配轮：后台进程终止边界

## 结论

- 已修复后台制作引擎与剧本 Agent 中直接依赖 Windows `taskkill` 的跨平台终止缺口。
- Windows 继续按进程树强制停止；其他宿主改用标准 `process.terminate()`，不再尝试不存在的 Windows 命令。
- 未修改用户项目数据、制作流程或可见本地应用启动行为。

## 改动

- `platform_tools.terminate_process_tree()` 成为已登记后台进程的唯一终止适配入口：Windows 调用 `taskkill /F /T`，其他平台调用进程对象的 `terminate()`。
- `workflow_engines.terminate()` 与 `Desktop.interrupt_script_agent()` 改为委托该入口；前者仍保留等待及兜底 `kill()` 收束语义。
- 新增平台适配单测，并以架构测试限制直接 `taskkill` 只能留在平台或本地应用适配模块。

## 验证

- 定向：`tests.test_platform_tools`、`tests.test_previs`、`tests.architecture.test_platform_process_boundary`，64/64 通过（3.180 秒）。
- 默认冒烟：`python smoke_test.py`，8/8 通过。

## 自审

- 变更只覆盖 L1 平台适配和其调用入口；Windows 的后台子进程结束方式未变，非 Windows 现在有可用的降级路径。
