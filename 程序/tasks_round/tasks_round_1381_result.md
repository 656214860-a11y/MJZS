# R1381：UI 统一入口覆盖轮 — 弹窗覆盖审计校正（门禁递归化与谓词加固）

类型：修复轮（§3.2）——修复「弹窗门禁只扫根目录，与 R922『递归架构门禁』口径不一致」的门禁缺陷；最小修复，不改生产代码、不改 UI 行为。中央轮次 1381（`.git/round-counter.json` 的 `last_claimed=1381`）。范围＝`维护记录/UI统一入口路线图_v1.md` §二 第一批 第 1 项「`Toplevel` 弹窗」（完成判据原文「旧弹窗按类型迁移，关闭、模态、居中与错误呈现由统一基类承担。」）。

## 三个必答
- 本轮类型：修复轮（§3.2）。根因＝`tests/architecture/test_dialog_boundary.py` 的全局扫描用 `ROOT.glob('*.py')`（只覆盖根目录），而 `project_status.md` 记 R922 为「递归架构门禁确认业务模块不直接创建 `tk.Toplevel`」；两者口径不一致，`batch_frames_tool/`、`agent/`、`scripts/` 等子目录不被门禁覆盖。
- 测试：`tests/architecture/test_dialog_boundary` **6/6**（新增 1 条 canary，原 5）；定向 `run_selftests.py -k "dialog prompt_window qwen tts_settings cloud_assets"` **24 条 / 0 文件红**；默认冒烟 `smoke_test.py` **8/8**；架构 `smoke_test.py --architecture` **326/326**（原 325，+1）；0 红。
- 欠账：1381 − 1380 = 1 **< 5**，且未命中 §5 升级条件（无启动路径／Tk 控件生命周期／删除语义／层级登记表改动），本轮不跑全量、无新增欠账。R1380 全量 4967/4967 为历史凭据（tree f62cd088＝`e25c70d:程序`，与当前树不同，不复用）。

## 根因与最小修复
- 根因：弹窗历史门禁自 R883 起为「扫描全部**根目录**生产模块」的零容忍规则；R922 的审计结论写成「递归」，但门禁实现从未递归，子目录模块可绕过。
- 最小修复：`test_dialogs_use_the_unified_boundary` 的扫描改为 `ROOT.rglob('*.py')`，排除 `{tests, tasks_round, 维护记录, .git, __pycache__}`（与 `test_data_table_boundary` 同一口径），保留 `TOPLEVEL_OWNERS = {ui_widgets.py, ui_theme.py, run_selftests.py}`。
- 同类复核（谓词加固）：原谓词只认 `ast.Attribute` 的 `tk.Toplevel(...)`；`from tkinter import Toplevel` 后的名字式 `Toplevel(...)` 会漏检（与按钮门禁已覆盖别名/导入的强度不一致）。扩为「属性式 ∪ 名字式」，并补 `test_raw_toplevel_canary_is_detected` 镜像两条构造。

## 审计结论（R1381 复核）
- 全生产模块（含子目录）**裸构造 `Toplevel` = 0**，仅 `ui_widgets.py` 统一基类自身 1 处（Tooltip 浮层内部）属例外。
- 其余 UI 覆盖门禁扫描广度核对：表格／输入／下拉／提示／右键菜单／文件选择／快捷键／Tooltip／图标／滚动条／文案与复制／忙碌态 均为**递归 `violations == []`**（表格固定为 `{'desktop.py': 3}`，项目树是唯一语义例外）；按钮＝固定页清单棘轮（未列页待迁移）；阶段显示＝只查 `desktop` 生成源；卡片／文字层级＝全站审计＋豁免／backlog。
- 因此此前「路线图其余 ~22 项均未收口」为**高估**，已在 `project_status.md` §已知阻塞与待办 更正；真正剩余是各棘轮门禁未列页的未迁移条目与尚无专用门禁的项（设计 token 内联视觉常量、§三 覆盖率审计）。

## 契约与回归
- 契约变化：`test_dialog_boundary` 全局门禁由「根目录零容忍」收紧为「全生产模块零容忍」，谓词新增名字式识别。无生产代码、无 UI 行为变化，无用户数据改动。
- 回归证据：见上「三个必答」；本轮不新增/删除架构门禁文件，§5 清单文件名不变（仅该文件内 +1 用例）。

## 产出与提交
- 改动文件：`tests/architecture/test_dialog_boundary.py`（门禁递归化＋谓词加固＋canary）、`project_status.md`（轮次头／已知阻塞与待办校正／验证基线）、本轮报告与接力记录。
- 提交：本轮内容、报告与状态页同一次收尾提交；commit hash 见文末补记。
