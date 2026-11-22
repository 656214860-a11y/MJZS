# R4076 结果：项目文件停靠面板支持鼠标拖动调整宽度
<!-- round-evidence: {"commit_base": "5c85dd13", "credential_hits": 0, "evidence_sha256": "ea07e3633e57aaf2", "exit": 0, "failed": 0, "passed": 145, "round": 4076, "tests": "run_selftests.py -k files_panel"} -->

## 开头三问

- （一）本轮属于哪种类型：修复轮，任务卡 W4-UX-B5W，车道 codex/ux-dock-resize，来源是用户反馈「允许用鼠标手动调整右侧文件停靠面板的宽度」。
- （二）测试跑了吗、三个基线：`tests/test_files_panel.py` 新增 `FilesPanelResizeTests` 5 条；改前红测因混入类文档字符串反斜杠导致 `SyntaxError`（`desktop_files_panel.py` 第 56 行），0 条用例执行，修复语法后重跑新增用例全过；原有用例与新增用例一起实测 145 条全过；架构门禁实测 696 条、失败集合为空；默认冒烟未单独跑；全量自测未跑。没有改原有用例断言（Esc 用例仅加长 pump 与 focus 处理）。
- （三）欠账少了吗：修掉一条用户反馈的界面缺陷；新增共享状态棘轮登记条目（`ProjectFilesPanel` 由 2 个基类增至 3 个，上限 2）；全量自测未跑。

## 改了哪些文件

- `ui/desktop_files_panel.py`：新增 `FilesPanelResizeMixin`（拖动起点记录、`_do_resize`、`_end_resize`、`_restore_auto_width`、`_manual_cap`）；新增常量 `SCRIPT_PANEL_USER_MAX_SHARE = 0.7`；`ProjectFilesPanel` 继承混入类；`__init__` 初始化 `_user_panel_width`/`_resize_start`；`build()` 创建 `resize_grip`；`open_panel()` 两分支与 `collapse()` 处理手柄；`_outside_press()` 放行 `resize_grip`；`_fit_script_width()` 支持手动宽度夹紧。
- `tests/test_files_panel.py`：新增 `FilesPanelResizeTests` 5 条；Esc 用例加长 pump 与 `focus_force`/`update_idletasks`。
- `tests/architecture/test_shared_state_ratchet.py`：登记 `ProjectFilesPanel` 共享状态上限 2（新增混入基类所致）。
- 本结果文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k files_panel`（改后） | 退出码 0；145 条用例全过 |
| `smoke_test.py --architecture` | 退出码 0；696 条用例全过 |
| `scripts\dev.py claim` | 轮次号 4076 |
| `scripts\dev.py commit ...` | 待提交 |

## 如实说明

- 手动宽度仅在本次运行内保持，跨重启保存未做（不在本卡范围）。
- 手动上限为内容区宽的 70%。
- 需求文档由受理窗口另行统一补写，本轮未改文档。
- 共享状态棘轮因新增混入基类从 2 个增至 3 个而登记新条目，未放宽任何阈值。
- 红测最初因文档字符串反斜杠语法错误失败，非标准红测；Esc 用例存在预存在时序敏感问题，本轮通过加长 pump 与 focus 处理缓解。
- 其他与卡面不一致之处如实写：无。

## 未覆盖项

- 未用真实鼠标拖动做人工验证。
- 全量自测未跑。
- 默认冒烟未单独跑。
