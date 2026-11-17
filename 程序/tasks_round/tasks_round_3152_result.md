# R3152 结果（全量红修复第二切片：日志器名与改名替身点）

- 轮次类型：修复轮（分支 `codex/wip-R3152`）。

## 三问

1. **本轮属于 §3 哪种类型？** 修复轮（修合并后后台全量暴露的回归）。
2. **测试跑了吗、三个基线过了吗？** 定向跑了：`test_script_workspace_results`、`test_recycle_directories`、`test_writing_page_services`、`test_rename*`、`test_script_workspace_service` 全部转绿（29 条 0 红）。本轮未跑全量，合并轮 CI 覆盖冒烟与架构。
3. **欠账少了吗？** 少 3 项：`test_script_workspace_results`（3 条）、`test_recycle_directories`（1 条）、`test_writing_page_services`（1 条，R3149 已修，本轮复核仍绿）。

## 根因与修法（全部是包化带来的口径漂移，不是行为退化）

| 现象 | 根因 | 修法 |
| --- | --- | --- |
| `assertLogs('script_workspace_service')` / `assertLogs('projects')` 收不到日志 | 包化后模块名变 `domain.*`，`logging.getLogger(__name__)` 跟着改名 | 日志器名**钉回包化前的稳定标识**（`script_workspace_service`／`projects`），失败路径的可追溯契约不变 |
| 改名失败用例打不出 ERROR | 用例替身点是旧的 `Path.rename`，R3110 起改名走 `agent.core.replace` | 用例替身点同步为 `agent.core.replace`，**断言原意不变**（非法名与同名改都不落盘、SystemError 不泄露系统细节） |
| 被拒绝的改名没有 ERROR 记录 | 该分支只返回 `UserError` 不写日志 | 补 `LOGGER.error('剧本文档重命名被拒绝：…')` |

## 仍未解决

`test_white_model_identity.test_rename_and_move_keep_the_same_directory` 仍红。该用例属白模身份/目录语义，与本任务书的改动无交集，需在干净 master 上复现确认归属（疑为他车道既有红）。
