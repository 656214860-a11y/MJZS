# R508 修复轮：任务栏最小化后无法恢复主窗口

日期：2026-09-28

## 根因

`pet_ui.Pet.window_visible()` 仅使用 `winfo_viewable()` 判断主窗口状态。Windows/Tk 对最小化（`iconic`）根窗口仍可能报告为可 viewable，导致从助手交互恢复主窗时跳过 `show_main()`，窗口持续停留在任务栏。

## 修复

- 可见性判断同时读取 Tk `state()`；`iconic` 与 `withdrawn` 均视为不可见。
- 恢复主窗时，若处于 `iconic`，先设为 `normal`，再 `deiconify()`、`lift()` 与 `focus_force()`。
- 新增两条回归：最小化状态不得被误判可见；恢复调用必须先恢复 normal，再显示、置顶和聚焦。

## 验证

- `python -m unittest tests.test_pet_ui.MainWindowRestoreTests -q`：2/2 通过。
- `python -m py_compile pet_ui.py`：通过。
- `python smoke_test.py`：8/8 通过。

## 后续

- R182 P3 结构治理仍待继续；本轮只处理用户报告的窗口恢复故障。
