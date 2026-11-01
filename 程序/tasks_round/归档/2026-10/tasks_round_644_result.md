# R644 功能轮（执行 R630 候选 4.2）结果

## 验证档位声明（验证前）

本轮改动涉及 **3 个实现模块**（`log_maintenance.py`、`desktop.py`、`scripts/maintain_logs.py`）及其回归测试；虽然模块数未达四个，但明确触及**正常退出路径**与受限文件删除路径。按分级规则执行 **默认冒烟 + 全量安全自检**，跳过 `--affected` 与 `--architecture`，理由是启动/退出边界要求使用全量安全自检，且验证档位不叠加。

## 轮末三问

- 本轮是功能轮还是整理轮？**功能轮**：新增程序自有日志的有界维护能力。
- 测试跑了吗？三个基线过了吗？聚焦回归 15/15、默认冒烟 8/8 通过；已声明的全量安全自检为 3347 条、19 个文件有红，**未通过**。本轮未声明运行 `--affected` 或 `--architecture`。
- `project_status.md` 的欠账少了吗？**没有**。按任务硬判定，本轮为 `[TASK_FAILED]`，R630 候选 4.2 不得按验收完成关闭。

## 已实现范围

- 策略常量位于 `log_maintenance.py` 顶部：保留 30 天、单文件 10 MiB、三份 `.1/.2/.3` 轮转、每目录 150 MiB 上限。
- 维护严格只枚举程序 `logs/`、`维护记录/` 的直接子级 `.log` 与本策略生成的轮转副本；不递归扫描，不读取或触碰用户项目目录、`.jsonl` 或其他用户数据。
- 正常关闭窗口后，以无窗口子进程异步执行；强制退出不触发。失败不阻塞、不弹窗。
- 手动入口为 `scripts/maintain_logs.py`；可运行 `D:\漫剧制作助手\运行环境\Python\python.exe -B scripts\maintain_logs.py --dry-run`。

## 改动文件清单

- `log_maintenance.py`（新增）：受限目录的非递归枚举、保留期删除、尺寸轮转、目录上限和无窗口异步入口。
- `desktop.py`：正常窗口关闭后调度日志维护；强制退出不调度；异常静默，不影响退出。
- `scripts/maintain_logs.py`（新增）：开发者可手动执行的演练/维护入口。
- `tests/test_log_maintenance.py`（新增）：范围隔离、30 天保留、三份轮转、目录 mtime 淘汰、演练无写入回归。
- `tests/test_force_quit.py`：补充正常关闭调度与强制退出不调度的回归。
- `tasks_round/tasks_round_644_result.md`、`project_status.md`：本轮记录与台账状态；未修改产品配置或用户项目数据。

## 回归断言

- 仅枚举传入程序根的 `logs/` 直接子级；31 天前的 `.log` 删除，而同根模拟用户项目的 `project/logs/agent.jsonl` 保持不动。
- 超过单文件上限时，内容按 `.log → .1 → .2 → .3` 轮转；不会产生 `.4`。
- 超过目录上限时，按 `mtime` 从旧到新删除受管日志，非日志文件保持不动。
- `--dry-run` 只汇报，不改变文件。
- 正常 `finish_close()` 调度日志维护；`_forcing_quit` 时不调度。

## 验证（原始汇总）

聚焦回归：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_log_maintenance tests.test_force_quit
...............
Ran 15 tests in 0.331s
OK
```

手动入口演练：

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B scripts\maintain_logs.py --dry-run
D:\漫剧制作助手\程序\logs: 轮转 0 个，删除 0 个（0.00 MiB），错误 0 个
D:\漫剧制作助手\程序\维护记录: 轮转 0 个，删除 0 个（0.00 MiB），错误 0 个
```

默认冒烟：

```text
python -B smoke_test.py
通过：8 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮
```

全量安全自检（完整原始输出：`维护记录/r644_safe_all.log`）：

```text
python -B run_selftests.py --all --safe
共 3347 条用例，920.4 秒；19 个文件有红
```

因此，尽管本轮新增的聚焦回归和默认冒烟均通过，声明档位中的全量安全自检未通过；严格判定为 **[TASK_FAILED]**。失败单元包括 `architecture.test_platform_process_boundary`、`architecture.test_recycle_service`、`test_copy_rules`、`test_core`、`test_hollmwood_ui_queue`、`test_idea_chat`、`test_line_endings`、`test_model_pool`、`test_pet_ui`、`test_row_targets`、`test_skills`、`test_static_names`、`test_ui_edges`；未在本轮越界修复。日志中首项原文为 `storyboard_files.py：remove_selected 里用了没定义的 remove`；`test_ui_edges` 中有 12 条“按一次只该开一块面板”断言失败。

## 用户数据确认

未访问、未创建、未修改 `D:\漫剧下载\` 下任何用户项目；未修改任何项目配置、密钥或用户数据。

## J｜后续

- 不顺手治理用户项目 `logs/*.jsonl`：这需要单独的产品决策与用户数据保留/恢复语义。
- 全量安全自检的 19 个红文件须按各自根因另立轮次处理；在其通过前，R644 不得标记为验收完成。

## 自审

- 只处理 R630 候选 4.2；未改变日志写入格式、阶段执行、项目数据或其他临时目录策略。
- 本轮只触及程序 `logs/`、`维护记录/` 的直接 `.log` 条目；未读取用户项目文件的修改时间或内容。
- 未修改任何用户项目数据、配置或密钥。
