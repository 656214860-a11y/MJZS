# R4079 结果：项目文件停靠面板拖动调宽复核返工
<!-- round-evidence: {"commit_base": "fce27e44", "credential_hits": 0, "evidence_sha256": "c33a385a0d25a29a", "exit": 0, "failed": 0, "passed": 145, "round": 4079, "tests": "run_selftests.py -k files_panel"} -->

## 开头三问

（一）本轮属于哪种类型：修复轮，任务卡 V-UX-B5W-FIX，车道 codex/ux-dock-resize，来源是验收窗口对 R4076 的复核意见。

（二）测试跑了吗、三个基线：`run_selftests.py -k files_panel` 实测 145 条用例全过（0 个文件有红）；`smoke_test.py --architecture` 实测 696 条、失败集合为空；默认冒烟没单独跑；全量自测没跑。没有新增或删除用例，只删了一句没用到的导入。

（三）欠账少了吗：共享状态登记值从 2 降到 0（实测 0）；去掉一处原卡没有要求的键盘焦点改动（打开面板不再抢输入框焦点）；拖动手柄改 ttk 后跟随主题。无新增欠账。

## 改了哪些文件

- `ui/desktop_files_panel.py`：`_bind_outside()` 删掉末尾 `win.focus_set()` 四行；`FilesPanelResizeMixin` 加类属性 `_user_panel_width = None`／`_resize_start = None`，`ProjectFilesPanel.__init__` 删掉对应两行赋值；`resize_grip` 由 `tk.Frame` 改 `ttk.Frame`；`_fit_script_width()` 恢复 R3060 两行注释与实宽缺口补偿四行注释；去掉文件末尾空行。
- `tests/architecture/test_shared_state_ratchet.py`：`'ProjectFilesPanel'` 登记值 2→0，注释同步。
- `tests/test_files_panel.py`：`test_drag_left_widens_panel` 删掉没用到的 `SCRIPT_LIST_MIN_WIDTH` 导入。
- 本结果文件。

## 命令与结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `git -c core.quotepath=false status --porcelain` | 0 | 无输出（工作树干净） |
| `git log -1 --format=%h` | 0 | fce27e44 |
| `git -c core.quotepath=false diff --stat` | 0 | 正好三个文件 |
| `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k files_panel` | 0 | ALL TESTS PASSED，共 145 条用例 |
| `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture` | 0 | Ran 696 tests，OK |
| `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim` | 0 | 领到 4079 |

## 如实说明

拖动手柄从 `tk.Frame` 换成 `ttk.Frame` 后没有做人工界面验证。项目命令按卡面原文发出；首次在 bash 下因反斜杠被当转义找不到解释器，改在 PowerShell 下原样执行成功，命令文本未变。

## 未覆盖项

没有用真实鼠标拖动做人工验证；全量自测没跑；默认冒烟没单独跑。
