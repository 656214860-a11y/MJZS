# R2006 结果：总控更新提示改为简明可读（功能轮）

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

---

（同号并存：该轮号在 master 与 `codex/wip-R2017` 分支各被占用一次，合并时两份记录都保留。）

# R2006 Pet 播报状态下沉 PetBroadcastState（结构治理轮·执行）

来源：`tasks_round/tasks_round_1983_result.md` J 节 **J5**。日期：2026-10-24。
基线：`codex/wip-R2001` @ ded11f16。零行为变更。

轮次类型：结构治理轮·执行（AGENTS.md §3.3）。三套基线：架构门禁仅剩 3 条已知历史红（`test_agents_md`、`test_round_baselines`、`test_skill_reference_injection`）；默认冒烟 8/8；覆盖率基线同步（315→316 模块）。债务：`--all --safe` 欠账 +1；Pet 共享状态上限 64→59。

## 改动

- 新增 `pet_broadcast_state.py`（L3，无 Tk）：`PetBroadcastState` 持有 `notice`／`last_status`／`announced`／`last_broadcast`／`held_broadcast`／`advance_at`；判重（`remember_status`、`is_repeat`、`spoke`、`forget_spoken`、`new_failure_batch`）、压住（`hold`、`take_held`）、推进节流（`advance_throttled`、`mark_advance`、`reset_advance`）只经这些方法写。`PetBroadcastAliasesMixin` 把旧属性名（含 `_last_broadcast` 等）转发到 `Pet.bstate`，既有调用方与用例不用改；`bstate` 缺失的半成品 Pet 首次访问补默认状态。
- `pet_ui.py`：`Pet.__init__` 改建 `self.bstate`，删四处散落初值；`pet_ui_voice.py`、`pet_ui_view.py`、`pet_ui_stages.py` 的 `say`／`broadcast`／招呼重置／`speech_blocked`／失败批次判重／snooze／unsnooze／`say_held`／推进节流改调状态方法。
- 偏差：`notice`（约 80 处写入）与 `last_status`（状态栏原文）写入面太宽，仍走旧属性名转发，没有逐处改成方法；任务单「只有一个 Mixin 写」在这两项上未做到，只做到判重／压住／节流四类的收口。
- 测试与登记：新增 `tests/test_pet_broadcast_state.py`；`_layers.py` 登记 L3；`test_shared_state_ratchet` Pet 64→59；覆盖率基线（316 模块，`pet_ui`／`pet_ui_stages`／`pet_ui_view`／`pet_ui_voice` 行数校正）与 `runbook.md` §11（316、266）；`architecture.md` 登记。

## 验证（本轮实测，经 gui_hidden）

- 定向 `-k pet_broadcast_state pet_ui sanhu_mode`：618 条，6 条红；同一批 `pet_ui` 在干净 HEAD（临时 worktree）同样 6 条红（5 条登录账号门禁拦截 + `test_the_cloud_stands_left_of_the_pet...` 几何），与本轮改动无关。
- `smoke_test.py --architecture`：410 条，仅 3 条已知红。
- 默认 `smoke_test.py`：8 项通过。
- 未跑 `--all --safe`，欠账 +1。未在真实窗口目测宠物播报。
- **断言未动**。

## 回滚

撤回 `pet_ui*.py` 四个文件、`runbook.md`、`architecture.md`、覆盖率基线、两个架构测试登记；删除 `pet_broadcast_state.py` 与其测试。

## 下一步

J6 Cloud 定位任务（`_position_job`／`_position_callback` 只由 CloudPlaceMixin 写，`pet_cloud_timing.py` 调其方法）。
