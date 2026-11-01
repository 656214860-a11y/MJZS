# R1623 运行期诊断统一到 app_logging，并冻结 print 棘轮（Q9 后半）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round/tasks_round_1610_result.md) J 第三批 Q9 后半）。至此 Q9 两半（拆 5 个大文件、统一运行期诊断）均落地。
- 测试：架构门禁 `smoke_test.py --architecture` **356 项 OK**（179.7 秒，比上轮 +2＝新门禁两个用例）；默认冒烟 8/8；定向 `test_core`／`test_force_quit`／`test_asset_gating`／`test_auto_import`／`test_aspect_ratio_priority`／`test_asset_batch_retention` 共 173 项 OK；新门禁专项 27 项 OK。
- 欠账：本轮改源码，`project_status.md` 全量欠账计数 +1；R1619–R1622 的欠账仍未清。

## 先更正 R1610 的错误前提

R1610 写「生产根目录 `print(` **606 处**」。复核后该数不成立：它是 `程序/` 目录**递归原始文本** grep 的结果，把 `tests/`、CLI 自检脚本、子进程输出协议、以及**文档字符串／注释里的字面量**一并算了进去。

按架构门禁自己的口径（`tests/architecture/_scan.production_files()`，即「运行期生产模块」）用 AST 统计真实 `print(...)` **调用**：**共 36 处、分布在 14 个文件**，其中 24 处本就是「自己就是控制台程序」或「stdout 是 IPC 协议」的入口，真正属于**运行期诊断**的只有 3 处。本轮据此把工作范围收敛到真实缺口，并把「以后不许再长回来」写成门禁。

## 做了什么

**1）3 处运行期诊断改走 `logging`（进 `logs/app.log`，由 `app_logging` 装好处理器并脱敏）**

| 位置 | 原 | 现 |
| --- | --- | --- |
| `desktop.py` `force_quit` | `print('强制关闭：白模批次未收干净（'+str(exc)+'）')` | `LOGGER.warning('强制关闭：白模批次未收干净（%s）', exc)` |
| `desktop.py` `stop_automation_processes` | `print('关闭：引擎进程未收干净（'+str(exc)+'）')` | `LOGGER.warning('关闭：引擎进程未收干净（%s）', exc)` |
| `native_assets.py` 制图前置异常 | `print('制图未开始：', repr(exc))` | 新增 `LOGGER = logging.getLogger(__name__)`，改 `LOGGER.warning('制图未开始：%r', exc)` |

`desktop.py` 早就有 `LOGGER`（第 48 行）与同类 `LOGGER.warning` 先例；`native_assets.py` 原先只 `import app_logging`，本轮补 `import logging` 与模块 `LOGGER`——异常原文从此写进 `app.log` 而不是写进 pythonw 下必然为 `None` 的 `sys.stdout`（`print` 在那里是静默空操作，这正是原诊断丢失的原因）。

**2）新增门禁 `tests/architecture/test_print_ratchet.py`**

- `test_no_print_outside_registered_console_entries`：生产模块（架构口径）里只有**登记的控制台入口**允许出现 `print`，其余一律失败，并逐处报 `文件:行号`。
- `test_registered_entries_only_shrink`：登记值只许下降；某文件降到 0 处时必须从登记表删除。

登记的控制台入口及理由：

| 文件 | 允许 | 理由 |
| --- | --- | --- |
| `engine_probe.py` | 9 | 命令行探针：USAGE、参数错误、真机验证报告 |
| `shot_numbering.py` | 4 | 命令行工具：用法／自检／复查结论 |
| `workspace_maintenance.py` | 4 | 命令行维护报告 |
| `log_maintenance.py` | 1 | 命令行轮转报告 |
| `exit_maintenance.py` | 1 | 命令行退出派发摘要 |
| `app_icon.py` | 2 | 命令行图标生成输出 |
| `app_shortcut.py` | 3 | 命令行快捷方式输出 |
| `asset_thumbs.py` | 1 | `--worker` 用法提示行 |
| `image_agent_runner.py` | 4 | **子进程协议**：stdout 是与父进程的 IPC 通道，不是诊断 |
| `console_submit.py` | 1 | 控制台提交工具，输出即结果 JSON |
| `broadcaster.py` | 1 | **双通道**：既 print 给调用端，又写 `sanhu_progress.log` |

**3）随本轮同步的入口**

- `AGENTS.md` §5「当前架构门禁清单」新增 `test_print_ratchet.py`（`test_agents_md` 要求清单与实际测试文件集合**完全相等**）。
- `architecture.md` §3 新增 `R1623` 说明：运行期诊断统一走 `logging`，仅登记的控制台入口保留 `print`。

## 本轮顺带发现并修掉的既有缺陷（R1622 引入）

R1622 用生成脚本改写 `desktop.py` 时按 LF 落盘，而 `.gitattributes` 把 `程序/desktop.py` 钉为 `eol=crlf`（与 `pet_ui.py`／`skill_panel.py` 同属历史行尾门禁的固定文件）。R1622 只跑了架构门禁与相关用例，没跑 `tests/test_line_endings.py`，所以没暴露。本轮回归时 `test_line_endings` 报「desktop.py 的换行符被换了」，已改回 CRLF，`test_line_endings` **16/16 OK**。教训：改写被 `.gitattributes` 钉行尾的文件必须按该行尾写盘，且结构治理轮收尾要顺带跑一次行尾门禁。

## 诚实边界

- 本轮只处理**运行期生产模块**；CLI 工具与子进程协议的 `print` 是**有意保留**的（它们就是 console 程序／IPC 通道），不是疏漏。
- 门禁冻结的是**调用点数量**，不判断某处 `print` 的语义是否恰当；新写的诊断若绕过 `logging` 直接 `print` 会被挡住，但写成 `LOGGER.info` 是否合适仍需人看。
- 未实机在 pythonw 下验证 `app.log` 内容（本环境 GUI 会话超时，见 R1619／R1620 说明）；`app_logging.install()` 的处理器安装是既有机制，本轮未改动它。
- 全量安全全量最后一次真实通过仍是 **R1605/e59e513**；R1606–R1623 未跑全量，最终定性以 post-commit 后台 `.git/auto-full-safe-result.json` 为准。