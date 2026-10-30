# R2100 从下载文件夹收回设定／大纲／角色卡时，覆盖前先备份原文件（修复轮）

轮次类型：修复轮。日期：2026-10-30。分支 `codex/wip-R2100`（`round_claim.py next` 从 `claude/blissful-meninsky-06b9e7` 带出；先领到的 R2096 已被其他会话占用，改领 R2100），基于 master `389007ed`。无对应队列 ID。

- 本轮运行：`run_selftests -k test_idea_download_import test_download_inbox test_media_publish_streaming`（31 条 0 红）、默认 `smoke_test.py`（8/8）、`smoke_test.py --architecture`（410 条，3 红，见下）、`smoke_test.py --affected idea_chat storage_maintenance stage_download_inbox_service stage_execution_service desktop_script_pages desktop_auto_flows`（唯一红项在 `test_writing_api`，见下）。未运行 `--all --safe`。
- `project_status.md` 欠账未减少：本缺陷此前未登记为待办。
- 新增测试，既有断言未动。

## 现象与根因

用户在 Typora 里手改了 `01剧本准备/Google/Google Gemini 4 Argon/创意_20261018/项目大纲/摄影侠_项目大纲_Google_20261018.md`，在剧本准备页点发送后，修改内容全部消失。

- 剧本页刷新时，`desktop_script_pages.refresh_script_workspace` 调用 `idea_chat.import_downloaded_documents`。只要「下载」文件夹里有同项目、同类型、修改时间比项目里该类最新文件更新的 `.md`，就经 `save_reply` 覆盖同一份设定／大纲／角色卡。
- 用户从 Gemini 网页下载了新版 `摄影侠 项目大纲 Google 20261030.md`，它的修改时间比用户手改的文件新，于是 11:45:03 和 11:55:38 两次把用户的修改整份覆盖。宠物事件日志里有「已从下载文件夹更新项目大纲」这一条。
- 发布事务提交后会清掉事务备份，程序里没有旧版本可以恢复。这次靠 Typora 的 `draftsRecover` 快照把文件恢复到 10:35:38 版。
- 同类路径：`stage_download_inbox_service.collect_download_inbox`（每 5 秒一次的下载收件箱）也用 `save_file` 直接覆盖已存在的目标，同样没有备份。

## 修复

- `storage_maintenance.backup_before_overwrite(root, path)`（L1）：把项目内的普通文件**复制**到 `<项目>/工作流任务/覆盖前备份/<时间>_<uuid8>/<原相对路径>`，经 `agent.core.save_file` 原子写入并核对长度，返回副本路径。文件不存在返回 None，越界或是链接就抛错。用复制而不是移进回收站，是因为 `reply_document_path` 要靠现有文件定位跨日期批次的覆盖目标，旧文件一移走，新内容就会落到另一个日期目录。
- `idea_chat.import_downloaded_documents`：目标已存在且正文不同时先备份；备份失败会被既有的 `except (OSError, ValueError)` 接住，这一份不覆盖。新增可选参数 `backups` 列表，用来收集 `(原文件, 副本)`。
- `stage_download_inbox_service.collect_download_inbox`：目标已存在且字节不同时先备份，失败则跳过这一份。新增 `backups` 参数，以及给状态栏用的 `overwrite_backup_notice()`。
- `stage_execution_service.import_downloaded_creatives` 透传 `backups`。`desktop_script_pages.refresh_script_workspace` 和 `desktop_auto_flows._tick_download_inbox` 在状态栏追加「覆盖前的原文件已备份到「…」」。
- 「询问后再覆盖」没有做：刷新和 5 秒收件箱都在后台路径上，弹窗会打断用户。选了「先备份、状态栏告诉用户备份在哪」。

## 先红后绿

改动前（新增 4 条用例）：

```
TypeError: collect_download_inbox() got an unexpected keyword argument 'backups'
AttributeError: <module 'storage_maintenance' ...> does not have the attribute 'backup_before_overwrite'
TypeError: import_downloaded_documents() got an unexpected keyword argument 'backups'   ×2
```

改动后：`共 31 条用例，6.0 秒；0 个文件有红`。

## 基线

- 默认冒烟：8/8。
- 架构门禁：410 条，红 3 条：`test_agents_md.test_performance_history_is_declared_as_historical_only`（ERROR）、`test_round_baselines.test_round_number_continuous`、`test_skill_reference_injection.test_script_stages_name_only_their_approved_00_references`。在 `HEAD`（389007ed）的临时 detached worktree 里单独跑这 3 个模块，红项完全相同，不是本轮引入的。本轮一度碰到 4 条棘轮（`os.replace` 直写、`工作流任务` 字面量、`AutoFlowsMixin` 行数、`stage_execution_service` 行数），都已改代码消除，没有放宽登记。
- `test_writing_api`：本树与 `HEAD` 临时 worktree 都是 63 条、5 个文件红，红项集合相同。`writing_api.py` 不引用本轮改动的任何函数，属既有环境问题（worktree 缺技能子模块），本轮未处理。
- 全量：未运行，由提交后的后台全量补跑。

## 提交

见本轮提交信息（R2100）。
