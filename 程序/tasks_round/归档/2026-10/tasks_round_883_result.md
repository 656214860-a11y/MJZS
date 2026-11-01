# R883 UI 统一入口覆盖：弹窗审计收口

## 结论

- 根目录业务生产模块已没有直接 `tk.Toplevel(...)` 调用；业务弹窗统一经 `BaseDialog`、`FormDialog` 或 `ConfirmDialog`。
- 弹窗边界测试不再维持旧页面的历史数量上限，改为扫描全部根目录生产模块的零容忍门禁；`ui_widgets.py`、`ui_theme.py` 和测试运行器是各自的实现／运行时边界。
- 路线图尚未完成：DataTable 的语义导航例外、输入／下拉／文字覆盖、忙碌态、确认对话框及其余项目仍须逐项审计。

## 验证

- `python -m unittest tests.architecture.test_dialog_boundary -v`：5 条／0 红。
- `python run_selftests.py --all --safe` 已实际启动；非 Tk 池完成后，Tk 串行池的 `test_asset_gating` 报 1 条失败，整轮退出码 1，未作为绿色全量凭据。
- 在测试目录按正式导入路径隔离复跑 `test_asset_gating`：18 条／0 红；Tk 销毁阶段仍会打印既有 `invalid command name ...run` 清理噪声，未影响该定向用例结果。

## 提交

- 本轮门禁与轮次记录已提交；提交标识见版本历史。
