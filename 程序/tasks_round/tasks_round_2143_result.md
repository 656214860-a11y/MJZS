# R2143 结果：/simplify 审查 2026-10-30 当日改动（简化轮，不改行为）

## 修复
- skill_panel：SKILL 两层根目录改用 `skill_registry.skill_roots(program)`。
- file_cache 新增 `path_key()`；desktop_send_ledger.ledger_path 与 edit_habits.records_path 共用，去掉重复的 sha1 表达式（edit_habits 删掉不再用的 hashlib 导入）。
- desktop_send_ledger.STEP_OF 删掉不会被查到的「当前采用的自然剧本」键。
- download_inbox：删除无生产调用方的 `match()`，docstring 同步；新增 `filename_day()`，idea_chat._filename_day 复用它，删掉重复的 `_FILENAME_DAY` 正则与日期校验。
- codex_paste：`_run` 截止时间只从 payload 取，不再重复传参。
- platform_tools：WebSocket 收发掩码改为 `_apply_mask()` 整段一次异或，替换逐字节生成器。
- desktop_idea_chat.update_idea_attachment_status：明细写入收成 `note()`，显示名每个文件只算一次，`idea_attachment_local_mode` 提到循环外。
- desktop_writing_page.VoiceInput：删掉与顶层重复的 `import time`；`stop()` 去掉没有调用方传的 `message` 参数。
- ui_widgets.BusyState：生产已无进度条，删掉 `progress`／`idle_determinate`／`progress_interval` 分支；调用方 app.py、native_assets.py、pet_models_ui.py、desktop_async_tasks.py 同步；ui_theme 删掉 TProgressbar 样式。

## 测试同步（契约有意变更）
- test_ui_compact_widgets：进度条模式断言改为 Spinner 的 running 开关；status 与控件断言未动。
- test_ui_notifications：假进度条改为假转圈，start/stop 成对断言保留。
- test_video_revision：`BusyState(Mock(), spinner=Mock())`。
- test_download_inbox：两处 `match()` 改调 `match_registered()`，仍断言为空。

## 跳过
- stage_download_inbox_service._same_bytes 改 filecmp：便携运行环境没有 filecmp 模块，已撤回。
- codex_skill_sync 单一 run 入口：test_codex_skill_sync / test_skill_user_layer 锚定无前置时 target 是 sync_codex_skills，已撤回。
- 架构层面的大改（日期批次目录收口、覆盖前备份统一入口、desktop_send_choice 下沉 L3 等）、需重做线程的效率项（收件箱 tick、台账写入后台、启动懒加载等）、reply_document_path 多次调用（需改接口）、误报项：均未动。

## 验证
- 定向自检 515 条全绿（gui_hidden）。
- smoke_test.py 通过。
- smoke_test.py --architecture：仅 worktree 既有红 test_performance_history_is_declared_as_historical_only，行数棘轮全过。
- 未跑全量。
