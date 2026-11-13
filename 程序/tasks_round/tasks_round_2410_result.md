# R2410 结果：修复弹窗居中偏移（外框/客户区坐标口径混用）

## 三个必答（§7）

- **轮次类型**：修复轮（§3.2）——修「几乎所有弹窗相对主窗口居中但偏移几十像素」的视觉缺陷。
- **测试跑了吗、三个基线过了吗**：
  - 默认冒烟 `smoke_test.py`：**8/8 通过**。
  - 定向 `run_selftests.py -k "test_ui_theme test_popup_no_interrupt test_timers"`：**34 条 0 红**。
  - 实测诊断（隐藏桌面）：修复前偏移 dx=8px、dy=31px；修复后 **dx=0.0、dy=0.0**。
  - 全量：未跑（不命中 §5 强制全量条件）。
- **project_status.md 的欠账少了吗**：无新增欠账；本轮修复既有居中精度 bug。

## 根因

`ui_theme.install_window_placement` 的全局居中 `place()` 里，居中公式混用了 Tk 的两种坐标口径：

```python
x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2   # 错：rootx 是外框，width 是客户区
y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
```

- `winfo_rootx()/rooty()` 返回窗口**外框**（含左边框 + 标题栏）的屏幕坐标。
- `winfo_width()/height()` 返回**客户区**（不含边框、标题栏）尺寸。

两者混用，导致弹窗相对主窗口视觉中心偏移了「左边框宽 + 标题栏高」的量。实测（隐藏桌面）：主窗口 `geometry('+100+100')` 时 `winfo_x()=100`（客户区）而 `winfo_rootx()=108`（外框），差 8px；`winfo_rooty()=131` 差 31px（标题栏）。高 DPI 缩放下这个偏移放大到几十像素，与用户观察一致。

## 最小修复

`ui_theme.py` `place()` 居中公式改用 `winfo_x()/winfo_y()`（客户区屏幕坐标，与 `winfo_width()/height()` 同口径）：

```python
x = parent.winfo_x() + (parent.winfo_width() - width) // 2
y = parent.winfo_y() + (parent.winfo_height() - height) // 2
```

`parent=None`（相对工作区居中）分支不动——它用 `_work_area` 的一致口径，本就正确。

## 验证证据（隐藏桌面实测）

- 修复前：弹窗客户区中心偏移 **dx=8.0 dy=31.0**（左边框 8px + 标题栏 31px）。
- 修复后：弹窗客户区中心偏移 **dx=0.0 dy=0.0**（精确居中）。

## 改动文件

- `ui_theme.py`：`place()` 居中公式 2 处（x/y）由 `winfo_rootx/rooty` 改为 `winfo_x/winfo_y`。

## 提交

- 已提交：是。commit hash 见 git log。
- 提交信息：`R2410: 修复弹窗居中偏移（外框/客户区坐标口径混用）`。
