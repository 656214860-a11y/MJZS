# R772 修复轮结果：Toplevel Map grab 输入锁

## 根因与修复

根因已由 R1 复现确认：`ui_theme.install_window_placement()` 把同一个 `<Map>` 回调绑定到 Toplevel；Tk 会把子控件的 Map 事件送达该绑定，原回调把 `event.widget`（可能是 Label／Frame／Button）执行 `grab_set()`，使全局输入被子控件或透明窗口占有。

- `grab_popup()` 现仅在 `event.widget is window` 时抓取；`<Unmap>` 同样只处理窗口自身，并释放隐藏复用窗口的 grab。
- `ready()` 的定位异常现强制恢复 `-alpha=1`、释放 grab，并通过 Desktop 既有状态栏入口显示可行动错误。
- `BaseDialog` 记录自己已取得过 modal grab；关闭时释放当前 grab 持有者及自身，不再依赖 `grab_current() == self`，重复关闭仍幂等。

## 回归与验证

- R1 子控件 Map 不抢 grab：通过。
- R2 withdraw 的隐形窗口不持 grab：通过。
- R3 定位异常恢复可见／释放 grab／状态栏通知：通过。
- R4 后来窗口持有 grab 时关闭 BaseDialog 不留输入锁：通过。
- R5 真实 Desktop 首日选择项目期间采样 grab，不会落到子控件：通过。
- `python smoke_test.py`：8/8。
- `python smoke_test.py --affected ui_theme desktop ui_widgets pet_cloud`：9/9。
- `python run_selftests.py -k ui_theme dialogs startup desktop_close pet_ui --safe`：593 条／0 红。
- `python smoke_test.py --architecture`：140/140。
- `python run_selftests.py --all --safe`：3,518 条中 1 个既有工作区红项：`tests/test_static_names.py` 发现 R771 未提交改动的 `app.py` 在 `import_json` 使用了未定义的 `project_registry_gateway`。这不是本轮 Tk 改动，且用户限定本轮不得改该业务模块，故未越权修补，也未推进 `last_full_safe_all_round`。

## 验收状态

P0 的代码与 R1–R5 已通过自动验证；完整安全全量受上述既有 R771 静态错误阻断，且仍须用户真机重启确认“主页面可点击、选择项目窗按钮一次生效、× 一次可关”后才可标记最终验收。

## Git

本轮未提交、未推送。建议提交信息：`fix: 防止 Toplevel Map 事件遗留输入 grab`。
