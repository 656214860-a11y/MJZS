# R2005 结果：总控更新提示改为简明可读（功能轮）

## 问题
手动“检查更新”返回的内容过长：新功能原文整段（含中英两份日志）、每个阶段逐个列文件名，且经状态栏通知显示时换行被压平，读不了。

## 做了什么
- `master_skill_update.describe` 重写：版本变化一行；“新功能”每个版本只一行标题（`feature_title`：版本号＋月-日＋短标题，28 字封顶），最多 4 条，其余写“另有 N 个版本的更新”；各阶段只写“阶段名：N 个文件”；公共文件只写总数。整段摘要约 300 字内。
- `new_log_lines` 只留含中文的日志条目，不再中英各列一遍。
- 新增 `ui_widgets.NoticeDialog`（保留换行、只有“知道了”）；手动检查遇到“只提示、不覆盖”的开发检出时用它展示，不再走会压平换行的状态栏通知。自动检查与有更新的确认窗沿用同一份简明摘要。
- 顺手把早先误入提交的 `tasks_round_2000／2001_result.md` 两个空号结果文件从仓库移除。

## 三问
1. 改了什么：见上；改 master_skill_update／ui_widgets／desktop_master_update，新增 tests/test_notice_dialog.py，扩 tests/test_master_skill_update.py。
2. 验证：定向（master_skill_update 16、notice_dialog、select_placeholder、skill_panel_production_locks）全绿；默认 smoke 8/8；`--architecture` 406 项剩 3 条旧红（agents_md 性能历史、Desktop 类行数 1303>1302、skill_reference_injection）。真实仓库联网摘要生成一次（V7.4.20→V7.4.26）输出为 4 条新功能＋公共文件计数。
   断言有一处契约变更：`test_manual_check_shows_notice_for_notice_only_checkout` 由“notifier.info”改为“NoticeDialog 弹出”，其余断言未动。
3. 未运行：`--all --safe`；真实界面目测弹窗排版。未 push。
