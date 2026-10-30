# R2104 合入 codex/wip-R2098（R2098：下载件日期比登记目标新时另存新日期批次）到 master（合并轮）

轮次类型：合并轮。日期：2026-10-30。把 `codex/wip-R2098` 的 R2098（`886bdf84`）以 `--no-ff` 合入 master `56921394`（R2102）。

- 冲突 3 处，两边改动都保留：
  - `stage_download_inbox_service.collect_download_inbox`：保留 R2100 的 `backup_before_overwrite` 导入与覆盖前备份，循环改用 R2098 的 `match_registered`，按原登记目标销账。
  - `idea_chat.import_downloaded_documents`：保留 R2100 的覆盖前备份，`save_reply` 带上 R2098 的 `at`／`reuse_latest`。另存到新日期批次时目标文件不存在，`backup_before_overwrite` 返回 None，不产生备份。
  - `docs/stages/S01_剧本准备.md`：REQ-S01-62~67 已被 R2092 占用，R2098 的需求改编号为 **REQ-S01-68／DES-S01-68**，测试锚定表同步。R2098 提交信息和 `tasks_round_2098_result.md` 里写的 REQ-S01-62 即本条。
- 本轮运行（主检出，合并后未提交状态，经 `gui_hidden.py`）：`run_selftests -k test_download_inbox test_idea_download_import test_idea_chat test_idea_document test_media_publish_streaming test_storage_maintenance test_script_composer` 186 条，红 1：`test_idea_chat.SendMessageTests.test_uploaded_file_list_survives_send_clear_and_deletes_only_confirmed_copy`。把 4 个合并源文件换回 master 版本后单例运行同样红；合并后代码再整文件跑 `-k test_idea_chat` 两次均 0 红（145 条）。判定为该用例（R2092 附件卡片）的时序不稳，与本次合并无关，未修。默认 `smoke_test.py` 8/8。
- 未运行：`--architecture`、`--all --safe`（由提交后的后台全量补跑）、真实界面目测。
- 断言未动。`project_status.md` 只更新头部当前轮次；债务未减少。
- 用户确认无需恢复项目里已被覆盖的 20261018 大纲。
- 未 push。
