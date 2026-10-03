# R917 UI 统一入口：通知分发全量审计

- 通知边界测试从根目录扩展为递归扫描所有生产 Python 模块。
- 统一组件 `ui_widgets.py` 是唯一允许直接调用 `messagebox.show*` 的实现位置；业务模块必须通过 `notify` 或 `NotificationDispatcher`。

验证：

- `python -m unittest tests.architecture.test_notification_boundary`：5 条通过。
- `python smoke_test.py`：8 项通过、0 失败。

路线图的忙碌态、菜单、输入和文本覆盖率仍待逐项完成。
